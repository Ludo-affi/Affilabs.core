"""Edits Tab - Data review and cycle editing functionality.

Extracted from affilabs_core_ui.py for better code organization.
This tab provides:
- Full timeline navigation with dual cursors
- Active selection view with baseline correction
- Cycle table for data management
- Export and segment creation tools
"""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QPushButton,
    QTableWidget, QHeaderView, QAbstractItemView, QSlider, QGraphicsDropShadowEffect,
    QComboBox, QDoubleSpinBox, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
import pyqtgraph as pg
import pandas as pd


class EditsTab:
    """Handles the Edits tab UI and logic."""

    def __init__(self, main_window):
        """Initialize Edits tab with reference to main window.

        Args:
            main_window: AffilabsMainWindow instance
        """
        self.main_window = main_window

        # Per-cycle editing state
        self._cycle_alignment = {}  # {row_idx: {'channel': str, 'shift': float}}

        # UI elements (will be created in create_content)
        self.cycle_data_table = None
        self.edits_timeline_graph = None
        self.edits_primary_graph = None
        self.edits_timeline_curves = []
        self.edits_graph_curves = []
        self.edits_timeline_cursors = {'left': None, 'right': None}
        self.edits_cycle_markers = []
        self.edits_cycle_labels = []
        self.edits_smooth_slider = None
        self.edits_smooth_label = None

    def create_content(self):
        """Create the Edits tab content with redesigned master-detail timeline layout.

        Returns:
            QFrame: The complete Edits tab content widget
        """
        # Initialize cursor state first
        self.edits_timeline_cursors = {'left': None, 'right': None}
        self.edits_cycle_markers = []
        self.edits_cycle_labels = []

        # Initialize table widget first (needed by panel methods)
        # Clean 6-column table - alignment controls moved to panel below
        self.cycle_data_table = QTableWidget(10, 6)
        self.cycle_data_table.setHorizontalHeaderLabels(
            ["Cycle", "Type", "Duration", "Conc.", "Start", "End"]
        )
        # Set column widths: fixed for some, stretch for others
        header = self.cycle_data_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # Cycle
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Type
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)  # Duration
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # Conc
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)  # Start
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)  # End
        self.cycle_data_table.setColumnWidth(0, 50)   # Cycle number
        self.cycle_data_table.setColumnWidth(2, 70)   # Duration
        self.cycle_data_table.setColumnWidth(3, 60)   # Concentration
        self.cycle_data_table.setColumnWidth(4, 70)   # Start time
        self.cycle_data_table.setColumnWidth(5, 70)   # End time
        self.cycle_data_table.verticalHeader().setVisible(False)  # Hide row numbers
        self.cycle_data_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.cycle_data_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cycle_data_table.itemSelectionChanged.connect(self.main_window._on_cycle_selected_in_table)

        # Initialize primary graph (needed by selection panel)
        self.edits_primary_graph = pg.PlotWidget()
        self.edits_primary_graph.setBackground('w')
        self.edits_primary_graph.setLabel('left', 'Response (RU)', color='#1D1D1F')
        self.edits_primary_graph.setLabel('bottom', 'Time (s)', color='#1D1D1F')
        self.edits_primary_graph.showGrid(x=True, y=True, alpha=0.2)

        # Create curves for 4 channels
        colors = [(0, 0, 0), (255, 0, 0), (0, 0, 255), (0, 170, 0)]
        self.edits_graph_curves = []
        for color in colors:
            curve = self.edits_primary_graph.plot(pen=pg.mkPen(color, width=2))
            self.edits_graph_curves.append(curve)

        content_widget = QFrame()
        content_widget.setStyleSheet("QFrame { background: #F8F9FA; border: none; }")

        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)

        # Main horizontal split: Table LEFT | Graphs RIGHT
        main_splitter = QSplitter(Qt.Horizontal)

        # LEFT: Cycle table (30% width)
        table_widget = self._create_table_panel()
        main_splitter.addWidget(table_widget)

        # RIGHT: Graphs (70% width)
        graphs_splitter = QSplitter(Qt.Vertical)

        # TOP: Full Timeline Navigator (35%)
        timeline_widget = self._create_timeline_navigator()
        graphs_splitter.addWidget(timeline_widget)

        # MIDDLE: Active Selection View (50%)
        selection_widget = self._create_active_selection()
        graphs_splitter.addWidget(selection_widget)

        # BOTTOM: Editing Tools (15%)
        tools_widget = self._create_tools_panel()
        graphs_splitter.addWidget(tools_widget)

        # Set vertical proportions: 35:50:15
        graphs_splitter.setStretchFactor(0, 35)
        graphs_splitter.setStretchFactor(1, 50)
        graphs_splitter.setStretchFactor(2, 15)

        main_splitter.addWidget(graphs_splitter)

        # Set horizontal proportions: 30:70 (table:graphs)
        main_splitter.setStretchFactor(0, 30)
        main_splitter.setStretchFactor(1, 70)

        # Set minimum widths
        main_splitter.setMinimumWidth(800)
        table_widget.setMinimumWidth(300)

        content_layout.addWidget(main_splitter)

        # Store references on main_window for external access
        self.main_window.cycle_data_table = self.cycle_data_table
        self.main_window.edits_timeline_graph = self.edits_timeline_graph
        self.main_window.edits_primary_graph = self.edits_primary_graph
        self.main_window.edits_timeline_curves = self.edits_timeline_curves
        self.main_window.edits_graph_curves = self.edits_graph_curves
        self.main_window.edits_timeline_cursors = self.edits_timeline_cursors
        self.main_window.edits_smooth_slider = self.edits_smooth_slider
        self.main_window.edits_smooth_label = self.edits_smooth_label

        return content_widget

    def _create_table_panel(self):
        """Left panel: Cycle table with Load Data button and alignment controls."""
        container = QFrame()
        container.setStyleSheet("QFrame { background: white; border-radius: 12px; }")
        container.setMinimumWidth(300)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header with Load button
        header = QHBoxLayout()
        title = QLabel("Cycles")
        title.setStyleSheet("font-size: 15px; font-weight: 600; color: #1D1D1F;")
        header.addWidget(title)
        header.addStretch()

        load_btn = QPushButton("📂 Load Data")
        load_btn.setFixedHeight(28)
        load_btn.setStyleSheet(
            "QPushButton { background: #007AFF; color: white; border-radius: 6px; "
            "font-size: 12px; font-weight: 600; padding: 4px 12px; }"
            "QPushButton:hover { background: #0051D5; }"
        )
        load_btn.clicked.connect(self.main_window._load_data_from_excel)
        header.addWidget(load_btn)
        layout.addLayout(header)

        # Table
        layout.addWidget(self.cycle_data_table)

        # Alignment Panel (shown when cycle selected)
        self.alignment_panel = self._create_alignment_panel()
        layout.addWidget(self.alignment_panel)
        self.alignment_panel.hide()  # Hidden until cycle selected

        return container

    def _create_alignment_panel(self):
        """Create alignment controls panel (shown when cycle selected)."""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background: #F5F5F7;
                border-radius: 8px;
                border: 1px solid #D1D1D6;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header
        self.alignment_title = QLabel("Cycle Alignment")
        self.alignment_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #1D1D1F;")
        layout.addWidget(self.alignment_title)

        # Channel selector
        ch_layout = QHBoxLayout()
        ch_label = QLabel("Channel:")
        ch_label.setStyleSheet("font-size: 12px; color: #1D1D1F;")
        ch_layout.addWidget(ch_label)

        self.alignment_channel_combo = QComboBox()
        self.alignment_channel_combo.addItems(["All", "A", "B", "C", "D"])
        self.alignment_channel_combo.setStyleSheet("""
            QComboBox {
                background: white;
                border: 1px solid #D1D1D6;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QComboBox:hover {
                border: 1px solid #007AFF;
            }
        """)
        self.alignment_channel_combo.currentTextChanged.connect(self._on_alignment_channel_changed)
        ch_layout.addWidget(self.alignment_channel_combo, 1)
        layout.addLayout(ch_layout)

        # Time shift
        shift_layout = QHBoxLayout()
        shift_label = QLabel("Time Shift:")
        shift_label.setStyleSheet("font-size: 12px; color: #1D1D1F;")
        shift_layout.addWidget(shift_label)

        self.alignment_shift_spinbox = QDoubleSpinBox()
        self.alignment_shift_spinbox.setRange(-1000.0, 1000.0)
        self.alignment_shift_spinbox.setValue(0.0)
        self.alignment_shift_spinbox.setSuffix(" s")
        self.alignment_shift_spinbox.setDecimals(2)
        self.alignment_shift_spinbox.setSingleStep(0.1)
        self.alignment_shift_spinbox.setStyleSheet("""
            QDoubleSpinBox {
                background: white;
                border: 1px solid #D1D1D6;
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
            }
            QDoubleSpinBox:hover {
                border: 1px solid #007AFF;
            }
        """)
        self.alignment_shift_spinbox.valueChanged.connect(self._on_alignment_shift_changed)
        shift_layout.addWidget(self.alignment_shift_spinbox, 1)
        layout.addLayout(shift_layout)

        return panel

    def _create_timeline_navigator(self):
        """Top right panel: Full experiment timeline with cycle markers."""
        container = QFrame()
        container.setStyleSheet("QFrame { background: white; border-radius: 12px; }")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Full Timeline Navigator")
        title.setStyleSheet("font-size: 15px; font-weight: 600; color: #1D1D1F;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Timeline graph
        self.edits_timeline_graph = pg.PlotWidget()
        self.edits_timeline_graph.setBackground('w')
        self.edits_timeline_graph.setLabel('left', 'Response (RU)', color='#1D1D1F')
        self.edits_timeline_graph.setLabel('bottom', 'Time (s)', color='#1D1D1F')
        self.edits_timeline_graph.showGrid(x=True, y=True, alpha=0.2)

        # Create curves for 4 channels
        colors = [(0, 0, 0), (255, 0, 0), (0, 0, 255), (0, 170, 0)]
        self.edits_timeline_curves = []
        for idx, color in enumerate(colors):
            curve = self.edits_timeline_graph.plot(pen=pg.mkPen(color, width=2))
            self.edits_timeline_curves.append(curve)

        # Add dual cursors for selection
        self.edits_timeline_cursors['left'] = pg.InfiniteLine(
            pos=0, angle=90, movable=True,
            pen=pg.mkPen('#34C759', width=2, style=Qt.DashLine),
            label='Start', labelOpts={'position': 0.95, 'color': '#34C759'}
        )
        self.edits_timeline_cursors['right'] = pg.InfiniteLine(
            pos=100, angle=90, movable=True,
            pen=pg.mkPen('#007AFF', width=2, style=Qt.DashLine),
            label='End', labelOpts={'position': 0.95, 'color': '#007AFF'}
        )
        self.edits_timeline_graph.addItem(self.edits_timeline_cursors['left'])
        self.edits_timeline_graph.addItem(self.edits_timeline_cursors['right'])

        # Connect cursor movement
        self.edits_timeline_cursors['left'].sigPositionChanged.connect(self._update_selection_view)
        self.edits_timeline_cursors['right'].sigPositionChanged.connect(self._update_selection_view)

        layout.addWidget(self.edits_timeline_graph)

        return container

    def _create_active_selection(self):
        """Middle right panel: Active selection view for detailed cycle analysis."""
        container = QFrame()
        container.setStyleSheet("QFrame { background: white; border-radius: 12px; }")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header with controls
        header = QHBoxLayout()
        title = QLabel("Active Selection View")
        title.setStyleSheet("font-size: 15px; font-weight: 600; color: #1D1D1F;")
        header.addWidget(title)

        # Channel toggles
        for ch, color in [("A", "#000000"), ("B", "#FF0000"), ("C", "#0000FF"), ("D", "#00AA00")]:
            ch_btn = QPushButton(f"Ch {ch}")
            ch_btn.setCheckable(True)
            ch_btn.setChecked(True)
            ch_btn.setFixedSize(40, 24)
            ch_btn.setStyleSheet(
                f"QPushButton {{ background: {color}; color: white; border: none; "
                f"border-radius: 4px; font-size: 11px; font-weight: 600; }}"
                "QPushButton:!checked { background: rgba(0, 0, 0, 0.06); color: #86868B; }"
            )
            ch_idx = ord(ch) - ord('A')
            ch_btn.toggled.connect(lambda checked, idx=ch_idx: self._toggle_channel(idx, checked))
            header.addWidget(ch_btn)

        header.addStretch()
        layout.addLayout(header)

        # Selection graph (reuse existing primary graph)
        self.edits_primary_graph.setBackground('w')
        self.edits_primary_graph.showGrid(x=True, y=True, alpha=0.2)

        layout.addWidget(self.edits_primary_graph)

        return container

    def _create_tools_panel(self):
        """Bottom right panel: Compact editing tools."""
        container = QFrame()
        container.setStyleSheet("QFrame { background: white; border-radius: 12px; }")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        container.setGraphicsEffect(shadow)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # Smoothing slider
        layout.addWidget(QLabel("Smoothing:"))
        self.edits_smooth_label = QLabel("0")
        self.edits_smooth_label.setStyleSheet("font-size: 12px; color: #86868B; min-width: 20px;")
        layout.addWidget(self.edits_smooth_label)

        self.edits_smooth_slider = QSlider(Qt.Horizontal)
        self.edits_smooth_slider.setRange(0, 50)
        self.edits_smooth_slider.setValue(0)
        self.edits_smooth_slider.setMaximumWidth(200)
        self.edits_smooth_slider.valueChanged.connect(lambda v: (
            self.edits_smooth_label.setText(str(v)),
            self._update_selection_view()
        ))
        layout.addWidget(self.edits_smooth_slider)

        layout.addStretch()

        # Create Segment button
        create_segment_btn = QPushButton("� Build Analysis Cycle")
        create_segment_btn.setToolTip(
            "Combine selected cycles into a new processable sensorgram for Analysis window.\n\n"
            "Select multiple cycles, choose channels and apply time shifts, then click to create\n"
            "a unified cycle that can be loaded in the Analysis tab for peak tracking and reporting."
        )
        create_segment_btn.setFixedHeight(32)
        create_segment_btn.setStyleSheet(
            "QPushButton { background: #007AFF; color: white; border-radius: 8px; "
            "font-size: 13px; font-weight: 600; padding: 4px 16px; }"
            "QPushButton:hover { background: #0051D5; }"
        )
        create_segment_btn.clicked.connect(self._create_segment_from_selection)
        layout.addWidget(create_segment_btn)

        # Export button
        export_btn = QPushButton("📥 Export")
        export_btn.setFixedHeight(32)
        export_btn.setStyleSheet(
            "QPushButton { background: #1D1D1F; color: white; border-radius: 8px; "
            "font-size: 13px; font-weight: 600; padding: 4px 16px; }"
            "QPushButton:hover { background: #3A3A3C; }"
        )
        export_btn.clicked.connect(self._export_selection)
        layout.addWidget(export_btn)

        return container

    # Helper methods

    def _update_selection_view(self):
        """Update active selection graph based on timeline cursor positions."""
        if not hasattr(self.main_window, '_loaded_cycles_data') or not self.main_window._loaded_cycles_data:
            return

        if not hasattr(self.main_window.app, 'recording_mgr') or not self.main_window.app.recording_mgr:
            return

        raw_data = self.main_window.app.recording_mgr.data_collector.raw_data_rows
        if not raw_data:
            return

        # Get cursor positions
        left_pos = self.edits_timeline_cursors['left'].value()
        right_pos = self.edits_timeline_cursors['right'].value()

        if left_pos > right_pos:
            left_pos, right_pos = right_pos, left_pos

        # Filter and plot data
        smoothing = self.edits_smooth_slider.value() if self.edits_smooth_slider else 0

        for ch_idx, ch in enumerate(['a', 'b', 'c', 'd']):
            times = []
            wavelengths = []

            # Filter rows for this channel within time range
            for row in raw_data:
                # New simple format: {time, channel, value}
                row_channel = row.get('channel', '')
                if row_channel != ch:
                    continue  # Skip other channels

                time = row.get('time', 0)
                value = row.get('value')

                if left_pos <= time <= right_pos:
                    if pd.notna(time) and pd.notna(value):
                        times.append(time)
                        wavelengths.append(value)

            if times:
                import numpy as np
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

                    self.edits_graph_curves[ch_idx].setData(times, rus)
            else:
                self.edits_graph_curves[ch_idx].setData([], [])

        self.edits_primary_graph.autoRange()

        # Call main window's delta SPR update if it exists
        if hasattr(self.main_window, '_update_edits_delta_spr'):
            self.main_window._update_edits_delta_spr()

    def _toggle_channel(self, ch_idx, visible):
        """Toggle channel visibility in both graphs."""
        if self.edits_timeline_curves:
            self.edits_timeline_curves[ch_idx].setVisible(visible)
        if self.edits_graph_curves:
            self.edits_graph_curves[ch_idx].setVisible(visible)

    def _export_selection(self):
        """Export combined sensorgram with selected cycles to Excel.

        Creates a new Excel file with:
        - Combined sensorgram data respecting channel selections and time shifts
        - Metadata about which cycles/channels were used
        - Alignment settings applied
        """
        from affilabs.utils.logger import logger
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import pandas as pd
        from datetime import datetime

        try:
            # Get selected cycles
            selected_rows = sorted(set(item.row() for item in self.cycle_data_table.selectedItems()))

            if not selected_rows:
                QMessageBox.information(
                    self.main_window,
                    "No Selection",
                    "Please select one or more cycles to export."
                )
                return

            # Get filename from user
            default_name = f"Combined_Sensorgram_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            file_path, _ = QFileDialog.getSaveFileName(
                self.main_window,
                "Export Combined Sensorgram",
                default_name,
                "Excel Files (*.xlsx);;All Files (*)"
            )

            if not file_path:
                return  # User cancelled

            logger.info(f"[EXPORT] Exporting combined sensorgram to: {file_path}")

            # Collect data from all selected cycles with alignment settings
            export_data = []
            metadata = []

            for row in selected_rows:
                if row >= len(self.main_window._loaded_cycles_data):
                    continue

                cycle = self.main_window._loaded_cycles_data[row]

                # Get alignment settings
                channel_filter = 'All'
                time_shift = 0.0
                if hasattr(self.main_window, '_cycle_alignment') and row in self.main_window._cycle_alignment:
                    channel_filter = self.main_window._cycle_alignment[row]['channel']
                    time_shift = self.main_window._cycle_alignment[row]['shift']

                # Get cycle time range
                start_time = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time'))
                end_time = cycle.get('end_time_sensorgram')

                if start_time is None:
                    continue

                if end_time is None:
                    duration_min = cycle.get('duration_minutes', cycle.get('length_minutes', 5))
                    end_time = start_time + (duration_min * 60) if duration_min else start_time + 300

                # Record metadata
                metadata.append({
                    'Cycle_Index': row,
                    'Cycle_Type': cycle.get('type', 'Unknown'),
                    'Channel_Filter': channel_filter,
                    'Time_Shift_s': time_shift,
                    'Start_Time_s': start_time,
                    'End_Time_s': end_time,
                    'Duration_min': cycle.get('duration_minutes', ''),
                    'Concentration': cycle.get('concentration_value', ''),
                    'Units': cycle.get('concentration_units', '')
                })

                # Get raw data
                raw_data = self.main_window.app.recording_mgr.data_collector.raw_data_rows

                # Filter and process data
                WAVELENGTH_TO_RU = 355.0
                baseline_wavelengths = {}

                for row_data in raw_data:
                    time = row_data.get('elapsed', row_data.get('time', 0))
                    if start_time <= time <= end_time:
                        relative_time = time - start_time + time_shift

                        # Handle both data formats
                        if 'channel' in row_data and 'value' in row_data:
                            ch = row_data.get('channel')
                            value = row_data.get('value')

                            # Apply channel filter
                            if channel_filter != 'All' and ch != channel_filter.lower():
                                continue

                            if ch in ['a', 'b', 'c', 'd'] and value is not None:
                                # Calculate baseline (first value for this channel)
                                if ch not in baseline_wavelengths:
                                    baseline_wavelengths[ch] = value

                                # Convert to RU
                                delta_wavelength = value - baseline_wavelengths[ch]
                                ru_value = delta_wavelength * WAVELENGTH_TO_RU

                                export_data.append({
                                    'Time_s': relative_time,
                                    'Channel': ch.upper(),
                                    'Wavelength_nm': value,
                                    'Response_RU': ru_value,
                                    'Cycle_Index': row,
                                    'Cycle_Type': cycle.get('type', 'Unknown')
                                })
                        else:
                            # Wide format
                            for ch in ['a', 'b', 'c', 'd']:
                                if channel_filter != 'All' and ch != channel_filter.lower():
                                    continue

                                wavelength = row_data.get(f'channel_{ch}', row_data.get(f'wavelength_{ch}'))
                                if wavelength is not None:
                                    if ch not in baseline_wavelengths:
                                        baseline_wavelengths[ch] = wavelength

                                    delta_wavelength = wavelength - baseline_wavelengths[ch]
                                    ru_value = delta_wavelength * WAVELENGTH_TO_RU

                                    export_data.append({
                                        'Time_s': relative_time,
                                        'Channel': ch.upper(),
                                        'Wavelength_nm': wavelength,
                                        'Response_RU': ru_value,
                                        'Cycle_Index': row,
                                        'Cycle_Type': cycle.get('type', 'Unknown')
                                    })

                logger.info(f"[EXPORT] Cycle {row}: Extracted {len([d for d in export_data if d['Cycle_Index'] == row])} data points")

            # Create Excel file with multiple sheets
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Sheet 1: Combined data
                df_data = pd.DataFrame(export_data)
                df_data = df_data.sort_values(['Time_s', 'Channel'])
                df_data.to_excel(writer, sheet_name='Combined Data', index=False)

                # Sheet 2: Metadata
                df_meta = pd.DataFrame(metadata)
                df_meta.to_excel(writer, sheet_name='Cycle Metadata', index=False)

                # Sheet 3: Export info
                export_info = pd.DataFrame([{
                    'Export_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'Total_Cycles': len(selected_rows),
                    'Total_Data_Points': len(export_data),
                    'Description': 'Combined sensorgram with custom channel selection and time alignment'
                }])
                export_info.to_excel(writer, sheet_name='Export Info', index=False)

            logger.info(f"✓ Exported {len(export_data)} data points from {len(selected_rows)} cycles")

            QMessageBox.information(
                self.main_window,
                "Export Complete",
                f"Combined sensorgram exported successfully!\n\n"
                f"File: {file_path}\n"
                f"Cycles: {len(selected_rows)}\n"
                f"Data points: {len(export_data)}"
            )

        except Exception as e:
            logger.exception(f"Error exporting selection: {e}")
            QMessageBox.critical(
                self.main_window,
                "Export Error",
                f"Failed to export combined sensorgram:\n{str(e)}"
            )

    def _on_alignment_channel_changed(self, channel):
        """Handle channel change in alignment panel."""
        from affilabs.utils.logger import logger

        # Get selected row
        selected_items = self.cycle_data_table.selectedItems()
        if not selected_items:
            return

        row_idx = selected_items[0].row()

        # Update alignment data
        if row_idx not in self._cycle_alignment:
            self._cycle_alignment[row_idx] = {'channel': 'All', 'shift': 0.0}

        self._cycle_alignment[row_idx]['channel'] = channel

        logger.info(f"Cycle {row_idx + 1} channel changed to: {channel}")

        # Trigger graph update
        if hasattr(self.main_window, '_on_cycle_selected_in_table'):
            self.main_window._on_cycle_selected_in_table()

    def _on_alignment_shift_changed(self, shift):
        """Handle time shift change in alignment panel."""
        from affilabs.utils.logger import logger

        # Get selected row
        selected_items = self.cycle_data_table.selectedItems()
        if not selected_items:
            return

        row_idx = selected_items[0].row()

        # Update alignment data
        if row_idx not in self._cycle_alignment:
            self._cycle_alignment[row_idx] = {'channel': 'All', 'shift': 0.0}

        self._cycle_alignment[row_idx]['shift'] = shift

        logger.info(f"Cycle {row_idx + 1} time shift changed to: {shift}s")

        # Trigger graph update
        if hasattr(self.main_window, '_on_cycle_selected_in_table'):
            self.main_window._on_cycle_selected_in_table()

    def _select_cycle_by_index(self, cycle_idx):
        """Select a cycle by index and move cursors to its bounds.

        Args:
            cycle_idx: Index of the cycle to select
        """
        # Select the corresponding row in the table
        self.cycle_data_table.clearSelection()
        self.cycle_data_table.selectRow(cycle_idx)

        logger.info(f"✓ Clicked cycle marker {cycle_idx + 1}")

        # The table selection change will trigger _on_cycle_selected_in_table
        # which updates the cursors and graph


    def _create_segment_from_selection(self):
        """Create a NEW combined cycle from selected channels of different cycles.

        Extracts actual data from selected cycles, applies channel filters and time shifts,
        and saves as a new processable cycle for Analysis window.
        """
        from affilabs.utils.logger import logger
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        import pandas as pd
        from pathlib import Path
        from datetime import datetime

        try:
            # Get selected cycles
            selected_rows = sorted(set(item.row() for item in self.cycle_data_table.selectedItems()))

            if not selected_rows:
                QMessageBox.information(
                    self.main_window,
                    "No Selection",
                    "Please select one or more cycles to create a segment."
                )
                return

            # Ask user for segment name
            segment_name, ok = QInputDialog.getText(
                self.main_window,
                "Create New Cycle Segment",
                "Enter a name for this new combined cycle:",
                text=f"Combined_Cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

            if not ok or not segment_name:
                return  # User cancelled

            logger.info(f"[SEGMENT] Creating new combined cycle: {segment_name}")
            logger.info(f"[SEGMENT] Creating new combined cycle: {segment_name}")

            # Collect combined data from all selected cycles
            combined_raw_data = []
            segment_metadata = {
                'name': segment_name,
                'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source_cycles': [],
                'type': 'combined',
                'description': f"Combined cycle from {len(selected_rows)} source cycle(s)"
            }

            WAVELENGTH_TO_RU = 355.0
            current_time_offset = 0.0  # Running time to concatenate cycles

            for row in selected_rows:
                if row >= len(self.main_window._loaded_cycles_data):
                    continue

                cycle = self.main_window._loaded_cycles_data[row]

                # Get alignment settings
                channel_filter = 'All'
                cycle_shift = 0.0
                if hasattr(self.main_window, '_cycle_alignment') and row in self.main_window._cycle_alignment:
                    channel_filter = self.main_window._cycle_alignment[row]['channel']
                    cycle_shift = self.main_window._cycle_alignment[row]['shift']

                # Get cycle time range
                start_time = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time'))
                end_time = cycle.get('end_time_sensorgram')

                if start_time is None:
                    continue

                if end_time is None:
                    duration_min = cycle.get('duration_minutes', cycle.get('length_minutes', 5))
                    end_time = start_time + (duration_min * 60) if duration_min else start_time + 300

                # Record source cycle info
                segment_metadata['source_cycles'].append({
                    'cycle_index': row,
                    'cycle_type': cycle.get('type', 'Unknown'),
                    'channel_used': channel_filter,
                    'time_shift': cycle_shift,
                    'original_start': start_time,
                    'original_end': end_time
                })

                # Get raw data
                raw_data = self.main_window.app.recording_mgr.data_collector.raw_data_rows

                # Extract and process data points
                for row_data in raw_data:
                    time = row_data.get('elapsed', row_data.get('time', 0))
                    if start_time <= time <= end_time:
                        # Convert to relative time with shift, then add to running total
                        relative_time = (time - start_time + cycle_shift) + current_time_offset

                        # Handle both data formats
                        if 'channel' in row_data and 'value' in row_data:
                            ch = row_data.get('channel')
                            value = row_data.get('value')

                            # Apply channel filter
                            if channel_filter != 'All' and ch != channel_filter.lower():
                                continue

                            if ch in ['a', 'b', 'c', 'd'] and value is not None:
                                combined_raw_data.append({
                                    'time': relative_time,
                                    'channel': ch,
                                    'value': value,
                                    'source_cycle': row,
                                    'source_type': cycle.get('type', 'Unknown')
                                })
                        else:
                            # Wide format
                            for ch in ['a', 'b', 'c', 'd']:
                                if channel_filter != 'All' and ch != channel_filter.lower():
                                    continue

                                wavelength = row_data.get(f'channel_{ch}', row_data.get(f'wavelength_{ch}'))
                                if wavelength is not None:
                                    combined_raw_data.append({
                                        'time': relative_time,
                                        'channel': ch,
                                        'value': wavelength,
                                        'source_cycle': row,
                                        'source_type': cycle.get('type', 'Unknown')
                                    })

                # Update time offset for next cycle (concatenate cycles end-to-end)
                cycle_duration = end_time - start_time + cycle_shift
                current_time_offset += cycle_duration

                logger.info(f"[SEGMENT] Extracted cycle {row}: {len([d for d in combined_raw_data if d['source_cycle'] == row])} points")

            if not combined_raw_data:
                QMessageBox.warning(
                    self.main_window,
                    "No Data",
                    "No data points were extracted from selected cycles.\n\n"
                    "Check that cycles have valid time ranges."
                )
                return

            # Save as Excel file (compatible with Analysis window)
            segments_dir = Path('data_results/segments')
            segments_dir.mkdir(parents=True, exist_ok=True)

            # Create filename-safe name
            safe_name = "".join(c for c in segment_name if c.isalnum() or c in (' ', '-', '_')).strip()
            segment_file = segments_dir / f"{safe_name}.xlsx"

            # Check if file exists
            if segment_file.exists():
                reply = QMessageBox.question(
                    self.main_window,
                    "Segment Exists",
                    f"A segment named '{segment_name}' already exists.\n\nOverwrite it?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return

            # Create Excel file with cycle data
            with pd.ExcelWriter(segment_file, engine='openpyxl') as writer:
                # Sheet 1: Raw Data (in long format for compatibility)
                df_raw = pd.DataFrame(combined_raw_data)
                df_raw.to_excel(writer, sheet_name='Raw Data', index=False)

                # Sheet 2: Cycles metadata (single combined cycle)
                cycle_meta = pd.DataFrame([{
                    'name': segment_name,
                    'type': 'combined',
                    'start_time_sensorgram': 0.0,
                    'end_time_sensorgram': current_time_offset,
                    'duration_minutes': current_time_offset / 60.0,
                    'concentration_value': '',
                    'concentration_units': '',
                    'note': f"Combined from {len(selected_rows)} source cycles"
                }])
                cycle_meta.to_excel(writer, sheet_name='Cycles', index=False)

                # Sheet 3: Segment metadata
                df_meta = pd.DataFrame([segment_metadata])
                df_meta.to_excel(writer, sheet_name='Segment Info', index=False)

            logger.info(f"✓ Created combined cycle segment: {segment_name}")
            logger.info(f"  Total data points: {len(combined_raw_data)}")
            logger.info(f"  Total duration: {current_time_offset:.1f}s")
            logger.info(f"  Saved to: {segment_file}")

            QMessageBox.information(
                self.main_window,
                "Segment Created",
                f"New combined cycle '{segment_name}' created!\n\n"
                f"Source cycles: {len(selected_rows)}\n"
                f"Data points: {len(combined_raw_data)}\n"
                f"Duration: {current_time_offset/60:.1f} min\n\n"
                f"Saved to: {segment_file}\n\n"
                f"You can load this in the Analysis window for kinetic fitting."
            )

        except Exception as e:
            logger.exception(f"Error creating segment: {e}")
            QMessageBox.critical(
                self.main_window,
                "Segment Error",
                f"Failed to create segment:\n{str(e)}"
            )

    def add_cycle_markers_to_timeline(self, cycles_data):
        """Add colored background regions and labels for each cycle.

        Args:
            cycles_data: List of cycle dictionaries with start/end times and type
        """
        from affilabs.utils.logger import logger

        # Clear existing markers
        for marker in self.edits_cycle_markers:
            self.edits_timeline_graph.removeItem(marker)
        for label in self.edits_cycle_labels:
            self.edits_timeline_graph.removeItem(label)

        self.edits_cycle_markers = []
        self.edits_cycle_labels = []

        # Color scheme by cycle type (R, G, B, Alpha)
        # Increased alpha from 40 to 120 for better visibility
        cycle_colors = {
            'baseline': (200, 200, 200, 120),      # Light gray
            'association': (100, 150, 255, 120),   # Light blue
            'dissociation': (255, 255, 150, 120),  # Light yellow
            'regeneration': (255, 150, 150, 120),  # Light red
            'wash': (150, 255, 200, 120),          # Light green
            'concentration': (150, 200, 255, 120), # Light cyan
            'conc.': (150, 200, 255, 120),         # Light cyan
            'default': (220, 220, 220, 100),       # Very light gray
        }

        for idx, cycle in enumerate(cycles_data):
            start = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time', 0))
            end = cycle.get('end_time_sensorgram', start + 100)
            cycle_type = cycle.get('type', '').lower()
            # Use index-based numbering instead of data name (fixes duplicate labeling)
            name = f'Cycle {idx+1}'

            # Get color for this cycle type
            color = cycle_colors.get(cycle_type, cycle_colors['default'])

            # Create filled region for cycle background
            region = pg.LinearRegionItem(
                values=(start, end),
                orientation='vertical',
                brush=pg.mkBrush(*color),
                movable=False
            )
            region.setZValue(-10)  # Put behind data curves

            # Store cycle index for mouse event handler
            region.cycle_index = idx

            # Override mouse click to select cycle
            def make_click_handler(cycle_idx):
                def mouseClickEvent(event):
                    if event.button() == Qt.LeftButton:
                        self._select_cycle_by_index(cycle_idx)
                        event.accept()
                return mouseClickEvent

            region.mouseClickEvent = make_click_handler(idx)

            self.edits_timeline_graph.addItem(region)
            self.edits_cycle_markers.append(region)

            # Add boundary line at start
            line = pg.InfiniteLine(
                pos=start, angle=90, movable=False,
                pen=pg.mkPen((120, 120, 120), width=2, style=Qt.DotLine)
            )
            self.edits_timeline_graph.addItem(line)
            self.edits_cycle_markers.append(line)

            # Add label with cycle name and type
            label_text = f"{name}"
            if cycle_type and cycle_type not in name.lower():
                label_text = f"{name}\n({cycle_type})"

            label = pg.TextItem(
                text=label_text,
                color=(60, 60, 60),
                anchor=(0, 1),
                fill=pg.mkBrush(255, 255, 255, 220),
                border=pg.mkPen((180, 180, 180), width=1)
            )
            # Position label at start + small offset, at top of graph
            label.setPos(start + 2, 0)
            self.edits_timeline_graph.addItem(label)
            self.edits_cycle_labels.append(label)

        logger.info(f"✓ Added {len(cycles_data)} cycle markers with colored backgrounds to timeline")

    def set_cycle_overlay_mode(self, mode='stack_cycles'):
        """Set how cycles are overlaid on the Active Selection graph.

        Args:
            mode: Either 'stack_cycles' (align same channel across cycles at t=0)
                  or 'compare_channels' (show different channels from same cycle)
        """
        self.overlay_mode = mode
        # Re-render the selection view with new mode
        self._update_selection_view()

    def get_cycle_data_normalized(self, cycle_idx, channel):
        """Get cycle data with time normalized to start at t=0.

        Useful for stacking multiple cycles aligned at injection point.

        Args:
            cycle_idx: Index of cycle in loaded data
            channel: Channel letter ('a', 'b', 'c', 'd')

        Returns:
            tuple: (times, values) arrays with time starting at 0
        """
        import numpy as np

        if not hasattr(self.main_window, '_loaded_cycles_data'):
            return ([], [])

        if cycle_idx >= len(self.main_window._loaded_cycles_data):
            return ([], [])

        cycle = self.main_window._loaded_cycles_data[cycle_idx]
        start_time = cycle.get('start_time_sensorgram', 0)
        end_time = cycle.get('end_time_sensorgram', start_time + 100)

        # Get raw data from main window
        if not hasattr(self.main_window, '_loaded_raw_data'):
            return ([], [])

        raw_data = self.main_window._loaded_raw_data

        times = []
        values = []

        for row in raw_data:
            if row.get('channel') != channel:
                continue

            time = row.get('time', 0)
            if start_time <= time <= end_time:
                value = row.get('value')
                if pd.notna(time) and pd.notna(value):
                    times.append(time - start_time)  # Normalize to t=0
                    values.append(value)

        if times:
            times = np.array(times)
            values = np.array(values)
            sort_idx = np.argsort(times)
            return (times[sort_idx], values[sort_idx])

        return ([], [])
