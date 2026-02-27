"""TraceDrawer Export Dialog.

Receives cycle data + raw time-series from the Edits tab, lets the user
select cycles, configure time windows / baseline / reference subtraction,
preview overlaid traces, and export a .zip with one .txt per cycle.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path
from typing import Any

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from affilabs.ui_styles import Colors, Fonts
from affilabs.utils.logger import logger
from affilabs.services.tracedrawer_exporter import (
    build_trace,
    export_zip,
    interpolate_traces,
)

# Channel colors matching the live sensorgram
_CH_COLORS = {
    "a": "#2196F3",  # blue
    "b": "#FF9800",  # orange
    "c": "#4CAF50",  # green
    "d": "#E91E63",  # pink
}

# Distinct trace colors for overlaid binding curves
_TRACE_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#17becf",
    "#bcbd22", "#7f7f7f",
]


class TraceDrawerExportDialog(QDialog):
    """Dialog for building and exporting TraceDrawer .zip (one .txt per cycle).

    Receives data from the Edits tab — no file loading needed.
    """

    exported = Signal(Path)  # emitted after successful export

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        cycles_data: list[dict[str, Any]] | None = None,
        raw_data_rows: list[dict[str, Any]] | None = None,
        alignment: dict[int, dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("TraceDrawer Export")
        self.setMinimumSize(880, 640)
        self.resize(960, 700)
        self.setStyleSheet(f"QDialog {{ background: {Colors.BACKGROUND_LIGHT}; }}")

        # Data from Edits tab
        self._cycles_data: list[dict[str, Any]] = cycles_data or []
        self._raw_data_rows: list[dict[str, Any]] = raw_data_rows or []
        self._alignment: dict[int, dict[str, Any]] = alignment or {}

        self._build_ui()

        # Populate immediately from passed data
        if self._cycles_data:
            self._populate_cycles_table()

    # ── UI Construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        # Main body: left config + right preview
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: #E0E0E0; width: 1px; }")
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_preview_panel())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter, stretch=1)

        root.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(56)
        bar.setStyleSheet(
            f"QFrame {{ background: {Colors.BACKGROUND_WHITE}; "
            f"border-bottom: 1px solid {Colors.OVERLAY_LIGHT_10}; }}"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)

        title = QLabel("TraceDrawer Export")
        title.setStyleSheet(
            f"font-family: {Fonts.DISPLAY}; font-size: 16px; "
            f"font-weight: {Fonts.WEIGHT_SEMIBOLD}; color: {Colors.PRIMARY_TEXT};"
        )
        lay.addWidget(title)
        lay.addStretch()

        self._file_label = QLabel(
            f"{len(self._cycles_data)} cycle(s) loaded from Edits"
            if self._cycles_data else "No cycle data"
        )
        self._file_label.setStyleSheet(
            f"font-family: {Fonts.SYSTEM}; font-size: 12px; color: {Colors.SECONDARY_TEXT};"
        )
        lay.addWidget(self._file_label)

        return bar

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(320)
        panel.setMaximumWidth(400)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 12, 8, 12)
        lay.setSpacing(12)

        # ── Channel Selector ──
        ch_group = self._titled_group("Channel")
        ch_lay = QHBoxLayout()
        ch_lay.setSpacing(6)
        self._ch_radios: dict[str, QRadioButton] = {}
        for ch in ("A", "B", "C", "D"):
            rb = QRadioButton(ch)
            rb.setStyleSheet(self._radio_style(ch))
            rb.toggled.connect(self._on_settings_changed)
            self._ch_radios[ch] = rb
            ch_lay.addWidget(rb)
        self._ch_radios["A"].setChecked(True)
        ch_group.layout().addLayout(ch_lay)

        # Reference subtraction
        ref_lay = QHBoxLayout()
        self._ref_check = QCheckBox("Subtract reference:")
        self._ref_check.setStyleSheet(f"font-size: 12px; color: {Colors.PRIMARY_TEXT};")
        self._ref_check.toggled.connect(self._on_settings_changed)
        ref_lay.addWidget(self._ref_check)
        self._ref_combo = QComboBox()
        self._ref_combo.addItems(["A", "B", "C", "D"])
        self._ref_combo.setCurrentText("D")
        self._ref_combo.setFixedWidth(60)
        self._ref_combo.setEnabled(False)
        self._ref_combo.currentTextChanged.connect(self._on_settings_changed)
        self._ref_check.toggled.connect(self._ref_combo.setEnabled)
        ref_lay.addWidget(self._ref_combo)
        ref_lay.addStretch()
        ch_group.layout().addLayout(ref_lay)
        lay.addWidget(ch_group)

        # ── Binding Cycles Table ──
        cycles_group = self._titled_group("Binding Cycles")
        self._cycles_table = QTableWidget()
        self._cycles_table.setColumnCount(4)
        self._cycles_table.setHorizontalHeaderLabels(["✓", "Cycle", "Type", "Conc."])
        self._cycles_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._cycles_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._cycles_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._cycles_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._cycles_table.setColumnWidth(0, 30)
        self._cycles_table.setColumnWidth(1, 50)
        self._cycles_table.verticalHeader().setVisible(False)
        self._cycles_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._cycles_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._cycles_table.setStyleSheet(self._table_style())
        self._cycles_table.setMinimumHeight(120)
        self._cycles_table.setMaximumHeight(220)
        cycles_group.layout().addWidget(self._cycles_table)

        # Select all / none
        sel_lay = QHBoxLayout()
        all_btn = QPushButton("Select All")
        all_btn.setFixedHeight(24)
        all_btn.setStyleSheet(self._small_button_style())
        all_btn.clicked.connect(lambda: self._toggle_all_cycles(True))
        sel_lay.addWidget(all_btn)
        none_btn = QPushButton("Select None")
        none_btn.setFixedHeight(24)
        none_btn.setStyleSheet(self._small_button_style())
        none_btn.clicked.connect(lambda: self._toggle_all_cycles(False))
        sel_lay.addWidget(none_btn)
        sel_lay.addStretch()
        cycles_group.layout().addLayout(sel_lay)
        lay.addWidget(cycles_group)

        # ── Time Window ──
        tw_group = self._titled_group("Time Window")
        tw_grid = QGridLayout()
        tw_grid.setHorizontalSpacing(8)
        tw_grid.setVerticalSpacing(6)

        tw_grid.addWidget(self._param_label("Pre-injection"), 0, 0)
        self._pre_inject_spin = self._time_spin(30.0, 0.0, 600.0)
        tw_grid.addWidget(self._pre_inject_spin, 0, 1)
        tw_grid.addWidget(QLabel("s"), 0, 2)

        tw_grid.addWidget(self._param_label("Association"), 1, 0)
        self._assoc_spin = self._time_spin(300.0, 10.0, 7200.0)
        tw_grid.addWidget(self._assoc_spin, 1, 1)
        tw_grid.addWidget(QLabel("s"), 1, 2)

        tw_grid.addWidget(self._param_label("Dissociation"), 2, 0)
        self._dissoc_spin = self._time_spin(300.0, 0.0, 7200.0)
        tw_grid.addWidget(self._dissoc_spin, 2, 1)
        tw_grid.addWidget(QLabel("s"), 2, 2)

        tw_group.layout().addLayout(tw_grid)
        lay.addWidget(tw_group)

        # ── Baseline & Output ──
        bl_group = self._titled_group("Baseline & Output")
        bl_grid = QGridLayout()
        bl_grid.setHorizontalSpacing(8)
        bl_grid.setVerticalSpacing(6)

        bl_grid.addWidget(self._param_label("Baseline window"), 0, 0)
        self._baseline_spin = self._time_spin(10.0, 1.0, 120.0)
        bl_grid.addWidget(self._baseline_spin, 0, 1)
        bl_grid.addWidget(QLabel("s"), 0, 2)

        bl_grid.addWidget(self._param_label("Interpolation step"), 1, 0)
        self._interp_spin = QDoubleSpinBox()
        self._interp_spin.setRange(0.1, 10.0)
        self._interp_spin.setValue(0.5)
        self._interp_spin.setSingleStep(0.1)
        self._interp_spin.setDecimals(1)
        self._interp_spin.setSuffix(" s")
        self._interp_spin.setFixedWidth(90)
        bl_grid.addWidget(self._interp_spin, 1, 1)

        bl_group.layout().addLayout(bl_grid)
        lay.addWidget(bl_group)

        lay.addStretch()
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(8, 12, 16, 12)
        lay.setSpacing(8)

        # Preview header
        hdr = QHBoxLayout()
        hdr.addWidget(self._section_label("Preview"))
        self._preview_info = QLabel("")
        self._preview_info.setStyleSheet(
            f"font-size: 11px; color: {Colors.SECONDARY_TEXT};"
        )
        hdr.addWidget(self._preview_info)
        hdr.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedHeight(26)
        refresh_btn.setStyleSheet(self._small_button_style())
        refresh_btn.clicked.connect(self._update_preview)
        hdr.addWidget(refresh_btn)
        lay.addLayout(hdr)

        # pyqtgraph plot
        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setBackground("#FFFFFF")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self._plot_widget.setLabel("bottom", "Time", units="s")
        self._plot_widget.setLabel("left", "Δ Resonance", units="nm")
        self._plot_widget.getAxis("bottom").setStyle(tickFont=QFont("Segoe UI", 9))
        self._plot_widget.getAxis("left").setStyle(tickFont=QFont("Segoe UI", 9))
        # Injection line
        self._inject_line = pg.InfiniteLine(
            pos=0, angle=90,
            pen=pg.mkPen("#FF3B30", width=1, style=Qt.PenStyle.DashLine),
        )
        self._plot_widget.addItem(self._inject_line)
        lay.addWidget(self._plot_widget, stretch=1)

        # Legend area (manual, below graph)
        self._legend_label = QLabel("")
        self._legend_label.setWordWrap(True)
        self._legend_label.setStyleSheet(
            f"font-size: 11px; color: {Colors.SECONDARY_TEXT}; padding: 4px;"
        )
        lay.addWidget(self._legend_label)

        return panel

    def _build_footer(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(52)
        bar.setStyleSheet(
            f"QFrame {{ background: {Colors.BACKGROUND_WHITE}; "
            f"border-top: 1px solid {Colors.OVERLAY_LIGHT_10}; }}"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)

        self._summary_label = QLabel(
            f"{len(self._cycles_data)} cycle(s) from Edits" if self._cycles_data
            else "No cycle data — load cycles in Edits first"
        )
        self._summary_label.setStyleSheet(
            f"font-size: 12px; color: {Colors.SECONDARY_TEXT};"
        )
        lay.addWidget(self._summary_label)
        lay.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(self._button_style(accent=False))
        cancel_btn.clicked.connect(self.reject)
        lay.addWidget(cancel_btn)

        self._export_btn = QPushButton("Export .zip")
        self._export_btn.setFixedSize(110, 32)
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.setStyleSheet(self._button_style(accent=True))
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export_clicked)
        lay.addWidget(self._export_btn)

        return bar

    # ── Actions ──────────────────────────────────────────────────────

    def _populate_cycles_table(self) -> None:
        """Fill the cycles table from the passed cycles_data list[dict]."""
        table = self._cycles_table
        table.setRowCount(0)

        if not self._cycles_data:
            self._summary_label.setText("No cycles loaded")
            return

        table.setRowCount(len(self._cycles_data))
        for i, cycle in enumerate(self._cycles_data):
            # Checkbox
            cb = QCheckBox()
            cb.setChecked(True)
            cb.stateChanged.connect(self._on_settings_changed)
            w = QWidget()
            cb_lay = QHBoxLayout(w)
            cb_lay.setContentsMargins(0, 0, 0, 0)
            cb_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb_lay.addWidget(cb)
            table.setCellWidget(i, 0, w)

            # Cycle number
            num = cycle.get("cycle_num", cycle.get("cycle_id", i + 1))
            item = QTableWidgetItem(str(num))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 1, item)

            # Type
            ctype = str(cycle.get("type", ""))
            if ctype.lower() == "nan":
                ctype = ""
            table.setItem(i, 2, QTableWidgetItem(ctype))

            # Concentration
            conc = self._get_display_concentration(cycle)
            item = QTableWidgetItem(conc)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 3, item)

        self._summary_label.setText(f"{len(self._cycles_data)} cycle(s) loaded")
        self._update_preview()

    def _get_display_concentration(self, cycle: dict) -> str:
        """Format concentration for table display."""
        ch = self._selected_channel()
        concs = cycle.get("concentrations")
        val = None

        if isinstance(concs, dict) and ch.upper() in concs:
            val = concs[ch.upper()]
        elif isinstance(concs, str):
            try:
                parsed = ast.literal_eval(concs)
                if isinstance(parsed, dict) and ch.upper() in parsed:
                    val = parsed[ch.upper()]
            except (ValueError, SyntaxError):
                pass

        if val is None:
            cv = cycle.get("concentration_value")
            if cv is not None and not (isinstance(cv, float) and math.isnan(cv)):
                val = cv

        if val is None or (isinstance(val, str) and val.strip() == ""):
            return "—"

        units = cycle.get("concentration_units", cycle.get("units", "nM"))
        if units is None or (isinstance(units, float) and math.isnan(units)):
            units = "nM"

        val = float(val)
        if abs(val) < 10:
            return f"{val:.1f} {units}"
        if val == int(val):
            return f"{int(val)} {units}"
        return f"{val} {units}"

    def _selected_channel(self) -> str:
        for ch, rb in self._ch_radios.items():
            if rb.isChecked():
                return ch.lower()
        return "a"

    def _selected_cycle_indices(self) -> list[int]:
        """Return table row indices of checked cycles."""
        indices = []
        for i in range(self._cycles_table.rowCount()):
            w = self._cycles_table.cellWidget(i, 0)
            if w:
                cb = w.findChild(QCheckBox)
                if cb and cb.isChecked():
                    indices.append(i)
        return indices

    def _toggle_all_cycles(self, state: bool) -> None:
        for i in range(self._cycles_table.rowCount()):
            w = self._cycles_table.cellWidget(i, 0)
            if w:
                cb = w.findChild(QCheckBox)
                if cb:
                    cb.setChecked(state)

    def _on_settings_changed(self) -> None:
        """Debounced preview update on any setting change."""
        # Direct update — fast enough for the data sizes involved
        self._update_preview()

    def _build_traces(self) -> list[dict[str, Any]]:
        """Build all selected traces with current settings.

        Returns a flat list of trace dicts (one per selected-cycle × channel).
        """
        if not self._cycles_data or not self._raw_data_rows:
            return []

        channel = self._selected_channel()

        ref_channel: str | None = None
        if self._ref_check.isChecked():
            ref_channel = self._ref_combo.currentText().lower()
            if ref_channel == channel:
                ref_channel = None

        indices = self._selected_cycle_indices()
        if not indices:
            return []

        traces: list[dict[str, Any]] = []
        for idx in indices:
            if idx >= len(self._cycles_data):
                continue
            cycle = self._cycles_data[idx]
            align = self._alignment.get(idx)

            tr = build_trace(
                raw_data_rows=self._raw_data_rows,
                channel=channel,
                cycle=cycle,
                alignment=align,
                ref_channel=ref_channel,
                pre_inject_s=self._pre_inject_spin.value(),
                assoc_s=self._assoc_spin.value(),
                dissoc_s=self._dissoc_spin.value(),
                baseline_window_s=self._baseline_spin.value(),
            )
            if tr is not None:
                traces.append(tr)

        # Sort by concentration ascending
        traces.sort(key=lambda t: (t["conc"] if t["conc"] is not None else float("inf")))
        return traces

    def _build_per_cycle_traces(self) -> list[list[dict[str, Any]]]:
        """Build per-cycle trace groups for zip export.

        Returns outer=cycle list, inner=per-channel traces for that cycle.
        Currently one channel per cycle (user selects the channel), but the
        structure supports multi-channel in future.
        """
        traces = self._build_traces()
        # Group: one list per trace (each trace = one cycle × one channel)
        return [[tr] for tr in traces]

    def _update_preview(self) -> None:
        """Rebuild the preview graph."""
        if not hasattr(self, '_plot_widget'):
            return
        self._plot_widget.clear()
        self._plot_widget.addItem(self._inject_line)
        self._legend_label.setText("")

        traces = self._build_traces()
        if not traces:
            self._preview_info.setText("")
            self._export_btn.setEnabled(False)
            if self._cycles_data:
                self._summary_label.setText("No traces to preview — check cycle selection")
            return

        # Interpolate for display
        step = self._interp_spin.value()
        common_time, values_list, labels = interpolate_traces(traces, step_s=step)

        # Plot each trace
        legend_parts = []
        for i, (vals, label) in enumerate(zip(values_list, labels)):
            color = _TRACE_PALETTE[i % len(_TRACE_PALETTE)]
            pen = pg.mkPen(color, width=2)
            self._plot_widget.plot(common_time, vals, pen=pen, name=label)
            legend_parts.append(
                f'<span style="color:{color}; font-weight:600;">●</span> {label}'
            )

        self._legend_label.setText("  &nbsp;&nbsp;".join(legend_parts))
        self._preview_info.setText(
            f"{len(traces)} trace(s)  ·  {len(common_time)} pts  ·  "
            f"Δt = {step} s"
        )
        self._summary_label.setText(
            f"Ready: {len(traces)} cycle(s), {len(common_time)} rows"
        )
        self._export_btn.setEnabled(True)

    def _on_export_clicked(self) -> None:
        """Export a .zip with one .txt per cycle."""
        per_cycle = self._build_per_cycle_traces()
        if not per_cycle:
            QMessageBox.warning(self, "No Data", "No traces to export.")
            return

        default_name = "tracedrawer_export.zip"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export TraceDrawer Zip",
            default_name,
            "Zip Files (*.zip);;All Files (*)",
        )
        if not path:
            return

        output = Path(path)
        step = self._interp_spin.value()

        try:
            export_zip(per_cycle, output, step_s=step, precision=4)
        except Exception as e:
            logger.error(f"TraceDrawer export failed: {e}")
            QMessageBox.warning(self, "Export Error", f"Export failed:\n{e}")
            return

        n_cycles = sum(1 for g in per_cycle if g)
        self._summary_label.setText(f"Exported → {output.name}")
        self.exported.emit(output)

        QMessageBox.information(
            self, "Export Complete",
            f"TraceDrawer zip saved:\n{output}\n\n"
            f"{n_cycles} cycle(s) exported",
        )

    # ── Widget Factories ─────────────────────────────────────────────

    def _titled_group(self, title: str) -> QGroupBox:
        box = QGroupBox(title)
        box.setStyleSheet(
            f"QGroupBox {{ "
            f"  font-family: {Fonts.SYSTEM}; font-size: 12px; "
            f"  font-weight: {Fonts.WEIGHT_SEMIBOLD}; color: {Colors.PRIMARY_TEXT}; "
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10}; "
            f"  border-radius: 8px; margin-top: 10px; padding-top: 14px; "
            f"  background: {Colors.BACKGROUND_WHITE}; "
            f"}}"
            f"QGroupBox::title {{ "
            f"  subcontrol-origin: margin; left: 12px; padding: 0 4px; "
            f"}}"
        )
        box.setLayout(QVBoxLayout())
        box.layout().setContentsMargins(10, 6, 10, 10)
        box.layout().setSpacing(6)
        return box

    def _param_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-family: {Fonts.SYSTEM}; font-size: 12px; color: {Colors.PRIMARY_TEXT};"
        )
        return lbl

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-family: {Fonts.DISPLAY}; font-size: 14px; "
            f"font-weight: {Fonts.WEIGHT_SEMIBOLD}; color: {Colors.PRIMARY_TEXT};"
        )
        return lbl

    def _time_spin(self, default: float, min_v: float, max_v: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(min_v, max_v)
        spin.setValue(default)
        spin.setSingleStep(5.0)
        spin.setDecimals(0)
        spin.setFixedWidth(90)
        spin.valueChanged.connect(self._on_settings_changed)
        return spin

    # ── Styles ───────────────────────────────────────────────────────

    @staticmethod
    def _button_style(accent: bool = False) -> str:
        if accent:
            return (
                f"QPushButton {{ "
                f"  background: {Colors.BUTTON_PRIMARY}; color: #FFFFFF; "
                f"  border: none; border-radius: 6px; "
                f"  font-family: {Fonts.SYSTEM}; font-size: 13px; "
                f"  font-weight: {Fonts.WEIGHT_SEMIBOLD}; padding: 6px 16px; "
                f"}}"
                f"QPushButton:hover {{ background: {Colors.BUTTON_PRIMARY_HOVER}; }}"
                f"QPushButton:pressed {{ background: {Colors.BUTTON_PRIMARY_PRESSED}; }}"
                f"QPushButton:disabled {{ background: {Colors.BUTTON_DISABLED}; color: #AAA; }}"
            )
        return (
            f"QPushButton {{ "
            f"  background: {Colors.BACKGROUND_WHITE}; color: {Colors.PRIMARY_TEXT}; "
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_20}; border-radius: 6px; "
            f"  font-family: {Fonts.SYSTEM}; font-size: 13px; padding: 6px 14px; "
            f"}}"
            f"QPushButton:hover {{ background: {Colors.BACKGROUND_LIGHT}; }}"
        )

    @staticmethod
    def _small_button_style() -> str:
        return (
            f"QPushButton {{ "
            f"  background: transparent; color: {Colors.INFO}; border: none; "
            f"  font-size: 11px; font-weight: {Fonts.WEIGHT_MEDIUM}; "
            f"  padding: 2px 8px; "
            f"}}"
            f"QPushButton:hover {{ color: {Colors.BUTTON_PRIMARY}; }}"
        )

    @staticmethod
    def _table_style() -> str:
        return (
            f"QTableWidget {{ "
            f"  background: {Colors.BACKGROUND_WHITE}; "
            f"  border: 1px solid {Colors.OVERLAY_LIGHT_10}; border-radius: 4px; "
            f"  font-size: 12px; gridline-color: {Colors.OVERLAY_LIGHT_6}; "
            f"}}"
            f"QHeaderView::section {{ "
            f"  background: {Colors.BACKGROUND_LIGHT}; border: none; "
            f"  border-bottom: 1px solid {Colors.OVERLAY_LIGHT_10}; "
            f"  font-size: 11px; font-weight: {Fonts.WEIGHT_SEMIBOLD}; "
            f"  padding: 4px; "
            f"}}"
        )

    @staticmethod
    def _radio_style(ch: str) -> str:
        color = _CH_COLORS.get(ch.lower(), Colors.PRIMARY_TEXT)
        return (
            f"QRadioButton {{ font-size: 13px; font-weight: 600; color: {color}; }}"
            f"QRadioButton::indicator {{ width: 14px; height: 14px; }}"
        )
