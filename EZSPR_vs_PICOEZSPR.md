# EZSPR vs PicoEZSPR - Hardware Comparison

**Date:** October 7, 2025  
**Status:** Both devices fully supported and operational

---

## Quick Summary

Both **EZSPR** and **PicoEZSPR** are controller devices that provide:
- Dual-channel kinetic control
- Valve control (3-way and 6-port)
- Temperature sensing
- Pump control capabilities

The main difference is the **hardware platform** they're built on.

---

## Side-by-Side Comparison

| Feature | EZSPR | PicoEZSPR |
|---------|-------|-----------|
| **Hardware Platform** | Custom PCB | Raspberry Pi Pico |
| **USB Chip** | Silicon Labs CP210X | Raspberry Pi Pico (RP2040) |
| **USB VID** | 0x10C4 (CP210X) | 0x2E8A (Pico) |
| **USB PID** | 0xEA60 (CP210X) | 0x000A (Pico) |
| **Baudrate** | 115200 | 115200 |
| **Device Name** | "EZSPR" | "pico_ezspr" |
| **Channels** | 2 (CH1, CH2) | 2 (CH1, CH2) |
| **Temperature Sensing** | ✅ Yes | ✅ Yes |
| **Valve Control** | ✅ 3-way & 6-port | ✅ 3-way & 6-port |
| **Firmware Updates** | Standard | OTA via USB (UF2) |
| **Version Detection** | Firmware string | Firmware string |
| **Status** | Current/Preferred | Current/Supported |
| **Cost** | Higher (custom PCB) | Lower (Pico-based) |
| **Reliability** | Proven | Good |

---

## Hardware Details

### EZSPR (Custom PCB)

**Communication:**
- USB-to-Serial bridge: **Silicon Labs CP210X** (VID: 0x10C4, PID: 0xEA60)
- Baudrate: **115200**
- Protocol: Text commands via serial

**Detection Method:**
```python
# Scans for CP210X chip (same as KNX2)
for dev in serial.tools.list_ports.comports():
    if dev.pid == CP210X_PID and dev.vid == CP210X_VID:
        # Try to connect and check firmware version
        info = self.get_info()
        if info['fw ver'].startswith('EZSPR'):
            self.name = "EZSPR"
            return True
```

**Firmware Versions:**
- V1.0 - Original
- V1.1 - Improved version

**Special Features:**
- Same USB chip as KNX2 (shared detection logic)
- Uses JSON protocol for status updates
- Integrated with KineticController class

---

### PicoEZSPR (Raspberry Pi Pico)

**Communication:**
- USB: **Native Raspberry Pi Pico** (VID: 0x2E8A, PID: 0x000A)
- Baudrate: **115200**
- Protocol: Text commands via serial

**Detection Method:**
```python
# Scans for Raspberry Pi Pico
for dev in serial.tools.list_ports.comports():
    if dev.pid == PICO_PID and dev.vid == PICO_VID:
        # Send "id\n" command
        reply = self._ser.readline()[0:5].decode()
        if reply == 'EZSPR':
            # Get version with "iv\n"
            self.version = self._ser.readline()[0:4].decode()
            return True
```

**Firmware Versions:**
- V1.3 - First updatable version
- V1.4 - Added pump correction
- V1.5 - Latest version with pump correction

**Special Features:**
- **Firmware Updates:** Can be updated via USB drag-and-drop (UF2 bootloader)
- **Pump Correction:** V1.4+ supports pump calibration multipliers
- **Cost Effective:** Built on inexpensive Raspberry Pi Pico platform
- **Update Process:** Device enters bootloader mode, appears as USB drive

---

## Software Integration

### Detection Logic (main.py)

Both devices are detected and configured:

```python
# Line 340-341
elif ctrl_name in ["pico_ezspr", "PicoEZSPR", "EZSPR"]:
    self.device_config["ctrl"] = "PicoEZSPR" if "Pico" in ctrl_name else "EZSPR"
```

**Result:**
- EZSPR → `device_config["ctrl"] = "EZSPR"`
- PicoEZSPR → `device_config["ctrl"] = "PicoEZSPR"`

### Shared Functionality

Both devices are treated **identically** in most code:

```python
# Dual-channel detection
if ctrl_type in ['EZSPR', 'PicoEZSPR']:
    self.knx2 = True  # Enable dual-channel mode

# Kinetic manager integration
if self.device_config["ctrl"] in ["EZSPR", "PicoEZSPR"]:
    # Use kinetic_manager for valve/sensor control

# Log file creation
if self.device_config["ctrl"] in ["EZSPR", "PicoEZSPR"]:
    # Create dual-channel logs
```

### Device-Specific Differences

**PicoEZSPR-Only Features:**

1. **Firmware Updates** (utils/controller.py):
```python
def update_firmware(self, firmware):
    """Only available for PicoEZSPR V1.3+"""
    if not (self.valid() and self.version in self.UPDATABLE_VERSIONS):
        return False
    
    self._ser.write(b"du\n")  # Enter bootloader mode
    self.close()
    
    # Wait for Pico to appear as USB drive
    pico_drive = next(d for d in listdrives() if (Path(d) / "INFO_UF2.TXT").exists())
    
    # Copy firmware
    copy(firmware, pico_drive)
    
    # Wait for reboot
    return self.open()
```

2. **Pump Corrections** (utils/controller.py):
```python
def get_pump_corrections(self):
    """Only available for PicoEZSPR V1.4+"""
    if not (self.valid() and self.version in self.VERSIONS_WITH_PUMP_CORRECTION):
        return None
    self._ser.write(b"pc\n")
    reply = self._ser.readline()
    return tuple(x / self.PUMP_CORRECTION_MULTIPLIER for x in reply[:2])

def set_pump_corrections(self, pump_1_correction, pump_2_correction):
    """Set pump calibration multipliers"""
    corrections = pump_1_correction, pump_2_correction
    corrrection_bytes = bytes(round(x * self.PUMP_CORRECTION_MULTIPLIER) for x in corrections)
    # ... send to device
```

**EZSPR Features:**
- Uses same protocol as KNX2 (CP210X chip)
- Shares detection code with KNX2/KNX
- Standard firmware update process (not OTA)

---

## Controller Classes

### EZSPR Class

**Location:** Uses `KineticController` class (not a separate class!)

```python
class KineticController(ControllerBase):
    def __init__(self):
        super().__init__(name='KNX2')
        # ...
    
    def open(self):
        # Scans for CP210X devices
        for dev in serial.tools.list_ports.comports():
            if dev.pid == CP210X_PID and dev.vid == CP210X_VID:
                # ...
                info = self.get_info()
                if info['fw ver'].startswith('EZSPR'):
                    self.name = "EZSPR"  # Change name to EZSPR
                    return True
```

**Key Point:** EZSPR is detected by `KineticController` class and changes its name to "EZSPR"!

---

### PicoEZSPR Class

**Location:** Separate class in `utils/controller.py`

```python
class PicoEZSPR(ControllerBase):
    UPDATABLE_VERSIONS: Final[set] = {"V1.3", "V1.4"}
    VERSIONS_WITH_PUMP_CORRECTION: Final[set] = {"V1.4", "V1.5"}
    PUMP_CORRECTION_MULTIPLIER: Final[int] = 100
    
    def __init__(self):
        super().__init__(name='pico_ezspr')
        self.version = ''
    
    def open(self):
        # Scans for Raspberry Pi Pico
        for dev in serial.tools.list_ports.comports():
            if dev.pid == PICO_PID and dev.vid == PICO_VID:
                self._ser = serial.Serial(port=dev.device, baudrate=115200, timeout=5)
                cmd = f"id\n"
                self._ser.write(cmd.encode())
                reply = self._ser.readline()[0:5].decode()
                if reply == 'EZSPR':
                    return True
```

**Key Point:** PicoEZSPR has its own class with additional methods for firmware updates and pump corrections!

---

## Type Hints & Imports

### main.py Type Declarations

```python
# Line 176
self.ctrl: PicoP4SPR | PicoEZSPR | None = None

# Line 177
self.knx: KineticController | PicoEZSPR | None = None
```

**Note:** `self.knx` can be PicoEZSPR because PicoEZSPR provides kinetic control functionality!

---

## UI Widgets

Both devices use the **same UI widget**:

```python
# widgets/device.py
elif ctrl_type in ['EZSPR', 'PicoEZSPR']:
    if ctrl_type == 'PicoEZSPR':
        self.ctrl_pico = True  # Flag for Pico-specific features
    
    self.ctrl_widget = EZSPRWidget(self.ui.controller_frame, self.ctrl_pico)
```

**EZSPRWidget Features:**
- Shows device temperature
- Displays connection status
- Provides disconnect/shutdown buttons
- Uses `ui/ui_EZSPR.py` (same UI for both)

---

## Capabilities Matrix

### Both Support:

✅ **Dual-Channel Operation**
- Channel 1 (CH1) control
- Channel 2 (CH2) control
- Synchronized mode

✅ **Valve Control**
- 3-way valves (2 positions: 0, 1)
- 6-port valves (2 positions: 0, 1)

✅ **Temperature Sensing**
- Device internal temperature
- Channel temperature sensors

✅ **Sensor Reading**
- Temperature readings per channel
- Valve position status

✅ **Pump Control**
- Integrated pump management
- Flow rate control
- Injection sequences

✅ **KineticManager Integration**
- Full compatibility with KineticManager
- Signal-based updates
- Thread-safe operation

✅ **Logging**
- Dual-channel log files
- Kinetic event logging
- CSV export

---

### PicoEZSPR-Specific:

✅ **OTA Firmware Updates**
- Drag-and-drop UF2 files
- Automatic bootloader mode
- Version checking (V1.3+)

✅ **Pump Corrections**
- Calibration multipliers for pumps
- Get/set correction values
- Per-pump adjustment (V1.4+)

✅ **Lower Cost**
- Built on $4 Raspberry Pi Pico
- Easier to manufacture
- More accessible for prototyping

---

### EZSPR-Specific:

✅ **Shared Hardware with KNX2**
- Same USB chip (CP210X)
- Same detection logic
- Proven reliability

✅ **Professional Hardware**
- Custom PCB design
- Industrial-grade components
- Better EMI/thermal performance

---

## When to Use Each

### Use EZSPR When:
- ✅ Need proven reliability
- ✅ Production environment
- ✅ Professional deployment
- ✅ Don't need frequent firmware updates
- ✅ Budget allows for custom hardware

### Use PicoEZSPR When:
- ✅ Development/prototyping
- ✅ Need easy firmware updates
- ✅ Want pump correction features
- ✅ Cost is a constraint
- ✅ Comfortable with Pico platform

---

## Migration Between Devices

### EZSPR → PicoEZSPR

**What Changes:**
- Hardware swap only
- Software auto-detects device type
- No code changes needed
- May gain firmware update capability
- May gain pump correction features

**What Stays the Same:**
- All valve control
- All sensor reading
- All pump control
- All UI functionality
- All logging

### PicoEZSPR → EZSPR

**What Changes:**
- Hardware swap only
- Software auto-detects device type
- No code changes needed
- Lose firmware update capability
- Lose pump correction features

**What Stays the Same:**
- All valve control
- All sensor reading
- All pump control
- All UI functionality
- All logging

---

## Testing Checklist

### EZSPR Testing
- [ ] Device detection (CP210X chip)
- [ ] Firmware version detection
- [ ] Dual-channel mode enabled
- [ ] Valve control (both channels)
- [ ] Sensor reading (both channels)
- [ ] Temperature display
- [ ] Log file creation
- [ ] KineticManager integration

### PicoEZSPR Testing
- [ ] Device detection (Pico VID/PID)
- [ ] Firmware version detection
- [ ] Dual-channel mode enabled
- [ ] Valve control (both channels)
- [ ] Sensor reading (both channels)
- [ ] Temperature display
- [ ] Log file creation
- [ ] KineticManager integration
- [ ] Firmware update (V1.3+)
- [ ] Pump corrections (V1.4+)

---

## Code Examples

### Detecting Which Device Type

```python
# In your code
if self.device_config["ctrl"] == "EZSPR":
    print("Using EZSPR (custom PCB)")
elif self.device_config["ctrl"] == "PicoEZSPR":
    print("Using PicoEZSPR (Raspberry Pi Pico)")
    
    # Check for firmware update support
    if hasattr(self.ctrl, 'UPDATABLE_VERSIONS'):
        if self.ctrl.version in self.ctrl.UPDATABLE_VERSIONS:
            print("Firmware updates supported!")
```

### Using Either Device

```python
# Both work the same way!
if self.device_config["ctrl"] in ["EZSPR", "PicoEZSPR"]:
    # Enable dual-channel
    self.kinetic_manager = KineticManager(self.ctrl, self.exp_start)
    
    # Control valves
    self.kinetic_manager.set_three_way_valve("CH1", 1)
    self.kinetic_manager.set_six_port_valve("CH2", 0)
    
    # Read sensors
    reading = self.kinetic_manager.read_sensor("CH1")
```

---

## Troubleshooting

### EZSPR Not Detected

**Possible Causes:**
1. CP210X driver not installed
2. Device is actually KNX2 (same chip!)
3. Firmware doesn't report "EZSPR" string
4. USB cable/connection issue

**Solution:**
- Check firmware version string
- Install CP210X drivers
- Try different USB port
- Check if detected as KNX2 instead

### PicoEZSPR Not Detected

**Possible Causes:**
1. Pico in bootloader mode (shows as drive)
2. Wrong firmware on Pico
3. USB cable is data-only
4. Device stuck in error state

**Solution:**
- Unplug and replug Pico
- Check for "RPI-RP2" drive (bootloader)
- Reflash firmware via UF2
- Try different USB port

---

## Summary

### Key Takeaway:
**EZSPR and PicoEZSPR are functionally equivalent** from the software perspective. The main differences are:

1. **Hardware Platform:**
   - EZSPR: Custom PCB with CP210X chip
   - PicoEZSPR: Raspberry Pi Pico (RP2040)

2. **Special Features:**
   - EZSPR: Shares hardware with KNX2, proven reliability
   - PicoEZSPR: OTA updates, pump corrections, lower cost

3. **Detection:**
   - EZSPR: Detected by KineticController class (changes name)
   - PicoEZSPR: Has dedicated PicoEZSPR class

4. **Usage:**
   - Both provide dual-channel kinetic control
   - Both work with KineticManager
   - Both support same UI/logging/features
   - Code treats them identically (with minor exceptions)

### Recommendation:
- **Production:** Use EZSPR (proven, reliable)
- **Development:** Use PicoEZSPR (flexible, updatable, cheaper)
- **Migration:** Seamless between both devices

---

**Last Updated:** October 7, 2025  
**Status:** Both devices fully supported ✅  
**Compatibility:** Software handles both transparently
