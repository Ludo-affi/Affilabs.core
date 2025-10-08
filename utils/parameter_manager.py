from __future__ import annotations

import time
from typing import Any, Callable

from utils.logger import logger
from settings import CH_LIST, DEVICES, MIN_INTEGRATION, MAX_INTEGRATION


class ParameterManager:
    """
    Manages advanced parameter validation, device configuration, and hardware updates.
    
    Handles LED intensities, servo positions, pump corrections, timing parameters,
    and other advanced device settings with proper validation and hardware synchronization.
    """
    
    def __init__(
        self,
        *,
        # Hardware references
        ctrl: Any | None,
        usb: Any | None, 
        knx: Any | None,
        # Configuration state
        device_config: dict[str, Any],
        leds_calibrated: dict[str, int],
        # Current parameter values
        led_delay: float,
        ht_req: float,
        sensor_interval: float,
        integration: float,
        num_scans: int,
        # Callbacks for state management
        pause_acquisition: Callable[[], None],
        resume_acquisition: Callable[[], None],
        # UI callbacks
        display_settings: Callable[[dict[str, Any]], None],
    ) -> None:
        # Hardware references
        self.ctrl = ctrl
        self.usb = usb
        self.knx = knx
        
        # Configuration
        self.device_config = device_config
        self.leds_calibrated = leds_calibrated
        
        # Current parameter values
        self.led_delay = led_delay
        self.ht_req = ht_req
        self.sensor_interval = sensor_interval
        self.integration = integration
        self.num_scans = num_scans
        
        # Callbacks
        self.pause_acquisition = pause_acquisition
        self.resume_acquisition = resume_acquisition
        self.display_settings = display_settings

    def get_device_parameters(self) -> None:
        """Get current device parameters and display them."""
        try:
            if not self.device_config["ctrl"] in DEVICES or self.ctrl is None:
                return
                
            # Get servo positions
            s_pos = 0
            p_pos = 0
            if self.device_config["ctrl"] in ["PicoP4SPR", "PicoEZSPR"]:
                try:
                    polarizer_pos = self.ctrl.servo_get()
                    s_pos = int(polarizer_pos["s"][0:3])
                    p_pos = int(polarizer_pos["p"][0:3])
                except Exception as e:
                    logger.exception(f"Error reading s & p from device: {e}")
                logger.debug(f"Current s = {s_pos}, current p = {p_pos}")
            
            # Get pump corrections
            pump_1_correction = 1.0
            pump_2_correction = 1.0
            try:
                from utils.pico_ezspr import PicoEZSPR
                if isinstance(self.knx, PicoEZSPR):
                    corrections = self.knx.get_pump_corrections()
                    if corrections is not None:
                        pump_1_correction = corrections[0]
                        pump_2_correction = corrections[1]
            except Exception as e:
                logger.debug(f"Could not get pump corrections: {e}")
            
            # Build parameter dictionary
            params = {
                "led_del": self.led_delay,
                "ht_req": self.ht_req,
                "sens_interval": self.sensor_interval,
                "intg_time": self.integration,
                "num_scans": self.num_scans,
                "led_int_a": self.leds_calibrated["a"],
                "led_int_b": self.leds_calibrated["b"],
                "led_int_c": self.leds_calibrated["c"],
                "led_int_d": self.leds_calibrated["d"],
                "s_pos": s_pos,
                "p_pos": p_pos,
                "pump_1_correction": pump_1_correction,
                "pump_2_correction": pump_2_correction,
            }
            
            self.display_settings(params)
            
        except Exception as e:
            logger.exception(f"Error getting device parameters: {e}")

    def update_advanced_parameters(self, params: dict[str, str]) -> bool:
        """Update advanced parameters with validation and hardware sync."""
        try:
            if not self.device_config["ctrl"] in DEVICES or self.ctrl is None:
                return False
                
            # Pause acquisition during parameter updates
            self.pause_acquisition()
            
            success = True
            
            # Update timing parameters
            success &= self._update_timing_parameters(params)
            
            # Update integration time
            success &= self._update_integration_time(params)
            
            # Update LED intensities
            success &= self._update_led_intensities(params)
            
            # Update servo positions
            success &= self._update_servo_positions(params)
            
            # Update pump corrections
            success &= self._update_pump_corrections(params)
            
            # Resume acquisition
            self.resume_acquisition()
            
            return success
            
        except Exception as e:
            logger.exception(f"Error while updating advanced parameters: {e}")
            self.resume_acquisition()  # Ensure we resume even on error
            return False

    def _update_timing_parameters(self, params: dict[str, str]) -> bool:
        """Update timing-related parameters."""
        try:
            self.led_delay = float(params["led_del"])
            self.ht_req = float(params["ht_req"])
            self.sensor_interval = float(params["sens_interval"])
            self.num_scans = int(params["num_scans"])
            return True
        except (ValueError, KeyError) as e:
            logger.warning(f"Error updating timing parameters: {e}")
            return False

    def _update_integration_time(self, params: dict[str, str]) -> bool:
        """Update and validate integration time."""
        try:
            new_intg = float(params["intg_time"])
            
            # Validate integration time bounds
            if new_intg < MIN_INTEGRATION:
                new_intg = MIN_INTEGRATION
                logger.warning(f"Integration time below minimum, set to {MIN_INTEGRATION}")
            elif new_intg > MAX_INTEGRATION:
                new_intg = MAX_INTEGRATION
                logger.warning(f"Integration time above maximum, set to {MAX_INTEGRATION}")
            
            # Special handling for specific USB devices
            if self.usb is not None and hasattr(self.usb, 'serial_number'):
                if self.usb.serial_number == "FLMT09793":
                    new_intg = round(new_intg / 2.5) * 2.5
            
            self.integration = new_intg
            if self.usb is not None:
                self.usb.set_integration(new_intg)
                
            return True
        except (ValueError, KeyError) as e:
            logger.warning(f"Error updating integration time: {e}")
            return False

    def _update_led_intensities(self, params: dict[str, str]) -> bool:
        """Update and validate LED intensities."""
        try:
            new_led_ints = {
                "a": int(params["led_int_a"]),
                "b": int(params["led_int_b"]),
                "c": int(params["led_int_c"]),
                "d": int(params["led_int_d"]),
            }
            
            # Validate and apply LED intensities
            for ch in CH_LIST:
                min_intensity = 1
                max_intensity = 255
                
                if new_led_ints[ch] > max_intensity:
                    new_led_ints[ch] = max_intensity
                    logger.warning(f"LED {ch} intensity clamped to {max_intensity}")
                elif new_led_ints[ch] < min_intensity:
                    new_led_ints[ch] = min_intensity
                    logger.warning(f"LED {ch} intensity clamped to {min_intensity}")
                
                self.leds_calibrated[ch] = new_led_ints[ch]
                
                # Set hardware intensity
                if self.ctrl is not None:
                    self.ctrl.set_intensity(ch=ch, raw_val=new_led_ints[ch])
                    time.sleep(0.1)
                    self.ctrl.turn_off_channels()
                    time.sleep(0.1)
            
            return True
        except (ValueError, KeyError) as e:
            logger.warning(f"Error updating LED intensities: {e}")
            return False

    def _update_servo_positions(self, params: dict[str, str]) -> bool:
        """Update servo polarizer positions if changed."""
        try:
            if self.ctrl is None:
                return True
                
            # Get current positions
            current_servo_positions = self.ctrl.servo_get()
            old_s = int(current_servo_positions["s"])
            old_p = int(current_servo_positions["p"])
            
            # Get new positions
            new_s = int(params["s_pos"])
            new_p = int(params["p_pos"])
            
            # Update if changed
            if old_s != new_s or old_p != new_p:
                self.ctrl.servo_set(s=new_s, p=new_p)
                self.ctrl.flash()
                logger.info(f"Updated servo positions: s={new_s}, p={new_p}")
            
            return True
        except (ValueError, KeyError) as e:
            logger.warning(f"Error updating servo positions: {e}")
            return False

    def _update_pump_corrections(self, params: dict[str, str]) -> bool:
        """Update pump flow rate corrections."""
        try:
            from utils.pico_ezspr import PicoEZSPR
            
            if not isinstance(self.knx, PicoEZSPR):
                return True  # Not applicable for this hardware
                
            # Get current corrections
            corrections = self.knx.get_pump_corrections()
            if corrections is None:
                return True
                
            # Parse new corrections
            try:
                new_corrections = (
                    float(params["pump_1_correction"]),
                    float(params["pump_2_correction"]),
                )
            except ValueError:
                logger.warning("Invalid pump correction values, using defaults")
                new_corrections = (1.0, 1.0)
            
            # Update if changed
            if corrections != new_corrections:
                self.knx.set_pump_corrections(*new_corrections)
                logger.info(f"Updated pump corrections: {new_corrections}")
            
            return True
        except Exception as e:
            logger.warning(f"Error updating pump corrections: {e}")
            return False

    def validate_parameters(self, params: dict[str, str]) -> tuple[bool, list[str]]:
        """Validate parameter values without applying them."""
        errors = []
        
        # Validate timing parameters
        try:
            led_delay = float(params["led_del"])
            if led_delay < 0:
                errors.append("LED delay must be non-negative")
        except (ValueError, KeyError):
            errors.append("Invalid LED delay value")
            
        try:
            ht_req = float(params["ht_req"])
            if ht_req < 0:
                errors.append("HT requirement must be non-negative")
        except (ValueError, KeyError):
            errors.append("Invalid HT requirement value")
            
        try:
            sensor_interval = float(params["sens_interval"])
            if sensor_interval <= 0:
                errors.append("Sensor interval must be positive")
        except (ValueError, KeyError):
            errors.append("Invalid sensor interval value")
            
        try:
            num_scans = int(params["num_scans"])
            if num_scans < 1:
                errors.append("Number of scans must be at least 1")
        except (ValueError, KeyError):
            errors.append("Invalid number of scans")
            
        # Validate integration time
        try:
            intg_time = float(params["intg_time"])
            if intg_time < MIN_INTEGRATION or intg_time > MAX_INTEGRATION:
                errors.append(f"Integration time must be between {MIN_INTEGRATION} and {MAX_INTEGRATION}")
        except (ValueError, KeyError):
            errors.append("Invalid integration time")
            
        # Validate LED intensities
        for ch in CH_LIST:
            try:
                led_int = int(params[f"led_int_{ch}"])
                if led_int < 1 or led_int > 255:
                    errors.append(f"LED {ch} intensity must be between 1 and 255")
            except (ValueError, KeyError):
                errors.append(f"Invalid LED {ch} intensity")
        
        # Validate servo positions
        try:
            s_pos = int(params["s_pos"])
            p_pos = int(params["p_pos"])
            if s_pos < 0 or s_pos > 180 or p_pos < 0 or p_pos > 180:
                errors.append("Servo positions must be between 0 and 180 degrees")
        except (ValueError, KeyError):
            errors.append("Invalid servo positions")
            
        # Validate pump corrections
        try:
            pump_1_corr = float(params["pump_1_correction"])
            pump_2_corr = float(params["pump_2_correction"])
            if pump_1_corr <= 0 or pump_2_corr <= 0:
                errors.append("Pump corrections must be positive")
        except (ValueError, KeyError):
            errors.append("Invalid pump correction values")
        
        return len(errors) == 0, errors

    def get_current_parameters(self) -> dict[str, Any]:
        """Get current parameter values."""
        return {
            "led_delay": self.led_delay,
            "ht_req": self.ht_req,
            "sensor_interval": self.sensor_interval,
            "integration": self.integration,
            "num_scans": self.num_scans,
            "leds_calibrated": self.leds_calibrated.copy(),
        }