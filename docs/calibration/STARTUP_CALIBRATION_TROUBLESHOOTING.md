# Startup Calibration Troubleshooting Guide

## Overview

This document provides detailed troubleshooting for common startup calibration failures in Affilabs.core. The calibration process consists of 6 main steps, and errors can occur at multiple points.

---

## Calibration Process Overview

### The 6 Calibration Steps

1. **Hardware Validation & LED Preparation** (0-5%)
   - Validates controller connection
   - Turns off all LEDs
   - Enables batch LED mode

2. **Wavelength Calibration** (5-17%)
   - Reads wavelength data from detector EEPROM
   - Defines ROI (Region of Interest: 560-720nm)

3. **LED Brightness Measurement & Model Validation** (17-30%)
   - Measures LED brightness for each channel
   - Validates or loads LED calibration model
   - May rebuild model if forced or missing

4. **S-Mode LED Convergence** (30-50%)
   - Converges LEDs to optimal brightness in S-polarization
   - Captures reference spectrum

5. **P-Mode LED Convergence** (50-85%)
   - Converges LEDs to optimal brightness in P-polarization
   - Captures reference and dark spectra

6. **QC Validation & Result Packaging** (85-100%)
   - Validates calibration quality
   - Packages results for system use

---

## Common Error Points & Solutions

### 1. Hardware Connection Errors

**Symptom:** Calibration fails immediately or shows "Hardware not found"

**Possible Causes:**
- USB cable disconnected or loose
- Detector not powered on
- Driver issues
- USB port malfunction
- Controller communication failure

**Solutions:**
1. Check all USB connections (detector and controller)
2. Verify power supply to detector
3. Try different USB port (USB 3.0 preferred)
4. Check Windows Device Manager for:
   - Ocean Optics USB4000 (or your detector model)
   - FTDI USB Serial Port (controller)
5. Restart software and try again
6. If persistent, power cycle the hardware

**Related Error Messages:**
- "Failed to read wavelength data from detector"
- "Cannot communicate with controller"
- "USB timeout"

---

### 2. LED Control Failures

**Symptom:** Calibration fails during Step 1 with LED-related errors

**Possible Causes:**
- Controller firmware issue
- LED driver malfunction
- Batch LED mode not supported
- Channel selection error

**Solutions:**
1. Power cycle the controller
2. Check controller firmware version (should support batch LEDs)
3. Verify all LED channels are functioning:
   - Go to Settings tab after reboot
   - Manually test each LED channel
4. If one channel fails, note which one and contact support

**Related Error Messages:**
- "LED turn-off failed"
- "Failed to enable batch LED mode"
- "Channel X not responding"

---

### 3. Wavelength Calibration Errors

**Symptom:** Calibration fails at Step 2 (17% progress)

**Possible Causes:**
- Detector EEPROM corruption
- Wavelength calibration data missing
- Communication timeout during EEPROM read

**Solutions:**
1. Power cycle the detector
2. Try calibration again (EEPROM read can be temperamental)
3. If repeated failures:
   - Detector may need factory recalibration
   - Contact support with detector serial number

**Related Error Messages:**
- "Failed to read wavelength data from detector"
- "Wavelength data is empty or invalid"
- "ROI definition failed"

---

### 4. LED Model Missing or Invalid

**Symptom:** Calibration takes longer than expected or fails at Step 3

**Possible Causes:**
- First-time calibration (no model exists)
- Model file corrupted
- Model doesn't match current detector
- Force OEM retrain flag set

**Solutions:**
1. **Normal behavior:** First calibration takes 3-5 minutes (building model)
2. Subsequent calibrations should take 1-2 minutes (using model)
3. If model corruption suspected:
   - Delete model file (located in calibration data folder)
   - Run full OEM calibration to rebuild
4. Model is detector-specific - swapping detectors requires new model

**Related Error Messages:**
- "LED calibration model not found - building new model"
- "Model validation failed"
- "Rebuilding optical model (OEM mode)"

**Note:** This is often NOT an error - just a longer first-time calibration

---

### 5. S-Mode Convergence Failures

**Symptom:** Calibration fails at Step 4 (30-50% progress)

**Possible Causes:**
- LED too weak (low optical power)
- LED too bright (saturation)
- Polarizer misalignment or failure
- Integration time out of range
- Contaminated flow cell
- Air bubbles in optical path

**Solutions:**

**If "Signal too weak" error:**
1. Check LED brightness manually in Settings tab
2. Verify polarizer is in correct position (S-mode)
3. Clean flow cell windows
4. Check for air bubbles - prime flow system
5. Increase integration time range in settings

**If "Signal too bright / saturated" error:**
1. Reduce LED brightness manually and retry
2. Check for contamination on detector window
3. Verify neutral density filter if installed

**If "Convergence timeout" error:**
1. LED may be failing - check with manual brightness test
2. Detector may need cleaning
3. Optical alignment may be off - contact support

**Related Error Messages:**
- "S-mode convergence failed: Channels below target"
- "Maximum signal too low (X% of target)"
- "LED intensity at maximum but signal still weak"
- "Convergence timeout after 12 iterations"
- "Check polarizer alignment - expected S-mode signal"

**Critical:** If S-mode fails repeatedly with "polarizer alignment" message, the polarizer motor may be malfunctioning

---

### 6. P-Mode Convergence Failures

**Symptom:** Calibration fails at Step 5 (50-85% progress)

**Possible Causes:**
- Same as S-mode issues
- P-polarizer position incorrect
- SPR sensitivity too high (P-mode typically stronger signal)

**Solutions:**
1. Same solutions as S-mode (see above)
2. P-mode should give stronger signal than S-mode
3. If P-mode succeeds but S-mode failed:
   - Polarizer likely OK
   - S-mode LED may be weak
4. If both modes fail:
   - Check optical path cleanliness
   - Verify flow cell is properly seated

**Related Error Messages:**
- "P-mode convergence failed: Channels below target"
- "Polarizer position error"
- "Dark spectrum acquisition failed"

---

### 7. Pump Priming Errors (During Calibration)

**Symptom:** Calibration fails with pump-related messages during Step 3-4

**Possible Causes:**
- Pump not initialized
- Valve position incorrect
- Pump communication failure
- Flow path blockage
- Air lock in pump

**Solutions:**
1. Check pump connections in Device Status tab
2. Ensure pumps are connected and recognized
3. If pump timeout:
   - Power cycle pump controller
   - Check USB connection to pump
4. If valve errors:
   - Valves may be stuck
   - Listen for valve click sounds
   - Manual valve test in Flow tab
5. Prime pumps manually before calibration:
   - Go to Flow tab
   - Run manual prime cycle
   - Ensure smooth flow

**Related Error Messages:**
- "Pump initialization failed"
- "Pump timeout waiting for ready"
- "Valve operation failed"
- "Pump priming cycle X/6 failed"

**Note:** Pump priming runs in parallel with optical calibration (cycles 4-6) to save time

---

### 8. QC Validation Failures

**Symptom:** Calibration completes but QC report shows warnings/errors

**Possible Causes:**
- Calibration marginally successful but below quality threshold
- One or more channels significantly weaker than others
- Dark spectrum issues
- Reference spectrum quality concerns

**Solutions:**

**Yellow Warnings (Acceptable):**
- "Partial convergence" - calibration usable but not perfect
- "Channel variation" - one channel weaker but still functional
- **Action:** Can proceed with "Continue Anyway" if running experiments

**Red Errors (Problematic):**
- "Critical failure" - calibration unusable
- "Signal saturation" - detector overloaded
- "No signal detected" - optical path blocked
- **Action:** Must retry calibration or fix underlying issue

**QC Report Interpretation:**
1. **All Green:** Perfect calibration - proceed
2. **Yellow Warnings:** Acceptable - proceed with caution
3. **Red Errors:** Do not proceed - troubleshoot first

---

## Retry Strategies

### When to Click "Retry"

- Hardware connection glitch (one-time failure)
- USB timeout or communication error
- First attempt after power-on (detector warm-up)

### When to Click "Continue Anyway"

- QC shows yellow warnings only
- Time-sensitive experiment and calibration is "good enough"
- You understand the limitations

### When to Cancel and Investigate

- Repeated failures (3+ retries)
- Red errors in QC report
- Hardware issues suspected
- Pump or valve malfunctions

---

## Advanced Diagnostics

### Check Integration Time Range

If convergence keeps timing out:
1. Go to Settings tab
2. Check detector integration time limits
3. Typical range: 10ms - 100ms
4. If detector supports wider range, adjust in config

### Check LED Brightness Manually

Test each channel individually:
1. Go to Settings > Display Controls
2. For each channel (A, B, C, D):
   - Set LED to 128
   - Set integration to 30ms
   - Check signal level
3. Compare channels - should be within 2x of each other
4. If one channel much weaker: LED failing

### Check Optical Path

1. Visual inspection:
   - Flow cell windows clean?
   - No visible contamination?
   - Liquid present in flow cell?
2. Run water flush if contaminated
3. Check for air bubbles (cloudy appearance)

### Check Polarizer Movement

1. During calibration, listen for polarizer motor
2. Should hear distinct motor sound when switching S↔P
3. If silent: polarizer motor may be disconnected
4. If clicking but cal fails: position sensor may be off

---

## Error Message Quick Reference

| Error Message | Step | Likely Cause | Quick Fix |
|---------------|------|--------------|-----------|
| "Hardware not found" | Pre-cal | USB connection | Check cables |
| "Failed to read wavelength" | Step 2 | EEPROM read | Power cycle detector |
| "LED turn-off failed" | Step 1 | Controller comm | Power cycle controller |
| "Model not found" | Step 3 | First calibration | Wait (3-5 min normal) |
| "S-mode convergence failed" | Step 4 | Weak LED or dirty optics | Clean flow cell, check LEDs |
| "P-mode convergence failed" | Step 5 | Same as S-mode | Same as S-mode |
| "Pump timeout" | Step 3-4 | Pump connection | Check pump USB |
| "Valve operation failed" | Step 3-4 | Stuck valve | Manual valve test |
| "Signal too low" | Step 4-5 | Weak LED or blocked path | Clean optics, check LED |
| "Signal saturated" | Step 4-5 | Too bright or dirty window | Reduce LED, clean |
| "Convergence timeout" | Step 4-5 | LED failing | Test LED manually |
| "Polarizer alignment" | Step 4-5 | Polarizer position error | Check polarizer motor |

---

## Prevention Tips

### Before Starting Calibration

1. ✅ Allow 10-15 minutes warmup time after power-on
2. ✅ Ensure flow cell is clean and filled with reference buffer
3. ✅ Prime pumps if using fluidics (avoids bubbles during cal)
4. ✅ Check all USB connections are secure
5. ✅ Verify detector shows up in Device Status tab
6. ✅ Close other applications using USB bandwidth (cameras, etc.)

### After Successful Calibration

1. ✅ Note the QC results for baseline comparison
2. ✅ If QC shows warnings, schedule maintenance
3. ✅ Save QC report for troubleshooting history
4. ✅ Recalibrate if detector is moved or flow cell replaced

---

## When to Contact Support

Contact technical support if:
- ❌ Calibration fails 3+ times with same error
- ❌ Hardware connection issues persist after troubleshooting
- ❌ QC always shows red errors even after retry
- ❌ LED channels fail manual brightness test
- ❌ Polarizer motor not functioning
- ❌ Pump communication repeatedly fails
- ❌ Detector EEPROM read errors persist

**Provide to Support:**
1. Full error message text
2. Calibration step where failure occurred (Step 1-6, % progress)
3. QC report screenshot (if calibration completed)
4. Detector serial number
5. Number of retry attempts
6. Any recent hardware changes

---

*Last Updated: February 3, 2026*
*Document Version: 1.0*
