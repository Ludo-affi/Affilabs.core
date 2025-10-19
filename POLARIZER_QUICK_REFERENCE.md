# Polarizer Configuration Quick Reference

**Last Updated**: 2025-10-19

---

## ✅ Single Source of Truth: OEM Calibration Tool

```
OEM Tool → Device Profile → Calibration State → Hardware → Measurements
  (finds)    (stores)         (loads)           (uses)      (applies)
  S=141      JSON file        state.s_pos       servo       ctrl.set_mode()
  P=55       persistent       validated         moves       uses positions
```

---

## 🔧 Required Manufacturing Workflow

### Step 1: OEM Calibration (First Time Only)
```bash
python utils/oem_calibration_tool.py --serial FLMT12345
```

**Output**: Creates `calibration_data/device_profiles/device_FLMT12345_YYYYMMDD.json`

**Contains**:
- `polarizer.s_position` (e.g., 141)
- `polarizer.p_position` (e.g., 55)
- `polarizer.sp_ratio` (e.g., 1.55)
- Timestamp and metadata

---

### Step 2: Normal Operation
```bash
python run_app.py
# Click "Calibrate" button
```

**Behavior**: Automatically loads S/P positions from device profile

---

## ❌ What Changed (No More Defaults)

### Before (Wrong)
```python
# ❌ Had fallback defaults everywhere
s_pos = getattr(state, 'polarizer_s_position', 100)  # DEFAULT
p_pos = getattr(state, 'polarizer_p_position', 10)   # DEFAULT
```

### After (Correct)
```python
# ✅ No defaults - explicit failure if missing
s_pos = state.polarizer_s_position  # From OEM tool only
p_pos = state.polarizer_p_position  # From OEM tool only

if s_pos is None:
    raise ValueError("OEM calibration required")
```

---

## 🚨 Error Messages

### Missing OEM Calibration
```
❌ POLARIZER CONFIGURATION MISSING
🔧 REQUIRED: Run OEM calibration tool
   Command: python utils/oem_calibration_tool.py --serial YOUR_SERIAL
```

**Solution**: Run OEM tool once

---

### Old Profile (No OEM Data)
```
❌ INVALID CALIBRATION PROFILE - Missing Polarizer Positions
This profile was created before OEM polarizer calibration.
```

**Solution**: Run OEM tool, then recalibrate

---

## 📊 Hardware Variants

| Type | Positions | S/P Ratio | Characteristics |
|------|-----------|-----------|----------------|
| **Barrel** | 2 fixed windows | 1.5-2.5× | Only 2 peaks, fixed orientation |
| **Round** | Continuous rotation | 3.0-15.0× | Smooth curve, many positions |

**Your System** (Barrel): S=141, P=55, Ratio=1.55× ✅ ACCEPTABLE

---

## 🧪 Quick Tests

### Test 1: Verify OEM Profile Exists
```bash
ls -la calibration_data/device_profiles/device_*.json
cat calibration_data/device_profiles/device_*.json | grep polarizer
```

**Expected**:
```json
"polarizer": {
  "s_position": 141,
  "p_position": 55,
  "sp_ratio": 1.55
}
```

---

### Test 2: Verify Main Calibration Uses OEM Values
```bash
python run_app.py
# Watch log during calibration Step 2B
```

**Expected Log**:
```
STEP 2B: Polarizer Position Validation
Servo positions: S=141, P=55 (0-255 scale)
✅ Polarizer positions VALIDATED
```

---

### Test 3: Verify Failure Without OEM Data
```bash
# Backup device profile
mv calibration_data/device_profiles/device_*.json ~/backup/

# Try to calibrate
python run_app.py  # Click Calibrate

# Expected: Fails with clear error
```

---

## 📁 File Locations

| File | Purpose | Created By |
|------|---------|----------|
| `calibration_data/device_profiles/device_SERIAL_DATE.json` | Device profile (OEM data) | OEM tool |
| `calibration_profiles/auto_save_TIMESTAMP.json` | Calibration profile | Main app |
| `utils/oem_calibration_tool.py` | OEM calibration script | Manufacturing |

---

## 🔄 Migration for Existing Devices

```bash
# 1. Run OEM calibration (one-time per device)
python utils/oem_calibration_tool.py --serial YOUR_SERIAL

# 2. Verify device profile created
ls calibration_data/device_profiles/

# 3. Delete old calibration profiles (optional)
rm calibration_profiles/*.json

# 4. Run new calibration
python run_app.py  # Click Calibrate
```

---

## 💡 Key Points

1. **OEM tool = Single source of truth** for polarizer positions
2. **No defaults** - System fails explicitly if OEM data missing
3. **Device-specific** - Each device has optimal positions for its hardware
4. **One-time setup** - Run OEM tool once during manufacturing
5. **Automatic loading** - Main app loads from device profile

---

## 📚 Full Documentation

- `POLARIZER_SINGLE_SOURCE_OF_TRUTH.md` - Complete architecture
- `POLARIZER_SINGLE_SOURCE_UPDATE.md` - Change summary
- `POLARIZER_HARDWARE_VARIANTS.md` - Barrel vs Round comparison
- `POLARIZER_CONFIGURATION_ACCEPTED.md` - Your 1.55× ratio analysis

---

**Status**: ✅ Enforced across entire codebase - OEM calibration is mandatory
