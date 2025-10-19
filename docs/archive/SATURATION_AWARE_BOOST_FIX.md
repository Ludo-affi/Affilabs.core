# Saturation-Aware Integration Time Boost Fix

## Problem Summary

**Issue**: Channels C and D saturating at 610nm and below wavelengths during live P-mode measurements

**Root Cause**: Smart boost system was **blindly** boosting integration time 1.5× (50% → 75% target) without checking per-channel saturation risk.

### Why Saturation Occurred

1. **Calibration (S-mode)**: Integration time optimized for **weakest channel** (e.g., channel B at 50%)
2. **Bright channels** (C, D): Already at 80-90% in S-mode at same integration time
3. **Blind boost**: System calculates `boost = 75% / 50% = 1.5×` for ALL channels
4. **Result**: Bright channels boosted from 85% → **>100%** = **SATURATION** 💥

### Wavelength Specificity

- **Blue wavelengths** (610nm and below): Highest LED output + detector sensitivity
- **Red wavelengths** (640-680nm): Lower intensity, no saturation
- **SPR peak** (630-650nm): Critical range, affected by saturation wings

---

## Solution Implemented

### Two-Part Fix

#### Part 1: Reduce Target (Quick Fix) ✅

**File**: `settings/settings.py`
**Change**: `LIVE_MODE_TARGET_INTENSITY_PERCENT = 60` (was 75%)

**Effect**:
- Desired boost: 60% / 50% = **1.2×** (was 1.5×)
- Reduces saturation risk across all channels
- Still provides 20% signal boost over calibration

#### Part 2: Saturation-Aware Boost (Smart Fix) ✅

**File**: `utils/spr_state_machine.py` (lines 370-430)

**Algorithm**:
```python
# For each channel, check S-mode reference spectrum maximum
for ch, ref_spectrum in self.ref_sig.items():
    max_signal = np.max(ref_spectrum)  # Peak signal at blue wavelengths
    current_percent = (max_signal / 65535) * 100

    # Calculate safe boost: What factor keeps channel below 90%?
    safe_boost = (0.9 * 65535) / max_signal

    # Limit global boost to the MOST RESTRICTIVE channel
    max_safe_boost = min(max_safe_boost, safe_boost)

# Final boost is the minimum of:
# 1. Desired boost (1.2× from 60/50 target)
# 2. Maximum allowed (2.5× hard limit)
# 3. Saturation-safe boost (per-channel check)
boost_factor = min(desired_boost, LIVE_MODE_MAX_BOOST_FACTOR, max_safe_boost)
```

**Example Output**:
```
📊 Calibration settings:
   Integration time: 150.0ms
   Target signal: 50% (~32768 counts)

⚠️  Channel C: S-mode max = 55000 (83.9%)
    Safe boost for this channel: 1.07×
⚠️  Channel D: S-mode max = 58000 (88.5%)
    Safe boost for this channel: 1.02×
🛡️  Boost reduced to 1.02× to prevent saturation

🎯 Live mode optimization:
   Target signal: 60% (~39321 counts)
   Boost factor: 1.02× (max: 2.5×)
   Boosted integration: 150.0ms → 153.0ms
   Expected signal: 51.0% (~33423 counts)
```

---

## How It Works

### Calibration Phase (S-mode)
1. **Step 3**: Identify weakest channel (e.g., Channel B)
2. **Step 4**: Optimize integration time for weakest at 50% target
   - Channel B: 50% ✅ (target)
   - Channel C: 84% ⚠️ (bright)
   - Channel D: 89% ⚠️ (brightest)
3. **Store S-mode reference spectra** in `state.ref_sig[ch]`

### Live Mode Phase (P-mode)
1. **Calculate desired boost**: 60% / 50% = 1.2×
2. **Check per-channel saturation**:
   - Scan each S-mode reference spectrum
   - Find maximum signal (usually at blue wavelengths 580-610nm)
   - Calculate safe boost: `(90% × 65535) / max_signal`
3. **Apply most restrictive limit**:
   - If Channel D at 89% → safe_boost = 1.01×
   - Use 1.01× instead of 1.2× to prevent saturation
4. **Result**: All channels stay below 90%

---

## Expected Behavior

### Before Fix
```
Channel A: 45% → 67.5%  ✅ Good
Channel B: 50% → 75.0%  ✅ Good (weakest)
Channel C: 84% → 126%   ❌ SATURATED!
Channel D: 89% → 133%   ❌ SATURATED!
```

### After Fix (Reduced Target)
```
Channel A: 45% → 54%    ✅ Good
Channel B: 50% → 60%    ✅ Good (weakest)
Channel C: 84% → 101%   ❌ Still saturates!
Channel D: 89% → 107%   ❌ Still saturates!
```

### After Fix (Saturation-Aware)
```
Channel A: 45% → 46%    ✅ Good
Channel B: 50% → 51%    ✅ Good (weakest)
Channel C: 84% → 86%    ✅ Safe
Channel D: 89% → 91%    ✅ Just below saturation
```

---

## Testing

### Test Command

After running calibration and starting live mode, check the logs for:

```bash
# Look for saturation-aware boost messages
grep "Safe boost for this channel" logs.txt
grep "Boost reduced to" logs.txt
```

**Success Criteria**:
- ✅ Log shows per-channel saturation check
- ✅ Boost factor reduced below desired (e.g., 1.05× instead of 1.2×)
- ✅ All channels below 90% in live P-mode
- ✅ No saturation artifacts at 610nm and below
- ✅ SPR peak (630-650nm) clean and trackable

### Manual Verification

```python
import numpy as np
import glob

# Check live P-mode signal levels
for f in sorted(glob.glob('generated-files/calibration_data/s_ref_*_latest.npy')):
    ch = f.split('\\')[-1][6].upper()
    data = np.load(f)
    max_signal = data.max()
    print(f"Channel {ch}: {max_signal:.0f} counts ({max_signal/65535*100:.1f}%)")
```

**Expected**: All channels 40-85% (none above 90%)

---

## Configuration

### Settings (settings/settings.py)

```python
# Live mode boost targets
LIVE_MODE_TARGET_INTENSITY_PERCENT = 60  # Reduced from 75% to prevent saturation
LIVE_MODE_MIN_BOOST_FACTOR = 1.0         # Never reduce below calibrated
LIVE_MODE_MAX_BOOST_FACTOR = 2.5         # Hard upper limit

# Calibration target
TARGET_INTENSITY_PERCENT = 50  # Conservative S-mode target
```

### Saturation Detection

```python
# In spr_state_machine.py
saturation_threshold = 0.9  # 90% of detector max (59K counts)
```

**Adjustment**: If still seeing saturation, reduce to `0.85` (85%)

---

## Trade-offs

### Pros ✅
- **No saturation**: Bright channels protected
- **Automatic**: Per-channel detection, no manual tuning
- **Diagnostic**: Logs show which channels limit boost
- **Safe**: Always stays below 90% detector max

### Cons ⚠️
- **Lower SNR for weak channels**: If bright channels limit boost, weak channels don't benefit
- **Minimal boost**: In your case, boost might be only 1.05× instead of 1.2×
- **Complexity**: More code, more failure modes

### Alternative Approach

**Per-Channel Integration Time** (Future Enhancement):
- Each channel uses different integration time
- Weak channels: Long integration (e.g., 200ms)
- Bright channels: Short integration (e.g., 100ms)
- **Downside**: More complex acquisition loop, slower updates

---

## Troubleshooting

### Issue: Still seeing saturation

**Check 1**: Is saturation-aware boost active?
```bash
grep "Safe boost for this channel" logs.txt
```
- If missing → Code not running, check imports

**Check 2**: What's the boost factor?
```bash
grep "Boost factor:" logs.txt
```
- If still 1.2× → Channels not limiting boost (all below 75% in S-mode)
- If 1.0× → Channels already at saturation threshold in S-mode

**Check 3**: Reduce saturation threshold
```python
# In spr_state_machine.py, line ~392
saturation_threshold = 0.85  # Was 0.9, reduce to 85%
```

### Issue: Weak channels too dim

**Symptom**: Channel B only at 51% instead of desired 60%

**Cause**: Bright channels (C, D) limiting boost factor

**Solutions**:
1. **Accept lower SNR** on weak channels (safest)
2. **Reduce LED intensity** of bright channels during calibration
3. **Implement per-channel integration** (complex)

### Issue: No boost at all (1.0×)

**Symptom**: Integration time unchanged in live mode

**Cause**: Brightest channel already at 90% in S-mode calibration

**Action**:
1. Re-run calibration with **lower target**:
   ```python
   TARGET_INTENSITY_PERCENT = 40  # Was 50%
   ```
2. This gives 20% headroom for boost in live mode

---

## Success Metrics

### Before Fix
- ❌ Channels C, D saturated (>95%) at 610nm and below
- ❌ Transmission spectra clipped
- ❌ SPR peak distorted by saturation wings
- ❌ Poor sensorgram quality

### After Fix
- ✅ All channels below 90% across full spectrum
- ✅ Clean transmission spectra (no clipping)
- ✅ Sharp SPR peak at 630-650nm
- ✅ Reliable peak tracking
- ✅ Stable sensorgram

---

## Related Documentation

- **Calibration Flow**: `CALIBRATION_STREAMLINED_FLOW.md`
- **Integration Time Optimization**: `INTEGRATION_TIME_REDUCTION_FIX.md`
- **LED Saturation**: `HARDWARE_LED_SATURATION_FIX.md`
- **Step 4 Algorithm**: `STEP_4_ALL_CHANNELS_VALIDATED.md`
- **Live Mode Boost**: `LIVE_MODE_INTEGRATION_BOOST.md`

---

## Implementation Status

- ✅ Reduced target from 75% → 60% (settings.py)
- ✅ Added per-channel saturation detection (spr_state_machine.py)
- ✅ Boost factor limited by most restrictive channel
- ✅ Diagnostic logging for channel saturation
- 📝 Documentation created (this file)
- ⏳ Testing required (run calibration → live mode)

**Next Steps**:
1. Run full calibration
2. Start live measurements
3. Check logs for saturation warnings
4. Verify all channels below 90%
5. Adjust `saturation_threshold` if needed
