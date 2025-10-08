# Hardware Abstraction Layer (HAL) Implementation

## Overview

The Hardware Abstraction Layer (HAL) provides a unified, device-agnostic interface for SPR instrument hardware components. This implementation addresses the scattered device-specific logic in your current codebase and provides a foundation for supporting multiple hardware types seamlessly.

## Architecture

### Core Components

1. **HAL Interfaces** (`utils/hal/`)
   - `SPRControllerHAL` - Abstract base for SPR controllers
   - `SpectrometerHAL` - Abstract base for spectrometers (placeholder)
   - `KineticSystemHAL` - Abstract base for kinetic systems (placeholder)

2. **Device Implementations**
   - `PicoP4SPRHAL` - Complete implementation for PicoP4SPR controllers
   - Future: `PicoEZSPRHAL`, `USB4000HAL`, etc.

3. **Factory System**
   - `HALFactory` - Creates and manages HAL instances
   - Auto-detection and device discovery
   - Configuration-based device creation

4. **Exception Hierarchy**
   - `HALError` - Base HAL exception
   - `HALConnectionError` - Connection failures
   - `HALTimeoutError` - Operation timeouts
   - `HALConfigurationError` - Configuration issues

## Benefits Achieved

### ✅ **Device Abstraction**
- **Before**: Device-specific `if/elif` chains throughout codebase
- **After**: Single interface for all controller types

```python
# Old approach
if ctrl_name in ["pico_p4spr", "PicoP4SPR"]:
    self.ctrl.turn_on_channel(ch)
elif ctrl_name in ["pico_ezspr", "PicoEZSPR"]:
    self.ctrl.enable_channel(ch)  # Different method name

# HAL approach  
controller.activate_channel(ChannelID.A)  # Same for all devices
```

### ✅ **Consistent Error Handling**
- **Before**: Different error types per device
- **After**: Standardized exception hierarchy

```python
try:
    controller.activate_channel(ChannelID.A)
except HALConnectionError:
    # Handle connection issues
except HALOperationError:
    # Handle operation failures
```

### ✅ **Testing & Simulation**
- **Before**: Required physical hardware for all testing
- **After**: Mock implementations possible

```python
# Create mock controller for testing
mock_controller = MockP4SPRHAL()
# Test application logic without hardware
```

### ✅ **Configuration Management**
- **Before**: Device-specific configuration scattered
- **After**: Unified capability discovery

```python
caps = controller.get_capabilities()
if caps.supports_temperature:
    temp = controller.get_temperature()
```

## Implementation Details

### SPRControllerHAL Interface

The core controller interface provides:

- **Connection Management**: `connect()`, `disconnect()`, `is_connected()`
- **Channel Control**: `activate_channel()`, `validate_channel()`
- **Device Information**: `get_device_info()`, `get_capabilities()`
- **Temperature Monitoring**: `get_temperature()` (if supported)
- **LED Control**: `set_led_intensity()`, `get_led_intensity()` (if supported)
- **Health Monitoring**: `health_check()`, `get_status()`

### PicoP4SPR Implementation

Complete HAL implementation featuring:

- **Auto-detection**: Scans for Pi Pico devices with P4SPR firmware
- **CDC Interface Preference**: Selects proper USB interface automatically
- **Robust Communication**: Retry logic and error handling
- **Capability Declaration**: Accurate feature reporting
- **Temperature Support**: Native temperature sensor integration

### HAL Factory

The factory system provides:

- **Auto-detection**: `create_controller()` without device type
- **Specific Creation**: `create_controller(device_type="PicoP4SPR")`
- **Device Discovery**: `detect_connected_devices()`
- **Capability Queries**: `get_controller_capabilities(device_type)`

## Integration Strategy

### Phase 1: Adapter Pattern (Current)

Use `HALControllerAdapter` to maintain compatibility:

```python
# In HardwareManager or main application
adapter = HALControllerAdapter()
if adapter.connect():
    # Works with both HAL and legacy controllers
    adapter.turn_on_channel('a')
    temp = adapter.get_temp()
```

### Phase 2: Direct Integration

Replace legacy controllers with HAL instances:

```python
# In HardwareManager.py
from utils.hal import HALFactory

class HardwareManager:
    def __init__(self):
        self.controller = None
    
    def connect_controller(self):
        try:
            self.controller = HALFactory.create_controller()
            return True
        except HALError as e:
            logger.error(f"Controller connection failed: {e}")
            return False
```

### Phase 3: Full HAL Ecosystem

Extend to all hardware types:

```python
# Future: Complete HAL integration
controller = HALFactory.create_controller("PicoP4SPR")
spectrometer = HALFactory.create_spectrometer("USB4000")
kinetic_system = HALFactory.create_kinetic_system("CavroKNX")
```

## Usage Examples

### Basic Controller Operation

```python
from utils.hal import HALFactory, ChannelID

# Auto-detect and connect
controller = HALFactory.create_controller()

# Get device information
info = controller.get_device_info()
print(f"Connected to {info['model']} v{info['firmware_version']}")

# Check capabilities
caps = controller.get_capabilities()
print(f"Supports {caps.max_channels} channels")
print(f"Temperature monitoring: {caps.supports_temperature}")

# Activate channel
success = controller.activate_channel(ChannelID.A)
if success:
    print("Channel A activated")

# Read temperature
if caps.supports_temperature:
    temp = controller.get_temperature()
    print(f"Temperature: {temp}°C")

# Cleanup
controller.disconnect()
```

### Configuration-Based Creation

```python
config = {
    "device_type": "PicoP4SPR",
    "connection": {
        "timeout": 5.0,
        "baud_rate": 115200
    },
    "auto_detect": True
}

controller = HALFactory.create_controller_from_config(config)
```

### Device Discovery

```python
# Find all connected devices
devices = HALFactory.detect_connected_devices()
for device in devices:
    print(f"Found: {device['model']} on {device.get('port', 'auto-detected')}")
```

## File Structure

```
utils/hal/
├── __init__.py                 # Package imports
├── hal_exceptions.py           # Exception hierarchy
├── spr_controller_hal.py       # Controller interface
├── pico_p4spr_hal.py          # PicoP4SPR implementation
├── spectrometer_hal.py         # Spectrometer interface (placeholder)
├── kinetic_system_hal.py       # Kinetic system interface (placeholder)
├── hal_factory.py              # Factory for HAL creation
└── integration_example.py      # Integration demonstration
```

## Future Extensions

### Additional Controllers

To add support for new controllers:

1. Create new HAL implementation (e.g., `PicoEZSPRHAL`)
2. Register with factory: `HALFactory.register_controller("PicoEZSPR", PicoEZSPRHAL)`
3. Implement required abstract methods

### Spectrometer HAL

Complete the spectrometer interface:

```python
class USB4000HAL(SpectrometerHAL):
    def capture_spectrum(self, integration_time, averages=1):
        # Implement USB4000-specific logic
        pass
```

### Kinetic System HAL

Complete the kinetic system interface:

```python
class CavroKNXHAL(KineticSystemHAL):
    def control_pump(self, pump_id, flow_rate, direction):
        # Implement Cavro pump control
        pass
```

## Migration Guide

### Current Code Patterns

Replace these patterns:

```python
# OLD: Direct controller access
if self.ctrl and self.ctrl.name == "pico_p4spr":
    success = self.ctrl.turn_on_channel(ch)

# NEW: HAL interface
success = self.hal_controller.activate_channel(channel)
```

### Error Handling Updates

```python
# OLD: Generic exception handling
try:
    self.ctrl.turn_on_channel(ch)
except Exception as e:
    logger.error(f"Channel error: {e}")

# NEW: Specific HAL exceptions
try:
    self.hal_controller.activate_channel(channel)
except HALConnectionError:
    # Handle connection loss
    self._reconnect_controller()
except HALOperationError as e:
    # Handle operation failure
    logger.error(f"Channel activation failed: {e}")
```

### Capability-Driven Logic

```python
# OLD: Device-specific assumptions
if self.device_config["ctrl"] == "PicoP4SPR":
    temp = self.ctrl.get_temp()

# NEW: Capability-driven
caps = self.hal_controller.get_capabilities()
if caps.supports_temperature:
    temp = self.hal_controller.get_temperature()
```

## Testing Strategy

### Unit Tests

```python
def test_channel_activation():
    controller = MockP4SPRHAL()
    assert controller.connect()
    assert controller.activate_channel(ChannelID.A)
    assert controller.get_status().active_channel == ChannelID.A
```

### Integration Tests

```python
def test_auto_detection():
    # Test with various hardware configurations
    devices = HALFactory.detect_connected_devices()
    assert len(devices) >= 0  # May be zero in CI environment
```

### Hardware Simulation

```python
class SimulatedP4SPRHAL(SPRControllerHAL):
    """Simulated controller for testing without hardware."""
    def connect(self):
        return True  # Always succeeds
    
    def activate_channel(self, channel):
        return True  # Simulate success
```

## Performance Considerations

### Connection Efficiency

- **Connection Pooling**: Reuse HAL instances when possible
- **Lazy Loading**: Create HAL instances only when needed
- **Resource Cleanup**: Always call `disconnect()` in finally blocks

### Error Recovery

- **Automatic Reconnection**: HAL can detect connection loss and retry
- **Graceful Degradation**: Fall back to legacy controllers if HAL fails
- **Health Monitoring**: Regular health checks prevent silent failures

## Conclusion

The HAL implementation provides:

1. **Immediate Benefits**: Cleaner code, better error handling, unified interface
2. **Future-Proofing**: Easy addition of new hardware types
3. **Testing Improvements**: Mock hardware for CI/CD and development
4. **Maintainability**: Centralized device logic, reduced code duplication
5. **User Flexibility**: Hardware choice independence from software

The system is designed for gradual adoption - you can start using HAL for new controller instances while maintaining compatibility with existing legacy code through the adapter pattern.

## Next Steps

1. **Test Integration**: Run the integration example to verify HAL functionality
2. **Gradual Migration**: Start using HALControllerAdapter in HardwareManager
3. **Extend Coverage**: Add PicoEZSPR and USB4000 HAL implementations
4. **Performance Testing**: Validate HAL overhead is minimal
5. **Documentation**: Update user documentation to reflect HAL capabilities