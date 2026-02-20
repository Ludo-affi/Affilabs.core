"""UI Builder Mixin for EditsTab.

Contains all UI construction methods extracted from EditsTab:
- create_content (main layout orchestrator)
- _update_empty_state
- _create_table_panel, _create_metadata_panel, _create_alignment_panel
- _create_active_selection, _create_delta_spr_barchart, _create_tools_panel
"""

import pyqtgraph as pg
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QPushButton,
    QTableWidget, QHeaderView, QAbstractItemView, QSlider,
    QGraphicsDropShadowEffect, QComboBox, QLineEdit, QTableWidgetItem,
    QWidget, QGridLayout, QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from affilabs.utils.logger import logger
from affilabs.ui_styles import Colors, Fonts


class UIBuildersMixin:
    """Mixin providing all UI construction helpers for EditsTab."""

    def create_content(self):
        """Create the Edits tab content with redesigned master-detail timeline layout.

        Returns:
            QFrame: The complete Edits tab content widget
        """
        # Initialize cursor state first
        self.edits_timeline_cursors = {'left': None, 'right': None}
        self.edits_cycle_markers = []
        self.edits_cycle_labels = []

        # Table view state
        self.compact_view = False  # Start in expanded view (default)
        self.cycle_filter = "All"  # Default: show all cycle types
        self._cycle_export_selection = {}  # Track checkbox state: {cycle_idx: True/False}

        # Initialize table widget — 5-column layout with export selection checkboxes
        # STARTS EMPTY - will be populated ONLY when cycles complete during live acquisition
        self.cycle_data_table = QTableWidget(0, 5)
        self.cycle_data_table.setHorizontalHeaderLabels(
            ["Export", "Type", "Time", "Conc.", "ΔSPR"]
        )
        # Set column widths: stretch to fill available space
        header = self.cycle_data_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)       # Export checkbox
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)       # Type icon
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)     # Time
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)     # Conc
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)     # ΔSPR
        self.cycle_data_table.setColumnWidth(0, 50)    # Export checkbox (fixed)
        self.cycle_data_table.setColumnWidth(1, 55)    # Type icon (fixed minimum)

        # Set compact font for better space utilization
        table_font = QFont("-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif")
        table_font.setPointSize(10)
        self.cycle_data_table.setFont(table_font)

        # Reduce row height for compact display
        self.cycle_data_table.verticalHeader().setDefaultSectionSize(22)
        self.cycle_data_table.verticalHeader().setVisible(False)  # Hide row numbers
        # Set header font to match table compact style
        header_font = QFont("-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif")
        header_font.setPointSize(9)
        header_font.setBold(True)
        self.cycle_data_table.horizontalHeader().setFont(header_font)
        self.cycle_data_table.horizontalHeader().setDefaultSectionSize(55)

        # Set column tooltips for better understanding
        tooltips = [
            "Check to include this cycle's chart in export",
            "Cycle type: BL=Baseline, IM=Immobilization, WS=Wash, CN=Concentration, RG=Regeneration, CU=Custom",
            "Duration (minutes) @ Start time (seconds)",
            "Analyte concentration (if applicable)",
            "Delta SPR response for all channels (in RU): A:val B:val C:val D:val",
        ]
        for col, tooltip in enumerate(tooltips):
            self.cycle_data_table.horizontalHeaderItem(col).setToolTip(tooltip)

        self.cycle_data_table.setShowGrid(True)  # Show grid lines
        self.cycle_data_table.setGridStyle(Qt.PenStyle.SolidLine)  # Solid grid lines
        self.cycle_data_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.cycle_data_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cycle_data_table.itemSelectionChanged.connect(self.main_window._on_cycle_selected_in_table)
        self.cycle_data_table.itemSelectionChanged.connect(self._update_export_sidebar_stats)
        self.cycle_data_table.itemSelectionChanged.connect(self._update_details_panel)  # Update Details tabs
        self.cycle_data_table.itemSelectionChanged.connect(self._reset_delta_spr_lock)  # Reset lock on cycle selection

        # Enhanced styling: zebra striping, hover, and selection highlight
        self.cycle_data_table.setAlternatingRowColors(True)
        self.cycle_data_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #FAFAFA;
                selection-background-color: #E3F2FD;
                selection-color: #1D1D1F;
                gridline-color: #E5E5EA;
            }
            QTableWidget::item:hover {
                background-color: #F0F7FF;
            }
            QTableWidget::item:selected {
                background-color: #D1E9FF;
                color: #1D1D1F;
                font-weight: 600;
            }
            QHeaderView::section {
                background-color: #F8F9FA;
                color: #1D1D1F;
                font-weight: 600;
                border: 1px solid #E5E5EA;
                padding: 6px;
            }
        """)

        # Enable context menu on header for column visibility
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_column_visibility_menu)

        # Enable context menu for loading cycles to reference graphs
        self.cycle_data_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cycle_data_table.customContextMenuRequested.connect(self._on_table_context_menu)

        # Initialize primary graph (needed by selection panel)
        self.edits_primary_graph = pg.PlotWidget()
        self.edits_primary_graph.setMenuEnabled(True)  # Enable context menu for export options
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

        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 12, 12, 12)  # Increased from 8 for more breathing room
        content_layout.setSpacing(12)  # Increased from 8 for better visual separation

        # Main content container with optional export sidebar
        outer_layout = QHBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Main horizontal split: Table LEFT | Graphs RIGHT
        main_splitter = QSplitter(Qt.Horizontal)

        # LEFT SIDE: Vertical split (Table TOP | Bottom Panels BOTTOM)
        left_splitter = QSplitter(Qt.Vertical)

        # LEFT TOP: Cycle table with details tabs
        from PySide6.QtWidgets import QTabWidget
        table_details_widget = QFrame()
        table_details_layout = QVBoxLayout(table_details_widget)
        table_details_layout.setContentsMargins(0, 0, 0, 0)
        table_details_layout.setSpacing(8)

        table_widget = self._create_table_panel()
        table_details_layout.addWidget(table_widget, 1)

        # Details tab widget (Flags & Notes)
        self.details_tab_widget = QTabWidget()
        self.details_tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #D1D1D6; }
            QTabBar::tab { padding: 4px 12px; background: white; color: #1D1D1F; }
            QTabBar::tab:selected { background: #E3F2FD; color: #0066CC; font-weight: 600; }
            QTabBar::tab:hover { background: #F5F5F5; }
        """)

        # Flags tab
        self.details_flags_text = QLabel("")
        self.details_flags_text.setWordWrap(True)
        self.details_flags_text.setStyleSheet("QLabel { padding: 8px; color: #1D1D1F; font-size: 12px; }")
        flags_scroll = QScrollArea()
        flags_scroll.setWidget(self.details_flags_text)
        flags_scroll.setWidgetResizable(True)
        self.details_tab_widget.addTab(flags_scroll, "Flags")

        # Notes tab
        self.details_notes_text = QLabel("")
        self.details_notes_text.setWordWrap(True)
        self.details_notes_text.setStyleSheet("QLabel { padding: 8px; color: #1D1D1F; font-size: 12px; }")
        notes_scroll = QScrollArea()
        notes_scroll.setWidget(self.details_notes_text)
        notes_scroll.setWidgetResizable(True)
        self.details_tab_widget.addTab(notes_scroll, "Notes")

        self.details_tab_widget.setMaximumHeight(120)
        table_details_layout.addWidget(self.details_tab_widget)

        left_splitter.addWidget(table_details_widget)

        # LEFT BOTTOM: Metadata and Alignment panels side by side
        bottom_left_widget = QFrame()
        bottom_left_layout = QHBoxLayout(bottom_left_widget)
        bottom_left_layout.setContentsMargins(0, 0, 0, 0)
        bottom_left_layout.setSpacing(8)

        # Metadata panel
        metadata_panel = self._create_metadata_panel()
        bottom_left_layout.addWidget(metadata_panel, 1)

        # Alignment panel
        self.alignment_panel = self._create_alignment_panel()
        bottom_left_layout.addWidget(self.alignment_panel, 1)
        self.alignment_panel.hide()  # Hidden until cycle selected

        left_splitter.addWidget(bottom_left_widget)

        # Set vertical proportions for left side: 70% table, 30% bottom panels
        left_splitter.setStretchFactor(0, 70)
        left_splitter.setStretchFactor(1, 30)

        main_splitter.addWidget(left_splitter)

        # RIGHT: Graphs (70% width)
        graphs_splitter = QSplitter(Qt.Vertical)

        # TOP: Active Cycle View with cursors (70%)
        selection_widget = self._create_active_selection()
        graphs_splitter.addWidget(selection_widget)

        # BOTTOM: Delta SPR Bar Chart (30%)
        barchart_widget = self._create_delta_spr_barchart()
        graphs_splitter.addWidget(barchart_widget)

        # Set vertical proportions: 70:30
        graphs_splitter.setStretchFactor(0, 70)
        graphs_splitter.setStretchFactor(1, 30)

        main_splitter.addWidget(graphs_splitter)

        # Set horizontal proportions: 50:50 (left:right)
        main_splitter.setStretchFactor(0, 50)
        main_splitter.setStretchFactor(1, 50)

        # Set minimum widths
        main_splitter.setMinimumWidth(800)
        table_widget.setMinimumWidth(300)

        # Export sidebar (collapsible left panel — consistent with main sidebar position)
        self.export_sidebar = self._create_export_sidebar()
        self.export_sidebar.setVisible(True)  # Visible by default
        outer_layout.addWidget(self.export_sidebar)

        outer_layout.addWidget(main_splitter, 1)

        content_layout.addLayout(outer_layout)

        # Apply default view settings (compact mode + binding filter)
        self._apply_compact_view_initial()

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

    def _update_empty_state(self):
        """Show/hide empty state message based on table row count."""
        if hasattr(self, 'empty_state_widget') and hasattr(self, 'cycle_data_table'):
            has_data = self.cycle_data_table.rowCount() > 0
            self.empty_state_widget.setVisible(not has_data)
            self.cycle_data_table.setVisible(has_data)

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

        # Header
        header = QHBoxLayout()
        title = QLabel("Cycles Recorded")
        title.setStyleSheet(
            f"font-size: 15px; font-weight: 600; color: {Colors.PRIMARY_TEXT}; "
            f"font-family: {Fonts.DISPLAY};"
        )
        header.addWidget(title)
        header.addStretch()

        # Units reference
        units_label = QLabel("ΔSPR in RU")
        units_label.setStyleSheet(
            f"font-size: 10px; color: {Colors.SECONDARY_TEXT}; font-weight: 500; "
            f"font-family: {Fonts.SYSTEM};"
        )
        header.addWidget(units_label)

        layout.addLayout(header)

        # View and filter controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        # Load button (matching control style)
        load_btn = QPushButton("📂 Load")
        load_btn.setFixedHeight(28)
        load_btn.setStyleSheet(
            f"QPushButton {{ background: {Colors.BACKGROUND_LIGHT}; color: {Colors.PRIMARY_TEXT}; "
            f"border: 1px solid {Colors.OVERLAY_LIGHT_20}; border-radius: 6px; "
            f"font-size: 11px; font-weight: 500; padding: 4px 10px; font-family: {Fonts.SYSTEM}; }}"
            f"QPushButton:hover {{ background: {Colors.OVERLAY_LIGHT_10}; border-color: {Colors.INFO}; }}"
        )
        load_btn.clicked.connect(self._load_data_from_excel_with_path_tracking)
        controls_layout.addWidget(load_btn)

        # Filter dropdown
        filter_label = QLabel("Show:")
        filter_label.setStyleSheet(
            f"font-size: 11px; color: {Colors.SECONDARY_TEXT}; font-family: {Fonts.SYSTEM};"
        )
        controls_layout.addWidget(filter_label)

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All")  # Initial placeholder - will be updated when data loads
        self.filter_combo.setCurrentText("All")
        self.filter_combo.setFixedHeight(28)
        self.filter_combo.setStyleSheet(
            f"QComboBox {{ background: white; border: 1px solid {Colors.OVERLAY_LIGHT_20}; "
            f"border-radius: 6px; font-size: 11px; padding: 4px 8px; min-width: 120px; "
            f"font-family: {Fonts.SYSTEM}; }}"
            f"QComboBox:hover {{ border: 1px solid {Colors.INFO}; }}"
            f"QComboBox::drop-down {{ border: none; }}"
        )
        self.filter_combo.currentTextChanged.connect(self._apply_cycle_filter)
        controls_layout.addWidget(self.filter_combo)

        # Search box
        from PySide6.QtWidgets import QLineEdit
        search_label = QLabel("🔍")
        search_label.setStyleSheet(f"font-size: 12px; color: {Colors.SECONDARY_TEXT};")
        controls_layout.addWidget(search_label)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.search_box.setFixedHeight(28)
        self.search_box.setFixedWidth(150)
        self.search_box.setStyleSheet(
            f"QLineEdit {{ background: white; border: 1px solid {Colors.OVERLAY_LIGHT_20}; "
            f"border-radius: 6px; font-size: 11px; padding: 4px 8px; font-family: {Fonts.SYSTEM}; }}"
            f"QLineEdit:focus {{ border: 1px solid {Colors.INFO}; }}"
        )
        self.search_box.setToolTip("Search across all columns")
        self.search_box.textChanged.connect(self._apply_search_filter)
        controls_layout.addWidget(self.search_box)

        controls_layout.addStretch()

        # Columns visibility button (store reference for menu positioning)
        self.columns_btn = QPushButton("☰")
        self.columns_btn.setFixedSize(28, 28)
        self.columns_btn.setStyleSheet(
            f"QPushButton {{ background: {Colors.BACKGROUND_LIGHT}; color: {Colors.PRIMARY_TEXT}; "
            f"border: 1px solid {Colors.OVERLAY_LIGHT_20}; border-radius: 6px; "
            f"font-size: 14px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {Colors.OVERLAY_LIGHT_10}; border-color: {Colors.INFO}; }}"
        )
        self.columns_btn.setToolTip("Show/hide table columns")
        self.columns_btn.clicked.connect(self._show_columns_menu)
        controls_layout.addWidget(self.columns_btn)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # Table
        # Empty state message (shown when table has no data)
        self.empty_state_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_state_widget)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_icon = QLabel("📊")
        empty_icon.setStyleSheet("font-size: 48px;")
        empty_icon.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_icon)
        empty_text = QLabel("No cycles to display")
        empty_text.setStyleSheet(
            f"font-size: 16px; font-weight: 600; color: {Colors.SECONDARY_TEXT}; "
            f"margin-top: 12px; font-family: {Fonts.DISPLAY};"
        )
        empty_text.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_text)
        empty_subtext = QLabel("Start a recording or load data to begin")
        empty_subtext.setStyleSheet(
            f"font-size: 13px; color: {Colors.SECONDARY_TEXT}; margin-top: 4px; "
            f"font-family: {Fonts.SYSTEM}; opacity: 0.7;"
        )
        empty_subtext.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_subtext)
        self.empty_state_widget.hide()  # Hidden by default

        layout.addWidget(self.empty_state_widget)
        layout.addWidget(self.cycle_data_table)

        return container

    def _create_metadata_panel(self):
        """Create metadata info panel showing experiment statistics."""
        panel = QFrame()
        panel.setStyleSheet("QFrame { background: white; border-radius: 12px; }")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        panel.setGraphicsEffect(shadow)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Title
        title = QLabel("Experiment Metadata")
        title.setStyleSheet("""
            font-size: 15px;
            font-weight: 600;
            color: #1D1D1F;
            border: none;
            background: transparent;
        """)
        layout.addWidget(title)

        # Stats grid with proper alignment
        stats_widget = QWidget()
        stats_widget.setStyleSheet("background: transparent; border: none;")
        grid = QGridLayout(stats_widget)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)

        # Method
        method_lbl = QLabel("Method:")
        method_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        self.meta_method = QLabel("-")
        self.meta_method.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        grid.addWidget(method_lbl, 0, 0, Qt.AlignLeft)
        grid.addWidget(self.meta_method, 0, 1, Qt.AlignLeft)

        # Cycles
        cycles_lbl = QLabel("Cycles:")
        cycles_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        self.meta_total_cycles = QLabel("0")
        self.meta_total_cycles.setStyleSheet("font-size: 12px; color: #007AFF; background: transparent; border: none;")
        grid.addWidget(cycles_lbl, 1, 0, Qt.AlignLeft)
        grid.addWidget(self.meta_total_cycles, 1, 1, Qt.AlignLeft)

        # Types
        types_lbl = QLabel("Types:")
        types_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        self.meta_cycle_types = QLabel("-")
        self.meta_cycle_types.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        grid.addWidget(types_lbl, 2, 0, Qt.AlignLeft)
        grid.addWidget(self.meta_cycle_types, 2, 1, Qt.AlignLeft)

        # Concentration
        conc_lbl = QLabel("Conc. Range:")
        conc_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        self.meta_conc_range = QLabel("-")
        self.meta_conc_range.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        grid.addWidget(conc_lbl, 3, 0, Qt.AlignLeft)
        grid.addWidget(self.meta_conc_range, 3, 1, Qt.AlignLeft)

        # Date
        date_lbl = QLabel("Date:")
        date_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        self.meta_date = QLabel("-")
        self.meta_date.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        grid.addWidget(date_lbl, 4, 0, Qt.AlignLeft)
        grid.addWidget(self.meta_date, 4, 1, Qt.AlignLeft)

        # Operator (matches Method Builder terminology)
        operator_lbl = QLabel("Operator:")
        operator_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        self.meta_operator = QLabel("-")
        self.meta_operator.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        grid.addWidget(operator_lbl, 5, 0, Qt.AlignLeft)
        grid.addWidget(self.meta_operator, 5, 1, Qt.AlignLeft)

        # Device
        device_lbl = QLabel("Device:")
        device_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        self.meta_device = QLabel("-")
        self.meta_device.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        grid.addWidget(device_lbl, 6, 0, Qt.AlignLeft)
        grid.addWidget(self.meta_device, 6, 1, Qt.AlignLeft)

        layout.addWidget(stats_widget)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("border: none; background: #E5E5EA; max-height: 1px;")
        layout.addWidget(divider)

        # Sensor input row
        sensor_layout = QHBoxLayout()
        sensor_layout.setSpacing(10)

        sensor_label = QLabel("Sensor:")
        sensor_label.setStyleSheet("font-size: 12px; color: #1D1D1F; font-weight: 500; background: transparent; border: none;")
        sensor_layout.addWidget(sensor_label)

        self.sensor_input = QLineEdit()
        self.sensor_input.setPlaceholderText("Enter sensor type...")
        self.sensor_input.setFixedHeight(28)
        self.sensor_input.setStyleSheet("""
            QLineEdit {
                background: #F8F9FA;
                border: 1px solid #D1D1D6;
                border-radius: 5px;
                font-size: 12px;
                padding: 4px 8px;
                color: #1D1D1F;
            }
            QLineEdit:focus {
                border: 1px solid #007AFF;
                background: white;
            }
        """)
        sensor_layout.addWidget(self.sensor_input, 1)

        layout.addLayout(sensor_layout)
        layout.addStretch()

        return panel

    def _create_alignment_panel(self):
        """Create alignment controls panel (shown when cycle selected)."""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 8px;
                border: 1px solid #E5E5EA;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Title
        self.alignment_title = QLabel("Cycle Details")
        self.alignment_title.setStyleSheet("""
            font-size: 13px;
            font-weight: 600;
            color: #1D1D1F;
            border: none;
            background: transparent;
        """)
        layout.addWidget(self.alignment_title)

        # Info grid
        info_widget = QWidget()
        info_widget.setStyleSheet("background: transparent; border: none;")
        grid = QGridLayout(info_widget)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)

        # Start Time
        start_lbl = QLabel("Start Time:")
        start_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        self.alignment_start_time = QLabel("0.00 s")
        self.alignment_start_time.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        grid.addWidget(start_lbl, 0, 0, Qt.AlignLeft)
        grid.addWidget(self.alignment_start_time, 0, 1, Qt.AlignLeft)

        # End Time
        end_lbl = QLabel("End Time:")
        end_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        self.alignment_end_time = QLabel("0.00 s")
        self.alignment_end_time.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        grid.addWidget(end_lbl, 1, 0, Qt.AlignLeft)
        grid.addWidget(self.alignment_end_time, 1, 1, Qt.AlignLeft)

        # Flags
        flags_lbl = QLabel("Flags:")
        flags_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        self.alignment_flags_display = QLabel("None")
        self.alignment_flags_display.setStyleSheet("font-size: 12px; color: #34C759; background: transparent; border: none;")
        grid.addWidget(flags_lbl, 2, 0, Qt.AlignLeft)
        grid.addWidget(self.alignment_flags_display, 2, 1, Qt.AlignLeft)

        layout.addWidget(info_widget)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("border: none; background: #E5E5EA; max-height: 1px;")
        layout.addWidget(divider)

        # Reference subtraction section
        ref_title = QLabel("Reference Subtraction")
        ref_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #1D1D1F; background: transparent; border: none;")
        layout.addWidget(ref_title)

        ref_layout = QHBoxLayout()
        ref_layout.setSpacing(10)
        ref_lbl = QLabel("Ref:")
        ref_lbl.setStyleSheet("font-size: 12px; color: #1D1D1F; font-weight: 500; background: transparent; border: none;")
        ref_layout.addWidget(ref_lbl)

        self.alignment_ref_combo = QComboBox()
        self.alignment_ref_combo.addItems(["Global", "None", "Ch A", "Ch B", "Ch C", "Ch D"])
        self.alignment_ref_combo.setToolTip(
            "Reference channel for this cycle.\n"
            "'Global' uses the toolbar Ref setting.\n"
            "'None' disables subtraction for this cycle."
        )
        self.alignment_ref_combo.setStyleSheet("""
            QComboBox {
                background: #F8F9FA;
                border: 1px solid #D1D1D6;
                border-radius: 5px;
                font-size: 12px;
                padding: 4px 8px;
                min-width: 80px;
            }
            QComboBox:focus {
                border: 1px solid #007AFF;
                background: white;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        ref_layout.addWidget(self.alignment_ref_combo)
        self.alignment_ref_combo.currentTextChanged.connect(self._on_cycle_ref_changed)
        ref_layout.addStretch()
        layout.addLayout(ref_layout)

        # Divider before alignment
        divider2 = QFrame()
        divider2.setFrameShape(QFrame.HLine)
        divider2.setStyleSheet("border: none; background: #E5E5EA; max-height: 1px;")
        layout.addWidget(divider2)

        # Alignment section
        align_title = QLabel("Alignment")
        align_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #1D1D1F; background: transparent; border: none;")
        layout.addWidget(align_title)

        # Channel selector
        ch_layout = QHBoxLayout()
        ch_layout.setSpacing(10)
        ch_label = QLabel("Channel:")
        ch_label.setStyleSheet("font-size: 12px; color: #1D1D1F; font-weight: 500; background: transparent; border: none;")
        ch_layout.addWidget(ch_label)

        self.alignment_channel_combo = QComboBox()
        self.alignment_channel_combo.addItems(["All", "A", "B", "C", "D"])
        self.alignment_channel_combo.setStyleSheet("""
            QComboBox {
                background: #F8F9FA;
                border: 1px solid #D1D1D6;
                border-radius: 5px;
                font-size: 12px;
                padding: 4px 8px;
                min-width: 80px;
            }
            QComboBox:focus {
                border: 1px solid #007AFF;
                background: white;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        ch_layout.addWidget(self.alignment_channel_combo)
        ch_layout.addStretch()
        layout.addLayout(ch_layout)

        # Shift controls - Add slider alongside input
        shift_layout = QVBoxLayout()
        shift_layout.setSpacing(6)

        # Shift label and input row
        shift_input_row = QHBoxLayout()
        shift_input_row.setSpacing(10)
        shift_label = QLabel("Shift:")
        shift_label.setStyleSheet("font-size: 12px; color: #1D1D1F; font-weight: 500; background: transparent; border: none;")
        shift_input_row.addWidget(shift_label)

        self.alignment_shift_input = QLineEdit("0.0")
        self.alignment_shift_input.setFixedWidth(80)
        self.alignment_shift_input.setStyleSheet("""
            QLineEdit {
                background: #F8F9FA;
                border: 1px solid #D1D1D6;
                border-radius: 5px;
                font-size: 12px;
                padding: 4px 8px;
            }
            QLineEdit:focus {
                border: 1px solid #007AFF;
                background: white;
            }
        """)
        self.alignment_shift_input.textChanged.connect(self._on_shift_input_changed)
        shift_input_row.addWidget(self.alignment_shift_input)

        unit_lbl = QLabel("s")
        unit_lbl.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        shift_input_row.addWidget(unit_lbl)
        shift_input_row.addStretch()
        shift_layout.addLayout(shift_input_row)

        # Slider for fine adjustment (-20s to +20s)
        self.alignment_shift_slider = QSlider(Qt.Horizontal)
        self.alignment_shift_slider.setRange(-200, 200)  # -20.0s to +20.0s (in 0.1s increments)
        self.alignment_shift_slider.setValue(0)
        self.alignment_shift_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #D1D1D6;
                height: 6px;
                background: #F8F9FA;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #007AFF;
                border: 2px solid #007AFF;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #0051D5;
                border: 2px solid #0051D5;
            }
        """)
        self.alignment_shift_slider.valueChanged.connect(self._on_shift_slider_changed)
        shift_layout.addWidget(self.alignment_shift_slider)

        # Hint label
        hint_lbl = QLabel("💡 Drag slider for real-time alignment (±20s)")
        hint_lbl.setStyleSheet("font-size: 10px; color: #86868B; font-style: italic; background: transparent; border: none;")
        shift_layout.addWidget(hint_lbl)

        layout.addLayout(shift_layout)

        layout.addStretch()

        return panel

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

        # Channel toggles - store references for colorblind palette updates
        self.edits_channel_buttons = {}
        # Standard colors (will be updated by global colorblind setting if enabled)
        standard_colors = ["#1D1D1F", "#FF3B30", "#007AFF", "#34C759"]

        for i, ch in enumerate(["A", "B", "C", "D"]):
            ch_btn = QPushButton(f"Ch {ch}")
            ch_btn.setCheckable(True)
            ch_btn.setChecked(True)
            ch_btn.setFixedSize(40, 24)
            color = standard_colors[i]
            ch_btn.setStyleSheet(
                f"QPushButton {{ background: {color}; color: white; border: none; "
                f"border-radius: 4px; font-size: 11px; font-weight: 600; }}"
                "QPushButton:!checked { background: rgba(0, 0, 0, 0.06); color: #86868B; }"
            )
            ch_idx = ord(ch) - ord('A')
            ch_btn.toggled.connect(lambda checked, idx=ch_idx: self._toggle_channel(idx, checked))
            self.edits_channel_buttons[ch] = ch_btn
            header.addWidget(ch_btn)

        # Reset view button
        reset_btn = QPushButton("⟲ Reset")
        reset_btn.setFixedSize(60, 24)
        reset_btn.setToolTip("Reset graph to full view")
        reset_btn.setStyleSheet("""
            QPushButton {
                background: #F8F9FA;
                color: #1D1D1F;
                border: 1px solid #D1D1D6;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #E5E5EA;
                border: 1px solid #007AFF;
            }
        """)
        reset_btn.clicked.connect(lambda: self.edits_primary_graph.autoRange())
        header.addWidget(reset_btn)

        header.addStretch()
        layout.addLayout(header)

        # Selection graph (reuse existing primary graph)
        self.edits_primary_graph.setBackground('w')
        self.edits_primary_graph.showGrid(x=True, y=True, alpha=0.2)

        # Add Delta SPR measurement cursors (start/stop)
        self.delta_spr_start_cursor = pg.InfiniteLine(
            pos=0, angle=90, movable=True,
            pen=pg.mkPen(color='#34C759', width=2, style=Qt.PenStyle.DashLine),
            label='Start', labelOpts={'position': 0.85, 'color': '#34C759'}
        )
        self.delta_spr_stop_cursor = pg.InfiniteLine(
            pos=100, angle=90, movable=True,
            pen=pg.mkPen(color='#FF3B30', width=2, style=Qt.PenStyle.DashLine),
            label='Stop', labelOpts={'position': 0.85, 'color': '#FF3B30'}
        )
        self.edits_primary_graph.addItem(self.delta_spr_start_cursor)
        self.edits_primary_graph.addItem(self.delta_spr_stop_cursor)

        # Connect cursor movement to Delta SPR calculation
        self.delta_spr_start_cursor.sigPositionChanged.connect(self._update_delta_spr_barchart)
        self.delta_spr_stop_cursor.sigPositionChanged.connect(self._update_delta_spr_barchart)

        layout.addWidget(self.edits_primary_graph)

        return container

    def _create_delta_spr_barchart(self):
        """Create Delta SPR bar chart showing channel responses."""
        container = QFrame()
        container.setStyleSheet("QFrame { background: white; border-radius: 12px; }")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel("ΔSPR (RU) - Response Between Cursors")
        title.setStyleSheet("font-size: 15px; font-weight: 600; color: #1D1D1F;")
        header.addWidget(title)
        header.addStretch()

        # Lock/Unlock cursor button
        self.delta_spr_lock_btn = QPushButton("🔓 Unlock")
        self.delta_spr_lock_btn.setFixedSize(80, 24)
        self.delta_spr_lock_btn.setCheckable(True)
        self.delta_spr_lock_btn.setToolTip("Lock cursors to contact_time + 10% for consistent delta SPR measurement")
        self.delta_spr_lock_btn.setStyleSheet("""
            QPushButton {
                background: #F8F9FA;
                color: #1D1D1F;
                border: 1px solid #D1D1D6;
                border-radius: 5px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #E5E5EA;
                border: 1px solid #007AFF;
            }
            QPushButton:checked {
                background: #34C759;
                color: white;
                border: 1px solid #2DB04E;
            }
        """)
        self.delta_spr_lock_btn.toggled.connect(self._toggle_delta_spr_lock)
        header.addWidget(self.delta_spr_lock_btn)

        # Reset bar chart button
        reset_bar_btn = QPushButton("⟲")
        reset_bar_btn.setFixedSize(28, 24)
        reset_bar_btn.setToolTip("Reset bar chart view")
        reset_bar_btn.setStyleSheet("""
            QPushButton {
                background: #F8F9FA;
                color: #1D1D1F;
                border: 1px solid #D1D1D6;
                border-radius: 5px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #E5E5EA;
                border: 1px solid #007AFF;
            }
        """)
        reset_bar_btn.clicked.connect(lambda: self.delta_spr_barchart.autoRange())
        header.addWidget(reset_bar_btn)

        layout.addLayout(header)

        # Bar chart
        self.delta_spr_barchart = pg.PlotWidget()
        self.delta_spr_barchart.setMenuEnabled(True)  # Enable context menu for export options
        self.delta_spr_barchart.setBackground('w')
        self.delta_spr_barchart.setYRange(0, 100)
        self.delta_spr_barchart.getAxis('bottom').setTicks([[(0, 'Ch A'), (1, 'Ch B'), (2, 'Ch C'), (3, 'Ch D')]])
        self.delta_spr_barchart.setLabel('left', 'ΔSPR (RU)')
        self.delta_spr_barchart.setFixedHeight(220)
        self.delta_spr_barchart.showGrid(y=True, alpha=0.2)

        # Add baseline indicator at y=0
        baseline = pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen(color='#86868B', width=1, style=Qt.DashLine))
        self.delta_spr_barchart.addItem(baseline)

        # Create bar graph items — colors MUST match sensorgram curve colors
        self.delta_spr_bars = []
        from affilabs.plot_helpers import CHANNEL_COLORS, CHANNEL_COLORS_COLORBLIND

        colorblind_enabled = (
            hasattr(self.main_window, 'colorblind_check') and
            self.main_window.colorblind_check.isChecked()
        )
        bar_colors = CHANNEL_COLORS_COLORBLIND if colorblind_enabled else CHANNEL_COLORS

        for i, color in enumerate(bar_colors):
            bar = pg.BarGraphItem(x=[i], height=[0], width=0.6, brush=pg.mkColor(color))
            self.delta_spr_barchart.addItem(bar)
            self.delta_spr_bars.append(bar)

        # Create text items for value labels
        self.delta_spr_labels = []
        for i in range(4):
            text = pg.TextItem(text='0.0', anchor=(0.5, 1.2), color='#1D1D1F')
            text.setFont(QFont('-apple-system', 10, QFont.Bold))
            self.delta_spr_barchart.addItem(text)
            self.delta_spr_labels.append(text)

        layout.addWidget(self.delta_spr_barchart)

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

        layout.addSpacing(12)

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
