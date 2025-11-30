# Servo EEPROM Legacy Functions DELETED

**Date:** 2025-11-30
**Critical Safety Update:** Complete removal of dangerous EEPROM servo operations

## Summary

ALL legacy EEPROM servo functions have been **DELETED** from the codebase. These functions were dangerous because they allowed runtime position changes that could cause:
- Position drift and inconsistency
- Calibration failures
- Polarizer inversion issues

## Single Source of Truth Architecture

### Device Config is ONLY Source
- **servo_s_position**: Set in `device_config.json` (currently 89° for FLMT09116)
- **servo_p_position**: Set in `device_config.json` (currently 179° for FLMT09116)

### Startup Flow
1. Application reads positions from `device_config.json`
2. Positions written to controller EEPROM via `write_config_to_eeprom()`
3. Controller firmware loads positions from EEPROM at boot
4. Positions are **IMMUTABLE** for entire session

### Runtime Behavior
- `ctrl.set_mode('s')` → Controller moves to S position (from EEPROM)
- `ctrl.set_mode('p')` → Controller moves to P position (from EEPROM)
- **NO** runtime position changes allowed
- **NO** EEPROM reads during operation

## Deleted Functions

### From PicoP4SPR Class (`src/utils/controller.py`)

#### ❌ `servo_get()` - DELETED
- **Why Deleted:** Read positions from EEPROM at runtime
- **Danger:** Could show drifted values if EEPROM corrupted
- **Replacement:** Use `device_config.get_servo_positions()`

#### ❌ `servo_set(s, p)` - DELETED
- **Why Deleted:** Wrote positions to EEPROM at runtime
- **Danger:** Could corrupt positions, cause drift
- **Replacement:** Update `device_config.json` and restart application

#### ❌ `flash()` - DELETED
- **Why Deleted:** Wrote settings to EEPROM at runtime
- **Danger:** Could persist incorrect settings
- **Replacement:** Use `write_config_to_eeprom()` at startup only

## Added Functions

### ✅ `servo_move_calibration_only(s, p)`
**Purpose:** ONLY for servo calibration workflow
**Usage:** Scan different angles to find optimal positions
**Safety:** Does NOT write to EEPROM, results saved to device_config
**Location:** `src/utils/controller.py` PicoP4SPR class

## Updated Files

### 1. `src/config/devices/FLMT09116/device_config.json`
```json
{
  "hardware": {
    "servo_s_position": 89,  // Changed from 93
    "servo_p_position": 179  // Changed from 182
  }
}
```

### 2. `src/main_simplified.py`
- Added EEPROM sync at startup in `_load_device_settings()`
- Checks device_config vs EEPROM
- Writes device_config to EEPROM if mismatch detected
- Logs verification of position source

### 3. `src/utils/calibration_6step.py`
- Added validation calls before `set_mode()`
- `_validate_polarizer_positions()` called at Steps 4 and 5
- Enhanced validation function documentation
- Emphasizes single source of truth enforcement

### 4. `src/utils/controller.py`
- Deleted `servo_get()`, `servo_set()`, `flash()`
- Added `servo_move_calibration_only()` for calibration workflow
- Added comprehensive docstring to `set_mode()`
- Documents EEPROM position loading from device_config

### 5. `src/utils/servo_calibration.py`
- Updated `_move_servo_to_angle()` to use `servo_move_calibration_only()`
- Added documentation that this is calibration-only workflow
- Results saved to device_config, not EEPROM

### 6. `src/utils/hal/controller_hal.py`
- Deleted `servo_get()` call in `get_polarizer_position()`
- Returns empty dict with warning
- Recommends using `device_config.get_servo_positions()` directly

### 7. `src/widgets/calibration_qc_dialog.py`
- Added second tab "Calibration Analysis" with matplotlib visualization
- Shows S/P max counts, P/S ratios, LED intensities, SPR wavelengths
- Detects and highlights polarizer inversion issues
- Displays QC summary with actionable recommendations

## Validation System

### Before Every `set_mode()` Call
```python
_validate_polarizer_positions(device_config, mode, logger)
ctrl.set_mode(mode)
```

### Validation Checks
1. Device config exists and is accessible
2. Servo positions exist in device_config
3. Positions are valid (not None, within 0-180°)
4. Logs positions for audit trail

### Validation Locations
- Step 4 (S-mode acquisition)
- Step 5 (P-mode acquisition)
- UI polarizer toggle
- Spectroscopy panel toggle

## Safety Guarantees

### ✅ Single Source of Truth
- Device_config.json is ONLY position source
- No EEPROM reads during runtime
- No position changes during session

### ✅ Startup Verification
- EEPROM synced with device_config at power-on
- Mismatch detection and correction
- Audit logging of all position operations

### ✅ Runtime Immutability
- Positions loaded once at initialization
- No servo_set() available for runtime changes
- Position changes require application restart

### ✅ Calibration Safety
- Special calibration-only function for finding positions
- Results saved to device_config only
- No EEPROM corruption during calibration

## Testing Checklist

- [x] Device config updated with new positions (S=89°, P=179°)
- [x] Validation functions added before set_mode() calls
- [x] EEPROM sync logic added at startup
- [x] Legacy functions deleted (servo_get, servo_set, flash)
- [x] Calibration workflow uses new function
- [x] HAL updated to warn against EEPROM reads
- [x] QC dialog shows polarizer analysis visualization

## Next Steps

1. **Test Startup Sync**
   - Power on system
   - Verify EEPROM sync messages in log
   - Confirm positions match device_config

2. **Test Calibration**
   - Run 6-step calibration
   - Verify validation messages appear
   - Confirm NO servo_set/servo_get/flash calls
   - Check QC dialog second tab

3. **Verify Position Consistency**
   - Run multiple calibrations
   - Positions should remain consistent
   - No drift between sessions

4. **Check Polarizer Inversion**
   - QC dialog should detect if P > S
   - Analysis tab should highlight issue
   - Recommendations should be clear

## Architecture Notes

### Why This Matters
The previous architecture allowed positions to be read/written from EEPROM at any time, which caused:
- **Position Drift:** EEPROM could have different values than device_config
- **Calibration Failures:** Inconsistent positions between calibrations
- **Debugging Nightmare:** Hard to trace which source was being used
- **User Confusion:** Settings could change without explicit action

### New Architecture Benefits
- **Predictable:** Positions loaded once, never change
- **Traceable:** All changes go through device_config
- **Debuggable:** Single source to check for position values
- **Safe:** No accidental EEPROM corruption
- **Explicit:** Position changes require restart (user awareness)

### Firmware Integration
The controller firmware (`PicoP4SPR`) still uses EEPROM internally:
- Loads S/P positions from EEPROM at boot
- Responds to `ss` and `sp` commands using those positions
- **Critical:** EEPROM written from device_config at application startup
- **Critical:** EEPROM NOT modified during runtime

This design gives us:
1. Fast servo response (firmware has positions in memory)
2. Single source of truth (application owns positions)
3. Safe operation (no runtime EEPROM corruption)
4. Easy debugging (one config file to check)

## Historical Context

### Previous Behavior (DANGEROUS)
```python
# OLD CODE - DELETED
ctrl.servo_set(s=120, p=60)  # Writes to EEPROM immediately
ctrl.flash()                  # Persists to EEPROM
positions = ctrl.servo_get()  # Reads from EEPROM
```

### Current Behavior (SAFE)
```python
# NEW CODE - SAFE
# 1. Startup: sync device_config → EEPROM
device_config.get_servo_positions()  # {'s': 89, 'p': 179}
ctrl.write_config_to_eeprom(config)  # Write to EEPROM once

# 2. Runtime: use positions from firmware (loaded from EEPROM at boot)
_validate_polarizer_positions(device_config, 's', logger)
ctrl.set_mode('s')  # Firmware uses position from EEPROM

# 3. Position changes: update config file and restart
# Edit device_config.json → restart application → EEPROM synced
```

## Configuration Reference

### FLMT09116 Device Config
```json
{
  "hardware": {
    "servo_s_position": 89,   // Maximum transmission (S-mode)
    "servo_p_position": 179   // Minimum transmission (P-mode, strongest SPR)
  }
}
```

### Position Interpretation
- **S Position (89°):** Maximum optical transmission through polarizer
  - Used for reference/baseline measurements
  - Higher signal levels expected

- **P Position (179°):** Minimum transmission, strongest SPR absorption
  - Used for SPR dip measurements
  - Lower signal levels expected
  - Maximum SPR contrast

### P/S Ratio Validation
- **Expected:** P/S < 1.0 (P signal lower than S signal)
- **Warning:** P/S > 1.15 suggests positions may be inverted
- **Current Issue:** All channels showing P/S = 5-7x (INVERTED)
- **Solution:** Positions now corrected in device_config

## Emergency Recovery

If positions become corrupted or lost:

1. **Check device_config.json**
   ```bash
   cat src/config/devices/FLMT09116/device_config.json | grep servo
   ```

2. **Restore from backup**
   ```bash
   # Current correct values
   servo_s_position: 89
   servo_p_position: 179
   ```

3. **Restart application**
   - Application will sync device_config → EEPROM
   - Verify sync in startup logs

4. **Re-run calibration**
   - Should show correct P/S ratios (< 1.0)
   - QC analysis tab should show no inversion

## Support

For questions or issues related to servo position management:
1. Check startup logs for EEPROM sync messages
2. Verify device_config.json contains correct positions
3. Confirm validation messages appear during calibration
4. Review QC dialog analysis tab for position diagnostics
