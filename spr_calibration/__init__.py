"""SPR 2D RBF Calibration Package

Optical system calibration for SPR measurements using 2D RBF interpolation.
Supports S and P polarization states with detector-specific models.

Key Features:
- 2D RBF interpolation (intensity, integration_time) → counts
- S and P polarization support
- Detector-specific models (by serial number)
- Dark current correction
- Model validation with <1% error

Workflow:
1. measure.py - Take calibration measurements (~10-12 min)
2. process.py - Build 2D RBF models with dark correction
3. validate.py - Test model accuracy and visualize results

Dependencies:
- numpy, scipy (RBF interpolation)
- matplotlib (visualization)
- Hardware: PicoP4SPR controller, USB4000/Flame-T spectrometer
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
    '__version__',
    'PACKAGE_DIR',
    'DATA_DIR',
    'VIZ_DIR'
]
