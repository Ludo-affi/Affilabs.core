# Cavro Pump Manager Documentation

## Overview

The `CavroPumpManager` class provides a high-level abstraction for controlling **Tecan Cavro Centris** dual syringe pumps. It replaces the scattered pump control code in `main.py` with a clean, testable, and maintainable interface.

---

## Features

### **Core Capabilities**
- ✅ **Volume-based operations** - Aspirate/dispense with precise volume control
- ✅ **Syringe position tracking** - Real-time monitoring of plunger position and remaining volume
- ✅ **Valve control** - Move and verify valve positions (1-9 ports)
- ✅ **Error detection & recovery** - Automatic error checking with retry logic
- ✅ **Speed ramping** - Gentle acceleration/deceleration to prevent bubbles
- ✅ **Multi-step protocols** - Complex sequences (regenerate, flush, inject, prime)
- ✅ **Diagnostic logging** - Comprehensive state tracking and event logging
- ✅ **Qt signal integration** - Emit events for UI updates

### **What's New (Previously Missing)**
1. **Plunger position queries** - Know exactly where the syringe is
2. **Volume calculations** - Automatic conversion between µL and encoder steps
3. **Valve position verification** - Confirm valve reached target port
4. **Error status queries** - Detect stalls, overloads, and jams
5. **Busy/idle detection** - Prevent command collisions
6. **Backlash compensation** - Accurate direction changes
7. **Syringe initialization** - Proper homing to zero position
8. **Auto-prime routines** - Automated filling and air removal
9. **Diagnostic info** - Lifetime statistics and health monitoring

---

## Architecture

### **Class Structure**

```
CavroPumpManager (QObject)
├── Hardware Communication Layer
│   ├── _send_command() - Low-level FTDI interface with retry
│   └── is_available() - Check hardware connection
│
├── State Management
│   ├── PumpState (dataclass) - Complete pump status
│   ├── SyringeState (dataclass) - Position, volume, capacity
│   └── ValveState (dataclass) - Port, move count, timing
│
├── Initialization & Configuration
│   ├── initialize_pumps() - Reset and home
│   ├── set_syringe_size() - Configure volume calculations
│   ├── set_speed_ramp() - Acceleration/deceleration
│   └── set_backlash() - Direction change compensation
│
├── Syringe Operations
│   ├── aspirate() - Pull liquid in
│   ├── dispense() - Push liquid out
│   ├── move_to_position() - Absolute positioning
│   ├── get_syringe_position() - Query encoder
│   └── initialize_syringe() - Home plunger
│
├── Valve Operations
│   ├── set_valve_position() - Move to port
│   ├── get_valve_position() - Query current port
│   └── verify_valve_position() - Wait for position
│
├── Flow Control
│   ├── start_flow() - Continuous run
│   ├── stop() - Immediate halt
│   └── set_flow_rate() - Change speed
│
├── Status & Diagnostics
│   ├── is_busy() - Check if executing
│   ├── wait_until_idle() - Block until ready
│   ├── get_error_status() - Query error flags
│   ├── clear_errors() - Reset error state
│   ├── get_pump_state() - Get PumpState object
│   └── get_diagnostic_info() - Complete health report
│
└── High-Level Protocols
    ├── auto_prime() - Automated priming cycles
    ├── purge_line() - Fast flush
    ├── regenerate_sequence() - Surface regeneration
    ├── flush_sequence() - System flush
    └── inject_sequence() - Sample injection
```

---

## Usage Examples

### **Basic Initialization**

```python
from utils.cavro_pump_manager import CavroPumpManager, PumpAddress
from pump_controller import PumpController

# Create pump controller
pump_hardware = PumpController()

# Create manager
pump_manager = CavroPumpManager(pump_hardware)

# Initialize pumps
if pump_manager.initialize_pumps():
    print("Pumps ready!")
    
# Configure syringe sizes
pump_manager.set_syringe_size(PumpAddress.PUMP_1, 5000)  # 5 mL
pump_manager.set_syringe_size(PumpAddress.PUMP_2, 5000)  # 5 mL
```

### **Volume-Based Operations**

```python
# Aspirate 500 µL at 10 ml/min
pump_manager.aspirate(
    address=PumpAddress.PUMP_1,
    volume_ul=500,
    speed=10.0
)

# Wait for operation to complete
pump_manager.wait_until_idle(PumpAddress.PUMP_1)

# Dispense 250 µL at 5 ml/min
pump_manager.dispense(
    address=PumpAddress.PUMP_1,
    volume_ul=250,
    speed=5.0
)
```

### **Valve Control**

```python
from utils.cavro_pump_manager import ValvePort

# Move valve to port 3
pump_manager.set_valve_position(PumpAddress.PUMP_1, ValvePort.PORT_3)

# Verify it reached the position
if pump_manager.verify_valve_position(PumpAddress.PUMP_1, ValvePort.PORT_3, timeout=5.0):
    print("Valve in position!")
    
# Query current position
current_port = pump_manager.get_valve_position(PumpAddress.PUMP_1)
print(f"Valve at port {current_port}")
```

### **Error Handling**

```python
from utils.cavro_pump_manager import PumpError

# Check for errors
error_code = pump_manager.get_error_status(PumpAddress.PUMP_1)

if error_code == PumpError.PLUNGER_OVERLOAD:
    print("Plunger overload detected!")
    pump_manager.clear_errors(PumpAddress.PUMP_1)
    
    # Retry operation
    pump_manager.initialize_syringe(PumpAddress.PUMP_1)
```

### **State Monitoring**

```python
# Get complete pump state
state = pump_manager.get_pump_state(PumpAddress.PUMP_1)

print(f"Syringe volume: {state.syringe.current_volume_ul:.1f} µL")
print(f"Remaining capacity: {state.syringe.remaining_volume_ul:.1f} µL")
print(f"Valve port: {state.valve.current_port}")
print(f"Flow rate: {state.flow_rate_ml_per_min} ml/min")
print(f"Total dispensed: {state.total_volume_dispensed_ul:.1f} µL")

# Get diagnostic info
diag = pump_manager.get_diagnostic_info(PumpAddress.PUMP_1)
print(f"Error count: {diag['error_count']}")
print(f"Valve switches: {diag['valve_move_count']}")
```

### **High-Level Protocols**

```python
import asyncio

# Auto-prime (3 fill/empty cycles)
await pump_manager.auto_prime(
    address=PumpAddress.PUMP_1,
    cycles=3,
    volume_per_cycle_ul=4000,
    speed=50.0
)

# Purge line
await pump_manager.purge_line(
    address=PumpAddress.PUMP_1,
    volume_ul=5000,
    speed=100.0
)

# Regeneration sequence (with valve controller)
await pump_manager.regenerate_sequence(
    contact_time=45.0,
    flow_rate=1.0,
    valve_controller=knx_controller
)

# Injection sequence
await pump_manager.inject_sequence(
    flow_rate=1.0,
    injection_time=80.0,
    valve_controller=knx_controller
)
```

### **Qt Signal Integration**

```python
# Connect to signals
pump_manager.pump_state_changed.connect(on_pump_state_changed)
pump_manager.valve_position_changed.connect(on_valve_moved)
pump_manager.error_occurred.connect(on_pump_error)
pump_manager.operation_progress.connect(on_progress_update)

# Signal handlers
def on_pump_state_changed(address: int, description: str):
    print(f"Pump {address:#x}: {description}")
    
def on_valve_moved(address: int, port: int):
    print(f"Pump {address:#x} valve moved to port {port}")
    
def on_pump_error(address: int, error_msg: str):
    print(f"ERROR on pump {address:#x}: {error_msg}")
    
def on_progress_update(operation: str, percent: int):
    print(f"{operation}: {percent}%")
```

---

## Integration with Main Application

### **Replace Existing Code**

**Before (in `main.py`):**
```python
# Scattered pump commands
self.pump.send_command(0x41, b"zR")
self.pump.send_command(0x41, b"e15R")
self.pump.send_command(0x41, f"V{self.flow_rate:.3f},1R".encode())
```

**After:**
```python
# Clean high-level API
self.pump_manager = CavroPumpManager(self.pump)
self.pump_manager.initialize_pumps()
self.pump_manager.start_flow(PumpAddress.PUMP_1, rate_ml_per_min=60.0)
```

### **Migration Steps**

1. **Import the manager:**
   ```python
   from utils.cavro_pump_manager import CavroPumpManager, PumpAddress
   ```

2. **Initialize in `__init__`:**
   ```python
   self.pump_manager = CavroPumpManager(self.pump)
   ```

3. **Replace pump initialization:**
   ```python
   # Old: self.initialize_pumps()
   # New:
   self.pump_manager.initialize_pumps()
   ```

4. **Replace flow control:**
   ```python
   # Old: self.pump.send_command(0x41, b"T")
   # New: 
   self.pump_manager.stop()
   ```

5. **Replace regenerate/flush/inject:**
   ```python
   # Old: async def regenerate(self): ...
   # New:
   async def regenerate(self):
       await self.pump_manager.regenerate_sequence(
           contact_time=self.contact_time,
           flow_rate=self.flow_rate,
           valve_controller=self.knx
       )
   ```

---

## Constants Reference

### **Pump Addresses**
```python
PumpAddress.PUMP_1 = 0x31      # First pump (Channel 1)
PumpAddress.PUMP_2 = 0x32      # Second pump (Channel 2)
PumpAddress.BROADCAST = 0x41   # Both pumps simultaneously
```

### **Valve Ports**
```python
ValvePort.PORT_1 through ValvePort.PORT_9  # Valve positions 1-9
```

### **Error Codes**
```python
PumpError.NO_ERROR = 0x00
PumpError.INITIALIZATION_ERROR = 0x01
PumpError.INVALID_COMMAND = 0x02
PumpError.PLUNGER_OVERLOAD = 0x07
PumpError.VALVE_OVERLOAD = 0x08
# ... see full list in cavro_pump_manager.py
```

### **Flow Rates**
```python
DEFAULT_FLOW_RATE = 1.0 ml/min
FLUSH_FLOW_RATE = 100.0 ml/min
FAST_FLUSH_RATE = 83.333 ml/min
ULTRA_FAST_FLUSH_RATE = 6000 ml/min
```

### **Syringe Parameters**
```python
DEFAULT_SYRINGE_VOLUME_UL = 5000  # 5 mL
STEPS_PER_STROKE = 3000           # Encoder steps
MAX_SPEED_STEPS_PER_SEC = 6000
MIN_SPEED_STEPS_PER_SEC = 2
```

---

## Command Protocol Reference

### **Cavro Commands Used**

| Command | Hex | Purpose | Example |
|---------|-----|---------|---------|
| Query position | `?` | Get plunger position | `/1?` → `1234` |
| Query valve | `?6` | Get valve port | `/1?6` → `3` |
| Query error | `?19` | Get error flags | `/1?19` → `07` |
| Query busy | `Q` | Check if idle | `/1Q` → `0x20` |
| Initialize | `ZR` | Home plunger | `/1ZR` |
| Enable | `e15R` | Enable pump | `/1e15R` |
| Reset | `zR` | Reset pump | `/1zR` |
| Clear error | `W5R` | Clear error flags | `/1W5R` |
| Stop | `T` | Stop immediately | `/1T` |
| Aspirate | `P<steps>V<speed>R` | Pull liquid in | `/1P1000V10R` |
| Dispense | `D<steps>V<speed>R` | Push liquid out | `/1D500V5R` |
| Move to position | `A<pos>V<speed>R` | Absolute move | `/1A2000V10R` |
| Set valve | `I<port>R` | Move valve | `/1I3R` |
| Set start ramp | `L<ms>R` | Acceleration time | `/1L500R` |
| Set stop ramp | `h<ms>R` | Deceleration time | `/1h500R` |
| Set backlash | `K<steps>R` | Direction compensation | `/1K10R` |

---

## Benefits Over Previous Implementation

### **Before (main.py)**
- ❌ Raw hex commands scattered throughout code
- ❌ No position or volume tracking
- ❌ No error detection
- ❌ Magic numbers everywhere
- ❌ No valve verification
- ❌ Minimal error handling
- ❌ Difficult to test
- ❌ Tightly coupled to main app

### **After (CavroPumpManager)**
- ✅ Clean, high-level API
- ✅ Real-time position and volume tracking
- ✅ Automatic error detection with retry
- ✅ Named constants and enums
- ✅ Valve position verification
- ✅ Comprehensive error handling
- ✅ Fully testable with mocks
- ✅ Reusable in other projects

---

## Testing

### **Unit Tests (Recommended)**

```python
import unittest
from unittest.mock import Mock, MagicMock
from utils.cavro_pump_manager import CavroPumpManager, PumpAddress

class TestCavroPumpManager(unittest.TestCase):
    def setUp(self):
        # Mock hardware
        self.mock_pump = Mock()
        self.manager = CavroPumpManager(self.mock_pump)
        
    def test_aspirate_success(self):
        # Setup
        self.mock_pump.send_command.return_value = [0x00]
        
        # Execute
        result = self.manager.aspirate(PumpAddress.PUMP_1, 500, 10.0)
        
        # Verify
        self.assertTrue(result)
        self.mock_pump.send_command.assert_called()
        
    def test_insufficient_capacity(self):
        # Setup - syringe nearly full
        state = self.manager.get_pump_state(PumpAddress.PUMP_1)
        state.syringe.position_steps = 2900  # Almost at max
        
        # Execute
        result = self.manager.aspirate(PumpAddress.PUMP_1, 1000, 10.0)
        
        # Verify - should fail
        self.assertFalse(result)
```

### **Hardware Smoke Tests**

```python
# Test with real hardware
async def test_pump_hardware():
    from pump_controller import PumpController
    
    pump = PumpController()
    manager = CavroPumpManager(pump)
    
    # Initialize
    assert manager.initialize_pumps()
    
    # Test position query
    pos = manager.get_syringe_position(PumpAddress.PUMP_1)
    assert pos is not None
    print(f"Syringe at position: {pos}")
    
    # Test valve
    manager.set_valve_position(PumpAddress.PUMP_1, 3)
    assert manager.verify_valve_position(PumpAddress.PUMP_1, 3)
    
    # Test aspirate/dispense
    manager.aspirate(PumpAddress.PUMP_1, 100, 10.0)
    manager.wait_until_idle(PumpAddress.PUMP_1)
    manager.dispense(PumpAddress.PUMP_1, 100, 10.0)
    
    print("All hardware tests passed!")
```

---

## Troubleshooting

### **Common Issues**

**1. Import Error: `pump_controller` not found**
- The error is expected - `pump_controller.py` is hardware-specific
- The class gracefully handles missing imports
- Ensure `pump_controller.py` is in your Python path

**2. Pump not responding**
- Check hardware connection (USB/FTDI)
- Verify pump is powered on
- Call `initialize_pumps()` after connecting
- Check error status with `get_error_status()`

**3. Volume calculations incorrect**
- Verify syringe size is set correctly: `set_syringe_size(address, volume_ul)`
- Default is 5000 µL (5 mL)
- Check `STEPS_PER_STROKE` constant matches your pump model

**4. Valve not moving**
- Query position with `get_valve_position()` before and after
- Use `verify_valve_position()` to wait for move completion
- Check for `VALVE_ERROR` or `VALVE_OVERLOAD` errors

**5. Operations timing out**
- Increase timeout in `wait_until_idle()`
- Check if pump is actually busy with `is_busy()`
- Look for mechanical obstructions

---

## Future Enhancements

### **Potential Additions**
1. **Flow sensor integration** - Closed-loop flow control
2. **Protocol builder** - GUI for defining multi-step sequences
3. **Calibration routines** - Automatic volume calibration
4. **Pressure monitoring** - Detect blockages
5. **Multi-pump coordination** - Synchronized operations
6. **Recipe management** - Save/load pump protocols
7. **Maintenance tracking** - Predict valve/seal replacement
8. **Remote control** - REST API for pump operations

---

## API Quick Reference

### **Initialization**
```python
CavroPumpManager(pump_controller)
initialize_pumps(pump_addresses=None) -> bool
set_syringe_size(address, volume_ul)
set_speed_ramp(address, start_ms, stop_ms) -> bool
set_backlash(address, steps) -> bool
```

### **Syringe Control**
```python
aspirate(address, volume_ul, speed) -> bool
dispense(address, volume_ul, speed) -> bool
move_to_position(address, position_steps, speed) -> bool
get_syringe_position(address) -> int | None
initialize_syringe(address) -> bool
```

### **Valve Control**
```python
set_valve_position(address, port) -> bool
get_valve_position(address) -> int | None
verify_valve_position(address, port, timeout) -> bool
```

### **Flow Control**
```python
start_flow(address, rate_ml_per_min, direction_forward) -> bool
stop(address=None) -> bool
set_flow_rate(address, rate_ml_per_min) -> bool
```

### **Status**
```python
is_busy(address) -> bool
wait_until_idle(address, timeout) -> bool
get_error_status(address) -> int
clear_errors(address) -> bool
get_pump_state(address) -> PumpState | None
get_diagnostic_info(address) -> dict
```

### **Protocols**
```python
async auto_prime(address, cycles, volume_per_cycle_ul, speed) -> bool
async purge_line(address, volume_ul, speed) -> bool
async regenerate_sequence(contact_time, flow_rate, valve_controller) -> bool
async flush_sequence(flow_rate) -> bool
async inject_sequence(flow_rate, injection_time, valve_controller) -> bool
```

---

## License & Support

This module is part of the Affinite SPR control software.

For questions or issues, check the logs first:
```python
pump_manager.log_pump_states()  # Log all pump states
pump_manager.get_diagnostic_info(address)  # Detailed diagnostics
```

**Logger**: `utils.logger` → Check `generated-files/logfile.txt`
