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

from affilabs.widgets._dw_models import (
    CYCLE_WINDOW_PADDING_FACTOR,
    CYCLE_Y_PADDING_TOP,
    CYCLE_Y_PADDING_BOTTOM,
    LOOP_BRUSH,
    LOOP_PEN,
    SENSOR_BRUSH,
    SENSOR_PEN,
    PROGRESS_BAR_UPDATE_TIME,
    DataDict,
    RoundedFrame,
    Segment,
)


from affilabs.widgets._dw_inject_mixin import InjectMixin
from affilabs.widgets._dw_setup_mixin import SetupMixin
from affilabs.widgets._dw_segment_mixin import SegmentMixin
from affilabs.widgets._dw_import_mixin import ImportMixin
from affilabs.widgets._dw_export_mixin import ExportMixin


class DataWindow(InjectMixin, SetupMixin, SegmentMixin, ImportMixin, ExportMixin, QWidget):
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
            from affilabs.ui_styles import get_button_style, get_container_style

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
            # Connect to sidebar's cycle history dialog (shows completed cycles, not segments)
            if hasattr(self, 'sidebar') and hasattr(self.sidebar, '_open_cycle_table_dialog'):
                cycle_data_widget.set_cycle_data_callback(self.sidebar._open_cycle_table_dialog)
            else:
                # Fallback to old segment dialog if sidebar not available
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

            from affilabs.ui_styles import Colors, Radius

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
        # Keep soi_frame header buttons in sync
        if hasattr(self, "soi_frame"):
            self.soi_frame.set_reference_channel(ch)

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

    # export table data
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
