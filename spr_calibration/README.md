# SPR 2D RBF Calibration Package

**Optical system calibration for SPR measurements using 2D Radial Basis Function (RBF) interpolation.**

## Overview

This package provides a complete workflow for calibrating the LED optical system with S and P polarization states. It builds detector-specific 2D RBF models that predict photon counts from (LED intensity, integration time) pairs.

**Validation Results**: <1% mean error across all LEDs (0.230% average)

## Quick Start

### Prerequisites
```bash
# Hardware required:
# - PicoP4SPR LED controller (V1.9+)
# - USB4000 or Flame-T spectrometer
# - Calibrated servo polarizer

# Python dependencies:
pip install numpy scipy matplotlib
```

### Installation
```bash
git clone https://github.com/Ludo-affi/ezControl-AI.git
cd ezControl-AI
```

### Usage

#### 1. Take Calibration Measurements (~10-12 minutes)
```bash
python spr_calibration/measure.py
```

**What it does:**
- Measures 92 points × 4 LEDs × S-polarization (368 measurements)
- Measures 92 points × 4 LEDs × P-polarization (368 measurements)
- Measures dark current at 11 integration times
- Validates S/P matching

**Outputs:**
- `data/S_polarization.json`
- `data/P_polarization.json`
- `data/dark_signal.json`

#### 2. Process Data & Build RBF Models
```bash
python spr_calibration/process.py
```

**What it does:**
- Validates intensity/time matching between S and P
- Applies dark current correction
- Builds 2D RBF interpolation models (thin_plate_spline kernel)
- Validates model accuracy

**Outputs:**
- `data/processed_models.json` (RBF models for all LEDs)
- `data/spr_calibration_comparison.png` (S vs P visualization)

#### 3. Validate Models (Optional)
```bash
python spr_calibration/validate.py
```

**What it does:**
- Tests RBF interpolation accuracy at training points
- Generates 2D surface visualizations
- Reports error statistics

**Outputs:**
- `data/visualizations/2d_rbf_visualization_*.png` (4 files, one per LED)
- Error statistics in console

## File Structure

```
spr_calibration/
├── __init__.py              # Package initialization
├── README.md                # This file
├── measure.py               # Calibration measurement script
├── process.py               # Data processing & RBF model building
├── validate.py              # Model validation & visualization
├── plan.py                  # Calibration plan validation utilities
└── data/                    # Calibration data & results
    ├── calibration_plan.json
    ├── S_polarization.json
    ├── P_polarization.json
    ├── processed_models.json
    └── visualizations/
        ├── 2d_rbf_visualization_A_FLMT09116.png
        ├── 2d_rbf_visualization_B_FLMT09116.png
        ├── 2d_rbf_visualization_C_FLMT09116.png
        └── 2d_rbf_visualization_D_FLMT09116.png
```

## Technical Details

### 2D RBF Interpolation
- **Method**: `scipy.interpolate.RBFInterpolator`
- **Kernel**: `thin_plate_spline`
- **Smoothing**: 0.1
- **Epsilon**: 1.0
- **Input dimensions**: (LED intensity [0-255], integration time [ms])
- **Output**: Photon counts (dark-corrected)

### Calibration Plan
- **23 (intensity, time) pairs per LED**
- **4 LEDs (A, B, C, D)**
- **2 polarization states (S, P)**
- **Total**: 184 measurements + 11 dark measurements

### Model Performance
From validation on real data (2025-12-05):
- **LED A**: 0.26% (S), 0.33% (P) mean error
- **LED B**: 0.37% (S), 0.31% (P) mean error
- **LED C**: 0.25% (S), 0.20% (P) mean error
- **LED D**: 0.053% (S), 0.081% (P) mean error ⭐
- **Average**: 0.230% mean error

**Status**: ✅ Production-ready (<5% error threshold)

## Notes

- **Detector-specific**: Models are calibrated per detector serial number
- **No sample required**: Calibration performed with clean optical path
- **Servo positions**: Must be pre-calibrated (see `SERVO_CALIBRATION_METHOD.md`)
- **Integration**: Compatible with main `ezControl-AI` application

## Related Documentation

- `../docs/SPR_EOM_CALIBRATION_GUIDE.md` - Detailed calibration workflow
- `../SERVO_CALIBRATION_METHOD.md` - Servo polarizer calibration reference
- `../SPR_OPTIMIZATION_COMPLETE.md` - Performance optimization notes

## Version History

**v1.0.0** (2025-12-05)
- Initial release
- 2D RBF interpolation with thin_plate_spline kernel
- S/P polarization support
- Dark current correction
- Validation achieving <1% error

## License

Proprietary - AffiLabs Inc.

## Contact

For issues or questions, see main repository: https://github.com/Ludo-affi/ezControl-AI
