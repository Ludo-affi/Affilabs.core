# QC Layer Consolidation - Step 6 Transmission Processing

**Date:** November 28, 2025
**Status:** ✅ Complete
**Architecture:** Layer 2 (Core Business Logic)

---

## Overview

Consolidated all transmission QC parameters at the output of Step 6 transmission processing. Created a single source of truth for QC validation that is used by both calibration and live acquisition.

---

## Implementation Summary

### 1. **TransmissionProcessor Enhancement**

**File:** `src/core/transmission_processor.py`

Added `calculate_transmission_qc()` method that consolidates all QC metrics:

```python
@staticmethod
def calculate_transmission_qc(
    transmission_spectrum: np.ndarray,
    wavelengths: np.ndarray,
    channel: str,
    p_spectrum: np.ndarray = None,
    s_spectrum: np.ndarray = None
) -> dict
```

**Consolidated QC Parameters:**

1. **FWHM (Full Width at Half Maximum)**
   - Calculated from transmission dip
   - Quality categories: excellent (<30nm), good (30-50nm), acceptable (50-60nm), poor (>60nm)

2. **SPR Dip Detection**
   - `dip_detected`: Boolean (depth > 5%)
   - `transmission_min`: Minimum transmission %
   - `dip_wavelength`: Wavelength at SPR minimum
   - `dip_depth`: Depth of SPR dip (100 - min_transmission)

3. **Orientation Validation** (if P/S spectra provided)
   - `ratio`: P/S intensity ratio in SPR region
   - `orientation_correct`: Boolean validation
     - True: ratio 0.10-0.95 (correct orientation)
     - False: ratio > 1.15 (inverted)
     - None: indeterminate (0.95-1.15)

4. **Overall Status**
   - `status`: '✅ PASS' / '⚠️ WARNING' / '❌ FAIL'
   - `fwhm_quality`: Quality category string
   - `warnings`: List of diagnostic warnings

### 2. **Step 6 Integration**

**File:** `src/utils/calibration_6step.py`

**Changes in Part D (QC Validation):**

- Removed inline QC calculations
- Call `TransmissionProcessor.calculate_transmission_qc()` for each channel
- Store results in three dictionaries:
  - `result.orientation_validation` - For orientation checks
  - `result.transmission_validation` - For FWHM and SPR metrics
  - `result.spr_fwhm` - For display compatibility

**Data Flow:**
```
Transmission Spectra (Part C)
    ↓
TransmissionProcessor.calculate_transmission_qc()
    ↓
Consolidated QC Metrics (per channel)
    ↓
Store in CalibrationResult:
  - orientation_validation {}
  - transmission_validation {}
  - spr_fwhm {}
    ↓
CalibrationData.from_calibration_result()
    ↓
CalibrationData.to_dict()
    ↓
QC Dialog Display
```

### 3. **Metadata Traceability**

**File:** `src/core/calibration_data.py`

**Enhanced Metadata Fields:**

```python
@dataclass(frozen=True)
class CalibrationData:
    # Device metadata
    device_type: str = "Unknown"
    detector_serial: str = "N/A"
    detector_number: str = "N/A"  # NEW: Added explicit field
    firmware_version: str = "N/A"
    calibration_timestamp: str = field(default_factory=...)
    calibration_method: str = "full_6step"
```

**Metadata Flow:**

1. **Capture in CalibrationService** (`src/core/calibration_service.py`):
   ```python
   device_info = {
       'device_type': type(ctrl).__name__,
       'detector_serial': device_serial or 'N/A',
       'firmware_version': getattr(ctrl, 'version', 'N/A'),
       'pre_led_delay_ms': pre_led_delay_ms,
       'post_led_delay_ms': post_led_delay_ms
   }
   ```

2. **Store in CalibrationData** via `from_calibration_result()`

3. **Export via to_dict()** for QC dialog display

---

## QC Parameters Tracked

### **Orientation Validation** (per channel)
```python
{
    'passed': bool | None,           # True/False/Indeterminate
    'reason': str,                   # Diagnostic reason or FWHM
    'confidence': float,             # Confidence score (0-1)
    'peak_wl': float,                # SPR wavelength (nm)
    'peak_value': float              # Transmission at SPR (%)
}
```

### **Transmission Validation** (per channel)
```python
{
    'fwhm': float | None,            # FWHM in nm
    'dip_detected': bool,            # SPR dip presence
    'transmission_min': float,       # Minimum transmission %
    'ratio': float | None,           # P/S intensity ratio
    'dip_depth': float,              # SPR dip depth (%)
    'status': str                    # '✅ PASS' / '⚠️ WARNING' / '❌ FAIL'
}
```

### **SPR FWHM** (per channel)
```python
{
    'a': 25.3,  # FWHM in nm
    'b': 28.1,
    'c': 31.5,
    'd': 27.8
}
```

### **Metadata** (global)
- `device_type`: Controller class name
- `detector_serial`: Spectrometer serial number
- `detector_number`: Detector identifier
- `firmware_version`: Controller firmware version
- `calibration_timestamp`: ISO format timestamp
- `integration_time`: S-mode integration time (ms)
- `p_integration_time`: P-mode integration time (ms)
- `num_scans`: Scan averaging count

---

## QC Decision Logic

### **FWHM Quality Grades**
- **Excellent**: <30nm - Perfect sensor coupling
- **Good**: 30-50nm - Good sensor quality
- **Acceptable**: 50-60nm - Usable but not optimal
- **Poor**: >60nm - Poor contact or degradation

### **Orientation Detection**
- **P/S Ratio < 0.10**: Unusual, verify sensor
- **P/S Ratio 0.10-0.95**: ✅ Correct orientation
- **P/S Ratio 0.95-1.15**: ⚠️ Indeterminate
- **P/S Ratio > 1.15**: ❌ Polarizer inverted

### **SPR Dip Quality**
- **Depth > 5%**: ✅ SPR detected
- **Depth < 5%**: ❌ Weak/missing SPR (check hydration)

### **Overall Pass Criteria**
```python
PASS = (
    dip_detected AND
    fwhm < 60.0 AND
    (orientation_correct OR indeterminate)
)
```

---

## Architecture Benefits

### **Single Source of Truth**
- All QC logic centralized in `TransmissionProcessor`
- No duplicate calculations
- Consistent metrics across calibration and live acquisition

### **Layer Separation**
- **Layer 2 (Core)**: TransmissionProcessor handles calculations
- **Layer 3 (Services)**: CalibrationService orchestrates flow
- **Layer 4 (UI)**: QC Dialog displays results

### **Traceability**
- All metadata captured at calibration time
- Immutable CalibrationData ensures data integrity
- Complete audit trail for troubleshooting

---

## Testing Checklist

- [ ] Run full 6-step calibration
- [ ] Verify QC dialog displays:
  - ✅ Orientation validation table (per channel)
  - ✅ Transmission validation table (per channel with FWHM, dip detection, P/S ratio)
  - ✅ Metadata section (timestamp, device, firmware)
- [ ] Check that FWHM values are reasonable (15-50nm for good sensors)
- [ ] Verify orientation validation matches polarizer position
- [ ] Confirm transmission dip detected for hydrated sensor
- [ ] Test with dry sensor - should show warnings

---

## Files Modified

1. `src/core/transmission_processor.py` - Added `calculate_transmission_qc()`
2. `src/utils/calibration_6step.py` - Integrated consolidated QC in Step 6
3. `src/core/calibration_data.py` - Enhanced metadata fields
4. `src/widgets/calibration_qc_dialog.py` - Already configured to display QC data

---

## Next Steps

1. **Validation Testing**: Run calibration and verify QC metrics
2. **Documentation**: Update user manual with QC interpretation guide
3. **Historical Tracking**: Consider storing QC trends over time
4. **Automated Alerts**: Add threshold-based warnings for degradation

---

## References

- **FWHM Thresholds**: Based on empirical SPR sensor data
- **Orientation Logic**: Derived from `spr_signal_processing.validate_sp_orientation()`
- **Metadata Fields**: Aligned with `device_configuration.py` schema
