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
    QWidget, QGridLayout, QScrollArea, QToolButton, QMenu, QTabWidget,
)
from PySide6.QtCore import Qt, QSize, QObject, QEvent, QUrl
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap, QPainter, QDesktopServices
from PySide6.QtSvg import QSvgRenderer
from affilabs.utils.resource_path import get_affilabs_resource

from affilabs.utils.logger import logger
from affilabs.ui_styles import Colors, Fonts


class _AlignChannelProxy:
    """Thin proxy so alignment_mixin can call .currentText() / blockSignals() as before.

    Wraps the channel button group (All/A/B/C/D) that replaced the QComboBox,
    exposing the same minimal API used by _edits_cycle_mixin.
    """
    def __init__(self):
        self._value = "All"
        self._btn_map: dict = {}   # populated by UIBuildersMixin after buttons are created

    def currentText(self) -> str:
        return self._value

    def setCurrentText(self, text: str) -> None:
        """Update internal value AND sync button visual state."""
        self._value = text
        # Sync button highlight if buttons have been wired in
        if self._btn_map:
            _ch_colors = {"All": "#86868B", "A": "#1D1D1F", "B": "#FF3B30",
                          "C": "#007AFF", "D": "#34C759"}
            for lbl, btn in self._btn_map.items():
                checked = lbl == text
                color = _ch_colors.get(lbl, "#86868B")
                if checked:
                    btn.setStyleSheet(
                        f"QPushButton {{ background: white; color: {color};"
                        f" border: 2px solid {color}; border-radius: 5px;"
                        f" font-size: 11px; font-weight: 700; padding: 0 6px; }}"
                    )
                else:
                    btn.setStyleSheet(
                        "QPushButton { background: #E5E5EA; color: #808080;"
                        " border: 2px solid #C7C7CC; border-radius: 5px;"
                        " font-size: 11px; font-weight: 700; padding: 0 6px; }"
                    )

    def blockSignals(self, block: bool) -> bool:  # noqa: N802  (matches Qt naming)
        return False


class _EditsEventFilter(QObject):
    """QObject shim so EditsTab (not a QObject) can be used as an event filter.

    Delegates all decisions to the EditsTab instance via its eventFilter method
    (defined in AlignmentMixin), which handles:
      - Ctrl+click on A/B/C/D channel buttons
      - Left/Right arrow on edits_primary_graph
      - Resize on edits_primary_graph → reposition legend
    """

    def __init__(self, edits_tab, parent=None):
        super().__init__(parent)
        self._tab = edits_tab

    def eventFilter(self, obj, event):
        return self._tab.eventFilter(obj, event)


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

        # Initialize table widget — 6-column layout; Score column hidden by default
        # STARTS EMPTY - will be populated ONLY when cycles complete during live acquisition
        self.cycle_data_table = QTableWidget(0, 6)
        self.cycle_data_table.setHorizontalHeaderLabels(
            ["Export", "Type", "Time", "Conc.", "ΔSPR", "Score"]
        )
        # Set column widths: stretch to fill available space
        header = self.cycle_data_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)       # Export checkbox
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)       # Type icon
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)     # Time
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)     # Conc
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)     # ΔSPR
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)       # Score
        header.setStretchLastSection(False)
        self.cycle_data_table.setColumnWidth(0, 50)    # Export checkbox (fixed)
        self.cycle_data_table.setColumnWidth(1, 55)    # Type icon (fixed minimum)
        self.cycle_data_table.setColumnWidth(5, 58)    # Score (fixed)
        self.cycle_data_table.setColumnHidden(5, True) # Hidden by default — revealed via column menu

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
            "Automated cycle quality score (0–100). Select the Quality tab below for details.",
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

        # Initialize primary graph using shared helpers so it matches live-data style
        # (axis colours, grid, clipToView, autoDownsample, connect='finite', active palette)
        from affilabs.plot_helpers import create_time_plot, add_channel_curves, _active_channel_colors
        self.edits_primary_graph = create_time_plot(
            left_label='Response (RU)',
            bottom_label='Time (s)',
        )
        self.edits_primary_graph.setMenuEnabled(True)
        self.edits_primary_graph.showGrid(x=True, y=True, alpha=0.2)

        self.edits_graph_curves = add_channel_curves(self.edits_primary_graph, width=2)

        # Channel-end labels (shown when a curve has data)
        self.edits_graph_curve_labels = []
        active_colors = _active_channel_colors()
        for i, ch_name in enumerate('ABCD'):
            label = pg.TextItem(text=ch_name, color=active_colors[i], anchor=(0, 0.5))
            label.setFont(pg.Qt.QtGui.QFont("Arial", 9, pg.Qt.QtGui.QFont.Bold))
            label.hide()
            self.edits_primary_graph.addItem(label)
            self.edits_graph_curve_labels.append(label)

        content_widget = QFrame()
        content_widget.setStyleSheet("QFrame { background: #F8F9FA; border: none; }")

        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(12)

        # Main content container with optional export sidebar
        outer_layout = QHBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Main horizontal split: Table LEFT | Graphs RIGHT
        main_splitter = QSplitter(Qt.Horizontal)

        # LEFT SIDE: Vertical split (Table TOP | Metadata BOTTOM)
        left_splitter = QSplitter(Qt.Vertical)

        # LEFT TOP: Cycle table with notes panel
        table_details_widget = QFrame()
        table_details_layout = QVBoxLayout(table_details_widget)
        table_details_layout.setContentsMargins(0, 0, 0, 0)
        table_details_layout.setSpacing(8)

        table_widget = self._create_table_panel()
        table_details_layout.addWidget(table_widget, 1)

        # Cycle details panel — shown below table when a cycle is selected.
        # Two tabs: Notes (user notes / flags) and Quality (automated score + reasoning).
        self.details_tab_widget = QTabWidget()
        self.details_tab_widget.setStyleSheet("""
            QTabWidget::pane {
                background: white;
                border: 1px solid #E5E5EA;
                border-radius: 6px;
            }
            QTabBar::tab {
                font-size: 11px;
                padding: 3px 10px;
                background: #F8F9FA;
                color: #6E6E73;
                border: 1px solid #E5E5EA;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: white;
                color: #1D1D1F;
                font-weight: 600;
            }
        """)

        # --- Tab 1: Notes ---
        notes_tab = QWidget()
        notes_tab_layout = QVBoxLayout(notes_tab)
        notes_tab_layout.setContentsMargins(8, 4, 8, 4)
        notes_tab_layout.setSpacing(2)
        self.details_notes_text = QLabel("")
        self.details_notes_text.setWordWrap(True)
        self.details_notes_text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.details_notes_text.setStyleSheet(
            "QLabel { color: #1D1D1F; font-size: 12px;"
            " background: transparent; border: none; padding: 2px 0; }"
        )
        notes_tab_layout.addWidget(self.details_notes_text, 1)
        self.details_flags_text = QLabel("")
        self.details_tab_widget.addTab(notes_tab, "Notes")

        # --- Tab 2: Quality ---
        quality_tab = QWidget()
        quality_tab_layout = QVBoxLayout(quality_tab)
        quality_tab_layout.setContentsMargins(8, 4, 8, 4)
        quality_tab_layout.setSpacing(4)

        score_header_row = QHBoxLayout()
        self.details_score_dot = QLabel("●")
        self.details_score_dot.setStyleSheet(
            "QLabel { font-size: 14px; background: transparent; border: none; }"
        )
        self.details_score_label = QLabel("")
        self.details_score_label.setStyleSheet(
            "QLabel { font-size: 13px; font-weight: 700; background: transparent; border: none; color: #1D1D1F; }"
        )
        score_header_row.addWidget(self.details_score_dot)
        score_header_row.addWidget(self.details_score_label)
        score_header_row.addStretch()
        quality_tab_layout.addLayout(score_header_row)

        self.details_quality_note = QLabel("")
        self.details_quality_note.setWordWrap(True)
        self.details_quality_note.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.details_quality_note.setStyleSheet(
            "QLabel { color: #3C3C43; font-size: 12px;"
            " background: transparent; border: none; padding: 1px 0; }"
        )
        quality_tab_layout.addWidget(self.details_quality_note, 1)
        self.details_tab_widget.addTab(quality_tab, "Quality")

        self.details_tab_widget.setMaximumHeight(110)
        self.details_tab_widget.hide()
        table_details_layout.addWidget(self.details_tab_widget)

        left_splitter.addWidget(table_details_widget)

        # LEFT BOTTOM: Metadata panel
        metadata_panel = self._create_metadata_panel()
        left_splitter.addWidget(metadata_panel)

        # Stub alignment widgets so mixin code keeps working
        self._create_alignment_stubs()

        # Match vertical proportion to right side so the divider aligns: 55% table / 45% metadata
        left_splitter.setStretchFactor(0, 55)
        left_splitter.setStretchFactor(1, 45)

        main_splitter.addWidget(left_splitter)

        # RIGHT: Graphs + tools bar
        right_container = QWidget()
        right_vbox = QVBoxLayout(right_container)
        right_vbox.setContentsMargins(0, 0, 0, 0)
        right_vbox.setSpacing(0)

        graphs_splitter = QSplitter(Qt.Vertical)

        # TOP: Active Cycle View with cursors (55%)
        selection_widget = self._create_active_selection()
        graphs_splitter.addWidget(selection_widget)

        # BOTTOM: Tabbed panel — ΔSPR bar chart + Binding plot (45%)
        analysis_container = QFrame()
        analysis_container.setObjectName("AnalysisContainer")
        analysis_container.setStyleSheet(
            "#AnalysisContainer { background: white; border-radius: 12px; }"
        )
        an_shadow = QGraphicsDropShadowEffect()
        an_shadow.setBlurRadius(8)
        an_shadow.setColor(QColor(0, 0, 0, 20))
        an_shadow.setOffset(0, 2)
        analysis_container.setGraphicsEffect(an_shadow)
        an_vbox = QVBoxLayout(analysis_container)
        an_vbox.setContentsMargins(0, 0, 0, 0)
        an_vbox.setSpacing(0)

        # Title strip
        an_title_strip = QFrame()
        an_title_strip.setStyleSheet(
            "QFrame { background: white; border-bottom: 1px solid #E5E5EA; }"
        )
        an_title_layout = QHBoxLayout(an_title_strip)
        an_title_layout.setContentsMargins(16, 10, 16, 10)
        an_title_lbl = QLabel("Analysis")
        an_title_lbl.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #1D1D1F; "
            "background: transparent; letter-spacing: -0.2px;"
        )
        an_title_layout.addWidget(an_title_lbl)
        an_vbox.addWidget(an_title_strip)

        self.bottom_tab_widget = QTabWidget()
        self.bottom_tab_widget.setStyleSheet("""
            QTabBar::tab { padding: 4px 14px; background: white; color: #1D1D1F; }
            QTabBar::tab:selected { background: #E3F2FD; color: #0066CC; font-weight: 600; }
            QTabBar::tab:hover { background: #F5F5F5; }
            QTabWidget::pane { border: none; }
        """)
        barchart_widget = self._create_delta_spr_barchart()
        self.bottom_tab_widget.addTab(barchart_widget, "ΔSPR")
        binding_widget = self._create_binding_panel()
        self.bottom_tab_widget.addTab(binding_widget, "Binding")
        self.bottom_tab_widget.currentChanged.connect(self._on_bottom_tab_changed)
        an_vbox.addWidget(self.bottom_tab_widget, 1)
        graphs_splitter.addWidget(analysis_container)

        graphs_splitter.setStretchFactor(0, 55)
        graphs_splitter.setStretchFactor(1, 45)

        right_vbox.addWidget(graphs_splitter, 1)

        main_splitter.addWidget(right_container)

        main_splitter.setStretchFactor(0, 50)
        main_splitter.setStretchFactor(1, 50)
        main_splitter.setMinimumWidth(800)
        table_widget.setMinimumWidth(300)

        # Export sidebar (hidden by default)
        self.export_sidebar = self._create_export_sidebar()
        self.export_sidebar.setVisible(False)
        outer_layout.addWidget(self.export_sidebar)
        outer_layout.addWidget(main_splitter, 1)

        content_layout.addLayout(outer_layout)

        self._apply_compact_view_initial()
        self.cycle_data_table.setColumnHidden(self.TABLE_COL_CONC, True)

        self.main_window.cycle_data_table         = self.cycle_data_table
        self.main_window.edits_timeline_graph     = self.edits_timeline_graph
        self.main_window.edits_primary_graph      = self.edits_primary_graph
        self.main_window.edits_timeline_curves    = self.edits_timeline_curves
        self.main_window.edits_graph_curves       = self.edits_graph_curves
        self.main_window.edits_graph_curve_labels = self.edits_graph_curve_labels
        self.main_window.edits_timeline_cursors   = self.edits_timeline_cursors
        self.main_window.edits_smooth_slider      = self.edits_smooth_slider
        self.main_window.edits_smooth_label       = self.edits_smooth_label
        self.main_window.bottom_tab_widget        = self.bottom_tab_widget
        self.main_window.binding_ch_btns          = self.binding_ch_btns
        self.main_window.binding_scatter_plot     = self.binding_scatter_plot


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
        container.setStyleSheet("QFrame { background: #F5F6F8; border-radius: 12px; }")
        container.setMinimumWidth(300)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 14, 16, 0)
        layout.setSpacing(10)

        # ── Section title bar ──────────────────────────────────────────────
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        title = QLabel("Recorded Cycles")
        title.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {Colors.PRIMARY_TEXT}; "
            f"font-family: {Fonts.DISPLAY}; letter-spacing: -0.2px;"
        )
        title_row.addWidget(title)
        title_row.addStretch()

        # Compact Export button in title row
        title_export_btn = QToolButton()
        title_export_btn.setText(" Export")
        _exp_svg = get_affilabs_resource("ui/img/export_package_icon.svg")
        if _exp_svg and _exp_svg.exists():
            _exp_src = _exp_svg.read_text(encoding="utf-8").replace("currentColor", "white")
            _exp_ren = QSvgRenderer(_exp_src.encode("utf-8"))
            _exp_px = QPixmap(QSize(13, 13))
            _exp_px.fill(Qt.GlobalColor.transparent)
            _exp_p = QPainter(_exp_px)
            _exp_ren.render(_exp_p)
            _exp_p.end()
            title_export_btn.setIcon(QIcon(_exp_px))
            title_export_btn.setIconSize(QSize(13, 13))
            title_export_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        else:
            title_export_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        title_export_btn.setFixedHeight(26)
        title_export_btn.setMinimumWidth(88)
        title_export_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        title_export_btn.setStyleSheet("""
            QToolButton {
                background: #1D1D1F; color: white; border-radius: 7px;
                font-size: 11px; font-weight: 600; padding: 2px 10px;
                border: none;
            }
            QToolButton:hover { background: #3A3A3C; }
            QToolButton::menu-button {
                border-left: 1px solid rgba(255,255,255,0.2);
                border-radius: 0px 7px 7px 0px;
                width: 16px;
            }
            QToolButton::menu-arrow { image: none; }
        """)
        title_export_btn.clicked.connect(self._export_package)
        _title_export_menu = QMenu(self.main_window)
        _title_export_menu.setStyleSheet("""
            QMenu { background: white; border: 1px solid #E5E5EA;
                    border-radius: 8px; padding: 4px; }
            QMenu::item { padding: 8px 16px; font-size: 12px; color: #1D1D1F;
                          border-radius: 6px; }
            QMenu::item:selected { background: #F0F0F0; }
            QMenu::separator { height: 1px; background: #E5E5EA; margin: 4px 8px; }
        """)
        _title_export_menu.addAction("📊  Excel + Charts",   self._export_post_edit_analysis_with_charts)
        _title_export_menu.addAction("💾  Excel only",         self._export_table_data)
        _title_export_menu.addSeparator()
        _title_export_menu.addAction("🖼  Sensorgram PNG",    self._export_graph_image)
        _title_export_menu.addAction("📈  ΔSPR Chart PNG",     self._export_barchart_image)
        _title_export_menu.addSeparator()
        _title_export_menu.addAction("📋  Copy to clipboard",   self._copy_table_to_clipboard)
        _title_export_menu.addAction("🔗  External (Prism / Origin)", self._export_for_external_software)
        _title_export_menu.addAction("📋  Save as Method",     self._save_cycles_as_method)
        _title_export_menu.addSeparator()
        _title_export_menu.addAction("📐  TraceDrawer (.zip)",  self._export_tracedrawer)
        title_export_btn.setMenu(_title_export_menu)
        title_row.addWidget(title_export_btn)

        # Sparq Coach — waitlist (feature coming soon)
        _SPARQ_WAITLIST_URL = "https://www.affilabs.com/sparq-coach"  # replace with Wix waitlist URL
        sparq_coach_btn = QToolButton()
        sparq_coach_btn.setText("✦ Sparq Coach")
        sparq_coach_btn.setFixedHeight(26)
        sparq_coach_btn.setToolTip(
            "Sparq Coach — Coming Soon\n\n"
            "Get a personalised debrief after every run: bubble fixes, regen tips,\n"
            "concentration advice, and product recommendations.\n\n"
            "Click to join the early access list."
        )
        sparq_coach_btn.setStyleSheet("""
            QToolButton {
                background: transparent;
                color: #8E8E93;
                border: 1px dashed #C7C7CC;
                border-radius: 5px;
                padding: 2px 10px;
                font-size: 12px;
            }
            QToolButton:hover {
                color: #636366;
                border-color: #8E8E93;
                background: #F5F5F7;
            }
        """)
        sparq_coach_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(_SPARQ_WAITLIST_URL))
        )
        title_row.addWidget(sparq_coach_btn)
        self._sparq_coach_btn = sparq_coach_btn

        layout.addLayout(title_row)

        # Thin divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("border: none; border-top: 1px solid #E5E5EA; margin: 0;")
        layout.addWidget(divider)

        # View and filter controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        # Load button (matching control style)
        load_btn = QPushButton(" Load")
        _folder_svg = get_affilabs_resource("ui/img/folder_icon.svg")
        if _folder_svg.exists():
            load_btn.setIcon(QIcon(str(_folder_svg)))
            load_btn.setIconSize(QSize(14, 14))
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
            f"font-size: 12px; color: {Colors.SECONDARY_TEXT}; font-family: {Fonts.SYSTEM};"
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
        layout.addWidget(self.cycle_data_table, 1)

        return container

    def _create_metadata_panel(self):
        """Create metadata info panel showing experiment statistics."""
        panel = QFrame()
        panel.setStyleSheet("QFrame { background: #F5F6F8; border-radius: 12px; }")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        panel.setGraphicsEffect(shadow)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # ── Section title bar ──────────────────────────────────────────────
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Experiment")
        title.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #1D1D1F; "
            "border: none; background: transparent; letter-spacing: -0.2px;"
        )
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        # Thin divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("border: none; border-top: 1px solid #E5E5EA; margin: 0;")
        layout.addWidget(divider)

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

        # Session row — Date + Operator combined
        session_lbl = QLabel("Session:")
        session_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        session_row = QWidget()
        session_row.setStyleSheet("background: transparent; border: none;")
        session_row_layout = QHBoxLayout(session_row)
        session_row_layout.setContentsMargins(0, 0, 0, 0)
        session_row_layout.setSpacing(4)
        self.meta_date = QLabel("-")
        self.meta_date.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        _sep_dot = QLabel("·")
        _sep_dot.setStyleSheet("font-size: 12px; color: #C7C7CC; background: transparent; border: none;")
        self.meta_operator = QLabel("-")
        self.meta_operator.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        session_row_layout.addWidget(self.meta_date)
        session_row_layout.addWidget(_sep_dot)
        session_row_layout.addWidget(self.meta_operator)
        session_row_layout.addStretch()
        grid.addWidget(session_lbl, 4, 0, Qt.AlignLeft)
        grid.addWidget(session_row, 4, 1, Qt.AlignLeft)

        # Device + Calibration row combined
        device_lbl = QLabel("Device:")
        device_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        device_cal_row = QWidget()
        device_cal_row.setStyleSheet("background: transparent; border: none;")
        device_cal_layout = QHBoxLayout(device_cal_row)
        device_cal_layout.setContentsMargins(0, 0, 0, 0)
        device_cal_layout.setSpacing(4)
        self.meta_device = QLabel("-")
        self.meta_device.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        _sep_dot2 = QLabel("·")
        _sep_dot2.setStyleSheet("font-size: 12px; color: #C7C7CC; background: transparent; border: none;")
        self.meta_calibration = QLabel("-")
        self.meta_calibration.setStyleSheet("font-size: 11px; color: #AEAEB2; background: transparent; border: none;")
        self.meta_calibration.setToolTip("Startup calibration file used for this session")
        # Hidden stub — kept as attribute so setText() calls in edits_tab.py don't crash
        self.meta_transmission_file = QLabel("-")
        self.meta_transmission_file.hide()
        self.meta_transmission_file.setToolTip("Transmission baseline recording (5-min baseline cycle)")
        device_cal_layout.addWidget(self.meta_device)
        device_cal_layout.addWidget(_sep_dot2)
        device_cal_layout.addWidget(self.meta_calibration)
        device_cal_layout.addStretch()
        grid.addWidget(device_lbl, 5, 0, Qt.AlignLeft)
        grid.addWidget(device_cal_row, 5, 1, Qt.AlignLeft)

        # Rating row
        rating_lbl = QLabel("Rating:")
        rating_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        stars_widget = QWidget()
        stars_widget.setStyleSheet("background: transparent; border: none;")
        stars_layout = QHBoxLayout(stars_widget)
        stars_layout.setContentsMargins(0, 0, 0, 0)
        stars_layout.setSpacing(2)
        self.meta_star_buttons: list = []
        for i in range(1, 6):
            btn = QPushButton("★")
            btn.setFixedSize(22, 22)
            btn.setCheckable(False)
            btn.setObjectName(f"meta_star_{i}")
            btn.setStyleSheet("""
                QPushButton#meta_star_1, QPushButton#meta_star_2, QPushButton#meta_star_3,
                QPushButton#meta_star_4, QPushButton#meta_star_5 {
                    background: transparent;
                    border: none;
                    font-size: 16px;
                    color: #D1D1D6;
                    padding: 0px;
                }
                QPushButton#meta_star_1:hover, QPushButton#meta_star_2:hover,
                QPushButton#meta_star_3:hover, QPushButton#meta_star_4:hover,
                QPushButton#meta_star_5:hover {
                    color: #FF9500;
                }
            """)
            _n = i
            btn.clicked.connect(lambda checked, n=_n: self._on_star_clicked(n))
            stars_layout.addWidget(btn)
            self.meta_star_buttons.append(btn)
        stars_layout.addStretch()
        grid.addWidget(rating_lbl, 6, 0, Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(stars_widget, 6, 1, Qt.AlignLeft)

        # Tags row
        tags_lbl = QLabel("Tags:")
        tags_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #1D1D1F; background: transparent; border: none;")
        tags_outer = QWidget()
        tags_outer.setStyleSheet("background: transparent; border: none;")
        tags_outer_layout = QVBoxLayout(tags_outer)
        tags_outer_layout.setContentsMargins(0, 0, 0, 0)
        tags_outer_layout.setSpacing(4)

        # Pills container (rebuilt on every refresh)
        self.meta_tags_pills = QWidget()
        self.meta_tags_pills.setStyleSheet("background: transparent; border: none;")
        self._meta_tags_pills_layout = QHBoxLayout(self.meta_tags_pills)
        self._meta_tags_pills_layout.setContentsMargins(0, 0, 0, 0)
        self._meta_tags_pills_layout.setSpacing(4)
        self._meta_tags_pills_layout.addStretch()
        tags_outer_layout.addWidget(self.meta_tags_pills)

        # Tag input row
        tag_input_row = QHBoxLayout()
        tag_input_row.setSpacing(4)
        self.meta_tag_input = QLineEdit()
        self.meta_tag_input.setPlaceholderText("Add tag…")
        self.meta_tag_input.setFixedHeight(24)
        self.meta_tag_input.setStyleSheet("""
            QLineEdit {
                background: #F8F9FA;
                border: 1px solid #D1D1D6;
                border-radius: 4px;
                font-size: 11px;
                padding: 2px 6px;
                color: #1D1D1F;
            }
            QLineEdit:focus { border: 1px solid #007AFF; background: white; }
        """)
        self.meta_tag_input.returnPressed.connect(self._on_tag_added)
        tag_input_row.addWidget(self.meta_tag_input, 1)

        add_tag_btn = QPushButton("+")
        add_tag_btn.setObjectName("meta_add_tag_btn")
        add_tag_btn.setFixedSize(24, 24)
        add_tag_btn.setStyleSheet("""
            QPushButton#meta_add_tag_btn {
                background: #007AFF;
                border: none;
                border-radius: 4px;
                color: white;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton#meta_add_tag_btn:hover { background: #0051D5; }
            QPushButton#meta_add_tag_btn:pressed { background: #003FA3; }
        """)
        add_tag_btn.clicked.connect(self._on_tag_added)
        tag_input_row.addWidget(add_tag_btn)
        tags_outer_layout.addLayout(tag_input_row)

        grid.addWidget(tags_lbl, 7, 0, Qt.AlignLeft | Qt.AlignTop)
        grid.addWidget(tags_outer, 7, 1, Qt.AlignLeft)

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

    def _create_alignment_stubs(self):
        """Create invisible stub widgets for alignment controls.

        The alignment panel has been removed from the UI. These stubs satisfy
        the hasattr() guards in _alignment_mixin and _edits_cycle_mixin so
        existing logic (ref subtraction, shift, channel filter) keeps working
        without a visible panel.
        """
        # Invisible dummy panel — keeps .show()/.hide() calls safe
        self.alignment_panel = QWidget()
        self.alignment_title = QLabel()
        self.alignment_flags_display = QLabel()

        self.alignment_ref_combo = QComboBox()
        self.alignment_ref_combo.addItems(["Global", "None", "Ch A", "Ch B", "Ch C", "Ch D"])
        self.alignment_ref_combo.currentTextChanged.connect(self._on_cycle_ref_changed)

        _ch_colors = {"All": "#86868B", "A": "#1D1D1F", "B": "#FF3B30", "C": "#007AFF", "D": "#34C759"}

        def _ch_btn_style(color, checked):
            if checked:
                return (f"QPushButton {{ background: white; color: {color};"
                        f" border: 2px solid {color}; border-radius: 5px;"
                        f" font-size: 11px; font-weight: 700; padding: 0 6px; }}")
            return ("QPushButton { background: #E5E5EA; color: #808080;"
                    " border: 2px solid #C7C7CC; border-radius: 5px;"
                    " font-size: 11px; font-weight: 700; padding: 0 6px; }")

        self._alignment_ch_btns = {}
        self.alignment_channel_combo = _AlignChannelProxy()

        def _on_ch_btn(selected):
            for lbl, btn in self._alignment_ch_btns.items():
                btn.setStyleSheet(_ch_btn_style(_ch_colors[lbl], lbl == selected))
            self.alignment_channel_combo._value = selected
            self._on_alignment_channel_changed(selected)

        for label in ["All", "A", "B", "C", "D"]:
            btn = QPushButton(label)
            btn.setStyleSheet(_ch_btn_style(_ch_colors[label], label == "All"))
            btn.clicked.connect(lambda checked=False, lbl=label: _on_ch_btn(lbl))
            self._alignment_ch_btns[label] = btn

        self.alignment_channel_combo._btn_map = self._alignment_ch_btns

        self.alignment_shift_input = QLineEdit("0.0")
        self.alignment_shift_input.textChanged.connect(self._on_shift_input_changed)

        self.alignment_shift_slider = QSlider(Qt.Horizontal)
        self.alignment_shift_slider.setRange(-200, 200)
        self.alignment_shift_slider.setValue(0)
        self.alignment_shift_slider.valueChanged.connect(self._on_shift_slider_changed)

    def _create_alignment_panel(self):
        """DEPRECATED — panel removed; stubs created via _create_alignment_stubs."""
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

        # Channel selector — inline buttons matching live channel toggle style
        ch_layout = QHBoxLayout()
        ch_layout.setSpacing(6)
        ch_label = QLabel("Channel:")
        ch_label.setStyleSheet("font-size: 12px; color: #1D1D1F; font-weight: 500; background: transparent; border: none;")
        ch_layout.addWidget(ch_label)

        _ch_colors = {"All": "#86868B", "A": "#1D1D1F", "B": "#FF3B30", "C": "#007AFF", "D": "#34C759"}

        def _ch_btn_style(color, checked):
            if checked:
                return (
                    f"QPushButton {{ background: white; color: {color};"
                    f" border: 2px solid {color}; border-radius: 5px;"
                    f" font-size: 11px; font-weight: 700; padding: 0 6px; }}"
                )
            return (
                "QPushButton { background: #E5E5EA; color: #808080;"
                " border: 2px solid #C7C7CC; border-radius: 5px;"
                " font-size: 11px; font-weight: 700; padding: 0 6px; }"
            )

        self._alignment_ch_btns = {}
        self.alignment_channel_combo = _AlignChannelProxy()  # keeps _alignment_mixin API intact

        def _on_ch_btn(selected):
            for lbl, btn in self._alignment_ch_btns.items():
                btn.setStyleSheet(_ch_btn_style(_ch_colors[lbl], lbl == selected))
            self.alignment_channel_combo._value = selected
            self._on_alignment_channel_changed(selected)

        for label in ["All", "A", "B", "C", "D"]:
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setMinimumWidth(30 if label != "All" else 36)
            btn.setStyleSheet(_ch_btn_style(_ch_colors[label], label == "All"))
            btn.clicked.connect(lambda checked=False, lbl=label: _on_ch_btn(lbl))
            ch_layout.addWidget(btn)
            self._alignment_ch_btns[label] = btn

        ch_layout.addStretch()
        layout.addLayout(ch_layout)

        # Wire proxy so setCurrentText() can sync button visuals on cycle selection restore
        self.alignment_channel_combo._btn_map = self._alignment_ch_btns

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
        hint_lbl.setStyleSheet("font-size: 11px; color: #6E6E73; font-style: italic; background: transparent; border: none;")
        shift_layout.addWidget(hint_lbl)

        layout.addLayout(shift_layout)

        layout.addStretch()

        return panel

    def _create_active_selection(self):
        """Middle right panel: Active selection view for detailed cycle analysis."""
        container = QFrame()
        container.setObjectName("editsSelectionContainer")
        container.setStyleSheet("#editsSelectionContainer { background: white; border-radius: 12px; }")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # ── Section title bar ──────────────────────────────────────────────
        sel_title_row = QHBoxLayout()
        sel_title_row.setContentsMargins(0, 0, 0, 0)
        sel_title_row.setSpacing(6)
        sel_title_lbl = QLabel("Selected Cycle")
        sel_title_lbl.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #1D1D1F; "
            "background: transparent; letter-spacing: -0.2px;"
        )
        sel_title_row.addWidget(sel_title_lbl)
        sel_title_row.addStretch()

        # Helper: render SVG file → QIcon with given CSS colour
        def _svg_icon(rel_path: str, color: str, size: int = 14) -> QIcon:
            p = get_affilabs_resource(rel_path)
            if not p or not p.exists():
                return QIcon()
            src = p.read_text(encoding="utf-8").replace("currentColor", color)
            renderer = QSvgRenderer(src.encode("utf-8"))
            px = QPixmap(QSize(size, size))
            px.fill(Qt.GlobalColor.transparent)
            painter = QPainter(px)
            renderer.render(painter)
            painter.end()
            return QIcon(px)

        # Lock/Unlock cursor button — two-state SVG icon
        _btn_style = (
            "QPushButton { background: #F2F2F7; border: 1px solid #D1D1D6; "
            "border-radius: 6px; padding: 3px 8px; font-size: 11px; font-weight: 600; "
            "color: #3C3C43; }"
            "QPushButton:hover { background: #E5E5EA; border-color: #007AFF; }"
            "QPushButton:checked { background: #34C759; border-color: #28A745; color: white; }"
        )
        self.delta_spr_lock_btn = QPushButton(" Unlock")  # icon is set below; text is icon label only
        self.delta_spr_lock_btn.setCheckable(True)
        self.delta_spr_lock_btn.setFixedHeight(26)
        self.delta_spr_lock_btn.setToolTip(
            "Unlock: drag the Start/Stop cursors manually.\n"
            "Lock: auto-position cursors from injection contact time."
        )
        self.delta_spr_lock_btn.setStyleSheet(_btn_style)
        _lock_icon = _svg_icon("ui/img/lock_icon.svg", "#3C3C43")
        _unlock_icon = _svg_icon("ui/img/unlock_icon.svg", "#3C3C43")
        # Build two-state icon
        _two_state = QIcon()
        if not _unlock_icon.isNull():
            _two_state.addPixmap(
                _unlock_icon.pixmap(QSize(14, 14)), QIcon.Mode.Normal, QIcon.State.Off
            )
        if not _lock_icon.isNull():
            _lock_icon_white = _svg_icon("ui/img/lock_icon.svg", "white")
            _two_state.addPixmap(
                _lock_icon_white.pixmap(QSize(14, 14)), QIcon.Mode.Normal, QIcon.State.On
            )
        if not _two_state.isNull():
            self.delta_spr_lock_btn.setIcon(_two_state)
            self.delta_spr_lock_btn.setIconSize(QSize(14, 14))
        self.delta_spr_lock_btn.toggled.connect(self._toggle_delta_spr_lock)
        sel_title_row.addWidget(self.delta_spr_lock_btn)

        # Reset bar chart button
        _reset_btn_style = (
            "QPushButton { background: #F2F2F7; border: 1px solid #D1D1D6; "
            "border-radius: 6px; padding: 0; }"
            "QPushButton:hover { background: #E5E5EA; border-color: #007AFF; }"
        )
        reset_bar_btn = QPushButton()
        reset_bar_btn.setFixedSize(26, 26)
        reset_bar_btn.setToolTip("Reset ΔSPR chart view")
        reset_bar_btn.setStyleSheet(_reset_btn_style)
        _reset_icon = _svg_icon("ui/img/reset_icon.svg", "#3C3C43")
        if not _reset_icon.isNull():
            reset_bar_btn.setIcon(_reset_icon)
            reset_bar_btn.setIconSize(QSize(14, 14))
        else:
            reset_bar_btn.setText("⟲")
        reset_bar_btn.clicked.connect(lambda: (
            self.delta_spr_barchart.autoRange(),
            self.delta_spr_barchart.setXRange(-0.5, 3.5, padding=0),
        ))
        sel_title_row.addWidget(reset_bar_btn)

        # Smooth slider — inline in title row
        _sep = QFrame()
        _sep.setFrameShape(QFrame.Shape.VLine)
        _sep.setFixedHeight(16)
        _sep.setStyleSheet("color: #D1D1D6; background: #D1D1D6; margin: 0 2px;")
        sel_title_row.addWidget(_sep)
        _smooth_lbl_hdr = QLabel("Smooth:")
        _smooth_lbl_hdr.setStyleSheet(
            "font-size: 11px; color: #86868B; background: transparent;"
        )
        sel_title_row.addWidget(_smooth_lbl_hdr)
        self.edits_smooth_label = QLabel("off")
        self.edits_smooth_label.setStyleSheet(
            "font-size: 11px; color: #86868B; min-width: 24px; background: transparent;"
        )
        sel_title_row.addWidget(self.edits_smooth_label)
        self.edits_smooth_slider = QSlider(Qt.Horizontal)
        self.edits_smooth_slider.setRange(0, 50)
        self.edits_smooth_slider.setValue(0)
        self.edits_smooth_slider.setFixedWidth(120)
        self.edits_smooth_slider.setFixedHeight(18)
        self.edits_smooth_slider.setToolTip("Savitzky-Golay smoothing window (0 = off)")
        self.edits_smooth_slider.valueChanged.connect(lambda v: (
            self.edits_smooth_label.setText("off" if v == 0 else f"{v} pts"),
            self._on_smooth_changed(),
        ))
        sel_title_row.addWidget(self.edits_smooth_slider)

        layout.addLayout(sel_title_row)
        # Thin divider
        sel_div = QFrame()
        sel_div.setFrameShape(QFrame.Shape.HLine)
        sel_div.setStyleSheet("border: none; border-top: 1px solid #E5E5EA; margin: 0;")
        layout.addWidget(sel_div)

        # QObject shim — required because EditsTab is not a QObject, but
        # installEventFilter() requires a QObject. Shim delegates to self.eventFilter().
        self._edits_event_filter = _EditsEventFilter(self, parent=self.main_window)

        # Header: [A][B][C][D]  →  cycle name label
        header = QHBoxLayout()
        header.setSpacing(8)

        self.edits_channel_buttons = {}
        self._edits_ref_channel: str | None = None
        from affilabs.ui_styles import get_channel_button_style
        # Use hardcoded CSS-safe hex colors — same as live Active Cycle graph.
        # ACTIVE_GRAPH_COLORS can return "k" (matplotlib) which is invalid CSS.
        _CH_COLORS = {"A": "#1D1D1F", "B": "#FF3B30", "C": "#007AFF", "D": "#34C759"}

        for ch in ["A", "B", "C", "D"]:
            ch_btn = QPushButton(ch)
            ch_btn.setCheckable(True)
            ch_btn.setChecked(True)
            ch_btn.setFixedSize(32, 28)
            ch_btn.setToolTip(f"Toggle Channel {ch}\nCtrl+click to set/clear as reference channel")
            color = _CH_COLORS[ch]
            ch_btn.setProperty("channel_color", color)
            ch_btn.setProperty("channel_letter", ch)
            ch_btn.setStyleSheet(get_channel_button_style(color))
            ch_idx = ord(ch) - ord('A')
            ch_btn.clicked.connect(lambda _, idx=ch_idx, b=ch_btn: self._toggle_channel(idx, b.isChecked()))
            ch_btn.installEventFilter(self._edits_event_filter)
            self.edits_channel_buttons[ch] = ch_btn
            header.addWidget(ch_btn)

        header.addStretch()

        # Start / End time — compact, right of centre
        self.alignment_start_time = QLabel("")
        self.alignment_start_time.setStyleSheet(
            "font-size: 12px; color: #6E6E73; background: transparent;"
        )
        self.alignment_start_time.setVisible(False)
        header.addWidget(self.alignment_start_time)

        self.alignment_end_time = QLabel("")
        self.alignment_end_time.setStyleSheet(
            "font-size: 12px; color: #6E6E73; background: transparent;"
        )
        self.alignment_end_time.setVisible(False)
        header.addWidget(self.alignment_end_time)

        header.addSpacing(8)

        self.cycle_context_label = QLabel("Select a cycle")
        self.cycle_context_label.setStyleSheet(
            "font-size: 13px; color: #86868B; background: transparent;"
        )
        header.addWidget(self.cycle_context_label)

        layout.addLayout(header)

        # Selection graph (reuse existing primary graph)
        self.edits_primary_graph.setBackground('w')
        self.edits_primary_graph.showGrid(x=True, y=True, alpha=0.2)

        # Add Delta SPR measurement cursors (start/stop)
        self.delta_spr_start_cursor = pg.InfiniteLine(
            pos=0, angle=90, movable=True,
            pen=pg.mkPen(color='#34C759', width=2, style=Qt.PenStyle.DashLine),
            label='Start', labelOpts={
                'position': 0.85, 'color': '#34C759',
                'fill': (255, 255, 255, 200),  # white bg — prevents ghost traces on drag
            }
        )
        self.delta_spr_stop_cursor = pg.InfiniteLine(
            pos=100, angle=90, movable=True,
            pen=pg.mkPen(color='#FF3B30', width=2, style=Qt.PenStyle.DashLine),
            label='Stop', labelOpts={
                'position': 0.85, 'color': '#FF3B30',
                'fill': (255, 255, 255, 200),  # white bg — prevents ghost traces on drag
            }
        )
        self.edits_primary_graph.addItem(self.delta_spr_start_cursor)
        self.edits_primary_graph.addItem(self.delta_spr_stop_cursor)

        # Disable paint caching on cursor lines — prevents ghost traces when dragging.
        # pyqtgraph InfiniteLine caches its bounding-rect paint; without NoCache the old
        # painted region is never invalidated when the line moves.
        from PySide6.QtWidgets import QGraphicsItem
        self.delta_spr_start_cursor.setCacheMode(QGraphicsItem.CacheMode.NoCache)
        self.delta_spr_stop_cursor.setCacheMode(QGraphicsItem.CacheMode.NoCache)

        # Connect cursor movement to Delta SPR calculation
        self.delta_spr_start_cursor.sigPositionChanged.connect(self._update_delta_spr_barchart)
        self.delta_spr_stop_cursor.sigPositionChanged.connect(self._update_delta_spr_barchart)

        # ── Floating Δ SPR legend (same widget as live-view Active Cycle graph) ──
        try:
            from affilabs.widgets.interactive_spr_legend import InteractiveSPRLegend
            from PySide6.QtCore import QTimer as _QTimer
            self.edits_spr_legend = InteractiveSPRLegend(
                parent=self.edits_primary_graph,
                title="Δ SPR (RU)",
            )
            self.edits_spr_legend.setVisible(False)  # shown once a cycle is loaded
            self.edits_spr_legend.raise_()
            # Wire legend channel click → alignment channel selector (mirrors live-view)
            self.edits_spr_legend.channel_timing_selected.connect(
                self._on_edits_legend_channel_selected
            )
            # Defer positioning 200ms so layout has settled (mirrors live-view pattern)
            _QTimer.singleShot(200, self._position_edits_legend)
        except Exception:
            self.edits_spr_legend = None

        # ── Keyboard navigation: ←/→ steps through cycles in the table ──
        self.edits_primary_graph.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.edits_primary_graph.installEventFilter(self._edits_event_filter)

        layout.addWidget(self.edits_primary_graph, 1)

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
        title = QLabel("ΔSPR (RU) · Response Between Cursors")
        title.setStyleSheet("font-size: 13px; font-weight: 600; color: #1D1D1F;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Bar chart
        self.delta_spr_barchart = pg.PlotWidget()
        self.delta_spr_barchart.setMenuEnabled(True)  # Enable context menu for export options
        self.delta_spr_barchart.setBackground('w')
        self.delta_spr_barchart.setYRange(0, 100)
        self.delta_spr_barchart.setXRange(-0.5, 3.5, padding=0)
        self.delta_spr_barchart.getAxis('bottom').setTicks([[(0, 'Ch A'), (1, 'Ch B'), (2, 'Ch C'), (3, 'Ch D')]])
        self.delta_spr_barchart.setLabel('left', 'ΔSPR (RU)')
        self.delta_spr_barchart.setMinimumHeight(160)  # Floor only — no ceiling
        self.delta_spr_barchart.showGrid(y=True, alpha=0.2)
        self.delta_spr_barchart.getViewBox().setMouseEnabled(x=False, y=True)

        # Add baseline indicator at y=0
        baseline = pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen(color='#86868B', width=1, style=Qt.DashLine))
        self.delta_spr_barchart.addItem(baseline)

        # Create bar graph items — colors MUST match active palette (ACTIVE_GRAPH_COLORS)
        self.delta_spr_bars = []
        from affilabs.settings import settings as _settings
        _ch_keys = ['a', 'b', 'c', 'd']
        bar_colors = [_settings.ACTIVE_GRAPH_COLORS.get(ch, '#1D1D1F') for ch in _ch_keys]

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

    def _position_edits_legend(self):
        """Pin the Δ SPR legend to the top-left of edits_primary_graph (mirrors graphs.py)."""
        legend = getattr(self, 'edits_spr_legend', None)
        if legend is None:
            return
        legend.adjustSize()
        left_axis_w = 58   # approx Y-axis width in pyqtgraph
        legend.move(left_axis_w + 8, 8)
        legend.raise_()

    # ------------------------------------------------------------------
    # Bottom tab handler
    # ------------------------------------------------------------------

    def _on_bottom_tab_changed(self, index: int):
        """Called when ΔSPR/Binding tab is switched."""
        if index == 1:  # Binding tab activated
            self.cycle_data_table.setColumnHidden(self.TABLE_COL_CONC, False)
            self._update_binding_plot()

    # ------------------------------------------------------------------
    # Binding panel construction
    # ------------------------------------------------------------------

    def _create_binding_panel(self):
        """Build the Binding Plot panel (Tab 1 of bottom_tab_widget)."""
        from PySide6.QtWidgets import QSplitter

        container = QFrame()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(8, 6, 8, 6)
        vbox.setSpacing(6)

        # --- Controls bar ---
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(6)

        ch_colors = ['#1D1D1F', '#FF3B30', '#007AFF', '#34C759']
        self.binding_ch_btns = []
        for i, (ch, color) in enumerate(zip('ABCD', ch_colors)):
            btn = QPushButton(ch)
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setFixedSize(28, 24)
            btn.setStyleSheet(
                f"QPushButton {{ border: 1px solid #D1D1D6; border-radius: 4px;"
                f" background: white; color: #1D1D1F; font-size: 12px; font-weight: 500; }}"
                f"QPushButton:checked {{ border: 2px solid {color}; color: {color}; font-weight: 700; }}"
                f"QPushButton:disabled {{ color: #C7C7CC; border: 1px solid #E5E5EA; background: #F8F9FA; }}"
            )
            btn.clicked.connect(lambda _, idx=i: self._on_binding_ch_clicked(idx))
            ctrl_bar.addWidget(btn)
            self.binding_ch_btns.append(btn)

        ctrl_bar.addSpacing(12)
        ctrl_bar.addWidget(QLabel("Model:"))
        self.binding_model_combo = QComboBox()
        self.binding_model_combo.addItems(["Linear", "1:1 Langmuir"])
        self.binding_model_combo.setFixedWidth(160)
        self.binding_model_combo.currentTextChanged.connect(lambda _: self._update_binding_plot())
        ctrl_bar.addWidget(self.binding_model_combo)



        ctrl_bar.addStretch()
        vbox.addLayout(ctrl_bar)

        # --- Horizontal split: scatter plot | formula panel ---
        hsplit = QSplitter(Qt.Horizontal)

        self.binding_scatter_plot = pg.PlotWidget()
        self.binding_scatter_plot.setBackground('w')
        self.binding_scatter_plot.setLabel('left', 'ΔSPR (RU)')
        self.binding_scatter_plot.setLabel('bottom', 'Concentration (nM)')
        self.binding_scatter_plot.showGrid(x=False, y=False)
        hsplit.addWidget(self.binding_scatter_plot)

        # Formula panel
        formula_frame = QFrame()
        formula_frame.setObjectName("BindingFormulaPanel")
        formula_frame.setStyleSheet(
            "QFrame#BindingFormulaPanel { background: white; border: 1px solid #E5E5EA; border-radius: 6px; }"
        )
        fpanel = QVBoxLayout(formula_frame)
        fpanel.setContentsMargins(10, 10, 10, 10)
        fpanel.setSpacing(4)

        self.binding_model_lbl   = QLabel("")
        self.binding_formula_lbl = QLabel("")
        self.binding_params_lbl  = QLabel("")
        self.binding_r2_lbl      = QLabel("")
        self.binding_ref_lbl     = QLabel("")
        self.binding_kd_lbl      = QLabel("")

        self.binding_model_lbl.setStyleSheet("font-size:12px; font-weight:700; color:#1D1D1F;")
        self.binding_formula_lbl.setStyleSheet("font-family: monospace; font-size:11px; color:#3A3A3C;")
        self.binding_params_lbl.setStyleSheet("font-size:11px; color:#1D1D1F;")
        self.binding_r2_lbl.setStyleSheet("font-size:12px; font-weight:700;")
        self.binding_ref_lbl.setStyleSheet("font-size:11px; color:#86868B; font-style:italic;")
        self.binding_kd_lbl.setStyleSheet("font-size:11px; font-style:italic; color:#1D1D1F;")

        # Langmuir warning banner
        self.binding_warn_frame = QFrame()
        self.binding_warn_frame.setStyleSheet(
            "QFrame { background: #FFF3CD; border: 1px solid #FFCC02; border-radius: 4px; }"
        )
        warn_inner = QVBoxLayout(self.binding_warn_frame)
        warn_inner.setContentsMargins(6, 4, 6, 4)
        warn_lbl = QLabel("⚠ Equilibrium estimate only.\nVerify with full kinetics for publication data.")
        warn_lbl.setStyleSheet("font-size:10px; color:#856404; background: transparent; border: none;")
        warn_lbl.setWordWrap(True)
        warn_inner.addWidget(warn_lbl)
        self.binding_warn_frame.hide()

        for w in [self.binding_model_lbl, self.binding_formula_lbl, self.binding_params_lbl,
                  self.binding_r2_lbl, self.binding_ref_lbl, self.binding_kd_lbl,
                  self.binding_warn_frame]:
            fpanel.addWidget(w)
        fpanel.addStretch()
        hsplit.addWidget(formula_frame)

        hsplit.setStretchFactor(0, 70)
        hsplit.setStretchFactor(1, 30)
        vbox.addWidget(hsplit, 1)

        # --- Rmax Calculator (collapsible section below the plot split) ---
        vbox.addWidget(self._create_rmax_calculator())

        return container

    def _create_rmax_calculator(self):
        """Build the Rmax Calculator collapsible panel (§12 of EDITS_BINDING_PLOT_FRS)."""
        from PySide6.QtWidgets import QDoubleSpinBox, QGridLayout

        outer = QFrame()
        outer.setStyleSheet(
            "QFrame#RmaxPanel { background: #F8F9FA; border: 1px solid #E5E5EA;"
            " border-radius: 6px; }"
        )
        outer.setObjectName("RmaxPanel")
        outer_vbox = QVBoxLayout(outer)
        outer_vbox.setContentsMargins(10, 6, 10, 8)
        outer_vbox.setSpacing(4)

        # Header row with collapse toggle
        hdr = QHBoxLayout()
        self._rmax_toggle_btn = QPushButton("▸ Rmax Calculator")
        self._rmax_toggle_btn.setFlat(True)
        self._rmax_toggle_btn.setStyleSheet(
            "QPushButton { font-size:11px; font-weight:600; color:#1D1D1F;"
            " text-align:left; background:transparent; border:none; padding:0; }"
            "QPushButton:hover { color:#007AFF; }"
        )
        self._rmax_toggle_btn.setCheckable(True)
        self._rmax_toggle_btn.setChecked(False)
        self._rmax_toggle_btn.clicked.connect(self._toggle_rmax_panel)
        hdr.addWidget(self._rmax_toggle_btn)
        hdr.addStretch()
        outer_vbox.addLayout(hdr)

        # Collapsible body
        self._rmax_body = QFrame()
        self._rmax_body.setVisible(False)
        body_grid = QGridLayout(self._rmax_body)
        body_grid.setContentsMargins(0, 4, 0, 0)
        body_grid.setSpacing(4)
        body_grid.setColumnStretch(1, 1)

        _lbl_style = "font-size:11px; color:#3A3A3C;"
        _val_style = "font-size:11px; font-weight:600; color:#1D1D1F;"

        # Row 0 — Ligand MW
        body_grid.addWidget(self._ql("Ligand MW:", _lbl_style), 0, 0)
        self.rmax_ligand_spin = QDoubleSpinBox()
        self.rmax_ligand_spin.setRange(0, 1_000_000)
        self.rmax_ligand_spin.setDecimals(0)
        self.rmax_ligand_spin.setSuffix(" Da")
        self.rmax_ligand_spin.setSpecialValueText("—")
        self.rmax_ligand_spin.setValue(0)
        self.rmax_ligand_spin.setFixedWidth(120)
        self.rmax_ligand_spin.valueChanged.connect(self._on_rmax_input_changed)
        body_grid.addWidget(self.rmax_ligand_spin, 0, 1, Qt.AlignLeft)

        # Row 1 — Analyte MW
        body_grid.addWidget(self._ql("Analyte MW:", _lbl_style), 1, 0)
        self.rmax_analyte_spin = QDoubleSpinBox()
        self.rmax_analyte_spin.setRange(0, 1_000_000)
        self.rmax_analyte_spin.setDecimals(0)
        self.rmax_analyte_spin.setSuffix(" Da")
        self.rmax_analyte_spin.setSpecialValueText("—")
        self.rmax_analyte_spin.setValue(0)
        self.rmax_analyte_spin.setFixedWidth(120)
        self.rmax_analyte_spin.valueChanged.connect(self._on_rmax_input_changed)
        body_grid.addWidget(self.rmax_analyte_spin, 1, 1, Qt.AlignLeft)

        # Row 2 — Immob ΔSPR (auto-filled, read-only)
        body_grid.addWidget(self._ql("Immob ΔSPR:", _lbl_style), 2, 0)
        self.rmax_immob_lbl = QLabel("—")
        self.rmax_immob_lbl.setStyleSheet(_val_style)
        body_grid.addWidget(self.rmax_immob_lbl, 2, 1)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #E5E5EA;")
        body_grid.addWidget(sep, 3, 0, 1, 3)

        # Row 4 — Theoretical Rmax
        body_grid.addWidget(self._ql("Theoretical Rmax:", _lbl_style), 4, 0)
        self.rmax_theoretical_lbl = QLabel("—")
        self.rmax_theoretical_lbl.setStyleSheet(_val_style)
        body_grid.addWidget(self.rmax_theoretical_lbl, 4, 1)

        # Row 5 — Empirical Rmax (from Langmuir)
        body_grid.addWidget(self._ql("Empirical Rmax:", _lbl_style), 5, 0)
        self.rmax_empirical_lbl = QLabel("—")
        self.rmax_empirical_lbl.setStyleSheet(f"font-size:11px; color:#86868B; font-style:italic;")
        body_grid.addWidget(self.rmax_empirical_lbl, 5, 1)

        # Row 6 — Surface activity
        body_grid.addWidget(self._ql("Surface activity:", _lbl_style), 6, 0)
        self.rmax_activity_lbl = QLabel("—")
        self.rmax_activity_lbl.setStyleSheet(_val_style)
        body_grid.addWidget(self.rmax_activity_lbl, 6, 1)

        outer_vbox.addWidget(self._rmax_body)
        return outer

    def _ql(self, text: str, style: str = "") -> "QLabel":
        """Convenience: create a styled QLabel."""
        lbl = QLabel(text)
        if style:
            lbl.setStyleSheet(style)
        return lbl

    def _toggle_rmax_panel(self, checked: bool):
        """Show/hide the Rmax body when header button is toggled."""
        self._rmax_body.setVisible(checked)
        self._rmax_toggle_btn.setText(
            "▾ Rmax Calculator" if checked else "▸ Rmax Calculator"
        )

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
        smooth_lbl = QLabel("Smooth:")
        smooth_lbl.setToolTip("Savitzky-Golay smoothing window (0 = off)")
        layout.addWidget(smooth_lbl)
        self.edits_smooth_label = QLabel("off")
        self.edits_smooth_label.setStyleSheet("font-size: 12px; color: #86868B; min-width: 28px;")
        layout.addWidget(self.edits_smooth_label)

        self.edits_smooth_slider = QSlider(Qt.Horizontal)
        self.edits_smooth_slider.setRange(0, 50)
        self.edits_smooth_slider.setValue(0)
        self.edits_smooth_slider.setMaximumWidth(200)
        self.edits_smooth_slider.setToolTip("Savitzky-Golay smoothing window (0 = off)")
        self.edits_smooth_slider.valueChanged.connect(lambda v: (
            self.edits_smooth_label.setText("off" if v == 0 else f"{v} pts"),
            self._on_smooth_changed(),
        ))
        layout.addWidget(self.edits_smooth_slider)

        layout.addStretch()

        layout.addSpacing(12)

        # Create Processing Cycle button
        create_processing_btn = QPushButton(" Create Processing Cycle")
        _merge_svg = get_affilabs_resource("ui/img/merge_icon.svg")
        if _merge_svg and _merge_svg.exists():
            _svg_white = _merge_svg.read_text(encoding="utf-8").replace("currentColor", "white")
            _renderer = QSvgRenderer(_svg_white.encode("utf-8"))
            _px = QPixmap(QSize(16, 16))
            _px.fill(Qt.GlobalColor.transparent)
            _p = QPainter(_px)
            _renderer.render(_p)
            _p.end()
            create_processing_btn.setIcon(QIcon(_px))
            create_processing_btn.setIconSize(QSize(16, 16))
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
        create_processing_btn.setVisible(False)  # TODO: hidden for now

        layout.addSpacing(8)

        # Split export button: left = Export Package (all at once), right arrow = individual options
        export_btn = QToolButton()
        export_btn.setText(" Export")
        _export_svg = get_affilabs_resource("ui/img/export_package_icon.svg")
        if _export_svg and _export_svg.exists():
            _svg_src = _export_svg.read_text(encoding="utf-8").replace("currentColor", "white")
            _renderer2 = QSvgRenderer(_svg_src.encode("utf-8"))
            _px2 = QPixmap(QSize(16, 16))
            _px2.fill(Qt.GlobalColor.transparent)
            _p2 = QPainter(_px2)
            _renderer2.render(_p2)
            _p2.end()
            export_btn.setIcon(QIcon(_px2))
            export_btn.setIconSize(QSize(16, 16))
            export_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        else:
            export_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        export_btn.setFixedHeight(32)
        export_btn.setMinimumWidth(120)
        export_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        export_btn.setStyleSheet("""
            QToolButton {
                background: #1D1D1F; color: white; border-radius: 8px;
                font-size: 13px; font-weight: 600; padding: 4px 16px;
                border: none;
            }
            QToolButton:hover { background: #3A3A3C; }
            QToolButton::menu-button {
                border-left: 1px solid rgba(255,255,255,0.2);
                border-radius: 0px 8px 8px 0px;
                width: 20px;
            }
            QToolButton::menu-arrow { image: none; }
        """)
        # Primary action: export everything at once
        export_btn.clicked.connect(self._export_package)

        # Dropdown menu: individual options
        export_menu = QMenu(self.main_window)
        export_menu.setStyleSheet("""
            QMenu {
                background: white; border: 1px solid #E5E5EA;
                border-radius: 8px; padding: 4px;
            }
            QMenu::item {
                padding: 8px 16px; font-size: 12px; color: #1D1D1F;
                border-radius: 6px;
            }
            QMenu::item:selected { background: #F0F0F0; }
            QMenu::separator { height: 1px; background: #E5E5EA; margin: 4px 8px; }
        """)
        export_menu.addAction("📊  Excel + Charts",  self._export_post_edit_analysis_with_charts)
        export_menu.addAction("💾  Excel only",       self._export_table_data)
        export_menu.addSeparator()
        export_menu.addAction("🖼  Sensorgram PNG",   self._export_graph_image)
        export_menu.addAction("📈  ΔSPR Chart PNG",   self._export_barchart_image)
        export_menu.addSeparator()
        export_menu.addAction("📋  Copy to clipboard", self._copy_table_to_clipboard)
        export_menu.addAction("🔗  External (Prism / Origin)", self._export_for_external_software)
        export_menu.addAction("📋  Save as Method",   self._save_cycles_as_method)
        export_btn.setMenu(export_menu)

        layout.addWidget(export_btn)

        return container
