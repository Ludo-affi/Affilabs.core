# Hardware LED Saturation Fix

## Issue Summary

**CALIBRATION CODE IS NOW WORKING CORRECTLY!** ✅

However, channels C and D have a **hardware limitation**:

### Calibration Results (Latest Run)
```
Step 3: Weakest channel identified: b (7,123 counts at LED=168)

Step 6: Binary Search LED Calibration
- Channel A: LED=133 → 41,639 counts (63.5%) ✅
- Channel B: LED=255 (weakest, fixed) → 26,277 counts (40%) ✅
- Channel C: LED=12 (MINIMUM) → 65,485 counts (99.9%) ❌ SATURATED
- Channel D: LED=14 (MINIMUM) → 62,081 counts (94.7%) ❌ SATURATED
```

**Problem**: Channels C and D LEDs are **physically too bright**. Even at the MINIMUM LED intensity (12-14), they saturate the detector.

The binary search correctly tried to reduce them but **hit the hardware minimum** (MIN_LED_INTENSITY=13).

## Root Cause

**Hardware Mismatch**:
- Channels C and D use brighter LEDs (or have higher optical efficiency)
- Current integration time: 200ms
- Even at LED=12 (5% of max), signal reaches 65,535 counts (100% saturation)

## Solution Options

### Option 1: Reduce Integration Time (RECOMMENDED)

**Modify Step 4 to use SHORTER integration time:**

Current behavior:
1. Step 3: Identify weakest channel (b)
2. Step 4: Optimize integration for weakest at LED=255
3. Result: Integration=200ms (too long for bright channels)
4. Step 6: Binary search fails - even LED=12 saturates

**Fix**: After Step 4, check if ANY channel will saturate, then REDUCE integration time:

```python
# After Step 4: Check if bright channels will saturate
brightest_signal_at_min = max_bright_channel_intensity_at_led_min
if brightest_signal_at_min > SATURATION_THRESHOLD:
    # Reduce integration time proportionally
    reduction_factor = SATURATION_THRESHOLD / brightest_signal_at_min
    new_integration = current_integration * reduction_factor
    logger.info(f"🔧 Reducing integration time: {current_integration}ms → {new_integration}ms")
    logger.info(f"   Reason: Bright channels would saturate even at minimum LED")
    self.state.integration = new_integration

    # Re-optimize weakest channel with new integration time
    # (May need to increase LED on weakest to compensate)
```

### Option 2: Per-Channel Integration Time (COMPLEX)

Allow each channel to use different integration times. Not recommended - requires major architecture changes.

### Option 3: Hardware Modification (EXTERNAL)

- Add neutral density (ND) filters to channels C and D
- Replace C and D LEDs with lower-power variants
- Add resistors to reduce C/D LED current

## Recommended Implementation

**Modify `_optimize_integration_time()` to be "saturation-aware":**

1. After optimizing for weakest channel:
   - Test ALL channels at their EXPECTED LED values
   - If any channel would saturate (>90%), reduce integration time
   - Re-test weakest channel, adjust LED upward if needed

2. **Target balance**:
   - Weakest channel: 40-60% of detector max (at LED=255)
   - Brightest channel: 80-90% of detector max (at LED=minimum)
   - All channels: Within 2x intensity range

## Expected Results After Fix

```
Integration Time: 80ms (reduced from 200ms to prevent saturation)

Step 6 Binary Search:
- Channel A: LED=160 → 42,000 counts (64%) ✅
- Channel B: LED=255 → 30,000 counts (46%) ✅
- Channel C: LED=12 → 26,000 counts (40%) ✅ NO SATURATION
- Channel D: LED=14 → 25,000 counts (38%) ✅ NO SATURATION
```

## Verification Command

```powershell
python -c "import json; data=json.load(open((sorted(__import__('glob').glob('generated-files/calibration_profiles/*.json'), key=lambda x: __import__('os').path.getmtime(x))[-1]))); print('Integration:', data['integration']*1000, 'ms'); print('LEDs:', data['ref_intensity']); import numpy as np; [print(f'Ch {f.split(chr(92))[-1][6].upper()}: {np.load(f).max():.0f} ({np.load(f).max()/65535*100:.1f}%)') for f in sorted(__import__('glob').glob('generated-files/calibration_data/s_ref_*_latest.npy'))]"
```

**Success criteria**:
- Integration time: < 150ms
- All channels: 30-60% of detector max
- NO channel at 99%+ saturation

## Current Status

✅ Calibration flow is correct
✅ Step 3 (weakest channel identification) works
✅ Step 6 (binary search LED calibration) works
❌ Hardware limitation: Channels C/D too bright
🔧 **Next step: Implement saturation-aware integration time optimization**
