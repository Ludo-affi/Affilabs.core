"""
Analysis Tab - Multi-cycle overlay, kinetic analysis, and dose-response curves.

This tab is focused on scientific analysis after data quality has been verified:
- Multi-cycle overlay with t=0 normalization
- Dose-response curve comparison
- Kinetic parameter fitting (association/dissociation rates)
- Statistical analysis across concentration series
- Export publication-ready overlays
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QCheckBox, QHeaderView,
    QComboBox, QGraphicsDropShadowEffect
)
from PySide6.QtGui import QColor
import pyqtgraph as pg

from affilabs.utils.logger import logger


class AnalysisTab:
    """Analysis tab for multi-cycle comparison and kinetic analysis."""
    
    def __init__(self, main_window):
        """Initialize Analysis tab.
        
        Args:
            main_window: Reference to AffilabsCoreUI main window
        """
        self.main_window = main_window
        self.overlay_curves = []  # Store overlay curve sets
        
    def create_content(self):
        """Create the Analysis tab content."""
        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame { background: #F8F9FA; border: none; }"
        )
        
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)
        
        # Left panel: Cycle selection and controls (30%)
        left_panel = self._create_left_panel()
        content_layout.addWidget(left_panel, 3)
        
        # Right panel: Overlay graph and analysis tools (70%)
        right_panel = self._create_right_panel()
        content_layout.addWidget(right_panel, 7)
        
        return content_widget
    
    def _create_left_panel(self):
        """Create left panel with cycle selection table."""
        panel = QFrame()
        panel.setStyleSheet("QFrame { background: transparent; border: none; }")
        
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)
        
        # Cycle Selection Card
        selection_card = QFrame()
        selection_card.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 8px;"
            "}"
        )
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 20))
        selection_card.setGraphicsEffect(shadow)
        
        selection_layout = QVBoxLayout(selection_card)
        selection_layout.setContentsMargins(16, 16, 16, 16)
        selection_layout.setSpacing(12)
        
        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Select Cycles to Compare")
        title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "}"
        )
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Load Data button
        load_btn = QPushButton("📁 Load Data")
        load_btn.setFixedHeight(32)
        load_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 0px 16px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover {"
            "  background: #0051D5;"
            "}"
        )
        load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_btn.clicked.connect(self.main_window._load_data_from_excel)
        header_layout.addWidget(load_btn)
        
        selection_layout.addLayout(header_layout)
        
        # Cycle table (compact view - only essential columns)
        self.cycle_table = QTableWidget()
        self.cycle_table.setColumnCount(6)
        self.cycle_table.setHorizontalHeaderLabels([
            "#", "Type", "Sample", "Conc.", "Duration", "Notes"
        ])
        self.cycle_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.cycle_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.cycle_table.verticalHeader().setVisible(False)
        self.cycle_table.setAlternatingRowColors(True)
        self.cycle_table.setStyleSheet(
            "QTableWidget {"
            "  background: white;"
            "  border: 1px solid #E5E5EA;"
            "  border-radius: 6px;"
            "  gridline-color: #F2F2F7;"
            "}"
            "QTableWidget::item {"
            "  padding: 6px 8px;"
            "  font-size: 12px;"
            "  color: #1D1D1F;"
            "}"
            "QTableWidget::item:selected {"
            "  background: #007AFF;"
            "  color: white;"
            "}"
            "QHeaderView::section {"
            "  background: #F8F9FA;"
            "  border: none;"
            "  border-bottom: 2px solid #E5E5EA;"
            "  padding: 8px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  color: #8E8E93;"
            "  text-transform: uppercase;"
            "}"
        )
        
        # Set column widths
        header = self.cycle_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # #
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Type
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Sample
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Conc.
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Duration
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # Notes
        self.cycle_table.setColumnWidth(0, 40)
        
        # Connect selection signal
        self.cycle_table.itemSelectionChanged.connect(self._on_cycles_selected)
        
        selection_layout.addWidget(self.cycle_table)
        
        # Help text
        help_text = QLabel(
            "💡 Tip: Select multiple cycles (Ctrl+Click) to overlay curves.\n"
            "Use Shift+Click to select a range."
        )
        help_text.setStyleSheet(
            "QLabel {"
            "  font-size: 11px;"
            "  color: #8E8E93;"
            "  background: #F8F9FA;"
            "  padding: 8px 12px;"
            "  border-radius: 6px;"
            "}"
        )
        help_text.setWordWrap(True)
        selection_layout.addWidget(help_text)
        
        panel_layout.addWidget(selection_card)
        
        return panel
    
    def _create_right_panel(self):
        """Create right panel with overlay graph and analysis tools."""
        panel = QFrame()
        panel.setStyleSheet("QFrame { background: transparent; border: none; }")
        
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)
        
        # Overlay Graph Card
        graph_card = QFrame()
        graph_card.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 8px;"
            "}"
        )
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 20))
        graph_card.setGraphicsEffect(shadow)
        
        graph_layout = QVBoxLayout(graph_card)
        graph_layout.setContentsMargins(16, 16, 16, 16)
        graph_layout.setSpacing(12)
        
        # Graph header with controls
        header = self._create_graph_header()
        graph_layout.addWidget(header)
        
        # Overlay graph
        self.overlay_graph = pg.PlotWidget()
        self.overlay_graph.setBackground('#FFFFFF')
        self.overlay_graph.setLabel('left', 'Response (RU)', color='#1D1D1F', size='12pt')
        self.overlay_graph.setLabel('bottom', 'Time (s)', color='#1D1D1F', size='12pt')
        self.overlay_graph.showGrid(x=True, y=True, alpha=0.2)
        self.overlay_graph.setMinimumHeight(500)
        
        # Create curves for each channel (used for single-cycle view)
        channel_colors = [
            (0, 0, 0),        # A: Black
            (255, 0, 0),      # B: Red
            (0, 0, 255),      # C: Blue
            (0, 170, 0),      # D: Green
        ]
        self.overlay_graph_curves = []
        for i in range(4):
            curve = self.overlay_graph.plot(
                pen=pg.mkPen(color=channel_colors[i], width=2),
                name=f"Channel {chr(ord('A')+i)}"
            )
            self.overlay_graph_curves.append(curve)
        
        graph_layout.addWidget(self.overlay_graph)
        
        panel_layout.addWidget(graph_card)
        
        # Kinetic Fitting Panel
        fitting_panel = self._create_fitting_panel()
        panel_layout.addWidget(fitting_panel)
        
        return panel
    
    def _create_graph_header(self):
        """Create graph header with overlay controls."""
        header = QFrame()
        header.setStyleSheet("QFrame { background: transparent; border: none; }")
        
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)
        
        # Title
        title = QLabel("Multi-Cycle Overlay")
        title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "}"
        )
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Channel toggles
        self.channel_toggles = []
        for ch, color in [
            ("A", "#000000"),  # Black
            ("B", "#FF0000"),  # Red
            ("C", "#0000FF"),  # Blue
            ("D", "#00AA00"),  # Green
        ]:
            ch_btn = QPushButton(f"Ch {ch}")
            ch_btn.setCheckable(True)
            ch_btn.setChecked(True)
            ch_btn.setFixedSize(50, 28)
            ch_btn.setProperty('channel_index', len(self.channel_toggles))
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
                "  background: rgba(0, 0, 0, 0.1);"
                "  color: #8E8E93;"
                "}"
                "QPushButton:hover {"
                "  opacity: 0.8;"
                "}"
            )
            ch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            ch_btn.toggled.connect(lambda checked, idx=len(self.channel_toggles): self._toggle_channel(idx, checked))
            header_layout.addWidget(ch_btn)
            self.channel_toggles.append(ch_btn)
        
        # Normalize overlay toggle (t=0 alignment)
        self.normalize_overlay_btn = QPushButton("📊 Align t=0")
        self.normalize_overlay_btn.setCheckable(True)
        self.normalize_overlay_btn.setChecked(True)  # Default enabled
        self.normalize_overlay_btn.setFixedHeight(28)
        self.normalize_overlay_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  color: #8E8E93;"
            "  border: 1px solid rgba(0, 0, 0, 0.08);"
            "  border-radius: 6px;"
            "  padding: 0px 12px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:checked {"
            "  background: rgba(52, 199, 89, 0.15);"
            "  color: #34C759;"
            "  border: 1px solid rgba(52, 199, 89, 0.3);"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
            "QPushButton:checked:hover {"
            "  background: rgba(52, 199, 89, 0.25);"
            "}"
        )
        self.normalize_overlay_btn.setToolTip(
            "Align t=0 for Multi-Cycle Overlay\n"
            "• Checked: All cycles start at t=0 (easy comparison)\n"
            "• Unchecked: Show original timestamps"
        )
        self.normalize_overlay_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.normalize_overlay_btn.toggled.connect(self._on_normalize_toggled)
        header_layout.addWidget(self.normalize_overlay_btn)
        
        return header
    
    def _toggle_channel(self, ch_idx, visible):
        """Toggle channel visibility on overlay graph."""
        logger.info(f"[ANALYSIS] Toggle channel {ch_idx}: {visible}")
        # Will be implemented when we add channel-specific overlay control
        self._on_cycles_selected()  # Redraw with updated channel visibility
    
    def _on_normalize_toggled(self, checked):
        """Handle normalize toggle - redraw graph with/without t=0 alignment."""
        logger.info(f"[ANALYSIS] Normalize overlay: {checked}")
        self._on_cycles_selected()  # Redraw with updated normalization
    
    def _on_cycles_selected(self):
        """Handle cycle selection - plot overlay or single cycle."""
        selected_rows = sorted(set(item.row() for item in self.cycle_table.selectedItems()))
        
        if not selected_rows:
            # Clear graph
            self._clear_overlay()
            return
        
        logger.info(f"[ANALYSIS] Selected {len(selected_rows)} cycles for overlay")
        
        # Get loaded cycles data from main window
        if not hasattr(self.main_window, '_loaded_cycles_data') or not self.main_window._loaded_cycles_data:
            logger.warning("[ANALYSIS] No loaded cycle data available")
            return
        
        # Check which mode: overlay (multiple cycles) or single
        if len(selected_rows) > 1 and self.normalize_overlay_btn.isChecked():
            self._plot_overlay(selected_rows)
        else:
            self._plot_single_or_blend(selected_rows)
    
    def _clear_overlay(self):
        """Clear all overlay curves from graph."""
        # Clear overlay curves
        for curve_set in self.overlay_curves:
            for curve in curve_set:
                try:
                    self.overlay_graph.removeItem(curve)
                except:
                    pass
        self.overlay_curves = []
        
        # Clear main curves
        for curve in self.overlay_graph_curves:
            curve.setData([], [])
    
    def _plot_overlay(self, selected_rows):
        """Plot multiple cycles as overlay with t=0 normalization."""
        import numpy as np
        from pyqtgraph import PlotDataItem
        
        # Clear previous overlays
        self._clear_overlay()
        
        # Conversion factor
        WAVELENGTH_TO_RU = 355.0
        
        # Colors for each channel (with transparency)
        channel_colors = [
            (0, 0, 0, 150),      # Black (A)
            (255, 0, 0, 150),    # Red (B)
            (0, 0, 255, 150),    # Blue (C)
            (0, 170, 0, 150),    # Green (D)
        ]
        
        # Get raw data
        if not hasattr(self.main_window.app, 'recording_mgr') or not self.main_window.app.recording_mgr:
            logger.warning("[ANALYSIS] Recording manager not available")
            return
        
        raw_data = self.main_window.app.recording_mgr.data_collector.raw_data_rows
        if not raw_data:
            logger.warning("[ANALYSIS] No raw data available")
            return
        
        # Process each selected cycle
        for cycle_row in selected_rows:
            if cycle_row >= len(self.main_window._loaded_cycles_data):
                continue
            
            cycle = self.main_window._loaded_cycles_data[cycle_row]
            start_time = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time'))
            end_time = cycle.get('end_time_sensorgram')
            
            # Handle NaN
            import math
            try:
                if start_time is not None and isinstance(start_time, float) and math.isnan(start_time):
                    start_time = None
                if end_time is not None and isinstance(end_time, float) and math.isnan(end_time):
                    end_time = None
            except:
                pass
            
            if start_time is None:
                continue
            
            # Get end time
            if end_time is None:
                duration_min = cycle.get('duration_minutes', cycle.get('length_minutes', 5))
                end_time = start_time + ((duration_min or 5) * 60)
            
            # Collect data for each channel
            cycle_data = {
                'a': {'time': [], 'wavelength': []},
                'b': {'time': [], 'wavelength': []},
                'c': {'time': [], 'wavelength': []},
                'd': {'time': [], 'wavelength': []},
            }
            
            for row_data in raw_data:
                time = row_data.get('elapsed', row_data.get('time', 0))
                if start_time <= time <= end_time:
                    # Normalize to t=0
                    relative_time = time - start_time
                    
                    # Handle both data formats
                    if 'channel' in row_data and 'value' in row_data:
                        ch = row_data.get('channel')
                        value = row_data.get('value')
                        if ch in ['a', 'b', 'c', 'd'] and value is not None:
                            cycle_data[ch]['time'].append(relative_time)
                            cycle_data[ch]['wavelength'].append(value)
                    else:
                        for ch in ['a', 'b', 'c', 'd']:
                            wavelength = row_data.get(f'channel_{ch}', row_data.get(f'wavelength_{ch}'))
                            if wavelength is not None:
                                cycle_data[ch]['time'].append(relative_time)
                                cycle_data[ch]['wavelength'].append(wavelength)
            
            # Plot each channel for this cycle
            curve_set = []
            for i, ch in enumerate(['a', 'b', 'c', 'd']):
                # Check if channel is enabled
                if not self.channel_toggles[i].isChecked():
                    continue
                
                time_data = np.array(cycle_data[ch]['time'])
                wavelength_data = np.array(cycle_data[ch]['wavelength'])
                
                if len(time_data) > 0:
                    # Sort by time
                    sort_indices = np.argsort(time_data)
                    time_data = time_data[sort_indices]
                    wavelength_data = wavelength_data[sort_indices]
                    
                    # Baseline correction and convert to RU
                    baseline = wavelength_data[0]
                    delta_wavelength = wavelength_data - baseline
                    spr_data = delta_wavelength * WAVELENGTH_TO_RU
                    
                    # Create curve
                    curve = PlotDataItem(
                        time_data, spr_data,
                        pen={'color': channel_colors[i], 'width': 2},
                        name=f"Cycle {cycle_row+1} Ch{ch.upper()}"
                    )
                    self.overlay_graph.addItem(curve)
                    curve_set.append(curve)
            
            self.overlay_curves.append(curve_set)
        
        # Auto-scale
        self.overlay_graph.autoRange()
        logger.info(f"[ANALYSIS] Plotted {len(self.overlay_curves)} cycle overlays")
    
    def _plot_single_or_blend(self, selected_rows):
        """Plot single cycle or blend multiple cycles into one dataset."""
        import numpy as np
        
        # Clear overlays
        self._clear_overlay()
        
        # Conversion factor
        WAVELENGTH_TO_RU = 355.0
        
        # Blend all selected cycles
        all_cycle_data = {
            'a': {'time': [], 'wavelength': []},
            'b': {'time': [], 'wavelength': []},
            'c': {'time': [], 'wavelength': []},
            'd': {'time': [], 'wavelength': []},
        }
        
        # Get raw data
        if not hasattr(self.main_window.app, 'recording_mgr') or not self.main_window.app.recording_mgr:
            return
        
        raw_data = self.main_window.app.recording_mgr.data_collector.raw_data_rows
        if not raw_data:
            return
        
        # Collect data from all cycles
        for cycle_row in selected_rows:
            if cycle_row >= len(self.main_window._loaded_cycles_data):
                continue
            
            cycle = self.main_window._loaded_cycles_data[cycle_row]
            start_time = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time'))
            end_time = cycle.get('end_time_sensorgram')
            
            if start_time is None:
                continue
            
            if end_time is None:
                duration_min = cycle.get('duration_minutes', 5)
                end_time = start_time + (duration_min * 60)
            
            for row_data in raw_data:
                time = row_data.get('elapsed', row_data.get('time', 0))
                if start_time <= time <= end_time:
                    relative_time = time - start_time
                    
                    if 'channel' in row_data and 'value' in row_data:
                        ch = row_data.get('channel')
                        value = row_data.get('value')
                        if ch in ['a', 'b', 'c', 'd'] and value is not None:
                            all_cycle_data[ch]['time'].append(relative_time)
                            all_cycle_data[ch]['wavelength'].append(value)
                    else:
                        for ch in ['a', 'b', 'c', 'd']:
                            wavelength = row_data.get(f'channel_{ch}', row_data.get(f'wavelength_{ch}'))
                            if wavelength is not None:
                                all_cycle_data[ch]['time'].append(relative_time)
                                all_cycle_data[ch]['wavelength'].append(wavelength)
        
        # Plot on main curves
        for i, ch in enumerate(['a', 'b', 'c', 'd']):
            if not self.channel_toggles[i].isChecked():
                self.overlay_graph_curves[i].setData([], [])
                continue
            
            time_data = np.array(all_cycle_data[ch]['time'])
            wavelength_data = np.array(all_cycle_data[ch]['wavelength'])
            
            if len(time_data) > 0:
                sort_indices = np.argsort(time_data)
                time_data = time_data[sort_indices]
                wavelength_data = wavelength_data[sort_indices]
                
                baseline = wavelength_data[0]
                delta_wavelength = wavelength_data - baseline
                spr_data = delta_wavelength * WAVELENGTH_TO_RU
                
                self.overlay_graph_curves[i].setData(time_data, spr_data)
            else:
                self.overlay_graph_curves[i].setData([], [])
        
        self.overlay_graph.autoRange()
    
    def populate_cycle_table(self, cycles_data):
        """Populate cycle table with loaded data."""
        self.cycle_table.setRowCount(0)
        
        for i, cycle in enumerate(cycles_data):
            row_idx = self.cycle_table.rowCount()
            self.cycle_table.insertRow(row_idx)
            
            # Cycle number
            num_item = QTableWidgetItem(str(i + 1))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cycle_table.setItem(row_idx, 0, num_item)
            
            # Type
            cycle_type = cycle.get('cycle_type', 'Unknown')
            type_item = QTableWidgetItem(cycle_type)
            self.cycle_table.setItem(row_idx, 1, type_item)
            
            # Sample
            sample = cycle.get('sample_name', '-')
            sample_item = QTableWidgetItem(sample)
            self.cycle_table.setItem(row_idx, 2, sample_item)
            
            # Concentration
            conc = cycle.get('concentration', '-')
            conc_item = QTableWidgetItem(str(conc))
            self.cycle_table.setItem(row_idx, 3, conc_item)
            
            # Duration
            duration = cycle.get('duration_minutes', cycle.get('length_minutes', 0))
            dur_item = QTableWidgetItem(f"{duration} min" if duration else "-")
            self.cycle_table.setItem(row_idx, 4, dur_item)
            
            # Notes
            notes = cycle.get('notes', '')
            notes_item = QTableWidgetItem(notes)
            self.cycle_table.setItem(row_idx, 5, notes_item)
        
        logger.info(f"[ANALYSIS] Populated table with {len(cycles_data)} cycles")
    
    def _create_fitting_panel(self):
        """Create kinetic fitting control panel."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 8px;"
            "}"
        )
        
        # Add shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 20))
        panel.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header_layout = QHBoxLayout()
        title = QLabel("🧬 Kinetic Analysis")
        title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "}"
        )
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Model selection
        model_layout = QHBoxLayout()
        model_label = QLabel("Binding Model:")
        model_label.setStyleSheet("font-size: 12px; color: #1D1D1F;")
        model_layout.addWidget(model_label)
        
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "1:1 Langmuir Binding",
            "1:2 Heterogeneous",
            "Mass Transport Limited",
            "Two-State Conformational Change"
        ])
        self.model_combo.setStyleSheet(
            "QComboBox {"
            "  background: white;"
            "  border: 1px solid #E5E5EA;"
            "  border-radius: 6px;"
            "  padding: 6px 12px;"
            "  font-size: 12px;"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "}"
            "QComboBox::down-arrow {"
            "  image: none;"
            "  border-left: 4px solid transparent;"
            "  border-right: 4px solid transparent;"
            "  border-top: 6px solid #8E8E93;"
            "  margin-right: 8px;"
            "}"
        )
        model_layout.addWidget(self.model_combo, 1)
        layout.addLayout(model_layout)
        
        # Concentration input
        conc_layout = QHBoxLayout()
        conc_label = QLabel("Analyte Conc.:")
        conc_label.setStyleSheet("font-size: 12px; color: #1D1D1F;")
        conc_layout.addWidget(conc_label)
        
        from PySide6.QtWidgets import QLineEdit
        self.conc_input = QLineEdit()
        self.conc_input.setPlaceholderText("e.g., 100 nM")
        self.conc_input.setText("100")
        self.conc_input.setStyleSheet(
            "QLineEdit {"
            "  background: white;"
            "  border: 1px solid #E5E5EA;"
            "  border-radius: 6px;"
            "  padding: 6px 12px;"
            "  font-size: 12px;"
            "}"
        )
        conc_layout.addWidget(self.conc_input, 1)
        
        conc_unit = QComboBox()
        conc_unit.addItems(["nM", "μM", "mM", "M"])
        conc_unit.setCurrentText("nM")
        conc_unit.setStyleSheet(
            "QComboBox {"
            "  background: white;"
            "  border: 1px solid #E5E5EA;"
            "  border-radius: 6px;"
            "  padding: 6px 12px;"
            "  font-size: 12px;"
            "  max-width: 60px;"
            "}"
        )
        conc_layout.addWidget(conc_unit)
        self.conc_unit_combo = conc_unit
        layout.addLayout(conc_layout)
        
        # Fit button
        self.fit_btn = QPushButton("⚡ Fit Kinetics")
        self.fit_btn.setFixedHeight(36)
        self.fit_btn.setStyleSheet(
            "QPushButton {"
            "  background: #007AFF;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover {"
            "  background: #0051D5;"
            "}"
            "QPushButton:pressed {"
            "  background: #004FC4;"
            "}"
            "QPushButton:disabled {"
            "  background: #E5E5EA;"
            "  color: #8E8E93;"
            "}"
        )
        self.fit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fit_btn.clicked.connect(self._fit_kinetics)
        layout.addWidget(self.fit_btn)
        
        # Results display
        self.results_label = QLabel("")
        self.results_label.setWordWrap(True)
        self.results_label.setStyleSheet(
            "QLabel {"
            "  background: #F8F9FA;"
            "  border-radius: 6px;"
            "  padding: 12px;"
            "  font-size: 11px;"
            "  font-family: 'Consolas', 'Monaco', monospace;"
            "  color: #1D1D1F;"
            "}"
        )
        self.results_label.setVisible(False)
        layout.addWidget(self.results_label)
        
        return panel
    
    def _fit_kinetics(self):
        """Fit kinetic model to selected cycle data."""
        from lmfit import Model
        import numpy as np
        
        # Get selected cycles
        selected_rows = sorted(set(item.row() for item in self.cycle_table.selectedItems()))
        if not selected_rows:
            self.results_label.setText("⚠️ No cycles selected")
            self.results_label.setVisible(True)
            return
        
        if len(selected_rows) > 1:
            self.results_label.setText("⚠️ Select only ONE cycle for kinetic fitting")
            self.results_label.setVisible(True)
            return
        
        cycle_idx = selected_rows[0]
        
        # Get concentration
        try:
            conc_value = float(self.conc_input.text())
            unit = self.conc_unit_combo.currentText()
            # Convert to M
            unit_factors = {'nM': 1e-9, 'μM': 1e-6, 'mM': 1e-3, 'M': 1.0}
            conc_M = conc_value * unit_factors[unit]
        except ValueError:
            self.results_label.setText("⚠️ Invalid concentration value")
            self.results_label.setVisible(True)
            return
        
        # Get cycle data
        if not hasattr(self.main_window, '_loaded_cycles_data'):
            self.results_label.setText("⚠️ No data loaded")
            self.results_label.setVisible(True)
            return
        
        cycle = self.main_window._loaded_cycles_data[cycle_idx]
        start_time = cycle.get('start_time_sensorgram')
        end_time = cycle.get('end_time_sensorgram')
        
        if start_time is None:
            self.results_label.setText("⚠️ Cycle missing start time")
            self.results_label.setVisible(True)
            return
        
        if end_time is None:
            duration_min = cycle.get('duration_minutes', 5)
            end_time = start_time + (duration_min * 60)
        
        # Extract data (use first enabled channel)
        raw_data = self.main_window.app.recording_mgr.data_collector.raw_data_rows
        
        # Find first enabled channel
        channel_idx = None
        for i, toggle in enumerate(self.channel_toggles):
            if toggle.isChecked():
                channel_idx = i
                break
        
        if channel_idx is None:
            self.results_label.setText("⚠️ No channels enabled")
            self.results_label.setVisible(True)
            return
        
        ch = chr(ord('a') + channel_idx)
        
        # Collect data
        time_list = []
        wavelength_list = []
        
        for row_data in raw_data:
            time = row_data.get('elapsed', row_data.get('time', 0))
            if start_time <= time <= end_time:
                relative_time = time - start_time
                
                if 'channel' in row_data and 'value' in row_data:
                    if row_data.get('channel') == ch:
                        wavelength = row_data.get('value')
                        if wavelength is not None:
                            time_list.append(relative_time)
                            wavelength_list.append(wavelength)
                else:
                    wavelength = row_data.get(f'channel_{ch}', row_data.get(f'wavelength_{ch}'))
                    if wavelength is not None:
                        time_list.append(relative_time)
                        wavelength_list.append(wavelength)
        
        if len(time_list) < 10:
            self.results_label.setText("⚠️ Insufficient data points")
            self.results_label.setVisible(True)
            return
        
        # Convert to numpy arrays and sort
        time_data = np.array(time_list)
        wavelength_data = np.array(wavelength_list)
        sort_idx = np.argsort(time_data)
        time_data = time_data[sort_idx]
        wavelength_data = wavelength_data[sort_idx]
        
        # Convert to RU (baseline corrected)
        WAVELENGTH_TO_RU = 355.0
        baseline = wavelength_data[0]
        response_data = (wavelength_data - baseline) * WAVELENGTH_TO_RU
        
        # Define 1:1 Langmuir binding model
        def langmuir_binding(t, ka, kd, Rmax, R0):
            """
            1:1 Langmuir binding model (association phase)
            ka: association rate constant (M^-1 s^-1)
            kd: dissociation rate constant (s^-1)
            Rmax: maximum binding capacity (RU)
            R0: baseline offset (RU)
            C: analyte concentration (M)
            """
            keq = ka * conc_M + kd
            Req = Rmax * (ka * conc_M) / keq
            return Req * (1 - np.exp(-keq * t)) + R0
        
        # Create model
        model = Model(langmuir_binding)
        
        # Initial parameter guesses
        params = model.make_params(
            ka=1e5,      # Typical: 10^4 to 10^6 M^-1 s^-1
            kd=1e-3,     # Typical: 10^-4 to 10^-2 s^-1
            Rmax=max(response_data) * 1.2,
            R0=0
        )
        
        # Set bounds
        params['ka'].min = 0
        params['kd'].min = 0
        params['Rmax'].min = 0
        
        try:
            # Fit the model
            result = model.fit(response_data, t=time_data, params=params)
            
            # Extract parameters
            ka = result.params['ka'].value
            ka_err = result.params['ka'].stderr or 0
            kd = result.params['kd'].value
            kd_err = result.params['kd'].stderr or 0
            Rmax = result.params['Rmax'].value
            Rmax_err = result.params['Rmax'].stderr or 0
            
            # Calculate KD (equilibrium dissociation constant)
            KD = kd / ka
            # Error propagation for KD
            KD_err = KD * np.sqrt((kd_err/kd)**2 + (ka_err/ka)**2) if (kd > 0 and ka > 0) else 0
            
            # Display results
            results_text = (
                f"<b>Kinetic Parameters (1:1 Langmuir):</b><br><br>"
                f"ka = {ka:.2e} ± {ka_err:.2e} M⁻¹s⁻¹<br>"
                f"kd = {kd:.2e} ± {kd_err:.2e} s⁻¹<br>"
                f"K<sub>D</sub> = {KD*1e9:.2f} ± {KD_err*1e9:.2f} nM<br>"
                f"R<sub>max</sub> = {Rmax:.1f} ± {Rmax_err:.1f} RU<br><br>"
                f"<b>Goodness of Fit:</b><br>"
                f"R² = {1 - result.residual.var() / np.var(response_data):.4f}<br>"
                f"χ² = {result.chisqr:.2e}"
            )
            
            self.results_label.setText(results_text)
            self.results_label.setVisible(True)
            
            # Plot fitted curve
            fitted_curve = result.best_fit
            
            # Add fitted curve to graph
            if hasattr(self, 'fitted_curve_item'):
                self.overlay_graph.removeItem(self.fitted_curve_item)
            
            self.fitted_curve_item = self.overlay_graph.plot(
                time_data, fitted_curve,
                pen=pg.mkPen(color='#FF9500', width=3, style=Qt.PenStyle.DashLine),
                name="Fitted Model"
            )
            
            logger.info(f"[FIT] ka={ka:.2e}, kd={kd:.2e}, KD={KD*1e9:.2f}nM, Rmax={Rmax:.1f}RU")
            
        except Exception as e:
            logger.exception(f"[FIT] Error fitting kinetics: {e}")
            self.results_label.setText(f"❌ Fit failed: {str(e)}")
            self.results_label.setVisible(True)
            self.cycle_table.setItem(row_idx, 5, notes_item)
        
        logger.info(f"[ANALYSIS] Populated table with {len(cycles_data)} cycles")
