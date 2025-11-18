from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from settings import DEV
from ui.ui_kinetic import Ui_Kinetic
from utils.logger import logger
from widgets.message import show_message


class Kinetic(QWidget):
    export_error_signal = Signal()
    sensor_read_en = Signal()

    run_sig = Signal(str, int)
    change_speed_sig = Signal(str, int)
    flush_sig = Signal(str)
    three_way_sig = Signal(str)
    six_port_sig = Signal(str)
    sync_sig = Signal(bool)

    def __init__(self):
        super().__init__()
        self.ui = Ui_Kinetic()
        self.ui.setupUi(self)

        self.no_kinetic = False
        self.knx2 = False
        self.knx = False

        self.sync = False
        self.updating = False

        self.state_sync1 = False
        self.state_sync2 = False

        self.ui.status1.setText("Off")
        self.ui.status2.setText("Off")

        self.ui.run1.clicked.connect(self.run_ch1)
        self.ui.run2.clicked.connect(self.run_ch2)
        self.ui.flush1.clicked.connect(self.flush_ch1)
        self.ui.flush2.clicked.connect(self.flush_ch2)
        self.ui.spr_ch1.clicked.connect(self.three_way_ch1)
        self.ui.waste_ch1.clicked.connect(self.three_way_ch1)
        self.ui.spr_ch2.clicked.connect(self.three_way_ch2)
        self.ui.waste_ch2.clicked.connect(self.three_way_ch2)
        self.ui.inject_ch1.clicked.connect(self.six_port_ch1)
        self.ui.load_ch1.clicked.connect(self.six_port_ch1)
        self.ui.inject_ch2.clicked.connect(self.six_port_ch2)
        self.ui.load_ch2.clicked.connect(self.six_port_ch2)
        self.ui.run_rate_ch1.currentIndexChanged.connect(self.change_speed_ch1)
        self.ui.run_rate_ch2.currentIndexChanged.connect(self.change_speed_ch2)
        self.ui.sync_1.clicked.connect(self.set_sync)
        self.ui.sync_2.clicked.connect(self.set_sync)

    def setup(self, ctrl_type, knx_type):
        self.reset_ui()
        # flow readings enabled for development version only
        if not DEV:
            self.ui.sensor_frame_ch1.setVisible(False)
            self.ui.sensor_frame_ch2.setVisible(False)
        if knx_type == "" and ctrl_type not in [
            "PicoEZSPR"
        ]:
            logger.debug("no kinetic")
            self.no_kinetic = True
        else:
            if knx_type == "KNX":
                self.knx = True
                self.ui.CH1.setEnabled(True)
                self.ui.sync_1.setEnabled(False)
            elif (knx_type in ["KNX2"]) or (
                ctrl_type in ["PicoEZSPR"]
            ):  # EZSPR/PicoKNX2 disabled
                self.knx2 = True
                self.ui.CH1.setEnabled(True)
                self.ui.CH2.setEnabled(True)
                logger.debug("Kinetic controls set up")
                self.ui.sync_1.setEnabled(True)
                self.ui.sync_2.setEnabled(True)
            self.sensor_read_en.emit()

    def update_readings(self, sensor_disp_vals):
        """Update sensor readings in the Kinetic UI.

        Flow sensors are obsolete; if flow keys are missing, default to blank.
        Temperature values are coerced to strings for display.
        """
        try:
            flow1 = str(sensor_disp_vals.get("flow1", ""))
            flow2 = str(sensor_disp_vals.get("flow2", ""))
            temp1 = str(sensor_disp_vals.get("temp1", ""))
            temp2 = str(sensor_disp_vals.get("temp2", ""))
            self.ui.flow1.setText(flow1)
            self.ui.temp1.setText(temp1)
            self.ui.flow2.setText(flow2)
            self.ui.temp2.setText(temp2)
        except Exception:
            # Be permissive: ignore any bad payloads
            pass

    def update_pump_ui(self, pump_states, sync):
        if pump_states["CH1"] == "Off":
            self.ui.run1.setText("Run")
            self.ui.run1.setEnabled(True)
            self.ui.flush1.setText("Flush")
            self.ui.flush1.setEnabled(True)
            self.ui.run_rate_ch1.setEnabled(True)
        elif pump_states["CH1"] == "Flushing":
            self.ui.run1.setEnabled(False)
            self.ui.flush1.setText("Stop")
            self.ui.flush1.setEnabled(True)
            self.ui.run_rate_ch1.setEnabled(False)
        elif pump_states["CH1"] == "Running":
            self.ui.run1.setText("Stop")
            self.ui.run1.setEnabled(True)
            self.ui.flush1.setEnabled(False)
            self.ui.run_rate_ch1.setEnabled(True)
        self.ui.status1.setText(pump_states["CH1"])
        if pump_states["CH2"] == "Off":
            self.ui.run2.setText("Run")
            self.ui.run2.setEnabled(True)
            self.ui.flush2.setText("Flush")
            self.ui.flush2.setEnabled(True)
            self.ui.run_rate_ch2.setEnabled(True)
        elif pump_states["CH2"] == "Flushing":
            self.ui.run2.setEnabled(False)
            self.ui.flush2.setText("Stop")
            self.ui.flush2.setEnabled(True)
            self.ui.run_rate_ch2.setEnabled(False)
        elif pump_states["CH2"] == "Running":
            self.ui.run2.setText("Stop")
            self.ui.run2.setEnabled(True)
            self.ui.flush2.setEnabled(False)
            self.ui.run_rate_ch2.setEnabled(True)
        self.ui.status2.setText(pump_states["CH2"])
        if self.knx or sync:
            self.ui.CH2.setEnabled(False)

    def update_valve_ui(self, valve_states, sync):
        logger.debug(f" valve states: {valve_states}, sync: {sync}")
        self.updating = True
        self.ui.CH2.setEnabled(True)
        self.ui.sample_flow_ch1.setEnabled(True)
        self.ui.sample_flow_ch2.setEnabled(True)
        self.ui.pump_flow_ch1.setEnabled(True)
        self.ui.pump_flow_ch2.setEnabled(True)

        if (
            valve_states["CH1"] in ["Inject", "Load"]
        ) and not self.ui.spr_ch1.isChecked():
            self.ui.spr_ch1.toggle()
        elif (
            valve_states["CH1"] in ["Waste", "Dispose"]
        ) and not self.ui.waste_ch1.isChecked():
            self.ui.waste_ch1.toggle()
        if (
            valve_states["CH1"] in ["Inject", "Dispose"]
        ) and not self.ui.inject_ch1.isChecked():
            self.ui.inject_ch1.toggle()
        elif (
            valve_states["CH1"] in ["Load", "Waste"]
        ) and not self.ui.load_ch1.isChecked():
            self.ui.load_ch1.toggle()
        if (
            valve_states["CH2"] in ["Inject", "Load"]
        ) and not self.ui.spr_ch2.isChecked():
            self.ui.spr_ch2.toggle()
        elif (
            valve_states["CH2"] in ["Waste", "Dispose"]
        ) and not self.ui.waste_ch2.isChecked():
            self.ui.waste_ch2.toggle()
        if (
            valve_states["CH2"] in ["Inject", "Dispose"]
        ) and not self.ui.inject_ch2.isChecked():
            self.ui.inject_ch2.toggle()
        elif (
            valve_states["CH2"] in ["Load", "Waste"]
        ) and not self.ui.load_ch2.isChecked():
            self.ui.load_ch2.toggle()

        if self.knx or sync:
            self.ui.CH2.setEnabled(False)

        self.updating = False

    def run_ch1(self):
        self.ui.status1.setText("Updating...")
        self.ui.status1.repaint()
        run_rate = int(self.ui.run_rate_ch1.currentText())
        self.run_sig.emit("CH1", run_rate)

    def run_ch2(self):
        self.ui.status2.setText("Updating...")
        self.ui.status1.repaint()
        run_rate = int(self.ui.run_rate_ch2.currentText())
        self.run_sig.emit("CH2", run_rate)

    def flush_ch1(self):
        self.ui.status1.setText("Updating...")
        self.ui.status1.repaint()
        self.flush_sig.emit("CH1")

    def flush_ch2(self):
        self.ui.status2.setText("Updating...")
        self.ui.status2.repaint()
        self.flush_sig.emit("CH2")

    def change_speed_ch1(self):
        self.change_speed_sig.emit("CH1", int(self.ui.run_rate_ch1.currentText()))

    def change_speed_ch2(self):
        self.change_speed_sig.emit("CH2", int(self.ui.run_rate_ch2.currentText()))

    def sync_speeds(self):
        self.ui.run_rate_ch2.setCurrentIndex(self.ui.run_rate_ch1.currentIndex())

    def three_way_ch1(self):
        if not self.updating:
            self.three_way_sig.emit("CH1")

    def three_way_ch2(self):
        if not self.updating:
            self.three_way_sig.emit("CH2")

    def six_port_ch1(self):
        if not self.updating:
            self.six_port_sig.emit("CH1")

    def six_port_ch2(self):
        if not self.updating:
            self.six_port_sig.emit("CH2")

    def set_sync(self, *, prompt: bool = True):
        self.updating = True
        if self.sync:
            self.sync = False
            logger.debug("stop channel sync")
            self.ui.sync_1.setChecked(False)
            self.ui.sync_2.setChecked(False)
            if self.knx2:
                self.ui.CH2.setEnabled(True)
        elif self.knx2:
            if not prompt or show_message(
                msg="Syncing Channel B with Channel A will override\n"
                "all Channel B settings: would you like to proceed?",
                yes_no=True,
            ):
                self.sync = True
                self.ui.status2.setText("Updating...")
                self.ui.status2.repaint()
                self.ui.CH2.setEnabled(False)
                self.ui.sync_1.setChecked(True)
                self.ui.sync_2.setChecked(True)
            else:
                self.ui.sync_1.setChecked(False)
                self.ui.sync_2.setChecked(False)
        self.sync_sig.emit(self.sync)
        self.updating = False

    def reset_ui(self):
        self.updating = True
        self.ui.sync_1.setChecked(False)
        self.state_sync1 = False
        self.ui.sync_2.setChecked(False)
        self.state_sync2 = False
        self.ui.sync_1.setEnabled(False)
        self.ui.sync_2.setEnabled(False)
        if self.sync:
            self.sync = False
            self.sync_sig.emit(self.sync)
        self.ui.load_ch1.setChecked(True)
        self.ui.load_ch2.setChecked(True)
        self.ui.waste_ch1.setChecked(True)
        self.ui.waste_ch2.setChecked(True)
        self.ui.run_rate_ch1.setCurrentIndex(0)
        self.ui.run_rate_ch2.setCurrentIndex(0)
        self.ui.status1.setText("Off")
        self.ui.status2.setText("Off")
        for k in ("run1", "run2", "flush1", "flush2"):
            getattr(self.ui, k).setEnabled(True)
        self.ui.run1.setText("Run")
        self.ui.run2.setText("Run")
        self.ui.flush1.setText("Flush")
        self.ui.flush2.setText("Flush")
        self.ui.CH1.setEnabled(False)
        self.ui.CH2.setEnabled(False)
        self.updating = False
