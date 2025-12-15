from functools import partial

import numpy as np
from pyqtgraph import GraphicsLayoutWidget, mkPen, setConfigOptions
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QWidget,
)

from affilabs.ui.ui_pop_out_dialog import Ui_SingleDialog
from affilabs.ui.ui_spectroscopy import Ui_Spectroscopy
from affilabs.utils.logger import logger
from settings import CH_LIST, DEV, GRAPH_COLORS


class Spectroscopy(QWidget):
    full_cal_sig = Signal()
    new_ref_sig = Signal()
    polarizer_sig = Signal(str)
    single_led_sig = Signal(str)

    def __init__(self):
        super(Spectroscopy, self).__init__()
        self.advanced_mode = False
        self.ui = Ui_Spectroscopy()
        self.ui.setupUi(self)
        self._fix_checkbox_styles()
        self.led_mode = "auto"

        # Configure graph toggles before creating plot widgets
        self._setup_graph_toggles()

        # setup plots
        self.intensity_plot_view = SpecPlot(
            "Intensity Plot",
            "Wavelength (nm)",
            "Intensity (counts)",
        )
        self.intensity_plot_view.setParent(self.ui.intensity_plot)
        self.trans_plot_view = SpecPlot(
            "Transmittance Plot",
            "Wavelength (nm)",
            "Transmittance (%)",
        )
        self.trans_plot_view.setParent(self.ui.transmission_plot)
        self.intensity_plot_view.show()
        self.trans_plot_view.show()

        # set up data source
        self.spec_data = {}

        # connect display channel check buttons
        for ch in CH_LIST:
            getattr(self.ui, f"segment_{ch.upper()}").stateChanged.connect(
                partial(self.display_channel_changed, ch),
            )

        # set up controls
        self.ui.new_ref_btn.clicked.connect(self.new_reference)
        self.ui.full_calibrate_btn.clicked.connect(self.full_calibration)
        self.ui.polarization.currentIndexChanged.connect(self.set_polarizer)
        self.ui.led_mode.currentIndexChanged.connect(self.set_led_mode)
        self.ui.single_A.clicked.connect(self.set_led_mode)
        self.ui.single_B.clicked.connect(self.set_led_mode)
        self.ui.single_C.clicked.connect(self.set_led_mode)
        self.ui.single_D.clicked.connect(self.set_led_mode)
        self.ui.led_off.clicked.connect(self.set_led_mode)
        self.enable_controls(False)

    def enable_controls(self, state):
        self.ui.controls.setEnabled(state)
        # Enable Auto-Align && Calibrate button
        self.ui.full_calibrate_btn.setEnabled(state)

    def resizeEvent(self, event):
        self.intensity_plot_view.resize(
            self.ui.intensity_plot.width(),
            self.ui.intensity_plot.height(),
        )
        self.trans_plot_view.resize(
            self.ui.transmission_plot.width(),
            self.ui.transmission_plot.height(),
        )

    def update_data(self, spec_data):
        try:
            if spec_data is not None:
                self.intensity_plot_view.update_plots(
                    spec_data["wave_data"],
                    spec_data["int_data"],
                    self.led_mode,
                )
                self.trans_plot_view.update_plots(
                    spec_data["wave_data"],
                    spec_data["trans_data"],
                    self.led_mode,
                )
        except Exception as e:
            logger.debug(f"Error during spectroscopy update: {e}")

    def display_channel_changed(self, ch, flag):
        self.intensity_plot_view.display_channel_changed(ch, flag)
        self.trans_plot_view.display_channel_changed(ch, flag)

    def _fix_checkbox_styles(self):
        """Fix checkbox styling to use global theme.

        Clears inline styles that override the global theme.
        """
        import re

        for checkbox_name in ["segment_A", "segment_B", "segment_C", "segment_D"]:
            if hasattr(self.ui, checkbox_name):
                checkbox = getattr(self.ui, checkbox_name)
                current_style = checkbox.styleSheet()
                if "color:" in current_style:
                    color_match = re.search(r"color:\s*([^;]+);", current_style)
                    if color_match:
                        color_value = color_match.group(1).strip()
                        checkbox.setStyleSheet(
                            f"QCheckBox {{ color: {color_value}; background-color: transparent; }}",
                        )
                else:
                    checkbox.setStyleSheet(
                        "QCheckBox { background-color: transparent; }",
                    )

    def full_calibration(self):
        self.full_cal_sig.emit()

    def new_reference(self):
        self.new_ref_sig.emit()

    def set_polarizer(self):
        logger.debug(
            f"spectroscopy dropdown current text: {self.ui.polarization.currentText()}",
        )
        self.polarizer_sig.emit(self.ui.polarization.currentText().lower())

    def set_led_mode(self):
        self.trans_plot_view.clear_plots()
        self.intensity_plot_view.clear_plots()
        if self.ui.led_mode.currentText() == "Auto":
            self.led_mode = "auto"
            self.ui.single_LED.setEnabled(False)
        else:
            self.ui.single_LED.setEnabled(True)
            if self.ui.single_A.isChecked():
                self.led_mode = "a"
            elif self.ui.single_B.isChecked():
                self.led_mode = "b"
            elif self.ui.single_C.isChecked():
                self.led_mode = "c"
            elif self.ui.single_D.isChecked():
                self.led_mode = "d"
            elif self.ui.led_off.isChecked():
                self.led_mode = "x"
        self.single_led_sig.emit(self.led_mode)

    def _setup_graph_toggles(self):
        """Insert circular toggle controls to switch/raw view visibility."""
        # Reorder plots so transmission is always first
        plots_layout = self.ui.Plots
        plots_layout.removeWidget(self.ui.intensity_plot)
        plots_layout.removeWidget(self.ui.transmission_plot)
        plots_layout.addWidget(self.ui.transmission_plot)
        plots_layout.addWidget(self.ui.intensity_plot)

        toggle_frame = QFrame(self)
        toggle_layout = QHBoxLayout(toggle_frame)
        toggle_layout.setContentsMargins(4, 0, 4, 4)
        toggle_layout.setSpacing(12)

        title = QLabel("Graph Selector", toggle_frame)
        title.setStyleSheet("font-weight: 600; color: rgb(60, 60, 75);")
        toggle_layout.addWidget(title)

        dot_style = (
            "QRadioButton::indicator {"
            " width: 14px;"
            " height: 14px;"
            " border-radius: 7px;"
            " border: 2px solid rgb(150, 150, 150);"
            " background: transparent;"
            "}"
            "QRadioButton::indicator:checked {"
            " background: rgb(0, 102, 204);"
            " border-color: rgb(0, 102, 204);"
            "}"
        )

        self.transmission_toggle = QRadioButton(toggle_frame)
        self.transmission_toggle.setStyleSheet(dot_style)
        self.transmission_toggle.setToolTip("Show transmission graph only")
        transmission_label = QLabel("Transmission", toggle_frame)

        self.raw_toggle = QRadioButton(toggle_frame)
        self.raw_toggle.setStyleSheet(dot_style)
        self.raw_toggle.setToolTip("Reveal raw data graph underneath")
        raw_label = QLabel("Raw", toggle_frame)

        toggle_layout.addWidget(self.transmission_toggle)
        toggle_layout.addWidget(transmission_label)
        toggle_layout.addSpacing(10)
        toggle_layout.addWidget(self.raw_toggle)
        toggle_layout.addWidget(raw_label)
        toggle_layout.addStretch(1)

        plots_layout.insertWidget(0, toggle_frame)

        self.graph_toggle_group = QButtonGroup(self)
        self.graph_toggle_group.addButton(self.transmission_toggle)
        self.graph_toggle_group.addButton(self.raw_toggle)

        self.transmission_toggle.setChecked(True)
        self.raw_toggle.setChecked(False)
        self.ui.intensity_plot.setVisible(True)  # Show raw spectrum by default

        self.transmission_toggle.toggled.connect(self._update_graph_visibility)
        self.raw_toggle.toggled.connect(self._update_graph_visibility)

    def _update_graph_visibility(self):
        """Show raw graph when its toggle is selected."""
        show_raw = getattr(self, "raw_toggle", None) and self.raw_toggle.isChecked()
        self.ui.intensity_plot.setVisible(bool(show_raw))


class SpecPlot(GraphicsLayoutWidget):
    def __init__(self, title_string, x_axis_string, y_axis_string):
        super(SpecPlot, self).__init__()

        # Enable antialiasing for prettier plots
        setConfigOptions(antialias=True)

        # Set plot settings: title (optional), grid, x, y axis labels
        if title_string:
            self.plot = self.addPlot(title=title_string)
            self.plot.titleLabel.setText(
                title_string,
                color=(250, 250, 250),
                size="10pt",
            )
        else:
            self.plot = self.addPlot()
        self.plot.showGrid(x=True, y=True)
        if DEV:
            self.plot.setMenuEnabled(True)
            self.plot.setMouseEnabled(True)
        else:
            self.plot.setMenuEnabled(False)
            self.plot.setMouseEnabled(False)
        self.plot.setDownsampling(ds=50, mode="subsample")
        self.plot.setLabel("left", y_axis_string)
        self.plot.setLabel("bottom", x_axis_string)

        # create plots for channels
        self.plots = {}
        for ch in CH_LIST:
            self.plots[ch] = self.plot.plot(pen=mkPen(GRAPH_COLORS[ch], width=2))

    def clear_plots(self):
        for ch in CH_LIST:
            self.plots[ch].setData(y=[np.nan], x=[np.nan])

    def update_plots(self, x_data, y_data, led_mode):
        try:
            for ch in CH_LIST:
                if y_data[ch] is None:
                    self.plots[ch].setData(y=[np.nan], x=[np.nan])
                elif (led_mode == "auto") or (ch == led_mode):
                    self.plots[ch].setData(y=y_data[ch], x=x_data)
        except Exception as e:
            logger.debug(f"Error while plotting: {e}")

    def display_channel_changed(self, ch, flag):
        self.plots[ch].setVisible(bool(flag))


class SpecDebugWindow(QDialog):
    def __init__(self, parent=None):
        super(SpecDebugWindow, self).__init__(parent)
        self.ui = Ui_SingleDialog()
        self.ui.setupUi(self)
