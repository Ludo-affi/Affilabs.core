from PySide6.QtCore import QPoint, QPropertyAnimation, QSize, Qt, Signal  # type: ignore
from PySide6.QtGui import QIcon  # type: ignore
from PySide6.QtWidgets import QPushButton, QWidget  # type: ignore

from settings import DEV, POP_OUT_SPEC, SW_APP_NAME, SW_VERSION
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
            "	border: 2px solid rgb(46, 48, 227);\n"
            "	border-radius: 4px;\n"
            "}\n"
            "QPushButton:pressed{\n"
            "	background: rgb(230, 230, 230);\n"
            "}",
        )
        self.ui.adv_btn.setToolTip(
            "Settings - Configure SPR tracking, calibration, and advanced options",
        )
        self.device_config = {"ctrl": "", "knx": ""}

        # set up recording
        self.recording = False
        # Hide the recording status label initially (shows "ghost button" when empty)
        self.ui.recording_status.hide()
        self.ui.rec_btn.clicked.connect(self.record_trigger)

        # set minimum size
        self.sidebar_width = 380

        # setup button styles - cache original and selected styles
        self.original_style = self.ui.sensorgram_btn.styleSheet()
        self.selected_style = (
            "background-color: rgb(254, 254, 254); border: 2px solid rgb(46, 48, 227); "
            "border-radius: 3px;"
        )
        # Cache button references for faster access
        self._page_buttons = {
            "sensorgram": self.ui.sensorgram_btn,
            "spectroscopy": self.ui.spectroscopy_btn,
            "data_processing": self.ui.data_processing_btn,
            "data_analysis": self.ui.data_analysis_btn,
        }

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

        # Sensorgram window (always created - main view)
        self.sensorgram = DataWindow("dynamic")
        self.sensorgram.setParent(self.ui.main_display)

        # Lazy-loaded windows (created on first access)
        self._spectroscopy = None
        self._spec_pop_out = None
        self._data_processing = None
        self._data_analysis = None

        # recording errors
        self.sensorgram.export_error_signal.connect(self._on_record_error)
        self.sidebar.kinetic_widget.export_error_signal.connect(self._on_record_error)

        # display
        self.x_pos = self.width() - self.sidebar_btn.width()

        # resize sensorgram (others lazy-loaded)
        self.sensorgram.setFixedSize(
            self.ui.main_display.width(),
            self.ui.main_display.height(),
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
                self.advanced_menu
                if self.advanced_menu is not None
                else P4SPRAdvMenu(parent=self),
                self,
            )
        except Exception:
            # Fallback minimal settings if construction fails for any reason
            self.settings = Settings(
                self.sensorgram.reference_channel_dlg,
                P4SPRAdvMenu(parent=self),
                self,
            )

        self.ui.adv_btn.clicked.connect(self.show_adv_settings)

        self.set_main_widget("sensorgram")
        self.show()
        self.redo_layout()
        self.sidebar_btn_anim = None
        self.sidebar_anim = None
        self.main_frame_anim = None

        self.toggle_side_bar(animation_time=0)

    @property
    def spectroscopy(self):
        """Lazy-load spectroscopy window."""
        if self._spectroscopy is None:
            self._spectroscopy = Spectroscopy()
            if POP_OUT_SPEC:
                self._spectroscopy.setParent(self.spec_pop_out.ui.single_frame)
            else:
                self._spectroscopy.setParent(self.ui.main_display)
            self._spectroscopy.setFixedSize(
                self.ui.main_display.width(),
                self.ui.main_display.height(),
            )
        return self._spectroscopy

    @property
    def spec_pop_out(self):
        """Lazy-load spectroscopy popup window."""
        if self._spec_pop_out is None:
            self._spec_pop_out = SpecDebugWindow(parent=self)
        return self._spec_pop_out

    @property
    def data_processing(self):
        """Lazy-load data processing window."""
        if self._data_processing is None:
            self._data_processing = DataWindow("static")
            self._data_processing.setParent(self.ui.main_display)
            self._data_processing.setFixedSize(
                self.ui.main_display.width(),
                self.ui.main_display.height(),
            )
        return self._data_processing

    @property
    def data_analysis(self):
        """Lazy-load data analysis window."""
        if self._data_analysis is None:
            self._data_analysis = AnalysisWindow()
            self._data_analysis.setParent(self.ui.main_display)
            self._data_analysis.setFixedSize(
                self.ui.main_display.width(),
                self.ui.main_display.height(),
            )
        return self._data_analysis

    def on_device_config(self, config):
        self.device_config = config
        # Ensure advanced/settings menus exist; refresh when device config arrives
        if self.advanced_menu is None:
            self.advanced_menu = P4SPRAdvMenu(parent=self)
        if not hasattr(self, "settings") or self.settings is None:
            self.settings = Settings(
                self.sensorgram.reference_channel_dlg,
                self.advanced_menu,
                self,
            )

        # Optionally refresh advanced values for supported controllers
        if config.get("ctrl") in ["PicoP4SPR", "PicoEZSPR"]:
            try:
                self.advanced_menu.refresh_values()
            except Exception:
                pass
        self.connect_adv_sig.emit()

    def main_display_resized(self):
        self.sensorgram.setFixedSize(
            self.ui.main_display.width(),
            self.ui.main_display.height(),
        )
        # Only resize lazy-loaded windows if they've been created
        if self._spectroscopy is not None:
            self._spectroscopy.setFixedSize(
                self.ui.main_display.width(),
                self.ui.main_display.height(),
            )
        if self._data_processing is not None:
            self._data_processing.setFixedSize(
                self.ui.main_display.width(),
                self.ui.main_display.height(),
            )
        if self._data_analysis is not None:
            self._data_analysis.setFixedSize(
                self.ui.main_display.width(),
                self.ui.main_display.height(),
            )

    # navigate the main contents: Sensorgram, Spectroscopy, DataProcessing
    def set_main_widget(self, window_id):
        # Use cached button references for performance
        page_list = self._page_buttons

        # Batch UI updates for better performance
        self.setUpdatesEnabled(False)
        try:
            # Hide all pages
            for page_name in page_list:
                getattr(self, page_name).hide()
            self.active_page = window_id

            revert = False
            if self.sidebar_state == "maximized":
                self.toggle_side_bar(animation_time=0)
                revert = True

            # Update button styles and show active page
            for page_name, button in page_list.items():
                if page_name == self.active_page:
                    getattr(self, page_name).show()
                    button.setStyleSheet(self.selected_style)
                else:
                    button.setStyleSheet(self.original_style)

            self.redo_layout()
            if revert:
                self.toggle_side_bar(animation_time=0)
        finally:
            self.setUpdatesEnabled(True)

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
        # Batch updates for better performance
        self.setUpdatesEnabled(False)
        try:
            if self.sidebar_state == "minimized":
                self.x_pos = self.width() - self.sidebar_btn.width()
            else:
                self.x_pos = (
                    self.width() - self.sidebar_btn.width() - self.sidebar.width()
                )

            self.ui.main_frame.setGeometry(
                0,
                0,
                self.x_pos + self.sidebar_btn.width(),
                self.height(),
            )

            # Resize sensorgram (always created)
            self.sensorgram.setFixedSize(
                self.ui.main_display.width(),
                self.ui.main_display.height(),
            )

            # Only resize lazy-loaded windows if they've been created
            if (
                POP_OUT_SPEC
                and self._spec_pop_out is not None
                and self._spectroscopy is not None
            ):
                self._spectroscopy.setFixedSize(
                    self._spec_pop_out.ui.single_frame.width(),
                    self._spec_pop_out.ui.single_frame.height(),
                )
            elif self._spectroscopy is not None:
                self._spectroscopy.setFixedSize(
                    self.ui.main_display.width(),
                    self.ui.main_display.height(),
                )

            if self._data_processing is not None:
                self._data_processing.setFixedSize(
                    self.ui.main_display.width(),
                    self.ui.main_display.height(),
                )

            if self._data_analysis is not None:
                self._data_analysis.setFixedSize(
                    self.ui.main_display.width(),
                    self.ui.main_display.height(),
                )
                self._data_analysis.resizeEvent()

            self.sidebar.move(self.x_pos + self.sidebar_btn.width(), 0)
            self.sidebar.setFixedSize(self.sidebar_width, self.height())
            self.sidebar_btn.move(self.x_pos - 5, 20)
            self.ui.tool_bar.setFixedWidth(self.ui.main_display.width())
        finally:
            self.setUpdatesEnabled(True)

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
                "background: none; color: red; font: 8pt 'Segoe UI Black';",
            )
            self.ui.rec_btn.setIcon(QIcon(":/img/img/record.png"))
            # Hide the label when not recording to avoid "ghost button" appearance
            self.ui.recording_status.hide()

        else:
            self.recording = True
            self.ui.recording_status.setText("Recording\nin Progress")
            self.ui.recording_status.setStyleSheet(
                "background: none; border: none; color: black;font: "
                "8pt 'Segoe UI Semibold';",
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

        # Reuse animation objects for better performance
        if self.sidebar_btn_anim is None:
            self.sidebar_btn_anim = QPropertyAnimation(self.sidebar_btn, b"pos")
        self.sidebar_btn_anim.setEndValue(QPoint(self.x_pos - 5, self.sidebar_btn.y()))
        self.sidebar_btn_anim.setDuration(animation_time)
        self.sidebar_btn_anim.start()

        if self.sidebar_anim is None:
            self.sidebar_anim = QPropertyAnimation(self.sidebar, b"pos")
        self.sidebar_anim.setEndValue(
            QPoint(self.x_pos + self.sidebar_btn.width(), self.sidebar.y()),
        )
        self.sidebar_anim.setDuration(animation_time)
        self.sidebar_anim.start()

        if self.main_frame_anim is None:
            self.main_frame_anim = QPropertyAnimation(self.ui.main_frame, b"size")
        self.main_frame_anim.setStartValue(self.ui.main_frame.size())
        self.main_frame_anim.setEndValue(
            QSize(self.x_pos + self.sidebar_btn.width(), self.height()),
        )
        self.main_frame_anim.setDuration(animation_time)
        self.main_frame_anim.start()

        # Batch widget resizing
        self.setUpdatesEnabled(False)
        try:
            self.sensorgram.setFixedSize(
                self.x_pos + self.sidebar_btn.width(),
                self.ui.main_display.height(),
            )
            if not POP_OUT_SPEC and self._spectroscopy is not None:
                self._spectroscopy.setFixedSize(
                    self.x_pos + self.sidebar_btn.width(),
                    self.ui.main_display.height(),
                )
            if self._data_processing is not None:
                self._data_processing.setFixedSize(
                    self.x_pos + self.sidebar_btn.width(),
                    self.ui.main_display.height(),
                )
            if self._data_analysis is not None:
                self._data_analysis.setFixedSize(
                    self.x_pos + self.sidebar_btn.width(),
                    self.ui.main_display.height(),
                )
            self.ui.tool_bar.setFixedWidth(self.ui.main_display.width())
        finally:
            self.setUpdatesEnabled(True)

    def show_adv_settings(self):
        # Always allow opening the Settings dialog
        try:
            if self.advanced_menu is not None:
                # Best-effort refresh of advanced values before showing
                try:
                    self.advanced_menu.refresh_values()
                except Exception:
                    pass

                # Load calibration parameters if available
                try:
                    if (
                        hasattr(self, "data_mgr")
                        and self.data_mgr
                        and hasattr(self.data_mgr, "calibration_data")
                    ):
                        cal_data = self.data_mgr.calibration_data
                        if cal_data and hasattr(
                            self.advanced_menu,
                            "load_calibration_params",
                        ):
                            self.advanced_menu.load_calibration_params(cal_data)
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
            self.sensorgram.reference_channel_dlg.close()
            # Access lazy-loaded windows only if they exist
            if self._data_processing is not None:
                self._data_processing.reference_channel_dlg.close()
            if DEV and (
                self.device_config["ctrl"] in ["PicoP4SPR", "PicoEZSPR"]
            ):  # EZSPR disabled
                if self.advanced_menu is not None:
                    self.advanced_menu.close()
            self.app.close()
            super().closeEvent(event)
        else:
            event.ignore()
