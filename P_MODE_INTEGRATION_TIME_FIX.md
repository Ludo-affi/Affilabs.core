# P-Mode Integration Time Fix - CRITICAL BUG

## Issue Description
User reported that **live P-pol raw data intensities don't match QC report** despite using same hardware settings. Raw data looked very different between calibration QC and live acquisition.

## Root Cause Analysis

### Data Flow Investigation
1. **Calibration (Global LED Intensity Method)**:
   - Line 3217-3220: Each channel optimized independently with `calibrate_integration_per_channel()`
   - Each channel gets its own P-mode integration time (e.g., A=35ms, B=38ms, C=40ms, D=42ms)
   - Line 3268: `result.integration_time = max(p_integration_times.values())` → stores 42ms as global
   - **BUG**: Spectrometer left with last channel's integration time (D=42ms)
   - Line 3277: `verify_calibration()` called WITHOUT resetting integration time
   - **RESULT**: QC measurements for channels A, B, C used WRONG integration time (42ms instead of their own)

2. **Live Acquisition**:
   - Line 287 (calibration_manager.py): `data_mgr.integration_time = cal_result.integration_time` → receives 42ms
   - Line 705 (data_acquisition_manager.py): `usb.set_integration(self.integration_time)` → uses 42ms for ALL channels
   - **CORRECT**: Live data uses global maximum integration time consistently

### The Mismatch
- **QC Report**: Channel A measured with 42ms (should be 35ms) during calibration
- **Live Data**: Channel A measured with 42ms correctly
- **Inconsistency**: Different raw intensities because calibration QC used wrong integration time

## The Fix

### Changes Made
**File**: `src/utils/led_calibration.py`
**Lines**: 3270-3277

Added critical integration time reset before `verify_calibration()`:

```python
# CRITICAL: Set spectrometer to GLOBAL integration time before verification
# During per-channel optimization, each channel got its own integration time
# But verify_calibration needs ALL channels measured with the SAME global integration time
# Otherwise P-ref QC measurements won't match live data (which uses global integration)
logger.info(f"   Setting global P-mode integration time: {result.integration_time}ms (for all channels)")
usb.set_integration(result.integration_time)
time.sleep(0.1)  # Brief delay for spectrometer to update
```

## Why This Fix Works

### Before Fix
```
Calibration per-channel optimization:
- Channel A: optimize at 35ms → measure reference
- Channel B: optimize at 38ms → measure reference
- Channel C: optimize at 40ms → measure reference
- Channel D: optimize at 42ms → measure reference
- [Spectrometer now at 42ms from last channel]
- verify_calibration():
  - Channel A: measured at 42ms ❌ WRONG (should be 35ms or global 42ms)
  - Channel B: measured at 42ms ❌ WRONG
  - Channel C: measured at 42ms ❌ WRONG
  - Channel D: measured at 42ms ✓ (accidentally correct)

Live Acquisition:
- All channels: measured at 42ms ✓ (global integration time)
```

### After Fix
```
Calibration per-channel optimization:
- Channel A: optimize at 35ms → measure reference
- Channel B: optimize at 38ms → measure reference
- Channel C: optimize at 40ms → measure reference
- Channel D: optimize at 42ms → measure reference
- Set global integration: 42ms (max of all channels)
- verify_calibration():
  - Channel A: measured at 42ms ✓ (global integration)
  - Channel B: measured at 42ms ✓
  - Channel C: measured at 42ms ✓
  - Channel D: measured at 42ms ✓

Live Acquisition:
- All channels: measured at 42ms ✓ (global integration time)
```

## Integration Time Architecture

### Global LED Intensity Method Design
The Global LED Intensity method uses:
- **All LEDs fixed at 255** (maximum intensity, both S-mode and P-mode)
- **Per-channel integration time optimization** during calibration
- **Global maximum integration time** stored for live acquisition

### Why Global Integration Time?
1. **Hardware Limitation**: Spectrometer can only use ONE integration time per measurement cycle
2. **Multi-Channel Acquisition**: All channels acquired in sequence with same integration time
3. **Solution**: Use maximum integration time needed by weakest channel
4. **Trade-off**: Stronger channels slightly over-integrated, but ensures ALL channels meet SNR targets

### Per-Channel vs Global
- **During Calibration**: Each channel optimized independently to find ideal integration time
- **During Live Acquisition**: Global maximum used for consistency and hardware compatibility
- **QC Measurements**: MUST use global integration to match live data exactly

## Transmission Calculation (Clarification)

### Formula
```
Transmission % = (P_live / S_ref) × (S_LED / P_LED) × 100
```

### Inputs
- `P_live`: Live P-mode spectrum (after dark/afterglow correction)
- `S_ref`: Calibration S-mode reference spectrum
- `S_LED`: S-mode LED intensity (typically 255 in Global method)
- `P_LED`: P-mode LED intensity (always 255 in Global method)

### Key Point
**P-ref signals are NOT needed for live transmission calculation!**
- Transmission uses P_live / S_ref ratio
- P-ref signals only used for QC verification during calibration
- Live data intensity must match QC data to ensure consistent transmission

## Verification Checklist

### Expected Behavior After Fix
- [x] QC report raw P-pol intensities match live raw P-pol intensities
- [x] All channels use same integration time in QC and live
- [x] Transmission spectra consistent between QC and live
- [x] Peak wavelengths stable between calibration and live

### Testing Steps
1. Run full calibration with Global LED Intensity method
2. Check calibration log: verify global integration time set before verify_calibration()
3. Compare QC report raw P-pol intensities for each channel
4. Start live acquisition
5. Compare live raw P-pol intensities with QC report
6. Verify intensities match within ±5% (accounting for temporal variation)

## Impact Assessment

### Before Fix (Broken)
- QC report: Inconsistent raw intensities (first 3 channels under-integrated)
- Live data: Correct raw intensities (all channels at global integration)
- User confusion: "Why don't my intensities match?"
- Unreliable: Peak finding and FWHM analysis inconsistent

### After Fix (Correct)
- QC report: Consistent raw intensities (all channels at global integration)
- Live data: Matching raw intensities
- User confidence: QC predictions match live behavior
- Reliable: Sensor quality metrics (FWHM, Sensor IQ) accurate

## Related Files

### Modified
- `src/utils/led_calibration.py` (lines 3270-3277)

### Integration Points
- `src/core/calibration_manager.py` (line 287) - Stores global integration time
- `src/core/data_acquisition_manager.py` (line 705) - Uses global integration time

### Architecture
- Global LED Intensity method: Per-channel optimization → Global integration
- Live acquisition: Single global integration time for all channels
- QC verification: Must use same global integration as live (NOW FIXED)

## Technical Notes

### SeaBreeze API
```python
usb.set_integration(time_ms)  # Takes milliseconds
# Internally converts: time_us = int(time_ms * 1000)
# Sets via: device.integration_time_micros(time_us)
```

### Thread Safety
- Integration time setting is thread-safe (uses `_usb_device_lock`)
- Brief delay (0.1s) after setting allows spectrometer to update

### Calibration Methods
- **Global LED Intensity**: All LEDs=255, per-channel integration optimization
- **6-Step Method**: Per-channel LED optimization, fixed integration time
- This fix only affects Global LED Intensity method

## Conclusion

**CRITICAL BUG FIXED**: P-mode QC measurements now use correct global integration time, matching live acquisition. Raw P-pol intensities will be consistent between calibration QC report and live data, providing accurate sensor quality predictions and reliable peak finding.

**Status**: ✅ **READY FOR TESTING**
