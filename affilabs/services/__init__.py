"""
Business Services - Pure Business Logic

This package contains business logic services with NO Qt dependencies.
Services encapsulate domain logic and can be tested in isolation.

Architecture:
- No UI code (no Qt imports)
- No hardware code (delegates to hardware layer)
- Uses domain models for data structures
- Fully testable with mocks
"""

from .spectrum_processor import SpectrumProcessor
from .calibration_validator import CalibrationValidator
from .transmission_calculator import TransmissionCalculator
from .baseline_corrector import BaselineCorrector

__all__ = [
    'SpectrumProcessor',
    'CalibrationValidator',
    'TransmissionCalculator',
    'BaselineCorrector',
]
