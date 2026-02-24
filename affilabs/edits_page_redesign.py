"""Standalone Edits Page Redesign - Test Implementation

NEW MASTER-DETAIL LAYOUT:
=========================
Top 30%: Full Timeline Navigator
  - Shows entire experiment with all cycles
  - Cycle boundary markers (vertical lines + labels)
  - Dual cursors for region selection
  - Familiar pattern from Live tab

Middle 50%: Active Selection View
  - Shows data between cursors
  - Baseline cursors (green/blue) for delta SPR calculation
  - All transformations applied here

Bottom 20%: Cycle Table + Editing Tools
  - Horizontal split layout
  - Minimal controls, maximum space for graphs

REMOVED:
========
- 3 reference graphs at bottom (unused, confusing)
- Redundant segment management UI

This is a test page. If it works well, we'll replace _create_edits_content()
in affilabs_core_ui.py with this implementation.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QSlider, QFrame, QFileDialog
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from affilabs.utils.resource_path import get_affilabs_resource


class EditsPageRedesign(QMainWindow):
    """Redesigned Edits page with master-detail timeline navigation."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Edits Page Redesign - Test")
        self.setGeometry(100, 100, 1400, 900)

        # Data storage
        self.raw_data_rows = []
        self.cycles_data = []
        self.all_cycle_data = {}  # {cycle_idx: {ch: {'time': [], 'wavelength': []}}}

        # Graph state
        self.timeline_cursors = {'left': None, 'right': None}
        self.baseline_cursors = {'baseline': None, 'association': None}
        self.cycle_markers = []  # InfiniteLines for cycle boundaries
        self.cycle_labels = []  # TextItems for cycle names

        # UI Setup
        self._init_ui()

    def _init_ui(self):
        """Initialize the layout with table on left, graphs on right."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Main horizontal split: Table LEFT | Graphs RIGHT
        main_splitter = QSplitter(Qt.Horizontal)

        # LEFT: Cycle table (20% width)
        table_widget = self._create_table_panel()
        main_splitter.addWidget(table_widget)

        # RIGHT: Graphs (80% width)
        graphs_splitter = QSplitter(Qt.Vertical)

        # TOP: Full Timeline Navigator (35%)
        timeline_widget = self._create_timeline_navigator()
        graphs_splitter.addWidget(timeline_widget)

        # MIDDLE: Active Selection View (50%)
        selection_widget = self._create_active_selection_view()
        graphs_splitter.addWidget(selection_widget)

        # BOTTOM: Editing Tools (15%)
        tools_widget = self._create_tools_panel()
        graphs_splitter.addWidget(tools_widget)

        # Set vertical proportions: 35:50:15
        graphs_splitter.setStretchFactor(0, 35)
        graphs_splitter.setStretchFactor(1, 50)
        graphs_splitter.setStretchFactor(2, 15)

        main_splitter.addWidget(graphs_splitter)

        # Set horizontal proportions: 20:80 (table:graphs)
        main_splitter.setStretchFactor(0, 20)
        main_splitter.setStretchFactor(1, 80)

        main_layout.addWidget(main_splitter)

    def _create_timeline_navigator(self):
        """Top panel: Full experiment timeline with cycle markers."""
        container = QFrame()
        container.setStyleSheet("QFrame { background: white; border-radius: 8px; }")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel("Full Timeline Navigator")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1D1D1F;")
        header.addWidget(title)
        header.addStretch()

        layout.addLayout(header)

        # Timeline graph
        self.timeline_graph = pg.PlotWidget()
        self.timeline_graph.setBackground('w')
        self.timeline_graph.setLabel('left', 'Response (RU)', color='#1D1D1F')
        self.timeline_graph.setLabel('bottom', 'Time (s)', color='#1D1D1F')
        self.timeline_graph.showGrid(x=True, y=True, alpha=0.2)

        # Create curves for 4 channels
        colors = [(0, 0, 0), (255, 0, 0), (0, 0, 255), (0, 170, 0)]  # A=Black, B=Red, C=Blue, D=Green
        self.timeline_curves = []
        for idx, color in enumerate(colors):
            curve = self.timeline_graph.plot(pen=pg.mkPen(color, width=2), name=f'Ch{chr(65+idx)}')
            self.timeline_curves.append(curve)

        # Add dual cursors for selection
        self.timeline_cursors['left'] = pg.InfiniteLine(
            pos=0, angle=90, movable=True,
            pen=pg.mkPen('#34C759', width=2, style=Qt.DashLine),
            label='Start', labelOpts={'position': 0.95, 'color': '#34C759'}
        )
        self.timeline_cursors['right'] = pg.InfiniteLine(
            pos=100, angle=90, movable=True,
            pen=pg.mkPen('#007AFF', width=2, style=Qt.DashLine),
            label='End', labelOpts={'position': 0.95, 'color': '#007AFF'}
        )
        self.timeline_graph.addItem(self.timeline_cursors['left'])
        self.timeline_graph.addItem(self.timeline_cursors['right'])

        # Connect cursor movement to update selection view
        self.timeline_cursors['left'].sigPositionChanged.connect(self._update_selection_view)
        self.timeline_cursors['right'].sigPositionChanged.connect(self._update_selection_view)

        layout.addWidget(self.timeline_graph)

        return container

    def _create_active_selection_view(self):
        """Middle panel: Selected region with baseline cursors."""
        container = QFrame()
        container.setStyleSheet("QFrame { background: white; border-radius: 8px; }")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header with controls
        header = QHBoxLayout()
        title = QLabel("Active Selection View")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1D1D1F;")
        header.addWidget(title)

        # Channel toggles
        for ch, color in [("A", "#000000"), ("B", "#FF0000"), ("C", "#0000FF"), ("D", "#00AA00")]:
            ch_btn = QPushButton(f"Ch {ch}")
            ch_btn.setCheckable(True)
            ch_btn.setChecked(True)
            ch_btn.setFixedSize(40, 24)
            ch_btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: {color};"
                "  color: white;"
                "  border: none;"
                "  border-radius: 4px;"
                "  font-size: 11px;"
                "  font-weight: 600;"
                "}"
                "QPushButton:!checked {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #86868B;"
                "}"
            )
            ch_idx = ord(ch) - ord('A')
            ch_btn.toggled.connect(lambda checked, idx=ch_idx: self._toggle_channel(idx, checked))
            header.addWidget(ch_btn)

        # Baseline cursor controls
        baseline_btn = QPushButton("⏺ Baseline")
        baseline_btn.setFixedHeight(28)
        baseline_btn.setStyleSheet(
            "QPushButton { background: #34C759; color: white; border-radius: 6px; "
            "font-size: 12px; font-weight: 600; padding: 4px 12px; }"
        )
        baseline_btn.clicked.connect(lambda: self._toggle_baseline_cursor('baseline'))
        header.addWidget(baseline_btn)

        assoc_btn = QPushButton("⏺ Association")
        assoc_btn.setFixedHeight(28)
        assoc_btn.setStyleSheet(
            "QPushButton { background: #007AFF; color: white; border-radius: 6px; "
            "font-size: 12px; font-weight: 600; padding: 4px 12px; }"
        )
        assoc_btn.clicked.connect(lambda: self._toggle_baseline_cursor('association'))
        header.addWidget(assoc_btn)

        # Delta SPR display
        self.delta_spr_label = QLabel("ΔRU: ---")
        self.delta_spr_label.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #FF3B30; "
            "background: #F2F2F7; padding: 4px 12px; border-radius: 6px;"
        )
        header.addWidget(self.delta_spr_label)

        header.addStretch()
        layout.addLayout(header)

        # Selection graph
        self.selection_graph = pg.PlotWidget()
        self.selection_graph.setBackground('w')
        self.selection_graph.setLabel('left', 'Response (RU)', color='#1D1D1F')
        self.selection_graph.setLabel('bottom', 'Time (s)', color='#1D1D1F')
        self.selection_graph.showGrid(x=True, y=True, alpha=0.2)

        # Create curves
        colors = [(0, 0, 0), (255, 0, 0), (0, 0, 255), (0, 170, 0)]
        self.selection_curves = []
        for idx, color in enumerate(colors):
            curve = self.selection_graph.plot(pen=pg.mkPen(color, width=2), name=f'Ch{chr(65+idx)}')
            self.selection_curves.append(curve)

        # Baseline cursors
        self.baseline_cursors['baseline'] = pg.InfiniteLine(
            pos=0, angle=90, movable=True,
            pen=pg.mkPen('#34C759', width=2, style=Qt.DashLine),
            label='Baseline', labelOpts={'position': 0.95, 'color': '#34C759'}
        )
        self.baseline_cursors['association'] = pg.InfiniteLine(
            pos=50, angle=90, movable=True,
            pen=pg.mkPen('#007AFF', width=2, style=Qt.DashLine),
            label='Association', labelOpts={'position': 0.95, 'color': '#007AFF'}
        )
        self.selection_graph.addItem(self.baseline_cursors['baseline'])
        self.selection_graph.addItem(self.baseline_cursors['association'])

        # Connect to delta calculation
        self.baseline_cursors['baseline'].sigPositionChanged.connect(self._update_delta_spr)
        self.baseline_cursors['association'].sigPositionChanged.connect(self._update_delta_spr)

        layout.addWidget(self.selection_graph)

        return container

    def _create_table_panel(self):
        """Left panel: Cycle table with Load Data button."""
        container = QFrame()
        container.setStyleSheet("QFrame { background: white; border-radius: 8px; }")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header with Load button
        header = QHBoxLayout()
        title = QLabel("Cycle Data")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1D1D1F;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        load_btn = QPushButton(" Load Data")
        _folder_svg = get_affilabs_resource("ui/img/folder_icon.svg")
        if _folder_svg.exists():
            load_btn.setIcon(QIcon(str(_folder_svg)))
            load_btn.setIconSize(QSize(14, 14))
        load_btn.setFixedHeight(32)
        load_btn.setStyleSheet(
            "QPushButton { background: #007AFF; color: white; border-radius: 6px; "
            "font-size: 12px; font-weight: 600; padding: 4px 12px; }"
            "QPushButton:hover { background: #0051D5; }"
        )
        load_btn.clicked.connect(self._load_data)
        layout.addWidget(load_btn)

        # Cycle table
        self.cycle_table = QTableWidget(0, 6)
        self.cycle_table.setHorizontalHeaderLabels(['Cycle', 'Type', 'Duration', 'Conc.', 'Start', 'End'])
        self.cycle_table.setColumnWidth(0, 60)
        self.cycle_table.setColumnWidth(1, 80)
        self.cycle_table.setColumnWidth(2, 70)
        self.cycle_table.setColumnWidth(3, 70)
        self.cycle_table.setColumnWidth(4, 70)
        self.cycle_table.setColumnWidth(5, 70)
        self.cycle_table.setStyleSheet(
            "QTableWidget { background: white; border: 1px solid #E5E5EA; border-radius: 6px; "
            "font-size: 11px; }"
            "QHeaderView::section { background: #F2F2F7; color: #1D1D1F; font-weight: 600; "
            "border: none; padding: 4px; font-size: 11px; }"
        )
        self.cycle_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cycle_table.itemSelectionChanged.connect(self._on_cycle_selected)
        layout.addWidget(self.cycle_table)

        return container

    def _create_tools_panel(self):
        """Bottom panel: Compact editing tools."""
        container = QFrame()
        container.setStyleSheet("QFrame { background: white; border-radius: 8px; }")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # Smoothing slider
        layout.addWidget(QLabel("Smoothing:"))
        self.smooth_label = QLabel("0")
        self.smooth_label.setStyleSheet("font-size: 12px; color: #86868B; min-width: 20px;")
        layout.addWidget(self.smooth_label)

        self.smooth_slider = QSlider(Qt.Horizontal)
        self.smooth_slider.setRange(0, 50)
        self.smooth_slider.setValue(0)
        self.smooth_slider.setMaximumWidth(200)
        self.smooth_slider.valueChanged.connect(lambda v: (
            self.smooth_label.setText(str(v)),
            self._update_selection_view()
        ))
        layout.addWidget(self.smooth_slider)

        layout.addStretch()

        # Export button
        export_btn = QPushButton("📥 Export Selection")
        export_btn.setFixedHeight(32)
        export_btn.setStyleSheet(
            "QPushButton { background: #1D1D1F; color: white; border-radius: 6px; "
            "font-size: 12px; font-weight: 600; padding: 4px 16px; }"
            "QPushButton:hover { background: #3A3A3C; }"
        )
        export_btn.clicked.connect(self._export_selection)
        layout.addWidget(export_btn)

        return container

    def _load_data(self):
        """Load Excel data via file dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Excel File",
            str(Path.home() / "Desktop"),
            "Excel Files (*.xlsx);;All Files (*)"
        )

        if not file_path:
            return

        try:
            excel_data = pd.read_excel(file_path, sheet_name=None, engine='openpyxl')

            # Load raw data
            raw_df = excel_data.get('Raw Data')
            if raw_df is not None:
                self.raw_data_rows = raw_df.to_dict('records')
                print(f"✓ Loaded {len(self.raw_data_rows)} raw data points")

            # Load cycles
            cycles_df = excel_data.get('Cycles')
            if cycles_df is not None:
                self.cycles_data = cycles_df.to_dict('records')
                print(f"✓ Loaded {len(self.cycles_data)} cycles")

                # Populate cycle table
                self._populate_cycle_table()

                # Plot full timeline
                self._plot_full_timeline()

                # Add cycle markers
                self._add_cycle_markers()

                # Set initial cursor positions
                if self.cycles_data:
                    first_start = self.cycles_data[0].get('start_time_sensorgram', 0)
                    last_end = self.cycles_data[-1].get('end_time_sensorgram', 100)
                    self.timeline_cursors['left'].setValue(first_start)
                    self.timeline_cursors['right'].setValue(last_end)
                    self._update_selection_view()

                print(f"✓ Data loaded from: {file_path}")

        except Exception as e:
            print(f"❌ Error loading data: {e}")
            import traceback
            traceback.print_exc()

    def _populate_cycle_table(self):
        """Fill cycle table with loaded data."""
        self.cycle_table.setRowCount(len(self.cycles_data))

        for idx, cycle in enumerate(self.cycles_data):
            # Cycle name
            name = cycle.get('name', f'Cycle {idx+1}')
            self.cycle_table.setItem(idx, 0, QTableWidgetItem(str(name)))

            # Type
            cycle_type = cycle.get('cycle_type', 'Unknown')
            self.cycle_table.setItem(idx, 1, QTableWidgetItem(str(cycle_type)))

            # Duration
            duration = cycle.get('duration_minutes', cycle.get('length_minutes', 0))
            self.cycle_table.setItem(idx, 2, QTableWidgetItem(f"{duration:.1f} min"))

            # Concentration
            conc_val = cycle.get('concentration_value', '')
            conc_units = cycle.get('concentration_units', '')
            conc_str = f"{conc_val}{conc_units}" if conc_val else '---'
            self.cycle_table.setItem(idx, 3, QTableWidgetItem(conc_str))

            # Start/End times
            start = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time', 0))
            end = cycle.get('end_time_sensorgram', 0)
            self.cycle_table.setItem(idx, 4, QTableWidgetItem(f"{start:.1f}"))
            self.cycle_table.setItem(idx, 5, QTableWidgetItem(f"{end:.1f}"))

    def _plot_full_timeline(self):
        """Plot all data on timeline graph."""
        if not self.raw_data_rows:
            return

        # Collect data for each channel
        for ch_idx, ch in enumerate(['a', 'b', 'c', 'd']):
            times = []
            wavelengths = []

            for row in self.raw_data_rows:
                time = row.get('elapsed', row.get('time', 0))
                wavelength = row.get(f'wavelength_{ch}', row.get(f'channel_{ch}'))

                if pd.notna(time) and pd.notna(wavelength):
                    times.append(time)
                    wavelengths.append(wavelength)

            if times:
                # Convert to numpy and sort
                times = np.array(times)
                wavelengths = np.array(wavelengths)
                sort_idx = np.argsort(times)
                times = times[sort_idx]
                wavelengths = wavelengths[sort_idx]

                # Baseline correction and convert to RU
                if len(wavelengths) > 0:
                    baseline = wavelengths[0]
                    rus = (wavelengths - baseline) * 355.0
                    self.timeline_curves[ch_idx].setData(times, rus)

        self.timeline_graph.autoRange()
        print("✓ Timeline plot updated")

    def _add_cycle_markers(self):
        """Add vertical lines and labels for cycle boundaries."""
        # Clear existing markers
        for marker in self.cycle_markers:
            self.timeline_graph.removeItem(marker)
        for label in self.cycle_labels:
            self.timeline_graph.removeItem(label)

        self.cycle_markers = []
        self.cycle_labels = []

        for idx, cycle in enumerate(self.cycles_data):
            start = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time', 0))

            # Vertical line
            line = pg.InfiniteLine(
                pos=start, angle=90, movable=False,
                pen=pg.mkPen('#86868B', width=1, style=Qt.DotLine)
            )
            self.timeline_graph.addItem(line)
            self.cycle_markers.append(line)

            # Label
            name = str(cycle.get('name', f'C{idx+1}'))
            label = pg.TextItem(text=name, color='#86868B', anchor=(0, 1))
            label.setPos(start, 0)
            self.timeline_graph.addItem(label)
            self.cycle_labels.append(label)

        print(f"✓ Added {len(self.cycle_markers)} cycle markers")

    def _update_selection_view(self):
        """Update active selection graph based on cursor positions."""
        if not self.raw_data_rows:
            return

        # Get cursor positions
        left_pos = self.timeline_cursors['left'].value()
        right_pos = self.timeline_cursors['right'].value()

        if left_pos > right_pos:
            left_pos, right_pos = right_pos, left_pos

        # Filter data in range
        smoothing = self.smooth_slider.value()

        for ch_idx, ch in enumerate(['a', 'b', 'c', 'd']):
            times = []
            wavelengths = []

            for row in self.raw_data_rows:
                time = row.get('elapsed', row.get('time', 0))

                if left_pos <= time <= right_pos:
                    wavelength = row.get(f'wavelength_{ch}', row.get(f'channel_{ch}'))

                    if pd.notna(time) and pd.notna(wavelength):
                        times.append(time)
                        wavelengths.append(wavelength)

            if times:
                times = np.array(times)
                wavelengths = np.array(wavelengths)
                sort_idx = np.argsort(times)
                times = times[sort_idx]
                wavelengths = wavelengths[sort_idx]

                # Baseline correction and convert to RU
                if len(wavelengths) > 0:
                    baseline = wavelengths[0]
                    rus = (wavelengths - baseline) * 355.0

                    # Apply smoothing if enabled
                    if smoothing > 0 and len(rus) > smoothing:
                        from scipy.ndimage import uniform_filter1d
                        rus = uniform_filter1d(rus, size=smoothing, mode='nearest')

                    # Normalize time to start at 0
                    times = times - times[0]

                    self.selection_curves[ch_idx].setData(times, rus)
            else:
                self.selection_curves[ch_idx].setData([], [])

        self.selection_graph.autoRange()
        # Update delta calculation
        self._update_delta_spr()

    def _toggle_channel(self, ch_idx, visible):
        """Toggle channel visibility."""
        self.timeline_curves[ch_idx].setVisible(visible)
        self.selection_curves[ch_idx].setVisible(visible)

    def _update_delta_spr(self):
        """Calculate delta SPR between baseline and association cursors."""
        try:
            baseline_time = self.baseline_cursors['baseline'].value()
            assoc_time = self.baseline_cursors['association'].value()

            # Get data from all visible channels and average
            deltas = []
            for ch_idx in range(4):
                curve = self.selection_curves[ch_idx]
                if not curve.isVisible():
                    continue

                x_data, y_data = curve.getData()
                if x_data is None or len(x_data) == 0:
                    continue

                # Find closest points
                baseline_idx = np.argmin(np.abs(x_data - baseline_time))
                assoc_idx = np.argmin(np.abs(x_data - assoc_time))

                delta = y_data[assoc_idx] - y_data[baseline_idx]
                deltas.append(delta)

            if deltas:
                avg_delta = np.mean(deltas)
                self.delta_spr_label.setText(f"ΔRU: {avg_delta:.2f}")
            else:
                self.delta_spr_label.setText("ΔRU: ---")

        except Exception as e:
            print(f"Error calculating delta: {e}")
            self.delta_spr_label.setText("ΔRU: Error")

    def _toggle_baseline_cursor(self, cursor_type):
        """Toggle visibility of baseline cursors."""
        cursor = self.baseline_cursors.get(cursor_type)
        if cursor:
            cursor.setVisible(not cursor.isVisible())

    def _on_cycle_selected(self):
        """Handle cycle selection - move cursors to cycle bounds."""
        selected = self.cycle_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        if row >= len(self.cycles_data):
            return

        cycle = self.cycles_data[row]

        # Debug: show what fields are available
        print(f"DEBUG: Cycle keys: {list(cycle.keys())}")

        start = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time', 0))
        end = cycle.get('end_time_sensorgram', 0)

        print(f"DEBUG: Cursor values - start={start}, end={end}")

        # Move timeline cursors to cycle bounds
        if self.timeline_cursors and 'left' in self.timeline_cursors and 'right' in self.timeline_cursors:
            self.timeline_cursors['left'].setValue(start)
            self.timeline_cursors['right'].setValue(end)
            print(f"✓ Selected cycle {row}: {cycle.get('name', '')} ({start:.1f}-{end:.1f}s)")

            # Update the selection view after moving cursors
            self._update_selection_view()
        else:
            print("❌ Timeline cursors not initialized!")

    def _export_selection(self):
        """Export selected region to CSV."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Selection",
            str(Path.home() / "Desktop" / "selection_export.csv"),
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        try:
            # Get data from selection view
            left_pos = self.timeline_cursors['left'].value()
            right_pos = self.timeline_cursors['right'].value()

            if left_pos > right_pos:
                left_pos, right_pos = right_pos, left_pos

            # Collect data
            export_data = {'Time (s)': []}
            for ch in ['a', 'b', 'c', 'd']:
                export_data[f'Ch_{ch.upper()}_RU'] = []

            # Filter and process
            for row in self.raw_data_rows:
                time = row.get('elapsed', row.get('time', 0))

                if left_pos <= time <= right_pos:
                    export_data['Time (s)'].append(time)

                    for ch in ['a', 'b', 'c', 'd']:
                        wavelength = row.get(f'wavelength_{ch}', row.get(f'channel_{ch}'))
                        export_data[f'Ch_{ch.upper()}_RU'].append(wavelength if pd.notna(wavelength) else 0)

            # Create DataFrame and save
            df = pd.DataFrame(export_data)
            df.to_csv(file_path, index=False)
            print(f"✓ Exported {len(df)} rows to: {file_path}")

        except Exception as e:
            print(f"❌ Export error: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Run standalone test."""
    app = QApplication(sys.argv)
    window = EditsPageRedesign()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
