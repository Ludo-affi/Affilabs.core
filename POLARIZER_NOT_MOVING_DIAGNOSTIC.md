# Polarizer Not Moving - Diagnostic Guide

## Issue
Polarizer servo is not physically moving to P-mode after calibration completes.

## Expected Flow

```
1. Calibration completes successfully in SPRCalibrator
   └─> Triggers on_calibration_complete_callback()

2. Callback executes auto_start_live_measurements() in state machine
   └─> Calls _transition_to_state(SPRSystemState.CALIBRATED)

3. State machine enters CALIBRATED state
   └─> Calls _handle_calibrated()

4. _handle_calibrated() switches polarizer (LINE 1007-1011)
   └─> ctrl_device.set_mode("p")
   └─> Sends "sp\n" command to hardware

5. Polarizer servo should physically move (~400ms)
```

## Where Polarizer Switching Happens

**File**: `utils/spr_state_machine.py`
**Lines**: 1007-1011

```python
logger.info("🔄 Switching polarizer to P-mode for live measurements...")
try:
    ctrl_device.set_mode("p")
    time.sleep(0.4)  # Wait for servo to rotate (400ms settling time)
    logger.info("✅ Polarizer switched to P-mode")
```

## Diagnostic Steps

### Step 1: Check if Auto-Start Callback is Triggered

**Look for these log messages after calibration:**

```
================================================================================
🚀 TRIGGERING AUTO-START CALLBACK
================================================================================
✅ Auto-start callback executed successfully
```

**If you DON'T see this:**
- Auto-start callback is NOT being called
- Problem is in calibrator not calling the callback
- Check: `self.on_calibration_complete_callback` is None

**If you DO see this:**
- Callback is working, proceed to Step 2

---

### Step 2: Check if State Transition Happens

**Look for these log messages:**

```
================================================================================
🚀 AUTO-STARTING LIVE MEASUREMENTS (from calibration callback)
================================================================================
State transition: calibrating → calibrated
✅ State transitioned to CALIBRATED - acquisition will start automatically
```

**If you DON'T see this:**
- State transition failed
- Problem is in `_transition_to_state()` method
- Exception may have been caught silently

**If you DO see this:**
- State transition worked, proceed to Step 3

---

### Step 3: Check if Polarizer Switch is Attempted

**Look for these log messages:**

```
🔄 Switching polarizer to P-mode for live measurements...
✅ Polarizer switched to P-mode
```

**If you DON'T see this:**
- `_handle_calibrated()` is not reaching the polarizer switch code
- Problem is before line 1007 in state machine
- Check: Hardware devices might be None
- Check: `hasattr(ctrl_device, 'set_mode')` might be False

**If you DO see this:**
- Command was sent, proceed to Step 4

---

### Step 4: Check Hardware Command Execution

**Look for these log messages in controller.py:**

```
🔄 Setting polarizer to P-mode (command: sp)
✅ Polarizer set to P-mode successfully
```

**If you DON'T see this:**
- `set_mode("p")` is being called but not executing
- Problem is in `utils/controller.py` PicoP4SPR.set_mode()
- Check: `self.valid()` might be False
- Check: Serial connection might be closed

**If you DO see this:**
- Command reached hardware, proceed to Step 5

---

### Step 5: Check Physical Servo Movement

**What to check:**

1. **Listen for servo sound**: You should hear a ~400ms buzzing/whirring sound
2. **Visual check**: Polarizer should rotate ~90 degrees
3. **Voltage check**: Servo should receive 5V power

**If servo doesn't move despite correct commands:**

#### Hardware Issues:
- ❌ Servo power disconnected (check 5V supply)
- ❌ Servo control wire disconnected (check signal pin)
- ❌ Servo mechanically jammed or broken
- ❌ Servo already at P-position (check current position)

#### Position Issues:
- ❌ S and P positions might be identical (check servo positions)
- ❌ Servo might already be at 100° (P-position)
- ❌ Positions not properly configured in EEPROM

---

## Quick Diagnostic Commands

### Check Current Servo Position

Run this in Python console or add to code:
```python
# Get current servo positions
if hasattr(ctrl, 'servo_get'):
    positions = ctrl.servo_get()
    print(f"Current positions: S={positions['s']}, P={positions['p']}")
```

### Manually Test Servo Movement

Run this to force servo to move:
```python
# Force move to S-mode
ctrl.set_mode("s")
time.sleep(0.5)

# Force move to P-mode
ctrl.set_mode("p")
time.sleep(0.5)

# You should hear/see movement
```

### Check Serial Connection

```python
# Check if device is still valid
print(f"Controller valid: {ctrl.valid()}")
print(f"Serial port open: {ctrl._hal._serial_port.is_open if hasattr(ctrl._hal, '_serial_port') else 'N/A'}")
```

---

## Common Issues

### Issue 1: Callback Not Set
**Symptom**: No "TRIGGERING AUTO-START CALLBACK" message

**Solution**: Check that callback is registered:
```python
# In _handle_connecting, around line 874
self.calibrator.set_on_calibration_complete_callback(auto_start_live_measurements)
```

---

### Issue 2: State Machine Stuck
**Symptom**: Callback triggers but no state transition

**Solution**: Check for exceptions in auto_start_live_measurements():
```python
def auto_start_live_measurements():
    try:
        self._transition_to_state(SPRSystemState.CALIBRATED)
    except Exception as e:
        logger.exception(f"Failed to auto-start: {e}")
```

---

### Issue 3: Controller Invalid
**Symptom**: Commands sent but servo doesn't move

**Solution**: Check controller validity:
- Serial connection might have closed
- Device might have been disconnected
- Re-establish connection

---

### Issue 4: Positions Not Configured
**Symptom**: Servo moves but to wrong position

**Solution**: Set proper positions:
```python
ctrl.servo_set(s=10, p=100)  # S at 10°, P at 100°
ctrl.flash()  # Save to EEPROM
```

---

## Testing Procedure

1. **Run calibration with verbose logging**
2. **Copy ALL log output to a text file**
3. **Search for each diagnostic message listed above**
4. **Identify where the chain breaks**
5. **Follow the specific solution for that step**

---

## Expected Log Sequence (Success)

```
Step 7: Reference Signal Measurement (S-mode)
[... calibration measurements ...]

Step 8: Calibration Validation (Using Step 7 Data)
✅ Calibration validation passed for all channels

💾 Auto-saving calibration data...
✅ Calibration saved as: auto_save_20241019_HHMMSS

================================================================================
🚀 TRIGGERING AUTO-START CALLBACK
================================================================================
✅ Auto-start callback executed successfully

================================================================================
🚀 AUTO-STARTING LIVE MEASUREMENTS (from calibration callback)
================================================================================
State transition: calibrating → calibrated
✅ State transitioned to CALIBRATED - acquisition will start automatically

📊 CALIBRATION SUMMARY
[... summary info ...]

🔄 Switching polarizer to P-mode for live measurements...
🔄 Setting polarizer to P-mode (command: sp)
✅ Polarizer set to P-mode successfully
✅ Polarizer switched to P-mode
✅ Data acquisition metadata updated: polarizer_mode='p'

Starting real-time data acquisition...
[... data acquisition starts ...]
```

---

## If Polarizer Still Doesn't Move

After checking all diagnostic steps, if the servo still doesn't move:

1. **Test servo manually** outside the application
2. **Check servo power supply** (5V)
3. **Check servo signal wire** connection
4. **Try different servo positions** (e.g., 50 and 140 degrees)
5. **Test with servo tester** or Arduino

The servo itself might be faulty or mechanically jammed.

---

## Next Steps

1. Run your application with logging enabled
2. Copy the complete log output
3. Search for the diagnostic messages above
4. Report which messages you see/don't see
5. This will pinpoint exactly where the issue is

**The code is correct - if polarizer isn't moving, it's either:**
- Callback not being called (software issue)
- Serial command not reaching device (connection issue)
- Servo not responding to commands (hardware issue)

Use the diagnostic steps above to determine which!
