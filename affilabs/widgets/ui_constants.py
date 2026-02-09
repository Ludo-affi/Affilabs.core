"""UI Constants and Configuration

Centralized constants for UI components to avoid duplication and magic values.
All hardcoded values used across datawindow.py, ui_sensorgram.py, and ui_processing.py
are defined here for maintainability.
"""

from __future__ import annotations

from typing import Final

# ============================================================================
# CYCLE TYPE STYLING
# ============================================================================


class CycleTypeStyle:
    """Color and abbreviation mapping for cycle types in queue/table views."""

    # Map of cycle type → (abbreviation, hex color)
    MAP: Final[dict[str, tuple[str, str]]] = {
        "Baseline": ("BL", "#007AFF"),
        "Concentration": ("CN", "#FF9500"),
        "Regeneration": ("RG", "#FF3B30"),
        "Association": ("AS", "#34C759"),
        "Dissociation": ("DS", "#5856D6"),
        "Wash": ("WS", "#00C7BE"),
        "Equilibration": ("EQ", "#86868B"),
        "Custom": ("CU", "#8E8E93"),
        "Flow": ("FL", "#007AFF"),
        "Static": ("ST", "#AF52DE"),
        "Auto-read": ("AR", "#FF2D55"),
        "Injection": ("IN", "#FF9500"),
        "Buffer": ("BF", "#34C759"),
        "Sample": ("SM", "#FF9500"),
        "Kinetic": ("KN", "#5856D6"),
    }

    _DEFAULT: Final[tuple[str, str]] = ("●", "#86868B")

    @classmethod
    def get(cls, cycle_type: str) -> tuple[str, str]:
        """Get (abbreviation, color) for a cycle type.

        Args:
            cycle_type: The cycle type string.

        Returns:
            Tuple of (abbreviation, hex_color). Falls back to default for unknown types.

        """
        return cls.MAP.get(cycle_type, cls._DEFAULT)


# ============================================================================
# CYCLE CONFIGURATION
# ============================================================================


class CycleConfig:
    """Configuration for cycle type and time controls."""

    # Cycle types
    TYPES: Final[list[str]] = ["Auto-read", "Baseline", "Flow", "Static"]

    # Cycle time options (minutes)
    TIME_OPTIONS: Final[list[int]] = [5, 15, 30, 60]

    # Default cycle times by type (minutes)
    DEFAULT_TIMES: Final[dict[str, int | None]] = {
        "Auto-read": None,  # No time limit
        "Baseline": 5,  # Fixed 5 minutes
        "Flow": 15,  # Default to 15 minutes
        "Static": 15,  # Default to 15 minutes
    }

    # Types where time dropdown should be enabled
    TIME_ENABLED_TYPES: Final[set[str]] = {"Flow", "Static"}

    @classmethod
    def get_default_time(cls, cycle_type: str) -> int | None:
        """Get default cycle time for a given type.

        Args:
            cycle_type: The cycle type string

        Returns:
            Default time in minutes, or None if no time limit

        """
        return cls.DEFAULT_TIMES.get(cycle_type)

    @classmethod
    def is_time_enabled(cls, cycle_type: str) -> bool:
        """Check if cycle time dropdown should be enabled for this type.

        Args:
            cycle_type: The cycle type string

        Returns:
            True if time dropdown should be enabled

        """
        return cycle_type in cls.TIME_ENABLED_TYPES


# ============================================================================
# TABLE CONFIGURATION
# ============================================================================


class TableConfig:
    """Configuration for cycle table views."""

    # Column indices to toggle between Tab 1 (simplified) and Tab 2 (detailed)
    COLUMNS_TO_TOGGLE: Final[frozenset[int]] = frozenset([2, 3, 4, 5, 6, 7])

    # Default view: Tab 1 (hide_columns = True)
    DEFAULT_HIDE_COLUMNS: Final[bool] = True


# ============================================================================
# UI STYLING
# ============================================================================


class UIStyle:
    """Centralized UI styling constants."""

    # Dropdown styling (used in both ui_sensorgram.py and ui_processing.py)
    DROPDOWN_STYLE: Final[str] = """
        QComboBox {
            background-color: white;
            border: 2px solid #0078d7;
            border-radius: 4px;
            padding: 6px;
            font-size: 11pt;
            font-weight: bold;
            color: black;
            min-width: 120px;
        }
        QComboBox:hover {
            border: 2px solid #005a9e;
            background-color: #f0f8ff;
        }
        QComboBox::drop-down {
            border: none;
            width: 30px;
        }
        QComboBox::down-arrow {
            image: url(:/icons/down_arrow.png);
            width: 12px;
            height: 12px;
        }
        QComboBox QAbstractItemView {
            background-color: white;
            border: 2px solid #0078d7;
            color: black;
            selection-background-color: #0078d7;
            selection-color: white;
            font-size: 11pt;
        }
    """

    # Label styling for dropdown labels
    LABEL_STYLE: Final[str] = """
        QLabel {
            font-size: 10pt;
            font-weight: bold;
            color: #333;
            padding: 2px;
        }
    """

    # Shaded region color (RGBA for cycle time visualization)
    CYCLE_TIME_REGION_COLOR: Final[tuple[int, int, int, int]] = (100, 100, 255, 50)

    # X-axis padding for cycle of interest graph (%)
    CYCLE_AXIS_PADDING: Final[float] = 0.1  # 10%


# ============================================================================
# EXPORT SINGLETON INSTANCES (for backward compatibility)
# ============================================================================

# Can be imported directly: from ui_constants import CYCLE_TYPES, CYCLE_TIME_OPTIONS, etc.
CYCLE_TYPES: Final[list[str]] = CycleConfig.TYPES
CYCLE_TIME_OPTIONS: Final[list[int]] = CycleConfig.TIME_OPTIONS
COLUMNS_TO_TOGGLE: Final[frozenset[int]] = TableConfig.COLUMNS_TO_TOGGLE
