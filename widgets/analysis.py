# This module is riddled with long function that have too many statements, too many
# branches, and are too complex. It also contains a lot of catch all exception blocks.
# These should eventually be adressed, but for now we'll just turn off the warnings.
# ruff: noqa: PLR0912, PLR0915, C901, BLE001

"""Widget for doing data analysis."""

import csv
import datetime
import json
from copy import deepcopy
from functools import partial
from pathlib import Path

# Python version compatibility
try:
    from typing import Optional, Self  # Python 3.11+
except ImportError:
    from typing_extensions import Self  # Python < 3.11
    from typing import Optional

import numpy as np
from pyqtgraph import InfiniteLine, PlotDataItem, mkPen
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QTableWidgetItem, QWidget

from settings import CH_LIST, SW_VERSION
from ui.ui_analysis import Ui_FormAnalysis
from utils.logger import logger
from utils.validator import NumericDelegate
from widgets.datawindow import DataDict, Segment
from widgets.graphs import SegmentGraph
from widgets.ka_kd_wizard import KAKDWizardDialog
from widgets.kd_wizard import KDWizardDialog
from widgets.message import show_message

# Python version compatibility for UTC
try:
    TIMEZONE = datetime.datetime.now(datetime.UTC).astimezone().tzinfo
except AttributeError:
    import datetime as dt

    TIMEZONE = dt.datetime.now(dt.UTC).astimezone().tzinfo
SEGMENT_COLORS = [
    "#c93c8a",
    "#ff8e1c",
    "#ffff00",
    "#6bffb5",
    "#26d1d1",
    "#699bff",
    "#7303fc",
    "#c080ff",
    "#ffa8dc",
    "#ffa8dc",
    "#f7d34f",
    "#6bfaba",
    "#31c6f7",
    "#c2027b",
    "#6e16a8",
    "#b09dcc",
    "#ace600",
    "#fbff8c",
    "#ffb3b3",
    "#ffdd99",
    "#40bf40",
    "#adebeb",
    "#ff3333",
    "#80bfff",
    "#e60000",
    "#cc00cc",
    "#ff4242",
    "#00cccc",
    "#00cc88",
    "#ffb3ff",
    "#4d4dff",
    "#ff99c0",
]


class AnalysisWindow(QWidget):
    """Widget for doing data analysis."""

    export_error_signal = Signal()

    def __init__(self: Self) -> None:
        """Make widget for doing data analysis."""
        super().__init__()
        self.ui = Ui_FormAnalysis()
        self.ui.setupUi(self)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, on=True)
        self.base_segments: list[AnalysisSegment] = []
        self.auto_segments: list[AnalysisSegment] = []
        self.unit = "RU"
        self.updating_table = False
        self.ui.seg_select.currentIndexChanged.connect(self.display_segment)
        delegate = NumericDelegate(self.ui.data_table)
        self.ui.data_table.setItemDelegate(delegate)
        self.ui.data_table.itemChanged.connect(self.on_analysis_table_edited)

        # SOI and Cursor Setup
        self.analysis_SOI_view = SegmentGraph(
            "Segment of Interest",
            self.unit,
            has_cursors=True,
        )
        self.analysis_SOI_view.dissoc_cursor_sig.connect(self.update_dissociation)
        self.analysis_SOI_view.assoc_cursor_sig.connect(self.update_association)
        self.ui.assoc_cursors.toggled.connect(self.en_assoc_cursors)
        self.ui.dissoc_cursors.toggled.connect(self.en_dissoc_cursors)
        self.analysis_SOI_view.setParent(self.ui.SOI)

        # UI Setup
        for ch in CH_LIST:
            getattr(self.ui, f"segment_{ch.upper()}").stateChanged.connect(
                partial(self.analysis_SOI_view.display_channel_changed, ch),
            )
            getattr(self.ui, f"radio_{ch}").toggled.connect(
                partial(self._on_stack_channel_changed, ch),
            )
        self.ui.export_btn.clicked.connect(self.export_analysis_data)
        self.ui.import_btn.clicked.connect(self.import_analysis_data)
        self.ui.reset_analysis_btn.clicked.connect(self.clear_analysis_segments)
        self.ui.fit_wizard_btn.clicked.connect(self._show_kd_wizard)
        self.ui.kin_wizard_btn.clicked.connect(self._show_ka_kd_wizard)
        self._kd_dlg: KDWizardDialog | None = None
        self._ka_kd_dlg: KAKDWizardDialog | None = None

        # Stacked Graph Setup
        self.ui.stack_graph.getAxis("bottom").enableAutoSIPrefix(enable=False)
        self.ui.stack_graph.getAxis("left").enableAutoSIPrefix(enable=False)
        self.ui.stack_graph.plotItem.setTitle(
            "Select a channel to display segments",
            color="w",
        )
        self.ui.stack_graph.plotItem.showGrid(x=True, y=True, alpha=0.3)
        self.ui.stack_graph.setLabel(axis="bottom", text="Time (s)")
        self.ui.stack_graph.setLabel(axis="left", text="Shift (RU)")
        self.ui.stack_graph.plotItem.addLegend()
        self.ui.stack_graph.setMenuEnabled(enableMenu=True)
        self.ui.stack_graph.setMouseEnabled(x=True, y=True)
        self.assoc_plots: list[PlotDataItem] = []  # type: ignore[no-any-unimported]
        self.dissoc_markers: list[InfiniteLine] = []  # type: ignore[no-any-unimported]
        self.curr_ch = "a"
        self.resizeEvent()
        self.analysis_SOI_view.show()

    def resizeEvent(self: Self, _: object = None) -> None:  # noqa: N802
        """Handle a resize event."""
        try:
            self.analysis_SOI_view.resize(self.ui.SOI.width(), self.ui.SOI.height())
        except Exception as e:
            logger.exception(f"Error while resizing analysis display: {e}")

    def clear_analysis_segments(self: Self) -> None:
        """Clear analysis segments."""
        try:
            self.base_segments = []
            self.auto_segments = []
            for p in self.assoc_plots:
                self.ui.stack_graph.plotItem.removeItem(p)
            for m in self.dissoc_markers:
                self.ui.stack_graph.plotItem.removeItem(m)
            self.assoc_plots = []
            self.dissoc_markers = []
            self.analysis_SOI_view.reset_segment_graph(unit=self.unit)
            self.ui.seg_select.clear()
            self.ui.data_table.clearContents()
            self.update_table()
        except Exception as e:
            logger.exception(f"Error while clearing analysis segments: {e}")

    def load_data(
        self: Self,
        raw_data: DataDict,
        saved_segments: list[Segment],
        units: str,
    ) -> None:
        """Load data into widget."""
        try:
            if (
                len(self.base_segments) > 0 or len(self.auto_segments) > 0
            ) and show_message(
                msg_type="Information",
                msg="Overwrite previous segments in Data Analysis?",
                yes_no=True,
            ):
                self.clear_analysis_segments()
            loaded = False
            self.unit = units
            self.ui.stack_graph.setLabel(axis="left", text=f"Shift ({self.unit})")
            self.ui.data_table.horizontalHeaderItem(1).setText(
                f"Assoc.\nShift ({self.unit})",
            )
            self.ui.data_table.horizontalHeaderItem(4).setText(
                f"Dissoc.\nShift ({self.unit})",
            )
            if raw_data is not None and saved_segments is not None:
                if (
                    len(raw_data["lambda_times"]) > 0
                    and len(raw_data["lambda_values"]) > 0
                    and len(saved_segments) > 0
                ):
                    logger.debug("Loading base data for analysis")
                    self.auto_segments = []
                    for seg in saved_segments:
                        self.base_segments.append(AnalysisSegment(deepcopy(seg)))
                        i = max(0, (len(self.base_segments) - 1)) % len(SEGMENT_COLORS)
                        plt = self.ui.stack_graph.plot(
                            pen=mkPen(SEGMENT_COLORS[i], width=2),
                            name=f"Segment {seg.name}",
                        )
                        self.assoc_plots.append(plt)
                        d_mrk = InfiniteLine(
                            pos=0,
                            pen=mkPen(
                                SEGMENT_COLORS[i],
                                width=2,
                                style=Qt.PenStyle.DotLine,
                            ),
                            movable=False,
                        )
                        self.ui.stack_graph.addItem(d_mrk)
                        self.dissoc_markers.append(d_mrk)
                    self.auto_segment()
                    self.ui.data_table.clearContents()
                    self.update_table()
                    loaded = True
                    self.analysis_SOI_view.reset_segment_graph(unit=self.unit)
                    if len(self.auto_segments) > 0:
                        self.analysis_SOI_view.update_display(
                            self.auto_segments[0],
                            use_data=True,
                        )
                self._on_stack_channel_changed(ch=self.curr_ch, active=True)
            if not loaded:
                logger.debug("No data for analysis")
        except Exception as e:
            logger.exception(f"Error, could not load data for analysis: {e}")

    def update_table(self: Self) -> None:
        """Update table."""
        self.updating_table = True
        try:
            if len(self.auto_segments) > 0:
                seg = self.auto_segments[self.ui.seg_select.currentIndex()]
                for i, ch in enumerate(CH_LIST):
                    self.ui.current_note.setText(f"{seg.note}")
                    self.ui.data_table.setItem(
                        i,
                        0,
                        QTableWidgetItem(f"{seg.conc[ch]:.3f}"),
                    )
                    self.ui.data_table.setItem(
                        i,
                        1,
                        QTableWidgetItem(f"{seg.assoc_shift[ch]:.3f}"),
                    )
                    self.ui.data_table.setItem(
                        i,
                        2,
                        QTableWidgetItem(f"{seg.assoc_start[ch]:.3f}"),
                    )
                    self.ui.data_table.setItem(
                        i,
                        3,
                        QTableWidgetItem(f"{seg.assoc_end[ch]:.3f}"),
                    )
                    self.ui.data_table.setItem(
                        i,
                        4,
                        QTableWidgetItem(f"{seg.dissoc_shift[ch]:.3f}"),
                    )
                    self.ui.data_table.setItem(
                        i,
                        5,
                        QTableWidgetItem(f"{seg.dissoc_start[ch]:.3f}"),
                    )
                    self.ui.data_table.setItem(
                        i,
                        6,
                        QTableWidgetItem(f"{seg.dissoc_end[ch]:.3f}"),
                    )
                    self.ui.data_table.setItem(
                        i,
                        7,
                        QTableWidgetItem(f"{seg.start[ch]:.3f}"),
                    )
                    self.ui.data_table.setItem(i, 8, QTableWidgetItem(f"{seg.ref_ch}"))
                    for col in range(9):
                        self.ui.data_table.item(i, col).setFlags(
                            Qt.ItemFlag.NoItemFlags,
                        )
                        if col in {
                            0,
                            2,
                            3,
                            5,
                            6,
                            7,
                        }:  # Enable edit feature for Conc & Time values only.
                            self.ui.data_table.item(i, col).setFlags(
                                Qt.ItemFlag.ItemIsEnabled
                                | Qt.ItemFlag.ItemIsSelectable
                                | Qt.ItemFlag.ItemIsEditable,
                            )
                        else:  # Enable edit feature for Conc & Time values only.
                            self.ui.data_table.item(i, col).setFlags(
                                Qt.ItemFlag.ItemIsEnabled,
                            )
        except Exception as e:
            logger.exception(f"Error while updating analysis table: {e}")
        self.updating_table = False

    def update_association(self: Self, ch: object, start: object, end: object) -> None:
        """Update the association section."""
        if len(self.auto_segments) > 0:
            try:
                seg = self.auto_segments[self.ui.seg_select.currentIndex()]
                seg.assoc_start[ch] = start
                seg.assoc_end[ch] = end
                self.update_table()
                self.on_analysis_table_edited()
            except Exception as e:
                logger.debug(f"error {e} when trying to update dissociation marker")

    def update_dissociation(self: Self, ch: object, start: object, end: object) -> None:
        """Update dissociation section."""
        if len(self.auto_segments) > 0:
            try:
                seg = self.auto_segments[self.ui.seg_select.currentIndex()]
                seg.dissoc_start[ch] = start
                seg.dissoc_end[ch] = end
                self.update_table()
                self.on_analysis_table_edited()
            except Exception as e:
                logger.debug(f"error {e} when trying to update dissociation marker")

    def display_segment(self: Self) -> None:
        """Display a segment."""
        try:
            if len(self.auto_segments) > 0:
                seg = self.auto_segments[self.ui.seg_select.currentIndex()]
                self.analysis_SOI_view.update_display(seg, use_data=True)
                for ch in CH_LIST:
                    self.analysis_SOI_view.move_assoc_cursors(
                        ch,
                        seg.assoc_start[ch],
                        seg.assoc_end[ch],
                    )
                    self.analysis_SOI_view.move_dissoc_cursors(
                        ch,
                        seg.dissoc_start[ch],
                        seg.dissoc_end[ch],
                    )
                self.update_table()
            else:
                self.analysis_SOI_view.reset_segment_graph()
        except Exception as e:
            logger.exception(f"Error while displaying analysis segment: {e}")

    def auto_segment(self: Self) -> None:
        """Automatically find segments."""
        try:
            self.auto_segments = deepcopy(self.base_segments)
            for seg in self.auto_segments:
                ch_list = [
                    ch
                    for ch in CH_LIST
                    if np.any(seg.base_seg_y[ch] != np.nan)
                    and np.any(seg.base_seg_y[ch] == 0)
                ]
                for ch in ch_list:
                    seg.assoc_end[ch] = seg.data_x[ch][-1]
                    seg.dissoc_start[ch] = seg.data_x[ch][-1]
                    seg.dissoc_end[ch] = seg.data_x[ch][-1]
            dropdown = [f"Segment {seg.name}" for seg in self.auto_segments]
            self.ui.seg_select.clear()
            self.ui.seg_select.addItems(dropdown)
            self.update_table()
        except Exception as e:
            logger.exception(f"Error while running auto-segmentation: {e}")
            self.clear_analysis_segments()
            show_message(
                msg_type="Warning",
                msg="Error: Auto-Segment Failed"
                "\nPlease check segments in Data Processing",
            )

    def export_analysis_data(self: Self) -> None:
        """Export data for data analysis."""
        try:
            export_dir = QFileDialog.getExistingDirectory(
                self,
                "Choose directory for Data Analysis export",
                "",
            )
            if (export_dir is not None) and (export_dir != ""):
                with Path(f"{export_dir}/Analysis-Segments-Table.txt").open(
                    mode="w",
                    newline="",
                    encoding="utf-8",
                ) as txtfile:
                    fieldnames = [
                        "Name",
                        "Conc_A",
                        "Assoc_Shift_A",
                        "Assoc_Start_A",
                        "Assoc_End_A",
                        "Dissoc_Shift_A",
                        "Dissoc_Start_A",
                        "Dissoc_End_A",
                        "Conc_B",
                        "Assoc_Shift_B",
                        "Assoc_Start_B",
                        "Assoc_End_B",
                        "Dissoc_Shift_B",
                        "Dissoc_Start_B",
                        "Dissoc_End_B",
                        "Conc_C",
                        "Assoc_Shift_C",
                        "Assoc_Start_C",
                        "Assoc_End_C",
                        "Dissoc_Shift_C",
                        "Dissoc_Start_C",
                        "Dissoc_End_C",
                        "Conc_D",
                        "Assoc_Shift_D",
                        "Assoc_Start_D",
                        "Assoc_End_D",
                        "Dissoc_Shift_D",
                        "Dissoc_Start_D",
                        "Dissoc_End_D",
                        "Ref_Ch",
                        "Note",
                    ]
                    table_data: list[dict[str, str]] = []
                    for i, seg in enumerate(self.auto_segments):
                        table_data.append({})
                        table_data[i]["Name"] = f"{seg.name}"
                        table_data[i]["Ref_Ch"] = f"{seg.ref_ch}"
                        table_data[i]["Note"] = f"{seg.note}"
                        for ch in CH_LIST:
                            table_data[i][f"Conc_{ch.upper()}"] = f"{seg.conc[ch]:.3f}"
                            table_data[i][f"Assoc_Shift_{ch.upper()}"] = (
                                f"{seg.assoc_shift[ch]:.3f}"
                            )
                            table_data[i][f"Assoc_Start_{ch.upper()}"] = (
                                f"{seg.assoc_start[ch]:.3f}"
                            )
                            table_data[i][f"Assoc_End_{ch.upper()}"] = (
                                f"{seg.assoc_end[ch]:.3f}"
                            )
                            table_data[i][f"Dissoc_Shift_{ch.upper()}"] = (
                                f"{seg.dissoc_shift[ch]:.3f}"
                            )
                            table_data[i][f"Dissoc_Start_{ch.upper()}"] = (
                                f"{seg.dissoc_start[ch]:.3f}"
                            )
                            table_data[i][f"Dissoc_End_{ch.upper()}"] = (
                                f"{seg.dissoc_end[ch]:.3f}"
                            )
                            table_data[i][f"Dissoc_Shift_{ch.upper()}"] = (
                                f"{seg.dissoc_shift[ch]:.3f}"
                            )
                    writer = csv.DictWriter(
                        txtfile,
                        dialect="excel-tab",
                        fieldnames=fieldnames,
                    )
                    writer.writeheader()
                    for table_data_row in table_data:
                        writer.writerow(table_data_row)
                    for seg in self.auto_segments:
                        for ch in CH_LIST:
                            with Path(
                                f"{export_dir}"
                                f"/Analysis Seg {seg.name} Ch {ch.upper()}.txt",
                            ).open(
                                "w",
                                newline="",
                                encoding="utf-8",
                            ) as txt_file:
                                fieldnames = ["X", "Y"]
                                writer = csv.DictWriter(
                                    txt_file,
                                    dialect="excel-tab",
                                    fieldnames=fieldnames,
                                )
                                writer.writerow({fieldnames[0]: "Plot name"})
                                writer.writerow(
                                    {
                                        fieldnames[0]: "Plot xlabel",
                                        fieldnames[1]: "Time (s)",
                                    },
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
                                now = datetime.datetime.now(TIMEZONE)
                                writer.writerow(
                                    {
                                        fieldnames[0]: "Property Analysis date",
                                        fieldnames[1]: f"{now:%Y-%m-%d %H:%M:%S}",
                                    },
                                )
                                writer.writerow(
                                    {
                                        fieldnames[0]: "Property Filename",
                                        fieldnames[
                                            1
                                        ]: f"Analysis Seg {seg.name} CH {ch}",
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
                                    {fieldnames[0]: "Curve", fieldnames[1]: 1},
                                )
                                writer.writerow(
                                    {
                                        fieldnames[0]: "Curve name",
                                        fieldnames[1]: f"{seg.note} Ch {ch}",
                                    },
                                )
                                writer.writerow(
                                    {
                                        fieldnames[0]: "Curve type",
                                        fieldnames[1]: "Curve",
                                    },
                                )
                                writer.writerow(
                                    {
                                        fieldnames[0]: "Curve ligand",
                                        fieldnames[1]: "N/A",
                                    },
                                )
                                writer.writerow(
                                    {
                                        fieldnames[0]: "Curve concentration (M)",
                                        fieldnames[1]: f"{seg.conc[ch]}E-8",
                                    },
                                )
                                writer.writerow(
                                    {
                                        fieldnames[0]: "Curve target",
                                        fieldnames[1]: "N/A",
                                    },
                                )
                                writer.writerow(
                                    {
                                        fieldnames[0]: "Curve description",
                                        fieldnames[1]: f"Segment {seg.name} Ch {ch}",
                                    },
                                )
                                writer.writerow(
                                    {fieldnames[0]: "X", fieldnames[1]: "Y"},
                                )
                                for i in range(len(seg.seg_x[ch])):
                                    writer.writerow(
                                        {
                                            fieldnames[0]: seg.seg_x[ch][i],
                                            fieldnames[1]: seg.seg_y[ch][i],
                                        },
                                    )
                    for ch in CH_LIST:
                        fieldnames = []
                        index_list = []
                        for n, seg in enumerate(self.auto_segments):
                            index_list.append(2 * n)
                            fieldnames.append(f"X{ch.upper()}{seg.name}")
                            fieldnames.append(f"Y{ch.upper()}{seg.name}")
                        with Path(
                            f"{export_dir}/Analysis Stacked Graph Ch{ch.upper()}.txt",
                        ).open(
                            "w",
                            newline="",
                            encoding="utf-8",
                        ) as txt_file:
                            writer = csv.DictWriter(
                                txt_file,
                                dialect="excel-tab",
                                fieldnames=fieldnames,
                            )
                            writer.writerow({fieldnames[0]: "Plot name"})
                            writer.writerow(
                                {
                                    fieldnames[0]: "Plot xlabel",
                                    fieldnames[1]: "Time (s)",
                                },
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
                            now = datetime.datetime.now(TIMEZONE)
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
                                    fieldnames[1]: f"Analysis Seg {seg.name} CH {ch}",
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
                            curve_num = {}  # 'Curve'
                            curve_name = {}  # 'Curve name'
                            curve_type = {}  # 'Curve type'
                            curve_ligand = {}  # 'Curve ligand'
                            curve_conc = {}  # 'Curve concentration (M)'
                            curve_target = {}  # 'Curve target'
                            curve_desc = {}  # 'Curve description'
                            curve_xy = {}
                            for ind in index_list:
                                seg = self.auto_segments[int(ind / 2)]
                                curve_num[fieldnames[ind]] = "Curve"
                                curve_num[fieldnames[ind + 1]] = str(int(ind / 2) + 1)
                                curve_name[fieldnames[ind]] = "Curve name"
                                curve_name[fieldnames[ind + 1]] = f"{seg.note} Ch {ch}"
                                curve_type[fieldnames[ind]] = "Curve type"
                                curve_type[fieldnames[ind + 1]] = "Curve"
                                curve_ligand[fieldnames[ind]] = "Curve ligand"
                                curve_ligand[fieldnames[ind + 1]] = "N/A"
                                curve_conc[fieldnames[ind]] = "Curve concentration (M)"
                                curve_conc[fieldnames[ind + 1]] = f"{seg.conc[ch]}"
                                curve_target[fieldnames[ind]] = "Curve target"
                                curve_target[fieldnames[ind + 1]] = "N/A"
                                curve_desc[fieldnames[ind]] = "Curve description"
                                curve_desc[fieldnames[ind + 1]] = (
                                    f" Seg {seg.name} Ch {ch}"
                                )
                                curve_xy[fieldnames[ind]] = "X"
                                curve_xy[fieldnames[ind + 1]] = "Y"
                            writer.writerow(curve_num)
                            writer.writerow(curve_name)
                            writer.writerow(curve_type)
                            writer.writerow(curve_ligand)
                            writer.writerow(curve_conc)
                            writer.writerow(curve_target)
                            writer.writerow(curve_desc)
                            writer.writerow(curve_xy)

                            if (len(seg.seg_y[ch]) > 0) and (
                                len(seg.seg_y[ch]) == len(seg.seg_x[ch])
                            ):
                                end_time = 1000000
                                for seg in self.auto_segments:
                                    end_time = min(end_time, seg.seg_x[ch][-1])
                                temp_data = []
                                for seg in self.auto_segments:
                                    x = []
                                    y = []
                                    for j in range(len(seg.seg_x[ch])):
                                        if (seg.seg_x[ch][j] >= 0) and (
                                            seg.seg_x[ch][j] < end_time
                                        ):
                                            x.append(seg.seg_x[ch][j])
                                            y.append(seg.seg_y[ch][j])
                                    temp_data.append({"x": x, "y": y})
                                max_length = 0
                                for i in range(len(temp_data)):
                                    max_length = max(max_length, len(temp_data[i]["x"]))
                                for i in range(len(temp_data)):
                                    for j in range(max_length):
                                        if (j + 1) > len(temp_data[i]["x"]):
                                            temp_data[i]["x"].append(None)
                                            temp_data[i]["y"].append(None)
                                for row in range(max_length):
                                    data_dict = {}
                                    for i in range(len(temp_data)):
                                        data_dict[fieldnames[2 * i]] = temp_data[i][
                                            "x"
                                        ][row]
                                        data_dict[fieldnames[(2 * i) + 1]] = temp_data[
                                            i
                                        ]["y"][row]
                                    writer.writerow(data_dict)

                with Path(f"{export_dir}/AnalysisRawData.json").open("w") as json_file:
                    analysis_data: list[object] = [self.unit]
                    for seg in self.auto_segments:
                        seg_dict = {
                            "seg_id": seg.seg_id,
                            "name": seg.name,
                            "note": seg.note,
                            "ref_ch": seg.ref_ch,
                            "unit": seg.unit,
                            "conc": seg.conc,
                            "start": seg.start,
                            "start_index": seg.start_index,
                            "end": seg.end,
                            "end_index": seg.end_index,
                            "base_start": seg.base_start,
                            "base_end": seg.base_end,
                            "base_seg_x": {
                                ch: seg.base_seg_x[ch].tolist() for ch in CH_LIST
                            },
                            "base_seg_y": {
                                ch: seg.base_seg_y[ch].tolist() for ch in CH_LIST
                            },
                            "seg_x": {ch: seg.seg_x[ch].tolist() for ch in CH_LIST},
                            "seg_y": {ch: seg.seg_y[ch].tolist() for ch in CH_LIST},
                            "data_x": {ch: seg.data_x[ch].tolist() for ch in CH_LIST},
                            "data_y": {ch: seg.data_y[ch].tolist() for ch in CH_LIST},
                            "d_seg_x": {ch: seg.d_seg_x[ch].tolist() for ch in CH_LIST},
                            "d_seg_y": {ch: seg.d_seg_y[ch].tolist() for ch in CH_LIST},
                            "assoc_shift": seg.assoc_shift,
                            "assoc_start": seg.assoc_start,
                            "assoc_end": seg.assoc_end,
                            "dissoc_shift": seg.dissoc_shift,
                            "dissoc_start": seg.dissoc_start,
                            "dissoc_end": seg.dissoc_end,
                        }
                        analysis_data.append(seg_dict)
                    json.dump(analysis_data, json_file)

                show_message(msg="Analysis data exported", auto_close_time=5)
        except Exception as e:
            logger.exception(f"export analysis data error: {e}")
            self.export_error_signal.emit()

    def import_analysis_data(self: Self) -> None:
        """Import data for data analysis."""
        try:
            proceed = True
            if len(self.auto_segments) > 0 and not show_message(
                msg_type="Warning",
                msg="Import will overwrite data & erase current Analysis!"
                "\nProceed with new import?",
                yes_no=True,
            ):
                proceed = False
            if proceed:
                json_file = QFileDialog.getOpenFileName(
                    self,
                    "Open File",
                    "",
                    "JSON Files (*.json)",
                )[0]
                try:
                    file = Path(json_file).open()
                except Exception as e:
                    logger.debug(f"file open error: {e}")
                    logger.debug("File name error")
                    return

                self.clear_analysis_segments()
                analysis_data = json.load(file)
                self.unit = analysis_data[0]
                self.ui.stack_graph.setLabel(
                    axis="left",
                    text=f"Shift ({self.unit})",
                )
                self.ui.data_table.horizontalHeaderItem(1).setText(
                    f"Assoc.\nShift ({self.unit})",
                )
                self.ui.data_table.horizontalHeaderItem(4).setText(
                    f"Dissoc.\nShift ({self.unit})",
                )
                self.auto_segments = []
                dropdown = []
                for i in range(len(analysis_data) - 1):
                    self.auto_segments.append(
                        AnalysisSegment(
                            None,
                            json_load=True,
                            json_data=analysis_data[i + 1],
                        ),
                    )
                    j = max(0, (len(self.auto_segments) - 1)) % len(SEGMENT_COLORS)
                    plt = self.ui.stack_graph.plot(
                        pen=mkPen(SEGMENT_COLORS[j], width=2),
                        name=f"Segment {self.auto_segments[-1].name}",
                    )
                    self.assoc_plots.append(plt)
                    d_mrk = InfiniteLine(
                        pos=0,
                        pen=mkPen(
                            SEGMENT_COLORS[j],
                            width=2,
                            style=Qt.PenStyle.DotLine,
                        ),
                        movable=False,
                    )
                    self.ui.stack_graph.addItem(d_mrk)
                    self.dissoc_markers.append(d_mrk)
                    dropdown.append(f"Segment {self.auto_segments[-1].name}")
                self.ui.seg_select.clear()
                self.ui.seg_select.addItems(dropdown)
                self.ui.data_table.clearContents()
                self.update_table()
                self.analysis_SOI_view.reset_segment_graph(unit=self.unit)
                if len(self.auto_segments) > 0:
                    self.analysis_SOI_view.update_display(
                        self.auto_segments[0],
                        use_data=True,
                    )
                self._on_stack_channel_changed(ch=self.curr_ch, active=True)
        except Exception as e:
            logger.exception(f"import analysis data error: {e}")

    def en_assoc_cursors(self: Self) -> None:
        """Enable association cursors."""
        self.analysis_SOI_view.en_assoc_cursors(self.ui.assoc_cursors.isChecked())

    def en_dissoc_cursors(self: Self) -> None:
        """Enable dissociation cursors."""
        self.analysis_SOI_view.en_dissoc_cursors(self.ui.dissoc_cursors.isChecked())

    def on_analysis_table_edited(self: Self) -> None:
        """Handle edit of data anlysis table."""
        if not self.updating_table:
            try:
                start_times = dict.fromkeys(CH_LIST, 0.0)
                end_times = dict.fromkeys(CH_LIST, 0.0)
                assoc_start_times = dict.fromkeys(CH_LIST, 0.0)
                seg = self.auto_segments[self.ui.seg_select.currentIndex()]
                for i, ch in enumerate(CH_LIST):
                    if np.all(seg.data_y[ch] == np.nan):
                        pass
                    else:
                        seg.conc[ch] = float(self.ui.data_table.item(i, 0).text())
                        if (ch != "a") and (seg.conc[ch] == 0) and (seg.conc["a"] != 0):
                            seg.conc[ch] = deepcopy(seg.conc["a"])
                        start_times[ch] = float(self.ui.data_table.item(i, 7).text())
                        assoc_start_times[ch] = float(
                            self.ui.data_table.item(i, 2).text(),
                        )
                        seg.assoc_end[ch] = float(self.ui.data_table.item(i, 3).text())
                        seg.dissoc_start[ch] = float(
                            self.ui.data_table.item(i, 5).text(),
                        )
                        seg.dissoc_end[ch] = float(self.ui.data_table.item(i, 6).text())
                        if assoc_start_times[ch] != 0:
                            seg.assoc_start[ch] = 0
                            start_times[ch] += assoc_start_times[ch]
                            seg.assoc_end[ch] -= assoc_start_times[ch]
                            seg.dissoc_start[ch] -= assoc_start_times[ch]
                            seg.dissoc_end[ch] -= assoc_start_times[ch]
                        end_times[ch] = seg.base_end[ch]
                seg.adjust_segment(start_times, end_times)
                self.display_segment()
                self._on_stack_channel_changed(ch=self.curr_ch, active=True)
            except Exception as e:
                logger.debug(f"Error manually adjusting analysis segment{e}")

    def _show_kd_wizard(self: Self) -> None:
        if self._kd_dlg is None:
            seg_data_to_fit = []
            for i, seg in enumerate(self.auto_segments):
                if self.assoc_plots[i].isVisible():
                    seg_data_to_fit.append(seg)
            self._kd_dlg = KDWizardDialog(
                parent=self,
                seg_data=seg_data_to_fit,
                units=self.unit,
            )
            self._kd_dlg.closed.connect(self._on_kd_dlg_closed)
            self._kd_dlg.show()

    def _show_ka_kd_wizard(self: Self) -> None:
        if self._ka_kd_dlg is None:
            seg_data_to_fit = []
            for i, seg in enumerate(self.auto_segments):
                if self.assoc_plots[i].isVisible():
                    seg_data_to_fit.append(seg)
            self._ka_kd_dlg = KAKDWizardDialog(
                parent=self,
                seg_data=seg_data_to_fit,
                units=self.unit,
            )
            self._ka_kd_dlg.closed.connect(self._on_ka_kd_dlg_closed)
            self._ka_kd_dlg.show()

    def _on_kd_dlg_closed(self: Self) -> None:
        if self._kd_dlg is not None:
            try:
                # Update conc data from the Fitting Wizard dialog
                for ch in CH_LIST:
                    if len(self._kd_dlg.seg_names[ch]) == len(
                        self._kd_dlg.conc_data[ch],
                    ):
                        for i, c in enumerate(self._kd_dlg.conc_data[ch]):
                            name = self._kd_dlg.seg_names[ch][i]
                            for seg in self.auto_segments:
                                if seg.name == name:
                                    seg.conc[ch] = deepcopy(c)
                                    break
                self._kd_dlg = None
                self.update_table()
            except Exception as e:
                logger.debug(f"Error while saving KD conc in Analysis: {e}")
        else:
            logger.debug("Error while saving KD conc in Analysis: no dialog widget")

    def _on_ka_kd_dlg_closed(self: Self) -> None:
        # Update conc data from the Kinetic Wizard dialog
        if self._ka_kd_dlg is not None:
            for ch in CH_LIST:
                if len(self._ka_kd_dlg.seg_names[ch]) == len(
                    self._ka_kd_dlg.conc_data[ch],
                ):
                    for i, c in enumerate(self._ka_kd_dlg.conc_data[ch]):
                        name = self._ka_kd_dlg.seg_names[ch][i]
                        for seg in self.auto_segments:
                            if seg.name == name:
                                seg.conc[ch] = deepcopy(c)
                                break
            self._ka_kd_dlg = None
            self.update_table()
        else:
            logger.debug("Error while closing KA KD wizard: no dialog widget")

    def _on_stack_channel_changed(
        self: Self,
        ch: str,
        active: bool,  # noqa: FBT001
    ) -> None:
        if active:
            try:
                self.curr_ch = ch
                for i, seg in enumerate(self.auto_segments):
                    self.assoc_plots[i].setData(x=seg.data_x[ch], y=seg.data_y[ch])
                    self.dissoc_markers[i].setPos(seg.assoc_end[ch])
                self.ui.stack_graph.plotItem.setTitle(
                    f"Segments Channel {ch.upper()}",
                    color="w",
                )
                self.ui.stack_graph.plotItem.vb.autoRange(padding=0.1)
            except Exception as e:
                logger.debug(f"Error while changing stack ch in Analysis: {e}")


class AnalysisSegment:
    """Segment of data for data anlysis."""

    def __init__(
        self: Self,
        base_segment: Segment | None,
        *,
        json_load: bool = False,
        json_data: dict | None = None,  # type: ignore[type-arg]
    ) -> None:
        """Make new segment."""
        try:
            if json_load and json_data is not None:
                self.seg_id = json_data["seg_id"]
                self.name = json_data["name"]
                self.note = json_data["note"]
                self.ref_ch = json_data["ref_ch"]
                self.unit = json_data["unit"]
                self.conc = json_data["conc"]
                self.start = json_data["start"]
                self.start_index = json_data["start_index"]
                self.end = json_data["end"]
                self.end_index = json_data["end_index"]
                self.base_start = json_data["base_start"]
                self.base_end = json_data["base_end"]
                self.base_seg_x = {
                    ch: np.asarray(json_data["base_seg_x"][ch]) for ch in CH_LIST
                }
                self.base_seg_y = {
                    ch: np.asarray(json_data["base_seg_y"][ch]) for ch in CH_LIST
                }
                self.seg_x = {ch: np.asarray(json_data["seg_x"][ch]) for ch in CH_LIST}
                self.seg_y = {ch: np.asarray(json_data["seg_y"][ch]) for ch in CH_LIST}
                self.data_x = {
                    ch: np.asarray(json_data["data_x"][ch]) for ch in CH_LIST
                }
                self.data_y = {
                    ch: np.asarray(json_data["data_y"][ch]) for ch in CH_LIST
                }
                self.d_seg_x = {
                    ch: np.asarray(json_data["d_seg_x"][ch]) for ch in CH_LIST
                }
                self.d_seg_y = {
                    ch: np.asarray(json_data["d_seg_y"][ch]) for ch in CH_LIST
                }
                self.assoc_start = json_data["assoc_start"]
                self.assoc_end = json_data["assoc_end"]
                self.assoc_shift = json_data["assoc_shift"]
                self.dissoc_start = json_data["dissoc_start"]
                self.dissoc_end = json_data["dissoc_end"]
                self.dissoc_shift = json_data["dissoc_shift"]

            elif base_segment:
                self.seg_id = base_segment.seg_id
                self.ref_ch = base_segment.ref_ch
                self.unit = base_segment.unit
                self.base_seg_x = base_segment.seg_x
                self.base_seg_y = base_segment.seg_y
                self.seg_x = deepcopy(base_segment.seg_x)
                self.seg_y = deepcopy(base_segment.seg_y)
                self.data_x = deepcopy(base_segment.seg_x)
                self.data_y = deepcopy(base_segment.seg_y)
                self.name = base_segment.name
                self.note = base_segment.note
                self.assoc_shift = base_segment.shift
                self.base_start = dict.fromkeys(CH_LIST, base_segment.start)
                self.base_end = dict.fromkeys(CH_LIST, base_segment.end)
                self.start = {ch: deepcopy(base_segment.start) for ch in CH_LIST}
                self.end = {ch: deepcopy(base_segment.end) for ch in CH_LIST}
                self.dissoc_start = {
                    ch: self.base_end[ch] - self.base_start[ch] for ch in CH_LIST
                }
                self.dissoc_end = {
                    ch: self.base_end[ch] - self.base_start[ch] for ch in CH_LIST
                }
                self.d_seg_x = {ch: np.ndarray([]) for ch in CH_LIST}
                self.d_seg_y = {ch: np.ndarray([]) for ch in CH_LIST}
                self.dissoc_shift = dict.fromkeys(CH_LIST, 0)
                self.start_index = dict.fromkeys(CH_LIST, 0)
                self.end_index = {ch: len(self.seg_x[ch]) - 1 for ch in CH_LIST}
                self.conc = dict.fromkeys(CH_LIST, 0)
                self.assoc_start = dict.fromkeys(CH_LIST, 0)
                self.assoc_end = dict.fromkeys(CH_LIST, 1)

        except Exception as e:
            logger.exception(f"Error while loading base segment: {e}")

    def align_start(self: Self, new_index: dict[str, int]) -> None:
        """Align segment start."""
        try:
            if len(new_index) == len(CH_LIST):
                for ch in CH_LIST:
                    if (
                        np.any(self.base_seg_y[ch] != np.nan)
                        and np.any(self.base_seg_y[ch] != 0)
                        and new_index[ch] > 0
                    ):
                        time_shift = (
                            self.data_x[ch][new_index[ch]]
                            - self.data_x[ch][self.start_index[ch]]
                        )
                        self.start_index[ch] += new_index[ch]
                        self.start[ch] += time_shift
                        self.data_x[ch] -= self.data_x[ch][self.start_index[ch]]
                        self.data_y[ch] -= self.data_y[ch][self.start_index[ch]]
                        i = 0
                        while i < len(self.data_x[ch]):
                            if self.data_x[ch][i] >= 0:
                                break
                            i += 1
                        self.seg_x[ch] = deepcopy(self.data_x[ch][i:])
                        self.seg_y[ch] = deepcopy(self.data_y[ch][i:])
                        self.assoc_start[ch] = 0
                        self.assoc_end[ch] = deepcopy(
                            self.seg_x[ch][int(len(self.seg_x[ch]) * 0.4)],
                        )
                        self.dissoc_start[ch] = deepcopy(
                            self.seg_x[ch][int(len(self.seg_x[ch]) * 0.6)],
                        )
                        self.dissoc_end[ch] = deepcopy(self.seg_x[ch][-1])
        except Exception as e:
            logger.exception(f"Error while aligning analysis segment: {e}")

    def adjust_segment(
        self: Self,
        new_start: dict[str, int],
        new_end: dict[str, int],
        single_ch: str | None = None,
    ) -> None:
        """Adjust a segment."""
        try:
            ch_list = CH_LIST if single_ch is None else [single_ch]
            for ch in ch_list:
                if not (
                    np.all(self.base_seg_y[ch] == np.nan)
                    or np.all(self.base_seg_y[ch] == 0)
                ):
                    i = 0
                    if new_start[ch] > self.base_end[ch] - 2:
                        new_start[ch] = self.base_end[ch] - 2
                    elif new_start[ch] < self.base_start[ch]:
                        new_start[ch] = self.base_start[ch]
                    if new_end[ch] > new_start[ch]:
                        while i < len(self.base_seg_x[ch] - 2):
                            if (
                                self.base_seg_x[ch][i] + self.base_start[ch]
                            ) < new_start[ch]:
                                i += 1
                            else:
                                self.start_index[ch] = i
                                self.start[ch] = new_start[ch]
                                break
                        while i < len(self.base_seg_x[ch]):
                            if (self.base_seg_x[ch][i] + self.base_start[ch]) < new_end[
                                ch
                            ]:
                                i += 1
                            else:
                                self.end_index[ch] = i
                                self.end[ch] = new_end[ch]
                                break
                        self.data_x[ch] = deepcopy(
                            self.base_seg_x[ch][: self.end_index[ch]]
                            - self.base_seg_x[ch][self.start_index[ch]],
                        )
                        self.data_y[ch] = deepcopy(
                            self.base_seg_y[ch][: self.end_index[ch]]
                            - self.base_seg_y[ch][self.start_index[ch]],
                        )
                        if len(self.data_x[ch]) > 0:
                            i = 0
                            while i < (len(self.data_x[ch]) - 1):
                                if self.data_x[ch][i] >= 0:
                                    break
                                i += 1
                                if self.assoc_start[ch] < self.data_x[ch][i]:
                                    self.assoc_start[ch] = self.data_x[ch][i]
                                    if self.assoc_end[ch] < self.assoc_start[ch]:
                                        self.assoc_end[ch] = self.data_x[ch][i + 1]
                                    self.dissoc_start[ch] = max(
                                        self.dissoc_start[ch],
                                        self.assoc_end[ch],
                                    )
                                    self.dissoc_end[ch] = max(
                                        self.dissoc_end[ch],
                                        self.dissoc_start[ch],
                                    )
                            j = i + 1
                            while j < len(self.data_x[ch]):
                                if (
                                    self.data_x[ch][j]
                                    > self.data_x[ch][i] + self.assoc_end[ch]
                                ):
                                    break
                                j += 1
                            k = deepcopy(j)
                            l = deepcopy(j)  # noqa: E741
                            if j == len(self.data_x[ch]):
                                self.assoc_end[ch] = self.data_x[ch][-1]
                                self.dissoc_start[ch] = self.data_x[ch][-1]
                                self.dissoc_end[ch] = self.data_x[ch][-1]
                            else:
                                while k < len(self.data_x[ch]):
                                    if (
                                        self.data_x[ch][k]
                                        > self.data_x[ch][i] + self.dissoc_start[ch]
                                    ):
                                        break
                                    k += 1
                                l = deepcopy(k)  # noqa: E741
                                if k == len(self.data_x[ch]):
                                    self.dissoc_start[ch] = self.data_x[ch][-1]
                                    self.dissoc_end[ch] = self.data_x[ch][-1]
                                else:
                                    while l < len(self.data_x[ch]):
                                        if (
                                            self.data_x[ch][l]
                                            > self.data_x[ch][i] + self.dissoc_end[ch]
                                        ):
                                            break
                                        l += 1  # noqa: E741
                                    if l == len(self.data_x[ch]):
                                        self.dissoc_end[ch] = self.data_x[ch][-1]
                            self.seg_x[ch] = deepcopy(self.data_x[ch][i:j])
                            self.seg_y[ch] = deepcopy(self.data_y[ch][i:j])
                            self.d_seg_x[ch] = self.data_x[ch][k:l]
                            self.d_seg_y[ch] = self.data_y[ch][k:l]
                            if len(self.seg_y[ch]) > 0:
                                self.assoc_shift[ch] = self.seg_y[ch][-1]
                                if len(self.d_seg_y[ch]) > 0:
                                    self.dissoc_shift[ch] = (
                                        self.d_seg_y[ch][-1] - self.d_seg_y[ch][0]
                                    )
                                else:
                                    self.dissoc_shift[ch] = 0
                                    self.d_seg_x[ch] = np.ndarray([0])
                                    self.d_seg_y[ch] = np.ndarray([0])
                            else:
                                self.assoc_shift[ch] = 0
        except Exception as e:
            logger.debug(f"Error while adjusting Analysis segment: {e}")
