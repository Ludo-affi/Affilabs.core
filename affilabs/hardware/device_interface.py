"""Device Interface Abstractions

Abstract base classes defining contracts for hardware devices.
All concrete implementations (real hardware or mocks) must implement these interfaces.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import numpy as np

# ============================================================================
# ENUMS
# ============================================================================


class ConnectionState(Enum):
    """Device connection state."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


# ============================================================================
# EXCEPTIONS
# ============================================================================


class DeviceError(Exception):
    """Base exception for hardware device errors."""


class ConnectionError(DeviceError):
    """Device connection failed."""


class CommandError(DeviceError):
    """Hardware command failed."""


class TimeoutError(DeviceError):
    """Operation timed out."""


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class DeviceInfo:
    """General device identification."""

    device_type: str  # "controller", "spectrometer", "servo", "pump"
    model: str  # "PicoP4SPR", "USB4000", etc.
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    hardware_version: Optional[str] = None
    port: Optional[str] = None  # COM port or USB address


@dataclass
class DeviceCapabilities:
    """Base capabilities all devices share."""

    supports_reconnect: bool = True
    supports_firmware_update: bool = False
    requires_calibration: bool = False


@dataclass
class ControllerCapabilities(DeviceCapabilities):
    """SPR controller capabilities."""

    # LED control
    num_led_channels: int = 4
    supports_batch_led_control: bool = True
    led_intensity_range: tuple[int, int] = (0, 255)

    # Polarizer control
    supports_polarizer: bool = True
    supports_servo: bool = True

    # Pump control
    supports_pump: bool = False

    # Temperature monitoring
    supports_temperature: bool = False

    # EEPROM configuration
    supports_eeprom_config: bool = True

    # Device variant
    is_flow_controller: bool = False  # True for EZSPR, False for P4SPR


@dataclass
class SpectrometerCapabilities(DeviceCapabilities):
    """Spectrometer capabilities."""

    # Wavelength range
    wavelength_range: tuple[float, float] = (200.0, 1100.0)  # nm
    wavelength_resolution: float = 0.3  # nm
    num_pixels: int = 3648

    # Integration time
    min_integration_time: float = 1.0  # milliseconds
    max_integration_time: float = 10000.0  # milliseconds

    # Detection
    bit_depth: int = 16
    max_counts: int = 65535
    supports_dark_correction: bool = True
    supports_averaging: bool = True
    max_averages: int = 100

    # Backend
    backend: str = "seabreeze"  # "seabreeze" or "phase_photonics"


@dataclass
class ServoCapabilities(DeviceCapabilities):
    """Servo/polarizer capabilities."""

    # Position range
    min_position: int = 0
    max_position: int = 255  # PWM units

    # Timing
    settling_time: float = 0.4  # seconds
    mode_switch_time: float = 0.15  # seconds

    # Polarizer
    polarizer_type: Optional[str] = None  # "barrel" or "round"
    s_position: Optional[int] = None
    p_position: Optional[int] = None

    # Calibration
    supports_calibration: bool = True


# ============================================================================
# ABSTRACT INTERFACES
# ============================================================================


class IController(ABC):
    """Abstract interface for SPR controllers.

    Supports all controller variants:
    - Static controllers: ArduinoController, PicoP4SPR
    - Flow controllers: PicoEZSPR, KineticController, PicoKNX2
    """

    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    @abstractmethod
    def connect(self, **kwargs) -> bool:
        """Connect to controller.

        Args:
            **kwargs: Connection parameters (port, timeout, etc.)

        Returns:
            True if connection successful

        Raises:
            ConnectionError: If connection fails

        """

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from controller. Should never raise."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if controller is connected and responsive."""

    @abstractmethod
    def get_info(self) -> DeviceInfo:
        """Get device identification information."""

    @abstractmethod
    def get_capabilities(self) -> ControllerCapabilities:
        """Get device capabilities."""

    # ========================================================================
    # LED CONTROL
    # ========================================================================

    @abstractmethod
    def turn_on_channel(self, channel: str) -> bool:
        """Turn on specific LED channel.

        Args:
            channel: 'a', 'b', 'c', or 'd'

        Returns:
            True if command succeeded

        """

    @abstractmethod
    def turn_off_channels(self) -> bool:
        """Turn off all LED channels.

        Returns:
            True if command succeeded

        """

    @abstractmethod
    def set_intensity(self, channel: str, intensity: int) -> bool:
        """Set LED channel intensity.

        Args:
            channel: 'a', 'b', 'c', or 'd'
            intensity: 0-255

        Returns:
            True if command succeeded

        """

    @abstractmethod
    def set_batch_intensities(
        self,
        a: int = 0,
        b: int = 0,
        c: int = 0,
        d: int = 0,
    ) -> bool:
        """Set all LED intensities in batch.

        Uses single command if supported, otherwise sequential commands.

        Args:
            a, b, c, d: Intensities 0-255

        Returns:
            True if all commands succeeded

        """

    @abstractmethod
    def get_led_intensities(self) -> dict[str, int]:
        """Get current LED intensities.

        Returns:
            {'a': 0-255, 'b': 0-255, 'c': 0-255, 'd': 0-255}

        """

    # ========================================================================
    # POLARIZER CONTROL
    # ========================================================================

    @abstractmethod
    def set_mode(self, mode: str) -> bool:
        """Set polarizer mode.

        Args:
            mode: 's' for S-polarization, 'p' for P-polarization

        Returns:
            True if command succeeded

        """

    @abstractmethod
    def get_mode(self) -> str:
        """Get current polarizer mode.

        Returns:
            's' or 'p'

        """

    @abstractmethod
    def set_servo_position(self, position: int, save_to_eeprom: bool = False) -> bool:
        """Set servo position (calibration only).

        Args:
            position: 0-255 PWM units
            save_to_eeprom: If True, save position to EEPROM

        Returns:
            True if command succeeded

        """

    # ========================================================================
    # TEMPERATURE MONITORING
    # ========================================================================

    @abstractmethod
    def get_temperature(self) -> Optional[float]:
        """Get controller temperature in Celsius.

        Returns:
            Temperature or None if not supported

        """

    # ========================================================================
    # EEPROM CONFIGURATION
    # ========================================================================

    @abstractmethod
    def is_config_valid_in_eeprom(self) -> bool:
        """Check if valid configuration exists in EEPROM."""

    @abstractmethod
    def read_config_from_eeprom(self) -> Optional[dict]:
        """Read device configuration from EEPROM.

        Returns:
            Configuration dict or None if not available

        """

    @abstractmethod
    def write_config_to_eeprom(self, config: dict[str, Any]) -> bool:
        """Write device configuration to EEPROM.

        Args:
            config: Configuration dictionary

        Returns:
            True if successful

        """


class ISpectrometer(ABC):
    """Abstract interface for spectrometers.

    Supports:
    - Ocean Optics USB4000/FLAME-T (via SeaBreeze)
    - Phase Photonics (custom driver)
    """

    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    @abstractmethod
    def connect(self, **kwargs) -> bool:
        """Connect to spectrometer.

        Args:
            **kwargs: Connection parameters (serial_number, timeout, etc.)

        Returns:
            True if connection successful

        Raises:
            ConnectionError: If connection fails

        """

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from spectrometer. Should never raise."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if spectrometer is connected and responsive."""

    @abstractmethod
    def get_info(self) -> DeviceInfo:
        """Get device identification information."""

    @abstractmethod
    def get_capabilities(self) -> SpectrometerCapabilities:
        """Get device capabilities."""

    # ========================================================================
    # WAVELENGTH CALIBRATION
    # ========================================================================

    @abstractmethod
    def get_wavelengths(self) -> np.ndarray:
        """Get wavelength calibration array.

        Returns:
            Wavelengths in nanometers (one per pixel)

        """

    # ========================================================================
    # INTEGRATION TIME
    # ========================================================================

    @abstractmethod
    def set_integration_time(self, time_ms: float) -> bool:
        """Set integration time.

        Args:
            time_ms: Integration time in milliseconds

        Returns:
            True if command succeeded

        """

    @abstractmethod
    def get_integration_time(self) -> float:
        """Get current integration time in milliseconds."""

    # ========================================================================
    # ACQUISITION
    # ========================================================================

    @abstractmethod
    def read_spectrum(self, num_scans: int = 1) -> Optional[np.ndarray]:
        """Capture and return spectrum.

        Args:
            num_scans: Number of scans to average (default 1)

        Returns:
            Intensity array or None on error

        """

    @abstractmethod
    def read_intensities(self, num_scans: int = 1) -> Optional[np.ndarray]:
        """Alias for read_spectrum() for compatibility."""


class IServo(ABC):
    """Abstract interface for servo/polarizer control.

    Handles servo calibration and position management.
    """

    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    @abstractmethod
    def connect(self, controller: IController) -> bool:
        """Connect servo to controller.

        Args:
            controller: Controller instance managing the servo

        Returns:
            True if connection successful

        """

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect servo. Should never raise."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if servo is connected."""

    @abstractmethod
    def get_info(self) -> DeviceInfo:
        """Get device identification information."""

    @abstractmethod
    def get_capabilities(self) -> ServoCapabilities:
        """Get servo capabilities."""

    # ========================================================================
    # CALIBRATION
    # ========================================================================

    @abstractmethod
    def calibrate(
        self,
        spectrometer: ISpectrometer,
        controller: IController,
        **kwargs,
    ) -> dict[str, int]:
        """Calibrate servo positions for S and P polarization.

        Args:
            spectrometer: Spectrometer for measurements
            controller: Controller managing LEDs and servo
            **kwargs: Calibration parameters (led_intensities, integration_time, etc.)

        Returns:
            {'s_position': 0-255, 'p_position': 0-255}

        Raises:
            DeviceError: If calibration fails

        """

    @abstractmethod
    def get_calibrated_positions(self) -> Optional[dict]:
        """Get previously calibrated S/P positions.

        Returns:
            {'s_position': 0-255, 'p_position': 0-255} or None if not calibrated

        """

    @abstractmethod
    def set_calibrated_positions(self, s_position: int, p_position: int) -> None:
        """Set calibrated S/P positions without running full calibration.

        Args:
            s_position: S-polarization servo position (0-255)
            p_position: P-polarization servo position (0-255)

        """

    # ========================================================================
    # POSITION CONTROL
    # ========================================================================

    @abstractmethod
    def move_to_position(self, position: int, wait: bool = True) -> bool:
        """Move servo to specific position.

        Args:
            position: Target position (0-255 PWM units)
            wait: If True, wait for settling time

        Returns:
            True if command succeeded

        """

    @abstractmethod
    def move_to_mode(self, mode: str, wait: bool = True) -> bool:
        """Move servo to calibrated S or P position.

        Args:
            mode: 's' or 'p'
            wait: If True, wait for settling time

        Returns:
            True if command succeeded

        Raises:
            DeviceError: If positions not calibrated

        """
