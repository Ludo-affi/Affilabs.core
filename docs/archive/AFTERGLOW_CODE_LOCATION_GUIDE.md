# Afterglow Code Location Guide

## Overview

This document maps all afterglow-related code in the control-3.2.9 software, showing where characterization, correction, and testing reside.

---

## 1. Core Afterglow Correction Module

### File: `afterglow_correction.py` (Root Directory)

**Purpose**: Passive correction module - loads and applies pre-computed optical calibration data

**Key Class**: `AfterglowCorrection`

**What It Does**:
- Loads optical calibration JSON files (τ tables per channel)
- Interpolates correction parameters based on integration time
- Applies exponential decay correction to measurements
- Uses physics model: `signal(t) = baseline + A × exp(-t/τ)`

**Key Methods**:
```python
AfterglowCorrection(calibration_file)  # Load optical calibration
calculate_correction(channel, integration_time_ms, delay_ms)  # Get correction value
apply_correction(spectrum, last_channel, integration_time_ms)  # Correct spectrum
correct_spectrum(spectrum, last_channel, integration_time_ms)  # Wrapper method
```

**Integration Time Dependency**:
- τ (decay constant) varies with integration time
- Typical range: τ ∈ [15, 25]ms for integration times 10-80ms
- Uses cubic spline interpolation for smooth τ(int_time) function

**Status**: ✅ Production-ready (passive correction only)

**Location**: Root directory (imported by `spr_calibrator.py` and `spr_data_acquisition.py`)

---

## 2. Integration in Calibration (SPRCalibrator)

### File: `utils/spr_calibrator.py`

**Lines**: 624-652, 2890-2945, 3055-3090

### Initialization (Lines 624-652)

**What Happens**:
1. Loads device configuration
2. Checks if optical calibration file exists
3. Creates `AfterglowCorrection` instance if enabled
4. Sets `afterglow_correction_enabled` flag

**Code**:
```python
# Line 625-627
self.afterglow_correction = None
self.afterglow_correction_enabled = False

# Line 631-638
if optical_cal_file and afterglow_enabled:
    from afterglow_correction import AfterglowCorrection
    self.afterglow_correction = AfterglowCorrection(optical_cal_file)
    self.afterglow_correction_enabled = True
```

**Configuration Source**: `config/device_config.json`
```json
{
  "optical_calibration_file": "optical_calibration/system_FLMT09788_20251011.json",
  "afterglow_correction_enabled": true
}
```

### Step 5: Dark Noise Re-measurement (Lines 2890-2945)

**What Happens**:
1. Measure dark noise after LED calibration (Step 4)
2. Apply afterglow correction if available
3. Compare corrected vs uncorrected dark noise
4. Log correction effectiveness

**Code**:
```python
# Line 2895-2910
correction_value = self.afterglow_correction.calculate_correction(
    previous_channel=self._last_active_channel,
    integration_time_ms=integration_time_ms,
    delay_ms=settle_delay * 1000
)
full_spectrum_dark_noise = full_spectrum_dark_noise - correction_value
```

**Correction Type**: Uniform scalar subtraction (afterglow is spectrally flat)

**Log Output**:
```
✨ Afterglow correction applied to dark noise:
   Previous channel: A
   Correction: 25.3 counts removed
   Dark noise mean: 115.2 → 89.9 counts
   Correction effectiveness: 78.5%
```

### Step 7: Reference Signal Measurement (Lines 3055-3090)

**What Happens**:
1. Measure reference signals for all channels (S-mode)
2. Measure dark noise after all channels
3. Apply afterglow correction to dark noise
4. Subtract corrected dark from all reference signals

**Code**:
```python
# Line 3063-3069
corrected_dark = self.afterglow_correction.correct_spectrum(
    spectrum=dark_spectrum,
    last_active_channel=last_active_ch,
    integration_time_ms=self.state.integration * 1000
)
```

**Correction Type**: Full spectrum correction (spectral method for compatibility)

**Purpose**: Remove afterglow contamination from reference signals

---

## 3. Characterization Scripts (Testing/OEM)

### 3A. Integration Time Aware Model

**File**: `led_afterglow_integration_time_model.py` (Root Directory)

**Purpose**: Full OEM characterization - measures τ(integration_time) for all channels

**What It Does**:
1. Tests all 4 channels (A, B, C, D)
2. Sweeps through multiple integration times (10-80ms)
3. Measures exponential decay for each condition
4. Builds lookup tables: τ(integration_time) per channel
5. Saves optical calibration JSON file

**Runtime**: 40-50 minutes (4 channels × 5 integration times × 5 cycles)

**Output**: `optical_calibration/system_SERIALNUMBER_DATE.json`

**Key Functions**:
```python
exponential_decay(t, baseline, amplitude, tau)  # Physics model
characterize_channel(channel, integration_times)  # Full sweep
build_interpolation_tables()  # Create τ(int_time) functions
save_optical_calibration(output_file)  # Store JSON
```

**Status**: ⏳ OEM tool (requires hardware and time)

**Usage**:
```bash
python led_afterglow_integration_time_model.py
```

### 3B. Validation Script

**File**: `tests/led_afterglow_validation.py`

**Purpose**: Validate afterglow correction accuracy

**What It Does**:
1. Tests decay at multiple integration times
2. Tests rapid multi-channel cycling (cumulative buildup)
3. Applies correction to live data
4. Validates correction accuracy vs ground truth

**Runtime**: ~20 minutes

**Output**: Validation report JSON + plots

**Key Tests**:
```python
test_integration_time_dependency()  # Verify τ variation
test_rapid_cycling()  # Worst-case cumulative afterglow
validate_correction_accuracy()  # Apply and measure error
```

**Status**: ✅ Ready for validation runs

**Usage**:
```bash
python tests/led_afterglow_validation.py
```

### 3C. Basic Model (Deprecated)

**File**: `led_afterglow_model.py` (Root Directory)

**Purpose**: Original single-integration-time characterization

**Status**: ⚠️ Superseded by `led_afterglow_integration_time_model.py`

**Reason**: Doesn't account for τ(integration_time) dependency

---

## 4. Integration in Live Data Acquisition

### File: `utils/spr_data_acquisition.py` (Expected)

**Purpose**: Apply afterglow correction during live SPR measurements

**Expected Integration**:
```python
class SPRDataAcquisition:
    def __init__(self, ...):
        from afterglow_correction import AfterglowCorrection
        self.afterglow_correction = AfterglowCorrection(
            'optical_calibration/system_FLMT09788_20251011.json'
        )

    def acquire_measurement(self, channel):
        raw_signal = self.usb.read_spectrum()

        # Apply afterglow correction
        if self._last_channel is not None:
            corrected_signal = self.afterglow_correction.apply_correction(
                measured_signal=raw_signal,
                previous_channel=self._last_channel,
                integration_time_ms=self.integration_time * 1000,
                delay_ms=self.led_delay
            )
        else:
            corrected_signal = raw_signal

        self._last_channel = channel
        return corrected_signal
```

**Status**: Implementation varies by acquisition mode

---

## 5. Test Suite

### File: `tests/test_afterglow_correction.py`

**Purpose**: Unit tests for `AfterglowCorrection` class

**Tests**:
- Loading optical calibration files
- Interpolation accuracy
- Correction calculation
- Edge cases (missing data, extrapolation)

**Usage**:
```bash
pytest tests/test_afterglow_correction.py
```

**Status**: ✅ Unit tests available

---

## 6. Optical Calibration Data

### Expected Location: `optical_calibration/` (Directory)

**File Format**: JSON with τ tables

**Example**: `optical_calibration/system_FLMT09788_20251011.json`

**Structure**:
```json
{
  "metadata": {
    "serial_number": "FLMT09788",
    "calibration_date": "2025-10-11",
    "integration_times_tested_ms": [10, 20, 35, 55, 80],
    "channels_tested": ["a", "b", "c", "d"]
  },
  "channel_data": {
    "a": {
      "integration_time_data": [
        {
          "integration_time_ms": 20.0,
          "tau_ms": 21.45,
          "amplitude": 1234.5,
          "baseline": 890.2,
          "r_squared": 0.978
        },
        ...
      ]
    },
    ...
  }
}
```

**Status**: ⏳ Generated by OEM characterization script

**Current State**: May or may not exist (check if directory present)

---

## 7. Code Flow Summary

### OEM Calibration (One-Time Setup)

```
1. Run led_afterglow_integration_time_model.py
   ↓
2. Characterize all 4 channels at 5 integration times
   ↓
3. Fit exponential decay: signal(t) = baseline + A × exp(-t/τ)
   ↓
4. Build τ(integration_time) lookup tables
   ↓
5. Save optical_calibration/system_SERIAL_DATE.json
   ↓
6. Update device_config.json:
      "optical_calibration_file": "optical_calibration/system_SERIAL_DATE.json"
```

### User Calibration (Step 5 & Step 7)

```
1. Load AfterglowCorrection(optical_cal_file)
   ↓
2. Step 5: Measure dark noise after LED calibration
   ↓
3. Calculate correction for last active channel
   ↓
4. Subtract correction from dark noise
   ↓
5. Step 7: Measure reference signals (S-mode)
   ↓
6. Measure dark noise after all channels
   ↓
7. Apply afterglow correction to dark
   ↓
8. Subtract corrected dark from all references
```

### Live Data Acquisition

```
1. Acquire spectrum from channel
   ↓
2. Calculate afterglow from previous channel
   ↓
3. Subtract correction from measurement
   ↓
4. Track current channel as "last active"
   ↓
5. Return corrected spectrum
```

---

## 8. Where to Add OEM Full Polarization Calibration

### Recommended Integration: Same OEM Tool

**File**: `utils/oem_calibration_tool.py` (NEW - to be created)

**Features**:
1. **Full Polarization Calibration** (from `auto_polarize()`)
   - Servo position sweep
   - Peak detection for S and P modes
   - Label verification (check which is HIGH vs LOW)

2. **Afterglow Characterization** (from `led_afterglow_integration_time_model.py`)
   - Per-channel decay measurement
   - Integration time sweep
   - Exponential fitting
   - τ(integration_time) table generation

3. **Unified Device Profile**
   - Serial number
   - Detector model
   - Polarizer positions (verified labels)
   - Afterglow profiles (τ tables)
   - Calibration date/version

**Storage**: Same device profile system
```
calibration_data/device_profiles/serial_12345.json
```

**Why Together**:
- Both are **one-time OEM characterizations**
- Both are **device-specific** (not user-repeatable)
- Both require **extended measurement time** (40-50 minutes)
- Both store results in **device-specific profiles**
- Both are **loaded automatically** by user calibration

---

## 9. Current vs Future State

### Current Implementation

| Feature | Status | Location |
|---------|--------|----------|
| Afterglow Correction Module | ✅ Production | `afterglow_correction.py` |
| Calibration Integration | ✅ Active | `spr_calibrator.py` (Steps 5, 7) |
| Characterization Script | ✅ Available | `led_afterglow_integration_time_model.py` |
| Validation Tests | ✅ Available | `tests/led_afterglow_validation.py` |
| Unit Tests | ✅ Available | `tests/test_afterglow_correction.py` |
| Optical Calibration Data | ⏳ OEM-dependent | `optical_calibration/` (may exist) |
| Device Config Integration | ✅ Active | `config/device_config.json` |

### Future OEM Tool

| Feature | Status | Location |
|---------|--------|----------|
| Polarization Sweep | ⏳ Planned | `utils/oem_calibration_tool.py` |
| Afterglow Characterization | ⏳ Move from root | `utils/oem_calibration_tool.py` |
| Unified Device Profiles | ⏳ Planned | `calibration_data/device_profiles/` |
| Profile Auto-Loading | ⏳ Planned | `spr_calibrator.py` enhancement |
| Manufacturing Workflow | ⏳ Planned | `OEM_CALIBRATION_GUIDE.md` |

---

## 10. Key Differences: Afterglow vs Polarization

### Afterglow Characterization
- **Time**: 40-50 minutes (comprehensive sweep)
- **Complexity**: Exponential fitting, integration time dependency
- **Output**: JSON with τ(int_time) tables per channel
- **Usage**: Loaded and applied during calibration (Steps 5, 7)
- **Repeatability**: OEM only (too time-consuming for users)

### Polarization Calibration
- **Time**: 5-10 minutes (servo sweep)
- **Complexity**: Peak detection, label verification
- **Output**: Two servo positions (S and P degrees)
- **Usage**: Stored in firmware/profile, validated in Step 2B
- **Repeatability**: OEM preferred, but user can run if needed (advanced)

### Why They Belong Together
1. **Same workflow**: One-time manufacturing setup
2. **Same storage**: Device-specific profiles
3. **Same access pattern**: Auto-loaded by user calibration
4. **Same user**: Manufacturing technician, not end user
5. **Complementary**: Optical (afterglow) + mechanical (polarizer) characterization

---

## 11. Quick Reference

### To Run Afterglow Characterization:
```bash
python led_afterglow_integration_time_model.py
```
**Output**: `optical_calibration/system_SERIAL_DATE.json`

### To Validate Afterglow Correction:
```bash
python tests/led_afterglow_validation.py
```

### To Check If Afterglow Is Enabled:
```bash
# Check device config
cat config/device_config.json | grep afterglow

# Check logs during calibration
# Look for: "✅ Optical calibration loaded for calibration afterglow correction"
```

### To Disable Afterglow Correction:
Edit `config/device_config.json`:
```json
{
  "afterglow_correction_enabled": false
}
```

### Current Afterglow Correction Value:
**Generic fallback**: 25 counts (if no optical calibration file)
**Device-specific**: Varies by channel and integration time (from τ tables)

---

## Summary

**Afterglow code is currently split across**:
1. **Production module**: `afterglow_correction.py` (passive correction)
2. **Calibration integration**: `spr_calibrator.py` (Steps 5 & 7)
3. **OEM characterization**: `led_afterglow_integration_time_model.py` (one-time)
4. **Validation/testing**: `tests/` directory

**For OEM production workflow**, the characterization script should be **moved into a unified OEM calibration tool** alongside polarization calibration, as outlined in `OEM_CALIBRATION_ROADMAP.md`.

**Current status**: Afterglow correction is **fully implemented and active** in calibration. OEM characterization script exists but needs to be integrated into manufacturing workflow.

---

**Last Updated**: 2025-10-19
**Related Documents**:
- `OEM_CALIBRATION_ROADMAP.md` (OEM tool planning)
- `POLARIZER_LABEL_SWAP_FIX.md` (polarizer validation)
- `afterglow_correction.py` (correction module)
