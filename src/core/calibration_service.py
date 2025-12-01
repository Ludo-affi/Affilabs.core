"""
CalibrationService - Unified calibration interface.

Merges CalibrationCoordinator + CalibrationManager into single service.
Handles UI interaction, threading, progress, and QC display.
"""

import threading
import time
import os
import numpy as np
from PySide6.QtCore import QObject, Signal
from typing import Optional
from utils.logger import logger
from core.calibration_data import CalibrationData
from core.ml_qc_intelligence import MLQCIntelligence


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

        # ML QC Intelligence (initialized lazily when device connects)
        self._ml_intelligence: Optional[MLQCIntelligence] = None

    def start_calibration(self) -> bool:
        """Start calibration dialog (does NOT start calibration thread).

        The actual calibration begins when user clicks Start button in dialog.

        Returns:
            True if dialog shown, False if already running
        """
        if self._running:
            logger.warning("Calibration already in progress")
            return False

        # Headless mode: allowed only when NOT running inside the UI
        # In UI context, we always show the dialog regardless of env var
        in_ui_context = hasattr(self.app, 'main_window') and self.app.main_window is not None
        headless_env = os.getenv("CALIBRATION_HEADLESS", "0") == "1"
        headless = (not in_ui_context) and headless_env

        if headless:
            logger.info("=" * 80)
            logger.info("🧪 CALIBRATION SERVICE: Headless mode active (no dialog)")
            logger.info("=" * 80)
            # Reset state
            self._calibration_completed = False
            self._current_calibration_data = None
            # Directly start calibration thread
            self._running = True
            self._thread = threading.Thread(
                target=self._run_calibration,
                daemon=True,
                name="CalibrationService"
            )
            self._thread.start()
            self.calibration_started.emit()
            logger.info("✅ Headless calibration thread started")
            return True

        logger.info("=" * 80)
        logger.info("🎬 CALIBRATION SERVICE: Showing calibration dialog (awaiting Start)...")
        logger.info("=" * 80)

        # Reset state
        self._calibration_completed = False
        self._current_calibration_data = None

        # Show progress dialog with Start button; do NOT auto-start
        self._show_progress_dialog()

        # Enable Start button for pre-calibration checklist (original feel)
        if self._calibration_dialog:
            try:
                self._calibration_dialog.enable_start_button_pre_calib()
            except Exception:
                pass

        # Wait for user to click Start in the dialog
        return True

    @property
    def dialog(self):
        """Get the calibration progress dialog (read-only property for external status updates)."""
        return self._calibration_dialog

    def _show_progress_dialog(self) -> None:
        """Show calibration progress dialog."""
        from affilabs_core_ui import StartupCalibProgressDialog

        message = (
            "Please verify before calibrating:\n\n"
            "  ✓  Prism installed in sensor holder\n"
            "  ✓  Water or buffer applied to prism\n"
            "  ✓  No air bubbles visible\n"
            "  ✓  Temperature stabilized (10 min after power-on)\n\n"
            "6-Step Calibration Process:\n"
            "  1. Hardware Validation & LED Verification\n"
            "  2. Wavelength Calibration\n"
            "  3. LED Brightness Ranking\n"
            "  4. S-Mode Integration Time Optimization\n"
            "  5. P-Mode Optimization (Transfer + Boost)\n"
            "  6. S-Mode Reference Signals + QC\n\n"
            "Takes approximately 30-60 seconds."
        )

        self._calibration_dialog = StartupCalibProgressDialog(
            parent=self.app.main_window,
            title="Calibrating SPR System",
            message=message,
            show_start_button=True
        )

        # Connect dialog signals (post-calibration continue handled if button exists)
        try:
            self._calibration_dialog.start_clicked.connect(self._on_start_button_clicked)
        except Exception:
            pass

        # Connect calibration service signals to update dialog
        self.calibration_progress.connect(self._update_dialog_progress)
        self.calibration_failed.connect(self._on_calibration_failed_dialog)

        self._calibration_dialog.hide_progress_bar()
        self._calibration_dialog.show()
        logger.info("✅ Calibration dialog displayed (Start button visible)")

    def _progress_callback(self, message: str, progress: int = 0) -> None:
        """Progress callback for calibration routines.

        This method is passed to run_full_6step_calibration() to receive
        progress updates during the calibration process.

        Args:
            message: Progress message to display
            progress: Progress percentage (0-100)
        """
        # Emit to UI and log for console visibility
        try:
            logger.info(f"[CAL] {message} ({progress}%)")
        except Exception:
            pass
        self.calibration_progress.emit(message, progress)

    def _update_dialog_progress(self, message: str, progress: int) -> None:
        """Update calibration dialog with progress information.

        Args:
            message: Progress message to display
            progress: Progress percentage (0-100)
        """
        if self._calibration_dialog:
            self._calibration_dialog.update_status(message)
            self._calibration_dialog.set_progress(progress)  # Use set_progress, not update_progress

    def _on_calibration_failed_dialog(self, error_message: str) -> None:
        """Handle calibration failure in dialog.

        Args:
            error_message: Error message to display
        """
        if self._calibration_dialog:
            self._calibration_dialog.update_title("❌ Calibration Failed")
            self._calibration_dialog.update_status(f"Error: {error_message}")
            self._calibration_dialog.hide_progress_bar()

    def _on_start_button_clicked(self) -> None:
        """Handle Start button click - begin calibration or transfer to live view."""
        if self._calibration_completed:
            # Calibration complete - transfer to live acquisition
            logger.info("=" * 80)
            logger.info("✅ User clicked Start - transferring to live view")
            logger.info("=" * 80)

            # Verify calibration data is available
            if not self._current_calibration_data:
                logger.error("❌ FATAL: No calibration data available!")
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    self._calibration_dialog if self._calibration_dialog else None,
                    "Calibration Error",
                    "No calibration data available. Please recalibrate."
                )
                return

            # Start live acquisition FIRST
            if hasattr(self.app, 'data_mgr'):
                try:
                    logger.info("📊 Verifying acquisition manager is ready...")
                    if not self.app.data_mgr.calibrated:
                        logger.error("❌ Acquisition manager reports not calibrated!")
                        raise RuntimeError("Acquisition manager not calibrated. Calibration data may not have been applied.")

                    logger.info("🚀 Starting live acquisition...")
                    self.app.data_mgr.start_acquisition()
                    logger.info("✅ Live acquisition started successfully")
                except Exception as e:
                    logger.error(f"❌ Failed to start acquisition: {e}", exc_info=True)
                    # Show error but don't close dialog yet
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.critical(
                        self._calibration_dialog if self._calibration_dialog else None,
                        "Acquisition Error",
                        f"Failed to start live acquisition:\n{e}\n\nPlease check the logs and try again."
                    )
                    return
            else:
                logger.error("❌ FATAL: data_mgr not found in app!")
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    self._calibration_dialog if self._calibration_dialog else None,
                    "System Error",
                    "Acquisition manager not found. Please restart the application."
                )
                return

            # Close calibration dialog AFTER acquisition starts successfully
            if self._calibration_dialog:
                # Use QTimer to defer dialog close to ensure acquisition thread starts
                # and allow Qt event loop to process properly
                from PySide6.QtCore import QTimer
                def close_dialog():
                    if self._calibration_dialog:
                        try:
                            logger.info("🔄 Closing calibration dialog...")

                            # Store reference to overlay before clearing dialog reference
                            overlay_to_cleanup = None
                            if hasattr(self._calibration_dialog, 'overlay'):
                                overlay_to_cleanup = self._calibration_dialog.overlay
                                self._calibration_dialog.overlay = None  # Clear reference first

                            # Close dialog first (this will trigger closeEvent)
                            logger.info("   Closing dialog window...")
                            self._calibration_dialog.accept()
                            self._calibration_dialog = None
                            logger.info("   ✅ Dialog closed")

                            # Clean up overlay AFTER dialog is closed
                            if overlay_to_cleanup:
                                try:
                                    logger.info("   Cleaning up overlay...")
                                    overlay_to_cleanup.hide()
                                    overlay_to_cleanup.deleteLater()
                                    logger.info("   ✅ Overlay cleaned up")
                                except RuntimeError as e:
                                    logger.debug(f"   Overlay already deleted: {e}")
                                except Exception as e:
                                    logger.warning(f"   Error cleaning overlay: {e}")

                            logger.info("✅ Calibration dialog and overlay closed successfully")
                        except Exception as e:
                            logger.error(f"⚠️ Error closing dialog: {e}", exc_info=True)

                QTimer.singleShot(150, close_dialog)  # Slightly longer delay for safety
                logger.info("📋 Dialog close scheduled in 150ms")

            logger.info("=" * 80)
            logger.info("✅ Calibration-to-live transfer completed")
            logger.info("=" * 80)
            return

        # Start calibration (first time only)
        if self._running:
            logger.warning("Calibration thread already running - ignoring duplicate click")
            return

        logger.info("🔄 User clicked Start - beginning calibration")

        # Update dialog
        if self._calibration_dialog:
            if self._calibration_dialog.start_button:
                self._calibration_dialog.start_button.setEnabled(False)
            self._calibration_dialog.show_progress_bar()
            self._calibration_dialog.update_status("Running LED intensity calibration...")

        # Launch calibration in background thread (ONLY PLACE IT STARTS)
        self._running = True
        self._thread = threading.Thread(
            target=self._run_calibration,
            daemon=True,
            name="CalibrationService"
        )
        self._thread.start()
        self.calibration_started.emit()
        logger.info("✅ Calibration thread started")

    def _run_calibration(self) -> None:
        """Main calibration routine (runs in background thread)."""
        import sys
        import io
        import logging
        from datetime import datetime
        # File logger to capture full calibration thread output (headless-safe)
        log_handler = None
        try:
            os.makedirs("logs", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            logfile = os.path.join("logs", f"calibration_{timestamp}.log")
            log_handler = logging.FileHandler(logfile, encoding="utf-8")
            log_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s')
            log_handler.setFormatter(formatter)
            logger.addHandler(log_handler)
            logger.info(f"[CAL] File logging enabled → {logfile}")
        except Exception as e:
            try:
                logger.warning(f"[CAL] Could not initialize file logger: {e}")
            except Exception:
                pass

        # Do NOT redirect stdout/stderr to logger to avoid recursion deadlocks.
        # Keep original streams so print() from dependencies remains visible.
        print("[CalibrationService] _run_calibration entered", flush=True)
        logger.info("[CalibrationService] _run_calibration entered")

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

            # CRITICAL FIX: Clear USB device buffer with dummy reads
            # [Errno 10060] Operation timed out = USB buffer has stale data from hardware scan
            # Solution: Perform 2-3 dummy reads to flush the buffer before calibration
            logger.info("🔄 Clearing USB buffer with dummy reads...")
            try:
                # Set short integration time for fast dummy reads
                usb.set_integration(10)  # 10ms minimum
                time.sleep(0.1)

                # Perform 3 dummy reads to flush any stale data
                for i in range(3):
                    dummy = usb.read_intensity(timeout_seconds=2.0)
                    if dummy is not None:
                        logger.info(f"   Dummy read {i+1}/3: Success ({len(dummy)} pixels)")
                    else:
                        logger.warning(f"   Dummy read {i+1}/3: Timeout (expected, continuing...)")
                    time.sleep(0.05)

                logger.info("✅ USB buffer cleared")
            except Exception as e:
                logger.warning(f"⚠️ USB buffer clear had issues (continuing anyway): {e}")

            logger.info("✅ Hardware ready")

            # Load configuration
            self.calibration_progress.emit("Loading configuration...", 10)
            from utils.device_configuration import DeviceConfiguration

            device_serial = getattr(usb, 'serial_number', None)
            device_config = DeviceConfiguration(device_serial=device_serial)

            # Get LED timing from device config
            pre_led_delay_ms = device_config.get_pre_led_delay_ms()
            post_led_delay_ms = device_config.get_post_led_delay_ms()
            logger.info(f"📊 LED timing: PRE={pre_led_delay_ms}ms, POST={post_led_delay_ms}ms")

            # Run calibration
            from utils.calibration_6step import run_full_6step_calibration

            logger.info("🚀 Starting 6-step calibration...")

            # Get device type from controller
            device_type = type(ctrl).__name__

            cal_result = run_full_6step_calibration(
                usb=usb,
                ctrl=ctrl,
                device_type=device_type,
                device_config=device_config,
                detector_serial=device_serial,
                pre_led_delay_ms=pre_led_delay_ms,
                post_led_delay_ms=post_led_delay_ms,
                progress_callback=self._progress_callback
            )

            if not cal_result or not cal_result.success:
                error_msg = "Calibration failed"
                if cal_result:
                    if hasattr(cal_result, 'error') and cal_result.error:
                        error_msg = cal_result.error
                    elif hasattr(cal_result, 'error_message') and cal_result.error_message:
                        error_msg = cal_result.error_message
                raise RuntimeError(error_msg)

            # Create immutable CalibrationData
            self.calibration_progress.emit("Storing results...", 95)

            device_info = {
                'device_type': type(ctrl).__name__,
                'detector_serial': device_serial or 'N/A',
                'firmware_version': getattr(ctrl, 'version', 'N/A'),
                'pre_led_delay_ms': pre_led_delay_ms,
                'post_led_delay_ms': post_led_delay_ms
            }

            # Get wavelength indices from calibration result
            wave_min_index = cal_result.wave_min_index
            wave_max_index = cal_result.wave_max_index

            # CalibrationData is just a type alias for LEDCalibrationResult
            calibration_data = cal_result

            if not calibration_data.validate():
                raise RuntimeError("Calibration data validation failed")

            logger.info("✅ Calibration data created and validated")

            # Store calibration data
            self._current_calibration_data = calibration_data
            self._calibration_completed = True

            # Update sensor_ready status based on transmission QC
            sensor_ready = self._evaluate_sensor_ready(calibration_data)
            if sensor_ready:
                hardware_mgr._sensor_verified = True
                logger.info("✅ SENSOR READY: Transmission QC passed")
            else:
                logger.warning("⚠️  SENSOR NOT READY: Transmission QC did not pass")

            # Emit completion signal
            self.calibration_complete.emit(calibration_data)

            # Handle post-calibration UI - KEEP DIALOG OPEN and ENABLE START BUTTON
            if self._calibration_dialog:
                self._calibration_dialog.update_title("✅ Calibration Complete!")
                self._calibration_dialog.update_status(
                    "Review QC results, then click Start to begin live data acquisition."
                )
                self._calibration_dialog.set_progress(100, 100)
                self._calibration_dialog.enable_start_button()
                logger.info("✅ Calibration dialog updated - Start button enabled for live data")

            # Some builds may not include the UI hook; guard the call
            if hasattr(self, "_on_calibration_complete_ui"):
                self._on_calibration_complete_ui(calibration_data)

        except Exception as e:
            logger.error(f"❌ Calibration failed: {e}", exc_info=True)
            self.calibration_failed.emit(str(e))

            if self._calibration_dialog:
                self._calibration_dialog.update_title("❌ Calibration Failed")
                self._calibration_dialog.update_status(f"Error: {e}")
                self._calibration_dialog.hide_progress_bar()

        finally:
            self._running = False
            logger.info("Calibration service reset - UI should be re-enabled")
            # No stream redirection performed; nothing to restore.
            # Detach file handler cleanly so subsequent runs create fresh logs
            try:
                if log_handler is not None:
                    logger.info("[CAL] Closing file logger")
                    logger.removeHandler(log_handler)
                    log_handler.close()
            except Exception:
                pass

    def _evaluate_sensor_ready(self, calibration_data: CalibrationData) -> bool:
        """Evaluate if sensor is ready based on transmission QC.

        Args:
            calibration_data: Calibration data with QC results

        Returns:
            True if at least one channel passed transmission QC
        """
        try:
            transmission_validation = calibration_data.transmission_validation

            if not transmission_validation:
                logger.warning("No transmission validation data available")
                return False

            # Check if at least one channel passed
            passed_channels = []
            for ch, validation in transmission_validation.items():
                status = validation.get('status', '')
                if '✅ PASS' in status:
                    passed_channels.append(ch)

            if passed_channels:
                logger.info(f"Sensor ready: {len(passed_channels)}/{len(transmission_validation)} channels passed QC")
                logger.info(f"   Passed channels: {passed_channels}")
                return True
            else:
                logger.warning("No channels passed transmission QC")
                return False

        except Exception as e:
            logger.error(f"Error evaluating sensor ready status: {e}")
            return False

    def get_current_calibration(self) -> Optional[CalibrationData]:
        """Get current calibration data.

        Returns:
            CalibrationData if calibration completed, None otherwise
        """
        return self._current_calibration_data

    def _update_ml_intelligence(self, calibration_data: CalibrationData) -> None:
        """Update ML QC intelligence with new calibration data.

        This runs all 4 ML models:
        1. Calibration quality prediction
        2. LED health monitoring
        3. Sensor coating degradation
        4. Optical alignment (baseline-based, non-interfering)

        Args:
            calibration_data: Latest calibration QC results
        """
        try:
            # Initialize ML intelligence if not done yet
            if self._ml_intelligence is None:
                device_serial = calibration_data.detector_serial or "unknown"
                self._ml_intelligence = MLQCIntelligence(device_serial=device_serial)
                logger.info(f"🤖 ML QC Intelligence initialized for {device_serial}")

            # Update ML models with new calibration data
            self._ml_intelligence.update_from_calibration(calibration_data)

            # Run all 4 ML models and log predictions
            logger.info("=" * 80)
            logger.info("🤖 ML QC INTELLIGENCE - POST-CALIBRATION ANALYSIS")
            logger.info("=" * 80)

            # Model 1: Calibration Quality Prediction
            cal_pred = self._ml_intelligence.predict_next_calibration()
            logger.info(f"\n📊 Model 1: Next Calibration Prediction")
            logger.info(f"   Failure Probability: {cal_pred.failure_probability*100:.1f}%")
            logger.info(f"   Risk Level: {cal_pred.risk_level.upper()}")
            if cal_pred.warnings:
                for warning in cal_pred.warnings:
                    logger.warning(f"   ⚠️  {warning}")
            if cal_pred.recommendations:
                for rec in cal_pred.recommendations:
                    logger.info(f"   💡 {rec}")

            # Model 2: LED Health Monitoring
            led_statuses = self._ml_intelligence.predict_led_health()
            logger.info(f"\n💡 Model 2: LED Health Status")
            for led in led_statuses:
                status_emoji = {'excellent': '✅', 'good': '✅', 'degrading': '⚠️', 'critical': '🚨'}.get(led.status, '❓')
                logger.info(f"   {status_emoji} Ch {led.channel.upper()}: {led.status} (intensity={led.current_intensity}, trend={led.intensity_trend:+.1f}/cal)")
                if led.replacement_recommended:
                    logger.warning(f"      🚨 REPLACEMENT RECOMMENDED")
                elif led.days_until_replacement and led.days_until_replacement < 30:
                    logger.warning(f"      ⚠️  Estimated {led.days_until_replacement} days until replacement")

            # Model 3: Sensor Coating Degradation
            coating = self._ml_intelligence.predict_sensor_coating_life()
            logger.info(f"\n🔬 Model 3: Sensor Coating Status")
            logger.info(f"   Quality: {coating.coating_quality.upper()}")
            logger.info(f"   Current FWHM (avg): {coating.current_fwhm_avg:.1f} nm")
            logger.info(f"   Trend: {coating.fwhm_trend:+.2f} nm/calibration")
            if coating.estimated_experiments_remaining:
                logger.info(f"   Estimated Lifespan: {coating.estimated_experiments_remaining} experiments")
            if coating.replacement_warning:
                logger.warning(f"   ⚠️  REPLACEMENT WARNING: Sensor chip approaching end of life")

            # Model 4: Optical Alignment (Baseline-based, Non-interfering)
            alignment = self._ml_intelligence.check_optical_alignment(calibration_data)
            logger.info(f"\n🔧 Model 4: Optical Alignment (Calibration Baseline)")
            logger.info(f"   P/S Ratio Baseline: {alignment.ps_ratio_baseline:.3f}")
            logger.info(f"   Deviation: {alignment.ps_ratio_deviation:.3f}")
            logger.info(f"   Confidence: {alignment.orientation_confidence*100:.0f}%")
            if alignment.alignment_drift_detected:
                logger.warning(f"   🚨 DRIFT DETECTED: {alignment.warning_message}")
            elif alignment.maintenance_recommended:
                logger.warning(f"   ⚠️  {alignment.warning_message}")
            else:
                logger.info(f"   ✅ Alignment stable")

            logger.info("=" * 80)

            # Generate and save comprehensive report
            report = self._ml_intelligence.generate_intelligence_report()
            logger.debug(f"\n{report}")

        except Exception as e:
            logger.error(f"Failed to update ML QC intelligence: {e}", exc_info=True)

    def get_ml_intelligence(self) -> Optional[MLQCIntelligence]:
        """Get ML QC intelligence instance.

        Returns:
            MLQCIntelligence instance if initialized, None otherwise
        """
        return self._ml_intelligence
