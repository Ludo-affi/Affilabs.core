# ✅ Smart Calibration QC System - Implementation Complete

## 🎯 What Was Implemented

Implemented S-mode reference spectrum based QC validation system with single source of truth storage in `device_config.json`.

---

## 📋 Changes Made

### 1. DeviceConfiguration Class (`utils/device_configuration.py`)

**Added 4 new methods:**

```python
def save_led_calibration(
    integration_time_ms, s_mode_intensities, p_mode_intensities,
    s_ref_spectra, s_ref_wavelengths
) -> None:
    """Save LED calibration to device_config.json (single source of truth)"""

def load_led_calibration() -> Optional[Dict]:
    """Load LED calibration from device_config.json"""

def get_calibration_age_days() -> Optional[float]:
    """Get age of stored calibration in days"""

def clear_led_calibration() -> None:
    """Clear stored LED calibration data"""
```

**What gets stored:**
- Integration time (ms)
- S-mode LED intensities (all channels)
- P-mode LED intensities (all channels)
- S-ref baseline spectra (~1000 pixels × 4 channels)
- S-ref max intensity (per channel)
- Calibration timestamp

**Storage location:** `config/device_config.json` → `led_calibration` section

---

### 2. SPRCalibrator Class (`utils/spr_calibrator.py`)

**Added 2 new methods:**

```python
def validate_s_ref_qc(
    baseline_config, num_samples=10,
    intensity_threshold=5.0, shape_threshold=0.98
) -> tuple[bool, dict]:
    """
    Quick QC validation using S-mode reference spectra.

    Two-stage validation:
    1. Intensity check: Within 5% of baseline
    2. Shape check: Pearson correlation > 0.98

    Returns: (all_passed, channel_results)
    """

def _log_qc_failure(channel_results, baseline_date) -> None:
    """Log QC failure for preventative maintenance tracking"""
```

**Modified method:**

```python
def run_full_calibration(
    ...,
    force_recalibrate=False  # NEW parameter
) -> tuple[bool, str]:
    """
    Now performs QC validation before full calibration:

    1. Check for stored calibration in device_config.json
    2. If found and not forced:
       - Run QC validation (5-10 seconds)
       - If PASS: Use stored values
       - If FAIL: Run full calibration
    3. After successful calibration:
       - Save to device_config.json (SINGLE SOURCE OF TRUTH)
       - Also save legacy profile for backward compatibility
    """
```

---

## 🔄 Workflow

### Normal Calibration Flow (QC Enabled)

```
User clicks "Calibrate"
    ↓
Check device_config.json for stored calibration
    ↓
┌─────────────────────────────────────────┐
│ FOUND CALIBRATION (7 days old)         │
│                                         │
│ Running QC validation...                │
│ (Requires prism + water)                │
└─────────────────────────────────────────┘
    ↓
Measure fresh S-ref for all channels
    ↓
FOR EACH CHANNEL:
├─ Stage 1: Intensity within 5%? ─────┐
└─ Stage 2: Shape correlation > 0.98? ┘
    ↓
    ├─ ALL PASS
    │      ↓
    │  ✅ Load stored calibration
    │     Use stored LED intensities
    │     Use stored integration time
    │     Time saved: ~2-3 minutes
    │
    └─ ANY FAIL
           ↓
       ❌ Run full calibration
          Log failure to maintenance_log/
          Recalibrate all parameters
          Save new baseline to device_config.json
```

### Force Recalibration Flow

```python
# Skip QC validation entirely
calibrator.run_full_calibration(force_recalibrate=True)
```

---

## 📊 QC Validation Criteria

### Stage 1: Intensity Check (Critical)
**Metric**: Absolute intensity deviation
```python
deviation = |current_max - baseline_max| / baseline_max
PASS if deviation < 5.0%
```

**Detects:**
- LED degradation
- Detector sensitivity drift
- Optical misalignment

---

### Stage 2: Spectral Shape Check (Important)
**Metric**: Pearson correlation of normalized spectra
```python
correlation = pearson(current_normalized, baseline_normalized)
PASS if correlation > 0.98
```

**Detects:**
- LED spectral shift (phosphor degradation)
- Polarizer misalignment (wrong position)
- Prism contamination
- Optical path changes

---

### Combined Logic
```
PASS = (intensity_pass AND shape_pass)

If PASS:
  → Use stored calibration (5-10 seconds)

If FAIL:
  → Run full calibration (2-3 minutes)
  → Log failure for maintenance tracking
```

---

## 📝 Log Files

### QC Failure Logs
**Location:** `generated-files/maintenance_log/qc_failure_YYYYMMDD_HHMMSS.json`

**Example:**
```json
{
  "timestamp": "2025-10-22T15:30:00",
  "baseline_date": "2025-10-15T14:30:00",
  "failure_type": "qc_validation",
  "failed_channels": {
    "B": {
      "intensity_deviation_pct": 5.5,
      "shape_correlation": 0.989,
      "failure_reason": "LED degradation or detector drift detected"
    },
    "C": {
      "intensity_deviation_pct": 1.2,
      "shape_correlation": 0.965,
      "failure_reason": "Spectral shift or polarizer misalignment detected"
    }
  },
  "action_taken": "full_recalibration"
}
```

**Use for:** Preventative maintenance scheduling, LED replacement tracking

---

## 🧪 Testing

### Test Script
Run: `python test_calibration_qc_system.py`

**Tests:**
1. ✅ Save LED calibration to device_config.json
2. ✅ Load calibration from device_config.json
3. ✅ Verify data integrity (numpy arrays, pixel counts)
4. ✅ Check calibration age calculation

---

## 📈 Expected Results

### First Calibration (No QC Available)
```
ℹ️  No stored calibration found - running full calibration
================================================================================
STEP 0: Loading Detector Profile
...
(Full 8-step calibration runs)
...
================================================================================
💾 SAVING CALIBRATION TO DEVICE CONFIG (SINGLE SOURCE OF TRUTH)
================================================================================
✅ LED calibration saved to device_config.json
   This will enable quick QC validation on next calibration
```

### Second Calibration (QC Available - PASS)
```
================================================================================
QUICK CALIBRATION QC CHECK
================================================================================
🔍 Found stored calibration (7.0 days old)
   Integration time: 32 ms
   S-mode LEDs: {'A': 128, 'B': 128, 'C': 128, 'D': 128}
   P-mode LEDs: {'A': 172, 'B': 185, 'C': 192, 'D': 199}

📋 Running QC validation (intensity + shape check)...
   This takes ~10 seconds vs ~2-3 minutes for full calibration

================================================================================
CALIBRATION QC VALIDATION (S-REF BASED)
================================================================================
Baseline date: 2025-10-15T14:30:00 (7.0 days ago)
📋 IMPORTANT: Ensure prism + water in place for validation

Validating Channel A:
  Intensity: 41250 → 41180 (0.2% deviation, ✅ pass)
  Shape: r=0.995 (excellent correlation, ✅ pass)

Validating Channel B:
  Intensity: 42100 → 41950 (0.4% deviation, ✅ pass)
  Shape: r=0.993 (excellent correlation, ✅ pass)

...

================================================================================
✅ QC VALIDATION PASSED - All channels within tolerance
   Using stored calibration values
   Time saved: ~2-3 minutes
================================================================================
================================================================================
✅ QC PASSED - USING STORED CALIBRATION
================================================================================
✅ Calibration loaded from device_config.json
   Time saved: ~2-3 minutes
```

### Third Calibration (QC Available - FAIL)
```
================================================================================
CALIBRATION QC VALIDATION (S-REF BASED)
================================================================================
...

Validating Channel B:
  Intensity: 42100 → 39800 (5.5% deviation, ❌ FAIL)
  ⚠️  LED degradation or detector drift detected

Validating Channel C:
  Intensity: 39800 → 39200 (1.5% deviation, ✅ pass)
  Shape: r=0.965 (poor correlation, ❌ FAIL)
  ⚠️  Spectral shift or polarizer misalignment detected

================================================================================
❌ QC VALIDATION FAILED - Channels: B, C
   Running full recalibration...
================================================================================
📝 QC failure logged to: generated-files/maintenance_log/qc_failure_20251022_153000.json

================================================================================
❌ QC FAILED - RUNNING FULL RECALIBRATION
================================================================================
QC validation detected calibration drift
Proceeding with full 8-step calibration...

(Full calibration runs and saves new baseline)
```

---

## ✅ Single Source of Truth Verification

### Data Flow

**After successful calibration:**
```
SPRCalibrator.run_full_calibration()
    ↓
Step 8: Validation PASSED
    ↓
device_config.save_led_calibration()  ← SINGLE SOURCE OF TRUTH
    ├─ integration_time_ms
    ├─ s_mode_intensities
    ├─ p_mode_intensities
    ├─ s_ref_baseline (4 channels × 1000 pixels)
    └─ s_ref_max_intensity
    ↓
config/device_config.json updated
```

**On next calibration:**
```
SPRCalibrator.run_full_calibration()
    ↓
device_config.load_led_calibration()  ← READ FROM SINGLE SOURCE
    ↓
validate_s_ref_qc(baseline_config)
    ├─ Use stored integration_time_ms
    ├─ Use stored s_mode_intensities
    └─ Compare fresh S-ref to stored baseline
```

**No intermediaries** - device_config.json is the authoritative source.

---

## 🎯 Benefits

### Time Savings
- **Full calibration**: 2-3 minutes
- **QC validation**: 5-10 seconds
- **Savings**: ~95% when QC passes

### Quality Assurance
- ✅ Automatic LED aging detection (5% intensity threshold)
- ✅ Spectral shift detection (0.98 correlation threshold)
- ✅ Polarizer misalignment detection (shape check)
- ✅ Maintenance logging for preventative action

### System Reliability
- ✅ Single source of truth (device_config.json)
- ✅ Traceable calibration history
- ✅ Quantitative pass/fail criteria
- ✅ No manual threshold tuning needed

---

## 📋 Integration Checklist

- [x] ✅ Add LED calibration storage to DeviceConfiguration
- [x] ✅ Implement QC validation in SPRCalibrator
- [x] ✅ Integrate QC into run_full_calibration workflow
- [x] ✅ Save calibration to device_config.json after Step 8
- [x] ✅ Add maintenance logging for QC failures
- [x] ✅ Create test script for verification
- [ ] ⏸️ Test with real hardware (full calibration)
- [ ] ⏸️ Test QC validation (prism + water required)
- [ ] ⏸️ Verify QC passes with recent calibration
- [ ] ⏸️ Verify QC fails with aged LEDs or misalignment

---

## 🚀 Usage Instructions

### For Developers

**Test storage system:**
```bash
python test_calibration_qc_system.py
```

**Run full calibration (with QC):**
```python
from utils.spr_calibrator import SPRCalibrator

calibrator = SPRCalibrator(...)
success, error = calibrator.run_full_calibration(auto_save=True)
```

**Force full calibration (skip QC):**
```python
success, error = calibrator.run_full_calibration(
    force_recalibrate=True,  # Skip QC validation
    auto_save=True
)
```

### For Users

1. **First calibration** (with prism + water):
   - Runs full 8-step calibration
   - Saves baseline to device_config.json
   - Takes 2-3 minutes

2. **Subsequent calibrations** (with prism + water):
   - Runs QC validation first (5-10 seconds)
   - If QC passes: Uses stored calibration
   - If QC fails: Runs full recalibration
   - Logs failures for maintenance tracking

3. **Check calibration status:**
   - Open `config/device_config.json`
   - Look for `led_calibration` section
   - Check `calibration_date` for age

4. **Review QC failures:**
   - Check `generated-files/maintenance_log/`
   - Look for `qc_failure_*.json` files
   - Review failed channels and reasons

---

## 🎉 Implementation Status

**✅ COMPLETE**

All core functionality implemented:
- ✅ Single source of truth storage (device_config.json)
- ✅ S-ref based QC validation (intensity + shape)
- ✅ Automatic QC on calibration start
- ✅ Full calibration fallback on QC failure
- ✅ Maintenance logging
- ✅ Test script

**Ready for hardware testing!**

---

**Date**: 2025-10-22
**Version**: 1.0
**Status**: Implementation Complete - Ready for Testing
