"""Settings and Calibration Helper Utilities.

Provides helper functions for:
- Device settings loading (servo positions, LED intensities)
- Calibration completion handling
- EEPROM synchronization
- QC report generation

These are utility functions extracted from the main Application class.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from affilabs.utils.logger import logger

if TYPE_CHECKING:
    from main_simplified import Application  # type: ignore[import-not-found]


class SettingsHelpers:
    """Settings and calibration utility functions.

    Static methods for device configuration and calibration handling.
    """

    @staticmethod
    def load_device_settings(app: Application) -> None:
        """Load servo positions from device config file and populate UI.

        The device config file is provided by OEM with factory-calibrated servo positions.
        This replaces reading from EEPROM since the config file is the source of truth.

        If S/P positions are missing or invalid (default values 10/100), automatically
        triggers servo calibration to find optimal positions.

        Args:
            app: Application instance

        """
        if not app.hardware_mgr or not app.hardware_mgr.ctrl:
            print("Cannot load settings - hardware not connected")
            return

        try:
            print("⚙️ Loading servo positions from device config file...")

            # Load servo positions from device config file (not EEPROM)
            if app.main_window.device_config:
                servo_positions = app.main_window.device_config.get_servo_positions()
                s_pos = servo_positions["s"]
                p_pos = servo_positions["p"]

                # Check if positions are absent or still at default values
                # Default values (10/100) indicate servo calibration hasn't been run
                if s_pos == 10 and p_pos == 100:
                    print("=" * 80)
                    print("   SERVO POSITIONS AT DEFAULT VALUES")
                    print("=" * 80)
                    print("   S=10, P=100 are uncalibrated defaults")
                    print("   Auto-triggering servo calibration...")
                    print("=" * 80)

                    # Trigger auto-calibration
                    app._run_servo_auto_calibration()
                    return  # Exit - calibration will update positions when complete

                # Update UI inputs with loaded values
                app.main_window.s_position_input.setText(str(s_pos))
                app.main_window.p_position_input.setText(str(p_pos))

                # ========================================================================
                # CRITICAL: WRITE DEVICE CONFIG POSITIONS TO CONTROLLER EEPROM
                # ========================================================================
                # Servo positions are IMMUTABLE and come from device_config ONLY
                # We write them to controller EEPROM at startup to ensure single source of truth
                # Controller firmware loads positions from EEPROM at boot
                # ========================================================================
                print("=" * 80)
                print("CRITICAL: Syncing servo positions to controller EEPROM")
                print("=" * 80)
                print(f"   Device Config: S={s_pos}, P={p_pos}")
                print("   Action: Writing to controller EEPROM...")

                try:
                    # Read current EEPROM config (use raw controller for EEPROM methods)
                    eeprom_config = app.hardware_mgr._ctrl_raw.read_config_from_eeprom()

                    if eeprom_config:
                        # Check if EEPROM positions match device_config
                        eeprom_s = eeprom_config.get("servo_s_position")
                        eeprom_p = eeprom_config.get("servo_p_position")

                        print(f"   Current EEPROM: S={eeprom_s}, P={eeprom_p}")

                        if eeprom_s != s_pos or eeprom_p != p_pos:
                            print("EEPROM MISMATCH DETECTED!")
                            print(f"   Device Config: S={s_pos}, P={p_pos}")
                            print(f"   EEPROM:        S={eeprom_s}, P={eeprom_p}")
                            print("   Updating EEPROM to match device_config...")

                            # Update EEPROM with device_config positions
                            eeprom_config["servo_s_position"] = s_pos
                            eeprom_config["servo_p_position"] = p_pos

                            # Use raw controller for EEPROM write
                            if app.hardware_mgr._ctrl_raw.write_config_to_eeprom(
                                eeprom_config
                            ):
                                print("[OK] EEPROM updated successfully")
                                print("Power cycle controller to apply new positions")
                                print("")
                                print("=" * 80)
                                print("CRITICAL: CONTROLLER NEEDS POWER CYCLE")
                                print("=" * 80)
                                print(
                                    "The controller firmware caches EEPROM positions at boot."
                                )
                                print(
                                    "New positions have been written but firmware is still using old values."
                                )
                                print("")
                                print("TO FIX:")
                                print("1. Close this application")
                                print("2. Unplug the controller USB cable")
                                print("3. Wait 5 seconds")
                                print("4. Plug the USB cable back in")
                                print("5. Restart this application")
                                print("=" * 80)
                                print("")
                            else:
                                print("[X] EEPROM write failed!")
                                print("   DANGER: Controller may use wrong positions!")
                        else:
                            print(
                                "[OK] EEPROM matches device_config - no update needed"
                            )
                    else:
                        print("   Could not read EEPROM config")
                        print("   Cannot verify position sync")

                except Exception as e:
                    print(f"[X] EEPROM sync failed: {e}")
                    print("   DANGER: Controller positions may not match device_config!")

                print("=" * 80)
                print(
                    f"  Servo positions: S={s_pos}°, P={p_pos}° (IMMUTABLE - loaded at init)"
                )
                print("=" * 80)
            else:
                print(" Device config not available - cannot load servo positions")

            # Load LED intensities from device config (for fast startup)
            if app.main_window.device_config:
                # Load LED intensities from config
                try:
                    # Get integration time from calibration data or use default
                    integration_time_ms = 40.0  # Default
                    if (
                        app.data_mgr
                        and app.data_mgr.calibrated
                        and hasattr(app.data_mgr, "calibration_data")
                    ):
                        cd = app.data_mgr.calibration_data
                        int_time_s = (
                            getattr(cd, "p_integration_time", None)
                            or getattr(cd, "s_mode_integration_time", None)
                            or 0.040
                        )
                        integration_time_ms = int_time_s * 1000.0  # Convert to ms

                    # TODO: Integrate 3-stage linear LED calibration model here
                    # from led_calibration_manager import get_led_intensities_for_scan
                    # target_counts = 60000
                    # intensities = get_led_intensities_for_scan(target_counts, integration_time_ms)
                    # led_a, led_b, led_c, led_d = intensities['A'], intensities['B'], intensities['C'], intensities['D']

                    # For now: Use static values from config
                    print("  [STATIC] Using static LED intensities from device config")
                    led_intensities = (
                        app.main_window.device_config.get_led_intensities()
                    )
                    led_a = led_intensities["a"]
                    led_b = led_intensities["b"]
                    led_c = led_intensities["c"]
                    led_d = led_intensities["d"]
                    print(
                        f"  [STATIC] Intensities: A={led_a}, B={led_b}, C={led_c}, D={led_d}"
                    )

                except Exception as e:
                    # Fallback to static values on error
                    print(f"  [FALLBACK] Could not load LED intensities: {e}")
                    print("  [FALLBACK] Using static values from config")
                    led_intensities = (
                        app.main_window.device_config.get_led_intensities()
                    )
                    led_a = led_intensities["a"]
                    led_b = led_intensities["b"]
                    led_c = led_intensities["c"]
                    led_d = led_intensities["d"]

                # Update UI inputs
                app.main_window.channel_a_input.setText(str(led_a))
                app.main_window.channel_b_input.setText(str(led_b))
                app.main_window.channel_c_input.setText(str(led_c))
                app.main_window.channel_d_input.setText(str(led_d))

                # Apply to hardware for fast startup
                if led_a > 0 or led_b > 0 or led_c > 0 or led_d > 0:
                    app.hardware_mgr.ctrl.set_intensity("a", led_a)
                    app.hardware_mgr.ctrl.set_intensity("b", led_b)
                    app.hardware_mgr.ctrl.set_intensity("c", led_c)
                    app.hardware_mgr.ctrl.set_intensity("d", led_d)
                    print(
                        f"  [OK] LED intensities applied to hardware: A={led_a}, B={led_b}, C={led_c}, D={led_d}"
                    )
                else:
                    print(
                        "  ⚠️  No calibrated LED intensities - will calibrate on startup"
                    )

            # Initialize polarizer position to S-mode (default after startup)
            # This keeps UI in sync with hardware state
            if hasattr(app.main_window, "sidebar"):
                app.main_window.sidebar.set_polarizer_position("S")
                print("  [OK] Polarizer position initialized to S-mode (default)")

            # Populate Hardware Configuration table with current settings
            # (after device_config is loaded and hardware is connected)
            if hasattr(app.main_window, '_load_current_settings'):
                try:
                    app.main_window._load_current_settings(show_warnings=False)
                    print("  [OK] Hardware Configuration populated with current settings")
                except Exception as load_err:
                    print(f"  [WARN] Could not populate Hardware Configuration: {load_err}")

        except Exception as e:
            print(f"Failed to load device settings: {e}")
            import traceback

            traceback.print_exc()

    @staticmethod
    def on_calibration_complete(app: Application, calibration_data) -> None:
        """Handler for calibration completion - updates status AND shows QC dialog.

        Args:
            app: Application instance
            calibration_data: CalibrationData object (immutable dataclass)

        """
        try:
            # === PART 1: Apply calibration to acquisition manager ===
            print("=" * 80)
            print("CALIBRATION COMPLETE - APPLYING TO ACQUISITION MANAGER")
            print("=" * 80)

            app.data_mgr.apply_calibration(calibration_data)

            print("Calibration data applied successfully")
            print("System ready for live acquisition")

            # Save SPR model path to device config
            device_serial = (
                app.hardware_mgr.usb.serial_number if app.hardware_mgr.usb else None
            )
            if calibration_data and app.main_window.device_config and device_serial:
                spr_model_path = Path(
                    f"OpticalSystem_QC/{device_serial}/spr_calibration/led_calibration_spr_processed_latest.json"
                )
                if spr_model_path.exists():
                    app.main_window.device_config.set_spr_model_path(
                        str(spr_model_path)
                    )
                    app.main_window.device_config.save()
                    print(f"✓ SPR model path saved to device_config: {spr_model_path}")
                else:
                    print(
                        f"SPR model file not in QC folder (expected location): {spr_model_path}"
                    )

            # Save QC report for traceability and ML model
            if calibration_data and device_serial:
                from affilabs.managers.qc_report_manager import QCReportManager

                qc_manager = QCReportManager()

                # Convert calibration data to dict for saving
                qc_data_dict = (
                    calibration_data.to_dict()
                    if hasattr(calibration_data, "to_dict")
                    else calibration_data
                )

                # Get software version
                software_version = getattr(app.main_window, "version", "2.0")

                # Save QC report
                report_path = qc_manager.save_qc_report(
                    calibration_data=qc_data_dict,
                    device_serial=device_serial,
                    software_version=software_version,
                )

                if report_path:
                    print(
                        f"QC report saved for ML/traceability: {report_path.name}"
                    )

                    # Generate HTML export
                    html_path = qc_manager.export_to_html(report_path)
                    if html_path:
                        print(f"HTML report exported: {html_path.name}")

            print("=" * 80)
            print("")

            # === PART 2: Update hardware manager status ===
            # CalibrationData is a dataclass, not a dict - check if channels were calibrated
            optics_ready = (
                len(calibration_data.get_channels()) > 0 if calibration_data else False
            )
            print(f"Calibration complete signal received - optics_ready={optics_ready}")

            # Extract channel errors and S-ref QC results
            ch_error_list = []
            s_ref_qc_results = {}
            if calibration_data:
                # Get failed channels from calibration data
                channels = calibration_data.get_channels()
                all_channels = ["a", "b", "c", "d"]
                ch_error_list = [ch for ch in all_channels if ch not in channels]

                # Get S-ref QC results if available
                s_ref_qc_results = getattr(calibration_data, "s_ref_qc_results", {})

            # Update hardware manager calibration status
            # This will set sensor_ready and optics_ready based on calibration results
            app.hardware_mgr.update_calibration_status(
                ch_error_list, "full", s_ref_qc_results
            )
            print(
                f"Hardware manager calibration status updated - ch_errors={ch_error_list}"
            )

            if optics_ready:
                # Update device status UI directly (no hardware scan needed)
                # Calibration has already verified the hardware is working
                # Check if pump is connected (external AffiPump/KNX OR internal P4PROPLUS pumps)
                external_pump_connected = (
                    hasattr(app.hardware_mgr, 'pump') and
                    app.hardware_mgr.pump is not None
                )

                # Check for P4PROPLUS internal pumps - try multiple access paths
                internal_pump_available = False

                # Method 1: Try _ctrl_raw (raw controller, most reliable)
                if hasattr(app.hardware_mgr, '_ctrl_raw') and app.hardware_mgr._ctrl_raw:
                    raw_ctrl = app.hardware_mgr._ctrl_raw
                    if hasattr(raw_ctrl, 'has_internal_pumps'):
                        internal_pump_available = raw_ctrl.has_internal_pumps()
                        logger.info(f"🔧 P4PROPLUS internal pumps check (_ctrl_raw): {internal_pump_available}")

                # Method 2: Fallback to ctrl (HAL adapter)
                if not internal_pump_available and hasattr(app.hardware_mgr, 'ctrl') and app.hardware_mgr.ctrl:
                    if hasattr(app.hardware_mgr.ctrl, 'has_internal_pumps'):
                        internal_pump_available = app.hardware_mgr.ctrl.has_internal_pumps()
                        logger.info(f"🔧 P4PROPLUS internal pumps check (ctrl): {internal_pump_available}")

                # Flow mode available if EITHER external pump OR internal pumps present
                pump_is_connected = external_pump_connected or internal_pump_available

                logger.info(f"🔧 Pump detection: external={external_pump_connected}, internal={internal_pump_available}, total={pump_is_connected}")

                # Mark flow as calibrated after successful calibration with pump
                if pump_is_connected:
                    app.hardware_mgr._flow_calibrated = True
                    logger.info("✅ Flow mode calibrated - _flow_calibrated flag set to True")

                # Save calibrated LED brightness and integration time to device_config for persistence
                try:
                    if hasattr(calibration_data, 'p_mode_intensities') and calibration_data.p_mode_intensities:
                        logger.info("💾 Saving calibrated LED brightness to device_config...")
                        app.main_window.device_config.set_led_intensities(
                            led_a=int(calibration_data.p_mode_intensities.get('a', 0)),
                            led_b=int(calibration_data.p_mode_intensities.get('b', 0)),
                            led_c=int(calibration_data.p_mode_intensities.get('c', 0)),
                            led_d=int(calibration_data.p_mode_intensities.get('d', 0)),
                        )
                        logger.info(f"   ✓ Saved LED brightness: A={calibration_data.p_mode_intensities['a']}, B={calibration_data.p_mode_intensities['b']}, C={calibration_data.p_mode_intensities['c']}, D={calibration_data.p_mode_intensities['d']}")

                    # Save integration time (prefer S-mode, then P-mode)
                    integration_time = None
                    if hasattr(calibration_data, 's_integration_time') and calibration_data.s_integration_time:
                        integration_time = calibration_data.s_integration_time
                        logger.info(f"💾 Saving S-mode integration time to device_config: {integration_time} ms")
                    elif hasattr(calibration_data, 'p_integration_time') and calibration_data.p_integration_time:
                        integration_time = calibration_data.p_integration_time
                        logger.info(f"💾 Saving P-mode integration time to device_config: {integration_time} ms")

                    if integration_time:
                        app.main_window.device_config.set_integration_time(integration_time)

                    # Save to disk once for all changes
                    app.main_window.device_config.save()
                    if integration_time:
                        logger.info(f"   ✓ Saved integration time: {integration_time} ms")

                    # Refresh Settings sidebar to show new calibrated values
                    if hasattr(app, 'main_window') and hasattr(app.main_window, 'sidebar'):
                        try:
                            servo_positions = app.main_window.device_config.get_servo_positions()
                            led_intensities = app.main_window.device_config.get_led_intensities()
                            app.main_window.sidebar.load_hardware_settings(
                                s_pos=servo_positions.get("s", 10) if servo_positions else 10,
                                p_pos=servo_positions.get("p", 187) if servo_positions else 187,
                                led_a=led_intensities.get("a", 0),
                                led_b=led_intensities.get("b", 0),
                                led_c=led_intensities.get("c", 0),
                                led_d=led_intensities.get("d", 0),
                            )
                            logger.info("✅ Settings sidebar refreshed with calibrated LED values")
                        except Exception as refresh_error:
                            logger.warning(f"Could not refresh Settings sidebar: {refresh_error}")
                except Exception as e:
                    logger.warning(f"Failed to save calibration data to device_config: {e}")

                status_update = {
                    "sensor_ready": True,
                    "optics_ready": True,
                    "ctrl_type": app.hardware_mgr._get_controller_type(),
                    "spectrometer": app.hardware_mgr.usb.serial_number
                    if app.hardware_mgr.usb
                    else None,
                    "fluidics_ready": pump_is_connected,  # Set to True if pump detected
                    "pump_connected": pump_is_connected,  # Enable/disable Flow operation mode
                    "flow_calibrated": pump_is_connected,  # Flow mode ready after calibration
                }

                pump_type = "P4PROPLUS internal" if internal_pump_available else ("external" if external_pump_connected else "none")
                logger.info("📋 Calibration complete - updating device status:")
                logger.info("   Sensor: Ready")
                logger.info("   Optics: Ready")
                logger.info(f"   Fluidics: {'Ready' if pump_is_connected else 'Not Ready'} (pump: {pump_type})")
                logger.info(f"   STATUS UPDATE DICT: {status_update}")

                app._update_device_status_ui(status_update)

                # Now enable operation mode indicators based on calibration completion
                static_available = True  # Static mode ready after calibration
                flow_available = pump_is_connected  # Flow mode ready if pump is present (external OR internal)

                if hasattr(app, 'sidebar') and hasattr(app.sidebar, 'set_operation_mode_availability'):
                    app.sidebar.set_operation_mode_availability(static_available, flow_available)
                    logger.info(f"✅ Operation mode indicators updated: Static={'Available' if static_available else 'Disabled'}, Flow={'Available' if flow_available else 'Disabled'}")
                print(
                    "Device status updated directly (no hardware scan post-calibration)"
                )

                # Mark calibration as completed (used by power-on workflow)
                app._calibration_completed = True

                print("Sensor and Optics status updated to READY in UI")
            else:
                # Calibration failed - optics not ready
                print(
                    "Calibration completed but optics not ready (some channels failed)"
                )
                app._update_device_status_ui(
                    {"optics_ready": False, "sensor_ready": True}
                )

            # === PART 3: Clear graphs and restart sensorgram at t=0 ===
            if optics_ready:
                print("Clearing graphs and restarting sensorgram at t=0...")
                app._on_clear_graphs_requested()
                print("✓ Sensorgram reset complete - ready for new data")

            # NOTE: QC dialog shown by main.py handler (_on_calibration_complete_status_update)
            # to avoid duplicate dialog display

        except Exception as e:
            print(f"[X] Failed to process calibration completion: {e}")
            import traceback

            traceback.print_exc()
