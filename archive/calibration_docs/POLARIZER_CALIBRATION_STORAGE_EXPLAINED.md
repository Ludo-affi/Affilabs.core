# Polarizer Calibration Storage - Complete Flow

**Question**: Where are the polarizer values saved after OEM calibration?

**Answer**: `config/device_config.json` → `oem_calibration` section

---

## 📁 Storage Location

**File**: `config/device_config.json`

**Section**: `oem_calibration`

**Format**:
```json
{
  "oem_calibration": {
    "polarizer_s_position": 165,
    "polarizer_p_position": 50,
    "polarizer_sp_ratio": 15.89,
    "calibration_date": "2025-10-19T15:32:00",
    "calibration_method": "window_verification_corrected"
  }
}
```

---

## 🔄 Complete Data Flow

### **1. OEM Calibration Tool** (Manufacturing)

**File**: `utils/oem_calibration_tool.py`

**Process**:
```python
# Step 1: Run calibration sweep
python utils/oem_calibration_tool.py --serial FLMT09788

# Step 2: Tool sweeps servo positions (10-255 PWM)
# - Measures intensity at each position
# - Finds optimal S-mode (HIGH transmission)
# - Finds optimal P-mode (LOWER transmission)
# - Calculates S/P ratio

# Step 3: Saves TWO files
# a) Device profile: calibration_data/device_profiles/device_{serial}_{date}.json
# b) Device config: config/device_config.json (updated with oem_calibration section)
```

**Saved Data**:
- `polarizer_s_position`: Servo position for S-mode (0-255 scale)
- `polarizer_p_position`: Servo position for P-mode (0-255 scale)
- `polarizer_sp_ratio`: Expected S/P intensity ratio
- `calibration_date`: When calibration was performed
- `calibration_method`: Which algorithm was used

---

### **2. Application Startup** (Loading)

**File**: `utils/spr_calibrator.py`

**Loading Code** (Line ~631):
```python
def __init__(self, ...):
    # Load OEM calibration positions immediately at initialization
    # Source priority:
    #   - device_config['oem_calibration'] (preferred format)
    #   - device_config['polarizer'] (legacy OEM tool format)

    if 'oem_calibration' in device_config:
        oem = device_config['oem_calibration']
        self.s_position_oem = oem.get('polarizer_s_position')
        self.p_position_oem = oem.get('polarizer_p_position')
        self.sp_ratio_oem = oem.get('polarizer_sp_ratio')
        logger.info("✅ OEM CALIBRATION POSITIONS LOADED AT INIT")
    else:
        raise ValueError("OEM calibration positions not found in device_config")
```

**Fallback Logic** (Line ~790):
```python
def _load_oem_positions(self, device_config: dict):
    """Load OEM calibration positions from device config.

    Tries two locations:
    - oem_calibration section (preferred format)
    - polarizer section (OEM tool legacy format)
    """

    # Try oem_calibration section first (preferred)
    if 'oem_calibration' in device_config:
        oem = device_config['oem_calibration']
        logger.info("✅ Found OEM calibration in 'oem_calibration' section")
        return {
            's_position': oem.get('polarizer_s_position'),
            'p_position': oem.get('polarizer_p_position'),
            'sp_ratio': oem.get('polarizer_sp_ratio')
        }

    # Fallback to polarizer section (legacy)
    elif 'polarizer' in device_config:
        pol = device_config['polarizer']
        logger.info("✅ Found OEM calibration in 'polarizer' section (OEM tool format)")
        return {
            's_position': pol.get('s_position'),
            'p_position': pol.get('p_position'),
            'sp_ratio': pol.get('sp_ratio')
        }
```

---

### **3. Calibration Validation** (Runtime)

**File**: `utils/spr_calibrator.py` (Line ~1900)

**Validation Code**:
```python
def _validate_polarizer_positions(self):
    """Verify loaded OEM positions produce expected S/P ratio.

    Expected behavior:
    - S-mode intensity should be 2.0× higher than P-mode (minimum)
    - Actual ratio should match sp_ratio_oem (±20% tolerance)
    """

    # Measure actual intensities
    s_intensity = self._measure_intensity_at_position(self.s_position_oem)
    p_intensity = self._measure_intensity_at_position(self.p_position_oem)

    measured_ratio = s_intensity / p_intensity
    expected_ratio = self.sp_ratio_oem

    if measured_ratio < 2.0:
        logger.error("❌ POLARIZER POSITION ERROR DETECTED")
        logger.error(f"   Measured ratio: {measured_ratio:.2f}x (expected: >2.0x)")
        logger.error(f"   Expected ratio: {expected_ratio:.2f}x (from OEM calibration)")
        raise ValueError("Polarizer positions invalid - run auto-polarization")
```

---

## 📊 Your Current Config

**File**: `config/device_config.json`

```json
{
  "oem_calibration": {
    "polarizer_s_position": 165,  ← S-mode servo position
    "polarizer_p_position": 50,   ← P-mode servo position
    "polarizer_sp_ratio": 15.89,  ← Expected S/P intensity ratio
    "calibration_date": "2025-10-19T15:32:00",
    "calibration_method": "window_verification_corrected"
  }
}
```

**Current Problem**:
```
❌ S-mode intensity (62482.2) is NOT significantly higher than P-mode (39512.4)
   Measured ratio: 1.58x (expected: >2.0x)
   OEM positions: S=165, P=50
   Expected ratio: 15.89x (from OEM calibration)
```

**Analysis**:
- Config says S=165 should give 15.89× more light than P=50
- Actual measurement: S gives only 1.58× more light than P
- **This suggests positions are swapped or hardware changed**

---

## 🔧 How to Fix

### **Option 1: GUI Auto-Polarization** (Recommended)

1. In application → **Settings** menu
2. Click **Auto-Polarization**
3. Tool will:
   - Sweep servo through all positions
   - Find actual optimal S and P positions
   - Measure actual S/P ratio
   - **Automatically update `config/device_config.json`**
   - Save new values to `oem_calibration` section

### **Option 2: Manual OEM Calibration Tool**

```powershell
# Run OEM calibration
python utils/oem_calibration_tool.py --serial FLMT09788

# This will:
# 1. Sweep servo positions (10-255)
# 2. Find optimal S and P positions
# 3. Calculate S/P ratio
# 4. Update config/device_config.json automatically
```

### **Option 3: Manual Swap** (Quick Test)

If you suspect positions are just swapped:

```json
{
  "oem_calibration": {
    "polarizer_s_position": 50,   ← Swapped
    "polarizer_p_position": 165,  ← Swapped
    "polarizer_sp_ratio": 15.89,
    "calibration_date": "2025-10-20T20:00:00",
    "calibration_method": "manual_swap"
  }
}
```

Then restart the application.

---

## 📝 Storage Architecture Summary

```
OEM Calibration Tool
    ↓
device_config.json (oem_calibration section)
    ↓
Application Startup
    ↓
SPRCalibrator.__init__() loads positions
    ↓
Calibration validates S/P ratio
    ↓
If invalid → Error (run auto-polarization)
    ↓
Auto-Polarization → Updates device_config.json
    ↓
Application restarts with correct positions
```

---

## 🔍 Where Values Are Used

### **Loading** (Application Start):
- `utils/spr_calibrator.py` → `__init__()` (line ~631)
- `utils/spr_calibrator.py` → `_load_oem_positions()` (line ~790)

### **Validation** (Calibration):
- `utils/spr_calibrator.py` → `_validate_polarizer_positions()` (line ~1900)
- `utils/spr_calibrator.py` → `calibrate()` Step 2 (line ~1950)

### **Saving** (OEM Tool):
- `utils/oem_calibration_tool.py` → `save_profile()` (line ~701)
- `utils/device_configuration.py` → `save()` (writes to file)

### **GUI Settings**:
- `widgets/device_settings.py` → Auto-Polarization feature
- Updates `device_config.json` when calibration succeeds

---

## ✅ Key Takeaways

1. **Single Source of Truth**: `config/device_config.json` → `oem_calibration` section
2. **Loaded at Startup**: Calibrator reads positions during `__init__()`
3. **Validated at Calibration**: Positions verified to produce correct S/P ratio
4. **Auto-Updated by GUI**: Auto-Polarization saves new positions automatically
5. **No Manual Editing Needed**: Use GUI or OEM tool to update safely

---

**Your Issue**: Positions likely swapped or hardware changed since original calibration

**Solution**: Run Auto-Polarization from Settings menu to re-measure and update config
