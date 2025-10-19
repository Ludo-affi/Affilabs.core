# OEM Calibration Tool - User Guide

## Overview

The OEM Calibration Tool (`utils/oem_calibration_tool.py`) is a comprehensive manufacturing characterization suite that performs one-time device-specific calibrations for:

1. **Polarizer Position Finding** (~5-10 minutes)
2. **Afterglow Characterization** (~40-50 minutes)
3. **Device Profile Generation** (unified JSON output)

This tool is intended for **manufacturing use only** - end users will automatically load the resulting device profiles.

---

## Quick Start

### Basic Usage (Full Calibration)

```bash
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Run full OEM calibration
python utils/oem_calibration_tool.py --serial FLMT12345 --detector "Hamamatsu S11639"
```

### Partial Calibration

```bash
# Only polarizer calibration (fast - 5 minutes)
python utils/oem_calibration_tool.py --serial FLMT12345 --skip-afterglow

# Only afterglow characterization (slow - 40 minutes)
python utils/oem_calibration_tool.py --serial FLMT12345 --skip-polarizer
```

---

## Prerequisites

### Hardware Requirements
- PicoP4SPR device connected via USB/serial
- Ocean Optics spectrometer (USB4000 or compatible)
- Polarizer installed (any orientation - tool will find optimal positions)
- Good optical coupling (fiber connected to sample chamber)

### Software Requirements
- Python 3.10+
- All dependencies installed (`pdm install`)
- SeaBreeze drivers installed
- Virtual environment activated

---

## Command-Line Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--serial` | **Yes** | - | Device serial number (e.g., FLMT12345) |
| `--detector` | No | "Unknown" | Detector model (e.g., "Hamamatsu S11639") |
| `--output-dir` | No | `calibration_data/device_profiles` | Output directory |
| `--skip-polarizer` | No | False | Skip polarizer calibration |
| `--skip-afterglow` | No | False | Skip afterglow characterization |

---

## Step-by-Step Workflow

### Step 1: Polarizer Calibration (5-10 minutes)

**What It Does**:
1. Sweeps servo from 10° to 170° in 5° steps
2. Measures light intensity at each position
3. Identifies two transmission peaks (most positions block light)
4. **Higher peak** = S-mode (perpendicular, HIGH transmission)
5. **Lower peak** = P-mode (parallel, LOWER but substantial transmission)
6. Verifies if hardware labels match physical behavior

**Physics Background**:
- **S-mode (perpendicular)**: Allows MORE light through (~1000+ counts)
- **P-mode (parallel)**: Allows LESS light through (~300-700 counts, but NOT near zero)
- **Most positions**: Block light almost completely (~50-100 counts)

**Expected Output**:
```
================================================================================
POLARIZER CALIBRATION RESULTS:
================================================================================
✅ LABELS CORRECT (or ⚠️ LABELS INVERTED)
Actual S position (HIGH transmission): 100° → 1050 counts
Actual P position (LOW transmission):   10° →  315 counts
S/P intensity ratio: 3.33× (expected > 3.0)
================================================================================
```

**Success Criteria**:
- S/P ratio > 3.0 (S is brighter than P, typical range 3-15×)
- Two distinct peaks found in sweep
- P-mode intensity substantial (>100 counts, NOT near zero)
- S-mode intensity clearly higher than P-mode

**Troubleshooting**:
| Problem | Likely Cause | Solution |
|---------|--------------|----------|
| S/P ratio < 2.0 | Poor polarizer alignment | Check fiber coupling, adjust polarizer |
| P-mode < 100 counts | Misalignment or blockage | Check optical path, fiber connection |
| Only one peak found | Polarizer not installed | Install polarizer, check hardware |
| Weak signal overall | LED off or fiber issue | Check LED intensity, fiber connection |

---

### Step 2: Afterglow Characterization (40-50 minutes)

**What It Does**:
1. Tests all 4 channels (A, B, C, D)
2. For each channel:
   - Tests 5 integration times (10, 20, 35, 55, 80 ms)
   - Runs 5 on/off cycles per integration time
   - Measures decay at 7 time points (10ms to 2000ms)
   - Fits exponential model: `signal(t) = baseline + A × exp(-t/τ)`
3. Builds τ(integration_time) lookup tables

**Expected Output** (per channel):
```
================================================================================
AFTERGLOW CHARACTERIZATION - Channel A
================================================================================
Testing integration time: 20ms
  Running 5 on/off cycles...
  Fitting exponential decay model...
  ✅ Fit successful:
     τ = 21.45 ms
     Amplitude = 1234.5 counts
     Baseline = 890.2 counts
     R² = 0.978
```

**Success Criteria**:
- R² > 0.95 (good fit quality)
- τ in range 15-30 ms (typical for LED phosphors)
- All 4 channels successfully characterized
- All integration times complete

**Troubleshooting**:
| Problem | Likely Cause | Solution |
|---------|--------------|----------|
| Fit fails (R² < 0.9) | Noisy data or wrong model | Increase cycles, check hardware stability |
| τ > 100 ms | Very slow phosphor or contamination | Check dark noise, fiber cleanliness |
| τ < 5 ms | Fast phosphor or measurement error | May be acceptable, check consistency |

---

### Step 3: Profile Generation & Plots

**Outputs Generated**:

1. **Device Profile JSON**: `calibration_data/device_profiles/device_SERIAL_DATE.json`
   ```json
   {
     "device_serial": "FLMT12345",
     "device_type": "PicoP4SPR",
     "detector_model": "Hamamatsu S11639",
     "calibration_date": "2025-10-19T14:30:00",
     "polarizer": {
       "s_position": 100,
       "p_position": 10,
       "ps_ratio": 10.25,
       "labels_inverted": true
     },
     "afterglow": {
       "channels": {
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
   }
   ```

2. **Polarizer Sweep Plot**: `polarizer_SERIAL_DATE.png`
   - Shows intensity vs servo position
   - Marks S and P positions
   - Visual verification of peaks

3. **Afterglow Decay Plots** (one per channel): `afterglow_chX_SERIAL_DATE.png`
   - Left: Decay curves for all integration times
   - Right: τ vs integration time relationship

---

## Integration with User Calibration

### Manual Integration (Temporary)

1. **Copy device profile** to known location:
   ```bash
   copy calibration_data\device_profiles\device_FLMT12345_20251019.json config\optical_calibration.json
   ```

2. **Update device config** (`config/device_config.json`):
   ```json
   {
     "optical_calibration_file": "config/optical_calibration.json",
     "afterglow_correction_enabled": true,
     "polarizer_s_position": 100,
     "polarizer_p_position": 10
   }
   ```

3. **Run user calibration** - will automatically use OEM data

### Automatic Integration (Future)

**Planned Enhancement** (see `OEM_CALIBRATION_ROADMAP.md`):
- Auto-detect device serial number
- Auto-load matching device profile
- Fallback to generic values if profile missing
- Profile validation on startup

---

## Validation & QA

### Post-Calibration Checks

1. **Polarizer Validation**:
   ```bash
   # Run user calibration and check Step 2B
   python run_app.py
   # Look for: "✅ Polarizer positions validated"
   ```

2. **Afterglow Validation**:
   ```bash
   # Run validation script
   python tests/led_afterglow_validation.py
   ```

3. **Visual Inspection**:
   - Review generated plots for anomalies
   - Check P/S ratio is reasonable (5-15×)
   - Verify τ values are consistent across channels

### Expected Values

| Parameter | Typical Range | Acceptable Range | Action if Outside |
|-----------|---------------|------------------|-------------------|
| P/S Ratio | 5-15× | 3-20× | < 3: Recheck polarizer alignment |
| τ (decay constant) | 15-25 ms | 10-40 ms | > 40: Check phosphor type |
| Amplitude | 500-2000 counts | 100-5000 counts | Very high: Check saturation |
| R² (fit quality) | > 0.97 | > 0.92 | < 0.92: Increase cycles |

---

## Example Session Output

```
================================================================================
OEM CALIBRATION TOOL
================================================================================
Device Serial: FLMT12345
Detector: Hamamatsu S11639
Output Directory: calibration_data/device_profiles
================================================================================
Initializing hardware...
✅ Spectrometer: USB4000
✅ Controller: PicoP4SPR

================================================================================
STEP 1: POLARIZER CALIBRATION
================================================================================
Setting up hardware for polarizer sweep...
Sweep parameters:
  Range: 10-170°
  Step size: 5°
  Total measurements: 65
Starting servo sweep...
  Progress: 5/32 positions measured
  Progress: 10/32 positions measured
  ...
Sweep complete. Analyzing data...
Verifying polarization modes...

================================================================================
POLARIZER CALIBRATION RESULTS:
================================================================================
⚠️ LABELS INVERTED
Actual S position (LOW): 100°
Actual P position (HIGH): 10°
P/S intensity ratio: 10.25× (should be > 3.0)
================================================================================

================================================================================
STEP 2: AFTERGLOW CHARACTERIZATION
================================================================================
Channels: ['A', 'B', 'C', 'D']
Integration times: [10, 20, 35, 55, 80] ms
Estimated time: 40 minutes
================================================================================

================================================================================
AFTERGLOW CHARACTERIZATION - Channel A
================================================================================

Testing integration time: 10ms
  Running 5 on/off cycles...
    Cycle 2/5 complete
    Cycle 4/5 complete
  Fitting exponential decay model...
  ✅ Fit successful:
     τ = 18.32 ms
     Amplitude = 982.3 counts
     Baseline = 785.1 counts
     R² = 0.981

[... repeats for all integration times and channels ...]

================================================================================
SAVING DEVICE PROFILE
================================================================================
✅ Device profile saved: calibration_data/device_profiles/device_FLMT12345_20251019.json

Generating diagnostic plots...
  Plot saved: calibration_data/device_profiles/polarizer_FLMT12345_20251019.png
  Plot saved: calibration_data/device_profiles/afterglow_cha_FLMT12345_20251019.png
  Plot saved: calibration_data/device_profiles/afterglow_chb_FLMT12345_20251019.png
  Plot saved: calibration_data/device_profiles/afterglow_chc_FLMT12345_20251019.png
  Plot saved: calibration_data/device_profiles/afterglow_chd_FLMT12345_20251019.png

================================================================================
✅ OEM CALIBRATION COMPLETE
================================================================================
Device Profile: calibration_data/device_profiles/device_FLMT12345_20251019.json
Serial Number: FLMT12345

Polarizer:
  S position: 100° (LOW)
  P position: 10° (HIGH)
  P/S ratio: 10.25×

Afterglow:
  Channel A: τ range = 18.3-24.6 ms
  Channel B: τ range = 19.1-25.2 ms
  Channel C: τ range = 17.8-23.9 ms
  Channel D: τ range = 18.5-24.8 ms
================================================================================
```

---

## Troubleshooting

### Hardware Connection Issues

**Problem**: `No spectrometer found!`
**Solutions**:
1. Check USB connection
2. Install SeaBreeze drivers
3. Run `python -c "import seabreeze; seabreeze.use('cseabreeze'); from seabreeze.spectrometers import list_devices; print(list_devices())"`

**Problem**: `Failed to connect to SPR controller!`
**Solutions**:
1. Check serial/USB connection
2. Verify correct COM port in HAL
3. Check device power
4. Run `python -c "from utils.hal.pico_p4spr_hal import PicoP4SPRHAL; ctrl = PicoP4SPRHAL(); print(ctrl.connect())"`

### Calibration Failures

**Problem**: Polarizer calibration finds no peaks
**Solutions**:
1. Check LED is on (`ctrl.set_intensity(ChannelID.A, 255)`)
2. Verify fiber is connected
3. Check polarizer is installed
4. Manually test servo movement

**Problem**: Afterglow fits consistently fail
**Solutions**:
1. Increase `num_cycles` to 10 for more averaging
2. Check integration time is appropriate
3. Verify LED turns on/off correctly
4. Check for external light contamination

### Data Quality Issues

**Problem**: τ values vary wildly between channels
**Solutions**:
1. May indicate LED quality differences (acceptable)
2. Check each channel independently
3. Verify consistent measurement conditions

**Problem**: Very high amplitude values (> 5000 counts)
**Solutions**:
1. Reduce LED intensity or integration time
2. Check for saturation
3. Verify spectrometer configuration

---

## File Structure

```
control-3.2.9/
├── utils/
│   └── oem_calibration_tool.py          # ✅ OEM calibration tool (NEW)
├── calibration_data/
│   └── device_profiles/                 # ✅ Output directory
│       ├── device_SERIAL_DATE.json      # Device profile
│       ├── polarizer_SERIAL_DATE.png    # Polarizer plot
│       └── afterglow_chX_SERIAL_DATE.png # Afterglow plots (4 files)
├── config/
│   └── device_config.json               # Update after calibration
└── OEM_CALIBRATION_TOOL_GUIDE.md        # This file
```

---

## Next Steps for Production

1. **Create Manufacturing SOP** (Standard Operating Procedure)
   - Hardware setup checklist
   - Calibration execution steps
   - QA validation criteria
   - Profile storage workflow

2. **Implement Auto-Loading** (see `OEM_CALIBRATION_ROADMAP.md`)
   - Device serial detection
   - Profile lookup by serial
   - Automatic profile loading in `spr_calibrator.py`

3. **Add Profile Validation**
   - Schema validation on load
   - Range checking for parameters
   - Version compatibility checks

4. **Manufacturing Documentation**
   - Training materials
   - Troubleshooting flowcharts
   - Example calibration reports

---

## Summary

The OEM Calibration Tool provides a unified, automated workflow for device-specific characterization:

- **Input**: Connected hardware + device serial number
- **Process**: 45-55 minutes of automated measurements
- **Output**: Device profile JSON + diagnostic plots
- **Integration**: Manual (now) → Automatic (future)

This eliminates manual polarizer adjustment and provides accurate afterglow correction for all acquisition settings, ensuring consistent performance across devices.

---

**Last Updated**: 2025-10-19
**Tool Version**: 1.0
**Author**: GitHub Copilot
**Related Files**:
- `utils/oem_calibration_tool.py` (tool implementation)
- `OEM_CALIBRATION_ROADMAP.md` (future enhancements)
- `AFTERGLOW_CODE_LOCATION_GUIDE.md` (code architecture)
