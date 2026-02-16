"""Manual Injection Dialog - User prompt for manual syringe injection.

This dialog appears when user needs to perform a manual syringe injection.
Supports both single injections and multi-injection binding cycles.

MODES:
1. Single Injection (regular cycles):
   - Shows sample info and asks user to inject

2. Binding Cycle (multi-injection):
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

from typing import Any, TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from affilabs.core.data_acquisition_manager import DataAcquisitionManager

from affilabs.utils.logger import logger

# Configuration constants
INJECTION_WINDOW_SECONDS = 60
DETECTION_CONFIDENCE_THRESHOLD = 0.30
DETECTION_CHECK_INTERVAL_MS = 200
UPDATE_STATUS_INTERVAL_MS = 1000
FINAL_MEASUREMENT_TIMEOUT_MS = 2000
MINIMUM_DATA_POINTS = 10
RU_CONVERSION_FACTOR = 355.0
FINAL_MEASUREMENT_DURATION_SECONDS = 10
CHANNEL_SCAN_GRACE_SECONDS = 10  # Keep scanning other channels after first detection


class ManualInjectionDialog(QDialog):
    """Modal dialog prompting user to perform manual injection.

    Auto-starts injection detection when dialog appears.
    User has 60 SECONDS TOTAL to inject and confirm with "Done Injecting" button.
    Auto-closes when injection detected within 60-second window OR at time expiration.

    Supports both single injections and multi-injection binding cycles.

    Attributes:
        sample_info: Dictionary with sample details (from parse_sample_info)
        injection_number: Current injection number (1-indexed) for binding cycles
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
        parent: QDialog | None = None,
        injection_number: int | None = None,
        total_injections: int | None = None,
        buffer_mgr: DataAcquisitionManager | None = None,
        channels: str | None = None,
        detection_priority: str = "auto",
        method_mode: str | None = None,
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
            injection_number: Current injection number (1-indexed) for binding cycles
            total_injections: Total number of injections planned for binding cycles
            buffer_mgr: DataAcquisitionManager for real-time sensorgram monitoring
            channels: Channels to monitor for detection (e.g., "ABCD", "AC")
            detection_priority: Detection priority from cycle ('auto', 'priority', 'off')
            method_mode: Method mode from cycle ('manual', 'semi-automated', None)
        """
        super().__init__(parent)
        self.sample_info = sample_info
        self.injection_number = injection_number
        self.total_injections = total_injections
        self.buffer_mgr = buffer_mgr
        self.detection_channels = channels or "ABCD"
        self.detection_priority = detection_priority or "auto"
        self.method_mode = method_mode
        self.detection_active = False
        self.window_start_time = None  # Time when "Set Injection Flag" clicked
        self.last_detection_time = None
        # Detection result (stored for coordinator to use for flag placement)
        self.detected_injection_time: float | None = None
        self.detected_channel: str | None = None
        self.detected_confidence: float | None = None
        self._status_label: QLabel | None = None
        self._set_flag_btn: QPushButton | None = None
        self._detection_timer: QTimer | None = None
        self._update_timer: QTimer | None = None
        self._detection_start_time: float | None = None
        self._window_elapsed: int = 0
        self._user_done_injecting: bool = False
        self._done_timestamp: float | None = None

        # Channel LED indicators for real-time detection feedback
        self._channel_leds: dict[str, QLabel] = {}  # Maps channel letter to LED label
        self._channel_detected: dict[str, bool] = {}  # Tracks detection state per channel
        self._first_detection_time: float | None = None  # When first channel was detected
        self._detected_channels_results: dict[str, dict] = {}  # Per-channel: {time, confidence}

        # Set window title based on mode
        if injection_number and total_injections:
            self.setWindowTitle(f"Manual Injection {injection_number} of {total_injections}")
        else:
            self.setWindowTitle("Manual Injection Required")

        self.setModal(True)  # Block execution
        self.setMinimumWidth(380)
        self.setMinimumHeight(220)
        self.setMaximumWidth(450)
        self.setMaximumHeight(280)

        # Remove close button (force user to click Complete/Cancel)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )

        self._setup_ui()

    def _setup_ui(self) -> None:
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

        # Channel LED indicators row
        led_row = QHBoxLayout()
        led_row.setSpacing(12)
        led_row.setContentsMargins(0, 8, 0, 8)
        led_row.addStretch()

        for channel in self.detection_channels.upper():
            # Container for each channel LED
            ch_container = QHBoxLayout()
            ch_container.setSpacing(4)

            # Channel label (A, B, C, D)
            ch_label = QLabel(f"Ch {channel}")
            ch_label.setStyleSheet("""
                font-size: 11px;
                font-weight: 500;
                color: #86868B;
                font-family: -apple-system, 'SF Pro Text', sans-serif;
            """)
            ch_container.addWidget(ch_label)

            # LED indicator (circle)
            led = QLabel("●")
            led.setStyleSheet("""
                font-size: 16px;
                color: #D1D1D6;
                padding: 0px 2px;
            """)
            led.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ch_container.addWidget(led)

            # Store reference to LED for updates
            self._channel_leds[channel] = led
            self._channel_detected[channel] = False

            led_row.addLayout(ch_container)

        led_row.addStretch()
        main_layout.addLayout(led_row)

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
        cancel_btn.setShortcut(QKeySequence.Cancel)
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
        self._set_flag_btn = QPushButton("✓ 1:00")
        self._set_flag_btn.setFixedHeight(32)
        self._set_flag_btn.setMinimumWidth(130)  # Make button wider to show time
        self._set_flag_btn.setShortcut(QKeySequence.Open)  # Return/Enter key
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

    def showEvent(self, event) -> None:
        """Dialog shown - auto-start detection monitoring immediately."""
        super().showEvent(event)
        # Auto-start detection when dialog appears
        self._start_detection()

    def closeEvent(self, event) -> None:
        """Dialog closing - clean up resources (timers, popout window)."""
        self._cleanup_resources()
        super().closeEvent(event)

    def _cleanup_resources(self) -> None:
        """Stop all timers to prevent resource leaks."""
        self.detection_active = False
        if self._detection_timer:
            self._detection_timer.stop()
        if self._update_timer:
            self._update_timer.stop()

    def _start_detection(self) -> None:
        """Auto-start detection monitoring when dialog appears."""
        if not self.buffer_mgr or not self.buffer_mgr.timeline_data:
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
                logger.warning("No time data available in channel")
                return
        else:
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

        logger.info("Auto-detection started - monitoring for injection")

        # Start detection timer (check every 200ms)
        self._detection_timer = QTimer(self)
        self._detection_timer.timeout.connect(self._check_for_injection_in_window)
        self._detection_timer.start(DETECTION_CHECK_INTERVAL_MS)

        # Start update timer to show elapsed time (update every 1 second)
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_detection_status)
        self._update_timer.start(UPDATE_STATUS_INTERVAL_MS)

    def _on_done_injecting(self) -> None:
        """User clicked 'Done Injecting' - mark as done but continue monitoring for 10 more seconds."""
        self._user_done_injecting = True
        import time
        self._done_timestamp = time.time()

        logger.info("User marked injection as done - continuing to monitor for 10 more seconds")

        # Disable button and update status
        self._set_flag_btn.setEnabled(False)

        # Update button with remaining time
        remaining = max(0, INJECTION_WINDOW_SECONDS - int(time.time() - self._detection_start_time))
        self._set_flag_btn.setText(f"✓ {self._format_time_display(remaining)}")


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

    def _get_sensitivity_factor(self) -> float:
        """Compute sensitivity_factor from detection_priority and method_mode.

        Returns:
            float: ≥1.0. Manual default=2.0 (conservative), pump=0.75 (tight).
                   'off' returns 999.0 (effectively disables detection).
        """
        priority = self.detection_priority
        mode = self.method_mode

        if priority == "off":
            return 999.0  # Effectively disable detection
        elif priority == "priority":
            return 1.0  # Most sensitive (still ≥ 2.5σ)
        elif priority == "auto":
            # Mode-dependent defaults
            if mode == "manual":
                return 2.0  # Manual syringe — conservative to avoid noise triggers
            elif mode == "semi-automated":
                return 0.75  # Pump-controlled — tight, predictable signal
            else:
                return 2.0  # Fallback to conservative
        else:
            return 2.0

    def _check_for_injection_in_window(self):
        """Check for injection continuously across all channels.

        After first channel detection, continues scanning remaining channels
        for up to CHANNEL_SCAN_GRACE_SECONDS before closing the dialog.
        This gives real-time LED feedback for all channels.

        Hard timeout: 60 seconds total from dialog appearance.
        """
        if not self.detection_active or not self.buffer_mgr or self.window_start_time is None:
            return

        # Skip auto-detection entirely when detection is off
        if self.detection_priority == "off":
            return

        try:
            from affilabs.utils.spr_signal_processing import auto_detect_injection_point
            import numpy as np
            import time

            now = time.time()

            # Hard 60-second limit from dialog start
            time_since_start = now - self._detection_start_time
            if time_since_start >= INJECTION_WINDOW_SECONDS:
                self._on_detection_timeout()
                return

            # Grace period expired — close with what we have
            if self._first_detection_time is not None:
                grace_elapsed = now - self._first_detection_time
                if grace_elapsed >= CHANNEL_SCAN_GRACE_SECONDS:
                    logger.info(
                        f"Channel scan grace period expired ({CHANNEL_SCAN_GRACE_SECONDS}s) — "
                        f"detected: {list(self._detected_channels_results.keys())}"
                    )
                    self._finalize_detection()
                    return

            # Scan each channel (skip already-detected ones)
            for channel_letter in self.detection_channels.lower():
                ch_upper = channel_letter.upper()

                # Skip channels already detected
                if ch_upper in self._detected_channels_results:
                    continue

                if channel_letter not in self.buffer_mgr.timeline_data:
                    continue

                channel_data = self.buffer_mgr.timeline_data[channel_letter]
                if not channel_data or len(channel_data.time) < 10:
                    continue

                times = np.array(channel_data.time)
                wavelengths = np.array(channel_data.wavelength)

                if len(times) < 10 or len(wavelengths) < 10:
                    continue

                # Define search window: from start until now
                window_mask = (times >= self.window_start_time) & (times <= times[-1])
                window_times = times[window_mask]
                window_wl = wavelengths[window_mask]

                if len(window_times) < 10:
                    continue

                # Convert wavelength to RU (baseline-corrected)
                baseline = window_wl[0] if len(window_wl) > 0 else 0
                window_ru = (window_wl - baseline) * RU_CONVERSION_FACTOR

                result = auto_detect_injection_point(
                    window_times, window_ru,
                    sensitivity_factor=self._get_sensitivity_factor(),
                )

                if result['injection_time'] is not None and result['confidence'] > DETECTION_CONFIDENCE_THRESHOLD:
                    # Light up LED
                    self._update_channel_led(channel_letter, detected=True)

                    # Store per-channel result
                    self._detected_channels_results[ch_upper] = {
                        'time': result['injection_time'],
                        'confidence': result['confidence'],
                    }

                    logger.info(
                        f"Channel {ch_upper} injection detected at "
                        f"t={result['injection_time']:.1f}s "
                        f"(confidence: {result['confidence']:.0%})"
                    )

                    # First detection — store primary result and start grace timer
                    if self._first_detection_time is None:
                        self._first_detection_time = now
                        self.detected_injection_time = result['injection_time']
                        self.detected_channel = channel_letter
                        self.detected_confidence = result['confidence']
                        self.injection_detected.emit()

            # All monitored channels detected — close immediately
            all_detected = all(
                ch.upper() in self._detected_channels_results
                for ch in self.detection_channels
            )
            if all_detected and self._first_detection_time is not None:
                logger.info(f"All {len(self._detected_channels_results)} channels detected — closing dialog")
                self._finalize_detection()

        except Exception as e:
            logger.debug(f"Detection check error: {e}")

    def _update_detection_status(self) -> None:
        """Update status label to show elapsed time and per-channel detection progress."""
        if not self.detection_active or not self._detection_start_time:
            return

        import time
        now = time.time()
        elapsed = now - self._detection_start_time
        self._window_elapsed = int(elapsed)
        remaining = max(0, INJECTION_WINDOW_SECONDS - self._window_elapsed)

        # Update button with remaining time in MM:SS format
        time_text = self._format_time_display(remaining)

        if self._first_detection_time is not None:
            # At least one channel detected — show scanning progress
            detected_chs = list(self._detected_channels_results.keys())
            total_chs = len(self.detection_channels)
            grace_remaining = max(0, int(CHANNEL_SCAN_GRACE_SECONDS - (now - self._first_detection_time)))
            self._status_label.setText(
                f"✓ Detected: {', '.join(detected_chs)}  "
                f"({len(detected_chs)}/{total_chs} channels, {grace_remaining}s scan)"
            )
            self._status_label.setStyleSheet("""
                font-size: 14px;
                color: #34C759;
                font-weight: 600;
                text-align: center;
                padding: 6px 0px;
            """)
            self._set_flag_btn.setText(f"✓ {time_text}")
        elif self._user_done_injecting and self._done_timestamp:
            self._status_label.setText(
                f"✓ Finalizing measurement ({remaining}s remaining)..."
            )
            self._set_flag_btn.setText(f"✓ {time_text}")
        else:
            self._status_label.setText(
                f"🔍 Inject within {remaining}s ({self._window_elapsed}s used)..."
            )
            self._set_flag_btn.setText(f"✓ {time_text}")

        logger.debug(f"Injection window: {self._window_elapsed}s / 60s")

    def _finalize_detection(self) -> None:
        """All channels scanned (or grace period expired) — close dialog with results."""
        if not self.detection_active:
            return

        self.detection_active = False
        if self._detection_timer:
            self._detection_timer.stop()
        if self._update_timer:
            self._update_timer.stop()

        detected_chs = list(self._detected_channels_results.keys())
        logger.info(
            f"✓ Injection finalized — detected on {detected_chs} "
            f"(primary: {self.detected_channel}, t={self.detected_injection_time:.1f}s)"
        )

        # Update UI before closing
        ch_list = ", ".join(detected_chs) if detected_chs else "none"
        self._status_label.setText(f"✓ Injection detected on {ch_list}")
        self._status_label.setStyleSheet("""
            font-size: 18px;
            color: #34C759;
            font-weight: 600;
            text-align: center;
            padding: 20px 0px;
        """)

        # Emit signal and close
        self.injection_complete.emit()
        self.accept()

    def _on_detection_timeout(self) -> None:
        """60-second injection window expired."""
        if not self.detection_active:
            return

        # If some channels were detected, finalize with those results
        if self._first_detection_time is not None:
            self._finalize_detection()
            return

        self.detection_active = False
        if self._detection_timer:
            self._detection_timer.stop()
        if self._update_timer:
            self._update_timer.stop()

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
        close_timer.start(FINAL_MEASUREMENT_TIMEOUT_MS)

    def _on_cancel(self) -> None:
        """User cancelled injection."""
        self.detection_active = False
        if self._detection_timer:
            self._detection_timer.stop()
        if self._update_timer:
            self._update_timer.stop()

        logger.info("⚠️ User cancelled manual injection")

        self.injection_cancelled.emit()
        self.reject()

    def _update_channel_led(self, channel: str, detected: bool) -> None:
        """Update LED indicator for a specific channel.

        Args:
            channel: Channel letter (A, B, C, or D)
            detected: True if injection detected on this channel
        """
        channel_upper = channel.upper()
        if channel_upper not in self._channel_leds:
            return

        led = self._channel_leds[channel_upper]

        if detected and not self._channel_detected[channel_upper]:
            # Light up green when injection detected
            led.setStyleSheet("""
                font-size: 16px;
                color: #34C759;
                padding: 0px 2px;
            """)
            self._channel_detected[channel_upper] = True
            logger.debug(f"LED indicator: Channel {channel_upper} detected ✓")

    def _format_time_display(self, total_seconds: int) -> str:
        """Convert total seconds to MM:SS format string.

        Args:
            total_seconds: Total seconds to format

        Returns:
            Formatted time string like "1:23" or "0:45"
        """
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"

    def _validate_detection_prerequisites(self) -> bool:
        """Validate that prerequisites for detection are met before starting.

        Returns:
            True if all prerequisites met, False otherwise
        """
        if not self.buffer_mgr:
            logger.warning("Cannot start detection - no buffer manager")
            return False

        if not self.buffer_mgr.timeline_data:
            logger.warning("Cannot start detection - no timeline data")
            return False

        if not any(ch.lower() in self.buffer_mgr.timeline_data for ch in self.detection_channels):
            logger.warning(f"Cannot start detection - no data for channels {self.detection_channels}")
            return False

        return True

    def _show_error_state(self, message: str) -> None:
        """Display error state in UI with consistent formatting.

        Args:
            message: Error message to display
        """
        self._status_label.setText(f"⚠ {message}")
        self._status_label.setStyleSheet("""
            font-size: 18px;
            color: #FF3B30;
            font-weight: 600;
            text-align: center;
            padding: 20px 0px;
        """)

