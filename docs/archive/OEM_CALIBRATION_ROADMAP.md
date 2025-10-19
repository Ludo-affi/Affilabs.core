# OEM Calibration Roadmap

## Overview

This document outlines the planned OEM-specific calibration features that need to be implemented for manufacturing and initial device setup. These are **device-specific characterizations** that happen once during manufacturing, not during normal user calibration.

---

## 1. Full Polarization Calibration (Servo Position Finding)

### Purpose
Find optimal servo positions for S-mode and P-mode polarization states when installing a new polarizer with unknown orientation.

### Current Status
- ✅ **Validation implemented**: `validate_polarizer_positions()` verifies existing positions
- ✅ **Auto-polarization exists**: `auto_polarize()` method (lines ~3930-3995 in `spr_calibrator.py`)
- ⏳ **OEM integration needed**: Move to OEM calibration tool

### What It Does
1. Sweeps servo through angle range (10-170°)
2. Measures light transmission at each position
3. Uses peak detection to find optimal S and P positions
4. Labels positions in firmware (currently may be inverted)

### Current Implementation Location
```python
# File: utils/spr_calibrator.py
# Method: auto_polarize() (lines ~3930-3995)
```

### Planned Changes for OEM Version

**Move to OEM Calibration Tool**:
- Remove from main calibration sequence (already done - it's optional)
- Create dedicated OEM calibration script/tool
- Store results in device-specific firmware/EEPROM
- Include label verification (check which position is actually S vs P)

**Integration Point**: Same location as afterglow characterization (see Section 2)

---

## 2. Afterglow Characterization (LED-Dependent Dark Noise)

### Purpose
Characterize LED-specific afterglow contamination for each channel to enable accurate dark noise correction.

### Current Status
- ✅ **Correction implemented**: Afterglow correction in Step 5 & Step 7
- ✅ **Generic correction**: Uses hardcoded 25-count approximation
- ⏳ **Device-specific characterization needed**: Measure actual afterglow per device

### What It Does
1. For each LED channel:
   - Turn LED ON at calibrated intensity
   - Turn LED OFF
   - Measure residual signal decay over time
2. Store channel-specific afterglow profiles
3. Use during calibration for accurate dark correction

### Planned Implementation

**Characterization Process**:
```python
def characterize_afterglow(self, channel: str) -> dict:
    """Measure LED-specific afterglow decay profile.

    Returns:
        dict: {
            'channel': str,
            'peak_contamination': float,  # counts
            'decay_time_ms': float,       # time to baseline
            'decay_curve': np.ndarray     # time series
        }
    """
    # 1. Activate LED at standard intensity
    # 2. Turn OFF and measure decay
    # 3. Fit exponential decay model
    # 4. Store device-specific profile
```

**Storage**: Device-specific JSON/EEPROM (same as polarizer positions)

---

## 3. OEM Calibration Tool Architecture

### Proposed Structure

**Location**: `utils/oem_calibration_tool.py` (new file)

**Purpose**: One-time manufacturing calibration for device-specific parameters

**Features**:
1. **Full Polarization Calibration**
   - Servo position sweep
   - Peak detection
   - Label verification (S vs P)
   - Store positions in firmware

2. **Afterglow Characterization**
   - Per-channel decay measurement
   - Exponential fit
   - Store correction profiles

3. **Device Profile Creation**
   - Detector model
   - Serial number
   - Calibration date
   - Afterglow profiles
   - Polarizer positions (with verified labels)

### Storage Location

**Device-Specific Calibration Data**:
```
calibration_data/
├── device_profiles/
│   ├── serial_12345.json       # Device-specific OEM calibration
│   └── serial_67890.json
└── afterglow_profiles/
    ├── serial_12345_ch_a.npy   # Decay curves
    ├── serial_12345_ch_b.npy
    ├── serial_12345_ch_c.npy
    └── serial_12345_ch_d.npy
```

**Device Profile JSON**:
```json
{
  "device_serial": "12345",
  "device_type": "PicoP4SPR",
  "calibration_date": "2025-10-19T14:30:00",
  "detector_model": "Hamamatsu S11639",
  "polarizer": {
    "s_position": 100,
    "p_position": 10,
    "verified": true,
    "notes": "Hardware labels inverted (10° labeled S is actually P)"
  },
  "afterglow": {
    "channel_a": {
      "peak_contamination_counts": 28.5,
      "decay_time_ms": 150,
      "profile_file": "serial_12345_ch_a.npy"
    },
    "channel_b": { /* ... */ },
    "channel_c": { /* ... */ },
    "channel_d": { /* ... */ }
  },
  "oem_calibration_version": "1.0"
}
```

---

## 4. Integration with User Calibration

### Current Flow (User Calibration)
```
Step 1: Dark noise baseline
Step 2: Wavelength range
Step 2B: Polarizer VALIDATION ← Uses OEM positions
Step 3: Weakest channel
Step 4: Integration time
Step 5: Dark noise (uses OEM afterglow correction)
Step 6: LED calibration
Step 7: Reference signals (uses OEM afterglow correction)
Step 8: Validation
```

### OEM Data Usage

**Polarizer Positions** (Step 2B):
- Load from device profile
- Validate (don't re-find)
- If validation fails → user runs OEM tool or contacts support

**Afterglow Correction** (Steps 5 & 7):
- Load channel-specific profiles
- Apply during dark noise measurement
- Much more accurate than generic 25-count correction

---

## 5. Implementation Phases

### Phase 1: Extract Existing Code (READY NOW)
- [x] Move `auto_polarize()` to OEM tool
- [ ] Create `oem_calibration_tool.py`
- [ ] Implement basic polarization sweep
- [ ] Add label verification

### Phase 2: Afterglow Characterization (NEXT)
- [ ] Implement decay measurement
- [ ] Exponential fitting
- [ ] Per-channel profiling
- [ ] Storage system

### Phase 3: Device Profile System (INTEGRATION)
- [ ] Profile JSON schema
- [ ] Load/save functionality
- [ ] Serial number tracking
- [ ] Profile validation

### Phase 4: User Calibration Integration (FINAL)
- [ ] Auto-load device profile at startup
- [ ] Use OEM polarizer positions in Step 2B
- [ ] Use OEM afterglow profiles in Steps 5 & 7
- [ ] Fallback to generic values if profile missing

---

## 6. User Experience

### Manufacturing (OEM Tool)
```
1. Connect fresh device
2. Run: python oem_calibration_tool.py --serial 12345
3. Tool executes:
   - Full polarization sweep
   - Afterglow characterization (4 channels)
   - Creates device profile
4. Profile stored in device memory
5. Device ready for shipment
```

### End User (Normal Calibration)
```
1. Run: python run_app.py
2. Click "Calibrate"
3. Software:
   - Auto-loads device profile (if available)
   - Uses OEM polarizer positions (validation only)
   - Uses OEM afterglow correction (accurate)
4. Calibration completes faster and more accurately
```

---

## 7. Migration Plan

### Existing Devices (No OEM Profile)
**Fallback Behavior**:
- Use current polarizer validation (assumes positions known)
- Use generic 25-count afterglow correction
- Optionally: User can run OEM tool to create profile

### New Devices (With OEM Profile)
**Enhanced Behavior**:
- Auto-load polarizer positions
- Use device-specific afterglow correction
- Faster, more accurate calibration

---

## 8. File Structure (Planned)

```
control-3.2.9/
├── utils/
│   ├── spr_calibrator.py           # User calibration (current)
│   ├── oem_calibration_tool.py     # NEW: OEM tool
│   └── device_profile_manager.py   # NEW: Profile loading
├── calibration_data/
│   ├── device_profiles/            # NEW: OEM profiles
│   └── afterglow_profiles/         # NEW: Decay curves
└── OEM_CALIBRATION_GUIDE.md        # NEW: OEM tool usage
```

---

## 9. Code References

### Current Auto-Polarization Code
**File**: `utils/spr_calibrator.py`
**Method**: `auto_polarize()` (lines ~3930-3995)
**Dependencies**:
- `scipy.signal.find_peaks`
- `scipy.signal.peak_prominences`
- `scipy.signal.peak_widths`

### Current Afterglow Correction
**File**: `utils/spr_calibrator.py`
**Methods**:
- `_apply_afterglow_correction_to_references()` (lines ~3015-3105)
- Generic 25-count correction in Step 5 (lines ~2895-2940)

**Enhancement Needed**: Replace generic value with device-specific profiles

---

## 10. Next Steps

### Immediate (This Session)
- ✅ Document OEM roadmap
- ✅ Identify integration points
- ✅ Plan file structure

### Short Term (Next Development Cycle)
- [ ] Create `oem_calibration_tool.py` skeleton
- [ ] Implement polarization sweep with label verification
- [ ] Test on current hardware

### Medium Term (Before Production)
- [ ] Implement afterglow characterization
- [ ] Create device profile system
- [ ] Add profile loading to main calibration
- [ ] Test with multiple devices

### Long Term (Production)
- [ ] Manufacturing documentation
- [ ] OEM tool GUI (optional)
- [ ] Profile validation/QA tools
- [ ] Support team training

---

## Notes

- **Current polarizer fix** (label swap in software) is a **workaround** for devices without OEM calibration
- **OEM tool** will properly characterize and **label** positions during manufacturing
- **Afterglow correction** will be much more accurate with device-specific profiles
- Both features belong in the **same OEM calibration workflow** (one-time setup)

---

**Status**: Planning phase - ready to implement when needed for OEM production

**Contact**: Documented by GitHub Copilot based on user requirements (2025-10-19)
