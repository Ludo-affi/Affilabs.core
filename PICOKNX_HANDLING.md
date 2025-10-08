# PicoKNX Handling in the Codebase

## Overview

**PicoKNX2** is a Raspberry Pi Pico-based kinetic controller that's still **supported but considered legacy hardware**. Here's how it's handled:

---

## Current Status

### ✅ Supported Devices
1. **KNX** (Original kinetic controller)
2. **KNX2** (Improved version)
3. **PicoKNX2** (Raspberry Pi Pico-based, legacy but still supported)
4. **PicoEZSPR** (EZSPR variant)

### ❌ Obsolete/Removed
- **PicoKNX** (original version - no longer supported)

---

## Implementation Details

### 1. Controller Class (`utils/controller.py`)

**Location:** Lines 460-530

```python
class PicoKNX2(ControllerBase):
    """
    Raspberry Pi Pico-based kinetic controller.
    
    Features:
    - Dual-channel support (CH1 and CH2)
    - Temperature sensing
    - Flow sensing (legacy, not used anymore)
    - Valve control (3-way and 6-port)
    - Serial communication over USB
    """
    
    def __init__(self):
        super().__init__(name='pico_knx2')
        self._ser = None
        self.version = ''
    
    def open(self):
        """Open USB serial connection to Pico."""
        # Searches for device with PICO_PID and PICO_VID
        # Sends "id\n" command to verify device type
        # Expects "KNX2" response
        # Gets version with "iv\n" command
    
    def get_status(self):
        """Get device internal temperature."""
        # Sends "it\n" command
        # Returns float temperature value
    
    def knx_status(self, ch):
        """Get channel status (sensors and valves)."""
        # Sends "ks{ch}\n" command
        # Returns dict: {'flow': float, 'temp': float, '3W': int, '6P': int}
```

### 2. KineticManager Integration (`utils/kinetic_manager.py`)

**Import Handling:**
```python
try:
    from utils.controller import KineticController, PicoKNX2, PicoEZSPR
except ImportError:
    KineticController = None
    PicoKNX2 = None
    PicoEZSPR = None
```

**Type Hints:**
```python
def __init__(
    self,
    kinetic_controller: Any | None = None,  # Accepts any controller type
    experiment_start_time: float | None = None,
) -> None:
```

**Device Detection:**
- KineticManager doesn't care about the specific hardware type
- It just needs an object with these methods:
  - `knx_three(position, channel)`
  - `knx_six(position, channel)`
  - `knx_status(channel)`
  - `get_status()`

### 3. Main Application (`main/main.py`)

**Type Declaration:**
```python
self.knx: KineticController | PicoKNX2 | PicoEZSPR | None = None
```

**Device Detection:**
```python
elif knx_name in {"pico_knx2", "pico_ezspr", "KNX2", "PicoKNX2"}:
    self.device_config["knx"] = "PicoKNX2"
```

**Device-Specific Checks:**
```python
# Check if device is PicoKNX2 or KNX2
if self.device_config["knx"] in ["KNX2", "PicoKNX2"]:
    # Dual-channel support enabled
```

---

## How PicoKNX2 Works with Managers

### CavroPumpManager
- **Independent** - Doesn't interact with PicoKNX2
- Manages Tecan Cavro pumps only

### KineticManager
- **Works with PicoKNX2** through abstraction
- Doesn't need to know it's a PicoKNX2 specifically
- Just calls the standard interface methods:

```python
# KineticManager doesn't care about hardware type
self.knx.knx_three(position, hw_channel)  # Works with all KNX types
self.knx.knx_six(position, hw_channel)    # Works with all KNX types
self.knx.knx_status(channel)              # Works with all KNX types
```

### Device Temperature Reading
```python
# PicoKNX2 returns temperature directly as float
if device_type == "PicoKNX2":
    temp = self.knx.get_status()  # Returns float directly
```

---

## PicoKNX2 Capabilities

### Hardware Features
- **USB Serial Communication** (115200 baud)
- **Dual Channel** (CH1 and CH2)
- **Valves per Channel:**
  - 3-way valve (2 positions: 0, 1)
  - 6-port valve (2 positions: 0, 1)
- **Sensors per Channel:**
  - Temperature sensor (°C)
  - Flow sensor (ml/min) - **No longer used**
- **Device Temperature:** Internal Pico temperature

### Commands
- `id\n` - Get device ID (returns "KNX2")
- `iv\n` - Get firmware version
- `it\n` - Get internal temperature
- `ks{ch}\n` - Get channel status (ch = 1 or 2)
- Plus valve control commands (inherited from base)

---

## Why PicoKNX2 Is "Legacy"

### Still Works But...
1. **Original KNX is preferred** - More stable, proven hardware
2. **Limited production** - PicoKNX2 was experimental/limited run
3. **Flow sensing removed** - One of its features no longer used
4. **Future: May be phased out** - When all systems upgraded to KNX2

### But It's Not Obsolete!
- ✅ Still fully supported in code
- ✅ Works with all managers
- ✅ Receives software updates
- ✅ Can be used in production
- ✅ Dual-channel support

---

## Comparison: PicoKNX2 vs KNX2

| Feature | PicoKNX2 | KNX2 |
|---------|----------|------|
| **Hardware** | Raspberry Pi Pico | Custom PCB |
| **Status** | Legacy but supported | Current/Preferred |
| **Channels** | 2 (CH1, CH2) | 2 (CH1, CH2) |
| **Temperature** | ✅ Yes | ✅ Yes |
| **Flow** | ❌ Not used | ❌ Not used |
| **Valves** | ✅ 3-way & 6-port | ✅ 3-way & 6-port |
| **USB** | ✅ USB Serial | ✅ USB Serial |
| **Cost** | Lower (Pico-based) | Higher (custom) |
| **Reliability** | Good | Better |
| **Future** | May phase out | Long-term support |

---

## Code Patterns

### Detection
```python
# Device is detected during open_device()
if self.knx is not None and isinstance(self.knx, PicoKNX2):
    # PicoKNX2-specific code (rare, usually not needed)
```

### Configuration
```python
# Device type stored in config
self.device_config["knx"] = "PicoKNX2"

# Check in code
if self.device_config["knx"] == "PicoKNX2":
    # Usually grouped with KNX2
```

### Usage Pattern
```python
# Usually grouped with KNX2 (same capabilities)
if self.device_config["knx"] in ["KNX2", "PicoKNX2"]:
    # Enable dual-channel features
    update2 = self.knx.knx_status(2)
```

---

## Integration with KineticManager

### ✅ Fully Compatible
```python
# Initialize (works with any controller)
kinetic_manager = KineticManager(self.knx, self.exp_start)

# All methods work
kinetic_manager.set_three_way_valve("CH1", 1)  # Works
kinetic_manager.set_six_port_valve("CH2", 0)   # Works
kinetic_manager.read_sensor("CH1")             # Works
kinetic_manager.read_device_temperature()      # Works
```

### No Special Handling Required
- KineticManager treats all KNX types the same
- Abstraction layer handles differences
- Commands are identical across hardware types

---

## Future Considerations

### Potential Changes
1. **Phase-out Timeline:** TBD (when all systems upgraded)
2. **Deprecation Notice:** None yet (still fully supported)
3. **Migration Path:** Upgrade to KNX2 hardware when available

### Maintaining Support
- Continue testing with PicoKNX2 hardware
- Keep serial communication code
- Maintain dual-channel capabilities
- Document any PicoKNX2-specific quirks

---

## Summary

### How PicoKNX2 Is Handled:

1. **Hardware Class:** `PicoKNX2` in `utils/controller.py`
   - USB serial communication
   - Standard KNX command interface
   - Returns same data format as KNX2

2. **Manager Integration:** Transparent
   - KineticManager doesn't know/care about hardware type
   - Uses standard interface methods
   - No special cases needed

3. **Application Level:** Grouped with KNX2
   - Same capabilities (dual-channel)
   - Same features enabled
   - Usually checked together: `if device in ["KNX2", "PicoKNX2"]`

4. **Status:** Legacy but fully supported
   - Not obsolete (unlike original PicoKNX)
   - Works with all managers
   - May be phased out eventually

### Key Takeaway:
**PicoKNX2 is treated the same as KNX2 in the codebase.** The abstraction layer (manager pattern) means we don't need special handling - it just works!

---

## Testing PicoKNX2

### Hardware Tests
- [ ] USB connection/detection
- [ ] Valve control (both channels)
- [ ] Sensor reading (both channels)
- [ ] Device temperature
- [ ] Synchronized mode
- [ ] Injection sequences

### Software Tests
- [ ] KineticManager integration
- [ ] Signal emissions
- [ ] Error handling
- [ ] Logging

### Compatibility Tests
- [ ] Works with CavroPumpManager
- [ ] Works with calibration
- [ ] UI updates correctly
- [ ] Log export works

---

**Last Updated:** October 7, 2025  
**Status:** PicoKNX2 fully supported, works with all managers  
**Future:** May be phased out when all systems upgraded to KNX2
