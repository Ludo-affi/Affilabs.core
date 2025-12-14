# Single Source of Truth: LED Calibration Complete

## ✅ Summary

Successfully enforced **device_config.json** as the single source of truth for LED calibration data. Removed all duplicate storage paths and updated collection script to load from the correct location.

## 🎯 What Was Fixed

### 1. Collection Script Now Uses device_config.json
**File:** `collect_training_data.py`

**Before (WRONG):**
```python
from utils.config_manager import ConfigurationManager

config_mgr = ConfigurationManager()
led_intensity = config_mgr.calibration.ref_intensity.get(channel.upper(), 128)
integration_time_ms = config_mgr.calibration.integration
```

**After (CORRECT):**
```python
from utils.device_configuration import DeviceConfiguration

device_config = DeviceConfiguration()
calibration = device_config.load_led_calibration()

if calibration:
    led_intensity = calibration['s_mode_intensities'].get(channel.upper(), 128)
    integration_time_ms = calibration['integration_time_ms']
else:
    # Fallback if no calibration found
    led_intensity = 128
    integration_time_ms = 50
```

**Changed:**
- Line 27: Import changed from `ConfigurationManager` to `DeviceConfiguration`
- Lines 233-252: Load LED calibration from `device_config.json` instead of runtime state

### 2. Removed Duplicate Storage from ConfigurationManager
**File:** `utils/config_manager.py`

**Removed from `save_configuration()` (lines 287-320):**
```python
# REMOVED - No longer saved to disk
"calibration": {
    "integration": self.calibration.integration,
    "ref_intensity": self.calibration.ref_intensity,
    "pol_intensity": self.calibration.pol_intensity,
}
```

**Removed from `load_configuration()` (lines 329-359):**
```python
# REMOVED - No longer loaded from disk
if "calibration" in config_data:
    cal_data = config_data["calibration"]
    self.calibration.integration = cal_data.get("integration", MIN_INTEGRATION)
    self.calibration.ref_intensity = cal_data.get("ref_intensity", ...)
    self.calibration.pol_intensity = cal_data.get("pol_intensity", ...)
```

**Added comments:**
```python
# Note: LED calibration (ref_intensity, pol_intensity, integration)
# is stored in device_config.json via DeviceConfiguration.save_led_calibration()
# and should NOT be duplicated here
```

## 📊 Storage Architecture

### ✅ Single Source of Truth: device_config.json

**Location:** `generated-files/config/device_config.json`

**Structure:**
```json
{
  "led_calibration": {
    "integration_time_ms": 50,
    "s_mode_intensities": {
      "A": 185,
      "B": 180,
      "C": 175,
      "D": 170
    },
    "p_mode_intensities": {
      "A": 200,
      "B": 195,
      "C": 190,
      "D": 185
    },
    "s_ref_baseline": {
      "A": [array of ~1000 pixels],
      "B": [...],
      "C": [...],
      "D": [...]
    }
  }
}
```

**API:**
- `DeviceConfiguration.save_led_calibration(...)` - Save calibration
- `DeviceConfiguration.load_led_calibration()` - Load calibration

### ❌ Runtime State Only: ConfigurationManager

**Purpose:** In-memory runtime state (NOT persisted)

**Location:** `utils/config_manager.py` → `CalibrationConfiguration` class

**Runtime Variables (not saved to disk):**
```python
self.calibration.integration = 50  # Current integration time
self.calibration.ref_intensity = {"A": 185, ...}  # Current S-mode intensities
self.calibration.pol_intensity = {"A": 200, ...}  # Current P-mode intensities
```

**When Updated:**
- During calibration via `update_from_calibrator(calibrator_state)`
- During manual parameter adjustment via `ParameterManager`
- When loading from device_config.json at startup

**Not Saved:** These values are NOT written to disk by ConfigurationManager

## 🔍 Verification

### Confirmed Single Storage Path

**Search:** All code that saves LED calibration
```bash
grep -r "save.*led.*calibration" --include="*.py"
```

**Results:**
- ✅ `DeviceConfiguration.save_led_calibration()` (utils/device_configuration.py)
- ✅ `SPRCalibrator` calls `device_config.save_led_calibration()` (utils/spr_calibrator.py:4154)
- ✅ Test file (test_calibration_qc_system.py)

**No other saves found** ✅

### Confirmed No Duplicate Loads

**Collection Script:**
- ✅ Now loads from `DeviceConfiguration.load_led_calibration()`
- ❌ No longer uses `ConfigurationManager.calibration` (old path)

**Main Application:**
- ✅ Uses `DeviceConfiguration` (main/main.py)

**Calibrator:**
- ✅ Saves to device_config.json after successful calibration
- ✅ Loads from device_config.json for QC validation

## 📝 Data Flow

### Calibration Flow
```
1. User triggers calibration
2. SPRCalibrator.calibrate_full()
   ├─ Measure optimal LED intensities
   ├─ Measure S-ref baseline spectra
   └─ Save to device_config.json ← SINGLE SOURCE OF TRUTH
3. ConfigurationManager.update_from_calibrator()
   └─ Copy to runtime state (in-memory only)
```

### Collection Script Flow
```
1. User runs collect_training_data.py --use-calibration
2. Script calls DeviceConfiguration.load_led_calibration()
   └─ Reads from device_config.json ← SINGLE SOURCE OF TRUTH
3. Uses calibrated LED intensities and integration time
4. Sets hardware with correct values
```

### QC Validation Flow
```
1. User triggers calibration
2. SPRCalibrator checks if calibration exists
3. If exists:
   ├─ Load S-ref baseline from device_config.json
   ├─ Take new S-ref measurement
   ├─ Validate intensity (within 5%)
   ├─ Validate shape (correlation > 0.98)
   └─ If PASS: Use existing calibration (5-10s)
      If FAIL: Run full calibration (2-3min)
```

## ✅ Benefits

### 1. No Duplicate Storage
- **Before:** LED calibration saved in both device_config.json AND ConfigurationManager files
- **After:** Only saved in device_config.json

### 2. Consistent Data
- **Before:** Collection script used ConfigurationManager (could be out of sync)
- **After:** Collection script uses device_config.json (same as calibrator)

### 3. Clear Separation
- **Device Config:** Hardware calibration (persistent)
- **Configuration Manager:** Runtime state (ephemeral)

### 4. Easier Maintenance
- Single place to update LED calibration
- No synchronization issues between multiple storage locations
- Clear data ownership

## 🎯 Testing Checklist

### Unit Tests
- [x] Test QC validation system (test_calibration_qc_system.py passes)
- [ ] Test collection script loads from device_config.json
- [ ] Test fallback behavior when no calibration exists

### Integration Tests
- [ ] Run full calibration → verify device_config.json updated
- [ ] Run collection script → verify it uses calibrated values
- [ ] Test QC validation → verify it passes with good S-ref
- [ ] Test QC validation → verify it fails with bad S-ref

### Hardware Tests
- [ ] Calibrate hardware → check device_config.json
- [ ] Run collection script with `--use-calibration`
- [ ] Verify LED intensities match calibration (not saturated at 255)
- [ ] Verify integration time matches calibration

## 📂 Files Modified

### Primary Changes
1. ✅ `collect_training_data.py` (lines 27, 233-252)
   - Changed import from ConfigurationManager to DeviceConfiguration
   - Load calibration from device_config.json

2. ✅ `utils/config_manager.py` (lines 287-359)
   - Removed LED calibration from save_configuration()
   - Removed LED calibration from load_configuration()
   - Added comments explaining new architecture

### No Changes Needed (Already Correct)
- ✅ `utils/device_configuration.py` - save_led_calibration() / load_led_calibration()
- ✅ `utils/spr_calibrator.py` - Saves to device_config.json after calibration
- ✅ `main/main.py` - Uses DeviceConfiguration

## 🚀 Next Steps

1. **Test collection script:**
   ```bash
   python collect_training_data.py --device "demo P4SPR 2.0" --use-calibration --label test
   ```

2. **Verify it loads from device_config.json:**
   - Check console output for "Using calibrated LED intensity: X"
   - Ensure values match device_config.json

3. **Hardware test:**
   - Run full calibration
   - Run collection script
   - Verify LED intensities are NOT 255 (saturated)

4. **Documentation update:**
   - Update README with new architecture
   - Document single source of truth pattern

## ✨ Status

- ✅ Collection script fixed
- ✅ Duplicate storage removed
- ✅ Single source of truth enforced
- ✅ No other duplicate paths found
- 🟡 Testing pending (software + hardware)

**Ready for hardware testing!** 🎉
