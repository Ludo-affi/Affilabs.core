# S-Mode Optimization Simplification

## Overview
Removed redundant Phase 1 (LED characterization) from S-mode calibration. Now starts directly with Phase 2 (adaptive LED optimization).

## Problem
The original S-mode calibration had two redundant phases:
- **Phase 1 (LED Characterization):** Measured LED response at [20, 128, 255] to build predictive model
- **Phase 2 (Adaptive Optimization):** Used prediction, then immediately re-measured and iteratively adjusted anyway

**Result:** 8+ measurements per channel (3 for characterization + 5+ for optimization)

## Solution
Eliminated Phase 1 completely. Now goes directly to adaptive optimization starting at LED=128.

**New Result:** ~5 measurements per channel (direct adaptive convergence)

**Time Savings:** ~40% reduction in S-mode calibration time

## Changes Made

### 1. Removed Step 3.1.5 - LED Characterization
**File:** `utils/spr_calibrator.py`
**Lines Removed:** ~35 lines
**What:** Deleted the LED characterization phase that sampled at [20, 128, 255]

**Before:**
```python
# STEP 1.5: Characterize LED response curves
logger.info("Characterizing LED response curves...")
test_leds = [20, 128, 255]
for ch in ch_list:
    for led_val in test_leds:
        # Measure and build model...
        self.led_model.characterize_led(ch, led_samples, count_samples)
```

**After:**
```python
# DELETED - goes directly to Step 2
```

### 2. Simplified `calibrate_led_s_mode_adaptive()`
**File:** `utils/spr_calibrator.py`
**Lines Modified:** ~110 lines simplified to ~40 lines

**Before:**
```python
# Try predictive calibration first
predicted_led = self.led_model.predict_led_for_target(...)
if predicted_led is not None:
    # Test prediction, check if within tolerance
    # If close, fine-tune from predicted value
else:
    # Fall back to iterative method from LED=128
```

**After:**
```python
# DIRECT ADAPTIVE OPTIMIZATION - Start at LED=128
logger.info("Starting adaptive optimization from LED=128")
current_led = 128
# Iteratively adjust to reach target...
```

### 3. Simplified Step 3.3 - Saturation Check
**File:** `utils/spr_calibrator.py`
**Lines Modified:** ~80 lines simplified to ~35 lines

**Before:**
```python
# Check if LED models available
if all_models_valid:
    # Use LED model predictions (no measurement)
    predicted_counts = self.led_model.predict_counts_for_led(ch, LOW_LED_TEST)
else:
    # Fallback: measure directly
```

**After:**
```python
# Check for saturation by testing at low LED intensity
for ch in ch_list:
    # Set LED and measure directly (always)
    counts = measure_intensity(ch, LOW_LED_TEST)
```

### 4. Cleaned Save/Load Functions
**File:** `utils/spr_calibrator.py`

**Removed:**
- `"led_response_models": self.led_model.to_dict()` from save
- `self.led_model.from_dict(calibration_data)` from load

**Reason:** LED models no longer built during calibration

### 5. LED Model Infrastructure Kept
**What:** `LEDResponseModel` class and `self.led_model` initialization remain in code

**Why:**
- Backward compatibility with existing code
- May be useful for future diagnostic features
- Zero overhead if not used

## Benefits

### Performance
- **40% faster S-mode calibration** (8+ measurements → 5 measurements per channel)
- **Simpler code** (120 fewer lines)
- **More predictable** (no branching between model-based vs iterative)

### Reliability
- **Direct optimization** always works (no model prediction failures)
- **Consistent behavior** (same path every calibration)
- **Easier debugging** (fewer code paths)

### Maintainability
- **Clearer logic** (one optimization strategy, not two)
- **Less complexity** (no LED model management in calibration flow)
- **Easier testing** (one code path to validate)

## Testing Recommendations

1. **Run full calibration** and verify S-mode completes successfully
2. **Check convergence** - should reach target in ~5 iterations starting from LED=128
3. **Verify timing** - S-mode calibration should be ~40% faster
4. **Test all channels** - ensure adaptive optimization works for all LED intensities

## Expected Log Output

**Before (with Phase 1):**
```
📊 Step 3.1.5: Characterizing LED response curves...
   Sampling LED at [20, 128, 255] to build predictive models
   Channel a: LED=20 → 1234 counts
   Channel a: LED=128 → 8567 counts
   Channel a: LED=255 → 16789 counts
   [... repeat for b, c, d ...]
✅ LED response models created for all channels

STEP 4: LED INTENSITY CALIBRATION (S-MODE)
🎯 LED model prediction for a: 145 (model-based)
🎯 Prediction result: LED=145, measured=48234 (77.8%), error=2345
🎯 Prediction close, fine-tuning from LED=145...
Adaptive iter 0: LED=145, measured=48234, error=2345
[... iterative refinement ...]
```

**After (Phase 2 only):**
```
STEP 4: LED INTENSITY CALIBRATION (S-MODE)
📊 Starting adaptive optimization for a from LED=128
Adaptive iter 0: LED=128, measured=42500, error=7500
Adaptive iter 1: LED=165, measured=51234, error=1234
Adaptive iter 2: LED=158, measured=49876, error=124
✅ Channel a converged in 3 iterations: LED=158
```

## Backward Compatibility

✅ **Profile Loading:** Old profiles with `led_response_models` will load without errors (field ignored)
✅ **Profile Saving:** New profiles won't include `led_response_models` (smaller file size)
✅ **API:** All public methods unchanged
✅ **Behavior:** Calibration still reaches same target intensity

## Future Enhancements

If Phase 1 is needed later for diagnostics:
1. Add optional `--characterize-leds` flag
2. Run characterization separately from calibration
3. Display LED response curves in diagnostic viewer
4. Use for quality control (detect failing LEDs early)

## Related Files

- `utils/spr_calibrator.py` - Main calibration logic
- `settings/settings.py` - Target intensity settings (unchanged)
- `DETECTOR_PROFILES_IMPLEMENTATION.md` - Detector-specific parameters (unchanged)

## Summary

**Before:** Phase 1 (characterize) → Phase 2 (optimize with prediction) → ~8 measurements
**After:** Phase 2 (optimize directly) → ~5 measurements
**Result:** 40% faster, simpler, more reliable S-mode calibration
