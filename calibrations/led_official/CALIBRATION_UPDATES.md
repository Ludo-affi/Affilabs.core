# LED Calibration Updates - December 13, 2025

## Changes Made

### 1. Fixed Detector Wait Time
- **Added 50ms detector wait time** after LED stabilization and before detector sampling
- This ensures the detector has adequate time to settle after LED changes
- Parameter: `DETECTOR_WAIT_MS = 50` (fixed, consistent across all measurements)

### 2. Saturation Protection
- **Previous issue**: Calibration was hitting 62,000+ counts (95% of 65535 max capacity)
- **New threshold**: Stop scanning when counts exceed **60,000** (92% capacity)
- **Reduced LED intensities**: Changed from `[50, 100, 150, 200, 255]` to `[30, 60, 90, 120, 150]`
- This prevents saturation artifacts that make calibration data unreliable

### 3. Enhanced Saturation Detection
- Added `is_saturated` flag that triggers when:
  - Any pixel reaches 65535 (hard saturation), OR
  - Top-10 average exceeds 60,000 (near-saturation warning)
- Added `near_saturation_pixels` count to warn when pixels approach limits
- Displays warnings during measurement: `⚠️ X pixels >60k`

### 4. Improved Validation Testing
- Validation tests now check for saturation and display `⚠️ SAT` status
- Target of 60,000 counts for validation (previously was pushing limits)

## Why These Changes Matter

### Saturation Artifacts
When a detector saturates:
- Response becomes non-linear
- Calibration models become inaccurate
- Cannot distinguish between different LED intensities
- Data is essentially "clipped" at the maximum value

### Detector Wait Time
The 50ms wait ensures:
- LED output has fully stabilized
- Photodetector has settled
- Measurements are consistent and repeatable
- Reduced noise and artifacts from transients

## Usage

Run the updated calibration:
```bash
python led_calibration_official/1_create_model.py
```

The script will now:
1. Use 50ms detector wait (consistent timing)
2. Test with lower LED intensities to avoid saturation
3. Stop scanning if approaching saturation threshold
4. Document detector_wait_ms in the output JSON

## Output Format

The generated JSON file now includes:
```json
{
  "detector_wait_ms": 50,
  "saturation_threshold": 60000,
  "timestamp": "...",
  "dark_counts_per_time": {...},
  "led_models": {...},
  ...
}
```

## Previous Saturation Issues

From `led_calibration_3stage_20251212_133206.json`:
- **20ms integration, all LEDs**: 62,433 counts (95% saturation) ❌
- **30ms integration, all LEDs**: 62,392 counts (95% saturation) ❌
- **50ms integration, all LEDs**: 62,297 counts (95% saturation) ❌

These measurements were too close to the 65535 limit and likely contained artifacts.

## Recommended Next Steps

1. **Re-run calibration** with the updated script
2. **Verify** that no measurements exceed 60,000 counts
3. **Validate** model accuracy at multiple integration times
4. **Compare** old vs new calibration to see improvement in linearity
