"""Device Configuration Manager - Handles device initialization and OEM calibration workflow.

Encapsulates device configuration, validation, OEM calibration workflow execution.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import threading

from dialogs import DeviceConfigDialog
from PySide6.QtWidgets import QDialog

from affilabs.utils.logger import logger


class DeviceConfigManager:
    """Manager for device configuration and OEM calibration workflow.

    Handles:
    - Device configuration initialization
    - Missing field validation
    - Device configuration dialog prompts
    - OEM calibration workflow execution (servo + LED calibration)
    - EEPROM synchronization
    """

    def __init__(self, main_window):
        """Initialize device config manager.

        Args:
            main_window: Main window reference with app and device_config

        """
        self.main_window = main_window
        self.device_config = None
        self.led_start_time = None
        self.last_powered_on = None
        self.oem_config_just_completed = False

    def initialize_device_config(self, device_serial: str | None = None):
        """Initialize device configuration for maintenance tracking.

        Args:
            device_serial: Spectrometer serial number for device-specific configuration.
                          If None, uses default config (not device-specific).

        """
        try:
            from affilabs.utils.device_configuration import DeviceConfiguration

            # Get controller reference for EEPROM operations and hardware detection
            controller = None
            if (
                hasattr(self.main_window, "app")
                and self.main_window.app
                and hasattr(self.main_window.app, "hardware_mgr")
            ):
                controller = (
                    self.main_window.app.hardware_mgr.ctrl
                    if self.main_window.app.hardware_mgr
                    else None
                )

            self.device_config = DeviceConfiguration(
                device_serial=device_serial,
                controller=controller,
            )
            self.main_window.device_config = self.device_config

            # Initialize tracking variables
            self.led_start_time = None
            self.last_powered_on = None

            # Check if config was created from scratch (not loaded from JSON or EEPROM)
            if self.device_config.created_from_scratch:
                logger.info("=" * 80)
                logger.info("📋 NEW DEVICE CONFIGURATION - Auto-Calibration Required")
                logger.info("=" * 80)
                logger.info(f"   Device Serial: {device_serial or 'Unknown'}")
                logger.info("   Config created with known info (serial, controller)")
                logger.info(
                    "   Missing calibration: Servo positions, LED intensities, SPR model",
                )
                logger.info("")
                logger.info("Automatic Workflow:")
                logger.info("   1. Run servo calibration (auto-detect S/P positions)")
                logger.info(
                    "   2. Run LED calibration (generate SPR model + intensities)",
                )
                logger.info(
                    "   3. Populate device_config.json (single source of truth)",
                )
                logger.info("   4. Save to JSON and EEPROM")
                logger.info("")
                logger.info(
                    "⚠️  No user input required - calibration runs automatically",
                )
                logger.info("=" * 80)

                # Mark that OEM calibration is needed
                self.oem_config_just_completed = False
                # Will be triggered automatically when hardware is ready
            else:
                logger.info("✓ Device configuration loaded successfully")
                if self.device_config.loaded_from_eeprom:
                    logger.info("  Source: EEPROM → JSON (auto-saved)")
                else:
                    logger.info("  Source: JSON file")

            # Update UI with current values
            if hasattr(self.main_window, "_update_maintenance_display"):
                self.main_window._update_maintenance_display()

            # Auto-load hardware settings into Settings sidebar
            if self.device_config:
                try:
                    s_pos, p_pos = self.device_config.get_servo_positions()
                    led_intensities = self.device_config.get_led_intensities()
                    self.main_window.sidebar.load_hardware_settings(
                        s_pos=s_pos,
                        p_pos=p_pos,
                        led_a=led_intensities.get("a", 0),
                        led_b=led_intensities.get("b", 0),
                        led_c=led_intensities.get("c", 0),
                        led_d=led_intensities.get("d", 0),
                    )
                    logger.info(
                        f"Auto-loaded hardware settings to sidebar: S={s_pos}, P={p_pos}",
                    )
                except Exception as e:
                    logger.warning(f"Could not auto-load hardware settings: {e}")

            if device_serial:
                logger.info(
                    f"Device configuration initialized for S/N: {device_serial}",
                )
            else:
                logger.info("Device configuration initialized with default config")
        except Exception as e:
            logger.error(f"Failed to initialize device configuration: {e}")
            self.device_config = None
            self.main_window.device_config = None

    def check_missing_config_fields(self):
        """Check for missing critical configuration fields.

        Returns:
            List of missing field names, empty if all fields are present

        """
        if not self.device_config:
            return []

        missing = []
        hw = self.device_config.config.get("hardware", {})

        # Check essential fields only
        if not hw.get("led_pcb_model"):
            missing.append("LED Model")

        if not hw.get("controller_type") and not hw.get("controller_model"):
            missing.append("Controller")

        if not hw.get("optical_fiber_diameter_um"):
            missing.append("Fiber Diameter")

        if not hw.get("polarizer_type"):
            missing.append("Polarizer")

        return missing

    def get_controller_type_from_hardware(self) -> str:
        """Get controller type from connected hardware.

        Returns:
            Controller type string: 'Arduino', 'PicoP4SPR', 'PicoEZSPR', or ''

        """
        try:
            if (
                hasattr(self.main_window, "hardware_mgr")
                and self.main_window.hardware_mgr
                and self.main_window.hardware_mgr.ctrl
            ):
                ctrl_name = getattr(
                    self.main_window.hardware_mgr.ctrl,
                    "device_name",
                    "",
                ).lower()
                if "arduino" in ctrl_name or ctrl_name == "p4spr":
                    return "Arduino"
                if "pico_p4spr" in ctrl_name or "picop4spr" in ctrl_name:
                    return "PicoP4SPR"
                if "pico_ezspr" in ctrl_name or "picoezspr" in ctrl_name:
                    return "PicoEZSPR"
        except Exception as e:
            logger.debug(f"Could not determine controller type: {e}")
        return ""

    def get_polarizer_type_for_controller(self, controller_type: str) -> str:
        """Determine polarizer type based on controller hardware rules.

        Hardware Rules:
        - Arduino P4SPR: Always 'round' (circular polarizer)
        - PicoP4SPR: Always 'round' (circular polarizer)
        - PicoEZSPR: Typically 'barrel' (2 fixed windows)

        Args:
            controller_type: Type of controller ('Arduino', 'PicoP4SPR', 'PicoEZSPR')

        Returns:
            'round' or 'barrel'

        """
        if controller_type in ["Arduino", "PicoP4SPR"]:
            return "round"  # Circular polarizer
        if controller_type == "PicoEZSPR":
            return "barrel"  # 2 fixed windows (S and P)
        return "barrel"  # Default fallback

    def prompt_device_config(self, device_serial: str):
        """Show dialog to collect missing device configuration.

        Args:
            device_serial: Device serial number

        """
        try:
            # Detect controller type from hardware
            controller_type = self.get_controller_type_from_hardware()

            # Get controller reference for EEPROM operations
            controller = None
            if hasattr(self.main_window, "hardware_mgr") and self.main_window.hardware_mgr:
                controller = self.main_window.hardware_mgr.ctrl

            # Create dialog with controller and device_config for EEPROM support
            dialog = DeviceConfigDialog(
                self.main_window,
                device_serial,
                controller_type,
                controller=controller,
                device_config=self.device_config,
            )

            # Pre-fill with existing values from config if available
            if self.device_config:
                hw = self.device_config.config.get("hardware", {})
                device_info = self.device_config.config.get("device_info", {})

                # Set LED model
                led_model = hw.get("led_pcb_model", "luminus_cool_white")
                if led_model == "luminus_cool_white":
                    dialog.led_model_combo.setCurrentText("LCW")
                elif led_model == "osram_warm_white":
                    dialog.led_model_combo.setCurrentText("OWW")

                # Set controller type
                ctrl_type = hw.get("controller_type", controller_type)
                if ctrl_type:
                    index = dialog.controller_combo.findText(ctrl_type)
                    if index >= 0:
                        dialog.controller_combo.setCurrentIndex(index)

                # Set fiber diameter
                fiber_diameter = hw.get("optical_fiber_diameter_um", 200)
                if fiber_diameter == 100:
                    dialog.fiber_diameter_combo.setCurrentText("A (100 µm)")
                else:
                    dialog.fiber_diameter_combo.setCurrentText("B (200 µm)")

                # Set polarizer type
                polarizer_type = hw.get("polarizer_type", "circle")
                index = dialog.polarizer_type_combo.findText(polarizer_type)
                if index >= 0:
                    dialog.polarizer_type_combo.setCurrentIndex(index)

                # Set device ID
                device_id = device_info.get("device_id", device_serial)
                if device_id:
                    dialog.device_id_input.setText(device_id)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Get configuration data
                config_data = dialog.get_config_data()

                # Update device configuration
                hw = self.device_config.config["hardware"]
                hw["led_pcb_model"] = config_data["led_pcb_model"]
                hw["optical_fiber_diameter_um"] = config_data["optical_fiber_diameter_um"]
                hw["polarizer_type"] = config_data["polarizer_type"]
                hw["controller_model"] = config_data.get(
                    "controller_model",
                    "Raspberry Pi Pico P4SPR",
                )
                hw["controller_type"] = config_data["controller_type"]

                if config_data["device_id"]:
                    self.device_config.config["device_info"]["device_id"] = config_data["device_id"]

                # Update LED type code based on model
                led_model = config_data["led_pcb_model"]
                if led_model == "luminus_cool_white":
                    hw["led_type_code"] = "LCW"
                elif led_model == "osram_warm_white":
                    hw["led_type_code"] = "OWW"

                # Save configuration
                self.device_config.save()

                logger.info("✅ Device configuration updated and saved")
                logger.info(f"  LED Model: {hw.get('led_pcb_model')}")
                logger.info(
                    f"  Controller: {hw.get('controller_type')} ({hw.get('controller_model')})",
                )
                logger.info(
                    f"  Fiber Diameter: {hw.get('optical_fiber_diameter_um')} µm",
                )
                logger.info(f"  Polarizer: {hw.get('polarizer_type')}")
                logger.info(
                    f"  Device ID: {self.device_config.config['device_info'].get('device_id', 'Not set')}",
                )
                logger.info(f"  Config file: {self.device_config.config_path}")

                # Verify it was actually saved
                missing_after_save = self.check_missing_config_fields()
                if missing_after_save:
                    logger.warning(
                        f"⚠️ After saving, still missing fields: {missing_after_save}",
                    )
                    from affilabs.widgets.message import show_message

                    show_message(
                        f"Configuration saved but some fields are still missing: {', '.join(missing_after_save)}",
                        "Configuration Warning",
                    )
                else:
                    logger.info("✅ All required fields are now present in config")
                    logger.info("💾 Saving device configuration to JSON...")

                    # Trigger OEM calibration workflow
                    logger.info("=" * 80)
                    logger.info(
                        "🏭 Device Configuration Complete - Starting Calibration Workflow",
                    )
                    logger.info("=" * 80)
                    logger.info(f"LED Model: {hw.get('led_pcb_model', 'N/A')}")
                    logger.info(f"Controller: {hw.get('controller_type', 'N/A')}")
                    logger.info(
                        f"Fiber: {hw.get('optical_fiber_diameter_um', 'N/A')} µm",
                    )
                    logger.info(f"Polarizer: {hw.get('polarizer_type', 'N/A')}")
                    logger.info("")
                    logger.info("Next Steps:")
                    logger.info("  1. Run servo calibration to find S/P positions")
                    logger.info("  2. Run LED calibration to find optimal intensities")
                    logger.info("  3. Push complete config to EEPROM")
                    logger.info("=" * 80)

                    self.oem_config_just_completed = True
                    self.start_oem_calibration_workflow()
            else:
                logger.warning("Device configuration dialog cancelled")
        except Exception as e:
            logger.error(f"Failed to prompt for device configuration: {e}")

    def start_oem_calibration_workflow(self):
        """Start OEM calibration workflow after device config is complete.

        Workflow:
        1. Run servo calibration to find optimal S/P positions
        2. Pull S/P positions from calibration result and update device_config
        3. Run LED calibration to find optimal intensities
        4. Pull LED intensities from data_mgr and update device_config
        5. Push complete config to EEPROM
        """
        logger.info("🏭 Starting OEM calibration workflow...")

        # Check if hardware is ready
        if not hasattr(self.main_window, "app") or not self.main_window.app:
            logger.error("Application not initialized")
            from affilabs.widgets.message import show_message

            show_message(
                "Cannot start calibration: Application not initialized",
                msg_type="Error",
                title="Calibration Error",
            )
            return

        hardware_mgr = self.main_window.app.hardware_mgr
        data_mgr = self.main_window.app.data_mgr

        # Check for controller
        if not hardware_mgr or not hardware_mgr.ctrl:
            logger.error("Controller not connected")
            from affilabs.widgets.message import show_message

            show_message(
                "Cannot start calibration:\n"
                "Controller must be connected.\n\n"
                "Please connect controller and try again.",
                msg_type="Warning",
                title="Hardware Not Ready",
            )
            return

        # Check for spectrometer
        if not hardware_mgr.detector:
            logger.warning("Spectrometer not connected - waiting for connection")
            from affilabs.widgets.message import show_message

            show_message(
                "Device configuration saved!\n\n"
                "Please connect the spectrometer to begin\n"
                "automatic calibration.\n\n"
                "Calibration will start automatically\n"
                "when the spectrometer is detected.",
                msg_type="Information",
                title="Connect Spectrometer",
            )
            return

        # Show initial message
        from affilabs.widgets.message import show_message

        show_message(
            "Starting servo calibration...\n\n"
            "This will automatically find optimal\n"
            "S and P polarizer positions.\n\n"
            "Please ensure water is on the sensor.\n"
            "This takes about 1-2 minutes.",
            msg_type="Information",
            title="Servo Calibration",
        )

        # Run workflow in background thread
        def oem_calibration_workflow():
            try:
                # Step 1: Run servo calibration
                logger.info("Running servo auto-calibration...")
                self.main_window.app._run_servo_auto_calibration()

                # Step 2: Verify servo positions
                s_pos = self.device_config.config["hardware"]["servo_s_position"]
                p_pos = self.device_config.config["hardware"]["servo_p_position"]

                if s_pos == 10 and p_pos == 100:
                    logger.warning("Servo positions not updated - using defaults")
                else:
                    logger.info(f"✓ Servo positions confirmed: S={s_pos}, P={p_pos}")

                # Step 3: Run LED calibration
                logger.info("Step 2/5: Running LED calibration...")
                show_message(
                    "Servo calibration complete!\n\n"
                    "Now starting LED intensity calibration...\n"
                    "This takes about 30-60 seconds.",
                    msg_type="Information",
                    title="LED Calibration",
                )

                self.main_window.app._on_simple_led_calibration()

                # Wait for completion
                if hasattr(hardware_mgr, "main_app") and hardware_mgr.main_app:
                    if hasattr(hardware_mgr.main_app, "calibration_thread"):
                        hardware_mgr.main_app.calibration_thread.join()
                        logger.info("LED calibration thread completed")

                # Step 4: Pull LED intensities and calibration data
                logger.info("Step 3/5: Updating calibration data in device config...")
                import time

                time.sleep(0.5)  # Reduced from 2s for faster hardware response

                if data_mgr and hasattr(data_mgr, "leds_calibrated") and data_mgr.leds_calibrated:
                    led_a = data_mgr.leds_calibrated.get("a", 0)
                    led_b = data_mgr.leds_calibrated.get("b", 0)
                    led_c = data_mgr.leds_calibrated.get("c", 0)
                    led_d = data_mgr.leds_calibrated.get("d", 0)

                    if any([led_a, led_b, led_c, led_d]):
                        # Save LED intensities
                        self.device_config.config["calibration"]["led_intensity_a"] = led_a
                        self.device_config.config["calibration"]["led_intensity_b"] = led_b
                        self.device_config.config["calibration"]["led_intensity_c"] = led_c
                        self.device_config.config["calibration"]["led_intensity_d"] = led_d
                        self.device_config.config["calibration"]["factory_calibrated"] = True
                        logger.info(
                            f"✓ LED intensities saved: A={led_a}, B={led_b}, C={led_c}, D={led_d}",
                        )

                        # Save integration time and num_scans if available
                        if (
                            hasattr(data_mgr, "integration_time_ms")
                            and data_mgr.integration_time_ms
                        ):
                            self.device_config.set_integration_time(
                                data_mgr.integration_time_ms,
                            )
                            logger.info(
                                f"✓ Integration time saved: {data_mgr.integration_time_ms} ms",
                            )

                        if hasattr(data_mgr, "num_scans") and data_mgr.num_scans:
                            self.device_config.set_num_scans(data_mgr.num_scans)
                            logger.info(
                                f"✓ Number of scans saved: {data_mgr.num_scans}",
                            )

                        # Save SPR model path
                        if device_serial:
                            from pathlib import Path

                            spr_model_path = Path(
                                f"OpticalSystem_QC/{device_serial}/spr_calibration/led_calibration_spr_processed_latest.json",
                            )
                            if spr_model_path.exists():
                                self.device_config.set_spr_model_path(
                                    str(spr_model_path),
                                )
                                logger.info(f"✓ SPR model path saved: {spr_model_path}")
                            else:
                                logger.warning(
                                    f"SPR model not found at expected location: {spr_model_path}",
                                )

                        self.device_config.save()
                        logger.info(
                            "✓ All calibration data saved to device_config.json",
                        )
                    else:
                        logger.warning(
                            "LED intensities are all zero - calibration may have failed",
                        )
                else:
                    logger.warning("Failed to read LED intensities from data_mgr")

                # Step 5: Push to EEPROM
                logger.info("Step 4/5: Pushing complete config to EEPROM...")
                if self.device_config.sync_to_eeprom(hardware_mgr.ctrl):
                    logger.info("=" * 80)
                    logger.info("✅ OEM CALIBRATION WORKFLOW COMPLETE!")
                    logger.info("=" * 80)
                    logger.info("   SINGLE SOURCE OF TRUTH CREATED")
                    logger.info(f"   Config file: {self.device_config.config_path}")
                    logger.info("")
                    logger.info("   Servo Positions:")
                    logger.info(f"     • S position: {s_pos}°")
                    logger.info(f"     • P position: {p_pos}°")
                    logger.info("")
                    logger.info("   LED Intensities:")
                    logger.info(
                        f"     • Channel A: {self.device_config.config['calibration']['led_intensity_a']}",
                    )
                    logger.info(
                        f"     • Channel B: {self.device_config.config['calibration']['led_intensity_b']}",
                    )
                    logger.info(
                        f"     • Channel C: {self.device_config.config['calibration']['led_intensity_c']}",
                    )
                    logger.info(
                        f"     • Channel D: {self.device_config.config['calibration']['led_intensity_d']}",
                    )
                    logger.info("")
                    logger.info("   Integration Settings:")
                    int_time = self.device_config.get_integration_time()
                    num_scans = self.device_config.get_num_scans()
                    logger.info(
                        f"     • Integration time: {int_time if int_time else 'Not set'} ms",
                    )
                    logger.info(
                        f"     • Number of scans: {num_scans if num_scans else 'Not set'}",
                    )
                    logger.info("")
                    logger.info("   SPR Model:")
                    spr_path = self.device_config.get_spr_model_path()
                    if spr_path:
                        logger.info(f"     • Path: {Path(spr_path).name}")
                    else:
                        logger.info("     • Not generated yet")
                    logger.info("")
                    logger.info("   Storage Locations:")
                    logger.info(
                        f"     • JSON (Primary): {self.device_config.config_path}",
                    )
                    logger.info("     • EEPROM (Backup): Controller memory")
                    logger.info("=" * 80)

                    show_message(
                        "✅ OEM Calibration Complete!\n\n"
                        "All calibrations finished successfully:\n"
                        f"• Servo S: {s_pos}°\n"
                        f"• Servo P: {p_pos}°\n"
                        f"• LED A: {self.device_config.config['calibration']['led_intensity_a']}\n"
                        f"• LED B: {self.device_config.config['calibration']['led_intensity_b']}\n"
                        f"• LED C: {self.device_config.config['calibration']['led_intensity_c']}\n"
                        f"• LED D: {self.device_config.config['calibration']['led_intensity_d']}\n\n"
                        "Configuration saved to JSON and EEPROM.\n"
                        "Device is ready for use!",
                        msg_type="Information",
                        title="Calibration Success",
                    )
                else:
                    logger.error("Failed to push config to EEPROM")
                    show_message(
                        "Calibration completed but EEPROM sync failed.\n\n"
                        "Configuration is saved to JSON file only.",
                        msg_type="Warning",
                        title="EEPROM Sync Failed",
                    )
            except Exception as e:
                logger.error(f"OEM calibration workflow failed: {e}")
                logger.exception("Full traceback:")
                show_message(
                    f"Calibration workflow failed:\n{e!s}",
                    msg_type="Error",
                    title="Calibration Error",
                )

        # Start workflow in background thread
        if hasattr(self.main_window.app, "_run_servo_auto_calibration"):
            workflow_thread = threading.Thread(
                target=oem_calibration_workflow,
                daemon=True,
            )
            workflow_thread.start()
        else:
            logger.error("Servo calibration method not found in application")
