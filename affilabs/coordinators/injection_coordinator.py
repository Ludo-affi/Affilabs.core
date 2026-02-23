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
- InjectionActionBar Phase 2 is shown inline in the sidebar (non-blocking UI)
- ManualInjectionDialog runs hidden — its 60-second detection engine stays active
- Dialog signals (injection_detected, injection_complete) are bridged to the bar
- Channel LEDs in bar update as each channel is auto-detected (grey→yellow→green)
- Background thread blocks on threading.Event until dialog completes (max 70s)
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

from PySide6.QtCore import QMetaObject, QObject, Qt, QTimer, Signal

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


class _WashMonitor(QObject):
    """Per-channel wash injection detector running on the main thread.

    Monitors the SPR signal during contact time using a 10-second moving slope.
    A sudden break from the contact trend (slope change exceeding threshold) is
    classified as a wash injection.

    Algorithm:
        Every POLL_INTERVAL_S seconds:
          1. Fetch the last WINDOW_S seconds of cycle_data[ch].spr (RU) for channel.
          2. Compute slope of two consecutive 10-second halves:
               slope_prev  = polyfit(t[-20s..-10s], spr[-20s..-10s])[0]  [RU/s]
               slope_now   = polyfit(t[-10s..now],  spr[-10s..now])[0]   [RU/s]
          3. delta_slope = slope_now - slope_prev
          4. A rolling noise estimate (std of slope_now over several polls) sets
             the adaptive threshold.
          5. If abs(delta_slope) > max(HARD_MIN_SLOPE_CHANGE, SIGMA * noise_std)
             for CONFIRM_POLLS consecutive polls → wash detected.

    The detector ignores the first MIN_CONTACT_S seconds to skip the initial
    injection transient, which also shows a large slope change.
    """

    wash_detected = Signal(str)   # channel letter (upper)

    POLL_INTERVAL_S   = 2         # check every 2 seconds
    WINDOW_S          = 20        # total lookback for slope pair (2 × 10 s)
    HALF_S            = 10        # each slope half is 10 seconds
    MIN_PTS           = 4         # minimum points per half-window (~0.5 Hz → 4 pts in 8-10 s)
    MIN_CONTACT_S     = 15        # ignore first 15 s after injection (injection transient)
    HARD_MIN_SLOPE    = 0.5       # RU/s — minimum detectable slope change (~30 RU/min)
    SIGMA             = 4.0       # how many noise σ above baseline variability
    CONFIRM_POLLS     = 2         # consecutive detections required to confirm

    def __init__(self, channel: str, buffer_mgr, injection_time: float, parent=None):
        super().__init__(parent)
        self._ch = channel.lower()
        self._ch_upper = channel.upper()
        self._buffer_mgr = buffer_mgr
        self._injection_wall_time = injection_time   # wall-clock time.time() for elapsed guard
        # Cycle-relative time of injection: read the latest cycle_data time at start.
        # Used to exclude pre-injection data points from the slope windows.
        self._injection_cycle_t: float | None = self._read_current_cycle_t()
        self._timer = QTimer(self)
        self._timer.setInterval(self.POLL_INTERVAL_S * 1000)
        self._timer.timeout.connect(self._poll)
        self._slope_history: list[float] = []   # rolling slope_now values for noise estimation
        self._confirm_count = 0
        self._stopped = False

    def _read_current_cycle_t(self) -> float | None:
        """Read the latest cycle-relative timestamp from cycle_data at monitor start."""
        try:
            data = self._buffer_mgr.cycle_data.get(self._ch)
            if data is not None and len(data.time) > 0:
                return float(np.asarray(data.time)[-1])
        except Exception:
            pass
        return None

    def start(self) -> None:
        self._timer.start()
        logger.debug(f"WashMonitor started for channel {self._ch_upper}")

    def stop(self) -> None:
        self._stopped = True
        self._timer.stop()
        logger.debug(f"WashMonitor stopped for channel {self._ch_upper}")

    def _poll(self) -> None:
        if self._stopped:
            return

        elapsed_since_injection = time.time() - self._injection_wall_time
        if elapsed_since_injection < self.MIN_CONTACT_S:
            return   # too early — injection transient still settling

        try:
            data = self._buffer_mgr.cycle_data.get(self._ch)
        except Exception:
            return
        if data is None or len(data.time) < self.MIN_PTS * 2:
            return

        times = np.asarray(data.time, dtype=float)
        spr   = np.asarray(data.spr,  dtype=float)

        # Exclude any data points that predate the injection itself.
        # _injection_cycle_t is the cycle-relative time when the monitor started.
        # Add MIN_CONTACT_S so the full transient region is skipped.
        if self._injection_cycle_t is not None:
            post_inj_t = self._injection_cycle_t + self.MIN_CONTACT_S
            post_mask = times >= post_inj_t
            times = times[post_mask]
            spr   = spr[post_mask]
            if len(times) < self.MIN_PTS * 2:
                return

        now = times[-1]
        t_split = now - self.HALF_S
        t_start = now - self.WINDOW_S

        # Previous 10-second window: [now-20s .. now-10s]
        mask_prev = (times >= t_start) & (times < t_split)
        # Current 10-second window: [now-10s .. now]
        mask_now  = (times >= t_split)

        if mask_prev.sum() < self.MIN_PTS or mask_now.sum() < self.MIN_PTS:
            return   # not enough data yet

        t_prev, spr_prev = times[mask_prev], spr[mask_prev]
        t_now,  spr_now  = times[mask_now],  spr[mask_now]

        try:
            slope_prev = float(np.polyfit(t_prev - t_prev[0], spr_prev, 1)[0])
            slope_now  = float(np.polyfit(t_now  - t_now[0],  spr_now,  1)[0])
        except (np.linalg.LinAlgError, ValueError):
            return

        # Rolling noise estimate: std of recent slope_now values
        self._slope_history.append(slope_now)
        if len(self._slope_history) > 10:
            self._slope_history.pop(0)
        noise_std = float(np.std(self._slope_history)) if len(self._slope_history) >= 3 else 0.0

        delta = abs(slope_now - slope_prev)
        threshold = max(self.HARD_MIN_SLOPE, self.SIGMA * noise_std)

        logger.debug(
            f"WashMonitor {self._ch_upper}: slope_prev={slope_prev:.4f} "
            f"slope_now={slope_now:.4f} delta={delta:.4f} threshold={threshold:.4f} "
            f"confirms={self._confirm_count}"
        )

        if delta >= threshold:
            self._confirm_count += 1
            if self._confirm_count >= self.CONFIRM_POLLS:
                logger.info(
                    f"✓ Wash injection detected on channel {self._ch_upper} "
                    f"(slope Δ={delta:.4f} RU/s, threshold={threshold:.4f}, "
                    f"contact elapsed={elapsed_since_injection:.0f}s)"
                )
                self.stop()
                self.wash_detected.emit(self._ch_upper)
        else:
            self._confirm_count = 0   # reset — must be consecutive


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

        # State for manual injection flow
        self._window_start_time: Optional[float] = None
        self._detection_channels: str = "ABCD"
        self._current_cycle: Optional[Cycle] = None
        self._is_p4spr: bool = False

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
        """Execute manual injection — shows InjectionActionBar Phase 2 + hidden dialog.

        This method:
        1. Opens valves for manual injection (non-P4SPR only)
        2. Shows InjectionActionBar.show_phase2() inline in the sidebar
        3. Runs ManualInjectionDialog hidden — its detection engine stays active
        4. Blocks background thread on threading.Event until detection complete (max 70s)
        5. Processes detection results and updates cycle state

        Args:
            cycle: Cycle requiring injection
            parent_widget: Parent widget for dialog positioning

        Returns:
            True if injection completed (detected or timed out), False if cancelled
        """
        logger.info("=== Manual Injection Mode (Non-Blocking) ===")

        # Parse sample information from cycle metadata
        sample_info = parse_sample_info(cycle)
        logger.info(f"  Sample: {sample_info['sample_id']}")

        # For P4SPR (static optical system), don't show valve channels
        self._is_p4spr = self.hardware_mgr._ctrl_type == "PicoP4SPR"
        if self._is_p4spr:
            sample_info["channels"] = None
            logger.info(f"  Hardware: P4SPR (no valve routing)")
        else:
            logger.info(f"  Channels: {sample_info['channels']}")

        if sample_info["concentration"]:
            logger.info(
                f"  Concentration: {sample_info['concentration']} {sample_info['units']}"
            )

        # Open valves for manual injection (only if not P4SPR)
        if not self._is_p4spr:
            self._open_valves_for_manual_injection(sample_info["channels"])

        # For binding/kinetic cycles, show injection number
        # NOTE: planned_concentrations groups parallel channels into ONE entry,
        # so len() correctly reflects actual injection events (not channel count)
        injection_num = None
        total_injections = None
        if cycle.type in ("Binding", "Kinetic", "Concentration") and cycle.planned_concentrations:
            injection_num = cycle.injection_count + 1
            total_injections = len(cycle.planned_concentrations)
            logger.info(f"  {cycle.type} Cycle: Injection {injection_num}/{total_injections}")

        self._detection_channels = self._resolve_detection_channels(cycle, sample_info)

        # Save current cycle for detection completion
        self._current_cycle = cycle

        self.injection_started.emit("manual")

        # Check method mode - only show dialog for manual injections
        method_mode = getattr(cycle, 'method_mode', None)

        # Compute pump transit delay — time for sample to travel from loop outlet to sensor.
        # Prevents the detector from firing on the bulk RI shift of the approaching plug.
        _pump_transit_delay_s = 0.0
        if method_mode in ('semi-automated', 'pump'):
            _active_flow_rate = getattr(cycle, 'flow_rate', None) or flow_rate
            if _active_flow_rate and _active_flow_rate > 0:
                _pump_transit_delay_s = FLUIDIC_PATH_VOLUME_UL / _active_flow_rate * 60.0
                logger.info(
                    f"Pump transit delay: {FLUIDIC_PATH_VOLUME_UL}µL ÷ {_active_flow_rate}µL/min × 60 "
                    f"= {_pump_transit_delay_s:.1f}s"
                )
        
        # Skip dialog for pump/semi-automated modes (injection is automatic)
        if method_mode in ['pump', 'semi-automated']:
            logger.info(f"Pump mode ({method_mode}) - skipping manual injection dialog")
            # Auto-complete for pump modes (detection happens in background)
            self._close_valves_after_manual_injection()
            self.injection_completed.emit()
            return True

        # ── Show inline InjectionActionBar Phase 2 (non-blocking detection) ──
        # ManualInjectionDialog handles the 60-second detection engine (timers,
        # peak detection, per-channel LED feedback). We run it hidden and bridge
        # its signals to the InjectionActionBar embedded in the sidebar.
        # A threading.Event lets this background thread block until the user
        # finishes or the 60s window expires.
        done_event = threading.Event()
        accepted_flag: list[bool] = [False]
        dialog_holder: list = [None]  # populated on main thread

        _has_contact_time = bool(getattr(cycle, 'contact_time', None))
        _contact_time_val = getattr(cycle, 'contact_time', None)
        _detection_channels = self._detection_channels
        _detection_priority = getattr(cycle, 'detection_priority', 'auto')
        _buffer_mgr = self.buffer_mgr

        # Get the sidebar injection bar reference (safe to read from bg thread)
        bar = None
        try:
            sidebar = getattr(parent_widget, 'sidebar', None)
            if sidebar is None and hasattr(parent_widget, 'main_window'):
                sidebar = getattr(parent_widget.main_window, 'sidebar', None)
            bar = getattr(sidebar, 'injection_action_bar', None)
        except Exception:
            pass

        def _dismiss_bar():
            if bar is not None:
                bar.set_panel_active(False)

        def _on_dialog_complete():
            accepted_flag[0] = True
            if _has_contact_time:
                # Detection finished, but contact window still active.
                # Do NOT unblock the BG thread yet — wait for _on_bar_done
                # (triggered when all channels are washed) to set done_event.
                # This prevents injection_completed from firing prematurely
                # while contact time is still running.
                logger.debug(
                    "Dialog complete with contact_time — waiting for wash "
                    "(bar done) before unblocking BG thread"
                )
            else:
                # No contact window configured.  Unblock the BG thread so
                # injection_completed fires, but do NOT dismiss the bar here.
                # The bar's own QTimer.singleShot(1500, _fire_done) keeps the
                # green LED visible for ~1.5 s so the user sees the confirmation,
                # then _fire_done → _on_bar_done → _dismiss_bar handles cleanup.
                done_event.set()

        def _on_dialog_cancelled():
            accepted_flag[0] = False
            _stop_all_wash_monitors()
            _dismiss_bar()
            done_event.set()
            d = dialog_holder[0]
            if d is not None:
                d.reject()

        def _on_bar_done():
            accepted_flag[0] = True
            _stop_all_wash_monitors()
            _dismiss_bar()
            if not done_event.is_set():
                d = dialog_holder[0]
                if d is not None:
                    d.accept()
                done_event.set()

        def _on_bar_cancel():
            _on_dialog_cancelled()

        def _on_anomaly(flag: str, channel: str) -> None:
            try:
                mw = getattr(parent_widget, 'main_window', parent_widget)
                cycle_bar = getattr(mw, 'unified_cycle_bar', None)
                if cycle_bar is not None:
                    cycle_bar.set_inject_anomaly(flag, channel)
            except Exception:
                pass

        # Active wash monitors, keyed by channel letter (upper).
        # Stored so they can be stopped on cancel/timeout.
        wash_monitors: dict[str, _WashMonitor] = {}

        def _start_wash_monitor(ch: str) -> None:
            """Start a wash detector for one channel — runs on the main thread."""
            if not _has_contact_time or _buffer_mgr is None or bar is None:
                return
            if ch in wash_monitors:
                return   # already started for this channel
            monitor = _WashMonitor(
                channel=ch,
                buffer_mgr=_buffer_mgr,
                injection_time=time.time(),
                parent=bar,   # ownership on main-thread QObject tree
            )
            def _on_wash(channel: str) -> None:
                logger.info(f"Wash detected on channel {channel} — transitioning Contact Monitor")
                bar.set_channel_wash(channel)
                wash_monitors.pop(channel, None)
            monitor.wash_detected.connect(_on_wash)
            wash_monitors[ch] = monitor
            monitor.start()

        def _stop_all_wash_monitors() -> None:
            for m in list(wash_monitors.values()):
                m.stop()
            wash_monitors.clear()

        def _setup_on_main_thread():
            """Create dialog, wire signals, show bar Phase 2 — all on main thread."""
            dialog = ManualInjectionDialog(
                sample_info,
                parent=parent_widget,
                injection_number=injection_num,
                total_injections=total_injections,
                buffer_mgr=_buffer_mgr,
                channels=_detection_channels,
                detection_priority=_detection_priority,
                method_mode=method_mode,
                pump_transit_delay_s=_pump_transit_delay_s,
            )
            dialog_holder[0] = dialog

            def _on_dialog_detected():
                if bar is None:
                    return
                for ch in dialog._detected_channels_results:
                    bar.update_channel_detected(ch, detected=True)
                    # Start wash monitor for each confirmed channel
                    if _has_contact_time:
                        _start_wash_monitor(ch)
                detected_chs = list(dialog._detected_channels_results.keys())
                if detected_chs:
                    chs_str = ', '.join(sorted(detected_chs))
                    bar.update_status(f"✓ Detected on {chs_str}")

            dialog.injection_detected.connect(_on_dialog_detected)
            dialog.injection_complete.connect(_on_dialog_complete)
            dialog.injection_cancelled.connect(_on_dialog_cancelled)
            dialog.anomaly_detected.connect(_on_anomaly)

            if bar is not None:
                bar.show_phase2(
                    channels=_detection_channels,
                    on_done=_on_bar_done,
                    on_cancel=_on_bar_cancel,
                    contact_time=_contact_time_val,
                )

            # WA_DontShowOnScreen is unreliable on Windows — move dialog
            # far off-screen instead so showEvent fires (starts detection)
            # but the dialog is never visible to the user.
            dialog.move(-9999, -9999)
            dialog.show()

        # Schedule everything on the main thread, then block background thread.
        QMetaObject.invokeMethod(
            parent_widget,
            "_call_on_main",
            Qt.ConnectionType.QueuedConnection,
            _setup_on_main_thread,
        ) if hasattr(parent_widget, '_call_on_main') else (
            # Fallback: use QTimer.singleShot which always fires on main thread
            QTimer.singleShot(0, _setup_on_main_thread)
        )

        # Block background thread until the full injection lifecycle completes:
        #   - Without contact_time: unblocks after detection dialog finishes (~95s max)
        #   - With contact_time: unblocks after wash detected on all channels
        #     (contact_time + 120s margin for late wash + detection overhead)
        _detection_timeout = 95   # Phase 1 (10s) + Phase 2 detection (80s) + 5s margin
        _contact_margin = (int(_contact_time_val) + 120) if _has_contact_time else 0
        _total_timeout = _detection_timeout + _contact_margin
        timed_out = not done_event.wait(timeout=_total_timeout)
        if timed_out:
            logger.warning(
                f"Injection lifecycle timed out after {_total_timeout}s "
                f"(contact_time={_contact_time_val}) — forcing cleanup"
            )
            if bar is not None:
                _bar_ref = bar
                QTimer.singleShot(0, lambda: (_stop_all_wash_monitors(), _bar_ref.set_panel_active(False)))

        accepted = accepted_flag[0]
        if accepted:
            self._process_detection_results(dialog_holder[0], cycle, timed_out=False)
            self._close_valves_after_manual_injection()
            self.injection_completed.emit()
        else:
            logger.info("❌ Injection cancelled by user")
            self._close_valves_after_manual_injection()
            self.injection_cancelled.emit()

        return accepted

    def _process_detection_results(self, dialog, cycle: Cycle, *, timed_out: bool = False) -> None:
        """Process detection results from ManualInjectionDialog after it closes.

        Handles three cases:
        1. Dialog auto-detected injection → emit flag + store per-channel results
        2. Dialog detected but no per-channel results → retroactive scan
        3a. User pressed Done without auto-detection → retroactive scan + fallback flag
        3b. 60s timeout with no detection → just increment injection count

        Args:
            dialog: Closed ManualInjectionDialog instance with detection results
            cycle: Current cycle to update with injection data
            timed_out: True if the 70s blocking wait expired (genuine timeout, not user Done)
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

                # Emit injection flag for EVERY detected channel (not just primary)
                for ch, result in dialog._detected_channels_results.items():
                    self.injection_flag_requested.emit(
                        ch.lower(),
                        result['time'],
                        result['confidence'],
                    )
            else:
                # Dialog detected primary channel but _detected_channels_results is empty
                # (edge case: primary detected but grace-period per-channel scan didn't run).
                # Run retroactive scan on all planned channels and emit whatever is found.
                logger.info(
                    f"Primary channel detected ({dialog.detected_channel}) but no per-channel "
                    f"results — running retroactive scan"
                )
                self._window_start_time = dialog.window_start_time
                self._scan_all_channels_for_injection()
                self._emit_scan_flags(cycle)

            # Track injection count for binding/kinetic cycles
            if cycle.type in ("Binding", "Kinetic", "Concentration") and cycle.planned_concentrations:
                cycle.injection_count += 1
                logger.info(
                    f"  Injection count: {cycle.injection_count}/"
                    f"{len(cycle.planned_concentrations)}"
                )
        else:
            if not timed_out:
                # User pressed "Done" without auto-detection firing — retroactive scan.
                logger.info("User pressed Done — no auto-detection; running retroactive scan")
                self._window_start_time = dialog.window_start_time
                self._scan_all_channels_for_injection()
                self._emit_scan_flags(cycle)

                if cycle.type in ("Binding", "Kinetic", "Concentration") and cycle.planned_concentrations:
                    cycle.injection_count += 1
            else:
                # Genuine timeout — no injection detected, still count
                logger.warning("60s window expired — no injection peak detected")
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

    # ------------------------------------------------------------------
    # Per-channel injection scan
    # ------------------------------------------------------------------

    def _scan_all_channels_for_injection(self):
        """Retroactively scan all 4 channels for injection points.

        Uses the detection window (window_start → now) to find per-channel
        injection times. Stores results on the current cycle and flags any
        channels that detected injection but are not in the cycle's active
        channel set (potential mislabeling).
        """
        cycle = self._current_cycle
        if not cycle or not self.buffer_mgr or self._window_start_time is None:
            return

        try:
            from affilabs.utils.spr_signal_processing import detect_injection_all_channels

            # Determine window end = latest timestamp across all channels
            window_end = self._window_start_time + 60.0  # min window
            for ch in ['a', 'b', 'c', 'd']:
                if ch in self.buffer_mgr.timeline_data:
                    ch_data = self.buffer_mgr.timeline_data[ch]
                    if ch_data and len(ch_data.time) > 0:
                        window_end = max(window_end, float(np.array(ch_data.time)[-1]))

            result = detect_injection_all_channels(
                self.buffer_mgr.timeline_data,
                self._window_start_time,
                window_end,
                min_confidence=0.20,  # Match live dialog threshold (0.15) with small margin
            )

            # Store per-channel injection times on cycle
            cycle.injection_time_by_channel = result['times']
            cycle.injection_confidence_by_channel = result['confidences']

            detected_channels = list(result['times'].keys())
            logger.info(
                f"Per-channel injection scan: detected on {detected_channels} "
                f"(confidences: {result['confidences']})"
            )

            # --- Mislabel detection ---
            # Determine expected active channels from cycle settings
            active_ch_str = (cycle.channels or "ABCD").upper()
            active_channels = set(active_ch_str)

            mislabel_flags = {}
            for ch, conf in result['confidences'].items():
                if ch not in active_channels:
                    mislabel_flags[ch] = 'inactive_channel'
                    logger.warning(
                        f"⚠ Mislabel warning: Channel {ch} detected injection "
                        f"(confidence: {conf:.0%}) but is not in active set "
                        f"({active_ch_str}). Signal may be optical artifact."
                    )
            cycle.injection_mislabel_flags = mislabel_flags

        except Exception as e:
            logger.warning(f"Per-channel injection scan failed: {e}")

    def _emit_scan_flags(self, cycle: Cycle) -> None:
        """Emit injection_flag_requested for each channel found by retroactive scan.

        Logs which planned detection channels were found vs missed — no fallback flags.
        """
        planned_chs = set(self._detection_channels.upper()) if self._detection_channels else set()
        found_chs = set(cycle.injection_time_by_channel.keys()) if cycle.injection_time_by_channel else set()

        if found_chs:
            for ch, inj_time in cycle.injection_time_by_channel.items():
                conf = cycle.injection_confidence_by_channel.get(ch, 0.5)
                self.injection_flag_requested.emit(ch.lower(), inj_time, conf)
                logger.info(f"  Scan flag: channel {ch} at t={inj_time:.1f}s (conf={conf:.0%})")
        else:
            logger.warning("Retroactive scan found no injection on any channel — no flags placed")

        missed = planned_chs - found_chs
        if missed:
            logger.warning(f"  Planned channels with NO detected injection: {sorted(missed)}")

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
