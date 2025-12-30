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

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("background: #D1D1D6;")
        layout.addWidget(divider)

        # Cycle boundaries header
        boundaries_label = QLabel("Cycle Boundaries")
        boundaries_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #1D1D1F; margin-top: 4px;")
        layout.addWidget(boundaries_label)

        # Start time editor
        start_layout = QHBoxLayout()
        start_label = QLabel("Start Time:")
        start_label.setStyleSheet("font-size: 12px; color: #1D1D1F;")
        start_layout.addWidget(start_label)

        self.cycle_start_spinbox = QDoubleSpinBox()
        self.cycle_start_spinbox.setRange(0.0, 999999.0)
        self.cycle_start_spinbox.setValue(0.0)
        self.cycle_start_spinbox.setSuffix(" s")
        self.cycle_start_spinbox.setDecimals(2)
        self.cycle_start_spinbox.setSingleStep(1.0)
        self.cycle_start_spinbox.setStyleSheet("""
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
        self.cycle_start_spinbox.valueChanged.connect(self._on_cycle_start_changed)
        start_layout.addWidget(self.cycle_start_spinbox, 1)
        layout.addLayout(start_layout)

        # End time editor
        end_layout = QHBoxLayout()
        end_label = QLabel("End Time:")
        end_label.setStyleSheet("font-size: 12px; color: #1D1D1F;")
        end_layout.addWidget(end_label)

        self.cycle_end_spinbox = QDoubleSpinBox()
        self.cycle_end_spinbox.setRange(0.0, 999999.0)
        self.cycle_end_spinbox.setValue(0.0)
        self.cycle_end_spinbox.setSuffix(" s")
        self.cycle_end_spinbox.setDecimals(2)
        self.cycle_end_spinbox.setSingleStep(1.0)
        self.cycle_end_spinbox.setStyleSheet("""
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
        self.cycle_end_spinbox.valueChanged.connect(self._on_cycle_end_changed)
        end_layout.addWidget(self.cycle_end_spinbox, 1)
        layout.addLayout(end_layout)

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

        # Create Processing Cycle button
        create_processing_btn = QPushButton("📊 Create Processing Cycle")
        create_processing_btn.setToolTip(
            "Extract and combine selected channels from multiple cycles.\n\n"
            "1. Select cycles in table\n"
            "2. Set Channel filter for each cycle (A/B/C/D or All)\n"
            "3. Click to extract and merge only those channels\n\n"
            "Perfect for creating single-channel datasets across multiple cycles."
        )
        create_processing_btn.setFixedHeight(32)
        create_processing_btn.setStyleSheet(
            "QPushButton { background: #34C759; color: white; border-radius: 8px; "
            "font-size: 13px; font-weight: 600; padding: 4px 16px; }"
            "QPushButton:hover { background: #28A745; }"
        )
        create_processing_btn.clicked.connect(self._create_processing_cycle)
        layout.addWidget(create_processing_btn)

        layout.addSpacing(8)

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

                # Sheet 3: Alignment settings (for re-loading)
                if self._cycle_alignment:
                    alignment_rows = []
                    for cycle_idx, settings in self._cycle_alignment.items():
                        if cycle_idx in selected_rows:
                            alignment_rows.append({
                                'Cycle_Index': cycle_idx,
                                'Channel_Filter': settings.get('channel', 'All'),
                                'Time_Shift_s': settings.get('shift', 0.0)
                            })
                    if alignment_rows:
                        df_alignment = pd.DataFrame(alignment_rows)
                        df_alignment.to_excel(writer, sheet_name='Alignment', index=False)

                # Sheet 4: Flags (if any)
                if self._edits_flags:
                    flag_rows = []
                    for flag in self._edits_flags:
                        flag_rows.append(flag.to_export_dict())
                    if flag_rows:
                        df_flags = pd.DataFrame(flag_rows)
                        df_flags.to_excel(writer, sheet_name='Flags', index=False)
                        logger.debug(f"Exported {len(flag_rows)} flags")

                # Sheet 5: Export info
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

    def _on_cycle_start_changed(self, start_time):
        """Handle cycle start time change."""
        from affilabs.utils.logger import logger

        # Get selected row
        selected_items = self.cycle_data_table.selectedItems()
        if not selected_items:
            return

        row_idx = selected_items[0].row()

        # Update cycle data
        if row_idx < len(self.main_window._loaded_cycles_data):
            cycle = self.main_window._loaded_cycles_data[row_idx]
            old_start = cycle.get('start_time_sensorgram', 0)
            cycle['start_time_sensorgram'] = start_time

            # Ensure end time is after start time
            end_time = cycle.get('end_time_sensorgram', start_time + 300)
            if end_time <= start_time:
                end_time = start_time + 300
                cycle['end_time_sensorgram'] = end_time
                self.cycle_end_spinbox.blockSignals(True)
                self.cycle_end_spinbox.setValue(end_time)
                self.cycle_end_spinbox.blockSignals(False)

            # Update duration
            duration_min = (end_time - start_time) / 60.0
            cycle['duration_minutes'] = duration_min

            logger.info(f"Cycle {row_idx + 1} start time: {old_start:.2f}s → {start_time:.2f}s")

            # Update table
            self._update_cycle_table_row(row_idx, cycle)

            # Trigger graph update
            if hasattr(self.main_window, '_on_cycle_selected_in_table'):
                self.main_window._on_cycle_selected_in_table()

    def _on_cycle_end_changed(self, end_time):
        """Handle cycle end time change."""
        from affilabs.utils.logger import logger

        # Get selected row
        selected_items = self.cycle_data_table.selectedItems()
        if not selected_items:
            return

        row_idx = selected_items[0].row()

        # Update cycle data
        if row_idx < len(self.main_window._loaded_cycles_data):
            cycle = self.main_window._loaded_cycles_data[row_idx]
            start_time = cycle.get('start_time_sensorgram', 0)

            # Ensure end time is after start time
            if end_time <= start_time:
                end_time = start_time + 300
                self.cycle_end_spinbox.blockSignals(True)
                self.cycle_end_spinbox.setValue(end_time)
                self.cycle_end_spinbox.blockSignals(False)

            old_end = cycle.get('end_time_sensorgram', end_time)
            cycle['end_time_sensorgram'] = end_time

            # Update duration
            duration_min = (end_time - start_time) / 60.0
            cycle['duration_minutes'] = duration_min

            logger.info(f"Cycle {row_idx + 1} end time: {old_end:.2f}s → {end_time:.2f}s")

            # Update table
            self._update_cycle_table_row(row_idx, cycle)

            # Trigger graph update
            if hasattr(self.main_window, '_on_cycle_selected_in_table'):
                self.main_window._on_cycle_selected_in_table()

    def _update_cycle_table_row(self, row_idx, cycle):
        """Update a single row in the cycle table."""
        from PySide6.QtWidgets import QTableWidgetItem

        # Update table cells
        self.cycle_data_table.setItem(row_idx, 0, QTableWidgetItem(str(cycle.get('cycle_number', row_idx + 1))))
        self.cycle_data_table.setItem(row_idx, 1, QTableWidgetItem(cycle.get('type', 'Unknown')))
        self.cycle_data_table.setItem(row_idx, 2, QTableWidgetItem(str(cycle.get('duration_minutes', ''))))
        self.cycle_data_table.setItem(row_idx, 3, QTableWidgetItem(str(cycle.get('concentration_value', ''))))
        self.cycle_data_table.setItem(row_idx, 4, QTableWidgetItem(cycle.get('concentration_units', '')))
        self.cycle_data_table.setItem(row_idx, 5, QTableWidgetItem(cycle.get('notes', '')))

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

    def _create_processing_cycle(self):
        """Create a processing cycle by extracting selected channels from multiple cycles.

        Uses the channel filter settings from the alignment panel to determine which
        channel to extract from each cycle. Concatenates the extracted data into a
        new synthetic cycle for data processing.
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
                    "Please select one or more cycles to create a processing cycle."
                )
                return

            # Ask user for cycle name
            cycle_name, ok = QInputDialog.getText(
                self.main_window,
                "Create Processing Cycle",
                "Enter a name for this processing cycle:",
                text=f"Processing_Cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

            if not ok or not cycle_name:
                return  # User cancelled

            logger.info(f"📊 Creating processing cycle: {cycle_name}")
            logger.info(f"   Extracting from {len(selected_rows)} source cycle(s)")

            # Collect extracted channel data
            combined_data = []
            current_time = 0.0

            metadata = {
                'name': cycle_name,
                'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source_cycles': [],
                'type': 'processing',
                'description': f"Channel-filtered processing cycle from {len(selected_rows)} source(s)"
            }

            WAVELENGTH_TO_RU = 355.0

            for row in selected_rows:
                if row >= len(self.main_window._loaded_cycles_data):
                    continue

                cycle = self.main_window._loaded_cycles_data[row]
                cycle_name_src = cycle.get('name', f'Cycle {row}')
                start_time = cycle.get('start_time_sensorgram', 0.0)
                end_time = cycle.get('end_time_sensorgram', 0.0)

                # Get alignment settings for this cycle (determines which channel to extract)
                alignment = self._cycle_alignment.get(row, {'channel': 'All', 'shift': 0.0})
                channel_filter = alignment.get('channel', 'All')
                time_shift = alignment.get('shift', 0.0)

                logger.info(f"   Cycle {row} ({cycle_name_src}): Extracting channel {channel_filter}, shift={time_shift}s")

                # Record metadata
                metadata['source_cycles'].append({
                    'index': row,
                    'name': cycle_name_src,
                    'channel': channel_filter,
                    'time_shift': time_shift,
                    'duration_s': end_time - start_time
                })

                # Get raw data
                raw_data = self.main_window._loaded_raw_data
                if raw_data is None or raw_data.empty:
                    logger.warning(f"      No raw data available")
                    continue

                # Filter to cycle time range
                cycle_mask = (raw_data['Time_s'] >= start_time) & (raw_data['Time_s'] <= end_time)
                cycle_data = raw_data[cycle_mask].copy()

                if cycle_data.empty:
                    logger.warning(f"      No data in time range {start_time:.1f}-{end_time:.1f}s")
                    continue

                # Normalize time to start at current_time
                cycle_data['Time_s'] = cycle_data['Time_s'] - start_time + time_shift + current_time

                # Extract only the selected channel(s)
                channels_to_extract = ['A', 'B', 'C', 'D'] if channel_filter == 'All' else [channel_filter]

                for ch in channels_to_extract:
                    wavelength_col = f'Wavelength_{ch}_nm'
                    ru_col = f'Response_{ch}_RU'

                    # Convert wavelength to RU if needed
                    if wavelength_col in cycle_data.columns and ru_col not in cycle_data.columns:
                        cycle_data[ru_col] = cycle_data[wavelength_col] * WAVELENGTH_TO_RU

                    # Extract channel data
                    if ru_col in cycle_data.columns:
                        for _, row_data in cycle_data.iterrows():
                            combined_data.append({
                                'Time_s': row_data['Time_s'],
                                'Channel': ch.lower(),
                                'Response_RU': row_data[ru_col]
                            })

                # Update time offset
                cycle_duration = end_time - start_time
                current_time += cycle_duration

                logger.info(f"      Extracted {len(cycle_data)} time points, total duration now: {current_time:.1f}s")

            if not combined_data:
                QMessageBox.warning(
                    self.main_window,
                    "No Data",
                    "No data was extracted from selected cycles.\n\n"
                    "Check that cycles have valid data and channel filters are set."
                )
                return

            # Save to Excel
            output_dir = Path('data_results/processing_cycles')
            output_dir.mkdir(parents=True, exist_ok=True)

            safe_name = "".join(c for c in cycle_name if c.isalnum() or c in (' ', '-', '_')).strip()
            output_file = output_dir / f"{safe_name}.xlsx"

            # Check if exists
            if output_file.exists():
                reply = QMessageBox.question(
                    self.main_window,
                    "File Exists",
                    f"Processing cycle '{cycle_name}' already exists.\n\nOverwrite?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return

            # Write Excel file
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Sheet 1: Extracted data in long format
                df_data = pd.DataFrame(combined_data)
                df_data.to_excel(writer, sheet_name='Data', index=False)

                # Sheet 2: Metadata
                df_meta = pd.DataFrame([metadata])
                df_meta.to_excel(writer, sheet_name='Metadata', index=False)

                # Sheet 3: Source details
                df_sources = pd.DataFrame(metadata['source_cycles'])
                df_sources.to_excel(writer, sheet_name='Source_Cycles', index=False)

            logger.info(f"✓ Created processing cycle: {cycle_name}")
            logger.info(f"   Total data points: {len(combined_data)}")
            logger.info(f"   Total duration: {current_time:.1f}s")
            logger.info(f"   Saved to: {output_file}")

            QMessageBox.information(
                self.main_window,
                "Processing Cycle Created",
                f"Processing cycle '{cycle_name}' created!\n\n"
                f"Source cycles: {len(selected_rows)}\n"
                f"Data points: {len(combined_data)}\n"
                f"Duration: {current_time/60:.1f} min\n\n"
                f"Saved to:\n{output_file}\n\n"
                f"This file contains only the selected channel(s) from each cycle."
            )

        except Exception as e:
            logger.exception(f"Error creating processing cycle: {e}")
            QMessageBox.critical(
                self.main_window,
                "Processing Cycle Error",
                f"Failed to create processing cycle:\n\n{str(e)}"
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
