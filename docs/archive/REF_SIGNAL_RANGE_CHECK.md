# Reference Signal Wavelength Range Verification

**Critical Finding:** S and P references may be sampling from wrong wavelength range (441-580 nm instead of 580-720 nm)

## What to Check

When main app starts acquisition after calibration, look for this log message:

```
🔍 Debug sizes cha: ref_sig=XXXX, dark_correction=1590, wave_data=1591, averaged_intensity=1590
```

### If ref_sig = 3648:
❌ **PROBLEM CONFIRMED** - Reference signal is NOT filtered to 580-720 nm!
- It's the full spectrum (441-773 nm)
- When used for transmission, it gets resized and takes first 1590 pixels
- This samples ~441-580 nm instead of 580-720 nm
- **This matches your observation!**

### If ref_sig = ~1591:
✅ Reference signal IS filtered correctly
- Issue is just 1-pixel mismatch (minor, fixable)

## How to Fix if ref_sig=3648

Check calibration logs for these warnings:
- "⚠️ Wavelength mask not initialized - returning full spectrum"
- "Could not recreate mask - returning unfiltered spectrum"

These indicate `_apply_spectral_filter()` in `spr_calibrator.py` is failing and falling back to unfiltered spectrum.

**Solution:** Ensure wavelength calibration step completes successfully before reference measurement.

## Files Modified

- `utils/spr_data_acquisition.py`: Added size logging at line 380
- `view_debug_steps.py`: Added size mismatch handling
- `utils/spr_data_acquisition.py`: Added size checking in `_save_debug_step()`

## Next Action

Start acquisition in main app and check the log for the debug sizes message.
