"""Controller Hardware Adapter

Wraps existing controller implementations (ArduinoController, PicoP4SPR, PicoEZSPR, etc.)
behind the IController interface for consistent access.
"""

from typing import Optional, Dict, Any
from .device_interface import (
    IController,
    DeviceInfo,
    ControllerCapabilities,
    ConnectionError as HWConnectionError,
    CommandError
)

# Import existing controller classes
from src.utils.controller import (
    ControllerBase,
    ArduinoController,
    PicoP4SPR,
    PicoEZSPR,
    KineticController,
    PicoKNX2,
    FlowController
)


class ControllerAdapter(IController):
    """Adapter wrapping existing controller implementations.

    Provides IController interface for:
    - ArduinoController (legacy static)
    - PicoP4SPR (static)
    - PicoEZSPR (flow)
    - KineticController (legacy flow)
    - PicoKNX2 (flow)
    """

    def __init__(self, controller: ControllerBase):
        """Initialize adapter.

        Args:
            controller: Existing controller instance (ArduinoController, PicoP4SPR, etc.)
        """
        self._controller = controller
        self._connected = False

    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    def connect(self, **kwargs) -> bool:
        """Connect to controller."""
        try:
            if hasattr(self._controller, 'open'):
                success = self._controller.open()
                if success:
                    self._connected = True
                return success
            return False
        except Exception as e:
            raise HWConnectionError(f"Controller connection failed: {e}")

    def disconnect(self) -> None:
        """Disconnect from controller."""
        try:
            if hasattr(self._controller, 'close'):
                self._controller.close()
        except Exception:
            pass  # Never raise on disconnect
        finally:
            self._connected = False

    def is_connected(self) -> bool:
        """Check if controller is connected."""
        # Check internal state and serial connection
        if not self._connected:
            return False

        if hasattr(self._controller, '_ser') and self._controller._ser is not None:
            try:
                return self._controller._ser.is_open
            except:
                return False

        return self._connected

    def get_info(self) -> DeviceInfo:
        """Get device identification."""
        controller_type = type(self._controller).__name__

        # Extract port if available
        port = None
        if hasattr(self._controller, '_ser') and self._controller._ser is not None:
            port = getattr(self._controller._ser, 'port', None)

        # Get firmware version if available
        firmware_version = None
        if hasattr(self._controller, 'get_info'):
            try:
                info = self._controller.get_info()
                if isinstance(info, dict):
                    firmware_version = info.get('firmware_version')
            except:
                pass

        return DeviceInfo(
            device_type="controller",
            model=controller_type,
            serial_number=None,  # Controllers typically don't expose serial
            firmware_version=firmware_version,
            hardware_version=None,
            port=port
        )

    def get_capabilities(self) -> ControllerCapabilities:
        """Get controller capabilities."""
        controller_type = type(self._controller).__name__

        # Determine if flow controller
        is_flow = isinstance(self._controller, FlowController)

        # Check for batch LED support
        supports_batch = hasattr(self._controller, 'set_batch_intensities')

        # Check for pump support (EZSPR only)
        supports_pump = 'EZSPR' in controller_type or 'EZS' in controller_type

        # Check for temperature monitoring
        supports_temp = hasattr(self._controller, 'get_temperature')

        return ControllerCapabilities(
            num_led_channels=4,
            supports_batch_led_control=supports_batch,
            led_intensity_range=(0, 255),
            supports_polarizer=True,
            supports_servo=True,
            supports_pump=supports_pump,
            supports_temperature=supports_temp,
            supports_eeprom_config=True,
            is_flow_controller=is_flow,
            supports_reconnect=True,
            supports_firmware_update=False,
            requires_calibration=True
        )

    # ========================================================================
    # LED CONTROL
    # ========================================================================

    def turn_on_channel(self, channel: str) -> bool:
        """Turn on specific LED channel."""
        try:
            if hasattr(self._controller, 'turn_on_channel'):
                self._controller.turn_on_channel(channel)
                return True
            return False
        except Exception as e:
            raise CommandError(f"Failed to turn on channel {channel}: {e}")

    def turn_off_channels(self) -> bool:
        """Turn off all LED channels."""
        try:
            if hasattr(self._controller, 'turn_off_channels'):
                self._controller.turn_off_channels()
                return True
            return False
        except Exception as e:
            raise CommandError(f"Failed to turn off channels: {e}")

    def set_intensity(self, channel: str, intensity: int) -> bool:
        """Set LED channel intensity."""
        if not 0 <= intensity <= 255:
            raise ValueError(f"Intensity must be 0-255, got {intensity}")

        try:
            if hasattr(self._controller, 'set_intensity'):
                self._controller.set_intensity(channel, intensity)
                return True
            return False
        except Exception as e:
            raise CommandError(f"Failed to set intensity for channel {channel}: {e}")

    def set_batch_intensities(self, a: int = 0, b: int = 0, c: int = 0, d: int = 0) -> bool:
        """Set all LED intensities in batch."""
        # Validate intensities
        for val in [a, b, c, d]:
            if not 0 <= val <= 255:
                raise ValueError(f"Intensities must be 0-255, got {val}")

        try:
            if hasattr(self._controller, 'set_batch_intensities'):
                # Use native batch command
                self._controller.set_batch_intensities(a, b, c, d)
                return True
            else:
                # Fall back to sequential commands
                self.set_intensity('a', a)
                self.set_intensity('b', b)
                self.set_intensity('c', c)
                self.set_intensity('d', d)
                return True
        except Exception as e:
            raise CommandError(f"Failed to set batch intensities: {e}")

    def get_led_intensities(self) -> Dict[str, int]:
        """Get current LED intensities."""
        try:
            if hasattr(self._controller, 'get_all_led_intensities'):
                result = self._controller.get_all_led_intensities()
                if isinstance(result, dict):
                    return result

            # Return zeros if not supported
            return {'a': 0, 'b': 0, 'c': 0, 'd': 0}
        except Exception:
            return {'a': 0, 'b': 0, 'c': 0, 'd': 0}

    # ========================================================================
    # POLARIZER CONTROL
    # ========================================================================

    def set_mode(self, mode: str) -> bool:
        """Set polarizer mode."""
        if mode not in ['s', 'p']:
            raise ValueError(f"Mode must be 's' or 'p', got '{mode}'")

        try:
            if hasattr(self._controller, 'set_mode'):
                self._controller.set_mode(mode)
                return True
            return False
        except Exception as e:
            raise CommandError(f"Failed to set mode to {mode}: {e}")

    def get_mode(self) -> str:
        """Get current polarizer mode."""
        try:
            if hasattr(self._controller, 'get_mode'):
                return self._controller.get_mode()
            return 's'  # Default
        except Exception:
            return 's'

    def set_servo_position(self, position: int, save_to_eeprom: bool = False) -> bool:
        """Set servo position."""
        if not 0 <= position <= 255:
            raise ValueError(f"Position must be 0-255, got {position}")

        try:
            if save_to_eeprom and hasattr(self._controller, 'servo_move_and_save'):
                self._controller.servo_move_and_save(position)
                return True
            elif hasattr(self._controller, 'servo_move_calibration_only'):
                self._controller.servo_move_calibration_only(position)
                return True
            return False
        except Exception as e:
            raise CommandError(f"Failed to set servo position: {e}")

    # ========================================================================
    # TEMPERATURE MONITORING
    # ========================================================================

    def get_temperature(self) -> Optional[float]:
        """Get controller temperature."""
        try:
            if hasattr(self._controller, 'get_temperature'):
                return self._controller.get_temperature()
            return None
        except Exception:
            return None

    # ========================================================================
    # EEPROM CONFIGURATION
    # ========================================================================

    def is_config_valid_in_eeprom(self) -> bool:
        """Check if valid configuration exists in EEPROM."""
        try:
            if hasattr(self._controller, 'is_config_valid_in_eeprom'):
                return self._controller.is_config_valid_in_eeprom()
            return False
        except Exception:
            return False

    def read_config_from_eeprom(self) -> Optional[Dict[str, Any]]:
        """Read device configuration from EEPROM."""
        try:
            if hasattr(self._controller, 'read_config_from_eeprom'):
                return self._controller.read_config_from_eeprom()
            return None
        except Exception:
            return None

    def write_config_to_eeprom(self, config: Dict[str, Any]) -> bool:
        """Write device configuration to EEPROM."""
        try:
            if hasattr(self._controller, 'write_config_to_eeprom'):
                return self._controller.write_config_to_eeprom(config)
            return False
        except Exception:
            return False


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_controller_adapter(controller_type: str, **kwargs) -> ControllerAdapter:
    """Factory function to create controller adapter by type.

    Args:
        controller_type: 'arduino', 'pico_p4spr', 'pico_ezspr', 'kinetic', 'pico_knx2'
        **kwargs: Additional parameters for controller initialization

    Returns:
        ControllerAdapter wrapping the requested controller type

    Raises:
        ValueError: If controller_type is unknown
    """
    controller_map = {
        'arduino': ArduinoController,
        'pico_p4spr': PicoP4SPR,
        'pico_ezspr': PicoEZSPR,
        'kinetic': KineticController,
        'pico_knx2': PicoKNX2
    }

    controller_class = controller_map.get(controller_type.lower())
    if not controller_class:
        raise ValueError(
            f"Unknown controller type '{controller_type}'. "
            f"Valid types: {list(controller_map.keys())}"
        )

    # Create controller instance
    controller = controller_class()

    # Wrap in adapter
    return ControllerAdapter(controller)


def wrap_existing_controller(controller: ControllerBase) -> ControllerAdapter:
    """Wrap an existing controller instance in an adapter.

    Args:
        controller: Existing controller instance

    Returns:
        ControllerAdapter wrapping the controller
    """
    return ControllerAdapter(controller)
