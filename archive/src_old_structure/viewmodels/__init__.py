"""View Models (Presenters) - Qt Signal/Slot Bridge

This package contains view models that bridge business services with Qt UI.
View models manage UI state and coordinate between services and widgets.

Architecture:
- Inherits from QObject for Qt signals/slots
- Uses business services for logic (no business logic here)
- Emits signals for UI updates
- Receives user actions via methods
- No direct widget manipulation (widgets subscribe to signals)
"""

from .calibration_viewmodel import CalibrationViewModel
from .device_status_viewmodel import DeviceStatusViewModel
from .spectrum_viewmodel import SpectrumViewModel

__all__ = [
    "CalibrationViewModel",
    "SpectrumViewModel",
    "DeviceStatusViewModel",
]
