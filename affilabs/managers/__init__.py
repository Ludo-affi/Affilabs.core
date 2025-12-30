"""Managers package for AffiLabs.core.

This package contains manager classes that handle specific domains of functionality:
- CursorManager: Cursor positioning, range selection, snap-to-data
- FlagManager: Flag marker management
- ExportManager: Data export functionality
- DeviceConfigManager: Device configuration and OEM calibration workflow
- CalibrationManager: Calibration workflow delegation
- SegmentManager: EditableSegment lifecycle management for multi-cycle analysis
"""

from .calibration_manager import CalibrationManager
from .cursor_manager import CursorManager
from .device_config_manager import DeviceConfigManager
from .export_manager import ExportManager
from .flag_manager import FlagManager
from .segment_manager import SegmentManager

__all__ = [
    "CursorManager",
    "FlagManager",
    "ExportManager",
    "DeviceConfigManager",
    "CalibrationManager",
    "SegmentManager",
]
