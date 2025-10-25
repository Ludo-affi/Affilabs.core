# Step 4 LED Balancing Validation System

## Problem Identified

**Original Issue:** Step 6 logging showed all LED values as 0 because it was reading from the wrong state variable.

**Root Cause Analysis:**
- **Step 4** stores balanced LED intensities in `self.state.ref_intensity`
- **Step 6** logging was reading from `self.state.leds_calibrated` (which is NEVER populated during calibration)
- Result: Step 6 showed zeros or stale values instead of actual balanced LEDs from Step 4

## Data Flow Through Calibration Steps

```
Step 3: Identify weakest channel
  └─> Stores ranking in: self.state.led_ranking
  └─> Returns weakest_ch

Step 4: Balance LEDs + optimize integration time
  ├─> Sets weakest LED to 255: self.state.ref_intensity[weakest_ch] = 255
  ├─> Measures other channels at LED=255
  ├─> Calculates reduction needed to match weakest
  └─> Stores balanced values: self.state.ref_intensity[ch] = calculated_value
      ✅ SOURCE OF TRUTH for LED intensities

Step 5: Re-measure dark noise
  └─> Uses: self.state.integration (from Step 4)
  └─> SHOULD verify: self.state.ref_intensity is populated

Step 6: Measure S-reference with balanced LEDs
  ├─> Reads LED values: self.state.ref_intensity.get(ch)
  └─> Logs final calibration table
      ❌ WAS reading from: self.state.leds_calibrated (wrong!)
      ✅ NOW reads from: self.state.ref_intensity (correct!)
```

## Validation System Implemented

### 1. **Step 4 End Validation** (Line ~3310)

**When:** Immediately after Step 4 completes LED balancing

**Checks:**
1. ✅ All channels have valid LED values (> 0)
2. ✅ Weakest channel is set to LED=255
3. ✅ LED values are differentiated (not all identical)
4. ❌ If all LEDs are identical → CRITICAL ERROR (Step 4 balancing didn't work)

**Example Output:**
```
================================================================================
🔍 STEP 4 VALIDATION: Checking LED values were stored correctly
================================================================================
✅ Channel A: LED = 187 (stored in self.state.ref_intensity)
✅ Channel B: LED = 255 (stored in self.state.ref_intensity)
✅ Channel C: LED = 201 (stored in self.state.ref_intensity)
✅ Channel D: LED = 178 (stored in self.state.ref_intensity)
✅ Weakest channel B correctly set to LED=255
✅ LED values are properly differentiated: [255, 201, 187, 178]

✅ Step 4 LED values validated - ready for Step 5
================================================================================
```

**If Step 4 Failed:**
```
================================================================================
❌ CRITICAL ERROR: All channels have IDENTICAL LED values!
   All LEDs = 255
   Step 4 LED BALANCING DID NOT WORK!
   Expected: Different LED values (weakest=255, others<255)

❌ STEP 4 LED BALANCING FAILED!
================================================================================
[Calibration stops here - returns False]
```

### 2. **Step 5 Pre-Start Validation** (Line ~4248)

**When:** Before Step 5 begins dark noise measurement

**Checks:**
1. ✅ `self.state.ref_intensity` exists and is not empty
2. ✅ All channels (A, B, C, D) have LED values present
3. ✅ No LED values are zero or negative
4. ❌ If any missing/zero → CRITICAL ERROR (Step 4 didn't store values)

**Example Output:**
```
================================================================================
STEP 5: Dark Noise Re-measurement (Final Integration Time)
================================================================================

🔍 Pre-Step 5 Validation: Checking Step 4 LED values...
--------------------------------------------------------------------------------
✅ Step 4 LED values validated:
   A: LED = 187
   B: LED = 255
   C: LED = 201
   D: LED = 178

✅ Pre-Step 5 validation passed - LED values are valid
================================================================================
```

**If Step 4 Didn't Store Values:**
```
🔍 Pre-Step 5 Validation: Checking Step 4 LED values...
--------------------------------------------------------------------------------
❌ CRITICAL: self.state.ref_intensity is empty!
   Step 4 did not store LED values properly
   Cannot proceed to Step 5
[Returns False - calibration stops]
```

### 3. **Step 6 Logging Fix** (Line ~3869)

**Fixed:** Changed from reading `leds_calibrated` to `ref_intensity`

**Before (WRONG):**
```python
led_val = self.state.leds_calibrated.get(ch, 0) if self.state.leds_calibrated else 0
```

**After (CORRECT):**
```python
led_val = self.state.ref_intensity.get(ch, 0) if self.state.ref_intensity else 0
```

**Example Output:**
```
================================================================================
📊 STEP 6 COMPLETE - FINAL CALIBRATION PARAMETERS
================================================================================
Mode: GLOBAL (single integration time for all channels)
Integration Time: 18.3 ms
Scans per channel: 4

   Channel  | LED Intensity
   --------------------------
      A     |      187
      B     |      255
      C     |      201
      D     |      178

================================================================================
```

## Why This Matters

### Without Validation:
- Step 4 could fail silently
- Step 6 would show zeros or stale values
- No way to know if LED balancing actually worked
- Hardware might be broken but calibration proceeds

### With Validation:
- ✅ Immediate detection if Step 4 fails
- ✅ Clear error messages showing what went wrong
- ✅ Calibration stops before wasting time on Steps 5-6
- ✅ Step 6 logs show actual balanced LED values
- ✅ Can diagnose hardware vs software issues

## State Variable Reference

| Variable | Purpose | Set By | Used By |
|----------|---------|--------|---------|
| `self.state.led_ranking` | Channel ranking (weakest first) | Step 3 | Step 4 |
| `self.state.ref_intensity` | **Balanced LED values** | **Step 4** | **Steps 5, 6, Save** |
| `self.state.leds_calibrated` | Legacy (not used in cal) | Load/Save | Save only |
| `self.state.integration` | Global integration time | Step 4 | Steps 5, 6 |
| `self.state.ref_sig` | S-reference spectra | Step 6 | Save |

## Expected Behavior in GLOBAL Mode

**Step 4 Should Produce:**
- Weakest LED: **255** (locked at max)
- Other LEDs: **< 255** (reduced to match weakest)
- All channels balanced to ~50,000 counts in 580-610nm

**Example Valid Result:**
```
Channel B (weakest): LED = 255
Channel C:           LED = 201  (79% of max)
Channel A:           LED = 187  (73% of max)
Channel D:           LED = 178  (70% of max)
```

**Invalid Result (Red Flag):**
```
All channels: LED = 255  ← WRONG! Step 4 didn't balance!
```

## Debugging with New Validation

If calibration shows "only channel B LED gets set, others dark":

1. **Check Step 4 validation output:**
   - Do all channels show LED values after Step 4?
   - Is weakest at 255 and others reduced?
   - Or do all show 255 (balancing failed)?

2. **Check Step 5 pre-validation:**
   - Does it pass or fail?
   - Are LED values still present?

3. **Check Step 6 final output:**
   - Now shows actual `ref_intensity` values
   - Should match Step 4 validation output

4. **If Step 4 validation fails:**
   - Issue is in Step 4 LED balancing logic
   - Check `_measure_channel_in_roi()` function
   - Check LED activation in `_activate_channel_batch()`

5. **If Step 4 passes but Step 6 shows zeros:**
   - Issue is data persistence (values being cleared)
   - Check for accidental `ref_intensity` reset between steps
