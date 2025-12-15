"""SPR Bilinear Calibration Package

Production-ready bilinear model for LED-intensity-time calibration in SPR optical systems.

Model: counts(I, t) = (a·t + b)·I + (c·t + d)

Key Features:
- Physics-based bilinear model (4 parameters per LED/pol)
- S and P polarization support
- Detector-specific models (by serial number)
- Dark current correction
- R² > 0.9999 accuracy, errors < 2%
- 2-point sampling (60% faster than previous methods)

Workflow:
1. measure.py - Acquire calibration data (2-point sampling, ~15 min)
2. process.py - Fit bilinear models, validate, save to JSON
3. tests/ - Validation scripts (transmission, fixed intensity)

Dependencies:
- numpy, scipy (linear regression)
- matplotlib (visualization)
- Hardware: PicoP4SPR controller, USB4000/Flame-T spectrometer

Documentation:
- models/BILINEAR_MODEL_DOCUMENTATION.md - Complete theory
- CALIBRATION_INTEGRATION_GUIDE.md - Deployment guide
- models/QUICK_REFERENCE.md - Code snippets
"""

from pathlib import Path

__version__ = "1.0.0"
__author__ = "AffiLabs"
__date__ = "2025-12-05"

# Package root directory
PACKAGE_DIR = Path(__file__).parent
DATA_DIR = PACKAGE_DIR / "data"
VIZ_DIR = DATA_DIR / "visualizations"

__all__ = [
    "__version__",
    "PACKAGE_DIR",
    "DATA_DIR",
    "VIZ_DIR",
]
