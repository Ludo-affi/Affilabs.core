"""DataWindow helper classes and module-level constants.

Extracted from datawindow.py to avoid circular imports with mixin files.

Contains:
- CYCLE_WINDOW_PADDING_FACTOR and other display constants
- RoundedFrame: Rounded-corner QWidget wrapper
- DataDict: TypedDict for sensorgram data
- Segment: A segment of the raw data with time/channel indexing
"""
from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING, Literal, TypedDict

if TYPE_CHECKING:
    from typing_extensions import Self
else:
    try:
        from typing import Self
    except ImportError:
        from typing_extensions import Self

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from affilabs.utils.logger import logger
from settings import CH_LIST, CYCLE_TIME, UNIT_LIST

# Cycle display constants (also re-exported for backward compat)
CYCLE_WINDOW_PADDING_FACTOR = 1.1  # Add 10% to cycle time for fixed window
CYCLE_Y_PADDING_TOP = 10           # RU to add above max Y value
CYCLE_Y_PADDING_BOTTOM = 5         # RU to subtract below min Y value

# Modern loop diagram colors
LOOP_BRUSH = QBrush(QColor(46, 227, 111))
SENSOR_BRUSH = QBrush(QColor(100, 150, 250))
LOOP_PEN = QPen(LOOP_BRUSH, 6)
SENSOR_PEN = QPen(SENSOR_BRUSH, 6)

PROGRESS_BAR_UPDATE_TIME = 100


class RoundedFrame(QWidget):
    """A responsive widget with rounded corners that wraps another widget."""

    def __init__(self: Self, child_widget: QWidget, border_radius: int = 8) -> None:
        """Initialize the rounded frame with a child widget."""
        super().__init__()
        self.border_radius = border_radius
        self.child_widget = child_widget

        # Set up layout with margin to account for border
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(child_widget)
        self.setLayout(layout)

        # Set background to transparent so custom painting works
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("RoundedFrame { background-color: white; }")

    def paintEvent(self: Self, event) -> None:
        """Paint the rounded rectangle background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Create rounded rectangle path
        rect = self.rect()
        painter.fillRect(rect, QColor(255, 255, 255))

        # Draw rounded corners by drawing a path
        from PySide6.QtGui import QPainterPath

        path = QPainterPath()
        path.addRoundedRect(
            QRect(0, 0, self.width(), self.height()),
            self.border_radius,
            self.border_radius,
        )
        painter.setClipPath(path)
        painter.fillPath(path, QColor(255, 255, 255))

        # Draw border
        painter.setClipRect(self.rect())
        painter.drawPath(path)

        painter.end()


class DataDict(TypedDict, total=False):
    """Dictionary for holding data."""

    lambda_times: dict[str, np.ndarray[int, np.dtype[np.float64]]]
    lambda_values: dict[str, np.ndarray[int, np.dtype[np.float64]]]
    buffered_lambda_times: dict[str, np.ndarray[int, np.dtype[np.float64]]]
    filtered_lambda_values: dict[str, np.ndarray[int, np.dtype[np.float64]]]
    filt: bool
    start: float
    rec: object


class Segment:
    """A segment of the raw data."""

    error: str | None

    def __init__(self: Self, seg_id: int, seg_start: float, seg_end: float) -> None:
        """Create a segment."""
        self.seg_id = seg_id
        self.start = seg_start
        self.end = seg_end
        self.ref_ch: str | None = None
        self.unit = "RU"
        self.start_index = {"a": 0, "b": 0, "c": 0, "d": 0}
        self.end_index = {"a": 0, "b": 0, "c": 0, "d": 0}
        self.shift = {"a": 0.0, "b": 0.0, "c": 0.0, "d": 0.0}
        self.seg_x: dict[str, np.ndarray[int, np.dtype[np.float64]]] = {}
        self.seg_y: dict[str, np.ndarray[int, np.dtype[np.float64]]] = {}
        self.name = str(seg_id + 1)
        self.note = ""
        self.cycle_type = "Auto-read"  # Default cycle type
        self.cycle_time: int | None = None  # Cycle time in minutes (None for Auto-read)

        if seg_end > seg_start:
            self.error = None
        else:
            self.error = "init end before start"

    def set_time(self: Self, seg_start: float, seg_end: float) -> None:
        """Set time of segment."""
        if (seg_end > seg_start) or (seg_start < 0):
            self.start = seg_start
            self.end = seg_end
            self.error = None
        else:
            self.error = "update end time before start time"

    def shift_time(self: Self, time_diff: float) -> None:
        """Shift time of segment."""
        self.start = self.start - time_diff
        self.end = self.end - time_diff

    def add_data(
        self: Self,
        sens_data: DataDict,
        unit: str,
        seg_ref_ch: str | None,
    ) -> None:
        """Pull segment data from the full sensorgram."""
        self.unit = unit
        unit_factor = UNIT_LIST[unit]
        try:
            self.ref_ch = seg_ref_ch
            if self.ref_ch not in CH_LIST:
                self.ref_ch = None
            if (self.start < self.end) or (self.start < 0):
                for ch in CH_LIST:
                    x_str: Literal["buffered_lambda_times", "lambda_times"]
                    y_str: Literal["filtered_lambda_values", "lambda_values"]
                    if sens_data["filt"]:
                        x_str = "buffered_lambda_times"
                        y_str = "filtered_lambda_values"
                    else:
                        x_str = "lambda_times"
                        y_str = "lambda_values"
                    self.seg_x[ch] = sens_data[x_str][ch]
                    self.seg_y[ch] = sens_data[y_str][ch] * unit_factor
                    ind = 0
                    if (len(self.seg_x[ch]) == 0) or (len(self.seg_y[ch]) == 0):
                        self.error = "no data"
                    else:
                        # Include 0.5 * CYCLE_TIME buffer before start cursor to properly establish 0,0 baseline
                        # This ensures Active Cycle graph displays the start point at 0,0
                        while (ind < (len(self.seg_x[ch]) - 2)) and (
                            self.seg_x[ch][ind] < (self.start - (0.5 * CYCLE_TIME))
                        ):
                            ind += 1
                        self.start_index[ch] = ind
                        while (ind < (len(self.seg_x[ch]) - 1)) and (
                            self.seg_x[ch][ind] < self.end
                        ):
                            ind += 1
                        self.end_index[ch] = ind
                        if self.start_index[ch] < self.end_index[ch]:
                            self.seg_x[ch] = self.seg_x[ch][
                                self.start_index[ch] : self.end_index[ch]
                            ]
                            self.seg_y[ch] = self.seg_y[ch][
                                self.start_index[ch] : self.end_index[ch]
                            ]
                        else:
                            self.error = "segment length = 0"

                # Normalize to START CURSOR position (self.start), not first data point
                # This ensures Active Cycle always shows start_cursor = 0,0
                for ch in CH_LIST:
                    if (len(self.seg_x[ch]) > 0) and (len(self.seg_y[ch]) > 0):
                        ref_index = 0
                        while (np.isnan(self.seg_y[ch][ref_index])) and (
                            ref_index < (len(self.seg_y[ch]) - 1)
                        ):
                            ref_index += 1
                        # Normalize time to START CURSOR position (not min_time)
                        # This makes Active Cycle display start at 0,0 regardless of timeline position
                        self.seg_x[ch] = self.seg_x[ch] - self.start
                        self.seg_y[ch] = self.seg_y[ch] - self.seg_y[ch][ref_index]
                        self.shift[ch] = self.seg_y[ch][-1]
                        self.error = None
                    else:
                        self.error = "seg x and y data empty"

                if self.ref_ch is not None:
                    try:
                        for ch in CH_LIST:
                            if ch == self.ref_ch:
                                pass
                            else:
                                if len(self.seg_x[ch]) > len(self.seg_x[self.ref_ch]):
                                    self.seg_x[ch] = self.seg_x[ch][0:-1]
                                    self.seg_y[ch] = self.seg_y[ch][0:-1]
                                elif len(self.seg_x[self.ref_ch]) > len(self.seg_x[ch]):
                                    self.seg_x[self.ref_ch] = self.seg_x[self.ref_ch][
                                        0:-1
                                    ]
                                    self.seg_y[self.ref_ch] = self.seg_y[self.ref_ch][
                                        0:-1
                                    ]
                                self.seg_y[ch] -= self.seg_y[self.ref_ch]
                                self.shift[ch] = self.seg_y[ch][-1]
                    except Exception as e:
                        logger.exception(f"error updating reference: {e}")
        except Exception as e:
            logger.exception(f"Error adding data: {e}")

    def add_info(self: Self, info: dict[str, str]) -> None:
        """Add info to segment with input validation and sanitization."""
        # Sanitize name - limit to 50 characters, remove problematic characters
        try:
            name_text = str(info.get("name", "")).strip()
            name_text = name_text.replace("\x00", "")  # Remove null bytes
            name_text = "".join(
                char for char in name_text if ord(char) >= 32 or char in "\n\r\t"
            )
            self.name = name_text[:50] if name_text else str(self.seg_id + 1)
        except Exception as e:
            logger.warning(f"Error sanitizing segment name: {e}")
            self.name = str(self.seg_id + 1)

        # Sanitize note - limit to 500 characters, remove problematic characters
        try:
            note_text = str(info.get("note", "")).strip()
            note_text = note_text.replace("\x00", "")  # Remove null bytes
            note_text = "".join(
                char for char in note_text if ord(char) >= 32 or char in "\n\r\t"
            )
            self.note = note_text[:500] if note_text else ""
        except Exception as e:
            logger.warning(f"Error sanitizing segment note: {e}")
            self.note = ""

        # Handle cycle type
        if "cycle_type" in info:
            try:
                cycle_type_text = str(info["cycle_type"]).strip()
                self.cycle_type = cycle_type_text if cycle_type_text else "Auto-read"
            except Exception:
                self.cycle_type = "Auto-read"

        # Handle cycle time
        if info.get("cycle_time"):
            try:
                self.cycle_time = int(info["cycle_time"])
            except (ValueError, TypeError):
                self.cycle_time = None
