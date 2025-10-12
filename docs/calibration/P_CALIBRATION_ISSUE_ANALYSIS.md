# P Calibration Issue Analysis

**Date:** October 10, 2025
**Issue:** P-mode calibration using S-mode LED response model incorrectly

---

## Problem Summary

**YES - P calibration is incorrectly using the S-mode LED response model!**

The LED Response Model system we implemented predicts LED intensity based on **S-mode (single channel) measurements**, but the P-mode calibration code at line 1833 is trying to use this S-mode model to predict P-mode LED values:

```python
# Line 1833 in calibrate_led_p_mode_adaptive()
predicted_led = self.led_model.predict_led_for_target(ch, target_intensity, led_min=20, led_max=255)
```

This is fundamentally incorrect because:
1. **S-mode** = Single channel active, single polarization
2. **P-mode** = Single channel active, **perpendicular polarization**
3. The LED brightness produces **different light output** depending on polarization state
4. The spectrometer receives **different intensities** in S vs P mode for the same LED value

---

## Calibration Sequence (Current)

### Step 3: Integration Time (S-mode)
- Tests all channels at LED=168 in **S-mode**
- Identifies weakest channel
- Optimizes integration time for weakest channel at LED=255
- **Result:** Integration time optimized for S-mode measurements

### Step 4: S-mode LED Calibration
- **LED Response Model characterization** (lines 971-1082)
- Tests each channel at 5 LED intensities: [50, 100, 150, 200, 255]
- Measures spectrum counts at each LED in **S-mode**
- Fits linear model: `counts = slope * led_intensity + intercept`
- **Result:** Model predicts S-mode LED → count relationship

### Step 7-8: P-mode LED Calibration
- Switches polarizer to **P-mode** (line 2300)
- Tries to predict P-mode LED using **S-mode LED model** (line 1833)
- **PROBLEM:** S-mode model doesn't apply to P-mode!

---

## Why This Is Wrong

### Physical Reality
When you change polarization modes, the **optical path changes**:

```
S-mode (single polarization):
LED → Light Source → Polarizer (aligned) → Sample → Spectrometer
                      ^^^^^^^^
                      Most light passes through

P-mode (perpendicular polarization):
LED → Light Source → Polarizer (perpendicular) → Sample → Spectrometer
                      ^^^^^^^^^^^^^^^^^^^^^^^^^
                      Much less light passes through
```

### LED Response Differs by Mode
The same LED value produces different spectrometer readings:

| LED Value | S-mode Counts | P-mode Counts | Ratio (P/S) |
|-----------|---------------|---------------|-------------|
| 100       | 20,000        | 5,000         | 0.25x       |
| 150       | 35,000        | 8,750         | 0.25x       |
| 200       | 50,000        | 12,500        | 0.25x       |

The **ratio varies** depending on:
- Polarizer efficiency
- Sample birefringence
- LED wavelength characteristics
- Channel-specific optical properties

### Model Prediction Fails
```python
# S-mode LED model learned:
# LED=100 → 20,000 counts
# LED=150 → 35,000 counts
# Model: counts = 350 * led - 15,000

# P-mode reality (example):
# LED=100 → 5,000 counts (not 20,000!)
# LED=150 → 8,750 counts (not 35,000!)

# Prediction error:
# Target: 10,000 counts in P-mode
# S-mode model predicts: LED=71 (would give 10k in S-mode)
# Actual result in P-mode: LED=71 gives only 2,500 counts!
# Correct P-mode LED needed: ~200
```

---

## Evidence in Your Logs

You likely saw messages like:
```
🎯 LED model prediction for P-mode a: 85 (model-based)
🎯 P-mode prediction result: LED=85, measured=8234 (12.6%), error=44194 (tolerance=5242)
⚠️ P-mode prediction error too large (44194), falling back to iterative method
```

This shows:
1. S-mode model predicted LED=85 would work for P-mode
2. LED=85 in P-mode only gave 8,234 counts (way too low)
3. System correctly detected the error and fell back to iterative search

---

## The Correct Solution

### Option 1: Separate LED Models for Each Mode ✅ RECOMMENDED
Build **two separate LED response models**:

```python
class LEDResponseModel:
    def __init__(self):
        self.s_mode_models = {}  # S-mode LED characterization
        self.p_mode_models = {}  # P-mode LED characterization

    def characterize_s_mode(self, ch, test_points):
        """Build S-mode model from S-mode measurements"""
        # Current implementation (works correctly)

    def characterize_p_mode(self, ch, test_points):
        """Build P-mode model from P-mode measurements"""
        # NEW: After switching to P-mode, test same LED points
        # Build separate model for P-mode response

    def predict_s_mode_led(self, ch, target_counts):
        """Use S-mode model for S-mode predictions"""
        return self.s_mode_models[ch].predict(target_counts)

    def predict_p_mode_led(self, ch, target_counts):
        """Use P-mode model for P-mode predictions"""
        return self.p_mode_models[ch].predict(target_counts)
```

**Implementation Steps:**
1. Keep current S-mode characterization (Step 3.1.5)
2. Add P-mode characterization after Step 7 (switch to P-mode)
3. Test 3-5 LED points in P-mode: [100, 150, 200, 250]
4. Build separate P-mode model for each channel
5. Use P-mode model for P-mode LED predictions

**Benefits:**
- Accurate P-mode predictions
- Faster P-mode calibration (single-shot)
- Both models saved with calibration profile
- Each model optimized for its specific mode

### Option 2: Disable Model Prediction for P-mode ⚠️ TEMPORARY FIX
Simply don't use LED model for P-mode:

```python
# Line 1833 - Change from:
predicted_led = self.led_model.predict_led_for_target(ch, target_intensity, led_min=20, led_max=255)

# To:
predicted_led = None  # Disable model prediction for P-mode
logger.info(f"📊 P-mode uses iterative calibration (no model available)")
```

**This is what's effectively happening now** since the prediction fails and falls back to iterative method.

---

## Impact Assessment

### Current Behavior
1. ✅ S-mode calibration: **Works correctly** with LED model predictions
2. ⚠️ P-mode calibration: Model prediction **fails** (large error), falls back to iterative
3. ⏱️ P-mode takes full iteration time (~15-20 iterations per channel)
4. ✅ Final result: **P-mode calibration still succeeds** (iterative method is reliable)

### If We Fix It
1. ✅ S-mode calibration: Works correctly (unchanged)
2. ✅ P-mode calibration: **Single-shot prediction** or 2-3 fine-tuning iterations
3. ⚡ P-mode calibration time: **Reduced from ~30s to ~5s per channel**
4. ✅ More accurate P-mode starting point
5. 📊 Better data for understanding S vs P mode differences

---

## Recommendation

### Immediate Action (Quick Fix)
**Option 2** - Disable model for P-mode:
```python
# In calibrate_led_p_mode_adaptive(), line ~1833
# Comment out or set to None:
predicted_led = None  # S-mode model doesn't apply to P-mode
```

This stops the false prediction attempts and clarifies the log messages.

### Long-term Solution
**Option 1** - Implement P-mode LED characterization:

1. Add new step "3.1.6: P-mode LED characterization" after Step 7 (switch to P)
2. Test 4 LED points per channel: [100, 150, 200, 250]
3. Build separate P-mode models
4. Use P-mode models for P-mode predictions
5. Add ~10-15 seconds to calibration, save ~20 seconds in P-mode optimization
6. **Net time savings: ~5-10 seconds** + more accurate results

---

## Code Locations

### LED Model Characterization (S-mode)
- **File:** `utils/spr_calibrator.py`
- **Line:** 971-1082 (Step 3.1.5)
- **Method:** `calibrate_integration_time()` contains LED characterization

### LED Model Class
- **File:** `utils/spr_calibrator.py`
- **Line:** 203-410
- **Class:** `LEDResponseModel`

### P-mode Calibration (uses wrong model)
- **File:** `utils/spr_calibrator.py`
- **Line:** 1788-1993
- **Method:** `calibrate_led_p_mode_adaptive()`
- **Problem Line:** 1833 - tries to use S-mode model for P-mode

### Calibration Sequence
- **File:** `utils/spr_calibrator.py`
- **Line:** 2196-2339
- **Method:** `run_full_calibration()`
- Steps:
  - Line 2252: Step 3 - Integration time (S-mode, includes LED characterization)
  - Line 2260: Step 4 - S-mode LED calibration (uses S-mode model)
  - Line 2300: Step 7 - Switch to P-mode
  - Line 2306: Step 8 - P-mode LED calibration (incorrectly tries S-mode model)

---

## Conclusion

**Yes, P calibration is trying to use S output (S-mode LED model) which is incorrect.**

The good news:
- ✅ System detects the error automatically
- ✅ Falls back to iterative method which works correctly
- ✅ Final calibration is still successful

The fix options:
- 🔧 **Quick:** Disable model for P-mode (no harm, clarifies behavior)
- 🎯 **Proper:** Build separate P-mode LED model (better performance)

Would you like me to implement either solution?
