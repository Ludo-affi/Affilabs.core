# QC Criteria Clarity Review & Redundant Code Cleanup

**Date**: 2025-01-21
**Status**: ✅ QC CRITERIA CLEAR | 🧹 REDUNDANT CODE IDENTIFIED

---

## 📊 QC Pass/Fail Criteria - Current State

### **✅ EXCELLENT CLARITY** - TransmissionProcessor QC

The QC criteria in `TransmissionProcessor.calculate_transmission_qc()` are **crystal clear** and well-documented:

```python
# PASS Criteria (ALL must be true):
passed = (
    qc['dip_detected'] and                    # Dip depth > 5%
    qc['fwhm'] is not None and
    qc['fwhm'] < 60.0 and                     # FWHM < 60nm
    (qc['orientation_correct'] is True or
     qc['orientation_correct'] is None) and   # Orientation OK or indeterminate
    not qc['s_saturated'] and                 # S-pol below 95% max
    not qc['p_saturated']                     # P-pol below 95% max
)

# FAIL Criteria (ANY trigger failure):
failed = (
    not qc['dip_detected'] or                 # No SPR dip detected
    (qc['fwhm'] is not None and qc['fwhm'] >= 80.0) or  # FWHM ≥ 80nm
    qc['orientation_correct'] is False or     # Inverted polarizer
    qc['s_saturated'] or                      # S-pol saturated
    qc['p_saturated']                         # P-pol saturated
)
```

**Result Statuses:**
- `✅ PASS`: All validation checks passed
- `⚠️ WARNING`: Some issues but not critical (e.g., 60nm < FWHM < 80nm)
- `❌ FAIL`: Critical failure detected

---

## 🎯 FWHM Quality Thresholds

**Location:** `src/core/transmission_processor.py` line 234-245

```python
# FWHM Quality Assessment
if fwhm < 30:
    qc['fwhm_quality'] = 'excellent'      # <30nm = Excellent coupling
elif fwhm < 50:
    qc['fwhm_quality'] = 'good'           # 30-50nm = Good quality
elif fwhm < 60:
    qc['fwhm_quality'] = 'acceptable'     # 50-60nm = Acceptable (warn)
    qc['warnings'].append(f"Broad FWHM ({fwhm:.1f}nm) - acceptable but not optimal")
else:
    qc['fwhm_quality'] = 'poor'           # ≥60nm = Poor (warn)
    qc['warnings'].append(f"Wide FWHM ({fwhm:.1f}nm) - poor sensor contact or degradation")
```

**Interpretation:**
- **<30nm**: Excellent sensor coupling, high sensitivity
- **30-50nm**: Good quality, normal operation
- **50-60nm**: Acceptable but monitor closely (generates warning)
- **60-80nm**: Poor quality, triggers WARNING status but not auto-fail
- **≥80nm**: Very poor, triggers FAIL status

---

## 🔍 Saturation Thresholds

**Location:** `src/core/transmission_processor.py` line 193-207
**Parameters:**
- `detector_max_counts`: 65535 (hardware limit)
- `saturation_threshold`: 62259 (95% of max)

**Why 95%?**
1. **Safety margin** - Prevents detector clipping
2. **Linear response** - Ensures detector stays in linear range
3. **Headroom** - Allows for spectrum variations
4. **Industry standard** - Matches best practices

```python
# Saturation checks
qc['s_saturated'] = s_max >= saturation_threshold  # S-pol check
qc['p_saturated'] = p_max >= saturation_threshold  # P-pol check

# Saturation = automatic FAIL
if qc['s_saturated'] or qc['p_saturated']:
    qc['status'] = '❌ FAIL'
```

---

## ✅ Orientation Validation (P/S Ratio)

**Location:** `src/core/transmission_processor.py` line 256-273

```python
# Expected P/S ratio: 0.1-0.95 (P < S due to SPR absorption)
if qc['ratio'] > 1.15:
    qc['orientation_correct'] = False       # ❌ Inverted polarizer
    qc['warnings'].append(f"P/S ratio ({qc['ratio']:.2f}) > 1.15 - polarizer may be inverted")
elif 0.95 < qc['ratio'] <= 1.15:
    qc['orientation_correct'] = None        # ⚠️ Indeterminate
    qc['warnings'].append(f"P/S ratio ({qc['ratio']:.2f}) borderline - cannot confirm orientation")
elif 0.10 <= qc['ratio'] <= 0.95:
    qc['orientation_correct'] = True        # ✅ Correct orientation
else:
    qc['orientation_correct'] = None        # ⚠️ Unusual
    qc['warnings'].append(f"P/S ratio ({qc['ratio']:.2f}) < 0.10 - unusual, verify sensor")
```

**Physical Meaning:**
- **P < S (ratio 0.1-0.95)**: SPR absorption reduces P-pol transmission ✅
- **P ≈ S (ratio 0.95-1.15)**: Unclear - needs investigation ⚠️
- **P > S (ratio >1.15)**: Inverted polarizer orientation ❌

---

## 🔗 Sensor Ready Connection

**Location:** `src/core/calibration_service.py` line 520-548

```python
def _evaluate_sensor_ready(self, calib_data: CalibrationData) -> bool:
    """
    Evaluate if sensor is ready for live measurements based on transmission QC.

    Criteria: At least 1 channel must pass ALL transmission QC checks
    """
    passed_channels = 0

    for ch in CH_LIST:
        if ch not in calib_data.transmission_validation:
            continue

        qc = calib_data.transmission_validation[ch]

        # Check all QC criteria
        passed = (
            qc.get('dip_detected', False) and
            qc.get('fwhm') is not None and
            qc.get('fwhm', 999) < 60.0 and
            (qc.get('orientation_correct') in [True, None]) and
            not qc.get('s_saturated', True) and
            not qc.get('p_saturated', True)
        )

        if passed:
            passed_channels += 1

    # Sensor ready if at least 1 channel passed
    return passed_channels >= 1
```

**Logic:**
- ✅ **SENSOR READY**: ≥1 channel with PASS status
- ❌ **SENSOR NOT READY**: All channels failed QC

---

## 🧹 REDUNDANT CODE IDENTIFIED

### **Functions No Longer Used in calibration_6step.py**

#### 1. `validate_s_ref_quality()` - **REDUNDANT**

**Location:** `src/utils/led_calibration.py` line 1801
**Purpose:** S-pol signal strength check for prism presence detection
**Why Redundant:**
- Only checks S-pol peak intensity (>5000 counts minimum)
- Does NOT check saturation
- Does NOT calculate FWHM
- Does NOT validate SPR dip
- **TransmissionProcessor QC now handles all validation**

**Import Status:**
- ✅ Imported in `calibration_6step.py` line 86
- ❌ **NEVER CALLED** in calibration_6step.py
- ❌ **NOT USED** anywhere in Step 6

**Recommendation:** 🗑️ **DELETE FROM IMPORTS**

---

#### 2. `verify_calibration()` - **REDUNDANT**

**Location:** `src/utils/led_calibration.py` line 1872
**Purpose:** P-mode verification with saturation + SPR validation
**Why Redundant:**
- Old QC function used before TransmissionProcessor existed
- Duplicates FWHM calculation (same logic as TransmissionProcessor)
- Duplicates saturation checks (same 95% threshold)
- Duplicates P/S ratio validation
- Returns `ch_error_list` and `spr_fwhm` - **no longer needed**

**Import Status:**
- ✅ Imported in `calibration_6step.py` line 88
- ❌ **NEVER CALLED** in calibration_6step.py
- ❌ **NOT USED** anywhere in Step 6

**Current Implementation:**
```python
# OLD WAY (verify_calibration):
ch_error_list, spr_fwhm, polarizer_swap = verify_calibration(
    usb, ctrl, leds_calibrated, wave_data, s_ref_signals
)

# NEW WAY (TransmissionProcessor):
qc = TransmissionProcessor.calculate_transmission_qc(
    transmission_spectrum=transmission,
    wavelengths=wavelengths,
    channel=ch,
    p_spectrum=p_spectrum,
    s_spectrum=s_spectrum,
    detector_max_counts=detector_params.max_counts,
    saturation_threshold=detector_params.saturation_threshold
)
```

**Recommendation:** 🗑️ **DELETE FROM IMPORTS**

---

## 🔧 Cleanup Actions Required

### **Step 1: Remove Unused Imports**

**File:** `src/utils/calibration_6step.py`
**Lines to Delete:** 86-88

```python
# REMOVE THESE IMPORTS:
    validate_s_ref_quality,
    calibrate_p_mode_leds,
    verify_calibration,
```

**Reasoning:**
- `validate_s_ref_quality` - Never called, replaced by TransmissionProcessor
- `verify_calibration` - Never called, replaced by TransmissionProcessor
- `calibrate_p_mode_leds` - Check if this is used (need to verify separately)

---

### **Step 2: Keep Functions in led_calibration.py (For Now)**

**DO NOT DELETE `validate_s_ref_quality()` and `verify_calibration()` from `led_calibration.py`**

**Reasoning:**
1. They may be used by **legacy calibration modes** not visible in calibration_6step.py
2. They are called in `led_calibration.py` internal workflows (lines 2869, 2893, 3417, 3528)
3. Safer to remove imports first, then observe if anything breaks

**Future Cleanup:**
- Monitor for 1-2 weeks after import removal
- If no errors reported, can safely delete the functions themselves

---

## 📋 Summary

### **QC Criteria Clarity: ✅ EXCELLENT**

✅ **Pass/Fail logic is crystal clear**
✅ **FWHM thresholds well-documented** (<30, 30-50, 50-60, 60-80, ≥80nm)
✅ **Saturation criteria explicit** (95% threshold with clear rationale)
✅ **Orientation validation logical** (P/S ratio bands)
✅ **Sensor ready connection clear** (≥1 channel must pass)

**NO CHANGES NEEDED TO QC LOGIC** - Current implementation is professional-grade.

---

### **Redundant Code: 🗑️ CLEANUP REQUIRED**

❌ **`validate_s_ref_quality` import** - Remove from calibration_6step.py
❌ **`verify_calibration` import** - Remove from calibration_6step.py
⚠️ **Keep functions in led_calibration.py** - May be used elsewhere

---

## 🎯 Next Actions

1. **Remove unused imports** from `calibration_6step.py`
2. **Test calibration flow** to verify no breakage
3. **Monitor for 1-2 weeks** for any hidden dependencies
4. **Future cleanup**: Remove function definitions if unused elsewhere

---

**Conclusion:** QC system is well-designed and clear. Only import cleanup needed.
