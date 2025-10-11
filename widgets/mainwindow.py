from PySide6.QtCore import QPoint, QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton, QWidget

from settings import DEV, POP_OUT_SPEC, SW_VERSION
from ui.ui_main import Ui_mainWindow
from widgets.advanced import P4SPRAdvMenu
from widgets.analysis import AnalysisWindow
from widgets.datawindow import DataWindow
from widgets.diagnostic_viewer import DiagnosticViewer
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
        self.ui.version.setText(SW_VERSION)
        self.advanced_menu = None
        self.ui.adv_btn.setEnabled(False)
        self.device_config = {"ctrl": "", "knx": ""}

        # set up recording
        self.recording = False
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

        # Diagnostic viewer (hidden by default, opened on demand)
        self.diagnostic_viewer = None

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
        self.ui.adv_btn.clicked.connect(self.show_adv_settings)

        # Add diagnostic viewer button to toolbar
        self.diagnostic_btn = QPushButton("🔬", self.ui.tool_bar)
        self.diagnostic_btn.setToolTip("Open Processing Diagnostics\n(Real-time view of all processing steps)")
        self.diagnostic_btn.setMinimumSize(QSize(35, 35))
        self.diagnostic_btn.setMaximumSize(QSize(35, 35))
        self.diagnostic_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: rgba(200, 200, 255, 100);
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: rgba(150, 150, 255, 150);
            }
            QPushButton:pressed {
                background: rgba(100, 100, 200, 200);
            }
        """)
        self.diagnostic_btn.clicked.connect(self.show_diagnostic_viewer)
        # Insert before rec_btn in toolbar layout
        self.ui.horizontalLayout.insertWidget(self.ui.horizontalLayout.count() - 3, self.diagnostic_btn)

        self.set_main_widget("sensorgram")
        self.show()
        self.redo_layout()
        self.sidebar_btn_anim = None
        self.sidebar_anim = None
        self.main_frame_anim = None

        self.toggle_side_bar(animation_time=0)

    def on_device_config(self, config):
        self.device_config = config
        if DEV:
            if config["ctrl"] in [
                "PicoP4SPR",
                "PicoEZSPR",
            ]:  # EZSPR disabled (obsolete)
                self.advanced_menu = P4SPRAdvMenu(parent=self)
                self.settings = Settings(
                    self.sensorgram.reference_channel_dlg, self.advanced_menu, self
                )
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

        else:
            self.recording = True
            self.ui.recording_status.setText("Recording\nin Progress")
            self.ui.recording_status.setStyleSheet(
                "background: none; border: none; color: black;font: "
                "8pt 'Segoe UI Semibold';"
            )
            self.ui.rec_btn.setIcon(QIcon(":/img/img/stop.png"))

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
        if DEV:
            self.advanced_menu.refresh_values()
            self.settings.show()
            self.settings.activateWindow()

    def show_diagnostic_viewer(self):
        """Open the real-time processing diagnostics viewer."""
        if self.diagnostic_viewer is None:
            self.diagnostic_viewer = DiagnosticViewer(parent=self)
            # Connect to app's processing_steps_signal
            if hasattr(self.app, 'processing_steps_signal'):
                self.app.processing_steps_signal.connect(self.diagnostic_viewer.update_data)
        
        self.diagnostic_viewer.show()
        self.diagnostic_viewer.activateWindow()

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
