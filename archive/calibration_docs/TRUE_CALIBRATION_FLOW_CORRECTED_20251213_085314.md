# TRUE CALIBRATION FLOW - CORRECTED

## Summary of Changes

Based on user clarification, the calibration flow has been corrected to match the TRUE ORIGINAL design:

### ❌ PREVIOUS MISUNDERSTANDING:
- Step 4: Set ALL channels to LED=255 (natural brightness variation)
- Step 6: DELETED (thought it was unnecessary)
- Smart boost: Adjusted both integration time AND LED values

### ✅ CORRECTED UNDERSTANDING:
- Step 4: Set ONLY weakest channel to LED=255
- Step 6: RESTORED - Adjust OTHER channels down to balance all within 15%
- Smart boost: ONLY adjusts integration time (NEVER touches LED values)

---

## Calibration Sequence (CORRECTED)

### Step 1: Measure Baseline Dark Noise
- Measure dark noise before any LEDs activated
- Provides clean baseline for comparison

### Step 2: Validate Polarizer Positions
- Check S and P polarizer positions are calibrated
- Ensures accurate polarization control

### Step 3: Find Weakest LED
- Test all channels at standard LED intensity
- Rank channels from weakest to strongest
- **Weakest channel** will be reference for optimization

### Step 4: Optimize Integration Time (WEAKEST @ LED=255)
**CORRECTED:** Only the weakest channel is set to LED=255

```
Goal: Find integration time where WEAKEST @ LED=255 reaches 75% detector max
- Set weakest channel: LED=255 (LOCKED)
- Binary search integration time: 5-200ms
- Target: 75% detector max (~49,152 counts for 65,535 max)
- Range: 50-80% acceptable
- Other channels NOT set yet (Step 6 will handle them)
```

**Output:**
```
Weakest channel (A): LED=255
Integration time: 150ms (example)
Signal: 49,152 counts (75%)
Status: ✅ OPTIMAL
```

### Step 5: Re-measure Dark Noise
- Re-measure dark noise at final integration time (150ms)
- Apply afterglow correction if available
- More accurate than Step 1 (which used temporary 32ms)

### Step 6: Balance LED Intensities (RESTORED)
**CORRECTED:** Adjust OTHER channels down to match weakest

```
Goal: Balance all channels by REDUCING brighter LEDs
- Weakest already at LED=255 (from Step 4)
- For each other channel:
  - Binary search LED intensity
  - Target: 50-75% detector max
  - Constraint: All within 15% of each other
  - Method: REDUCE LED value until signal matches target
```

**Example Output:**
```
Reference (weakest): A @ LED=255
Calibrating B...
  ✅ Found optimal LED=180 → 51,000 counts (78%)
Calibrating C...
  ✅ Found optimal LED=200 → 48,000 counts (73%)
Calibrating D...
  ✅ Found optimal LED=190 → 49,500 counts (76%)

Final Balance:
  A: LED=255 → 49,152 counts (75%)
  B: LED=180 → 51,000 counts (78%)
  C: LED=200 → 48,000 counts (73%)
  D: LED=190 → 49,500 counts (76%)

Variation: 12.5% ✅ PASS (within 15% tolerance)
```

### Step 7: Measure S-ref (Balanced S-mode Baseline)
- Capture reference spectra with balanced LED settings
- All channels use their calibrated LED values
- Integration time: 150ms (from Step 4)
- **This is the baseline saved for QC validation**

### Step 8: Validation
- Verify calibration meets quality thresholds
- Check all channels have valid spectra
- Save to device_config.json (single source of truth)

---

## Smart Boost (P-pol Live Mode ONLY)

**CORRECTED:** Smart boost ONLY adjusts integration time, NEVER LED values

### When Smart Boost Applies:
- **P-polarized measurements ONLY** (live mode)
- After switching polarizer from S to P
- Goal: Maximize signal while staying within 200ms budget

### What Smart Boost Does:
```
1. Calculate boost factor:
   - Calibration target: 75% (weakest channel)
   - Live target: 76% (~50,000 counts)
   - Boost factor: 76 / 75 = 1.01× (minimal boost in this case)

2. Apply constraints:
   - Min boost: 1.0× (never reduce)
   - Max boost: 2.5× (configurable)
   - Max integration: 200ms (hard limit)

3. Boost integration time ONLY:
   - Calibrated: 150ms
   - Boosted: 150ms × 1.01 = 151.5ms (example)
   - Capped: min(151.5ms, 200ms) = 151.5ms

4. LED values UNCHANGED:
   - Use calibrated values from Step 6
   - A: LED=255 (weakest, no change)
   - B: LED=180 (balanced, no change)
   - C: LED=200 (balanced, no change)
   - D: LED=190 (balanced, no change)
```

### What Smart Boost NEVER Does:
❌ Adjust LED intensities (LED values are LOCKED from Step 6)
❌ Apply to S-mode measurements (S uses calibration settings directly)

### Dynamic Scan Averaging (200ms Budget):
```
Formula: num_scans = min(200ms / integration_time, 25)

Examples:
- 150ms integration → 1 scan (150ms total, within budget)
- 100ms integration → 2 scans (200ms total, exactly budget)
- 50ms integration → 4 scans (200ms total, exactly budget)
- 40ms integration → 5 scans (200ms total, exactly budget)
```

---

## Key Architecture Points

### 1. LED Calibration = Step 6 Balancing
```
All channels balanced to similar intensities (within 15%)
Weakest @ LED=255, others reduced to match
Integration time fixed at calibrated value
```

### 2. Smart Boost = Integration Time Only
```
P-pol live mode only
Boosts integration time (never LED values)
Stays within 200ms per channel budget
Uses calibrated LED values unchanged
```

### 3. S-mode vs P-mode
```
S-mode (calibration):
  - Uses calibrated settings directly
  - All channels balanced from Step 6
  - Integration time from Step 4
  - LED values from Step 6

P-mode (live):
  - Smart boost increases integration time
  - LED values unchanged from S-mode
  - Stays within 200ms budget
  - Maximizes signal without saturation
```

---

## Files Modified

### `utils/spr_calibrator.py`
1. **Step 4** (lines 2250-2450):
   - Updated docstring to clarify weakest @ LED=255 only
   - Changed output to set ONLY weakest channel to LED=255
   - Removed loop that set all channels

2. **Step 6** (lines 2757-2920):
   - **RESTORED** entire method `step_6_balance_led_intensities()`
   - Implements binary search LED balancing
   - Reduces other channels to match weakest
   - Target: All within 15% of each other, within 50-75% range

3. **Calibration Flow** (lines 4090-4120):
   - Re-inserted Step 6 call between Step 5 and Step 7
   - Renumbered: Step 6 = LED balancing, Step 7 = S-ref, Step 8 = Validation

### `utils/spr_state_machine.py`
1. **Smart Boost** (lines 435-445):
   - **REMOVED** per-channel LED adjustment code (~40 lines)
   - Now uses calibrated LED values directly
   - Only adjusts integration time
   - Added comment: "Smart boost ONLY adjusts integration time, NEVER LED values"

### `settings/settings.py`
No changes needed:
- `WEAKEST_TARGET_PERCENT = 75` (correct for Step 4)
- `LIVE_MODE_TARGET_INTENSITY_PERCENT = 76` (correct for P-mode boost)
- No conflict because they apply to different steps

---

## Expected Calibration Results

### Example Output:
```
Step 3: LED Ranking
  Weakest: A (15,000 counts @ LED=128)
  B: 22,000 counts
  C: 18,000 counts
  D: 20,000 counts

Step 4: Integration Time Optimization
  Weakest (A) @ LED=255
  Integration time: 150ms
  Signal: 49,152 counts (75%) ✅ OPTIMAL

Step 5: Dark Noise Re-measurement
  Dark noise: 85 counts (with afterglow correction)

Step 6: LED Balancing
  A: LED=255 → 49,152 counts (75%) [reference]
  B: LED=180 → 51,000 counts (78%)
  C: LED=200 → 48,000 counts (73%)
  D: LED=190 → 49,500 counts (76%)
  Variation: 12.5% ✅ PASS

Step 7: S-ref Measurement
  All channels @ balanced LED values
  Integration: 150ms
  Saved to device_config.json

Step 8: Validation ✅ PASS

Smart Boost (P-mode):
  Integration: 150ms → 151.5ms (1.01× boost)
  LED values: UNCHANGED (A=255, B=180, C=200, D=190)
  Scans: 1 (151.5ms < 200ms budget)
  Expected signal: 76% (~50,000 counts)
```

---

## Testing Checklist

- [ ] Step 3 identifies weakest channel correctly
- [ ] Step 4 sets ONLY weakest to LED=255 (not all channels)
- [ ] Step 4 finds integration time where weakest @ 255 reaches 75%
- [ ] Step 5 re-measures dark noise at final integration time
- [ ] Step 6 balances other channels by reducing their LEDs
- [ ] Step 6 achieves all within 15% variation
- [ ] Step 7 measures S-ref with balanced settings
- [ ] Smart boost ONLY increases integration time (P-pol only)
- [ ] Smart boost NEVER touches LED values
- [ ] Scan count = min(200ms / integration_time, 25)
- [ ] QC validation uses balanced baseline

---

## Status

✅ All corrections implemented
✅ No syntax errors
✅ Code compiles successfully
⏳ Ready for testing
