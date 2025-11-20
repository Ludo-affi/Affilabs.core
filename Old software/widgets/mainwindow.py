from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QSizePolicy

from widgets.message import show_message
from widgets.sidebar import Sidebar
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
        self.active_page = 'sensorgram'
        self.update_counter = 0
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.ui.version.setText(SW_VERSION)
        self.advanced_menu = None
        self.ui.adv_btn.setEnabled(True)  # Enable settings button
        self.device_config = {'ctrl': '', 'knx': ''}

        # set up recording
        self.recording = False
        self.ui.rec_btn.clicked.connect(self.record_trigger)

        # Set up power button (always visible, changes color based on state)
        self.ui.power_btn.clicked.connect(self.power_off_device)
        # Start in OFF state (gray)
        self.ui.power_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: transparent;"
            "    color: rgb(150, 150, 150);"
            "    border: none;"
            "}"
            "QPushButton:hover {"
            "    color: rgb(100, 100, 100);"
            "}"
            "QPushButton:pressed {"
            "    color: rgb(50, 50, 50);"
            "}"
        )
        self.ui.power_btn.setToolTip("OFF - No device connected")

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

        # setup modern pill-shaped button styles (Company blue palette)
        self.original_style = (
            "QPushButton {"
            "  background: rgba(46, 48, 227, 8);"
            "  color: rgb(30, 35, 55);"
            "  border: 1px solid rgba(46, 48, 227, 50);"
            "  border-radius: 20px;"
            "  padding: 10px 24px;"
            "  font-weight: 600;"
            "  font-size: 13px;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(46, 48, 227, 18);"
            "  border: 1px solid rgba(46, 48, 227, 80);"
            "}"
        )
        self.selected_style = (
            "QPushButton {"
            "  background: rgb(46, 48, 227);"
            "  color: white;"
            "  border: 1px solid rgb(46, 48, 227);"
            "  border-radius: 20px;"
            "  padding: 10px 26px;"
            "  font-weight: 700;"
            "  font-size: 13px;"
            "}"
            "QPushButton:hover {"
            "  background: rgb(36, 38, 207);"
            "  border: 2px solid rgb(56, 58, 247);"
            "}"
        )

        self.nav_buttons = [
            self.ui.sensorgram_btn,
            # self.ui.spectroscopy_btn,  # Moved to sidebar
            self.ui.data_processing_btn,
            self.ui.data_analysis_btn,
        ]
        # Hide spectroscopy button since it's now in the sidebar
        self.ui.spectroscopy_btn.hide()

        for button in self.nav_buttons:
            button.setStyleSheet(self.original_style)

        # Embed the sidebar directly into the main content area
        self.ui.verticalLayout.removeWidget(self.ui.main_display)
        self.main_content = QWidget(self.ui.main_frame)
        self.main_content.setObjectName("main_content")
        self.main_content_layout = QHBoxLayout(self.main_content)
        self.main_content_layout.setContentsMargins(8, 8, 8, 8)  # Standard padding around content
        self.main_content_layout.setSpacing(8)  # Spacing between sidebar and main area

        self.sidebar = Sidebar()
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
            "  background: rgba(46, 48, 227, 8);"
            "  border: 1px solid rgba(46, 48, 227, 30);"
            "  border-radius: 4px;"
            "  color: rgb(46, 48, 227);"
            "  font-weight: bold;"
            "  font-size: 11px;"
            "}"
            "QToolButton:hover {"
            "  background: rgba(46, 48, 227, 15);"
            "  border: 1px solid rgba(46, 48, 227, 60);"
            "}"
            "QToolButton:pressed {"
            "  background: rgba(46, 48, 227, 25);"
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

        # Sensorgram window
        self.sensorgram = DataWindow('dynamic')
        self.sensorgram.setParent(self.ui.main_display)
        controls_panel = self.sensorgram.take_sensorgram_controls_panel()
        if controls_panel is not None:
            self.sidebar.install_sensorgram_controls(controls_panel)

        # Connect settings panel button to sensorgram margin adjustment
        if hasattr(self, 'settings_panel'):
            self.settings_panel.adjust_margins_requested.connect(
                self.sensorgram.open_margin_adjust_dialog
            )

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

        # resize widgets
        self.sensorgram.setFixedSize(self.ui.main_display.width(), self.ui.main_display.height())
        self.spectroscopy.setFixedSize(self.ui.main_display.width(), self.ui.main_display.height())
        self.data_processing.setFixedSize(self.ui.main_display.width(), self.ui.main_display.height())

        self.ui.sensorgram_btn.clicked.connect(self.display_sensorgram_page)
        # self.ui.spectroscopy_btn.clicked.connect(self.display_spectroscopy_page)  # Moved to sidebar
        self.ui.data_processing_btn.clicked.connect(self.display_data_processing_page)
        self.ui.data_analysis_btn.clicked.connect(self.display_data_analysis_page)
        self.ui.adv_btn.clicked.connect(self.show_adv_settings)
        self.set_main_widget('sensorgram')

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

    def on_device_config(self, config):
        self.device_config = config
        # Update power button styling based on device connection
        if config['ctrl'] and config['ctrl'] != '':
            # Connected state - company blue
            self.ui.power_btn.setStyleSheet(
                "QPushButton {"
                "    background-color: transparent;"
                "    color: rgb(46, 48, 227);"
                "    border: none;"
                "}"
                "QPushButton:hover {"
                "    color: rgb(66, 68, 247);"
                "}"
                "QPushButton:pressed {"
                "    color: rgb(26, 28, 187);"
                "}"
            )
            self.ui.power_btn.setToolTip("ON - Click to gracefully exit")
            self.ui.power_btn.show()
        else:
            # Disconnected state - gray/black, acts as Connect button
            self.ui.power_btn.setStyleSheet(
                "QPushButton {"
                "    background-color: transparent;"
                "    color: rgb(150, 150, 150);"
                "    border: none;"
                "}"
                "QPushButton:hover {"
                "    color: rgb(100, 100, 100);"
                "}"
                "QPushButton:pressed {"
                "    color: rgb(50, 50, 50);"
                "}"
            )
            self.ui.power_btn.setToolTip("OFF - Click to connect device")
            self.ui.power_btn.show()

        # Create advanced menu - QSPR disabled (obsolete hardware)
        self.advanced_menu = None
        if config['ctrl'] in ['P4SPR', 'PicoP4SPR', 'EZSPR', 'PicoEZSPR']:
            self.advanced_menu = P4SPRAdvMenu(parent=self)
            self.settings = Settings(self.sensorgram.reference_channel_dlg, self.advanced_menu, self)
        self.connect_adv_sig.emit()

    def main_display_resized(self):
        self.sensorgram.setFixedSize(self.ui.main_display.width(), self.ui.main_display.height())
        self.spectroscopy.setFixedSize(self.ui.main_display.width(), self.ui.main_display.height())
        self.data_processing.setFixedSize(self.ui.main_display.width(), self.ui.main_display.height())
        self.data_analysis.setFixedSize(self.ui.main_display.width(), self.ui.main_display.height())

    # navigate the main contents: Sensorgram, Spectroscopy, DataProcessing
    def set_main_widget(self, window_id):

        page_list = {'sensorgram': self.ui.sensorgram_btn,
                     # 'spectroscopy': self.ui.spectroscopy_btn,  # Moved to sidebar
                     'data_processing': self.ui.data_processing_btn, 'data_analysis': self.ui.data_analysis_btn}

        for page in page_list:
            getattr(self, page).hide()
        self.active_page = window_id

        while len(page_list) > 0:
            page = page_list.popitem()
            if page[0] == self.active_page:
                getattr(self, page[0]).show()
                page[1].setStyleSheet(self.selected_style)
            else:
                page[1].setStyleSheet(self.original_style)

        self.redo_layout()

    def display_sensorgram_page(self):
        self.set_main_widget('sensorgram')

    def display_spectroscopy_page(self):
        if POP_OUT_SPEC:
            self.spec_pop_out.show()
            self.spectroscopy.show()
            self.redo_layout()
        else:
            self.set_main_widget('spectroscopy')

    def display_data_processing_page(self):
        self.set_main_widget('data_processing')

    def display_data_analysis_page(self):
        self.set_main_widget('data_analysis')

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
        self.sensorgram.setFixedSize(self.ui.main_display.width(), self.ui.main_display.height())
        if POP_OUT_SPEC:
            self.spectroscopy.setFixedSize(self.spec_pop_out.ui.single_frame.width(),
                                           self.spec_pop_out.ui.single_frame.height())
        else:
            self.spectroscopy.setFixedSize(self.ui.main_display.width(), self.ui.main_display.height())
        self.data_processing.setFixedSize(self.ui.main_display.width(), self.ui.main_display.height())
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

