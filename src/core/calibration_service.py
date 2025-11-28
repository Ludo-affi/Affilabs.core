"""
CalibrationService - Unified calibration interface.

Merges CalibrationCoordinator + CalibrationManager into single service.
Handles UI interaction, threading, progress, and QC display.
"""

import threading
import numpy as np
from PySide6.QtCore import QObject, Signal
from typing import Optional
from utils.logger import logger
from core.calibration_data import CalibrationData


class CalibrationService(QObject):
    """Unified calibration service for UI and backend coordination.

    Replaces both CalibrationCoordinator and CalibrationManager with
    a single, streamlined interface.

    Signals:
        calibration_started: Emitted when calibration begins
        calibration_progress: Emitted with (message: str, percent: int)
        calibration_complete: Emitted with CalibrationData
        calibration_failed: Emitted with error message string
    """

    calibration_started = Signal()
    calibration_progress = Signal(str, int)  # (message, percent)
    calibration_complete = Signal(object)  # CalibrationData
    calibration_failed = Signal(str)

    def __init__(self, app):
        """Initialize calibration service.

        Args:
            app: Reference to main Application instance
        """
        super().__init__()
        self.app = app
        self._thread = None
        self._running = False
        self._calibration_dialog: Optional[object] = None
        self._calibration_completed: bool = False
        self._current_calibration_data: Optional[CalibrationData] = None

    def start_calibration(self) -> bool:
        """Start calibration in background thread.

        Returns:
            True if calibration started, False if already running
        """
        if self._running:
            logger.warning("Calibration already in progress")
            return False

        logger.info("=" * 80)
        logger.info("🎬 CALIBRATION SERVICE: Starting calibration...")
        logger.info("=" * 80)

        # Reset state
        self._calibration_completed = False
        self._current_calibration_data = None
        self._running = True

        # Show progress dialog
        self._show_progress_dialog()

        # Emit started signal
        self.calibration_started.emit()

        # Run in background thread
        self._thread = threading.Thread(
            target=self._run_calibration,
            daemon=True,
            name="CalibrationService"
        )
        self._thread.start()
        return True

    def _show_progress_dialog(self) -> None:
        """Show calibration progress dialog."""
        from affilabs_core_ui import StartupCalibProgressDialog

        message = (
            "Please verify before calibrating:\n\n"
            "  ✓  Prism installed in sensor holder\n"
            "  ✓  Water or buffer applied to prism\n"
            "  ✓  No air bubbles visible\n"
            "  ✓  Temperature stabilized (10 min after power-on)\n\n"
            "Calibration takes approximately 30-60 seconds."
        )

        self._calibration_dialog = StartupCalibProgressDialog(
            parent=self.app.main_window,
            title="Calibrating SPR System",
            message=message,
            show_start_button=True
        )

        # Connect dialog signals
        self._calibration_dialog.start_clicked.connect(self._on_start_button_clicked)
        self._calibration_dialog.hide_progress_bar()
        self._calibration_dialog.show()
        self._calibration_dialog.enable_start_button_pre_calib()

        logger.info("✅ Calibration dialog displayed")

    def _on_start_button_clicked(self) -> None:
        """Handle Start button click - begin calibration or transfer to live view."""
        if self._calibration_completed:
            # Calibration complete - transfer to live acquisition
            logger.info("✅ User clicked Start - transferring to live view")

            # Close calibration dialog
            if self._calibration_dialog:
                self._calibration_dialog.accept()
                self._calibration_dialog = None

            # Start live acquisition
            if hasattr(self.app, 'data_mgr'):
                self.app.data_mgr.start_acquisition()

            return

        # Start calibration
        logger.info("🔄 User clicked Start - beginning calibration")

        # Update dialog
        if self._calibration_dialog:
            if self._calibration_dialog.start_button:
                self._calibration_dialog.start_button.setEnabled(False)
            self._calibration_dialog.show_progress_bar()
            self._calibration_dialog.update_status("Running LED intensity calibration...")

        # Launch calibration in background thread
        self._running = True
        self._thread = threading.Thread(target=self._run_calibration, daemon=True)
        self._thread.start()
        self.calibration_started.emit()

    def _run_calibration(self) -> None:
        """Main calibration routine (runs in background thread)."""
        try:
            # Get hardware
            self.calibration_progress.emit("Initializing...", 5)

            hardware_mgr = self.app.hardware_mgr
            ctrl = hardware_mgr.ctrl
            usb = hardware_mgr.usb

            if not ctrl:
                raise RuntimeError("Controller not connected")
            if not usb:
                raise RuntimeError("Spectrometer not connected")

            logger.info("✅ Hardware ready")

            # Load configuration
            self.calibration_progress.emit("Loading configuration...", 10)
            from settings import MIN_WAVELENGTH, MAX_WAVELENGTH
            from utils.device_configuration import DeviceConfiguration

            device_serial = getattr(usb, 'serial_number', None)
            device_config = DeviceConfiguration(device_serial=device_serial)

            # Get wavelength data
            self.calibration_progress.emit("Reading wavelength data...", 15)
            wave_data = usb.read_wavelength()
            wave_min_index = wave_data.searchsorted(MIN_WAVELENGTH)
            wave_max_index = wave_data.searchsorted(MAX_WAVELENGTH)

            # Load afterglow correction
            afterglow_correction = self._load_afterglow_correction()

            # Get LED timing from device config
            pre_led_delay_ms = device_config.get_pre_led_delay_ms()
            post_led_delay_ms = device_config.get_post_led_delay_ms()
            logger.info(f"📊 LED timing: PRE={pre_led_delay_ms}ms, POST={post_led_delay_ms}ms")

            # Run calibration
            from utils.led_calibration import perform_full_led_calibration

            logger.info("🚀 Starting 6-step calibration...")

            cal_result = perform_full_led_calibration(
                ctrl=ctrl,
                usb=usb,
                afterglow_correction=afterglow_correction,
                pre_led_delay_ms=pre_led_delay_ms,
                post_led_delay_ms=post_led_delay_ms,
                progress_callback=self._progress_callback
            )

            if not cal_result or not cal_result.success:
                raise RuntimeError("Calibration failed")

            # Create immutable CalibrationData
            self.calibration_progress.emit("Storing results...", 95)

            device_info = {
                'device_type': type(ctrl).__name__,
                'detector_serial': device_serial or 'N/A',
                'firmware_version': getattr(ctrl, 'version', 'N/A'),
                'pre_led_delay_ms': pre_led_delay_ms,
                'post_led_delay_ms': post_led_delay_ms
            }

            # Add wavelength indices to result
            cal_result.wave_min_index = wave_min_index
            cal_result.wave_max_index = wave_max_index

            calibration_data = CalibrationData.from_calibration_result(
                cal_result,
                device_info=device_info
            )

            if not calibration_data.validate():
                raise RuntimeError("Calibration data validation failed")

            logger.info("✅ Calibration data created and validated")

            # Store calibration data
            self._current_calibration_data = calibration_data
            self._calibration_completed = True
            self._running = False

            # Emit completion signal
            self.calibration_complete.emit(calibration_data)

            # Handle post-calibration UI
            self._on_calibration_complete_ui(calibration_data)

        except Exception as e:
            logger.error(f"❌ Calibration failed: {e}", exc_info=True)
            self._running = False
            self.calibration_failed.emit(str(e))

            if self._calibration_dialog:
                self._calibration_dialog.update_title("❌ Calibration Failed")
                self._calibration_dialog.update_status(f"Error: {e}")
                self._calibration_dialog.hide_progress_bar()

    def _load_afterglow_correction(self):
        """Load afterglow correction if available."""
        try:
            from afterglow_correction import AfterglowCorrection
            from utils.device_integration import get_device_optical_calibration_path

            optical_cal_path = get_device_optical_calibration_path()
            if optical_cal_path and optical_cal_path.exists():
                afterglow_correction = AfterglowCorrection(optical_cal_path)
                logger.info(f"✅ Loaded afterglow correction: {optical_cal_path.name}")
                return afterglow_correction
        except Exception as e:
            logger.debug(f"Afterglow correction not available: {e}")

        return None

    def _progress_callback(self, message: str) -> None:
        """Map calibration progress messages to percentages."""
        msg_lower = message.lower()

        if "step 1" in msg_lower:
            self.calibration_progress.emit(message, 20)
        elif "step 2" in msg_lower:
            self.calibration_progress.emit(message, 25)
        elif "step 3" in msg_lower:
            self.calibration_progress.emit(message, 35)
        elif "step 4" in msg_lower:
            self.calibration_progress.emit(message, 50)
        elif "step 5" in msg_lower:
            self.calibration_progress.emit(message, 70)
        elif "step 6" in msg_lower:
            self.calibration_progress.emit(message, 85)
        else:
            logger.info(f"Progress: {message}")

    def _on_calibration_complete_ui(self, calibration_data: CalibrationData) -> None:
        """Handle post-calibration UI updates.

        Args:
            calibration_data: Immutable calibration results
        """
        logger.info("🎯 Calibration complete - updating UI...")

        # Update dialog
        if self._calibration_dialog:
            self._calibration_dialog.update_title("✅ Calibration Complete!")
            self._calibration_dialog.update_status(
                "Calibration successful! Review QC graphs, then click Start to begin live acquisition."
            )
            self._calibration_dialog.hide_progress_bar()

            # Re-enable Start button for transfer to live view
            if self._calibration_dialog.start_button:
                self._calibration_dialog.start_button.setEnabled(True)
                self._calibration_dialog.start_button.setText("Start")

        # Show QC dialog
        self._show_qc_dialog(calibration_data)

        logger.info("=" * 80)
        logger.info("Calibration complete - waiting for user to click Start")
        logger.info("=" * 80)

    def _show_qc_dialog(self, calibration_data: CalibrationData) -> None:
        """Show QC dialog with calibration results.

        Args:
            calibration_data: Immutable calibration results
        """
        try:
            from widgets.calibration_qc_dialog import CalibrationQCDialog

            # Convert to dict for QC dialog
            qc_data = calibration_data.to_dict()

            logger.info("📊 Showing QC report dialog...")
            CalibrationQCDialog.show_qc_report(
                parent=self.app.main_window,
                calibration_data=qc_data
            )

            logger.info("✅ QC report displayed")

        except Exception as e:
            logger.error(f"❌ Failed to show QC report: {e}", exc_info=True)

    def get_current_calibration(self) -> Optional[CalibrationData]:
        """Get current calibration data.

        Returns:
            CalibrationData if calibration completed, None otherwise
        """
        return self._current_calibration_data
