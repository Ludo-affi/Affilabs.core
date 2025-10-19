# Polarizer Configuration - Single Source of Truth

**Date**: 2025-10-19
**Status**: ✅ **ENFORCED - OEM Calibration Mandatory**

---

## Architecture Overview

The polarizer servo positions (S and P) are determined **ONCE during manufacturing** by the OEM calibration tool and stored in the device profile. These values are the **single source of truth** used everywhere in the codebase.

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  OEM CALIBRATION TOOL (Manufacturing - Run Once)            │
│  ============================================                │
│  1. Sweeps servo through full range (10-255)                │
│  2. Finds optimal S-mode position (HIGH transmission)       │
│  3. Finds optimal P-mode position (LOWER transmission)      │
│  4. Measures S/P ratio (validates quality)                  │
│  5. Saves to device profile: device_SERIAL_DATE.json        │
│                                                              │
│  OUTPUT: calibration_data/device_profiles/device_*.json     │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ SINGLE SOURCE OF TRUTH
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  DEVICE PROFILE (JSON File)                                 │
│  ===========================                                 │
│  {                                                           │
│    "serial_number": "FLMT12345",                            │
│    "polarizer": {                                            │
│      "s_position": 141,    ← AUTHORITATIVE VALUE            │
│      "p_position": 55,     ← AUTHORITATIVE VALUE            │
│      "sp_ratio": 1.55,                                       │
│      "calibration_date": "2025-10-19T14:30:00"              │
│    },                                                        │
│    "afterglow": { ... }                                      │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ LOADED AT STARTUP
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  CALIBRATION PROFILE (SPRCalibrator.state)                  │
│  ==========================================                  │
│  self.state.polarizer_s_position = 141  (from device)       │
│  self.state.polarizer_p_position = 55   (from device)       │
│  self.state.polarizer_sp_ratio = 1.55   (from device)       │
│                                                              │
│  ❌ NO DEFAULT VALUES - Will fail if missing                │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ USED BY ALL MEASUREMENTS
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  HARDWARE OPERATIONS (ctrl.set_mode())                      │
│  ======================================                      │
│  ctrl.set_mode("s") → moves servo to position 141           │
│  ctrl.set_mode("p") → moves servo to position 55            │
│                                                              │
│  Values propagated from calibration state                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Critical Rules

### ✅ **DO's**

1. **Run OEM calibration once during manufacturing**:
   ```bash
   python utils/oem_calibration_tool.py --serial FLMT12345
   ```

2. **Load device profile at application startup**:
   ```python
   # Device profile loader automatically finds and loads:
   # calibration_data/device_profiles/device_SERIAL_DATE.json
   ```

3. **Use calibration state values everywhere**:
   ```python
   s_pos = self.state.polarizer_s_position  # Always from OEM tool
   p_pos = self.state.polarizer_p_position  # Always from OEM tool
   ```

4. **Validate positions before use**:
   ```python
   if self.state.polarizer_s_position is None:
       raise ValueError("OEM calibration required - run oem_calibration_tool.py")
   ```

### ❌ **DON'Ts**

1. **NEVER use hardcoded default positions**:
   ```python
   # ❌ WRONG - NO DEFAULTS ALLOWED
   s_pos = getattr(self.state, 'polarizer_s_position', 100)
   p_pos = getattr(self.state, 'polarizer_p_position', 10)

   # ✅ CORRECT - Force OEM calibration
   s_pos = self.state.polarizer_s_position
   if s_pos is None:
       raise ValueError("OEM calibration required")
   ```

2. **NEVER override OEM values in code**:
   ```python
   # ❌ WRONG - Overrides OEM calibration
   self.state.polarizer_s_position = 100

   # ✅ CORRECT - Load from device profile only
   device_profile = load_device_profile(serial_number)
   self.state.polarizer_s_position = device_profile['polarizer']['s_position']
   ```

3. **NEVER save profiles without OEM data**:
   ```python
   # ❌ WRONG - Missing critical data
   if s_pos is None:
       s_pos = 100  # DON'T DO THIS

   # ✅ CORRECT - Fail and force OEM calibration
   if s_pos is None:
       raise ValueError("Cannot save profile - OEM calibration required first")
   ```

---

## Implementation Status

### Files Updated (2025-10-19)

#### 1. **`utils/spr_calibrator.py`** - Validation Logic

**Lines ~1665-1690**: `validate_polarizer_positions()`
```python
except Exception as e:
    logger.error("=" * 80)
    logger.error("❌ POLARIZER CONFIGURATION MISSING")
    logger.error("=" * 80)
    logger.error(f"⚠️ Could not read servo positions from hardware: {e}")
    logger.error("")
    logger.error("🔧 REQUIRED: Run OEM calibration tool to configure polarizer positions")
    logger.error("   Command: python utils/oem_calibration_tool.py --serial YOUR_SERIAL")
    logger.error("")
    logger.error("   ❌ NO DEFAULT POSITIONS - OEM calibration is MANDATORY")
    logger.error("=" * 80)
    self.state.polarizer_s_position = None  # ✅ No defaults!
    self.state.polarizer_p_position = None  # ✅ No defaults!
    return False  # Fail calibration
```

**Status**: ✅ **NO DEFAULTS** - Fails explicitly if OEM data missing

---

#### 2. **`utils/spr_calibrator.py`** - Profile Saving

**Lines ~3730-3760**: `save_profile()`
```python
# ⚠️ CRITICAL: Polarizer positions MUST come from OEM calibration (NO DEFAULTS)
s_pos = getattr(self.state, 'polarizer_s_position', None)
p_pos = getattr(self.state, 'polarizer_p_position', None)

if s_pos is None or p_pos is None:
    logger.error("=" * 80)
    logger.error("❌ CANNOT SAVE PROFILE - Missing Polarizer Configuration")
    logger.error("🔧 REQUIRED: Run OEM calibration tool first")
    logger.error("=" * 80)
    return False

calibration_data = {
    "polarizer_s_position": s_pos,  # ✅ From OEM only!
    "polarizer_p_position": p_pos,  # ✅ From OEM only!
    ...
}
```

**Status**: ✅ **ENFORCED** - Cannot save without OEM data

---

#### 3. **`utils/spr_calibrator.py`** - Profile Loading

**Lines ~3807-3825**: `load_profile()`
```python
# ✨ Load validated polarizer positions from OEM calibration (NO DEFAULTS!)
self.state.polarizer_s_position = calibration_data.get("polarizer_s_position")  # No default!
self.state.polarizer_p_position = calibration_data.get("polarizer_p_position")  # No default!

# Validate that OEM-calibrated positions were loaded
if self.state.polarizer_s_position is None or self.state.polarizer_p_position is None:
    logger.error("=" * 80)
    logger.error("❌ INVALID CALIBRATION PROFILE - Missing Polarizer Positions")
    logger.error("This profile was created before OEM polarizer calibration.")
    logger.error("🔧 REQUIRED: Run OEM calibration tool")
    logger.error("=" * 80)
    return False, "Profile missing OEM polarizer calibration data"
```

**Status**: ✅ **VALIDATED** - Fails if OEM data missing from profile

---

#### 4. **`utils/oem_calibration_tool.py`** - Source of Truth

**Lines ~250-450**: `run_calibration()`
```python
# Find optimal positions through sweep
s_position = 141  # Found by peak detection
p_position = 55   # Found by peak detection
sp_ratio = 1.55   # Measured and validated

# Save to device profile (SINGLE SOURCE OF TRUTH)
device_profile = {
    "serial_number": serial_number,
    "polarizer": {
        "s_position": int(s_position),  # ✅ Authoritative value
        "p_position": int(p_position),  # ✅ Authoritative value
        "sp_ratio": float(sp_ratio),
        "calibration_date": timestamp
    }
}

# Save to: calibration_data/device_profiles/device_SERIAL_DATE.json
save_device_profile(device_profile)
```

**Status**: ✅ **AUTHORITATIVE** - Creates single source of truth

---

## Error Handling

### Scenario 1: No OEM Calibration Run

**When**: User tries to run main calibration without OEM tool first

**Result**:
```
================================================================================
❌ POLARIZER CONFIGURATION MISSING
================================================================================
⚠️ Could not read servo positions from hardware: [error]

🔧 REQUIRED: Run OEM calibration tool to configure polarizer positions
   This tool finds optimal S and P positions during manufacturing.

   Command: python utils/oem_calibration_tool.py --serial YOUR_SERIAL

   The OEM tool will:
   1. Sweep servo through full range (10-255)
   2. Find optimal S-mode position (perpendicular - HIGH transmission)
   3. Find optimal P-mode position (parallel - LOWER transmission)
   4. Save positions to device profile (single source of truth)

   ❌ NO DEFAULT POSITIONS - OEM calibration is MANDATORY
================================================================================
CALIBRATION FAILED: Step 2B: Polarizer positions invalid
```

**Action**: User must run OEM tool

---

### Scenario 2: Old Profile Without OEM Data

**When**: User loads calibration profile created before OEM feature

**Result**:
```
================================================================================
❌ INVALID CALIBRATION PROFILE - Missing Polarizer Positions
================================================================================
This calibration profile was created before OEM polarizer calibration.

🔧 REQUIRED ACTION: Run OEM calibration tool to configure polarizer:
   python utils/oem_calibration_tool.py --serial YOUR_SERIAL

The OEM tool will find optimal S/P positions and save to device profile.
================================================================================
LOAD FAILED: Profile missing OEM polarizer calibration data
```

**Action**: User must run OEM tool, then recalibrate

---

### Scenario 3: Trying to Save Without OEM Data

**When**: Calibration state missing polarizer positions

**Result**:
```
================================================================================
❌ CANNOT SAVE PROFILE - Missing Polarizer Configuration
================================================================================
Polarizer positions are not configured in calibration state.

🔧 REQUIRED: Run OEM calibration tool first:
   python utils/oem_calibration_tool.py --serial YOUR_SERIAL

The OEM tool finds optimal S/P positions (single source of truth).
================================================================================
SAVE FAILED
```

**Action**: User must run OEM tool and restart calibration

---

## Migration Guide

### For Existing Systems

If you have devices deployed **before** OEM calibration feature:

1. **Identify current positions**:
   ```python
   # Read from hardware
   positions = ctrl.get_servo_positions()
   # Or check calibration profile (if it has them)
   ```

2. **Run OEM calibration tool**:
   ```bash
   python utils/oem_calibration_tool.py --serial DEVICE_SERIAL
   ```

3. **Verify positions match**:
   - OEM tool should find similar positions to what was working
   - If very different, investigate hardware changes

4. **Update all calibration profiles**:
   - Delete old profiles without OEM data
   - Run full calibration to create new profiles with OEM data

### For New Systems

1. **Run OEM tool during manufacturing** (FIRST STEP):
   ```bash
   python utils/oem_calibration_tool.py --serial FLMT12345
   ```

2. **Verify device profile created**:
   ```bash
   ls calibration_data/device_profiles/device_FLMT12345_*.json
   ```

3. **Run main calibration** (will auto-load OEM data):
   ```bash
   python run_app.py  # Start application, click Calibrate
   ```

---

## Verification Checklist

### ✅ After OEM Calibration

- [ ] Device profile exists in `calibration_data/device_profiles/`
- [ ] Profile contains `polarizer.s_position` (integer 10-255)
- [ ] Profile contains `polarizer.p_position` (integer 10-255)
- [ ] Profile contains `polarizer.sp_ratio` (float)
- [ ] S/P ratio is acceptable (>1.5× for barrel, >3.0× for round)

### ✅ During Main Calibration

- [ ] Step 2B loads positions from device profile
- [ ] Log shows: `"Servo positions: S=XXX, P=YYY (0-255 scale)"`
- [ ] Validation passes with loaded positions
- [ ] No hardcoded defaults used anywhere

### ✅ In Saved Calibration Profile

- [ ] Profile JSON contains `"polarizer_s_position": XXX`
- [ ] Profile JSON contains `"polarizer_p_position": YYY`
- [ ] Profile JSON contains `"polarizer_sp_ratio": Z.ZZ`
- [ ] Values match device profile exactly

---

## Testing

### Test 1: OEM Tool Creates Device Profile

```bash
# Run OEM calibration
python utils/oem_calibration_tool.py --serial TEST001 --skip-afterglow

# Expected: Creates calibration_data/device_profiles/device_TEST001_*.json
# Verify file contains polarizer positions
cat calibration_data/device_profiles/device_TEST001_*.json | grep polarizer
```

**Expected Output**:
```json
"polarizer": {
  "s_position": 141,
  "p_position": 55,
  "sp_ratio": 1.55,
  "calibration_date": "2025-10-19T14:30:00"
}
```

### Test 2: Main Calibration Uses OEM Values

```python
# Start application
python run_app.py

# Click "Calibrate" button
# Watch log output during Step 2B
```

**Expected Log**:
```
================================================================================
STEP 2B: Polarizer Position Validation
================================================================================
Reading current servo positions from hardware...
   Servo positions: S=141, P=55 (0-255 scale)
...
✅ Polarizer positions VALIDATED (ratio: 1.55x is acceptable)
   Servo positions confirmed: S=141, P=55 (0-255 scale)
```

### Test 3: No Defaults Used (Failure Test)

```python
# Delete device profile
rm calibration_data/device_profiles/device_TEST001_*.json

# Try to run calibration
python run_app.py
# Click "Calibrate"
```

**Expected Result**: Calibration fails at Step 2B with clear error

---

## Summary

| Aspect | Implementation |
|--------|---------------|
| **Single Source** | OEM calibration tool (`oem_calibration_tool.py`) |
| **Storage** | Device profile JSON (`device_SERIAL_DATE.json`) |
| **Loading** | Automatic at startup (device profile loader) |
| **Defaults** | ❌ **NONE** - Fails if OEM data missing |
| **Validation** | Step 2B enforces OEM data presence |
| **Propagation** | Through `self.state.polarizer_*_position` |
| **Hardware** | Values used by `ctrl.set_mode("s"/"p")` |

---

## Conclusion

✅ **Polarizer positions are now managed as a SINGLE SOURCE OF TRUTH**:

1. **OEM tool** finds and saves positions (manufacturing, run once)
2. **Device profile** stores authoritative values (persistent, device-specific)
3. **Calibration state** loads from device profile (runtime, validated)
4. **Hardware operations** use calibration state values (measurements)
5. **NO DEFAULTS** anywhere - system fails explicitly if OEM data missing

This architecture ensures:
- ✅ Consistency across all code
- ✅ No conflicting hardcoded values
- ✅ Clear error messages when OEM tool not run
- ✅ Manufacturing workflow is explicit and required
- ✅ Device-specific optimization preserved

**Status**: ✅ **COMPLETE** - OEM calibration is now mandatory and enforced throughout the codebase.
