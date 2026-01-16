from __future__ import annotations

# This module is riddled with long function that have too many statements, too many
# branches, and are too complex. It also contains a lot of catch all exception blocks.
# These should eventually be adressed, but for now we'll just turn off the warnings.
# ruff: noqa: PLR0912, PLR0915, C901, BLE001

"""Data processing widget."""

import csv
import datetime
import time
from bisect import bisect_left
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypedDict

# Python 3.11+ has UTC, older versions use timezone.utc
try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

if TYPE_CHECKING:
    from typing_extensions import Self
else:
    try:
        from typing import Self
    except ImportError:
        from typing_extensions import Self

import numpy as np
import pandas as pd
from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDoubleValidator,
    QFont,
    QPainter,
    QPen,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QHBoxLayout,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from scipy.signal import medfilt

from affilabs.ui.ui_processing import Ui_Processing
from affilabs.ui.ui_sensorgram import Ui_Sensorgram
from affilabs.utils.logger import logger
from affilabs.widgets.channelmenu import ChannelMenu
from affilabs.widgets.cycle_manager import CycleManager
from affilabs.widgets.cycle_table_dialog import CycleTableDialog
from affilabs.widgets.delegates import CycleTypeDelegate, TextInputDelegate
from affilabs.widgets.graphs import SegmentGraph, SensorgramGraph
from affilabs.widgets.message import show_message
from affilabs.widgets.metadata import Metadata, MetadataPrompt
from affilabs.widgets.segment_dataframe import SegmentDataFrame
from affilabs.widgets.table_manager import CycleTableManager
from settings import CH_LIST, CYCLE_TIME, MED_FILT_WIN, SW_VERSION, UNIT_LIST

TIME_ZONE = datetime.datetime.now(UTC).astimezone().tzinfo
# Tab 1 (default): Shows ID, Start, Cycle Type, Note (columns 0, 1, 8, 9)
# Tab 2: Shows ID, Start, Shift A-D (columns 0, 1, 3, 4, 5, 6)
# COLUMNS_TO_TOGGLE and CYCLE_TYPES now imported from widgets.ui_constants

ON_BRUSH = QBrush(Qt.GlobalColor.darkGray)
OFF_BRUSH = QBrush(Qt.GlobalColor.transparent)

# Modern loop diagram colors
LOOP_BRUSH = QBrush(QColor(46, 227, 111))  # Fresh green matching inject button
SENSOR_BRUSH = QBrush(QColor(100, 150, 250))  # Clear blue matching flush button
LOOP_PEN = QPen(LOOP_BRUSH, 6)

# Cycle display constants
CYCLE_WINDOW_PADDING_FACTOR = 1.1  # Add 10% to cycle time for fixed window
CYCLE_Y_PADDING_TOP = 10  # RU to add above max Y value
CYCLE_Y_PADDING_BOTTOM = 5  # RU to subtract below min Y value
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


class DataWindow(QWidget):
    """Data processing widget."""

    ui: Ui_Processing | Ui_Sensorgram

    export_error_signal = Signal()
    reset_graphs_sig = Signal()
    send_to_analysis_sig = Signal(dict, list, str)
    pull_sensorgram_sig = Signal()
    save_sig = Signal()

    def __init__(
        self: Self,
        data_source: Literal["dynamic", "static"],
        sidebar: Sidebar = None,
    ) -> None:
        """Make a data processing widget."""
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, on=True)
        self.data_source = data_source
        self._controls_detached = False
        self.reference_channel_id: str | None = None
        self.return_ref: str | None = None
        self.full_segment_view: SensorgramGraph
        self.SOI_view: SegmentGraph
        self.exp_clock_raw = 0.0
        self.reloading = False
        self.live_mode = True
        self.progress_bar_timer = QTimer()
        self.sidebar = sidebar
        # --- Sidebar integration for cycle controls ---
        from affilabs.widgets.cycle_controls_widget import CycleControlsWidget
        from affilabs.widgets.prime_pump_widget import PrimePumpWidget

        if self.sidebar is not None:
            # Graph Controls tab: Clear Graph button
            graph_controls = QWidget()
            from PySide6.QtCore import QSize
            from PySide6.QtWidgets import QFrame, QVBoxLayout

            graph_layout = QVBoxLayout(graph_controls)
            graph_layout.setContentsMargins(0, 0, 0, 0)
            graph_layout.setSpacing(8)

            # Styled container for Clear Graph button
            from affilabs.ui.styles import get_button_style, get_container_style

            clear_container = QFrame(graph_controls)
            clear_container.setObjectName("clear_graph_container")
            clear_container.setStyleSheet(get_container_style(elevated=True))
            clear_container.setFrameShape(QFrame.StyledPanel)
            clear_container.setFrameShadow(QFrame.Raised)
            clear_layout = QVBoxLayout(clear_container)
            clear_layout.setContentsMargins(12, 12, 12, 12)
            clear_layout.setSpacing(8)

            self.clear_graph_btn_sidebar = QPushButton("Clear Graph", clear_container)
            self.clear_graph_btn_sidebar.setMinimumSize(QSize(0, 35))
            self.clear_graph_btn_sidebar.setObjectName("clear_graph_btn_sidebar")
            self.clear_graph_btn_sidebar.setStyleSheet(get_button_style("error"))
            clear_layout.addWidget(self.clear_graph_btn_sidebar)
            graph_layout.addWidget(clear_container)

            # Add Display channel checkboxes to Graphic Control tab
            # Note: groupBox will be moved here after UI setup
            # Placeholder for now - actual widget moved in setup()

            graph_layout.addStretch()

            # Static tab: Cycle settings only
            static_controls = CycleControlsWidget(
                show_cycle_data_button=False,
                show_cycle_settings=True,
            )

            # Flow tab: Cycle settings + Cycle Data Table + Prime Pump button (identical structure to Static)
            flow_controls = QWidget()
            from PySide6.QtWidgets import QVBoxLayout

            flow_layout = QVBoxLayout(flow_controls)
            flow_layout.setContentsMargins(0, 0, 0, 0)
            flow_layout.setSpacing(8)

            flow_cycle_settings = CycleControlsWidget(
                show_cycle_data_button=False,
                show_cycle_settings=True,
            )
            flow_layout.addWidget(flow_cycle_settings)

            # Add Cycle Data Table button in styled container
            cycle_data_widget = CycleControlsWidget(
                show_cycle_data_button=True,
                show_cycle_settings=False,
            )
            cycle_data_widget.set_cycle_data_callback(self.open_cycle_table)
            flow_layout.addWidget(cycle_data_widget)

            prime_pump_widget = PrimePumpWidget()
            flow_layout.addWidget(prime_pump_widget)
            # Connect prime button to main handler if available
            if hasattr(self, "prime"):
                prime_pump_widget.set_prime_callback(self.prime)

            self.sidebar.set_widgets(
                cycle_controls_widget=graph_controls,
                static_cycle_controls=static_controls,
                flow_cycle_controls=flow_controls,
            )

        # display data processing or sensorgram page depending on source

        if self.data_source == "dynamic":
            self.ui = Ui_Sensorgram()
            self.ui.setupUi(self)
            self._fix_checkbox_styles()

            # White opaque rectangle as a standalone widget on the main UI
            from PySide6.QtCore import QSize
            from PySide6.QtWidgets import QFrame

            from ui.styles import Colors, Radius

            self.bg_rect_widget = QFrame(self)
            self.bg_rect_widget.setStyleSheet(
                f"background-color: {Colors.SURFACE};"
                f"border: 1px solid {Colors.ON_SURFACE_VARIANT};"
                f"border-radius: {Radius.MD}px;",
            )
            # Store margins from splitter edges (left, top, right, bottom)
            self.bg_rect_margin_left = -2
            self.bg_rect_margin_top = -4
            self.bg_rect_margin_right = -2
            self.bg_rect_margin_bottom = -4
            self.bg_rect_radius = 8
            # Will be sized and positioned in setup() based on splitter dimensions

            # Wire Inject button to external callback if provided
            self._inject_callback = None
            try:
                self.ui.inject_button.clicked.connect(self._on_inject_clicked)
            except Exception:
                # Defensive: if button not available, just log
                logger.warning("Inject button not available to wire")

        elif self.data_source == "static":
            self.ui = Ui_Processing()
            self.ui.setupUi(self)
            self._fix_checkbox_styles()
            self.ui.align_seg_btn.clicked.connect(self.send_segments_to_analysis)

        self.original_style = self.ui.save_segment_btn.styleSheet()
        self.edit_color = QColor(208, 245, 208)
        self.view_color = QColor(230, 230, 230)
        self.edit_style = (
            "background-color: rgb(208, 245, 208);"
            "border: 2px solid rgb(170, 170, 170);"
            "border-radius: 3px;"
        )
        self.view_style = (
            "background-color: rgb(220, 220, 220);"
            "border: 2px solid rgb(170, 170, 170);"
            "border-radius: 3px;"
        )

        # segment data
        self.current_segment: Segment | None = None
        self.live_segment_start: list[float] | None = None
        self.saved_segments = SegmentDataFrame()  # Using pandas DataFrame backend
        self.deleted_segment: Segment | None = None
        self.segment_edit: int | None = None
        self.viewing = False
        self.seg_count = 0
        self.saving = False
        self.restoring = False

        # settings and flags
        self.unit = "RU"
        self.busy = False
        self.ready = False

        # latest sensorgram data
        self.data: DataDict = {
            "lambda_times": {ch: np.array([]) for ch in CH_LIST},
            "lambda_values": {ch: np.array([]) for ch in CH_LIST},
            "buffered_lambda_times": {ch: np.array([]) for ch in CH_LIST},
            "filtered_lambda_values": {ch: np.array([]) for ch in CH_LIST},
            "filt": False,
        }

        # set up displays
        self.setup()

    def set_inject_callback(self: Self, callback) -> None:
        """Set callback for Inject button.

        The callback should perform the injection sequence using the
        application's pump control path (e.g., a PumpManager or controller).
        """
        self._inject_callback = callback

    @Slot()
    def _on_inject_clicked(self: Self) -> None:
        """Handle UI Inject button click by delegating to provided callback."""
        if getattr(self, "busy", False):
            show_message("System busy — cannot start injection right now.")
            return
        if callable(getattr(self, "_inject_callback", None)):
            try:
                self._inject_callback()
            except Exception as e:
                logger.error(f"Injection callback error: {e}")
                show_message("Injection failed to start. See logs.")
        else:
            logger.warning("No injection callback set; ignoring Inject click")
            show_message("Injection not configured in this build.")

        # Create object to hold metadata and allow user input
        self.metadata = Metadata(CH_LIST)

        # dialogs: reference channel, average channel, units, cycle table
        self.reference_channel_dlg = ChannelMenu(self.data_source, self.metadata)
        self.reference_channel_dlg.ref_ch_signal.connect(self.reference_change)
        self.reference_channel_dlg.unit_to_ru_signal.connect(self.unit_to_nm)
        self.reference_channel_dlg.unit_to_nm_signal.connect(self.unit_to_nm)
        self.reference_channel_dlg.cycle_marker_style_signal.connect(
            self.cycle_marker_style_changed,
        )
        if self.data_source == "static":
            # Disable filter for static data by unchecking the filter checkbox
            self.reference_channel_dlg.ui.filt_en.setChecked(False)

        # Create cycle table dialog (popup window)
        self.table_dialog = CycleTableDialog(self)
        self.table_dialog.set_segment_data(self.saved_segments, self.deleted_segment)
        self.table_dialog.row_deleted_sig.connect(self.delete_row)
        self.table_dialog.row_restored_sig.connect(self.restore_deleted)
        self.table_dialog.cell_edited_sig.connect(self.enter_edit_mode)
        self.table_dialog.table_toggled_sig.connect(self.toggle_table_style)

        # update segment data when cursor positions changed
        self.full_segment_view.segment_signal.connect(self.update_segment)

        # Connect shift values signal to update display box
        if hasattr(self.full_segment_view, "shift_values_signal"):
            self.full_segment_view.shift_values_signal.connect(
                self.update_shift_display_box,
            )

        # channel display options changed in full segment plot
        for ch in CH_LIST:
            getattr(self.ui, f"segment_{ch.upper()}").stateChanged.connect(
                partial(self.full_segment_view.display_channel_changed, ch),
            )
            getattr(self.ui, f"segment_{ch.upper()}").stateChanged.connect(
                partial(self.SOI_view.display_channel_changed, ch),
            )

            # Connect right-side display checkboxes (if they exist)
            right_checkbox_name = f"segment_{ch.upper()}_right"
            if hasattr(self.ui, right_checkbox_name):
                getattr(self.ui, right_checkbox_name).stateChanged.connect(
                    partial(self.full_segment_view.display_channel_changed, ch),
                )
                getattr(self.ui, right_checkbox_name).stateChanged.connect(
                    partial(self.SOI_view.display_channel_changed, ch),
                )
                # Sync left and right checkboxes
                getattr(self.ui, f"segment_{ch.upper()}").stateChanged.connect(
                    lambda state, cb_name=right_checkbox_name: (
                        getattr(self.ui, cb_name).blockSignals(True),
                        getattr(self.ui, cb_name).setChecked(
                            state == Qt.CheckState.Checked,
                        ),
                        getattr(self.ui, cb_name).blockSignals(False),
                    ),
                )
                getattr(self.ui, right_checkbox_name).stateChanged.connect(
                    lambda state, ch_name=ch: (
                        getattr(self.ui, f"segment_{ch_name.upper()}").blockSignals(
                            True,
                        ),
                        getattr(self.ui, f"segment_{ch_name.upper()}").setChecked(
                            state == Qt.CheckState.Checked,
                        ),
                        getattr(self.ui, f"segment_{ch_name.upper()}").blockSignals(
                            False,
                        ),
                    ),
                )

        if isinstance(self.ui, Ui_Processing):
            for ch in CH_LIST:
                getattr(self.ui, f"SOI_{ch.upper()}").toggled.connect(
                    getattr(self.ui, f"segment_{ch.upper()}").setChecked,
                )
                getattr(self.ui, f"segment_{ch.upper()}").toggled.connect(
                    getattr(self.ui, f"SOI_{ch.upper()}").setChecked,
                )

        # save segment button
        self.ui.save_segment_btn.clicked.connect(self.save_segment)

        # new segment button - now opens cycle data table
        if isinstance(self.ui, Ui_Sensorgram):
            self.ui.new_segment_btn.clicked.connect(self.open_cycle_table)
        else:
            self.ui.new_segment_btn.clicked.connect(self.new_segment)

        if isinstance(self.ui, Ui_Sensorgram) and hasattr(self.ui, "reset_segment_btn"):
            self.ui.reset_segment_btn.hide()
        elif hasattr(self.ui, "reset_segment_btn"):
            self.ui.reset_segment_btn.clicked.connect(self.reset_graphs)

        # clear graph button (only in sensorgram UI)
        if isinstance(self.ui, Ui_Sensorgram):
            # Connect sidebar Clear Graph button if it exists
            if hasattr(self, "clear_graph_btn_sidebar"):
                self.clear_graph_btn_sidebar.clicked.connect(self.reset_graphs)

            # Legacy buttons (hidden)
            if hasattr(self.ui, "clear_graph_btn"):
                self.ui.clear_graph_btn.clicked.connect(self.reset_graphs)

            # Connect Clear button in Sensorgram graph (top-left)
            if (
                hasattr(self.full_segment_view, "clear_button")
                and self.full_segment_view.clear_button
            ):
                self.full_segment_view.clear_button.clicked.connect(self.reset_graphs)

            # Connect legend checkboxes in Cycle of Interest graph to sync with UI checkboxes
            if hasattr(self.SOI_view, "legend_checkboxes"):
                for ch in CH_LIST:
                    if ch in self.SOI_view.legend_checkboxes:
                        # When legend checkbox changes, update the UI checkbox
                        legend_cb = self.SOI_view.legend_checkboxes[ch]
                        ui_cb = getattr(self.ui, f"segment_{ch.upper()}")

                        # Legend checkbox -> UI checkbox
                        legend_cb.stateChanged.connect(
                            lambda state, ui_checkbox=ui_cb: (
                                ui_checkbox.blockSignals(True),
                                ui_checkbox.setChecked(
                                    state == Qt.CheckState.Checked.value,
                                ),
                                ui_checkbox.blockSignals(False),
                            ),
                        )

                        # UI checkbox -> Legend checkbox (already connected via display_channel_changed)

            # Connect adjust margins button
            if hasattr(self.ui, "adjust_margins_btn"):
                self.ui.adjust_margins_btn.clicked.connect(
                    self.open_margin_adjust_dialog,
                )
            # Connect adjust margins button
            if hasattr(self.ui, "adjust_margins_btn"):
                self.ui.adjust_margins_btn.clicked.connect(
                    self.open_margin_adjust_dialog,
                )

        # open cycle table dialog button (only in sensorgram UI)
        if isinstance(self.ui, Ui_Sensorgram):
            self.ui.open_table_btn.clicked.connect(self.open_cycle_table)

        # For processing UI, keep old table setup
        if isinstance(self.ui, Ui_Processing):
            # data table add/remove row
            self.ui.delete_row_btn.clicked.connect(self.delete_row)
            self.ui.add_row_btn.clicked.connect(self.restore_deleted)

            # Set up cycle type dropdown for column 8
            cycle_type_delegate = CycleTypeDelegate(self.ui.data_table)
            self.ui.data_table.setItemDelegateForColumn(8, cycle_type_delegate)

            # Set up text input delegates with character limits for name and note columns
            text_delegate_name = TextInputDelegate(self.ui.data_table)
            text_delegate_note = TextInputDelegate(self.ui.data_table)
            self.ui.data_table.setItemDelegateForColumn(
                0,
                text_delegate_name,
            )  # Name column
            self.ui.data_table.setItemDelegateForColumn(
                9,
                text_delegate_note,
            )  # Note column

            # data table
            self.ui.data_table.cellDoubleClicked.connect(self.enter_edit_mode)
            self.ui.data_table.cellClicked.connect(self.enter_view_mode)
            self.ui.table_toggle.clicked.connect(self.toggle_table_style)

            # Set up page indicator circles for table toggle
            self.ui.page_indicator.setScene(QGraphicsScene())
            self.circles = (
                QGraphicsEllipseItem(-4, 0, 5, 5),
                QGraphicsEllipseItem(4, 0, 5, 5),
            )
            for c in self.circles:
                self.ui.page_indicator.scene().addItem(c)

            # Initialize table manager (handles table operations)
            self.table_manager = CycleTableManager(
                table_widget=self.ui.data_table,
                toggle_indicators=self.circles,
            )

        # open the average channel and reference channel dialog
        if isinstance(self.ui, Ui_Processing):
            self.ui.reference_channel_btn.clicked.connect(
                self.open_reference_channel_dlg,
            )

        # text fields
        self.ui.left_cursor_time.returnPressed.connect(self.update_left)
        self.ui.right_cursor_time.returnPressed.connect(self.update_right)

        # Initialize cycle manager (handles cycle type/time logic)
        # Only Processing UI has cycle type/time dropdowns
        if isinstance(self.ui, Ui_Processing):
            self.cycle_manager = CycleManager(
                cycle_type_dropdown=self.ui.current_cycle_type,
                cycle_time_dropdown=self.ui.current_cycle_time,
                sensorgram_graph=self.full_segment_view,
            )
        else:
            # Sensorgram doesn't have cycle controls in UI
            self.cycle_manager = None

        # Note: table_manager only exists for Ui_Processing, sensorgram uses table_dialog
        self.enable_controls(data_ready=False)

        # live view and reset segment button if dynamic window, imports if static window
        if self.data_source == "dynamic" and isinstance(self.ui, Ui_Sensorgram):
            self.ui.live_btn.setChecked(True)
            self.ui.live_btn.clicked.connect(self.toggle_view)
            self.reference_channel_dlg.ui.export_data.clicked.connect(
                self.export_trigger,
            )

        elif isinstance(self.ui, Ui_Processing):
            self.ui.export_raw_data_btn.clicked.connect(self.export_raw_data)
            self.ui.export_table_btn.clicked.connect(self.export_table)

            # Add Excel export button next to raw data export
            self.export_excel_btn = QPushButton(self.ui.export_raw_data_btn.parent())
            self.export_excel_btn.setObjectName("export_excel_btn")
            self.export_excel_btn.setText("📊 Excel")
            self.export_excel_btn.setToolTip("Export data to Excel format (.xlsx)")
            self.export_excel_btn.setStyleSheet(
                "QPushButton {"
                "  background: #1E8E3E;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  padding: 8px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: #188038;"
                "}"
                "QPushButton:pressed {"
                "  background: #0F5C26;"
                "}",
            )
            # Position it near the export button
            raw_btn_geom = self.ui.export_raw_data_btn.geometry()
            self.export_excel_btn.setGeometry(
                raw_btn_geom.x() + 35,
                raw_btn_geom.y(),
                70,
                30,
            )
            self.export_excel_btn.clicked.connect(self.export_to_excel)

            self.ui.import_sens_btn.clicked.connect(self.pull_from_sensorgram)
            self.ui.import_raw_data_btn.clicked.connect(self.import_raw_data)
            self.ui.import_table_btn.clicked.connect(self.import_table)
            self.ui.new_segment_btn.clicked.connect(self.start_from_last_seg)

        self.new_segment()

        # Move display groupBox to Graphic Control tab in sidebar
        if self.sidebar is not None and isinstance(self.ui, Ui_Sensorgram):
            # Get the Graphic Control tab
            graphic_control_tab = None
            for i in range(self.sidebar.tabWidget.count()):
                if self.sidebar.tabWidget.tabText(i) == "Graphic Control":
                    graphic_control_tab = self.sidebar.tabWidget.widget(i)
                    break

            if graphic_control_tab and hasattr(self.ui, "groupBox"):
                # The tab content is wrapped in a QScrollArea
                scroll_area = graphic_control_tab.findChild(QScrollArea)
                if scroll_area:
                    # Get the content widget inside the scroll area
                    content_widget = scroll_area.widget()
                    if content_widget:
                        layout = content_widget.layout()
                        if layout:
                            # Remove groupBox from its current parent
                            self.ui.groupBox.setParent(None)
                            # Insert display groupBox after clear button, before stretch
                            # Layout structure: clear_container, stretch
                            # We want: clear_container, groupBox, stretch
                            if layout.count() > 0:
                                # Remove the stretch temporarily
                                stretch_item = None
                                for i in range(layout.count()):
                                    item = layout.itemAt(i)
                                    if item and item.spacerItem():
                                        stretch_item = layout.takeAt(i)
                                        break

                                # Add groupBox
                                layout.addWidget(self.ui.groupBox)

                                # Re-add stretch at the end
                                if stretch_item:
                                    layout.addItem(stretch_item)
                                else:
                                    layout.addStretch()

        # Add settings panel to Settings tab in sidebar
        if self.sidebar is not None:
            from affilabs.widgets.settings_panel import SettingsPanel

            settings_panel = SettingsPanel()
            settings_panel.adjust_margins_requested.connect(
                self.open_margin_adjust_dialog,
            )
            settings_tab = self.sidebar.get_settings_tab()
            if settings_tab:
                layout = settings_tab.layout()
                if layout:
                    # Clear placeholder
                    while layout.count():
                        item = layout.takeAt(0)
                        if item.widget():
                            item.widget().deleteLater()
                    # Add settings panel
                    settings_panel.setParent(settings_tab)
                    layout.addWidget(settings_panel)

            # Add data export panel to Data tab (for sensorgram)
            if isinstance(self.ui, Ui_Sensorgram):
                from affilabs.widgets.data_panel import DataPanel

                self.data_panel = DataPanel()
                self.data_panel.export_triggered.connect(self.export_trigger)
                self.data_panel.export_excel_triggered.connect(self.export_to_excel)
                data_tab = self.sidebar.get_data_tab()
                if data_tab:
                    layout = data_tab.layout()
                    if layout:
                        # Clear placeholder
                        while layout.count():
                            item = layout.takeAt(0)
                            if item.widget():
                                item.widget().deleteLater()
                        # Add data panel
                        self.data_panel.setParent(data_tab)
                        layout.addWidget(self.data_panel)

        # Add text box validators
        self.ui.left_cursor_time.setValidator(QDoubleValidator())
        self.ui.right_cursor_time.setValidator(QDoubleValidator())
        if isinstance(self.ui, Ui_Sensorgram):
            self.ui.flow_rate.setValidator(QDoubleValidator(-60000, 60000, 1))

        # Circles for page indicator already created before table_manager initialization

        # Set up valve indicator diagram
        if isinstance(self.ui, Ui_Sensorgram):
            self.ui.loop_diagram.setScene(QGraphicsScene())

            # Reduced size: 80x80 (was 100x100)
            self.loop = QGraphicsEllipseItem(0, 0, 80, 80)
            self.loop_line = QGraphicsLineItem(-15, 0, 95, 0)
            self.sensor_line = QGraphicsLineItem(-15, 95, 95, 95)
            self.loop_label = QGraphicsSimpleTextItem("Loop")
            self.sensor_label = QGraphicsSimpleTextItem("Sensor")

            # Create modern styled pens with rounded caps (thinner: 5px instead of 6px)
            loop_pen = QPen(LOOP_BRUSH, 5)
            loop_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            sensor_pen = QPen(SENSOR_BRUSH, 5)
            sensor_pen.setCapStyle(Qt.PenCapStyle.RoundCap)

            self.loop.setPen(loop_pen)
            self.loop_line.setPen(loop_pen)
            self.sensor_line.setPen(sensor_pen)

            # Smaller font: 10pt instead of 12pt
            font = self.loop_label.font()
            font.setPointSize(10)
            font.setWeight(QFont.Weight.Medium)

            self.loop_label.setFont(font)
            self.loop_label.setBrush(LOOP_BRUSH)
            self.loop_label.setPos(100, -10)

            self.sensor_label.setFont(font)
            self.sensor_label.setBrush(SENSOR_BRUSH)
            self.sensor_label.setPos(100, 85)

            self.ui.loop_diagram.scene().addItem(self.loop)
            self.ui.loop_diagram.scene().addItem(self.loop_line)
            self.ui.loop_diagram.scene().addItem(self.sensor_line)
            self.ui.loop_diagram.scene().addItem(self.loop_label)
            self.ui.loop_diagram.scene().addItem(self.sensor_label)

        # Table manager initialized above with default Tab 1 view
        # (no need for separate hide_columns variable)

        # Hide progress bar until injection
        if isinstance(self.ui, Ui_Sensorgram):
            self.ui.progress_bar.hide()
            self.progress_bar_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self.progress_bar_timer.setInterval(PROGRESS_BAR_UPDATE_TIME)
            self.progress_bar_timer.timeout.connect(self.increment_progress_bar)

    @Slot()
    def increment_progress_bar(self: Self) -> None:
        """Increment the progress bar by 100 and check if it's reached the maximum."""
        if not isinstance(self.ui, Ui_Sensorgram):
            raise TypeError

        current = self.ui.progress_bar.value() + PROGRESS_BAR_UPDATE_TIME
        if current >= self.ui.progress_bar.maximum():
            self.cancel_progress_bar()
        else:
            self.ui.progress_bar.setValue(current)

    @Slot()
    def start_progress_bar(self: Self, time: int) -> None:
        """Start the progress bar counting for a certain number of seconds."""
        if not isinstance(self.ui, Ui_Sensorgram):
            raise TypeError

        self.ui.progress_bar.setMaximum(time)
        self.ui.progress_bar.setValue(0)
        self.ui.inject_button.setText("Cancel")
        self.ui.regen_button.hide()
        self.ui.flush_button.hide()
        self.ui.flow_rate_box.hide()
        self.ui.progress_bar.show()
        self.loop.setRect(0, 20, 100, 100)
        self.loop.setPen(SENSOR_PEN)
        self.progress_bar_timer.start()

    def cancel_progress_bar(self: Self) -> None:
        """Stop and cancel the progress."""
        if not isinstance(self.ui, Ui_Sensorgram):
            raise TypeError

        self.progress_bar_timer.stop()
        self.ui.progress_bar.hide()
        self.ui.inject_button.setText("Inject")
        self.ui.regen_button.show()
        self.ui.flush_button.show()
        self.ui.flow_rate_box.show()
        self.loop.setRect(0, 0, 100, 100)
        self.loop.setPen(LOOP_PEN)

    def update_table_style(self: Self) -> None:
        """Update the style of the cycle table."""
        self._get_table_manager().update_table_style()

    def _fix_checkbox_styles(self: Self) -> None:
        """Fix checkbox and label styling to use global theme.

        The UI files have inline styles that override the global theme,
        causing gray shades and invisible checkmarks. This method clears
        those problematic inline styles while preserving text colors.
        """
        # Fix channel checkboxes - clear background but keep text color
        for checkbox_name in ["segment_A", "segment_B", "segment_C", "segment_D"]:
            if hasattr(self.ui, checkbox_name):
                checkbox = getattr(self.ui, checkbox_name)
                # Get current text color from stylesheet
                current_style = checkbox.styleSheet()
                if "color:" in current_style:
                    # Extract just the color line
                    import re

                    color_match = re.search(r"color:\s*([^;]+);", current_style)
                    if color_match:
                        color_value = color_match.group(1).strip()
                        # Set only text color, let global theme handle the rest
                        checkbox.setStyleSheet(
                            f"QCheckBox {{ color: {color_value}; background-color: transparent; }}",
                        )
                else:
                    checkbox.setStyleSheet(
                        "QCheckBox { background-color: transparent; }",
                    )

    @Slot()
    def toggle_table_style(self: Self) -> None:
        """Toggle the style of the table."""
        self._get_table_manager().toggle_table_style()

    def resizeEvent(self: Self, _: object) -> None:  # noqa: N802
        """Resize the widget - splitter handles graph resizing automatically."""
        super().resizeEvent(_)

        # Reposition background rectangle when window resizes
        self._position_bg_rect()
        self._position_channel_overlay()

    def _position_bg_rect(self: Self) -> None:
        """Position and size the background rectangle to match graph area with margins."""
        if hasattr(self, "bg_rect_widget") and hasattr(self, "graph_splitter"):
            # Get splitter's geometry in DataWindow's coordinate space
            splitter_pos = self.graph_splitter.pos()
            splitter_width = self.graph_splitter.width()
            splitter_height = self.graph_splitter.height()

            # Calculate rectangle geometry based on splitter size minus margins
            rect_x = splitter_pos.x() + self.bg_rect_margin_left
            rect_y = splitter_pos.y() + self.bg_rect_margin_top
            rect_width = (
                splitter_width - self.bg_rect_margin_left - self.bg_rect_margin_right
            )
            rect_height = (
                splitter_height - self.bg_rect_margin_top - self.bg_rect_margin_bottom
            )

            # Set geometry (position and size) in DataWindow coordinate space
            self.bg_rect_widget.setGeometry(rect_x, rect_y, rect_width, rect_height)

            # Show and ensure it's behind the splitter
            if not self.bg_rect_widget.isVisible():
                self.bg_rect_widget.lower()
                self.bg_rect_widget.show()
                self.graph_splitter.raise_()

    def _position_channel_overlay(self: Self) -> None:
        """Keep the channel display block aligned with the sensorgram graph edge."""
        if not hasattr(self, "channel_overlay"):
            return

        if not hasattr(self, "sensorgram_frame") or not hasattr(
            self,
            "full_segment_view",
        ):
            return

        # Map graph's origin into the sensorgram frame so we can align precisely
        top_left = self.full_segment_view.mapTo(self.sensorgram_frame, QPoint(0, 0))
        x_offset = getattr(self, "_channel_overlay_left_offset", 0)
        y_offset = getattr(self, "_channel_overlay_top_offset", 0)
        self.channel_overlay.move(top_left.x() + x_offset, top_left.y() + y_offset)
        self.channel_overlay.raise_()

    def eventFilter(self, obj, event):
        """Handle double-click on splitter handle to swap graph ratios and splitter resize."""
        import time

        from PySide6.QtCore import QEvent

        # Check if double-click on splitter or its handle
        if hasattr(self, "graph_splitter"):
            is_splitter = obj == self.graph_splitter
            is_handle = obj == self.graph_splitter.handle(1)

            if is_splitter or is_handle:
                event_type = event.type()

                # Reposition background rectangle when splitter resizes
                if event_type == QEvent.Type.Resize and is_splitter:
                    self._position_bg_rect()

                # Manual double-click detection using time tracking
                if event_type == QEvent.Type.MouseButtonPress:
                    current_time = time.time()

                    # Initialize last_click_time if it doesn't exist
                    if not hasattr(self, "_last_click_time"):
                        self._last_click_time = 0

                    # Check if this is a double-click (< 500ms between clicks)
                    time_diff = current_time - self._last_click_time
                    if time_diff < 0.5:
                        logger.info("Double-click detected - swapping graph ratios")
                        self._swap_graph_ratios()
                        self._last_click_time = 0  # Reset to prevent triple-click
                        return True
                    self._last_click_time = current_time

        return super().eventFilter(obj, event)

    def _swap_graph_ratios(self):
        """Swap graph size ratios: 30/70 ↔ 70/30."""
        if not hasattr(self, "graph_splitter"):
            return

        self._detail_focused = not self._detail_focused

        if self._detail_focused:
            # Detail view gets 70% (default)
            self.graph_splitter.setStretchFactor(0, 3)  # Overview: 30%
            self.graph_splitter.setStretchFactor(1, 7)  # Detail: 70%
            logger.debug("Graph ratio: Overview 30% / Detail 70%")
        else:
            # Overview gets 70% (reversed)
            self.graph_splitter.setStretchFactor(0, 7)  # Overview: 70%
            self.graph_splitter.setStretchFactor(1, 3)  # Detail: 30%
            logger.debug("Graph ratio: Overview 70% / Detail 30%")

        # Force splitter to update sizes
        total_height = self.graph_splitter.height()
        if self._detail_focused:
            sizes = [int(total_height * 0.3), int(total_height * 0.7)]
        else:
            sizes = [int(total_height * 0.7), int(total_height * 0.3)]
        self.graph_splitter.setSizes(sizes)

    def is_busy(self: Self) -> bool:
        """Check if the widget is busy."""
        return self.busy

    def enable_controls(self: Self, *, data_ready: bool = False) -> None:
        """Enable controls."""
        self.ready = data_ready
        # TODO(Ryan): Disable sensorgram controls?
        # 000

    def set_filter(self: Self, *, filt_en: bool, med_filt_win: int) -> None:
        """Set filter size on the data."""
        if self.data_source == "static":
            self.data["filt"] = filt_en
            if filt_en:
                for ch in CH_LIST:
                    self.data["filtered_lambda_values"][ch] = medfilt(
                        self.data["lambda_values"][ch],
                        med_filt_win,
                    )
            self.update_data(self.data)
            for seg in self.saved_segments:
                seg.add_data(self.data, self.unit, seg.ref_ch)
            self.quick_segment_update()

    @Slot(dict)
    def update_data(self: Self, app_data: DataDict) -> None:
        """Update plot data."""
        try:
            if self.data_source == "dynamic":
                self.busy = True
                self.data = app_data
                y_data = self.data["lambda_values"]
                x_data = self.data["lambda_times"]
                if self.data["filt"]:
                    y_data = self.data["filtered_lambda_values"]
                    x_data = self.data["buffered_lambda_times"]
                if len(y_data["d"]) > 0:
                    self.enable_controls(data_ready=True)
                else:
                    self.enable_controls(data_ready=False)
                if (not self.full_segment_view.is_updating()) and (
                    not self.SOI_view.is_updating()
                ):
                    self.full_segment_view.update(y_data, x_data)
                else:
                    logger.debug("busy updating")

                # Prefer monotonic start if available to avoid wall-clock jumps
                if "start_perf" in self.data:
                    self.exp_clock_raw = time.perf_counter() - self.data["start_perf"]
                else:
                    self.exp_clock_raw = time.time() - self.data["start"]
                if self.exp_clock_raw == 0:
                    self.ui.exp_clock.setText("00h 00m 00s")
                    # Also update the one in Cycle Settings
                    if hasattr(self.ui, "exp_clock_settings"):
                        self.ui.exp_clock_settings.setText("00h 00m 00s")
                else:
                    time_str = (
                        f"{int(self.exp_clock_raw / 3600):02d}h "
                        f"{int((self.exp_clock_raw % 3600) / 60):02d}m "
                        f"{int(self.exp_clock_raw % 60):02d}s"
                    )
                    # Only update if the widget exists
                    if hasattr(self.ui, "exp_clock"):
                        self.ui.exp_clock.setText(time_str)
                    # Also update the one in Cycle Settings
                    if hasattr(self.ui, "exp_clock_settings"):
                        self.ui.exp_clock_settings.setText(time_str)
                if (self.segment_edit is not None or self.viewing) and isinstance(
                    self.ui,
                    Ui_Processing,
                ):
                    end = self.exp_clock_raw
                    if (not self.live_mode) and (self.live_segment_start is not None):
                        end = self.live_segment_start[1]
                    self.ui.end_time.setText(f"{end:.2f}")
                self.busy = False
            elif len(self.data["lambda_times"]["d"]) == 0:
                logger.debug("No data imported to display")
                self.update_left(preset=True, preset_val=0)
                self.update_right(preset=True, preset_val=1)
            elif self.data["filt"]:
                self.full_segment_view.update(
                    self.data["filtered_lambda_values"],
                    self.data["buffered_lambda_times"],
                )
            else:
                self.full_segment_view.update(
                    self.data["lambda_values"],
                    self.data["lambda_times"],
                )
        except Exception as e:
            logger.exception(f"Error during sensorgram update: {e}")

    def quick_segment_update(self: Self) -> None:
        """Update segments with defaults."""
        if self.current_segment:
            self.update_segment(
                self.current_segment.start,
                self.current_segment.end,
                update=False,
                force=True,
            )

    def update_segment(
        self: Self,
        start: float,
        end: float,
        update: bool,  # noqa: FBT001
        *,
        force: bool = False,
    ) -> None:
        """Update the segments table."""
        if self.ready:
            if self.data_source == "dynamic":
                self.busy = True

            allow_update = True
            if (
                self.viewing
                or self.saving
                or (
                    (self.segment_edit is not None)
                    and (self.data_source == "dynamic")
                    and update
                )
            ):
                allow_update = False

            if (allow_update or force) and self.current_segment is not None:
                self.current_segment.set_time(start, end)
                self.current_segment.add_data(
                    self.data,
                    self.unit,
                    self.current_segment.ref_ch,
                )
                if self.current_segment.error is None:
                    self.SOI_view.update_display(self.current_segment)

                    # Update cycle time shaded region position as time advances
                    if self.full_segment_view.cycle_time_region is not None:
                        cycle_time = self.cycle_manager.get_current_time_minutes()
                        if cycle_time is not None:
                            self.full_segment_view.update_cycle_time_region(cycle_time)
                else:
                    logger.debug(f"{self.current_segment.error}")

            self.update_displayed_values()
            self.busy = False

    def update_shift_display_box(self: Self, shift_data: dict) -> None:
        """Update the shift display box with shift values."""
        # shift_display_box removed from UI - status now in Flow tab sidebar

    def update_left(
        self: Self,
        *,
        preset: bool = False,
        preset_val: int = 0,
        is_update: bool = False,
    ) -> None:
        """Update left end of segment."""
        try:
            if preset:
                if self.data_source == "dynamic":
                    self.full_segment_view.set_left(float(preset_val), update=is_update)
                else:
                    self.full_segment_view.set_left(float(preset_val), update=False)
            else:
                self.full_segment_view.set_left(
                    float(self.ui.left_cursor_time.text()),
                    update=is_update,
                )
            self.ui.left_cursor_time.clearFocus()
        except Exception as e:
            if type(e) == ValueError:
                logger.debug("non-numerical value entered for left cursor")
                self.ui.left_cursor_time.setText("")

    def update_right(
        self: Self,
        *,
        preset: bool = False,
        preset_val: int = 0,
        latest: bool = False,
    ) -> None:
        """Update right end of segment."""
        try:
            if preset:
                self.full_segment_view.set_right(float(preset_val), update=False)
            if latest:
                self.full_segment_view.set_right(
                    float(self.full_segment_view.get_time()),
                    update=False,
                )
            else:
                self.full_segment_view.set_right(
                    float(self.ui.right_cursor_time.text()),
                    update=False,
                )
            self.ui.right_cursor_time.clearFocus()
        except Exception as e:
            if type(e) == ValueError:
                logger.debug("non-numerical value entered for right cursor")
                self.ui.right_cursor_time.setText("")

    def start_from_last_seg(self: Self) -> None:
        """Create new segment starting from the last segment."""
        if self.segment_edit is None:
            if len(self.saved_segments) > 0:
                new_end = (
                    self.saved_segments[-1].end - self.saved_segments[-1].start
                ) + self.saved_segments[-1].end
                self.full_segment_view.set_right(new_end, update=True)
                self.full_segment_view.set_left(
                    self.saved_segments[-1].end,
                    update=False,
                )
        else:
            self.new_segment()

    def new_segment(self: Self) -> None:
        """Create a new segment."""
        # Clear gray zone and re-enable auto-ranging
        self.full_segment_view.hide_cycle_time_region()
        self.full_segment_view.fixed_window_active = False
        self.SOI_view.fixed_window_active = False
        self.full_segment_view.plot.enableAutoRange(axis="x", enable=True)
        self.SOI_view.plot.enableAutoRange(axis="x", enable=True)

        if self.segment_edit is not None:
            self.reassert_row(self.segment_edit)
        self.segment_edit = None
        self.viewing = False
        if isinstance(self.ui, Ui_Processing):
            self.ui.reference_channel_btn.setEnabled(True)
            self.ui.curr_seg_box.setEnabled(True)
        self.full_segment_view.movable_cursors(state=True)
        self.cursors_text_edit(state=True)
        self._get_table_widget().clearSelection()
        self.set_row_properties()
        if self.data_source == "dynamic":
            self.ui.save_segment_btn.setText("Start\nCycle")
            self.ui.save_segment_btn.setStyleSheet(self.original_style)
            self.ui.new_segment_btn.setText("Start at\nLive Time")
            self.ui.new_segment_btn.setStyleSheet(self.original_style)
            if self.live_segment_start is not None:
                self.current_segment = Segment(
                    self.seg_count,
                    self.live_segment_start[0],
                    self.live_segment_start[1],
                )
                self.full_segment_view.move_both_cursors(
                    self.current_segment.start,
                    self.current_segment.end,
                )
                logger.debug(f"returning to live segment {self.current_segment.seg_id}")
                self.live_segment_start = None
            else:
                current_time = self.full_segment_view.get_time()
                self.current_segment = Segment(
                    self.seg_count,
                    current_time,
                    current_time + 2,
                )
                self.full_segment_view.move_both_cursors(
                    self.current_segment.start,
                    self.current_segment.end,
                )
                logger.debug(f"new segment {self.current_segment.seg_id}")
            self.set_live(on=self.live_mode)
        else:
            self.current_segment = Segment(self.seg_count, 0, 1)
            self.update_segment(
                self.full_segment_view.get_left(),
                self.full_segment_view.get_right(),
                update=False,
            )
            self.ui.save_segment_btn.setText("Start\nCycle")
            self.ui.save_segment_btn.setStyleSheet(self.original_style)
            self.ui.new_segment_btn.setText("Start from\nLast Cycle")
            self.ui.new_segment_btn.setStyleSheet(self.original_style)
        self.full_segment_view.block_updates = False
        if self.return_ref is None:
            self.return_ref = self.reference_channel_dlg.ref_ch
        self.set_reference(self.return_ref)
        self.current_segment.ref_ch = self.return_ref
        self.quick_segment_update()
        self.return_ref = None

    def update_displayed_values(self: Self) -> None:
        """Update displayed values and cursor labels."""
        # Update cursor labels with time values
        left_time = self.full_segment_view.left_cursor_pos
        right_time = self.full_segment_view.right_cursor_pos
        self.full_segment_view.left_cursor.label.setFormat(f"Start\n{left_time:.2f}s")
        self.full_segment_view.right_cursor.label.setFormat(f"Stop\n{right_time:.2f}s")

        if not self.ui.left_cursor_time.hasFocus():
            self.ui.left_cursor_time.setText(
                f"{left_time:.2f}",
            )
        if not self.ui.right_cursor_time.hasFocus():
            self.ui.right_cursor_time.setText(
                f"{right_time:.2f}",
            )

        start = 0.0
        end = 0.0

        if self.current_segment is not None and self.current_segment.error is None:
            if (
                self.live_segment_start is None
                or self.data_source == "static"
                or isinstance(self.ui, Ui_Processing)
            ):
                start = self.current_segment.start
                end = self.current_segment.end
            else:
                start = self.live_segment_start[0]
                if self.live_mode or self.ui.live_btn.isChecked():
                    end = self.exp_clock_raw
                else:
                    end = self.live_segment_start[1]

        if isinstance(self.ui, Ui_Processing):
            self.ui.start_time.setText(f"{start:.2f}")
            self.ui.end_time.setText(f"{end:.2f}")

    def _insert_segment_into_table(self: Self, seg: Segment, row: int) -> None:
        """Insert a segment into the data table at the specified row."""
        table = self._get_table_widget()
        table.blockSignals(True)
        try:
            table.insertRow(row)

            # Sanitize data
            name = str(seg.name)[:50] if seg.name else ""
            note = str(seg.note)[:500] if seg.note else ""
            cycle_type = str(seg.cycle_type) if seg.cycle_type else "Auto-read"

            # Create table items
            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem(f"{seg.start:.2f}"))
            table.setItem(row, 2, QTableWidgetItem(f"{seg.end:.2f}"))
            table.setItem(row, 3, QTableWidgetItem(f"{seg.shift['a']:.3f}"))
            table.setItem(row, 4, QTableWidgetItem(f"{seg.shift['b']:.3f}"))
            table.setItem(row, 5, QTableWidgetItem(f"{seg.shift['c']:.3f}"))
            table.setItem(row, 6, QTableWidgetItem(f"{seg.shift['d']:.3f}"))
            table.setItem(row, 7, QTableWidgetItem(f"{seg.ref_ch}"))
            table.setItem(row, 8, QTableWidgetItem(cycle_type))
            table.setItem(row, 9, QTableWidgetItem(note))
        except Exception as e:
            logger.error(f"Error creating table items: {e}")
            # Create minimal safe row if there's an error
            for col in range(10):
                if table.item(row, col) is None:
                    table.setItem(row, col, QTableWidgetItem(""))
        finally:
            table.blockSignals(False)

    def save_segment(self: Self) -> None:
        """Save a segment and start a new cycle."""
        if (
            self.data_source == "dynamic"
            and not self.data["rec"]
            and not self.reloading
        ):
            show_message(msg="Data recording not started!", msg_type="Warning")
            return

        self.saving = True

        if self.current_segment:
            try:
                if self.segment_edit:
                    logger.debug(
                        f"saving_edited_segment {self.segment_edit} "
                        f"from {self.current_segment.start} "
                        f"- {self.current_segment.end}",
                    )
                    row = self.segment_edit
                    seg = self.current_segment

                    # Update segment info from table
                    seg.add_info(self.get_info(row))
                    self.delete_row()

                elif self.restoring and self.deleted_segment:
                    logger.debug("Branch: restoring deleted segment")
                    seg = self.deleted_segment
                    row = self.deleted_segment.seg_id

                else:
                    # Check if a cycle is already running (fixed window is active)
                    cycle_already_running = (
                        self.data_source == "dynamic"
                        and hasattr(self, "full_segment_view")
                        and self.full_segment_view.fixed_window_active
                    )

                    if cycle_already_running:
                        logger.info(
                            "[WARN] Cycle already running - completing and saving current cycle first",
                        )

                        # Save the currently running cycle with its current end time
                        current_time = self.full_segment_view.get_time()
                        self.current_segment.end = current_time
                        self.update_segment(
                            self.current_segment.start,
                            self.current_segment.end,
                            update=True,
                            force=True,
                        )

                        # Save the old segment
                        old_segment = self.current_segment
                        old_row = len(self.saved_segments)

                        # Insert old segment into table
                        self._insert_segment_into_table(old_segment, old_row)
                        self.saved_segments.insert(old_row, old_segment)
                        logger.info(
                            f"✓ Previous cycle saved: {old_segment.cycle_type} at row {old_row}",
                        )

                        # Create new segment at current time for the new cycle
                        self.seg_count += 1
                        self.current_segment = Segment(
                            self.seg_count,
                            current_time,
                            current_time + 2,
                        )
                        self.full_segment_view.move_both_cursors(
                            self.current_segment.start,
                            self.current_segment.end,
                        )
                        logger.info(
                            f"✓ New segment created for new cycle: ID {self.seg_count}",
                        )

                    # Set cycle type and time from cycle manager for the current/new segment
                    self.current_segment.cycle_type = (
                        self.cycle_manager.get_current_type()
                    )
                    self.current_segment.cycle_time = (
                        self.cycle_manager.get_current_time_minutes()
                    )

                    seg = self.current_segment
                    row = len(self.saved_segments)

                    if not cycle_already_running:
                        self.seg_count += 1

                    # Apply fixed window and gray zone when cycle starts
                    if self.data_source == "dynamic":
                        cycle_time_minutes = (
                            self.cycle_manager.get_current_time_minutes()
                        )
                        self._apply_cycle_fixed_window(cycle_time_minutes)
                        self.cycle_manager.reset_to_default()

                if (seg is not None) and (row is not None):
                    # Insert segment into table
                    self._insert_segment_into_table(seg, row)

                self.saved_segments.insert(row, self.current_segment)
                self.saving = False
                self._get_table_widget().clearSelection()

            except Exception as e:
                logger.exception(f"error while saving row {e}")
                # Ensure signals are re-enabled even if error occurs
                self._get_table_widget().blockSignals(False)
        else:
            logger.error("error while saveing row no current_segment")

        # Final safety check to ensure signals are always enabled
        self._get_table_widget().blockSignals(False)

    def restore_deleted(self: Self) -> None:
        """Restore a deleted segment."""
        if self.deleted_segment is not None:
            self.restoring = True
            self.save_segment()
            self.deleted_segment = None
            self.restoring = False

    def reassert_row(self: Self, row: int) -> None:
        """Reassert a row in the data cycle table with error handling."""
        try:
            seg = self.saved_segments[row]
            # Block signals to prevent cascading updates
            table = self._get_table_widget()
            table.blockSignals(True)

            # Safely create table items with sanitized data
            name = str(seg.name)[:50] if seg.name else ""
            note = str(seg.note)[:500] if seg.note else ""
            cycle_type = str(seg.cycle_type) if seg.cycle_type else "Auto-read"

            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem(f"{seg.start:.2f}"))
            table.setItem(row, 2, QTableWidgetItem(f"{seg.end:.2f}"))
            table.setItem(row, 3, QTableWidgetItem(f"{seg.shift['a']:.3f}"))
            table.setItem(row, 4, QTableWidgetItem(f"{seg.shift['b']:.3f}"))
            table.setItem(row, 5, QTableWidgetItem(f"{seg.shift['c']:.3f}"))
            table.setItem(row, 6, QTableWidgetItem(f"{seg.shift['d']:.3f}"))
            table.setItem(row, 7, QTableWidgetItem(f"{seg.ref_ch}"))
            table.setItem(row, 8, QTableWidgetItem(cycle_type))
            table.setItem(row, 9, QTableWidgetItem(note))

            table.blockSignals(False)
        except Exception as e:
            logger.error(f"Error reasserting table row {row}: {e}")
            self._get_table_widget().blockSignals(
                False,
            )  # Ensure signals are re-enabled

    def delete_row(self: Self, *, first_available: bool = False) -> None:
        """Delete a row in the data cycle table."""
        if len(self.saved_segments) == 0:
            return

        row = None
        new_seg_trigger = False

        if first_available:
            self.deleted_segment = self._get_table_manager().delete_row(
                saved_segments=self.saved_segments,
                first_available=True,
            )
        else:
            if self.viewing:
                row = self._get_table_widget().currentRow()
                new_seg_trigger = True
            elif self.segment_edit is not None:
                row = self.segment_edit
                new_seg_trigger = True

            self.deleted_segment = self._get_table_manager().delete_row(
                row=row,
                saved_segments=self.saved_segments,
            )

            if new_seg_trigger and not self.saving:
                self.new_segment()

    # open reference channel dialog
    def open_reference_channel_dlg(self: Self) -> None:
        """Open reference channel dialog."""
        self.reference_channel_dlg.show()

    def open_cycle_table(self: Self) -> None:
        """Open cycle data table dialog."""
        self.table_dialog.show()
        self.table_dialog.raise_()
        self.table_dialog.activateWindow()

    def _get_table_widget(self):
        """Get the appropriate table widget based on UI type."""
        if isinstance(self.ui, Ui_Processing):
            return self.ui.data_table
        return self.table_dialog.ui.data_table

    def _get_table_manager(self):
        """Get the appropriate table manager based on UI type."""
        if isinstance(self.ui, Ui_Processing):
            return self.table_manager
        return self.table_dialog.table_manager

    def reset_graphs(self: Self, *, no_msg: bool = False) -> None:
        """Reset the graphs."""
        if no_msg:
            proceed = True
        else:
            proceed = show_message(
                msg="Clear all graphs and table data?",
                msg_type="Warning",
                yes_no=True,
            )
        if proceed:
            if self.segment_edit is not None:
                self.new_segment()
            if self.data_source == "dynamic":
                self.reset_graphs_sig.emit()
            else:
                self.data = {
                    "lambda_times": {ch: np.array([]) for ch in CH_LIST},
                    "lambda_values": {ch: np.array([]) for ch in CH_LIST},
                    "buffered_lambda_times": {ch: np.array([]) for ch in CH_LIST},
                    "filtered_lambda_values": {ch: np.array([]) for ch in CH_LIST},
                    "filt": False,
                }
            self.full_segment_view.reset_sensorgram()
            self.SOI_view.reset_segment_graph(self.unit)
            for _i in range(self._get_table_widget().rowCount()):
                self.delete_row(first_available=True)
            self.saved_segments.clear()  # Clear DataFrame
            self.current_segment = None
            self.enable_controls(data_ready=False)
            self.live_segment_start = None
            self.seg_count = 0
            self.new_segment()

    def open_margin_adjust_dialog(self: Self) -> None:
        """Open dialog to adjust graph margins."""
        if not hasattr(self, "bg_rect_widget"):
            from affilabs.widgets.message import show_message

            show_message(
                msg_type="Information",
                msg="Margin adjustment is only available in Sensorgram view.",
            )
            return

        from affilabs.widgets.margin_adjust_dialog import MarginAdjustDialog

        # Get current margin values
        current_margins = {
            "left": self.bg_rect_margin_left,
            "top": self.bg_rect_margin_top,
            "right": self.bg_rect_margin_right,
            "bottom": self.bg_rect_margin_bottom,
            "radius": self.bg_rect_radius,
        }

        # Store original values in case of cancel
        self._original_margins = current_margins.copy()

        # Create and show dialog (non-blocking)
        if hasattr(self, "_margin_dialog") and self._margin_dialog:
            # Close existing dialog if open
            self._margin_dialog.close()

        self._margin_dialog = MarginAdjustDialog(current_margins, self)
        self._margin_dialog.margins_changed.connect(self.apply_margin_changes)

        # Handle cancel/close to revert
        def on_rejected():
            if hasattr(self, "_original_margins"):
                self.apply_margin_changes(self._original_margins)
                del self._original_margins

        def on_accepted():
            if hasattr(self, "_original_margins"):
                del self._original_margins

        self._margin_dialog.rejected.connect(on_rejected)
        self._margin_dialog.accepted.connect(on_accepted)

        # Show non-blocking
        self._margin_dialog.show()
        self._margin_dialog.show()

    def apply_margin_changes(self: Self, margins: dict) -> None:
        """Apply new margin values to background rectangle."""
        self.bg_rect_margin_left = margins["left"]
        self.bg_rect_margin_top = margins["top"]
        self.bg_rect_margin_right = margins["right"]
        self.bg_rect_margin_bottom = margins["bottom"]
        self.bg_rect_radius = margins["radius"]

        # Update border radius styling
        if hasattr(self, "bg_rect_widget"):
            self.bg_rect_widget.setStyleSheet(
                f"background-color: rgb(255, 255, 255);"
                f"border: 1px solid rgb(100, 100, 100);"
                f"border-radius: {self.bg_rect_radius}px;",
            )

        # Reposition rectangle with new margins
        self._position_bg_rect()

        logger.debug(
            f"Applied new margins: L={margins['left']}, T={margins['top']}, R={margins['right']}, B={margins['bottom']}, Radius={margins['radius']}",
        )

    def reference_change(self: Self, ref_ch: str) -> None:
        """Change the reference channel."""
        if not self.viewing:
            if ref_ch == "None":
                self.reference_channel_id = None
            else:
                self.reference_channel_id = ref_ch
            if self.current_segment is not None:
                self.current_segment.add_data(
                    self.data,
                    self.unit,
                    self.reference_channel_id,
                )
                self.SOI_view.update_display(self.current_segment)
                self.update_displayed_values()

    def set_reference(self: Self, ch: str | None) -> None:
        """Set the reference channel."""
        if ch == "a":
            self.reference_channel_dlg.ui.channelA.setChecked(True)
        elif ch == "b":
            self.reference_channel_dlg.ui.channelB.setChecked(True)
        elif ch == "c":
            self.reference_channel_dlg.ui.channelC.setChecked(True)
        elif ch == "d":
            self.reference_channel_dlg.ui.channelD.setChecked(True)
        else:
            self.reference_channel_dlg.ui.noRef.setChecked(True)

    def take_sensorgram_controls_panel(self) -> QWidget | None:
        """Detach the right-hand sensorgram controls so they can live in the sidebar."""
        if not isinstance(self.ui, Ui_Sensorgram):
            return None

        container = getattr(self.ui, "controls_container", None)
        if container is None:
            return None

        if not self._controls_detached:
            parent_layout = getattr(self.ui, "horizontalLayout", None)
            if isinstance(parent_layout, QHBoxLayout):
                parent_layout.removeWidget(container)
            container.setParent(None)
            self._controls_detached = True

        return container

    def setup(self: Self) -> None:
        """Set up the widget with master-detail layout (30% overview / 70% detail)."""
        title = (
            "Full Experiment Timeline"
            if self.data_source == "dynamic"
            else "Data Processing"
        )

        # Create modern graph containers with Rev 1 styling
        from affilabs.widgets.graph_components import GraphContainer

        # Top graph (Overview) - 30%
        self.sensorgram_frame = GraphContainer(title, height=200, show_delta_spr=False)
        self.sensorgram_frame.setMinimumHeight(150)
        self.sensorgram_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        # Create graph and embed it
        self.full_segment_view = SensorgramGraph(title, show_title=False)
        self.full_segment_view.setMinimumHeight(150)
        self.full_segment_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.sensorgram_frame.set_graph_widget(self.full_segment_view)

        # Bottom graph (Cycle of Interest) - 70%
        self.soi_frame = GraphContainer(
            "Cycle of Interest",
            height=400,
            show_delta_spr=True,
        )
        self.soi_frame.setMinimumHeight(200)
        self.soi_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        # Create graph and embed it
        self.SOI_view = SegmentGraph("Cycle of Interest", self.unit, show_title=False)
        self.SOI_view.setMinimumHeight(200)
        self.SOI_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.soi_frame.set_graph_widget(self.SOI_view)

        # Create vertical splitter for master-detail layout with modern grayscale styling
        self.graph_splitter = QSplitter(Qt.Orientation.Vertical)
        self.graph_splitter.addWidget(self.sensorgram_frame)
        self.graph_splitter.addWidget(self.soi_frame)

        # Style the splitter handle with grayscale theme
        self.graph_splitter.setStyleSheet("""
            QSplitter {
                background-color: transparent;
                spacing: 8px;
            }
            QSplitter::handle {
                background: rgba(0, 0, 0, 0.1);
                border: none;
                border-radius: 4px;
                margin: 0px 16px;
                height: 8px;
            }
            QSplitter::handle:hover {
                background: rgba(0, 0, 0, 0.15);
            }
            QSplitter::handle:pressed {
                background: #1D1D1F;
            }
        """)

        # Track layout mode for ratio swapping
        self._detail_focused = (
            True  # True = 30/70 (detail gets 70%), False = 70/30 (overview gets 70%)
        )

        # Set proportions: 3 parts overview, 7 parts detail (30%/70%)
        self.graph_splitter.setStretchFactor(0, 3)
        self.graph_splitter.setStretchFactor(1, 7)

        # Set handle width for visible appearance
        self.graph_splitter.setHandleWidth(8)

        # Make splitter more responsive
        self.graph_splitter.setChildrenCollapsible(
            False,
        )  # Prevent graphs from collapsing completely

        # Configure the splitter handle to capture events
        handle = self.graph_splitter.handle(1)
        handle.setEnabled(True)
        handle.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        handle.setToolTip(
            "Drag to resize graphs\nDouble-click to swap sizes (20/80 ↔ 80/20)",
        )

        # Install event filter on BOTH handle and splitter to catch double-click
        # (splitter handles consume events, so we need both levels)
        handle.installEventFilter(self)
        self.graph_splitter.installEventFilter(self)

        # Install resize event filter for splitter to reposition background rectangle
        self.graph_splitter.installEventFilter(self)

        logger.debug("Event filter installed on splitter and handle")

        # Add splitter to UI - handle both UI types (Sensorgram and Processing)
        if hasattr(self.ui, "displays"):
            # Ui_Sensorgram uses 'displays' layout
            target_layout = self.ui.displays
        elif hasattr(self.ui, "verticalLayout_5"):
            # Ui_Processing uses 'verticalLayout_5'
            target_layout = self.ui.verticalLayout_5
        else:
            logger.error("Cannot find target layout for graphs")
            return

        # Only clear layout if it has old widgets (optimization)
        if target_layout.count() > 0:
            self._clear_layout(target_layout)

        # Remove extra padding so graphs can use the full width/height
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.setSpacing(6)

        # Rebuild the top-of-graph controls for the Sensorgram UI
        is_sensorgram = isinstance(self.ui, Ui_Sensorgram)
        # shift_display_box removed from UI

        if is_sensorgram and hasattr(self.ui, "groupBox"):
            # Hide the groupBox since we now have legend checkboxes in Cycle of Interest
            self.ui.groupBox.setVisible(False)

            # Hide the standalone Clear Graph button since it's in the groupBox
            if hasattr(self.ui, "clear_graph_btn"):
                self.ui.clear_graph_btn.hide()

            if hasattr(self.ui, "groupBox_display_right"):
                self.ui.groupBox_display_right.setVisible(False)

        target_layout.addWidget(self.graph_splitter)

        # Position background rectangle after splitter is in layout
        if hasattr(self, "bg_rect_widget"):
            # Keep as child of DataWindow, position will be calculated relative to splitter
            QTimer.singleShot(0, self._position_bg_rect)
        self._update_display_group_width()

    def disable_channels(self: Self, error_channels: list[str]) -> None:
        """Disable some channels."""
        if len(error_channels) == 0:
            for ch in CH_LIST:
                getattr(self.ui, f"segment_{ch.upper()}").setEnabled(
                    True,
                )
        else:
            for ch in error_channels:
                getattr(self.ui, f"segment_{ch.upper()}").setEnabled(
                    False,
                )

    def unit_to_nm(self: Self) -> None:
        """Change units to nanometers."""
        if self.live_segment_start is None and self.current_segment:
            self.live_segment_start = [
                deepcopy(self.current_segment.start),
                deepcopy(self.current_segment.end),
            ]
        self.unit = "nm"
        for ch in CH_LIST:
            getattr(self.ui, f"unit_{ch}").setText(self.unit)
        self.SOI_view.reset_segment_graph(self.unit)
        self.reload_segments()

    def _clear_layout(self: Self, layout: QLayout) -> None:
        """Recursively remove widgets/layouts while keeping objects alive."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.setParent(None)
            elif child_layout is not None:
                self._clear_layout(child_layout)

    def _update_display_group_width(self: Self) -> None:
        """Clamp the display checkbox group to at most half the graph width."""
        if not isinstance(self.ui, Ui_Sensorgram):
            return
        if not hasattr(self, "graph_splitter"):
            return
        max_width = max(250, int(self.graph_splitter.width() * 0.5))
        self.ui.groupBox.setMaximumWidth(max_width)

    def resizeEvent(self: Self, event: QResizeEvent) -> None:
        """Ensure auxiliary widgets react to window resizes."""
        super().resizeEvent(event)
        self._update_display_group_width()

    def unit_to_ru(self: Self) -> None:
        """Change unit to RU."""
        if self.live_segment_start is None and self.current_segment:
            self.live_segment_start = [
                deepcopy(self.current_segment.start),
                deepcopy(self.current_segment.end),
            ]
        self.unit = "RU"
        for ch in CH_LIST:
            getattr(self.ui, f"unit_{ch}").setText(self.unit)
        self.SOI_view.reset_segment_graph(self.unit)
        self.reload_segments()

    def set_live(self: Self, *, on: bool) -> None:
        """Turn on live view."""
        if isinstance(self.ui, Ui_Sensorgram):
            self.ui.live_btn.setChecked(on)
        self.full_segment_view.set_live(on)

    def toggle_view(self: Self) -> None:
        """Toggle live view."""
        if isinstance(self.ui, Ui_Sensorgram) and self.ui.live_btn.isChecked():
            self.live_mode = True
        else:
            self.live_mode = False
        self.full_segment_view.set_live(self.live_mode)

    def cursors_text_edit(self: Self, *, state: bool) -> None:
        """Set text edit cursors."""
        self.ui.left_cursor_time.setEnabled(state)
        self.ui.right_cursor_time.setEnabled(state)

    def reload_segments(self: Self, time_shift: float | None = None) -> None:
        """Reload segments."""
        logger.debug("reloading segments")
        self.reloading = True
        if (
            self.data_source == "dynamic"
            and self.live_segment_start is None
            and self.current_segment
        ):
            self.live_segment_start = [
                deepcopy(self.current_segment.start),
                deepcopy(self.current_segment.end),
            ]
        for row in range(self._get_table_widget().rowCount()):
            self.segment_edit = row
            self.current_segment = self.saved_segments[row]
            if time_shift is not None:
                self.current_segment.shift_time(time_shift)
            self.current_segment.add_data(
                self.data,
                self.unit,
                self.reference_channel_id,
            )
            self.save_segment()
        self.reloading = False
        self.new_segment()

    def send_segments_to_analysis(self: Self) -> None:
        """Send segements to data analysis."""
        self.send_to_analysis_sig.emit(self.data, self.saved_segments, self.unit)

    def get_info(self: Self, row: int) -> dict[str, str]:
        """Get info."""
        return self._get_table_manager().get_row_info(row)

    def enter_view_mode(self: Self) -> None:
        """Enter view mode."""
        if (
            (self._get_table_widget().currentRow() > -1)
            and (self.segment_edit is None)
            and (len(self.saved_segments) > self._get_table_widget().currentRow())
        ):
            self.viewing = True
            self.full_segment_view.block_updates = True
            if isinstance(self.ui, Ui_Processing):
                self.ui.curr_seg_box.setEnabled(False)
                self.ui.reference_channel_btn.setEnabled(False)
            row: int = self._get_table_widget().currentRow()
            logger.debug(f"row = {row}")
            if self.data_source == "dynamic":
                self.set_live(on=False)
            if self.live_segment_start is None and self.current_segment:
                self.live_segment_start = [
                    deepcopy(self.current_segment.start),
                    deepcopy(self.current_segment.end),
                ]
                logger.debug(f"live segment start from view: {self.live_segment_start}")
            self.current_segment = self.saved_segments[row]
            logger.debug(
                f"viewing segment {self.current_segment.seg_id}: "
                f"{self.current_segment.start} - {self.current_segment.end}, "
                f"ref ch = {self.current_segment.ref_ch}",
            )
            if self.return_ref is None:
                self.return_ref = self.reference_channel_id
            self.set_reference(self.current_segment.ref_ch)
            self.full_segment_view.move_both_cursors(
                self.current_segment.start,
                self.current_segment.end,
            )
            self.SOI_view.update_display(self.current_segment)
            self.set_row_properties()
            self.full_segment_view.movable_cursors(state=False)
            self.cursors_text_edit(state=False)
            self.ui.new_segment_btn.setText("Leave\nView Mode")
            self.ui.new_segment_btn.setStyleSheet(self.view_style)

            # Hide cycle time shaded region in view mode
            self.full_segment_view.hide_cycle_time_region()

            # Show cycle type and time in dropdowns using cycle_manager
            try:
                cycle_type_text = (
                    self.current_segment.cycle_type
                    if self.current_segment.cycle_type
                    else "Auto-read"
                )
                cycle_time = self.current_segment.cycle_time
                self.cycle_manager.set_cycle_info(cycle_type_text, cycle_time)
            except Exception as e:
                logger.warning(f"Could not set cycle info: {e}")
                self.cycle_manager.reset_to_default()

    def enter_edit_mode(self: Self) -> None:
        """Enter edit mode."""
        if self._get_table_widget().currentRow() > -1 and self.segment_edit is None:
            if isinstance(self.ui, Ui_Processing):
                self.ui.curr_seg_box.setEnabled(True)
                self.ui.reference_channel_btn.setEnabled(True)
            self.viewing = False
            if self.data_source == "dynamic":
                self.set_live(on=False)
            self.full_segment_view.block_updates = True
            self.full_segment_view.movable_cursors(state=True)
            self.cursors_text_edit(state=True)
            row = self._get_table_widget().currentRow()
            self.segment_edit = row
            self.set_row_properties()
            self.set_row_properties(row)

            # Only change button text in static mode (data processing)
            # In dynamic mode (sensorgram), keep "Start\nCycle" for new cycles
            if self.data_source == "static":
                self.ui.save_segment_btn.setText("Save Edited\nCycle")
                self.ui.save_segment_btn.setStyleSheet(self.edit_style)

            self.ui.new_segment_btn.setText("Leave\n Edit Mode")
            self.ui.new_segment_btn.setStyleSheet(self.edit_style)
            if self.live_segment_start is None and self.current_segment:
                self.live_segment_start = [
                    deepcopy(self.current_segment.start),
                    deepcopy(self.current_segment.end),
                ]
                logger.debug(f"live segment start from edit: {self.live_segment_start}")
            self.current_segment = deepcopy(self.saved_segments[row])
            self.return_ref = self.reference_channel_id
            if self.current_segment:
                self.set_reference(self.current_segment.ref_ch)
                self.full_segment_view.move_both_cursors(
                    self.current_segment.start,
                    self.current_segment.end,
                )

    def set_row_properties(self: Self, edit_row: int | None = None) -> None:
        """Set row properties."""
        # Make Cycle Type (column 8) and Notes (column 9) editable, all others read-only
        for row in range(self._get_table_widget().rowCount()):
            for col in range(self._get_table_widget().columnCount()):
                item = self._get_table_widget().item(row, col)
                if item is not None:
                    # Highlight the current row if viewing or editing
                    if isinstance(edit_row, int) and row == edit_row:
                        item.setBackground(self.edit_color)
                    elif self.viewing and row == self._get_table_widget().currentRow():
                        item.setBackground(self.view_color)
                    else:
                        item.setBackground(QColor("white"))

                    # Cycle Type (column 8) and Notes (column 9) are editable
                    if col in {8, 9}:
                        item.setFlags(
                            Qt.ItemFlag.ItemIsEnabled
                            | Qt.ItemFlag.ItemIsSelectable
                            | Qt.ItemFlag.ItemIsEditable,
                        )
                    else:
                        item.setFlags(
                            Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable,
                        )

    def pull_from_sensorgram(self: Self) -> None:
        """Get data from sensorgram."""
        self.pull_sensorgram_sig.emit()

    def update_sensorgram_data(
        self: Self,
        sens_data: DataDict,
        seg_list: list[Segment],
    ) -> None:
        """Update sensorgram data."""
        try:
            proceed = True
            if len(self.data["lambda_times"]["a"]) > 0 and not show_message(
                msg_type="Warning",
                msg="Loading data from Sensorgram will overwrite "
                "\ncurrent data & clear table!"
                "\nProceed with new import?",
                yes_no=True,
            ):
                proceed = False

            if proceed:
                self.data = deepcopy(sens_data)
                for _i in range(len(self.saved_segments)):
                    self.delete_row(first_available=True)
                self.seg_count = 0
                for seg in deepcopy(seg_list):
                    self.current_segment = seg
                    self.save_segment()
                self.current_segment = None
                self.enable_controls(data_ready=True)
                self.update_data(self.data)
                self.full_segment_view.center_cursors()
                self.new_segment()

        except Exception as e:
            logger.exception(f"Error pulling data from sensorgram: {e}")

    def import_raw_data(self: Self) -> None:
        """Import raw data."""
        proceed = True
        if len(self.data["lambda_times"]["a"]) > 0:
            if not show_message(
                msg_type="Warning",
                msg="Import will overwrite data & erase Cycle Data Table!"
                "\nProceed with new import?",
                yes_no=True,
            ):
                proceed = False
            else:
                self.reset_graphs(no_msg=True)

        if proceed:
            file_name = QFileDialog.getOpenFileName(
                self,
                "Open File",
                "",
                "Text Files (*.txt)",
            )[0]

            try:
                file = Path(file_name).open(encoding="utf-8")  # noqa: SIM115
            except Exception as e:
                logger.exception(f"file open error: {e}")
                return
            try:
                skip_first = True

                if "All_Graph" in file_name:
                    # 🚀 OPTIMIZED: Use pandas for fast CSV loading
                    import pandas as pd

                    columns = ["GraphAll_x", "GraphAll_y"]
                    # Read entire CSV at once (much faster than row-by-row)
                    df = pd.read_csv(file, sep="\t", names=columns, skiprows=1)

                    # Convert to numpy arrays
                    times = df["GraphAll_x"].values.astype(float)
                    intensities = df["GraphAll_y"].values.astype(float)

                    # Distribute data across channels (d, a, b, c pattern)
                    ch_list = ["d", "a", "b", "c"]
                    for i, ch in enumerate(ch_list):
                        # Extract every 4th value starting at position i
                        ch_times = times[i::4]
                        ch_intensities = intensities[i::4]

                        self.data["lambda_times"][ch] = np.append(
                            self.data["lambda_times"][ch],
                            ch_times,
                        )
                        self.data["lambda_values"][ch] = np.append(
                            self.data["lambda_values"][ch],
                            ch_intensities,
                        )

                else:
                    # 🚀 OPTIMIZED: Use pandas for fast CSV loading
                    import pandas as pd

                    columns = [
                        "Time_A",
                        "Channel_A",
                        "Time_B",
                        "Channel_B",
                        "Time_C",
                        "Channel_C",
                        "Time_D",
                        "Channel_D",
                    ]

                    # Read CSV with pandas (much faster)
                    df = pd.read_csv(file, sep="\t", names=columns)

                    # Extract reference values from first row if present
                    references = None
                    try:
                        # Check if first row contains reference values (non-numeric)
                        first_row = df.iloc[0]
                        if pd.isna(first_row["Time_A"]) or not isinstance(
                            first_row["Time_A"],
                            (int, float),
                        ):
                            # Has header/reference row
                            references = [
                                float(first_row[f"Channel_{ch}"])
                                if pd.notna(first_row[f"Channel_{ch}"])
                                else 0.0
                                for ch in ["A", "B", "C", "D"]
                            ]
                            df = df.iloc[1:]  # Skip reference row
                    except (ValueError, KeyError):
                        pass

                    # Convert to numeric
                    df = df.apply(pd.to_numeric, errors="coerce")

                    # Apply reference conversion if needed (RU to nm)
                    if references:
                        for i, ch in enumerate(["A", "B", "C", "D"]):
                            df[f"Channel_{ch}"] = (
                                df[f"Channel_{ch}"] / 355 + references[i]
                            )

                    # Append to data arrays
                    self.data["lambda_times"]["a"] = np.append(
                        self.data["lambda_times"]["a"],
                        df["Time_A"].values,
                    )
                    self.data["lambda_values"]["a"] = np.append(
                        self.data["lambda_values"]["a"],
                        df["Channel_A"].values,
                    )
                    self.data["lambda_times"]["b"] = np.append(
                        self.data["lambda_times"]["b"],
                        df["Time_B"].values,
                    )
                    self.data["lambda_values"]["b"] = np.append(
                        self.data["lambda_values"]["b"],
                        df["Channel_B"].values,
                    )
                    self.data["lambda_times"]["c"] = np.append(
                        self.data["lambda_times"]["c"],
                        df["Time_C"].values,
                    )
                    self.data["lambda_values"]["c"] = np.append(
                        self.data["lambda_values"]["c"],
                        df["Channel_C"].values,
                    )
                    self.data["lambda_times"]["d"] = np.append(
                        self.data["lambda_times"]["d"],
                        df["Time_D"].values,
                    )
                    self.data["lambda_values"]["d"] = np.append(
                        self.data["lambda_values"]["d"],
                        df["Channel_D"].values,
                    )

                self.data["filt"] = False
                for ch in CH_LIST:
                    self.data["filtered_lambda_values"][ch] = medfilt(
                        self.data["lambda_values"][ch],
                        MED_FILT_WIN,
                    )
                self.data["buffered_lambda_times"] = deepcopy(
                    self.data["lambda_times"],
                )

                for _i in range(len(self.saved_segments)):
                    self.delete_row(first_available=True)

                self.current_segment = None
                self.enable_controls(data_ready=True)
                self.update_data(self.data)
                self.full_segment_view.center_cursors()
                self.new_segment()

            except Exception as e:
                logger.exception(f"import raw data error {e}")
                show_message(msg="Import Error: Incorrect file for Raw Data")

    def import_table(self: Self) -> None:
        """Import cycle data table using pandas."""
        if (len(self.data["lambda_times"]["a"]) > 0) and (
            len(self.data["lambda_times"]["a"]) == len(self.data["lambda_times"]["d"])
        ):
            file_name = QFileDialog.getOpenFileName(
                self,
                "Open File",
                "",
                "Text Files (*.txt)",
            )[0]

            if not file_name:
                return

            try:
                # Clear existing segments
                if self.segment_edit is not None:
                    self.new_segment()

                for _i in range(self._get_table_widget().rowCount()):
                    self.delete_row(first_available=True)
                self.seg_count = 0

                # Import using pandas
                imported_df = SegmentDataFrame.from_csv(file_name, encoding="utf-8")

                # Reconstruct Segment objects with data
                for i, row_dict in enumerate(imported_df.df.iterrows()):
                    _, row = row_dict
                    self.current_segment = Segment(
                        i,
                        float(row["start"]),
                        float(row["end"]),
                    )
                    self.current_segment.add_info(
                        {"name": str(row["name"]), "note": str(row["note"])},
                    )
                    ref_ch = row["ref_ch"]
                    if ref_ch in {"", "None", None}:
                        ref_ch = None
                    self.current_segment.add_data(
                        self.data,
                        self.unit,
                        ref_ch,
                    )
                    # Set cycle type from imported data
                    self.current_segment.cycle_type = str(
                        row.get("cycle_type", "Auto-read"),
                    )
                    self.save_segment()

                logger.info(f"Successfully imported {len(imported_df)} segments")

            except Exception as e:
                logger.exception(f"import table error {e}, type {type(e)}")
                show_message(msg="Import Error: Incorrect file for Data Table")

        else:
            show_message(
                msg="Missing Data:\n"
                "Please import raw data first, then load segment data table",
            )

    def export_trigger(self: Self) -> None:
        """Export trigger."""
        self.save_sig.emit()

    def export_raw_data(
        self: Self,
        *,
        preset: bool = False,
        preset_dir: str | Path = "",
    ) -> None:
        """Export raw data."""
        try:
            error = True
            if preset:
                file_name = preset_dir
            else:
                if self.metadata.show_on_save:
                    metadata_prompt = MetadataPrompt(self.metadata, self)
                    if not metadata_prompt.exec():
                        show_message("Data export aborted", "Warning")
                        return
                file_name = QFileDialog.getSaveFileName(
                    self,
                    "Export Raw Data to file",
                )[0]
            full_file = f"{file_name} Raw Data.txt"

            if full_file not in {" Raw Data.txt", "/Recording Raw Data.txt"}:
                error = False

                with Path(full_file).open("w", newline="", encoding="utf-8") as txtfile:
                    fieldnames = [
                        "X_RawDataA",
                        "Y_RawDataA",
                        "X_RawDataB",
                        "Y_RawDataB",
                        "X_RawDataC",
                        "Y_RawDataC",
                        "X_RawDataD",
                        "Y_RawDataD",
                    ]
                    writer = csv.DictWriter(
                        txtfile,
                        dialect="excel-tab",
                        fieldnames=fieldnames,
                    )

                    l_val_data = deepcopy(self.data["lambda_values"])
                    l_time_data = deepcopy(self.data["lambda_times"])

                    # Finds the first time greater than or equal to 0 on the first
                    # channel to use as a reference point
                    reference_index = bisect_left(l_time_data[CH_LIST[0]], 0)
                    # Clamp to valid range - check minimum length across ALL channels
                    min_array_len = min(len(l_val_data[ch]) for ch in CH_LIST)
                    if min_array_len == 0:
                        logger.error("Cannot export: no data in lambda_values")
                        return
                    reference_index = min(reference_index, min_array_len - 1)
                    logger.debug(
                        f"Export reference index: {reference_index} (min array length: {min_array_len})",
                    )
                    references = [l_val_data[ch][reference_index] for ch in CH_LIST]

                    row_count = min(len(x) for x in l_time_data.values())

                    self.metadata.write_tracedrawer_header(
                        writer,
                        fieldnames,
                        "Raw data",
                        references,
                    )

                    # Build DataFrame for vectorized CSV writing
                    row_count = min(len(x) for x in l_time_data.values())

                    # Prepare data dictionary
                    data_dict = {}
                    for i, ch in enumerate(CH_LIST):
                        data_dict[f"X_RawData{ch.upper()}"] = np.round(
                            l_time_data[ch][:row_count],
                            4,
                        )
                        # Convert wavelength to shift (nm) using reference
                        values = l_val_data[ch][:row_count]
                        data_dict[f"Y_RawData{ch.upper()}"] = np.round(
                            (values - references[i]) * 355,
                            4,
                        )

                    # Create DataFrame and write to CSV
                    df = pd.DataFrame(data_dict)
                    df.replace({np.nan: None}, inplace=True)
                    df.to_csv(
                        txtfile,
                        sep="\t",
                        index=False,
                        header=False,
                        encoding="utf-8",
                    )

            if self.data["filt"]:
                full_file = f"{preset_dir} Filtered Data.txt"
                if full_file not in {
                    " Filtered Data.txt",
                    "/Recording Filtered Data.txt",
                }:
                    error = False
                    with Path(full_file).open(
                        "w",
                        newline="",
                        encoding="utf-8",
                    ) as txtfile:
                        fieldnames = [
                            "X_DataA",
                            "Y_DataA",
                            "X_DataB",
                            "Y_DataB",
                            "X_DataC",
                            "Y_DataC",
                            "X_DataD",
                            "Y_DataD",
                        ]
                        writer = csv.DictWriter(
                            txtfile,
                            dialect="excel-tab",
                            fieldnames=fieldnames,
                        )
                        writer.writeheader()

                        l_val_data = deepcopy(self.data["filtered_lambda_values"])
                        l_time_data = deepcopy(self.data["buffered_lambda_times"])

                        row_count = min(len(l_time_data[ch]) for ch in CH_LIST)

                        # Build DataFrame for vectorized CSV writing
                        data_dict = {}
                        for ch in CH_LIST:
                            data_dict[f"X_Data{ch.upper()}"] = np.round(
                                l_time_data[ch][:row_count],
                                4,
                            )
                            data_dict[f"Y_Data{ch.upper()}"] = np.round(
                                l_val_data[ch][:row_count],
                                4,
                            )

                        # Create DataFrame and write to CSV
                        df = pd.DataFrame(data_dict)
                        df.replace({np.nan: None}, inplace=True)
                        df.to_csv(
                            txtfile,
                            sep="\t",
                            index=False,
                            header=False,
                            encoding="utf-8",
                        )
            if error:
                self.export_error_signal.emit()
            elif not preset:
                show_message(
                    msg="Sensorgram data exported",
                    msg_type="Info",
                    auto_close_time=3,
                )

        except Exception as e:
            logger.exception(f"export raw data error: {e}")
            self.export_error_signal.emit()

    def export_to_excel(self: Self) -> None:
        """Export data to Excel format with multiple sheets (pandas-based)."""
        try:
            # Get file location from user
            file_name = QFileDialog.getSaveFileName(
                self,
                "Export Data to Excel",
                "",
                "Excel Files (*.xlsx)",
            )[0]

            if not file_name:
                return  # User cancelled

            # Ensure .xlsx extension
            if not file_name.endswith(".xlsx"):
                file_name += ".xlsx"

            # Prepare data from existing data structure
            l_val_data = deepcopy(self.data["lambda_values"])
            l_time_data = deepcopy(self.data["lambda_times"])

            # Check if data is available
            min_array_len = min(len(l_val_data[ch]) for ch in CH_LIST)
            if min_array_len == 0:
                logger.error("Cannot export: no data available")
                show_message("No data to export", "Warning")
                return

            # Create raw data in LONG format (each channel has its own timestamp)
            # CRITICAL: Channels are measured in SERIES not PARALLEL
            raw_data_rows = []
            for ch in CH_LIST:
                ch_times = l_time_data[ch]
                ch_wavelengths = l_val_data[ch]
                for t, w in zip(ch_times, ch_wavelengths):
                    raw_data_rows.append({
                        'time': round(t, 4),
                        'channel': ch,
                        'value': round(w, 4)
                    })

            df_raw = pd.DataFrame(raw_data_rows)

            # Create Excel writer
            with pd.ExcelWriter(file_name, engine="openpyxl") as writer:
                # Write raw data
                df_raw.to_excel(writer, sheet_name="Raw Data", index=False)

                # Add filtered data if available (also in long format)
                if self.data["filt"]:
                    l_val_filt = deepcopy(self.data["filtered_lambda_values"])
                    l_time_filt = deepcopy(self.data["buffered_lambda_times"])

                    filtered_data_rows = []
                    for ch in CH_LIST:
                        ch_times = l_time_filt[ch]
                        ch_wavelengths = l_val_filt[ch]
                        for t, w in zip(ch_times, ch_wavelengths):
                            filtered_data_rows.append({
                                'time': round(t, 4),
                                'channel': ch,
                                'value': round(w, 4)
                            })

                    df_filt = pd.DataFrame(filtered_data_rows)
                    df_filt.to_excel(writer, sheet_name="Filtered Data", index=False)

            show_message(
                msg=f"Data exported to Excel:\n{Path(file_name).name}",
                msg_type="Info",
                auto_close_time=3,
            )

        except Exception as e:
            logger.exception(f"Excel export error: {e}")
            show_message(f"Excel export failed: {e}", "Error")

    # export table data
    def export_table(
        self: Self,
        *,
        preset: bool = False,
        preset_dir: str | None = None,
    ) -> None:
        """Export table data using pandas."""
        try:
            if len(self.saved_segments) == 0:
                show_message("No segments to export", "Warning")
                return

            error = True
            if preset:
                dir_path = preset_dir
                file_name = f"{dir_path}"
            else:
                file_name = QFileDialog.getSaveFileName(
                    self,
                    "Export Cycle Data Table to file, with segments data",
                )[0]
            full_file = f"{file_name} Cycle Data Table.txt"

            if full_file not in {
                " Cycle Data Table.txt",
                "/Recording Cycle Data Table.txt",
            }:
                error = False
                # Use pandas to export table data
                self.saved_segments.to_csv(full_file, encoding="utf-8")

                for seg in self.saved_segments:
                    with Path(f"{file_name} Cycle{seg.name}.txt").open(
                        "w",
                        newline="",
                        encoding="utf-8",
                    ) as txtfile:
                        fieldnames = [
                            f"X_Cyc{seg.name}_ChA",
                            f"Y_Cyc{seg.name}_ChA",
                            f"X_Cyc{seg.name}_ChB",
                            f"Y_Cyc{seg.name}_ChB",
                            f"X_Cyc{seg.name}_ChC",
                            f"Y_Cyc{seg.name}_ChC",
                            f"X_Cyc{seg.name}_ChD",
                            f"Y_Cyc{seg.name}_ChD",
                        ]
                        writer = csv.DictWriter(
                            txtfile,
                            dialect="excel-tab",
                            fieldnames=fieldnames,
                        )
                        writer.writerow({fieldnames[0]: "Plot name"})
                        writer.writerow(
                            {fieldnames[0]: "Plot xlabel", fieldnames[1]: "Time (s)"},
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Plot ylabel",
                                fieldnames[1]: f"{self.unit}",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Property Analysis temp",
                                fieldnames[1]: "0.0",
                            },
                        )
                        now = datetime.datetime.now(TIME_ZONE)
                        writer.writerow(
                            {
                                fieldnames[0]: "Property Analysis date",
                                fieldnames[
                                    1
                                ]: f"{now.year:04d}-{now.month:02d}-{now.day:02d} "
                                f"{now.hour:02d}:{now.minute:02d}:{now.second:02d}",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Property Filename",
                                fieldnames[1]: f"Cycle{seg.name}",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Property Instrument id",
                                fieldnames[1]: "N/A",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Property Instrument type",
                                fieldnames[1]: "Affinite SPR",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Property Software",
                                fieldnames[1]: f"ezControl {SW_VERSION}",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Property Solid support",
                                fieldnames[1]: "N/A",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Curve",
                                fieldnames[1]: 1,
                                fieldnames[2]: "Curve",
                                fieldnames[3]: 2,
                                fieldnames[4]: "Curve",
                                fieldnames[5]: 3,
                                fieldnames[6]: "Curve",
                                fieldnames[7]: 4,
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Curve name",
                                fieldnames[1]: f"{seg.note} Ch A",
                                fieldnames[2]: "Curve name",
                                fieldnames[3]: f"{seg.note} Ch B",
                                fieldnames[4]: "Curve name",
                                fieldnames[5]: f"{seg.note} Ch C",
                                fieldnames[6]: "Curve name",
                                fieldnames[7]: f"{seg.note} Ch D",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Curve type",
                                fieldnames[1]: "Curve",
                                fieldnames[2]: "Curve type",
                                fieldnames[3]: "Curve",
                                fieldnames[4]: "Curve type",
                                fieldnames[5]: "Curve",
                                fieldnames[6]: "Curve type",
                                fieldnames[7]: "Curve",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Curve ligand",
                                fieldnames[1]: "N/A",
                                fieldnames[2]: "Curve ligand",
                                fieldnames[3]: "N/A",
                                fieldnames[4]: "Curve ligand",
                                fieldnames[5]: "N/A",
                                fieldnames[6]: "Curve ligand",
                                fieldnames[7]: "N/A",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Curve concentration (M)",
                                fieldnames[1]: "0.0E-8",
                                fieldnames[2]: "Curve concentration (M)",
                                fieldnames[3]: "0.0E-8",
                                fieldnames[4]: "Curve concentration (M)",
                                fieldnames[5]: "0.0E-8",
                                fieldnames[6]: "Curve concentration (M)",
                                fieldnames[7]: "0.0E-8",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Curve target",
                                fieldnames[1]: "N/A",
                                fieldnames[2]: "Curve target",
                                fieldnames[3]: "N/A",
                                fieldnames[4]: "Curve target",
                                fieldnames[5]: "N/A",
                                fieldnames[6]: "Curve target",
                                fieldnames[7]: "N/A",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "Curve description",
                                fieldnames[1]: f"Cycle {seg.name} Ch A",
                                fieldnames[2]: "Curve description",
                                fieldnames[3]: f"Cycle {seg.name} Ch B",
                                fieldnames[4]: "Curve description",
                                fieldnames[5]: f"Cycle {seg.name} Ch C",
                                fieldnames[6]: "Curve description",
                                fieldnames[7]: f"Cycle {seg.name} Ch D",
                            },
                        )
                        writer.writerow(
                            {
                                fieldnames[0]: "X",
                                fieldnames[1]: "Y",
                                fieldnames[2]: "X",
                                fieldnames[3]: "Y",
                                fieldnames[4]: "X",
                                fieldnames[5]: "Y",
                                fieldnames[6]: "X",
                                fieldnames[7]: "Y",
                            },
                        )

                        row_count = len(seg.seg_x["a"])
                        for ch in CH_LIST:
                            row_count = min(len(seg.seg_x[ch]), row_count)

                        for j in range(row_count):
                            for ch in CH_LIST:
                                if np.isnan(seg.seg_y[ch][j]):
                                    seg.seg_y[ch][j] = None
                            writer.writerow(
                                {
                                    f"X_Cyc{seg.name}_ChA": round(seg.seg_x["a"][j], 4),
                                    f"Y_Cyc{seg.name}_ChA": round(seg.seg_y["a"][j], 4),
                                    f"X_Cyc{seg.name}_ChB": round(seg.seg_x["b"][j], 4),
                                    f"Y_Cyc{seg.name}_ChB": round(seg.seg_y["b"][j], 4),
                                    f"X_Cyc{seg.name}_ChC": round(seg.seg_x["c"][j], 4),
                                    f"Y_Cyc{seg.name}_ChC": round(seg.seg_y["c"][j], 4),
                                    f"X_Cyc{seg.name}_ChD": round(seg.seg_x["d"][j], 4),
                                    f"Y_Cyc{seg.name}_ChD": round(seg.seg_y["d"][j], 4),
                                },
                            )
                if not preset:
                    show_message(msg="Cycle data exported")

            if error:
                self.export_error_signal.emit()

        except Exception as e:
            logger.exception(f"export table error: {e}")
            self.export_error_signal.emit()

    def _apply_cycle_fixed_window(self: Self, cycle_time_minutes: float | None) -> None:
        """Apply fixed window and cycle markers for cycle start."""
        if cycle_time_minutes is None or cycle_time_minutes <= 0:
            logger.warning("Invalid cycle time, skipping fixed window")
            return

        logger.info(
            f"Cycle started: {self.current_segment.cycle_type}, {cycle_time_minutes} min",
        )

        # Calculate window parameters once
        window_seconds = cycle_time_minutes * 60 * CYCLE_WINDOW_PADDING_FACTOR
        start_time = self.full_segment_view.left_cursor_pos
        end_time = start_time + window_seconds

        # Apply fixed window to both graphs
        self._set_fixed_x_range(
            self.full_segment_view,
            start_time,
            end_time,
            "Sensorgram",
        )
        self._set_fixed_x_range(self.SOI_view, 0, window_seconds, "SOI")

        # Apply Y padding with auto-range enabled
        for plot, name in [
            (self.full_segment_view.plot, "Sensorgram"),
            (self.SOI_view.plot, "SOI"),
        ]:
            self._apply_y_padding(plot, name)

        # Show cycle markers (after ranges are set)
        self.full_segment_view.show_cycle_time_region(cycle_time_minutes)

        # Force immediate visual update
        self.full_segment_view.plot.update()
        self.SOI_view.plot.update()

        logger.debug(f"Fixed window applied: {window_seconds:.0f}s")

    def _set_fixed_x_range(
        self: Self,
        view,
        start: float,
        end: float,
        name: str,
    ) -> None:
        """Set fixed X range on a view and disable X auto-range."""
        view.fixed_window_active = True
        view.plot.setRange(xRange=(start, end), padding=0, disableAutoRange=False)
        view.plot.enableAutoRange(axis="x", enable=False)
        view.plot.enableAutoRange(axis="y", enable=True)
        logger.debug(f"{name}: X range [{start:.1f}, {end:.1f}]s")

    def _apply_y_padding(self: Self, plot, graph_name: str) -> None:
        """Ensure Y-axis auto-range is enabled for live data updates."""
        plot.enableAutoRange(axis="y", enable=True)
        logger.debug(f"{graph_name}: Y auto-range enabled")

    def cycle_marker_style_changed(self: Self, style: str) -> None:
        """Handle cycle marker style change - re-render if cycle is active."""
        logger.info(f"Cycle marker style changed to: {style}")

        # Only re-render if currently in an active cycle
        if not (
            hasattr(self, "full_segment_view")
            and self.full_segment_view.fixed_window_active
        ):
            return

        cycle_time = (
            self.cycle_manager.get_current_time_minutes()
            if hasattr(self, "cycle_manager")
            else CYCLE_TIME
        )
        if cycle_time and cycle_time > 0:
            self.full_segment_view.hide_cycle_time_region()
            self.full_segment_view.show_cycle_time_region(cycle_time)
            logger.info("✓ Cycle markers re-rendered")

    def save_data(self: Self, rec_dir: str) -> None:
        """Save data using centralized DataExporter."""
        try:
            # Extract experiment name from rec_dir
            from pathlib import Path

            rec_path = Path(rec_dir)
            exp_name = rec_path.name if rec_path.name else "Recording"

            # Create DataExporter instance
            exporter = DataExporter(base_dir=rec_dir, experiment_name=exp_name)

            # Export raw data
            try:
                exporter.export_raw_data(
                    data=self.data,
                    metadata=self.metadata,
                    references=None,  # Will auto-calculate
                )
            except Exception as e:
                logger.error(f"Failed to export raw data: {e}")

            # Export filtered data if available
            if self.data.get("filt", False):
                try:
                    # Create filtered data dict
                    filtered_data = {
                        "lambda_times": self.data.get(
                            "buffered_lambda_times",
                            self.data["lambda_times"],
                        ),
                        "lambda_values": self.data.get(
                            "filtered_lambda_values",
                            self.data["lambda_values"],
                        ),
                        "filt": True,
                    }
                    exporter.export_filtered_data(
                        data=filtered_data,
                        metadata=self.metadata,
                    )
                except Exception as e:
                    logger.error(f"Failed to export filtered data: {e}")

            # Export segments
            try:
                segments = [seg.to_dict() for seg in self.segment_list]
                if segments:
                    exporter.export_segments(
                        segments=segments,
                        value_list=self.data["lambda_values"],
                        ts_list=self.data["lambda_times"],
                    )
            except Exception as e:
                logger.error(f"Failed to export segments: {e}")

            # Save manifest
            exporter.save_manifest()
            logger.info(f"Data export completed to {rec_dir}")

        except Exception as e:
            logger.exception(f"Error in save_data: {e}")

    def start_recording(self: Self, rec_dir: str) -> None:
        """Start recording."""
        # Reset time reference so timestamps start at zero
        self.full_segment_view.reset_time()
        self.live_segment_start = None

        # Move yellow cursor (right) to 0
        self.full_segment_view.set_right(0, emit=False, update=False)
        logger.debug("Recording started: time reset to zero")
        self.new_segment()
        # Don't save data yet - wait for set_start() to adjust timestamps
        # self.save_data(rec_dir) will be called after timestamps are adjusted


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    app = QApplication([])

    widget = DataWindow("static")
    for key in widget.data["lambda_times"]:
        widget.data["lambda_times"][key] = np.arange(500, dtype=np.float64)
        widget.data["lambda_values"][key] = np.random.default_rng().random(500)

    widget.export_raw_data(preset=True, preset_dir=Path("data_export") / Path("Test"))
