"""Mock Hardware Devices

Simulated hardware implementations for testing without physical devices.
All mocks implement the same interfaces as real hardware (IController, ISpectrometer, IServo).
"""

import time
from typing import Optional, Dict, Any
import numpy as np

from .device_interface import (
    IController,
    ISpectrometer,
    IServo,
    DeviceInfo,
    ControllerCapabilities,
    SpectrometerCapabilities,
    ServoCapabilities,
    DeviceError
)


# ============================================================================
# MOCK CONTROLLER
# ============================================================================

class MockController(IController):
    """Mock SPR controller for testing.

    Simulates:
    - LED control (tracks intensities)
    - Polarizer mode switching
    - Servo position control
    - EEPROM configuration
    """

    def __init__(self, model: str = "MockPicoP4SPR"):
        """Initialize mock controller.

        Args:
            model: Mock model name ('MockPicoP4SPR', 'MockPicoEZSPR', etc.)
        """
        self._model = model
        self._connected = False
        self._led_intensities = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
        self._mode = 's'
        self._servo_position = 128
        self._eeprom_config: Optional[Dict[str, Any]] = None
        self._temperature = 25.0  # Mock temperature

    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    def connect(self, **kwargs) -> bool:
        """Connect to mock controller."""
        time.sleep(0.1)  # Simulate connection delay
        self._connected = True
        return True

    def disconnect(self) -> None:
        """Disconnect from mock controller."""
        self._connected = False

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    def get_info(self) -> DeviceInfo:
        """Get device info."""
        return DeviceInfo(
            device_type="controller",
            model=self._model,
            serial_number="MOCK12345",
            firmware_version="1.0.0-mock",
            hardware_version="Rev A",
            port="MOCK_COM1"
        )

    def get_capabilities(self) -> ControllerCapabilities:
        """Get capabilities."""
        is_flow = "EZSPR" in self._model or "KNX" in self._model
        supports_pump = "EZSPR" in self._model

        return ControllerCapabilities(
            num_led_channels=4,
            supports_batch_led_control=True,
            led_intensity_range=(0, 255),
            supports_polarizer=True,
            supports_servo=True,
            supports_pump=supports_pump,
            supports_temperature=True,
            supports_eeprom_config=True,
            is_flow_controller=is_flow
        )

    # ========================================================================
    # LED CONTROL
    # ========================================================================

    def turn_on_channel(self, channel: str) -> bool:
        """Turn on LED channel (set to default intensity)."""
        if channel not in ['a', 'b', 'c', 'd']:
            raise ValueError(f"Invalid channel: {channel}")
        self._led_intensities[channel] = 180  # Default intensity
        return True

    def turn_off_channels(self) -> bool:
        """Turn off all LED channels."""
        self._led_intensities = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
        return True

    def set_intensity(self, channel: str, intensity: int) -> bool:
        """Set LED intensity."""
        if channel not in ['a', 'b', 'c', 'd']:
            raise ValueError(f"Invalid channel: {channel}")
        if not 0 <= intensity <= 255:
            raise ValueError(f"Intensity must be 0-255, got {intensity}")

        self._led_intensities[channel] = intensity
        return True

    def set_batch_intensities(self, a: int = 0, b: int = 0, c: int = 0, d: int = 0) -> bool:
        """Set all LED intensities."""
        self._led_intensities = {'a': a, 'b': b, 'c': c, 'd': d}
        return True

    def get_led_intensities(self) -> Dict[str, int]:
        """Get current LED intensities."""
        return self._led_intensities.copy()

    # ========================================================================
    # POLARIZER CONTROL
    # ========================================================================

    def set_mode(self, mode: str) -> bool:
        """Set polarizer mode."""
        if mode not in ['s', 'p']:
            raise ValueError(f"Mode must be 's' or 'p', got '{mode}'")
        self._mode = mode
        return True

    def get_mode(self) -> str:
        """Get current mode."""
        return self._mode

    def set_servo_position(self, position: int, save_to_eeprom: bool = False) -> bool:
        """Set servo position."""
        if not 0 <= position <= 255:
            raise ValueError(f"Position must be 0-255, got {position}")

        self._servo_position = position

        if save_to_eeprom and self._eeprom_config:
            self._eeprom_config['servo_position'] = position

        return True

    # ========================================================================
    # TEMPERATURE MONITORING
    # ========================================================================

    def get_temperature(self) -> Optional[float]:
        """Get mock temperature."""
        # Add small random variation
        import random
        return self._temperature + random.uniform(-0.5, 0.5)

    # ========================================================================
    # EEPROM CONFIGURATION
    # ========================================================================

    def is_config_valid_in_eeprom(self) -> bool:
        """Check if EEPROM has valid config."""
        return self._eeprom_config is not None

    def read_config_from_eeprom(self) -> Optional[Dict[str, Any]]:
        """Read EEPROM config."""
        return self._eeprom_config.copy() if self._eeprom_config else None

    def write_config_to_eeprom(self, config: Dict[str, Any]) -> bool:
        """Write EEPROM config."""
        self._eeprom_config = config.copy()
        return True


# ============================================================================
# MOCK SPECTROMETER
# ============================================================================

class MockSpectrometer(ISpectrometer):
    """Mock spectrometer for testing.

    Simulates:
    - Wavelength calibration (600-700nm range)
    - Integration time control
    - Spectrum acquisition (Gaussian peak)
    """

    def __init__(self, model: str = "MockUSB4000", num_pixels: int = 3648):
        """Initialize mock spectrometer.

        Args:
            model: Mock model name
            num_pixels: Number of pixels to simulate
        """
        self._model = model
        self._num_pixels = num_pixels
        self._connected = False
        self._integration_time = 100.0  # ms

        # Generate mock wavelength calibration (200-1100nm)
        self._wavelengths = np.linspace(200, 1100, num_pixels)

    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    def connect(self, **kwargs) -> bool:
        """Connect to mock spectrometer."""
        time.sleep(0.2)  # Simulate connection delay
        self._connected = True
        return True

    def disconnect(self) -> None:
        """Disconnect from mock spectrometer."""
        self._connected = False

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    def get_info(self) -> DeviceInfo:
        """Get device info."""
        return DeviceInfo(
            device_type="spectrometer",
            model=self._model,
            serial_number="MOCK_SPEC_001",
            firmware_version="2.0.0-mock",
            hardware_version=None,
            port=None
        )

    def get_capabilities(self) -> SpectrometerCapabilities:
        """Get capabilities."""
        return SpectrometerCapabilities(
            wavelength_range=(200.0, 1100.0),
            wavelength_resolution=0.3,
            num_pixels=self._num_pixels,
            min_integration_time=1.0,
            max_integration_time=10000.0,
            bit_depth=16,
            max_counts=65535,
            supports_dark_correction=True,
            supports_averaging=True,
            max_averages=100,
            backend="mock"
        )

    # ========================================================================
    # WAVELENGTH CALIBRATION
    # ========================================================================

    def get_wavelengths(self) -> np.ndarray:
        """Get wavelength array."""
        return self._wavelengths.copy()

    # ========================================================================
    # INTEGRATION TIME
    # ========================================================================

    def set_integration_time(self, time_ms: float) -> bool:
        """Set integration time."""
        if time_ms < 1.0 or time_ms > 10000.0:
            raise ValueError(f"Integration time must be 1-10000 ms, got {time_ms}")
        self._integration_time = time_ms
        return True

    def get_integration_time(self) -> float:
        """Get integration time."""
        return self._integration_time

    # ========================================================================
    # ACQUISITION
    # ========================================================================

    def read_spectrum(self, num_scans: int = 1) -> Optional[np.ndarray]:
        """Generate mock spectrum.

        Creates a Gaussian peak centered at 640nm with noise.
        """
        if not self._connected:
            return None

        # Simulate acquisition time
        time.sleep(self._integration_time / 1000.0 * num_scans)

        # Generate Gaussian peak at 640nm (SPR resonance)
        center_wl = 640.0
        width = 30.0  # FWHM

        # Calculate Gaussian
        intensities = 20000.0 * np.exp(-0.5 * ((self._wavelengths - center_wl) / width) ** 2)

        # Add baseline
        baseline = 2000.0
        intensities += baseline

        # Add noise
        noise = np.random.normal(0, 100, len(intensities))
        intensities += noise

        # Clip to valid range
        intensities = np.clip(intensities, 0, 65535)

        return intensities.astype(np.uint16)

    def read_intensities(self, num_scans: int = 1) -> Optional[np.ndarray]:
        """Alias for read_spectrum()."""
        return self.read_spectrum(num_scans)


# ============================================================================
# MOCK SERVO
# ============================================================================

class MockServo(IServo):
    """Mock servo for testing.

    Simulates:
    - Position control
    - S/P calibration
    - Settling time
    """

    def __init__(self):
        """Initialize mock servo."""
        self._controller: Optional[IController] = None
        self._connected = False
        self._position = 128
        self._s_position: Optional[int] = None
        self._p_position: Optional[int] = None

    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    def connect(self, controller: IController) -> bool:
        """Connect servo to controller."""
        if not controller.is_connected():
            raise DeviceError("Controller must be connected first")

        self._controller = controller
        self._connected = True

        # Load mock calibration
        self._s_position = 45
        self._p_position = 135

        return True

    def disconnect(self) -> None:
        """Disconnect servo."""
        self._controller = None
        self._connected = False

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected and self._controller is not None

    def get_info(self) -> DeviceInfo:
        """Get device info."""
        return DeviceInfo(
            device_type="servo",
            model="MockHS-55MG",
            serial_number=None,
            firmware_version=None,
            hardware_version=None,
            port=None
        )

    def get_capabilities(self) -> ServoCapabilities:
        """Get capabilities."""
        return ServoCapabilities(
            min_position=5,
            max_position=250,
            settling_time=0.4,
            mode_switch_time=0.15,
            polarizer_type="barrel",
            s_position=self._s_position,
            p_position=self._p_position,
            supports_calibration=True
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
        """Simulate servo calibration.

        Returns mock calibrated positions without running actual calibration.
        """
        # Simulate calibration time
        time.sleep(2.0)

        # Return mock positions
        self._s_position = 45
        self._p_position = 135

        return {
            's_position': self._s_position,
            'p_position': self._p_position
        }

    def get_calibrated_positions(self) -> Optional[Dict[str, int]]:
        """Get calibrated positions."""
        if self._s_position is None or self._p_position is None:
            return None

        return {
            's_position': self._s_position,
            'p_position': self._p_position
        }

    def set_calibrated_positions(self, s_position: int, p_position: int) -> None:
        """Set calibrated positions."""
        self._s_position = s_position
        self._p_position = p_position

    # ========================================================================
    # POSITION CONTROL
    # ========================================================================

    def move_to_position(self, position: int, wait: bool = True) -> bool:
        """Move to position."""
        if not 0 <= position <= 255:
            raise ValueError(f"Position must be 0-255, got {position}")

        self._position = position

        if wait:
            time.sleep(0.4)  # Simulate settling time

        return True

    def move_to_mode(self, mode: str, wait: bool = True) -> bool:
        """Move to calibrated S or P position."""
        if mode not in ['s', 'p']:
            raise ValueError(f"Mode must be 's' or 'p', got '{mode}'")

        if mode == 's' and self._s_position is None:
            raise DeviceError("S position not calibrated")
        if mode == 'p' and self._p_position is None:
            raise DeviceError("P position not calibrated")

        position = self._s_position if mode == 's' else self._p_position
        return self.move_to_position(position, wait=wait)


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_mock_controller(model: str = "MockPicoP4SPR") -> MockController:
    """Create mock controller.

    Args:
        model: 'MockPicoP4SPR', 'MockPicoEZSPR', 'MockKNX2', etc.
    """
    return MockController(model=model)


def create_mock_spectrometer(
    model: str = "MockUSB4000",
    num_pixels: int = 3648
) -> MockSpectrometer:
    """Create mock spectrometer.

    Args:
        model: 'MockUSB4000', 'MockPhasePhotonics', etc.
        num_pixels: Number of pixels to simulate
    """
    return MockSpectrometer(model=model, num_pixels=num_pixels)


def create_mock_servo() -> MockServo:
    """Create mock servo."""
    return MockServo()


def create_full_mock_system() -> Dict[str, Any]:
    """Create complete mock hardware system.

    Returns:
        {
            'controller': MockController (connected),
            'spectrometer': MockSpectrometer (connected),
            'servo': MockServo (connected)
        }
    """
    # Create devices
    controller = create_mock_controller()
    spectrometer = create_mock_spectrometer()
    servo = create_mock_servo()

    # Connect all devices
    controller.connect()
    spectrometer.connect()
    servo.connect(controller)

    return {
        'controller': controller,
        'spectrometer': spectrometer,
        'servo': servo
    }
