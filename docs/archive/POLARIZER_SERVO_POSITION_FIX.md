# Polarizer Servo Position Fix - Units Correction

## Issue
The codebase incorrectly used "degrees" terminology for polarizer servo positions, when the actual hardware uses **0-255 raw servo positions** (NOT degrees).

## Changes Made

### 1. **Constant Rename** (Line 147)
**Before:**
```python
MAX_POLARIZER_ANGLE = 170  # Maximum polarizer angle in degrees
```

**After:**
```python
MAX_POLARIZER_POSITION = 255  # Maximum servo position (raw value, NOT degrees)
```

### 2. **Servo Validation Range** (Line 896)
**Before:**
```python
if (s < 0) or (p < 0) or (s > 180) or (p > 180):
    raise ValueError(f"Invalid polarizer position given: {s}, {p}")
```

**After:**
```python
if (s < 0) or (p < 0) or (s > 255) or (p > 255):
    raise ValueError(f"Invalid polarizer position given: {s}, {p} (must be 0-255)")
```

### 3. **Removed Misleading "°" Symbols**

All logging statements that used "°" (degree symbol) were updated to clarify these are **0-255 raw servo positions**, not angular degrees:

- **Step 2B Validation** (lines 1650-1675):
  - Changed: `"labeled-S={s_hardware}°"` → `"labeled-S={s_hardware} (0-255 scale)"`
  - Changed: `"S={position}° (LOW)"` → `"S={position} (LOW)"`
  - Changed all position displays to remove "°" and add "(0-255 scale)" where appropriate

- **Validation Error Messages** (lines 1710-1750):
  - Updated all servo position displays to show raw values without degree symbols
  - Added "(0-255 scale)" clarification

- **Profile Save/Load** (lines 3720-3815):
  - Updated comments: `"S at 100°"` → `"S at 100 (0-255 scale)"`
  - Updated logging to remove degree symbols

- **Profile Apply** (line 3894):
  - Changed: `"S={s_pos}°"` → `"S={s_pos} (0-255 scale)"`

### 4. **Auto-Polarization Function** (lines 3920-3970)
**Before:**
```python
min_angle = 10
max_angle = MAX_POLARIZER_ANGLE
# ... uses "angle" terminology throughout
```

**After:**
```python
min_position = 10
max_position = MAX_POLARIZER_POSITION
# ... uses "position" terminology throughout
```

Updated all variable names from `angle_*` to `position_*` and updated logging to clarify 0-255 scale.

## Impact

### ✅ Fixed
- Servo position validation now correctly checks 0-255 range (was incorrectly checking 0-180)
- All logging now correctly indicates "0-255 scale" instead of misleading degree symbols
- Variable names in auto-polarization now accurately reflect they are positions, not angles

### ⚠️ Backwards Compatibility
- **Calibration profiles saved before this fix may have incorrect values if they were near the 180-255 range**
- Running a fresh calibration is recommended after this fix

## Testing Recommendations

1. **Run fresh calibration** to verify Step 2B polarizer validation works correctly
2. **Check servo positions** are within 0-255 range
3. **Verify auto-polarization** (if used) scans the full 0-255 range properly

## Root Cause
The original code confused servo positions (0-255 PWM control range) with angular degrees (0-180°). This likely caused:
- Positions above 180 to be rejected as invalid (limiting usable range)
- Confusing logs showing "°" symbols for what are actually raw servo values
- Potential issues with polarizer positioning during calibration

## Resolution
All references to "angle" and "°" have been corrected to "position" with clear "(0-255 scale)" notation where appropriate.
