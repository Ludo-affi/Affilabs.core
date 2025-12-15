from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QWidget

from settings import DEV
from ui.ui_Affipump import Ui_Affipump
from ui.ui_device import Ui_Device
from ui.ui_EZSPR import Ui_EZSPRForm
from ui.ui_KNX2 import Ui_KNX2
from ui.ui_P4SPR import Ui_P4SPR_2
from ui.ui_QSPR import Ui_QSPR
from utils.logger import logger
from widgets.message import show_message


class Device(QWidget):
    connect_dev_sig = Signal()
    disconnect_dev_sig = Signal(str)
    quick_cal_sig = Signal()
    shutdown_sig = Signal(str)
    crt_sig = Signal(str)
    sensor_read_sig = Signal()
    init_pumps = Signal()

    def __init__(self):
        super(Device, self).__init__()
        self.ui = Ui_Device()
        self.ui.setupUi(self)
        self.p4spr = False
        self.qspr = False
        self.knx2 = False
        self.knx = False
        self.ctrl_widget = None
        self.ctrl_pico = False
        self.knx_widget = None
        self.knx_pico = False
        self.pump_widget = None
        self.up = False
        self.ui.add_ctrl.clicked.connect(self.call_connect)
        self.ui.add_knx.clicked.connect(self.call_connect)
        self.ui.add_pump.clicked.connect(self.call_connect)

    def setup(self, ctrl_type, knx_type, pump):
        logger.debug("updating device widget")
        # Reset display
        if self.ctrl_widget is not None:
            self.ctrl_widget.hide()
        if self.knx_widget is not None:
            self.knx_widget.hide()
        if self.pump_widget is not None:
            self.pump_widget.hide()
        # Set up controller
        if ctrl_type == "":
            self.ui.add_ctrl.show()
        elif ctrl_type in ["P4SPR", "PicoP4SPR"]:
            self.p4spr = True
            self.ui.add_ctrl.hide()
            self.ctrl_widget = P4SPRWidget(self.ui.controller_frame)
            if ctrl_type == "PicoP4SPR" and DEV:
                self.ctrl_widget.ui.temp_display.setVisible(True)
                self.sensor_read_sig.emit()
            else:
                self.ctrl_widget.ui.temp_display.setVisible(False)
            self.ctrl_widget.calibrate_btn.connect(self.call_calibrate)
            self.ctrl_widget.disconnect_btn.connect(self.call_disconnect)
        elif ctrl_type == "QSPR":
            self.up = False
            self.qspr = True
            self.ui.add_ctrl.hide()
            self.ctrl_widget = QSPRWidget(self.ui.controller_frame)
            self.ctrl_widget.calibrate_btn.connect(self.call_calibrate)
            self.ctrl_widget.disconnect_btn.connect(self.call_disconnect)
            self.ctrl_widget.shutdown_btn.connect(self.initiate_shutdown)
            self.ctrl_widget.crt_command.connect(self.cartridge_motion)
            self.sensor_read_sig.emit()
            if not DEV:
                self.ctrl_widget.ui.temp_display.hide()
        elif ctrl_type in ["EZSPR", "PicoEZSPR"]:
            if ctrl_type == "PicoEZSPR":
                self.ctrl_pico = True
            self.ui.add_ctrl.hide()
            self.ui.add_knx.hide()
            if self.ctrl_widget is not None:
                self.ctrl_widget.hide()
            self.ctrl_widget = EZSPRWidget(self.ui.controller_frame, self.ctrl_pico)
            self.ctrl_widget.calibrate_btn.connect(self.call_calibrate)
            self.ctrl_widget.disconnect_btn.connect(self.call_disconnect)
            self.ctrl_widget.shutdown_btn.connect(self.initiate_shutdown)
            if not DEV:
                self.ctrl_widget.ui.temp_display.hide()
        else:
            logger.debug(f"controller {ctrl_type} not supported")

        # Set up kinetic
        if knx_type == "":
            if ctrl_type == "":
                self.ui.add_knx.hide()
                self.ui.add_ctrl.setText("Add Devices")
            elif ctrl_type not in ["EZSPR", "PicoEZSPR"]:
                self.ui.add_knx.show()
        elif knx_type in ["KNX", "KNX2", "PicoKNX2"]:
            if knx_type == "PicoKNX2":
                self.knx_pico = True
            self.ui.add_knx.hide()
            self.knx_widget = KNX2Widget(self.ui.kinetic_frame, self.knx_pico)
            self.knx_widget.disconnect_btn.connect(self.call_disconnect)
            self.knx_widget.shutdown_btn.connect(self.initiate_shutdown)
            if knx_type == "KNX":
                self.knx_widget.ui.KnxBox.setTitle("KNX")
            if not DEV:
                self.knx_widget.ui.temp_display.hide()

        # Set up pump
        if pump is None:
            self.ui.add_pump.show()
        else:
            self.ui.add_pump.hide()
            self.pump_widget = AffipumpWidget(self.ui.pump_frame)
            self.pump_widget.disconnect_btn.connect(self.disconnect_dev_sig)
            self.pump_widget.initialize.connect(self.init_pumps)

        self.allow_commands(True)

    def allow_commands(self, state):
        try:
            if self.ctrl_widget is not None and type(state) == bool:
                self.ctrl_widget.ui.ctrls_frame.setEnabled(state)
        except AttributeError:
            pass

    def call_connect(self):
        self.connect_dev_sig.emit()

    def call_calibrate(self):
        self.quick_cal_sig.emit()

    def call_disconnect(self, disconnect_type):
        self.disconnect_dev_sig.emit(disconnect_type)

    def initiate_shutdown(self, device_type):
        self.shutdown_sig.emit(device_type)

    def cartridge_motion(self, command):
        if command == "up":
            if not self.up:
                self.up = True
                self.crt_sig.emit(command)
        else:
            self.up = False
            self.crt_sig.emit(command)

    def update_temp(self, temp_str, temp_type):
        try:
            if temp_type == "ctrl":
                self.ctrl_widget.update_temp(temp_str)
            else:
                self.knx_widget.update_temp(temp_str)
        except AttributeError:
            pass


class ControlWidgetBase(QWidget):
    calibrate_btn = Signal()
    disconnect_btn = Signal(str)
    shutdown_btn = Signal(str)

    def __init__(self):
        super(ControlWidgetBase, self).__init__()

    def update_temp(self, temp):
        pass


class AffipumpWidget(ControlWidgetBase):
    initialize = Signal()

    def __init__(self, parent):
        super().__init__()
        self.ui = Ui_Affipump()
        self.ui.setupUi(self)
        self.setParent(parent)
        self.show()
        self.ui.disconnect_btn.clicked.connect(self.disconnect_device)
        self.ui.initialize_btn.clicked.connect(self.initialize)

    @Slot()
    def disconnect_device(self):
        self.setEnabled(False)
        self.disconnect_btn.emit("pump")


class P4SPRWidget(ControlWidgetBase):
    def __init__(self, parent):
        super(P4SPRWidget, self).__init__()
        self.ui = Ui_P4SPR_2()
        self.ui.setupUi(self)
        self.setParent(parent)
        self.show()
        self.ui.quick_calibrate_btn.clicked.connect(self.quick_calibration)
        self.ui.disconnect_btn.clicked.connect(self.disconnect_device)

    def disconnect_device(self):
        self.setEnabled(False)
        self.disconnect_btn.emit("controller")

    def quick_calibration(self):
        self.calibrate_btn.emit()

    def update_temp(self, temp):
        self.ui.temp1.setText(temp)


class QSPRWidget(ControlWidgetBase):
    crt_command = Signal(str)

    def __init__(self, parent):
        super(QSPRWidget, self).__init__()
        self.ui = Ui_QSPR()
        self.ui.setupUi(self)
        self.setParent(parent)
        self.show()
        self.ui.disconnect_btn.clicked.connect(self.disconnect_device)
        self.ui.quick_calibrate_btn.clicked.connect(self.quick_calibration)
        self.ui.shutdown_btn.clicked.connect(self.shutdown_device)
        self.ui.crt_up_btn.clicked.connect(self.cartridge_up)
        self.ui.crt_down_btn.clicked.connect(self.cartridge_down)
        self.ui.adj_up_btn.clicked.connect(self.adjust_up)
        self.ui.adj_down_btn.clicked.connect(self.adjust_down)

    def quick_calibration(self):
        self.calibrate_btn.emit()

    def cartridge_up(self):
        self.crt_command.emit("up")

    def cartridge_down(self):
        self.crt_command.emit("down")

    def adjust_up(self):
        self.crt_command.emit("adj_up")

    def adjust_down(self):
        self.crt_command.emit("adj_down")

    def disconnect_device(self):
        self.setEnabled(False)
        self.disconnect_btn.emit("controller")

    def shutdown_device(self):
        self.setEnabled(False)
        if show_message(msg_type="Warning", msg="Power off QSPR?", yes_no=True):
            show_message(
                msg_type="Warning",
                msg="Warning: DO NOT UNPLUG\n "
                "Wait until power button light is OFF to unplug the device",
            )
            self.shutdown_btn.emit("controller")
        else:
            self.setEnabled(True)

    def update_temp(self, temp):
        self.ui.temp1.setText(temp)


class KNX2Widget(ControlWidgetBase):
    def __init__(self, parent, pico):
        super(KNX2Widget, self).__init__()
        self.ui = Ui_KNX2()
        self.ui.setupUi(self)
        self.setParent(parent)
        self.show()
        self.ui.shutdown_btn.clicked.connect(self.shutdown_device)
        self.ui.disconnect_btn.clicked.connect(self.disconnect_device)
        self.pico = pico

    def disconnect_device(self):
        self.setEnabled(False)
        self.disconnect_btn.emit("kinetic")

    def quick_calibration(self):
        self.calibrate_btn.emit()

    def update_temp(self, temp):
        self.ui.temp1.setText(temp)

    def shutdown_device(self):
        self.setEnabled(False)
        if show_message(msg_type="Warning", msg="Power off KNX2?", yes_no=True):
            if not self.pico:
                show_message(
                    msg_type="Warning",
                    msg="Warning: DO NOT UNPLUG\n "
                    "Wait until power button light is OFF to unplug the device",
                )
            self.shutdown_btn.emit("kinetic")
        else:
            self.setEnabled(True)


class EZSPRWidget(ControlWidgetBase):
    def __init__(self, parent, pico):
        super(EZSPRWidget, self).__init__()
        self.ui = Ui_EZSPRForm()
        self.ui.setupUi(self)
        self.setParent(parent)
        self.show()
        self.ui.temp_display.setVisible(False)
        self.ui.shutdown_btn.clicked.connect(self.shutdown_device)
        self.ui.disconnect_btn.clicked.connect(self.disconnect_device)
        self.ui.quick_calibrate_btn.clicked.connect(self.quick_calibration)
        self.pico = pico

    def disconnect_device(self):
        self.setEnabled(False)
        self.disconnect_btn.emit("both")

    def update_temp(self, temp):
        if not self.ui.temp_display.isVisible():
            self.ui.temp_display.setVisible(True)
        self.ui.temp1.setText(temp)

    def quick_calibration(self):
        self.calibrate_btn.emit()

    def shutdown_device(self):
        self.setEnabled(False)
        if show_message(msg_type="Warning", msg="Power off EZSPR?", yes_no=True):
            if not self.pico:
                show_message(
                    msg_type="Warning",
                    msg="Warning: DO NOT UNPLUG\n "
                    "Wait until power button light is OFF to unplug the device",
                )
            self.shutdown_btn.emit("both")
        else:
            self.setEnabled(True)
