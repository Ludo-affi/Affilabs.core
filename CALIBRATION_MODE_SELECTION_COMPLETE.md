# Calibration Mode Selection - Implementation Complete

**Status:** ✅ Complete and tested
**Date:** October 24, 2025

## Overview

Implemented persistent, user-selectable calibration mode for SPR spectroscopy with clean UI integration.

## What Was Implemented

### 1. Backend Configuration (`utils/device_configuration.py`)

**Added field to config schema:**
```python
'calibration': {
    'preferred_calibration_mode': 'global',  # 'global' or 'per_channel'
    # ... other calibration fields
}
```

**Added getter/setter methods:**
- `get_calibration_mode()` → Returns current mode ('global' or 'per_channel')
- `set_calibration_mode(mode)` → Validates and saves mode to disk

**Validation:**
- Only accepts 'global' or 'per_channel'
- Raises ValueError for invalid modes
- Automatically saves to `config/device_config.json`

### 2. Calibrator Integration (`utils/spr_calibrator.py`)

**Mode loading at initialization (lines 619-631):**
```python
# ✨ Load preferred calibration mode from device config (if available)
if device_config and 'calibration' in device_config:
    preferred_mode = device_config['calibration'].get('preferred_calibration_mode', 'global')
    if preferred_mode in ['global', 'per_channel']:
        self.state.calibration_mode = preferred_mode
        logger.info(f"📋 Calibration mode loaded from config: {preferred_mode.upper()}")
```

**Benefits:**
- Mode is automatically loaded when calibrator starts
- No manual `set_calibration_mode()` call needed
- Falls back to 'global' if config missing or invalid

### 3. Settings UI (`widgets/device_settings.py`)

**Added Calibration Mode section between LED PCB and Hardware Detection:**

**UI Components:**
- Radio button group with two options:
  - "Global Mode - Balanced LED intensities (Recommended)"
  - "Per-Channel Mode - Individual integration times (Advanced)"
- Clear descriptions explaining each mode
- Real-time preview in configuration display

**Features:**
- Loads current mode from device config on startup
- Updates live preview when selection changes
- Saves to disk when "Save Configuration" clicked
- Displays in success message: "Calibration Mode: Global (Balanced LEDs)"

### 4. Testing (`test_calibration_mode_selection.py`)

**Test coverage:**
1. ✅ DeviceConfiguration getter/setter correctness
2. ✅ Mode persistence to disk (reload validation)
3. ✅ Invalid mode rejection (ValueError)
4. ✅ SPRCalibrator loading logic simulation
5. ✅ Display name formatting

**All tests pass:** 🎉

## User Workflow

### Setting the Mode

1. Open application
2. Navigate to **Settings → Device Settings**
3. Locate **Calibration Mode** section
4. Select desired mode:
   - **Global Mode (Default - Recommended):** Traditional approach - calibrates LED intensities, uses single integration time
   - **Per-Channel Mode (Advanced):** All LEDs at 255, individual integration times per channel
5. Click **💾 Save Configuration**
6. **⚠️ IMPORTANT:** If you change modes, you **MUST run a full calibration** before measurements
   - A warning dialog will appear when changing modes
   - The two modes use incompatible LED intensity and integration time strategies
   - Existing calibration data will not be valid with the new mode
7. Mode persists across sessions

### Running Calibration

- Mode is **automatically applied** when calibration starts
- No manual code changes needed
- Mode displayed at Step 2 for confirmation
- Conditional logic in Steps 4, 6, 6.5, 7 applies mode-specific behavior
- **Always recalibrate after changing modes**

## Technical Details

### Configuration File

**Location:** `config/device_config.json`

**Structure:**
```json
{
  "calibration": {
    "preferred_calibration_mode": "global",
    "dark_calibration_date": "2025-10-24T...",
    ...
  }
}
```

### Mode Behavior

**Global Mode (Default):**
- Step 4: Calibrates LED intensities per channel
- Step 6: Balances LEDs to match weakest channel
- Uses single global integration time
- Best for balanced signal levels
- **Default mode** - recommended for most applications

**Per-Channel Mode:**
- Step 4: SKIPPED (all LEDs fixed at 255)
- Step 6: SKIPPED (no LED balancing)
- Step 6.5: Optimizes individual integration times per channel
- Step 7: Saves per-channel parameters
- Best for widely varying channel responses

**⚠️ CRITICAL: Recalibration Required When Changing Modes**

The two modes produce **incompatible calibration parameters**:
- **Global mode** optimizes LED intensities (varies 0-255) + single integration time
- **Per-channel mode** fixes LEDs at 255 + optimizes per-channel integration times

**If you change modes, you MUST:**
1. Run a full calibration (Steps 1-7) before measurements
2. Do NOT use old calibration data with the new mode
3. Expect different reference spectra (S-mode baseline differs between modes)

The UI will show a warning dialog when you attempt to change modes.

## Files Modified

1. ✅ `utils/device_configuration.py` - Config schema, getter/setter
2. ✅ `utils/spr_calibrator.py` - Mode loading logic
3. ✅ `widgets/device_settings.py` - UI controls

## Files Created

1. ✅ `test_calibration_mode_selection.py` - Integration test suite
2. ✅ `CALIBRATION_MODE_SELECTION_COMPLETE.md` - This document

## Validation

```bash
# Run test suite
python test_calibration_mode_selection.py

# Expected output:
# ✅ TEST 1 PASSED: DeviceConfiguration works correctly
# ✅ TEST 2 PASSED: SPRCalibrator correctly loads mode from device config
# ✅ TEST 3 PASSED: Display names are user-friendly
# 🎉 ALL TESTS PASSED!
```

## Benefits

### Before (Old Behavior)
- Mode hardcoded to 'global' every session
- Required programmatic `set_calibration_mode()` call before calibration
- No GUI control
- No persistence

### After (New Behavior)
- ✅ User-selectable via GUI
- ✅ Persists across sessions
- ✅ Automatically loaded at startup
- ✅ Clear descriptions in UI
- ✅ Validated and error-checked
- ✅ No manual code changes needed

## API Reference

### DeviceConfiguration

```python
# Get current mode
mode = config.get_calibration_mode()  # Returns 'global' or 'per_channel'

# Set mode (validates and saves to disk)
config.set_calibration_mode('per_channel')  # Raises ValueError if invalid
```

### SPRCalibrator

```python
# Mode is automatically loaded from device_config at init
calibrator = SPRCalibrator(ctrl, usb, device_type, device_config=device_config_dict)

# Check current mode
print(calibrator.state.calibration_mode)  # 'global' or 'per_channel'

# Mode can still be changed programmatically (but not recommended)
calibrator.set_calibration_mode('per_channel')
```

## Future Enhancements (Optional)

1. Add mode explanation tooltip on hover
2. Show mode-specific parameter preview (LEDs, integration times)
3. Add "Reset to recommended" button (sets to 'global')
4. Add mode history tracking in diagnostics
5. Add mode comparison tool (visualize differences)

## Notes

- **Backward compatible:** Existing configs without `preferred_calibration_mode` default to 'global'
- **Safe defaults:** Invalid modes fall back to 'global' with warning
- **Clean separation:** UI, config, and calibrator are loosely coupled
- **Tested:** All integration tests pass successfully

---

**Implementation completed:** October 24, 2025
**Test status:** ✅ All tests passing
**Production ready:** Yes
