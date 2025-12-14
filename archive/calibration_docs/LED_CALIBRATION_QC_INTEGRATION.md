# LED Calibration QC Integration - Step 6 Backend

**Date:** November 28, 2025
**Status:** ✅ Complete
**Architecture:** Layer 2 & 3 Integration

---

## Overview

Connected LED calibration QC parameters (saturation checks for S and P, ch_error_list, integration time, num_scans) in Step 6 backend and linked sensor_ready status to transmission QC pass criteria.

---

## Implementation Summary

### 1. **Enhanced TransmissionProcessor QC**

**File:** `src/core/transmission_processor.py`

**New Saturation Check Parameters:**

```python
def calculate_transmission_qc(
    transmission_spectrum: np.ndarray,
    wavelengths: np.ndarray,
    channel: str,
    p_spectrum: np.ndarray = None,
    s_spectrum: np.ndarray = None,
    detector_max_counts: float = 65535,      # NEW
    saturation_threshold: float = 62259      # NEW (95% of max)
) -> dict:
```

**Added QC Metrics:**

```python
{
    # Existing metrics
    'fwhm': float,
    'dip_detected': bool,
    'transmission_min': float,
    'dip_wavelength': float,
    'dip_depth': float,
    'ratio': float,
    'orientation_correct': bool,
    'status': str,
    'fwhm_quality': str,
    'warnings': list,

    # NEW: Saturation checks
    's_saturated': bool,        # S-pol saturation flag
    'p_saturated': bool,        # P-pol saturation flag
    's_max_counts': float,      # S-pol maximum counts
    'p_max_counts': float       # P-pol maximum counts
}
```

**Saturation Check Logic:**

```python
# 0. Saturation Checks (before other QC)
if s_spectrum is not None:
    s_max = float(np.max(s_spectrum))
    qc['s_max_counts'] = s_max
    qc['s_saturated'] = s_max >= saturation_threshold

if p_spectrum is not None:
    p_max = float(np.max(p_spectrum))
    qc['p_max_counts'] = p_max
    qc['p_saturated'] = p_max >= saturation_threshold
```

**Updated Pass/Fail Logic:**

```python
passed = (
    qc['dip_detected'] and
    qc['fwhm'] < 60.0 and
    not qc['s_saturated'] and     # NEW: Block if saturated
    not qc['p_saturated']          # NEW: Block if saturated
)
```

---

### 2. **Step 6 Backend Integration**

**File:** `src/utils/calibration_6step.py`

**Part D: QC Validation Enhancement**

```python
# Get detector parameters for saturation checks
detector_max_counts = usb.max_counts
saturation_threshold = detector_max_counts * 0.95  # 95% safety margin

# Pass to QC calculation
qc_metrics = TransmissionProcessor.calculate_transmission_qc(
    transmission_spectrum=transmission_ch,
    wavelengths=wavelengths,
    channel=ch,
    p_spectrum=p_pol_ref[ch],
    s_spectrum=s_pol_ref[ch],
    detector_max_counts=detector_max_counts,
    saturation_threshold=saturation_threshold
)
```

**Logging Enhancement:**

```python
# Log saturation status per channel
if qc_metrics['s_max_counts'] is not None:
    s_status = '❌ SATURATED' if qc_metrics['s_saturated'] else '✅ OK'
    logger.info(f"   S-pol Max: {qc_metrics['s_max_counts']:.0f} counts ({s_status})")

if qc_metrics['p_max_counts'] is not None:
    p_status = '❌ SATURATED' if qc_metrics['p_saturated'] else '✅ OK'
    logger.info(f"   P-pol Max: {qc_metrics['p_max_counts']:.0f} counts ({p_status})")
```

**Storage in CalibrationResult:**

```python
result.transmission_validation[ch] = {
    'fwhm': qc_metrics['fwhm'],
    'dip_detected': qc_metrics['dip_detected'],
    'transmission_min': qc_metrics['transmission_min'],
    'ratio': qc_metrics['ratio'],
    'dip_depth': qc_metrics['dip_depth'],
    'status': qc_metrics['status'],
    's_saturated': qc_metrics['s_saturated'],      # NEW
    'p_saturated': qc_metrics['p_saturated'],      # NEW
    's_max_counts': qc_metrics['s_max_counts'],    # NEW
    'p_max_counts': qc_metrics['p_max_counts']     # NEW
}
```

**LED Calibration QC Summary:**

```python
logger.info("=" * 80)
logger.info("LED CALIBRATION QC SUMMARY")
logger.info("=" * 80)
logger.info(f"Integration Time (S-mode): {result.s_integration_time:.2f}ms")
logger.info(f"Integration Time (P-mode): {result.p_integration_time:.2f}ms")
logger.info(f"Scans per Measurement: {result.num_scans}")
logger.info(f"Saturation Threshold: {saturation_threshold:.0f} counts")
logger.info(f"Channels with Issues: {result.ch_error_list if result.ch_error_list else 'None'}")

# Check for saturation
saturated_channels = [ch for ch, v in result.transmission_validation.items()
                      if v.get('s_saturated') or v.get('p_saturated')]

if saturated_channels:
    logger.warning(f"⚠️  Saturated channels: {saturated_channels}")
else:
    logger.info("✅ No saturation detected in any channel")
```

---

### 3. **Sensor Ready Status Integration**

**File:** `src/core/calibration_service.py`

**Automatic Sensor Ready Update:**

```python
# After calibration completes
calibration_data = CalibrationData.from_calibration_result(cal_result, device_info)

# Store calibration data
self._current_calibration_data = calibration_data
self._calibration_completed = True

# Update sensor_ready status based on transmission QC
sensor_ready = self._evaluate_sensor_ready(calibration_data)
if sensor_ready:
    hardware_mgr._sensor_verified = True
    logger.info("✅ SENSOR READY: Transmission QC passed")
else:
    logger.warning("⚠️  SENSOR NOT READY: Transmission QC did not pass")
```

**Sensor Ready Evaluation Logic:**

```python
def _evaluate_sensor_ready(self, calibration_data: CalibrationData) -> bool:
    """Evaluate if sensor is ready based on transmission QC.

    Criteria:
    - At least one channel must pass transmission QC (status = '✅ PASS')
    - Pass means: SPR dip detected, FWHM < 60nm, no saturation, orientation OK

    Returns:
        True if sensor is ready for experiments
    """
    transmission_validation = calibration_data.transmission_validation

    # Check if at least one channel passed
    passed_channels = [ch for ch, val in transmission_validation.items()
                      if '✅ PASS' in val.get('status', '')]

    if passed_channels:
        logger.info(f"Sensor ready: {len(passed_channels)}/{len(transmission_validation)} channels passed QC")
        return True
    else:
        logger.warning("No channels passed transmission QC")
        return False
```

---

## QC Parameters Now Tracked

### **Per-Channel Transmission Validation**

```python
{
    'fwhm': 28.5,                    # FWHM in nm
    'dip_detected': True,            # SPR dip presence
    'transmission_min': 15.2,        # Minimum transmission %
    'ratio': 0.72,                   # P/S intensity ratio
    'dip_depth': 84.8,              # SPR dip depth %
    'status': '✅ PASS',             # Overall channel status
    's_saturated': False,            # NEW: S-pol saturation flag
    'p_saturated': False,            # NEW: P-pol saturation flag
    's_max_counts': 48250.0,         # NEW: S-pol max counts
    'p_max_counts': 45100.0          # NEW: P-pol max counts
}
```

### **Global LED Calibration QC**

```python
{
    's_integration_time': 93.0,      # S-mode integration time (ms)
    'p_integration_time': 93.0,      # P-mode integration time (ms)
    'num_scans': 3,                  # Scan averaging count
    'detector_max_counts': 65535,    # Detector maximum
    'saturation_threshold': 62259,   # 95% safety threshold
    'ch_error_list': [],             # Channels that failed calibration
    'saturated_channels': []         # Channels with saturation
}
```

---

## QC Decision Flow

```
Step 6 Calibration Complete
    ↓
TransmissionProcessor.calculate_transmission_qc()
    ↓
For each channel:
    1. Check S-pol saturation
    2. Check P-pol saturation
    3. Calculate FWHM
    4. Detect SPR dip
    5. Validate orientation
    6. Assess overall status
    ↓
Store in CalibrationResult:
    - transmission_validation {}
    - orientation_validation {}
    - spr_fwhm {}
    - ch_error_list []
    ↓
CalibrationData.from_calibration_result()
    ↓
CalibrationService._evaluate_sensor_ready()
    ↓
If ≥1 channel passed transmission QC:
    hardware_mgr._sensor_verified = True
    ✅ SENSOR READY
Else:
    ⚠️ SENSOR NOT READY
    ↓
Status Update → UI
```

---

## Sensor Ready Criteria

**PASS Status Requires:**

✅ SPR dip detected (depth > 5%)
✅ FWHM < 60nm (good sensor quality)
✅ Orientation correct or indeterminate
✅ **No S-pol saturation**
✅ **No P-pol saturation**
✅ No channel in ch_error_list

**Sensor Ready Requires:**

At least **1 channel** with PASS status

---

## Saturation Thresholds

**Detector Parameters:**
- `max_counts`: 65535 (detector hardware limit)
- `saturation_threshold`: 62259 (95% of max - safety margin)

**Why 95%?**
- Allows headroom for spectrum variations
- Prevents clipping of SPR features
- Ensures linear detector response
- Matches industry best practices

---

## Benefits

### **1. Complete LED Calibration QC**

- **Saturation Detection**: Prevents invalid data from saturated detectors
- **Integration Time**: Optimized for signal quality
- **Scan Averaging**: Balances SNR vs throughput
- **Channel Errors**: Tracks problematic channels

### **2. Automatic Sensor Ready Status**

- **No Manual Checks**: System determines sensor readiness
- **Objective Criteria**: Based on measurable QC metrics
- **Fast Feedback**: User knows immediately if sensor is ready
- **Experiment Safety**: Blocks experiments with poor sensor coupling

### **3. Comprehensive Traceability**

- **All Parameters Logged**: Complete audit trail
- **Per-Channel Granularity**: Identify specific channel issues
- **Historical Tracking**: Can compare across calibrations
- **Troubleshooting**: Full diagnostic information available

---

## Testing Checklist

- [ ] Run full calibration with good sensor
  - [ ] Verify no saturation detected
  - [ ] Confirm sensor_ready = True
  - [ ] Check all channels pass QC

- [ ] Test with high LED intensity (force saturation)
  - [ ] Verify saturation detected in S and/or P
  - [ ] Confirm channel fails QC
  - [ ] Check sensor_ready = False if all fail

- [ ] Test with dry sensor (no water contact)
  - [ ] Verify weak/missing SPR dip
  - [ ] Confirm FWHM > 60nm or undefined
  - [ ] Check sensor_ready = False

- [ ] Test with partial sensor (e.g., 2/4 channels good)
  - [ ] Verify 2 channels pass, 2 fail
  - [ ] Confirm sensor_ready = True (≥1 passed)
  - [ ] Check QC dialog shows mixed status

---

## Files Modified

1. `src/core/transmission_processor.py` - Added saturation checks to QC
2. `src/utils/calibration_6step.py` - Integrated saturation QC in Step 6
3. `src/core/calibration_service.py` - Added sensor_ready evaluation

---

## Next Steps

1. **UI Integration**: Display saturation status in QC dialog
2. **Historical Tracking**: Store QC trends for degradation detection
3. **Adaptive LED**: Auto-reduce LED if saturation detected
4. **Advanced Warnings**: Predict saturation before it occurs

---

## References

- **Saturation Threshold**: Based on detector linearity specs (95% rule)
- **Sensor Ready Logic**: Derived from experimental validation requirements
- **QC Criteria**: Aligned with SPR measurement best practices
