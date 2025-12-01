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
try:
    from hardware.device_interface import (
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
except ImportError:
    from src.hardware.device_interface import (
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
try:
    from hardware.controller_adapter import (
        ControllerAdapter,
        create_controller_adapter,
        wrap_existing_controller
    )
except ImportError:
    from src.hardware.controller_adapter import (
        ControllerAdapter,
        create_controller_adapter,
        wrap_existing_controller
    )

try:
    from hardware.spectrometer_adapter import (
        USB4000Adapter,
        PhasePhotonicsAdapter,
        create_spectrometer_adapter,
        wrap_existing_spectrometer
    )
except ImportError:
    from src.hardware.spectrometer_adapter import (
        USB4000Adapter,
        PhasePhotonicsAdapter,
        create_spectrometer_adapter,
        wrap_existing_spectrometer
    )

try:
    from hardware.servo_adapter import (
        ServoAdapter,
        create_servo_adapter
    )
except ImportError:
    from src.hardware.servo_adapter import (
        ServoAdapter,
        create_servo_adapter
    )

# Mock devices
try:
    from hardware.mock_devices import (
        MockController,
        MockSpectrometer,
        MockServo,
        create_mock_controller,
        create_mock_spectrometer,
        create_mock_servo,
        create_full_mock_system
    )
except ImportError:
    from src.hardware.mock_devices import (
        MockController,
        MockSpectrometer,
        MockServo,
        create_mock_controller,
        create_mock_spectrometer,
        create_mock_servo,
        create_full_mock_system
    )

# Device manager
try:
    from hardware.device_manager import (
        DeviceManager,
        SystemState,
        DeviceHealth,
        SystemHealth
    )
except ImportError:
    from src.hardware.device_manager import (
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
