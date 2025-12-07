# SPR Calibration System - README

## Overview
Production-ready bilinear calibration model for LED-intensity-time control in SPR optical systems.

**Model Equation:** `counts(I, t) = (a·t + b)·I + (c·t + d)`  
**Accuracy:** R² > 0.9999, errors < 2% (validated)  
**Status:** ✅ Production-Ready (Dec 2025)

**REQUIRES FIRMWARE V1.9+** for multi-LED activation and batch intensity control.

## Quick Links
- **📘 Full Documentation:** [models/BILINEAR_MODEL_DOCUMENTATION.md](models/BILINEAR_MODEL_DOCUMENTATION.md)
- **🚀 Integration Guide:** [CALIBRATION_INTEGRATION_GUIDE.md](CALIBRATION_INTEGRATION_GUIDE.md)
- **🧪 Validation Tests:** [tests/](tests/)
- **📊 Model Files:** [models/](models/)
- **📜 Old RBF Version:** [README_OLD_RBF.md](README_OLD_RBF.md)

## File Structure
```
spr_calibration/
├── README.md                              # This file
├── CALIBRATION_INTEGRATION_GUIDE.md       # Deployment guide
│
├── models/
│   ├── BILINEAR_MODEL_DOCUMENTATION.md    # Complete model documentation
│   └── led_calibration_spr_processed_FLMT09116.json  # Production model
│
├── data/
│   ├── spr_2d_grid_S_FLMT09116.json       # Raw S-pol measurements
│   ├── spr_2d_grid_P_FLMT09116.json       # Raw P-pol measurements
│   └── dark_current_FLMT09116.json        # Dark current data
│
├── tests/
│   ├── validate_calibration.py            # Transmission validation
│   ├── validate_fixed_intensity.py        # Linearity validation
│   └── test_sensitivity_correction_simple.py
│
├── validation_results/
│   ├── validation_transmission_spectra_FLMT09116.png
│   ├── validation_results_FLMT09116.json
│   ├── validation_fixed_intensity_FLMT09116.png
│   └── validation_fixed_intensity_FLMT09116.json
│
├── measure.py      # Data acquisition (2-point sampling, ~15 min)
└── process.py      # Model fitting and validation
```

## Quick Start

### Prerequisites
```bash
# Hardware required:
# - PicoP4SPR LED controller with Firmware V1.9 or higher
# - USB4000 or Flame-T spectrometer
# - Calibrated servo polarizer

# Python dependencies:
pip install numpy scipy matplotlib seabreeze
```

### Installation
```bash
git clone https://github.com/Ludo-affi/ezControl-AI.git
cd ezControl-AI
```

### Load Model
```python
import json

with open('spr_calibration/models/led_calibration_spr_processed_FLMT09116.json') as f:
    calibration = json.load(f)
models = calibration['models']
```

### Predict Counts
```python
def predict_counts(led, pol, intensity, time_ms):
    """Predict detector counts using bilinear model."""
    params = models[pol][led]
    a, b, c, d = params['a'], params['b'], params['c'], params['d']
    return (a * time_ms + b) * intensity + (c * time_ms + d)

# Example: LED_C, S-pol, I=100, t=30ms
counts = predict_counts('C', 'S', 100, 30.0)
print(f"Predicted: {counts:.0f} counts")
```

## Model Performance
- **R² Linearity:** > 0.9999 ✅
- **Mean Error:** < 0.15% ✅
- **Max Error:** < 2.15% (10-60ms range) ✅
- **Validation:** Fixed intensity + Transmission spectra ✅

## Validation Results
| LED | S-pol (10-60ms) | P-pol (10-60ms) |
|-----|-----------------|-----------------|
| A | < 0.8% error | < 1.5% error |
| B | < 1.8% error | < 2.0% error |
| C | < 2.1% error | < 2.1% error |
| D | < 2.1% error | < 1.8% error |

## Operating Guidelines
- **Integration time:** 10-60 ms (optimal range)
- **Target counts:** 30,000-50,000 (avoid saturation)
- **Detector limit:** ~62,000 counts (16-bit ADC)
- **LED brightness:** 3× variation between LEDs (per-LED control recommended)

## Running Calibration

### New Detector Setup
```bash
# 1. Measure (takes ~15 minutes, 2-point sampling)
python spr_calibration/measure.py

# 2. Process data and fit bilinear model
python spr_calibration/process.py

# 3. Validate results
python spr_calibration/tests/validate_calibration.py
python spr_calibration/tests/validate_fixed_intensity.py

# 4. Commit to Git for deployment
git add spr_calibration/models/led_calibration_spr_processed_{SERIAL}.json
git commit -m "Add calibration for detector {SERIAL}"
git push
```

### Outputs from measure.py
- `data/spr_2d_grid_S_{SERIAL}.json` - S-polarization measurements
- `data/spr_2d_grid_P_{SERIAL}.json` - P-polarization measurements
- `data/dark_current_{SERIAL}.json` - Dark current data

### Outputs from process.py
- `models/led_calibration_spr_processed_{SERIAL}.json` - Bilinear models
- Validation plots in `LED-Counts relationship/` directory

## Key Features
✅ **Physics-based:** Bilinear model matches theory  
✅ **Fast:** 4 parameters per LED (vs. hundreds for RBF)  
✅ **Accurate:** < 2% error in operating range  
✅ **Validated:** Multiple independent tests  
✅ **Portable:** Single JSON file deployment  
✅ **Efficient:** 60% faster calibration (2-point vs. 5-point sampling)  

## Model Advantages Over RBF

| Feature | Bilinear Model | RBF Model |
|---------|----------------|-----------|
| **Parameters** | 4 per LED/pol (32 total) | Hundreds of control points |
| **Accuracy** | R² > 0.9999 | Similar |
| **Speed** | O(1) evaluation | O(n) interpolation |
| **Physics** | Matches theory | Black box |
| **Extrapolation** | Reliable | Unstable |
| **Storage** | ~1 KB JSON | Large arrays |

## Technical Details

### Bilinear Model
```
counts(I, t) = (a·t + b)·I + (c·t + d)

Where:
  a = Sensitivity slope (counts/ms/intensity_unit)
  b = Sensitivity offset (counts/intensity_unit)
  c = Dark signal slope (counts/ms)
  d = Dark signal offset (counts)
```

### Calibration Method
- **2-point sampling** per LED (low/high intensity)
- **4 LEDs** (A, B, C, D)
- **2 polarizations** (S, P)
- **Duration:** ~15 minutes (60% faster than previous 5-point method)

### Servo Positions
- **S-polarization:** PWM 72 (parallel, high transmission)
- **P-polarization:** PWM 8 (perpendicular, SPR dip)

## Documentation
- **Full Model Documentation:** [models/BILINEAR_MODEL_DOCUMENTATION.md](models/BILINEAR_MODEL_DOCUMENTATION.md)
- **Integration Guide:** [CALIBRATION_INTEGRATION_GUIDE.md](CALIBRATION_INTEGRATION_GUIDE.md)
- **Old RBF Method:** [README_OLD_RBF.md](README_OLD_RBF.md)

## Notes

- **Detector-specific:** Models are calibrated per detector serial number
- **No sample required:** Calibration performed with clean optical path
- **Git deployment:** Commit model JSON to repository for easy multi-system deployment
- **Integration:** Compatible with main `ezControl-AI` application

## Version History

**v2.0.0** (2025-12-07)
- 🎉 **NEW: Bilinear model replaces RBF**
- R² > 0.9999 validation
- 2-point sampling (60% faster)
- Comprehensive validation suite
- Improved documentation

**v1.0.0** (2025-12-05)
- Initial release with RBF interpolation
- See [README_OLD_RBF.md](README_OLD_RBF.md)

## Support

**Repository:** https://github.com/Ludo-affi/ezControl-AI  
**Branch:** affilabs.core-beta  
**Status:** Production-Ready ✅

---
**Last Updated:** December 7, 2025