from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QSizePolicy, QLabel, QFrame, QVBoxLayout, QSplitter

from widgets.message import show_message
from widgets.sidebar_modern import ModernSidebar  # NEW: Use modern sidebar
from widgets.datawindow import DataWindow
from widgets.advanced import P4SPRAdvMenu  # QSPRAdvMenu removed - obsolete hardware
from widgets.analysis import AnalysisWindow
from widgets.settings_menu import Settings
from widgets.spectroscopy import Spectroscopy, SpecDebugWindow
from widgets.sidebar_spectroscopy_panel import SidebarSpectroscopyPanel
from settings import SW_VERSION, DEV, POP_OUT_SPEC
from ui.ui_main import Ui_mainWindow
from utils.logger import logger


class MainWindow(QWidget):
    connect_adv_sig = Signal()
    set_start_sig = Signal()
    clear_flow_buf_sig = Signal()
    record_sig = Signal()
    pause_sig = Signal(bool)  # True = pause, False = resume

    def __init__(self, app):
        super(MainWindow, self).__init__()
        self.ui = Ui_mainWindow()
        self.ui.setupUi(self)
        self.setDisabled(False)
        self.app = app
        self.update_counter = 0
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.ui.version.setText(SW_VERSION)
        self.advanced_menu = None
        self.ui.adv_btn.setEnabled(True)  # Enable settings button
        self.device_config = {'ctrl': '', 'knx': ''}

        # Modern stacked widget system for tab pages
        from PySide6.QtWidgets import QStackedWidget
        self.content_stack = None  # Will be created after UI setup

        # set up recording
        self.recording = False

        # Add recording indicator next to record button
        from PySide6.QtWidgets import QFrame
        self.recording_indicator = QFrame(self.ui.tool_bar)
        self.recording_indicator.setFixedSize(200, 32)
        self.recording_indicator.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  border-radius: 6px;"
            "}"
        )
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

        # Insert recording indicator before record button in toolbar
        toolbar_layout = self.ui.tool_bar.layout()
        rec_btn_index = toolbar_layout.indexOf(self.ui.rec_btn)
        toolbar_layout.insertWidget(rec_btn_index, self.recording_indicator, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        toolbar_layout.insertSpacing(rec_btn_index + 1, 8)  # Add spacing between indicator and button

        # Style the record button with grayscale theme
        self.ui.rec_btn.setFixedSize(40, 40)
        self.ui.rec_btn.setCheckable(True)
        self.ui.rec_btn.setText("●")
        self.ui.rec_btn.setStyleSheet(
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
        self.ui.rec_btn.setToolTip("Start/Stop Recording (Ctrl+R)")
        self.ui.rec_btn.clicked.connect(self.record_trigger)

        # Set up power button with three states (gray/yellow/green)
        self.ui.power_btn.setCheckable(True)
        self.ui.power_btn.setFixedSize(40, 40)
        self.ui.power_btn.setText("⏻")
        self.ui.power_btn.setProperty("powerState", "disconnected")  # Track state
        self.ui.power_btn.clicked.connect(self.power_off_device)
        self._update_power_button_style()  # Apply initial disconnected style

        # Add pause button next to recording button (hidden for now)
        self.paused = False
        self.pause_btn = QPushButton(self.ui.tool_bar)
        self.pause_btn.setFixedSize(40, 40)
        self.pause_btn.setToolTip("Pause/Resume\nLive Acquisition")
        self.pause_btn.setCheckable(True)
        self.pause_btn.setStyleSheet(
            "QPushButton{\n"
            "	background: rgb(207, 207, 207);\n"
            "	border: 1px solid;\n"
            "	border-radius: 8px;\n"
            "}\n"
            "\n"
            "QPushButton:checked{\n"
            "	background: rgb(255, 200, 100);\n"
            "	border: 2px solid rgb(200, 150, 50);\n"
            "	border-radius: 8px;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 8px;\n"
            "}"
        )
        # Use pause/play icons (Unicode symbols)
        self.pause_btn.setText("⏸")
        self.pause_btn.setFont(self.ui.rec_btn.font())
        self.pause_btn.clicked.connect(self.toggle_pause)
        # Insert pause button after recording button in toolbar
        toolbar_layout = self.ui.tool_bar.layout()
        rec_btn_index = toolbar_layout.indexOf(self.ui.rec_btn)
        toolbar_layout.insertWidget(rec_btn_index + 1, self.pause_btn, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        # Hide the pause button for now
        self.pause_btn.hide()

        # Set standard dimensions for professional layout
        self.sidebar_width = 320  # Standard sidebar width
        self.toolbar_height = 60  # Standard toolbar height
        self.ui.tool_bar.setMinimumHeight(self.toolbar_height)
        self.ui.tool_bar.setMaximumHeight(self.toolbar_height)
        self.sidebar_collapsed = False  # Track sidebar state

        # setup modern pill-shaped button styles (Grayscale theme from Rev 1)
        self.original_style = (
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  color: #1D1D1F;"
            "  border: none;"
            "  border-radius: 20px;"
            "  padding: 10px 24px;"
            "  font-weight: 500;"
            "  font-size: 13px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
        )
        self.selected_style = (
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 20px;"
            "  padding: 10px 24px;"
            "  font-weight: 600;"
            "  font-size: 13px;"
            "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}"
        )

        # Modern navigation system - buttons will be recreated in content setup
        # Hide old spectroscopy button
        self.ui.spectroscopy_btn.hide()

        # Create Report button (4th nav button)
        self.report_btn = QPushButton(self.ui.frame_2)
        self.report_btn.setObjectName("report_btn")
        self.report_btn.setMinimumSize(110, 35)
        self.report_btn.setMaximumSize(135, 16777215)
        self.report_btn.setFont(self.ui.sensorgram_btn.font())
        self.report_btn.setText("Report")
        self.report_btn.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.report_btn.setAutoFillBackground(False)
        self.report_btn.setAutoRepeat(False)
        self.report_btn.setAutoExclusive(False)
        self.report_btn.setAutoDefault(False)
        self.report_btn.setFlat(False)

        # Insert Report button after Analyze button in the layout
        # Find the layout containing nav buttons (horizontalLayout_4)
        nav_layout = self.ui.data_analysis_btn.parent().layout()
        nav_layout.addWidget(self.report_btn)

        self.nav_buttons = {
            'Sensorgram': self.ui.sensorgram_btn,
            'Edits': self.ui.data_processing_btn,  # Repurpose for Edits
            'Analyze': self.ui.data_analysis_btn,  # Repurpose for Analyze
            'Report': self.report_btn,  # New 4th button
        }

        # Apply initial styling to nav buttons
        for button in self.nav_buttons.values():
            button.setStyleSheet(self.original_style)
            button.setCheckable(True)

        # Set first button as checked
        self.ui.sensorgram_btn.setChecked(True)
        self.ui.sensorgram_btn.setStyleSheet(self.selected_style)

        # Embed the sidebar directly into the main content area
        self.ui.verticalLayout.removeWidget(self.ui.main_display)
        self.main_content = QWidget(self.ui.main_frame)
        self.main_content.setObjectName("main_content")
        self.main_content_layout = QHBoxLayout(self.main_content)
        self.main_content_layout.setContentsMargins(8, 8, 8, 8)  # Standard padding around content
        self.main_content_layout.setSpacing(8)  # Spacing between sidebar and main area

        self.sidebar = ModernSidebar()  # NEW: Use modern sidebar
        self.sidebar.setParent(self.main_content)
        self.sidebar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.sidebar.set_widgets()

        # Get tab bar width (will stay fixed)
        self.tab_bar_width = self.sidebar.tab_widget.tabBar().sizeHint().width()

        # Set initial sidebar width
        self.sidebar.setMinimumWidth(self.sidebar_width)
        self.sidebar.setMaximumWidth(self.sidebar_width)

        # Create subtle toggle button at bottom of tab bar
        from PySide6.QtWidgets import QToolButton
        from PySide6.QtCore import Qt as QtCore

        self.sidebar_toggle_btn = QToolButton(self.sidebar)
        self.sidebar_toggle_btn.setText("◀")
        self.sidebar_toggle_btn.setToolTip("Collapse Sidebar")
        self.sidebar_toggle_btn.setFixedSize(60, 24)
        self.sidebar_toggle_btn.setStyleSheet(
            "QToolButton {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  border: none;"
            "  border-radius: 4px;"
            "  color: #1D1D1F;"
            "  font-weight: bold;"
            "  font-size: 11px;"
            "}"
            "QToolButton:hover {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}"
            "QToolButton:pressed {"
            "  background: rgba(0, 0, 0, 0.15);"
            "}"
        )
        self.sidebar_toggle_btn.clicked.connect(self.toggle_sidebar)
        self.sidebar_toggle_btn.raise_()  # Ensure button is on top
        self.sidebar_toggle_btn.show()  # Explicitly show the button

        # Setup animation for sidebar width (will collapse to just tab bar width)
        self.sidebar_animation = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self.sidebar_animation.setDuration(300)
        self.sidebar_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.sidebar_animation.finished.connect(self._on_sidebar_animation_finished)

        # Also animate maximum width
        self.sidebar_max_animation = QPropertyAnimation(self.sidebar, b"maximumWidth")
        self.sidebar_max_animation.setDuration(300)
        self.sidebar_max_animation.setEasingCurve(QEasingCurve.InOutQuad)

        # Add settings panel to Settings tab
        from widgets.settings_panel import SettingsPanel
        self.settings_panel = SettingsPanel()
        settings_tab = self.sidebar.get_settings_tab()
        if settings_tab:
            layout = settings_tab.layout()
            # Clear placeholder
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.settings_panel.setParent(settings_tab)
            layout.addWidget(self.settings_panel)

        # Connect UI inspector button (will be connected after shortcut is installed)
        self._settings_panel_needs_connection = True

        self.sidebar_spectroscopy = SidebarSpectroscopyPanel()
        self.sidebar.install_spectroscopy_panel(self.sidebar_spectroscopy)
        self.main_content_layout.addWidget(self.sidebar)
        self.sidebar.raise_()  # Ensure sidebar is above main_display

        self.ui.main_display.setParent(self.main_content)
        self.ui.main_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.main_content_layout.addWidget(self.ui.main_display, 1)
        self.main_content_layout.setStretch(0, 0)
        self.main_content_layout.setStretch(1, 1)

        self.ui.verticalLayout.insertWidget(1, self.main_content)
        self.main_content.show()  # Ensure main content is visible

        # Create modern stacked widget system for all tabs
        self.content_stack = QStackedWidget(self.ui.main_display)
        self.content_stack.setStyleSheet("QStackedWidget { background: #F8F9FA; border: none; }")
        
        # Add content_stack to main_display layout
        if self.ui.main_display.layout() is None:
            main_display_layout = QVBoxLayout(self.ui.main_display)
            main_display_layout.setContentsMargins(0, 0, 0, 0)
            main_display_layout.setSpacing(0)
        else:
            main_display_layout = self.ui.main_display.layout()
        main_display_layout.addWidget(self.content_stack)

        # Page 0: Sensorgram with dual-graph layout from Rev 1
        sensorgram_page = self._create_sensorgram_content()
        self.content_stack.addWidget(sensorgram_page)  # Index 0

        # Page 1: Edits (placeholder for now)
        edits_page = self._create_placeholder_page("Edits", "📝", "Data editing features coming soon")
        self.content_stack.addWidget(edits_page)  # Index 1

        # Page 2: Analyze (Data Processing)
        self.data_processing = DataWindow('static')
        analyze_page = QWidget()
        analyze_layout = QVBoxLayout(analyze_page)
        analyze_layout.setContentsMargins(16, 16, 16, 16)
        analyze_layout.setSpacing(8)
        analyze_layout.addWidget(self.data_processing)
        self.content_stack.addWidget(analyze_page)  # Index 2

        # Page 3: Report (Data Analysis - placeholder)
        self.data_analysis = AnalysisWindow()
        report_page = QWidget()
        report_layout = QVBoxLayout(report_page)
        report_layout.setContentsMargins(16, 16, 16, 16)
        report_layout.setSpacing(8)
        report_layout.addWidget(self.data_analysis)
        self.content_stack.addWidget(report_page)  # Index 3

        # Connect settings panel button to sensorgram margin adjustment
        if hasattr(self, 'settings_panel'):
            self.settings_panel.adjust_margins_requested.connect(
                self.sensorgram.open_margin_adjust_dialog
            )

        # Connect navigation buttons to page switching
        self.ui.sensorgram_btn.clicked.connect(lambda: self._switch_page(0))
        self.ui.data_processing_btn.clicked.connect(lambda: self._switch_page(1))  # Edits placeholder
        self.ui.data_analysis_btn.clicked.connect(lambda: self._switch_page(2))  # Analyze (was data processing)
        self.report_btn.clicked.connect(lambda: self._switch_page(3))  # Report (data analysis)

        # Update button labels to match Rev 1 - FIXED ORDER
        self.ui.sensorgram_btn.setText("Sensorgram")  # Index 0
        self.ui.data_processing_btn.setText("Edits")  # Index 1  
        self.ui.data_analysis_btn.setText("Analyze")  # Index 2
        self.report_btn.setText("Report")  # Index 3

        # Helper methods available for layout customization:
        # self.move_graph_settings_to_device_status() - Move graph display settings to device status
        # self.move_connect_button_to_settings() - Move connect button to settings panel

        # Spectroscopy window
        self.spectroscopy = Spectroscopy()
        self.spec_pop_out = SpecDebugWindow(parent=self)
        if POP_OUT_SPEC:
            self.spectroscopy.setParent(self.spec_pop_out.ui.single_frame)
        else:
            self.spectroscopy.setParent(self.ui.main_display)
        # Hide spectroscopy from main display since it's now in sidebar only
        self.spectroscopy.hide()

        # Keep spectroscopy sidebar preview in sync with full view
        self.sidebar_spectroscopy.polarizer_sig.connect(self._forward_sidebar_polarizer)
        self.sidebar_spectroscopy.single_led_sig.connect(self._forward_sidebar_led_mode)
        self.spectroscopy.polarizer_sig.connect(self._sync_sidebar_polarizer)
        self.spectroscopy.single_led_sig.connect(self.sidebar_spectroscopy.sync_led_mode)
        self.sidebar_spectroscopy.sync_polarizer(self.spectroscopy.ui.polarization.currentText())
        self.sidebar_spectroscopy.sync_led_mode(getattr(self.spectroscopy, "led_mode", "auto"))

        # Data Processing window
        self.data_processing = DataWindow('static')
        self.data_processing.setParent(self.ui.main_display)

        # Data Analysis window
        self.data_analysis = AnalysisWindow()
        self.data_analysis.setParent(self.ui.main_display)

        # recording errors
        self.sensorgram.export_error_signal.connect(self._on_record_error)
        self.sidebar.kinetic_widget.export_error_signal.connect(self._on_record_error)

        # Set content stack to fill main_display
        if self.content_stack:
            self.content_stack.setParent(self.ui.main_display)
            # Use a layout to make stack fill the entire main_display
            if not self.ui.main_display.layout():
                display_layout = QVBoxLayout(self.ui.main_display)
                display_layout.setContentsMargins(0, 0, 0, 0)
                display_layout.setSpacing(0)
                display_layout.addWidget(self.content_stack)

        self.ui.adv_btn.clicked.connect(self.show_adv_settings)

        # Ensure all UI elements are properly shown
        self.sidebar.show()
        self.ui.main_display.show()

        self.show()
        self.redo_layout()

        # Install UI Inspector Console (Ctrl+Shift+I)
        from widgets.ui_inspector_console import install_inspector_shortcut
        self.open_ui_inspector = install_inspector_shortcut(self)

        # Install Hover Inspector (Ctrl+Hover shows widget info)
        from widgets.hover_inspector import install_hover_inspector
        self._hover_inspector = install_hover_inspector(self)
        self._hover_inspector.enable()  # Enable hover inspect

        # Connect the settings panel button to inspector
        if hasattr(self, '_settings_panel_needs_connection') and hasattr(self, 'settings_panel'):
            self.settings_panel.ui_inspector_btn.clicked.connect(self.open_ui_inspector)

    def toggle_sidebar(self):
        """Toggle sidebar collapse/expand with smooth animation."""
        # Get actual tab bar width
        tab_bar_width = self.sidebar.tab_widget.tabBar().width()
        if tab_bar_width < 50:  # Fallback if width not calculated yet
            tab_bar_width = 80

        # Get current sidebar width
        current_width = self.sidebar.width()

        if self.sidebar_collapsed:
            # Expand sidebar
            self.sidebar_animation.setStartValue(current_width)
            self.sidebar_animation.setEndValue(self.sidebar_width)
            self.sidebar_max_animation.setStartValue(current_width)
            self.sidebar_max_animation.setEndValue(self.sidebar_width)
            self.sidebar_collapsed = False
            self.sidebar_toggle_btn.setText("◀")
            self.sidebar_toggle_btn.setToolTip("Collapse Sidebar")
        else:
            # Collapse sidebar to just show tab bar
            self.sidebar_animation.setStartValue(current_width)
            self.sidebar_animation.setEndValue(tab_bar_width)
            self.sidebar_max_animation.setStartValue(current_width)
            self.sidebar_max_animation.setEndValue(tab_bar_width)
            self.sidebar_collapsed = True
            self.sidebar_toggle_btn.setText("▶")
            self.sidebar_toggle_btn.setToolTip("Expand Sidebar")

        self.sidebar_animation.start()
        self.sidebar_max_animation.start()

    def _on_sidebar_animation_finished(self):
        """Called when sidebar animation completes - resize main display."""
        self.redo_layout()

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

            # Update button styles
            button_map = {
                0: self.ui.sensorgram_btn,
                1: self.ui.data_processing_btn,
                2: self.ui.data_analysis_btn,
                3: self.report_btn,
            }

            for idx, btn in button_map.items():
                if idx == page_index:
                    btn.setChecked(True)
                    btn.setStyleSheet(self.selected_style)
                else:
                    btn.setChecked(False)
                    btn.setStyleSheet(self.original_style)

    def _update_power_button_style(self):
        """Update power button styling based on current state."""
        power_state = self.ui.power_btn.property("powerState")

        if power_state == "disconnected":
            # Gray - no device connected
            self.ui.power_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: #86868B;"
                "  border: none;"
                "  border-radius: 8px;"
                "  font-size: 16px;"
                "  font-weight: 400;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.1);"
                "}"
            )
            self.ui.power_btn.setToolTip("Power On Device\nGray = Disconnected")
        elif power_state == "searching":
            # Yellow - searching for connection
            self.ui.power_btn.setStyleSheet(
                "QPushButton {"
                "  background: #FFCC00;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  font-size: 16px;"
                "  font-weight: 400;"
                "}"
                "QPushButton:hover {"
                "  background: #E6B800;"
                "}"
            )
            self.ui.power_btn.setToolTip("Connecting...\nYellow = Searching")
        elif power_state == "connected":
            # Green - device connected
            self.ui.power_btn.setStyleSheet(
                "QPushButton {"
                "  background: #34C759;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  font-size: 16px;"
                "  font-weight: 400;"
                "}"
                "QPushButton:hover {"
                "  background: #2FB350;"
                "}"
            )
            self.ui.power_btn.setToolTip("Device Connected\nClick to power off")

    def on_device_config(self, config):
        self.device_config = config
        # Update power button state based on device connection
        if config['ctrl'] and config['ctrl'] != '':
            # Connected state - green
            self.ui.power_btn.setProperty("powerState", "connected")
            self._update_power_button_style()
            self.ui.power_btn.show()
        else:
            # Disconnected state - gray
            self.ui.power_btn.setProperty("powerState", "disconnected")
            self._update_power_button_style()
            self.ui.power_btn.show()

        # Create advanced menu - QSPR disabled (obsolete hardware)
        self.advanced_menu = None
        if config['ctrl'] in ['P4SPR', 'PicoP4SPR', 'EZSPR', 'PicoEZSPR']:
            self.advanced_menu = P4SPRAdvMenu(parent=self)
            self.settings = Settings(self.sensorgram.reference_channel_dlg, self.advanced_menu, self)
        self.connect_adv_sig.emit()

    def main_display_resized(self):
        # Stacked widget handles sizing automatically
        pass

    def changeEvent(self, event):
        if event.type() == 105:
            self.redo_layout()

    def resizeEvent(self, event):
        self.redo_layout()
        # Reposition toggle button at bottom of sidebar
        if hasattr(self, 'sidebar_toggle_btn') and hasattr(self, 'sidebar'):
            sidebar_height = self.sidebar.height()
            if sidebar_height > 60:  # Only position if sidebar has reasonable height
                self.sidebar_toggle_btn.move(10, sidebar_height - 34)
                self.sidebar_toggle_btn.raise_()  # Keep on top after resize

    def redo_layout(self):
        # Stacked widget handles all page sizing automatically
        pass
        self.data_analysis.setFixedSize(self.ui.main_display.width(), self.ui.main_display.height())
        self.data_analysis.resizeEvent()
        self.ui.tool_bar.setFixedWidth(self.ui.main_frame.width())

    def _on_record_error(self):
        if self.recording:
            show_message(msg="Recording Error:\nInvalid directory or no live data", msg_type='Warning')
            self.set_recording(False)

    def _forward_sidebar_polarizer(self, mode: str) -> None:
        target = (mode or "p").strip().upper()
        combo = self.spectroscopy.ui.polarization
        index = 0 if target == "P" else 1
        if combo.currentIndex() != index:
            combo.setCurrentIndex(index)

    def _forward_sidebar_led_mode(self, mode: str) -> None:
        normalized = (mode or "auto").strip().lower()
        combo = self.spectroscopy.ui.led_mode
        target_text = "Auto" if normalized == "auto" else "Single"
        if combo.currentText() != target_text:
            combo.setCurrentText(target_text)
        if normalized == "auto":
            if not self.spectroscopy.ui.led_off.isChecked():
                self.spectroscopy.ui.led_off.setChecked(True)
            return
        if normalized == "x":
            button = self.spectroscopy.ui.led_off
        else:
            button = getattr(self.spectroscopy.ui, f"single_{normalized.upper()}", None)
        if button is not None and not button.isChecked():
            button.setChecked(True)

    def _sync_sidebar_polarizer(self, mode: str) -> None:
        self.sidebar_spectroscopy.sync_polarizer(mode)

    def record_trigger(self):
        self.record_sig.emit()

    def toggle_pause(self):
        """Toggle pause/resume of live acquisition."""
        self.paused = self.pause_btn.isChecked()
        if self.paused:
            self.pause_btn.setText("▶")  # Play icon when paused
            self.ui.recording_status.setText("PAUSED")
            self.ui.recording_status.setStyleSheet(
                "background:none;\n"
                "color: orange;\n"
                "font: 87 8pt \"Segoe UI Black\";\n"
            )
        else:
            self.pause_btn.setText("⏸")  # Pause icon when running
            if self.recording:
                # Resume recording status
                self.ui.recording_status.setText("Recording\nin Progress")
                self.ui.recording_status.setStyleSheet(
                    "background: none; border: none; color: black;font: "
                    "8pt 'Segoe UI Semibold';"
                )
            else:
                # Resume non-recording status
                self.ui.recording_status.setText("NOT\nRECORDING")
                self.ui.recording_status.setStyleSheet(
                    "background:none;\n"
                    "color: red;\n"
                    "font: 87 8pt \"Segoe UI Black\";\n"
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
        if show_message(msg_type="Warning", msg="Exit application?", yes_no=True, title="Graceful Exit"):
            self.close()  # This will trigger closeEvent which handles shutdown

    def set_recording(self, state):
        self.recording = state
        if not self.recording:
            self.recording = False
            self.ui.recording_status.setText("NOT\nRECORDING")
            self.ui.recording_status.setStyleSheet("background: none; color: red; font: 8pt 'Segoe UI Black';")
            self.ui.rec_btn.setIcon(QIcon(':/img/img/record.png'))

        else:
            self.recording = True
            self.ui.recording_status.setText("Recording\nin Progress")
            self.ui.recording_status.setStyleSheet("background: none; border: none; color: black;font: "
                                                   "8pt 'Segoe UI Semibold';")
            self.ui.rec_btn.setIcon(QIcon(':/img/img/stop.png'))

    def show_adv_settings(self):
        if self.advanced_menu and hasattr(self, 'settings'):
            self.advanced_menu.refresh_values()
            self.settings.show()
            self.settings.activateWindow()

    def closeEvent(self, event):
        if show_message(msg="Quit application?", msg_type='Warning', yes_no=True, title="Exit"):
            self.ui.status.setText("Closing application ... ")
            self.ui.status.repaint()
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

