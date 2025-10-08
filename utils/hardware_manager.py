from __future__ import annotations

import time
import threading
from typing import Any, Callable

from utils.logger import logger
from widgets.message import show_message
from settings import DEVICES
from utils.cavro_pump_manager import CavroPumpManager, PumpAddress
from utils.kinetic_manager import KineticManager
from utils.spr_calibrator import SPRCalibrator


class HardwareManager:
    """
    Manages hardware initialization, connection, and lifecycle management.
    
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
            
            # Check controller type
            if self.ctrl is not None:
                if hasattr(self.ctrl, 'name'):
                    ctrl_name = self.ctrl.name
                    if ctrl_name in ["pico_p4spr", "PicoP4SPR"]:
                        config["ctrl"] = "PicoP4SPR"
                    elif ctrl_name in ["pico_ezspr", "PicoEZSPR"]:  # EZSPR disabled (obsolete)
                        config["ctrl"] = "PicoEZSPR"
                    else:
                        config["ctrl"] = ctrl_name
            
            # Check kinetic system type
            if self.knx is not None:
                if hasattr(self.knx, 'name'):
                    knx_name = self.knx.name
                    if knx_name == "KNX":
                        config["knx"] = "KNX"
                    elif knx_name in {"pico_ezspr", "KNX2"}:  # PicoKNX2 disabled (obsolete)
                        config["knx"] = "KNX2"
                    else:
                        config["knx"] = knx_name
            
            # Update device config
            self.device_config.update(config)
            
            # Update UI display
            mods = []
            if config["ctrl"]:
                mods.append("SPR")
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
                self.pump_manager.pump_state_changed.connect(self._on_pump_state_changed)
                self.pump_manager.error_occurred.connect(self._on_pump_error)
                return True
            else:
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
            self.kinetic_manager.valve_state_changed.connect(self._on_valve_state_changed)
            self.kinetic_manager.sensor_reading.connect(self._on_sensor_reading)
            self.kinetic_manager.device_temp_updated.connect(self._on_device_temp_updated)
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
            self.pump_state_changed(pump_states, False)  # synced flag would come from caller
            
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
            self.valve_state_changed(valve_states, False)  # synced flag would come from caller
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
            if self.ctrl is not None and hasattr(self.ctrl, 'shutdown'):
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
                if hasattr(self.knx, 'shutdown'):
                    self.knx.shutdown()
                self.knx.close()
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
        pump: bool = True
    ) -> bool:
        """Disconnect hardware components gracefully."""
        try:
            self.update_status("Disconnecting...")
            success = True
            
            # Disconnect controller
            if self.ctrl is not None and ctrl:
                try:
                    if self.usb is not None:
                        logger.debug("Closing USB connection")
                        self.usb.close()
                    logger.debug("Closing device")
                    self.ctrl.stop()
                    self.ctrl.close()
                    self.ctrl = None
                except Exception as e:
                    logger.exception(f"Error disconnecting controller: {e}")
                    success = False
            
            # Disconnect kinetics
            if self.knx is not None and knx:
                try:
                    self.knx.close()
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