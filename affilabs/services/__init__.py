"""Business Services - Pure Business Logic

This package contains business logic services with NO Qt dependencies.
Services encapsulate domain logic and can be tested in isolation.

Architecture:
- No UI code (no Qt imports)
- No hardware code (delegates to hardware layer)
- Uses domain models for data structures
- Fully testable with mocks
"""

from .baseline_corrector import BaselineCorrector
from .calibration_validator import CalibrationValidator
from .spectrum_processor import SpectrumProcessor
from .transmission_calculator import TransmissionCalculator

__all__ = [
    "SpectrumProcessor",
    "CalibrationValidator",
    "TransmissionCalculator",
    "BaselineCorrector",
]
