# TRUE ORIGINAL CALIBRATION SEQUENCE RESTORED ✅

## Problem Identified

The current GitHub version had **ALREADY DIVERGED** from the true original calibration flow. It was using a **dual-constraint optimization** in Step 4 that tried to:
1. Maximize weakest LED signal
2. Constrain strongest LED to prevent saturation during calibration

This caused the **hardware saturation issue** where channels C/D at 91-93% forced integration time to 19ms because the algorithm was testing ALL channels during Step 4's binary search.

## TRUE ORIGINAL SEQUENTIAL CALIBRATION

### Step 3: Find Weakest LED
- Test all channels at standard LED intensity (66%)
- Rank by brightness (weakest → strongest)
- Identify weakest channel
- **Result**: Weakest channel identified (will be FIXED at LED=255)

### Step 4: Optimize Integration Time (SINGLE CONSTRAINT)
- **ONLY** optimize for weakest LED @ 255
- Find integration time where weakest reaches 50-75% detector max (~50,000 counts)
- **NO testing of strongest LED**
- **NO prediction of other LED intensities**
- **Result**: Integration time LOCKED (e.g., 150ms instead of 19ms)

### Step 5: Re-measure Dark Noise
- Use final integration time from Step 4
- Measure dark noise with LEDs OFF
- **Result**: Accurate dark noise for final integration time

### Step 6: LED Intensity Calibration (BINARY SEARCH)
- Integration time is FIXED from Step 4
- For each channel (except weakest):
  - Binary search LED intensity (13-255 range)
  - Target: Match weakest channel signal
  - **This is where saturation is handled!**
- Bright channels (C/D) get LED intensity REDUCED to prevent saturation
- **Result**: All channels balanced, bright channels dimmed

### Step 7: Reference Signal Measurement (S-mode)
- Measure reference spectra with calibrated settings
- Store S-pol reference for QC validation
- **Result**: Baseline spectra for all channels

### Step 8: Validation
- Verify all channels within acceptable range
- Check polarizer positions
- **Result**: Calibration complete

## Why This Fixes Hardware Saturation

### Old (GitHub) Method - BROKEN:
```
Step 4: Dual Optimization
├── Test weakest @ LED=255 → 45,000 counts ✓
├── Test strongest @ LED=25 → Check if <95%
├── Test channel C @ predicted LED → 91% SATURATION! ❌
└── Result: Force integration to 19ms to prevent saturation
```

### TRUE ORIGINAL - WORKING:
```
Step 4: Single Constraint (Weakest Only)
├── Test weakest @ LED=255 → 45,000 counts ✓
└── Result: Integration = 150ms (optimal for weakest)

Step 6: LED Reduction (Saturation Handled Here)
├── Channel A: LED=255 (weakest, fixed)
├── Channel B: LED=180 (binary search to match A)
├── Channel C: LED=65 (REDUCED from 255 to prevent saturation)
├── Channel D: LED=48 (REDUCED from 255 to prevent saturation)
└── Result: All channels balanced, no saturation
```

## Code Changes

### 1. `settings/settings.py`
**Removed dual-constraint parameters:**
- ❌ `STRONGEST_MAX_PERCENT` (95% saturation check)
- ❌ `STRONGEST_MIN_LED` (25 minimum LED)

**Simplified to single constraint:**
- ✅ `WEAKEST_TARGET_PERCENT = 75%` (target ~50,000 counts)
- ✅ `WEAKEST_MIN_PERCENT = 50%` (minimum ~32,768 counts)
- ✅ `WEAKEST_MAX_PERCENT = 80%` (maximum ~52,428 counts)

### 2. `utils/spr_calibrator.py` - Step 4
**Before (Dual Optimization):**
```python
def step_4_optimize_integration_time():
    # Test weakest @ 255
    # Test strongest @ 25
    # Test all channels at predicted LEDs
    # Check saturation constraints
    # Store predicted LED intensities
```

**After (Single Constraint):**
```python
def step_4_optimize_integration_time():
    # ONLY test weakest @ 255
    # Find integration where weakest reaches 50-75%
    # NO testing of other channels
    # Store ONLY weakest LED = 255
    # Step 6 handles other channels
```

### 3. `utils/spr_calibrator.py` - Step 6
**Before (Simplified - No Binary Search):**
```python
def step_6_apply_led_calibration():
    # Apply LED values from Step 4
    # No binary search
    # Just use predicted values
```

**After (Binary Search LED Calibration):**
```python
def step_6_apply_led_calibration():
    # Measure weakest channel signal (target)
    # For each other channel:
    #   - Binary search LED intensity (13-255)
    #   - Find LED where signal matches target
    #   - REDUCE bright channels to prevent saturation
    # Store calibrated LED intensities
```

## Expected Behavior After Fix

### Calibration Logs (Step 4):
```
⚡ STEP 4: INTEGRATION TIME OPTIMIZATION (TRUE ORIGINAL)
   Weakest LED: b (will be FIXED at LED=255)

   GOAL: Find integration time where weakest LED @ 255 reaches target
      → Target: 75% (49,151 counts)
      → Range: 50-80% (32,768-52,428 counts)

   Integration time limit: ≤ 200ms

   Note: Other channels will be calibrated in Step 6 (LED reduction)

🔍 Binary search: 50.0ms - 200.0ms

   Iteration 1: 125.0ms
      Weakest (b @ LED=255): 38,456 counts ( 58.7%)
      ⚠️  Too low → Increase integration

   Iteration 2: 162.5ms
      Weakest (b @ LED=255): 51,234 counts ( 78.2%)
      ✅ TARGET REACHED!

✅ INTEGRATION TIME OPTIMIZED (S-MODE)
   Optimal integration time: 162.5ms

   Weakest LED (b @ LED=255):
      Signal: 51,234 counts ( 78.2%)
      Status: ✅ OPTIMAL

   Integration time LOCKED for S-mode: 162.5ms
```

### Calibration Logs (Step 6):
```
STEP 6: LED Intensity Calibration (TRUE ORIGINAL)
   Weakest channel: B @ LED=255 (FIXED)
   Integration time: 162.5ms (LOCKED from Step 4)

   Measuring weakest channel (b) to establish target...
   Target signal: 51,234 counts (78.2%)

   Channel A: LED=255 (weakest, already calibrated)

   Calibrating channel B...
      Iter 1: LED=128 → 45,678 counts (69.7%)
      Iter 2: LED=192 → 52,345 counts (79.9%)
      Iter 3: LED=176 → 50,123 counts (76.5%)
      ✅ LED=180 → 51,456 counts (78.5%) - TARGET REACHED
      Final: LED=180 → 51,456 counts (78.5%)

   Calibrating channel C...
      Iter 1: LED=128 → 58,934 counts (89.9%) [TOO HIGH]
      Iter 2: LED=64 → 46,123 counts (70.4%)
      Iter 3: LED=96 → 54,678 counts (83.4%)
      Iter 4: LED=80 → 48,234 counts (73.6%)
      Iter 5: LED=72 → 50,456 counts (77.0%)
      ✅ LED=68 → 51,123 counts (78.0%) - TARGET REACHED
      Final: LED=68 → 51,123 counts (78.0%)

   Calibrating channel D...
      Iter 1: LED=128 → 60,234 counts (91.9%) [TOO HIGH]
      Iter 2: LED=64 → 47,890 counts (73.1%)
      Iter 3: LED=48 → 42,345 counts (64.6%)
      Iter 4: LED=56 → 50,678 counts (77.3%)
      ✅ LED=52 → 51,234 counts (78.2%) - TARGET REACHED
      Final: LED=52 → 51,234 counts (78.2%)

✅ LED CALIBRATION COMPLETE
   Final LED intensities:
      A: LED=255
      B: LED=180
      C: LED=68  ← REDUCED from 255 to prevent saturation
      D: LED=52  ← REDUCED from 255 to prevent saturation

   All channels balanced to match weakest channel signal
   Integration time: 162.5ms (LOCKED from Step 4)
```

## Key Differences

| Aspect | Old (Broken) | TRUE ORIGINAL (Fixed) |
|--------|--------------|----------------------|
| **Step 4 Goal** | Dual optimization | Single constraint (weakest only) |
| **Channels Tested in Step 4** | ALL 4 channels | ONLY weakest |
| **Integration Time** | 19ms (forced by saturation) | 150-200ms (optimal) |
| **Saturation Handling** | During Step 4 (prevents optimization) | During Step 6 (LED reduction) |
| **Step 6 Purpose** | Apply pre-calculated LEDs | Binary search LED intensities |
| **Bright Channel LEDs** | Predicted from ratio | Actively REDUCED via binary search |

## Testing Instructions

1. **Clear old calibration:**
   ```powershell
   Remove-Item generated-files\device_config.json
   ```

2. **Run calibration:**
   ```powershell
   .\run_app.bat
   ```

3. **Expected results:**
   - Step 4 should find integration time 100-200ms (NOT 19ms!)
   - Step 6 should show LED reduction for channels C/D
   - Final LED intensities: A=255, B~180, C~65, D~48
   - Live signals should be ~50,000 counts (76% detector max)
   - Smart boost should activate normally

4. **Verify in logs:**
   - ✅ "STEP 4: INTEGRATION TIME OPTIMIZATION (TRUE ORIGINAL)"
   - ✅ "STEP 6: LED Intensity Calibration (TRUE ORIGINAL)"
   - ✅ Integration time 100-200ms
   - ✅ Channels C/D LED reduced to <100

## Summary

The TRUE ORIGINAL calibration sequence has been restored. The key insight is:

**SEQUENTIAL optimization, not SIMULTANEOUS:**
1. **Step 4**: Find integration time for weakest LED ONLY
2. **Step 6**: Reduce bright LEDs to match weakest signal

This allows the weakest channel to get optimal integration time (150-200ms) without being constrained by bright channels' saturation. The bright channels are then dimmed in Step 6 to prevent saturation while maintaining the optimal integration time.

This is the **correct architectural pattern** that was lost in the GitHub version's "optimization" attempts.
