# Step 5 Dark Noise QC Enhancement - Complete

## Summary
Added robust quality control (QC) for dark noise measurement in Step 5 to ensure LEDs are completely off and dark noise levels are within expected range for Ocean Optics/USB4000 class detectors.

## Changes Made to `utils/spr_calibrator.py`

### 1. Added QC Parameters (Detector Class Specific)
```python
# Ocean Optics Flame-T detector: typical dark noise ~3,000 counts @ 36ms integration
EXPECTED_DARK_MEAN_OCEAN_OPTICS = 3000.0  # counts (detector class specific)
DARK_QC_THRESHOLD = EXPECTED_DARK_MEAN_OCEAN_OPTICS * 2.0  # 6,000 counts
MAX_RETRY_ATTEMPTS = 3
```

**Key Point**: The 3,000 count baseline is **specific to Ocean Optics/USB4000 class detectors**. Other detector types will have different dark noise characteristics.

### 2. Retry Loop with Escalating LED-Off Delays
- Implemented 3-attempt retry loop for dark noise measurement
- Each retry uses **progressively longer LED-off settle times**:
  - Attempt 1: `settle_delay = max(led_off_delay_s, 0.5)` (typically 500ms)
  - Attempt 2: `settle_delay × 2` (1000ms)
  - Attempt 3: `settle_delay × 3` (1500ms)
- Ensures LEDs have sufficient time to completely turn off

### 3. Dark Noise QC Check
After each dark measurement:
```python
# Measure dark noise mean
dark_mean = np.mean(full_spectrum_dark_noise)

# QC: Check if exceeds 2× expected (6,000 counts for Ocean Optics)
if dark_mean > DARK_QC_THRESHOLD:
    # FAILED - retry with longer LED-off time
    if attempt < MAX_RETRY_ATTEMPTS:
        continue  # Retry
    else:
        # FATAL ERROR after 3 attempts
        return False
else:
    # PASSED
    break  # Exit retry loop
```

### 4. Comprehensive Error Logging
**On QC Failure:**
```
❌ QC FAILED: Dark noise mean (8,523.4) exceeds threshold (6,000 counts)
   Expected for Ocean Optics/USB4000: ~3,000 counts
   Measured dark is 2.8× higher than expected
   Possible causes:
   • LEDs not completely turned off
   • Light leaking into detector
   • Previous measurement residual signal

   Retrying with longer LED settle time...
```

**On Fatal Error (after 3 attempts):**
```
❌ FATAL: Dark noise QC failed after 3 attempts
   Cannot proceed with calibration - dark noise too high
   Please check:
   • All LEDs are physically off
   • Detector enclosure is light-tight
   • Hardware connections are secure
```

**On Success:**
```
✅ Dark noise QC PASSED: 2,847.3 counts < 6,000 threshold
   (Succeeded on retry attempt 2)
```

## Flow Diagram

```
Step 5: Measure Dark Noise
    │
    └─> For attempt = 1 to 3:
         │
         ├─> Turn off ALL LEDs (hardware command 'lx\n')
         ├─> Wait (settle_delay × attempt)
         ├─> Measure dark noise
         ├─> Calculate mean
         │
         ├─> IF mean > 6,000 counts:
         │    ├─> Log error with diagnostics
         │    ├─> IF attempt < 3:
         │    │    └─> Continue to next attempt (longer wait)
         │    └─> ELSE:
         │         └─> RETURN FALSE (fatal error)
         │
         └─> ELSE (mean ≤ 6,000 counts):
              └─> QC PASSED - break loop
```

## Testing Recommendations

1. **Normal Case** (LEDs properly turn off):
   - Should pass on first attempt
   - Dark noise ~3,000 counts for Ocean Optics detector

2. **Slow LED Decay** (LEDs take time to fully extinguish):
   - May fail attempt 1
   - Should pass on attempt 2 or 3 with longer settle time

3. **Fatal Error Cases** (should fail after 3 attempts):
   - LEDs physically stuck on
   - Light leaking into detector enclosure
   - Hardware malfunction

## Detector Class Notes

**Ocean Optics / USB4000 Class** (e.g., Flame-T):
- Expected dark noise: ~3,000 counts @ 36ms integration
- QC threshold: 6,000 counts (2× expected)
- 16-bit detector: 0-65,535 count range

**Other Detector Classes**:
- Different detectors will have different dark noise characteristics
- QC thresholds should be adjusted accordingly
- Always measure baseline dark during Step 1 for comparison

## Related Files
- `utils/spr_calibrator.py` - Modified `_measure_dark_noise_internal()` method
- Step 1 also uses this method (baseline dark before any LEDs)
- Step 5 uses this method (re-measure dark with final integration time)

## Backward Compatibility
✅ Fully backward compatible - existing calibration flow unchanged
✅ Only adds QC checks and retry logic
✅ No changes to API or return values
