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
- Real-time background detection of injection peak
- Auto-closes when injection detected (Option A: Background Real-Time Detection)
- Apple HIG design matching existing dialogs
- Displays sample info parsed from cycle name/notes

REAL-TIME DETECTION:
- Starts monitoring sensorgram data when dialog opens
- Automatically flags injection when peak detected
- Shows "⏳ Detecting injection..." → "✓ Injection detected!" status
- User just injects, no button clicking needed
- Detection runs indefinitely, user can cancel anytime

USAGE:
    from affilabs.dialogs.manual_injection_dialog import ManualInjectionDialog
    from affilabs.utils.sample_parser import parse_sample_info

    # With real-time detection (recommended)
    sample_info = parse_sample_info(cycle)
    dialog = ManualInjectionDialog(
        sample_info,
        injection_number=1,
        total_injections=3,
        buffer_mgr=buffer_manager,  # For real-time detection
        channels="ABCD",             # Channels to monitor
        parent=main_window
    )

    result = dialog.exec()  # Blocks until detection completes or user cancels
    if result == ManualInjectionDialog.DialogCode.Accepted:
        # Injection detected automatically
        continue_cycle()
    else:
        # User cancelled
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

    Performs real-time background detection of injection peak.
    Automatically closes when injection detected, or user can manually cancel.
    Displays sample information extracted from cycle metadata.

    Supports both single injections and multi-injection concentration cycles.

    Attributes:
        sample_info: Dictionary with sample details (from parse_sample_info)
        injection_number: Current injection number (1-indexed) for concentration cycles
        total_injections: Total number of injections planned
        buffer_mgr: DataAcquisitionManager for real-time sensorgram monitoring
        channels: Channels to monitor for injection detection (e.g., "ABCD")
        detection_active: Whether background detection is running

    Signals:
        injection_complete: Emitted when injection detected or user confirms
        injection_cancelled: Emitted when user clicks "Cancel Cycle"
        injection_detected: Emitted when real-time detection finds peak
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
        self.last_detection_time = None
        self._status_label = None
        self._detection_timer = None
        self._update_timer = None
        self._detection_start_time = None
        self._data_points_at_start = 0

        # Set window title based on mode
        if injection_number and total_injections:
            self.setWindowTitle(f"Manual Injection {injection_number} of {total_injections}")
        else:
            self.setWindowTitle("Manual Injection Required")

        self.setModal(True)  # Block execution
        self.setMinimumWidth(480)
        self.setMinimumHeight(320)

        # Remove close button (force user to click Complete/Cancel)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )

        self._setup_ui()

    def _setup_ui(self):
        """Build dialog UI with modern, clean design matching calibration dialogs."""
        # Main container with white background
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Set dialog background
        self.setStyleSheet("""
            QDialog {
                background: #FFFFFF;
            }
        """)

        # Header section with flat blue background
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: #007AFF;
            }
        """)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(32, 24, 32, 24)
        header_layout.setSpacing(8)

        # Title with injection number
        if self.injection_number and self.total_injections:
            title_text = f"Manual Injection {self.injection_number} of {self.total_injections}"
        else:
            title_text = "Manual Injection Required"

        title = QLabel(title_text)
        title.setStyleSheet("""
            font-size: 24px;
            font-weight: 700;
            color: white;
            font-family: -apple-system, 'SF Pro Display', sans-serif;
        """)
        header_layout.addWidget(title)

        # Subtitle instruction
        subtitle = QLabel("Inject sample via syringe, then confirm completion below")
        subtitle.setStyleSheet("""
            font-size: 14px;
            font-weight: 400;
            color: rgba(255, 255, 255, 0.9);
            font-family: -apple-system, 'SF Pro Text', sans-serif;
        """)
        header_layout.addWidget(subtitle)

        main_layout.addWidget(header)

        # Content section
        content = QFrame()
        content.setStyleSheet("""
            QFrame {
                background: #F8F9FA;
            }
        """)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(32, 32, 32, 32)
        content_layout.setSpacing(20)

        # Sample information card
        info_card = QFrame()
        info_card.setStyleSheet("""
            QFrame {
                background: white;
            }
        """)
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(20, 20, 20, 20)
        info_layout.setSpacing(16)

        # Card title
        card_title = QLabel("💉 Injection Details")
        card_title.setStyleSheet("""
            font-size: 15px;
            font-weight: 600;
            color: #1D1D1F;
            font-family: -apple-system, 'SF Pro Text', sans-serif;
        """)
        info_layout.addWidget(card_title)

        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background: #E5E5EA; max-height: 1px; border: none;")
        info_layout.addWidget(separator)

        # Sample details with better formatting
        sample_id = self.sample_info.get("sample_id", "Unknown Sample")
        conc = self.sample_info.get("concentration")
        units = self.sample_info.get("units", "nM")
        channels = self.sample_info.get("channels")

        # Sample name - largest text
        sample_label = QLabel(f"<span style='color: #86868B; font-size: 12px;'>SAMPLE</span><br>"
                              f"<span style='font-size: 18px; font-weight: 600; color: #007AFF;'>{sample_id}</span>")
        info_layout.addWidget(sample_label)

        # Two-column layout for concentration and channels (if applicable)
        details_layout = QHBoxLayout()
        details_layout.setSpacing(24)

        # Concentration column
        if conc is not None:
            conc_widget = QFrame()
            conc_layout = QVBoxLayout(conc_widget)
            conc_layout.setContentsMargins(0, 0, 0, 0)
            conc_layout.setSpacing(4)

            conc_header = QLabel("CONCENTRATION")
            conc_header.setStyleSheet("font-size: 11px; color: #86868B; font-weight: 600;")
            conc_layout.addWidget(conc_header)

            conc_value = QLabel(f"{conc} {units}")
            conc_value.setStyleSheet("font-size: 20px; color: #1D1D1F; font-weight: 700;")
            conc_layout.addWidget(conc_value)

            details_layout.addWidget(conc_widget)

        # Channels column (only show for systems with valve routing, not P4SPR)
        if channels is not None:
            channel_widget = QFrame()
            channel_layout = QVBoxLayout(channel_widget)
            channel_layout.setContentsMargins(0, 0, 0, 0)
            channel_layout.setSpacing(4)

            channel_header = QLabel("TARGET CHANNELS")
            channel_header.setStyleSheet("font-size: 11px; color: #86868B; font-weight: 600;")
            channel_layout.addWidget(channel_header)

            channel_value = QLabel(channels)
            channel_value.setStyleSheet("font-size: 20px; color: #1D1D1F; font-weight: 700;")
            channel_layout.addWidget(channel_value)

            details_layout.addWidget(channel_widget)

        details_layout.addStretch()

        info_layout.addLayout(details_layout)

        content_layout.addWidget(info_card)

        # Real-time detection status label - BIG and visible
        self._status_label = QLabel("⏳ Detecting injection...")
        self._status_label.setStyleSheet("""
            font-size: 18px;
            color: #FF9500;
            font-weight: 600;
            text-align: center;
            padding: 20px 0px;
        """)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self._status_label)

        # Button row with proper spacing
        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.setContentsMargins(0, 8, 0, 0)

        # Cancel button only
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(50)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #F5F5F7;
                padding: 0px 24px;
                font-size: 16px;
                font-weight: 500;
                color: #1D1D1F;
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

        content_layout.addLayout(button_row)

        main_layout.addWidget(content)

    def showEvent(self, event):
        """Start real-time injection detection when dialog is shown."""
        super().showEvent(event)
        if self.buffer_mgr:
            self._start_real_time_detection()

    def _start_real_time_detection(self):
        """Start background monitoring for injection peak."""
        self.detection_active = True

        # Record when detection started for timer display
        import time
        self._detection_start_time = time.time()

        # Record initial data point count
        if self.buffer_mgr and self.buffer_mgr.timeline_data:
            first_channel = self.detection_channels[0].lower()
            if first_channel in self.buffer_mgr.timeline_data:
                self._data_points_at_start = len(self.buffer_mgr.timeline_data[first_channel].time)

        # Start detection timer (check every 200ms)
        self._detection_timer = QTimer(self)
        self._detection_timer.timeout.connect(self._check_for_injection)
        self._detection_timer.start(200)

        # Start update timer to show elapsed time (update every 1 second)
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_detection_status)
        self._update_timer.start(1000)

    def _check_for_injection(self):
        """Check if injection peak has been detected in real-time data."""
        if not self.detection_active or not self.buffer_mgr:
            return

        try:
            from affilabs.utils.spr_signal_processing import auto_detect_injection_point
            import numpy as np

            # Try each channel in priority order (A, B, C, D)
            for channel_letter in self.detection_channels.lower():
                if channel_letter not in self.buffer_mgr.timeline_data:
                    continue

                channel_data = self.buffer_mgr.timeline_data[channel_letter]
                if not channel_data or len(channel_data.time) < 10:
                    continue

                # Need at least 20 new data points (showing injection is happening)
                current_points = len(channel_data.time)
                if current_points < self._data_points_at_start + 20:
                    continue

                # Analyze recent data (last 120 seconds)
                times = np.array(channel_data.time)
                spr_values = np.array(channel_data.spr)  # FIX: Use SPR signal, not wavelength!

                if len(times) < 10:
                    continue

                # Filter to recent data
                current_time = times[-1]
                lookback_start = current_time - 120.0
                recent_mask = times >= lookback_start

                recent_times = times[recent_mask]
                recent_spr = spr_values[recent_mask]  # FIX: Use SPR values

                if len(recent_times) < 10:
                    continue

                # Use auto_detect_injection_point
                result = auto_detect_injection_point(  # FIX: Returns dict, not tuple
                    recent_times,
                    recent_spr  # FIX: Pass SPR signal (RU), not wavelength
                )

                # Accept detection if confidence > 15%
                if result['injection_time'] is not None and result['confidence'] > 0.15:
                    injection_time = result['injection_time']
                    confidence = result['confidence']
                    self._on_injection_detected(injection_time, confidence, channel_letter)
                    return

        except Exception as e:
            from affilabs.utils.logger import logger
            logger.debug(f"Detection check error: {e}")

    def _update_detection_status(self):
        """Update status label to show elapsed detection time."""
        if not self.detection_active or not self._detection_start_time:
            return

        import time
        elapsed = time.time() - self._detection_start_time
        seconds = int(elapsed)

        # Emit signal for main window to update intelligence bar
        # Status label stays simple
        from affilabs.utils.logger import logger
        logger.debug(f"Detection elapsed: {seconds}s")

    def _on_injection_detected(self, injection_time: float, confidence: float, channel: str):
        """Auto-detection found injection peak - close dialog."""
        if not self.detection_active:
            return

        self.detection_active = False
        if self._detection_timer:
            self._detection_timer.stop()
        if self._update_timer:
            self._update_timer.stop()

        from affilabs.utils.logger import logger
        logger.info(f"✓ Injection detected at {injection_time:.2f}s (confidence: {confidence*100:.0f}%) on channel {channel}")

        # Update UI before closing
        self._status_label.setText(f"✓ Injection detected!\n(confidence: {confidence*100:.0f}%)")
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
