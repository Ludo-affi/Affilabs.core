"""Dialogs Package

Extracted from affilabs_core_ui.py for better modularity.

Contains:
- StartupCalibProgressDialog: Non-modal calibration progress dialog
- DeviceConfigDialog: Device configuration dialog
- AdvancedSettingsDialog: Application settings and device information
"""

from .advanced_settings_dialog import AdvancedSettingsDialog
from .device_config_dialog import DeviceConfigDialog
from .startup_calib_dialog import StartupCalibProgressDialog

__all__ = [
    "StartupCalibProgressDialog",
    "DeviceConfigDialog",
    "AdvancedSettingsDialog",
]
