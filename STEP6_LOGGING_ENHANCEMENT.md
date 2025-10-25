# Step 6 Calibration Logging Enhancement

## Summary

Added detailed logging after Step 6 (S-reference measurement) completion to help diagnose calibration issues, specifically to identify why only Channel B LED is being set while A/C/D remain at 0.

## Location

**File:** `utils/spr_calibrator.py`
**Function:** `step_6_measure_s_reference()`
**Line:** ~3830 (after marking calibration complete)

## Changes

Added comprehensive logging block that prints final calibration parameters after Step 6 completes:

### For GLOBAL Calibration Mode:
```
================================================================================
📊 STEP 6 COMPLETE - FINAL CALIBRATION PARAMETERS
================================================================================
Mode: GLOBAL (single integration time for all channels)
Integration Time: 150.0 ms
Scans per channel: 4

   Channel  | LED Intensity
   --------------------------
      A     |      128
      B     |      255
      C     |       96
      D     |       64

================================================================================
```

**If all LEDs have the same value (red flag):**
```
   Channel  | LED Intensity
   --------------------------
      A     |      255
      B     |      255
      C     |      255
      D     |      255

⚠️  WARNING: All channels have IDENTICAL LED values!
   All LEDs = 255
   This suggests Step 4 (LED balancing) did not execute properly.
   Expected: Different LED values to balance channels to weakest.
```

### For PER-CHANNEL Calibration Mode:
```
================================================================================
📊 STEP 6 COMPLETE - FINAL CALIBRATION PARAMETERS
================================================================================
Mode: PER-CHANNEL (separate integration times per channel)

   Channel  | LED Intensity | Integration Time | Scans
   ----------------------------------------------------------
      A     |      255       |      120.0 ms     |   1
      B     |      255       |       80.0 ms     |   1
      C     |      255       |      150.0 ms     |   1
      D     |      255       |      200.0 ms     |   1

================================================================================
```

## Diagnostic Value

This logging will immediately show:

1. **Calibration Mode**: Whether global or per-channel mode was used
2. **LED Intensities**: Final LED intensity value for each channel (should show why only B is set)
3. **Integration Time**: Either single global value or per-channel values
4. **Scan Counts**: Number of scans per measurement
5. **⚠️ LED Balancing Validation**: Automatic warning if all LEDs have identical values in GLOBAL mode (indicates Step 4 failure)

## Expected Issues to Diagnose

Based on user report: "only channel B gets set"

The new logging will reveal:
- Whether `state.leds_calibrated` has zeros for A/C/D channels
- Whether the issue is in Step 4 (LED calibration) or Step 6 (final application)
- If per-channel mode is being used unexpectedly (all LEDs would be 255)
- **NEW:** If all LEDs have the same value in GLOBAL mode → Step 4 LED balancing completely failed

## Testing

To verify this logging:
1. Run full calibration via main app
2. Check console/log output after "Step 6" completes
3. Look for the new "📊 STEP 6 COMPLETE" banner with the parameter table

## Next Steps

Once the logging shows the actual values:
- If LEDs are 0 for A/C/D → Problem is in Step 4 (LED optimization/binary search)
- If LEDs are set but not applied → Problem is in hardware communication layer
- If per-channel mode with all 255 → Mode selection issue in device config

This targeted logging will pinpoint exactly where the calibration goes wrong without needing to instrument Step 4 further.
