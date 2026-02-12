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
    QComboBox, QDoubleSpinBox, QCheckBox, QLineEdit, QTableWidgetItem, QWidget,
    QGridLayout, QScrollArea, QApplication
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QFont, QCursor
import pyqtgraph as pg
import pandas as pd
import numpy as np

from affilabs.utils.logger import logger
from affilabs.widgets.ui_constants import CycleTypeStyle


class EditsTab:
    """Handles the Edits tab UI and logic."""

    def __init__(self, main_window):
        """Initialize Edits tab with reference to main window.

        Args:
            main_window: AffilabsMainWindow instance
        """
        self.main_window = main_window

        # Get shared user profile manager from main app
        self.user_manager = None
        if hasattr(main_window, 'app') and hasattr(main_window.app, 'user_profile_manager'):
            self.user_manager = main_window.app.user_profile_manager

        # Loaded metadata from Excel file (populated when loading file)
        self._loaded_metadata = {}

        # Per-cycle editing state
        self._cycle_alignment = {}  # {row_idx: {'channel': str, 'shift': float}}

        # Injection detection system (auto-detect + manual correction)
        self._injection_points = {}  # {row_idx: {'time': float, 'auto': bool, 'confidence': float}}
        self._injection_marker = None  # Draggable line on graph showing injection point
        self._auto_detect_enabled = True  # Auto-detection enabled by default

        # Flags system for marking/annotating graph points
        self._edits_flags = []
        self._selected_flag_idx = None

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

    def _ensure_experiment_folder(self):
        """Ensure an experiment folder exists, creating one if needed.

        Returns:
            Path to experiment folder, or None if user cancels
        """
        from pathlib import Path
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        from affilabs.services.user_profile_manager import UserProfileManager

        # Check if we already have an active experiment folder
        if (hasattr(self.main_window, 'app') and
            hasattr(self.main_window.app, 'current_experiment_folder') and
            self.main_window.app.current_experiment_folder):
            return self.main_window.app.current_experiment_folder

        # Prompt user for experiment name
        experiment_name, ok = QInputDialog.getText(
            self.main_window,
            "Create Experiment Folder",
            "Enter experiment name:",
            text="Experiment"
        )

        if not ok or not experiment_name.strip():
            # User cancelled or entered empty name
            logger.info("User cancelled experiment folder creation")
            return None

        # Get user profile
        if not self.user_manager:
            # Fallback: try to get from main app if not set in __init__
            if hasattr(self.main_window, 'app') and hasattr(self.main_window.app, 'user_profile_manager'):
                self.user_manager = self.main_window.app.user_profile_manager

        if self.user_manager:
            user_name = self.user_manager.get_current_user()
        else:
            # Last resort fallback
            from affilabs.services.user_profile_manager import UserProfileManager
            user_manager = UserProfileManager()
            user_name = user_manager.get_current_user()

        # Get device ID
        device_id = "Unknown"
        if hasattr(self.main_window, 'app') and hasattr(self.main_window.app, 'device_config'):
            device_id = self.main_window.app.device_config.device_serial

        # Create experiment folder
        try:
            exp_folder = self.main_window.app.experiment_folder_mgr.create_experiment_folder(
                experiment_name=experiment_name.strip(),
                user_name=user_name,
                device_id=device_id,
                sensor_type="",  # Could be populated from device config if available
                description=""
            )

            # Store as current experiment folder
            self.main_window.app.current_experiment_folder = exp_folder

            logger.info(f"✓ Created experiment folder: {exp_folder.name}")
            return exp_folder

        except Exception as e:
            logger.error(f"Failed to create experiment folder: {e}")
            QMessageBox.warning(
                self.main_window,
                "Folder Creation Failed",
                f"Could not create experiment folder:\n{str(e)}"
            )
            return None

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
        self.cycle_filter = "Binding (High)"  # Default: show only concentration/binding cycles

        # Initialize table widget — compact 6-column layout
        # STARTS EMPTY - will be populated ONLY when cycles complete during live acquisition
        self.cycle_data_table = QTableWidget(0, 6)
        self.cycle_data_table.setHorizontalHeaderLabels(
            ["Type", "Time", "Conc.", "ΔSPR", "Flags", "Notes"]
        )
        # Set column widths: stretch to fill available space
        header = self.cycle_data_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)       # Type icon
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)     # Time
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)     # Conc
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)     # ΔSPR
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)     # Flags
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)     # Notes
        self.cycle_data_table.setColumnWidth(0, 55)    # Type icon (fixed minimum)

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
            "Cycle type: BL=Baseline, IM=Immobilization, WS=Wash, CN=Concentration, RG=Regeneration, CU=Custom",
            "Duration (minutes) @ Start time (seconds)",
            "Analyte concentration (if applicable)",
            "Delta SPR response for all channels (in RU): A:val B:val C:val D:val",
            "Event flags (injection ▲, wash ■, spike ◆) with times",
            "Custom notes or comments for this cycle",
        ]
        for col, tooltip in enumerate(tooltips):
            self.cycle_data_table.horizontalHeaderItem(col).setToolTip(tooltip)

        self.cycle_data_table.setShowGrid(True)  # Show grid lines
        self.cycle_data_table.setGridStyle(Qt.PenStyle.SolidLine)  # Solid grid lines
        self.cycle_data_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.cycle_data_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cycle_data_table.itemSelectionChanged.connect(self.main_window._on_cycle_selected_in_table)
        self.cycle_data_table.itemSelectionChanged.connect(self._update_export_sidebar_stats)
        self.cycle_data_table.itemSelectionChanged.connect(self._run_injection_detection)  # Auto-detect on selection

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

        # LEFT TOP: Cycle table
        table_widget = self._create_table_panel()
        left_splitter.addWidget(table_widget)

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
        title.setStyleSheet("font-size: 15px; font-weight: 600; color: #1D1D1F;")
        header.addWidget(title)
        header.addStretch()

        # Units reference
        units_label = QLabel("ΔSPR in RU")
        units_label.setStyleSheet("font-size: 10px; color: #86868B; font-weight: 500;")
        header.addWidget(units_label)

        layout.addLayout(header)

        # View and filter controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        # Load button (matching control style)
        load_btn = QPushButton("📂 Load")
        load_btn.setFixedHeight(28)
        load_btn.setStyleSheet(
            "QPushButton { background: #F5F5F7; color: #1D1D1F; border: 1px solid #D1D1D6; "
            "border-radius: 6px; font-size: 11px; font-weight: 500; padding: 4px 10px; }"
            "QPushButton:hover { background: #E5E5EA; border-color: #007AFF; }"
        )
        load_btn.clicked.connect(self.main_window._load_data_from_excel)
        controls_layout.addWidget(load_btn)

        # Export sidebar toggle button
        self.export_toggle_btn = QPushButton("📤 Export")
        self.export_toggle_btn.setFixedHeight(28)
        self.export_toggle_btn.setCheckable(True)
        self.export_toggle_btn.setChecked(True)  # Sidebar visible by default
        self.export_toggle_btn.setStyleSheet(
            "QPushButton { background: #34C759; color: white; border: 1px solid #34C759; "
            "border-radius: 6px; font-size: 11px; font-weight: 500; padding: 4px 10px; }"
            "QPushButton:hover { background: #2FB350; }"
            "QPushButton:checked { background: #007AFF; border-color: #007AFF; }"
        )
        self.export_toggle_btn.setToolTip("Toggle export sidebar")
        self.export_toggle_btn.clicked.connect(self._toggle_export_sidebar)
        controls_layout.addWidget(self.export_toggle_btn)

        # Filter dropdown
        filter_label = QLabel("Show:")
        filter_label.setStyleSheet("font-size: 11px; color: #86868B;")
        controls_layout.addWidget(filter_label)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Binding (High)", "Baseline (Low)", "Regeneration (Med)"])
        self.filter_combo.setCurrentText("Binding (High)")  # Default: binding cycles
        self.filter_combo.setFixedHeight(28)
        self.filter_combo.setStyleSheet(
            "QComboBox { background: white; border: 1px solid #D1D1D6; border-radius: 6px; "
            "font-size: 11px; padding: 4px 8px; min-width: 120px; }"
            "QComboBox:hover { border: 1px solid #007AFF; }"
            "QComboBox::drop-down { border: none; }"
        )
        self.filter_combo.currentTextChanged.connect(self._apply_cycle_filter)
        controls_layout.addWidget(self.filter_combo)

        # Search box
        from PySide6.QtWidgets import QLineEdit
        search_label = QLabel("🔍")
        search_label.setStyleSheet("font-size: 12px; color: #86868B;")
        controls_layout.addWidget(search_label)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.search_box.setFixedHeight(28)
        self.search_box.setFixedWidth(150)
        self.search_box.setStyleSheet(
            "QLineEdit { background: white; border: 1px solid #D1D1D6; border-radius: 6px; "
            "font-size: 11px; padding: 4px 8px; }"
            "QLineEdit:focus { border: 1px solid #007AFF; }"
        )
        self.search_box.setToolTip("Search across all columns")
        self.search_box.textChanged.connect(self._apply_search_filter)
        controls_layout.addWidget(self.search_box)

        controls_layout.addStretch()

        # Columns visibility button (store reference for menu positioning)
        self.columns_btn = QPushButton("☰")
        self.columns_btn.setFixedSize(28, 28)
        self.columns_btn.setStyleSheet(
            "QPushButton { background: #F5F5F7; color: #1D1D1F; border: 1px solid #D1D1D6; "
            "border-radius: 6px; font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background: #E5E5EA; border-color: #007AFF; }"
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
        empty_text.setStyleSheet("font-size: 16px; font-weight: 600; color: #86868B; margin-top: 12px;")
        empty_text.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_text)
        empty_subtext = QLabel("Start a recording or load data to begin")
        empty_subtext.setStyleSheet("font-size: 13px; color: #AEAEB2; margin-top: 4px;")
        empty_subtext.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_subtext)
        self.empty_state_widget.hide()  # Hidden by default

        layout.addWidget(self.empty_state_widget)
        layout.addWidget(self.cycle_data_table)

        return container

    def _create_metadata_panel(self):
        """Create metadata info panel showing experiment statistics."""
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
        layout.setSpacing(10)

        # Title
        title = QLabel("Experiment Metadata")
        title.setStyleSheet("""
            font-size: 13px;
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

        # Cycles
        cycles_lbl = QLabel("Cycles:")
        cycles_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        self.meta_total_cycles = QLabel("0")
        self.meta_total_cycles.setStyleSheet("font-size: 12px; color: #007AFF; background: transparent; border: none;")
        grid.addWidget(cycles_lbl, 0, 0, Qt.AlignLeft)
        grid.addWidget(self.meta_total_cycles, 0, 1, Qt.AlignLeft)

        # Types
        types_lbl = QLabel("Types:")
        types_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        self.meta_cycle_types = QLabel("-")
        self.meta_cycle_types.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        grid.addWidget(types_lbl, 1, 0, Qt.AlignLeft)
        grid.addWidget(self.meta_cycle_types, 1, 1, Qt.AlignLeft)

        # Concentration
        conc_lbl = QLabel("Conc. Range:")
        conc_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        self.meta_conc_range = QLabel("-")
        self.meta_conc_range.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        grid.addWidget(conc_lbl, 2, 0, Qt.AlignLeft)
        grid.addWidget(self.meta_conc_range, 2, 1, Qt.AlignLeft)

        # Date
        date_lbl = QLabel("Date:")
        date_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        self.meta_date = QLabel("-")
        self.meta_date.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        grid.addWidget(date_lbl, 3, 0, Qt.AlignLeft)
        grid.addWidget(self.meta_date, 3, 1, Qt.AlignLeft)

        # User
        user_lbl = QLabel("User:")
        user_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        self.meta_user = QLabel("-")
        self.meta_user.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        grid.addWidget(user_lbl, 4, 0, Qt.AlignLeft)
        grid.addWidget(self.meta_user, 4, 1, Qt.AlignLeft)

        # Device
        device_lbl = QLabel("Device:")
        device_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        self.meta_device = QLabel("-")
        self.meta_device.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        grid.addWidget(device_lbl, 5, 0, Qt.AlignLeft)
        grid.addWidget(self.meta_device, 5, 1, Qt.AlignLeft)

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

    def _update_metadata_stats(self):
        """Update metadata statistics based on loaded metadata or current table data."""
        if not hasattr(self, 'meta_total_cycles'):
            return

        # Check if we have loaded metadata from Excel file
        loaded_metadata = getattr(self, '_loaded_metadata', {})

        # CYCLES COUNT: Always count from table (dynamic)
        total_visible = 0
        cycle_types = set()
        concentrations = []

        for row in range(self.cycle_data_table.rowCount()):
            if not self.cycle_data_table.isRowHidden(row):
                total_visible += 1

                # Get cycle type (col 0 text is like '● BL 1')
                type_item = self.cycle_data_table.item(row, 0)
                if type_item:
                    tip = type_item.toolTip()  # Full type name e.g. 'Baseline 1'
                    if tip:
                        cycle_types.add(tip.split()[0])
                    else:
                        cycle_types.add(type_item.text())

                # Get concentration (col 2)
                conc_item = self.cycle_data_table.item(row, 2)
                if conc_item and conc_item.text().strip():
                    try:
                        # Try to extract number from text like "10 nM" or "[High] 10 nM"
                        conc_text = conc_item.text().strip()
                        # Extract numbers
                        import re
                        numbers = re.findall(r'\d+\.?\d*', conc_text)
                        if numbers:
                            conc_val = float(numbers[0])
                            concentrations.append(conc_val)
                    except (ValueError, IndexError):
                        pass

        # Update cycle count
        self.meta_total_cycles.setText(f"{total_visible}")

        # Update cycle types
        if cycle_types:
            types_text = ", ".join(sorted(cycle_types))
            if len(types_text) > 30:
                types_text = types_text[:27] + "..."
            self.meta_cycle_types.setText(types_text)
        else:
            self.meta_cycle_types.setText("-")

        # Update concentration range
        if concentrations:
            min_conc = min(concentrations)
            max_conc = max(concentrations)
            self.meta_conc_range.setText(f"{min_conc:.2e} - {max_conc:.2e}")
        else:
            self.meta_conc_range.setText("-")

        # DATE: Prefer loaded metadata, fall back to recording_mgr or today
        from datetime import datetime
        date_str = None

        if loaded_metadata and 'recording_start' in loaded_metadata:
            date_str = loaded_metadata['recording_start']
            # If it's ISO format, convert to readable format
            if 'recording_start_iso' in loaded_metadata:
                try:
                    dt_obj = datetime.fromisoformat(loaded_metadata['recording_start_iso'])
                    date_str = dt_obj.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass  # Use the string as-is
        elif hasattr(self.main_window, 'app') and hasattr(self.main_window.app, 'recording_mgr'):
            rec = self.main_window.app.recording_mgr
            if hasattr(rec, 'recording_start_time') and rec.recording_start_time:
                date_str = rec.recording_start_time.strftime("%Y-%m-%d %H:%M")

        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        self.meta_date.setText(date_str)

        # USER: Prefer loaded metadata, fall back to current user
        user_str = None

        if loaded_metadata and 'User' in loaded_metadata:
            user_str = loaded_metadata['User']
        else:
            try:
                if self.user_manager:
                    user = self.user_manager.get_current_user()
                else:
                    # Fallback
                    from affilabs.services.user_profile_manager import UserProfileManager
                    user_mgr = UserProfileManager()
                    user = user_mgr.get_current_user()
                user_str = user if user else None
            except Exception:
                pass

        self.meta_user.setText(user_str if user_str else "-")

        # DEVICE: Prefer loaded metadata, fall back to current device
        device_str = None

        if loaded_metadata and 'device_id' in loaded_metadata:
            device_str = loaded_metadata['device_id']
        elif hasattr(self.main_window, 'device_config') and self.main_window.device_config:
            dc = self.main_window.device_config
            device_id = getattr(dc, 'device_serial', '') or ''
            device_str = device_id if device_id else None

        self.meta_device.setText(device_str if device_str else "-")

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

        # Auto-Align to Injection button
        self.auto_align_btn = QPushButton("⚡ Auto-Align to Injection")
        self.auto_align_btn.setToolTip(
            "Automatically align all selected cycles so their injection flags line up.\n"
            "Uses the first cycle's injection time as the reference point."
        )
        self.auto_align_btn.setStyleSheet("""
            QPushButton {
                background: #FF9500;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #E08600;
            }
            QPushButton:pressed {
                background: #CC7700;
            }
            QPushButton:disabled {
                background: #C7C7CC;
                color: #8E8E93;
            }
        """)
        self.auto_align_btn.clicked.connect(self._auto_align_to_injection)
        layout.addWidget(self.auto_align_btn)

        # Find Multiple Injections button
        self.find_injections_btn = QPushButton("🔍 Find Multiple Injections")
        self.find_injections_btn.setToolTip(
            "Automatically detect multiple injection points within the selected cycle.\n\n"
            "How it works:\n"
            "1. Detects first injection (if not already flagged)\n"
            "2. Searches for additional injections in the next 60 seconds\n"
            "3. Places flags at each detected injection point\n\n"
            "Perfect for concentration series with multiple injections!"
        )
        self.find_injections_btn.setStyleSheet("""
            QPushButton {
                background: #34C759;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                padding: 8px 16px;
                margin-top: 8px;
            }
            QPushButton:hover {
                background: #2DB04E;
            }
            QPushButton:pressed {
                background: #289944;
            }
            QPushButton:disabled {
                background: #C7C7CC;
                color: #8E8E93;
            }
        """)
        self.find_injections_btn.clicked.connect(self._find_multiple_injections)
        layout.addWidget(self.find_injections_btn)

        layout.addStretch()

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
        self.edits_timeline_graph.setMenuEnabled(True)  # Enable context menu for export options
        self.edits_timeline_graph.setBackground('w')
        self.edits_timeline_graph.setLabel('left', 'Response', units='RU', color='#1D1D1F')
        self.edits_timeline_graph.setLabel('bottom', 'Time', units='s', color='#1D1D1F')
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
            label='Start', labelOpts={'position': 0.85, 'color': '#34C759'}
        )
        self.edits_timeline_cursors['right'] = pg.InfiniteLine(
            pos=100, angle=90, movable=True,
            pen=pg.mkPen('#007AFF', width=2, style=Qt.DashLine),
            label='End', labelOpts={'position': 0.85, 'color': '#007AFF'}
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
        title.setStyleSheet("font-size: 13px; font-weight: 600; color: #1D1D1F;")
        header.addWidget(title)
        header.addStretch()

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

        # Create bar graph items
        self.delta_spr_bars = []

        # Import professional channel colors from UI constants
        from affilabs.widgets.ui_constants import ChannelColors
        from affilabs.plot_helpers import CHANNEL_COLORS, CHANNEL_COLORS_COLORBLIND

        # Check if colorblind mode is enabled
        colorblind_enabled = (
            hasattr(self.main_window, 'colorblind_check') and
            self.main_window.colorblind_check.isChecked()
        )

        # Use colorblind palette if enabled, otherwise use default
        if colorblind_enabled:
            bar_colors = ChannelColors.get_rgba_from_colors(CHANNEL_COLORS_COLORBLIND)
        else:
            bar_colors = ChannelColors.get_all_rgba_for_channels(['A', 'B', 'C', 'D'])

        for i, color in enumerate(bar_colors):
            bar = pg.BarGraphItem(x=[i], height=[0], width=0.6, brush=color)
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

        # Auto-detect injection checkbox with improved visibility
        self.auto_detect_checkbox = QCheckBox("💉 Show Injection Marker")
        self.auto_detect_checkbox.setChecked(True)  # Enabled by default
        self.auto_detect_checkbox.setStyleSheet(
            "QCheckBox { "
            "  font-size: 13px; "
            "  color: #1D1D1F; "
            "  font-weight: 600; "
            "  padding: 6px; "
            "  background: #F5F5F7; "
            "  border-radius: 6px; "
            "}"
            "QCheckBox::indicator { width: 20px; height: 20px; }"
            "QCheckBox::indicator:checked { "
            "  background: #FF3B30; "
            "  border: 2px solid #FF3B30; "
            "  border-radius: 4px; "
            "  image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMy41IDhMNi41IDExTDEyLjUgNSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz48L3N2Zz4=); "
            "}"
            "QCheckBox::indicator:unchecked { "
            "  background: white; "
            "  border: 2px solid #D1D1D6; "
            "  border-radius: 4px; "
            "}"
            "QCheckBox:hover { background: #E8E8EA; }"
        )
        self.auto_detect_checkbox.setToolTip(
            "Toggle injection marker visibility\n\n"
            "✓ CHECKED: Shows red dashed vertical line at injection point\n"
            "  • Auto-detects maximum slope in SPR signal\n"
            "  • Draggable for manual correction\n"
            "  • Displays on primary graph (top)\n\n"
            "✗ UNCHECKED: Hides injection marker from graph"
        )
        self.auto_detect_checkbox.stateChanged.connect(self._on_auto_detect_toggled)
        layout.addWidget(self.auto_detect_checkbox)

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

    # Helper methods

    def _update_selection_view(self):
        """Update active selection graph based on timeline cursor positions."""
        # Check for recording manager and raw data
        if not hasattr(self.main_window.app, 'recording_mgr') or not self.main_window.app.recording_mgr:
            return

        raw_data = self.main_window.app.recording_mgr.data_collector.raw_data_rows
        if not raw_data:
            return

        # Check if cursors exist
        if not self.edits_timeline_cursors.get('left') or not self.edits_timeline_cursors.get('right'):
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

    def _calculate_actual_duration(self, cycle_idx, cycle, all_cycles):
        """Calculate ACTUAL cycle duration (not planned duration).

        Strategy:
        1. If end_time_sensorgram exists: use (end - start) / 60
        2. Else if next cycle exists: use (next_start - current_start) / 60
        3. Else: fall back to duration_minutes field (planned duration)

        Args:
            cycle_idx: Index of current cycle in all_cycles list
            cycle: Current cycle dict
            all_cycles: Complete list of all cycles

        Returns:
            float: Actual duration in minutes
        """
        start_time = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time'))
        end_time = cycle.get('end_time_sensorgram')

        # Strategy 1: Use recorded end time if available
        if pd.notna(end_time) and pd.notna(start_time):
            actual_duration = (end_time - start_time) / 60.0
            logger.debug(f"Cycle {cycle_idx + 1}: Using recorded end time → {actual_duration:.2f} min")
            return actual_duration

        # Strategy 2: Calculate from spacing to next cycle
        if cycle_idx < len(all_cycles) - 1:
            next_cycle = all_cycles[cycle_idx + 1]
            next_start = next_cycle.get('start_time_sensorgram', next_cycle.get('sensorgram_time'))

            if pd.notna(next_start) and pd.notna(start_time):
                actual_duration = (next_start - start_time) / 60.0
                logger.debug(f"Cycle {cycle_idx + 1}: Calculated from spacing → {actual_duration:.2f} min")
                return actual_duration

        # Strategy 3: Fall back to planned duration
        planned_duration = cycle.get('duration_minutes', cycle.get('length_minutes', 0))
        logger.debug(f"Cycle {cycle_idx + 1}: Using planned duration → {planned_duration:.2f} min")
        return planned_duration

    def _populate_cycles_table(self, cycles_data):
        """Populate the cycles table with loaded cycle data."""
        from PySide6.QtGui import QColor
        self.cycle_data_table.setRowCount(0)  # Clear existing rows

        type_counts = {}  # Track numbering per type

        for cycle_idx, cycle in enumerate(cycles_data):
            row_idx = self.cycle_data_table.rowCount()
            self.cycle_data_table.insertRow(row_idx)

            # --- Col 0: Type icon (color-coded abbreviation) ---
            cycle_type = str(cycle.get('type', 'Custom'))
            type_counts[cycle_type] = type_counts.get(cycle_type, 0) + 1
            abbr, color = CycleTypeStyle.get(cycle_type)
            type_item = QTableWidgetItem(f"{abbr} {type_counts[cycle_type]}")
            type_item.setForeground(QColor(color))
            type_item.setToolTip(f"{cycle_type} {type_counts[cycle_type]}")
            self.cycle_data_table.setItem(row_idx, 0, type_item)

            # --- Col 1: Time (ACTUAL duration @ start) ---
            # Calculate ACTUAL duration (not planned)
            actual_duration_min = self._calculate_actual_duration(cycle_idx, cycle, cycles_data)
            start_time = cycle.get('start_time_sensorgram', 0)

            # Handle NaN values
            if pd.notna(actual_duration_min) and pd.notna(start_time) and isinstance(actual_duration_min, (int, float)) and isinstance(start_time, (int, float)):
                time_str = f"{actual_duration_min:.1f}m @ {start_time:.0f}s"
            else:
                time_str = f"{actual_duration_min}m @ {start_time}s" if actual_duration_min != 0 or start_time != 0 else "—"
            self.cycle_data_table.setItem(row_idx, 1, QTableWidgetItem(time_str))

            # --- Col 2: Concentration ---
            conc_val = cycle.get('concentration_value', '')
            conc_str = str(conc_val) if pd.notna(conc_val) and conc_val != '' else ''
            self.cycle_data_table.setItem(row_idx, 2, QTableWidgetItem(conc_str))

            # --- Col 3: ΔSPR (combined 4 channels) ---
            delta_parts = []
            for ch_key, ch_label in [('delta_ch1', 'A'), ('delta_ch2', 'B'), ('delta_ch3', 'C'), ('delta_ch4', 'D')]:
                val = cycle.get(ch_key, '')
                if pd.notna(val) and isinstance(val, (int, float)):
                    delta_parts.append(f"{ch_label}:{val:.0f}")
                elif val and pd.notna(val):
                    delta_parts.append(f"{ch_label}:{val}")
            # Also check delta_spr_by_channel dict
            if not delta_parts:
                delta_by_ch = cycle.get('delta_spr_by_channel', {})
                if isinstance(delta_by_ch, str):
                    # If it's a string representation of dict, try to parse it
                    import ast
                    try:
                        delta_by_ch = ast.literal_eval(delta_by_ch)
                    except:
                        delta_by_ch = {}
                for ch in ['A', 'B', 'C', 'D']:
                    val = delta_by_ch.get(ch, '')
                    if pd.notna(val) and isinstance(val, (int, float)):
                        delta_parts.append(f"{ch}:{val:.0f}")
            delta_str = " ".join(delta_parts) if delta_parts else ''
            self.cycle_data_table.setItem(row_idx, 3, QTableWidgetItem(delta_str))

            # --- Col 4: Flags ---
            flag_data = cycle.get('flag_data', [])
            if flag_data:
                _ICONS = {'injection': '▲', 'wash': '■', 'spike': '◆'}
                parts = []
                for f in flag_data:
                    icon = _ICONS.get(f.get('type', ''), '●')
                    parts.append(f"{icon}{f.get('time', 0):.0f}s")
                flags_display = " ".join(parts)
            else:
                raw_flags = cycle.get('flags', '')
                # Handle string representation of list
                if isinstance(raw_flags, str) and raw_flags.startswith('['):
                    import ast
                    try:
                        raw_flags = ast.literal_eval(raw_flags)
                    except:
                        pass
                if isinstance(raw_flags, list) and raw_flags:
                    flags_display = ', '.join(raw_flags)
                else:
                    flags_display = str(raw_flags) if raw_flags and pd.notna(raw_flags) else ''
            self.cycle_data_table.setItem(row_idx, 4, QTableWidgetItem(flags_display))

            # --- Col 5: Notes ---
            notes = cycle.get('note', cycle.get('notes', ''))
            cycle_id = cycle.get('cycle_id', '')
            if cycle_id:
                notes_display = f"[{cycle_id}] {notes}" if notes else f"[{cycle_id}]"
            else:
                notes_display = str(notes) if notes else ''
            self.cycle_data_table.setItem(row_idx, 5, QTableWidgetItem(notes_display))

        # Update empty state visibility
        self._update_empty_state()

        # Update metadata stats
        if hasattr(self, '_update_metadata_stats'):
            self._update_metadata_stats()

    def _export_selection(self):
        """Export data from Edits tab to Excel.

        Two modes:
        1. If cycles exist and are selected: Export combined sensorgram with cycles
        2. If no cycles (live data): Export raw data directly
        """
        from affilabs.utils.logger import logger
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import pandas as pd
        from datetime import datetime

        try:
            # Check if we have raw data available (either from Send to Edits or loaded file)
            raw_data = None

            # Option 1: Data from Send to Edits (stored in main_window._edits_raw_data)
            if hasattr(self.main_window, '_edits_raw_data') and self.main_window._edits_raw_data is not None:
                raw_data = self.main_window._edits_raw_data

            # Option 2: Data loaded from file (stored in recording_mgr.data_collector.raw_data_rows)
            elif hasattr(self.main_window, 'app') and hasattr(self.main_window.app, 'recording_mgr'):
                if hasattr(self.main_window.app.recording_mgr, 'data_collector'):
                    if hasattr(self.main_window.app.recording_mgr.data_collector, 'raw_data_rows'):
                        raw_rows = self.main_window.app.recording_mgr.data_collector.raw_data_rows
                        if raw_rows and len(raw_rows) > 0:
                            # Keep raw data in original format (don't pivot)
                            # Just pass the raw_rows list directly for long format export
                            self._export_raw_data_long_format(raw_rows)
                            return

            # If we have raw data, export it directly
            if raw_data is not None and len(raw_data) > 0:
                self._export_raw_data_direct(raw_data)
                return

            # Otherwise, export selected cycles (original behavior)
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
                # Sheet 1: Combined data in long format (original format)
                df_data_long = pd.DataFrame(export_data)
                df_data_long = df_data_long.sort_values(['Time_s', 'Channel'])
                df_data_long.to_excel(writer, sheet_name='Combined Data (Long)', index=False)

                # Sheet 2: Per-channel format (Time_A, A, Time_B, B, Time_C, C, Time_D, D)
                # Convert long format to wide per-channel format
                per_channel_data = {}
                for item in export_data:
                    ch = item['Channel']
                    time = item['Time_s']
                    ru = item['Response_RU']

                    if ch not in per_channel_data:
                        per_channel_data[ch] = {'times': [], 'values': []}

                    per_channel_data[ch]['times'].append(time)
                    per_channel_data[ch]['values'].append(ru)

                # Find max length for padding
                max_len = max((len(per_channel_data[ch]['times']) for ch in ['A', 'B', 'C', 'D'] if ch in per_channel_data), default=0)

                # Build per-channel DataFrame
                per_channel_dict = {}
                for ch in ['A', 'B', 'C', 'D']:
                    if ch in per_channel_data:
                        times = per_channel_data[ch]['times']
                        values = per_channel_data[ch]['values']
                        # Pad to max length with NaN
                        times += [None] * (max_len - len(times))
                        values += [None] * (max_len - len(values))
                        per_channel_dict[f'Time_{ch}'] = times
                        per_channel_dict[ch] = values
                    else:
                        per_channel_dict[f'Time_{ch}'] = [None] * max_len
                        per_channel_dict[ch] = [None] * max_len

                # Create DataFrame with column order: Time_A, A, Time_B, B, Time_C, C, Time_D, D
                column_order = []
                for ch in ['A', 'B', 'C', 'D']:
                    column_order.append(f'Time_{ch}')
                    column_order.append(ch)

                df_per_channel = pd.DataFrame(per_channel_dict)[column_order]
                df_per_channel.to_excel(writer, sheet_name='Per-Channel Format', index=False)

                # Sheet 3: Metadata
                df_meta = pd.DataFrame(metadata)
                df_meta.to_excel(writer, sheet_name='Cycle Metadata', index=False)

                # Sheet 4: Alignment settings (for re-loading)
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

                # Sheet 5: Flags (if any)
                if self._edits_flags:
                    flag_rows = []
                    for flag in self._edits_flags:
                        flag_rows.append(flag.to_export_dict())
                    if flag_rows:
                        df_flags = pd.DataFrame(flag_rows)
                        df_flags.to_excel(writer, sheet_name='Flags', index=False)
                        logger.debug(f"Exported {len(flag_rows)} flags")

                # Sheet 6: Export info
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

    def _export_raw_data_long_format(self, raw_rows):
        """
        Export raw data in LONG format (Time, Channel, Value) and also create per-channel format.
        This avoids the sparse wide-format with lots of NaN values.
        """
        import pandas as pd
        from datetime import datetime
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from affilabs.utils.logger import logger
        from affilabs.utils.time_utils import filename_timestamp
        from pathlib import Path

        # Ensure experiment folder exists
        exp_folder = self._ensure_experiment_folder()

        # Get default save location in Raw_Data subfolder
        if exp_folder:
            raw_data_folder = self.main_window.app.experiment_folder_mgr.get_subfolder_path(
                exp_folder, "Raw_Data"
            )
            default_filename = f"Raw_{filename_timestamp()}.xlsx"
            default_path = str(raw_data_folder / default_filename)
        else:
            # Fallback if no experiment folder
            default_filename = f"Raw_{filename_timestamp()}.xlsx"
            default_path = default_filename

        # Ask user for save location (defaults to experiment folder)
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Save Raw Data",
            default_path,
            "Excel Files (*.xlsx)"
        )

        if not file_path:
            return

        # Convert raw_rows to long format DataFrame
        rows_list = []
        for row in raw_rows:
            time_key = 'elapsed' if 'elapsed' in row else 'time'
            rows_list.append({
                'Time': row[time_key],
                'Channel': row['channel'].upper(),
                'Value': row['value']
            })

        df_long = pd.DataFrame(rows_list)

        # Also create wide format for per-channel extraction
        df_wide = df_long.pivot_table(
            index='Time',
            columns='Channel',
            values='Value',
            aggfunc='first'
        ).reset_index()

        # Get cycle table data if available (match Edits table columns)
        cycles_table = []
        if hasattr(self.main_window, '_loaded_cycles_data') and self.main_window._loaded_cycles_data:
            for idx, cycle in enumerate(self.main_window._loaded_cycles_data):
                # Build ΔSPR string (A:val B:val C:val D:val)
                delta_parts = []
                for ch_idx, ch_label in enumerate(['A', 'B', 'C', 'D']):
                    val = cycle.get(f'delta_ch{ch_idx + 1}', '')
                    if isinstance(val, (int, float)):
                        delta_parts.append(f"{ch_label}:{val:.0f}")
                delta_spr_str = " ".join(delta_parts) if delta_parts else ''

                # Build Flags string (icon + time)
                flag_data = cycle.get('flag_data', [])
                if flag_data:
                    _ICONS = {'injection': '▲', 'wash': '■', 'spike': '◆'}
                    flag_parts = []
                    for f in flag_data:
                        icon = _ICONS.get(f.get('type', ''), '●')
                        flag_parts.append(f"{icon}{f.get('time', 0):.0f}s")
                    flags_str = " ".join(flag_parts)
                else:
                    flags_str = cycle.get('flags', '')

                cycles_table.append({
                    'Cycle #': cycle.get('cycle_number', idx + 1),
                    'Type': cycle.get('type', 'Unknown'),
                    'Duration (min)': cycle.get('duration_minutes', ''),
                    'Start Time (s)': cycle.get('start_time', ''),
                    'Concentration': cycle.get('concentration_value', ''),
                    'Units': cycle.get('concentration_units', ''),
                    'ΔSPR': delta_spr_str,
                    'Flags': flags_str,
                    'Notes': cycle.get('note', cycle.get('notes', '')),
                    'Cycle ID': cycle.get('cycle_id', ''),
                })

        # Export to Excel with multiple sheets
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # Sheet 1: Raw data in LONG format (Time, Channel, Value - no NaNs!)
            df_long.to_excel(writer, sheet_name='Raw Data', index=False)

            # Sheet 2: Per-channel format (Time_A, A, Time_B, B, Time_C, C, Time_D, D)
            per_channel_dict = {}
            for ch in ['A', 'B', 'C', 'D']:
                if ch in df_wide.columns:
                    # Get non-null values and their corresponding times
                    valid_mask = df_wide[ch].notna()
                    times = df_wide.loc[valid_mask, 'Time'].values
                    values = df_wide.loc[valid_mask, ch].values
                    per_channel_dict[f'Time_{ch}'] = list(times)
                    per_channel_dict[ch] = list(values)
                else:
                    per_channel_dict[f'Time_{ch}'] = []
                    per_channel_dict[ch] = []

            # Pad all lists to the same length
            max_len = max(len(v) for v in per_channel_dict.values()) if per_channel_dict else 0
            for key in per_channel_dict:
                while len(per_channel_dict[key]) < max_len:
                    per_channel_dict[key].append(None)

            df_per_channel = pd.DataFrame(per_channel_dict)
            df_per_channel.to_excel(writer, sheet_name='Per-Channel Format', index=False)

            # Sheet 3: Cycle Table
            if cycles_table:
                df_cycles = pd.DataFrame(cycles_table)
                df_cycles.to_excel(writer, sheet_name='Cycle Table', index=False)

            # Sheet 4: Export info
            info_dict = {
                'Property': ['Export Date', 'Data Points', 'Channels', 'Cycles'],
                'Value': [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    str(len(df_long)),
                    ', '.join(df_long['Channel'].unique()),
                    str(len(cycles_table)) if cycles_table else '0'
                ]
            }
            df_info = pd.DataFrame(info_dict)
            df_info.to_excel(writer, sheet_name='Export Info', index=False)

        logger.info(f"[EXPORT] Exported {len(df_long)} rows to: {file_path}")

        # Register file in experiment metadata (if using experiment folder)
        if exp_folder and Path(file_path).is_relative_to(exp_folder):
            self.main_window.app.experiment_folder_mgr.register_file(
                exp_folder,
                Path(file_path),
                "raw_data",
                f"Raw sensor data export with {len(df_long)} data points"
            )
            logger.debug(f"Registered raw data file in experiment metadata")

        metadata_text = f"Exported to:\n{file_path}\n\n"
        metadata_text += f"Raw Data: {len(df_long)} rows (long format)\n"
        metadata_text += f"Per-Channel Format: {max_len} rows\n"
        metadata_text += f"Channels: {', '.join(df_long['Channel'].unique())}"

        QMessageBox.information(self.main_window, "Export Complete", metadata_text)

    def _export_raw_data_direct(self, df_raw):
        """Export raw data DataFrame directly to Excel in per-channel format.

        Args:
            df_raw: DataFrame with columns Time, A, B, C, D
        """
        from affilabs.utils.logger import logger
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import pandas as pd
        from datetime import datetime

        try:
            if df_raw is None or len(df_raw) == 0:
                QMessageBox.warning(
                    self.main_window,
                    "No Data",
                    "No data available to export."
                )
                return

            # Get filename from user
            default_name = f"Edits_Data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            file_path, _ = QFileDialog.getSaveFileName(
                self.main_window,
                "Export Data",
                default_name,
                "Excel Files (*.xlsx);;All Files (*)"
            )

            if not file_path:
                return  # User cancelled

            logger.info(f"[EXPORT] Exporting data to: {file_path}")

            # Create Excel file with multiple sheets
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Sheet 1: Raw data (Time, A, B, C, D format)
                df_raw.to_excel(writer, sheet_name='Raw Data', index=False)

                # Sheet 2: Per-channel format (Time_A, A, Time_B, B, Time_C, C, Time_D, D)
                per_channel_dict = {}
                for ch in ['A', 'B', 'C', 'D']:
                    if ch in df_raw.columns:
                        # Get non-null values and their corresponding times
                        valid_mask = df_raw[ch].notna()
                        times = df_raw.loc[valid_mask, 'Time'].values
                        values = df_raw.loc[valid_mask, ch].values
                        per_channel_dict[f'Time_{ch}'] = list(times)
                        per_channel_dict[ch] = list(values)
                    else:
                        per_channel_dict[f'Time_{ch}'] = []
                        per_channel_dict[ch] = []

                # Find max length for padding
                max_len = max((len(per_channel_dict[f'Time_{ch}']) for ch in ['A', 'B', 'C', 'D']), default=0)

                # Pad all to same length
                for ch in ['A', 'B', 'C', 'D']:
                    current_len = len(per_channel_dict[f'Time_{ch}'])
                    if current_len < max_len:
                        per_channel_dict[f'Time_{ch}'].extend([None] * (max_len - current_len))
                        per_channel_dict[ch].extend([None] * (max_len - current_len))

                # Create DataFrame with column order: Time_A, A, Time_B, B, Time_C, C, Time_D, D
                column_order = []
                for ch in ['A', 'B', 'C', 'D']:
                    column_order.append(f'Time_{ch}')
                    column_order.append(ch)

                df_per_channel = pd.DataFrame(per_channel_dict)[column_order]
                df_per_channel.to_excel(writer, sheet_name='Per-Channel Format', index=False)

                # Sheet 3: Cycle Table
                cycles_table = []
                if hasattr(self.main_window, '_loaded_cycles_data') and self.main_window._loaded_cycles_data:
                    for idx, cycle in enumerate(self.main_window._loaded_cycles_data):
                        cycles_table.append({
                            'Cycle #': cycle.get('cycle_number', idx + 1),
                            'Type': cycle.get('type', 'Unknown'),
                            'Duration (min)': cycle.get('duration_minutes', ''),
                            'Concentration': cycle.get('concentration_value', ''),
                            'Units': cycle.get('concentration_units', ''),
                            'Notes': cycle.get('notes', '')
                        })

                if cycles_table:
                    df_cycles = pd.DataFrame(cycles_table)
                    df_cycles.to_excel(writer, sheet_name='Cycle Table', index=False)

                # Sheet 4: Export info
                source_file = getattr(self.main_window, '_edits_source_file', 'Unknown')
                export_info = pd.DataFrame([{
                    'Export_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'Source': source_file,
                    'Total_Data_Points': len(df_raw),
                    'Time_Range_s': f"{df_raw['Time'].min():.1f} - {df_raw['Time'].max():.1f}",
                    'Cycles': str(len(cycles_table)) if cycles_table else '0',
                    'Description': 'Data exported from Edits tab'
                }])
                export_info.to_excel(writer, sheet_name='Export Info', index=False)

            logger.info(f"✓ Exported {len(df_raw)} data points")

            QMessageBox.information(
                self.main_window,
                "Export Complete",
                f"Data exported successfully!\n\n"
                f"File: {file_path}\n"
                f"Data points: {len(df_raw)}\n"
                f"Sheets: Raw Data + Per-Channel Format"
            )

        except Exception as e:
            logger.exception(f"Error exporting data: {e}")
            QMessageBox.critical(
                self.main_window,
                "Export Error",
                f"Failed to export data:\n{str(e)}"
            )

    def _export_raw_data(self):
        """Export raw data (from Send to Edits) to Excel in per-channel format."""
        from affilabs.utils.logger import logger
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import pandas as pd
        from datetime import datetime

        try:
            # Get raw data DataFrame
            df_raw = self.main_window._edits_raw_data

            if df_raw is None or len(df_raw) == 0:
                QMessageBox.warning(
                    self.main_window,
                    "No Data",
                    "No data available to export."
                )
                return

            # Get filename from user
            default_name = f"Live_Data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            file_path, _ = QFileDialog.getSaveFileName(
                self.main_window,
                "Export Live Data",
                default_name,
                "Excel Files (*.xlsx);;All Files (*)"
            )

            if not file_path:
                return  # User cancelled

            logger.info(f"[EXPORT] Exporting raw data to: {file_path}")

            # Create Excel file with multiple sheets
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Sheet 1: Raw data (Time, A, B, C, D format)
                df_raw.to_excel(writer, sheet_name='Raw Data', index=False)

                # Sheet 2: Per-channel format (Time_A, A, Time_B, B, Time_C, C, Time_D, D)
                per_channel_dict = {}
                for ch in ['A', 'B', 'C', 'D']:
                    if ch in df_raw.columns:
                        # Get non-null values and their corresponding times
                        valid_mask = df_raw[ch].notna()
                        times = df_raw.loc[valid_mask, 'Time'].values
                        values = df_raw.loc[valid_mask, ch].values
                        per_channel_dict[f'Time_{ch}'] = list(times)
                        per_channel_dict[ch] = list(values)
                    else:
                        per_channel_dict[f'Time_{ch}'] = []
                        per_channel_dict[ch] = []

                # Find max length for padding
                max_len = max((len(per_channel_dict[f'Time_{ch}']) for ch in ['A', 'B', 'C', 'D']), default=0)

                # Pad all to same length
                for ch in ['A', 'B', 'C', 'D']:
                    current_len = len(per_channel_dict[f'Time_{ch}'])
                    if current_len < max_len:
                        per_channel_dict[f'Time_{ch}'].extend([None] * (max_len - current_len))
                        per_channel_dict[ch].extend([None] * (max_len - current_len))

                # Create DataFrame with column order: Time_A, A, Time_B, B, Time_C, C, Time_D, D
                column_order = []
                for ch in ['A', 'B', 'C', 'D']:
                    column_order.append(f'Time_{ch}')
                    column_order.append(ch)

                df_per_channel = pd.DataFrame(per_channel_dict)[column_order]
                df_per_channel.to_excel(writer, sheet_name='Per-Channel Format', index=False)

                # Sheet 3: Export info
                export_info = pd.DataFrame([{
                    'Export_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'Source': getattr(self.main_window, '_edits_source_file', 'Live Data'),
                    'Total_Data_Points': len(df_raw),
                    'Time_Range_s': f"{df_raw['Time'].min():.1f} - {df_raw['Time'].max():.1f}",
                    'Description': 'Live data exported from Edits tab'
                }])
                export_info.to_excel(writer, sheet_name='Export Info', index=False)

            logger.info(f"✓ Exported {len(df_raw)} data points")

            QMessageBox.information(
                self.main_window,
                "Export Complete",
                f"Data exported successfully!\n\n"
                f"File: {file_path}\n"
                f"Data points: {len(df_raw)}\n"
                f"Format: Raw Data + Per-Channel sheets"
            )

        except Exception as e:
            logger.exception(f"Error exporting raw data: {e}")
            QMessageBox.critical(
                self.main_window,
                "Export Error",
                f"Failed to export data:\n{str(e)}"
            )

    def update_barchart_colors(self, colorblind_enabled: bool):
        """Update bar chart colors when colorblind mode is toggled.

        Args:
            colorblind_enabled: True if colorblind mode is enabled
        """
        from affilabs.widgets.ui_constants import ChannelColors
        from affilabs.plot_helpers import CHANNEL_COLORS, CHANNEL_COLORS_COLORBLIND

        # Get appropriate color palette
        if colorblind_enabled:
            bar_colors = ChannelColors.get_rgba_from_colors(CHANNEL_COLORS_COLORBLIND)
        else:
            bar_colors = ChannelColors.get_all_rgba_for_channels(['A', 'B', 'C', 'D'])

        # Update each bar's color
        for i, (bar, color) in enumerate(zip(self.delta_spr_bars, bar_colors)):
            bar.setOpts(brush=color)

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
        from PySide6.QtGui import QColor

        # Col 0: Type icon
        cycle_type = cycle.get('type', 'Custom')
        cycle_num = cycle.get('cycle_number', row_idx + 1)
        abbr, color = CycleTypeStyle.get(cycle_type)
        type_item = QTableWidgetItem(f"{abbr} {cycle_num}")
        type_item.setForeground(QColor(color))
        type_item.setToolTip(f"{cycle_type} {cycle_num}")
        self.cycle_data_table.setItem(row_idx, 0, type_item)

        # Col 1: Time (ACTUAL duration @ start)
        # Get all cycles to calculate actual duration from spacing if needed
        all_cycles = getattr(self.main_window, '_loaded_cycles_data', [])
        if all_cycles:
            actual_duration = self._calculate_actual_duration(row_idx, cycle, all_cycles)
        else:
            # Fallback if no loaded cycles (shouldn't happen in normal operation)
            actual_duration = cycle.get('duration_minutes', '')

        start = cycle.get('start_time_sensorgram', cycle.get('sensorgram_time', 0))
        if isinstance(actual_duration, (int, float)) and isinstance(start, (int, float)):
            self.cycle_data_table.setItem(row_idx, 1, QTableWidgetItem(f"{actual_duration:.1f}m @ {start:.0f}s"))
        else:
            self.cycle_data_table.setItem(row_idx, 1, QTableWidgetItem(f"{actual_duration}m @ {start}s"))

        # Col 2: Concentration
        self.cycle_data_table.setItem(row_idx, 2, QTableWidgetItem(str(cycle.get('concentration_value', ''))))

        # Col 3: ΔSPR (combined)
        delta_by_ch = cycle.get('delta_spr_by_channel', {})
        parts = []
        for ch in ['A', 'B', 'C', 'D']:
            val = delta_by_ch.get(ch, '')
            if isinstance(val, (int, float)):
                parts.append(f"{ch}:{val:.0f}")
        self.cycle_data_table.setItem(row_idx, 3, QTableWidgetItem(" ".join(parts)))

        # Col 5: Notes
        self.cycle_data_table.setItem(row_idx, 5, QTableWidgetItem(cycle.get('notes', cycle.get('note', ''))))

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

                # Get raw data (list of dicts with 'time', 'channel', 'value')
                raw_data_list = self.main_window._loaded_raw_data
                if not raw_data_list:
                    logger.warning("      No raw data available")
                    continue

                # Filter to cycle time range and extract selected channel(s)
                channels_to_extract = ['a', 'b', 'c', 'd'] if channel_filter == 'All' else [channel_filter.lower()]

                points_before = len(combined_data)
                for ch in channels_to_extract:
                    # Extract data for this channel in this time range
                    for row_data in raw_data_list:
                        if row_data.get('channel') == ch:
                            time = row_data.get('time')
                            value = row_data.get('value')

                            if time is not None and value is not None:
                                if start_time <= time <= end_time:
                                    # Normalize time to start at current_time
                                    adjusted_time = time - start_time + time_shift + current_time
                                    combined_data.append({
                                        'Time_s': adjusted_time,
                                        'Channel': ch,
                                        'Response_RU': value
                                    })

                # Update time offset
                cycle_duration = end_time - start_time
                current_time += cycle_duration
                points_extracted = len(combined_data) - points_before

                logger.info(f"      Extracted {points_extracted} time points, total duration now: {current_time:.1f}s")

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
                anchor=(0, 0.5),  # Left-center anchor for better visibility
                fill=pg.mkBrush(255, 255, 255, 220),
                border=pg.mkPen((180, 180, 180), width=1)
            )
            # Position label at start + small offset, centered vertically
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

    def _on_table_context_menu(self, position):
        """Show context menu for cycle table with option to load to reference graphs or delete."""
        from PySide6.QtWidgets import QMenu

        menu = QMenu()

        # Get selected rows
        selected_rows = sorted(set(item.row() for item in self.cycle_data_table.selectedItems()))

        if not selected_rows:
            return  # No selection, don't show menu

        if len(selected_rows) == 1:
            # Single cycle selected - offer to edit timing
            edit_action = menu.addAction("✏️ Edit Cycle Timing")
            edit_action.triggered.connect(lambda: self._edit_cycle_timing(selected_rows[0]))

            menu.addSeparator()

            # Single cycle selected - offer to load to reference slots
            ref_menu = menu.addMenu("📊 Load to Reference Graph")

            for i in range(3):
                ref_label = f"Reference {i + 1}"
                # Check if slot is already occupied
                if hasattr(self.main_window, 'edits_reference_cycle_data'):
                    existing_cycle = self.main_window.edits_reference_cycle_data[i]
                    if existing_cycle is not None:
                        ref_label += f" (Currently: Cycle {existing_cycle + 1})"

                action = ref_menu.addAction(ref_label)
                action.triggered.connect(lambda checked=False, row=selected_rows[0], idx=i:
                                        self.main_window._load_cycle_to_reference(row, idx))

            menu.addSeparator()

        # Delete option (works for single or multiple selections)
        if len(selected_rows) == 1:
            cycle_text = "this cycle"
        else:
            cycle_text = f"{len(selected_rows)} cycles"

        delete_action = menu.addAction(f"🗑️ Delete {cycle_text}")
        delete_action.triggered.connect(lambda: self._delete_cycles_from_table(selected_rows))

        # Show menu at cursor position
        menu.exec(self.cycle_data_table.viewport().mapToGlobal(position))

    def _delete_cycles_from_table(self, row_indices):
        """Delete selected cycles from the cycle data table.

        Args:
            row_indices: List of row indices to delete
        """
        from PySide6.QtWidgets import QMessageBox
        from affilabs.utils.logger import logger

        if not row_indices:
            return

        # Confirm deletion
        if len(row_indices) == 1:
            msg = "Are you sure you want to delete this cycle?"
        else:
            msg = f"Are you sure you want to delete {len(row_indices)} cycles?"

        reply = QMessageBox.question(
            self.main_window,
            "Delete Cycle(s)",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Delete from table and data (reverse order to maintain indices)
        for row in sorted(row_indices, reverse=True):
            # Remove from loaded cycles data if it exists
            if hasattr(self.main_window, '_loaded_cycles_data') and row < len(self.main_window._loaded_cycles_data):
                del self.main_window._loaded_cycles_data[row]

            # Remove from cycle alignment settings
            if hasattr(self.main_window, '_cycle_alignment') and row in self.main_window._cycle_alignment:
                del self.main_window._cycle_alignment[row]

            # Remove row from table
            self.cycle_data_table.removeRow(row)

        # Rebuild cycle alignment indices (they shifted after deletion)
        if hasattr(self.main_window, '_cycle_alignment'):
            new_alignment = {}
            for old_idx, settings in sorted(self.main_window._cycle_alignment.items()):
                # Calculate how many deletions occurred before this index
                shift = sum(1 for deleted_row in row_indices if deleted_row < old_idx)
                new_idx = old_idx - shift
                new_alignment[new_idx] = settings
            self.main_window._cycle_alignment = new_alignment

        logger.info(f"🗑️ Deleted {len(row_indices)} cycle(s) from data table")

        # Show confirmation
        if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'intel_message_label'):
            self.main_window.sidebar.intel_message_label.setText(
                f"🗑️ Deleted {len(row_indices)} cycle{'s' if len(row_indices) > 1 else ''} from data table"
            )
            self.main_window.sidebar.intel_message_label.setStyleSheet(
                "font-size: 12px;"
                "color: #FF9500;"  # Orange for deletion
                "background: transparent;"
                "font-weight: 600;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )

    def _edit_cycle_timing(self, row_index):
        """Open dialog to manually edit cycle start/end times.

        Args:
            row_index: Row index in cycle table
        """
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton, QFormLayout
        from affilabs.utils.logger import logger

        # Get current cycle data
        if not hasattr(self.main_window, '_loaded_cycles_data') or row_index >= len(self.main_window._loaded_cycles_data):
            logger.warning(f"Cannot edit cycle timing - row {row_index} not found in loaded data")
            return

        cycle_data = self.main_window._loaded_cycles_data[row_index]

        # Get current values
        current_start = cycle_data.get('start_time_sensorgram', 0)
        current_end = cycle_data.get('end_time_sensorgram', 0)
        current_duration = cycle_data.get('duration_minutes', 0)

        # Handle NaN values
        if pd.isna(current_start):
            current_start = 0
        if pd.isna(current_end):
            current_end = current_start + (current_duration * 60 if not pd.isna(current_duration) else 0)
        if pd.isna(current_duration):
            current_duration = (current_end - current_start) / 60 if current_end > current_start else 0

        # Create dialog
        dialog = QDialog(self.main_window)
        dialog.setWindowTitle(f"Edit Timing - Cycle {row_index + 1}")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)

        # Info label
        cycle_type = cycle_data.get('type', 'Unknown')
        info_label = QLabel(f"<b>{cycle_type} (Cycle {row_index + 1})</b>")
        info_label.setStyleSheet("font-size: 14px; color: #1D1D1F; padding: 8px;")
        layout.addWidget(info_label)

        # Form layout for timing inputs
        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        # Start time input (seconds)
        start_spin = QDoubleSpinBox()
        start_spin.setRange(0, 999999)
        start_spin.setValue(current_start)
        start_spin.setSuffix(" s")
        start_spin.setDecimals(2)
        start_spin.setMinimumWidth(150)
        start_spin.setStyleSheet("""
            QDoubleSpinBox {
                padding: 6px;
                font-size: 13px;
                border: 1px solid #D1D1D6;
                border-radius: 6px;
            }
            QDoubleSpinBox:focus {
                border: 2px solid #007AFF;
            }
        """)
        form_layout.addRow("Start Time:", start_spin)

        # End time input (seconds)
        end_spin = QDoubleSpinBox()
        end_spin.setRange(0, 999999)
        end_spin.setValue(current_end)
        end_spin.setSuffix(" s")
        end_spin.setDecimals(2)
        end_spin.setMinimumWidth(150)
        end_spin.setStyleSheet(start_spin.styleSheet())
        form_layout.addRow("End Time:", end_spin)

        # Duration (calculated, read-only display)
        duration_label = QLabel(f"{current_duration:.2f} min")
        duration_label.setStyleSheet("font-size: 13px; color: #86868B; padding: 6px;")
        form_layout.addRow("Duration:", duration_label)

        # Auto-update duration when times change
        def update_duration():
            start = start_spin.value()
            end = end_spin.value()
            duration_min = (end - start) / 60
            duration_label.setText(f"{duration_min:.2f} min")
            # Validate times
            if end <= start:
                duration_label.setStyleSheet("font-size: 13px; color: #FF3B30; padding: 6px; font-weight: 600;")
            else:
                duration_label.setStyleSheet("font-size: 13px; color: #86868B; padding: 6px;")

        start_spin.valueChanged.connect(update_duration)
        end_spin.valueChanged.connect(update_duration)

        layout.addLayout(form_layout)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #F2F2F7;
                color: #1D1D1F;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 20px;
            }
            QPushButton:hover {
                background: #E5E5EA;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("✓ Save")
        save_btn.setFixedHeight(36)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #007AFF;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 20px;
            }
            QPushButton:hover {
                background: #0051D5;
            }
        """)

        def save_changes():
            new_start = start_spin.value()
            new_end = end_spin.value()

            # Validate
            if new_end <= new_start:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    dialog,
                    "Invalid Timing",
                    "End time must be after start time!"
                )
                return

            # Update cycle data
            cycle_data['start_time_sensorgram'] = new_start
            cycle_data['end_time_sensorgram'] = new_end
            cycle_data['duration_minutes'] = (new_end - new_start) / 60

            # Update table display
            time_str = f"{cycle_data['duration_minutes']:.1f}m @ {new_start:.0f}s"
            self.cycle_data_table.item(row_index, 1).setText(time_str)

            logger.info(f"✏️ Updated cycle {row_index + 1} timing: {new_start:.2f}s → {new_end:.2f}s ({cycle_data['duration_minutes']:.2f} min)")

            # Show confirmation
            if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'intel_message_label'):
                self.main_window.sidebar.intel_message_label.setText(
                    f"✏️ Updated Cycle {row_index + 1} timing"
                )
                self.main_window.sidebar.intel_message_label.setStyleSheet(
                    "font-size: 12px; color: #34C759; background: transparent; font-weight: 600;"
                )

            dialog.accept()

        save_btn.clicked.connect(save_changes)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

        # Show dialog
        dialog.exec()

    def _update_delta_spr_barchart(self):
        """Update Delta SPR bar chart based on cursor positions."""
        if not hasattr(self, 'delta_spr_bars'):
            return

        start_time = self.delta_spr_start_cursor.value()
        stop_time = self.delta_spr_stop_cursor.value()

        # Ensure start is before stop
        if start_time > stop_time:
            start_time, stop_time = stop_time, start_time

        # Calculate Delta SPR for each channel between cursors
        self.current_delta_values = []  # Store for saving later
        for ch_idx, curve in enumerate(self.edits_graph_curves):
            data = curve.getData()
            if data[0] is None or len(data[0]) == 0:
                self.current_delta_values.append(0)
                continue

            times, values = data

            # Find closest point to start cursor
            start_mask = times >= start_time
            if start_mask.sum() > 0:
                start_idx = np.where(start_mask)[0][0]
                start_value = values[start_idx]
            else:
                self.current_delta_values.append(0)
                continue

            # Find closest point to stop cursor
            stop_mask = times <= stop_time
            if stop_mask.sum() > 0:
                stop_idx = np.where(stop_mask)[0][-1]
                stop_value = values[stop_idx]
            else:
                self.current_delta_values.append(0)
                continue

            # Delta SPR = end value - start value (actual response)
            delta_spr = stop_value - start_value
            self.current_delta_values.append(delta_spr)

        # Update bar heights and value labels
        for i, (bar, delta_val) in enumerate(zip(self.delta_spr_bars, self.current_delta_values)):
            bar.setOpts(height=[delta_val])

            # Update value label position and text
            if hasattr(self, 'delta_spr_labels') and i < len(self.delta_spr_labels):
                label = self.delta_spr_labels[i]
                label.setText(f"{delta_val:.1f}")
                # Position label above bar (with more space) or below if negative
                # Add fixed offset to prevent cutoff
                if delta_val >= 0:
                    label_offset = max(abs(delta_val) * 0.08, 15)  # At least 15 RU above bar
                    label_y = delta_val + label_offset
                else:
                    label_offset = max(abs(delta_val) * 0.08, 15)  # At least 15 RU below bar
                    label_y = delta_val - label_offset
                label.setPos(i, label_y)

        # Auto-scale Y axis (handle negative values too)
        if self.current_delta_values:
            min_delta = min(self.current_delta_values)
            max_delta = max(self.current_delta_values)
            y_range = max_delta - min_delta
            # Increase padding significantly to accommodate labels (25% on each side)
            padding = max(y_range * 0.25, 50)  # At least 50 RU padding for label space
            self.delta_spr_barchart.setYRange(min_delta - padding, max_delta + padding)
        else:
            self.delta_spr_barchart.setYRange(0, 100)

        # Auto-save delta SPR to the currently selected cycle
        row_idx = self.cycle_data_table.currentRow()
        if (row_idx >= 0
                and hasattr(self.main_window, '_loaded_cycles_data')
                and row_idx < len(self.main_window._loaded_cycles_data)):
            cycle = self.main_window._loaded_cycles_data[row_idx]
            ch_labels = ['A', 'B', 'C', 'D']
            delta_parts = []
            for ch_idx, delta_val in enumerate(self.current_delta_values):
                cycle[f'delta_ch{ch_idx + 1}'] = round(delta_val, 2)
                delta_parts.append(f"{ch_labels[ch_idx]}:{delta_val:.0f}")
            # Update ΔSPR column in the table
            delta_str = " ".join(delta_parts)
            self.cycle_data_table.setItem(row_idx, 3, QTableWidgetItem(delta_str))

    def _apply_time_shift(self):
        """Apply time shift to the selected cycle's sensorgram."""
        from PySide6.QtWidgets import QMessageBox
        from affilabs.utils.logger import logger

        # Check if a cycle is selected
        selected_rows = self.cycle_data_table.selectedItems()
        if not selected_rows:
            QMessageBox.warning(
                self.main_window,
                "No Cycle Selected",
                "Please select a cycle in the table to apply time shift."
            )
            return

        # Get the selected row index
        row_idx = self.cycle_data_table.currentRow()
        if row_idx < 0:
            return

        # Get shift value
        try:
            shift_value = float(self.alignment_shift_input.text())
        except ValueError:
            QMessageBox.warning(
                self.main_window,
                "Invalid Input",
                "Please enter a valid number for time shift (in seconds)."
            )
            return

        # Get selected channel
        channel_text = self.alignment_channel_combo.currentText()
        channel_map = {"All": None, "A": 0, "B": 1, "C": 2, "D": 3}
        channel_idx = channel_map.get(channel_text)

        # Update the cycle data with shift
        if hasattr(self.main_window, '_loaded_cycles_data') and row_idx < len(self.main_window._loaded_cycles_data):
            cycle = self.main_window._loaded_cycles_data[row_idx]

            # Store the shift in the cycle data
            if 'shifts' not in cycle:
                cycle['shifts'] = {}

            if channel_idx is None:
                # Apply to all channels
                for ch in range(4):
                    cycle['shifts'][ch] = shift_value
                cycle['shift'] = shift_value  # Also update main shift field
            else:
                # Apply to specific channel
                cycle['shifts'][channel_idx] = shift_value

            # Table display — shift is no longer a visible column

            # Initialize _cycle_alignment if it doesn't exist
            if not hasattr(self.main_window, '_cycle_alignment'):
                self.main_window._cycle_alignment = {}

            # Update the _cycle_alignment dictionary that the graph uses
            ref_text = self.alignment_ref_combo.currentText() if hasattr(self, 'alignment_ref_combo') else 'Global'
            self.main_window._cycle_alignment[row_idx] = {
                'channel': channel_text,
                'shift': shift_value,
                'ref': ref_text,
            }

            # Refresh the graph with shifted data
            if hasattr(self, 'edits_graph_curves'):
                # Re-select the cycle to refresh the display with shift
                self.main_window._on_cycle_selected_in_table()

            logger.info(f"Applied {shift_value}s time shift to cycle {row_idx + 1}, channel {channel_text}")
        else:
            QMessageBox.warning(
                self.main_window,
                "Error",
                "Could not access cycle data. Please reload the data."
            )

    def _auto_align_to_injection(self):
        """Auto-align all loaded cycles so their injection flags line up.

        Uses the first cycle's first injection time as the reference point.
        Calculates the time shift needed for each subsequent cycle to align
        their injection times to the reference.
        """
        from PySide6.QtWidgets import QMessageBox
        from affilabs.utils.logger import logger

        if not hasattr(self.main_window, '_loaded_cycles_data') or not self.main_window._loaded_cycles_data:
            QMessageBox.warning(
                self.main_window,
                "No Data",
                "No cycle data loaded. Please load cycles first."
            )
            return

        cycles_data = self.main_window._loaded_cycles_data

        # Find injection times for all cycles
        injection_times = {}  # {row_idx: first_injection_time}
        for idx, cycle in enumerate(cycles_data):
            flag_data = cycle.get('flag_data', [])
            if not flag_data:
                continue
            # Find the first injection flag in this cycle
            for f in flag_data:
                if f.get('type') == 'injection':
                    injection_times[idx] = f.get('time', 0.0)
                    break  # Use first injection only

        if len(injection_times) == 0:
            QMessageBox.information(
                self.main_window,
                "No Injection Flags",
                "None of the loaded cycles have injection flags.\n\n"
                "Place injection flags during acquisition to use auto-alignment."
            )
            return

        if len(injection_times) == 1:
            QMessageBox.information(
                self.main_window,
                "Single Injection",
                "Only one cycle has an injection flag — no alignment needed.\n\n"
                "Auto-alignment requires at least 2 cycles with injection flags."
            )
            return

        # Use the first cycle (lowest row index) as reference
        reference_idx = min(injection_times.keys())
        reference_time = injection_times[reference_idx]

        # Initialize alignment dict
        if not hasattr(self.main_window, '_cycle_alignment'):
            self.main_window._cycle_alignment = {}

        aligned_count = 0
        for idx, inj_time in injection_times.items():
            shift = reference_time - inj_time
            self.main_window._cycle_alignment[idx] = {
                'channel': 'All',
                'shift': shift
            }
            aligned_count += 1
            logger.info(f"Auto-align: Cycle {idx + 1} injection at {inj_time:.2f}s → shift {shift:+.2f}s (ref={reference_time:.2f}s)")

        # Refresh the graph
        if hasattr(self.main_window, '_on_cycle_selected_in_table'):
            self.main_window._on_cycle_selected_in_table()

        # Update the shift input if a single cycle is selected
        row_idx = self.cycle_data_table.currentRow()
        if row_idx >= 0 and row_idx in self.main_window._cycle_alignment:
            shift_val = self.main_window._cycle_alignment[row_idx]['shift']
            if hasattr(self, 'alignment_shift_input'):
                self.alignment_shift_input.blockSignals(True)
                self.alignment_shift_input.setText(f"{shift_val:.1f}")
                self.alignment_shift_input.blockSignals(False)
            if hasattr(self, 'alignment_shift_slider'):
                self.alignment_shift_slider.blockSignals(True)
                slider_val = int(max(-20.0, min(20.0, shift_val)) * 10)
                self.alignment_shift_slider.setValue(slider_val)
                self.alignment_shift_slider.blockSignals(False)

        QMessageBox.information(
            self.main_window,
            "Auto-Aligned",
            f"✓ Aligned {aligned_count} cycles to injection reference.\n\n"
            f"Reference: Cycle {reference_idx + 1} (injection at {reference_time:.1f}s)\n"
            f"All cycles shifted so injection times match."
        )
        logger.info(f"✓ Auto-aligned {aligned_count} cycles to injection at {reference_time:.2f}s")

    def _find_multiple_injections(self):
        """Find and flag multiple injection points within the selected cycle.

        Uses the existing injection detection algorithm to find all injection
        points within a 60-second window after the first injection.
        """
        from PySide6.QtWidgets import QMessageBox, QInputDialog
        from affilabs.utils.logger import logger
        from affilabs.utils.spr_signal_processing import auto_detect_injection_point
        import numpy as np

        # Get selected cycle
        selected_rows = sorted(set(item.row() for item in self.cycle_data_table.selectedItems()))
        if len(selected_rows) != 1:
            QMessageBox.warning(
                self.main_window,
                "Select Single Cycle",
                "Please select exactly one cycle to detect multiple injections.\n\n"
                "This feature analyzes injection points within a single cycle."
            )
            return

        row_idx = selected_rows[0]

        # Get cycle data
        if not hasattr(self.main_window, '_loaded_cycles_data') or row_idx >= len(self.main_window._loaded_cycles_data):
            QMessageBox.warning(self.main_window, "No Data", "Cycle data not loaded.")
            return

        cycle = self.main_window._loaded_cycles_data[row_idx]

        # Get time window from user
        search_window, ok = QInputDialog.getDouble(
            self.main_window,
            "Search Time Window",
            "Search for injections within how many seconds?\n"
            "(Typical: 60-120 seconds for concentration series)",
            value=60.0,
            min=10.0,
            max=300.0,
            decimals=1
        )
        if not ok:
            return

        # Get raw data
        all_data = cycle.get('all_cycle_data', {})
        if not all_data:
            QMessageBox.warning(self.main_window, "No Data", "No raw data available for this cycle.")
            return

        # Try channels in order: A, B, C, D
        channel_priority = ['a', 'b', 'c', 'd']
        detected_injections = []
        search_start_time = None

        for channel in channel_priority:
            if channel not in all_data or not all_data[channel]:
                continue

            # Extract wavelength data
            data_points = all_data[channel]
            if len(data_points) < 100:
                continue

            times = np.array([p['time'] for p in data_points])
            wavelengths = np.array([p['wavelength'] for p in data_points])

            # Calculate baseline from first 50 points
            baseline = np.mean(wavelengths[:50]) if len(wavelengths) >= 50 else wavelengths[0]

            # Convert to RU
            values_ru = (wavelengths - baseline) * 355.0

            # Search for first injection across full time range
            if search_start_time is None:
                result = auto_detect_injection_point(times, values_ru)
                if result and result.get('confidence', 0) > 0.3:
                    first_injection_time = result['injection_time']
                    search_start_time = first_injection_time
                    detected_injections.append({
                        'time': first_injection_time,
                        'confidence': result['confidence'],
                        'channel': channel.upper()
                    })
                    logger.info(f"First injection detected at t={first_injection_time:.2f}s (channel {channel.upper()}, confidence={result['confidence']:.2%})")
                    break

        if search_start_time is None:
            QMessageBox.information(
                self.main_window,
                "No Injection Found",
                "Could not detect the first injection point.\n\n"
                "Try:\n"
                "• Ensure the cycle has a clear injection spike\n"
                "• Check that SPR signal rises >2 RU\n"
                "• Manually place a flag if auto-detection fails"
            )
            return

        # Now search for additional injections after the first one
        search_end_time = search_start_time + search_window
        search_interval = 5.0  # Look every 5 seconds

        current_search_start = search_start_time + search_interval

        while current_search_start < search_end_time:
            # Get data for this search window
            for channel in channel_priority:
                if channel not in all_data or not all_data[channel]:
                    continue

                data_points = all_data[channel]
                times = np.array([p['time'] for p in data_points])
                wavelengths = np.array([p['wavelength'] for p in data_points])

                # Filter to search window
                mask = (times >= current_search_start) & (times < current_search_start + 30.0)
                if np.sum(mask) < 50:
                    continue

                window_times = times[mask]
                window_wavelengths = wavelengths[mask]

                # Calculate baseline
                baseline = np.mean(window_wavelengths[:20]) if len(window_wavelengths) >= 20 else window_wavelengths[0]
                window_values_ru = (window_wavelengths - baseline) * 355.0

                # Detect injection in this window
                result = auto_detect_injection_point(window_times, window_values_ru)
                if result and result.get('confidence', 0) > 0.3:
                    injection_time = result['injection_time']

                    # Check if this is a new injection (not too close to previous ones)
                    is_new = all(abs(injection_time - inj['time']) > 3.0 for inj in detected_injections)

                    if is_new:
                        detected_injections.append({
                            'time': injection_time,
                            'confidence': result['confidence'],
                            'channel': channel.upper()
                        })
                        logger.info(f"Additional injection detected at t={injection_time:.2f}s (channel {channel.upper()}, confidence={result['confidence']:.2%})")
                        current_search_start = injection_time + search_interval
                        break
                else:
                    current_search_start += search_interval
            else:
                # No injection found in this window across any channel
                current_search_start += search_interval

        # Show results
        if len(detected_injections) == 1:
            QMessageBox.information(
                self.main_window,
                "Single Injection",
                f"Found only 1 injection at t={detected_injections[0]['time']:.1f}s\n\n"
                f"No additional injections detected within {search_window:.0f}s window."
            )
            return

        # Place flags at detected injections
        if not hasattr(cycle, 'flag_data'):
            cycle['flag_data'] = []

        flags_placed = 0
        for i, inj in enumerate(detected_injections):
            # Check if flag already exists at this time
            existing = any(
                abs(f.get('time', 0) - inj['time']) < 1.0 and f.get('type') == 'injection'
                for f in cycle.get('flag_data', [])
            )

            if not existing:
                cycle['flag_data'].append({
                    'time': inj['time'],
                    'type': 'injection',
                    'note': f"Auto-detected injection {i+1} ({inj['confidence']:.0%} confidence)",
                    'channel': inj['channel']
                })
                flags_placed += 1

        # Refresh graph to show new flags
        if hasattr(self.main_window, '_on_cycle_selected_in_table'):
            self.main_window._on_cycle_selected_in_table()

        # Show summary
        summary_lines = [f"✓ Found {len(detected_injections)} injections:\n"]
        for i, inj in enumerate(detected_injections):
            summary_lines.append(f"{i+1}. t={inj['time']:.1f}s (Ch {inj['channel']}, {inj['confidence']:.0%} confidence)")

        summary_lines.append(f"\n{flags_placed} new flags placed.")

        QMessageBox.information(
            self.main_window,
            "Multiple Injections Detected",
            "\n".join(summary_lines)
        )
        logger.info(f"✓ Detected {len(detected_injections)} injections in cycle {row_idx + 1}, placed {flags_placed} new flags")

    def _on_shift_input_changed(self, text):
        """Sync slider when input box changes."""
        try:
            shift_value = float(text)
            # Clamp to slider range
            shift_value = max(-20.0, min(20.0, shift_value))
            slider_value = int(shift_value * 10)  # Convert to 0.1s increments
            self.alignment_shift_slider.blockSignals(True)
            self.alignment_shift_slider.setValue(slider_value)
            self.alignment_shift_slider.blockSignals(False)
        except ValueError:
            pass  # Ignore invalid input

    def _on_shift_slider_changed(self, value):
        """Sync input box when slider changes and apply shift in real-time."""
        shift_value = value / 10.0  # Convert from 0.1s increments to seconds
        self.alignment_shift_input.blockSignals(True)
        self.alignment_shift_input.setText(f"{shift_value:.1f}")
        self.alignment_shift_input.blockSignals(False)

        # Apply shift in real-time (no need to press button)
        self._apply_time_shift()

    def _export_barchart_image(self):
        """Export the delta SPR bar chart as an image."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from datetime import datetime

        # Open file dialog
        default_name = f"delta_spr_barchart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Export Bar Chart",
            default_name,
            "PNG Image (*.png);;JPEG Image (*.jpg);;SVG Image (*.svg);;All Files (*.*)"
        )

        if not file_path:
            return  # User cancelled

        try:
            # Use pyqtgraph's export functionality
            exporter = pg.exporters.ImageExporter(self.delta_spr_barchart.plotItem)

            # Set resolution for better quality
            exporter.parameters()['width'] = 1200

            exporter.export(file_path)

            QMessageBox.information(
                self.main_window,
                "Export Successful",
                f"Bar chart exported to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self.main_window,
                "Export Failed",
                f"Failed to export bar chart:\n{str(e)}"
            )

    def _export_graph_image(self):
        """Export the active cycle graph as an image."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from datetime import datetime

        # Open file dialog
        default_name = f"sensorgram_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Export Sensorgram",
            default_name,
            "PNG Image (*.png);;JPEG Image (*.jpg);;SVG Image (*.svg);;All Files (*.*)"
        )

        if not file_path:
            return  # User cancelled

        try:
            # Use pyqtgraph's export functionality
            exporter = pg.exporters.ImageExporter(self.edits_primary_graph.plotItem)

            # Set resolution for better quality
            exporter.parameters()['width'] = 2400

            exporter.export(file_path)

            QMessageBox.information(
                self.main_window,
                "Export Successful",
                f"Sensorgram exported to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self.main_window,
                "Export Failed",
                f"Failed to export sensorgram:\n{str(e)}"
            )

    def _on_reference_changed(self, text):
        """Handle global reference channel change — refresh graph with subtraction."""
        # Refresh graph to apply/remove reference subtraction
        if hasattr(self.main_window, '_on_cycle_selected_in_table'):
            self.main_window._on_cycle_selected_in_table()

    def _get_effective_ref_channel(self, row_idx):
        """Get the effective reference channel for a cycle.

        Returns channel index (0-3) or None.
        Per-cycle override takes priority over global toolbar setting.
        """
        _REF_MAP = {"None": None, "Ch A": 0, "Ch B": 1, "Ch C": 2, "Ch D": 3}

        # Check per-cycle override
        if hasattr(self.main_window, '_cycle_alignment'):
            per_cycle_ref = self.main_window._cycle_alignment.get(row_idx, {}).get('ref', 'Global')
        else:
            per_cycle_ref = 'Global'

        if per_cycle_ref != 'Global':
            return _REF_MAP.get(per_cycle_ref)

        # Fall back to global toolbar Ref
        if hasattr(self, 'edits_ref_combo'):
            return _REF_MAP.get(self.edits_ref_combo.currentText())
        return None

    def _on_cycle_ref_changed(self, text):
        """Handle per-cycle reference channel change — save and refresh graph."""
        row_idx = self.cycle_data_table.currentRow()
        if row_idx < 0:
            return

        if not hasattr(self.main_window, '_cycle_alignment'):
            self.main_window._cycle_alignment = {}

        if row_idx not in self.main_window._cycle_alignment:
            self.main_window._cycle_alignment[row_idx] = {'channel': 'All', 'shift': 0.0, 'ref': 'Global'}

        self.main_window._cycle_alignment[row_idx]['ref'] = text

        # Refresh graph
        if hasattr(self.main_window, '_on_cycle_selected_in_table'):
            self.main_window._on_cycle_selected_in_table()

    # ── Export Sidebar ───────────────────────────────────────────────────────

    def _create_export_sidebar(self):
        """Create the collapsible export sidebar panel for the Edit tab."""
        sidebar = QFrame()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("""
            QFrame#ExportSidebar {
                background: #FFFFFF;
                border-right: 1px solid #E5E5EA;
                border-radius: 0;
            }
        """)
        sidebar.setObjectName("ExportSidebar")

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent; width: 6px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(0,0,0,0.15); border-radius: 3px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        content = QWidget()
        content.setStyleSheet("background: #FFFFFF;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Header ──
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_icon = QLabel("📤")
        header_icon.setStyleSheet("font-size: 18px; background: transparent;")
        header_row.addWidget(header_icon)
        header_title = QLabel("EXPORT")
        header_title.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #1D1D1F; letter-spacing: 1px;"
            "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "background: transparent;"
        )
        header_row.addWidget(header_title)
        header_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #86868B; border: none; "
            "font-size: 14px; font-weight: bold; border-radius: 12px; }"
            "QPushButton:hover { background: #F5F5F7; color: #1D1D1F; }"
        )
        close_btn.clicked.connect(self._toggle_export_sidebar)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        # Divider
        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.HLine)
        div1.setStyleSheet("border: none; background: #E5E5EA; max-height: 1px;")
        layout.addWidget(div1)

        # ── Export Analysis ──
        export_analysis_btn = self._export_sidebar_button(
            "💾", "Export Analysis",
            "Save cycle table to Excel (.xlsx) or CSV"
        )
        export_analysis_btn.clicked.connect(self._export_table_data)
        layout.addWidget(export_analysis_btn)

        # ── Save Cycles as Method ──
        save_method_btn = self._export_sidebar_button(
            "📋", "Save as Method",
            "Convert cycles to reusable method file (.json)"
        )
        save_method_btn.clicked.connect(self._save_cycles_as_method)
        layout.addWidget(save_method_btn)

        # Divider
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet("border: none; background: #E5E5EA; max-height: 1px;")
        layout.addWidget(div2)

        # ── Export Sensorgram ──
        export_sensorgram_btn = self._export_sidebar_button(
            "📊", "Export Sensorgram",
            "Save active cycle graph as PNG image"
        )
        export_sensorgram_btn.clicked.connect(self._export_graph_image)
        layout.addWidget(export_sensorgram_btn)

        # ── Export ΔSPR Chart ──
        export_dspr_btn = self._export_sidebar_button(
            "📈", "Export ΔSPR Chart",
            "Save bar chart as PNG image"
        )
        export_dspr_btn.clicked.connect(self._export_barchart_image)
        layout.addWidget(export_dspr_btn)

        # Divider
        div3 = QFrame()
        div3.setFrameShape(QFrame.Shape.HLine)
        div3.setStyleSheet("border: none; background: #E5E5EA; max-height: 1px;")
        layout.addWidget(div3)

        # ── Copy to Clipboard ──
        copy_btn = self._export_sidebar_button(
            "📋", "Copy to Clipboard",
            "Copy selected cycles as tab-separated text"
        )
        copy_btn.clicked.connect(self._copy_table_to_clipboard)
        layout.addWidget(copy_btn)

        # ── External Software ──
        external_btn = self._export_sidebar_button(
            "🔗", "External Software",
            "Export formatted for Prism / Origin / other"
        )
        external_btn.clicked.connect(self._export_for_external_software)
        layout.addWidget(external_btn)

        # Spacer
        layout.addSpacing(8)

        # ── Info / Stats Panel ──
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background: #F8F9FA;
                border: 1px solid #E5E5EA;
                border-radius: 8px;
            }
        """)
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(12, 10, 12, 10)
        stats_layout.setSpacing(6)

        stats_title = QLabel("Summary")
        stats_title.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #1D1D1F; "
            "background: transparent; border: none;"
        )
        stats_layout.addWidget(stats_title)

        self.export_stats_cycles = QLabel("Cycles: 0")
        self.export_stats_cycles.setStyleSheet(
            "font-size: 11px; color: #86868B; background: transparent; border: none;"
        )
        stats_layout.addWidget(self.export_stats_cycles)

        self.export_stats_selected = QLabel("Selected: 0")
        self.export_stats_selected.setStyleSheet(
            "font-size: 11px; color: #86868B; background: transparent; border: none;"
        )
        stats_layout.addWidget(self.export_stats_selected)

        self.export_stats_channels = QLabel("Channels: A, B, C, D")
        self.export_stats_channels.setStyleSheet(
            "font-size: 11px; color: #86868B; background: transparent; border: none;"
        )
        stats_layout.addWidget(self.export_stats_channels)

        self.export_stats_duration = QLabel("Duration: —")
        self.export_stats_duration.setStyleSheet(
            "font-size: 11px; color: #86868B; background: transparent; border: none;"
        )
        stats_layout.addWidget(self.export_stats_duration)

        layout.addWidget(stats_frame)

        layout.addStretch()

        scroll.setWidget(content)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.addWidget(scroll)

        return sidebar

    def _export_sidebar_button(self, icon_text, label_text, tooltip_text):
        """Create a styled export sidebar action button.

        Args:
            icon_text: Emoji icon string
            label_text: Button label
            tooltip_text: Tooltip description

        Returns:
            QPushButton with consistent styling
        """
        btn = QPushButton(f"  {icon_text}  {label_text}")
        btn.setFixedHeight(40)
        btn.setToolTip(tooltip_text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: #F8F9FA;
                color: #1D1D1F;
                border: 1px solid #E5E5EA;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 500;
                padding: 8px 12px;
                text-align: left;
                font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton:hover {
                background: #E8F0FE;
                border-color: #007AFF;
                color: #007AFF;
            }
            QPushButton:pressed {
                background: #D1E4FF;
            }
        """)
        return btn

    def _toggle_export_sidebar(self):
        """Toggle the export sidebar visibility."""
        is_visible = self.export_sidebar.isVisible()
        self.export_sidebar.setVisible(not is_visible)

        # Sync toggle button checked state
        if hasattr(self, 'export_toggle_btn'):
            self.export_toggle_btn.setChecked(not is_visible)

        # Update stats when showing
        if not is_visible:
            self._update_export_sidebar_stats()

    def _update_export_sidebar_stats(self):
        """Update the export sidebar summary statistics."""
        if not hasattr(self, 'export_stats_cycles'):
            return

        # Total visible cycles
        total = 0
        for row in range(self.cycle_data_table.rowCount()):
            if not self.cycle_data_table.isRowHidden(row):
                total += 1

        selected_rows = self.cycle_data_table.selectionModel().selectedRows()
        selected = len(selected_rows)

        self.export_stats_cycles.setText(f"Cycles: {total}")
        self.export_stats_selected.setText(f"Selected: {selected}")

        # Channels (always 4 for now)
        self.export_stats_channels.setText("Channels: A, B, C, D")

        # Duration estimate from first/last visible cycle
        first_time = None
        last_time = None
        for row in range(self.cycle_data_table.rowCount()):
            if self.cycle_data_table.isRowHidden(row):
                continue
            time_item = self.cycle_data_table.item(row, 1)
            if time_item and time_item.text().strip():
                time_text = time_item.text().strip()
                if first_time is None:
                    first_time = time_text
                last_time = time_text

        if first_time and last_time:
            self.export_stats_duration.setText(f"Time: {first_time} → {last_time}")
        else:
            self.export_stats_duration.setText("Duration: —")

    def _save_cycles_as_method(self):
        """Convert visible cycle table rows into a reusable method JSON file."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox, QInputDialog
        from pathlib import Path
        from datetime import datetime
        import json

        # Collect visible rows from the cycle table
        cycle_dicts = []
        for row in range(self.cycle_data_table.rowCount()):
            if self.cycle_data_table.isRowHidden(row):
                continue

            # Extract data from table columns
            type_item = self.cycle_data_table.item(row, 0)
            time_item = self.cycle_data_table.item(row, 1)
            conc_item = self.cycle_data_table.item(row, 2)
            flags_item = self.cycle_data_table.item(row, 4)
            notes_item = self.cycle_data_table.item(row, 5)

            # Parse cycle type from display text (e.g., '● BL 1' → 'Baseline')
            raw_type = type_item.text().strip() if type_item else "Custom"
            full_type = type_item.toolTip() if type_item and type_item.toolTip() else raw_type

            # Map abbreviations back to full type names
            type_map = {
                'BL': 'Baseline', 'IM': 'Immobilization', 'WS': 'Wash',
                'CN': 'Concentration', 'RG': 'Regeneration', 'CU': 'Custom',
                'AS': 'Association', 'DS': 'Dissociation', 'BD': 'Binding',
            }
            cycle_type = full_type.split()[0] if full_type else "Custom"
            # Check if it's an abbreviation
            for abbr, full_name in type_map.items():
                if abbr in raw_type:
                    cycle_type = full_name
                    break
            # Also check tooltip for full name
            for full_name in type_map.values():
                if full_name.lower() in full_type.lower():
                    cycle_type = full_name
                    break

            # Parse duration from time column (format: 'Xm @ Ys')
            duration_minutes = 1.0  # default
            if time_item and time_item.text().strip():
                import re
                time_text = time_item.text().strip()
                min_match = re.search(r'(\d+\.?\d*)\s*m', time_text)
                if min_match:
                    duration_minutes = float(min_match.group(1))

            # Parse concentration
            conc_value = None
            conc_units = "nM"
            if conc_item and conc_item.text().strip():
                import re
                conc_text = conc_item.text().strip()
                numbers = re.findall(r'(\d+\.?\d*)', conc_text)
                if numbers:
                    conc_value = float(numbers[0])
                if 'ug/mL' in conc_text or 'µg/mL' in conc_text:
                    conc_units = "ug/mL"

            cycle_dict = {
                "type": cycle_type,
                "length_minutes": duration_minutes,
                "note": notes_item.text().strip() if notes_item else "",
                "pumps": {},
                "contact_times": {},
            }

            # Add concentration if present
            if conc_value is not None:
                cycle_dict["concentration_value"] = conc_value
                cycle_dict["concentration_units"] = conc_units

            # Add flags if present
            if flags_item and flags_item.text().strip():
                cycle_dict["flags"] = flags_item.text().strip()

            cycle_dicts.append(cycle_dict)

        if not cycle_dicts:
            QMessageBox.information(
                self.main_window,
                "No Cycles",
                "No visible cycles to save. Load or record data first."
            )
            return

        # Prompt for method name
        method_name, ok = QInputDialog.getText(
            self.main_window,
            "Save Cycles as Method",
            f"Method name ({len(cycle_dicts)} cycles):",
            text="My Method"
        )

        if not ok or not method_name.strip():
            return

        # Get user profile
        try:
            if self.user_manager:
                username = self.user_manager.get_current_user() or "Default"
            else:
                # Fallback
                from affilabs.services.user_profile_manager import UserProfileManager
                user_mgr = UserProfileManager()
                username = user_mgr.get_current_user() or "Default"
        except Exception:
            username = "Default"

        # Default save directory
        default_dir = Path.home() / "Documents" / "Affilabs Methods" / username
        default_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in method_name.strip())
        default_path = str(default_dir / f"{safe_name}.json")

        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Save Method File",
            default_path,
            "JSON Files (*.json);;All Files (*.*)"
        )

        if not file_path:
            return

        try:
            method_data = {
                "version": "1.0",
                "name": method_name.strip(),
                "description": f"Created from Edit tab cycle table ({len(cycle_dicts)} cycles)",
                "author": username,
                "created": datetime.now().isoformat(),
                "source_experiment": "",
                "cycles": cycle_dicts,
                "cycle_count": len(cycle_dicts),
            }

            # Add experiment source metadata if available
            if (hasattr(self.main_window, 'app') and
                hasattr(self.main_window.app, 'current_experiment_folder') and
                self.main_window.app.current_experiment_folder):
                method_data["source_experiment"] = str(
                    self.main_window.app.current_experiment_folder.name
                )

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(method_data, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ Saved {len(cycle_dicts)} cycles as method: {file_path}")

            QMessageBox.information(
                self.main_window,
                "Method Saved",
                f"Saved {len(cycle_dicts)} cycles as method:\n{file_path}\n\n"
                f"You can load this method in the Method Builder sidebar."
            )

        except Exception as e:
            logger.error(f"Failed to save method: {e}")
            QMessageBox.critical(
                self.main_window,
                "Save Failed",
                f"Failed to save method file:\n{str(e)}"
            )

    def _copy_table_to_clipboard(self):
        """Copy cycle table data to clipboard as tab-separated text."""
        from PySide6.QtWidgets import QMessageBox

        lines = []

        # Header row
        headers = []
        for col in range(self.cycle_data_table.columnCount()):
            if self.cycle_data_table.isColumnHidden(col):
                continue
            header_item = self.cycle_data_table.horizontalHeaderItem(col)
            headers.append(header_item.text().replace('\n', ' ') if header_item else f"Col{col}")
        lines.append('\t'.join(headers))

        # Data rows (selected rows if any, else all visible)
        selected_rows = set()
        for idx in self.cycle_data_table.selectionModel().selectedRows():
            selected_rows.add(idx.row())

        copied_count = 0
        for row in range(self.cycle_data_table.rowCount()):
            if self.cycle_data_table.isRowHidden(row):
                continue
            # If rows are selected, only copy those
            if selected_rows and row not in selected_rows:
                continue

            row_data = []
            for col in range(self.cycle_data_table.columnCount()):
                if self.cycle_data_table.isColumnHidden(col):
                    continue
                item = self.cycle_data_table.item(row, col)
                row_data.append(item.text() if item else "")
            lines.append('\t'.join(row_data))
            copied_count += 1

        if copied_count == 0:
            QMessageBox.information(
                self.main_window,
                "Nothing to Copy",
                "No visible data to copy."
            )
            return

        text = '\n'.join(lines)
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

        logger.info(f"📋 Copied {copied_count} cycles to clipboard")

        # Brief feedback via tooltip on the export sidebar
        if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'intel_message_label'):
            self.main_window.sidebar.intel_message_label.setText(
                f"📋 Copied {copied_count} cycles to clipboard"
            )
        else:
            # Show a brief status on the button itself
            QMessageBox.information(
                self.main_window,
                "Copied",
                f"Copied {copied_count} cycle{'s' if copied_count != 1 else ''} to clipboard.\n"
                "Paste into Excel, Google Sheets, or any spreadsheet."
            )

    def _export_for_external_software(self):
        """Export data formatted for external analysis software (GraphPad Prism, Origin, etc.)."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from datetime import datetime
        import csv

        # Collect visible rows with ΔSPR data
        rows = []
        for row in range(self.cycle_data_table.rowCount()):
            if self.cycle_data_table.isRowHidden(row):
                continue

            type_item = self.cycle_data_table.item(row, 0)
            conc_item = self.cycle_data_table.item(row, 2)
            dspr_item = self.cycle_data_table.item(row, 3)

            cycle_type = type_item.toolTip() if type_item and type_item.toolTip() else (type_item.text() if type_item else "")

            # Parse concentration
            conc_val = ""
            if conc_item and conc_item.text().strip():
                import re
                numbers = re.findall(r'(\d+\.?\d*)', conc_item.text())
                if numbers:
                    conc_val = numbers[0]

            # Parse ΔSPR per channel (format: 'A:val B:val C:val D:val')
            dspr_a = dspr_b = dspr_c = dspr_d = ""
            if dspr_item and dspr_item.text().strip():
                import re
                dspr_text = dspr_item.text()
                for ch_match in re.finditer(r'([ABCD]):([+-]?\d+\.?\d*)', dspr_text):
                    ch, val = ch_match.group(1), ch_match.group(2)
                    if ch == 'A': dspr_a = val
                    elif ch == 'B': dspr_b = val
                    elif ch == 'C': dspr_c = val
                    elif ch == 'D': dspr_d = val

            rows.append({
                "type": cycle_type,
                "concentration": conc_val,
                "dspr_a": dspr_a,
                "dspr_b": dspr_b,
                "dspr_c": dspr_c,
                "dspr_d": dspr_d,
            })

        if not rows:
            QMessageBox.information(
                self.main_window,
                "No Data",
                "No visible cycle data to export."
            )
            return

        # File dialog
        default_name = f"SPR_external_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Export for External Software",
            default_name,
            "CSV Files (*.csv);;All Files (*.*)"
        )

        if not file_path:
            return

        try:
            # Write in column-oriented format suitable for Prism/Origin
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Header
                writer.writerow([
                    "Cycle Type", "Concentration",
                    "ΔSPR Ch A (RU)", "ΔSPR Ch B (RU)", "ΔSPR Ch C (RU)", "ΔSPR Ch D (RU)"
                ])

                for row in rows:
                    writer.writerow([
                        row["type"], row["concentration"],
                        row["dspr_a"], row["dspr_b"], row["dspr_c"], row["dspr_d"]
                    ])

            logger.info(f"✅ Exported {len(rows)} rows for external software: {file_path}")

            QMessageBox.information(
                self.main_window,
                "Export Successful",
                f"Exported {len(rows)} cycles to:\n{file_path}\n\n"
                "Format: CSV with columns for Concentration, ΔSPR per channel.\n"
                "Compatible with GraphPad Prism, Origin, and Excel."
            )

        except Exception as e:
            logger.error(f"Failed to export for external software: {e}")
            QMessageBox.critical(
                self.main_window,
                "Export Failed",
                f"Failed to export:\n{str(e)}"
            )

    def _export_table_data(self):
        """Export the cycle data table (analysis results) to CSV or Excel file."""
        from PySide6.QtWidgets import QFileDialog
        import csv
        from datetime import datetime
        from pathlib import Path
        from affilabs.utils.time_utils import filename_timestamp

        # Ensure experiment folder exists
        exp_folder = self._ensure_experiment_folder()

        # Get default save location in Analysis subfolder
        if exp_folder:
            analysis_folder = self.main_window.app.experiment_folder_mgr.get_subfolder_path(
                exp_folder, "Analysis"
            )
            default_name = f"Analysis_{filename_timestamp()}.xlsx"
            default_path = str(analysis_folder / default_name)
        else:
            # Fallback if no experiment folder
            default_name = f"Analysis_{filename_timestamp()}.xlsx"
            default_path = default_name

        # Open file dialog
        file_filter = "Excel Files (*.xlsx);;CSV Files (*.csv);;All Files (*.*)"
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self.main_window,
            "Export Analysis",
            default_path,
            file_filter
        )

        if not file_path:
            return  # User cancelled

        try:
            # Collect visible rows only (respect filter)
            rows_data = []
            header = []

            # Get column headers
            for col in range(self.cycle_data_table.columnCount()):
                if not self.cycle_data_table.isColumnHidden(col):
                    header_item = self.cycle_data_table.horizontalHeaderItem(col)
                    header.append(header_item.text().replace('\n', ' ') if header_item else f"Column {col}")

            rows_data.append(header)

            # Get visible row data
            for row in range(self.cycle_data_table.rowCount()):
                if self.cycle_data_table.isRowHidden(row):
                    continue  # Skip filtered out rows

                row_data = []
                for col in range(self.cycle_data_table.columnCount()):
                    if self.cycle_data_table.isColumnHidden(col):
                        continue  # Skip hidden columns

                    item = self.cycle_data_table.item(row, col)
                    cell_value = item.text() if item else ""
                    row_data.append(cell_value)

                rows_data.append(row_data)

            # Write to file
            if file_path.endswith('.xlsx'):
                # Excel export (if pandas available)
                try:
                    import pandas as pd
                    df = pd.DataFrame(rows_data[1:], columns=rows_data[0])
                    df.to_excel(file_path, index=False, engine='openpyxl')
                    logger.info(f"✅ Exported {len(rows_data)-1} cycles to Excel: {file_path}")
                except ImportError:
                    logger.warning("pandas not available, falling back to CSV export")
                    file_path = file_path.replace('.xlsx', '.csv')
                    self._write_csv(file_path, rows_data)
            else:
                # CSV export
                self._write_csv(file_path, rows_data)

            # Register file in experiment metadata (if using experiment folder)
            if exp_folder and Path(file_path).is_relative_to(exp_folder):
                self.main_window.app.experiment_folder_mgr.register_file(
                    exp_folder,
                    Path(file_path),
                    "analysis",
                    f"Cycle analysis table with {len(rows_data)-1} cycles"
                )
                logger.debug(f"Registered analysis file in experiment metadata")

            # Show success message
            if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'intel_message_label'):
                self.main_window.sidebar.intel_message_label.setText(
                    f"✅ Exported {len(rows_data)-1} cycles to {file_path.split('/')[-1]}"
                )
                self.main_window.sidebar.intel_message_label.setStyleSheet(
                    "font-size: 12px; color: #34C759; background: transparent; font-weight: 600;"
                )

        except Exception as e:
            logger.error(f"Failed to export table data: {e}")
            if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'intel_message_label'):
                self.main_window.sidebar.intel_message_label.setText(f"❌ Export failed: {str(e)}")

    def _write_csv(self, file_path, rows_data):
        """Write data to CSV file."""
        import csv
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(rows_data)
        logger.info(f"✅ Exported {len(rows_data)-1} cycles to CSV: {file_path}")

    def _apply_compact_view_initial(self):
        """Apply initial column visibility based on compact_view flag."""
        if self.compact_view:
            self.cycle_data_table.setColumnHidden(1, True)  # Time
            self.cycle_data_table.setColumnHidden(5, True)  # Notes

    def _toggle_compact_view(self):
        """Toggle between compact and expanded table view."""
        self.compact_view = not self.compact_view

        if self.compact_view:
            # Hide less important columns in compact view
            self.cycle_data_table.setColumnHidden(1, True)   # Time
            self.cycle_data_table.setColumnHidden(5, True)   # Notes
        else:
            # Show all columns in expanded view
            for col in range(6):
                self.cycle_data_table.setColumnHidden(col, False)

    def _apply_cycle_filter(self, filter_text):
        """Filter cycles by type based on priority (concentration is key, baseline less important)."""
        self.cycle_filter = filter_text

        # Priority mapping
        priority_map = {
            "All": ["Binding", "Association", "Dissociation", "Baseline", "Regeneration", "Wash", "Prime"],
            "Binding (High)": ["Binding", "Association", "Dissociation"],
            "Baseline (Low)": ["Baseline"],
            "Regeneration (Med)": ["Regeneration", "Wash"]
        }

        allowed_types = priority_map.get(filter_text, priority_map["All"])

        # Show/hide rows based on filter
        for row in range(self.cycle_data_table.rowCount()):
            cycle_type_item = self.cycle_data_table.item(row, 0)
            if cycle_type_item:
                # Use tooltip which stores full type name (e.g. 'Baseline 1')
                cycle_type = cycle_type_item.toolTip() or cycle_type_item.text()
                # Check if cycle type matches filter
                show_row = any(allowed in cycle_type for allowed in allowed_types)
                self.cycle_data_table.setRowHidden(row, not show_row)

        # Re-apply search filter if active
        if hasattr(self, 'search_box') and self.search_box.text():
            self._apply_search_filter(self.search_box.text())

        # Apply color coding for missing data
        self._apply_row_color_coding()

        # Update metadata stats
        self._update_metadata_stats()

    def _apply_search_filter(self, search_text):
        """Filter table rows based on search text across all columns."""
        search_text = search_text.lower().strip()

        # First, restore all rows that were hidden by previous search
        # (but respect cycle filter)
        for row in range(self.cycle_data_table.rowCount()):
            # Check if row should be visible based on cycle filter
            cycle_type_item = self.cycle_data_table.item(row, 0)
            if cycle_type_item:
                cycle_type = cycle_type_item.toolTip() or cycle_type_item.text()
                priority_map = {
                    "All": ["Binding", "Association", "Dissociation", "Baseline", "Regeneration", "Wash", "Prime"],
                    "Binding (High)": ["Binding", "Association", "Dissociation"],
                    "Baseline (Low)": ["Baseline"],
                    "Regeneration (Med)": ["Regeneration", "Wash"]
                }
                allowed_types = priority_map.get(self.cycle_filter, priority_map["All"])
                show_by_filter = any(allowed in cycle_type for allowed in allowed_types)
            else:
                show_by_filter = True

            if not search_text:
                # No search text - show row if cycle filter allows it
                self.cycle_data_table.setRowHidden(row, not show_by_filter)
            elif show_by_filter:
                # Search active - check if row matches
                row_matches = False
                for col in range(self.cycle_data_table.columnCount()):
                    if self.cycle_data_table.isColumnHidden(col):
                        continue

                    item = self.cycle_data_table.item(row, col)
                    if item and search_text in item.text().lower():
                        row_matches = True
                        break

                # Show row only if it matches search AND passes cycle filter
                self.cycle_data_table.setRowHidden(row, not row_matches)
            else:
                # Hidden by cycle filter
                self.cycle_data_table.setRowHidden(row, True)

        # Apply color coding after filtering
        self._apply_row_color_coding()

        # Update metadata stats
        self._update_metadata_stats()

    def _apply_row_color_coding(self):
        """Color code rows based on missing critical information."""
        for row in range(self.cycle_data_table.rowCount()):
            if self.cycle_data_table.isRowHidden(row):
                continue

            # Check for missing concentration (col 2) or notes (col 5)
            conc_item = self.cycle_data_table.item(row, 2)
            notes_item = self.cycle_data_table.item(row, 5)

            conc_missing = not conc_item or not conc_item.text().strip()
            notes_missing = not notes_item or not notes_item.text().strip()

            # Apply red background if critical data is missing
            if conc_missing or notes_missing:
                for col in range(self.cycle_data_table.columnCount()):
                    item = self.cycle_data_table.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 230, 230))  # Light red
            else:
                # Clear background (alternating rows handled by stylesheet)
                for col in range(self.cycle_data_table.columnCount()):
                    item = self.cycle_data_table.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 255, 255))  # White

    def _show_columns_menu(self):
        """Show menu to hide/unhide columns (triggered by button click)."""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtCore import QPoint

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: white;
                border: 1px solid #D1D1D6;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                font-size: 11px;
            }
            QMenu::item:selected {
                background: #007AFF;
                color: white;
            }
        """)

        # Get column names (6-column layout)
        column_names = [
            "Type", "Time", "Conc.", "ΔSPR", "Flags", "Notes"
        ]

        # Create checkable actions for each column
        for col, name in enumerate(column_names):
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(not self.cycle_data_table.isColumnHidden(col))
            action.setData(col)  # Store column index
            action.triggered.connect(lambda checked, c=col: self._toggle_column_visibility(c, checked))

        # Show menu below the columns button (use stored reference)
        if hasattr(self, 'columns_btn') and self.columns_btn is not None:
            pos = self.columns_btn.mapToGlobal(QPoint(0, self.columns_btn.height()))
            menu.exec(pos)
        else:
            # Fallback: show at cursor
            menu.exec(QCursor.pos())

    def _show_column_visibility_menu(self, position):
        """Show context menu to hide/unhide columns (right-click on header - kept for advanced users)."""
        # Just call the same menu function
        self._show_columns_menu()

    def _toggle_column_visibility(self, col, visible):
        """Toggle column visibility."""
        self.cycle_data_table.setColumnHidden(col, not visible)

    # =========================
    # INJECTION AUTO-DETECTION
    # =========================

    def _on_auto_detect_toggled(self, state):
        """Handle auto-detect checkbox toggle with visual feedback."""
        self._auto_detect_enabled = (state == Qt.CheckState.Checked.value)

        if self._auto_detect_enabled:
            # Show feedback and re-run detection
            if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'intel_message_label'):
                self.main_window.sidebar.intel_message_label.setText(
                    "💉 Injection marker enabled - Detecting injection point..."
                )
                self.main_window.sidebar.intel_message_label.setStyleSheet(
                    "font-size: 14px; color: #007AFF; background: transparent; font-weight: 600;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )

            # Re-run detection on currently selected cycle
            self._run_injection_detection()
        else:
            # Hide injection marker and show feedback
            self._hide_injection_marker()

            if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'intel_message_label'):
                self.main_window.sidebar.intel_message_label.setText(
                    "Injection marker hidden"
                )
                self.main_window.sidebar.intel_message_label.setStyleSheet(
                    "font-size: 14px; color: #8E8E93; background: transparent; font-weight: 500;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )

        logger.info(f"Injection marker: {'shown' if self._auto_detect_enabled else 'hidden'}")

    def _run_injection_detection(self):
        """Run auto-detection on currently selected cycle and show marker."""
        if not self._auto_detect_enabled:
            return

        # Get selected cycle
        selected_rows = sorted(set(item.row() for item in self.cycle_data_table.selectedItems()))
        if len(selected_rows) != 1:
            # Only auto-detect for single selection
            self._hide_injection_marker()
            return

        row_idx = selected_rows[0]

        # Check if already detected (and not manually corrected)
        if row_idx in self._injection_points and not self._injection_points[row_idx].get('manual_override', False):
            # Already detected, just show marker
            self._show_injection_marker(row_idx)
            return

        # Get cycle data
        if not hasattr(self.main_window, '_loaded_cycles_data') or row_idx >= len(self.main_window._loaded_cycles_data):
            return

        cycle = self.main_window._loaded_cycles_data[row_idx]

        # Extract data for detection (use first active channel)
        raw_data = None
        if hasattr(self.main_window.app, 'recording_mgr') and self.main_window.app.recording_mgr:
            if hasattr(self.main_window.app.recording_mgr, 'data_collector'):
                raw_data = self.main_window.app.recording_mgr.data_collector.raw_data_rows

        if not raw_data:
            logger.debug("No raw data available for injection detection")
            return

        # Get cycle time boundaries
        start_time = cycle.get('start_time_sensorgram', 0)
        end_time = cycle.get('end_time_sensorgram', 0)

        # Extract channel data (try A first, then B, C, D)
        for channel in ['a', 'b', 'c', 'd']:
            times_list = []
            values_list = []

            for row in raw_data:
                if row.get('channel') != channel:
                    continue

                time = row.get('time', 0)
                if start_time <= time <= end_time:
                    value = row.get('value')
                    if pd.notna(time) and pd.notna(value):
                        times_list.append(time)
                        values_list.append(value)

            if len(times_list) > 50:  # Need sufficient data points
                # Found data - run detection
                times = np.array(times_list)
                values = np.array(values_list)

                # Sort by time
                sort_idx = np.argsort(times)
                times = times[sort_idx]
                values = values[sort_idx]

                # Convert to RU (baseline correction)
                if len(values) > 0:
                    baseline = values[0]
                    values_ru = (values - baseline) * 355.0
                else:
                    values_ru = values

                # Run auto-detection
                from affilabs.utils.spr_signal_processing import auto_detect_injection_point
                result = auto_detect_injection_point(times, values_ru)

                if result['injection_time'] is not None and result['confidence'] > 0.3:
                    # Store detection result
                    self._injection_points[row_idx] = {
                        'time': result['injection_time'],
                        'channel': channel.upper(),
                        'confidence': result['confidence'],
                        'auto': True,
                        'manual_override': False,
                    }

                    logger.info(
                        f"→ Auto-detected injection in Cycle {row_idx + 1} at t={result['injection_time']:.2f}s "
                        f"(Channel {channel.upper()}, confidence: {result['confidence']:.2f})"
                    )

                    # Show marker
                    self._show_injection_marker(row_idx)
                    return

        logger.debug(f"Could not auto-detect injection in Cycle {row_idx + 1}")

    def _show_injection_marker(self, row_idx):
        """Show draggable injection marker on graph."""
        if row_idx not in self._injection_points:
            return

        injection_data = self._injection_points[row_idx]
        injection_time = injection_data['time']

        # Remove old marker if exists
        if self._injection_marker is not None:
            try:
                self.edits_primary_graph.removeItem(self._injection_marker)
            except:
                pass

        # Create draggable vertical line
        self._injection_marker = pg.InfiniteLine(
            pos=injection_time,
            angle=90,  # Vertical
            pen=pg.mkPen(color=(255, 59, 48, 200), width=3, style=Qt.PenStyle.DashLine),
            movable=True,  # Allow dragging
            label="Injection",
            labelOpts={'position': 0.85, 'color': (255, 59, 48), 'fill': (255, 255, 255, 200), 'movable': False}
        )

        # Connect drag signal for manual correction
        self._injection_marker.sigPositionChanged.connect(lambda: self._on_injection_marker_moved(row_idx))

        self.edits_primary_graph.addItem(self._injection_marker)

        # Update intelligence bar
        confidence_pct = int(injection_data['confidence'] * 100)
        if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'intel_message_label'):
            self.main_window.sidebar.intel_message_label.setText(
                f"Injection detected at t={injection_time:.2f}s ({confidence_pct}% confidence) - Drag line to adjust"
            )
            self.main_window.sidebar.intel_message_label.setStyleSheet(
                "font-size: 14px; color: #007AFF; background: transparent; font-weight: 600;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )

    def _hide_injection_marker(self):
        """Hide injection marker from graph."""
        if self._injection_marker is not None:
            try:
                self.edits_primary_graph.removeItem(self._injection_marker)
            except:
                pass
            self._injection_marker = None

    def _on_injection_marker_moved(self, row_idx):
        """Handle manual adjustment of injection marker."""
        if self._injection_marker is None:
            return

        new_time = self._injection_marker.value()

        # Update stored injection point
        if row_idx in self._injection_points:
            old_time = self._injection_points[row_idx]['time']
            self._injection_points[row_idx]['time'] = new_time
            self._injection_points[row_idx]['manual_override'] = True  # Mark as manually corrected
            self._injection_points[row_idx]['auto'] = False

            logger.info(f"Injection point manually adjusted: {old_time:.2f}s → {new_time:.2f}s")

            # Update intelligence bar
            if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'intel_message_label'):
                self.main_window.sidebar.intel_message_label.setText(
                    f"✓ Injection corrected to t={new_time:.2f}s (manual)"
                )
                self.main_window.sidebar.intel_message_label.setStyleSheet(
                    "font-size: 14px; color: #34C759; background: transparent; font-weight: 600;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )
