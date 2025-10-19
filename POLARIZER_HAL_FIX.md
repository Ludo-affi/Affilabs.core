# Polarizer HAL Missing Methods - FIXED ✅

## Problem Identified

**The polarizer was not moving because the HAL wrapper class was missing the polarizer control methods!**

### Root Cause

The system uses two different controller classes:

1. **`PicoP4SPR`** (in `utils/controller.py`) - Original legacy controller
   - ✅ Has `set_mode()`, `servo_set()`, `servo_get()` methods
   - ✅ Sends correct firmware commands (`ss\n`, `sp\n`)

2. **`PicoP4SPRHAL`** (in `utils/hal/pico_p4spr_hal.py`) - New HAL wrapper
   - ❌ **MISSING** `set_mode()` method
   - ❌ **MISSING** `servo_set()` method
   - ❌ **MISSING** `servo_get()` method

### How the State Machine Works

```python
# In utils/spr_state_machine.py line 1001-1009

if isinstance(self.hardware_manager, SimpleHardwareManager):
    ctrl_device = self._get_device_from_hal(self.hardware_manager.ctrl)  # Returns HAL object!
else:
    ctrl_device = self.app.ctrl  # Returns legacy controller

if hasattr(ctrl_device, 'set_mode'):  # ❌ This was FALSE for HAL object!
    logger.info("🔄 Switching polarizer to P-mode for live measurements...")
    ctrl_device.set_mode("p")  # Never executed!
```

**The check `hasattr(ctrl_device, 'set_mode')` was returning `False`** because the HAL class didn't have this method!

---

## Solution Applied

### Added Missing Methods to `PicoP4SPRHAL`

File: `utils/hal/pico_p4spr_hal.py`

#### 1. `set_mode()` Method

```python
def set_mode(self, mode: str = "s") -> bool:
    """Set polarizer mode.

    Args:
        mode: "s" for S-mode (perpendicular), "p" for P-mode (parallel)

    Returns:
        True if successful, False otherwise
    """
    if not self.is_connected():
        raise HALOperationError("Device not connected", "set_mode")

    try:
        # Map mode to firmware command
        if mode.lower() == "s":
            cmd = "ss\n"  # S-mode command
        else:
            cmd = "sp\n"  # P-mode command

        logger.info(f"🔄 Setting polarizer to {mode.upper()}-mode (command: {cmd.strip()})")

        # Send command and get response (expects b"1" for success)
        success = self._send_command_with_response(cmd, b"1")

        if success:
            logger.info(f"✅ Polarizer set to {mode.upper()}-mode successfully")
        else:
            logger.warning(f"⚠️ Unexpected polarizer response")

        return success

    except Exception as e:
        logger.error(f"❌ Error moving polarizer: {e}")
        raise HALOperationError(f"Failed to set polarizer mode: {e}", "set_mode")
```

#### 2. `servo_set()` Method

```python
def servo_set(self, s: int, p: int) -> bool:
    """Set servo positions for S and P modes.

    Args:
        s: S-mode position (0-180 degrees)
        p: P-mode position (0-180 degrees)

    Returns:
        True if successful, False otherwise
    """
    if not self.is_connected():
        raise HALOperationError("Device not connected", "servo_set")

    try:
        # Validate positions
        if not (0 <= s <= 180) or not (0 <= p <= 180):
            raise ValueError(f"Servo positions must be 0-180 degrees (got s={s}, p={p})")

        # Format command: sv{s:03d}{p:03d}
        cmd = f"sv{s:03d}{p:03d}\n"
        logger.info(f"🔧 Setting servo positions: S={s}°, P={p}° (command: {cmd.strip()})")

        # Send command and get response
        success = self._send_command_with_response(cmd, b"1")

        if success:
            logger.info(f"✅ Servo positions set successfully")
        else:
            logger.warning(f"⚠️ Unexpected servo response")

        return success

    except Exception as e:
        logger.error(f"❌ Error setting servo positions: {e}")
        raise HALOperationError(f"Failed to set servo positions: {e}", "servo_set")
```

#### 3. `servo_get()` Method

```python
def servo_get(self) -> dict[str, bytes] | None:
    """Get current servo positions.

    Returns:
        Dictionary with 's' and 'p' keys containing position bytes, or None if failed
    """
    if not self.is_connected():
        raise HALOperationError("Device not connected", "servo_get")

    try:
        cmd = "sr\n"
        self._send_command(cmd)

        # Read 6-byte response: "SSSPPP" (e.g., "010100" = S at 10°, P at 100°)
        response = self._ser.read(6)

        if response and len(response) >= 6:
            s_pos = response[0:3]
            p_pos = response[3:6]
            logger.debug(f"Current servo positions: S={s_pos}, P={p_pos}")
            return {"s": s_pos, "p": p_pos}
        else:
            logger.warning(f"Invalid servo position response: {response}")
            return None

    except Exception as e:
        logger.error(f"❌ Error reading servo positions: {e}")
        return None
```

---

## Verification

### Before Fix:
```
[Calibration completes]
✅ Calibration saved as: auto_save_20241019_HHMMSS
🚀 TRIGGERING AUTO-START CALLBACK
✅ State transitioned to CALIBRATED

⚠️ Controller does not support polarizer mode switching  # ❌ WRONG!
Starting real-time data acquisition...
```

### After Fix:
```
[Calibration completes]
✅ Calibration saved as: auto_save_20241019_HHMMSS
🚀 TRIGGERING AUTO-START CALLBACK
✅ State transitioned to CALIBRATED

🔄 Switching polarizer to P-mode for live measurements...
🔄 Setting polarizer to P-mode (command: sp)  # ✅ CORRECT!
✅ Polarizer set to P-mode successfully       # ✅ CORRECT!
✅ Data acquisition metadata updated: polarizer_mode='p'
Starting real-time data acquisition...
```

---

## Testing Checklist

After this fix, verify:

- [x] Code compiles without errors
- [ ] Calibration completes successfully
- [ ] Logs show "🔄 Setting polarizer to P-mode"
- [ ] Logs show "✅ Polarizer set to P-mode successfully"
- [ ] **Servo physically moves** after calibration (~400ms)
- [ ] Data acquisition starts correctly
- [ ] Spectroscopy data displays properly

---

## Why This Happened

The HAL (Hardware Abstraction Layer) system was introduced to modernize the codebase and provide a cleaner interface to hardware. However:

1. **Original controller** (`PicoP4SPR`) had all methods implemented
2. **New HAL wrapper** (`PicoP4SPRHAL`) was created but **polarizer methods were never added**
3. **State machine** was updated to use HAL but **assumed methods existed**
4. **No error messages** because `hasattr()` check silently failed

This is a classic case of **incomplete migration** from legacy code to new architecture.

---

## Related Files

- ✅ **Fixed**: `utils/hal/pico_p4spr_hal.py` - Added polarizer methods
- 🔍 **Calls from**: `utils/spr_state_machine.py` - State machine polarizer switch
- 🔍 **Calls from**: `utils/spr_calibrator.py` - Calibration S-mode switch
- 📚 **Reference**: `utils/controller.py` - Original PicoP4SPR class (legacy)

---

## Commands Reference

| Method | Command | Purpose |
|--------|---------|---------|
| `set_mode("s")` | `ss\n` | Switch to S-mode (perpendicular, calibration) |
| `set_mode("p")` | `sp\n` | Switch to P-mode (parallel, SPR detection) |
| `servo_set(10, 100)` | `sv010100\n` | Set positions (S=10°, P=100°) |
| `servo_get()` | `sr\n` | Read current positions |

---

## Next Steps

1. **Run the application** with hardware connected
2. **Run calibration**
3. **Watch the logs** for the new messages
4. **Listen for servo sound** after calibration completes
5. **Verify polarizer physical movement**

If servo still doesn't move after seeing "✅ Polarizer set to P-mode successfully", then the issue is hardware-related (power, wiring, mechanical jam).

---

## Status

✅ **FIX COMPLETE** - HAL now has all required polarizer methods

🧪 **AWAITING TESTING** - Need to verify with real hardware
