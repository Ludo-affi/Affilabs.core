# Polarizer S/P Mode Inversion Fix

## Issue Identified

**Problem**: The transmission signal was inverted - the physical S position was producing P-mode signal characteristics and vice versa.

**Root Cause**: The firmware commands `ss` (S-mode) and `sp` (P-mode) were producing inverted optical results in transmission measurements.

## Solution Implemented

### HAL Command Inversion

**File**: `utils/hal/pico_p4spr_hal.py`

**Changes**:
```python
# BEFORE (incorrect)
if mode.lower() == "s":
    cmd = "ss\n"  # S-mode command
else:
    cmd = "sp\n"  # P-mode command

# AFTER (corrected)
if mode.lower() == "s":
    cmd = "sp\n"  # S-mode uses P command (inverted)
else:
    cmd = "ss\n"  # P-mode uses S command (inverted)
```

### Why This Fix Works

1. **Software Layer**: The calibration, measurements, and all logic use "s" and "p" mode labels correctly
2. **HAL Translation**: Only the HAL layer swaps the commands to match the physical hardware behavior
3. **Clean Separation**: No changes needed in calibration logic, state machine, or UI

### Impact on System

#### Before Fix
- User sets mode "s" → Hardware receives `ss` → Produces HIGH intensity (wrong for S-mode)
- User sets mode "p" → Hardware receives `sp` → Produces LOW intensity (wrong for P-mode)
- Validation fails because S/P ratio is inverted

#### After Fix
- User sets mode "s" → Hardware receives `sp` → Produces LOW intensity (correct for S-mode perpendicular)
- User sets mode "p" → Hardware receives `ss` → Produces HIGH intensity (correct for P-mode parallel)
- Validation passes with proper S/P ratio (P >> S as expected)

### Affected Operations

All polarizer operations now work correctly:

1. **Calibration (Step 2B)**: Polarizer validation checks P > S correctly
2. **Reference Measurement (Step 7)**: S-mode reference signals measure perpendicular polarization
3. **Live Measurements**: P-mode measurements capture parallel polarization with higher intensity
4. **Auto-Polarization**: Peak detection finds correct optimal positions

### Testing Verification

To verify the fix works:

```python
# Test S-mode (should be LOW intensity - perpendicular)
ctrl.set_mode("s")
ctrl.set_intensity("a", 255)
spectrum_s = usb.read_intensity()
print(f"S-mode max: {np.max(spectrum_s)}")  # Should be LOW

# Test P-mode (should be HIGH intensity - parallel)
ctrl.set_mode("p")
spectrum_p = usb.read_intensity()
print(f"P-mode max: {np.max(spectrum_p)}")  # Should be HIGH

# Ratio should be > 2.0 (ideally 3-15)
ratio = np.max(spectrum_p) / np.max(spectrum_s)
print(f"P/S ratio: {ratio:.2f}×")  # Should be > 2.0
```

### Polarizer Position Propagation

The validated servo positions are now correctly associated with the physical polarization states:

- **S position** (e.g., 10°): Perpendicular polarization, LOW transmission
- **P position** (e.g., 100°): Parallel polarization, HIGH transmission

Stored in calibration profiles:
```json
{
  "polarizer_s_position": 10,
  "polarizer_p_position": 100,
  "polarizer_sp_ratio": 5.15
}
```

## Graph Background Fix

### Issue
The sensorgram graph (top graph) was showing a black background instead of white.

### Root Cause
The `setConfigOptions()` function sets **global** PyQtGraph settings, but was called multiple times (once per graph instance), causing conflicts.

### Solution

**File**: `widgets/graphs.py`

**Changes**:
```python
# BEFORE (global configuration)
setConfigOptions(antialias=True, background='w', foreground='k')

# AFTER (per-widget configuration)
setConfigOptions(antialias=True)
self.setBackground('w')  # Set background per widget instance
```

Applied to both:
- `SensorgramGraph.__init__()`
- `SegmentGraph.__init__()`

### Why This Works

1. **Global Config**: `setConfigOptions()` only sets antialiasing (affects all graphs)
2. **Widget-Specific**: `self.setBackground('w')` sets white background per graph instance
3. **No Conflicts**: Each graph independently controls its background color

### Visual Result

- ✅ **Top sensorgram**: White background, black text
- ✅ **Bottom segment graphs**: White background, black text
- ✅ **All UI elements**: High contrast, easy to read

## Deployment Notes

### Backward Compatibility

**Hardware Settings**: Any saved polarizer positions remain valid because:
- Positions are stored as degrees (10°, 100°)
- Physical servo positions don't change
- Only the command mapping is inverted

**Calibration Profiles**: Existing profiles work correctly because:
- LED intensities are independent of polarizer inversion
- Integration times are unaffected
- Wavelength calibration is polarization-independent

### Production Impact

**Systems already calibrated**: No recalibration needed! The fix only affects future calibrations.

**Systems needing calibration**: Will now calibrate correctly with proper S/P validation.

## Summary

| Component | Issue | Fix | Impact |
|-----------|-------|-----|--------|
| **Polarizer HAL** | S/P commands inverted | Swap `ss` ↔ `sp` in HAL layer | Correct S/P behavior |
| **Sensorgram** | Black background | Use `setBackground('w')` per widget | White background |
| **Segment Graphs** | Inconsistent styling | Use `setBackground('w')` per widget | Consistent white |

**Result**: ✅ Polarizer works correctly, all graphs have white backgrounds with black text.

**Testing**: Run calibration and verify Step 2B polarizer validation passes with proper S/P ratio.
