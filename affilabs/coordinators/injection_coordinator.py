"""Injection Coordinator - Handles both automated and manual injection flows.

This coordinator manages the injection workflow for experiments, automatically
routing to manual or automated mode based on hardware configuration and user settings.

MODES:
1. Hardware Auto-Detection (legacy):
   - P4SPR without pump → manual injection
   - P4SPR with pump or P4PRO → automated injection

2. Per-Cycle User Selection:
   - User explicitly sets cycle.manual_injection_mode = "manual" or "automated"
   - Overrides hardware defaults

MANUAL INJECTION FLOW:
- InjectionActionBar is shown inline in the sidebar (non-blocking UI)
- One _InjectionMonitor per channel runs until injection is detected, then self-stops
- Channel LEDs update as each event is detected (yellow → green)
- Background thread blocks on threading.Event until detection confirmed on expected channels
- Returns detection results (channel, time, confidence) to coordinator

HARDWARE MODES:
- P4SPR + No Pump → Manual injection (dialog shown)
- P4SPR + AffiPump → Automated injection (pump controlled)
- P4PRO/P4PROPLUS → Automated injection (internal pumps)

USAGE:
    from affilabs.coordinators.injection_coordinator import InjectionCoordinator

    coordinator = InjectionCoordinator(hardware_mgr, pump_mgr, parent=main_window)
    coordinator.execute_injection(cycle, flow_rate=100.0, parent_widget=window)

    coordinator.injection_completed.connect(on_injection_done)
    coordinator.injection_cancelled.connect(on_injection_cancelled)
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import TYPE_CHECKING, Optional

import numpy as np

from PySide6.QtCore import QObject, QTimer, Signal

from affilabs.utils.logger import logger
from affilabs.utils.sample_parser import parse_sample_info

if TYPE_CHECKING:
    from affilabs.core.hardware_manager import HardwareManager
    from affilabs.core.data_acquisition_manager import DataAcquisitionManager
    from affilabs.domain.cycle import Cycle
    from affilabs.managers.pump_manager import PumpManager

# Fluidic path dead volume from loop outlet to sensor (P4PRO/PROPLUS geometry, µL).
# Transit delay = FLUIDIC_PATH_VOLUME_UL / flow_rate_ul_per_min * 60.0 seconds.
# Must match the constant of the same name in manual_injection_dialog.py.
FLUIDIC_PATH_VOLUME_UL = 8.0


class _InjectionMonitor(QObject):
    """Per-channel injection detector.

    Runs continuously from cycle start until stopped. Detects a single
    threshold crossing (injection event) then self-stops.

    Algorithm (every POLL_INTERVAL_S = 2 seconds):

    Step 1 — Quality gate:
        win_pre = spr[-(2*W):-W]  (5-frame window ending 5 frames ago)
        baseline_std = std(win_pre).  If > STD_MAX_RU (≈20 RU):
            emit readiness_update("CHECK", "Flush channel — signal unstable")
            return  ← do not attempt detection on a noisy channel

    Step 2 — Adaptive threshold:
        threshold = max(HARD_MIN_RU, SIGMA × baseline_std)

    Stage 1 — _detect_spike():
        p2p = ptp(spr[-(2*W):])   (10-frame window, direction-agnostic)
        If p2p > max(HARD_MIN_RU, 5σ × baseline_std): confirm_count += 1
        Confirmed after CONFIRM_FRAMES consecutive polls above threshold.

    Stage 2 — deferred pre/post triage (5 polls = 5s):
        On spike confirm: snapshot pre-window (last 5 optical frames), collect 5 more.
        Then compare pre vs post across 4 optical signals (cascade, highest priority first):
        POSSIBLE_LEAK   — raw_peak collapses ≥75% (intensity wipeout)
        POSSIBLE_BUBBLE — %T drops ≥10pp AND FWHM broadens ≥30%
        CHIP_DEGRADED   — FWHM broadens ≥30% without %T drop
        SIGNAL_SPIKE    — transient: SPR mean returns to pre-spike level
        INJECTION       — none of the above → sustained binding event → advance fire_count

        fire_count semantics (owned by _InjectionSession, not this class):
          #1 = sample injection  |  #2 = wash  |  #3+ = stop monitoring

    Parallel — _check_leak():
        Not spike-triggered. Sustained %T drop >2% for >30s → POSSIBLE_LEAK.
    """

    injection_detected = Signal(str, float)  # channel (upper), cycle-relative time (s)
    anomaly_detected   = Signal(str, str)    # flag ('POSSIBLE_BUBBLE'), channel
    readiness_update   = Signal(str, str)    # verdict ('READY'/'WAIT'/'CHECK'), message

    POLL_INTERVAL_S = 1       # seconds between polls (1 Hz data → catch every frame)
    WINDOW_FRAMES   = 3       # frames per rolling window (~3s at 1 Hz — fast reaction)
    MIN_PTS         = 6       # need 2 × WINDOW_FRAMES before detecting
    HARD_MIN_RU     = 10.0    # absolute floor — reject crosstalk (<10 RU) from adjacent channels

    # Tunable constants — override via settings.py
    try:
        from settings import INJECTION_DETECTION_SIGMA as SIGMA
        from settings import INJECTION_CONFIRM_FRAMES  as CONFIRM_FRAMES
        from settings import INJECTION_STD_MAX_NM      as STD_MAX_NM
        from settings import INJECTION_DEAD_ZONE_S     as DEAD_ZONE_S
    except ImportError:
        SIGMA          = 3.0
        CONFIRM_FRAMES = 2
        STD_MAX_NM     = 0.056
        DEAD_ZONE_S    = 15.0
    # STD_MAX in RU (converted from nm threshold used in readiness check only)
    STD_MAX_RU = STD_MAX_NM * 355

    def __init__(self, channel: str, buffer_mgr, parent=None, contact_time_s: float | None = None):
        super().__init__(parent)
        self._ch           = channel.lower()
        self._ch_upper     = channel.upper()
        self._buffer_mgr   = buffer_mgr
        self._contact_time_s = contact_time_s  # cycle contact time (seconds)
        self._confirm_count = 0
        self._stopped       = False
        self._fire_count    = 0              # 0=idle, 1=injection fired
        self._last_fire_at  = 0.0           # monotonic time of last fire
        self._last_anomaly  = ''
        self._poll_count    = 0
        self._thread: threading.Thread | None = None
        # Leak detection: %T drops >2% and stays down >30s
        self._transmittance_ref: float | None = None   # mean %T from first WINDOW_FRAMES
        self._leak_polls_below: int = 0                # consecutive polls with %T suppressed
        self._leak_fired: bool = False
        # Deferred triage state — pre/post 5-point optical window
        self._triage_pending: bool = False             # True while collecting post-window
        self._triage_pre: list = []                    # pre-event optical snapshot (5 frames)
        self._triage_t_fire: float = 0.0              # onset time captured at spike confirm
        self._triage_p2p: float = 0.0                 # p2p at spike confirm
        self._triage_threshold: float = 0.0           # threshold at spike confirm
        self._triage_post_polls: int = 0              # polls collected since triage started

    def start(self) -> None:
        self._stopped = False
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name=f"InjectionMonitor-{self._ch_upper}",
        )
        self._thread.start()
        logger.debug(f"InjectionMonitor started for channel {self._ch_upper}")

    def stop(self) -> None:
        self._stopped = True
        logger.debug(f"InjectionMonitor stopped for channel {self._ch_upper}")

    def _run_loop(self) -> None:
        import time as _time
        while not self._stopped:
            try:
                self._poll()
            except Exception:
                logger.exception(f"InjectionMonitor {self._ch_upper}: unhandled error in _poll")
            _time.sleep(self.POLL_INTERVAL_S)

    def _poll(self) -> None:
        if self._stopped:
            return

        import time as _time
        self._poll_count += 1

        # Dead zone — skip polls immediately after a fire to absorb biphasic artifact.
        # After fire #1 (injection), extend dead zone to 80% of the contact time so
        # binding-kinetics signal changes are not misclassified as wash events.
        if self._last_fire_at > 0:
            if self._fire_count >= 1 and self._contact_time_s:
                wash_deadzone = max(self.DEAD_ZONE_S, 0.80 * self._contact_time_s)
            else:
                wash_deadzone = self.DEAD_ZONE_S
            if _time.monotonic() - self._last_fire_at < wash_deadzone:
                return

        # Fetch cycle-relative ΔSPR (RU) — this is what the Active Cycle graph plots.
        # cycle_data[ch].spr is zeroed at the cycle start cursor, same reference as the graph.
        try:
            cd = self._buffer_mgr.cycle_data.get(self._ch)
        except Exception as _e:
            logger.debug(f"InjectionMonitor {self._ch_upper}: buffer read error: {_e}")
            return
        if cd is None or len(cd.spr) < self.MIN_PTS:
            if self._poll_count % 5 == 1:
                n = 0 if cd is None else len(cd.spr)
                logger.debug(f"InjectionMonitor {self._ch_upper}: waiting for data ({n}/{self.MIN_PTS} pts)")
            return

        spr = np.asarray(cd.spr, dtype=float)  # ΔSPR in RU, zeroed at cycle start

        W = self.WINDOW_FRAMES
        win_pre = spr[-(2 * W):-W]

        # Baseline noise from the OLDER half of the 2W window (pre-spike).
        # Using win_pre instead of spr[-W:] is critical: if the injection
        # front lands in the last W frames, std(spr[-W:]) would spike and
        # either block the quality gate or inflate the adaptive threshold,
        # adding several seconds of detection delay.
        baseline_std_ru = float(np.std(win_pre))
        if baseline_std_ru > self.STD_MAX_RU:
            self.readiness_update.emit("CHECK", "Flush channel — signal unstable")
            self._confirm_count = 0
            return

        threshold = max(self.HARD_MIN_RU, self.SIGMA * baseline_std_ru)

        # Stage 1 — spike detector
        # If a triage is already pending, collect post-window frames instead of
        # running the spike detector again — avoids re-triggering on the same event.
        if self._triage_pending:
            self._triage_post_polls += 1
            if self._triage_post_polls >= 5:
                self._resolve_triage(cd)
            return

        spike_p2p = self._detect_spike(spr, W)
        exceeded  = spike_p2p > threshold

        if self._poll_count % 15 == 0:
            logger.debug(
                f"InjectionMonitor {self._ch_upper}: fire={self._fire_count} "
                f"pts={len(spr)} spr={spr[-1]:.1f}RU "
                f"p2p={spike_p2p:.1f}RU thresh={threshold:.1f}RU std={baseline_std_ru:.1f}RU"
            )

        if exceeded:
            self._confirm_count += 1
            if self._confirm_count >= self.CONFIRM_FRAMES:
                times  = np.asarray(cd.time, dtype=float)
                t_fire = self._find_onset_time(spr, times, W)
                # Snapshot pre-window and start collecting post-window (deferred triage)
                self._start_triage(t_fire, spike_p2p, threshold)
        else:
            self._confirm_count = 0

        # Leak monitor — sustained %T suppression, not spike-triggered (FRS §6b.1)
        self._check_leak(cd)

        # Readiness update — only while waiting for first injection
        if self._fire_count == 0:
            try:
                from affilabs.utils.signal_event_classifier import SignalEventClassifier
                iq_metrics = getattr(cd, 'iq_metrics_latest', None) or {}
                _p2p_ru   = float(np.ptp(spr[-5:])) if len(spr) >= 5 else 0.0
                _slope_ru = float(np.polyfit(np.arange(5), spr[-5:], 1)[0]) if len(spr) >= 5 else 0.0
                readiness = SignalEventClassifier.check_readiness(
                    slope_5s_ru=_slope_ru,
                    p2p_5frame_ru=_p2p_ru,
                    iq_level=str(iq_metrics.get('iq_level', '')),
                )
                self.readiness_update.emit(readiness.verdict, readiness.message)
            except Exception:
                pass

    # ── Stage 1: spike detector ───────────────────────────────────────────────

    def _detect_spike(self, spr: np.ndarray, W: int) -> float:
        """Return p2p of the combined 2W window.

        Pure threshold input — direction-agnostic. Caller compares against
        adaptive threshold (5σ × baseline_std). No classification here.
        """
        return float(np.ptp(spr[-(2 * W):]))

    # ── Onset time finder ─────────────────────────────────────────────────────

    def _find_onset_time(self, spr: np.ndarray, times: np.ndarray, W: int) -> float:
        """Find the actual injection onset within the 2W detection window.

        Called after _detect_spike confirms p2p > threshold.  Instead of using
        ``times[-1]`` (the latest frame — causes ~5 s placement delay), scan
        the 10-frame window to find where the signal first departs from the
        pre-spike baseline.

        Algorithm:
            1. Baseline = mean/std of the first W frames in the 2W window
            2. Determine shift direction (rising = injection, falling = wash)
            3. Scan forward from frame W to find first frame exceeding
               base_mean ± onset_threshold
            4. onset_threshold = max(1.5 × baseline_std, 2.0 RU) — sensitive,
               because the spike is already confirmed

        Returns cycle-time (same timebase as cd.time) of the estimated onset.
        """
        if len(spr) < 2 * W or len(times) < 2 * W:
            return float(times[-1])

        win_spr = np.asarray(spr[-(2 * W):], dtype=float)
        win_t   = np.asarray(times[-(2 * W):], dtype=float)

        base_mean = float(np.mean(win_spr[:W]))
        base_std  = float(np.std(win_spr[:W]))

        post_mean = float(np.mean(win_spr[W:]))
        onset_delta = max(1.5 * base_std, 2.0)

        if post_mean >= base_mean:
            # Rising — injection binding (red-shift)
            for i in range(W, len(win_spr)):
                if win_spr[i] - base_mean > onset_delta:
                    return float(win_t[i])
        else:
            # Falling — wash or unusual event
            for i in range(W, len(win_spr)):
                if base_mean - win_spr[i] > onset_delta:
                    return float(win_t[i])

        # Fallback — start of post-baseline region
        return float(win_t[W])

    # ── Stage 2: deferred pre/post triage ────────────────────────────────────

    def _start_triage(self, t_fire: float, p2p: float, threshold: float) -> None:
        """Snapshot the pre-event optical window and begin collecting post-window.

        Called immediately when CONFIRM_FRAMES consecutive polls exceed threshold.
        The actual classification fires 5 polls later in _resolve_triage().
        """
        try:
            from affilabs.services.signal_telemetry_logger import SignalTelemetryLogger
            pre = SignalTelemetryLogger.get_instance().get_optical_snapshot(self._ch)
        except Exception:
            pre = []

        self._triage_pending    = True
        self._triage_pre        = pre
        self._triage_t_fire     = t_fire
        self._triage_p2p        = p2p
        self._triage_threshold  = threshold
        self._triage_post_polls = 0
        self._confirm_count     = 0

        logger.debug(
            f"[InjectionMonitor] {self._ch_upper} triage started — "
            f"t={t_fire:.1f}s p2p={p2p:.1f}RU pre_frames={len(pre)}"
        )

    def _resolve_triage(self, cd) -> None:
        """Collect post-window and run the 4-step triage cascade.

        Called 5 polls after _start_triage(). Compares pre vs post optical
        windows to distinguish LEAK / BUBBLE / CHIP_DEGRADED / INJECTION.
        """
        self._triage_pending = False

        try:
            from affilabs.services.signal_telemetry_logger import SignalTelemetryLogger
            from affilabs.utils.signal_event_classifier import check_event_triage
            post = SignalTelemetryLogger.get_instance().get_optical_snapshot(self._ch)
            label_triage = check_event_triage(self._triage_pre, post)
        except Exception:
            label_triage = "INJECTION"

        label_map = {
            "LEAK":          "POSSIBLE_LEAK",
            "BUBBLE":        "POSSIBLE_BUBBLE",
            "CHIP_DEGRADED": "CHIP_DEGRADED",
            "INJECTION":     "INJECTION",
        }
        label = label_map.get(label_triage, "INJECTION")

        # Transient check — SPR returned to baseline → noise spike, not a real event
        try:
            spr_arr = np.asarray(cd.spr, dtype=float)
            W = self.WINDOW_FRAMES
            if len(spr_arr) >= 3 * W:
                pre_mean  = float(np.mean(spr_arr[-(3 * W):-(2 * W)]))
                post_mean = float(np.mean(spr_arr[-W:]))
                if abs(post_mean - pre_mean) < self.HARD_MIN_RU:
                    label = "SIGNAL_SPIKE"
        except Exception:
            pass

        logger.info(
            f"[InjectionMonitor] {self._ch_upper} triage resolved → {label} "
            f"t={self._triage_t_fire:.1f}s p2p={self._triage_p2p:.1f}RU"
        )
        self._fire(self._triage_t_fire, self._triage_p2p, self._triage_threshold, label)

    def _fire(self, t_fire: float, p2p: float, threshold: float, label: str) -> None:
        import time as _time
        self._fire_count   += 1
        self._last_fire_at  = _time.monotonic()
        self._confirm_count = 0

        logger.info(
            f"[InjectionMonitor] {self._ch_upper} spike classified={label} "
            f"t={t_fire:.1f}s p2p={p2p:.1f}RU thresh={threshold:.1f}RU "
            f"(fire #{self._fire_count})"
        )

        if label == 'SIGNAL_SPIKE':
            # Noise — log only, do not advance injection state
            self._fire_count -= 1   # undo increment — noise doesn't count
            self.anomaly_detected.emit('SIGNAL_SPIKE', self._ch_upper)
            return

        if label in ('POSSIBLE_BUBBLE', 'POSSIBLE_LEAK', 'CHIP_DEGRADED'):
            # Fault — emit anomaly, do not advance injection state
            self._fire_count -= 1
            if label != self._last_anomaly:
                self._last_anomaly = label
                self.anomaly_detected.emit(label, self._ch_upper)
            return

        # INJECTION — advance state (fire #1 = sample, fire #2 = wash, #3+ ignored by session)
        self._last_anomaly = ''
        self.injection_detected.emit(self._ch_upper, t_fire)

    def _check_leak(self, cd) -> None:
        """POSSIBLE_LEAK: mean %T drops >2% from reference and stays down >30s."""
        if self._leak_fired:
            return
        try:
            tx = getattr(cd, 'transmittance', None)
            if tx is None or len(tx) < self.WINDOW_FRAMES:
                return
            tx_arr = np.asarray(tx, dtype=float)
            if self._transmittance_ref is None:
                self._transmittance_ref = float(np.mean(tx_arr[:self.WINDOW_FRAMES]))
                return
            current_tx = float(np.mean(tx_arr[-self.WINDOW_FRAMES:]))
            drop_frac = (self._transmittance_ref - current_tx) / max(self._transmittance_ref, 1e-6)
            # Each poll = POLL_INTERVAL_S=2s; need >30s → >15 consecutive polls below threshold
            if drop_frac > 0.02:
                self._leak_polls_below += 1
                if self._leak_polls_below > (30 // self.POLL_INTERVAL_S):
                    self._leak_fired = True
                    logger.warning(
                        f"[InjectionMonitor] {self._ch_upper} POSSIBLE_LEAK: "
                        f"%T dropped {drop_frac*100:.1f}% from ref={self._transmittance_ref:.1f}% "
                        f"sustained >{self._leak_polls_below * self.POLL_INTERVAL_S}s"
                    )
                    self.anomaly_detected.emit("POSSIBLE_LEAK", self._ch_upper)
                    try:
                        from affilabs.services.signal_quality_scorer import SignalQualityScorer
                        SignalQualityScorer.get_instance().notify_leak_detected()
                    except Exception:
                        pass
            else:
                self._leak_polls_below = 0
        except Exception:
            pass



class _InjectionSession:
    """Owns the full manual-injection lifecycle for one cycle.

    Created by InjectionCoordinator._execute_manual_injection(), run on the
    background "ManualInjectionExec" thread.  All UI callbacks are marshalled
    to the main thread via coordinator._invoke_on_main.

    Lifecycle
    ---------
    run() → blocks until one of:
      • all expected channels detected + (wash done or no contact_time)  → accepted=True
      • user cancels                                                      → accepted=False
      • timeout                                                           → accepted=True (partial)
    """

    def __init__(
        self,
        coordinator,
        cycle,
        sample_info:        dict,
        bar,
        parent_widget,
        injection_num,
        total_injections,
        method_mode,
        pump_transit_delay_s: float,
    ):
        self._coord              = coordinator
        self._cycle              = cycle
        self._sample_info        = sample_info
        self._bar                = bar
        self._parent_widget      = parent_widget
        self._injection_num      = injection_num
        self._total_injections   = total_injections
        self._method_mode        = method_mode
        self._transit_delay_s    = pump_transit_delay_s

        self._detection_channels: str = coordinator._detection_channels
        self._is_p4spr: bool          = coordinator._is_p4spr
        self._buffer_mgr              = coordinator.buffer_mgr
        self._invoke_on_main          = coordinator._invoke_on_main

        self._has_contact_time = bool(getattr(cycle, 'contact_time', None))
        self._contact_time_val = getattr(cycle, 'contact_time', None)

        self._done_event  = threading.Event()
        self._accepted    = False

        self.dialog = None                           # set on main thread in _setup()
        self._monitors: dict[str, _InjectionMonitor] = {}
        self._fire_counts: dict[str, int] = {}       # per-channel fire counter (1=injection, 2=wash)
        self._flags_placed: set[str] = set()         # channels whose flag was already placed (prevents double-placement)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(self) -> bool:
        """Block the calling BG thread until the lifecycle completes. Returns accepted flag."""
        detection_timeout = 95 if self._has_contact_time else 300
        contact_margin    = (int(self._contact_time_val) + 120) if self._has_contact_time else 0
        total_timeout     = detection_timeout + contact_margin

        # Wrap _setup so _run_on_main_thread can call _done_event_setter on exception.
        done_set = self._done_event.set
        def setup_fn():
            self._setup()
        setup_fn._done_event_setter = done_set
        self._invoke_on_main.emit(setup_fn)

        timed_out = not self._done_event.wait(timeout=total_timeout)
        if timed_out:
            logger.warning(
                f"Injection lifecycle timed out after {total_timeout}s "
                f"(contact_time={self._contact_time_val}) — forcing cleanup"
            )
            bar = self._bar
            QTimer.singleShot(0, lambda: self._on_timeout(bar))

        return self._accepted

    # ------------------------------------------------------------------
    # Main-thread setup
    # ------------------------------------------------------------------

    def _setup(self) -> None:
        """Create dialog, show bar, start monitors — runs on main thread."""
        from affilabs.dialogs.manual_injection_dialog import ManualInjectionDialog
        self.dialog = ManualInjectionDialog(
            self._sample_info,
            parent            = self._parent_widget,
            injection_number  = self._injection_num,
            total_injections  = self._total_injections,
            buffer_mgr        = self._buffer_mgr,
            channels          = self._detection_channels,
            detection_priority= getattr(self._cycle, 'detection_priority', 'auto'),
            method_mode       = self._method_mode,
            pump_transit_delay_s = self._transit_delay_s,
        )
        self.dialog.injection_cancelled.connect(self._on_cancelled)

        if self._bar is not None:
            self._bar.show_monitoring(
                channels      = self._detection_channels,
                on_done       = self._on_bar_done,
                on_cancel     = self._on_cancelled,
                contact_time  = self._contact_time_val,
                buffer_mgr    = self._buffer_mgr,
                keep_alive    = self._is_p4spr,
                concentrations= getattr(self._cycle, 'concentrations', {}) or {},
                conc_units    = getattr(self._cycle, 'units', None) or getattr(self._cycle, 'concentration_units', 'nM') or 'nM',
            )

        for ch in self._detection_channels.upper():
            self._start_monitor(ch)

    # ------------------------------------------------------------------
    # Monitor management
    # ------------------------------------------------------------------

    def _start_monitor(self, ch: str) -> None:
        if self._buffer_mgr is None or self._bar is None:
            logger.warning(f"InjectionMonitor {ch}: skipped — buffer_mgr or bar is None")
            return
        if ch in self._monitors:
            return
        ct_s = None
        try:
            ct_s = float(self._contact_time_val) if self._contact_time_val else None
        except (TypeError, ValueError):
            pass
        monitor = _InjectionMonitor(channel=ch, buffer_mgr=self._buffer_mgr, parent=self._bar, contact_time_s=ct_s)
        inv = self._invoke_on_main
        monitor.injection_detected.connect(
            lambda c, t, _inv=inv: _inv.emit(lambda c=c, t=t: self._on_detected(c, t))
        )
        monitor.anomaly_detected.connect(
            lambda flag, c, _inv=inv: _inv.emit(lambda f=flag, c=c: self._on_anomaly(f, c))
        )
        monitor.readiness_update.connect(self._bar.update_readiness)
        self._monitors[ch] = monitor
        monitor.start()

    def _stop_all_monitors(self) -> None:
        for m in list(self._monitors.values()):
            m.stop()
        self._monitors.clear()

    # ------------------------------------------------------------------
    # Event handlers — all run on main thread
    # ------------------------------------------------------------------

    def _on_detected(self, ch_upper: str, approx_t: float) -> None:
        """Handle monitor fire — route to injection (fire #1) or wash (fire #2+) handler."""
        if self.dialog is None:
            logger.warning(f"InjectionMonitor {ch_upper}: fire at t={approx_t:.1f}s dropped — dialog not ready")
            return
        self._fire_counts[ch_upper] = self._fire_counts.get(ch_upper, 0) + 1
        fire_num = self._fire_counts[ch_upper]
        if fire_num == 1:
            self._handle_injection(ch_upper, approx_t)
        else:
            self._handle_wash(ch_upper, approx_t, fire_num)

    def _handle_injection(self, ch_upper: str, approx_t: float) -> None:
        d = self.dialog
        if ch_upper not in d._detected_channels_results:
            d._detected_channels_results[ch_upper] = {'time': approx_t, 'confidence': 0.80}
        if d.detected_injection_time is None:
            d.detected_injection_time = approx_t
            d.detected_channel        = ch_upper.lower()
            d.detected_confidence     = 0.80

        if self._bar is not None:
            self._bar.update_channel_detected(ch_upper, detected=True)

        # ── Fast path: place flag + start timer immediately, before BG thread unblocks ──
        # We are already on the main thread (via _invoke_on_main), so emitting here is safe.
        # The guard set prevents the later post-_done_event emission from double-placing.
        if ch_upper not in self._flags_placed:
            self._flags_placed.add(ch_upper)
            self._coord.injection_flag_requested.emit(
                ch_upper.lower(), approx_t, 0.80
            )

        # Unblock BG thread after first detected channel on P4SPR — cycle timer is already
        # running, user is still pipetting remaining channels sequentially (up to ~15s apart).
        # Monitors keep running after _on_detection_complete fires, so subsequent channels
        # are still detected and stored in _detected_channels_results for flag placement.
        # P4PRO/PROPLUS: wait for all expected channels before unblocking (simultaneous injection).
        found    = set(d._detected_channels_results.keys())
        complete = (len(found) >= 1 if self._is_p4spr
                    else set(self._detection_channels.upper()).issubset(found))
        if complete:
            QTimer.singleShot(0, self._on_detection_complete)


    def _handle_wash(self, ch_upper: str, approx_t: float, fire_num: int) -> None:
        """Handle fire #2+ on P4SPR.

        Fire #2 = wash (buffer flushing sample off) → transition channel to WASH state.
        Fire #3 = next injection → reset bar to PENDING and treat as a new injection.
        """
        if fire_num == 2:
            logger.info(f"[InjectionSession] {ch_upper} wash detected at t={approx_t:.1f}s")
            if self._bar is not None:
                try:
                    self._bar.set_channel_wash(ch_upper)
                except Exception:
                    pass
            try:
                from affilabs.services.signal_quality_scorer import SignalQualityScorer
                SignalQualityScorer.get_instance().notify_wash_detected(ch_upper)
            except Exception:
                pass
        else:
            # Fire #3+ = next injection after wash — reset bar and treat as fresh injection
            logger.info(f"[InjectionSession] {ch_upper} next injection at t={approx_t:.1f}s (fire #{fire_num}) — resetting bar")
            # Reset fire counts so the cycle starts clean (this fire becomes the new #1)
            for k in list(self._fire_counts.keys()):
                self._fire_counts[k] = 0
            self._fire_counts[ch_upper] = 1
            if self._bar is not None:
                try:
                    self._bar.reset_for_next_injection()
                except Exception:
                    pass
            # Now handle this as a fresh injection
            self._handle_injection(ch_upper, approx_t)

    def _on_anomaly(self, flag: str, ch_upper: str) -> None:
        # Notify quality scorer so fault impacts cycle score
        try:
            from affilabs.services.signal_quality_scorer import SignalQualityScorer
            scorer = SignalQualityScorer.get_instance()
            if flag == 'CHIP_DEGRADED':
                scorer.notify_chip_degraded()
            elif flag == 'POSSIBLE_LEAK':
                scorer.notify_leak_detected()
        except Exception:
            pass

        try:
            mw      = getattr(self._parent_widget, 'main_window', self._parent_widget)
            bar_ref = getattr(mw, 'unified_cycle_bar', None)
            if bar_ref is None:
                return
            from affilabs.widgets.unified_cycle_bar import CycleBarState
            if bar_ref.state == CycleBarState.INJECT:
                bar_ref.set_inject_anomaly(flag, ch_upper)
            else:
                bar_ref.set_anomaly(flag, ch_upper, restore_fn=None)
        except Exception:
            pass

    def _on_detection_complete(self) -> None:
        """Injection detected — unblock BG thread immediately.
        P4SPR: keep monitors alive so fire #2 (manual buffer flush = wash) is caught.
        P4PRO/PROPLUS: stop monitors now — injection is automated, no manual wash step.
        """
        self._accepted = True
        if not self._is_p4spr:
            self._stop_all_monitors()
        self._done_event.set()

    def _on_bar_done(self) -> None:
        self._accepted = True
        self._stop_all_monitors()
        if self._bar is not None:
            self._bar.set_panel_active(False)
        if not self._done_event.is_set():
            self._done_event.set()

    def _on_cancelled(self) -> None:
        self._accepted = False
        self._stop_all_monitors()
        if self._bar is not None:
            self._bar.set_panel_active(False)
        self._done_event.set()

    def _on_timeout(self, bar) -> None:
        self._stop_all_monitors()
        if bar is not None:
            bar.set_panel_active(False)
            bar.show_injection_missed()


class InjectionCoordinator(QObject):
    """Coordinates injection workflows - automated or manual based on hardware.

    Responsibilities:
    - Detect injection mode (manual vs automated)
    - Show ManualInjectionDialog for manual injection with real-time detection
    - Execute automated injections via PumpManager
    - Handle valve control for manual injections
    - Log injection events differently based on mode

    Signals:
        injection_started: Injection sequence started (arg: injection_type str)
        injection_completed: Injection completed successfully
        injection_cancelled: User cancelled manual injection
        injection_flag_requested: Place injection flag (args: channel, injection_time, confidence)
    """

    injection_started = Signal(str)  # injection_type
    injection_completed = Signal()
    injection_cancelled = Signal()
    injection_flag_requested = Signal(str, float, float)  # channel, injection_time, confidence
    _invoke_on_main = Signal(object)  # cross-thread callable invocation

    def __init__(
        self,
        hardware_mgr: HardwareManager,
        pump_mgr: PumpManager,
        buffer_mgr: Optional[DataAcquisitionManager] = None,
        parent=None,
    ):
        """Initialize injection coordinator.

        Args:
            hardware_mgr: Hardware manager for valve control and mode detection
            pump_mgr: Pump manager for automated injections
            buffer_mgr: Data acquisition manager for real-time sensorgram monitoring (optional)
            parent: Parent QObject for Qt hierarchy
        """
        super().__init__(parent)
        self.hardware_mgr = hardware_mgr
        self.pump_mgr = pump_mgr
        self.buffer_mgr = buffer_mgr

        # Cross-thread invocation: emit from bg thread → runs on main thread
        self._invoke_on_main.connect(self._run_on_main_thread)

        # State for manual injection flow
        self._detection_channels: str = "ABCD"
        self._current_cycle: Optional[Cycle] = None
        self._is_p4spr: bool = False
        self._active_session: Optional["_InjectionSession"] = None

    def cleanup_monitors(self) -> None:
        """Stop any active injection monitors — called from cycle_mixin on cycle end."""
        s = self._active_session
        if s is not None:
            s._stop_all_monitors()
            self._active_session = None

    def reset_cycle_state(self) -> None:
        """Full state wipe between cycles — nothing carries over.

        Called from ``_on_cycle_completed`` after ``cleanup_monitors``.
        Clears detection channels, current-cycle reference, and any
        session-level artefacts so the next cycle starts fresh.
        """
        self.cleanup_monitors()
        self._detection_channels = "ABCD"
        self._current_cycle = None
        self._is_p4spr = False

    def _run_on_main_thread(self, fn) -> None:
        """Execute a callable on the main thread (slot for _invoke_on_main signal)."""
        try:
            fn()
        except Exception as e:
            import traceback
            logger.error(f"_run_on_main_thread failed: {e}\n{traceback.format_exc()}")
            # fn carries a done_event_setter — call it to prevent the BG thread blocking forever
            setter = getattr(fn, '_done_event_setter', None)
            if setter is not None:
                setter()

    def execute_injection(
        self,
        cycle: Cycle,
        flow_rate: float,
        parent_widget=None,
    ) -> bool:
        """Execute injection for cycle - manual or automated based on hardware and user settings.

        This is the single entry point for all injection requests. The coordinator:
        1. Checks if cycle explicitly sets manual_injection_mode
        2. Falls back to hardware auto-detection (P4SPR without pump = manual)
        3. Shows concentration schedule dialog if cycle has planned_concentrations
        4. Routes to appropriate execution method

        NOTE: Manual mode is NON-BLOCKING. The method returns True immediately and
        the actual result comes via injection_completed / injection_cancelled signals.

        Args:
            cycle: Cycle requiring injection
            flow_rate: Flow rate in µL/min
            parent_widget: Parent widget for dialog positioning

        Returns:
            True if injection initiated successfully, False if cancelled at schedule stage
        """
        # Determine injection mode: explicit setting takes precedence
        is_manual_mode = self._determine_injection_mode(cycle)

        # NOTE: Schedule dialog (ConcentrationScheduleDialog) is now shown earlier
        # in main.py _schedule_injection() with a 20s countdown, so we skip it here.

        # Execute appropriate injection mode
        if is_manual_mode:
            return self._execute_manual_injection(cycle, parent_widget, flow_rate=flow_rate)
        else:
            return self._execute_automated_injection(cycle, flow_rate)

    def _determine_injection_mode(self, cycle: Cycle) -> bool:
        """Determine if manual injection mode should be used.

        Priority order:
        1. Explicit cycle.manual_injection_mode setting
        2. Hardware auto-detection (P4SPR without pump = manual)

        Args:
            cycle: Cycle to check

        Returns:
            True if manual mode, False if automated mode
        """
        # If cycle explicitly sets mode, use that
        if cycle.manual_injection_mode == "manual":
            return True
        elif cycle.manual_injection_mode == "automated":
            return False

        # Fall back to hardware detection
        return self.hardware_mgr.requires_manual_injection

    def _execute_manual_injection(self, cycle: Cycle, parent_widget, flow_rate: float = 0.0) -> bool:
        """Execute manual injection — delegates to _InjectionSession."""
        logger.info("=== Manual Injection Mode (Non-Blocking) ===")

        sample_info = parse_sample_info(cycle)
        self._is_p4spr = self.hardware_mgr._ctrl_type == "PicoP4SPR"
        if self._is_p4spr:
            sample_info["channels"] = None
        self._detection_channels = self._resolve_detection_channels(cycle, sample_info)
        self._current_cycle = cycle

        logger.info(f"  Sample: {sample_info['sample_id']}")
        if not self._is_p4spr:
            logger.info(f"  Channels: {sample_info['channels']}")
            self._open_valves_for_manual_injection(sample_info["channels"])
        if sample_info["concentration"]:
            logger.info(f"  Concentration: {sample_info['concentration']} {sample_info['units']}")

        injection_num = total_injections = None
        if cycle.type in ("Binding", "Kinetic", "Concentration") and cycle.planned_concentrations:
            injection_num    = cycle.injection_count + 1
            total_injections = len(cycle.planned_concentrations)
            logger.info(f"  {cycle.type} Cycle: Injection {injection_num}/{total_injections}")

        method_mode = getattr(cycle, 'method_mode', None)

        pump_transit_delay_s = 0.0
        if method_mode in ('semi-automated', 'pump'):
            active_fr = getattr(cycle, 'flow_rate', None) or flow_rate
            if active_fr and active_fr > 0:
                pump_transit_delay_s = FLUIDIC_PATH_VOLUME_UL / active_fr * 60.0
                logger.info(f"  Pump transit delay: {pump_transit_delay_s:.1f}s")

        if method_mode in ('pump', 'semi-automated'):
            logger.info(f"  Pump mode ({method_mode}) — skipping detection")
            self._close_valves_after_manual_injection()
            self.injection_completed.emit()
            return True

        bar = self._resolve_bar(parent_widget)
        self.injection_started.emit("manual")

        session = _InjectionSession(
            coordinator      = self,
            cycle            = cycle,
            sample_info      = sample_info,
            bar              = bar,
            parent_widget    = parent_widget,
            injection_num    = injection_num,
            total_injections = total_injections,
            method_mode      = method_mode,
            pump_transit_delay_s = pump_transit_delay_s,
        )
        self._active_session = session
        accepted = session.run()   # blocks BG thread until lifecycle completes

        self._close_valves_after_manual_injection()
        if accepted:
            self._process_detection_results(session.dialog, cycle, bar=bar, timed_out=False,
                                            already_placed=session._flags_placed)
            self.injection_completed.emit()
        else:
            logger.info("❌ Injection cancelled by user")
            self.injection_cancelled.emit()

        return accepted

    def _resolve_bar(self, parent_widget):
        """Return the InjectionActionBar from sidebar, or None."""
        try:
            sidebar = getattr(parent_widget, 'sidebar', None)
            if sidebar is None and hasattr(parent_widget, 'main_window'):
                sidebar = getattr(parent_widget.main_window, 'sidebar', None)
            return getattr(sidebar, 'injection_action_bar', None)
        except Exception:
            return None

    def _process_detection_results(self, dialog, cycle: Cycle, *, bar=None, timed_out: bool = False,
                                    already_placed: "set[str] | None" = None) -> None:
        """Process detection results after the injection lifecycle completes.

        Handles two cases:
        1. _InjectionMonitor detected injection → dialog._detected_channels_results populated
           → emit flag + store per-channel times + confidences on cycle
        2. Timed out or cancelled with no detection → increment injection count only

        Args:
            dialog: ManualInjectionDialog instance holding detection results
            cycle: Current cycle to update with injection data
            bar: InjectionActionBar instance for UI feedback (may be None)
            timed_out: True if the blocking wait expired without detection
        """
        from affilabs.dialogs.manual_injection_dialog import ManualInjectionDialog

        if dialog.detected_injection_time is not None:
            # Dialog auto-detected injection — place flags for ALL detected channels
            logger.info(
                f"✓ Injection auto-detected: primary channel {dialog.detected_channel.upper()} "
                f"at t={dialog.detected_injection_time:.1f}s "
                f"(confidence: {dialog.detected_confidence:.0%})"
            )

            # Use dialog's per-channel results (already scanned during grace period)
            if dialog._detected_channels_results:
                cycle.injection_time_by_channel = {
                    ch: r['time'] for ch, r in dialog._detected_channels_results.items()
                }
                cycle.injection_confidence_by_channel = {
                    ch: r['confidence'] for ch, r in dialog._detected_channels_results.items()
                }
                logger.info(
                    f"Per-channel injection times from dialog: "
                    f"{list(cycle.injection_time_by_channel.keys())} "
                    f"(confidences: {cycle.injection_confidence_by_channel})"
                )

                # Emit injection flag for channels not already placed by the fast path
                _placed = already_placed or set()
                for ch, result in dialog._detected_channels_results.items():
                    if ch in _placed:
                        logger.debug(f"Flag for ch {ch} already placed via fast path — skipping duplicate")
                        continue
                    self.injection_flag_requested.emit(
                        ch.lower(),
                        result['time'],
                        result['confidence'],
                    )
            else:
                # Primary detected but _detected_channels_results is empty — log and move on.
                logger.warning(
                    f"Primary channel detected ({dialog.detected_channel}) but no per-channel "
                    f"results in _detected_channels_results — no flags placed"
                )

            # Track injection count for binding/kinetic cycles
            if cycle.type in ("Binding", "Kinetic", "Concentration") and cycle.planned_concentrations:
                cycle.injection_count += 1
                logger.info(
                    f"  Injection count: {cycle.injection_count}/"
                    f"{len(cycle.planned_concentrations)}"
                )
        else:
            if not timed_out:
                # User pressed "Done" — _InjectionMonitor did not fire.
                logger.info("User pressed Done — no injection detected by _InjectionMonitor")
                if bar is not None:
                    QTimer.singleShot(0, bar.show_injection_missed)
                if cycle.type in ("Binding", "Kinetic", "Concentration") and cycle.planned_concentrations:
                    cycle.injection_count += 1
            else:
                # Genuine timeout — no injection detected, still count
                logger.warning("Detection window expired — no injection detected")
                if cycle.type in ("Binding", "Kinetic", "Concentration") and cycle.planned_concentrations:
                    cycle.injection_count += 1

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_detection_channels(self, cycle, sample_info: dict) -> str:
        """Resolve which channels to monitor for injection detection.

        Priority:
        1. cycle.target_channels (explicit override)
        2. Keys of cycle.concentrations (auto-derive, e.g. {"A": 50} → "A")
        3. Hardware default: "ABCD" for P4SPR, else sample_info channels or "AC"
        """
        if getattr(cycle, 'target_channels', None):
            return cycle.target_channels
        if getattr(cycle, 'concentrations', None):
            return "".join(sorted(cycle.concentrations.keys()))
        return "ABCD" if self._is_p4spr else (sample_info.get("channels") or "AC")

    def _execute_automated_injection(self, cycle: Cycle, flow_rate: float) -> bool:
        """Execute automated injection via PumpManager (existing logic).

        Runs in background thread to avoid blocking UI. This preserves the
        existing injection behavior for P4PRO and AffiPump systems.

        Args:
            cycle: Cycle requiring injection
            flow_rate: Flow rate in µL/min

        Returns:
            True if injection initiated successfully (runs async in background)
        """
        logger.info("=== Automated Injection Mode ===")
        self.injection_started.emit(cycle.injection_method or "automated")

        # Run in background thread (existing pattern from main.py)
        def run_injection():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Stop any running pump operation first
                if not self.pump_mgr.is_idle:
                    logger.info("⏹ Stopping pump before injection...")
                    idle_ok = loop.run_until_complete(
                        self.pump_mgr.stop_and_wait_for_idle(timeout=30.0)
                    )
                    if not idle_ok:
                        logger.error("❌ Could not stop pump for injection")
                        return

                # Execute injection with channel selection
                channels = cycle.channels  # None = use default_channels
                if cycle.injection_method == "simple":
                    logger.info(
                        f"💉 AUTO-INJECT: Simple @ {flow_rate} µL/min (channels={channels or 'default'})"
                    )
                    success = loop.run_until_complete(
                        self.pump_mgr.inject_simple(flow_rate, channels=channels)
                    )
                elif cycle.injection_method == "partial":
                    logger.info(
                        f"💉 AUTO-INJECT: Partial @ {flow_rate} µL/min (channels={channels or 'default'})"
                    )
                    success = loop.run_until_complete(
                        self.pump_mgr.inject_partial_loop(flow_rate, channels=channels)
                    )
                else:
                    logger.warning(
                        f"Unknown injection method: {cycle.injection_method}"
                    )
                    success = False

                if success:
                    self.injection_completed.emit()
                else:
                    logger.error("❌ Automated injection failed")

            except Exception as e:
                logger.exception(f"Automated injection error: {e}")
            finally:
                loop.close()

        thread = threading.Thread(
            target=run_injection, daemon=True, name="AutoInjection"
        )
        thread.start()
        return True

    def _open_valves_for_manual_injection(self, channels: str):
        """Open valves to assist manual syringe injection.

        Sets 3-way valves to route flow to the target channels.
        This helps guide the user's manual injection to the correct flow path.

        Args:
            channels: Target channels ("AC" or "BD")
        """
        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl:
            logger.warning("No controller - cannot open valves for manual injection")
            return

        try:
            # Set 3-way valves to route to selected channels
            # AC = state 0, BD = state 1
            three_way_state = 1 if channels == "BD" else 0

            # Check if controller supports valve control (FlowController only)
            if hasattr(ctrl, 'knx_three_both'):
                ctrl.knx_three_both(state=three_way_state)
                logger.info(
                    f"✓ Valves opened for manual injection (channels: {channels})"
                )

        except Exception as e:
            logger.error(f"Failed to open valves: {e}")

    def _close_valves_after_manual_injection(self):
        """Return valves to default position after manual injection.

        Resets valves to the default channel pair and closes 6-port valves
        to LOAD position for normal buffer flow.
        """
        ctrl = self.hardware_mgr._ctrl_raw
        if not ctrl:
            return

        try:
            # Return to default channel pair
            default_channels = self.pump_mgr.default_channels if self.pump_mgr else "AC"
            default_state = 1 if default_channels == "BD" else 0

            # Check if controller supports valve control (FlowController only)
            if hasattr(ctrl, 'knx_three_both'):
                ctrl.knx_three_both(state=default_state)
            if hasattr(ctrl, 'knx_six_both'):
                ctrl.knx_six_both(state=0)
        except Exception as e:
            logger.error(f"Failed to close valves: {e}")
