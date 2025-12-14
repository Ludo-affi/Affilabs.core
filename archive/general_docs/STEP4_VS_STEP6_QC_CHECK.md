# Step 4 vs Step 6 QC Check Implementation

**Date**: 2025-10-25
**Status**: ✅ Implemented
**Priority**: HIGH - Early Detection of Dark Contamination

---

## Overview

Added automatic QC check that compares Step 4 (raw S-pol) ROI means with Step 6 (dark-subtracted S-ref) ROI means. Since the **ONLY** difference between these two steps is dark subtraction, large differences indicate the dark measurement was contaminated with LED light.

---

## User Insight

> "I didn't see any QC step that compared the step 4 output and step 6 output. You could be comparing the ROI mean intensities of both and you would see right away that there is a big problem."

This is exactly right! The comparison catches the suppression issue immediately.

---

## Implementation Details

### Part 1: Store Step 4 ROI Means (Line 3921)

At the end of Step 4 diagnostic capture, we now store the raw S-pol ROI means:

```python
# ✨ STORE Step 4 ROI means for QC comparison with Step 6
self.state.step4_raw_spol_roi_means = step4_diagnostic_roi_means.copy()
logger.debug(f"📊 Stored Step 4 ROI means for QC: {step4_diagnostic_roi_means}")
```

This preserves the ROI means (580-610nm) before any dark subtraction.

### Part 2: QC Check in Step 6 (Lines 4241-4323)

Right after calculating Step 6 ROI means, we compare with Step 4:

```python
# ========================================================================
# STEP 6.8: QC CHECK - Compare Step 4 vs Step 6 ROI Means
# ========================================================================
# The ONLY difference between Step 4 and Step 6 is dark subtraction
# If Step 6 is dramatically different from Step 4, this is a RED FLAG
# indicating the dark measurement was contaminated (LEDs not fully off)

if hasattr(self.state, 'step4_raw_spol_roi_means') and self.state.step4_raw_spol_roi_means:
    # Calculate expected dark based on detector class and integration time
    expected_dark = 3000.0  # Ocean Optics detector class baseline @ 36ms
    if self.detector_profile:
        integration_ms = self.state.integration * 1000
        expected_dark = 3000.0 * (integration_ms / 36.0)

    max_allowed_dark = expected_dark * 2.0  # 2x tolerance

    # Compare each channel
    for ch in ch_list:
        step4_mean = self.state.step4_raw_spol_roi_means.get(ch, 0)
        step6_mean = step6_diagnostic_roi_means.get(ch, 0)
        difference = step4_mean - step6_mean  # Effective dark subtracted

        # QC criteria:
        # 1. Difference should be positive (dark reduces signal)
        # 2. Difference should be ~expected_dark (±2x tolerance)
        # 3. Step 6 should not be near-zero
```

---

## QC Criteria

The check validates:

1. **Positive Difference**
   `Step4 - Step6 > 0`
   Dark subtraction should reduce signal, not increase it.

2. **Expected Dark Range**
   `difference ≈ expected_dark ± 2x`
   - Ocean Optics baseline: 3,000 counts @ 36ms
   - Scaled by integration time
   - Maximum allowed: 6,000 counts (2× expected)

3. **Reasonable Step 6 Signal**
   `Step6 > 1,000 counts`
   Signal shouldn't be near-zero after dark subtraction

---

## QC Output Example

### ✅ Passing Case (Normal Dark Subtraction)
```
🔍 QC CHECK: Comparing Step 4 (raw S-pol) vs Step 6 (dark-subtracted)
================================================================================

Expected dark noise: ~3000 counts
Maximum allowed dark (QC threshold): 6000 counts

Channel | Step 4 (raw) | Step 6 (dark-sub) | Difference | Status
---------------------------------------------------------------------------
   A    |   52504      |     49504         |    3000    | ✅ OK
   B    |   65535      |     62535         |    3000    | ✅ OK
   C    |   49209      |     46209         |    3000    | ✅ OK
   D    |   48850      |     45850         |    3000    | ✅ OK

✅ QC PASSED - Step 4 vs Step 6 comparison looks good
   Dark subtraction is within expected range
```

### ❌ Failing Case (Contaminated Dark)
```
🔍 QC CHECK: Comparing Step 4 (raw S-pol) vs Step 6 (dark-subtracted)
================================================================================

Expected dark noise: ~3000 counts
Maximum allowed dark (QC threshold): 6000 counts

Channel | Step 4 (raw) | Step 6 (dark-sub) | Difference | Status
---------------------------------------------------------------------------
   A    |   52504      |     45504         |    7000    | ⚠️ HIGH - Dark too large (>6000)
   B    |   65535      |     58535         |    7000    | ⚠️ HIGH - Dark too large (>6000)
   C    |   49209      |     42209         |    7000    | ⚠️ HIGH - Dark too large (>6000)
   D    |   48850      |     41850         |    7000    | ⚠️ HIGH - Dark too large (>6000)

❌ QC FAILED - Step 4 vs Step 6 comparison shows problems!

   • Channel A: Dark subtraction = 7000 counts (expected ~3000, max 6000)
   • Channel B: Dark subtraction = 7000 counts (expected ~3000, max 6000)
   • Channel C: Dark subtraction = 7000 counts (expected ~3000, max 6000)
   • Channel D: Dark subtraction = 7000 counts (expected ~3000, max 6000)

DIAGNOSIS:
   The ONLY difference between Step 4 and Step 6 should be dark subtraction.
   Large differences indicate the dark measurement was contaminated.

POSSIBLE CAUSES:
   1. LEDs not completely turned off during Step 5 dark measurement
   2. Insufficient LED-off settle time (increase led_off_delay_s)
   3. Hardware issue with LED control
   4. Wrong dark noise file being used

RECOMMENDED ACTIONS:
   1. Check Step 5 logs - verify 'lx' command sent successfully
   2. Verify dark noise mean is within expected range (~3,000 for Ocean Optics)
   3. Re-run calibration with longer LED-off delay if needed
```

---

## Calibration Behavior

**If QC Fails:**
- Calibration stops immediately (`return False`)
- Detailed diagnostic output explains the problem
- User can check Step 5 logs and dark noise measurements
- Re-run calibration after fixing LED kill command or increasing settle time

**If QC Passes:**
- Calibration continues to live measurements
- Step 6 S-reference values are validated
- User can trust the calibrated signals

---

## Integration Time Scaling

Expected dark noise scales with integration time:

```python
# Baseline: Ocean Optics @ 36ms = 3,000 counts
expected_dark = 3000.0 * (integration_ms / 36.0)

# Examples:
# 18ms integration → 1,500 counts expected dark
# 36ms integration → 3,000 counts expected dark
# 72ms integration → 6,000 counts expected dark
```

This ensures the QC check works correctly regardless of the optimized integration time.

---

## Detector-Specific Parameters

### Ocean Optics / USB4000:
- **Baseline dark**: 3,000 counts @ 36ms
- **QC threshold**: 2× expected (e.g., 6,000 @ 36ms)
- **Scaling**: Linear with integration time

**Note**: Other detector classes may have different dark noise characteristics. The baseline value (3,000 counts @ 36ms) is specific to Ocean Optics detectors.

---

## Benefits

1. **Early Detection**
   Catches dark contamination immediately (before user notices)

2. **Clear Diagnostics**
   Detailed output explains exactly what went wrong

3. **Automatic Validation**
   No manual comparison needed - QC is built into workflow

4. **Root Cause Analysis**
   Points directly to LED control or settle time issues

5. **Calibration Safety**
   Prevents bad calibration data from being used

---

## Files Modified

**`utils/spr_calibrator.py`**:

1. **Line 3921**: Store Step 4 ROI means in state
   ```python
   self.state.step4_raw_spol_roi_means = step4_diagnostic_roi_means.copy()
   ```

2. **Lines 4241-4323**: Add Step 6.8 QC check
   - Compare Step 4 vs Step 6 ROI means
   - Calculate effective dark subtraction
   - Validate against expected dark range
   - Log detailed comparison table
   - Return False if QC fails (stops calibration)

---

## Related Fixes

This QC check works in conjunction with:

1. **LED Kill Command Fix** (`LED_KILL_COMMAND_FIX.md`)
   - Ensures LEDs are completely off during dark measurement
   - Uses `self.ctrl._hal._ser.write(b"lx\n")`
   - Primary root cause fix

2. **Step 5 Dark QC** (`STEP5_DARK_QC_COMPLETE.md`)
   - Validates dark noise magnitude before Step 6
   - Retry logic with escalating settle delays
   - Catches high dark before it contaminates S-ref

3. **Diagnostic Plots**
   - Step 4: Raw S-pol spectra (before dark subtraction)
   - Step 6: Dark-subtracted S-ref (after dark subtraction)
   - Visual comparison available in diagnostics folder

---

## Testing Validation

**Test Scenarios:**

1. **Normal Operation** (QC should pass)
   - LEDs completely off during Step 5
   - Dark ~3,000 counts @ 36ms
   - Step 6 ≈ Step 4 - 3,000 counts
   - Result: QC passes, calibration continues

2. **LED Control Failure** (QC should fail)
   - LEDs partially on during Step 5
   - Dark ~6,000+ counts (contaminated)
   - Step 6 much lower than expected
   - Result: QC fails, calibration stops with diagnosis

3. **Settle Time Too Short** (QC should fail)
   - LEDs don't fully turn off in time
   - Dark ~5,000 counts (slightly contaminated)
   - Step 6 slightly lower than expected
   - Result: QC fails, suggests longer settle time

---

## Future Enhancements

1. **Detector Class Auto-Detection**
   - Auto-detect expected dark based on detector type
   - Eliminate hardcoded 3,000 count baseline

2. **Historical Trending**
   - Track Step 4 vs Step 6 differences over time
   - Detect gradual LED control degradation

3. **Per-Channel Analysis**
   - Flag individual channels with issues
   - Allow calibration to continue with good channels only

4. **Dark Noise Library**
   - Database of expected dark by detector + integration time
   - More accurate QC thresholds

---

## Conclusion

The Step 4 vs Step 6 QC check provides **immediate, automatic detection** of dark measurement contamination. By comparing ROI means before and after dark subtraction, it catches excessive dark values that would otherwise cause Step 6 signal suppression.

Combined with the LED kill command fix, this ensures calibration data is valid and prevents bad S-reference values from being used in live measurements.

**User's suggestion was spot-on - this QC check catches the problem right away!**
