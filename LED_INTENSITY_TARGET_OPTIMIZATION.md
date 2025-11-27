# LED Intensity Target Optimization

## Overview
Adjusted calibration targets to optimize LED intensity values rather than just signal counts. This ensures better hardware utilization and more predictable P-mode performance.

## Changes Made

### 1. S-Mode Target Adjustment (70% instead of 75%)

**Files Modified:**
- `src/utils/usb4000_wrapper.py`
- `src/utils/phase_photonics_wrapper.py`

**Change:**
```python
# OLD: Target 75% of detector max
return int(0.75 * self._max_counts)

# NEW: Target 70% of detector max
return int(0.70 * self._max_counts)
```

**Rationale:**
- By lowering the S-mode target from 75% to 70%, the optimization algorithm allows more LED headroom
- This typically results in the weakest channel reaching LED intensity ~220 (instead of maxing out at 255)
- Provides ~35 LED intensity units of headroom for P-mode boost
- Better balance between signal quality and P-mode optimization potential

### 2. P-Mode Target Adjustment (92% instead of 95%)

**File Modified:**
- `src/utils/led_calibration.py`

**Change:**
```python
# OLD: Target 95% of saturation threshold (90% of absolute max)
optimal_target = saturation_threshold * 0.95

# NEW: Target 92% of saturation threshold (87% of absolute max)
optimal_target = saturation_threshold * 0.92
```

**Rationale:**
- Slightly more conservative P-mode target provides safety margin when pushing LEDs to 255
- Goal is to maximize LED intensity (reach 255) while staying safely below saturation
- 92% target allows for spectrum variations and temporal fluctuations
- Still maximizes SNR while preventing accidental saturation

### 3. Enhanced Documentation

**Added clarifications in code comments:**
- S-mode optimizes for ~70% target with weakest LED near 220
- P-mode goal is to push to LED=255 (max) as long as signal doesn't saturate
- Priority in P-mode: Maximize LED intensity over conservative signal target

## Expected Behavior After Changes

### S-Mode Calibration
- Target signal: ~70% of detector max
- Weakest channel LED intensity: ~220 (not maxed out)
- Headroom for P-mode: ~35 LED intensity units
- Signal quality: Still excellent (70% provides good SNR)

### P-Mode Calibration
- Starting point: S-mode LED intensities (~220 for weakest)
- Target: Push to LED=255 (maximum intensity)
- Signal constraint: Stay below 92% of saturation threshold
- Expected result: Most channels reach LED=255, signals near ~87% of detector max

## Benefits

1. **Predictable LED Usage**: Weakest channel consistently near LED=220, not saturated at 255
2. **Better P-Mode Headroom**: ~35 LED units available for P-mode boost
3. **Hardware Longevity**: Not running weakest LED at maximum during S-mode
4. **Maximum SNR in P-Mode**: Push to LED=255 while staying safe from saturation
5. **Consistent Performance**: More predictable calibration results across devices

## Validation

After calibration, verify:
- ✅ S-mode weakest channel LED intensity: ~200-230 (target: 220)
- ✅ P-mode LED intensities: Most channels at or near 255
- ✅ P-mode signals: ~85-90% of detector max (below saturation)
- ✅ All channels balanced via weakest LED rule

## Technical Notes

- Detector `target_counts` property returns 70% of `max_counts` (was 75%)
- P-mode `optimal_target` is 92% of `saturation_threshold` (was 95%)
- Both detectors (USB4000 and PhasePhotonics) updated for consistency
- Changes are backward compatible with existing calibration flow
