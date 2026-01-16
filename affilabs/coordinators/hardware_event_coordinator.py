"""Hardware Event Coordinator - Handles hardware connection lifecycle events.

This coordinator manages all hardware-related events including:
- Hardware connection and disconnection
- Hardware scanning
- LED status monitoring
- Connection progress updates
- Hardware error handling

Architecture Alignment:
- Layer 3: Coordinator (orchestration between hardware and UI)
- Depends on: HardwareManager (Layer 1), MainWindow (Layer 4)
- No business logic - pure event coordination
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer

from affilabs.ui.ui_message import error as ui_error
from affilabs.ui.ui_message import info as ui_info
from affilabs.utils.logger import logger
from affilabs.utils.time_utils import monotonic

if TYPE_CHECKING:
    from affilabs.affilabs_core_ui import AffilabsMainWindow
    from affilabs.core.hardware_manager import HardwareManager


class HardwareEventCoordinator:
    """Coordinates hardware connection lifecycle events.

    Responsibilities:
    -----------------
    - Handle hardware connection/disconnection events
    - Manage LED status monitoring timer
    - Update device status UI
    - Validate hardware combinations
    - Trigger calibration workflow on connection
    - Handle hardware errors and connection progress

    Architecture:
    -------------
    - Pure coordinator - no business logic
    - Bridges hardware events to UI updates
    - Manages lifecycle timers (LED monitoring)
    """

    def __init__(
        self,
        hardware_mgr: HardwareManager,
        main_window: AffilabsMainWindow,
        app,
    ):
        """Initialize hardware event coordinator.

        Args:
            hardware_mgr: Hardware manager instance
            main_window: Main window instance
            app: Application instance (for callbacks to other coordinators)
        """
        self._hardware_mgr = hardware_mgr
        self._main_window = main_window
        self._app = app

        # LED status monitoring timer
        self._led_status_timer = None

        # Tracking flags
        self._last_hw_callback_time = 0

    def on_scan_requested(self):
        """User clicked Scan button in UI."""
        logger.info("User requested hardware scan")
        self._hardware_mgr.scan_and_connect()

    def on_hardware_connected(self, status: dict):
        """Hardware connection completed and update Device Status UI."""
        # Deduplicate rapid-fire signals (prevent double-processing within 500ms)
        current_time = monotonic()
        time_since_last = current_time - self._last_hw_callback_time
        if time_since_last < 0.5:  # Less than 500ms since last callback
            logger.debug(
                f"Skipping duplicate hardware callback ({time_since_last * 1000:.0f}ms since last)",
            )
            return
        self._last_hw_callback_time = current_time

        logger.debug("Hardware connection callback received")
        logger.debug(f"   Status: {status}")

        # Reset scan button state in UI
        self._main_window._on_hardware_scan_complete()

        # Validate hardware combinations
        valid_hardware = self._validate_hardware_combinations(status)

        # Update power button based on valid hardware combinations
        if valid_hardware:
            logger.info(
                f"[OK] Scan SUCCESSFUL - found valid hardware: {', '.join(valid_hardware)}",
            )
            self._main_window.set_power_state("connected")
        else:
            logger.warning(
                "Scan FAILED - no valid hardware combinations found",
            )
            self._main_window.set_power_state("disconnected")
            self._handle_scan_failure(status)
            return  # Exit early if scan failed

        # Handle device initialization
        device_serial = status.get("spectrometer_serial")
        if device_serial and not self._app._device_config_initialized:
            self._initialize_device_config(status, device_serial)
        elif not device_serial and status.get("ctrl_type"):
            self._handle_new_oem_device(status)

        # Update device status UI
        logger.debug(
            f"Calling _update_device_status_ui with optics_ready={status.get('optics_ready')}, sensor_ready={status.get('sensor_ready')}",
        )
        self._app._update_device_status_ui(status)

        # Start LED status monitoring timer
        if not self._app._device_config_initialized:
            self.start_led_status_monitoring()

        # Load device settings
        if not self._app._device_config_initialized:
            self._app._load_device_settings()

        # Check for bilinear model
        if not self._app._device_config_initialized and device_serial:
            if not self._check_bilinear_model(device_serial):
                return  # Exit early - redirecting to OEM calibration

        # Handle OEM config completion
        if self._main_window.oem_config_just_completed and status.get("spectrometer"):
            self._handle_oem_config_complete()

        # Update calibration dialog if waiting
        self._update_calibration_dialog(status)

        # Start calibration on initial connection
        if not self._app._initial_connection_done:
            self._handle_initial_connection(status)

    def on_hardware_disconnected(self):
        """Hardware disconnected."""
        # Check if this was an intentional disconnect
        was_intentional = self._app._intentional_disconnect
        if was_intentional:
            logger.info("Hardware disconnected (user-initiated)")
            self._app._intentional_disconnect = False
        else:
            logger.error("=" * 80)
            logger.error("CRITICAL: HARDWARE DISCONNECTED")
            logger.error("=" * 80)

        # Check if acquisition was running
        acquisition_was_running = (
            self._app.data_mgr._acquiring
            if hasattr(self._app.data_mgr, "_acquiring")
            else False
        )

        # Stop acquisition if running
        if acquisition_was_running:
            logger.info("Stopping acquisition (hardware disconnected gracefully)...")
            try:
                self._app.data_mgr.stop_acquisition()
            except Exception as e:
                logger.error(f"Error stopping acquisition: {e}")

        # Stop LED status monitoring
        self.stop_led_status_monitoring()

        # Reset calibration flags
        self._app._calibration_completed = False
        self._app._initial_connection_done = False

        # Update power button
        self._main_window.set_power_state("disconnected")

        # Clear hardware status UI
        empty_status = {
            "ctrl_type": None,
            "knx_type": None,
            "pump_connected": False,
            "spectrometer": False,
            "sensor_ready": False,
            "optics_ready": False,
            "fluidics_ready": False,
        }
        self._main_window.update_hardware_status(empty_status)

        # Show error dialog only if NOT user-initiated
        if acquisition_was_running and not was_intentional:
            ui_error(
                self._main_window,
                "Device Disconnected",
                "<b>Hardware has been disconnected during acquisition!</b><br><br>"
                "Acquisition has been stopped.<br><br>"
                "Please check:<br>"
                "• USB cable connections<br>"
                "• USB port stability<br>"
                "• Device power<br><br>"
                "Click 'Scan' to reconnect devices.",
            )

    def on_connection_progress(self, message: str):
        """Hardware connection progress update."""
        logger.info(f"Connection: {message}")

    def on_hardware_error(self, error: str):
        """Hardware error occurred."""
        logger.error(f"Hardware error: {error}")
        ui_error(
            self._main_window,
            "Hardware Error",
            f"A hardware error occurred:\n\n{error}\n\n"
            "Please check device connections and try again.",
        )

    def start_led_status_monitoring(self):
        """Start periodic LED status monitoring timer (V1.1+ firmware)."""
        if self._led_status_timer is not None:
            return  # Already running

        # Check if hardware supports LED queries
        if not self._hardware_mgr or not self._hardware_mgr.ctrl:
            return

        if not hasattr(self._hardware_mgr.ctrl, "get_all_led_intensities"):
            logger.debug("LED status monitoring not available (firmware < V1.1)")
            return

        self._led_status_timer = QTimer()
        self._led_status_timer.timeout.connect(self._update_led_status_display)
        self._led_status_timer.start(2000)  # Update every 2 seconds
        logger.info("[OK] LED status monitoring started (2s interval)")

    def stop_led_status_monitoring(self):
        """Stop LED status monitoring timer."""
        if self._led_status_timer is not None:
            self._led_status_timer.stop()
            self._led_status_timer.deleteLater()
            self._led_status_timer = None
            logger.info("LED status monitoring stopped")

    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================

    def _validate_hardware_combinations(self, status: dict) -> list[str]:
        """Validate hardware combinations and return list of valid hardware.

        Valid combinations:
        - P4SPR/P4PRO/ezSPR: controller + detector (BOTH required)
        - KNX: standalone kinetic controller
        - AffiPump: standalone pump
        """
        ctrl_type = status.get("ctrl_type")
        knx_type = status.get("knx_type")
        pump_connected = status.get("pump_connected")
        has_detector = status.get("spectrometer") is True

        valid_hardware = []
        if ctrl_type and has_detector:  # SPR device requires BOTH
            valid_hardware.append(ctrl_type)
        if knx_type:  # Kinetic controller (standalone)
            valid_hardware.append(knx_type)
        if pump_connected:  # Pump (standalone)
            valid_hardware.append("AffiPump")

        return valid_hardware

    def _handle_scan_failure(self, status: dict):
        """Handle scan failure - no valid hardware found."""
        # Clear Device Status UI
        empty_status = {
            "ctrl_type": None,
            "knx_type": None,
            "pump_connected": False,
            "spectrometer": False,
            "sensor_ready": False,
            "optics_ready": False,
            "fluidics_ready": False,
        }
        self._app._update_device_status_ui(empty_status)

        # Build detailed message about what was found vs what's missing
        ctrl_type = status.get("ctrl_type")
        has_detector = status.get("spectrometer") is True
        has_pump = status.get("pump_connected") is True

        # Build found/missing lists
        found = []
        missing = []

        if ctrl_type:
            found.append(f"✓ Controller ({ctrl_type})")
        else:
            missing.append("✗ Controller (Pico P4PRO/EZSPR)")

        if has_detector:
            detector_serial = status.get("spectrometer_serial", "unknown")
            found.append(f"✓ Detector (S/N: {detector_serial})")
        else:
            missing.append("✗ Detector (USB4000 or PhasePhotonics)")

        if has_pump:
            found.append("✓ Pump (AffiPump)")
        else:
            missing.append("✗ Pump (optional)")

        # Build error message
        error_msg = "Hardware scan incomplete.\n\n"

        if found:
            error_msg += "FOUND:\n" + "\n".join(found) + "\n\n"

        if missing:
            error_msg += "MISSING:\n" + "\n".join(missing) + "\n\n"

        error_msg += "REQUIRED: Controller + Detector\n\n"
        error_msg += "TO FIX:\n"
        
        if not ctrl_type:
            error_msg += "• Plug in Pico controller (USB)\n"
        if not has_detector:
            error_msg += "• Plug in USB4000/PhasePhotonics spectrometer\n"
        
        error_msg += "• Wait 5 seconds for Windows to detect\n"
        error_msg += "• Press Power button to scan again"

        from affilabs.widgets.message import show_message
        show_message(error_msg, msg_type="Warning", title="Hardware Scan Failed")

    def _initialize_device_config(self, status: dict, device_serial: str):
        """Initialize device configuration for newly connected device."""
        logger.info(f"Re-initializing device configuration for S/N: {device_serial}")

        # Initialize device-specific directory and configuration
        from affilabs.utils.device_integration import initialize_device_on_connection

        # Create mock USB device object with serial number
        class MockUSBDevice:
            def __init__(self, serial):
                self.serial_number = serial

        mock_usb = MockUSBDevice(device_serial)
        device_dir = initialize_device_on_connection(mock_usb)

        if device_dir:
            logger.info(f"[OK] Device initialized: {device_dir}")

        # Initialize device config and prompt for missing fields
        self._main_window._init_device_config(device_serial=device_serial)

        # Check for and apply special case if detector is in registry
        special_case_info = status.get("special_case")
        if special_case_info and special_case_info.get("has_overrides"):
            logger.info("=" * 60)
            logger.info("APPLYING SPECIAL CASE CONFIGURATION")
            logger.info(f"   Detector S/N: {special_case_info['detector_serial']}")
            logger.info(f"   Description: {special_case_info['description']}")
            logger.info("=" * 60)

            # Get special case and apply to device config
            special_case = self._hardware_mgr.get_special_case()
            if special_case:
                from affilabs.utils.device_special_cases import apply_special_case

                self._main_window.device_config = apply_special_case(
                    special_case,
                    self._main_window.device_config,
                )
                logger.info("[OK] Special case configuration applied to device")

        # Mark as initialized
        self._app._device_config_initialized = True
        self._main_window.update_last_power_on()

    def _handle_new_oem_device(self, status: dict):
        """Handle new OEM device that needs provisioning."""
        logger.warning("No spectrometer serial in hardware status")

        if status.get("ctrl_type"):
            logger.info("=" * 80)
            logger.info("NEW DEVICE DETECTED - OEM Provisioning Required")
            logger.info("=" * 80)
            logger.info(f"   Controller: {status.get('ctrl_type')}")
            logger.info("   Spectrometer: NOT CONNECTED")
            logger.info("")
            logger.info("Starting OEM device configuration workflow:")
            logger.info("   1. Collect device info (LED model, fiber diameter, etc.)")
            logger.info("   2. Connect spectrometer")
            logger.info("   3. Auto-calibrate servo positions")
            logger.info("   4. Calculate afterglow correction")
            logger.info("   5. Calibrate LED intensities")
            logger.info("=" * 80)

            # Initialize device config with default/placeholder serial
            self._main_window._init_device_config(device_serial=None)

            # Show message to user
            ui_info(
                self._main_window,
                "OEM Device Provisioning",
                "New Device Detected!\n\n"
                f"Controller: {status.get('ctrl_type')}\n"
                f"Spectrometer: NOT CONNECTED\n\n"
                "Please complete device configuration,\n"
                "then connect the spectrometer to begin\n"
                "automatic calibration.",
            )
        else:
            logger.warning("Using default config")
            self._main_window._init_device_config(device_serial=None)

    def _check_bilinear_model(self, device_serial: str) -> bool:
        """Check if bilinear model exists and is valid.

        Returns:
            True if model exists and is valid, False otherwise
        """
        logger.info("=" * 80)
        logger.info("CHECKING FOR BILINEAR MODEL...")
        logger.info("=" * 80)

        model_exists = False
        try:
            from affilabs.services.led_model_loader import (
                LEDCalibrationModelLoader,
                ModelNotFoundError,
            )

            model = LEDCalibrationModelLoader()
            model.load_model(device_serial)

            # Verify model has all required parameters
            model_info = model.get_model_info()
            r2_scores = model_info.get("r2_scores", {})

            # Check if all channels have valid R² scores
            required_channels = ["A", "B", "C", "D"]
            all_channels_valid = all(
                ch in r2_scores and "S" in r2_scores[ch] and r2_scores[ch]["S"] > 0.5
                for ch in required_channels
            )

            if all_channels_valid:
                model_exists = True
                logger.info(f"Valid bilinear model found for detector {device_serial}")
                logger.info(
                    f"  Model timestamp: {model_info.get('timestamp', 'Unknown')}"
                )
                logger.info(f"  R² scores: {r2_scores}")
            else:
                logger.warning("Model exists but has invalid/missing parameters")

        except ModelNotFoundError as e:
            logger.warning(f"No bilinear model found: {e}")
        except Exception as e:
            logger.warning(f"Model check failed: {e}")

        if not model_exists:
            logger.warning("=" * 80)
            logger.warning("NO VALID MODEL → STARTING OEM MODEL TRAINING")
            logger.warning("=" * 80)

            from affilabs.widgets.message import show_message

            show_message(
                "No Calibration Model Found!\n\n"
                f"Detector: {device_serial}\n\n"
                "This device requires OEM model training before use.\n"
                "The automatic model training workflow will now start.\n\n"
                "This process will:\n"
                "  1. Measure LED response at multiple integration times\n"
                "  2. Generate 3-stage linear calibration model\n"
                "  3. Save model for future calibrations\n"
                "  4. Automatically start regular calibration\n\n"
                "This takes approximately 2-3 minutes.",
                title="Model Training Required",
                msg_type="Warning",
            )

            # Start OEM model training workflow (automatically proceeds to calibration)
            QTimer.singleShot(500, self._start_oem_model_training)
            return False

        logger.info("=" * 80)
        return True

    def _start_oem_model_training(self):
        """Start OEM model training workflow for new device without calibration model.

        This workflow:
        1. Shows progress dialog
        2. Runs LED model training (3-stage linear calibration)
        3. Saves model to led_calibration_official/spr_calibration/data/
        4. Automatically starts regular 6-step calibration after model is created
        """
        logger.info("=" * 80)
        logger.info("STARTING OEM MODEL TRAINING WORKFLOW")
        logger.info("=" * 80)

        from affilabs_core_ui import StartupCalibProgressDialog

        # Show progress dialog
        training_dialog = StartupCalibProgressDialog(
            parent=self._app.main_window,
            title="OEM Model Training",
            message=(
                "Training LED calibration model for new device...\n\n"
                "This process will:\n"
                "  1. Measure LED response at 10ms, 20ms, 30ms\n"
                "  2. Fit 3-stage linear models\n"
                "  3. Save model for future use\n"
                "  4. Automatically start system calibration\n\n"
                "Please wait 2-3 minutes..."
            ),
            show_start_button=False,
        )
        training_dialog.show()
        training_dialog.show_progress_bar()

        # Run training in background thread
        import threading

        def training_workflow():
            try:
                from affilabs.core.oem_model_training import (
                    run_oem_model_training_workflow,
                )

                # Progress callback to update dialog
                def update_progress(message: str, percent: int):
                    training_dialog.update_status(message)
                    training_dialog.set_progress(percent, 100)

                # Run training
                success = run_oem_model_training_workflow(
                    hardware_mgr=self._hardware_mgr,
                    progress_callback=update_progress,
                )

                if success:
                    logger.info("=" * 80)
                    logger.info("✅ OEM MODEL TRAINING COMPLETE")
                    logger.info("=" * 80)
                    logger.info("Starting regular calibration workflow...")

                    # Close training dialog
                    training_dialog.close()

                    # Start regular calibration (now model exists)
                    QTimer.singleShot(500, self._app._on_oem_led_calibration)
                else:
                    logger.error("❌ Model training failed")
                    training_dialog.update_status(
                        "Model training failed!\n\nPlease check logs and try again."
                    )
                    QTimer.singleShot(3000, training_dialog.close)

            except Exception as e:
                logger.error(f"❌ Model training workflow failed: {e}")
                logger.exception("Full traceback:")
                training_dialog.update_status(
                    f"Model training error:\n{e}\n\nPlease check logs."
                )
                QTimer.singleShot(3000, training_dialog.close)

        # Start training thread
        training_thread = threading.Thread(
            target=training_workflow,
            daemon=True,
            name="OEMModelTraining",
        )
        training_thread.start()

    def _handle_oem_config_complete(self):
        """Handle OEM config completion + spectrometer connection."""
        logger.info("=" * 80)
        logger.info(
            "OEM Config Complete + Spectrometer Connected → Auto-Starting Calibration"
        )
        logger.info("=" * 80)
        self._main_window.oem_config_just_completed = False

        if hasattr(self._main_window, "_start_oem_calibration_workflow"):
            self._main_window._start_oem_calibration_workflow()
        else:
            logger.error("_start_oem_calibration_workflow method not found")

    def _update_calibration_dialog(self, status: dict):
        """Update calibration dialog if it exists and is waiting."""
        calibration_dialog = (
            self._app.calibration.dialog if self._app.calibration else None
        )
        if not calibration_dialog or calibration_dialog._is_closing:
            return

        ctrl_type = status.get("ctrl_type")
        has_spectrometer = status.get("spectrometer")

        if ctrl_type and has_spectrometer:
            logger.info("Calibration dialog updated: Hardware detected")
            calibration_dialog.update_status(
                "Hardware detected:\n"
                f"• Controller: {ctrl_type}\n"
                "• Spectrometer: Connected\n\n"
                "Click Start to begin calibration."
            )
        elif has_spectrometer and not ctrl_type:
            logger.warning("Spectrometer found but controller missing")
            calibration_dialog.update_status(
                "Controller not detected\n\n"
                "Please connect the SPR controller\n"
                "to continue calibration."
            )
        elif ctrl_type and not has_spectrometer:
            logger.warning("Controller found but spectrometer missing")
            calibration_dialog.update_status(
                "Spectrometer not detected\n\n"
                "Please connect the spectrometer\n"
                "to continue calibration."
            )

    def _handle_initial_connection(self, status: dict):
        """Handle initial hardware connection and start calibration."""
        self._app._initial_connection_done = True
        self._app._calibration_completed = False
        logger.debug("New hardware connection - calibration flag reset")

        # Start calibration ONLY if BOTH controller and spectrometer connected
        if not status.get("ctrl_type") or not status.get("spectrometer"):
            if status.get("spectrometer") and not status.get("ctrl_type"):
                logger.warning("Spectrometer detected but no controller found")
                logger.info("Controller is required for calibration")
            elif status.get("ctrl_type") and not status.get("spectrometer"):
                logger.warning("Controller detected but no spectrometer found")
                logger.info("Spectrometer is required for calibration")
            return

        if self._app._calibration_completed:
            logger.info("[OK] Calibration already completed - ready for live data")
            return

        logger.info("=" * 80)
        logger.info("HARDWARE CONNECTION SUCCESSFUL")
        logger.info("=" * 80)
        logger.info("   Hardware Detected:")
        logger.info(f"     Controller: {status.get('ctrl_type')}")
        logger.info("     Spectrometer: Connected")
        logger.info("")
        logger.info("✅ Hardware ready!")
        logger.info("   Showing calibration dialog...")
        logger.info("=" * 80)

        # Show calibration dialog with Start button (user must click to begin)
        self._app.calibration.start_calibration()

    def _update_led_status_display(self):
        """Query hardware for LED intensities and update UI display."""
        try:
            if not self._hardware_mgr or not self._hardware_mgr.ctrl:
                return

            # SKIP LED queries during acquisition - they interfere with CYCLE_SYNC
            if (
                hasattr(self._hardware_mgr, "data_acq_mgr")
                and self._hardware_mgr.data_acq_mgr
            ):
                if hasattr(self._hardware_mgr.data_acq_mgr, "_rankbatch_running"):
                    if self._hardware_mgr.data_acq_mgr._rankbatch_running:
                        logger.debug("Skipping LED query - rankbatch active")
                        return

            # Also skip if acquisition is running
            if hasattr(self._app, "_acquisition_running") and self._app._acquisition_running:
                return

            # Get current LED intensities from hardware (HAL method)
            led_intensities = self._hardware_mgr.ctrl.get_all_led_intensities() if self._hardware_mgr.ctrl else None

            if led_intensities:
                # Update device status widget
                if hasattr(self._main_window, "sidebar"):
                    if hasattr(self._main_window.sidebar, "device_widget"):
                        if hasattr(
                            self._main_window.sidebar.device_widget,
                            "device_status_widget",
                        ):
                            self._main_window.sidebar.device_widget.device_status_widget.update_led_status(
                                led_intensities
                            )

        except Exception as e:
            # Silent fail - don't disrupt normal operation
            logger.debug(f"LED status update failed: {e}")
