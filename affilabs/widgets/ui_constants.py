"""UI Constants and Configuration

Centralized constants for UI components to avoid duplication and magic values.
All hardcoded values used across datawindow.py, ui_sensorgram.py, and ui_processing.py
are defined here for maintainability.
"""

from __future__ import annotations

from typing import Final

# ============================================================================
# TABLE ITEM DELEGATE — Qt6/Windows QSS fix
# ============================================================================
# Import guard: only define when PySide6 is available (not during headless tests
# that import ui_constants for color constants only).
try:
    from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem
    from PySide6.QtCore import QModelIndex, Qt
    from PySide6.QtGui import QBrush, QPainter

    from PySide6.QtGui import QColor, QFont

    class TableItemDelegate(QStyledItemDelegate):
        """Delegate that correctly renders item background + foreground on Qt6/Windows.

        Problem: Qt6 on Windows uses QStyleSheetStyle which RE-APPLIES QSS rules
        *inside* drawControl(), clobbering any backgroundBrush we set on the option
        after initStyleOption().  Even setting option.backgroundBrush = blue right
        before super().paint() is overwritten when QSS says
        ``QTableWidget::item { background: transparent }``, leaving coloured
        foreground text invisible on a white background.

        Solution: when BackgroundRole data is set on an item, skip super().paint()
        entirely and manually fill the rect + draw text.  This sidesteps
        QStyleSheetStyle completely for those rows.  Rows with no custom background
        still go through super().paint() so normal QSS/hover/selection styling works.

        Usage::

            table.setItemDelegate(TableItemDelegate(table))
        """

        def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
            self.initStyleOption(option, index)

            bg = index.data(Qt.ItemDataRole.BackgroundRole)
            fg = index.data(Qt.ItemDataRole.ForegroundRole)

            if bg is None:
                # No custom background — let QSS / Qt handle normally.
                if fg is not None:
                    fg_brush = fg if isinstance(fg, QBrush) else QBrush(fg)
                    option.palette.setBrush(option.palette.ColorRole.Text, fg_brush)
                    option.palette.setBrush(option.palette.ColorRole.HighlightedText, fg_brush)
                super().paint(painter, option, index)
                return

            # ── Custom-background row: bypass QStyleSheetStyle entirely ──────────
            bg_brush = bg if isinstance(bg, QBrush) else QBrush(bg)

            # 1. Fill background.
            painter.save()
            painter.fillRect(option.rect, bg_brush)
            painter.restore()

            # 2. Determine text colour.
            if fg is not None:
                if isinstance(fg, QBrush):
                    text_color = fg.color()
                elif isinstance(fg, QColor):
                    text_color = fg
                else:
                    text_color = QColor(fg)
            else:
                text_color = option.palette.color(option.palette.ColorRole.Text)

            # 3. Draw text with correct font, alignment, and padding.
            text = index.data(Qt.ItemDataRole.DisplayRole)
            if text is not None:
                font_data = index.data(Qt.ItemDataRole.FontRole)
                painter.setFont(font_data if isinstance(font_data, QFont) else option.font)

                raw_align = index.data(Qt.ItemDataRole.TextAlignmentRole)
                align = raw_align if raw_align is not None else int(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )

                painter.save()
                painter.setPen(text_color)
                # 6 px left/right padding matches QSS `padding: 8px 6px`
                painter.drawText(option.rect.adjusted(6, 0, -6, 0), align, str(text))
                painter.restore()

except ImportError:
    TableItemDelegate = None  # type: ignore

# ============================================================================
# CYCLE TYPE STYLING
# ============================================================================


class CycleTypeStyle:
    """Color and abbreviation mapping for cycle types in queue/table views."""

    # Map of cycle type → (abbreviation, hex color)
    MAP: Final[dict[str, tuple[str, str]]] = {
        "Baseline":       ("BL", "#007AFF"),
        "Binding":        ("BN", "#FF9500"),
        "Kinetic":        ("KN", "#5856D6"),
        "Regeneration":   ("RG", "#FF3B30"),
        "Immobilization": ("IM", "#AF52DE"),
        "Blocking":       ("BK", "#FF2D55"),
        "Wash":           ("WS", "#00C7BE"),
        "Other":          ("OT", "#636366"),
        # Legacy alias — old saved files may contain "Concentration"; treat as Binding
        "Concentration":  ("CN", "#FF9500"),
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
# CHANNEL COLORS
# ============================================================================


class ChannelColors:
    """Professional channel color palette for bar charts and visualizations.

    Uses Apple iOS color scheme for consistency with app design.
    Colors are colorblind-friendly and have good visual contrast.
    """

    # Channel A-D colors (Apple iOS colors from CycleTypeStyle)
    MAP: Final[dict[str, str]] = {
        'A': '#007AFF',  # Blue - professional, primary channel
        'B': '#FF9500',  # Orange - warm, distinct
        'C': '#34C759',  # Green - natural, complements blue
        'D': '#AF52DE',  # Purple - unique, balanced palette
    }

    # RGBA tuples for PyQtGraph (with Alpha=200 for good visibility)
    RGBA_MAP: Final[dict[str, tuple[int, int, int, int]]] = {
        'A': (0, 122, 255, 200),      # Blue
        'B': (255, 149, 0, 200),       # Orange
        'C': (52, 199, 89, 200),       # Green
        'D': (175, 82, 222, 200),      # Purple
    }

    @classmethod
    def get_hex(cls, channel: str) -> str:
        """Get hex color for a channel.

        Args:
            channel: Channel identifier ('A', 'B', 'C', 'D')

        Returns:
            Hex color code (e.g., '#007AFF')
        """
        return cls.MAP.get(channel.upper(), '#86868B')

    @classmethod
    def get_rgba(cls, channel: str) -> tuple[int, int, int, int]:
        """Get RGBA tuple for a channel (for PyQtGraph).

        Args:
            channel: Channel identifier ('A', 'B', 'C', 'D')

        Returns:
            RGBA tuple (R, G, B, Alpha)
        """
        return cls.RGBA_MAP.get(channel.upper(), (134, 134, 139, 200))

    @classmethod
    def get_all_rgba_for_channels(cls, channels: list[str] = None) -> list[tuple[int, int, int, int]]:
        """Get RGBA colors for a list of channels in order.

        Args:
            channels: List of channel identifiers (default: ['A', 'B', 'C', 'D'])

        Returns:
            List of RGBA tuples
        """
        if channels is None:
            channels = ['A', 'B', 'C', 'D']
        return [cls.get_rgba(ch) for ch in channels]


# ============================================================================
# CYCLE CONFIGURATION
# ============================================================================


class CycleConfig:
    """Configuration for cycle type and time controls."""

    # Canonical cycle types for the Method Builder (P4SPR / manual injection context)
    TYPES: Final[list[str]] = [
        "Baseline",
        "Binding",
        "Regeneration",
        "Immobilization",
        "Blocking",
        "Wash",
        "Other",
    ]

    # Default durations (minutes) used by the Add Step menu
    DEFAULT_TIMES: Final[dict[str, float]] = {
        "Baseline":       5.0,
        "Binding":        8.5,   # 5 min contact + 3.5 min buffer
        "Regeneration":   0.5,   # 30 sec
        "Immobilization": 30.0,  # 30 min freestyle window (no injection prompt currently)
        "Blocking":       4.0,
        "Wash":           0.5,   # 30 sec
        "Other":          2.0,
    }

    # All types support a user-adjustable time limit
    TIME_ENABLED_TYPES: Final[frozenset[str]] = frozenset([
        "Baseline", "Binding", "Regeneration", "Immobilization",
        "Blocking", "Wash", "Other",
    ])

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

# Can be imported directly: from ui_constants import CYCLE_TYPES, etc.
CYCLE_TYPES: Final[list[str]] = CycleConfig.TYPES
COLUMNS_TO_TOGGLE: Final[frozenset[int]] = TableConfig.COLUMNS_TO_TOGGLE
