"""Controller Hardware Abstraction Layer.

Provides unified interface for all controller types (PicoP4SPR, PicoEZSPR, etc.)
with type-safe capability queries and consistent API.

This is an ADDITIVE layer - does not modify existing controller implementations.
Use create_controller_hal() factory function to wrap existing controller instances.
"""

from __future__ import annotations

from typing import Protocol, Optional, Dict, Any, Tuple


class ControllerHAL(Protocol):
    """Unified controller interface abstracting device-specific implementations.

    Provides:
    - LED control (on/off/intensity/batch operations)
    - Polarizer control (for devices that support it)
    - Type-safe capability queries (eliminates string-based device type checks)
    - Temperature monitoring
    - Pump control (for EZSPR devices)
    """

    # LED Control
    def turn_on_channel(self, ch: str) -> bool:
        """Turn on a specific LED channel.

        Args:
            ch: Channel identifier ('a', 'b', 'c', 'd')

        Returns:
            True if command succeeded
        """
        ...

    def turn_off_channels(self) -> bool:
        """Turn off all LED channels.

        Returns:
            True if command succeeded
        """
        ...

    def set_intensity(self, ch: str, raw_val: int) -> bool:
        """Set LED channel intensity.

        Args:
            ch: Channel identifier ('a', 'b', 'c', 'd')
            raw_val: Intensity value (0-255)

        Returns:
            True if command succeeded
        """
        ...

    def set_batch_intensities(self, a: int = 0, b: int = 0, c: int = 0, d: int = 0) -> bool:
        """Set all LED intensities in a single batch command (if supported).

        Falls back to sequential commands for controllers without batch support.

        Args:
            a: Intensity for LED A (0-255)
            b: Intensity for LED B (0-255)
            c: Intensity for LED C (0-255)
            d: Intensity for LED D (0-255)

        Returns:
            True if all commands succeeded
        """
        ...

    # Polarizer Control
    def set_mode(self, mode: str) -> bool:
        """Set polarizer mode.

        Args:
            mode: 's' for S-polarization, 'p' for P-polarization

        Returns:
            True if command succeeded (False if polarizer not supported)
        """
        ...

    def get_polarizer_position(self) -> Dict[str, Any]:
        """Get current polarizer position.

        Returns:
            Dictionary with 's' and 'p' positions, or empty dict if not supported
        """
        ...

    # Device Info & Capabilities
    def get_device_type(self) -> str:
        """Get the underlying device type string.

        Returns:
            Device type: 'PicoP4SPR', 'PicoEZSPR', 'QSPR', 'Arduino', 'Kinetic'
        """
        ...

    def get_firmware_version(self) -> str:
        """Get firmware version if available.

        Returns:
            Version string (e.g., 'V1.4') or empty string if not available
        """
        ...

    def get_temperature(self) -> float:
        """Get device temperature in Celsius.

        Returns:
            Temperature in °C, or -1 if not supported
        """
        ...

    # Type-safe capability queries (eliminates string-based device checks)
    @property
    def supports_polarizer(self) -> bool:
        """Check if device has polarizer control capability."""
        ...

    @property
    def supports_batch_leds(self) -> bool:
        """Check if device supports batch LED intensity commands."""
        ...

    @property
    def supports_pump(self) -> bool:
        """Check if device has pump control capability (EZSPR only)."""
        ...

    @property
    def supports_firmware_update(self) -> bool:
        """Check if device supports firmware updates."""
        ...

    @property
    def channel_count(self) -> int:
        """Get number of LED channels (typically 4)."""
        ...

    # Pump Control (EZSPR-specific)
    def get_pump_corrections(self) -> Optional[Tuple[float, float]]:
        """Get pump correction factors (EZSPR only).

        Returns:
            Tuple of (pump1_correction, pump2_correction) or None if not supported
        """
        ...

    def set_pump_corrections(self, pump_1_correction: float, pump_2_correction: float) -> bool:
        """Set pump correction factors (EZSPR only).

        Args:
            pump_1_correction: Correction factor for pump 1
            pump_2_correction: Correction factor for pump 2

        Returns:
            True if command succeeded (False if not supported)
        """
        ...

    # Connection Management
    def open(self) -> bool:
        """Open connection to controller.

        Returns:
            True if connection established
        """
        ...

    def close(self) -> None:
        """Close connection to controller."""
        ...

    def is_connected(self) -> bool:
        """Check if controller is connected and ready.

        Returns:
            True if device is connected and operational
        """
        ...


class PicoP4SPRAdapter:
    """Adapter wrapping PicoP4SPR controller to provide ControllerHAL interface."""

    def __init__(self, controller):
        """Initialize adapter with existing PicoP4SPR controller instance.

        Args:
            controller: PicoP4SPR instance from utils.controller
        """
        self._ctrl = controller
        self._device_type = "PicoP4SPR"

    # LED Control
    def turn_on_channel(self, ch: str) -> bool:
        return self._ctrl.turn_on_channel(ch) or False

    def turn_off_channels(self) -> bool:
        return self._ctrl.turn_off_channels() or False

    def set_intensity(self, ch: str, raw_val: int) -> bool:
        return self._ctrl.set_intensity(ch, raw_val) or False

    def set_batch_intensities(self, a: int = 0, b: int = 0, c: int = 0, d: int = 0) -> bool:
        # PicoP4SPR supports batch command
        return self._ctrl.set_batch_intensities(a=a, b=b, c=c, d=d)

    # Polarizer Control
    def set_mode(self, mode: str) -> bool:
        return self._ctrl.set_mode(mode) or False

    def get_polarizer_position(self) -> Dict[str, Any]:
        try:
            return self._ctrl.servo_get()
        except:
            return {}

    # Device Info & Capabilities
    def get_device_type(self) -> str:
        return self._device_type

    def get_firmware_version(self) -> str:
        return getattr(self._ctrl, 'version', '')

    def get_temperature(self) -> float:
        try:
            return self._ctrl.get_temp()
        except:
            return -1.0

    # Capability queries
    @property
    def supports_polarizer(self) -> bool:
        return True  # P4SPR has polarizer

    @property
    def supports_batch_leds(self) -> bool:
        return True  # P4SPR has batch command

    @property
    def supports_pump(self) -> bool:
        return False  # P4SPR does not have pump

    @property
    def supports_firmware_update(self) -> bool:
        return False  # P4SPR firmware update not implemented

    @property
    def channel_count(self) -> int:
        return 4

    # Pump Control (not supported)
    def get_pump_corrections(self) -> Optional[Tuple[float, float]]:
        return None

    def set_pump_corrections(self, pump_1_correction: float, pump_2_correction: float) -> bool:
        return False

    # Connection Management
    def open(self) -> bool:
        return self._ctrl.open()

    def close(self) -> None:
        self._ctrl.close()

    def is_connected(self) -> bool:
        return self._ctrl._ser is not None and self._ctrl._ser.is_open


class PicoEZSPRAdapter:
    """Adapter wrapping PicoEZSPR controller to provide ControllerHAL interface."""

    def __init__(self, controller):
        """Initialize adapter with existing PicoEZSPR controller instance.

        Args:
            controller: PicoEZSPR instance from utils.controller
        """
        self._ctrl = controller
        self._device_type = "PicoEZSPR"

    # LED Control
    def turn_on_channel(self, ch: str) -> bool:
        return self._ctrl.turn_on_channel(ch) or False

    def turn_off_channels(self) -> bool:
        return self._ctrl.turn_off_channels() or False

    def set_intensity(self, ch: str, raw_val: int) -> bool:
        return self._ctrl.set_intensity(ch, raw_val) or False

    def set_batch_intensities(self, a: int = 0, b: int = 0, c: int = 0, d: int = 0) -> bool:
        # EZSPR doesn't have batch command - fall back to sequential
        success = True
        if a > 0:
            success &= self.set_intensity('a', a)
        if b > 0:
            success &= self.set_intensity('b', b)
        if c > 0:
            success &= self.set_intensity('c', c)
        if d > 0:
            success &= self.set_intensity('d', d)
        return success

    # Polarizer Control
    def set_mode(self, mode: str) -> bool:
        return False  # EZSPR does not have polarizer

    def get_polarizer_position(self) -> Dict[str, Any]:
        return {}  # No polarizer support

    # Device Info & Capabilities
    def get_device_type(self) -> str:
        return self._device_type

    def get_firmware_version(self) -> str:
        return getattr(self._ctrl, 'version', '')

    def get_temperature(self) -> float:
        return -1.0  # EZSPR doesn't have temp sensor

    # Capability queries
    @property
    def supports_polarizer(self) -> bool:
        return False  # EZSPR does not have polarizer

    @property
    def supports_batch_leds(self) -> bool:
        return False  # EZSPR doesn't have batch command

    @property
    def supports_pump(self) -> bool:
        return True  # EZSPR has pump control

    @property
    def supports_firmware_update(self) -> bool:
        return True  # EZSPR supports firmware updates

    @property
    def channel_count(self) -> int:
        return 4

    # Pump Control
    def get_pump_corrections(self) -> Optional[Tuple[float, float]]:
        return self._ctrl.get_pump_corrections()

    def set_pump_corrections(self, pump_1_correction: float, pump_2_correction: float) -> bool:
        return self._ctrl.set_pump_corrections(pump_1_correction, pump_2_correction)

    # Connection Management
    def open(self) -> bool:
        return self._ctrl.open()

    def close(self) -> None:
        self._ctrl.close()

    def is_connected(self) -> bool:
        return self._ctrl.valid()


class QSPRAdapter:
    """Adapter wrapping QSPR controller to provide ControllerHAL interface."""

    def __init__(self, controller):
        """Initialize adapter with existing QSPRController instance.

        Args:
            controller: QSPRController instance from utils.controller
        """
        self._ctrl = controller
        self._device_type = "QSPR"

    # LED Control
    def turn_on_channel(self, ch: str) -> bool:
        return self._ctrl.turn_on_channel(ch) or False

    def turn_off_channels(self) -> bool:
        return self._ctrl.turn_off_channels() or False

    def set_intensity(self, ch: str, raw_val: int) -> bool:
        return self._ctrl.set_intensity(ch, raw_val) or False

    def set_batch_intensities(self, a: int = 0, b: int = 0, c: int = 0, d: int = 0) -> bool:
        # QSPR doesn't have batch command - fall back to sequential
        success = True
        if a > 0:
            success &= self.set_intensity('a', a)
        if b > 0:
            success &= self.set_intensity('b', b)
        if c > 0:
            success &= self.set_intensity('c', c)
        if d > 0:
            success &= self.set_intensity('d', d)
        return success

    # Polarizer Control
    def set_mode(self, mode: str) -> bool:
        return False  # QSPR does not have polarizer

    def get_polarizer_position(self) -> Dict[str, Any]:
        return {}

    # Device Info & Capabilities
    def get_device_type(self) -> str:
        return self._device_type

    def get_firmware_version(self) -> str:
        return ''

    def get_temperature(self) -> float:
        return -1.0

    # Capability queries
    @property
    def supports_polarizer(self) -> bool:
        return False

    @property
    def supports_batch_leds(self) -> bool:
        return False

    @property
    def supports_pump(self) -> bool:
        return False

    @property
    def supports_firmware_update(self) -> bool:
        return False

    @property
    def channel_count(self) -> int:
        return 4

    # Pump Control (not supported)
    def get_pump_corrections(self) -> Optional[Tuple[float, float]]:
        return None

    def set_pump_corrections(self, pump_1_correction: float, pump_2_correction: float) -> bool:
        return False

    # Connection Management
    def open(self) -> bool:
        return self._ctrl.open()

    def close(self) -> None:
        self._ctrl.close()

    def is_connected(self) -> bool:
        return self._ctrl._ser is not None and self._ctrl._ser.is_open


class ArduinoAdapter:
    """Adapter wrapping Arduino controller to provide ControllerHAL interface."""

    def __init__(self, controller):
        """Initialize adapter with existing ArduinoController instance.

        Args:
            controller: ArduinoController instance from utils.controller
        """
        self._ctrl = controller
        self._device_type = "Arduino"

    # LED Control
    def turn_on_channel(self, ch: str) -> bool:
        return self._ctrl.turn_on_channel(ch) or False

    def turn_off_channels(self) -> bool:
        return self._ctrl.turn_off_channels() or False

    def set_intensity(self, ch: str, raw_val: int) -> bool:
        # Arduino has basic LED control but intensity may not be supported
        return False

    def set_batch_intensities(self, a: int = 0, b: int = 0, c: int = 0, d: int = 0) -> bool:
        return False

    # Polarizer Control
    def set_mode(self, mode: str) -> bool:
        return False

    def get_polarizer_position(self) -> Dict[str, Any]:
        return {}

    # Device Info & Capabilities
    def get_device_type(self) -> str:
        return self._device_type

    def get_firmware_version(self) -> str:
        return ''

    def get_temperature(self) -> float:
        return -1.0

    # Capability queries
    @property
    def supports_polarizer(self) -> bool:
        return False

    @property
    def supports_batch_leds(self) -> bool:
        return False

    @property
    def supports_pump(self) -> bool:
        return False

    @property
    def supports_firmware_update(self) -> bool:
        return False

    @property
    def channel_count(self) -> int:
        return 4

    # Pump Control (not supported)
    def get_pump_corrections(self) -> Optional[Tuple[float, float]]:
        return None

    def set_pump_corrections(self, pump_1_correction: float, pump_2_correction: float) -> bool:
        return False

    # Connection Management
    def open(self) -> bool:
        return self._ctrl.open()

    def close(self) -> None:
        self._ctrl.close()

    def is_connected(self) -> bool:
        return self._ctrl._ser is not None and self._ctrl._ser.is_open


class KineticAdapter:
    """Adapter wrapping Kinetic controller to provide ControllerHAL interface."""

    def __init__(self, controller):
        """Initialize adapter with existing KineticController instance.

        Args:
            controller: KineticController instance from utils.controller
        """
        self._ctrl = controller
        self._device_type = "Kinetic"

    # LED Control
    def turn_on_channel(self, ch: str) -> bool:
        return self._ctrl.turn_on_channel(ch) or False

    def turn_off_channels(self) -> bool:
        return self._ctrl.turn_off_channels() or False

    def set_intensity(self, ch: str, raw_val: int) -> bool:
        return self._ctrl.set_intensity(ch, raw_val) or False

    def set_batch_intensities(self, a: int = 0, b: int = 0, c: int = 0, d: int = 0) -> bool:
        # Kinetic doesn't have batch command
        success = True
        if a > 0:
            success &= self.set_intensity('a', a)
        if b > 0:
            success &= self.set_intensity('b', b)
        if c > 0:
            success &= self.set_intensity('c', c)
        if d > 0:
            success &= self.set_intensity('d', d)
        return success

    # Polarizer Control
    def set_mode(self, mode: str) -> bool:
        return False

    def get_polarizer_position(self) -> Dict[str, Any]:
        return {}

    # Device Info & Capabilities
    def get_device_type(self) -> str:
        return self._device_type

    def get_firmware_version(self) -> str:
        return ''

    def get_temperature(self) -> float:
        return -1.0

    # Capability queries
    @property
    def supports_polarizer(self) -> bool:
        return False

    @property
    def supports_batch_leds(self) -> bool:
        return False

    @property
    def supports_pump(self) -> bool:
        return False

    @property
    def supports_firmware_update(self) -> bool:
        return False

    @property
    def channel_count(self) -> int:
        return 4

    # Pump Control (not supported)
    def get_pump_corrections(self) -> Optional[Tuple[float, float]]:
        return None

    def set_pump_corrections(self, pump_1_correction: float, pump_2_correction: float) -> bool:
        return False

    # Connection Management
    def open(self) -> bool:
        return self._ctrl.open()

    def close(self) -> None:
        self._ctrl.close()

    def is_connected(self) -> bool:
        return self._ctrl._ser is not None and self._ctrl._ser.is_open


def create_controller_hal(controller) -> ControllerHAL:
    """Factory function to create appropriate HAL adapter for a controller instance.

    This is the main entry point for using the Controller HAL. Pass any existing
    controller instance and get back a ControllerHAL interface with type-safe
    capability queries.

    Args:
        controller: Controller instance (PicoP4SPR, PicoEZSPR, QSPR, Arduino, Kinetic)

    Returns:
        ControllerHAL adapter wrapping the controller

    Raises:
        ValueError: If controller type is not recognized

    Example:
        from utils.controller import PicoP4SPR
        from utils.hal.controller_hal import create_controller_hal

        # Create controller normally
        ctrl = PicoP4SPR()
        ctrl.open()

        # Wrap with HAL for type-safe access
        hal = create_controller_hal(ctrl)

        # Type-safe capability check (no more string matching!)
        if hal.supports_polarizer:
            hal.set_mode('s')

        # Use batch commands if available
        if hal.supports_batch_leds:
            hal.set_batch_intensities(a=255, b=128, c=64, d=0)
    """
    controller_name = controller.name if hasattr(controller, 'name') else type(controller).__name__

    # Map controller name to adapter class
    adapter_map = {
        'pico_p4spr': PicoP4SPRAdapter,
        'PicoP4SPR': PicoP4SPRAdapter,
        'pico_ezspr': PicoEZSPRAdapter,
        'PicoEZSPR': PicoEZSPRAdapter,
        'qspr': QSPRAdapter,
        'QSPRController': QSPRAdapter,
        'p4spr': ArduinoAdapter,  # Arduino uses 'p4spr' as name
        'ArduinoController': ArduinoAdapter,
        'kinetic': KineticAdapter,
        'KineticController': KineticAdapter,
        'KNX2': KineticAdapter,  # KineticController uses 'KNX2' as name
        'EZSPR': PicoEZSPRAdapter,  # Legacy EZSPR name
        'KNX': KineticAdapter,  # Legacy KNX name
    }

    adapter_class = adapter_map.get(controller_name)
    if adapter_class is None:
        raise ValueError(f"Unknown controller type: {controller_name}")

    return adapter_class(controller)
