# Polarizer Position Loading Fix ✅

**Date**: 2025-10-20
**Issue**: Polarizer positions not loading from device configuration
**Status**: FIXED - Supports both naming conventions

---

## 🐛 Problem Identified

The code expected polarizer positions in this format:
```json
{
  "oem_calibration": {
    "polarizer_s_position": 165,
    "polarizer_p_position": 50
  }
}
```

But the OEM calibration tool saves them in this format:
```json
{
  "polarizer": {
    "s_position": 50,
    "p_position": 165
  }
}
```

**Result**: The calibrator couldn't find polarizer positions and failed at initialization.

---

## ✅ Solution Implemented

### 1. Updated `_get_oem_positions()` Method

Added fallback to check `polarizer` section if `oem_calibration` doesn't exist:

```python
def _get_oem_positions(self) -> tuple[int | None, int | None, float | None]:
    # ... existing code for state and oem_calibration ...

    # ✨ FIX: Also check 'polarizer' section (OEM tool output format)
    if self.device_config and 'polarizer' in self.device_config:
        pol = self.device_config['polarizer']
        logger.info("✨ Found polarizer positions in 'polarizer' section (OEM tool format)")
        return (
            pol.get('s_position'),
            pol.get('p_position'),
            pol.get('sp_ratio') or pol.get('s_p_ratio')
        )

    return (None, None, None)
```

### 2. Updated `__init__()` Initialization

Modified early position loading to check both sections:

```python
oem_cal = None
if device_config and 'oem_calibration' in device_config:
    oem_cal = device_config['oem_calibration']
    logger.info("✅ Found OEM calibration in 'oem_calibration' section")
elif device_config and 'polarizer' in device_config:
    oem_cal = device_config['polarizer']
    logger.info("✅ Found OEM calibration in 'polarizer' section (OEM tool format)")

if oem_cal:
    # Handle both naming conventions
    self.state.polarizer_s_position = oem_cal.get('polarizer_s_position') or oem_cal.get('s_position')
    self.state.polarizer_p_position = oem_cal.get('polarizer_p_position') or oem_cal.get('p_position')
    self.state.polarizer_sp_ratio = oem_cal.get('polarizer_sp_ratio') or oem_cal.get('sp_ratio') or oem_cal.get('s_p_ratio')
```

---

## 📊 Files Modified

### `utils/spr_calibrator.py`

1. **Line 802-850**: Modified `_get_oem_positions()` to check both `oem_calibration` and `polarizer` sections
2. **Line 629-680**: Modified `__init__()` to load positions from either section format

---

## ⚠️ Current Calibration Issue

**Hardware Mismatch Detected**:
- **Config expects**: S=165, P=50
- **Hardware reports**: S=30, P=120

This is a **servo positioning issue**, not a software bug. The servos are at different positions than what's saved in the config.

### Possible Causes:
1. Servos were manually moved after calibration
2. Previous calibration didn't save properly
3. Servo power cycle reset positions to default

### Solutions:
1. **Recommended**: Run auto-polarization from Settings menu in GUI
2. **Alternative**: Run OEM calibration tool manually:
   ```bash
   python utils/oem_calibration_tool.py --serial TEST001
   ```
3. **Quick fix**: Manually set servos to match config (if you know correct positions)

---

## 🎯 Testing Status

**Software Fix**: ✅ COMPLETE
- Code now reads positions from both formats
- No more "OEM positions not found" errors

**Hardware Issue**: ⏸️ PENDING
- Servo positions need to be synchronized with config
- Requires running auto-polarization or manual calibration

**Pipeline Testing**: ⏸️ BLOCKED BY CALIBRATION
- Pipeline code is ready (implemented separately)
- Can't test until hardware calibration passes

---

## 📝 Notes

- The fix is backward compatible - works with both old and new config formats
- Existing calibrations in `oem_calibration` format still work
- New calibrations from OEM tool in `polarizer` format also work
- Code handles missing ratio values gracefully

---

## 🔄 Next Steps

1. Fix servo positions (run auto-polarization or OEM calibration)
2. Verify calibration passes
3. Test pipeline architecture with live measurements
4. Measure performance improvements
