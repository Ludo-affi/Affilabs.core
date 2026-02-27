"""AirBubbleDetector — per-channel air bubble detection from SPR wavelength noise.

Algorithm (two-stage):

  Stage 1 — Noise trigger:
    Rolling std(wavelength, 30-frame window) exceeds _STD_THRESHOLD_NM
    (20 RU = 20/355 nm ≈ 0.056 nm).

  Stage 2 — %T confirmation (examined over a ±30 s window centred on the trigger):
    The transmission dip depth *increased* by more than _T_DROP_THRESHOLD_PP
    percentage points (absolute).  "Dip depth went up" means mean_%T dropped —
    e.g. 77% → 50% = 27 pp drop → confirms air bubble.

  Mutual exclusion:
    If the leak detector has already alerted on this channel this session
    (app._leak_alerted), the bubble detector skips — leaks and bubbles
    cannot be concurrent faults on the same channel.

Alert: opens SparkBubble with actionable message.
Cooldown: 60 s per channel after each confirmed alert.

See docs/features/OPTICAL_FAULT_DETECTION_FRS.md §2 for full spec.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Optional

import numpy as np

from PySide6.QtCore import QObject, Signal

from affilabs.utils.logger import logger

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
_NM_TO_RU = 355.0

# Stage 1: wavelength std threshold
_STD_THRESHOLD_NM = 20.0 / _NM_TO_RU     # 20 RU → ~0.056 nm

# Stage 2: transmittance dip confirmation
_T_DROP_THRESHOLD_PP = 10.0              # pp (percentage points) absolute drop in mean_%T

# Rolling windows
_STD_WINDOW_FRAMES  = 30                 # frames for std computation (~30 s at 1 Hz)
_CONFIRM_WINDOW_S   = 30.0               # seconds of %T history to examine for confirmation

# Cooldown between alerts per channel
_BUBBLE_COOLDOWN_S  = 60.0


class AirBubbleDetector(QObject):
    """Singleton detector for air bubbles in the SPR flow cell.

    Usage::
        detector = AirBubbleDetector.get_instance()
        detector.set_alert_target(main_window)   # once at startup / session start
        # Per-frame (from spectrum_helpers):
        detector.feed(channel, wavelength_nm, mean_transmittance, timestamp, app)
    """

    # Emitted on confirmed detection: (channel, std_nm, t_drop_pp)
    bubble_detected = Signal(str, float, float)

    _instance: Optional["AirBubbleDetector"] = None

    @classmethod
    def get_instance(cls) -> "AirBubbleDetector":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        # Rolling wavelength history per channel (deque of float, maxlen=_STD_WINDOW_FRAMES)
        self._wl_history: dict[str, deque[float]] = {}
        # Time-stamped %T history per channel (deque of (timestamp, mean_%T))
        self._t_history:  dict[str, deque[tuple[float, float]]] = {}
        # Timestamp of last alert per channel
        self._last_alert_ts: dict[str, float] = {}
        # Main window reference for spark_bubble access
        self._main_window = None

    def set_alert_target(self, main_window) -> None:
        """Provide the main window so alerts can reach spark_bubble."""
        self._main_window = main_window

    def reset_session(self) -> None:
        """Clear all per-channel state at the start of a new acquisition session."""
        self._wl_history.clear()
        self._t_history.clear()
        self._last_alert_ts.clear()

    # ------------------------------------------------------------------
    # Main feed — called once per frame from spectrum_helpers
    # ------------------------------------------------------------------

    def feed(
        self,
        channel: str,
        wavelength_nm: float,
        mean_transmittance: float | None,
        timestamp: float,
        app=None,
    ) -> None:
        """Process one frame.

        Args:
            channel:            Channel letter ('a', 'b', 'c', 'd').
            wavelength_nm:      SPR resonance wavelength from the pipeline (nm).
            mean_transmittance: Mean %T across the SPR window (0–100). None → skip.
            timestamp:          Unix epoch (seconds).
            app:                Application instance — used to read _leak_alerted.
        """
        if mean_transmittance is None:
            return

        # Mutual exclusion: skip if leak already confirmed on this channel
        if app is not None:
            leak_alerted: set = getattr(app, '_leak_alerted', set())
            if channel in leak_alerted:
                return

        # Ensure per-channel state exists
        if channel not in self._wl_history:
            self._wl_history[channel]    = deque(maxlen=_STD_WINDOW_FRAMES)
            self._t_history[channel]     = deque()   # unbounded — we trim by time
            self._last_alert_ts[channel] = 0.0

        wl_hist = self._wl_history[channel]
        t_hist  = self._t_history[channel]

        # Append current frame to histories
        wl_hist.append(wavelength_nm)
        t_hist.append((timestamp, mean_transmittance))

        # Trim %T history to _CONFIRM_WINDOW_S
        cutoff = timestamp - _CONFIRM_WINDOW_S
        while t_hist and t_hist[0][0] < cutoff:
            t_hist.popleft()

        # Need a full std window before evaluating
        if len(wl_hist) < _STD_WINDOW_FRAMES:
            return

        # --- Stage 1: wavelength std threshold ---
        std_nm = float(np.std(wl_hist))

        if std_nm < _STD_THRESHOLD_NM:
            return  # Normal noise — nothing to investigate

        # --- Stage 2: %T confirmation ---
        # Check if mean_%T dropped by >_T_DROP_THRESHOLD_PP pp within the window.
        # "Dip depth went up" = transmission value dropped (e.g. 77% → 50%).
        if len(t_hist) < 2:
            return

        t_values = [v for _, v in t_hist]
        t_baseline = max(t_values)   # best (highest) %T seen in the window = pre-bubble
        t_current  = mean_transmittance
        t_drop_pp  = t_baseline - t_current  # positive = %T fell = dip deepened

        if t_drop_pp < _T_DROP_THRESHOLD_PP:
            return  # No significant %T dip → not a bubble

        # --- Cooldown guard ---
        now = time.time()
        since_last = now - self._last_alert_ts.get(channel, 0.0)
        if since_last < _BUBBLE_COOLDOWN_S:
            return

        # --- Confirmed bubble ---
        self._last_alert_ts[channel] = now
        self._fire_alert(channel, std_nm, t_drop_pp)

    # ------------------------------------------------------------------
    # Internal — alert delivery
    # ------------------------------------------------------------------

    def _fire_alert(self, channel: str, std_nm: float, t_drop_pp: float) -> None:
        """Emit Qt signal and push message to Sparq bubble.

        Runs on the processing worker thread — UI update routed via
        QTimer.singleShot(0) to the main thread.
        """
        ch  = channel.upper()
        std_ru = std_nm * _NM_TO_RU

        logger.warning(
            f"🫧 AIR BUBBLE confirmed — Channel {ch}: "
            f"std={std_ru:.1f} RU ({std_nm*1000:.0f} milli-nm), "
            f"%T dropped {t_drop_pp:.1f} pp"
        )
        self.bubble_detected.emit(channel, std_nm, t_drop_pp)

        msg = (
            f"🫧 **Air bubble detected — Channel {ch}**\n\n"
            f"Signal noise spiked ({std_ru:.0f} RU std) and transmission dropped "
            f"{t_drop_pp:.0f} percentage points — consistent with an air bubble "
            f"passing through the flow cell.\n\n"
            "**Push more liquid** to flush the bubble out.\n\n"
            "- **P4SPR (manual):** Pipette 50–100 µL of running buffer slowly through "
            "the flow cell inlet. Avoid introducing more air.\n"
            "- **P4PRO / P4PROPLUS (automated):** Run a 2–3 min buffer wash at normal "
            "flow rate. If bubbles recur, check pump lines for air and reprime.\n\n"
            "The signal should recover within 1–2 minutes once the bubble clears."
        )

        if self._main_window is None:
            return

        # Emit via Application.spark_alert_signal — thread-safe queued delivery to main thread
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None and hasattr(app, 'spark_alert_signal'):
            app.spark_alert_signal.emit(msg)
        else:
            logger.warning("spark_alert_signal not available — bubble alert not delivered to UI")
