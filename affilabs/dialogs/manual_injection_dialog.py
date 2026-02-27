"""ManualInjectionDialog -- lightweight state container for active injection lifecycle.

NOT a visible dialog. Exists only to hold detection state attributes that the
InjectionCoordinator reads after the injection lifecycle completes.

Detection is driven entirely by _InjectionMonitor (coordinator-owned).
This class holds results: detected_injection_time, detected_channel,
detected_confidence, _detected_channels_results.

Lifecycle:
  1. Coordinator creates instance on main thread (_setup_on_main_thread)
  2. _InjectionMonitor(s) populate detection attrs via coordinator callbacks
  3. Coordinator reads attrs in _process_detection_results()
  4. Instance is discarded

No UI. No timers. No modal blocking.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal

from affilabs.utils.logger import logger

# Kept for backward compat -- coordinator imports this constant.
FLUIDIC_PATH_VOLUME_UL = 8.0  # Dead volume from loop outlet to sensor (P4PRO/PROPLUS, uL)


class ManualInjectionDialog(QObject):
    """State container for an active injection lifecycle.

    Not a dialog -- just a QObject that holds detection results and emits signals.
    The name is kept for backward compatibility with InjectionCoordinator imports.

    Signals:
        injection_complete:  Emitted when injection lifecycle ends normally.
        injection_cancelled: Emitted if user cancels via the Contact Monitor bar.
        injection_detected:  Emitted when any channel first detects injection.
        anomaly_detected:    Emitted on bubble/leak detection (flag, channel_upper).
    """

    injection_complete = Signal()
    injection_cancelled = Signal()
    injection_detected = Signal()
    anomaly_detected = Signal(str, str)  # flag, channel_upper

    def __init__(
        self,
        sample_info: dict[str, Any],
        parent=None,
        injection_number: int | None = None,
        total_injections: int | None = None,
        buffer_mgr=None,
        channels: str | None = None,
        detection_priority: str = "auto",
        method_mode: str | None = None,
        pump_transit_delay_s: float = 0.0,
    ):
        super().__init__(parent)
        self.sample_info = sample_info
        self.injection_number = injection_number
        self.total_injections = total_injections
        self.buffer_mgr = buffer_mgr
        self.detection_channels = channels or "ABCD"
        self.detection_priority = detection_priority or "auto"
        self.method_mode = method_mode

        # Detection results (populated by _InjectionMonitor via coordinator)
        self.detected_injection_time: float | None = None
        self.detected_channel: str | None = None
        self.detected_confidence: float | None = None
        self._detected_channels_results: dict[str, dict] = {}
        self._channel_detected: dict[str, bool] = {
            ch: False for ch in (channels or "ABCD").upper()
        }

        # Compat flags read by coordinator
        self.detection_active = False
        self._user_done_injecting: bool = False

        logger.debug(
            f"ManualInjectionDialog created (state container) -- "
            f"channels={self.detection_channels}, mode={self.method_mode}"
        )
