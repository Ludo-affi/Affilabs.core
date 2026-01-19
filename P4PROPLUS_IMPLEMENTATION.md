# P4PRO+ (P4PROPLUS) Support Implementation

## Summary
Added support for the P4PRO+ device (internally identified as "P4PROPLUS"), which is a P4PRO with populated internal pumps. The device is handled using Option 1 (minimal changes) - treating it as a P4PRO variant with pump capabilities.

## Device Identification
- **P4PRO**: Standard device without internal pumps
- **P4PROPLUS**: P4PRO with internal pumps populated
- Firmware responds with "p4proplus" when queried with `id` command
- Software stores exact firmware ID to distinguish variants

## Changes Made

### 1. Controller Class (`affilabs/utils/controller.py`)

#### Firmware ID Detection
- Modified to store exact firmware ID: `self.firmware_id = reply.upper()`
- Preserves "P4PRO" vs "P4PROPLUS" distinction

#### New Methods Added to `PicoP4PRO` class:

```python
has_pumps() -> bool
    # Returns True if firmware contains "PLUS"

pump_run(pump: int, rpm: int) -> bool
    # Run pump at specified RPM (5-220 auto-clamped)
    # pump: 1, 2, or 3 (both)
    
pump_stop(pump: int) -> bool
    # Stop pump(s)
    # pump: 1, 2, or 3 (both)
    
pump_read_calibration() -> tuple[int, int] | None
    # Returns (pump1_percent, pump2_percent)
    # Default: (100, 100) = 100% duty cycle
    # Range: 50-150 (50%-150%)
    
pump_read_cycle_counts() -> tuple[int, int] | None
    # Returns (count1, count2) for lifecycle tracking
    
pump_flash_calibration(pump1_pct: int, pump2_pct: int) -> bool
    # Flash calibration to EEPROM (use sparingly)
    # Range: 50-150%
```

#### Updated Methods:
- `stop_kinetic()` - Now stops pumps if device has them (checks `has_pumps()`)

### 2. HAL Adapter (`affilabs/utils/hal/controller_hal.py`)

#### New Property:
```python
@property
def has_internal_pumps(self) -> bool
    # Check if device has internal pumps
```

#### Updated Properties:
- `supports_pump` - Now checks `has_pumps()` instead of returning False

#### New Pump Methods:
All pump methods from controller class are exposed through HAL:
- `pump_run(pump, rpm)`
- `pump_stop(pump)`
- `pump_read_calibration()`
- `pump_read_cycle_counts()`
- `pump_flash_calibration(pump1_pct, pump2_pct)`

#### Device Type:
- Now returns actual firmware ID ("P4PRO" or "P4PROPLUS")

### 3. Hardware Manager (`affilabs/core/hardware_manager.py`)

Updated `_get_controller_type()` to handle P4PROPLUS:
```python
elif device_type == "P4PROPLUS":
    return "P4PROPLUS"  # P4PRO with internal pumps
```

### 4. UI Display (`affilabs/affilabs_core_ui.py`)

Added display name mapping:
```python
"P4PROPLUS": "P4PRO+",  # P4PROPLUS with internal pumps
```

Device will show as "P4PRO+" in the UI instead of just "P4PRO"

## Firmware Commands (P4PROPLUS V2.3+)

### Basic Pump Control
- `pr1XXX` - Run pump 1 at XXX RPM (e.g., pr1050 = 50 RPM)
- `pr2XXX` - Run pump 2 at XXX RPM
- `pr3XXX` - Run both pumps at XXX RPM
- `ps1` - Stop pump 1
- `ps2` - Stop pump 2
- `ps3` - Stop both pumps

### Calibration & Status
- `pc` - Read calibration values (returns 2 bytes: pump1%, pump2%)
- `pcc` - Read cycle counts (returns "count1,count2")
- `pf` + char(pump1%) + char(pump2%) - Flash new calibration

### Valid Speed Range
- Minimum: 5 RPM (pr1005)
- Maximum: 220 RPM (pr1220)
- Auto-clamping: Values outside range are clamped automatically

### Calibration Values
- Default: 100 (100% duty cycle)
- Range: 50-150 (50%-150% duty cycle)

## Usage Example

```python
from affilabs.utils.controller import PicoP4PRO

# Connect to device
ctrl = PicoP4PRO()
if ctrl.open():
    print(f"Connected to {ctrl.firmware_id}")
    
    # Check if device has pumps
    if ctrl.has_pumps():
        print("This is a P4PROPLUS with internal pumps")
        
        # Run pump 1 at 50 RPM
        ctrl.pump_run(1, 50)
        
        # Read calibration
        cal = ctrl.pump_read_calibration()
        if cal:
            pump1_pct, pump2_pct = cal
            print(f"Pump 1: {pump1_pct}%, Pump 2: {pump2_pct}%")
        
        # Stop pump
        ctrl.pump_stop(1)
    else:
        print("This is a standard P4PRO without pumps")
    
    ctrl.close()
```

## Test Script

Created `test_p4proplus_pumps.py` to demonstrate pump functionality:
- Detects if device has pumps
- Reads calibration and cycle counts
- Tests pump control at low speed (25 RPM)
- Safely handles both P4PRO and P4PROPLUS devices

## Backward Compatibility

- Standard P4PRO devices work unchanged
- `has_pumps()` returns False for P4PRO
- Pump methods log warning if called on P4PRO
- No breaking changes to existing code

## Notes

1. The internal pump feature is additive - P4PROPLUS has all P4PRO features plus pumps
2. Firmware version V2.3+ required for pump commands
3. Device ID command must be sent first before pumps work (`id` command)
4. Calibration flash writes to EEPROM - use sparingly (limited write cycles)
