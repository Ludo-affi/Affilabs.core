"""Calibration Coordinator - Simplified UI interface to CalibrationManager.

Handles UI interactions and delegates actual calibration to CalibrationManager.
"""

import numpy as np
from PySide6.QtCore import QObject, QTimer
from utils.logger import logger
from typing import Optional, Dict, Any


class CalibrationCoordinator(QObject):
    """Coordinates calibration UI with the CalibrationManager backend."""

    def __init__(self, app):
        """Initialize calibration coordinator.

        Args:
            app: Reference to main Application instance
        """
        super().__init__()
        self.app = app
        self._calibration_dialog: Optional[Any] = None
        self._calibration_completed: bool = False

        # Create calibration manager
        from core.calibration_manager import CalibrationManager
        self.manager = CalibrationManager(app)

        # Connect manager signals
        self.manager.calibration_started.connect(self._on_calibration_started)
        self.manager.calibration_progress.connect(self._on_calibration_progress)
        self.manager.calibration_complete.connect(self._on_calibration_complete)
        self.manager.calibration_failed.connect(self._on_calibration_failed)

    def start_calibration(self) -> None:
        """Start calibration routine and show progress dialog."""
        logger.info("🎬 Starting calibration...")

        # Reset state
        self._calibration_completed = False

        # Show progress dialog
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

            # Get calibration result
            from utils.calibration_ui_transfer import transfer_calibration_to_live_view, save_calibration_to_device_config

            # Build result object from data_mgr
            class SimpleCalResult:
                def __init__(self, data_mgr):
                    self.success = True
                    self.ref_intensity = data_mgr.ref_intensity
                    self.p_mode_intensity = getattr(data_mgr, 'p_mode_intensity', data_mgr.leds_calibrated)
                    self.integration_time = data_mgr.integration_time
                    self.num_scans = data_mgr.num_scans
                    self.wave_data = data_mgr.wave_data
                    self.dark_noise = data_mgr.dark_noise
                    self.s_ref_sig = data_mgr.ref_sig
                    self.ch_error_list = data_mgr.ch_error_list
                    self.wave_min_index = data_mgr.wave_min_index
                    self.wave_max_index = data_mgr.wave_max_index
                    self.s_ref_qc = getattr(data_mgr, 's_ref_qc_results', {})
                    self.verification = {}
                    self.calibration_method = 'standard'

            cal_result = SimpleCalResult(self.app.data_mgr)

            # Save calibration to device config
            try:
                save_calibration_to_device_config(
                    calibration_result=cal_result,
                    device_config=self.app.data_mgr.device_config if hasattr(self.app.data_mgr, 'device_config') else None
                )
                logger.info("✅ Calibration saved to device config")
            except Exception as e:
                logger.error(f"Failed to save calibration: {e}")

            # Close dialog
            self._close_dialog()

            # Start acquisition
            self._start_acquisition()
            return

        logger.info("🚀 User clicked Start - beginning calibration...")

        # Update dialog
        if self._calibration_dialog:
            if self._calibration_dialog.start_button:
                self._calibration_dialog.start_button.setEnabled(False)
            self._calibration_dialog.show_progress_bar()
            self._calibration_dialog.update_status("Running LED intensity calibration...")

        # Start calibration
        self.manager.start_calibration()

    def _on_calibration_started(self) -> None:
        """Handle calibration start."""
        logger.info("🔧 Calibration started")
        if self._calibration_dialog:
            self._calibration_dialog.update_status("Calibration in progress...")

    def _on_calibration_progress(self, message: str, percent: int) -> None:
        """Handle calibration progress updates.

        Args:
            message: Progress message
            percent: Progress percentage (0-100)
        """
        logger.info(f"📊 Calibration progress: {message} ({percent}%)")
        if self._calibration_dialog:
            self._calibration_dialog.update_status(message)
            self._calibration_dialog.set_progress(percent, 100)

    def _on_calibration_complete(self, calibration_data: Dict[str, Any]) -> None:
        """Handle calibration completion.

        Shows post-calibration dialog and waits for user to click Start
        before transferring to live view. Does NOT auto-start.

        Args:
            calibration_data: Dictionary containing calibration results
        """
        logger.info("🎯 Calibration complete!")

        self._calibration_completed = True

        # Show QC graphs dialog
        from widgets.calibration_qc_dialog import CalibrationQCDialog

        # Build QC data from data_mgr
        qc_data = {
            's_pol_spectra': self.app.data_mgr.ref_sig,
            'p_pol_spectra': getattr(self.app.data_mgr, 'p_pol_spectra', {}),
            'dark_scan': {'all': self.app.data_mgr.dark_noise} if self.app.data_mgr.dark_noise is not None else {},
            'afterglow_curves': getattr(self.app.data_mgr, 'afterglow_curves', {}),
            'transmission_spectra': getattr(self.app.data_mgr, 'transmission_spectra', {}),
            'wavelengths': self.app.data_mgr.wave_data,
            'integration_time': self.app.data_mgr.integration_time,
            'led_intensities': self.app.data_mgr.ref_intensity,
        }

        qc_dialog = CalibrationQCDialog(parent=self.app.main_window, calibration_data=qc_data)
        qc_dialog.exec()  # Show QC graphs and wait for user to close

        # Keep progress dialog open and show completion with Start button
        if self._calibration_dialog:
            self._calibration_dialog.update_title("✅ Calibration Complete!")
            self._calibration_dialog.update_status("Calibration successful! Click Start to begin live acquisition.")
            self._calibration_dialog.hide_progress_bar()

            # Re-enable Start button for transfer to live view
            if self._calibration_dialog.start_button:
                self._calibration_dialog.start_button.setEnabled(True)
                self._calibration_dialog.start_button.setText("Start")

        logger.info("=" * 80)
        logger.info("Calibration complete - waiting for user to click Start")
        logger.info("=" * 80)

    def _on_calibration_failed(self, error: str) -> None:
        """Handle calibration failure.

        Args:
            error: Error message
        """
        logger.error(f"❌ Calibration failed: {error}")

        if self._calibration_dialog:
            self._calibration_dialog.update_title("❌ Calibration Failed")
            self._calibration_dialog.update_status(f"Error: {error}")
            QTimer.singleShot(4000, self._close_dialog)

        from widgets.message import show_message
        show_message(error, "Calibration Error")

    def _show_qc_report(self) -> None:
        """Show calibration QC report."""
        try:
            logger.info("📊 Showing calibration QC report...")

            # Collect QC data from data_mgr
            data_mgr = self.app.data_mgr

            # Get wavelengths
            wavelengths = data_mgr.wave_data if hasattr(data_mgr, 'wave_data') else None
            if wavelengths is None:
                wavelengths = np.linspace(560, 720, 3648)

            # Collect S-pol spectra
            s_pol_spectra = dict(data_mgr.ref_sig) if hasattr(data_mgr, 'ref_sig') else {}

            # P-pol spectra (use S-pol as placeholder since P-mode data isn't stored separately)
            p_pol_spectra = s_pol_spectra.copy()

            # Dark scan
            dark_scan = {}
            if hasattr(data_mgr, 'dark_noise') and data_mgr.dark_noise is not None:
                for ch in s_pol_spectra.keys():
                    dark_scan[ch] = data_mgr.dark_noise

            # Afterglow curves (placeholder)
            afterglow_curves = {}
            for ch in s_pol_spectra.keys():
                afterglow_curves[ch] = np.zeros_like(wavelengths)

            # Transmission spectra
            transmission_spectra = {}
            for ch in s_pol_spectra.keys():
                if ch in p_pol_spectra:
                    with np.errstate(divide='ignore', invalid='ignore'):
                        transmission = np.where(
                            s_pol_spectra[ch] > 0,
                            (p_pol_spectra[ch] / s_pol_spectra[ch]) * 100.0,
                            0.0
                        )
                    transmission_spectra[ch] = transmission

            qc_data = {
                's_pol_spectra': s_pol_spectra,
                'p_pol_spectra': p_pol_spectra,
                'dark_scan': dark_scan,
                'afterglow_curves': afterglow_curves,
                'transmission_spectra': transmission_spectra,
                'wavelengths': wavelengths,
                'integration_time': data_mgr.integration_time,
                'led_intensities': data_mgr.leds_calibrated
            }

            # Show QC dialog
            from widgets.calibration_qc_dialog import CalibrationQCDialog
            CalibrationQCDialog.show_qc_report(
                parent=self.app.main_window,
                calibration_data=qc_data
            )

            logger.info("✅ QC report shown")

        except Exception as e:
            logger.error(f"❌ Failed to show QC report: {e}", exc_info=True)

    def _save_calibration_to_device_config(self, calibration_data: Dict[str, Any]) -> None:
        """Save calibration results to device_config.json.

        Args:
            calibration_data: Calibration results dictionary
        """
        try:
            logger.info("💾 Saving calibration to device_config.json...")

            from utils.device_configuration import DeviceConfiguration

            device_serial = getattr(self.app.hardware_mgr.usb, 'serial_number', None)
            device_config = DeviceConfiguration(device_serial=device_serial)

            device_config.save_led_calibration(
                integration_time=calibration_data['integration_time'],
                s_mode_intensities=calibration_data['ref_intensity'],
                p_mode_intensities=calibration_data['leds_calibrated'],
                calibration_method='standard'
            )

            logger.info("✅ Calibration saved to device_config.json")

        except Exception as e:
            logger.error(f"❌ Failed to save calibration: {e}", exc_info=True)

    def _update_led_intensities_in_ui(self) -> None:
        """Update LED intensity displays in UI."""
        try:
            data_mgr = self.app.data_mgr

            if hasattr(data_mgr, 'leds_calibrated') and data_mgr.leds_calibrated:
                for ch, intensity in data_mgr.leds_calibrated.items():
                    logger.info(f"LED {ch.upper()}: {intensity}/255")

        except Exception as e:
            logger.error(f"Failed to update UI LED intensities: {e}")

    def _close_dialog(self) -> None:
        """Close calibration dialog."""
        if self._calibration_dialog:
            self._calibration_dialog.close()
            self._calibration_dialog = None
            logger.info("Calibration dialog closed")

    def _close_dialog_and_start_acquisition(self) -> None:
        """Close dialog and start data acquisition."""
        self._close_dialog()
        self._start_acquisition()

    def _start_acquisition(self) -> None:
        """Start data acquisition after successful calibration."""
        try:
            logger.info("🎬 Starting data acquisition...")

            if not self.app.data_mgr.calibrated:
                logger.error("Cannot start acquisition - system not calibrated")
                return

            if self.app.data_mgr._acquiring:
                logger.warning("Acquisition already running")
                return

            # Start acquisition
            self.app.data_mgr.start_acquisition()
            logger.info("✅ Acquisition started")

        except Exception as e:
            logger.error(f"Failed to start acquisition: {e}", exc_info=True)
