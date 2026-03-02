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

# Use the application logger (same instance as main.py and all other modules)
from affilabs.utils.logger import logger


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
            if hasattr(self.main_window, 'stage_bar'):
                self.main_window.stage_bar.advance_to("calibrate")
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

            # Close the calibration progress dialog from the main thread before opening QC
            if hasattr(self, 'calibration') and hasattr(self.calibration, '_calibration_dialog'):
                calib_dialog = self.calibration._calibration_dialog
                if calib_dialog:
                    if hasattr(calib_dialog, '_stop_activity_animation'):
                        calib_dialog._stop_activity_animation()
                    try:
                        calib_dialog.close()
                    except Exception:
                        pass

            # Create dialog instance — pass shared user manager so the footer
            # shows a user selector + "Start →" instead of a plain Close button
            _user_mgr = getattr(self, 'user_profile_manager', None)
            dialog = CalibrationQCDialog(
                parent=self.main_window,
                calibration_data=qc_data,
                user_manager=_user_mgr,
            )

            # Wire accepted (Start Session / Close) → start acquisition
            dialog.accepted.connect(
                lambda: QTimer.singleShot(50, self._restart_acquisition_after_calibration)
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
            try:
                if getattr(self, '_leak_recal_was_acquiring', False):
                    # Leak-triggered recal: resume the paused thread — no data lost
                    logger.debug("Resuming paused acquisition after leak recal...")
                    self.data_mgr.resume_acquisition()
                    logger.debug("Acquisition resumed")
                else:
                    logger.debug("Restarting live data acquisition...")
                    self.data_mgr.start_acquisition()
                    logger.debug("Live data acquisition restarted")
            except Exception as e:
                logger.error(f"Failed to restart live data: {e}")

    # ------------------------------------------------------------------
    # Shared monitoring-gate helper
    # ------------------------------------------------------------------

    def _stop_all_monitoring_for_calibration(self, pause_only: bool = False):
        """Stop acquisition and every monitoring subsystem before any calibration.

        All four calibration entry-points call this so the logic lives in one place:
          - Joins the acquisition thread (guarantees hardware bus is free)
          - Stops InjectionMonitors (they poll buffer_mgr independently)
          - Clears leak-detection baselines/alert sets (LEDs change their output
            during calibration — old baselines would cause false alerts on restart)
          - Resets AirBubbleDetector history (polarizer position changes produce
            wavelength swings that look like bubbles to the rolling-std detector)
        The restart side (_restart_acquisition_after_calibration) resets all
        monitoring state again via _on_acquisition_started(), so nothing is lost.

        Args:
            pause_only: If True, *pause* acquisition instead of stopping it.
                The thread stays alive so resume_acquisition() can continue the
                sensorgram without resetting buffers/timers.  Used by simple cal.
        """
        # 1. Stop (or pause) acquisition
        if hasattr(self, 'data_mgr') and self.data_mgr and self.data_mgr._acquiring:
            if pause_only:
                logger.debug("Pausing live data acquisition before calibration...")
                self.data_mgr.pause_acquisition()
                # Wait for the current acquisition cycle to finish so the
                # hardware bus is idle when the calibration thread starts.
                import time as _time
                _time.sleep(1.5)
                logger.debug("Acquisition paused — hardware bus should be idle")
            else:
                logger.debug("Stopping live data acquisition before calibration...")
                self.data_mgr.stop_acquisition()
                logger.debug("Acquisition stopped — hardware bus released")

        # 2. Stop injection monitors
        try:
            inj_coord = getattr(self, 'injection_coordinator', None)
            if inj_coord and hasattr(inj_coord, '_stop_all_monitors'):
                inj_coord._stop_all_monitors()
                logger.debug("Injection monitors stopped for calibration")
        except Exception as _e:
            logger.debug(f"Could not stop injection monitors: {_e}")

        # 3. Clear leak-detection state
        for _attr in ('_intensity_baseline', '_intensity_baseline_locked',
                      '_intensity_low_since'):
            if hasattr(self, _attr):
                getattr(self, _attr).clear()
        for _attr in ('_leak_alerted', '_leak_recovered', '_wl_high_alerted'):
            if hasattr(self, _attr):
                getattr(self, _attr).clear()
        if hasattr(self, '_wl_high_counts'):
            self._wl_high_counts.clear()

        # 4. Reset air bubble detector
        try:
            from affilabs.services.air_bubble_detector import AirBubbleDetector
            AirBubbleDetector.get_instance().reset_session()
            logger.debug("Air bubble detector reset for calibration")
        except Exception as _e:
            logger.debug(f"Could not reset air bubble detector: {_e}")

        # 5. Pause UI spectrum updates
        if hasattr(self, 'ui_updates') and self.ui_updates is not None:
            self.ui_updates.set_transmission_updates_enabled(False)
            self.ui_updates.set_raw_spectrum_updates_enabled(False)

    def _set_live_sensorgram_cal_label(self, calibrating: bool) -> None:
        """Show/hide a 'Calibrating…' title inside the Live Sensorgram plot."""
        try:
            graph = getattr(self.main_window, 'full_timeline_graph', None)
            if graph is None:
                return
            if calibrating:
                graph.setTitle("⟳  Calibrating…", color="#FF9500", size="11pt")
            else:
                graph.setTitle("")
        except Exception as e:
            logger.debug(f"Could not update sensorgram cal label: {e}")

    def _on_simple_led_calibration(self):
        """Run quick LED re-convergence for sensor swaps."""
        logger.info("Starting simple LED calibration...")

        # Double-launch guard — prevent concurrent runs
        if getattr(self, '_simple_cal_running', False):
            logger.warning("Simple calibration already in progress — ignoring duplicate request")
            return

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

        self._simple_cal_running = True
        # Track whether acquisition was live so we can resume (not restart)
        self._leak_recal_was_acquiring = (
            hasattr(self, 'data_mgr') and self.data_mgr and self.data_mgr._acquiring
        )
        self._stop_all_monitoring_for_calibration(pause_only=self._leak_recal_was_acquiring)
        self._set_live_sensorgram_cal_label(True)

        # Wire the thread-safe result signal once (disconnect first to avoid duplicate connections)
        try:
            self._simple_cal_result_signal.disconnect(self._process_simple_calibration_result)
        except Exception:
            pass
        self._simple_cal_result_signal.connect(self._process_simple_calibration_result)

        # Show progress dialog
        from affilabs.dialogs.startup_calib_dialog import StartupCalibProgressDialog

        dialog = StartupCalibProgressDialog(
            parent=self.main_window,
            title="Quick LED Calibration",
            message=(
                "Re-converging LED intensities for new sensor...\n\n"
                "  \u2022 S-mode convergence (2\u20134 iterations)\n"
                "  \u2022 P-mode convergence (2\u20134 iterations)\n"
                "  \u2022 Reference capture + dark frame\n\n"
                "Duration: ~15\u201325 seconds"
            ),
            show_start_button=False,
        )
        dialog.show()
        dialog.show_progress_bar()

        import threading

        def run_calibration():
            try:
                from affilabs.core.simple_led_calibration import run_simple_led_calibration

                current_s_leds = None
                current_integration_ms = None
                existing_dark = None
                try:
                    cal_data = (
                        self.calibration._current_calibration_data
                        if hasattr(self, 'calibration') and self.calibration
                        else None
                    )
                    if cal_data:
                        s_leds = getattr(cal_data, 's_mode_intensities', None)
                        if s_leds and len(s_leds) >= 4:
                            current_s_leds = dict(s_leds)
                        s_int = getattr(cal_data, 'integration_time_s', None)
                        if s_int and s_int > 0:
                            current_integration_ms = float(s_int)
                        # Recycle dark from prior calibration
                        dark_noise = getattr(cal_data, 'dark_noise', None)
                        if dark_noise is not None and len(dark_noise) > 0:
                            existing_dark = dark_noise
                        else:
                            # Fall back to first channel's S-dark if available
                            dark_s = getattr(cal_data, 'dark_s', None)
                            if dark_s:
                                for _ch_dark in dark_s.values():
                                    if _ch_dark is not None and len(_ch_dark) > 0:
                                        existing_dark = _ch_dark
                                        break
                        logger.debug(
                            "Starting from current cal: LEDs=%s, integration=%.1fms, dark=%s",
                            current_s_leds,
                            current_integration_ms or 0,
                            "recycled" if existing_dark is not None else "none",
                        )
                except Exception as e:
                    logger.debug(f"Could not extract current cal values: {e}")

                def _progress(msg, pct, _d=dialog):
                    _d.update_status(msg)
                    _d.set_progress(pct, 100)

                cal_result = run_simple_led_calibration(
                    self.hardware_mgr,
                    progress_callback=_progress,
                    current_s_leds=current_s_leds,
                    current_integration_ms=current_integration_ms,
                    existing_dark=existing_dark,
                )
            except Exception as e:
                logger.error(f"Simple calibration error: {e}", exc_info=True)
                cal_result = None

            # Deliver result to main thread via signal — safe from any thread
            self._simple_cal_result_signal.emit(cal_result, dialog)

        thread = threading.Thread(target=run_calibration, daemon=True, name="SimpleCalibration")
        thread.start()

    # ------------------------------------------------------------------
    # Simple calibration result processing (runs on main thread)
    # ------------------------------------------------------------------

    def _process_simple_calibration_result(self, cal_result, dialog):
        """Apply simple calibration result and restart live data. Runs on main thread."""
        from PySide6.QtCore import QTimer

        self._simple_cal_running = False

        try:
            if not cal_result or not cal_result.success:
                err = getattr(cal_result, 'error', 'Unknown') if cal_result else 'No result'
                logger.error(f"Simple calibration failed: {err}")
                dialog.update_status(f"❌ Calibration failed: {err}")
                QTimer.singleShot(3000, dialog.close)
                return

            # Snapshot existing dark references BEFORE overwriting cal data.
            # Simple cal does not capture per-channel darks, so the adapter
            # returns empty dicts — we recycle the ones from the prior full
            # calibration to avoid losing the dark correction.
            old_cal = (
                self.calibration._current_calibration_data
                if hasattr(self, 'calibration') and self.calibration
                else None
            )

            # Convert to domain model
            from affilabs.domain import led_calibration_result_to_domain
            calibration_data = led_calibration_result_to_domain(cal_result)

            # Recycle per-channel darks from previous calibration
            if old_cal is not None:
                if old_cal.dark_s and not calibration_data.dark_s:
                    calibration_data.dark_s = old_cal.dark_s
                if old_cal.dark_p and not calibration_data.dark_p:
                    calibration_data.dark_p = old_cal.dark_p

            # Store on calibration service
            if hasattr(self, 'calibration') and self.calibration:
                self.calibration._current_calibration_data = calibration_data
                self.calibration._calibration_completed = True

            # Apply to acquisition pipeline
            if hasattr(self, 'data_mgr') and self.data_mgr:
                self.data_mgr.apply_calibration(calibration_data)

            # Push new LED intensities to controller
            try:
                intensities = calibration_data.p_mode_intensities
                self.hardware_mgr.ctrl.set_batch_intensities(
                    a=int(intensities.get('a', 0)),
                    b=int(intensities.get('b', 0)),
                    c=int(intensities.get('c', 0)),
                    d=int(intensities.get('d', 0)),
                )
            except Exception as e:
                logger.warning(f"Could not set LED intensities: {e}")

            logger.info("Simple calibration complete")
            dialog.update_status("✅ Calibration complete — live data resumed")
            QTimer.singleShot(1500, dialog.close)

            # Place a "Simple Cal" marker on the live sensorgram so the user
            # can see exactly where the recalibration happened.
            try:
                if hasattr(self, 'clock') and self.clock is not None:
                    marker_t = self.clock.raw_elapsed_now()
                elif hasattr(self, 'experiment_start_time') and self.experiment_start_time:
                    import time as _time
                    marker_t = _time.time() - self.experiment_start_time
                else:
                    marker_t = None
                if marker_t is not None and hasattr(self.main_window, 'add_event_marker'):
                    self.main_window.add_event_marker(marker_t, "Simple Cal", "#FF9500")
            except Exception as _e:
                logger.debug(f"Could not place simple-cal marker: {_e}")

        except Exception as e:
            logger.error(f"Simple calibration post-processing failed: {e}", exc_info=True)
            dialog.update_status(f"❌ Error: {e}")
            QTimer.singleShot(3000, dialog.close)

        finally:
            self._set_live_sensorgram_cal_label(False)
            QTimer.singleShot(50, self._restart_acquisition_after_calibration)

    def _on_polarizer_calibration(self):
        """Run servo polarizer calibration using existing hardware connection."""
        logger.info("Starting polarizer calibration...")

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

        self._stop_all_monitoring_for_calibration()

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

            self._stop_all_monitoring_for_calibration()

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
        """Run LED model training only (no full calibration)."""
        logger.info("Starting LED Model Training...")

        if getattr(self, '_model_training_running', False):
            logger.warning("LED model training already in progress — ignoring duplicate request")
            return

        if not self.hardware_mgr or not self.hardware_mgr.ctrl or not self.hardware_mgr.usb:
            from affilabs.ui.ui_message import error as ui_error
            ui_error(self.main_window, "Hardware Not Ready",
                     "Please connect hardware before training the LED model.")
            return

        self._model_training_running = True
        self._model_training_was_acquiring = (
            hasattr(self, 'data_mgr') and self.data_mgr and self.data_mgr._acquiring
        )
        self._stop_all_monitoring_for_calibration(pause_only=self._model_training_was_acquiring)
        self._set_live_sensorgram_cal_label(True)

        # Wire result signal once
        try:
            self._model_training_result_signal.disconnect(self._process_model_training_result)
        except Exception:
            pass
        self._model_training_result_signal.connect(self._process_model_training_result)

        from affilabs.dialogs.startup_calib_dialog import StartupCalibProgressDialog
        import threading

        dialog = StartupCalibProgressDialog(
            parent=self.main_window,
            title="LED Model Training",
            message=(
                "LED Model Training:\n\n"
                "  \u2022 Servo polarizer calibration\n"
                "  \u2022 LED response measurement (10\u201360 ms)\n"
                "  \u2022 3-Stage linear model fitting\n\n"
                "Duration: ~2\u20135 minutes\n\n"
                "Click Start to begin."
            ),
            show_start_button=True,
        )

        def run_training():
            from affilabs.core.oem_model_training import run_oem_model_training_workflow
            success = False
            error_msg = ""
            try:
                def _progress(msg, pct):
                    dialog.update_status(msg)

                success = run_oem_model_training_workflow(
                    hardware_mgr=self.hardware_mgr,
                    progress_callback=_progress,
                )
            except Exception as e:
                logger.error(f"LED model training error: {e}", exc_info=True)
                error_msg = str(e)

            self._model_training_result_signal.emit(success, error_msg, dialog)

        def on_start_clicked():
            dialog.start_button.setEnabled(False)
            dialog.show_progress_bar()
            dialog.update_status("Starting LED model training...")
            thread = threading.Thread(target=run_training, daemon=True, name="LEDModelTraining")
            thread.start()

        dialog.start_clicked.connect(on_start_clicked)
        dialog.show()
        dialog.enable_start_button_pre_calib()

    def _process_model_training_result(self, success: bool, error_msg: str, dialog):
        """Apply LED model training result. Runs on main thread."""
        from PySide6.QtCore import QTimer

        self._model_training_running = False

        try:
            if success:
                logger.info("[OK] LED model training complete")
                dialog.update_status("Model created successfully")
                QTimer.singleShot(1500, dialog.close)
                QTimer.singleShot(0, self._on_clear_graphs_requested)
            else:
                msg = error_msg or "Model training encountered errors"
                logger.error(f"LED model training failed: {msg}")
                dialog.update_status(f"Training failed: {msg}")
                QTimer.singleShot(3000, dialog.close)
        except Exception as e:
            logger.error(f"Model training post-processing failed: {e}", exc_info=True)
        finally:
            self._set_live_sensorgram_cal_label(False)
            QTimer.singleShot(100, self._restart_acquisition_after_calibration)

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
