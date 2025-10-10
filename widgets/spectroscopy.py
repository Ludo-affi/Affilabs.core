from functools import partial

import numpy as np
from pyqtgraph import GraphicsLayoutWidget, mkPen, setConfigOptions
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QSizePolicy, QVBoxLayout, QWidget

from settings import CH_LIST, DEV, GRAPH_COLORS
from ui.ui_pop_out_dialog import Ui_SingleDialog
from ui.ui_spectroscopy import Ui_Spectroscopy
from utils.logger import logger


class Spectroscopy(QWidget):
    full_cal_sig = Signal()
    new_ref_sig = Signal()
    polarizer_sig = Signal(str)
    single_led_sig = Signal(str)

    def __init__(self):
        super().__init__()
        self.advanced_mode = False
        self.ui = Ui_Spectroscopy()
        self.ui.setupUi(self)
        self.led_mode = "auto"

        # setup plots
        self.intensity_plot_view = SpecPlot(
            "Intensity Plot", "Wavelength (nm)", "Intensity (counts)"
        )
        # Place SpecPlot widget into its container, removing any spacer-only items from the .ui that squeeze content
        layout_int = self._ensure_clean_container(self.ui.intensity_plot)
        self.intensity_plot_view.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        layout_int.addWidget(self.intensity_plot_view, 1)

        self.trans_plot_view = SpecPlot(
            "Transmittance Plot", "Wavelength (nm)", "Transmittance (%)"
        )
        layout_tr = self._ensure_clean_container(self.ui.transmission_plot)
        self.trans_plot_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout_tr.addWidget(self.trans_plot_view, 1)
        self.intensity_plot_view.show()
        self.trans_plot_view.show()

        # set up data source
        self.spec_data = {}

        # connect display channel check buttons
        for ch in CH_LIST:
            getattr(self.ui, f"segment_{ch.upper()}").stateChanged.connect(
                partial(self.display_channel_changed, ch)
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
        if DEV:
            self.ui.full_calibrate_btn.setEnabled(state)
        else:
            self.ui.full_calibrate_btn.setEnabled(False)

    def resizeEvent(self, event):
        self.intensity_plot_view.resize(
            self.ui.intensity_plot.width(), self.ui.intensity_plot.height()
        )
        self.trans_plot_view.resize(
            self.ui.transmission_plot.width(), self.ui.transmission_plot.height()
        )

    def update_data(self, spec_data):
        try:
            if spec_data is not None:
                self.intensity_plot_view.update_plots(
                    spec_data["wave_data"], spec_data["int_data"], self.led_mode
                )
                self.trans_plot_view.update_plots(
                    spec_data["wave_data"], spec_data["trans_data"], self.led_mode
                )
        except Exception as e:
            logger.debug(f"Error during spectroscopy update: {e}")

    def display_channel_changed(self, ch, flag):
        self.intensity_plot_view.display_channel_changed(ch, flag)
        self.trans_plot_view.display_channel_changed(ch, flag)

    def full_calibration(self):
        self.full_cal_sig.emit()

    def new_reference(self):
        self.new_ref_sig.emit()

    def set_polarizer(self):
        logger.debug(
            f"spectroscopy dropdown current text: {self.ui.polarization.currentText()}"
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

    def _ensure_clean_container(self, container_widget):
        """Ensure the given container has a clean, marginless layout without spacer items.
        If a layout exists, remove all its items (spacers/placeholders) and reuse it; otherwise create a new QVBoxLayout.
        """
        layout = container_widget.layout()
        if layout is None:
            layout = QVBoxLayout(container_widget)
        else:
            # Remove all existing items (likely spacers from the .ui)
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.setParent(None)
                # spacer items will be garbage collected
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        return layout


class SpecPlot(GraphicsLayoutWidget):
    def __init__(self, title_string, x_axis_string, y_axis_string):
        super().__init__()

        # Enable antialiasing for prettier plots
        setConfigOptions(antialias=True)

        # Set plot settings: title, grid, x, y axis labels
        self.plot = self.addPlot(title=title_string)
        self.plot.titleLabel.setText(title_string, color=(250, 250, 250), size="10pt")
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
        super().__init__(parent)
        self.ui = Ui_SingleDialog()
        self.ui.setupUi(self)
