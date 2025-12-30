"""Domain Models - Pure Business Logic Data Structures

This package contains domain models with NO Qt dependencies.
These are pure Python dataclasses representing the business entities.

Architecture:
- No UI code (no Qt imports)
- No hardware code (no device drivers)
- Just data structures and validation
- Fully testable in isolation
"""

from .acquisition_config import (
    AcquisitionConfig,
    AcquisitionMode,
    LEDConfig,
    PolarizerMode,
    TimingConfig,
)
from .adapters import (
    create_processed_spectrum,
    create_raw_spectrum,
    domain_to_acquisition_config,
    led_calibration_result_to_domain,
    numpy_spectrum_to_domain,
)
from .calibration_data import CalibrationData, CalibrationMetrics
from .cycle import Cycle
from .device_status import ConnectionState, DeviceStatus, DeviceType, SystemStatus
from .editable_segment import EditableSegment
from .flag import Flag, InjectionFlag, WashFlag, SpikeFlag, create_flag, flag_from_dict
from .spectrum_data import (
    ProcessedSpectrumData,
    RawSpectrumData,
    SpectrumBatch,
    SpectrumData,
)

__all__ = [
    # Data models
    "SpectrumData",
    "RawSpectrumData",
    "ProcessedSpectrumData",
    "SpectrumBatch",
    "CalibrationData",
    "CalibrationMetrics",
    "Cycle",
    "Flag",
    "InjectionFlag",
    "WashFlag",
    "SpikeFlag",
    "create_flag",
    "flag_from_dict",
    "EditableSegment",
    "AcquisitionConfig",
    "LEDConfig",
    "TimingConfig",
    "AcquisitionMode",
    "PolarizerMode",
    "DeviceStatus",
    "DeviceType",
    "ConnectionState",
    "SystemStatus",
    # Adapters
    "led_calibration_result_to_domain",
    "domain_to_acquisition_config",
    "numpy_spectrum_to_domain",
    "create_raw_spectrum",
    "create_processed_spectrum",
]
