# Polarizer Position Validation Feature

**Date**: October 19, 2025
**Status**: ✅ Implemented
**Location**: `utils/spr_calibrator.py`

## Overview

The calibration system now includes **automatic polarizer position validation** during Step 2B. This ensures the polarizer is correctly configured before proceeding with LED calibration.

## How It Works

### Validation Logic

During calibration (Step 2B), the system:

1. **Turns on LED A** at moderate intensity (150/255)
2. **Measures S-mode** intensity (perpendicular polarization)
3. **Measures P-mode** intensity (parallel polarization)
4. **Calculates S/P ratio**
5. **Validates ratio** against expected thresholds

### Expected Behavior

**Correct polarizer configuration:**
- **S-mode**: HIGH intensity (perpendicular to SPR sensing layer)
- **P-mode**: LOW intensity (parallel to SPR sensing layer)
- **Ratio**: S-mode should be **3-10× higher** than P-mode

## Validation Thresholds

| Threshold | Value | Behavior |
|-----------|-------|----------|
| **Minimum Ratio** | 2.0× | Below this → **Calibration FAILS** |
| **Ideal Range** | 3.0-15.0× | Optimal performance |
| **Warning Range** | 2.0-3.0× | Allows calibration with warning |
| **High Ratio** | >15.0× | P-mode may be blocking too much (warning) |

## Error Messages

### ❌ Critical Error (S/P < 2.0×)

```
❌ POLARIZER POSITION ERROR DETECTED
   S-mode intensity (1200) is NOT significantly higher than P-mode (1100)
   Ratio: 1.09x (expected: >2.0x)

Possible causes:
   1. Polarizer positions are swapped (S and P reversed)
   2. Servo positions need adjustment
   3. Polarizer not properly aligned

💡 Solution: Run auto-polarization from Settings menu
```

**Result**: Calibration stops. User must fix polarizer positions.

### ⚠️ Warning (2.0× < S/P < 3.0×)

```
⚠️ POLARIZER POSITION WARNING
   S/P ratio (2.5x) is lower than ideal (3.0-15.0x)
   Calibration will continue, but consider running auto-polarization
   (Available in Settings menu)
```

**Result**: Calibration continues with warning logged.

### ✅ Success (3.0× < S/P < 15.0×)

```
✅ Polarizer positions VALIDATED (ratio: 5.2x is ideal)
```

**Result**: Calibration proceeds normally.

## Auto-Polarization (Advanced Feature)

Auto-polarization is **NOT enabled by default** during calibration. It is an **advanced feature** accessible through:

- **Settings Menu** → "Polarizer Alignment"
- **Manual calibration mode**

### Why Not Auto-Run?

1. **Time**: Adds ~30-60 seconds to calibration
2. **Not always needed**: Most systems have stable polarizer positions
3. **Advanced users**: Requires understanding of polarizer mechanics
4. **Validation is enough**: Checks if positions are correct without changing them

### When to Use Auto-Polarization

- Initial system setup
- After hardware maintenance
- After polarizer replacement
- When validation fails
- When S/P ratio is below ideal range

## Implementation Details

### Method: `validate_polarizer_positions()`

**Location**: `utils/spr_calibrator.py` (lines ~1605-1684)

**Flow**:
```python
def validate_polarizer_positions(self) -> bool:
    # Turn on LED A at 150/255
    # Measure S-mode → s_max
    # Measure P-mode → p_max
    # Calculate ratio = s_max / p_max

    if ratio < 2.0:
        return False  # FAIL - positions invalid
    elif ratio < 3.0:
        # WARNING - suboptimal but acceptable
        return True
    else:
        # SUCCESS - positions validated
        return True
```

### Integration in Calibration

**Location**: `run_full_calibration()` (lines ~3373-3380)

```python
# ========================================================================
# STEP 2B: POLARIZER POSITION VALIDATION
# ========================================================================
self._emit_progress(2, "Step 2B: Validating polarizer positions...")
polarizer_valid = self.validate_polarizer_positions()
if not polarizer_valid:
    self._safe_hardware_cleanup()
    return False, "Polarizer positions invalid - run auto-polarization from Settings"
```

## Testing

### Expected Log Output (Success)

```
================================================================================
STEP 2B: Polarizer Position Validation
================================================================================
Verifying S-mode and P-mode positions are correct...
   S-mode intensity: 8500.2 counts
   P-mode intensity: 1650.8 counts
   S/P ratio: 5.15x
✅ Polarizer positions VALIDATED (ratio: 5.15x is ideal)
================================================================================
```

### Expected Log Output (Failure)

```
================================================================================
STEP 2B: Polarizer Position Validation
================================================================================
Verifying S-mode and P-mode positions are correct...
   S-mode intensity: 2100.5 counts
   P-mode intensity: 1980.3 counts
   S/P ratio: 1.06x
================================================================================
❌ POLARIZER POSITION ERROR DETECTED
================================================================================
   S-mode intensity (2100.5) is NOT significantly higher than P-mode (1980.3)
   Ratio: 1.06x (expected: >2.0x)

Possible causes:
   1. Polarizer positions are swapped (S and P reversed)
   2. Servo positions need adjustment
   3. Polarizer not properly aligned

💡 Solution: Run auto-polarization from Settings menu
================================================================================
```

## Troubleshooting

### Problem: Validation Always Fails

**Possible Causes**:
1. S and P servo positions are swapped in configuration
2. Polarizer physically installed backwards
3. Servo motor not moving (mechanical issue)

**Solution**:
```python
# Check current servo positions
ctrl.servo_get()  # Should return "s=010,p=100"

# Try swapping S and P positions
ctrl.servo_set(s=100, p=10)  # Reverse positions

# Or run auto-polarization to find optimal positions
calibrator.auto_polarize(ctrl, usb)
```

### Problem: S/P Ratio Too High (>15×)

**Possible Causes**:
1. P-mode blocking too much light (over-polarized)
2. Polarizer angle too extreme
3. LED too dim in P-mode

**Solution**: Usually acceptable, but can optimize with:
```python
# Run auto-polarization to find better balance
calibrator.auto_polarize(ctrl, usb)
```

### Problem: Validation Skipped

**Cause**: Hardware not available (ctrl or usb is None)

**Behavior**: Validation returns `True` with warning:
```
⚠️ Cannot validate polarizer - hardware not available
```

## Configuration

### Default Values

**File**: `utils/settings.py`

```python
# Polarizer servo positions (degrees)
S_POSITION = 10   # Perpendicular polarization
P_POSITION = 100  # Parallel polarization

# Valid range: 0-180° (servo motor limits)
MAX_POLARIZER_ANGLE = 180
```

### Validation Thresholds

**File**: `utils/spr_calibrator.py`

```python
MIN_RATIO = 2.0          # Minimum acceptable S/P ratio
IDEAL_RATIO_MIN = 3.0    # Lower bound of ideal range
IDEAL_RATIO_MAX = 15.0   # Upper bound of ideal range
```

## Summary

✅ **Implemented**: Automatic validation in Step 2B
✅ **Non-invasive**: Checks positions without changing them
✅ **Clear feedback**: Errors guide user to solution
✅ **Optional optimization**: Auto-polarization available in Settings
✅ **Fail-safe**: Allows calibration to continue with warnings when appropriate

This feature ensures polarizer is correctly configured without adding unnecessary calibration time or complexity.
