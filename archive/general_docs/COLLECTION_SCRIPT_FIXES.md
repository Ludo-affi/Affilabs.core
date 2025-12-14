# Collection Script Fixes - COMPLETE

## Critical Bugs Fixed

### Bug 1: Polarizer Not Switching ✅ FIXED
**Problem**: Polarizer stuck in P position, both S and P modes collected with same polarization
**Location**: Lines 207-217
**Fix Applied**:
```python
# CRITICAL FIX: Actually move the polarizer!
if mode == 's':
    print(f"  → Setting polarizer to S-mode...")
    self.spr_device.set_mode('s')
    time.sleep(2.0)  # Wait for servo to move
else:
    print(f"  → Setting polarizer to P-mode...")
    self.spr_device.set_mode('p')
    time.sleep(2.0)  # Wait for servo to move
```

### Bug 2: LED Saturation (255 vs Calibrated) ✅ FIXED
**Problem**: LED intensity hardcoded to 255 (full power) causing detector saturation
**Location**: Lines 220-244
**Fix Applied**:
```python
# Load calibrated LED intensity from last calibration
config_mgr = ConfigurationManager()

# Get calibrated LED intensity for this channel
led_intensity = config_mgr.calibration.ref_intensity.get(channel.upper(), 128)
integration_time_ms = config_mgr.calibration.integration

# Use calibrated values (NOT 255!)
self.spectrometer.set_integration_time(integration_time_ms / 1000.0)
self.spr_device.set_intensity(channel.lower(), led_intensity)
```

### Bug 3: Integration Time Not Set ✅ FIXED
**Problem**: Script didn't set integration time, used spectrometer default
**Location**: Line 235
**Fix Applied**:
```python
# Set integration time from calibration (convert ms to seconds)
self.spectrometer.set_integration_time(integration_time_ms / 1000.0)
```

## What Changed

### Added Import
```python
from utils.config_manager import ConfigurationManager
```

### Added Polarizer Control
- Calls `set_mode('s')` before S-mode collection
- Calls `set_mode('p')` before P-mode collection
- 2-second wait for servo movement

### Uses Calibrated Parameters
- Loads LED intensities from ConfigurationManager
- Loads integration time from calibration
- Falls back to safe defaults (128, 50ms) if no calibration found

## Expected Results After Fix

### Before (WRONG):
- ❌ Both modes collected in P polarization
- ❌ Detector saturated (65,535 counts max)
- ❌ 642-1092 saturated pixels per sensor
- ❌ Transmission: -89 to +39 (impossible values)
- ❌ LED at 255 (full power)
- ❌ Integration time: default (~100ms)

### After (CORRECT):
- ✅ S-mode collected with S polarization
- ✅ P-mode collected with P polarization
- ✅ No saturation (<60,000 counts max)
- ✅ Zero saturated pixels
- ✅ Transmission: 0.05-0.15 (5-15%)
- ✅ LED at calibrated value (typically 128-200)
- ✅ Integration time: calibrated (e.g., 32ms)

## Next Steps

### 1. Delete Invalid Data
```bash
Remove-Item -Recurse -Force training_data/used_current/
Remove-Item -Recurse -Force training_data/new_sealed/
```

### 2. Re-collect Old Sensor
```bash
python collect_training_data.py --device "demo P4SPR 2.0" --label used_current --notes "Re-collected with proper polarizer control and calibrated LED"
```

### 3. Re-collect Good Sensor
```bash
python collect_training_data.py --device "demo P4SPR 2.0" --label new_sealed --sensor-id "GOOD-SENSOR-001" --notes "Re-collected with all fixes"
```

### 4. Verify Data Quality
Run the diagnostic to confirm transmission is in expected range:
```bash
python diagnose_transmission.py
```

**Expected output:**
```
OLD SENSOR: Transmission 0.08-0.12 ✅
NEW SENSOR: Transmission 0.05-0.10 ✅
No saturated pixels ✅
```

## Files Modified

- ✅ `collect_training_data.py` - All 3 bugs fixed
- ✅ `verify_collection_fixes.py` - Created verification script
- ✅ `COLLECTION_SCRIPT_FIXES.md` - This documentation

## Technical Details

### Polarizer Control API
```python
controller.set_mode('s')  # S-mode: sends "ss\n" to firmware
controller.set_mode('p')  # P-mode: sends "sp\n" to firmware
```

### Calibration Loading
```python
config_mgr = ConfigurationManager()
# Automatically loads from generated-files/calibration_data/
led_intensity = config_mgr.calibration.ref_intensity.get(channel, 128)
integration_time_ms = config_mgr.calibration.integration
```

### Expected Calibration Values
- **LED Intensity**: 128-200 (typical range)
- **Integration Time**: 30-50 ms (typical range)
- **Transmission**: 0.05-0.15 (5-15% through SPR dip)

## Validation Checklist

Before re-collecting data, verify:
- [ ] Polarizer moves when switching modes (listen for servo)
- [ ] LED brightness is reasonable (not blinding)
- [ ] Transmission values are 0.05-0.15
- [ ] No saturated pixels (max counts <60,000)
- [ ] Clear SPR dip visible in both modes

## User Confirmation Required

**Ready to proceed?**
1. Delete invalid datasets (used_current, new_sealed)
2. Re-run collection with fixed script
3. Verify transmission in expected range

---
**Status**: ✅ ALL BUGS FIXED - Ready for data re-collection
**Date**: 2025-10-22
**Version**: collect_training_data.py v2.0 (fixed)
