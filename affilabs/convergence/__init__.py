"""Convergence engine package (device-agnostic).

PRODUCTION INTEGRATION:
The convergence engine can be used as a drop-in replacement for the
current LEDconverge() function. See production_wrapper.py for details.

ARCHITECTURE:
- Policies: Modular decision logic (acceptance, priority, boundary, saturation)
- Estimators: Slope estimation from measurement history
- Sensitivity: Device sensitivity classification (HIGH vs BASELINE)
- Adapters: Bridge to existing hardware stack
- Engine: Main convergence loop coordinator
"""

# Core engine components
from .engine import ConvergenceEngine, ConvergenceResult
from .config import ConvergenceRecipe, DetectorParams
from .interfaces import Spectrometer, LEDActuator, ROIExtractor, Logger
from .sensitivity import SensitivityClassifier, SensitivityLabel, SensitivityFeatures

# Production integration
from .production_adapters import (
    CalibrationSpectrometerAdapter,
    ProductionROIExtractor,
    ProductionLogger,
    ProductionLEDActuator,
    create_production_adapters,
)
from .production_bridge import (
    create_recipe_from_production_config,
    create_detector_params_from_production,
    convert_engine_result_to_production,
    validate_engine_result,
)

__all__ = [
    # Engine core
    'ConvergenceEngine',
    'ConvergenceResult',
    'ConvergenceRecipe',
    'DetectorParams',

    # Interfaces
    'Spectrometer',
    'LEDActuator',
    'ROIExtractor',
    'Logger',

    # Sensitivity classification
    'SensitivityClassifier',
    'SensitivityLabel',
    'SensitivityFeatures',

    # Production adapters
    'CalibrationSpectrometerAdapter',
    'ProductionROIExtractor',
    'ProductionLogger',
    'ProductionLEDActuator',
    'create_production_adapters',

    # Production bridge
    'create_recipe_from_production_config',
    'create_detector_params_from_production',
    'convert_engine_result_to_production',
    'validate_engine_result',
]
