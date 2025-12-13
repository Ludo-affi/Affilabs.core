"""Hardware Abstraction Layer

Provides abstract interfaces for all hardware devices with concrete adapters
and mock implementations for testing.

Architecture:
- device_interface.py: Abstract base classes (IController, ISpectrometer, etc.)
- controller_adapter.py: Wraps existing controller.py implementations
- spectrometer_adapter.py: Wraps USB4000/PhasePhotonics implementations
- servo_adapter.py: Wraps servo calibration functionality
- mock_devices.py: Mock implementations for testing without hardware
- device_manager.py: Coordinates multiple devices with lifecycle management

Benefits:
1. Testability: Swap real hardware for mocks in tests
2. Loose coupling: UI/services depend on interfaces, not implementations
3. Hot-swap: Reconnect devices without restart
4. Consistent API: Single interface for different hardware variants
"""

# Abstract interfaces
from affilabs.hardware.device_interface import (
    IController,
    ISpectrometer,
    IServo,
    DeviceCapabilities,
    ControllerCapabilities,
    SpectrometerCapabilities,
    ServoCapabilities,
    ConnectionState,
    DeviceError,
    DeviceInfo
)

# Real hardware adapters
from affilabs.hardware.controller_adapter import (
    ControllerAdapter,
    create_controller_adapter,
    wrap_existing_controller
)

from affilabs.hardware.spectrometer_adapter import (
    USB4000Adapter,
    PhasePhotonicsAdapter,
    create_spectrometer_adapter,
    wrap_existing_spectrometer
)

from affilabs.hardware.servo_adapter import (
    ServoAdapter,
    create_servo_adapter
)

# Mock devices
from affilabs.hardware.mock_devices import (
    MockController,
    MockSpectrometer,
    MockServo,
    create_mock_controller,
    create_mock_spectrometer,
    create_mock_servo,
    create_full_mock_system
)

# Device manager
from affilabs.hardware.device_manager import (
    DeviceManager,
    SystemState,
    DeviceHealth,
    SystemHealth
)

__all__ = [
    # Interfaces
    'IController',
    'ISpectrometer',
    'IServo',
    'DeviceCapabilities',
    'ControllerCapabilities',
    'SpectrometerCapabilities',
    'ServoCapabilities',
    'ConnectionState',
    'DeviceError',
    'DeviceInfo',
    # Real hardware adapters
    'ControllerAdapter',
    'USB4000Adapter',
    'PhasePhotonicsAdapter',
    'ServoAdapter',
    'create_controller_adapter',
    'create_spectrometer_adapter',
    'create_servo_adapter',
    'wrap_existing_controller',
    'wrap_existing_spectrometer',
    # Mock devices
    'MockController',
    'MockSpectrometer',
    'MockServo',
    'create_mock_controller',
    'create_mock_spectrometer',
    'create_mock_servo',
    'create_full_mock_system',
    # Device manager
    'DeviceManager',
    'SystemState',
    'DeviceHealth',
    'SystemHealth',
]


