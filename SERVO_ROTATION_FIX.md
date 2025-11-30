# Servo Rotation Fix - November 29, 2025

## Problem
Polarizer servo was not rotating despite commands being sent successfully. Signal measurements showed no variation across different servo positions (0.5% range), indicating the servo was stuck in one position.

## Root Cause
The firmware requires a **3-step command sequence** to physically move the servo:

1. `servo_set(s, p)` - Sets target positions in RAM/EEPROM
2. `flash()` - Saves positions to EEPROM
3. `set_mode('s' or 'p')` - **Actually moves the servo** to the stored position

The code was **only calling step 1**, which sets positions but doesn't trigger physical movement.

## Firmware Command Details

### Wrong (What was being used):
```python
ctrl.servo_set(s=45, p=135)  # Sets positions but servo doesn't move!
time.sleep(0.3)
```

### Correct (What firmware actually requires):
```python
# Step 1: Set positions
ctrl.servo_set(s=45, p=135)
time.sleep(0.1)

# Step 2: Flash to EEPROM
ctrl.flash()
time.sleep(0.1)

# Step 3: Move to position (this actually moves the servo!)
ctrl.set_mode('s')  # Moves to S position
# OR
ctrl.set_mode('p')  # Moves to P position
time.sleep(0.5)  # Wait for physical movement
```

### Why This Design?
The P4SPR firmware uses **mode commands** (`ss\n` / `sp\n`) to switch between S and P polarization states during live acquisition. These modes read positions from EEPROM, so:
- Calibration finds optimal positions
- Positions are saved to EEPROM via `flash()`
- Live acquisition just sends `ss`/`sp` to toggle between saved positions (fast!)

## Files Modified

### 1. `src/utils/servo_calibration.py`
Added helper function:
```python
def _move_servo_to_position(ctrl, angle: int, mode: str = 's', wait_time: float = 0.5):
    """Move servo using correct 3-step firmware sequence."""
    ctrl.servo_set(s=angle, p=angle)
    time.sleep(0.1)
    ctrl.flash()
    time.sleep(0.1)
    ctrl.set_mode(mode)
    time.sleep(wait_time)
    return True
```

Updated all servo movement calls in:
- `perform_quadrant_search()` - Main calibration function
- `verify_and_correct_positions()` - Position verification
- `measure_position()` helper

### 2. `quick_polarizer_test.py`
Updated scanning loop to use correct sequence:
```python
for angle in positions:
    ctrl.servo_set(s=angle, p=angle)
    time.sleep(0.1)
    ctrl.flash()
    time.sleep(0.1)
    ctrl.set_mode('s')
    time.sleep(0.5)  # Wait for movement
    # Now measure...
```

## Test Results

### Before Fix (Servo not moving):
```
Position  Signal
   10°    36281 counts
   50°    36307 counts
   90°    36165 counts
  130°    36141 counts
  170°    36130 counts

Range: 177 counts (0.5% variation)
S/P Ratio: 1.00x (no polarization effect visible)
```

### After Fix (Servo rotating correctly):
```
Position  Signal
   10°    28993 counts ← P position (minimum)
   50°    36289 counts
   90°    49165 counts ← S position (maximum)
  130°    40849 counts
  170°    32912 counts

Range: 20,172 counts (70% variation)
S/P Ratio: 1.70x (excellent polarization effect!)
```

## Calibration Results
- **P Position**: 10° (minimum transmission, strongest SPR absorption)
- **S Position**: 90° (maximum transmission, reference)
- **Separation**: 80° (close to ideal 90° for circular polarizer)
- **Signal Quality**: 1.70x S/P ratio (exceeds 1.3x minimum requirement)

## Verification Tests

### Test 1: Manual Servo Movement (`test_servo_rotation.py`)
- Sent commands to positions: 0°, 45°, 90°, 135°, 180°
- User confirmed: **No physical movement observed**
- All commands returned success but servo didn't move

### Test 2: Mode Commands (`test_servo_flash.py`)
- Set positions: S=45°, P=135°
- Flashed to EEPROM
- Used `set_mode('s')` and `set_mode('p')`
- User confirmed: **Servo moved!** ✓

### Test 3: Full Calibration (`quick_polarizer_test.py`)
- 5-position scan with corrected commands
- Servo rotated through all positions
- Got clean polarization signal (1.70x ratio)

## Hardware Details
- **Controller**: P4SPR firmware 1V1. on COM4
- **Servo**: Circular polarizer servo (0-180° range)
- **Spectrometer**: FLMT09116 Flame-T
- **LED**: Channel B at intensity 64

## Future Recommendations

1. **Update Documentation**: Add firmware command sequence to PICOP4SPR_FIRMWARE_COMMANDS.md
2. **Add Comments**: Document the 3-step sequence wherever servo movement is used
3. **Error Handling**: Check if `set_mode()` returns False and retry
4. **Timing Optimization**: May be able to reduce flash/wait times for faster calibration

## References
- `docs/hardware/PICOP4SPR_FIRMWARE_COMMANDS.md` - Firmware command reference
- `src/utils/controller.py` - Lines 1190-1200 (`set_mode()` implementation)
- `src/utils/controller.py` - Lines 1280-1305 (`servo_set()` implementation)
- `src/utils/controller.py` - Lines 1305-1365 (`flash()` implementation)

---
**Issue Resolved**: November 29, 2025, 23:46
**Status**: ✅ Servo rotation working, calibration successful
