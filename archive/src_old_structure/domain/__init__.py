"""
Domain Models - Pure Business Logic Data Structures

This package contains domain models with NO Qt dependencies.
These are pure Python dataclasses representing the business entities.

Architecture:
- No UI code (no Qt imports)
- No hardware code (no device drivers)
- Just data structures and validation
- Fully testable in isolation
"""

from .spectrum_data import SpectrumData, RawSpectrumData, ProcessedSpectrumData, SpectrumBatch
from .calibration_data import CalibrationData, CalibrationMetrics
from .acquisition_config import AcquisitionConfig, LEDConfig, TimingConfig, AcquisitionMode, PolarizerMode
from .device_status import DeviceStatus, DeviceType, ConnectionState, SystemStatus
from .adapters import (
    led_calibration_result_to_domain,
    domain_to_acquisition_config,
    numpy_spectrum_to_domain,
    create_raw_spectrum,
    create_processed_spectrum
)

__all__ = [
    # Data models
    'SpectrumData',
    'RawSpectrumData',
    'ProcessedSpectrumData',
    'SpectrumBatch',
    'CalibrationData',
    'CalibrationMetrics',
    'AcquisitionConfig',
    'LEDConfig',
    'TimingConfig',
    'AcquisitionMode',
    'PolarizerMode',
    'DeviceStatus',
    'DeviceType',
    'ConnectionState',
    'SystemStatus',
    # Adapters
    'led_calibration_result_to_domain',
    'domain_to_acquisition_config',
    'numpy_spectrum_to_domain',
    'create_raw_spectrum',
    'create_processed_spectrum',
]
