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
from typing import Literal, Self, TypedDict

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QDoubleValidator, QFont, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QStyledItemDelegate,
    QTableWidgetItem,
    QWidget,
)
from scipy.signal import medfilt

from settings import CH_LIST, CYCLE_TIME, MED_FILT_WIN, SW_VERSION, UNIT_LIST
from ui.ui_processing import Ui_Processing
from ui.ui_sensorgram import Ui_Sensorgram
from utils.logger import logger
from widgets.channelmenu import ChannelMenu
from widgets.cycle_manager import CycleManager
from widgets.graphs import SegmentGraph, SensorgramGraph
from widgets.message import show_message
from widgets.metadata import Metadata, MetadataPrompt
from widgets.table_manager import CycleTableManager
from widgets.ui_constants import COLUMNS_TO_TOGGLE, CYCLE_TYPES

TIME_ZONE = datetime.datetime.now(datetime.UTC).astimezone().tzinfo
# Tab 1 (default): Shows ID, Start, Cycle Type, Note (columns 0, 1, 8, 9)
# Tab 2: Shows ID, Start, Shift A-D (columns 0, 1, 3, 4, 5, 6)
# COLUMNS_TO_TOGGLE and CYCLE_TYPES now imported from widgets.ui_constants

ON_BRUSH = QBrush(Qt.GlobalColor.darkGray)
OFF_BRUSH = QBrush(Qt.GlobalColor.transparent)

LOOP_BRUSH = QBrush(Qt.GlobalColor.green)
SENSOR_BRUSH = QBrush(Qt.GlobalColor.blue)
LOOP_PEN = QPen(LOOP_BRUSH, 6)
SENSOR_PEN = QPen(SENSOR_BRUSH, 6)

PROGRESS_BAR_UPDATE_TIME = 100


class CycleTypeDelegate(QStyledItemDelegate):
    """Delegate to provide a dropdown for cycle type selection."""

    def createEditor(self, parent, option, index):
        """Create a QComboBox editor."""
        combo = QComboBox(parent)
        combo.addItems(CYCLE_TYPES)
        # Style the combobox to ensure text is visible
        combo.setStyleSheet("""
            QComboBox {
                background-color: white;
                color: black;
                border: 1px solid gray;
                padding: 2px;
            }
            QComboBox:hover {
                background-color: #f0f0f0;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: black;
                selection-background-color: #0078d4;
                selection-color: white;
            }
        """)
        return combo

    def setEditorData(self, editor, index):
        """Set the current value in the combo box."""
        current_text = index.data()
        if current_text in CYCLE_TYPES:
            editor.setCurrentText(current_text)
        else:
            editor.setCurrentIndex(0)

    def setModelData(self, editor, model, index):
        """Save the selected value back to the model."""
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class TextInputDelegate(QStyledItemDelegate):
    """Delegate for text input with character limits and validation."""

    # Character limits for different column types
    NAME_LIMIT = 50
    NOTE_LIMIT = 500

    def createEditor(self, parent, option, index):
        """Create a line edit with character limit."""
        from PySide6.QtWidgets import QLineEdit

        editor = QLineEdit(parent)

        # Set character limit based on column
        column = index.column()
        if column == 0:  # Name column
            editor.setMaxLength(self.NAME_LIMIT)
            editor.setPlaceholderText(f"Max {self.NAME_LIMIT} characters")
        elif column == 9:  # Note column
            editor.setMaxLength(self.NOTE_LIMIT)
            editor.setPlaceholderText(f"Max {self.NOTE_LIMIT} characters")
        else:
            editor.setMaxLength(100)  # Default limit for other text columns

        return editor

    def setEditorData(self, editor, index):
        """Set current value in editor with safety checks."""
        try:
            current_text = index.data()
            if current_text is not None:
                editor.setText(str(current_text))
            else:
                editor.setText("")
        except Exception as e:
            logger.warning(f"Error setting editor data: {e}")
            editor.setText("")

    def setModelData(self, editor, model, index):
        """Save value back to model with validation."""
        try:
            text = editor.text().strip()
            # Additional validation: remove any problematic characters
            text = text.replace('\x00', '')  # Remove null bytes
            text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')  # Keep printable chars
            model.setData(index, text, Qt.ItemDataRole.EditRole)
        except Exception as e:
            logger.error(f"Error saving table cell data: {e}")
            # Don't crash - just log the error


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

                # Find the earliest timestamp across all channels for proper normalization
                min_time = None
                for ch in CH_LIST:
                    if len(self.seg_x[ch]) > 0:
                        if min_time is None or self.seg_x[ch][0] < min_time:
                            min_time = self.seg_x[ch][0]

                # Now normalize all channels relative to the earliest timestamp
                for ch in CH_LIST:
                    if (len(self.seg_x[ch]) > 0) and (len(self.seg_y[ch]) > 0):
                        ref_index = 0
                        while (np.isnan(self.seg_y[ch][ref_index])) and (
                            ref_index < (len(self.seg_y[ch]) - 1)
                        ):
                            ref_index += 1
                        # Normalize to the earliest time across all channels
                        if min_time is not None:
                            self.seg_x[ch] = self.seg_x[ch] - min_time
                        self.seg_y[ch] = (
                            self.seg_y[ch] - self.seg_y[ch][ref_index]
                        )
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
            name_text = name_text.replace('\x00', '')  # Remove null bytes
            name_text = ''.join(char for char in name_text if ord(char) >= 32 or char in '\n\r\t')
            self.name = name_text[:50] if name_text else str(self.seg_id + 1)
        except Exception as e:
            logger.warning(f"Error sanitizing segment name: {e}")
            self.name = str(self.seg_id + 1)

        # Sanitize note - limit to 500 characters, remove problematic characters
        try:
            note_text = str(info.get("note", "")).strip()
            note_text = note_text.replace('\x00', '')  # Remove null bytes
            note_text = ''.join(char for char in note_text if ord(char) >= 32 or char in '\n\r\t')
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
        if "cycle_time" in info and info["cycle_time"]:
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
    ) -> None:
        """Make a data processing widget."""
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, on=True)
        self.data_source = data_source
        self.reference_channel_id: str | None = None
        self.return_ref: str | None = None
        self.full_segment_view: SensorgramGraph
        self.SOI_view: SegmentGraph
        self.exp_clock_raw = 0.0
        self.reloading = False
        self.live_mode = True
        self.progress_bar_timer = QTimer()

        # display data processing or sensorgram page depending on source

        if self.data_source == "dynamic":
            self.ui = Ui_Sensorgram()
            self.ui.setupUi(self)
            self._fix_checkbox_styles()

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
        self.saved_segments: list[Segment] = []
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

        # Create object to hold metadata and allow user input
        self.metadata = Metadata(CH_LIST)

        # dialogs: reference channel, average channel, units
        self.reference_channel_dlg = ChannelMenu(self.data_source, self.metadata)
        self.reference_channel_dlg.ref_ch_signal.connect(self.reference_change)
        self.reference_channel_dlg.unit_to_ru_signal.connect(self.unit_to_nm)
        self.reference_channel_dlg.unit_to_nm_signal.connect(self.unit_to_nm)
        if self.data_source == "static":
            # Disable filter for static data by unchecking the filter checkbox
            self.reference_channel_dlg.ui.filt_en.setChecked(False)

        # update segment data when cursor positions changed
        self.full_segment_view.segment_signal.connect(self.update_segment)

        # channel display options changed in full segment plot
        for ch in CH_LIST:
            getattr(self.ui, f"segment_{ch.upper()}").stateChanged.connect(
                partial(self.full_segment_view.display_channel_changed, ch),
            )
            getattr(self.ui, f"segment_{ch.upper()}").stateChanged.connect(
                partial(self.SOI_view.display_channel_changed, ch),
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

        # new segment button
        self.ui.new_segment_btn.clicked.connect(self.new_segment)

        if isinstance(self.ui, Ui_Processing):
            self.ui.reset_segment_btn.clicked.connect(self.reset_graphs)
        elif isinstance(self.ui, Ui_Sensorgram):
            self.reference_channel_dlg.ui.reset_data.clicked.connect(self.reset_graphs)

        # data table add/remove row
        self.ui.delete_row_btn.clicked.connect(self.delete_row)
        self.ui.add_row_btn.clicked.connect(self.restore_deleted)

        # Set up cycle type dropdown for column 8
        cycle_type_delegate = CycleTypeDelegate(self.ui.data_table)
        self.ui.data_table.setItemDelegateForColumn(8, cycle_type_delegate)

        # Set up text input delegates with character limits for name and note columns
        text_delegate_name = TextInputDelegate(self.ui.data_table)
        text_delegate_note = TextInputDelegate(self.ui.data_table)
        self.ui.data_table.setItemDelegateForColumn(0, text_delegate_name)  # Name column
        self.ui.data_table.setItemDelegateForColumn(9, text_delegate_note)  # Note column

        # open the average channel and reference channel dialog
        if isinstance(self.ui, Ui_Processing):
            self.ui.reference_channel_btn.clicked.connect(
                self.open_reference_channel_dlg,
            )

        # data table
        self.ui.data_table.cellDoubleClicked.connect(self.enter_edit_mode)
        self.ui.data_table.cellClicked.connect(self.enter_view_mode)
        self.ui.table_toggle.clicked.connect(self.toggle_table_style)

        # text fields
        self.ui.left_cursor_time.returnPressed.connect(self.update_left)
        self.ui.right_cursor_time.returnPressed.connect(self.update_right)

        # Set up page indicator circles for table toggle BEFORE initializing table_manager
        self.ui.page_indicator.setScene(QGraphicsScene())
        self.circles = (
            QGraphicsEllipseItem(-4, 0, 5, 5),
            QGraphicsEllipseItem(4, 0, 5, 5),
        )
        for c in self.circles:
            self.ui.page_indicator.scene().addItem(c)

        # Initialize cycle manager (handles cycle type/time logic)
        self.cycle_manager = CycleManager(
            cycle_type_dropdown=self.ui.current_cycle_type,
            cycle_time_dropdown=self.ui.current_cycle_time,
            sensorgram_graph=self.full_segment_view
        )

        # Initialize table manager (handles table operations)
        self.table_manager = CycleTableManager(
            table_widget=self.ui.data_table,
            toggle_indicators=self.circles
        )

        logger.debug(f"current row is {self.ui.data_table.currentRow()}")        # add ready flag
        self.enable_controls(data_ready=False)

        # live view and reset segment button if dynamic window, imports if static window
        if self.data_source == "dynamic" and isinstance(self.ui, Ui_Sensorgram):
            self.ui.live_btn.setChecked(True)  # noqa: FBT003
            self.ui.live_btn.clicked.connect(self.toggle_view)
            self.reference_channel_dlg.ui.export_data.clicked.connect(self.export_trigger)

        elif isinstance(self.ui, Ui_Processing):
            self.ui.export_raw_data_btn.clicked.connect(self.export_raw_data)
            self.ui.export_table_btn.clicked.connect(self.export_table)
            self.ui.import_sens_btn.clicked.connect(self.pull_from_sensorgram)
            self.ui.import_raw_data_btn.clicked.connect(self.import_raw_data)
            self.ui.import_table_btn.clicked.connect(self.import_table)
            self.ui.new_segment_btn.clicked.connect(self.start_from_last_seg)

        self.new_segment()

        # Add text box validators
        self.ui.left_cursor_time.setValidator(QDoubleValidator())
        self.ui.right_cursor_time.setValidator(QDoubleValidator())
        if isinstance(self.ui, Ui_Sensorgram):
            self.ui.flow_rate.setValidator(QDoubleValidator(-60000, 60000, 1))

        # Circles for page indicator already created before table_manager initialization

        # Set up valve indicator diagram
        if isinstance(self.ui, Ui_Sensorgram):
            self.ui.loop_diagram.setScene(QGraphicsScene())

            self.loop = QGraphicsEllipseItem(0, 0, 100, 100)
            self.loop_line = QGraphicsLineItem(-20, 0, 120, 0)
            self.sensor_line = QGraphicsLineItem(-20, 120, 120, 120)
            self.loop_label = QGraphicsSimpleTextItem("Loop")
            self.sensor_label = QGraphicsSimpleTextItem("Sensor")

            self.loop.setPen(LOOP_PEN)
            self.loop_line.setPen(LOOP_PEN)
            self.sensor_line.setPen(SENSOR_PEN)

            font = self.loop_label.font()
            font.setPointSize(12)
            font.setWeight(QFont.Weight.Medium)

            self.loop_label.setFont(font)
            self.loop_label.setBrush(LOOP_BRUSH)
            self.loop_label.setPos(125, -12)

            self.sensor_label.setFont(font)
            self.sensor_label.setBrush(SENSOR_BRUSH)
            self.sensor_label.setPos(125, 108)

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
        self.table_manager.update_table_style()

    def _fix_checkbox_styles(self: Self) -> None:
        """Fix checkbox and label styling to use global theme.

        The UI files have inline styles that override the global theme,
        causing gray shades and invisible checkmarks. This method clears
        those problematic inline styles while preserving text colors.
        """
        # Fix channel checkboxes - clear background but keep text color
        for checkbox_name in ['segment_A', 'segment_B', 'segment_C', 'segment_D']:
            if hasattr(self.ui, checkbox_name):
                checkbox = getattr(self.ui, checkbox_name)
                # Get current text color from stylesheet
                current_style = checkbox.styleSheet()
                if 'color:' in current_style:
                    # Extract just the color line
                    import re
                    color_match = re.search(r'color:\s*([^;]+);', current_style)
                    if color_match:
                        color_value = color_match.group(1).strip()
                        # Set only text color, let global theme handle the rest
                        checkbox.setStyleSheet(f"QCheckBox {{ color: {color_value}; background-color: transparent; }}")
                else:
                    checkbox.setStyleSheet("QCheckBox { background-color: transparent; }")

        # Fix shift value labels - make background transparent
        for label_name in ['shift_A', 'shift_B', 'shift_C', 'shift_D']:
            if hasattr(self.ui, label_name):
                label = getattr(self.ui, label_name)
                # Use a light background that's visible but consistent with theme
                label.setStyleSheet("QLabel { background-color: #F5F5F5; border: 1px solid #AAAAAA; padding: 3px; border-radius: 2px; }")

    @Slot()
    def toggle_table_style(self: Self) -> None:
        """Toggle the style of the table."""
        self.table_manager.toggle_table_style()

    def resizeEvent(self: Self, _: object) -> None:  # noqa: N802
        """Resize the widget."""
        self.full_segment_view.resize(
            self.ui.full_segment.width(),
            self.ui.full_segment.height(),
        )
        self.SOI_view.resize(self.ui.SOI.width(), self.ui.SOI.height())

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
                else:
                    self.ui.exp_clock.setText(
                        f"{int(self.exp_clock_raw / 3600):02d}h "
                        f"{int((self.exp_clock_raw % 3600) / 60):02d}m "
                        f"{int(self.exp_clock_raw % 60):02d}s",
                    )
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
        if self.segment_edit is not None:
            self.reassert_row(self.segment_edit)
        self.segment_edit = None
        self.viewing = False
        if isinstance(self.ui, Ui_Processing):
            self.ui.reference_channel_btn.setEnabled(True)  # noqa: FBT003
            self.ui.curr_seg_box.setEnabled(True)  # noqa: FBT003
        self.full_segment_view.movable_cursors(state=True)
        self.cursors_text_edit(state=True)
        self.ui.data_table.clearSelection()
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
        """Update displayed values."""
        if not self.ui.left_cursor_time.hasFocus():
            self.ui.left_cursor_time.setText(
                f"{self.full_segment_view.left_cursor_pos:.2f}",
            )
        if not self.ui.right_cursor_time.hasFocus():
            self.ui.right_cursor_time.setText(
                f"{self.full_segment_view.right_cursor_pos:.2f}",
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

            for ch in CH_LIST:
                text = "0"
                try:
                    if np.isnan(self.current_segment.shift[ch]):
                        text = "no signal"
                    else:
                        text = f"{self.current_segment.shift[ch]:.3f}"
                except Exception as e:
                    logger.exception(f"update display error: {e}")
                getattr(self.ui, f"shift_{ch.upper()}").setText(text)

        if isinstance(self.ui, Ui_Processing):
            self.ui.start_time.setText(f"{start:.2f}")
            self.ui.end_time.setText(f"{end:.2f}")

    def save_segment(self: Self) -> None:
        """Save a segment."""
        logger.debug(f"=== save_segment called: data_source={self.data_source} ===")
        if (
            self.data_source == "dynamic"
            and not self.data["rec"]
            and not self.reloading
        ):
            show_message(msg="Data recording not started!", msg_type="Warning")

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
                    logger.debug("Branch: normal save segment (creating new cycle)")
                    # Set cycle type and time from cycle manager
                    self.current_segment.cycle_type = self.cycle_manager.get_current_type()
                    self.current_segment.cycle_time = self.cycle_manager.get_current_time_minutes()

                    seg = self.current_segment
                    row = len(self.saved_segments)
                    self.seg_count += 1

                    # Show gray zone and fix window when cycle starts
                    logger.debug(f"save_segment: data_source={self.data_source}, cycle_time={self.cycle_manager.get_current_time_minutes()}")
                    if self.data_source == "dynamic":
                        cycle_time_minutes = self.cycle_manager.get_current_time_minutes()
                        logger.debug(f"Cycle start: type={self.current_segment.cycle_type}, time={cycle_time_minutes} min")

                        if cycle_time_minutes is not None and cycle_time_minutes > 0:
                            # Disable live mode to prevent auto-following
                            self.full_segment_view.live = False
                            logger.debug("Disabled live mode for fixed window")
                            
                            # Show the gray zone
                            logger.debug(f"Showing gray zone for {cycle_time_minutes} minutes")
                            try:
                                self.full_segment_view.show_cycle_time_region(cycle_time_minutes)
                                logger.debug("Gray zone function returned successfully")
                            except Exception as e:
                                logger.error(f"Failed to show gray zone: {e}", exc_info=True)

                            # Fix window to cycle_time + 10%
                            window_seconds = cycle_time_minutes * 60 * 1.1  # Add 10%
                            start_time = self.full_segment_view.left_cursor_pos
                            end_time = start_time + window_seconds
                            logger.debug(f"Setting fixed window: X=[{start_time:.2f}s, {end_time:.2f}s] ({window_seconds:.1f}s total)")

                            # Set X range with no padding
                            self.full_segment_view.plot.setXRange(start_time, end_time, padding=0)
                            self.full_segment_view.plot.enableAutoRange(axis='x', enable=False)

                            # Set Y range with padding: +10 on top, -5 on bottom
                            y_min, y_max = self.full_segment_view.plot.viewRange()[1]
                            logger.debug(f"Current Y range: [{y_min:.2f}, {y_max:.2f}]")
                            self.full_segment_view.plot.setYRange(y_min - 5, y_max + 10, padding=0)
                            self.full_segment_view.plot.enableAutoRange(axis='y', enable=False)
                            logger.debug(f"Fixed Y range: [{y_min-5:.2f}, {y_max+10:.2f}]")
                        else:
                            logger.debug(f"Not showing gray zone: cycle_time_minutes={cycle_time_minutes}")

                        # Reset dropdown to default after save
                        self.cycle_manager.reset_to_default()

                if (seg is not None) and (row is not None):
                    # Block signals to prevent cascading updates
                    self.ui.data_table.blockSignals(True)
                    self.ui.data_table.insertRow(row)

                    # Safely create table items with sanitized data
                    try:
                        name = str(seg.name)[:50] if seg.name else ""
                        note = str(seg.note)[:500] if seg.note else ""
                        cycle_type = str(seg.cycle_type) if seg.cycle_type else "Auto-read"

                        self.ui.data_table.setItem(row, 0, QTableWidgetItem(name))
                        self.ui.data_table.setItem(row, 1, QTableWidgetItem(f"{seg.start:.2f}"))
                        self.ui.data_table.setItem(row, 2, QTableWidgetItem(f"{seg.end:.2f}"))
                        self.ui.data_table.setItem(row, 3, QTableWidgetItem(f"{seg.shift['a']:.3f}"))
                        self.ui.data_table.setItem(row, 4, QTableWidgetItem(f"{seg.shift['b']:.3f}"))
                        self.ui.data_table.setItem(row, 5, QTableWidgetItem(f"{seg.shift['c']:.3f}"))
                        self.ui.data_table.setItem(row, 6, QTableWidgetItem(f"{seg.shift['d']:.3f}"))
                        self.ui.data_table.setItem(row, 7, QTableWidgetItem(f"{seg.ref_ch}"))
                        self.ui.data_table.setItem(row, 8, QTableWidgetItem(cycle_type))
                        self.ui.data_table.setItem(row, 9, QTableWidgetItem(note))
                    except Exception as e:
                        logger.error(f"Error creating table items: {e}")
                        # Create minimal safe row if there's an error
                        for col in range(10):
                            if self.ui.data_table.item(row, col) is None:
                                self.ui.data_table.setItem(row, col, QTableWidgetItem(""))

                    # Re-enable signals after all items are set
                    self.ui.data_table.blockSignals(False)

                self.saved_segments.insert(row, self.current_segment)
                self.saving = False
                self.ui.data_table.clearSelection()
                if not self.reloading:
                    # Hide the shaded region after saving
                    self.full_segment_view.hide_cycle_time_region()
                    self.new_segment()

            except Exception as e:
                logger.exception(f"error while saving row {e}")
                # Ensure signals are re-enabled even if error occurs
                self.ui.data_table.blockSignals(False)
        else:
            logger.error("error while saveing row no current_segment")

        # Final safety check to ensure signals are always enabled
        self.ui.data_table.blockSignals(False)

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
            self.ui.data_table.blockSignals(True)

            # Safely create table items with sanitized data
            name = str(seg.name)[:50] if seg.name else ""
            note = str(seg.note)[:500] if seg.note else ""
            cycle_type = str(seg.cycle_type) if seg.cycle_type else "Auto-read"

            self.ui.data_table.setItem(row, 0, QTableWidgetItem(name))
            self.ui.data_table.setItem(row, 1, QTableWidgetItem(f"{seg.start:.2f}"))
            self.ui.data_table.setItem(row, 2, QTableWidgetItem(f"{seg.end:.2f}"))
            self.ui.data_table.setItem(row, 3, QTableWidgetItem(f"{seg.shift['a']:.3f}"))
            self.ui.data_table.setItem(row, 4, QTableWidgetItem(f"{seg.shift['b']:.3f}"))
            self.ui.data_table.setItem(row, 5, QTableWidgetItem(f"{seg.shift['c']:.3f}"))
            self.ui.data_table.setItem(row, 6, QTableWidgetItem(f"{seg.shift['d']:.3f}"))
            self.ui.data_table.setItem(row, 7, QTableWidgetItem(f"{seg.ref_ch}"))
            self.ui.data_table.setItem(row, 8, QTableWidgetItem(cycle_type))
            self.ui.data_table.setItem(row, 9, QTableWidgetItem(note))

            self.ui.data_table.blockSignals(False)
        except Exception as e:
            logger.error(f"Error reasserting table row {row}: {e}")
            self.ui.data_table.blockSignals(False)  # Ensure signals are re-enabled

    def delete_row(self: Self, *, first_available: bool = False) -> None:
        """Delete a row in the data cycle table."""
        if len(self.saved_segments) == 0:
            return

        row = None
        new_seg_trigger = False

        if first_available:
            self.deleted_segment = self.table_manager.delete_row(
                saved_segments=self.saved_segments,
                first_available=True
            )
        else:
            if self.viewing:
                row = self.ui.data_table.currentRow()
                new_seg_trigger = True
            elif self.segment_edit is not None:
                row = self.segment_edit
                new_seg_trigger = True

            self.deleted_segment = self.table_manager.delete_row(
                row=row,
                saved_segments=self.saved_segments
            )

            if new_seg_trigger and not self.saving:
                self.new_segment()

    # open reference channel dialog
    def open_reference_channel_dlg(self: Self) -> None:
        """Open reference channel dialog."""
        self.reference_channel_dlg.show()

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
            for _i in range(self.ui.data_table.rowCount()):
                self.delete_row(first_available=True)
            self.saved_segments = []
            self.current_segment = None
            self.enable_controls(data_ready=False)
            self.live_segment_start = None
            self.seg_count = 0
            self.new_segment()

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
            self.reference_channel_dlg.ui.channelA.setChecked(True)  # noqa: FBT003
        elif ch == "b":
            self.reference_channel_dlg.ui.channelB.setChecked(True)  # noqa: FBT003
        elif ch == "c":
            self.reference_channel_dlg.ui.channelC.setChecked(True)  # noqa: FBT003
        elif ch == "d":
            self.reference_channel_dlg.ui.channelD.setChecked(True)  # noqa: FBT003
        else:
            self.reference_channel_dlg.ui.noRef.setChecked(True)  # noqa: FBT003

    def setup(self: Self) -> None:
        """Set up the widget."""
        title = "Sensorgram" if self.data_source == "dynamic" else "Data Processing"
        self.full_segment_view = SensorgramGraph(title)
        self.full_segment_view.setParent(self.ui.full_segment)
        self.full_segment_view.show()

        self.SOI_view = SegmentGraph("Cycle of Interest", self.unit)
        self.SOI_view.setParent(self.ui.SOI)
        self.SOI_view.show()

    def disable_channels(self: Self, error_channels: list[str]) -> None:
        """Disable some channels."""
        if len(error_channels) == 0:
            for ch in CH_LIST:
                getattr(self.ui, f"segment_{ch.upper()}").setEnabled(
                    True,  # noqa: FBT003
                )
        else:
            for ch in error_channels:
                getattr(self.ui, f"segment_{ch.upper()}").setEnabled(
                    False,  # noqa: FBT003
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
        for row in range(self.ui.data_table.rowCount()):
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
        return self.table_manager.get_row_info(row)

    def enter_view_mode(self: Self) -> None:
        """Enter view mode."""
        if (
            (self.ui.data_table.currentRow() > -1)
            and (self.segment_edit is None)
            and (len(self.saved_segments) > self.ui.data_table.currentRow())
        ):
            self.viewing = True
            self.full_segment_view.block_updates = True
            if isinstance(self.ui, Ui_Processing):
                self.ui.curr_seg_box.setEnabled(False)  # noqa: FBT003
                self.ui.reference_channel_btn.setEnabled(False)  # noqa: FBT003
            row: int = self.ui.data_table.currentRow()
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
                cycle_type_text = self.current_segment.cycle_type if self.current_segment.cycle_type else "Auto-read"
                cycle_time = self.current_segment.cycle_time
                self.cycle_manager.set_cycle_info(cycle_type_text, cycle_time)
            except Exception as e:
                logger.warning(f"Could not set cycle info: {e}")
                self.cycle_manager.reset_to_default()

    def enter_edit_mode(self: Self) -> None:
        """Enter edit mode."""
        if self.ui.data_table.currentRow() > -1 and self.segment_edit is None:
            if isinstance(self.ui, Ui_Processing):
                self.ui.curr_seg_box.setEnabled(True)  # noqa: FBT003
                self.ui.reference_channel_btn.setEnabled(True)  # noqa: FBT003
            self.viewing = False
            if self.data_source == "dynamic":
                self.set_live(on=False)
            self.full_segment_view.block_updates = True
            self.full_segment_view.movable_cursors(state=True)
            self.cursors_text_edit(state=True)
            row = self.ui.data_table.currentRow()
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
        for row in range(self.ui.data_table.rowCount()):
            for col in range(self.ui.data_table.columnCount()):
                item = self.ui.data_table.item(row, col)
                if item is not None:
                    # Highlight the current row if viewing or editing
                    if isinstance(edit_row, int) and row == edit_row:
                        item.setBackground(self.edit_color)
                    elif self.viewing and row == self.ui.data_table.currentRow():
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
                    columns = ["GraphAll_x", "GraphAll_y"]

                    with file as txtfile:
                        cf = csv.DictReader(
                            txtfile,
                            dialect="excel-tab",
                            fieldnames=columns,
                        )

                        temp_data_all = {
                            "Time": {ch: np.array([]) for ch in CH_LIST},
                            "Intensity": {ch: np.array([]) for ch in CH_LIST},
                        }
                        count = 0
                        ch_list = ["d", "a", "b", "c"]
                        for row in cf:
                            if skip_first:
                                skip_first = False
                                continue
                            count += 1
                            ch = ch_list[(count % 4)]
                            temp_data_all["Time"][ch] = np.append(
                                temp_data_all["Time"][ch],
                                float(row["GraphAll_x"]),
                            )
                            temp_data_all["Intensity"][ch] = np.append(
                                temp_data_all["Intensity"][ch],
                                float(row["GraphAll_y"]),
                            )

                    for ch in CH_LIST:
                        logger.debug(
                            f"temp data ch {ch}: "
                            f"{temp_data_all['Time'][ch]}, "
                            f"{temp_data_all['Intensity'][ch]}",
                        )
                        self.data["lambda_times"][ch] = np.append(
                            self.data["lambda_times"][ch],
                            temp_data_all["Time"][ch],
                        )
                        self.data["lambda_values"][ch] = np.append(
                            self.data["lambda_values"][ch],
                            temp_data_all["Intensity"][ch],
                        )
                    logger.debug(f" all graph import: {self.data}")

                else:
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

                    with file as txtfile:
                        cf = csv.DictReader(
                            txtfile,
                            dialect="excel-tab",
                            fieldnames=columns,
                        )
                        references = self.metadata.read_header(cf, columns)

                        temp_data: dict[str, list[float]] = {
                            "Time_A": [],
                            "Channel_A": [],
                            "Time_B": [],
                            "Channel_B": [],
                            "Time_C": [],
                            "Channel_C": [],
                            "Time_D": [],
                            "Channel_D": [],
                        }

                        for row in cf:
                            for i, column in enumerate(columns):
                                value = float(row[column])

                                # Must change the odd columns from RU to nm for
                                # new file formats
                                quot, rem = divmod(i, 2)
                                if references and rem == 1:
                                    value = value / 355 + references[quot]

                                temp_data[column].append(value)

                    self.data["lambda_times"]["a"] = np.append(
                        self.data["lambda_times"]["a"],
                        temp_data["Time_A"],
                    )
                    self.data["lambda_values"]["a"] = np.append(
                        self.data["lambda_values"]["a"],
                        temp_data["Channel_A"],
                    )
                    self.data["lambda_times"]["b"] = np.append(
                        self.data["lambda_times"]["b"],
                        temp_data["Time_B"],
                    )
                    self.data["lambda_values"]["b"] = np.append(
                        self.data["lambda_values"]["b"],
                        temp_data["Channel_B"],
                    )
                    self.data["lambda_times"]["c"] = np.append(
                        self.data["lambda_times"]["c"],
                        temp_data["Time_C"],
                    )
                    self.data["lambda_values"]["c"] = np.append(
                        self.data["lambda_values"]["c"],
                        temp_data["Channel_C"],
                    )
                    self.data["lambda_times"]["d"] = np.append(
                        self.data["lambda_times"]["d"],
                        temp_data["Time_D"],
                    )
                    self.data["lambda_values"]["d"] = np.append(
                        self.data["lambda_values"]["d"],
                        temp_data["Channel_D"],
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
        """Import cycle data table."""
        if (len(self.data["lambda_times"]["a"]) > 0) and (
            len(self.data["lambda_times"]["a"]) == len(self.data["lambda_times"]["d"])
        ):
            file_name = QFileDialog.getOpenFileName(
                self,
                "Open File",
                "",
                "Text Files (*.txt)",
            )[0]

            try:
                file = Path(file_name).open(encoding="utf-8")  # noqa: SIM115
            except Exception as e:
                logger.debug(f"import table error {type(e)}")
                logger.exception(f"file open error: {e}")
                return

            try:
                if self.segment_edit is not None:
                    self.new_segment()

                for _i in range(self.ui.data_table.rowCount()):
                    self.delete_row(first_available=True)
                self.seg_count = 0

                with file as txtfile:
                    has_ref = True
                    cf = csv.DictReader(
                        txtfile,
                        dialect="excel-tab",
                        fieldnames=[
                            "Name",
                            "StartTime",
                            "EndTime",
                            "ShiftA",
                            "ShiftB",
                            "ShiftC",
                            "ShiftD",
                            "Ref",
                            "UserNote",
                        ],
                    )

                    i = 0
                    for row in cf:
                        if row["Name"] == "Name":
                            if row["Ref"] == "UserNote":
                                has_ref = False
                            continue
                        if has_ref:
                            ref_ch = row["Ref"]
                            if ref_ch in {"", "None"}:
                                ref_ch = None
                            user_note = row["UserNote"]
                        else:
                            ref_ch = None
                            user_note = row["Ref"]
                        self.current_segment = Segment(
                            i,
                            float(row["StartTime"]),
                            float(row["EndTime"]),
                        )
                        self.current_segment.add_info(
                            {"name": row["Name"], "note": user_note},
                        )
                        self.current_segment.add_data(
                            self.data,
                            self.unit,
                            ref_ch,
                        )
                        self.save_segment()
                        i += 1

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
                    # Clamp to valid range (bisect_left can return len(array))
                    array_len = len(l_val_data[CH_LIST[0]])
                    if array_len == 0:
                        logger.error("Cannot export: no data in lambda_values")
                        return
                    reference_index = min(reference_index, array_len - 1)
                    logger.debug(f"Export reference index: {reference_index} (array length: {array_len})")
                    references = [l_val_data[ch][reference_index] for ch in CH_LIST]

                    row_count = min(len(x) for x in l_time_data.values())

                    self.metadata.write_tracedrawer_header(
                        writer,
                        fieldnames,
                        "Raw data",
                        references,
                    )

                    for i in range(row_count):
                        for ch in CH_LIST:
                            if np.isnan(l_val_data[ch][i]):
                                l_val_data[ch][i] = None
                        writer.writerow(
                            {
                                "X_RawDataA": round(l_time_data["a"][i], 4),
                                "Y_RawDataA": round(
                                    (l_val_data["a"][i] - references[0]) * 355,
                                    4,
                                ),
                                "X_RawDataB": round(l_time_data["b"][i], 4),
                                "Y_RawDataB": round(
                                    (l_val_data["b"][i] - references[1]) * 355,
                                    4,
                                ),
                                "X_RawDataC": round(l_time_data["c"][i], 4),
                                "Y_RawDataC": round(
                                    (l_val_data["c"][i] - references[2]) * 355,
                                    4,
                                ),
                                "X_RawDataD": round(l_time_data["d"][i], 4),
                                "Y_RawDataD": round(
                                    (l_val_data["d"][i] - references[3]) * 355,
                                    4,
                                ),
                            },
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

                        row_count = len(l_time_data["a"])
                        for ch in CH_LIST:
                            if len(l_time_data[ch]) < row_count:
                                row_count = len(l_time_data[ch])

                        for i in range(row_count):
                            for ch in CH_LIST:
                                if np.isnan(l_val_data[ch][i]):
                                    l_val_data[ch][i] = None
                            writer.writerow(
                                {
                                    "X_DataA": round(l_time_data["a"][i], 4),
                                    "Y_DataA": round(l_val_data["a"][i], 4),
                                    "X_DataB": round(l_time_data["b"][i], 4),
                                    "Y_DataB": round(l_val_data["b"][i], 4),
                                    "X_DataC": round(l_time_data["c"][i], 4),
                                    "Y_DataC": round(l_val_data["c"][i], 4),
                                    "X_DataD": round(l_time_data["d"][i], 4),
                                    "Y_DataD": round(l_val_data["d"][i], 4),
                                },
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

    # export table data
    def export_table(
        self: Self,
        *,
        preset: bool = False,
        preset_dir: str | None = None,
    ) -> None:
        """Export table data."""
        try:
            row_count = len(self.saved_segments)
            table_data = []
            for i in range(row_count):
                name = self.ui.data_table.item(i, 0).text()
                start = self.ui.data_table.item(i, 1).text()
                end = self.ui.data_table.item(i, 2).text()
                shift_a = self.ui.data_table.item(i, 3).text()
                shift_b = self.ui.data_table.item(i, 4).text()
                shift_c = self.ui.data_table.item(i, 5).text()
                shift_d = self.ui.data_table.item(i, 6).text()
                ref = self.ui.data_table.item(i, 7).text()
                cycle_type = self.ui.data_table.item(i, 8).text()
                note = self.ui.data_table.item(i, 9).text()
                table_data.append(
                    {
                        "Name": name,
                        "StartTime": start,
                        "EndTime": end,
                        "ShiftA": shift_a,
                        "ShiftB": shift_b,
                        "ShiftC": shift_c,
                        "ShiftD": shift_d,
                        "Reference": ref,
                        "CycleType": cycle_type,
                        "UserNote": note,
                    },
                )
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
                with Path(full_file).open(
                    mode="w",
                    newline="",
                    encoding="utf-8",
                ) as txtfile:
                    fieldnames = [
                        "Name",
                        "StartTime",
                        "EndTime",
                        "ShiftA",
                        "ShiftB",
                        "ShiftC",
                        "ShiftD",
                        "Reference",
                        "CycleType",
                        "UserNote",
                    ]
                    writer = csv.DictWriter(
                        txtfile,
                        dialect="excel-tab",
                        fieldnames=fieldnames,
                    )
                    writer.writeheader()
                    for row in table_data:
                        writer.writerow(row)

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
                            if len(seg.seg_x[ch]) < row_count:
                                row_count = len(seg.seg_x[ch])

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

    def save_data(self: Self, rec_dir: str) -> None:
        """Save data."""
        self.export_raw_data(preset=True, preset_dir=rec_dir)
        self.export_table(preset=True, preset_dir=rec_dir)

    def start_recording(self: Self, rec_dir: str) -> None:
        """Start recording."""
        # Reset time reference (but keep existing data - it will have negative timestamps)
        self.full_segment_view.reset_time()
        self.live_segment_start = None
        # Move yellow cursor (right) slightly ahead to avoid timing gap on first point
        # Use 0.5 seconds to account for data collection timing
        self.full_segment_view.set_right(0.5, emit=False, update=False)
        logger.debug("Recording started: yellow cursor set to 0.5s")
        self.new_segment()
        self.save_data(rec_dir)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    app = QApplication([])

    widget = DataWindow("static")
    for key in widget.data["lambda_times"]:
        widget.data["lambda_times"][key] = np.arange(500, dtype=np.float64)
        widget.data["lambda_values"][key] = np.random.default_rng().random(500)

    widget.export_raw_data(preset=True, preset_dir=Path("data_export") / Path("Test"))
