from PySide6.QtCore import QPoint, QPropertyAnimation, QSize, Qt, Signal  # type: ignore
from PySide6.QtGui import QIcon  # type: ignore
from PySide6.QtWidgets import QPushButton, QWidget  # type: ignore

from settings import DEV, POP_OUT_SPEC, SW_VERSION, SW_APP_NAME
from ui.ui_main import Ui_mainWindow
from widgets.advanced import P4SPRAdvMenu
from widgets.analysis import AnalysisWindow
from widgets.datawindow import DataWindow
from widgets.message import show_message
from widgets.settings_menu import Settings
from widgets.sidebar import Sidebar
from widgets.spectroscopy import SpecDebugWindow, Spectroscopy


class MainWindow(QWidget):
    connect_adv_sig = Signal()
    set_start_sig = Signal()
    clear_flow_buf_sig = Signal()
    record_sig = Signal()

    def __init__(self, app):
        super().__init__()
        self.ui = Ui_mainWindow()
        self.ui.setupUi(self)
        self.setDisabled(False)
        self.app = app
        self.active_page = "sensorgram"
        self.update_counter = 0
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        # Set app identity
        try:
            self.setWindowTitle(SW_APP_NAME)
        except Exception:
            pass
        self.ui.version.setText(SW_VERSION)
        self.advanced_menu = None
        # Enable Settings button by default so users can access configuration any time
        self.ui.adv_btn.setEnabled(True)
        # Make settings button more visible with better styling
        self.ui.adv_btn.setStyleSheet(
            "QPushButton{\n"
            "	border: 1px solid rgb(200, 200, 200);\n"
            "	background: rgb(245, 245, 245);\n"
            "	border-radius: 4px;\n"
            "}\n"
            "QPushButton:hover{\n"
            "	background: white;\n"
            "	border: 2px solid rgb(45, 49, 224);\n"
            "	border-radius: 4px;\n"
            "}\n"
            "QPushButton:pressed{\n"
            "	background: rgb(230, 230, 230);\n"
            "}"
        )
        self.ui.adv_btn.setToolTip("Settings - Configure SPR tracking, calibration, and advanced options")
        self.device_config = {"ctrl": "", "knx": ""}

        # set up recording
        self.recording = False
        # Hide the recording status label initially (shows "ghost button" when empty)
        self.ui.recording_status.hide()
        self.ui.rec_btn.clicked.connect(self.record_trigger)

        # set minimum size
        self.sidebar_width = 280

        # setup button styles
        self.original_style = self.ui.sensorgram_btn.styleSheet()
        self.selected_style = (
            "background-color: rgb(254, 254, 254); border: 2px solid rgb(45, 49, 224); "
            "border-radius: 3px;"
        )

        # display sidebar open/close button
        self.sidebar_btn = QPushButton("Device\nControls", self)
        self.sidebar_btn.setToolTip("Show/Hide\nControl Bar")
        self.sidebar_btn.setFixedSize(70, 40)
        self.sidebar_btn.setStyleSheet(self.original_style)
        self.sidebar_btn.setFont(self.ui.sensorgram_btn.font())
        self.sidebar_btn.move(self.width() - self.sidebar_btn.width() - 5, 20)
        self.sidebar_btn.clicked.connect(self.toggle_side_bar)
        self.sidebar_state = "maximized"

        # display right sidebar
        self.sidebar = Sidebar()
        self.sidebar.setParent(self)
        self.sidebar.setFixedSize(self.sidebar_width, self.height())
        self.sidebar.move(self.width(), 0)
        self.sidebar.set_widgets()

        # Sensorgram window
        self.sensorgram = DataWindow("dynamic")
        self.sensorgram.setParent(self.ui.main_display)

        # Spectroscopy window
        self.spectroscopy = Spectroscopy()
        self.spec_pop_out = SpecDebugWindow(parent=self)
        if POP_OUT_SPEC:
            self.spectroscopy.setParent(self.spec_pop_out.ui.single_frame)
        else:
            self.spectroscopy.setParent(self.ui.main_display)

        # Data Processing window
        self.data_processing = DataWindow("static")
        self.data_processing.setParent(self.ui.main_display)

        # Data Analysis window
        self.data_analysis = AnalysisWindow()
        self.data_analysis.setParent(self.ui.main_display)

        # recording errors
        self.sensorgram.export_error_signal.connect(self._on_record_error)
        self.sidebar.kinetic_widget.export_error_signal.connect(self._on_record_error)

        # display
        self.x_pos = self.width() - self.sidebar_btn.width()

        # resize widgets
        self.sensorgram.setFixedSize(
            self.ui.main_display.width(), self.ui.main_display.height()
        )
        self.spectroscopy.setFixedSize(
            self.ui.main_display.width(), self.ui.main_display.height()
        )
        self.data_processing.setFixedSize(
            self.ui.main_display.width(), self.ui.main_display.height()
        )

        self.ui.sensorgram_btn.clicked.connect(self.display_sensorgram_page)
        self.ui.spectroscopy_btn.clicked.connect(self.display_spectroscopy_page)
        self.ui.data_processing_btn.clicked.connect(self.display_data_processing_page)
        self.ui.data_analysis_btn.clicked.connect(self.display_data_analysis_page)
        # Initialize Advanced and Settings menus upfront so the Settings button always works
        try:
            self.advanced_menu = P4SPRAdvMenu(parent=self)
        except Exception:
            self.advanced_menu = None

        try:
            self.settings = Settings(
                self.sensorgram.reference_channel_dlg,  # Channel/SPR settings widget
                self.advanced_menu if self.advanced_menu is not None else P4SPRAdvMenu(parent=self),
                self,
            )
        except Exception:
            # Fallback minimal settings if construction fails for any reason
            self.settings = Settings(self.sensorgram.reference_channel_dlg, P4SPRAdvMenu(parent=self), self)

        self.ui.adv_btn.clicked.connect(self.show_adv_settings)

        self.set_main_widget("sensorgram")
        self.show()
        self.redo_layout()
        self.sidebar_btn_anim = None
        self.sidebar_anim = None
        self.main_frame_anim = None

        self.toggle_side_bar(animation_time=0)

    def on_device_config(self, config):
        self.device_config = config
        # Ensure advanced/settings menus exist; refresh when device config arrives
        if self.advanced_menu is None:
            self.advanced_menu = P4SPRAdvMenu(parent=self)
        if not hasattr(self, 'settings') or self.settings is None:
            self.settings = Settings(self.sensorgram.reference_channel_dlg, self.advanced_menu, self)

        # Optionally refresh advanced values for supported controllers
        if config.get("ctrl") in ["PicoP4SPR", "PicoEZSPR"]:
            try:
                self.advanced_menu.refresh_values()
            except Exception:
                pass
        self.connect_adv_sig.emit()

    def main_display_resized(self):
        self.sensorgram.setFixedSize(
            self.ui.main_display.width(), self.ui.main_display.height()
        )
        self.spectroscopy.setFixedSize(
            self.ui.main_display.width(), self.ui.main_display.height()
        )
        self.data_processing.setFixedSize(
            self.ui.main_display.width(), self.ui.main_display.height()
        )
        self.data_analysis.setFixedSize(
            self.ui.main_display.width(), self.ui.main_display.height()
        )

    # navigate the main contents: Sensorgram, Spectroscopy, DataProcessing
    def set_main_widget(self, window_id):
        page_list = {
            "sensorgram": self.ui.sensorgram_btn,
            "spectroscopy": self.ui.spectroscopy_btn,
            "data_processing": self.ui.data_processing_btn,
            "data_analysis": self.ui.data_analysis_btn,
        }

        for page in page_list:
            getattr(self, page).hide()
        self.active_page = window_id

        revert = False
        if self.sidebar_state == "maximized":
            self.toggle_side_bar(animation_time=0)
            revert = True

        while len(page_list) > 0:
            page = page_list.popitem()
            if page[0] == self.active_page:
                getattr(self, page[0]).show()
                page[1].setStyleSheet(self.selected_style)
            else:
                page[1].setStyleSheet(self.original_style)

        self.redo_layout()
        if revert:
            self.toggle_side_bar(animation_time=0)

    def display_sensorgram_page(self):
        self.set_main_widget("sensorgram")

    def display_spectroscopy_page(self):
        if POP_OUT_SPEC:
            self.spec_pop_out.show()
            self.spectroscopy.show()
            self.redo_layout()
        else:
            self.set_main_widget("spectroscopy")

    def display_data_processing_page(self):
        self.set_main_widget("data_processing")

    def display_data_analysis_page(self):
        self.set_main_widget("data_analysis")

    def changeEvent(self, event):
        if event.type() == 105:
            revert = False
            if self.sidebar_state == "maximized":
                self.toggle_side_bar(animation_time=0)
                revert = True
            self.redo_layout()
            if revert:
                self.toggle_side_bar(animation_time=0)

    def resizeEvent(self, event):
        self.redo_layout()

    def redo_layout(self):
        if self.sidebar_state == "minimized":
            self.x_pos = self.width() - self.sidebar_btn.width()
        else:
            self.x_pos = self.width() - self.sidebar_btn.width() - self.sidebar.width()

        self.ui.main_frame.setGeometry(
            0, 0, self.x_pos + self.sidebar_btn.width(), self.height()
        )
        self.sensorgram.setFixedSize(
            self.ui.main_display.width(), self.ui.main_display.height()
        )
        if POP_OUT_SPEC:
            self.spectroscopy.setFixedSize(
                self.spec_pop_out.ui.single_frame.width(),
                self.spec_pop_out.ui.single_frame.height(),
            )
        else:
            self.spectroscopy.setFixedSize(
                self.ui.main_display.width(), self.ui.main_display.height()
            )
        self.data_processing.setFixedSize(
            self.ui.main_display.width(), self.ui.main_display.height()
        )
        self.data_analysis.setFixedSize(
            self.ui.main_display.width(), self.ui.main_display.height()
        )
        self.data_analysis.resizeEvent()

        self.sidebar.move(self.x_pos + self.sidebar_btn.width(), 0)
        self.sidebar.setFixedSize(self.sidebar_width, self.height())
        self.sidebar_btn.move(self.x_pos - 5, 20)
        self.ui.tool_bar.setFixedWidth(self.ui.main_display.width())

    def _on_record_error(self):
        if self.recording:
            show_message(
                msg="Recording Error:\nInvalid directory or no live data",
                msg_type="Warning",
            )
            self.set_recording(False)

    def record_trigger(self):
        self.record_sig.emit()

    def set_recording(self, state):
        self.recording = state
        if not self.recording:
            self.recording = False
            self.ui.recording_status.setText("NOT\nRECORDING")
            self.ui.recording_status.setStyleSheet(
                "background: none; color: red; font: 8pt 'Segoe UI Black';"
            )
            self.ui.rec_btn.setIcon(QIcon(":/img/img/record.png"))
            # Hide the label when not recording to avoid "ghost button" appearance
            self.ui.recording_status.hide()

        else:
            self.recording = True
            self.ui.recording_status.setText("Recording\nin Progress")
            self.ui.recording_status.setStyleSheet(
                "background: none; border: none; color: black;font: "
                "8pt 'Segoe UI Semibold';"
            )
            self.ui.rec_btn.setIcon(QIcon(":/img/img/stop.png"))
            # Show the label when recording is active
            self.ui.recording_status.show()

    # open/close sidebar
    def toggle_side_bar(self, animation_time=150):
        if self.sidebar_state == "minimized":
            self.x_pos = self.width() - self.sidebar_btn.width() - self.sidebar.width()
            self.sidebar_btn.setText("Device\nControls")
            self.sidebar_btn.setStyleSheet(self.selected_style)
            self.sidebar_state = "maximized"
        else:
            self.sidebar_state = "minimized"
            self.x_pos = self.width() - self.sidebar_btn.width()
            self.sidebar_btn.setText("Device\nControls")
            self.sidebar_btn.setStyleSheet(self.original_style)

        self.sidebar_btn_anim = QPropertyAnimation(self.sidebar_btn, b"pos")
        self.sidebar_btn_anim.setEndValue(QPoint(self.x_pos - 5, self.sidebar_btn.y()))
        self.sidebar_btn_anim.setDuration(animation_time)
        self.sidebar_btn_anim.start()

        self.sidebar_anim = QPropertyAnimation(self.sidebar, b"pos")
        self.sidebar_anim.setEndValue(
            QPoint(self.x_pos + self.sidebar_btn.width(), self.sidebar.y())
        )
        self.sidebar_anim.setDuration(animation_time)
        self.sidebar_anim.start()

        self.main_frame_anim = QPropertyAnimation(self.ui.main_frame, b"size")
        self.main_frame_anim.setStartValue(self.ui.main_frame.size())
        self.main_frame_anim.setEndValue(
            QSize(self.x_pos + self.sidebar_btn.width(), self.height())
        )
        self.main_frame_anim.setDuration(animation_time)
        self.main_frame_anim.start()

        self.sensorgram.setFixedSize(
            self.x_pos + self.sidebar_btn.width(), self.ui.main_display.height()
        )
        if not POP_OUT_SPEC:
            self.spectroscopy.setFixedSize(
                self.x_pos + self.sidebar_btn.width(), self.ui.main_display.height()
            )
        self.data_processing.setFixedSize(
            self.x_pos + self.sidebar_btn.width(), self.ui.main_display.height()
        )
        self.data_analysis.setFixedSize(
            self.x_pos + self.sidebar_btn.width(), self.ui.main_display.height()
        )
        self.ui.tool_bar.setFixedWidth(self.ui.main_display.width())

    def show_adv_settings(self):
        # Always allow opening the Settings dialog
        try:
            if self.advanced_menu is not None:
                # Best-effort refresh of advanced values before showing
                try:
                    self.advanced_menu.refresh_values()
                except Exception:
                    pass
            self.settings.show()
            self.settings.activateWindow()
        except Exception as e:
            # Fall back to a simple info message if settings cannot be shown
            show_message(f"Unable to open Settings: {e}", msg_type="Warning")

    def closeEvent(self, event):
        if show_message(msg="Quit application?", msg_type="Warning", yes_no=True):
            self.ui.status.setText("Closing application ... ")
            self.ui.status.repaint()
            self.sensorgram.reference_channel_dlg.close()
            self.data_processing.reference_channel_dlg.close()
            if DEV and (
                self.device_config["ctrl"] in ["PicoP4SPR", "PicoEZSPR"]
            ):  # EZSPR disabled
                self.advanced_menu.close()
            self.app.close()
            super().closeEvent(event)
        else:
            event.ignore()
