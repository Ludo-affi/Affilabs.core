# Servo Polarizer Calibration Package

**Version:** 1.0
**Date:** December 7, 2025
**Status:** Production Ready

## Overview

This package contains the complete, validated method for automatic servo-controlled polarizer calibration. It supports both **CIRCULAR** and **BARREL** polarizer types with automatic detection.

## Quick Start

### Requirements

- Python 3.8+
- NumPy
- Hardware: PicoP4SPR controller with servo-controlled polarizer
  - **Firmware V1.9 or higher required** (multi-LED command support)
  - Earlier firmware versions do not support the `lm:A,B,C,D` command
- Spectrometer: Ocean Optics USB4000 (or compatible)

### Installation

```bash
# Copy this entire folder to your project
cp -r servo_polarizer_calibration /path/to/your/project/

# Ensure you have the required hardware manager module
# This package requires a hardware_manager module with HardwareManager class
```

### Basic Usage

```python
# Run full calibration (~60 seconds)
python calibrate_polarizer.py
```

The script will:
1. **Stage 1:** Perform 5-position bidirectional sweep (1→255→1)
2. **Stage 2:** Automatically detect polarizer type (CIRCULAR vs BARREL)
3. **Stage 3:** Refine positions using ±10 PWM sweep around detected regions
4. Output optimal P and S positions with stability metrics

### Fast-Track Calibration (FT)

```python
# Fast-track: Validate stored positions (~30 seconds)
python calibrate_polarizer_ft.py

# Or specify positions manually
python calibrate_polarizer_ft.py --p-pwm 6 --s-pwm 69

# Quiet mode (minimal output)
python calibrate_polarizer_ft.py --quiet
```

**When to use fast-track:**
- ✅ After moving hardware to new location
- ✅ After system power cycle
- ✅ Periodic checks (daily/weekly)
- ✅ After mechanical adjustments
- ✅ You have known-good P/S positions
- ❌ First-time setup (use full calibration)
- ❌ After changing polarizer type
- ❌ Unknown/new hardware

**Important: Detector-Specific Intensities**
- Absolute intensity values vary between detectors/sensors
- OEM baseline (USB4000): P~5250 counts, S~13450 counts
- Your sensor may show different absolute values (e.g., 3000 vs 5000)
- **Validation focuses on RELATIVE metrics:**
  - S/P ratio > 1.5× (typically 2.5×)
  - P noise < 2% CV (typically 0.2%)
  - S noise < 2% CV (typically 0.1%)
  - Separation > 50% of P intensity

**Fast-track validation checks:**
- S/P ratio > 1.5× (typically 2.5×)
- P noise < 2% CV (typically 0.2%)
- S noise < 2% CV (typically 0.1%)
- Separation > 50% of P intensity

Exit code: 0 = PASS, 1 = FAIL (useful for automated testing)

### Legacy Quick Validation

For compatibility, `validate_stored_calibration.py` is still available (identical to FT mode).

### Output Files

- `polarizer_calibration_results.csv` - Summary of calibration results
- `polarizer_calibration_detail.csv` - Detailed sweep data for all positions
- `polarizer_validation_results.csv` - Fast-track validation results with timestamp

## Method Description

### Three-Stage Calibration

#### Stage 1: Bidirectional Sweep
- 5 positions across full range: PWM 1, 65, 128, 191, 255
- Forward and backward sweeps to assess hysteresis
- Measures mean of top 20 spectral max points (robust signal metric)
- **Duration:** ~30 seconds

#### Stage 2: Type Detection
- **CIRCULAR Polarizer:** All positions above dark threshold (3000 counts for USB4000)
  - Single smooth transition from low to high intensity
  - Refinement finds plateau centers
- **BARREL Polarizer:** Some positions at/below dark threshold
  - Multiple transmission windows (~90° spacing)
  - Refinement optimizes window alignment

#### Stage 3: Refinement
- ±10 PWM sweep around detected P and S regions
- 10 scans per position for noise characterization
- Spectral analysis:
  - **P position:** Min in 610-680nm ± 10 pixels (SPR-relevant range)
  - **S position:** Mean of top 20 max points
- Finds stable ranges within 1% of optimum
- Selects middle position of stable range (maximum tolerance)

### Key Features

✅ **Automatic polarizer type detection**
✅ **Detector-agnostic thresholds**
✅ **Directional approach eliminates hysteresis**
✅ **Robust spectral analysis methods**
✅ **Noise characterization (CV < 0.3%)**
✅ **Middle-of-plateau selection for maximum tolerance**
✅ **~60 second total calibration time**
✅ **Firmware V1.9+ multi-LED command (lm:A,B,C,D)**

## Firmware Requirements

**This calibration method requires PicoP4SPR Firmware V1.9 or higher.**

The multi-LED activation command `lm:A,B,C,D` was introduced in Firmware V1.9, which allows simultaneous activation of all 4 LED channels. Earlier firmware versions do not support this command and will require individual LED activation (e.g., `la`, `lb`, `lc`, `ld` separately).

If you have firmware < V1.9, you will need to:
1. Update firmware to V1.9+, or
2. Modify the LED activation code to use individual channel commands

## Validated Results

### CIRCULAR Polarizer (Our Hardware)
- **P Position:** PWM 6 (stable range: 1-11)
  - Intensity: 5245.9 ± 11.9 counts
  - Noise: 0.23% CV
- **S Position:** PWM 69 (stable range: 64-75)
  - Intensity: 13455.0 ± 12.4 counts
  - Noise: 0.09% CV
- **S/P Ratio:** 2.56×
- **Separation:** 8209 counts

### Stability
- P plateau: 11 PWM positions (all within 1% = 13 counts variation)
- S plateau: 12 PWM positions (all within 1% = 13 counts variation)
- Plateau width >> mechanical hysteresis (±8 PWM tolerance vs ±2-3 PWM hysteresis)

## Package Contents

### Main Scripts
- **`calibrate_polarizer.py`** - Full calibration method (universal, auto-detect, ~60s)
- **`calibrate_polarizer_ft.py`** - Fast-track validation of stored positions (~30s)
- **`validate_stored_calibration.py`** - Legacy validation (same as FT)

### Test Scripts (`test_scripts/`)
Development and validation scripts used to develop this method:

1. **`servo_continuous_sweep.py`** - Initial 5-position continuous sweep test
2. **`servo_refined_sweep.py`** - 2 PWM resolution full range sweep
3. **`validate_s_p_directional.py`** - Directional approach validation
4. **`validate_optimal_positions_sweep.py`** - ±10 PWM sweep with noise analysis
5. **`plot_optimal_noise_analysis.py`** - Comprehensive visualization

### Test Data (`test_data/`)
Raw data and analysis from validation studies:

- `servo_continuous_latest.csv` - 5-position sweep data (1,882 samples)
- `servo_refined_sweep.csv` - 2 PWM resolution sweep (1,419 samples)
- `optimal_position_sweep.csv` - Final ±10 PWM sweep with noise metrics
- `polarizer_calibration_results.csv` - Latest calibration summary
- `polarizer_calibration_detail.csv` - Latest detailed sweep data
- `optimal_position_validation_overlay.png` - Validation vs sweep comparison plot
- `optimal_position_noise_analysis.png` - 7-panel noise characterization

### Documentation (`documentation/`)
- **`SERVO_POLARIZER_CALIBRATION.md`** - Comprehensive 69KB documentation
  - Complete methodology
  - All sweep results with statistics
  - Production implementation guide
  - Troubleshooting guide
  - Validation results (5/5 checks passed)

## Integration Guide

### Adapting for Your Hardware

If using different hardware than PicoP4SPR + USB4000:

1. **Update Hardware Manager Import:**
```python
# In calibrate_polarizer.py, replace:
from core.hardware_manager import HardwareManager

# With your hardware interface
```

2. **Adjust Dark Threshold (if needed):**
```python
# In detect_polarizer_type() function:
DARK_THRESHOLD = 3000  # Change for your detector
```

3. **Modify Servo Commands (if needed):**
```python
# In move_to_position() function:
cmd = f"sv{target_pwm:03d}000\n"  # Adjust format for your controller
```

### Using Results in Your Code

```python
import csv

# Load calibration results
with open('polarizer_calibration_results.csv', 'r') as f:
    reader = csv.DictReader(f)
    results = {row['Parameter']: row['Value'] for row in reader}

p_pwm = int(results['P PWM'])
s_pwm = int(results['S PWM'])
polarizer_type = results['Polarizer Type']

print(f"Using {polarizer_type} polarizer: P={p_pwm}, S={s_pwm}")
```

## Technical Details

### Hardware Requirements
- **Controller:** PicoP4SPR (firmware V1.9+) with servo commands `sv` (set position), `ss` (status)
- **LEDs:** All 4 channels at 20% (51/255) for consistent illumination
- **Integration Time:** 5ms proven sufficient
- **Servo Response:** ~42 PWM/second movement speed

### Spectral Analysis Methods

**Why Mean of Top 20 Points?**
- More robust than single max point
- Less sensitive to noise spikes
- Consistent across detector types

**Why 610-680nm for P?**
- SPR-relevant wavelength range
- Where minimum transmission occurs in our application
- ±10 pixel averaging reduces noise

**Why Directional Approach?**
- Eliminates mechanical hysteresis (±2-3 PWM)
- P: Always approach from high (PWM 255)
- S: Always approach from low (PWM 1)
- Ensures repeatability: 0.01-0.08% CV

### Validation Metrics

The calibration is considered valid if:
1. ✅ S/P ratio > 1.5× (typically 2.5×)
2. ✅ P noise < 2% CV (typically 0.2%)
3. ✅ S noise < 2% CV (typically 0.1%)
4. ✅ Separation > 50% of P intensity
5. ✅ Stable ranges > 5 PWM width

## Development History

This method was developed through systematic testing:

1. **Continuous Sweep** (1,882 samples) - Identified approximate regions
2. **Refined Sweep** (1,419 samples, 2 PWM resolution) - Mapped full characteristics
3. **Directional Validation** - Proven repeatability (0.01-0.08% CV)
4. **Noise Analysis** - Characterized stability (±10 PWM sweep, 10 scans/position)
5. **Spectral Analysis** - 70% improvement in S/P ratio (2.53× vs 1.49×)
6. **Universal Method** - Automatic type detection for CIRCULAR and BARREL

## Troubleshooting

### Issue: "Hardware not connected"
- Check USB connections
- Verify controller firmware version (need V1.9+)
- Ensure hardware manager module is properly imported

### Issue: "Polarizer type detection incorrect"
- Check dark threshold matches your detector
- Verify LED brightness (should be consistent)
- Review Stage 1 sweep data

### Issue: "Calibration unstable (high CV)"
- Check mechanical stability of polarizer mount
- Verify integration time is appropriate
- Ensure settle time is sufficient (1.5s default)

### Issue: "P and S positions reversed"
- Physically rotate polarizer 90°, or
- Swap P/S assignments in your code

## Citation

If using this calibration method in publications or other projects:

```
Servo Polarizer Calibration Package v1.0
ezControl-AI System, December 2025
Three-stage automatic calibration with type detection
Validated on PicoP4SPR + USB4000 hardware
```

## License

This calibration method is part of the ezControl-AI system.

## Contact

For issues or questions about this calibration package, refer to the main ezControl-AI documentation.

---

**Package Status:** ✅ Production Ready
**Last Validated:** December 7, 2025
**Hardware:** PicoP4SPR (FW V1.9) + Ocean Optics USB4000
**Polarizer Type:** CIRCULAR (tested), BARREL (designed, pending hardware test)
