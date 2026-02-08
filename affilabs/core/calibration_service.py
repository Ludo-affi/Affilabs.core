"""CalibrationService - Unified calibration interface.

Merges CalibrationCoordinator + CalibrationManager into single service.
Handles UI interaction, threading, progress, and QC display.
"""

from __future__ import annotations

import contextlib
import os
import threading
import time

from PySide6.QtCore import QObject, Signal

from affilabs.core.ml_qc_intelligence import MLQCIntelligence

# Phase 1.1 Domain Model + Adapter
from affilabs.domain import CalibrationData, led_calibration_result_to_domain
from affilabs.ui.ui_message import error as ui_error
from affilabs.utils.logger import logger


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

    def __init__(self, app) -> None:
        """Initialize calibration service.

        Args:
            app: Reference to main Application instance

        """
        super().__init__()
        self.app = app
        self._thread = None
        self._running = False
        self._calibration_dialog: object | None = None
        self._calibration_completed: bool = False
        self._current_calibration_data: CalibrationData | None = None
        self._force_oem_retrain: bool = False  # Track if OEM button requested retrain
        self._retry_count: int = 0  # Track retry attempts (max 3)
        self._max_retries: int = 3  # Maximum retry attempts

        # ML QC Intelligence (initialized lazily when device connects)
        self._ml_intelligence: MLQCIntelligence | None = None

    def start_calibration(self, force_oem_retrain: bool = False) -> bool:
        """Start calibration dialog (does NOT start calibration thread).

        The actual calibration begins when user clicks Start button in dialog.

        Args:
            force_oem_retrain: If True, always rebuild optical model (OEM calibration mode)

        Returns:
            True if dialog shown, False if already running

        """
        # Store retrain flag for use when calibration actually runs
        self._force_oem_retrain = force_oem_retrain

        if self._running:
            logger.warning("Calibration already in progress")
            return False

        # CRITICAL: Stop live data acquisition before calibration
        if hasattr(self.app, "data_mgr") and self.app.data_mgr:
            if self.app.data_mgr._acquiring:
                logger.info("🛑 Stopping live data acquisition before calibration...")
                self.app.data_mgr.stop_acquisition()
                # Wait briefly for acquisition to stop
                import time

                time.sleep(0.1)
                logger.info("[OK] Live data stopped")

        # Headless mode: allowed only when NOT running inside the UI
        # In UI context, we always show the dialog regardless of env var
        in_ui_context = hasattr(self.app, "main_window") and self.app.main_window is not None
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
                name="CalibrationService",
            )
            self._thread.start()
            self.calibration_started.emit()
            logger.info("[OK] Headless calibration thread started")
            return True

        logger.info("=" * 80)
        logger.info(
            "🎬 CALIBRATION SERVICE: Showing calibration dialog (awaiting Start)...",
        )
        logger.info("=" * 80)

        # Check if LED model exists - if not, prompt for OEM calibration instead
        if not force_oem_retrain:
            try:
                from affilabs.services.led_model_loader import LEDCalibrationModelLoader

                model_loader = LEDCalibrationModelLoader()
                detector_serial = (
                    getattr(self.app.hardware_mgr.usb, "serial_number", None)
                    if hasattr(self.app, "hardware_mgr") and self.app.hardware_mgr.usb
                    else None
                )

                if detector_serial:
                    led_model = model_loader.load_model(detector_serial)
                    if led_model is None:
                        logger.warning("❌ No LED calibration model found for this detector")
                        logger.warning(
                            "   OEM calibration is required before running regular calibration"
                        )

                        # Show prompt to run OEM calibration
                        from PySide6.QtWidgets import QMessageBox

                        reply = QMessageBox.question(
                            self.app.main_window,
                            "LED Model Missing",
                            "This detector has no LED calibration model.\n\n"
                            "OEM Calibration is required to create the LED model.\n\n"
                            "Would you like to run OEM Calibration now?\n\n"
                            "(This will take approximately 10-15 minutes)",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                            QMessageBox.StandardButton.Yes,
                        )

                        if reply == QMessageBox.StandardButton.Yes:
                            # Trigger OEM calibration instead
                            if hasattr(self.app, "_on_oem_led_calibration"):
                                self.app._on_oem_led_calibration()
                                return True
                        else:
                            logger.info(
                                "User declined OEM calibration - cancelling regular calibration"
                            )
                            return False
            except Exception as e:
                logger.warning(f"Could not check LED model status: {e}")

        # Reset state
        self._calibration_completed = False
        self._current_calibration_data = None
        self._retry_count = 0  # Reset retry counter for new calibration attempt

        # Show progress dialog with Start button; do NOT auto-start
        self._show_progress_dialog()

        # Enable Start button for pre-calibration checklist (original feel)
        if self._calibration_dialog:
            with contextlib.suppress(Exception):
                self._calibration_dialog.enable_start_button_pre_calib()

        # Wait for user to click Start in the dialog
        return True

    @property
    def dialog(self):
        """Get the calibration progress dialog (read-only property for external status updates)."""
        return self._calibration_dialog

    def _show_progress_dialog(self) -> None:
        """Show calibration progress dialog."""
        from affilabs_core_ui import StartupCalibProgressDialog

        # Check if pump is detected
        has_pump = self.app.hardware_mgr.pump is not None

        pump_instruction = ""
        if has_pump:
            pump_instruction = "  ✓  Buffer loaded in pump reservoir (for priming)\n"

        message = (
            "Please verify before calibrating:\n\n"
            "  ✓  Prism installed in sensor holder\n"
            "  ✓  Water or buffer applied to prism\n"
            "  ✓  No air bubbles visible\n"
            f"{pump_instruction}"
            "  ✓  Temperature stabilized (10 min after power-on)\n\n"
        )

        if has_pump:
            message += (
                "Calibration Process:\n"
                "  0. Pump Priming (6 cycles, ~60s)\n"
                "     → Optical calibration starts during cycle 3\n"
                "  1. Hardware Validation & LED Verification\n"
                "  2. Wavelength Calibration\n"
                "  3. LED Brightness Measurement & 3-Stage Model Load\n"
                "  4. S-Mode LED Convergence + Reference Capture\n"
                "  5. P-Mode LED Convergence + Reference + Dark Capture\n"
                "  6. QC Validation & Result Packaging\n\n"
                "Takes approximately 2 minutes (pump + optics)."
            )
        else:
            message += (
                "6-Step Calibration Process:\n"
                "  1. Hardware Validation & LED Verification\n"
                "  2. Wavelength Calibration\n"
                "  3. LED Brightness Measurement & 3-Stage Model Load\n"
                "  4. S-Mode LED Convergence + Reference Capture\n"
                "  5. P-Mode LED Convergence + Reference + Dark Capture\n"
                "  6. QC Validation & Result Packaging\n\n"
                "Takes approximately 30-60 seconds."
            )

        self._calibration_dialog = StartupCalibProgressDialog(
            parent=self.app.main_window,
            title="Calibrating SPR System",
            message=message,
            show_start_button=True,
        )

        # Connect dialog signals (post-calibration continue handled if button exists)
        with contextlib.suppress(Exception):
            self._calibration_dialog.start_clicked.connect(
                self._on_start_button_clicked,
            )
            # Connect retry/continue signals for failure recovery
            self._calibration_dialog.retry_clicked.connect(
                self._on_retry_calibration,
            )
            self._calibration_dialog.continue_anyway_clicked.connect(
                self._on_continue_anyway,
            )

        # Connect calibration service signals to update dialog
        self.calibration_progress.connect(self._update_dialog_progress)
        self.calibration_failed.connect(self._on_calibration_failed_dialog)

        # Add Compression Assistant button alongside Start (visible only before calibration)
        self._add_compression_assistant_button()

        self._calibration_dialog.hide_progress_bar()
        self._calibration_dialog.show()
        logger.info("[OK] Calibration dialog displayed (Start button visible)")

    def _add_compression_assistant_button(self) -> None:
        """Add a 'Compression Assistant' button to the calibration dialog.

        Only shown for P4SPR 2.0 devices (PicoP4SPR + barrel polarizer).
        P4SPR original (round polarizer) does not support it, and
        P4PRO / P4PRO Plus will have a different implementation.
        """
        # Gate: only available for P4SPR 2.0 = PicoP4SPR + barrel polarizer
        hw = self.app.hardware_mgr
        if not hw or not hw.ctrl:
            return
        device_type = hw.ctrl.get_device_type() if hasattr(hw.ctrl, "get_device_type") else None
        if device_type != "PicoP4SPR":
            logger.debug(f"Compression Assistant not available for device type: {device_type}")
            return

        # Check polarizer type from device_config (barrel = P4SPR 2.0)
        device_config = getattr(hw, "device_config", None) or getattr(
            self.app.main_window, "device_config", None
        )
        polarizer_type = None
        if device_config and hasattr(device_config, "get_polarizer_type"):
            polarizer_type = device_config.get_polarizer_type()
        if polarizer_type != "barrel":
            logger.debug(
                f"Compression Assistant requires barrel polarizer (found: {polarizer_type})"
            )
            return

        from PySide6.QtWidgets import QPushButton

        dialog = self._calibration_dialog
        if dialog is None:
            return

        btn = QPushButton("\U0001f527 Compression Assistant")
        btn.setFixedSize(210, 36)
        btn.setStyleSheet(
            "QPushButton {"
            "  background: #5856D6;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover {"
            "  background: #4B49B0;"
            "}"
        )
        btn.setToolTip(
            "Launch the guided Compression Assistant to help\n"
            "position your sensor chip before calibration.\n"
            "Requires polarizer to be already calibrated."
        )
        btn.clicked.connect(self._on_compression_assistant_clicked)

        # Insert before the Start button (at position 1, after the leading stretch)
        dialog.button_layout.insertWidget(1, btn)
        self._compression_assistant_btn = btn

    def _on_compression_assistant_clicked(self) -> None:
        """Handle Compression Assistant button click.

        1. Move servo to P-pol position (using device_config as source of truth)
        2. Launch Compression Assistant as modal window
        3. Return control to calibration dialog when done
        """
        logger.info("=" * 60)
        logger.info("\U0001f527 Compression Assistant requested")
        logger.info("=" * 60)

        # Validate hardware
        hw = self.app.hardware_mgr
        if not hw or not hw.ctrl or not hw.usb:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self._calibration_dialog,
                "Hardware Not Ready",
                "Please connect hardware before using the Compression Assistant.",
            )
            return

        # Move servo to P-pol using device_config positions (source of truth),
        # following the same pattern as _load_device_settings / _on_polarizer_toggle
        logger.info("Moving servo to P-pol position...")
        try:
            # 1. Read positions from device_config (single source of truth)
            device_config = getattr(self.app.main_window, "device_config", None)
            if device_config:
                positions = device_config.get_servo_positions()
                if positions:
                    s_pos = positions.get("s")
                    p_pos = positions.get("p")
                    logger.info(f"   Device config positions: S={s_pos}, P={p_pos}")
                    # 2. Cache positions in controller so set_mode uses them
                    hw.ctrl.set_servo_positions(s=s_pos, p=p_pos)
                else:
                    logger.warning("   Servo positions not found in device_config")
            else:
                logger.warning("   device_config not available")

            # 3. Move to P-pol (same call used throughout the app)
            hw.ctrl.set_mode(mode="p")
            hw._current_polarizer = "p"
            logger.info("[OK] Servo moved to P-pol")
        except Exception as e:
            logger.error(f"Failed to move servo to P-pol: {e}")
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self._calibration_dialog,
                "Servo Error",
                f"Failed to move polarizer to P-pol position:\n{e}",
            )
            return

        # Temporarily hide calibration dialog
        if self._calibration_dialog:
            self._calibration_dialog.hide()

        # Launch Compression Assistant modally
        logger.info("Launching Compression Assistant (modal)...")
        try:
            from standalone_tools.compression_trainer_ui import (
                CompressionTrainerWindow,
            )

            CompressionTrainerWindow.launch_modal(
                parent=self.app.main_window,
                hardware_mgr=hw,
            )
        except Exception as e:
            logger.error(f"Compression Assistant error: {e}")
            import traceback

            traceback.print_exc()

        # Re-show calibration dialog
        logger.info("Compression Assistant closed — returning to calibration dialog")
        if self._calibration_dialog:
            self._calibration_dialog.show()
            self._calibration_dialog.raise_()

    def _progress_callback(self, message: str, progress: int = 0) -> None:
        """Progress callback for calibration routines.

        This method is passed to run_full_7step_calibration() to receive
        progress updates during the calibration process.

        Args:
            message: Progress message to display
            progress: Progress percentage (0-100)

        """
        # Emit to UI and log for console visibility
        with contextlib.suppress(Exception):
            logger.info(f"[CAL] {message} ({progress}%)")
        self.calibration_progress.emit(message, progress)

    def _update_dialog_progress(self, message: str, progress: int) -> None:
        """Update calibration dialog with progress information.

        Args:
            message: Progress message to display
            progress: Progress percentage (0-100)

        """
        if self._calibration_dialog:
            # Show progress bar on first progress update
            if not self._calibration_dialog.progress_bar.isVisible():
                self._calibration_dialog.show_progress_bar()
            self._calibration_dialog.update_status(message)
            self._calibration_dialog.set_progress(
                progress,
                100,
            )  # Now thread-safe via signal

    def _on_calibration_failed_dialog(self, error_message: str) -> None:
        """Handle calibration failure in dialog - show retry/continue options.

        Args:
            error_message: Error message to display

        """
        if self._calibration_dialog:
            # Show retry options if under max attempts
            if self._retry_count < self._max_retries:
                logger.info(
                    f"Calibration failed (attempt {self._retry_count + 1}/{self._max_retries + 1}). Showing retry options..."
                )
                self._calibration_dialog.show_error_state(
                    error_message=error_message,
                    retry_count=self._retry_count,
                    max_retries=self._max_retries,
                )
            else:
                logger.warning(
                    f"Max retries ({self._max_retries}) reached. Showing final error state."
                )
                self._calibration_dialog.show_max_retries_error(error_message)

    def _on_retry_calibration(self) -> None:
        """Handle retry button click - user wants to retry calibration."""
        logger.info("=" * 80)
        logger.info("🔄 User clicked Retry - restarting calibration...")
        logger.info("=" * 80)

        if self._calibration_dialog:
            # Increment retry counter
            self._retry_count += 1
            logger.info(f"Retry attempt {self._retry_count}/{self._max_retries}")

            # Reset dialog to progress state
            self._calibration_dialog.reset_to_progress_state()
            self._calibration_dialog.update_status("Retrying calibration...")
            self._calibration_dialog.show_progress_bar()

            # Restart calibration thread
            self._running = True
            self._calibration_completed = False
            self._current_calibration_data = None

            self._thread = threading.Thread(
                target=self._run_calibration,
                daemon=True,
                name="CalibrationService-Retry",
            )
            self._thread.start()
            self.calibration_started.emit()
            logger.info("[OK] Retry calibration thread started")

    def _on_continue_anyway(self) -> None:
        """Handle continue anyway button - user wants to proceed despite failure."""
        logger.warning("=" * 80)
        logger.warning("⚠️  User chose to continue with failed calibration")
        logger.warning("=" * 80)

        if self._calibration_dialog:
            # Close dialog and allow user to proceed
            logger.info("Closing calibration dialog...")
            self._calibration_dialog.accept()
            self._calibration_dialog = None

        # Reset retry counter for next calibration attempt
        self._retry_count = 0
        logger.info("[OK] Dialog closed - user can troubleshoot manually")

    def _on_start_button_clicked(self) -> None:
        """Handle Start button click - begin calibration or transfer to live view."""
        if self._calibration_completed:
            # Calibration complete - transfer to live acquisition
            logger.info("=" * 80)
            logger.info("[OK] User clicked Start - transferring to live view")
            logger.info("=" * 80)

            # Verify calibration data is available
            if not self._current_calibration_data:
                logger.error("[ERROR] FATAL: No calibration data available!")
                ui_error(
                    self._calibration_dialog if self._calibration_dialog else None,
                    "Calibration Error",
                    "No calibration data available. Please recalibrate.",
                )
                return

            # Start live acquisition FIRST
            if hasattr(self.app, "data_mgr"):
                try:
                    logger.info("📊 Verifying acquisition manager is ready...")
                    if not self.app.data_mgr.calibrated:
                        logger.error(
                            "[ERROR] Acquisition manager reports not calibrated!",
                        )
                        msg = "Acquisition manager not calibrated. Calibration data may not have been applied."
                        raise RuntimeError(msg)

                    logger.info("🚀 Starting live acquisition...")
                    self.app.data_mgr.start_acquisition()
                    logger.info("[OK] Live acquisition started successfully")
                except Exception as e:
                    logger.error(
                        f"[ERROR] Failed to start acquisition: {e}",
                        exc_info=True,
                    )
                    # Show error but don't close dialog yet
                    ui_error(
                        self._calibration_dialog if self._calibration_dialog else None,
                        "Acquisition Error",
                        f"Failed to start live acquisition:\n{e}\n\nPlease check the logs and try again.",
                    )
                    return
            else:
                logger.error("[ERROR] FATAL: data_mgr not found in app!")
                ui_error(
                    self._calibration_dialog if self._calibration_dialog else None,
                    "System Error",
                    "Acquisition manager not found. Please restart the application.",
                )
                return

            # Close calibration dialog AFTER acquisition starts successfully
            if self._calibration_dialog:
                # Use QTimer to defer dialog close to ensure acquisition thread starts
                # and allow Qt event loop to process properly
                from PySide6.QtCore import QTimer

                def close_dialog() -> None:
                    if self._calibration_dialog:
                        try:
                            logger.info("🔄 Closing calibration dialog...")

                            # Store reference to overlay before clearing dialog reference
                            overlay_to_cleanup = None
                            if hasattr(self._calibration_dialog, "overlay"):
                                overlay_to_cleanup = self._calibration_dialog.overlay
                                self._calibration_dialog.overlay = None  # Clear reference first

                            # Close dialog first (this will trigger closeEvent)
                            logger.info("   Closing dialog window...")
                            self._calibration_dialog.accept()
                            self._calibration_dialog = None
                            logger.info("   [OK] Dialog closed")

                            # Clean up overlay AFTER dialog is closed
                            if overlay_to_cleanup:
                                try:
                                    logger.info("   Cleaning up overlay...")
                                    overlay_to_cleanup.hide()
                                    overlay_to_cleanup.deleteLater()
                                    logger.info("   [OK] Overlay cleaned up")
                                except RuntimeError as e:
                                    logger.debug(f"   Overlay already deleted: {e}")
                                except Exception as e:
                                    logger.warning(f"   Error cleaning overlay: {e}")

                            logger.info(
                                "[OK] Calibration dialog and overlay closed successfully",
                            )
                        except Exception as e:
                            logger.error(
                                f"[WARN] Error closing dialog: {e}",
                                exc_info=True,
                            )

                QTimer.singleShot(150, close_dialog)  # Slightly longer delay for safety
                logger.info("📋 Dialog close scheduled in 150ms")

            logger.info("=" * 80)
            logger.info("[OK] Calibration-to-live transfer completed")
            logger.info("=" * 80)
            return

        # Start calibration (first time only)
        if self._running:
            logger.warning(
                "Calibration already running - ignoring duplicate click",
            )
            return

        logger.info("Starting calibration...")

        # Update dialog
        if self._calibration_dialog:
            if self._calibration_dialog.start_button:
                self._calibration_dialog.start_button.setEnabled(False)
            # Hide Compression Assistant button during calibration
            if hasattr(self, "_compression_assistant_btn") and self._compression_assistant_btn:
                self._compression_assistant_btn.hide()
            self._calibration_dialog.show_progress_bar()
            self._calibration_dialog.update_status(
                "Running LED intensity calibration...",
            )

        # Launch calibration in background thread
        self._running = True
        self._thread = threading.Thread(
            target=self._run_calibration,
            daemon=True,
            name="CalibrationService",
        )
        self._thread.start()
        self.calibration_started.emit()

    def _run_calibration(self) -> None:
        """Main calibration routine (runs in background thread)."""
        # CRITICAL FIX: Disable logger thread filtering for this calibration thread
        # The logger's ConditionalThreadFilterConsoleHandler blocks background threads
        from affilabs.utils.logger import enable_verbose_console

        enable_verbose_console()

        # File logger to capture full calibration thread output
        log_handler = None
        try:
            import logging
            import os

            from affilabs.utils.time_utils import for_filename

            os.makedirs("logs", exist_ok=True)
            logfile = os.path.join(
                "logs",
                for_filename(prefix="calibration_", ext="log"),
            )
            log_handler = logging.FileHandler(logfile, encoding="utf-8")
            log_handler.setLevel(logging.INFO)
            formatter = logging.Formatter("%(asctime)s :: %(levelname)s :: %(message)s")
            log_handler.setFormatter(formatter)
            logger.addHandler(log_handler)
            logger.info(f"Calibration log: {logfile}")
        except Exception as e:
            with contextlib.suppress(Exception):
                logger.warning(f"Could not initialize calibration log file: {e}")

        try:
            # Get hardware
            self.calibration_progress.emit("Initializing...", 5)

            hardware_mgr = self.app.hardware_mgr
            ctrl = hardware_mgr.ctrl
            usb = hardware_mgr.usb
            pump = hardware_mgr.pump  # Get pump if available

            if not ctrl:
                msg = "Controller not connected"
                raise RuntimeError(msg)
            if not usb:
                msg = "Spectrometer not connected"
                raise RuntimeError(msg)

            # === PUMP PRIMING (if available) + PARALLEL OPTICAL CALIBRATION ===
            # Auto-prime enabled - pump will be primed during startup calibration
            cal_result = None

            if pump:  # ENABLED
                logger.info(
                    "Pump detected - starting prime sequence with parallel optical calibration...",
                )
                self.calibration_progress.emit("Pump Priming: Initializing", 8)

                import asyncio
                import threading

                # Track optical calibration state
                optical_cal_complete = threading.Event()
                optical_cal_result = None
                optical_cal_error = None
                optical_cal_thread = None

                # Define optical calibration function to run in parallel
                def run_optical_calibration():
                    nonlocal optical_cal_result, optical_cal_error
                    try:
                        logger.info(
                            "🔬 Starting optical calibration (parallel with pump priming)..."
                        )

                        # USB buffer clear
                        logger.info("🔄 Clearing USB buffer with dummy reads...")
                        try:
                            # NOTE: Skip changing integration time - just use current setting
                            # Changing integration caused detector to hang on first read
                            current_int = (
                                usb._integration_time * 1000
                                if hasattr(usb, "_integration_time")
                                else 100
                            )
                            logger.info(
                                f"   Using current integration time ({current_int:.1f}ms)..."
                            )
                            for i in range(3):
                                dummy = usb.read_intensity()
                                if dummy is not None:
                                    logger.info(f"   Dummy read {i + 1}/3: Success")
                                time.sleep(0.05)
                            logger.info("[OK] USB buffer cleared")
                        except Exception as e:
                            logger.warning(f"USB buffer clear issues: {e}")

                        # Load configuration
                        from affilabs.utils.device_configuration import DeviceConfiguration

                        device_serial = getattr(usb, "serial_number", None)
                        device_config = DeviceConfiguration(device_serial=device_serial)

                        # Run optical calibration
                        from affilabs.core.calibration_orchestrator import run_startup_calibration

                        device_type = (
                            ctrl.get_device_type()
                        )  # Use HAL method, not Python class name

                        # Progress callback that maps to overall progress (pump uses 8-40%, optical uses 40-95%)
                        def optical_progress(msg, pct):
                            adjusted_pct = 40 + int(pct * 0.55)
                            self.calibration_progress.emit(f"Optical: {msg}", adjusted_pct)

                        optical_cal_result = run_startup_calibration(
                            usb=usb,
                            ctrl=ctrl,
                            device_type=device_type,
                            device_config=device_config,
                            detector_serial=device_serial,
                            progress_callback=optical_progress,
                            use_convergence_engine=True,
                            force_oem_retrain=self._force_oem_retrain,
                        )

                        logger.info("✅ Optical calibration complete")

                    except Exception as e:
                        optical_cal_error = e
                        logger.exception("❌ Optical calibration failed")
                    finally:
                        optical_cal_complete.set()

                # Pump priming with optical cal trigger on cycle 3
                async def prime_with_optical_cal():
                    nonlocal optical_cal_thread

                    try:
                        # Get raw controller for valve operations (HAL adapter doesn't have valve methods)
                        raw_ctrl = ctrl._ctrl if hasattr(ctrl, "_ctrl") else ctrl

                        # CRITICAL: Initialize pumps before priming!
                        logger.info("🔧 Initializing pumps to zero position...")
                        self.calibration_progress.emit("Initializing Pumps", 5)
                        pump._pump.pump.initialize_pumps()
                        logger.info("✅ Pumps initialized and ready")

                        aspirate_speed_ul_s = 24000.0 / 60.0
                        dispense_speed_ul_s = 5000.0 / 60.0
                        volume_ul = 1000.0

                        for cycle in range(1, 7):  # 6 cycles
                            # Only emit pump progress before optical cal starts (cycles 1-3)
                            # After cycle 4, optical cal controls the progress bar (40-95%)
                            if cycle <= 3:
                                progress = 8 + int((cycle - 1) / 6 * 32)  # 8-40%
                                self.calibration_progress.emit(
                                    f"Pump Priming: Cycle {cycle}/6", progress
                                )

                            logger.info(f"\n🔄 Pump Cycle {cycle}/6")

                            # Open 6-port valves at cycle 3 (INJECT position for flow)
                            if cycle == 3:
                                logger.info("  🔧 Opening 6-port valves to INJECT position")
                                if raw_ctrl:
                                    result1 = raw_ctrl.knx_six(state=1, ch=1)
                                    logger.info(
                                        f"     6-port valve 1: {'SUCCESS' if result1 else 'FAILED'}"
                                    )
                                    await asyncio.sleep(0.2)
                                    result2 = raw_ctrl.knx_six(state=1, ch=2)
                                    logger.info(
                                        f"     6-port valve 2: {'SUCCESS' if result2 else 'FAILED'}"
                                    )
                                await asyncio.sleep(0.3)

                            elif cycle == 4:
                                # === START OPTICAL CALIBRATION IN PARALLEL ===
                                if not optical_cal_thread:
                                    logger.info(
                                        "🚀 Starting optical calibration in parallel (cycle 4)..."
                                    )
                                    optical_cal_thread = threading.Thread(
                                        target=run_optical_calibration,
                                        daemon=True,
                                        name="OpticalCalibration",
                                    )
                                    optical_cal_thread.start()

                            elif cycle == 5:
                                logger.info("  🔧 Opening 3-way valves to LOAD position")
                                if raw_ctrl:
                                    result1 = raw_ctrl.knx_three(state=1, ch=1)
                                    logger.info(
                                        f"     3-way valve 1: {'SUCCESS' if result1 else 'FAILED'}"
                                    )
                                    await asyncio.sleep(0.2)
                                    result2 = raw_ctrl.knx_three(state=1, ch=2)
                                    logger.info(
                                        f"     3-way valve 2: {'SUCCESS' if result2 else 'FAILED'}"
                                    )
                                await asyncio.sleep(0.3)

                            # Aspirate
                            pump._pump.pump.aspirate_both(volume_ul, aspirate_speed_ul_s)
                            (
                                p1_ready,
                                p2_ready,
                                _,
                                _,
                                _,
                            ) = await asyncio.get_event_loop().run_in_executor(
                                None, pump._pump.pump.wait_until_both_ready, 60.0
                            )

                            if not (p1_ready and p2_ready):
                                # Recovery: switch to INPUT and send plunger home
                                failed_pumps = []
                                if not p1_ready:
                                    failed_pumps.append("Pump 1")
                                if not p2_ready:
                                    failed_pumps.append("Pump 2")

                                pumps_str = " and ".join(failed_pumps)
                                logger.warning(
                                    f"⚠️ {pumps_str} blocked - attempting to unclog by pushing liquid back through valve..."
                                )

                                if not p1_ready:
                                    logger.info(
                                        "  🔧 Pump 1: Switching to INPUT valve and pushing liquid back to unclog"
                                    )
                                    pump._pump.pump.set_valve_input(1)
                                    await asyncio.sleep(0.5)
                                    pump._pump.pump.move_to_position(1, 0, speed_ul_s=100)
                                    await asyncio.sleep(2.0)

                                if not p2_ready:
                                    logger.info(
                                        "  🔧 Pump 2: Switching to INPUT valve and pushing liquid back to unclog"
                                    )
                                    pump._pump.pump.set_valve_input(2)
                                    await asyncio.sleep(0.5)
                                    pump._pump.pump.move_to_position(2, 0, speed_ul_s=100)
                                    await asyncio.sleep(2.0)

                                raise RuntimeError(
                                    f"{pumps_str} blocked - pushed liquid back from device to unclog valve. Check tubing and try calibration again."
                                )

                            await asyncio.sleep(0.5)

                            # Dispense
                            pump._pump.pump.dispense_both(volume_ul, dispense_speed_ul_s)
                            (
                                p1_ready,
                                p2_ready,
                                _,
                                _,
                                _,
                            ) = await asyncio.get_event_loop().run_in_executor(
                                None, pump._pump.pump.wait_until_both_ready, 60.0
                            )

                            if not (p1_ready and p2_ready):
                                raise RuntimeError("Pump dispense failed")

                            logger.info("  ✅ Cycle completed")

                        # CRITICAL: Close all valves after priming to prevent device heating
                        if raw_ctrl:
                            logger.info(
                                "\n🔒 Closing all valves after priming (critical safety step)..."
                            )
                            try:
                                # Close 3-way valves to WASTE (state 0)
                                raw_ctrl.knx_three(state=0, ch=1)
                                await asyncio.sleep(0.1)
                                raw_ctrl.knx_three(state=0, ch=2)
                                await asyncio.sleep(0.1)

                                # Close 6-port valves to LOAD (state 0)
                                raw_ctrl.knx_six(state=0, ch=1)
                                await asyncio.sleep(0.1)
                                raw_ctrl.knx_six(state=0, ch=2)
                                logger.info("✅ All valves closed - device safe from heating")
                            except Exception as valve_err:
                                logger.error(f"❌ CRITICAL: Valve close failed: {valve_err}")
                                logger.error(
                                    "⚠️  DEVICE MAY BE HEATING! Manually power off if needed!"
                                )

                        logger.info("✅ Pump priming complete - waiting for optical calibration...")

                    except Exception as e:
                        logger.exception(f"❌ Pump priming failed: {e}")
                        raise

                # Run pump priming in asyncio loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(prime_with_optical_cal())
                finally:
                    loop.close()

                # Wait for optical calibration to complete
                self.calibration_progress.emit("Waiting for optical calibration...", 95)
                optical_cal_complete.wait(
                    timeout=300
                )  # 5 minute timeout (servo cal can take 2-3 min)

                if optical_cal_error:
                    raise optical_cal_error

                if optical_cal_result is None:
                    raise RuntimeError("Optical calibration timed out or failed to start")

                cal_result = optical_cal_result

            else:
                # === NO PUMP - Run optical calibration directly ===
                logger.info("No pump detected - running optical calibration only...")

                # CRITICAL FIX: Clear USB device buffer with dummy reads
                logger.info("🔄 Clearing USB buffer with dummy reads...")
                try:
                    # NOTE: Skip changing integration time - just use current setting
                    # Changing integration caused detector to hang on first read
                    current_int = (
                        usb._integration_time * 1000 if hasattr(usb, "_integration_time") else 100
                    )
                    logger.info(f"   Using current integration time ({current_int:.1f}ms)...")
                    for i in range(3):
                        dummy = usb.read_intensity()
                        if dummy is not None:
                            logger.info(f"   Dummy read {i + 1}/3: Success ({len(dummy)} pixels)")
                        else:
                            logger.warning(f"   Dummy read {i + 1}/3: No data (continuing...)")
                        time.sleep(0.05)
                    logger.info("[OK] USB buffer cleared")
                except Exception as e:
                    logger.warning(f"[WARN] USB buffer clear had issues (continuing anyway): {e}")

                logger.info("[OK] Hardware ready")

                # Load configuration and run calibration (no-pump path)
                self.calibration_progress.emit("Loading configuration...", 10)
                from affilabs.utils.device_configuration import DeviceConfiguration

                device_serial = getattr(usb, "serial_number", None)
                device_config = DeviceConfiguration(device_serial=device_serial)

                # Run calibration
                from affilabs.core.calibration_orchestrator import run_startup_calibration

                logger.info("🚀 Starting 6-step calibration...")
                device_type = ctrl.get_device_type()  # Use HAL method, not Python class name

                try:
                    cal_result = run_startup_calibration(
                        usb=usb,
                        ctrl=ctrl,
                        device_type=device_type,
                        device_config=device_config,
                        detector_serial=device_serial,
                        progress_callback=self._progress_callback,
                        use_convergence_engine=True,
                        force_oem_retrain=self._force_oem_retrain,
                    )
                except RuntimeError as e:
                    error_str = str(e)

                    # Detect servo calibration requirement:
                    # 1. Missing servo positions
                    # 2. Polarizer blocking (signal <5%)
                    # 3. Signal extremely low (likely wrong positions)
                    # DO NOT trigger on generic convergence failures when there's light!
                    needs_servo_cal = (
                        "Servo positions not found" in error_str
                        or "ServoCalibrationRequired" in type(e).__name__
                        or "Polarizer blocking light" in error_str
                        or "positions are INCORRECT" in error_str
                        or "Signal is extremely low" in error_str
                        or "Signal is too low" in error_str
                    )
                    # Removed: "convergence failed" - too broad, triggers even with good signal

                    if needs_servo_cal:
                        logger.warning("=" * 80)
                        logger.warning(f"⚠️ Convergence issue detected: {error_str[:100]}...")
                        logger.warning("   This may indicate incorrect servo positions.")
                        logger.warning("=" * 80)
                        logger.warning("⚠️ SERVO CALIBRATION REQUIRED - Starting automatically...")
                        logger.warning("=" * 80)

                        # Emit progress update
                        self._progress_callback("Servo calibration required - starting...", 0)

                        # Trigger servo calibration automatically
                        logger.info("🔧 Starting automatic servo calibration...")
                        try:
                            # Import servo calibration function
                            from servo_polarizer_calibration.calibrate_polarizer import (
                                run_calibration_with_hardware,
                            )

                            # Create a simple hardware manager wrapper for servo calibration
                            class HardwareManagerWrapper:
                                def __init__(self, usb, ctrl):
                                    self.usb = usb
                                    self.ctrl = ctrl

                            hw_wrapper = HardwareManagerWrapper(usb=usb, ctrl=ctrl)

                            # Run servo calibration using existing hardware connection
                            logger.info(
                                "   Scanning servo positions to find correct S/P orientations..."
                            )
                            servo_success = run_calibration_with_hardware(
                                hardware_manager=hw_wrapper,
                                progress_callback=self._progress_callback,
                            )

                            if servo_success:
                                # Re-create device config to get updated servo positions from disk
                                from affilabs.utils.device_configuration import DeviceConfiguration

                                device_config = DeviceConfiguration(device_serial=device_serial)
                                servo_positions = device_config.get_servo_positions()

                                if servo_positions:
                                    s_pos = servo_positions["s"]
                                    p_pos = servo_positions["p"]
                                    logger.info("=" * 80)
                                    logger.info("✅ SERVO CALIBRATION COMPLETED SUCCESSFULLY")
                                    logger.info("=" * 80)
                                    logger.info(f"   New servo positions: S={s_pos}, P={p_pos}")
                                    logger.info(
                                        f"   Positions loaded from: {device_config.config_path}"
                                    )

                                    # CRITICAL: Sync to the app's live DeviceConfiguration
                                    # so any later save() won't clobber the values
                                    synced_to_app = False
                                    if (
                                        hasattr(self, "app")
                                        and self.app
                                        and hasattr(self.app, "main_window")
                                        and self.app.main_window
                                        and hasattr(self.app.main_window, "device_config")
                                        and self.app.main_window.device_config
                                    ):
                                        logger.info(
                                            "   🔄 Syncing to app's in-memory DeviceConfiguration..."
                                        )
                                        old_s = self.app.main_window.device_config.config.get(
                                            "hardware", {}
                                        ).get("servo_s_position")
                                        old_p = self.app.main_window.device_config.config.get(
                                            "hardware", {}
                                        ).get("servo_p_position")
                                        logger.info(f"      Before sync: S={old_s}, P={old_p}")

                                        self.app.main_window.device_config.set_servo_positions(
                                            s_pos, p_pos
                                        )
                                        synced_to_app = True

                                        new_s = self.app.main_window.device_config.config.get(
                                            "hardware", {}
                                        ).get("servo_s_position")
                                        new_p = self.app.main_window.device_config.config.get(
                                            "hardware", {}
                                        ).get("servo_p_position")
                                        logger.info(f"      After sync: S={new_s}, P={new_p}")

                                        # Force save to persist the change immediately
                                        self.app.main_window.device_config.save()
                                        logger.info(
                                            "      ✅ In-memory config synced and saved to disk"
                                        )
                                        logger.info(
                                            f"         Path: {self.app.main_window.device_config.config_path}"
                                        )
                                    else:
                                        logger.warning(
                                            "   ⚠️  Could not access app's in-memory DeviceConfiguration!"
                                        )
                                        logger.warning(
                                            "      This may cause positions to be overwritten later"
                                        )
                                        logger.warning("      Checking access path:")
                                        logger.warning(
                                            f"         hasattr(self, 'app'): {hasattr(self, 'app')}"
                                        )
                                        if hasattr(self, "app"):
                                            logger.warning(f"         self.app: {self.app}")
                                            logger.warning(
                                                f"         hasattr(app, 'main_window'): {hasattr(self.app, 'main_window')}"
                                            )
                                            if hasattr(self.app, "main_window"):
                                                logger.warning(
                                                    f"                 main_window: {self.app.main_window}"
                                                )
                                                logger.warning(
                                                    f"                 hasattr(main_window, 'device_config'): {hasattr(self.app.main_window, 'device_config')}"
                                                )

                                    # Load into controller RAM
                                    if ctrl and hasattr(ctrl, "set_servo_positions"):
                                        ctrl.set_servo_positions(s=s_pos, p=p_pos)
                                        logger.info("   -> Controller RAM updated")

                                    # Also update hardware manager's device_config if accessible
                                    if (
                                        not synced_to_app
                                        and hasattr(self.app, "hardware_mgr")
                                        and hasattr(self.app.hardware_mgr, "device_config")
                                    ):
                                        logger.info(
                                            "   🔄 Syncing to hardware manager's DeviceConfiguration..."
                                        )
                                        if self.app.hardware_mgr.device_config:
                                            self.app.hardware_mgr.device_config.set_servo_positions(
                                                s_pos, p_pos
                                            )
                                            self.app.hardware_mgr.device_config.save()
                                            logger.info(
                                                "      ✅ Hardware manager config synced and saved"
                                            )
                                        else:
                                            logger.warning(
                                                "      ⚠️  Hardware manager device_config is None"
                                            )

                                    logger.info(
                                        "   Retrying LED calibration with correct positions..."
                                    )
                                    logger.info("=" * 80)

                                    # Retry LED calibration with correct servo positions
                                    self._progress_callback("Retrying LED calibration...", 40)
                                    cal_result = run_startup_calibration(
                                        usb=usb,
                                        ctrl=ctrl,
                                        device_type=device_type,
                                        device_config=device_config,
                                        detector_serial=device_serial,
                                        progress_callback=self._progress_callback,
                                        use_convergence_engine=True,
                                        force_oem_retrain=self._force_oem_retrain,
                                    )
                                else:
                                    raise RuntimeError(
                                        "Servo calibration completed but positions not saved"
                                    )
                            else:
                                raise RuntimeError("Servo calibration returned False - scan failed")

                        except Exception as servo_err:
                            logger.error(f"❌ Automatic servo calibration failed: {servo_err}")
                            error_msg = (
                                "Servo calibration failed.\n\n"
                                f"Error: {servo_err}\n\n"
                                "Please try manual servo calibration from Tools > Polarizer Calibration."
                            )
                            raise RuntimeError(error_msg)
                    else:
                        raise

            # Validate calibration result (common for both pump and no-pump paths)

            if not cal_result or not cal_result.success:
                error_msg = "Calibration failed"
                if cal_result:
                    if hasattr(cal_result, "error") and cal_result.error:
                        error_msg = cal_result.error
                    elif hasattr(cal_result, "error_message") and cal_result.error_message:
                        error_msg = cal_result.error_message
                raise RuntimeError(error_msg)

            # Convert calibration result to domain model
            self.calibration_progress.emit("Storing results...", 95)
            # This provides type safety, validation, and immutability
            logger.info("🔄 Converting calibration result to domain model...")
            try:
                calibration_data = led_calibration_result_to_domain(cal_result)
                logger.info("[OK] Calibration data converted to domain model")
                logger.info(f"   Channels: {list(calibration_data.s_pol_ref.keys())}")
                logger.info(
                    f"   Integration times: S={calibration_data.integration_time_s}ms, P={calibration_data.integration_time_p}ms",
                )
                logger.info(f"   P-mode LEDs: {calibration_data.p_mode_intensities}")
                logger.info(f"   S-mode LEDs: {calibration_data.s_mode_intensities}")
            except Exception as e:
                logger.error(f"[ERROR] Failed to convert calibration data: {e}")
                msg = f"Calibration data conversion failed: {e}"
                raise RuntimeError(msg)

            # Explicitly log timing sync metrics for QC visibility (prefer domain)
            try:
                ts = getattr(calibration_data, "timing_sync", None) or getattr(
                    cal_result,
                    "timing_sync",
                    None,
                )
                if ts:
                    logger.info(
                        f"⏱ Timing Sync: avg={ts.get('avg_cycle_ms', 0):.1f} ms, "
                        f"jitter={ts.get('jitter_ms', 0):.1f} ms, status={ts.get('status', 'unknown')}",
                    )
                else:
                    logger.info(
                        "⏱ Timing Sync: not measured (no timing_sync available)",
                    )
            except Exception as _e:
                logger.debug(f"(Timing sync log skipped: {_e})")

            # Domain model has built-in validation
            # Note: validate() method is from CalibrationData dataclass
            logger.info("[OK] Calibration data validated (domain model)")

            # Store calibration data
            self._current_calibration_data = calibration_data
            self._calibration_completed = True

            # Propagate wavelengths to data manager as a stable source-of-truth
            try:
                if hasattr(self.app, "data_mgr") and self.app.data_mgr is not None:
                    if getattr(calibration_data, "wavelengths", None) is not None:
                        self.app.data_mgr.wave_data = calibration_data.wavelengths
                        logger.info(
                            f"📡 Wavelengths propagated to data_mgr: {len(self.app.data_mgr.wave_data)} points",
                        )
            except Exception as _e:
                logger.debug(f"(Wavelength propagation skipped: {_e})")

            # Update sensor_ready status based on transmission QC
            sensor_ready = self._evaluate_sensor_ready(calibration_data)
            if sensor_ready:
                hardware_mgr._sensor_verified = True
                logger.info("[OK] SENSOR READY: Transmission QC passed")
            else:
                logger.warning("[WARN]  SENSOR NOT READY: Transmission QC did not pass")

            # Emit completion signal
            self.calibration_complete.emit(calibration_data)

            # Handle post-calibration UI - KEEP DIALOG OPEN and ENABLE START BUTTON
            if self._calibration_dialog:
                self._calibration_dialog.update_title("✅ Calibration Successful!")
                self._calibration_dialog.update_status(
                    "🎉 Your system is ready! Review the QC graphs below, then click Start when you're ready to begin live acquisition.",
                )
                self._calibration_dialog.set_progress(100, 100)
                self._calibration_dialog.enable_start_button()
                logger.info(
                    "[OK] Calibration dialog updated - Start button enabled for live data",
                )

            # Some builds may not include the UI hook; guard the call
            if hasattr(self, "_on_calibration_complete_ui"):
                self._on_calibration_complete_ui(calibration_data)

        except Exception as e:
            logger.error(f"[ERROR] Calibration failed: {e}", exc_info=True)
            self.calibration_failed.emit(str(e))

            if self._calibration_dialog:
                self._calibration_dialog.update_title("[ERROR] Calibration Failed")
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
                status = validation.get("status", "")
                if "[OK] PASS" in status:
                    passed_channels.append(ch)

            if passed_channels:
                logger.info(
                    f"Sensor ready: {len(passed_channels)}/{len(transmission_validation)} channels passed QC",
                )
                logger.info(f"   Passed channels: {passed_channels}")
                return True
            logger.warning("No channels passed transmission QC")
            return False

        except Exception as e:
            logger.error(f"Error evaluating sensor ready status: {e}")
            return False

    def get_current_calibration(self) -> CalibrationData | None:
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
            logger.info("\n📊 Model 1: Next Calibration Prediction")
            logger.info(
                f"   Failure Probability: {cal_pred.failure_probability * 100:.1f}%",
            )
            logger.info(f"   Risk Level: {cal_pred.risk_level.upper()}")
            if cal_pred.warnings:
                for warning in cal_pred.warnings:
                    logger.warning(f"   [WARN]  {warning}")
            if cal_pred.recommendations:
                for rec in cal_pred.recommendations:
                    logger.info(f"   💡 {rec}")

            # Model 2: LED Health Monitoring
            led_statuses = self._ml_intelligence.predict_led_health()
            logger.info("\n💡 Model 2: LED Health Status")
            for led in led_statuses:
                status_emoji = {
                    "excellent": "[OK]",
                    "good": "[OK]",
                    "degrading": "[WARN]",
                    "critical": "🚨",
                }.get(led.status, "❓")
                logger.info(
                    f"   {status_emoji} Ch {led.channel.upper()}: {led.status} (intensity={led.current_intensity}, trend={led.intensity_trend:+.1f}/cal)",
                )
                if led.replacement_recommended:
                    logger.warning("      🚨 REPLACEMENT RECOMMENDED")
                elif led.days_until_replacement and led.days_until_replacement < 30:
                    logger.warning(
                        f"      [WARN]  Estimated {led.days_until_replacement} days until replacement",
                    )

            # Model 3: Sensor Coating Degradation
            coating = self._ml_intelligence.predict_sensor_coating_life()
            logger.info("\n🔬 Model 3: Sensor Coating Status")
            logger.info(f"   Quality: {coating.coating_quality.upper()}")
            logger.info(f"   Current FWHM (avg): {coating.current_fwhm_avg:.1f} nm")
            logger.info(f"   Trend: {coating.fwhm_trend:+.2f} nm/calibration")
            if coating.estimated_experiments_remaining:
                logger.info(
                    f"   Estimated Lifespan: {coating.estimated_experiments_remaining} experiments",
                )
            if coating.replacement_warning:
                logger.warning(
                    "   [WARN]  REPLACEMENT WARNING: Sensor chip approaching end of life",
                )

            # Model 4: Optical Alignment (Baseline-based, Non-interfering)
            alignment = self._ml_intelligence.check_optical_alignment(calibration_data)
            logger.info("\n🔧 Model 4: Optical Alignment (Calibration Baseline)")
            logger.info(f"   P/S Ratio Baseline: {alignment.ps_ratio_baseline:.3f}")
            logger.info(f"   Deviation: {alignment.ps_ratio_deviation:.3f}")
            logger.info(f"   Confidence: {alignment.orientation_confidence * 100:.0f}%")
            if alignment.alignment_drift_detected:
                logger.warning(f"   🚨 DRIFT DETECTED: {alignment.warning_message}")
            elif alignment.maintenance_recommended:
                logger.warning(f"   [WARN]  {alignment.warning_message}")
            else:
                logger.info("   [OK] Alignment stable")

            logger.info("=" * 80)

            # Generate and save comprehensive report
            report = self._ml_intelligence.generate_intelligence_report()
            logger.debug(f"\n{report}")

        except Exception as e:
            logger.error(f"Failed to update ML QC intelligence: {e}", exc_info=True)

    def get_ml_intelligence(self) -> MLQCIntelligence | None:
        """Get ML QC intelligence instance.

        Returns:
            MLQCIntelligence instance if initialized, None otherwise

        """
        return self._ml_intelligence
