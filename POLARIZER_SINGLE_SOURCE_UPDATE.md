# Polarizer Configuration Update Summary

**Date**: 2025-10-19
**Status**: ✅ **COMPLETE - Single Source of Truth Enforced**

---

## What Was Changed

Removed **all hardcoded default polarizer positions** from the calibration system and enforced OEM calibration tool as the **single source of truth** for S and P servo positions.

---

## Changes Made

### 1. **`utils/spr_calibrator.py` - `validate_polarizer_positions()`** (Lines ~1665-1690)

**Before** (❌ Had fallback defaults):
```python
except Exception as e:
    logger.warning(f"⚠️ Could not read servo positions: {e}")
    logger.warning("   Using default SWAPPED positions (S=100, P=10)")
    self.state.polarizer_s_position = 100  # ❌ DEFAULT
    self.state.polarizer_p_position = 10   # ❌ DEFAULT
```

**After** (✅ No defaults, explicit failure):
```python
except Exception as e:
    logger.error("=" * 80)
    logger.error("❌ POLARIZER CONFIGURATION MISSING")
    logger.error("🔧 REQUIRED: Run OEM calibration tool to configure polarizer positions")
    logger.error("   Command: python utils/oem_calibration_tool.py --serial YOUR_SERIAL")
    logger.error("   ❌ NO DEFAULT POSITIONS - OEM calibration is MANDATORY")
    logger.error("=" * 80)
    self.state.polarizer_s_position = None  # ✅ NO DEFAULT
    self.state.polarizer_p_position = None  # ✅ NO DEFAULT
    return False  # Fail calibration
```

---

### 2. **`utils/spr_calibrator.py` - `save_profile()`** (Lines ~3730-3760)

**Before** (❌ Had fallback defaults):
```python
calibration_data = {
    "polarizer_s_position": getattr(self.state, 'polarizer_s_position', 100),  # ❌ DEFAULT
    "polarizer_p_position": getattr(self.state, 'polarizer_p_position', 10),   # ❌ DEFAULT
}
```

**After** (✅ Validates before saving):
```python
s_pos = getattr(self.state, 'polarizer_s_position', None)
p_pos = getattr(self.state, 'polarizer_p_position', None)

if s_pos is None or p_pos is None:
    logger.error("❌ CANNOT SAVE PROFILE - Missing Polarizer Configuration")
    logger.error("🔧 REQUIRED: Run OEM calibration tool first")
    return False

calibration_data = {
    "polarizer_s_position": s_pos,  # ✅ From OEM only
    "polarizer_p_position": p_pos,  # ✅ From OEM only
}
```

---

### 3. **`utils/spr_calibrator.py` - `load_profile()`** (Lines ~3807-3825)

**Before** (❌ Had fallback defaults):
```python
self.state.polarizer_s_position = calibration_data.get("polarizer_s_position", 100)  # ❌ DEFAULT
self.state.polarizer_p_position = calibration_data.get("polarizer_p_position", 10)   # ❌ DEFAULT
```

**After** (✅ Validates loaded data):
```python
self.state.polarizer_s_position = calibration_data.get("polarizer_s_position")  # No default
self.state.polarizer_p_position = calibration_data.get("polarizer_p_position")  # No default

# Validate that OEM-calibrated positions were loaded
if self.state.polarizer_s_position is None or self.state.polarizer_p_position is None:
    logger.error("❌ INVALID CALIBRATION PROFILE - Missing Polarizer Positions")
    logger.error("This profile was created before OEM polarizer calibration.")
    logger.error("🔧 REQUIRED: Run OEM calibration tool")
    return False, "Profile missing OEM polarizer calibration data"
```

---

## Architecture

```
OEM CALIBRATION TOOL (Manufacturing)
     └─> Finds optimal S/P positions (141, 55)
          └─> Saves to device profile (single source of truth)
               └─> calibration_data/device_profiles/device_SERIAL_DATE.json
                    └─> Loaded by SPRCalibrator.validate_polarizer_positions()
                         └─> self.state.polarizer_s_position = 141 (from device)
                         └─> self.state.polarizer_p_position = 55  (from device)
                              └─> Used by ctrl.set_mode("s"/"p") during measurements
                                   └─> Saved to calibration profile (propagates OEM data)
```

---

## What This Prevents

### ❌ **Before** - Multiple Sources of Truth

1. **Hardcoded in validation**: S=100, P=10
2. **Hardcoded in save**: S=100, P=10 (fallback)
3. **Hardcoded in load**: S=100, P=10 (fallback)
4. **Hardcoded in controller**: s=10, p=100 (method signature)
5. **OEM tool finds**: S=141, P=55 (actual hardware optimal)

**Problem**: Which values are correct? System uses defaults even when OEM tool was never run!

### ✅ **After** - Single Source of Truth

1. **OEM tool finds**: S=141, P=55 (authoritative)
2. **Device profile stores**: S=141, P=55 (persistent)
3. **Calibration loads**: S=141, P=55 (from device profile)
4. **Hardware uses**: S=141, P=55 (from calibration state)
5. **Profiles save**: S=141, P=55 (propagated from state)

**Result**: All values come from OEM calibration. System **fails explicitly** if OEM tool not run.

---

## User Impact

### Existing Devices (Before OEM Feature)

**Symptom**: Calibration will fail at Step 2B

**Solution**:
```bash
# Run OEM calibration once
python utils/oem_calibration_tool.py --serial YOUR_SERIAL_NUMBER

# Then run normal calibration
python run_app.py
```

### New Devices (Manufacturing)

**Required Workflow**:
1. **First**: Run OEM calibration tool (finds optimal S/P positions)
2. **Then**: Run main application calibration (uses OEM values)

---

## Error Messages

### Missing OEM Calibration

```
================================================================================
❌ POLARIZER CONFIGURATION MISSING
================================================================================
⚠️ Could not read servo positions from hardware

🔧 REQUIRED: Run OEM calibration tool to configure polarizer positions
   Command: python utils/oem_calibration_tool.py --serial YOUR_SERIAL

   The OEM tool will:
   1. Sweep servo through full range (10-255)
   2. Find optimal S-mode position (perpendicular - HIGH transmission)
   3. Find optimal P-mode position (parallel - LOWER transmission)
   4. Save positions to device profile (single source of truth)

   ❌ NO DEFAULT POSITIONS - OEM calibration is MANDATORY
================================================================================
```

### Old Profile Without OEM Data

```
================================================================================
❌ INVALID CALIBRATION PROFILE - Missing Polarizer Positions
================================================================================
This calibration profile was created before OEM polarizer calibration.

🔧 REQUIRED ACTION: Run OEM calibration tool to configure polarizer:
   python utils/oem_calibration_tool.py --serial YOUR_SERIAL
================================================================================
```

---

## Testing

### Verify OEM Tool is Single Source

```bash
# 1. Run OEM calibration
python utils/oem_calibration_tool.py --serial TEST001 --skip-afterglow

# 2. Check device profile created
cat calibration_data/device_profiles/device_TEST001_*.json

# Expected output:
# {
#   "polarizer": {
#     "s_position": 141,
#     "p_position": 55,
#     "sp_ratio": 1.55
#   }
# }

# 3. Run main calibration
python run_app.py
# Click "Calibrate" and watch logs

# Expected: Step 2B loads positions from device profile
# "Servo positions: S=141, P=55 (0-255 scale)"
```

### Verify Failure Without OEM Tool

```bash
# 1. Delete device profile
rm calibration_data/device_profiles/device_TEST001_*.json

# 2. Try to run calibration
python run_app.py
# Click "Calibrate"

# Expected: Fails at Step 2B with clear error message
# "❌ POLARIZER CONFIGURATION MISSING"
# "🔧 REQUIRED: Run OEM calibration tool"
```

---

## Documentation

Created comprehensive documentation:

1. **`POLARIZER_SINGLE_SOURCE_OF_TRUTH.md`**
   - Architecture overview
   - Data flow diagram
   - Implementation details
   - Error handling
   - Migration guide
   - Testing procedures

2. **`POLARIZER_HARDWARE_VARIANTS.md`** (Already exists)
   - Barrel vs Round polarizer comparison
   - Algorithm compatibility
   - Expected S/P ratios

3. **`POLARIZER_CONFIGURATION_ACCEPTED.md`** (Already exists)
   - Acceptance of 1.55× ratio for barrel polarizer
   - Intensity analysis
   - Hardware limitations

---

## Backward Compatibility

### Breaking Change

**Old behavior**: System used hardcoded defaults (S=100, P=10) if OEM tool not run

**New behavior**: System **fails explicitly** and requires OEM tool

### Migration Path

For existing deployed devices:

```bash
# Step 1: Run OEM calibration (one-time, per device)
python utils/oem_calibration_tool.py --serial DEVICE_SERIAL

# Step 2: Delete old calibration profiles (optional but recommended)
rm calibration_profiles/*.json

# Step 3: Run new calibration (creates profiles with OEM data)
python run_app.py  # Click Calibrate button
```

---

## Benefits

### ✅ Consistency
- All code uses same S/P positions
- No conflicting values in different parts of codebase

### ✅ Traceability
- Clear origin: OEM tool is authoritative
- Timestamp and metadata in device profile

### ✅ Device-Specific
- Each device has optimal positions for its hardware
- Barrel polarizer: S=141, P=55 (1.55× ratio)
- Round polarizer: S=XXX, P=YYY (3.0-15.0× ratio)

### ✅ Explicit Failures
- No silent fallback to wrong values
- Clear error messages guide user to solution

### ✅ Manufacturing Workflow
- Forces proper manufacturing process
- OEM tool must be run before deployment

---

## Code Search Results

All references to polarizer positions reviewed:

- ✅ `utils/spr_calibrator.py` - No defaults, enforces OEM data
- ✅ `utils/oem_calibration_tool.py` - Authoritative source
- ⚠️ `utils/controller.py` - Method signatures (s=10, p=100) - **OK** (not used by calibration)
- ℹ️ Documentation files - Contain examples/explanations - **OK**

---

## Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Default Positions** | S=100, P=10 (hardcoded 3 places) | ❌ None - Fails explicitly |
| **Source of Truth** | Multiple conflicting sources | ✅ OEM tool only |
| **Failure Mode** | Silent fallback to defaults | ✅ Explicit error with guidance |
| **Device Specificity** | All devices use same defaults | ✅ Each device has optimal values |
| **Manufacturing** | Optional (used defaults) | ✅ Mandatory (explicit requirement) |

---

**Status**: ✅ **COMPLETE** - Polarizer positions are now managed through a single source of truth (OEM calibration tool), with no hardcoded defaults anywhere in the calibration system.
