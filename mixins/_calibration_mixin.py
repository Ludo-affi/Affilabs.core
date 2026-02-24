"""Calibration Control Mixin for Affilabs.core

This mixin provides calibration-related functionality for the main application,
including LED calibration, polarizer calibration, and calibration result handling.
Extracted from main.py for modularity.

Methods (10 total):
===================
Calibration Result Handlers:
    - _on_calibration_complete_status_update  (L1356, ~52 lines)
    - _show_qc_dialog                        (L1408, ~49 lines)
    - _restart_acquisition_after_calibration (L2841, ~16 lines)

LED Calibration:
    - _on_simple_led_calibration             (L2857, ~119 lines)
    - _on_oem_led_calibration                (L3134, ~60 lines)
    - _on_led_model_training                 (L3194, ~150 lines)

Polarizer Calibration:
    - _on_polarizer_calibration              (L2976, ~158 lines)
    - _run_servo_auto_calibration            (L4065, ~5 lines)

Calibration ViewModel Handlers:
    - _on_cal_vm_complete                    (L4021, ~10 lines)
    - _on_cal_vm_failed                      (L4036, stub)

Dependencies:
    - threading (background calibration operations)
    - PySide6.QtCore (QTimer for thread-safe UI updates)
    - PySide6.QtWidgets (QProgressDialog, QMessageBox)
    - logger (application logger)
    - UI message utilities (ui_error, ui_info, ui_warn)

Last Updated: 2026-02-18
"""

import threading
import time
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QProgressDialog

# Logger is assumed to be available at module level in main.py context
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class CalibrationMixin:
    """Mixin providing calibration control functionality.
    
    This mixin is intended to be mixed into the main application class.
    It assumes the following attributes are available:
        - self.main_window: Main application window
        - self.hardware_mgr: Hardware manager instance
        - self.data_mgr: Data acquisition manager
        - self.ui_updates: UI update coordinator
        - self.calibration: Calibration service instance
        - self.graph: Graph widget for clearing plots
    
    All methods in this mixin are internal (prefixed with _) and should only
    be called from the main application class or connected signals.
    """

    def _on_calibration_complete_status_update(self, calibration_data):
        """Handler for calibration completion - updates status AND shows QC dialog."""
        from affilabs.utils.settings_helpers import SettingsHelpers

        # Calibration succeeded — turn power button green now
        if hasattr(self, 'main_window') and self.main_window:
            self.main_window.set_power_state("connected")
            logger.debug("Power button set to connected (calibration succeeded)")

        # Resume live spectrum updates after calibration
        if hasattr(self, 'ui_updates') and self.ui_updates is not None:
            logger.debug("Resuming live spectrum updates after calibration...")
            self.ui_updates.set_transmission_updates_enabled(True)
            self.ui_updates.set_raw_spectrum_updates_enabled(True)

        SettingsHelpers.on_calibration_complete(self, calibration_data)

        # Set LED intensities once after calibration (fixed for entire run)
        if hasattr(self, 'hardware_mgr') and self.hardware_mgr and hasattr(self.hardware_mgr, 'ctrl'):
            try:
                intensities = calibration_data.p_mode_intensities
                logger.debug(f"Setting LED intensities (fixed for run): A={intensities.get('a', 0)}, B={intensities.get('b', 0)}, C={intensities.get('c', 0)}, D={intensities.get('d', 0)}")
                self.hardware_mgr.ctrl.set_batch_intensities(
                    a=int(intensities.get('a', 0)),
                    b=int(intensities.get('b', 0)),
                    c=int(intensities.get('c', 0)),
                    d=int(intensities.get('d', 0))
                )

            except Exception as e:
                logger.warning(f"Could not set LED intensities: {e}")

        # Show QC dialog with calibration results
        self._show_qc_dialog(calibration_data)

        # Automatically log calibration to database for ML training (optional)
        if hasattr(self, '_log_calibration_to_database'):
            self._log_calibration_to_database(calibration_data)

        # Populate LED brightness in Hardware Configuration section
        try:
            if hasattr(self.main_window, '_load_current_settings'):
                self.main_window._load_current_settings(show_warnings=False)
            else:
                logger.warning("   _load_current_settings method not found on main_window")
        except Exception as e:
            logger.warning(f"   Could not populate settings: {e}")

        # Clear graph and resume live data after OEM calibration
        # Clear the graph
        if hasattr(self, 'graph') and self.graph:
            self.graph.clear_plot()

        # NOTE: Live acquisition will be started only after user reviews QC and clicks "Start"
        # See: _on_qc_start_requested() handler and _show_qc_dialog()



    def _show_qc_dialog(self, calibration_data):
        """Show QC dialog with calibration results (Layer 1 - UI responsibility).

        Args:
            calibration_data: CalibrationData instance

        """
        try:
            from affilabs.widgets.calibration_qc_dialog import CalibrationQCDialog

            # Convert to dict for QC dialog
            qc_data = calibration_data.to_dict()

            logger.debug("Showing QC report dialog (modal)...")

            # Stop the calibration startup dialog timer (freeze on final elapsed time)
            if hasattr(self, 'calibration') and hasattr(self.calibration, '_calibration_dialog'):
                calib_dialog = self.calibration._calibration_dialog
                if calib_dialog and hasattr(calib_dialog, '_stop_activity_animation'):
                    logger.debug("Stopping calibration timer display...")
                    calib_dialog._stop_activity_animation()

            # Create dialog instance
            dialog = CalibrationQCDialog(
                parent=self.main_window,
                calibration_data=qc_data,
            )

            # Store reference and show modal dialog
            self._qc_dialog = dialog
            dialog.setModal(True)
            from PySide6.QtCore import Qt
            dialog.setWindowModality(Qt.ApplicationModal)
            dialog.exec()

            logger.debug("QC report displayed and closed (modal)")

            # Switch sidebar to Flow tab (index 0) since Method was removed from sidebar
            # Method button now lives in transport bar
            try:
                sidebar = self.main_window.sidebar
                flow_idx = sidebar.tab_indices.get("Flow", 0)
                sidebar.tab_widget.setCurrentIndex(flow_idx)
            except Exception:
                pass

            # Turn off all LEDs after QC report
            if hasattr(self, 'hardware_mgr') and self.hardware_mgr and hasattr(self.hardware_mgr, 'ctrl'):
                try:
                    self.hardware_mgr.ctrl.turn_off_channels()
                except Exception as led_error:
                    logger.warning(f"Failed to turn off LEDs: {led_error}")

            logger.debug("System ready - Live data acquisition controlled by user")

        except Exception as e:
            logger.error(f"[X] Failed to show QC report: {e}", exc_info=True)

    def _restart_acquisition_after_calibration(self):
        """Helper method to restart acquisition from main thread after calibration."""
        # Close Sparq bubble so the sensorgram gets full attention
        try:
            if hasattr(self, 'spark_toggle_btn'):
                self.spark_toggle_btn.setChecked(False)
        except Exception as e:
            logger.debug(f"Could not collapse Sparq sidebar: {e}")

        # Resume live spectrum updates after calibration
        if hasattr(self, 'ui_updates') and self.ui_updates is not None:
            logger.debug("Resuming live spectrum updates after calibration...")
            self.ui_updates.set_transmission_updates_enabled(True)
            self.ui_updates.set_raw_spectrum_updates_enabled(True)

        # Re-enable live graph display on main window
        try:
            if hasattr(self, 'sensogram_presenter') and self.sensogram_presenter:
                self.sensogram_presenter.set_live_data_enabled(True)
                logger.debug("Live graph display re-enabled")
            elif hasattr(self, 'main_window'):
                self.main_window.live_data_enabled = True
        except Exception as e:
            logger.debug(f"Could not re-enable live graph display: {e}")

        if hasattr(self, 'data_mgr') and self.data_mgr:
            logger.debug("Restarting live data acquisition...")
            try:
                self.data_mgr.start_acquisition()
                logger.debug("Live data acquisition restarted")
            except Exception as e:
                logger.error(f"Failed to restart live data: {e}")

    def _on_simple_led_calibration(self):
        """Run simple LED intensity adjustment (quick, for sensor swaps)."""
        logger.info("🚀 Starting calibration...")

        # Check if hardware is connected
        if not self.hardware_mgr.ctrl or not self.hardware_mgr.usb:
            from affilabs.ui.ui_message import error as ui_error
            ui_error(
                self,
                "Hardware Not Connected",
                "Please connect hardware before running LED calibration.\n\n"
                "Use the power button to connect to the device.",
            )
            return

        # Stop live data if running
        if hasattr(self, 'data_mgr') and self.data_mgr and self.data_mgr._acquiring:
            logger.debug("Stopping live data acquisition before calibration...")
            self.data_mgr.stop_acquisition()
            import time
            time.sleep(0.1)
            logger.debug("Live data stopped")

        # Pause live spectrum updates during calibration
        if hasattr(self, 'ui_updates') and self.ui_updates is not None:
            logger.debug("Pausing live spectrum updates during calibration...")
            self.ui_updates.set_transmission_updates_enabled(False)
            self.ui_updates.set_raw_spectrum_updates_enabled(False)

        # Import simple calibration function
        try:
            from affilabs.core.simple_led_calibration import run_simple_led_calibration
        except ImportError as e:
            logger.error(f"Failed to import simple calibration module: {e}")
            from affilabs.ui.ui_message import error as ui_error
            ui_error(
                self,
                "Import Error",
                f"Could not load simple calibration module.\n\n{e}",
            )
            return

        # Show progress dialog
        from affilabs.dialogs.startup_calib_dialog import StartupCalibProgressDialog

        message = (
            "Simple LED Calibration - Quick Intensity Adjustment\n\n"
            "This calibration quickly adjusts LED intensities for sensor swaps:\n\n"
            "  • Uses existing LED calibration model\n"
            "  • Quick S-mode convergence (3-5 iterations)\n"
            "  • Quick P-mode convergence (3-5 iterations)\n"
            "  • Updates device config\n\n"
            "Duration: ~10-20 seconds\n\n"
            "Requirements:\n"
            "  ✓ LED model already exists (run OEM calibration first if needed)\n"
            "  ✓ Prism installed with water/buffer\n"
            "  ✓ No air bubbles"
        )

        dialog = StartupCalibProgressDialog(
            parent=self.main_window,
            title="Simple LED Calibration",
            message=message,
            show_start_button=False,  # Auto-start (quick operation, ~10-20 seconds)
        )
        dialog.show()

        # Run calibration in thread
        import threading

        def progress_callback(msg, percent):
            """Update progress dialog."""
            dialog.update_status(msg)
            dialog.set_progress(percent, 100)

        def run_calibration():
            """Thread worker for simple calibration."""
            try:
                success = run_simple_led_calibration(
                    self.hardware_mgr,
                    progress_callback=progress_callback,
                )

                if success:
                    dialog.update_status("✅ Simple calibration complete!")
                    dialog.set_progress(100, 100)
                    logger.info("✅ Simple LED calibration completed successfully")

                    # Clear graphs and restart sensorgram at t=0 (must be on main thread)
                    # Use QTimer.singleShot to call from main thread
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, self._on_clear_graphs_requested)
                    logger.info("✓ Scheduled sensorgram reset on main thread")

                    # Restart live data acquisition (also from main thread)
                    QTimer.singleShot(100, self._restart_acquisition_after_calibration)
                else:
                    dialog.update_status("❌ Simple calibration failed")
                    dialog.set_progress(100, 100)
                    logger.error("❌ Simple LED calibration failed")
                    # Always restart acquisition so live data doesn't freeze
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(100, self._restart_acquisition_after_calibration)

                # Auto-close after 2 seconds
                import time
                time.sleep(2)
                dialog.close_from_thread()

            except Exception as e:
                logger.error(f"Simple calibration error: {e}")
                import traceback
                traceback.print_exc()
                dialog.update_status(f"❌ Error: {e}")
                dialog.set_progress(100, 100)
                # Always restart acquisition so live data doesn't freeze
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, self._restart_acquisition_after_calibration)
                import time
                time.sleep(3)
                dialog.close_from_thread()

        # Show progress bar and start thread
        dialog.show_progress_bar()
        thread = threading.Thread(target=run_calibration, daemon=True, name="SimpleCalibration")
        thread.start()

    def _on_polarizer_calibration(self):
        """Run servo polarizer calibration using existing hardware connection."""
        logger.info("🚀 Starting calibration...")

        # Check if hardware is connected
        if not self.hardware_mgr or not self.hardware_mgr.ctrl or not self.hardware_mgr.usb:
            from affilabs.ui.ui_message import error as ui_error
            ui_error(
                self.main_window,
                "Hardware Not Connected",
                "Polarizer calibration requires connected hardware.\n"
                "Please ensure the controller and detector are connected."
            )
            logger.error("Cannot run polarizer calibration - hardware not connected")
            return

        # Stop live data if running
        if hasattr(self, 'data_mgr') and self.data_mgr and self.data_mgr._acquiring:
            logger.debug("🛑 Stopping live data acquisition before polarizer calibration...")
            self.data_mgr.stop_acquisition()
            import time
            time.sleep(0.2)
            logger.debug("Live data stopped")

        # Pause live spectrum updates during calibration
        if hasattr(self, 'ui_updates') and self.ui_updates is not None:
            logger.debug("Pausing live spectrum updates during calibration...")
            self.ui_updates.set_transmission_updates_enabled(False)
            self.ui_updates.set_raw_spectrum_updates_enabled(False)

        # Create progress dialog
        from PySide6.QtWidgets import QProgressDialog
        from PySide6.QtCore import Qt

        progress = QProgressDialog(
            "Initializing polarizer calibration...",
            "Cancel",
            0,
            100,
            self.main_window
        )
        progress.setWindowTitle("Polarizer Calibration")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()

        # Progress callback to update dialog
        def update_progress(message, value):
            if progress.wasCanceled():
                return
            progress.setLabelText(message)
            progress.setValue(int(value))
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()

        # Import and run the servo calibration with existing hardware
        try:
            from servo_polarizer_calibration.calibrate_polarizer import run_calibration_with_hardware

            # Run calibration using existing hardware manager
            logger.info("Running polarizer calibration with connected hardware...")
            update_progress("Running polarizer calibration...", 10)

            success = run_calibration_with_hardware(self.hardware_mgr, progress_callback=update_progress)

            progress.close()

            if success:
                # Sync calibrated positions into the live system:
                # 1. Read from disk JSON (where calibrate_polarizer wrote them)
                # 2. Update in-memory DeviceConfiguration (prevents save() from clobbering)
                # 3. Load into controller RAM (so set_mode works immediately)
                try:
                    import json

                    serial_number = None
                    if hasattr(self, 'hardware_mgr') and self.hardware_mgr:
                        if hasattr(self.hardware_mgr, 'detector') and self.hardware_mgr.detector:
                            serial_number = getattr(self.hardware_mgr.detector, 'serial_number', None)

                    from affilabs.utils.resource_path import get_affilabs_resource
                    if serial_number:
                        config_path = get_affilabs_resource(f"config/devices/{serial_number}/device_config.json")
                    else:
                        config_path = get_affilabs_resource("config/device_config.json")

                    with open(config_path) as f:
                        config = json.load(f)

                    s_position = config.get("hardware", {}).get("servo_s_position")
                    p_position = config.get("hardware", {}).get("servo_p_position")

                    if s_position is not None and p_position is not None:
                        logger.info(f"Syncing calibrated servo positions: S={s_position}, P={p_position}")

                        # Update in-memory DeviceConfiguration so save() won't clobber
                        if self.main_window.device_config:
                            self.main_window.device_config.set_servo_positions(s_position, p_position)
                            logger.info("  -> In-memory DeviceConfiguration updated")

                        # Load into controller RAM so set_mode() works now
                        if self.hardware_mgr and self.hardware_mgr.ctrl:
                            self.hardware_mgr.ctrl.set_servo_positions(s=s_position, p=p_position)
                            logger.info("  -> Controller RAM updated")

                        # Update UI inputs
                        if hasattr(self.main_window, 's_position_input'):
                            self.main_window.s_position_input.setText(str(s_position))
                        if hasattr(self.main_window, 'p_position_input'):
                            self.main_window.p_position_input.setText(str(p_position))
                    else:
                        logger.warning("Servo positions not found in device_config.json after calibration")
                except Exception as e:
                    logger.error(f"Failed to sync servo positions after calibration: {e}")

                # Clear graphs and restart sensorgram at t=0
                logger.info("📊 Clearing graph and restarting sensorgram...")
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self._on_clear_graphs_requested)

                # Restart live data acquisition
                logger.info("🔄 Restarting live data acquisition...")
                QTimer.singleShot(100, self._restart_acquisition_after_calibration)

                # Give UI time to update before showing completion dialog
                from PySide6.QtWidgets import QApplication
                import time
                QApplication.processEvents()
                time.sleep(0.3)
                QApplication.processEvents()

                from affilabs.ui.ui_message import info as ui_info
                ui_info(
                    self.main_window,
                    "Calibration Complete",
                    "Polarizer calibration completed successfully!\n"
                    "Servo moved to P position and live data resumed."
                )
            else:
                from affilabs.ui.ui_message import warn as ui_warn
                ui_warn(
                    self.main_window,
                    "Calibration Issue",
                    "Polarizer calibration completed with warnings.\n"
                    "Please check the logs for details."
                )

        except Exception as e:
            progress.close()
            logger.error(f"Polarizer calibration failed: {e}")
            logger.exception("Servo calibration error")
            # Resume spectrum updates even on failure
            if hasattr(self, 'ui_updates') and self.ui_updates is not None:
                self.ui_updates.set_transmission_updates_enabled(True)
                self.ui_updates.set_raw_spectrum_updates_enabled(True)
            from affilabs.ui.ui_message import error as ui_error
            ui_error(
                self.main_window,
                "Calibration Failed",
                f"Polarizer calibration encountered an error:\n{str(e)}"
            )

    def _on_oem_led_calibration(self):
        """Run full OEM calibration (servo + LED) via CalibrationService.

        This ALWAYS rebuilds the optical model, regardless of whether one exists.
        Shows dialog with "Start" button BEFORE beginning calibration.
        """
        from affilabs.dialogs.startup_calib_dialog import StartupCalibProgressDialog

        # Show pre-calibration dialog with Start button
        dialog = StartupCalibProgressDialog(
            parent=self.main_window,
            title="OEM Calibration",
            message=(
                "Automated device characterization:\n\n"
                "1. Polarizer calibration (~2-5 min)\n"
                "2. LED model training (~2 min)\n"
                "3. Full system calibration (~3-5 min)\n\n"
                "Total time: ~10-15 minutes\n\n"
                "Click Start to begin."
            ),
            show_start_button=True,
        )

        def on_start():
            """Called when user clicks Start button."""
            logger.info("🚀 Starting calibration...")
            dialog.hide_start_button()
            dialog.show_progress_bar()

            # Pause live spectrum updates during calibration
            if hasattr(self, 'ui_updates') and self.ui_updates is not None:
                logger.debug("Pausing live spectrum updates during calibration...")
                self.ui_updates.set_transmission_updates_enabled(False)
                self.ui_updates.set_raw_spectrum_updates_enabled(False)

            # Clear sensorgram immediately — don't leave stale data visible during 10-15 min run
            if hasattr(self, 'graph') and self.graph:
                self.graph.clear_plot()

            # CRITICAL: Pass the dialog to calibration service to avoid creating a second dialog
            # Set the existing dialog as the calibration dialog before starting
            self.calibration._calibration_dialog = dialog
            self.calibration._force_oem_retrain = True

            # Connect calibration service signals to THIS dialog
            self.calibration.calibration_progress.connect(lambda msg, prog: dialog.update_status(msg))
            self.calibration.calibration_progress.connect(lambda msg, prog: dialog.set_progress(prog, 100))

            # Start calibration WITHOUT creating a new dialog (headless mode)
            self.calibration._running = True
            import threading
            self.calibration._thread = threading.Thread(
                target=self.calibration._run_calibration,
                daemon=True,
                name="CalibrationService",
            )
            self.calibration._thread.start()
            self.calibration.calibration_started.emit()
            logger.info("[OK] Calibration thread started (using existing dialog)")

        dialog.start_clicked.connect(on_start)
        dialog.show()
        dialog.enable_start_button_pre_calib()  # Enable the Start button after dialog is visible

    def _on_led_model_training(self):
        """Run LED model training only (no full calibration).

        Directly trains the 3-stage linear LED model without running the full
        6-step calibration. Useful for quickly rebuilding the optical model.
        """
        logger.info("=" * 80)
        logger.info("Starting LED Model Training (optical model only)...")
        logger.info("=" * 80)

        # Import required modules
        from affilabs.core.oem_model_training import run_oem_model_training_workflow
        from affilabs.dialogs.startup_calib_dialog import StartupCalibProgressDialog
        import threading

        # Check hardware
        if not self.hardware_mgr or not self.hardware_mgr.ctrl or not self.hardware_mgr.usb:
            from affilabs.ui.ui_message import error as ui_error
            ui_error(
                self.main_window,
                "Hardware Not Ready",
                "Please connect hardware before training the LED model."
            )
            return

        # Stop live data if running
        if hasattr(self, 'data_mgr') and self.data_mgr and self.data_mgr._acquiring:
            logger.debug("Stopping live data acquisition before LED model training...")
            self.data_mgr.stop_acquisition()
            import time
            time.sleep(0.1)
            logger.debug("Live data stopped")

        # Pause live spectrum updates during calibration
        if hasattr(self, 'ui_updates') and self.ui_updates is not None:
            logger.debug("Pausing live spectrum updates during LED model training...")
            self.ui_updates.set_transmission_updates_enabled(False)
            self.ui_updates.set_raw_spectrum_updates_enabled(False)

        # Show progress dialog
        dialog = StartupCalibProgressDialog(
            parent=self.main_window,
            title="Training LED Model",
            message=(
                "LED Model Training Process:\n\n"
                "  1. Servo Polarizer Calibration (if P4SPR)\n"
                "  2. LED Response Measurement (10-60ms)\n"
                "  3. 3-Stage Linear Model Fitting\n"
                "  4. Model File Creation\n\n"
                "This will take approximately 2-5 minutes.\n\n"
                "Click Start to begin."
            ),
            show_start_button=True,
        )

        def progress_callback(message: str, percent: int):
            """Update progress dialog."""
            dialog.update_status(message)
            dialog.set_progress(percent, 100)
            if not dialog.progress_bar.isVisible():
                dialog.show_progress_bar()

        def run_training():
            """Run training in background thread."""
            try:
                logger.info("🔬 LED Model Training thread started...")

                # Run OEM model training workflow
                success = run_oem_model_training_workflow(
                    hardware_mgr=self.hardware_mgr,
                    progress_callback=progress_callback,
                )

                if success:
                    logger.info("[OK] LED model training completed successfully")
                    dialog.update_title("LED Model Training Complete")
                    dialog.update_status("✓ Model created successfully!")
                    dialog.hide_progress_bar()

                    # Clear graphs and restart sensorgram at t=0 (use QTimer for thread safety)
                    from PySide6.QtCore import QTimer

                    logger.info("📊 Clearing graph and restarting sensorgram...")
                    QTimer.singleShot(0, self._on_clear_graphs_requested)

                    # Restart live data acquisition (also from main thread)
                    QTimer.singleShot(100, self._restart_acquisition_after_calibration)

                    # Show success dialog (also from main thread for safety)
                    from PySide6.QtCore import QMetaObject, Qt as QtCore
                    import time
                    time.sleep(0.5)  # Brief delay before showing dialog

                    QMetaObject.invokeMethod(
                        dialog,
                        "close",
                        QtCore.ConnectionType.QueuedConnection
                    )

                    from affilabs.ui.ui_message import info as ui_info
                    ui_info(
                        self.main_window,
                        "Training Complete",
                        "LED calibration model created successfully!\n\n"
                        "The new model is now active and will be used for all calibrations."
                    )
                else:
                    logger.error("[ERROR] LED model training failed")
                    dialog.update_title("Training Failed")
                    dialog.update_status("❌ Model training encountered errors")
                    dialog.hide_progress_bar()

                    from affilabs.ui.ui_message import error as ui_error
                    from PySide6.QtCore import QMetaObject, Qt as QtCore
                    import time

                    time.sleep(0.5)  # Brief delay before showing error

                    QMetaObject.invokeMethod(
                        dialog,
                        "close",
                        QtCore.ConnectionType.QueuedConnection
                    )

                    ui_error(
                        self.main_window,
                        "Training Failed",
                        "LED model training failed.\n\nPlease check the logs for details."
                    )

            except Exception as e:
                logger.error(f"LED model training error: {e}", exc_info=True)
                dialog.update_title("Training Error")
                dialog.update_status(f"Error: {str(e)}")
                dialog.hide_progress_bar()

        def on_start_clicked():
            """Handle Start button click."""
            dialog.start_button.setEnabled(False)
            dialog.show_progress_bar()
            dialog.update_status("Initializing LED model training...")

            # Start training thread
            thread = threading.Thread(target=run_training, daemon=True, name="LEDModelTraining")
            thread.start()

        # Connect start button
        dialog.start_clicked.connect(on_start_clicked)
        dialog.show()
        dialog.enable_start_button_pre_calib()  # Enable the Start button after dialog is visible

    def _on_calibration_failed(self, error_message: str):
        """Handle calibration_failed signal from CalibrationService.

        Resets the power button to disconnected (gray) so the user can retry.

        Args:
            error_message: Error description from CalibrationService

        """
        logger.error(f"[Calibration] Calibration failed: {error_message}")
        # Revert power button to gray — calibration did not succeed
        if hasattr(self, 'main_window') and self.main_window:
            self.main_window.set_power_state("disconnected")
            logger.debug("Power button reset to disconnected (calibration failed)")

    def _on_cal_vm_complete(self, calibration_data: dict):
        """Handle calibration_complete signal from CalibrationViewModel.

        Args:
            calibration_data: Calibration data dictionary

        """
        logger.info("[CalibrationViewModel] Calibration complete")
        # Future: Display success message, enable acquisition

    def _on_cal_vm_failed(self, error_message: str):
        """Handle calibration_failed signal from CalibrationViewModel.

        Args:
            error_message: Error description

        """
        logger.error(
            f"[CalibrationViewModel] Calibration failed: {error_message}",
        )
        # Revert power button to gray — calibration did not succeed
        if hasattr(self, 'main_window') and self.main_window:
            self.main_window.set_power_state("disconnected")
            logger.debug("Power button reset to disconnected (CalibrationViewModel failure)")

    def _run_servo_auto_calibration(self):
        """Run servo polarizer calibration automatically."""
        logger.info("🔧 Auto-triggering servo polarizer calibration...")
        self._on_polarizer_calibration()
