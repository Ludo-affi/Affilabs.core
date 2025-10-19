# Integration Time Reduction for Saturating Channels

## Current Status

**✅ Calibration code is working correctly!**
**❌ Hardware limitation: Integration time too long for bright channels**

### Latest Calibration Results (auto_save_20251017_201946)

```
Weakest channel: b
Integration time: 200.0ms
LED values: {'a': 133, 'b': 255, 'c': 133, 'd': 12}

S-mode signals:
  Channel A: LED=133 →  42,393 counts ( 64.7%)  ✅
  Channel B: LED=255 →  26,987 counts ( 41.2%)  ✅ (weakest)
  Channel C: LED=133 →  58,417 counts ( 89.2%)  ⚠️ Too bright
  Channel D: LED= 12 →  61,170 counts ( 93.3%)  ⚠️ NEAR SATURATION
```

**Problem**: Channel D reaches 93% at LED=12 (minimum). This leaves no headroom for P-mode, which typically measures 2-3x brighter than S-mode.

### Binary Search Bug Found and Fixed

**Issue**: When all LED values produce equal error (all saturated), binary search was choosing the FIRST tested value (133) instead of the LOWEST value (12).

**Fix Applied** (line 1973):
```python
# OLD: if intensity_error < best_error:
# NEW: if intensity_error < best_error or (intensity_error == best_error and current_led < best_led):
```

This ensures that when saturation occurs at all LED levels, we choose the minimum LED to reduce heat/power.

**Commit needed**:
```powershell
git add utils/spr_calibrator.py
git commit -m "Fix binary search to prefer lower LED when errors are equal"
git push origin master
```

## Root Cause Analysis

### Why Channel D Saturates

1. **Step 3**: Weakest channel identified as `b` (7,273 counts at LED=168)
2. **Step 4**: Integration time optimized for weakest channel at LED=255
   - Target: 80% of detector max = 52,428 counts
   - Result: 200ms integration achieves only 44.9% (29,449 counts)
   - **Issue**: 200ms is MAXIMUM integration time, can't go higher
3. **Step 6**: Binary search for other channels
   - Channel D tries to reach 52,428 counts
   - Even at LED=12 (minimum), reaches 61,170 counts (93%)
   - **Can't go lower** - already at hardware minimum!

### Why This Causes P-Mode Saturation

- **S-mode at 93%** leaves only 7% headroom (4,365 counts)
- **P-mode typically 2-3x brighter** than S-mode
- **Result**: P-mode channels C and D hit 65,535 (100% saturated)

## Solution: Reduce Integration Time

### Strategy

Instead of optimizing integration time for 80% of detector max (52,428 counts), we need to target a LOWER percentage that leaves headroom for bright channels.

**New target**: 40-50% of detector max (~26,000-32,000 counts)

This ensures:
- Weakest channel (b) at ~40%: 26,214 counts
- Bright channels (c, d) at minimum LED: ~30,000 counts (under 50%)
- P-mode has 2x headroom: 60,000 counts < 65,535 (no saturation)

### Implementation

**Modify `_optimize_integration_time()` to target lower percentage:**

```python
# Current (line ~1709):
S_COUNT_TARGET = int(0.80 * detector_max)  # 80% = 52,428

# Proposed:
S_COUNT_TARGET = int(0.50 * detector_max)  # 50% = 32,768
```

**Expected results after fix:**
```
Integration time: ~100ms (reduced from 200ms)

S-mode signals:
  Channel A: LED=133 →  21,000 counts ( 32%)  ✅
  Channel B: LED=255 →  14,700 counts ( 22%)  ✅ (weakest)
  Channel C: LED= 12 →  29,000 counts ( 44%)  ✅
  Channel D: LED= 12 →  30,500 counts ( 47%)  ✅

P-mode signals:
  Channel A: LED=133 →  42,000 counts ( 64%)  ✅
  Channel B: LED=255 →  29,400 counts ( 45%)  ✅
  Channel C: LED= 12 →  58,000 counts ( 88%)  ✅ (within limit)
  Channel D: LED= 12 →  61,000 counts ( 93%)  ✅ (within limit)
```

### Alternative: Dynamic Target Based on Bright Channels

More sophisticated approach:

1. **After Step 3**: Measure ALL channels at LED=minimum
2. **Calculate brightest-to-weakest ratio**
3. **Set target based on ratio**:
   ```python
   brightest_at_min = max(channel_intensities.values())
   weakest_intensity = min(channel_intensities.values())
   ratio = brightest_at_min / weakest_intensity  # e.g., 1.9x

   # Target should leave headroom for P-mode (assume 2x multiplier)
   max_s_mode_percent = 95% / 2 = 47.5%  # Leave 5% safety margin

   # Adjust for channel ratio
   target_percent = max_s_mode_percent / ratio = 47.5% / 1.9 = 25%

   S_COUNT_TARGET = int(0.25 * detector_max)  # 16,384 counts
   ```

This automatically adapts to hardware variability!

## Recommended Fix

### Option A: Quick Fix (5 minutes)

Change line ~1709 in `_optimize_integration_time()`:

```python
S_COUNT_TARGET = int(0.50 * detector_max)  # 50% target (was 80%)
```

**Pros**: Simple, immediate
**Cons**: May be too conservative for systems without bright LEDs

### Option B: Smart Fix (30 minutes)

Add saturation-aware integration time optimization:

```python
def _optimize_integration_time(self, weakest_ch: str, integration_step: float) -> bool:
    # ... existing code to optimize for weakest channel ...

    # NEW: Check if bright channels would saturate
    logger.info("🔧 Checking for potential saturation in bright channels...")

    # Test all channels at minimum LED
    brightest_signal = 0
    for ch in self.state.channels:
        if ch == weakest_ch:
            continue  # Skip weakest, we know it's optimized

        # Measure at minimum LED
        intensities_dict = {ch: MIN_LED_INTENSITY}
        self._activate_channel_batch([ch], intensities_dict)
        time.sleep(ADAPTIVE_STABILIZATION_DELAY)

        raw_spectrum = self.usb.read_intensity()
        spectrum = self._apply_spectral_filter(raw_spectrum)
        signal_region = spectrum[target_min_idx:target_max_idx]
        channel_max = signal_region.max()

        brightest_signal = max(brightest_signal, channel_max)

    # If brightest channel at minimum LED > 50% of detector max, reduce integration
    P_MODE_MULTIPLIER = 2.0  # Assume P-mode is 2x brighter
    SAFETY_MARGIN = 0.95  # Leave 5% headroom
    max_allowed_s_mode = (detector_max * SAFETY_MARGIN) / P_MODE_MULTIPLIER

    if brightest_signal > max_allowed_s_mode:
        reduction_factor = max_allowed_s_mode / brightest_signal
        new_integration = self.state.integration * reduction_factor

        logger.warning(f"⚠️ Bright channel would saturate in P-mode!")
        logger.warning(f"   Brightest signal at LED=min: {brightest_signal:.0f} ({brightest_signal/detector_max*100:.1f}%)")
        logger.warning(f"   P-mode estimate: {brightest_signal*P_MODE_MULTIPLIER:.0f} ({brightest_signal*P_MODE_MULTIPLIER/detector_max*100:.1f}%)")
        logger.info(f"🔧 Reducing integration time: {self.state.integration*1000:.1f}ms → {new_integration*1000:.1f}ms")

        self.state.integration = new_integration

        # Re-measure weakest channel with new integration, adjust LED upward
        # ... (implement LED boost for weakest channel)
```

**Pros**: Automatically adapts, prevents saturation
**Cons**: More complex, adds calibration time

## Next Steps

1. ✅ Commit binary search tie-breaker fix
2. Choose Option A or Option B
3. Implement fix
4. Test calibration
5. Verify P-mode doesn't saturate

## Testing Command

After implementing fix, run calibration and verify:

```powershell
python -c "import json; import numpy as np; data=json.load(open((sorted(__import__('glob').glob('generated-files/calibration_profiles/*.json'), key=lambda x: __import__('os').path.getmtime(x))[-1]))); print(f'Integration: {data[\"integration\"]*1000:.1f}ms'); print(f'LEDs: {data[\"ref_intensity\"]}'); print('\nS-mode signals:'); [print(f'  Ch {f.split(chr(92))[-1][6].upper()}: {np.load(f).max():6.0f} ({np.load(f).max()/65535*100:5.1f}%)') for f in sorted(__import__('glob').glob('generated-files/calibration_data/s_ref_*_latest.npy'))]; print('\n✅ SUCCESS if all channels 30-60%')"
```

**Success criteria**:
- Integration time: < 150ms
- All S-mode channels: 30-60% of detector max
- NO saturation warnings in logs
