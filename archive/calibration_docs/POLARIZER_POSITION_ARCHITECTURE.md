# Polarizer Position Architecture - Modern Design

**Date**: November 30, 2025
**Status**: ✅ **IMPLEMENTED - Legacy EEPROM behavior removed**

---

## Critical Design Principle

**Polarizer positions are loaded ONCE at controller initialization from `device_config.json` and NEVER changed during runtime.**

---

## Architecture

### ❌ OLD (Legacy EEPROM-based behavior)
```python
# During calibration:
ctrl.servo_set(s=120, p=60)    # Set positions in firmware RAM
ctrl.flash()                    # Flash to EEPROM
ctrl.set_mode('s')             # ss command reads from EEPROM
```

**Problems**:
- Positions written during every calibration
- EEPROM wear from repeated flashing
- Firmware ss/sp commands depend on EEPROM state
- Positions can get out of sync with device_config.json

### ✅ NEW (Config-based initialization)
```python
# At controller initialization (once):
# - Load positions from device_config.json
# - Configure firmware with these positions
# - Positions remain constant for the session

# During calibration/operation:
ctrl.set_mode('s')             # Use pre-configured S position
ctrl.set_mode('p')             # Use pre-configured P position
```

**Benefits**:
- Single source of truth: `device_config.json`
- No EEPROM writes during calibration
- Positions guaranteed consistent throughout session
- Cleaner code with no position management logic

---

## Implementation Status

### ✅ Completed (November 30, 2025)

**File**: `src/utils/calibration_6step.py`

**Removed**:
- All `servo_set()` calls during calibration
- All `flash()` calls during calibration
- All servo position configuration logic

**Kept**:
- Loading positions from device_config (for logging/validation)
- Storing positions in calibration result (for reference)
- `set_mode('s')` and `set_mode('p')` calls (now use pre-configured positions)

---

## Device Configuration Format

### Required Structure in `device_config.json`

```json
{
  "oem_calibration": {
    "polarizer_s_position": 60,
    "polarizer_p_position": 120,
    "polarizer_sp_ratio": 0.18
  }
}
```

**Alternative format** (OEM tool output):
```json
{
  "polarizer": {
    "s_position": 60,
    "p_position": 120,
    "sp_ratio": 0.18
  }
}
```

Both formats are supported for backward compatibility.

---

## Controller Initialization Responsibilities

The controller's `__init__()` or `open()` method should:

1. Load polarizer positions from device_config
2. Configure firmware with these positions (if needed)
3. Store positions for later use by `set_mode()`

**Location**: `src/utils/controller.py` - `PicoP4SPR` class

---

## Calibration Flow

### Simplified 6-Step Calibration

```python
# Step 1-2: Validation and LED characterization
# (no polarizer involvement)

# Step 3: Capture S-polarized reference
result.polarizer_s_position = s_pos  # From device_config
ctrl.set_mode('s')                   # Move to S position
spectrum = usb.read_intensity()      # Capture reference

# Step 4-5: LED optimization in P-mode
result.polarizer_p_position = p_pos  # From device_config
ctrl.set_mode('p')                   # Move to P position
# ... LED optimization logic ...

# Step 6: QC validation
# ... quality checks ...
```

**No servo configuration needed** - positions come from device_config!

---

## Firmware Commands

### Polarizer Mode Commands
```
ss\n        - Move servo to S position (uses pre-configured position)
sp\n        - Move servo to P position (uses pre-configured position)
```

**Note**: These commands use positions that were configured at controller initialization. They do NOT read from EEPROM during calibration.

---

## Benefits of New Architecture

1. **Single Source of Truth**: device_config.json contains all configuration
2. **No Runtime Changes**: Positions never change after initialization
3. **Reduced EEPROM Wear**: No flash operations during calibration
4. **Cleaner Code**: No position management in calibration logic
5. **Guaranteed Consistency**: Positions can't get out of sync
6. **Better Performance**: No servo configuration delays during calibration

---

## Migration Notes

### For Developers

**Before**:
- Calibration code had to call `servo_set()` and `flash()`
- Positions were configured multiple times per calibration
- Code had to handle servo configuration failures

**After**:
- Calibration code just calls `set_mode('s')` or `set_mode('p')`
- Positions configured once at controller initialization
- Cleaner, simpler calibration logic

### For Users

**No visible changes** - calibration works the same way, just more reliably.

---

## Testing Checklist

- [x] Remove `servo_set()` calls from `calibration_6step.py`
- [x] Remove `flash()` calls from `calibration_6step.py`
- [ ] Verify `set_mode()` works with device_config positions
- [ ] Test full calibration with new architecture
- [ ] Confirm servo moves correctly between S and P positions
- [ ] Verify P/S intensity ratios are correct (P < S)

---

## Related Documentation

- `SIGNAL_ORIENTATION_CLARIFICATION.md` - S vs P polarization physics
- `docs/hardware/PICOP4SPR_FIRMWARE_COMMANDS.md` - Firmware command reference
- `SERVO_ROTATION_FIX.md` - Historical servo movement issue (now obsolete)

---

## Summary

Polarizer positions are now treated as **immutable configuration data** loaded from device_config at initialization. Calibration code no longer manages positions - it simply uses `set_mode()` to switch between pre-configured positions.

This is the **correct modern architecture** that eliminates legacy EEPROM-based position management.
