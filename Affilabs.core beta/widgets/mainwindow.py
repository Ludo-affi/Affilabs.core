from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow, QWidget, QPushButton, QHBoxLayout, QSizePolicy, QLabel, QFrame, QVBoxLayout, QSplitter, QStackedWidget

from widgets.message import show_message
from widgets.sidebar_modern import ModernSidebar
from widgets.datawindow import DataWindow
from widgets.advanced import P4SPRAdvMenu
from widgets.analysis import AnalysisWindow
from widgets.settings_menu import Settings
from widgets.spectroscopy import Spectroscopy, SpecDebugWindow
from widgets.sidebar_spectroscopy_panel import SidebarSpectroscopyPanel
from settings import SW_VERSION, DEV, POP_OUT_SPEC
from utils.logger import logger


class MainWindow(QMainWindow):
    connect_adv_sig = Signal()
    set_start_sig = Signal()
    clear_flow_buf_sig = Signal()
    record_sig = Signal()
    pause_sig = Signal(bool)  # True = pause, False = resume

    def __init__(self, app):
        super(MainWindow, self).__init__()
        logger.info("MainWindow: Starting initialization")
        self.setWindowTitle("ezControl Software")
        self.setGeometry(100, 100, 1400, 900)
        logger.info("MainWindow: Basic properties set")
        self.app = app
        self.update_counter = 0
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.device_config = {'ctrl': '', 'knx': ''}
        self.recording = False
        self.paused = False
        self.advanced_menu = None
        self.nav_buttons = []
        self.content_stack = None
        logger.info("MainWindow: About to setup UI")

        # Setup UI matching prototype structure exactly
        self._setup_ui()
        logger.info("MainWindow: UI setup complete")
        self._connect_signals()
        logger.info("MainWindow: Signals connected")

    def _setup_ui(self):
        """Setup the main window UI - EXACT COPY from prototype structure"""
        logger.info("MainWindow._setup_ui: Creating central widget")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        logger.info("MainWindow._setup_ui: Creating splitter")
        # Create splitter for resizable sidebar (EXACT prototype structure)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(6)
        self.splitter.setStyleSheet(
            "QSplitter::handle {"
            "  background: rgba(0, 0, 0, 0.06);"
            "}"
            "QSplitter::handle:hover {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
            "QSplitter::handle:pressed {"
            "  background: rgba(0, 0, 0, 0.15);"
            "}"
        )

        logger.info("MainWindow._setup_ui: Creating sidebar")
        # Sidebar with EXACT prototype constraints
        self.sidebar = ModernSidebar()
        self.sidebar.setMinimumWidth(55)  # EXACT prototype value
        self.sidebar.setMaximumWidth(800)  # EXACT prototype value
        self.splitter.addWidget(self.sidebar)
        self.splitter.setCollapsible(0, False)

        logger.info("MainWindow._setup_ui: Setting sidebar widgets")
        # Initialize sidebar widgets
        self.sidebar.set_widgets()

        logger.info("MainWindow._setup_ui: Creating settings panel")
        # Add settings panel to Settings tab
        from widgets.settings_panel import SettingsPanel
        self.settings_panel = SettingsPanel()
        settings_tab = self.sidebar.get_settings_tab()
        if settings_tab:
            layout = settings_tab.layout()
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.settings_panel.setParent(settings_tab)
            layout.addWidget(self.settings_panel)

        # Connect UI inspector button
        self._settings_panel_needs_connection = True

        logger.info("MainWindow._setup_ui: Creating spectroscopy panel")
        # Add spectroscopy panel
        self.sidebar_spectroscopy = SidebarSpectroscopyPanel()
        self.sidebar.install_spectroscopy_panel(self.sidebar_spectroscopy)

        logger.info("MainWindow._setup_ui: Creating right widget")
        # Right widget containing nav bar and content (EXACT prototype structure)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Navigation bar (replaces old toolbar)
        nav_bar = self._create_navigation_bar()
        right_layout.addWidget(nav_bar)

        # Stacked widget for content pages (EXACT prototype structure)
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("QStackedWidget { background: #F8F9FA; border: none; }")

        # Page 0: Sensorgram
        sensorgram_page = self._create_sensorgram_content()
        self.content_stack.addWidget(sensorgram_page)

        # Page 1: Edits (placeholder)
        edits_page = self._create_placeholder_page("Edits", "📝", "Data editing features coming soon")
        self.content_stack.addWidget(edits_page)

        # Page 2: Analyze (Data Processing)
        self.data_processing = DataWindow('static')
        analyze_page = QWidget()
        analyze_layout = QVBoxLayout(analyze_page)
        analyze_layout.setContentsMargins(16, 16, 16, 16)
        analyze_layout.setSpacing(8)
        analyze_layout.addWidget(self.data_processing)
        self.content_stack.addWidget(analyze_page)

        # Page 3: Report (Data Analysis)
        self.data_analysis = AnalysisWindow()
        report_page = QWidget()
        report_layout = QVBoxLayout(report_page)
        report_layout.setContentsMargins(16, 16, 16, 16)
        report_layout.setSpacing(8)
        report_layout.addWidget(self.data_analysis)
        self.content_stack.addWidget(report_page)

        right_layout.addWidget(self.content_stack, 1)
        self.splitter.addWidget(right_widget)

        # Set initial sizes: 450px for sidebar, rest for main content (EXACT prototype)
        self.splitter.setSizes([450, 950])

        main_layout.addWidget(self.splitter)

    def _create_navigation_bar(self):
        """Create the pill-shaped navigation bar - EXACT COPY from prototype"""
        nav_widget = QWidget()
        nav_widget.setStyleSheet("background: #FFFFFF;")
        nav_widget.setFixedHeight(60)

        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(20, 10, 20, 10)
        nav_layout.setSpacing(12)

        # Logo placeholder (left side)
        logo_label = QLabel()
        logo_label.setFixedSize(100, 40)
        logo_label.setStyleSheet("background: transparent;")
        nav_layout.addWidget(logo_label)

        # Navigation buttons
        nav_button_configs = [
            ("Sensorgram", 0),
            ("Edits", 1),
            ("Analyze", 2),
            ("Report", 3),
        ]

        for i, (label, page_index) in enumerate(nav_button_configs):
            btn = QPushButton(label)
            btn.setFixedHeight(40)
            btn.setMinimumWidth(120)
            btn.setCheckable(True)
            btn.setChecked(i == 0)  # First button selected by default

            self.nav_buttons.append(btn)

            btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(46, 48, 227, 0.1);"
                "  color: rgb(46, 48, 227);"
                "  border: none;"
                "  border-radius: 20px;"
                "  padding: 8px 24px;"
                "  font-size: 13px;"
                "  font-weight: 500;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(46, 48, 227, 0.2);"
                "}"
                "QPushButton:checked {"
                "  background: rgba(46, 48, 227, 1.0);"
                "  color: white;"
                "  font-weight: 600;"
                "}"
            )

            btn.clicked.connect(lambda checked, idx=page_index: self._switch_page(idx))
            nav_layout.addWidget(btn)

        nav_layout.addStretch()

        # Recording status indicator
        self.recording_indicator = QFrame()
        self.recording_indicator.setFixedSize(200, 32)
        indicator_layout = QHBoxLayout(self.recording_indicator)
        indicator_layout.setContentsMargins(10, 6, 10, 6)
        indicator_layout.setSpacing(8)

        self.rec_status_dot = QLabel("●")
        self.rec_status_dot.setStyleSheet(
            "QLabel {"
            "  color: #86868B;"
            "  font-size: 16px;"
            "  background: transparent;"
            "}"
        )
        indicator_layout.addWidget(self.rec_status_dot)

        self.rec_status_text = QLabel("Viewing (not saved)")
        self.rec_status_text.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "  font-weight: 500;"
            "}"
        )
        indicator_layout.addWidget(self.rec_status_text)
        indicator_layout.addStretch()

        self.recording_indicator.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  border-radius: 6px;"
            "}"
        )
        nav_layout.addWidget(self.recording_indicator)
        nav_layout.addSpacing(8)

        # Record button
        self.rec_btn = QPushButton("●")
        self.rec_btn.setCheckable(True)
        self.rec_btn.setFixedSize(40, 40)
        self.rec_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  color: #86868B;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 16px;"
            "  font-weight: 400;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
            "QPushButton:checked {"
            "  background: #FF3B30;"
            "  color: white;"
            "}"
            "QPushButton:hover:checked {"
            "  background: #E6342A;"
            "}"
        )
        self.rec_btn.setToolTip("Start/Stop Recording (Ctrl+R)")
        self.rec_btn.clicked.connect(self.record_trigger)
        nav_layout.addWidget(self.rec_btn)

        # Pause button
        self.pause_btn = QPushButton("⏸")
        self.pause_btn.setCheckable(True)
        self.pause_btn.setFixedSize(40, 40)
        self.pause_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  color: #86868B;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 16px;"
            "  font-weight: 400;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover:!checked {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
            "QPushButton:checked {"
            "  background: #1D1D1F;"
            "  color: white;"
            "}"
            "QPushButton:hover:checked {"
            "  background: #3A3A3C;"
            "}"
        )
        self.pause_btn.setToolTip("Pause/Resume Live Acquisition")
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.hide()
        nav_layout.addWidget(self.pause_btn)

        # Power button
        self.power_btn = QPushButton("⏻")
        self.power_btn.setCheckable(True)
        self.power_btn.setFixedSize(40, 40)
        self.power_btn.setProperty("powerState", "disconnected")
        self._update_power_button_style()
        self.power_btn.setToolTip("Power On Device\nGray = Disconnected | Yellow = Searching | Green = Connected")
        self.power_btn.clicked.connect(self.power_off_device)
        nav_layout.addWidget(self.power_btn)

        # Settings button
        self.adv_btn = QPushButton("⚙")
        self.adv_btn.setFixedSize(40, 40)
        self.adv_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  color: #86868B;"
            "  border: none;"
            "  border-radius: 8px;"
            "  font-size: 18px;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
        )
        self.adv_btn.setToolTip("Advanced Settings")
        self.adv_btn.clicked.connect(self.show_adv_settings)
        nav_layout.addWidget(self.adv_btn)

        return nav_widget

    def _connect_signals(self):
        """Connect UI signals"""
        # Connect settings panel button to sensorgram margin adjustment
        if hasattr(self, 'settings_panel') and hasattr(self, 'sensorgram'):
            self.settings_panel.adjust_margins_requested.connect(
                self.sensorgram.open_margin_adjust_dialog
            )

        # Spectroscopy signals
        if hasattr(self, 'sidebar_spectroscopy'):
            self.sidebar_spectroscopy.polarizer_sig.connect(self._forward_sidebar_polarizer)
            self.sidebar_spectroscopy.single_led_sig.connect(self._forward_sidebar_led_mode)

        # Recording errors
        if hasattr(self, 'sensorgram'):
            self.sensorgram.export_error_signal.connect(self._on_record_error)
        if hasattr(self.sidebar, 'kinetic_widget'):
            self.sidebar.kinetic_widget.export_error_signal.connect(self._on_record_error)

        # Install UI Inspector Console (Ctrl+Shift+I) - TEMPORARILY DISABLED
        # from widgets.ui_inspector_console import install_inspector_shortcut
        # self.open_ui_inspector = install_inspector_shortcut(self)

        # Install Hover Inspector - TEMPORARILY DISABLED
        # from widgets.hover_inspector import install_hover_inspector
        # self._hover_inspector = install_hover_inspector(self)
        # self._hover_inspector.enable()

        # Connect settings panel button to inspector
        # if hasattr(self, '_settings_panel_needs_connection') and hasattr(self, 'settings_panel'):
        #     self.settings_panel.ui_inspector_btn.clicked.connect(self.open_ui_inspector)

    def _create_sensorgram_content(self):
        """Create the Sensorgram tab content with dual-graph layout (master-detail pattern) from Rev 1."""
        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {"
            "  background: #F8F9FA;"
            "  border: none;"
            "}"
        )

        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(8)

        # Graph header with channel controls (from Rev 1)
        from widgets.graph_components import GraphHeader
        self.graph_header = GraphHeader()
        content_layout.addWidget(self.graph_header)

        # Create QSplitter for resizable graph panels (30/70 split)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(8)
        splitter.setChildrenCollapsible(False)

        # Top graph (Navigation/Overview) - 30%
        top_graph = self._create_graph_container(
            "Full Experiment Timeline",
            height=200,
            show_delta_spr=False
        )

        # Bottom graph (Detail/Cycle of Interest) - 70%
        bottom_graph = self._create_graph_container(
            "Cycle of Interest",
            height=400,
            show_delta_spr=True
        )

        splitter.addWidget(top_graph)
        splitter.addWidget(bottom_graph)

        # Set initial sizes (30% / 70%)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)

        # Style the splitter handle (grayscale theme)
        splitter.setStyleSheet(
            "QSplitter {"
            "  background-color: transparent;"
            "  spacing: 8px;"
            "}"
            "QSplitter::handle {"
            "  background: rgba(0, 0, 0, 0.1);"
            "  border: none;"
            "  border-radius: 4px;"
            "  margin: 0px 16px;"
            "}"
            "QSplitter::handle:hover {"
            "  background: rgba(0, 0, 0, 0.15);"
            "}"
            "QSplitter::handle:pressed {"
            "  background: #1D1D1F;"
            "}"
        )

        content_layout.addWidget(splitter, 1)

        # Connect to real sensorgram data
        self.sensorgram = DataWindow('dynamic')
        controls_panel = self.sensorgram.take_sensorgram_controls_panel()
        if controls_panel is not None:
            self.sidebar.install_sensorgram_controls(controls_panel)

        return content_widget

    def _create_graph_container(self, title, height, show_delta_spr=False):
        """Create a graph container with title and controls (from Rev 1 prototype)."""
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from PySide6.QtGui import QColor

        container = QFrame()
        container.setMinimumHeight(height)
        container.setStyleSheet(
            "QFrame {"
            "  background: #FFFFFF;"
            "  border: none;"
            "  border-radius: 12px;"
            "}"
        )
        # Add shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title row with controls
        title_row = QHBoxLayout()
        title_row.setSpacing(12)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        title_row.addWidget(title_label)

        title_row.addStretch()

        # Delta SPR signal display (only for Cycle of Interest graph)
        if show_delta_spr:
            delta_display = QLabel("Δ SPR: Ch A: 0.0 nm  |  Ch B: 0.0 nm  |  Ch C: 0.0 nm  |  Ch D: 0.0 nm")
            delta_display.setStyleSheet(
                "QLabel {"
                "  background: rgba(0, 0, 0, 0.04);"
                "  border: none;"
                "  border-radius: 6px;"
                "  padding: 6px 12px;"
                "  font-size: 12px;"
                "  font-weight: 500;"
                "  color: #1D1D1F;"
                "  font-family: 'SF Mono', 'Consolas', monospace;"
                "}"
            )
            title_row.addWidget(delta_display)

        layout.addLayout(title_row)

        # Placeholder for graph widget (will be replaced with PyQtGraph)
        graph_placeholder = QLabel("[Graph Placeholder - Connect to real sensorgram data]")
        graph_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        graph_placeholder.setStyleSheet(
            "QLabel {"
            "  background: #F8F9FA;"
            "  color: #86868B;"
            "  border: 1px dashed rgba(0, 0, 0, 0.2);"
            "  border-radius: 8px;"
            "  padding: 40px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        layout.addWidget(graph_placeholder, 1)

        # Axis labels
        axis_row = QHBoxLayout()
        axis_row.setSpacing(0)

        y_label = QLabel("SPR Signal (nm)")
        y_label.setStyleSheet(
            "QLabel {"
            "  font-size: 11px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        axis_row.addWidget(y_label)

        axis_row.addStretch()

        x_label = QLabel("Time (s)")
        x_label.setStyleSheet(
            "QLabel {"
            "  font-size: 11px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        axis_row.addWidget(x_label)

        layout.addLayout(axis_row)

        return container

    def _create_placeholder_page(self, title, icon, message):
        """Create a placeholder page for tabs not yet implemented."""
        page = QFrame()
        page.setStyleSheet(
            "QFrame {"
            "  background: #F8F9FA;"
            "  border: none;"
            "}"
        )

        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)

        # Icon
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(
            "QLabel {"
            "  font-size: 64px;"
            "  background: transparent;"
            "}"
        )
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        layout.addSpacing(20)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(
            "QLabel {"
            "  font-size: 24px;"
            "  font-weight: 600;"
            "  color: #1D1D1F;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        layout.addSpacing(12)

        # Message
        message_label = QLabel(message)
        message_label.setStyleSheet(
            "QLabel {"
            "  font-size: 14px;"
            "  color: #86868B;"
            "  background: transparent;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
        )
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        return page

    def _switch_page(self, page_index):
        """Switch to the specified page in the content stack."""
        if self.content_stack:
            self.content_stack.setCurrentIndex(page_index)

            # Update button styles - now using self.nav_buttons list
            for i, btn in enumerate(self.nav_buttons):
                if i == page_index:
                    btn.setChecked(True)
                    btn.setStyleSheet(
                        "QPushButton {"
                        "  background: rgba(46, 48, 227, 1.0);"
                        "  color: white;"
                        "  border: none;"
                        "  border-radius: 20px;"
                        "  padding: 8px 24px;"
                        "  font-size: 13px;"
                        "  font-weight: 600;"
                        "}"
                    )
                else:
                    btn.setChecked(False)
                    btn.setStyleSheet(
                        "QPushButton {"
                        "  background: rgba(46, 48, 227, 0.1);"
                        "  color: rgb(46, 48, 227);"
                        "  border: none;"
                        "  border-radius: 20px;"
                        "  padding: 8px 24px;"
                        "  font-size: 13px;"
                        "  font-weight: 500;"
                        "}"
                        "QPushButton:hover {"
                        "  background: rgba(46, 48, 227, 0.2);"
                        "}"
                    )

    def _update_power_button_style(self):
        """Update power button styling based on current state."""
        power_state = self.power_btn.property("powerState")
        self.power_btn.setFixedSize(40, 40)

        if power_state == "disconnected":
            self.power_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #86868B;"
                "  border: none;"
                "  border-radius: 8px;"
                "  font-size: 18px;"
                "  font-weight: 400;"
                "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.1);"
                "}"
            )
            self.power_btn.setToolTip("Power On Device\nGray = Disconnected")
        elif power_state == "searching":
            self.power_btn.setStyleSheet(
                "QPushButton {"
                "  background: #FFCC00;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  font-size: 18px;"
                "  font-weight: 400;"
                "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: #E6B800;"
                "}"
            )
            self.power_btn.setToolTip("Connecting...\nYellow = Searching")
        elif power_state == "connected":
            self.power_btn.setStyleSheet(
                "QPushButton {"
                "  background: #34C759;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  font-size: 18px;"
                "  font-weight: 400;"
                "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: #2EAF4F;"
                "}"
            )
            self.power_btn.setToolTip("Device Connected\nClick to power off")

    def on_device_config(self, config):
        self.device_config = config
        # Update power button state based on device connection
        if config['ctrl'] and config['ctrl'] != '':
            self.power_btn.setProperty("powerState", "connected")
            self._update_power_button_style()
            self.power_btn.show()
        else:
            self.power_btn.setProperty("powerState", "disconnected")
            self._update_power_button_style()
            self.power_btn.show()

        # Create advanced menu
        self.advanced_menu = None
        if config['ctrl'] in ['P4SPR', 'PicoP4SPR', 'EZSPR', 'PicoEZSPR']:
            self.advanced_menu = P4SPRAdvMenu(parent=self)
            self.settings = Settings(self.sensorgram.reference_channel_dlg, self.advanced_menu, self)
        # Removed connect_adv_sig emission - no longer needed

    def main_display_resized(self):
        # Stacked widget handles sizing automatically
        pass

    def changeEvent(self, event):
        # QSplitter and stacked widget handle all layout changes automatically
        pass

    def resizeEvent(self, event):
        # QSplitter and stacked widget handle all resizing automatically
        pass

    def redo_layout(self):
        # QSplitter and stacked widget handle all layout automatically
        pass

    def _on_record_error(self):
        if self.recording:
            show_message(msg="Recording Error:\nInvalid directory or no live data", msg_type='Warning')
            self.set_recording(False)

    def _forward_sidebar_polarizer(self, mode: str) -> None:
        # Spectroscopy widget removed - sidebar handles all UI
        pass

    def _forward_sidebar_led_mode(self, mode: str) -> None:
        # Spectroscopy widget removed - sidebar handles all UI
        pass

    def _sync_sidebar_polarizer(self, mode: str) -> None:
        self.sidebar_spectroscopy.sync_polarizer(mode)

    def record_trigger(self):
        self.record_sig.emit()

    def toggle_pause(self):
        """Toggle pause/resume of live acquisition."""
        self.paused = self.pause_btn.isChecked()
        if self.paused:
            self.pause_btn.setText("▶")  # Play icon when paused
            self.rec_status_text.setText("PAUSED")
            self.rec_status_dot.setStyleSheet(
                "QLabel {"
                "  color: #FF9500;"
                "  font-size: 16px;"
                "  background: transparent;"
                "}"
            )
        else:
            self.pause_btn.setText("⏸")  # Pause icon when running
            if self.recording:
                # Resume recording status
                self.rec_status_text.setText("Recording")
                self.rec_status_dot.setStyleSheet(
                    "QLabel {"
                    "  color: #FF3B30;"
                    "  font-size: 16px;"
                    "  background: transparent;"
                    "}"
                )
            else:
                # Resume non-recording status
                self.rec_status_text.setText("Viewing (not saved)")
                self.rec_status_dot.setStyleSheet(
                    "QLabel {"
                    "  color: #86868B;"
                    "  font-size: 16px;"
                    "  background: transparent;"
                    "}"
                )
        self.pause_sig.emit(self.paused)

    def power_off_device(self):
        """Handle power button click - Connect when OFF, gracefully exit when ON."""
        ctrl_type = self.device_config.get('ctrl', '')

        if not ctrl_type:
            # No device connected - act as Connect button
            if hasattr(self.sidebar, 'device_widget') and hasattr(self.sidebar.device_widget, 'call_connect'):
                self.sidebar.device_widget.call_connect()
            return

        # Device is connected - gracefully exit the application
        if show_message(msg_type="Warning", msg="Exit application?", yes_no=True):
            self.close()  # This will trigger closeEvent which handles shutdown

    def set_recording(self, state):
        """Update recording status indicator."""
        self.recording = state
        if not self.recording:
            self.rec_status_text.setText("Viewing (not saved)")
            self.rec_status_dot.setStyleSheet(
                "QLabel {"
                "  color: #86868B;"
                "  font-size: 16px;"
                "  background: transparent;"
                "}"
            )
            self.rec_btn.setIcon(QIcon(':/img/img/record.png'))
        else:
            self.rec_status_text.setText("Recording")
            self.rec_status_dot.setStyleSheet(
                "QLabel {"
                "  color: #FF3B30;"
                "  font-size: 16px;"
                "  background: transparent;"
                "}"
            )
            self.rec_btn.setIcon(QIcon(':/img/img/stop.png'))

    def show_adv_settings(self):
        if self.advanced_menu and hasattr(self, 'settings'):
            self.advanced_menu.refresh_values()
            self.settings.show()
            self.settings.activateWindow()

    def closeEvent(self, event):
        if show_message(msg="Quit application?", msg_type='Warning', yes_no=True):
            # No status bar in new design - remove status updates
            self.sensorgram.reference_channel_dlg.close()
            self.data_processing.reference_channel_dlg.close()
            if self.advanced_menu and (self.device_config['ctrl'] in ['P4SPR', 'PicoP4SPR', 'EZSPR', 'PicoEZSPR']):  # QSPR removed
                self.advanced_menu.close()
            self.app.close()
            super().closeEvent(event)
        else:
            event.ignore()

    # === Layout Customization Helper Methods ===

    def move_graph_settings_to_device_status(self):
        """
        Move the Graph Display Settings box from Settings panel to Device Status widget.
        This allows you to consolidate all hardware-related settings in one place.

        Usage: Call this method after UI initialization, e.g., in __init__() after set_widgets()
        """
        if not hasattr(self, 'settings_panel') or not hasattr(self, 'sidebar'):
            logger.warning("Cannot move graph settings: settings_panel or sidebar not found")
            return False

        # Get the device status widget from sidebar
        device_status = self.sidebar.device_widget.device_status_widget
        if not device_status:
            logger.warning("Cannot move graph settings: device_status_widget not found")
            return False

        # Remove graph display group from settings panel
        graph_group = self.settings_panel.remove_graph_display_group()
        if not graph_group:
            logger.warning("Cannot move graph settings: graph_group not found")
            return False

        # Add it to device status layout
        device_status.add_widget_to_layout(graph_group)
        logger.info("Graph Display Settings moved to Device Status widget")
        return True

    def move_connect_button_to_device_bottom(self):
        """
        Move the Connect button to the bottom of the device status widget.
        Makes it more prominent and easier to access.

        Usage: Call this method after UI initialization
        """
        if not hasattr(self, 'sidebar'):
            logger.warning("Cannot move connect button: sidebar not found")
            return False

        device_status = self.sidebar.device_widget.device_status_widget
        if not device_status:
            logger.warning("Cannot move connect button: device_status_widget not found")
            return False

        # Get the main layout and move button there
        main_layout = device_status.get_main_layout()
        if not main_layout:
            logger.warning("Cannot move connect button: main_layout not found")
            return False

        device_status.move_connect_button_to_layout(main_layout, -1)
        logger.info("Connect button moved to bottom of Device Status")
        return True

    def get_device_status_widget(self):
        """Get the device status widget for manual layout manipulation."""
        if hasattr(self, 'sidebar'):
            return self.sidebar.device_widget.device_status_widget
        return None

    def get_settings_panel(self):
        """Get the settings panel for manual layout manipulation."""
        if hasattr(self, 'settings_panel'):
            return self.settings_panel
        return None

