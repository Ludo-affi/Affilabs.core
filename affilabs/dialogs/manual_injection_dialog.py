"""Manual Injection Dialog - User prompt for manual syringe injection.

This dialog appears when user needs to perform a manual syringe injection.
Supports both single injections and multi-injection concentration cycles.

MODES:
1. Single Injection (regular cycles):
   - Shows sample info and asks user to inject

2. Concentration Cycle (multi-injection):
   - Shows "Injection X of Y"
   - Displays current concentration
   - Tracks progress through planned injections

ARCHITECTURE:
- Modal dialog (blocks execution via .exec())
- Auto-starts injection detection when dialog appears
- User has 60 SECONDS TOTAL to inject and confirm
- User clicks "Done Injecting" when finished
- Auto-closes when injection detected OR at 60-second mark
- Apple HIG design matching existing dialogs
- Displays sample info parsed from cycle name/notes

60-SECOND INJECTION WINDOW:
- Dialog appears → Timer starts (60 seconds total)
- User injects sample anytime during this window
- User clicks "Done Injecting" to finish (can be before 60s)
- System continues monitoring for injection peak
- Auto-closes at 60-second mark regardless
- All injection detection must occur within this 60s window

USAGE:
    from affilabs.dialogs.manual_injection_dialog import ManualInjectionDialog
    from affilabs.utils.sample_parser import parse_sample_info

    # 60-second injection window
    sample_info = parse_sample_info(cycle)
    dialog = ManualInjectionDialog(
        sample_info,
        injection_number=1,
        total_injections=3,
        buffer_mgr=buffer_manager,  # For continuous monitoring
        channels="ABCD",             # Channels to monitor
        parent=main_window
    )

    result = dialog.exec()  # Blocks for 60 seconds or until detection
    if result == ManualInjectionDialog.DialogCode.Accepted:
        # Injection detected within 60s window
        continue_cycle()
    else:
        # User cancelled or 60s window expired without detection
        stop_cycle()
"""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from affilabs.core.data_acquisition_manager import DataAcquisitionManager


class ManualInjectionDialog(QDialog):
    """Modal dialog prompting user to perform manual injection.

    Auto-starts injection detection when dialog appears.
    User has 60 SECONDS TOTAL to inject and confirm with "Done Injecting" button.
    Auto-closes when injection detected within 60-second window OR at time expiration.

    Supports both single injections and multi-injection concentration cycles.

    Attributes:
        sample_info: Dictionary with sample details (from parse_sample_info)
        injection_number: Current injection number (1-indexed) for concentration cycles
        total_injections: Total number of injections planned
        buffer_mgr: DataAcquisitionManager for real-time sensorgram monitoring
        channels: Channels to monitor for injection detection (e.g., "ABCD")
        detection_active: Whether injection monitoring is running
        window_start_time: Time when monitoring started

    Signals:
        injection_complete: Emitted when injection detected or window expires
        injection_cancelled: Emitted when user clicks "Cancel"
        injection_detected: Emitted when injection peak is found
    """

    injection_complete = Signal()
    injection_cancelled = Signal()
    injection_detected = Signal()

    def __init__(
        self,
        sample_info: dict[str, Any],
        parent=None,
        injection_number: Optional[int] = None,
        total_injections: Optional[int] = None,
        buffer_mgr: Optional[DataAcquisitionManager] = None,
        channels: Optional[str] = None,
    ):
        """Initialize manual injection dialog.

        Dialog auto-starts injection monitoring when shown.
        User has 60 seconds total to inject and click "Done Injecting".
        Dialog auto-closes at 60-second mark or when injection is detected.

        Args:
            sample_info: Dictionary with keys:
                - sample_id: Sample identifier (str)
                - display_name: Full cycle name (str)
                - concentration: Concentration value (float or None)
                - units: Concentration units (str, default "nM")
                - channels: Target SPR channels (str, default None for P4SPR)
            parent: Parent widget for positioning
            injection_number: Current injection number (1-indexed) for concentration cycles
            total_injections: Total number of injections planned for concentration cycles
            buffer_mgr: DataAcquisitionManager for real-time sensorgram monitoring
            channels: Channels to monitor for detection (e.g., "ABCD", "AC")
        """
        super().__init__(parent)
        self.sample_info = sample_info
        self.injection_number = injection_number
        self.total_injections = total_injections
        self.buffer_mgr = buffer_mgr
        self.detection_channels = channels or "ABCD"
        self.detection_active = False
        self.window_start_time = None  # Time when "Set Injection Flag" clicked
        self.last_detection_time = None
        # Detection result (stored for coordinator to use for flag placement)
        self.detected_injection_time: Optional[float] = None
        self.detected_channel: Optional[str] = None
        self.detected_confidence: Optional[float] = None
        self._status_label = None
        self._set_flag_btn = None
        self._detection_timer = None
        self._update_timer = None
        self._detection_start_time = None
        self._window_elapsed = 0
        self._user_done_injecting = False  # Flag for when user clicks "Done"
        self._done_timestamp = None  # When user clicked "Done"

        # Set window title based on mode
        if injection_number and total_injections:
            self.setWindowTitle(f"Manual Injection {injection_number} of {total_injections}")
        else:
            self.setWindowTitle("Manual Injection Required")

        self.setModal(True)  # Block execution
        self.setMinimumWidth(360)
        self.setMinimumHeight(180)
        self.setMaximumWidth(420)
        self.setMaximumHeight(220)

        # Remove close button (force user to click Complete/Cancel)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )

        self._setup_ui()

    def _setup_ui(self):
        """Build minimal, semi-transparent dialog UI for injection monitoring."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # Semi-transparent background (rgba allows seeing graph below)
        self.setStyleSheet("""
            QDialog {
                background: rgba(255, 255, 255, 0.95);
                border-radius: 8px;
            }
        """)

        # Compact title + sample info on one line
        sample_id = self.sample_info.get("sample_id", "Unknown")
        conc = self.sample_info.get("concentration")
        units = self.sample_info.get("units", "nM")

        if self.injection_number and self.total_injections:
            title = f"💉 Injection {self.injection_number}/{self.total_injections}"
        else:
            title = "💉 Manual Injection"

        if conc is not None:
            header_text = f"{title}  •  {sample_id}  ({conc} {units})"
        else:
            header_text = f"{title}  •  {sample_id}"

        header = QLabel(header_text)
        header.setStyleSheet("""
            font-size: 13px;
            font-weight: 600;
            color: #1D1D1F;
            font-family: -apple-system, 'SF Pro Text', sans-serif;
        """)
        main_layout.addWidget(header)

        # Status label (countdown/detection status)
        self._status_label = QLabel("🔍 Monitoring for injection...")
        self._status_label.setStyleSheet("""
            font-size: 14px;
            color: #FF9500;
            font-weight: 500;
            text-align: center;
            padding: 6px 0px;
        """)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self._status_label)

        # Compact button row
        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.setContentsMargins(0, 4, 0, 0)

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(32)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #F5F5F7;
                padding: 0px 16px;
                font-size: 13px;
                font-weight: 500;
                color: #1D1D1F;
                border-radius: 6px;
                font-family: -apple-system, 'SF Pro Text', sans-serif;
            }
            QPushButton:hover {
                background: #E5E5EA;
            }
            QPushButton:pressed {
                background: #D1D1D6;
            }
        """)
        cancel_btn.clicked.connect(self._on_cancel)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        button_row.addWidget(cancel_btn)

        button_row.addStretch()

        # Done button (primary)
        self._set_flag_btn = QPushButton("✓ Done Injecting")
        self._set_flag_btn.setFixedHeight(32)
        self._set_flag_btn.setStyleSheet("""
            QPushButton {
                background: #34C759;
                padding: 0px 20px;
                font-size: 13px;
                font-weight: 600;
                color: white;
                border-radius: 6px;
                font-family: -apple-system, 'SF Pro Text', sans-serif;
            }
            QPushButton:hover {
                background: #2DA84C;
            }
            QPushButton:pressed {
                background: #248A3D;
            }
            QPushButton:disabled {
                background: #E5E5EA;
                color: #86868B;
            }
        """)
        self._set_flag_btn.clicked.connect(self._on_done_injecting)
        self._set_flag_btn.setDefault(True)
        self._set_flag_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        button_row.addWidget(self._set_flag_btn)

        main_layout.addLayout(button_row)

    def showEvent(self, event):
        """Dialog shown - auto-start detection monitoring immediately."""
        super().showEvent(event)
        # Auto-start detection when dialog appears
        self._start_detection()

    def _start_detection(self):
        """Auto-start detection monitoring when dialog appears."""
        if not self.buffer_mgr or not self.buffer_mgr.timeline_data:
            from affilabs.utils.logger import logger
            logger.warning("Cannot start detection - no data available")
            self._status_label.setText("⚠ No data available. Ensure acquisition is running.")
            self._status_label.setStyleSheet("""
                font-size: 18px;
                color: #FF3B30;
                font-weight: 600;
                text-align: center;
                padding: 20px 0px;
            """)
            return

        # Get current time as window start
        first_channel = self.detection_channels[0].lower()
        if first_channel in self.buffer_mgr.timeline_data:
            channel_data = self.buffer_mgr.timeline_data[first_channel]
            if channel_data and len(channel_data.time) > 0:
                import numpy as np
                times = np.array(channel_data.time)
                self.window_start_time = times[-1]  # Current time = window start
            else:
                from affilabs.utils.logger import logger
                logger.warning("No time data available in channel")
                return
        else:
            from affilabs.utils.logger import logger
            logger.warning(f"Channel {first_channel} not found in timeline data")
            return

        # Start detection
        self.detection_active = True
        self._user_done_injecting = False
        self._done_timestamp = None
        self._window_elapsed = 0
        import time
        self._detection_start_time = time.time()

        # Update status
        self._status_label.setText("🔍 Monitoring for injection...")
        self._status_label.setStyleSheet("""
            font-size: 18px;
            color: #FF9500;
            font-weight: 600;
            text-align: center;
            padding: 20px 0px;
        """)

        from affilabs.utils.logger import logger
        logger.info(f"Auto-detection started - monitoring for injection")

        # Start detection timer (check every 200ms)
        self._detection_timer = QTimer(self)
        self._detection_timer.timeout.connect(self._check_for_injection_in_window)
        self._detection_timer.start(200)

        # Start update timer to show elapsed time (update every 1 second)
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_detection_status)
        self._update_timer.start(1000)

    def _on_done_injecting(self):
        """User clicked 'Done Injecting' - mark as done but continue monitoring for 10 more seconds."""
        self._user_done_injecting = True
        import time
        self._done_timestamp = time.time()

        from affilabs.utils.logger import logger
        logger.info("User marked injection as done - continuing to monitor for 10 more seconds")

        # Disable button and update status
        self._set_flag_btn.setEnabled(False)
        self._set_flag_btn.setText("✓ Monitoring (10s)")

        self._status_label.setText("✓ Injection complete. Finalizing measurement...")
        self._status_label.setStyleSheet("""
            font-size: 18px;
            color: #34C759;
            font-weight: 600;
            text-align: center;
            padding: 20px 0px;
        """)

    def _on_set_flag(self):
        """Legacy method - now redirects to _start_detection."""
        self._start_detection()

    def _check_for_injection_in_window(self):
        """Check for injection continuously while monitoring.

        Hard timeout: 60 seconds total from dialog appearance.
        User must complete injection within this window.
        """
        if not self.detection_active or not self.buffer_mgr or self.window_start_time is None:
            return

        try:
            from affilabs.utils.spr_signal_processing import auto_detect_injection_point
            import numpy as np
            import time

            # Hard 60-second limit from dialog start
            time_since_start = time.time() - self._detection_start_time
            if time_since_start >= 60.0:
                # Total 60 seconds elapsed - close dialog
                self._on_detection_timeout()
                return

            # Try each channel in priority order (A, B, C, D)
            for channel_letter in self.detection_channels.lower():
                if channel_letter not in self.buffer_mgr.timeline_data:
                    continue

                channel_data = self.buffer_mgr.timeline_data[channel_letter]
                if not channel_data or len(channel_data.time) < 10:
                    continue

                times = np.array(channel_data.time)
                wavelengths = np.array(channel_data.wavelength)

                if len(times) < 10 or len(wavelengths) < 10:
                    continue

                # Get current time in data
                current_time = times[-1]

                # Define search window: from start until now (continuous monitoring)
                window_start = self.window_start_time
                window_end = current_time

                # Extract data within window
                window_mask = (times >= window_start) & (times <= window_end)
                window_times = times[window_mask]
                window_wl = wavelengths[window_mask]

                # Need minimum data points
                if len(window_times) < 10:
                    # Not enough data yet, keep waiting
                    continue

                # Convert wavelength to RU (baseline-corrected)
                baseline = window_wl[0] if len(window_wl) > 0 else 0
                window_ru = (window_wl - baseline) * 355.0

                # Run detection on windowed data
                result = auto_detect_injection_point(
                    window_times,
                    window_ru
                )

                # Accept detection if confidence > 30%
                if result['injection_time'] is not None and result['confidence'] > 0.30:
                    injection_time = result['injection_time']
                    confidence = result['confidence']
                    self._on_injection_detected(injection_time, confidence, channel_letter)
                    return

        except Exception as e:
            from affilabs.utils.logger import logger
            logger.debug(f"Detection check error: {e}")

    def _update_detection_status(self):
        """Update status label to show elapsed time and remaining injection window."""
        if not self.detection_active or not self._detection_start_time:
            return

        import time
        elapsed = time.time() - self._detection_start_time
        self._window_elapsed = int(elapsed)
        remaining = max(0, 60 - self._window_elapsed)

        if self._user_done_injecting and self._done_timestamp:
            # User clicked Done - show final measurement phase with countdown
            self._status_label.setText(
                f"✓ Finalizing measurement ({remaining}s remaining)..."
            )
        else:
            # Still waiting for injection - show injection window countdown
            self._status_label.setText(
                f"🔍 Inject within {remaining}s ({self._window_elapsed}s used)..."
            )

        from affilabs.utils.logger import logger
        logger.debug(f"Injection window: {self._window_elapsed}s / 60s")

    def _on_injection_detected(self, injection_time: float, confidence: float, channel: str):
        """Windowed detection found injection peak - close dialog."""
        if not self.detection_active:
            return

        self.detection_active = False
        if self._detection_timer:
            self._detection_timer.stop()
        if self._update_timer:
            self._update_timer.stop()

        # Store detection result for coordinator to use for flag placement
        self.detected_injection_time = injection_time
        self.detected_channel = channel
        self.detected_confidence = confidence

        from affilabs.utils.logger import logger
        logger.info(f"✓ Injection detected at {injection_time:.2f}s (confidence: {confidence*100:.0f}%) on channel {channel}")

        # Update UI before closing
        self._status_label.setText(f"✓ Injection detected at {injection_time:.1f}s!\n(confidence: {confidence*100:.0f}%)")
        self._status_label.setStyleSheet("""
            font-size: 18px;
            color: #34C759;
            font-weight: 600;
            text-align: center;
            padding: 20px 0px;
        """)

        # Emit signal and close
        self.injection_detected.emit()
        self.injection_complete.emit()
        self.accept()

    def _on_detection_timeout(self):
        """60-second injection window expired."""
        if not self.detection_active:
            return

        self.detection_active = False
        if self._detection_timer:
            self._detection_timer.stop()
        if self._update_timer:
            self._update_timer.stop()

        from affilabs.utils.logger import logger
        logger.warning("⚠ 60-second injection window expired - no clear injection peak detected")

        # Update UI to show timeout
        self._status_label.setText("⚠ 60-second window expired\nNo injection peak detected\nManual adjustment available in Edits tab")
        self._status_label.setStyleSheet("""
            font-size: 16px;
            color: #FF9500;
            font-weight: 600;
            text-align: center;
            padding: 20px 0px;
        """)

        # Auto-close dialog after 2 seconds
        close_timer = QTimer(self)
        close_timer.setSingleShot(True)
        close_timer.timeout.connect(lambda: (self.injection_complete.emit(), self.accept()))
        close_timer.start(2000)  # 2 second delay

    def _on_cancel(self):
        """User cancelled injection."""
        self.detection_active = False
        if self._detection_timer:
            self._detection_timer.stop()
        if self._update_timer:
            self._update_timer.stop()

        from affilabs.utils.logger import logger
        logger.info("⚠️ User cancelled manual injection")

        self.injection_cancelled.emit()
        self.reject()
