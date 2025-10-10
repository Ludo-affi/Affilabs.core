from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from utils.cavro_pump_manager import CavroPumpManager, PumpAddress
from utils.hal import HALFactory
from utils.kinetic_manager import KineticManager
from utils.logger import logger
from utils.spr_calibrator import SPRCalibrator


class HardwareManager:
    """Manages hardware initialization, connection, and lifecycle management.

    Handles device discovery, connection establishment, manager initialization,
    graceful shutdown, and hardware state synchronization.
    """

    def __init__(
        self,
        *,
        # Hardware state references
        ctrl: Any | None = None,
        usb: Any | None = None,
        knx: Any | None = None,
        pump: Any | None = None,
        # Manager references (will be created/managed)
        pump_manager: CavroPumpManager | None = None,
        kinetic_manager: KineticManager | None = None,
        calibrator: SPRCalibrator | None = None,
        # Configuration
        device_config: dict[str, Any],
        # State flags
        _c_stop: threading.Event,
        exp_start: float,
        # UI callbacks
        update_device_display: Callable[[str], None],
        update_status: Callable[[str], None],
        setup_device_widget: Callable[[str, str, Any], None],
        setup_kinetic_widget: Callable[[str, str], None],
        # Signal callbacks
        pump_state_changed: Callable[[dict, bool], None],
        valve_state_changed: Callable[[dict, bool], None],
        sensor_reading_updated: Callable[[dict], None],
        temp_display_updated: Callable[[str], None],
        calibration_progress: Callable[[int, str], None],
        on_kinetic_error: Callable[[str, str], None],
        on_pump_error: Callable[[str, str], None],
    ) -> None:
        # Hardware references
        self.ctrl = ctrl
        self.usb = usb
        self.knx = knx
        self.pump = pump

        # Manager references
        self.pump_manager = pump_manager
        self.kinetic_manager = kinetic_manager
        self.calibrator = calibrator

        # Configuration
        self.device_config = device_config

        # State
        self._c_stop = _c_stop
        self.exp_start = exp_start

        # UI callbacks
        self.update_device_display = update_device_display
        self.update_status = update_status
        self.setup_device_widget = setup_device_widget
        self.setup_kinetic_widget = setup_kinetic_widget

        # Signal callbacks
        self.pump_state_changed = pump_state_changed
        self.valve_state_changed = valve_state_changed
        self.sensor_reading_updated = sensor_reading_updated
        self.temp_display_updated = temp_display_updated
        self.calibration_progress = calibration_progress
        self.on_kinetic_error = on_kinetic_error
        self.on_pump_error = on_pump_error

    def get_current_device_config(self) -> dict[str, str]:
        """Update device configuration based on connected devices."""
        try:
            config = {"ctrl": "", "knx": ""}

            # Check controller type by examining HAL object and device info
            if self.ctrl is not None:
                try:
                    # Get device info from HAL object
                    device_info = self.ctrl.get_device_info()
                    model = device_info.get("model", "")

                    if model == "PicoP4SPR" or (
                        isinstance(self.ctrl, type(self.ctrl))
                        and "PicoP4SPR" in type(self.ctrl).__name__
                    ):
                        config["ctrl"] = "PicoP4SPR"
                    elif (
                        model == "PicoEZSPR" or "PicoEZSPR" in type(self.ctrl).__name__
                    ):
                        config["ctrl"] = "PicoEZSPR"  # EZSPR disabled (obsolete)
                    else:
                        config["ctrl"] = model or type(self.ctrl).__name__
                except Exception as e:
                    logger.debug(f"Could not get controller device info: {e}")
                    # Fallback to class name
                    if "PicoP4SPR" in type(self.ctrl).__name__:
                        config["ctrl"] = "PicoP4SPR"
                    else:
                        config["ctrl"] = type(self.ctrl).__name__

            # Check kinetic system type
            if self.knx is not None:
                if hasattr(self.knx, "name"):
                    knx_name = self.knx.name
                    if knx_name == "KNX":
                        config["knx"] = "KNX"
                    elif knx_name in {
                        "pico_ezspr",
                        "KNX2",
                    }:  # PicoKNX2 disabled (obsolete)
                        config["knx"] = "KNX2"
                    else:
                        config["knx"] = knx_name

            # Update device config
            self.device_config.update(config)

            # Update UI display
            mods = []
            if config["ctrl"]:
                # Show specific controller type
                if config["ctrl"] == "PicoP4SPR":
                    mods.append("P4SPR")
                elif config["ctrl"] == "PicoEZSPR":
                    mods.append("EZSPR")
                else:
                    mods.append("SPR")  # Generic fallback
            if config["knx"]:  # EZSPR check removed (obsolete)
                mods.append("Kinetics")
            if self.pump:  # EZSPR check removed (obsolete)
                mods.append("Pumps")

            dev_str = " + ".join(mods) or "No Devices"
            self.update_device_display(dev_str)

            if dev_str == "No Devices":
                self.update_status("No Connection")
            else:
                self.update_status("Connected")

            return config

        except Exception as e:
            logger.exception(f"Error updating device config: {e}")
            return {"ctrl": "", "knx": ""}

    def initialize_hardware_managers(self) -> tuple[bool, list[str]]:
        """Initialize all hardware managers and return success status."""
        errors = []
        success = True

        # Initialize pump manager
        if not self._initialize_pump_manager():
            errors.append("Pump manager initialization failed")
            success = False

        # Initialize kinetic manager
        if not self._initialize_kinetic_manager():
            errors.append("Kinetic manager initialization failed")
            success = False

        # Initialize calibrator
        if not self._initialize_calibrator():
            errors.append("Calibrator initialization failed")
            success = False

        return success, errors

    def _initialize_pump_manager(self) -> bool:
        """Initialize pump manager if pump hardware is available."""
        if not self.pump:
            return True  # No pump hardware, not an error

        try:
            self.pump_manager = CavroPumpManager(self.pump)
            if self.pump_manager.initialize_pumps():
                # Set default syringe sizes (5 mL syringes)
                self.pump_manager.set_syringe_size(PumpAddress.PUMP_1, 5000)
                self.pump_manager.set_syringe_size(PumpAddress.PUMP_2, 5000)
                logger.info("Pump manager initialized successfully")

                # Connect pump manager signals
                self.pump_manager.pump_state_changed.connect(
                    self._on_pump_state_changed,
                )
                self.pump_manager.error_occurred.connect(self._on_pump_error)
                return True
            logger.warning("Pump manager initialization failed")
            return False
        except Exception as e:
            logger.exception(f"Error initializing pump manager: {e}")
            self.pump_manager = None
            return False

    def _initialize_kinetic_manager(self) -> bool:
        """Initialize kinetic manager if KNX hardware is available."""
        if not self.knx:
            return True  # No kinetic hardware, not an error

        try:
            self.kinetic_manager = KineticManager(self.knx, self.exp_start)
            logger.info("Kinetic manager initialized successfully")

            # Connect kinetic manager signals
            self.kinetic_manager.valve_state_changed.connect(
                self._on_valve_state_changed,
            )
            self.kinetic_manager.sensor_reading.connect(self._on_sensor_reading)
            self.kinetic_manager.device_temp_updated.connect(
                self._on_device_temp_updated,
            )
            self.kinetic_manager.injection_started.connect(self._on_injection_started)
            self.kinetic_manager.injection_ended.connect(self._on_injection_ended)
            self.kinetic_manager.error_occurred.connect(self._on_kinetic_error)
            return True
        except Exception as e:
            logger.exception(f"Error initializing kinetic manager: {e}")
            self.kinetic_manager = None
            return False

    def _initialize_calibrator(self) -> bool:
        """Initialize calibrator if SPR controller is available."""
        if not self.ctrl or not self.usb:
            return True  # No SPR hardware, not an error

        try:
            device_type = self.device_config.get("ctrl", "") or ""
            self.calibrator = SPRCalibrator(
                ctrl=self.ctrl,
                usb=self.usb,
                device_type=device_type,
                stop_flag=self._c_stop,
            )
            self.calibrator.set_progress_callback(self.calibration_progress)
            logger.info("SPR calibrator initialized successfully")
            return True
        except Exception as e:
            logger.exception(f"Error initializing calibrator: {e}")
            self.calibrator = None
            return False

    def _on_pump_state_changed(self, address: int, description: str) -> None:
        """Handle pump state changes from pump manager."""
        try:
            # Map pump address to channel name
            ch_name = "CH1" if address == PumpAddress.PUMP_1 else "CH2"

            # Determine state
            if "Running" in description or "Flowing" in description:
                state = "Running"
            elif "Stopped" in description or description == "Stopped":
                state = "Off"
            else:
                state = description

            # Emit signal to update UI (assuming pump_states dict and synced flag from caller)
            pump_states = {ch_name: state}
            self.pump_state_changed(
                pump_states,
                False,
            )  # synced flag would come from caller

            logger.debug(f"Pump {ch_name} state: {description}")
        except Exception as e:
            logger.exception(f"Error handling pump state change: {e}")

    def _on_pump_error(self, address: int, error: str) -> None:
        """Handle pump errors from pump manager."""
        try:
            ch_name = "CH1" if address == PumpAddress.PUMP_1 else "CH2"
            logger.error(f"Pump {ch_name} error: {error}")
            self.on_pump_error(ch_name, error)
        except Exception as e:
            logger.exception(f"Error handling pump error: {e}")

    def _on_valve_state_changed(self, channel: str, position_name: str) -> None:
        """Handle valve state changes from kinetic manager."""
        try:
            valve_states = {channel: position_name}
            logger.debug(f"Valve {channel} state: {position_name}")
            self.valve_state_changed(
                valve_states,
                False,
            )  # synced flag would come from caller
        except Exception as e:
            logger.exception(f"Error handling valve state change: {e}")

    def _on_sensor_reading(self, readings: dict) -> None:
        """Handle sensor readings from kinetic manager."""
        try:
            # Update UI with sensor readings
            # readings dict has keys: "temp1", "temp2" (no flow keys)
            self.sensor_reading_updated(readings)
        except Exception as e:
            logger.exception(f"Error handling sensor reading: {e}")

    def _on_device_temp_updated(self, temperature: str, source: str) -> None:
        """Handle device temperature updates from kinetic manager."""
        try:
            logger.debug(f"Device temp ({source}): {temperature}°C")
            self.temp_display_updated(f"{temperature}°C")
        except Exception as e:
            logger.exception(f"Error handling device temp update: {e}")

    def _on_injection_started(self, channel: str, exp_time: float) -> None:
        """Handle injection start from kinetic manager."""
        try:
            logger.info(f"Injection started on {channel} at {exp_time:.2f}s")
            # This would need UI widget reference to update inject time labels
            # Could be enhanced with additional callbacks if needed
        except Exception as e:
            logger.exception(f"Error handling injection start: {e}")

    def _on_injection_ended(self, channel: str) -> None:
        """Handle injection end from kinetic manager."""
        try:
            logger.info(f"Injection ended on {channel}")
        except Exception as e:
            logger.exception(f"Error handling injection end: {e}")

    def _on_kinetic_error(self, channel: str, error_message: str) -> None:
        """Handle kinetic errors from kinetic manager."""
        try:
            logger.error(f"Kinetic {channel} error: {error_message}")
            self.on_kinetic_error(channel, error_message)
        except Exception as e:
            logger.exception(f"Error handling kinetic error: {e}")

    def discover_and_connect_devices(self) -> tuple:
        """Discover and connect to all available hardware devices."""
        # This is a simplified version that returns current device state
        # Device detection happens in the main application's connection_thread
        # TODO: Move actual hardware discovery logic here in future iterations

        device_config = {"ctrl": "", "knx": "", "usb": "", "pump": ""}

        # Return current hardware state
        return device_config, self.ctrl, self.knx, self.usb, self.pump

    def setup_ui_widgets(self) -> None:
        """Setup UI widgets based on connected hardware."""
        try:
            # Use callback functions to setup widgets
            self.setup_device_widget(
                self.device_config.get("ctrl", ""),
                self.device_config.get("knx", ""),
                self.pump,
            )

            self.setup_kinetic_widget(
                self.device_config.get("ctrl", ""),
                self.device_config.get("knx", ""),
            )
        except Exception as e:
            logger.exception(f"Error setting up UI widgets: {e}")
        """Setup UI widgets with current hardware configuration."""
        try:
            self.setup_device_widget(
                self.device_config["ctrl"],
                self.device_config["knx"],
                self.pump,
            )
            self.setup_kinetic_widget(
                self.device_config["ctrl"],
                self.device_config["knx"],
            )
        except Exception as e:
            logger.exception(f"Error setting up UI widgets: {e}")

    def shutdown_controller(self) -> bool:
        """Shutdown controller hardware gracefully."""
        try:
            self.update_status("SPR device powering off...")

            # Shutdown controller if it supports it
            if self.ctrl is not None and hasattr(self.ctrl, "shutdown"):
                self.ctrl.shutdown()

            # Close hardware connections
            success = self.disconnect_hardware(knx=False, pump=False)

            # Update configuration
            self.get_current_device_config()
            self.setup_ui_widgets()

            return success
        except Exception as e:
            logger.exception(f"Error during controller shutdown: {e}")
            return False

    def shutdown_kinetics(self, *, skip_setup: bool = False) -> bool:
        """Shutdown kinetics hardware gracefully."""
        try:
            self.update_status("Kinetic unit powering off...")

            # Shutdown kinetic hardware
            if self.knx is not None:
                if hasattr(self.knx, "shutdown"):
                    self.knx.shutdown()
                self.knx.disconnect()
            self.knx = None

            # Cleanup kinetic manager
            if self.kinetic_manager:
                try:
                    logger.info("Shutting down kinetic manager")
                    self.kinetic_manager.shutdown()
                except Exception as e:
                    logger.warning(f"Error shutting down kinetic manager: {e}")
                finally:
                    self.kinetic_manager = None

            if not skip_setup:
                self.get_current_device_config()
                self.setup_ui_widgets()

            return True
        except Exception as e:
            logger.exception(f"Error during kinetics shutdown: {e}")
            return False

    def disconnect_hardware(
        self,
        *,
        ctrl: bool = True,
        knx: bool = True,
        pump: bool = True,
    ) -> bool:
        """Disconnect hardware components gracefully."""
        try:
            self.update_status("Disconnecting...")
            success = True

            # Disconnect controller
            if self.ctrl is not None and ctrl:
                try:
                    # First, turn off all LEDs before disconnection
                    self._safe_led_shutdown()

                    if self.usb is not None:
                        logger.debug("Closing USB connection")
                        self.usb.disconnect()
                    logger.debug("Closing device")
                    # HAL objects don't have a stop() method, only disconnect()
                    self.ctrl.disconnect()
                    self.ctrl = None
                except Exception as e:
                    logger.exception(f"Error disconnecting controller: {e}")
                    success = False

            # Disconnect kinetics
            if self.knx is not None and knx:
                try:
                    self.knx.disconnect()
                    self.knx = None

                    # Cleanup kinetic manager
                    if self.kinetic_manager:
                        try:
                            logger.info("Shutting down kinetic manager")
                            self.kinetic_manager.shutdown()
                        except Exception as e:
                            logger.warning(f"Error shutting down kinetic manager: {e}")
                        finally:
                            self.kinetic_manager = None
                except Exception as e:
                    logger.exception(f"Error disconnecting kinetics: {e}")
                    success = False

            # Disconnect pump
            if self.pump and pump:
                try:
                    # Gracefully stop pumps using pump manager
                    if self.pump_manager:
                        try:
                            logger.info("Stopping pumps gracefully")
                            self.pump_manager.stop()  # Stop all pumps
                            time.sleep(0.2)  # Brief delay for command completion
                        except Exception as e:
                            logger.warning(f"Error stopping pumps: {e}")
                        finally:
                            self.pump_manager = None
                    self.pump = None
                except Exception as e:
                    logger.exception(f"Error disconnecting pump: {e}")
                    success = False

            # Update configuration and UI
            self.get_current_device_config()
            self.setup_ui_widgets()

            return success

        except Exception as e:
            logger.exception(f"Error during hardware disconnect: {e}")
            return False

    def get_hardware_status(self) -> dict[str, bool]:
        """Get current hardware connection status."""
        return {
            "controller": self.ctrl is not None,
            "kinetics": self.knx is not None,
            "pump": self.pump is not None,
            "usb": self.usb is not None,
        }

    def get_manager_status(self) -> dict[str, bool]:
        """Get current manager initialization status."""
        return {
            "pump_manager": self.pump_manager is not None,
            "kinetic_manager": self.kinetic_manager is not None,
            "calibrator": self.calibrator is not None,
        }

    def update_hardware_references(
        self,
        *,
        ctrl: Any | None = None,
        usb: Any | None = None,
        knx: Any | None = None,
        pump: Any | None = None,
    ) -> None:
        """Update hardware references and reconfigure."""
        if ctrl is not None:
            self.ctrl = ctrl
        if usb is not None:
            self.usb = usb
        if knx is not None:
            self.knx = knx
        if pump is not None:
            self.pump = pump

        # Update device configuration
        self.get_current_device_config()

    def discover_and_connect_hardware(self) -> tuple[bool, list[str]]:
        """Discover and connect to available hardware using HAL factory.

        Returns:
            tuple: (success, list of error messages)

        """
        errors = []
        success = False

        try:
            logger.info("Starting hardware discovery...")

            # ROBUST CONTROLLER DISCOVERY with multiple attempts
            ctrl_attempts = 0
            max_ctrl_attempts = 3

            while ctrl_attempts < max_ctrl_attempts and self.ctrl is None:
                ctrl_attempts += 1
                try:
                    logger.debug(
                        f"Attempting to connect to PicoP4SPR controller (attempt {ctrl_attempts}/{max_ctrl_attempts})...",
                    )

                    # Enhanced auto-detection with explicit port scanning
                    controller = HALFactory.create_controller(
                        "PicoP4SPR",
                        auto_detect=True,
                    )

                    if controller and controller.is_connected():
                        self.ctrl = controller
                        logger.info("Successfully connected to PicoP4SPR controller")

                        # Reset hardware to clean state on startup
                        self._reset_hardware_on_startup()
                        success = True
                        break
                    logger.warning(
                        f"Controller created but not connected (attempt {ctrl_attempts})",
                    )

                except Exception as e:
                    logger.warning(
                        f"Failed to connect to PicoP4SPR (attempt {ctrl_attempts}): {e}",
                    )
                    if ctrl_attempts < max_ctrl_attempts:
                        logger.debug("Waiting before retry...")
                        import time

                        time.sleep(1.0)  # Wait before retry

            if self.ctrl is None:
                errors.append(
                    f"PicoP4SPR connection failed after {max_ctrl_attempts} attempts",
                )

            # ROBUST SPECTROMETER DISCOVERY with fallback options
            spec_attempts = 0
            max_spec_attempts = 3

            while spec_attempts < max_spec_attempts and self.usb is None:
                spec_attempts += 1
                try:
                    logger.debug(
                        f"Attempting to connect to USB4000 spectrometer (attempt {spec_attempts}/{max_spec_attempts})...",
                    )

                    # Try real hardware first
                    spectrometer = HALFactory.create_spectrometer(
                        "USB4000",
                        auto_detect=True,
                    )

                    if spectrometer and spectrometer.is_connected():
                        self.usb = spectrometer
                        logger.info("Successfully connected to USB4000 spectrometer")
                        success = True
                        break
                    logger.warning(
                        f"Spectrometer created but not connected (attempt {spec_attempts})",
                    )

                except Exception as e:
                    logger.warning(
                        f"Failed to connect to USB4000 (attempt {spec_attempts}): {e}",
                    )

                    if spec_attempts < max_spec_attempts:
                        logger.debug("Waiting before spectrometer retry...")
                        import time

                        time.sleep(1.0)  # Wait before retry

            if self.usb is None:
                errors.append(
                    f"USB4000 connection failed after {max_spec_attempts} attempts",
                )
                self.usb = None

            # TODO: Add kinetic controller discovery when available
            # For now, set to None
            self.knx = None

            # TODO: Add pump discovery when available
            # For now, set to None
            self.pump = None

            # Update device configuration based on connected hardware
            self.get_current_device_config()

            if success:
                logger.info("Hardware discovery completed successfully")
                if errors:
                    logger.warning(f"Partial success with warnings: {errors}")
            else:
                logger.error("Hardware discovery failed - no devices connected")

        except Exception as e:
            logger.exception(f"Error during hardware discovery: {e}")
            errors.append(f"Hardware discovery error: {e}")
            success = False

        return success, errors

    def _reset_hardware_on_startup(self) -> None:
        """Reset hardware to clean state on application startup."""
        try:
            logger.info("Resetting hardware to clean state...")

            # Reset controller if available
            if self.ctrl is not None:
                try:
                    # Use HAL reset_device method if available
                    if hasattr(self.ctrl, "reset_device"):
                        success = self.ctrl.reset_device()
                        if success:
                            logger.info("Hardware reset via HAL successful")
                        else:
                            logger.warning("Hardware reset via HAL failed")

                    # Also try direct LED shutdown
                    if hasattr(self.ctrl, "set_led_intensity"):
                        self.ctrl.set_led_intensity(0.0)  # Turn off LEDs
                        logger.debug("LEDs turned off via HAL")

                except Exception as hal_e:
                    logger.warning(f"HAL hardware reset failed: {hal_e}")

            # Emergency direct serial reset as backup
            self._emergency_hardware_reset()

            logger.info("Hardware startup reset completed")

        except Exception as e:
            logger.error(f"Hardware startup reset failed: {e}")

    def _emergency_hardware_reset(self) -> None:
        """Emergency hardware reset using direct serial commands."""
        try:
            import time

            import serial

            logger.debug("Performing emergency hardware reset via direct serial")

            # Try COM4 (most common for PicoP4SPR)
            try:
                with serial.Serial("COM4", 115200, timeout=1) as ser:
                    # Turn off all LED channels
                    ser.write(b"lx\n")
                    time.sleep(0.1)
                    response1 = ser.read(10)

                    # Set LED intensity to 0
                    ser.write(b"i0\n")
                    time.sleep(0.1)
                    response2 = ser.read(10)

                    # Reset polarizer to S-mode
                    ser.write(b"ss\n")
                    time.sleep(0.1)
                    response3 = ser.read(10)

                    logger.debug(
                        f"Emergency reset: lx={response1}, i0={response2}, ss={response3}",
                    )

            except Exception as serial_e:
                logger.debug(f"Direct serial hardware reset failed: {serial_e}")

        except Exception as e:
            logger.error(f"Emergency hardware reset failed: {e}")

    def _safe_led_shutdown(self) -> None:
        """Safely turn off all LEDs before disconnection."""
        try:
            logger.debug("Performing safe LED shutdown...")

            # Method 1: Try HAL interface first
            try:
                if hasattr(self.ctrl, "reset_device"):
                    # P4SPR - use reset which turns off all channels (and thus LEDs)
                    self.ctrl.reset_device()
                    logger.debug("LEDs turned off via HAL reset_device")
                elif hasattr(self.ctrl, "turn_off_channels"):
                    self.ctrl.turn_off_channels()
                    logger.debug("LEDs turned off via HAL turn_off_channels")
                elif hasattr(self.ctrl, "set_led_intensity"):
                    self.ctrl.set_led_intensity(0.0)
                    logger.debug("LEDs turned off via HAL set_led_intensity")
                elif hasattr(self.ctrl, "turn_off_leds"):
                    self.ctrl.turn_off_leds()
                    logger.debug("LEDs turned off via HAL turn_off_leds")
            except Exception as hal_e:
                logger.warning(f"HAL LED shutdown failed: {hal_e}")

            # Method 2: Emergency direct serial LED shutdown as backup
            try:
                import time

                import serial

                logger.debug("Emergency LED shutdown via direct serial...")
                with serial.Serial("COM4", 115200, timeout=1) as ser:
                    # Turn off all P4SPR LED channels (oa, ob, oc, od)
                    for channel in ["a", "b", "c", "d"]:
                        ser.write(f"o{channel}\n".encode())
                        time.sleep(0.05)

                    # Also try generic LED off commands as backup
                    ser.write(b"lx\n")
                    time.sleep(0.1)

                    logger.debug("Direct LED shutdown commands sent")
            except Exception as serial_e:
                logger.warning(f"Direct serial LED shutdown failed: {serial_e}")

            logger.debug("LED shutdown completed")

        except Exception as e:
            logger.error(f"Error during LED shutdown: {e}")
            # Even if LED shutdown fails, log and continue
