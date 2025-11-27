# Calibration Failure Diagnostic Guide

## Problem
Calibration completes all steps but is marked as unsuccessful with error:
```
RuntimeError: Calibration failed: Calibration completed but marked as unsuccessful
```

## Root Cause
The calibration function `perform_alternative_calibration()` returns `success=False` when channels are added to `ch_error_list` during P-mode verification.

## Diagnosis Added

### Debug Output Added to Code
Enhanced `src/utils/led_calibration.py` with comprehensive debug logging:

1. **After verify_calibration() (line ~3164)**:
   - Shows which channels failed verification
   - Lists the error count
   - Logs specific error reasons

2. **Before setting success flag (line ~3231)**:
   - Shows ch_error_list contents
   - Shows error count
   - Shows final success determination

### Channel Error Conditions

Channels are added to `ch_error_list` in `verify_calibration()` for these reasons:

1. **Failed to read intensity** (line 1623)
   - Hardware communication error during P-mode measurement

2. **Flat transmission spectrum** (line 1662)
   - Indicates saturation, dark signal, or no SPR coupling
   - Range check: transmission variance too low
   - **BLOCKING ISSUE** - calibration cannot proceed

3. **S/P orientation inverted** (line 1671)
   - Transmission peak is HIGHER than sides (should be lower for SPR dip)
   - Indicates polarizer servo positions are swapped
   - **BLOCKING ISSUE** - requires OEM-level configuration fix
   - Auto-corrects if 3+ channels affected (swaps positions and retries)

4. **Saturation after LED reduction** (line 1699)
   - Channel still saturated even after automatically reducing LED intensity
   - Hardware issue - detector saturating even at low LED

5. **Failed to read after intensity reduction** (line 1713)
   - Hardware communication error after attempting to fix saturation

## How to Diagnose

### Run the Test Script
```powershell
cd C:\Users\ludol\ezControl-AI\src
python test_calibration_debug.py
```

This will:
1. Connect to hardware
2. Run full calibration with enhanced debug output
3. Show detailed results including which channels failed and why

### What to Look For in Output

1. **Look for ❌ and ⚠️ symbols** in the log output
2. **Check for these specific errors**:

   **Flat Spectrum Error**:
   ```
   ❌ CALIBRATION FAILED - Ch X: Flat transmission spectrum!
      Range: X.XX% - possible saturation or dark signal
   ```
   → **Cause**: Detector saturated or not receiving proper signal
   → **Fix**: Check LED intensities, integration times, connections

   **Inverted Orientation Error**:
   ```
   ❌ CALIBRATION FAILED - Ch X: S/P ORIENTATION INVERTED!
      Transmission peak at XXX.Xnm is HIGHER (XX.X%) than sides
      ⚠️ CRITICAL: S and P polarizer positions are SWAPPED
   ```
   → **Cause**: Polarizer servo positions swapped in device_config.json
   → **Fix**: Auto-corrects if 3+ channels affected; otherwise manual config edit needed

   **Saturation Error**:
   ```
   ❌ Ch X still saturated after LED reduction: XXXX counts (LED=XX)
   ```
   → **Cause**: Signal too strong even at minimum LED
   → **Fix**: Check integration time settings, detector gain

3. **Check the final summary**:
   ```
   🔥 verify_calibration() RETURNED:
      ch_error_list = ['a', 'c']  ← These channels failed
      spr_fwhm = {...}
      polarizer_swap_detected = False/True
   ```

## Common Issues and Solutions

### Issue 1: All Channels Show "Flat Spectrum"
**Cause**: Integration time too high or LEDs too bright
**Solution**:
- Check device_config.json integration time settings
- Verify LED intensities are not all at maximum already
- Check if detector is saturating during S-mode reference acquisition

### Issue 2: Multiple Channels Show "Inverted Orientation"
**Cause**: Polarizer positions swapped in device_config.json
**Solution**:
- If 3+ channels: Auto-correction will trigger (positions swapped and retry)
- If 1-2 channels: Manual review of device_config.json servo positions needed

### Issue 3: Single Channel Fails
**Cause**: Hardware issue with specific channel (LED, fiber, detector pixel)
**Solution**:
- Check fiber connection for that channel
- Verify LED is working (test with manual control)
- Check for prism contact on that channel

## Next Steps

1. **Run the debug script** to capture detailed error information
2. **Review the error messages** to identify specific failure reasons
3. **Apply the appropriate fix** based on error type
4. **Re-run calibration** after fixes

## Code Changes Made

Files modified:
- `src/utils/led_calibration.py` - Added debug output at lines ~3164 and ~3231
- `src/test_calibration_debug.py` - Created new diagnostic test script

The debug output will help identify exactly which channels are failing and why, making it much easier to diagnose and fix calibration issues.
