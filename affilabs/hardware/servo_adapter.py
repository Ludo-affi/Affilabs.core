"""Servo Hardware Adapter

Wraps servo calibration functionality behind the IServo interface.
Delegates to existing servo_calibration.py module.
"""

from typing import Optional, Dict
import time
from .device_interface import (
    IServo,
    IController,
    ISpectrometer,
    DeviceInfo,
    ServoCapabilities,
    DeviceError
)


class ServoAdapter(IServo):
    """Adapter for servo/polarizer control.

    Wraps existing servo calibration functionality from servo_calibration.py
    behind the IServo interface.
    """

    def __init__(self):
        """Initialize servo adapter."""
        self._controller: Optional[IController] = None
        self._connected = False
        self._s_position: Optional[int] = None
        self._p_position: Optional[int] = None

    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    def connect(self, controller: IController) -> bool:
        """Connect servo to controller.

        Args:
            controller: Controller instance managing the servo
        """
        if not controller.is_connected():
            raise DeviceError("Controller must be connected before servo")

        self._controller = controller
        self._connected = True

        # Try to load calibrated positions from controller EEPROM
        self._load_positions_from_eeprom()

        return True

    def disconnect(self) -> None:
        """Disconnect servo."""
        self._controller = None
        self._connected = False

    def is_connected(self) -> bool:
        """Check if servo is connected."""
        return (
            self._connected and
            self._controller is not None and
            self._controller.is_connected()
        )

    def get_info(self) -> DeviceInfo:
        """Get device identification."""
        return DeviceInfo(
            device_type="servo",
            model="HS-55MG",  # Standard servo used in SPR systems
            serial_number=None,
            firmware_version=None,
            hardware_version=None,
            port=None
        )

    def get_capabilities(self) -> ServoCapabilities:
        """Get servo capabilities."""
        # Load polarizer type from EEPROM if available
        polarizer_type = None
        if self._controller:
            config = self._controller.read_config_from_eeprom()
            if config:
                polarizer_type = config.get('polarizer_type')

        return ServoCapabilities(
            min_position=5,
            max_position=250,
            settling_time=0.4,
            mode_switch_time=0.15,
            polarizer_type=polarizer_type,
            s_position=self._s_position,
            p_position=self._p_position,
            supports_calibration=True,
            supports_reconnect=True,
            supports_firmware_update=False,
            requires_calibration=True
        )

    # ========================================================================
    # CALIBRATION
    # ========================================================================

    def calibrate(
        self,
        spectrometer: ISpectrometer,
        controller: IController,
        **kwargs
    ) -> Dict[str, int]:
        """Calibrate servo positions for S and P polarization.

        Args:
            spectrometer: Spectrometer for measurements
            controller: Controller managing LEDs and servo
            **kwargs: Calibration parameters:
                - led_intensities: Dict[str, int] - LED intensities to use
                - integration_time_ms: float - Integration time
                - num_scans: int - Number of scans per measurement

        Returns:
            {'s_position': 0-255, 'p_position': 0-255}
        """
        # Import servo calibration function
        from affilabs.utils.servo_calibration import calibrate_servo_positions_6step
        from affilabs.utils.controller import ControllerBase
        from affilabs.utils.usb4000_wrapper import USB4000

        # Extract kwargs
        led_intensities = kwargs.get('led_intensities', {'a': 180, 'b': 180, 'c': 180, 'd': 180})
        integration_time = kwargs.get('integration_time_ms', 100.0)
        num_scans = kwargs.get('num_scans', 3)

        # Unwrap controller and spectrometer from adapters
        # This is necessary because servo_calibration.py expects raw controller/spectrometer
        raw_controller = self._unwrap_controller(controller)
        raw_spectrometer = self._unwrap_spectrometer(spectrometer)

        if not raw_controller or not raw_spectrometer:
            raise DeviceError("Failed to unwrap controller/spectrometer for calibration")

        try:
            # Run calibration
            result = calibrate_servo_positions_6step(
                ctrl=raw_controller,
                usb=raw_spectrometer,
                led_intensities=led_intensities,
                integration_time_ms=integration_time,
                num_scans=num_scans
            )

            if not result['success']:
                raise DeviceError(f"Servo calibration failed: {result.get('error', 'Unknown error')}")

            # Extract S and P positions
            s_position = result['s_position']
            p_position = result['p_position']

            # Store positions
            self._s_position = s_position
            self._p_position = p_position

            return {
                's_position': s_position,
                'p_position': p_position
            }

        except Exception as e:
            raise DeviceError(f"Servo calibration failed: {e}")

    def get_calibrated_positions(self) -> Optional[Dict[str, int]]:
        """Get previously calibrated S/P positions."""
        if self._s_position is None or self._p_position is None:
            return None

        return {
            's_position': self._s_position,
            'p_position': self._p_position
        }

    def set_calibrated_positions(self, s_position: int, p_position: int) -> None:
        """Set calibrated S/P positions without running full calibration."""
        if not 0 <= s_position <= 255:
            raise ValueError(f"s_position must be 0-255, got {s_position}")
        if not 0 <= p_position <= 255:
            raise ValueError(f"p_position must be 0-255, got {p_position}")

        self._s_position = s_position
        self._p_position = p_position

    # ========================================================================
    # POSITION CONTROL
    # ========================================================================

    def move_to_position(self, position: int, wait: bool = True) -> bool:
        """Move servo to specific position.

        Args:
            position: Target position (0-255 PWM units)
            wait: If True, wait for settling time
        """
        if not self.is_connected():
            raise DeviceError("Servo not connected")

        if not 0 <= position <= 255:
            raise ValueError(f"Position must be 0-255, got {position}")

        # Use controller's servo control
        success = self._controller.set_servo_position(position, save_to_eeprom=False)

        if success and wait:
            # Wait for servo to settle
            time.sleep(0.4)  # Standard settling time

        return success

    def move_to_mode(self, mode: str, wait: bool = True) -> bool:
        """Move servo to calibrated S or P position.

        Args:
            mode: 's' or 'p'
            wait: If True, wait for settling time
        """
        if mode not in ['s', 'p']:
            raise ValueError(f"Mode must be 's' or 'p', got '{mode}'")

        if mode == 's' and self._s_position is None:
            raise DeviceError("S position not calibrated")
        if mode == 'p' and self._p_position is None:
            raise DeviceError("P position not calibrated")

        position = self._s_position if mode == 's' else self._p_position
        return self.move_to_position(position, wait=wait)

    # ========================================================================
    # PRIVATE HELPERS
    # ========================================================================

    def _load_positions_from_eeprom(self) -> None:
        """Load calibrated positions from controller EEPROM."""
        if not self._controller:
            return

        try:
            config = self._controller.read_config_from_eeprom()
            if config:
                self._s_position = config.get('servo_s_position')
                self._p_position = config.get('servo_p_position')
        except Exception:
            pass  # EEPROM read failed, positions remain None

    def _unwrap_controller(self, controller: IController):
        """Extract raw controller from adapter."""
        from affilabs.hardware.controller_adapter import ControllerAdapter

        if isinstance(controller, ControllerAdapter):
            return controller._controller
        return None

    def _unwrap_spectrometer(self, spectrometer: ISpectrometer):
        """Extract raw spectrometer from adapter."""
        from affilabs.hardware.spectrometer_adapter import USB4000Adapter, PhasePhotonicsAdapter

        if isinstance(spectrometer, (USB4000Adapter, PhasePhotonicsAdapter)):
            return spectrometer._spectrometer
        return None


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_servo_adapter(controller: IController) -> ServoAdapter:
    """Factory function to create servo adapter.

    Args:
        controller: Controller instance managing the servo

    Returns:
        ServoAdapter connected to controller
    """
    servo = ServoAdapter()
    servo.connect(controller)
    return servo


