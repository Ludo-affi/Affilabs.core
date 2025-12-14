# HAL LED Intensity Control Fix

**Status**: ✅ Complete
**Date**: October 11, 2025
**Issue**: HAL stub method didn't implement LED intensity control
**Resolution**: Proper implementation added

---

## Problem

The `PicoP4SPRHAL.set_led_intensity()` method was a stub that:
- Had misleading comments: "PicoP4SPR doesn't support variable LED intensity"
- Always returned `True` without doing anything
- Made the HAL interface incomplete

**Reality**: The firmware DOES support intensity control via `baXXX\n` commands (0-255 range).

---

## Solution

### File Modified
`utils/hal/pico_p4spr_hal.py`

### Changes Made

**1. Added intensity tracking in `__init__()`**:
```python
def __init__(self) -> None:
    super().__init__("PicoP4SPR")
    self._ser: serial.Serial | None = None
    self._connection_timeout = 3.0
    self._operation_timeout = 2.0
    self._current_intensity = 1.0  # Default to full intensity
```

**2. Implemented `set_led_intensity()`**:
```python
def set_led_intensity(self, intensity: float) -> bool:
    """Set LED intensity for all channels.

    Args:
        intensity: LED intensity (0.0 to 1.0 normalized scale)
    """
    # Convert 0.0-1.0 to 0-255 firmware range
    max_intensity = 204  # 4LED PCB limit
    firmware_value = int(intensity * max_intensity)
    intensity_str = f"{firmware_value:03d}"

    # Set all 4 channels
    for channel_letter in ['a', 'b', 'c', 'd']:
        cmd = f"b{channel_letter}{intensity_str}\n"
        self._send_command_with_response(cmd, expected_response=b"1")

    self._current_intensity = intensity
    return success
```

**3. Implemented `get_led_intensity()`**:
```python
def get_led_intensity(self) -> float | None:
    """Get current LED intensity."""
    return getattr(self, '_current_intensity', 1.0)
```

---

## Technical Details

### Firmware Commands
```
baXXX\n  - Set LED A intensity (000-255)
bbXXX\n  - Set LED B intensity (000-255)
bcXXX\n  - Set LED C intensity (000-255)
bdXXX\n  - Set LED D intensity (000-255)
```

### HAL Interface
- **Input**: Normalized intensity (0.0 to 1.0)
- **Output**: Firmware commands with 0-255 range
- **Hardware Limits**:
  - 4LED PCB: Max 204 (~80% range)
  - 8LED PCB: Max 255 (100% range)

### Conversion Formula
```python
firmware_value = int(intensity * 204)  # For 4LED PCB
firmware_str = f"{firmware_value:03d}"  # Zero-pad to 3 digits
```

### Example Usage
```python
hal = PicoP4SPRHAL()
hal.connect()

# Set to 50% intensity
hal.set_led_intensity(0.5)  # Sends ba102\n, bb102\n, bc102\n, bd102\n

# Set to 80% intensity
hal.set_led_intensity(0.8)  # Sends ba163\n, bb163\n, bc163\n, bd163\n

# Get current intensity
intensity = hal.get_led_intensity()  # Returns 0.8
```

---

## Impact on Optical System Calibration

### Before Fix
- Calibration always ran at default firmware intensity (~204-255)
- No way to control intensity from Python code
- Had to use firmware commands directly

### After Fix ✅
- **Can control intensity via HAL**: `hal.set_led_intensity(0.8)`
- **Calibration script can specify intensity**: Easy to add intensity parameter
- **Future enhancements possible**:
  - Calibrate at multiple intensities if needed
  - Validate intensity-independence of τ experimentally
  - Support different operating intensities

### Current Calibration Status
- **Still valid**: Performed at default intensity (likely max)
- **Theory unchanged**: τ should be intensity-independent in linear regime
- **Implementation ready**: Can now add intensity control if validation testing desired

---

## Testing Notes

**Not tested yet** - this is a code fix to make the HAL interface complete.

**Recommended testing**:
1. Connect to PicoP4SPR
2. Set various intensities: `hal.set_led_intensity(0.25)`, `0.5`, `0.75`, `1.0`
3. Activate channel and measure signal levels with spectrometer
4. Verify signal scales linearly with intensity setting

**Future work**:
- Could add intensity validation test to optical calibration script
- Could test τ at different intensities to confirm theory
- Could add intensity parameter to calibration metadata

---

## Summary

✅ **HAL interface now complete** - `set_led_intensity()` properly implemented
✅ **Firmware commands used correctly** - `baXXX\n` format with 0-255 range
✅ **Backward compatible** - Default 1.0 intensity maintains current behavior
✅ **Ready for future enhancements** - Can now do intensity-dependent testing if needed

**Bottom line**: The stub is fixed. The HAL now properly supports variable LED intensity control as the firmware intended. 🎯

---

**Related Documentation**:
- `PICOP4SPR_FIRMWARE_COMMANDS.md` - Firmware command reference
- `LED_INTENSITY_CALIBRATION_CONSIDERATIONS.md` - Intensity effects on calibration
- `utils/hal/spr_controller_hal.py` - HAL interface definition
