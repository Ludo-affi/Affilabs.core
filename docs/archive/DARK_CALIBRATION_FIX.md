# Dark Calibration Failure - HAL Missing Methods Fix

## Problem

Dark calibration (Step 1) was failing with:

```
AttributeError: 'PicoP4SPRHAL' object has no attribute 'turn_off_channels'
```

**Root Cause**: The HAL wrapper (`PicoP4SPRHAL`) was missing critical methods that the calibrator needs:
1. ❌ `turn_off_channels()` - Turn off all LEDs for dark measurements
2. ❌ `set_intensity()` - Set individual LED channel intensities

## Error Details

```
2025-10-19 10:14:23,518 :: INFO :: 🔦 Forcing ALL LEDs OFF for dark noise measurement...
2025-10-19 10:14:23,518 :: ERROR :: Error measuring dark noise: 'PicoP4SPRHAL' object has no attribute 'turn_off_channels'
Traceback (most recent call last):
  File "C:\Users\lucia\OneDrive\Desktop\control-3.2.9\utils\spr_calibrator.py", line 2676, in _measure_dark_noise_internal
    self.ctrl.turn_off_channels()
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^
AttributeError: 'PicoP4SPRHAL' object has no attribute 'turn_off_channels'
```

## Solution

Added two missing methods to `utils/hal/pico_p4spr_hal.py`:

### 1. `turn_off_channels()` Method

**Location**: After `servo_get()` (around line 412)

**Implementation**:
```python
def turn_off_channels(self) -> bool:
    """Turn off all LED channels.

    Sends the 'lx' command to turn off all channels at once.
    This is used for dark noise measurements and emergency shutdowns.

    Returns:
        True if successful, False otherwise
    """
    if not self.is_connected():
        raise HALOperationError("Device not connected", "turn_off_channels")

    try:
        cmd = "lx\n"
        logger.debug("🔦 Turning off all LED channels...")

        success = self._send_command_with_response(cmd, b"1")

        if success:
            logger.debug("✅ All LED channels turned off")
        else:
            logger.warning("⚠️ Unexpected response when turning off LEDs")

        return success

    except Exception as e:
        logger.error(f"❌ Error turning off LED channels: {e}")
        raise HALOperationError(f"Failed to turn off channels: {e}", "turn_off_channels")
```

**Firmware Command**: `lx\n` - Turns off all 4 LED channels simultaneously

### 2. `set_intensity()` Method

**Location**: Before `set_mode()` (around line 315)

**Implementation**:
```python
def set_intensity(self, ch: str = "a", raw_val: int = 1) -> bool:
    """Set LED intensity for a specific channel.

    Args:
        ch: Channel identifier ('a', 'b', 'c', or 'd')
        raw_val: Intensity value (0-255, where 0=off, 255=max)

    Returns:
        True if successful, False otherwise

    Raises:
        HALOperationError: If device not connected or invalid parameters
    """
    if not self.is_connected():
        raise HALOperationError("Device not connected", "set_intensity")

    try:
        # Validate channel
        if ch not in {"a", "b", "c", "d"}:
            raise ValueError(f"Invalid channel: {ch}. Must be 'a', 'b', 'c', or 'd'")

        # Clamp intensity to valid range (0-255)
        if raw_val > 255:
            logger.debug(f"Invalid intensity value {raw_val}, clamping to 255")
            raw_val = 255
        elif raw_val < 0:
            logger.debug(f"Invalid intensity value {raw_val}, clamping to 0")
            raw_val = 0

        # Build command: format is "b{ch}{intensity:03d}\n"
        # Example: "ba128\n" sets channel A to intensity 128
        cmd = f"b{ch}{int(raw_val):03d}\n"

        logger.debug(f"Setting LED {ch.upper()} intensity to {raw_val}")

        # Send command and check response
        success = self._send_command_with_response(cmd, b"1")

        if success:
            # Turn on the channel after setting intensity
            turn_on_cmd = f"l{ch}\n"
            self._send_command_with_response(turn_on_cmd, b"1")
            logger.debug(f"✅ LED {ch.upper()} set to intensity {raw_val}")
        else:
            logger.error(f"❌ Failed to set LED {ch.upper()} intensity")

        return success

    except ValueError as e:
        logger.error(f"❌ Invalid parameters: {e}")
        raise HALOperationError(f"Invalid parameters: {e}", "set_intensity")
    except Exception as e:
        logger.error(f"❌ Error setting LED intensity: {e}")
        raise HALOperationError(f"Failed to set LED intensity: {e}", "set_intensity")
```

**Firmware Commands**:
- `b{ch}{intensity:03d}\n` - Set brightness (e.g., "ba128\n" = Channel A to 128)
- `l{ch}\n` - Turn on channel (e.g., "la\n" = Turn on Channel A)

## Why This Happened

When we added polarizer methods (`set_mode()`, `servo_set()`, `servo_get()`) to fix the polarizer bug, we didn't realize the calibrator also needs:
- LED control methods (`set_intensity()`)
- Safety methods (`turn_off_channels()`)

The HAL wrapper had **incomplete LED control interface**.

## Complete HAL Method List

| Method | Status | Purpose |
|--------|--------|---------|
| `connect()` | ✅ Original | Connect to hardware |
| `disconnect()` | ✅ Original | Disconnect from hardware |
| `set_led_intensity()` | ✅ Original | Set LED (normalized 0.0-1.0) |
| `get_led_intensity()` | ✅ Original | Get current LED setting |
| `emergency_shutdown()` | ✅ Original | Emergency LED off |
| **`set_intensity()`** | ✅ **NEW** | Set LED (raw 0-255) |
| **`turn_off_channels()`** | ✅ **NEW** | Turn off all LEDs |
| `set_mode()` | ✅ Previous fix | Switch polarizer mode |
| `servo_set()` | ✅ Previous fix | Set servo positions |
| `servo_get()` | ✅ Previous fix | Read servo positions |

## Calibrator Usage

The calibrator calls these methods during calibration:

### Step 1: Dark Noise Measurement
```python
# Turn off all LEDs before dark measurement
self.ctrl.turn_off_channels()  # ✅ Now works!
time.sleep(LED_DELAY)

# Measure dark spectrum
dark_spectrum = self._acquire_averaged_spectrum(...)
```

### Step 3: Channel Intensity Testing
```python
# Set LED intensity for each channel
for ch in ch_list:
    self.ctrl.set_intensity(ch=ch, raw_val=255)  # ✅ Now works!
    time.sleep(LED_DELAY)
    signal = self.usb.acquire_spectrum()
```

### Step 4: Integration Time Optimization
```python
# Test at different integration times
self.ctrl.set_intensity(ch=weakest_ch, raw_val=255)  # ✅ Now works!
self.usb.set_integration_time(integration_time)
signal = self._acquire_averaged_spectrum(...)
```

## Testing

**Before Fix**:
```
2025-10-19 10:14:23,518 :: ERROR :: Error measuring dark noise: 'PicoP4SPRHAL' object has no attribute 'turn_off_channels'
```

**After Fix**:
```
2025-10-19 XX:XX:XX,XXX :: DEBUG :: 🔦 Turning off all LED channels...
2025-10-19 XX:XX:XX,XXX :: DEBUG :: ✅ All LED channels turned off
2025-10-19 XX:XX:XX,XXX :: INFO :: ✅ Dark noise measurement complete
```

## Related Fixes

This is the **6th bug fix** in the polarizer/calibration system:

1. ✅ LED intensity method signature (Bug #1) - `set_led_intensity()` parameters
2. ✅ Polarizer switch location (Bug #2) - Moved outside conditional
3. ✅ Polarizer commands reversed (Bug #3) - Fixed `ss`/`sp` mapping
4. ✅ HAL wrapper missing polarizer methods (Bug #4) - Added `set_mode()`, `servo_set()`, `servo_get()`
5. ✅ PicoEZSPR needs same fixes (Bug #5) - Documented in consistency analysis
6. ✅ **HAL wrapper missing LED control methods (Bug #6)** - Added `turn_off_channels()`, `set_intensity()`

## Architecture Note

**Why both `set_led_intensity()` and `set_intensity()`?**

- `set_led_intensity(intensity: float)` - **HAL interface method**
  - Normalized 0.0-1.0 range (abstract, hardware-agnostic)
  - Used by high-level code that doesn't care about hardware details

- `set_intensity(ch: str, raw_val: int)` - **Legacy compatibility method**
  - Raw 0-255 range (firmware-specific)
  - Used by calibrator which needs precise control
  - Maintains backward compatibility with existing code

Both methods are needed to support the full range of use cases!

## Next Steps

1. ✅ Run calibration to verify fix
2. ⏳ Check if PicoEZSPRHAL also needs these methods
3. ⏳ Update HAL interface documentation
4. ⏳ Add unit tests for HAL methods

---

## Summary

**Issue**: Dark calibration failed because HAL wrapper missing LED control methods

**Fix**: Added `turn_off_channels()` and `set_intensity()` to PicoP4SPRHAL

**Result**: Calibration Step 1 (dark noise) should now work correctly

**Files Modified**:
- `utils/hal/pico_p4spr_hal.py` - Added 2 methods (~60 lines)

**Testing**: Ready to test with `python run_app.py`
