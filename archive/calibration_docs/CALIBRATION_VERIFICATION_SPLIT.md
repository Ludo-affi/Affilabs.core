# Calibration Verification Function Split - Complete

**Date:** November 26, 2025
**Status:** ✅ COMPLETE - Ready for testing

## What Was Done

Split the shared `verify_calibration()` function into two completely separate functions to eliminate confusion and prevent cross-contamination between calibration methods.

## New Architecture

### 1. `verify_calibration_global_integration()` (Line 1532)
**Used by:** `perform_full_led_calibration()`
**Strategy:** Fixed integration time, variable LED intensity per channel
**Saturation handling:** Single-pass LED intensity reduction (85% target)

```python
# Function signature
def verify_calibration_global_integration(
    usb, ctrl, leds_calibrated,
    wave_data=None, s_ref_signals=None,
    pre_led_delay_ms=45.0, post_led_delay_ms=5.0
) -> tuple[list[str], dict[str, float], bool]
```

**Key behavior:**
- If channel saturates → reduce LED intensity (NOT integration time)
- Single reduction pass: target 85% of detector max
- Updates `leds_calibrated` dict with corrected LED values

### 2. `verify_calibration_global_led()` (Line 1900)
**Used by:** `perform_alternative_calibration()`
**Strategy:** Fixed LED intensity (255 for all), variable integration time per channel
**Saturation handling:** Multi-pass integration time reduction (80% target, up to 5 attempts)

```python
# Function signature
def verify_calibration_global_led(
    usb, ctrl, leds_calibrated, integration_times,
    wave_data=None, s_ref_signals=None,
    pre_led_delay_ms=45.0, post_led_delay_ms=5.0
) -> tuple[list[str], dict[str, float], bool]
```

**Key behavior:**
- If channel saturates → reduce integration time (NOT LED)
- Multi-pass reduction: up to 5 attempts, target 80% of detector max
- Updates `integration_times` dict with corrected values

## Changes Made

### File: `src/utils/led_calibration.py`

1. **Created two new functions** (lines 1532-2247):
   - `verify_calibration_global_integration()` - LED reduction logic only
   - `verify_calibration_global_led()` - Integration time reduction logic only

2. **Updated `perform_full_led_calibration()`** (line ~2931):
   ```python
   # OLD
   result.ch_error_list, result.spr_fwhm, polarizer_swap_detected = verify_calibration(
       usb, ctrl, result.leds_calibrated, result.wave_data, result.ref_sig,
       pre_led_delay_ms=pre_led_delay_ms, post_led_delay_ms=post_led_delay_ms
   )

   # NEW
   result.ch_error_list, result.spr_fwhm, polarizer_swap_detected = verify_calibration_global_integration(
       usb, ctrl, result.leds_calibrated, result.wave_data, result.ref_sig,
       pre_led_delay_ms=pre_led_delay_ms, post_led_delay_ms=post_led_delay_ms
   )
   ```

3. **Updated `perform_alternative_calibration()`** (line ~3552):
   ```python
   # OLD
   result.ch_error_list, result.spr_fwhm, polarizer_swap_detected = verify_calibration(
       usb, ctrl, result.leds_calibrated, result.wave_data, result.ref_sig,
       pre_led_delay_ms=pre_led_delay_ms, post_led_delay_ms=post_led_delay_ms,
       integration_times=p_integration_times, use_integration_reduction=True
   )

   # NEW
   result.ch_error_list, result.spr_fwhm, polarizer_swap_detected = verify_calibration_global_led(
       usb, ctrl, result.leds_calibrated, p_integration_times,
       result.wave_data, result.ref_sig,
       pre_led_delay_ms=pre_led_delay_ms, post_led_delay_ms=post_led_delay_ms
   )
   ```

## Benefits

✅ **Zero confusion** - Function name clearly indicates which method it belongs to
✅ **No conditional logic** - Each function has single, clear purpose
✅ **Easier debugging** - No need to trace through if/else branches
✅ **AI-friendly** - Copilot sees correct context immediately
✅ **Safer modifications** - Changes to one method can't affect the other
✅ **Better maintainability** - Each function is self-contained

## Shared Logic

Both functions share:
- Global orientation tracking (polarizer is hardware property)
- SPR FWHM calculation and sensor readiness assessment
- S/P orientation validation (same physics for both methods)
- Polarizer swap detection (3+ channels with inverted orientation)

## Critical Differences

| Aspect | Global Integration | Global LED |
|--------|-------------------|-----------|
| **LED intensity** | Variable per channel | Fixed at 255 |
| **Integration time** | Fixed for all | Variable per channel |
| **Saturation fix** | Reduce LED | Reduce integration |
| **Passes** | Single pass | Multi-pass (up to 5) |
| **Target** | 85% of max | 80% of max |
| **Updates** | `leds_calibrated` | `integration_times` |

## Testing Priority

**Focus on GLOBAL INTEGRATION TIME method first** (`perform_full_led_calibration`):
- This is the most critical method to make work fast
- Uses `verify_calibration_global_integration()`
- Should handle LED intensity reduction cleanly
- No risk of confusion with global LED method

## Next Steps

1. ✅ Refactoring complete
2. ⏳ Run `.\run.bat` to test global integration method
3. ⏳ Verify LED intensity reduction works correctly
4. ⏳ Confirm no channels fail verification
5. ⏳ Check calibration completes successfully

## Old Function

The original `verify_calibration()` with conditional logic can now be safely removed in future cleanup (not removed yet to avoid breaking anything during testing).
