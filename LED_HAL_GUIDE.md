# LED Hardware Abstraction Layer (HAL)

## Overview

The LED HAL provides a unified interface for LED control with support for both individual commands (backward compatible) and optimized batch commands (new feature).

## Key Features

- ✅ **Backward Compatible**: All existing code continues to work unchanged
- ⚡ **Batch Commands**: 100-200x faster LED setup when supported by hardware
- 🔌 **Multi-Controller**: Works with Pico, Arduino, and other controller types
- 🛡️ **Auto-Fallback**: Automatically uses sequential commands if batch not supported

## Performance Comparison

### Benchmark Results (Pico P4SPR Controller)

```
Operation: Set mode + 4 channel intensities

Sequential: 808.28 ms  (5 separate serial commands)
Batch:        4.91 ms  (1 combined serial command)
Speedup:    164.7x faster ⚡
```

## Architecture

### Components

1. **`utils/hal/interfaces.py`** - Protocol definitions
   - `LEDController` - Interface all LED controllers must implement
   - `LEDCommand` - Data class representing a single LED operation

2. **`utils/hal/adapters.py`** - Implementation
   - `CtrlLEDAdapter` - Wraps existing controller classes with HAL interface
   - Automatically detects controller capabilities
   - Optimizes batch commands for Pico controllers

3. **`utils/led_batch.py`** - Convenience utilities
   - `LEDBatchBuilder` - Fluent interface for building command batches
   - Helper functions for common patterns

## Usage Examples

### Example 1: Builder Pattern (Recommended)

```python
from utils.led_batch import LEDBatchBuilder

# Create and execute a batch of commands
batch = LEDBatchBuilder()
batch.set_mode('s')\
     .set_intensity('a', 180)\
     .set_intensity('b', 200)\
     .set_intensity('c', 150)\
     .set_intensity('d', 100)\
     .execute(led_controller)
```

### Example 2: Helper Function

```python
from utils.led_batch import create_calibration_batch

# Setup all channels for calibration
commands = create_calibration_batch('p', {
    'a': 180,
    'b': 200,
    'c': 150,
    'd': 100
})
led_controller.execute_batch(commands)
```

### Example 3: Manual Command List

```python
from utils.hal.interfaces import LEDCommand

# Build custom command sequence
commands = [
    LEDCommand('mode', mode='s'),
    LEDCommand('intensity', channel='a', intensity=180),
    LEDCommand('intensity', channel='b', intensity=200),
]
led_controller.execute_batch(commands)
```

### Example 4: Check Capabilities

```python
# Check if batch commands are supported
caps = led_controller.get_capabilities()

if caps.get('supports_batch', False):
    # Use optimized batch
    batch = LEDBatchBuilder()
    batch.set_mode('s').set_intensity('a', 180).execute(led_controller)
else:
    # Fall back to individual commands
    led_controller.set_mode('s')
    led_controller.set_intensity('a', 180)
```

## Integration in Application

### Current Usage (Still Works)

The existing application code doesn't need to change:

```python
# Old code still works exactly as before
led_controller.set_mode('s')
led_controller.set_intensity('a', 180)
led_controller.turn_on_channel('a')
led_controller.turn_off_channels()
```

### Optimized Usage (Recommended for New Code)

When setting up multiple LED parameters before acquisition:

```python
from utils.led_batch import LEDBatchBuilder

# Before starting acquisition cycle, set all LED parameters at once
batch = LEDBatchBuilder()
batch.set_mode(self.current_mode)

for ch in ['a', 'b', 'c', 'd']:
    intensity = self.channel_intensities.get(ch, 255)
    batch.set_intensity(ch, intensity)

batch.execute(self.led_controller)

# Then proceed with individual channel acquisitions
for ch in acquisition_channels:
    self.led_controller.turn_on_channel(ch)
    # ... acquire spectrum ...
    self.led_controller.turn_off_channels()
```

## Protocol Details

### Pico Batch Command Format

```
lb<mode><default_intensity><ch_a><int_a><ch_b><int_b><ch_c><int_c><ch_d><int_d>\n
```

**Example:**
```
lbs255a180b200c150d100\n
```
- `lb` - Batch LED command
- `s` - S-polarized mode
- `255` - Default intensity (unused but required)
- `a180` - Channel A intensity 180
- `b200` - Channel B intensity 200
- `c150` - Channel C intensity 150
- `d100` - Channel D intensity 100

**Response:**
- `1` - Success
- Other - Failure

### Controller Support Matrix

| Controller | Batch Support | Protocol |
|-----------|---------------|----------|
| PicoP4SPR | ✅ Yes | `lb` command |
| PicoEZSPR | ✅ Yes | `lb` command |
| Arduino   | ❌ No | Sequential only |

## Testing

Run the test script to verify functionality:

```bash
python test_led_batch.py
```

This will:
1. Detect connected controller
2. Check capabilities
3. Test batch commands
4. Compare performance vs sequential
5. Validate responses

## Implementation Notes

### Auto-Fallback Logic

The adapter automatically handles fallback:

```python
def execute_batch(self, commands):
    # 1. Check if controller supports batch (Pico variants)
    # 2. Analyze commands to see if batch is beneficial
    # 3. If yes, send optimized batch command
    # 4. If no, execute sequentially
    # 5. If batch fails, fall back to sequential
```

### When Batch is Used

Batch optimization triggers when:
- Controller type contains "Pico" (PicoP4SPR, PicoEZSPR)
- Commands include mode change + 2+ intensity changes
- Serial connection is available

### Thread Safety

The adapter respects controller locking:

```python
if hasattr(self._ctrl, '_lock'):
    with self._ctrl._lock:
        # Send command
```

## Migration Guide

### For New Features

When adding new LED control features, prefer batch commands:

```python
# OLD (slow)
def setup_calibration(self):
    self.led_controller.set_mode('s')
    self.led_controller.set_intensity('a', 180)
    self.led_controller.set_intensity('b', 200)
    # ... etc (5 serial commands, ~1000ms)

# NEW (fast)
def setup_calibration(self):
    from utils.led_batch import create_calibration_batch
    commands = create_calibration_batch('s', {
        'a': 180, 'b': 200, 'c': 150, 'd': 100
    })
    self.led_controller.execute_batch(commands)
    # (1 serial command, ~5ms)
```

### For Existing Code

No changes required! The HAL is backward compatible.

If you want to optimize existing sequential LED setup code:
1. Identify sections where multiple LED parameters are set
2. Replace with batch builder pattern
3. Test performance improvement

## Future Enhancements

Potential improvements:
- [ ] Add batch support for other controller types
- [ ] Extend batch commands to include turn_on/turn_off
- [ ] Cache LED state to avoid redundant commands
- [ ] Add LED state validation/readback
- [ ] Implement LED command queuing for async operation

## See Also

- `utils/hal/interfaces.py` - Protocol definitions
- `utils/hal/adapters.py` - Implementation
- `utils/led_batch.py` - Convenience builders
- `test_led_batch.py` - Test suite and examples
