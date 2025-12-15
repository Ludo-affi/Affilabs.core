# This module is riddled with long function that have too many statements, too many
# branches, and are too complex. It also contains a lot of catch all exception blocks.
# These should eventually be adressed, but for now we'll just turn off the warnings.
# ruff: noqa: PLR0912, PLR0915, C901, BLE001

"""Defines and launches the application."""

import asyncio
import csv
import datetime as dt
import faulthandler
import gc
import os
import sys
import threading
import time
from asyncio import create_task, get_event_loop, set_event_loop_policy
from contextlib import suppress
from copy import deepcopy
from pathlib import Path
from types import TracebackType
from typing import Self

import numpy as np
import pyqtgraph
import serial
from pump_controller import FTDIError, PumpController
from PySide6.QtAsyncio import QAsyncioEventLoopPolicy
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow
from scipy.fft import dst, idct
from scipy.signal import find_peaks, peak_prominences, peak_widths
from scipy.stats import linregress

from settings import (
    CH_LIST,
    DARK_NOISE_SCANS,
    DEV,
    EZ_CH_LIST,
    FILTERING_ON,
    FLUSH_RATE,
    INTEGRATION_STEP,
    LED_DELAY,
    MAX_INTEGRATION,
    MAX_NUM_SCANS,
    MAX_READ_TIME,
    MAX_WAVELENGTH,
    MED_FILT_WIN,
    MIN_INTEGRATION,
    MIN_WAVELENGTH,
    P_COUNT_THRESHOLD,
    P_LED_MAX,
    P_MAX_INCREASE,
    RECORDING_INTERVAL,
    REF_SCANS,
    ROOT_DIR,
    S_COUNT_MAX,
    S_LED_INT,
    S_LED_MIN,
    SENSOR_AVG,
    SENSOR_POLL_INTERVAL,
    SW_VERSION,
    TRANS_SEG_H_REQ,
)
from utils.common import get_config
from utils.controller import (
    ArduinoController,
    KineticController,
    PicoEZSPR,
    PicoKNX2,
    PicoP4SPR,
    QSPRController,
)
from utils.logger import logger
from utils.usb4000 import USB4000
from widgets.datawindow import Segment
from widgets.mainwindow import MainWindow
from widgets.message import show_message
from widgets.priming import PrimingWindow

with suppress(ImportError):
    import pyi_splash

pyqtgraph.setConfigOption("background", "w")
pyqtgraph.setConfigOption("foreground", "k")


os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
DEVICES = ["P4SPR", "PicoP4SPR", "QSPR", "EZSPR", "PicoEZSPR"]
TIME_ZONE = dt.datetime.now(dt.UTC).astimezone().tzinfo

Controller = ArduinoController | PicoEZSPR | PicoP4SPR | QSPRController
KNX = KineticController | PicoKNX2 | PicoEZSPR


class AffiniteApp(QMainWindow):
    """Main Window."""

    # index of minimum wavelength
    wave_min_index = 0
    # index of maximum wavelength
    wave_max_index = 0
    # number of intensity readings to average
    num_scans = 0
    # detector integration time in ms
    integration = MIN_INTEGRATION

    update_live_signal = Signal(dict)
    update_spec_signal = Signal(dict)

    raise_error = Signal(str)
    calibration_status = Signal(bool, str)
    calibration_started = Signal()
    connected = Signal()
    new_ref_done_sig = Signal()

    update_sensor_display = Signal(dict)
    update_temp_display = Signal(str, str)
    update_pump_display = Signal(dict, bool)
    update_valve_display = Signal(dict, bool)
    sync_speed_sig = Signal()
    knx_reset_ui = Signal()
    temp_sig = Signal(float)

    calibrated = False  # Calibration flag

    ctrl: Controller | None = None
    knx: KNX | None = None
    pump: PumpController | None = None
    auto_polarize = False
    flow_rate: float = 0.5

    def __init__(self: Self) -> None:
        """Create the app's main window."""
        gc.enable()
        self.main_window = MainWindow(self)
        self.device_config = {"ctrl": "", "knx": ""}
        self.conf = get_config()
        self.usb = USB4000(self)
        self.recording = False
        self.rec_dir = ""
        self.adv_connected = False

        # Final LED intensities placeholder
        self.leds_calibrated = {"a": 170, "b": 170, "c": 170, "d": 170}
        # LED ref intensities placeholder
        self.ref_intensity = {"a": 170, "b": 170, "c": 170, "d": 170}

        # reference data
        self.ref_sig = {ch: np.array([]) for ch in CH_LIST}
        # intensity data
        self.int_data = {ch: np.array([]) for ch in CH_LIST}
        # transmission data
        self.trans_data = {ch: np.array([]) for ch in CH_LIST}

        # sensorgram data for each channel
        self.lambda_values = {ch: np.array([]) for ch in CH_LIST}
        # sensorgram data timestamps
        self.lambda_times = {ch: np.array([]) for ch in CH_LIST}
        # sensorgram data with median filter on lambda values
        self.filtered_lambda = {ch: np.array([]) for ch in CH_LIST}
        # sensorgram data unfiltered buffered values
        self.buffered_lambda = {ch: np.array([]) for ch in CH_LIST}
        # sensorgram data time for filtered data
        self.buffered_times = {ch: np.array([]) for ch in CH_LIST}

        # start with no fixed filtered data
        self.filt_buffer_index = 0
        self.new_filtered_data = np.array([])

        # User settable advanced parameters
        # enable/disable filtering
        self.filt_on = FILTERING_ON
        # default declaration
        self.med_filt_win = MED_FILT_WIN
        self.proc_filt_win = MED_FILT_WIN
        # ensure odd size window for sensorgram median filtering
        self.median_window(deepcopy(MED_FILT_WIN))
        # time delay after LEDs turned on
        self.led_delay = LED_DELAY
        # height requirement for curve fitting
        self.ht_req = TRANS_SEG_H_REQ
        # time between sensor polls
        self.sensor_interval: float = SENSOR_POLL_INTERVAL

        self._b_stop = threading.Event()
        self._b_stop.set()
        self._b_kill = threading.Event()
        self._b_kill.clear()
        self._b_no_read = threading.Event()
        self._b_no_read.clear()

        self._tr = threading.Thread(target=self._grab_data)
        self._tr.start()

        self._c_kill = threading.Event()
        self._c_stop = threading.Event()
        self._c_stop.set()
        self._c_kill.clear()
        self._c_tr = threading.Thread(target=self.calibrate)
        self._c_tr.start()

        self._con_tr = threading.Thread(target=self.connection_thread)
        self._new_sig_tr = threading.Thread(target=self.new_ref_thread)

        self.single_mode = False
        self.single_ch = "x"

        self._s_kill = threading.Event()
        self._s_stop = threading.Event()
        self._s_kill.clear()
        self._s_stop.set()
        self._s_tr = threading.Thread(target=self.sensor_reading_thread)
        self._s_tr.start()

        self.rec_timer = QTimer()
        self.rec_timer.timeout.connect(self.save_rec_data)

        self.update_timer = QTimer()

        self.timer1 = QTimer()
        self.timer2 = QTimer()
        self.timer1.timeout.connect(self.turn_off_six_ch1)
        self.timer2.timeout.connect(self.turn_off_six_ch2)

        self.temp_log: dict[str, list[str]] = {
            "readings": [],
            "times": [],
            "exp": [],
        }
        self.temp = 0.0
        self.flow_buf_1: list[float] = []
        self.temp_buf_1: list[float] = []
        self.flow_buf_2: list[float] = []
        self.temp_buf_2: list[float] = []
        self.log_ch1: dict[str, list[str]] = {
            "timestamps": [],
            "times": [],
            "events": [],
            "flow": [],
            "temp": [],
            "dev": [],
        }
        self.log_ch2: dict[str, list[str]] = {
            "timestamps": [],
            "times": [],
            "events": [],
            "flow": [],
            "temp": [],
            "dev": [],
        }

        self.pump_states = {"CH1": "Off", "CH2": "Off"}
        self.valve_states = {"CH1": "Waste", "CH2": "Waste"}
        self.synced = False

        self.exp_start = time.time()
        self.reconnect_count = 2
        self.closing = False
        self.new_default_values = False

        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, on=True)

        self.calibration_status.connect(self._on_calibration_status)
        self.calibration_started.connect(self._on_calibration_started)
        self.connected.connect(self.open_device)
        self.raise_error.connect(self.error_handler)
        self.new_ref_done_sig.connect(self.new_ref_done)
        self.temp_sig.connect(self.update_internal_temp)

        #  replacement flag
        self.update_spec_signal.connect(self.main_window.spectroscopy.update_data)
        #  replacement flag
        self.update_live_signal.connect(self.main_window.sensorgram.update_data)
        #  replacement flag
        self.update_temp_display.connect(
            self.main_window.sidebar.device_widget.update_temp,
        )
        #  replacement flag
        self.update_sensor_display.connect(
            self.main_window.sidebar.kinetic_widget.update_readings,
        )
        #  replacement flag
        self.update_pump_display.connect(
            self.main_window.sidebar.kinetic_widget.update_pump_ui,
        )
        #  replacement flag
        self.update_valve_display.connect(
            self.main_window.sidebar.kinetic_widget.update_valve_ui,
        )
        #  replacement flag
        self.sync_speed_sig.connect(self.main_window.sidebar.kinetic_widget.sync_speeds)
        #  replacement flag
        self.knx_reset_ui.connect(self.main_window.sidebar.kinetic_widget.reset_ui)

        # Main Window Signals
        self.main_window.set_start_sig.connect(self.set_start)
        self.main_window.clear_flow_buf_sig.connect(self.clear_sensor_reading_buffers)
        self.main_window.record_sig.connect(self.recording_on)

        # Data Window Signals
        self.main_window.sensorgram.reset_graphs_sig.connect(self.clear_data)
        self.main_window.sensorgram.reference_channel_dlg.live_filt_sig.connect(
            self.set_live_filt,
        )
        self.main_window.sensorgram.save_sig.connect(self.manual_export_raw_data)
        self.main_window.data_processing.send_to_analysis_sig.connect(
            self.send_to_analysis,
        )
        self.main_window.data_processing.reference_channel_dlg.proc_filt_sig.connect(
            self.set_proc_filt,
        )
        self.main_window.data_processing.pull_sensorgram_sig.connect(
            self.transfer_sens_data,
        )
        self.main_window.sensorgram.ui.inject_button.clicked.connect(
            self.handle_inject_button,
        )
        self.main_window.sensorgram.ui.regen_button.clicked.connect(
            self.handle_regen_button,
        )
        self.main_window.sensorgram.ui.flush_button.clicked.connect(
            self.handle_flush_button,
        )
        self.main_window.sensorgram.ui.flow_rate.editingFinished.connect(
            self.change_flow_rate,
        )

        # Device Signals
        self.main_window.sidebar.device_widget.connect_dev_sig.connect(self.connect_dev)
        self.main_window.sidebar.device_widget.disconnect_dev_sig.connect(
            self.disconnect_handler,
        )
        self.main_window.sidebar.device_widget.quick_cal_sig.connect(
            self.quick_calibration,
        )
        self.main_window.sidebar.device_widget.shutdown_sig.connect(
            self.shutdown_handler,
        )
        self.main_window.sidebar.device_widget.crt_sig.connect(self.crt_control_handler)
        self.main_window.sidebar.device_widget.sensor_read_sig.connect(
            self.enable_sensor_reading,
        )
        self.main_window.sidebar.device_widget.init_pumps.connect(self.initialize_pumps)

        # Kinetic Signals
        self.main_window.sidebar.kinetic_widget.sensor_read_en.connect(
            self.enable_sensor_reading,
        )
        self.main_window.sidebar.kinetic_widget.run_sig.connect(self.run_button_handler)
        self.main_window.sidebar.kinetic_widget.flush_sig.connect(
            self.flush_button_handler,
        )
        self.main_window.sidebar.kinetic_widget.change_speed_sig.connect(
            self.speed_change_handler,
        )
        self.main_window.sidebar.kinetic_widget.three_way_sig.connect(
            self.three_way_handler,
        )
        self.main_window.sidebar.kinetic_widget.six_port_sig.connect(
            self.six_port_handler,
        )
        self.main_window.sidebar.kinetic_widget.sync_sig.connect(self.sync_handler)

        self.main_window.spectroscopy.ui.prime_btn.clicked.connect(self.prime)

        if DEV:
            self.main_window.connect_adv_sig.connect(self.connect_advanced_menu)

        self.main_window.spectroscopy.full_cal_sig.connect(self.full_recalibration)
        self.main_window.spectroscopy.new_ref_sig.connect(self.start_new_ref)
        self.main_window.spectroscopy.single_led_sig.connect(self.single_led)
        self.main_window.spectroscopy.polarizer_sig.connect(self.set_polarizer)

        self.kinetic_tasks = set()

    def connection_thread(self: Self) -> None:
        """Attempt to connect to different controlers."""
        qspr = QSPRController()
        arduino = ArduinoController()
        knx2 = KineticController()
        pico_p4spr = PicoP4SPR()
        pico_ezspr = PicoEZSPR()
        pico_knx2 = PicoKNX2()
        try:
            # Look for controller if not already connected
            if self.ctrl is None:
                if arduino.open():
                    if arduino.turn_off_channels():
                        logger.debug("attempting spectrometer connection")
                        if self.usb.open():
                            self.ctrl = arduino
                        else:
                            self.raise_error.emit("spec")
                    else:
                        self.raise_error.emit("ctrl")
                elif qspr.open():
                    logger.debug(f"RPI INFO: {qspr.get_info()}")
                    logger.debug("connect directly to spectrometer")
                    if self.usb.open():
                        self.ctrl = qspr
                    else:
                        self.raise_error.emit("spec")
                elif pico_p4spr.open():
                    logger.debug(f" Pico P4SPR Fw: {pico_p4spr.version}")
                    logger.debug("attempting spectrometer connection")
                    if self.usb.open():
                        self.ctrl = pico_p4spr
                    else:
                        self.raise_error.emit("spec")
                elif pico_ezspr.open():
                    logger.debug(f" Pico EZSPR Fw: {pico_ezspr.version}")
                    logger.debug("attempting spectrometer connection")
                    if self.usb.open():
                        self.ctrl = pico_ezspr
                        self.knx = pico_ezspr
                        if (
                            pico_ezspr.version in pico_ezspr.UPDATABLE_VERSIONS
                            and show_message(
                                "Would you like to update the firmware on your device?",
                                "Question",
                                yes_no=True,
                            )
                        ):
                            if getattr(sys, "frozen", False) and hasattr(
                                sys,
                                "_MEIPASS",
                            ):
                                firmware = Path(sys._MEIPASS) / "affinite_ezspr.uf2"  # noqa: SLF001
                            else:
                                firmware = Path("affinite_ezspr.uf2")
                            if firmware.exists and pico_ezspr.update_firmware(firmware):
                                pico_ezspr.set_pump_corrections(1, 1)
                                show_message("The firmware was successfully updated!")
                            else:
                                show_message(
                                    "The firmware could not be updated.",
                                    "Warning",
                                )
                    else:
                        self.raise_error.emit("spec")

            # Look for kinetic unit if not already connected
            if self.knx is None:
                if knx2.open():
                    logger.debug(f"RPI INFO: {knx2.get_info()}")
                    self.knx = knx2
                elif pico_knx2.open():
                    logger.debug(f" Pico KNX2 Fw: {pico_knx2.version}")
                    self.knx = pico_knx2

            if self.pump is None:
                try:
                    self.pump = PumpController.from_first_available()
                    self.pump.send_command(0x41, b"e15R")
                    self.main_window.sensorgram.ui.flow_rate_box.setEnabled(True)
                except FTDIError:
                    self.pump = None

            if self.knx is not None:
                self.main_window.sensorgram.ui.inject_box.setEnabled(True)

            self.connected.emit()
        except Exception as e:
            logger.exception(f"Error in connection thread: {e}")

    def get_current_device_config(self: Self) -> None:
        """Get configuration of connected devices."""
        # Reset to no devices
        self.device_config["ctrl"] = ""
        self.device_config["knx"] = ""
        # Get current device configuration
        if self.ctrl is not None:
            if self.ctrl.name == "p4spr":
                self.device_config["ctrl"] = "P4SPR"
                if self.knx is not None and self.knx.name == "EZSPR":
                    self.device_config["ctrl"] = "EZSPR"
            elif self.ctrl.name == "qspr":
                self.device_config["ctrl"] = "QSPR"
            elif self.ctrl.name in {"pico_p4spr", "pico_ezspr"}:
                self.device_config["ctrl"] = "PicoP4SPR"
        if self.knx is not None:
            if self.knx.name == "KNX2":
                self.device_config["knx"] = "KNX2"
            elif self.knx.name == "KNX":
                self.device_config["knx"] = "KNX"
            elif self.knx.name in {"pico_knx2", "pico_ezspr"}:
                self.device_config["knx"] = "PicoKNX2"

        mods = []
        if self.device_config["ctrl"]:
            mods.append("SPR")
        if self.device_config["knx"] or self.device_config["ctrl"] == "EZSPR":
            mods.append("Kinetics")
        if self.pump or self.device_config["ctrl"] == "EZSPR":
            mods.append("Pumps")
        dev_str = " + ".join(mods) or "No Devices"
        self.main_window.ui.device.setText(dev_str)
        if dev_str == "No Devices":
            self.main_window.ui.status.setText("No Connection")
        else:
            self.main_window.ui.status.setText("Connected")
        self.main_window.on_device_config(self.device_config)

    def open_device(self: Self) -> None:
        """Open connection to devices."""
        if self._con_tr.is_alive():
            self.main_window.ui.status.setText(
                "Connection Error: Check USB cables & drivers",
            )
            self._con_tr.join(0.5)
        self.get_current_device_config()
        if self.ctrl is None and self.knx is None:
            logger.debug("no device")
            self.stop()
            self.ctrl = None
            self.knx = None
        else:
            logger.debug("start")
            self.startup()
        self.main_window.sidebar.device_widget.setup(
            self.device_config["ctrl"],
            self.device_config["knx"],
            self.pump,
        )
        self.main_window.sidebar.kinetic_widget.setup(
            self.device_config["ctrl"],
            self.device_config["knx"],
        )
        self.main_window.sidebar.kinetic_widget.set_sync(prompt=False)

    @Slot()
    def prime(self: Self) -> None:
        """Start a priming sequence."""
        if self.pump and self.knx:
            priming_window = PrimingWindow(self.pump, self.knx, self)
            # priming_window.accepted.connect(self.quick_calibration)
            priming_window.show()

    @Slot()
    def handle_regen_button(self: Self) -> None:
        """Handle the regenerate button being pressed."""
        task = create_task(self.regenerate())
        self.kinetic_tasks.add(task)
        task.add_done_callback(self.kinetic_tasks.discard)

    async def regenerate(self: Self) -> None:
        """Do the regenerate sequence."""
        if self.pump and self.knx:
            try:
                contact_time = float(
                    self.main_window.advanced_menu.ui.contact_time.text(),
                )
                self.pump.send_command(0x41, b"T")
                cmd = (
                    "IS15A181490"
                    "OV4.167,1A0"
                    "IS15A181490"
                    f"OV{self.flow_rate:.3f},1A0R"
                ).encode()
                self.pump.send_command(0x41, cmd)
                self.main_window.sensorgram.start_progress_bar(
                    int(67_000 + 1125 * contact_time),
                )
                await asyncio.sleep(22)
                self.knx.knx_six(state=1, ch=3)
                await asyncio.sleep(contact_time)
                self.knx.knx_six(state=0, ch=3)
                self.pump.send_command(0x41, b"V83.333,1R")
                await asyncio.sleep(0.8)
                self.pump.send_command(0x41, b"V6000R")
            except FTDIError as e:
                logger.exception(f"Error communicating with pumps: {e}")
            except ValueError as e:
                logger.exception(f"Invalid contact time: {e}")

    @Slot()
    def handle_flush_button(self: Self) -> None:
        """Handle the flush button being pressed."""
        task = create_task(self.flush())
        self.kinetic_tasks.add(task)
        task.add_done_callback(self.kinetic_tasks.discard)

    async def flush(self: Self) -> None:
        """Do the flush sequence."""
        if self.pump:
            try:
                self.pump.send_command(0x41, b"T")
                cmd = (
                    "IS12A181490OS15A0IS12A181490" f"OV{self.flow_rate:.3f},1A0R"
                ).encode()
                self.pump.send_command(0x41, cmd)
                self.main_window.sensorgram.start_progress_bar(29_000)
                await asyncio.sleep(9)
                self.pump.send_command(0x41, b"V83.333,1R")
                await asyncio.sleep(0.8)
                self.pump.send_command(0x41, b"V9000R")
                await asyncio.sleep(4)
                self.pump.send_command(0x41, b"V83.333,1R")
                await asyncio.sleep(0.8)
                self.pump.send_command(0x41, b"V9000R")
            except FTDIError as e:
                logger.exception(f"Error communicating with pumps: {e}")

    @Slot()
    def handle_inject_button(self: Self) -> None:
        """Handle the inject button being pressed."""
        if self.main_window.sensorgram.ui.inject_button.text() == "Inject":
            task = create_task(self.inject())
            self.kinetic_tasks.add(task)
            task.add_done_callback(self.kinetic_tasks.discard)
        else:
            self.cancel_injection()

    async def inject(self: Self) -> None:
        """Start an injection."""
        if self.pump:
            try:
                self.pump.send_command(0x41, b"T")

                cmd = f"IS15A181490OV{self.flow_rate:.3f},1A0R"
                self.pump.send_command(0x41, cmd.encode())
                self.main_window.sensorgram.ui.flow_rate_now.setText(
                    f"{self.flow_rate * 60:.1f}",
                )

                self.main_window.sensorgram.ui.inject_box.setEnabled(False)
                await asyncio.sleep(50)
                self.main_window.sensorgram.ui.inject_box.setEnabled(True)
            except FTDIError as e:
                logger.exception(f"Error communicating with pump: {e}")

        try:
            injection_time = int(80 / self.flow_rate * 1000)
            self.main_window.sensorgram.start_progress_bar(injection_time)
            self.main_window.sensorgram.new_segment()
        except ZeroDivisionError:
            return

        if self.knx:
            self.knx.knx_six(state=1, ch=3)
            await asyncio.sleep(80 / self.flow_rate)
            self.knx.knx_six(state=0, ch=3)

    def cancel_injection(self: Self) -> None:
        """Cancel a currently ongoing injection."""
        self.main_window.sensorgram.cancel_progress_bar()
        for task in self.kinetic_tasks:
            task.cancel()
        if self.knx:
            self.knx.knx_six(state=0, ch=3)
        if self.pump:
            self.pump.send_command(0x41, b"T")

    @Slot()
    def change_flow_rate(self: Self) -> None:
        """Change flow rate based on user input."""
        text = self.main_window.sensorgram.ui.flow_rate.text()
        self.main_window.sensorgram.ui.flow_rate.clear()
        v = float(text) / 60
        self.flow_rate = abs(v)
        self.main_window.sensorgram.ui.flow_rate_now.setText(text)
        if self.pump:
            try:
                if self.flow_rate:
                    self.pump.send_command(0x41, f"V{self.flow_rate:.3f},1R".encode())
                    with suppress(IndexError):
                        if (
                            self.pump.send_command(0x31, b"Q")[0]
                            & self.pump.send_command(0x32, b"Q")[0]
                            & 0x20
                        ):
                            if v > 0:
                                self.pump.send_command(0x41, b"OA0R")
                            else:
                                self.pump.send_command(0x41, b"IA181490R")
                else:
                    self.pump.send_command(0x41, b"T")
                with suppress(ValueError, IndexError):
                    reply = self.pump.send_command(0x31, b"?37")
                    speed = "0" if reply[0] & 0x20 else f"{float(reply[1:]) * 60:.1f}"
                    self.main_window.sensorgram.ui.flow_rate_now.setText(speed)
            except FTDIError as e:
                logger.exception(f"Error communicating with pump: {e}")

    @Slot()
    def initialize_pumps(self: Self) -> None:
        """Initialize the pumps."""
        if self.pump:
            try:
                self.pump.send_command(0x41, b"zR")
                self.pump.send_command(0x41, b"e15R")
            except FTDIError as e:
                logger.exception(f"Error initializing pumps: {e}")

    def usb_ok(self: Self) -> bool:
        """Check if usb is connected."""
        return (
            self.ctrl is None
            or self.device_config["ctrl"]
            not in ["P4SPR", "PicoP4SPR", "EZSPR", "PicoEZSPR"]
            or self.usb.spec is not None
        )

    @Slot()
    def set_start(self: Self) -> None:
        """Set recording start time."""
        start_time = time.time()
        time_diff = start_time - self.exp_start
        self.exp_start = start_time
        for ch in CH_LIST:
            self.lambda_times[ch] -= time_diff
            self.buffered_times[ch] -= time_diff
        self.main_window.sensorgram.reload_segments(time_diff)

    def startup(self: Self) -> None:
        """Start device calibration, I think."""
        if self.ctrl is not None and self.device_config["ctrl"] in DEVICES:
            if DEV:
                for _ in range(10):
                    if not self.adv_connected:
                        time.sleep(0.2)
                try:
                    self.get_device_parameters()
                except Exception as e:
                    logger.exception(f"Error getting advanced parameters at start: {e}")
            self._c_stop.clear()
            logger.debug(f"start calibration {self.device_config['ctrl']}")
        if self.knx is not None:
            logger.debug(f"kinetic system: {self.device_config['knx']}")

    def calibrate(self: Self) -> None:
        """Calibrate the sensors."""
        self._b_no_read.set()
        time.sleep(1)
        while not self._c_kill.is_set():
            time.sleep(0.01)
            if not self._c_stop.is_set() and (self.ctrl is not None) and self.usb_ok():
                self.ignore_warnings = {ch: False for ch in CH_LIST}
                self.no_sig_count = {ch: 0 for ch in CH_LIST}
                if self.calibrated:
                    self.calibration_status.emit(True, "")  # noqa: FBT003
                    self._c_stop.set()
                    logger.debug("already calibrated")
                else:
                    logger.debug("Calibration started")
                    self.calibration_started.emit()
                    try:
                        logger.debug("Getting wavelength intensities")
                        # Read the wavelength data from the detector and get wave max
                        # and min indices
                        if self.device_config["ctrl"] in DEVICES:
                            serial_number = self.usb.serial_number
                            logger.debug(f"Spectrometer serial number: {serial_number}")
                            wave_data = self.usb.read_wavelength()
                            integration_step = INTEGRATION_STEP
                        else:
                            logger.debug(f"unrecognized controller: {self.ctrl.name}")
                            wave_data = []
                            self.error_handler("ctrl")
                        if not self._c_stop.is_set():
                            self.wave_min_index = wave_data.searchsorted(MIN_WAVELENGTH)
                            self.wave_max_index = wave_data.searchsorted(MAX_WAVELENGTH)
                            self.wave_data = wave_data[
                                self.wave_min_index : self.wave_max_index
                            ]
                            logger.debug(
                                f"wave min index : {self.wave_min_index}, "
                                f"wave max index = {self.wave_max_index}",
                            )

                            alpha = 2e3
                            n = len(self.wave_data) - 1
                            phi = np.pi / n * np.arange(1, n)
                            phi2 = phi**2
                            self.fourier_weights = phi / (1 + alpha * phi2 * (1 + phi2))

                        # Automatically calibrate polarizer servo alignment if option is
                        # enabled
                        if self.auto_polarize and not self._c_stop.is_set():
                            self.auto_polarize = False
                            self.auto_polarization()

                        # Start calibration in S position with all channels off
                        if not (self._c_stop.is_set() or (self.ctrl is None)):
                            self.ctrl.set_mode(mode="s")
                            time.sleep(0.5)
                            self.ctrl.turn_off_channels()
                            # Set the integration time to the minimum
                            if self.device_config["ctrl"] in DEVICES:
                                self.integration = deepcopy(MIN_INTEGRATION)
                                self.usb.set_integration(self.integration)
                            else:
                                logger.debug("controller does not match in config")
                                self._c_stop.set()
                            time.sleep(0.1)

                        # Set the integration time to compensate for the weakest channel
                        # in use
                        ch_list = CH_LIST
                        if self.single_mode:
                            ch_list = [self.single_ch]
                        elif self.device_config["ctrl"] in ["EZSPR", "PicoEZSPR"]:
                            ch_list = EZ_CH_LIST
                        max_int = deepcopy(MAX_INTEGRATION)
                        for ch in ch_list:
                            if self._c_stop.is_set():
                                break
                            if self.device_config["ctrl"] in DEVICES:
                                # Check the intensity is enough and raise integration
                                # time if needed
                                self.ctrl.set_intensity(ch=ch, raw_val=S_LED_INT)
                                time.sleep(LED_DELAY)
                                int_array = self.usb.read_intensity()
                                time.sleep(LED_DELAY)
                                current_count = int_array.max()
                                # If max intensity is not sufficient
                                while (
                                    current_count < S_COUNT_MAX
                                    and self.integration < max_int
                                ):
                                    self.integration += integration_step
                                    logger.debug(
                                        "increasing integration time - "
                                        f"{self.integration}",
                                    )
                                    # Change detector setting
                                    self.usb.set_integration(self.integration)
                                    time.sleep(0.02)
                                    int_array = self.usb.read_intensity()
                                    current_count = int_array.max()

                        # Check if low intensity is saturating and if so lower the the
                        # max integration allowed
                        for ch in ch_list:
                            if self._c_stop.is_set():
                                break
                            if self.device_config["ctrl"] in DEVICES:
                                self.ctrl.set_intensity(ch=ch, raw_val=S_LED_MIN)
                                time.sleep(LED_DELAY)
                                int_array = self.usb.read_intensity()
                                current_count = int_array.max()
                                logger.debug(
                                    f"saturation check: {current_count}, "
                                    f"limit: {S_COUNT_MAX}",
                                )
                                while (
                                    current_count > S_COUNT_MAX
                                    and self.integration > MIN_INTEGRATION
                                ):
                                    self.integration -= integration_step
                                    if self.integration < max_int:
                                        max_int = deepcopy(self.integration)
                                    logger.debug(
                                        "decreasing integration time - %i",
                                        f"{self.integration}",
                                    )
                                    # Change detector setting
                                    self.usb.set_integration(self.integration)
                                    time.sleep(0.02)
                                    int_array = self.usb.read_intensity()
                                    current_count = int_array.max()

                        logger.debug(f"final integration time: {self.integration}")
                        # Set the number of scans to average based on intensity and
                        # 225ms read time
                        self.num_scans = min(
                            int(MAX_READ_TIME / self.integration),
                            MAX_NUM_SCANS,
                        )
                        logger.debug(f"scans to average: {self.num_scans}")

                        # Calibrate LED intensity values in S
                        for ch in ch_list:
                            if self._c_stop.is_set():
                                break

                            logger.debug(f"Calibrating LED {ch}...")

                            # Start at maximum for the S-polarized light
                            intensity = deepcopy(P_LED_MAX)
                            self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                            time.sleep(LED_DELAY)
                            if self.device_config["ctrl"] in DEVICES:
                                calibration_max = self.usb.read_intensity().max()
                            else:
                                calibration_max = 0
                                self._c_stop.set()

                            logger.debug(
                                f"initial intensity: {intensity} "
                                f"= {calibration_max} counts",
                            )
                            # Quick adjust by 20
                            quick_adjustment = 20
                            while (
                                calibration_max > S_COUNT_MAX
                                and intensity > quick_adjustment
                                and not self._c_stop.is_set()
                            ):
                                intensity -= quick_adjustment
                                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                                time.sleep(LED_DELAY)
                                if self.device_config["ctrl"] in DEVICES:
                                    calibration_max = self.usb.read_intensity().max()
                            logger.debug(
                                f"coarse adjust: {intensity} = "
                                f"{calibration_max} counts",
                            )

                            # Med adjust by 5
                            medium_adjustment = 5
                            while (
                                calibration_max < S_COUNT_MAX
                                and intensity < P_LED_MAX
                                and not self._c_stop.is_set()
                            ):
                                intensity += medium_adjustment
                                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                                time.sleep(LED_DELAY)
                                if self.device_config["ctrl"] in DEVICES:
                                    calibration_max = self.usb.read_intensity().max()
                            logger.debug(
                                f"med adjust: {intensity} = {calibration_max} counts",
                            )

                            # Fine adjust by 1
                            fine_adjustment = 1
                            while (
                                calibration_max > S_COUNT_MAX
                                and intensity > fine_adjustment + 1
                            ):
                                intensity -= fine_adjustment
                                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                                time.sleep(LED_DELAY)
                                calibration_max = self.usb.read_intensity().max()
                            logger.debug(
                                f"fine adjust: {intensity} = {calibration_max} counts",
                            )

                            # append the value to the list of calibrated LEDs
                            self.ref_intensity[ch] = deepcopy(intensity)
                        # Review calibrated LED intensities
                        logger.debug(
                            f"Finished reference calibration: {self.ref_intensity}",
                        )

                        # Dark noise intensity when all LEDs off
                        self.ctrl.turn_off_channels()
                        time.sleep(LED_DELAY)
                        # No idea why 50
                        fifty = 50
                        if self.integration < fifty:
                            dark_scans = DARK_NOISE_SCANS
                        else:
                            dark_scans = int(DARK_NOISE_SCANS / 2)
                        if (
                            not self._c_stop.is_set()
                            and self.device_config["ctrl"] in DEVICES
                        ):
                            dark_noise_sum = np.zeros(
                                self.wave_max_index - self.wave_min_index,
                            )
                            for _scan in range(dark_scans):
                                dark_noise_single = self.usb.read_intensity()[
                                    self.wave_min_index : self.wave_max_index
                                ]
                                dark_noise_sum += dark_noise_single
                                self.dark_noise = dark_noise_sum / dark_scans
                            logger.debug("Finished dark noise scans")
                            logger.debug(
                                f"Maximum counts in dark noise: "
                                f"{max(self.dark_noise)}",
                            )
                        else:
                            self._c_stop.set()
                            break

                        # Reference Signal - S-position intensity reading on each
                        # channel
                        self.ctrl.set_mode(mode="s")
                        time.sleep(0.4)
                        for ch in ch_list:
                            if (
                                not self._c_stop.is_set()
                                and self.device_config["ctrl"] in DEVICES
                            ):
                                self.ctrl.set_intensity(
                                    ch=ch,
                                    raw_val=self.ref_intensity[ch],
                                )
                                time.sleep(LED_DELAY)
                                if self.integration < fifty:
                                    ref_scans = REF_SCANS
                                else:
                                    ref_scans = int(REF_SCANS / 2)
                                ref_data_sum = np.zeros_like(self.dark_noise)
                                for _scan in range(ref_scans):
                                    int_val = self.usb.read_intensity()[
                                        self.wave_min_index : self.wave_max_index
                                    ]
                                    ref_data_single = int_val - self.dark_noise
                                    ref_data_sum += ref_data_single
                                self.ref_sig[ch] = deepcopy(ref_data_sum / ref_scans)
                                logger.debug(
                                    f"Finished {ch} reference signal measurement",
                                )
                                logger.debug(
                                    f"Reference max counts: {max(self.ref_sig[ch])}",
                                )
                            else:
                                self._c_stop.set()
                                break

                        # At end of calibration sequence move to position p
                        self.ctrl.set_mode(mode="p")
                        time.sleep(0.4)

                        # Fine tune LED intensities after switch to P
                        if (
                            not self._c_stop.is_set()
                            and self.device_config["ctrl"] in DEVICES
                        ):
                            for ch in ch_list:
                                logger.debug(f"Finishing calibration LED {ch}...")
                                p_intensity = deepcopy(self.ref_intensity[ch])
                                self.ctrl.set_intensity(ch=ch, raw_val=p_intensity)
                                time.sleep(LED_DELAY)
                                calibration_max = self.usb.read_intensity().max()
                                initial_counts = deepcopy(calibration_max)
                                logger.debug(f"initial counts: {initial_counts}")
                                # Rough calibration, adjust by 20
                                while (
                                    calibration_max < initial_counts * P_MAX_INCREASE
                                    and calibration_max < S_COUNT_MAX
                                    and p_intensity < (P_LED_MAX - 20)
                                ):
                                    p_intensity += quick_adjustment
                                    self.ctrl.set_intensity(ch=ch, raw_val=p_intensity)
                                    time.sleep(LED_DELAY)
                                    calibration_max = self.usb.read_intensity().max()
                                logger.debug(
                                    f"coarse adjust: {p_intensity} = "
                                    f"{calibration_max} counts",
                                )

                                # Medium adjust by 5
                                while (
                                    calibration_max > initial_counts * P_MAX_INCREASE
                                    and p_intensity > medium_adjustment
                                ):
                                    p_intensity -= medium_adjustment
                                    self.ctrl.set_intensity(ch=ch, raw_val=p_intensity)
                                    time.sleep(LED_DELAY)
                                    calibration_max = self.usb.read_intensity().max()
                                logger.debug(
                                    f"medium adjust: {p_intensity} = "
                                    f"{calibration_max} counts",
                                )

                                # Fine adjust by 1
                                while (
                                    calibration_max < initial_counts * P_MAX_INCREASE
                                    and calibration_max < S_COUNT_MAX
                                    and p_intensity < P_LED_MAX
                                ):
                                    p_intensity += fine_adjustment
                                    self.ctrl.set_intensity(ch=ch, raw_val=p_intensity)
                                    time.sleep(LED_DELAY)
                                    calibration_max = self.usb.read_intensity().max()
                                logger.debug(
                                    f"fine adjust: {p_intensity} = "
                                    f"{calibration_max} counts",
                                )

                                # keep calibrated LED values
                                self.leds_calibrated[ch] = deepcopy(p_intensity)

                            # Review calibrated LED intensities
                            logger.debug(
                                f"Finished LED calibration: {self.leds_calibrated}",
                            )

                        else:
                            self._c_stop.set()
                            break

                        # Check that all channels pass calibration requirements
                        self.ch_error_list = []

                        for ch in CH_LIST:
                            if (
                                not self._c_stop.is_set()
                                and self.device_config["ctrl"] in DEVICES
                            ):
                                intensity = self.leds_calibrated[ch]
                                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                                time.sleep(LED_DELAY)
                                calibration_max = self.usb.read_intensity().max()
                                if calibration_max < P_COUNT_THRESHOLD:
                                    self.ch_error_list.append(ch)
                                    logger.debug(
                                        f"calibration failed on ch {ch}: "
                                        f"intensity {calibration_max} at {intensity}",
                                    )
                            else:
                                self._c_stop.set()
                                break

                        ch_str = ""
                        if len(self.ch_error_list) > 0:
                            for ch in self.ch_error_list:
                                if ch_str == "":
                                    ch_str += f"{ch} "
                                else:
                                    ch_str += f", {ch} "
                            calibration_success = False
                        else:
                            calibration_success = True
                        # Update calibration status
                        if not self._c_stop.is_set():
                            self.calibration_status.emit(calibration_success, ch_str)

                        self._c_stop.set()

                    except Exception as e:
                        logger.exception(
                            f"Device error during calibration: {e}, type {type(e)}",
                        )
                        self._c_stop.set()
                        self.main_window.sidebar.device_widget.allow_commands(
                            True,  # noqa: FBT003
                        )
                        if type(e) == serial.SerialException:
                            self.raise_error.emit("ctrl")
                        else:
                            pass
            else:
                time.sleep(0.2)

    def quick_calibration(self: Self) -> None:
        """Calibrate quickly."""
        if self._c_stop.is_set():
            self._b_no_read.set()
            time.sleep(1)
            self.calibrated = False
            self.main_window.ui.adv_btn.setEnabled(False)
            self._c_stop.clear()

    def full_recalibration(self: Self) -> None:
        """Recalibrate."""
        if self._c_stop.is_set():
            self._b_no_read.set()
            time.sleep(1)
            self.calibrated = False
            self.main_window.ui.adv_btn.setEnabled(False)
            self.auto_polarize = True
            self._c_stop.clear()

    def start_new_ref(self: Self, *, new_settings: bool = False) -> None:
        """Create a new reference spectrum."""
        try:
            if self.device_config["ctrl"] in DEVICES and self._c_stop.is_set():
                logger.debug("starting new reference")
                self._b_no_read.set()
                time.sleep(1)
                self.main_window.ui.status.setText("New reference ...")
                self.main_window.spectroscopy.ui.controls.setEnabled(False)
                self.main_window.sidebar.device_widget.allow_commands(state=False)
                if new_settings:
                    self.usb.set_integration(self.integration)
                self._new_sig_tr = threading.Thread(target=self.new_ref_thread)
                self._new_sig_tr.start()
                show_message(msg="New reference started", auto_close_time=5)
        except Exception as e:
            logger.exception(f"Error starting new reference thread: {e}")

    def new_ref_done(self: Self) -> None:
        """Finilize new reference spectrum."""
        try:
            logger.debug("done new reference")
            if self._new_sig_tr.is_alive():
                self._new_sig_tr.join(0.1)
            self.main_window.ui.status.setText("Connected")
            self.main_window.spectroscopy.ui.controls.setEnabled(True)
            self.main_window.sidebar.device_widget.allow_commands(state=True)
            self._b_no_read.clear()
            show_message(msg="New reference completed", auto_close_time=5)
        except Exception as e:
            logger.exception(f"Error ending new reference thread: {e}")

    def new_ref_thread(self: Self) -> None:
        """Make new reference."""
        if self.ctrl is not None:
            try:
                logger.debug("new reference thread")
                # Reference Signal - S-position intensity reading on each channel
                self.ctrl.set_mode(mode="s")
                self.ctrl.turn_off_channels()
                time.sleep(0.4)
                for ch in CH_LIST:
                    self.ctrl.set_intensity(ch=ch, raw_val=self.ref_intensity[ch])
                    time.sleep(LED_DELAY)
                    ref_data_sum = np.zeros_like(self.dark_noise)
                    ref_scans = REF_SCANS
                    # No idea why 75
                    if self.integration > 75:  # noqa: PLR2004
                        ref_scans = int(REF_SCANS / 2)
                    for _scan in range(ref_scans):
                        int_val = self.usb.read_intensity()
                        ref_data_single = (
                            int_val[self.wave_min_index : self.wave_max_index]
                            - self.dark_noise
                        )
                        ref_data_sum += ref_data_single
                    self.ref_sig[ch] = deepcopy(ref_data_sum / REF_SCANS)
                    self.ctrl.set_intensity(ch=ch, raw_val=self.leds_calibrated[ch])
                    self.ctrl.turn_off_channels()
                self.ctrl.set_mode(mode="p")
                self.new_ref_done_sig.emit()
                time.sleep(0.1)
                logger.debug("new reference signal")
            except Exception as e:
                logger.exception(f"Error during new reference: {e}")

    def single_led(self: Self, led_setting: str) -> None:
        """Trun on only one LED."""
        if led_setting == "auto":
            self.single_mode = False
            self.single_ch = "x"
        elif led_setting in ["a", "b", "c", "d"]:
            self.single_mode = True
            self.single_ch = led_setting
        else:
            self.single_mode = True
            self.single_ch = "x"

    def set_polarizer(self: Self, pos: str) -> None:
        """Move polariizer."""
        if self.ctrl is not None:
            self._b_no_read.set()
            time.sleep(0.5)
            if "s" in pos or "S" in pos:
                for ch in CH_LIST:
                    self.ctrl.set_intensity(ch=ch, raw_val=self.ref_intensity[ch])
                logger.debug(f"set to S intensities: {self.ref_intensity}")
                set_pos = "s"
            else:
                for ch in CH_LIST:
                    self.ctrl.set_intensity(ch=ch, raw_val=self.leds_calibrated[ch])
                logger.debug(f"set to P intensities: {self.leds_calibrated}")
                set_pos = "p"
            self.ctrl.set_mode(mode=set_pos)
            logger.debug(f"set polarizer: {set_pos}")
            time.sleep(0.1)
            self._b_no_read.clear()

    def _on_calibration_started(self: Self) -> None:
        self.main_window.ui.status.setText("Calibrating")
        self.main_window.sensorgram.enable_controls(data_ready=False)
        self.main_window.spectroscopy.enable_controls(False)  # noqa: FBT003
        self.main_window.sidebar.device_widget.allow_commands(False)  # noqa: FBT003
        show_message(
            msg="Calibration Started:\nThis process may take a few minutes to complete",
            auto_close_time=10,
        )

    def _on_calibration_status(
        self: Self,
        state: bool,  # noqa: FBT001
        ch_error_str: str,
    ) -> None:
        self.calibrated = state
        if self.adv_connected and DEV:
            self.main_window.ui.adv_btn.setEnabled(True)
        current_text = self.main_window.ui.status.text()
        if current_text.endswith("Calibrating"):
            self.main_window.ui.status.setText("Connected")
        if ch_error_str != "":
            if (
                self.device_config["ctrl"] in ["EZSPR", "PicoEZSPR"]
                and "a" not in ch_error_str
                and "b" not in ch_error_str
            ):
                pass
            elif DEV:
                show_message(
                    msg_type="warning",
                    msg=f"Calibration Failed: {ch_error_str}",
                    auto_close_time=5,
                )
            else:
                show_message(
                    msg_type="warning",
                    msg=f"Poor Signal on Channels: {ch_error_str}\n"
                    "If sensor chip is prepared for channel(s) listed\n"
                    "above, please check device & optical light path",
                )

        self.main_window.sensorgram.disable_channels(self.ch_error_list)

        if self.new_default_values:
            self.save_default_values()

        if state:
            logger.debug("passed calibration")
        else:
            logger.debug("manually passing calibration")
            self.calibrated = True
        self.main_window.spectroscopy.enable_controls(True)  # noqa: FBT003
        self.main_window.sidebar.device_widget.allow_commands(True)  # noqa: FBT003
        if not self._b_kill.is_set() and state:
            self._b_no_read.clear()
            if self._b_stop.is_set():
                self._b_stop.clear()

    def error_handler(self: Self, error_type: object) -> None:
        """Handle error."""
        logger.debug(f"Error handler:{error_type}")
        if error_type == "ctrl":
            self._on_ctrl_error()
        if error_type == "spec":
            self._on_spec_error()

    def _on_ctrl_error(self: Self) -> None:
        if self.ctrl is not None:
            self.disconnect_dev(knx=False)
            if not self.closing:
                show_message(
                    msg="Error: Device Disconnected!\nCheck connection and USB cable",
                    msg_type="Warning",
                )
                self.main_window.ui.status.setText("Device Connection Error")

    def _on_spec_error(self: Self) -> None:
        if self.usb.spec is not None:
            self.disconnect_dev(knx=False)
            if not self.closing:
                show_message(
                    msg="Error: Device Disconnected!\nCheck connection and USB cable",
                    msg_type="Warning",
                )
                self.main_window.ui.status.setText("Device Connection Error")

    @Slot(dict, list, str)
    def send_to_analysis(
        self: Self,
        data_dict: dict[str, np.ndarray[int, np.dtype[np.float64]]],
        seg_list: list[Segment],
        unit: str,
    ) -> None:
        """Send data from processing tab to analysis tab."""
        self.main_window.set_main_widget("data_analysis")
        self.main_window.data_analysis.load_data(data_dict, seg_list, unit)

    @Slot()
    def recording_on(self: Self) -> bool | None:
        """Start recording data."""
        if not self.recording:
            try:
                self.rec_dir = ""
                self.rec_dir = QFileDialog.getExistingDirectory(
                    self,
                    "Choose directory for recorded data files",
                    "",
                )
                time_data = dt.datetime.now(TIME_ZONE)
                logger.debug(f"recording path: {self.rec_dir}")
                if self.rec_dir in {None, ""}:
                    logger.debug(
                        f"Recording directory could not be opened: {self.rec_dir}",
                    )
                else:
                    self.recording = True
                    self.rec_dir = (
                        f"{self.rec_dir}/"
                        f"Recording {time_data.hour:02d}{time_data.minute:02d}"
                    )
                    if self.device_config["ctrl"] != "":
                        self.main_window.sensorgram.start_recording(self.rec_dir)
                    self.set_start()
                    self.clear_sensor_reading_buffers()
                    self.rec_timer.start(1000 * RECORDING_INTERVAL)
            except Exception as e:
                logger.exception(f"Error while starting recording: {e}")
                return False
        else:
            self.recording = False
            self.rec_timer.stop()
        self.main_window.set_recording(self.recording)
        return None

    def save_rec_data(self: Self) -> None:
        """Save recorded data."""
        if self.device_config["ctrl"] != "":
            logger.debug("saving SPR data")
            self.main_window.sensorgram.save_data(self.rec_dir)
            if self.device_config["ctrl"] == "PicoP4SPR":
                self.save_temp_log(self.rec_dir)
        if self.device_config["knx"] != "" or self.device_config["ctrl"] in [
            "EZSPR",
            "PicoEZSPR",
        ]:
            logger.debug("saving kinetic log")
            self.save_kinetic_log(self.rec_dir)
        self.rec_timer.start()

    def manual_export_raw_data(self: Self) -> None:
        """Export raw data."""
        try:
            save_dir = QFileDialog.getExistingDirectory(
                self,
                "Choose directory for recorded data files",
                "",
            )
            if save_dir in [None, ""]:
                logger.debug(f"Directory could not be opened: {save_dir}")
            else:
                self.main_window.sensorgram.save_data(f"{save_dir}/Export")
                show_message(
                    msg="Files exported successfully!",
                    msg_type="Information",
                    auto_close_time=3,
                )
        except Exception as e:
            logger.exception(f"error during manual export {e}")

    def _grab_data(self: Self) -> None:
        # transmission segment of interest
        # transmission segment wavelengths

        first_run = True

        while not self._b_kill.is_set():
            ch = CH_LIST[0]
            time.sleep(0.01)
            try:
                if self._b_stop.is_set() or self.device_config["ctrl"] not in DEVICES:
                    time.sleep(0.2)
                    continue

                if first_run:
                    self.exp_start = time.time()
                    first_run = False

                if not (
                    len(self.buffered_times["a"])
                    == len(self.buffered_times["b"])
                    == len(self.buffered_times["c"])
                    == len(self.buffered_times["d"])
                ):
                    self.pad_values()

                ch_list = CH_LIST
                if self.single_mode:
                    ch_list = [self.single_ch]
                elif self.device_config["ctrl"] in ["EZSPR", "PicoEZSPR"]:
                    ch_list = EZ_CH_LIST
                for ch in CH_LIST:
                    fit_lambda = np.nan
                    if self._b_stop.is_set():
                        break
                    if (
                        ch in ch_list
                        and not self._b_no_read.is_set()
                        and self.calibrated
                        and self.ctrl is not None
                    ):
                        int_data_sum = np.zeros_like(self.wave_data, "u4")
                        self.ctrl.turn_on_channel(ch=ch)
                        if self.led_delay > 0:
                            time.sleep(self.led_delay)

                        offset = self.wave_min_index * 2
                        num = self.wave_max_index - self.wave_min_index

                        # Sum of total delta times.
                        sDT = 0.0

                        for _scan in range(self.num_scans):
                            t0 = time.time()
                            # read_intensity() in USB4000.py has been modified.
                            pixel_data = self.usb.read_intensity(data_type=np.uint16)
                            dt = time.time() - t0

                            # Adding the time differences.
                            sDT += dt

                            # The pixel data is already a uint16_t numpy array..
                            # So framebuffer(..) is not required.
                            int_data_sum += pixel_data[offset : offset + num]

                        # Showing an auto-closing message box with average frame rate achieved.
                        show_message(
                            msg_type="Information",
                            msg=f"Average frame rate for {self.num_scans} scans: {float(self.num_scans)/sDT}",
                            auto_close_time=2,
                        )

                        if int_data_sum is not None:
                            self.int_data[ch] = (
                                int_data_sum / self.num_scans
                            ) - self.dark_noise
                            if self.ref_sig[ch] is not None:
                                # Get percentage transmission p intensity
                                # over s reference
                                try:
                                    self.trans_data[ch] = (
                                        self.int_data[ch] / self.ref_sig[ch] * 100
                                    )
                                except Exception as e:
                                    logger.exception(f"Failed to get trans data: {e}")
                        if self.device_config["ctrl"] in DEVICES:
                            self.ctrl.turn_off_channels()

                        if not (self._b_stop.is_set() or self.trans_data[ch] is None):
                            window = 165
                            spectrum = self.trans_data[ch]

                            fourier_coeff = np.zeros_like(spectrum)
                            fourier_coeff[0] = 2 * (spectrum[-1] - spectrum[0])
                            fourier_coeff[1:-1] = self.fourier_weights * dst(
                                spectrum[1:-1]
                                - np.linspace(
                                    spectrum[0],
                                    spectrum[-1],
                                    len(spectrum),
                                )[1:-1],
                                1,
                            )

                            derivative = idct(fourier_coeff, 1)

                            zero = derivative.searchsorted(0)
                            start = max(zero - window, 0)
                            end = min(zero + window, len(spectrum) - 1)
                            line = linregress(
                                self.wave_data[start:end],
                                derivative[start:end],
                            )

                            fit_lambda = -line.intercept / line.slope
                    else:
                        fit_lambda = np.nan
                        time.sleep(0.1)

                    # update lambda values
                    self.lambda_values[ch] = np.append(
                        self.lambda_values[ch],
                        fit_lambda,
                    )
                    self.lambda_times[ch] = np.append(
                        self.lambda_times[ch],
                        round(time.time() - self.exp_start, 3),
                    )

                    if ch in ch_list:
                        if len(self.lambda_values[ch]) > self.filt_buffer_index:
                            if np.isnan(self.lambda_values[ch][self.filt_buffer_index]):
                                filtered_value = np.nan
                            elif len(self.lambda_values[ch]) > self.med_filt_win:
                                unfiltered = self.lambda_values[ch][
                                    self.filt_buffer_index
                                    - self.med_filt_win : self.filt_buffer_index
                                ]
                                filtered_value = np.nanmean(unfiltered)
                            else:
                                unfiltered = self.lambda_values[ch]
                                if (len(unfiltered) % 2) == 0:
                                    unfiltered = unfiltered[1:]
                                filtered_value = np.nanmean(unfiltered)
                        else:
                            filtered_value = fit_lambda

                        self.filtered_lambda[ch] = np.append(
                            self.filtered_lambda[ch],
                            filtered_value,
                        )
                        self.buffered_lambda[ch] = np.append(
                            self.buffered_lambda[ch],
                            self.lambda_values[ch][self.filt_buffer_index],
                        )

                    else:
                        self.filtered_lambda[ch] = np.append(
                            self.filtered_lambda[ch],
                            np.nan,
                        )
                        self.buffered_lambda[ch] = np.append(
                            self.buffered_lambda[ch],
                            np.nan,
                        )

                    self.buffered_times[ch] = np.append(
                        self.buffered_times[ch],
                        self.lambda_times[ch][self.filt_buffer_index],
                    )

                    if ch == CH_LIST[-1]:
                        self.filt_buffer_index += 1

                if not self._b_stop.is_set():
                    self.update_live_signal.emit(self.sensorgram_data())
                    self.update_spec_signal.emit(self.spectroscopy_data())

                if self.device_config["ctrl"] == "PicoP4SPR" and isinstance(
                    self.ctrl,
                    PicoP4SPR,
                ):
                    self.temp_sig.emit(self.ctrl.get_temp())

            except Exception as e:
                logger.exception(
                    f"Error while grabbing data:{type(e)}:{e}:channel {ch}",
                )
                self.pad_values()
                self._b_stop.set()
                self.main_window.ui.status.setText("Error while reading SPR data")
                if e is IndexError:
                    show_message(
                        msg_type="Warning",
                        msg="Data Error: the program has encountered an error, "
                        "stopped data acquisition",
                    )
                else:
                    self.raise_error.emit("ctrl")

    @staticmethod
    def median_window(win_size: int) -> int:
        """Make an odd integer."""
        if (win_size % 2) == 0:
            win_size += 1
        return win_size

    def update_filtered_lambda(self: Self) -> None:
        """Filter data."""
        try:
            new_filtered_lambda = {ch: np.array([]) for ch in CH_LIST}
            for ch in CH_LIST:
                if (
                    len(self.lambda_values[ch]) > 0
                    and len(self.lambda_times[ch]) > 0
                    and len(self.buffered_times[ch]) > 0
                ):
                    first_filt_index = self.med_filt_win
                    last_filt_index = len(self.lambda_values[ch]) - 1
                    for i in range(first_filt_index):
                        filt_val = np.nanmean(self.lambda_values[ch][0:i])
                        new_filtered_lambda[ch] = np.append(
                            new_filtered_lambda[ch],
                            filt_val,
                        )
                    for i in range(first_filt_index, last_filt_index):
                        filt_val = np.nanmean(
                            self.lambda_values[ch][(i - self.med_filt_win) : i],
                        )
                        new_filtered_lambda[ch] = np.append(
                            new_filtered_lambda[ch],
                            filt_val,
                        )
                    for i in range(last_filt_index, len(self.lambda_values[ch])):
                        filt_val = np.nanmean(
                            self.lambda_values[ch][(i - self.med_filt_win) : i],
                        )
                        new_filtered_lambda[ch] = np.append(
                            new_filtered_lambda[ch],
                            filt_val,
                        )
                    offset = 0
                    while self.lambda_times[ch][offset] != self.buffered_times[ch][0]:
                        offset += 1
                    self.filtered_lambda[ch] = deepcopy(
                        new_filtered_lambda[ch][offset:],
                    )
        except Exception as e:
            logger.exception(f"error updating the filter win size: {e}")
            show_message("Filter window could not be updated", msg_type="Warning")

    def pause(self: Self) -> None:
        """Pause sensor."""
        self._b_stop.set()
        self._s_stop.set()

    def resume(self: Self) -> None:
        """Resume sensor."""
        self._b_stop.clear()
        self._s_stop.clear()

    def pad_values(self: Self) -> None:
        """Pad Values."""
        try:
            max_raw_len = 0
            max_filt_len = 0
            for ch in CH_LIST:
                max_raw_len = max(len(self.lambda_times[ch]), max_raw_len)
                max_filt_len = max(len(self.buffered_times[ch]), max_filt_len)
            for ch in CH_LIST:
                if len(self.lambda_times[ch]) < max_raw_len:
                    self.lambda_values[ch] = np.append(self.lambda_values[ch], np.nan)
                    self.lambda_times[ch] = np.append(
                        self.lambda_times[ch],
                        round(time.time() - self.exp_start, 3),
                    )
                if len(self.buffered_times[ch]) < max_filt_len:
                    self.filtered_lambda[ch] = np.append(
                        self.filtered_lambda[ch],
                        np.nan,
                    )
                    self.buffered_lambda[ch] = np.append(
                        self.buffered_lambda[ch],
                        np.nan,
                    )
                    self.buffered_times[ch] = np.append(self.buffered_times[ch], np.nan)
            self.filt_buffer_index += 1
        except Exception as e:
            logger.exception(f"Error while padding missing values: {e}")

    def sensorgram_data(self: Self) -> object:
        """Return sensorgram data."""
        sens_data = {
            "lambda_values": self.lambda_values,
            "lambda_times": self.lambda_times,
            "buffered_lambda_values": self.buffered_lambda,
            "filtered_lambda_values": self.filtered_lambda,
            "buffered_lambda_times": self.buffered_times,
            "filt": self.filt_on,
            "start": self.exp_start,
            "rec": self.recording,
        }
        return deepcopy(sens_data)

    def transfer_sens_data(self: Self) -> None:
        """Transfer sensorgram data."""
        raw_data = self.sensorgram_data()
        seg_table = self.main_window.sensorgram.saved_segments
        self.main_window.data_processing.update_sensorgram_data(raw_data, seg_table)

    def spectroscopy_data(self: Self) -> dict[str, object]:
        """Retrun spectroscopy data."""
        return {
            "wave_data": self.wave_data,
            "int_data": self.int_data,
            "trans_data": self.trans_data,
        }

    def auto_polarization(self: Self) -> None:
        """Find polarizer positions."""
        try:
            if self.device_config["ctrl"] in DEVICES and self.ctrl is not None:
                self.ctrl.set_intensity("a", 255)
                self.usb.set_integration(max(MIN_INTEGRATION, self.usb.min_integration))
                min_angle = 10
                max_angle = 170
                half_range = (max_angle - min_angle) // 2
                angle_step = 5
                steps = half_range // angle_step
                max_intensities = np.zeros(2 * steps + 1)
                self.ctrl.servo_set(half_range + min_angle, max_angle)
                self.ctrl.set_mode("p")
                self.ctrl.set_mode("s")
                max_intensities[steps] = self.usb.read_intensity().max()
                for i in range(steps):
                    x = min_angle + angle_step * i
                    self.ctrl.servo_set(s=x, p=x + half_range + angle_step)
                    self.ctrl.set_mode("s")
                    max_intensities[i] = self.usb.read_intensity().max()
                    self.ctrl.set_mode("p")
                    max_intensities[i + steps + 1] = self.usb.read_intensity().max()
                peaks = find_peaks(max_intensities)[0]
                prominences = peak_prominences(max_intensities, peaks)
                # Index of two most prominent peaks
                i = prominences[0].argsort()[-2:]
                # Edges of peaks at 5% from max, essentially full width 95% max
                # This is to find the middle of the range the P4Pro let light through
                edges = peak_widths(max_intensities, peaks, 0.05, prominences)[2:4]
                edges = np.array(edges)[:, i]
                # Midpoint of peaks by averaging and converting from indexes to angles
                # S is most prominent peak, P is second most prominent
                p_pos, s_pos = (min_angle + angle_step * edges.mean(0)).astype(int)
                self.ctrl.servo_set(s_pos, p_pos)
                logger.debug(f"final positions: s = {s_pos}, p = {p_pos}")
                self.new_default_values = True
        except Exception as e:
            logger.exception(f"Error aligning polarizer servo: {e}")

    def stop_pump(self: Self, stop_ch: str) -> None:
        """Stop a pump."""
        if self.knx is not None:
            try:
                log1 = False
                log2 = True
                self._s_stop.set()
                if stop_ch == "CH1":
                    log1 = True
                    if self.synced:
                        log2 = True
                        self.knx.knx_stop(3)
                        self.pump_states["CH2"] = "Off"
                        if self.knx.version == "1.1":
                            self.knx.knx_led("x", 3)
                    else:
                        self.knx.knx_stop(1)
                        if self.knx.version == "1.1":
                            self.knx.knx_led("x", 1)
                elif stop_ch == "CH2":
                    log2 = True
                    self.knx.knx_stop(2)
                    if self.knx.version == "1.1":
                        self.knx.knx_led("x", 2)
                self.pump_states[stop_ch] = "Off"
                logger.debug("pump stopped")
                log_time = f"{(time.time() - self.exp_start):.2f}"
                time_now = dt.datetime.now(TIME_ZONE)
                log_timestamp = (
                    f"{time_now.hour:02d}:{time_now.minute:02d}:{time_now.second:02d}"
                )
                if log1:
                    self.log_ch1["timestamps"].append(log_timestamp)
                    self.log_ch1["times"].append(log_time)
                    self.log_ch1["events"].append("CH 1 Stop")
                    self.log_ch1["flow"].append("-")
                    self.log_ch1["temp"].append("-")
                    self.log_ch1["dev"].append("-")
                if log2:
                    self.log_ch2["timestamps"].append(log_timestamp)
                    self.log_ch2["times"].append(log_time)
                    self.log_ch2["events"].append("CH 2 Stop")
                    self.log_ch2["flow"].append("-")
                    self.log_ch2["temp"].append("-")
                    self.log_ch2["dev"].append("-")
                self._s_stop.clear()
                self.update_pump_display.emit(self.pump_states, self.synced)
            except Exception as e:
                logger.exception(f"Error stopping pump: {e}")

    def run_pump(self: Self, run_ch: str, run_rate: int) -> None:
        """Run a pump."""
        if self.knx is not None:
            try:
                log1 = False
                log2 = False
                self._s_stop.set()
                state = "Running" if run_rate < FLUSH_RATE else "Flushing"
                if run_ch == "CH1":
                    log1 = True
                    if self.synced:
                        log2 = True
                        self.knx.knx_start(run_rate, 3)
                        self.pump_states["CH2"] = deepcopy(state)
                        if self.knx.version == "1.1":
                            self.knx.knx_led("g", 3)
                    else:
                        self.knx.knx_start(run_rate, 1)
                        if self.knx.version == "1.1":
                            self.knx.knx_led("g", 1)
                elif run_ch == "CH2":
                    log2 = True
                    self.knx.knx_start(run_rate, 2)
                    if self.knx.version == "1.1":
                        self.knx.knx_led("g", 2)
                self.pump_states[run_ch] = state
                log_time = f"{(time.time() - self.exp_start):.2f}"
                time_now = dt.datetime.now(TIME_ZONE)
                log_timestamp = (
                    f"{time_now.hour:02d}:{time_now.minute:02d}:{time_now.second:02d}"
                )
                if log1:
                    self.log_ch1["timestamps"].append(log_timestamp)
                    self.log_ch1["times"].append(log_time)
                    self.log_ch1["events"].append(f"CH 1 {state} ({run_rate})")
                    self.log_ch1["flow"].append("-")
                    self.log_ch1["temp"].append("-")
                    self.log_ch1["dev"].append("-")
                if log2:
                    self.log_ch2["timestamps"].append(log_timestamp)
                    self.log_ch2["times"].append(log_time)
                    self.log_ch2["events"].append(f"CH 2 {state} ({run_rate})")
                    self.log_ch2["flow"].append("-")
                    self.log_ch2["temp"].append("-")
                    self.log_ch2["dev"].append("-")
                self._s_stop.clear()
                self.update_pump_display.emit(self.pump_states, self.synced)
            except Exception as e:
                logger.exception(f"Error running pump: {e}")

    def three_way(self: Self, ch: str, state: object) -> None:
        """Switch a three-way valve."""
        if self.knx is not None:
            try:
                self._s_stop.set()
                if ch == "CH1":
                    if self.synced:
                        self.knx.knx_three(state, 3)
                    else:
                        self.knx.knx_three(state, 1)
                elif ch == "CH2":
                    self.knx.knx_three(state, 2)
                self._s_stop.clear()
            except Exception as e:
                logger.exception(f"Error setting 3-way valve: {e}")

    def six_port(self: Self, ch: str, state: object) -> None:
        """Change a six port valve."""
        if self.knx is not None:
            try:
                self._s_stop.set()
                if ch == "CH1":
                    if self.synced:
                        self.knx.knx_six(state, 3)
                    else:
                        self.knx.knx_six(state, 1)
                elif ch == "CH2":
                    self.knx.knx_six(state, 2)
                self._s_stop.clear()
            except Exception as e:
                logger.exception(f"Error setting 6-port valve: {e}")

    @Slot(str, int)
    def speed_change_handler(self: Self, ch: str, rate: int) -> None:
        """Change a pump speed."""
        if self.pump_states[ch] == "Running":
            self.run_pump(ch, rate)
            if not self.pump:
                self.flow_rate = rate / 60
                self.main_window.sensorgram.ui.flow_rate_now.setText(str(rate))

    @Slot(str, int)
    def run_button_handler(self: Self, ch: str, rate: int) -> None:
        """Run a pump."""
        if self.pump_states[ch] == "Off":
            self.run_pump(ch, rate)
        elif self.pump_states[ch] == "Running":
            self.stop_pump(ch)

    @Slot(str)
    def flush_button_handler(self: Self, ch: str) -> None:
        """Flush a tube."""
        if self.pump_states[ch] == "Off":
            self.run_pump(ch, FLUSH_RATE)
        elif self.pump_states[ch] == "Flushing":
            self.stop_pump(ch)

    def valve_state_check(self: Self, curr_status: dict[str, float], ch: int) -> None:
        """Check valve state."""
        if not self.update_timer.isActive():
            ch_name = "CH1" if ch == 1 else "CH2"
            if (curr_status["6P"] == 1) and (curr_status["3W"] == 1):
                fw_state = "Inject"
            elif (curr_status["6P"] == 0) and (curr_status["3W"] == 1):
                fw_state = "Load"
            elif (curr_status["6P"] == 1) and (curr_status["3W"] == 0):
                fw_state = "Dispose"
            else:
                fw_state = "Waste"
            if self.valve_states[ch_name] != fw_state:
                self.valve_states[ch_name] = fw_state
                logger.debug(f"correcting valve state error on ch {ch}")
                self.update_valve_display.emit(self.valve_states, self.synced)

    @Slot(str)
    def three_way_handler(self: Self, ch: str) -> None:
        """Switch three wayy valve."""
        self.update_timer.start(5000)
        if self.valve_states[ch] == "Waste":
            self.three_way(ch, 1)
            self.valve_states[ch] = "Load"
        elif self.valve_states[ch] == "Dispose":
            self.three_way(ch, 1)
            self.valve_states[ch] = "Inject"
        elif self.valve_states[ch] == "Inject":
            self.three_way(ch, 0)
            self.valve_states[ch] = "Dispose"
        else:
            self.three_way(ch, 0)
            self.valve_states[ch] = "Waste"
        if self.synced:
            self.valve_states["CH2"] = deepcopy(self.valve_states["CH1"])
        self.update_valve_display.emit(self.valve_states, self.synced)

    @Slot(str)
    def six_port_handler(self: Self, ch: str) -> None:
        """Switch a six port valve."""
        self.update_timer.start(5000)
        inject_time: int | str = 0
        timeout_mins = 0
        if self.valve_states[ch] in ["Load", "Waste"]:
            self.six_port(ch, 1)
            if self.valve_states[ch] == "Load":
                self.valve_states[ch] = "Inject"
            elif self.valve_states[ch] == "Waste":
                self.valve_states[ch] = "Dispose"
            inject_time = f"{(time.time() - self.exp_start):.2f}"
            time_now = dt.datetime.now(TIME_ZONE)
            inject_timestamp = (
                f"{time_now.hour:02d}:{time_now.minute:02d}:{time_now.second:02d}"
            )
            if ch == "CH1":
                self.log_ch1["timestamps"].append(inject_timestamp)
                self.log_ch1["times"].append(inject_time)
                self.log_ch1["events"].append("Inject sample")
                self.log_ch1["flow"].append("-")
                self.log_ch1["temp"].append("-")
                self.log_ch1["dev"].append("-")
                self.main_window.sidebar.kinetic_widget.ui.inject_time_ch1.setText(
                    f"{inject_time}",
                )
                timeout_mins = (
                    int(
                        100
                        / float(
                            self.main_window.sidebar.kinetic_widget.ui.run_rate_ch1.currentText(),
                        ),
                    )
                    + 2
                )
                self.timer1.start(int(1000 * 60 * timeout_mins))
            if (ch == "CH2") or self.synced:
                self.log_ch2["timestamps"].append(inject_timestamp)
                self.log_ch2["times"].append(inject_time)
                self.log_ch2["events"].append("Inject sample")
                self.log_ch2["flow"].append("-")
                self.log_ch2["temp"].append("-")
                self.log_ch2["dev"].append("-")
                self.main_window.sidebar.kinetic_widget.ui.inject_time_ch2.setText(
                    f"{inject_time}",
                )
                timeout_mins = (
                    int(
                        100
                        / float(
                            self.main_window.sidebar.kinetic_widget.ui.run_rate_ch2.currentText(),
                        ),
                    )
                    + 2
                )
                if self.synced:
                    self.valve_states["CH2"] = deepcopy(self.valve_states["CH1"])
                else:
                    self.timer2.start(int(1000 * 60 * timeout_mins))
                self.main_window.sidebar.kinetic_widget.ui.inject_time_ch2.setText(
                    f"{inject_time}",
                )
            logger.debug(f"starting timer on {ch} for {timeout_mins} min")
        else:
            if self.valve_states[ch] == "Inject":
                self.valve_states[ch] = "Load"
            elif self.valve_states[ch] == "Dispose":
                self.valve_states[ch] = "Waste"
            self.six_port(ch, 0)
            if ch == "CH1":
                self.timer1.stop()
            if (ch == "CH2") or self.synced:
                self.timer2.stop()
            if self.synced:
                self.valve_states["CH2"] = deepcopy(self.valve_states["CH1"])
        self.update_valve_display.emit(self.valve_states, self.synced)

    def turn_off_six_ch1(self: Self) -> None:
        """Turn off six way valve channnel 1."""
        if self.valve_states["CH1"] in ["Inject", "Dispose"]:
            self.six_port_handler("CH1")
            logger.debug("Auto shutoff 6P1")

    def turn_off_six_ch2(self: Self) -> None:
        """Turn off six way valve channel 2."""
        if self.valve_states["CH2"] in ["Inject", "Dispose"]:
            self.six_port_handler("CH2")
            logger.debug("Auto shutoff 6P2")

    def sync_handler(self: Self, sync: bool) -> None:  # noqa: FBT001
        """Handle sync."""
        self.synced = sync
        if sync:
            self.timer2.stop()
            self.sync_speed_sig.emit()
            if self.pump_states["CH1"] == "Running":
                self.run_pump(
                    "CH2",
                    int(
                        self.main_window.sidebar.kinetic_widget.ui.run_rate_ch1.currentText(),
                    ),
                )
            elif self.pump_states["CH1"] == "Flushing":
                self.run_pump("CH2", FLUSH_RATE)
            else:
                self.stop_pump("CH2")
            if (
                (self.valve_states["CH2"] in ["Waste", "Dispose"])
                and (self.valve_states["CH1"] in ["Load", "Inject"])
            ) or (
                (self.valve_states["CH2"] in ["Load", "Inject"])
                and (self.valve_states["CH1"] in ["Waste", "Dispose"])
            ):
                self.three_way_handler("CH2")
            if (
                (self.valve_states["CH2"] in ["Waste", "Load"])
                and (self.valve_states["CH1"] in ["Dispose", "Inject"])
            ) or (
                (self.valve_states["CH2"] in ["Dispose", "Inject"])
                and (self.valve_states["CH1"] in ["Waste", "Load"])
            ):
                self.six_port_handler("CH2")
        elif self.timer1.isActive():
            self.timer2.start(self.timer1.remainingTime())

    def enable_sensor_reading(self: Self) -> None:
        """Enable sensor reading."""
        self._s_stop.clear()

    def clear_kin_log(self: Self) -> None:
        """Clear kinetics log."""
        self.clear_sensor_reading_buffers()
        self.log_ch1 = {
            "timestamps": [],
            "times": [],
            "events": [],
            "flow": [],
            "temp": [],
            "dev": [],
        }
        self.log_ch2 = {
            "timestamps": [],
            "times": [],
            "events": [],
            "flow": [],
            "temp": [],
            "dev": [],
        }

    def clear_sensor_reading_buffers(self: Self) -> None:
        """Clear sensor reading buffer."""
        self.flow_buf_1 = []
        self.temp_buf_1 = []
        self.flow_buf_2 = []
        self.temp_buf_2 = []
        self.update_sensor_display.emit(
            {"flow1": "", "temp1": "", "flow2": "", "temp2": ""},
        )
        self.temp_log = {"readings": [], "times": [], "exp": []}
        self.update_temp_display.emit(0.0, "ctrl")

    def save_temp_log(self: Self, rec_dir: str) -> None:
        """Save temperature log."""
        try:
            if rec_dir is not None:
                with Path(rec_dir + " Temperature Log.txt").open(
                    "w",
                    newline="",
                    encoding="utf-8",
                ) as txtfile:
                    fieldnames = ["Timestamp", "Experiment Time", "Device Temp"]
                    writer = csv.DictWriter(
                        txtfile,
                        dialect="excel-tab",
                        fieldnames=fieldnames,
                    )
                    writer.writeheader()
                    for i in range(len(self.temp_log["readings"])):
                        writer.writerow(
                            {
                                "Timestamp": self.temp_log["times"][i],
                                "Experiment Time": self.temp_log["exp"][i],
                                "Device Temp": self.temp_log["readings"][i],
                            },
                        )
        except Exception as e:
            logger.exception(f" Error while saving temperature log data: {e}")

    def save_kinetic_log(self: Self, rec_dir: str) -> None:
        """Save kinetics log."""
        if self.knx is not None:
            try:
                if rec_dir is not None:
                    with Path(rec_dir + " Kinetic Log Ch A.txt").open(
                        "w",
                        newline="",
                        encoding="utf-8",
                    ) as txtfile:
                        if self.knx.version == "1.1":
                            fieldnames = [
                                "Timestamp",
                                "Experiment Time",
                                "Event Type",
                                "Flow Rate",
                                "Sensor Temp",
                                "Device Temp",
                            ]
                        else:
                            fieldnames = [
                                "Timestamp",
                                "Experiment Time",
                                "Event Type",
                                "Flow Rate",
                                "Temperature",
                            ]
                        writer = csv.DictWriter(
                            txtfile,
                            dialect="excel-tab",
                            fieldnames=fieldnames,
                        )
                        writer.writeheader()

                        for i in range(len(self.log_ch1["times"])):
                            if self.knx.version == "1.1":
                                writer.writerow(
                                    {
                                        "Timestamp": self.log_ch1["timestamps"][i],
                                        "Experiment Time": self.log_ch1["times"][i],
                                        "Event Type": self.log_ch1["events"][i],
                                        "Flow Rate": self.log_ch1["flow"][i],
                                        "Sensor Temp": self.log_ch1["temp"][i],
                                        "Device Temp": self.log_ch1["dev"][i],
                                    },
                                )
                            else:
                                writer.writerow(
                                    {
                                        "Timestamp": self.log_ch1["timestamps"][i],
                                        "Experiment Time": self.log_ch1["times"][i],
                                        "Event Type": self.log_ch1["events"][i],
                                        "Flow Rate": self.log_ch1["flow"][i],
                                        "Temperature": self.log_ch1["temp"][i],
                                    },
                                )

                        logger.debug("Ch 1 log saved")

                    if (self.device_config["ctrl"] in ["EZSPR", "PicoEZSPR"]) or (
                        self.device_config["knx"] in ["KNX2", "PicoKNX2"]
                    ):
                        with Path(rec_dir + " Kinetic Log Ch B.txt").open(
                            "w",
                            newline="",
                            encoding="utf-8",
                        ) as txtfile:
                            if self.knx.version == "1.1":
                                fieldnames = [
                                    "Timestamp",
                                    "Experiment Time",
                                    "Event Type",
                                    "Flow Rate",
                                    "Sensor Temp",
                                    "Device Temp",
                                ]
                            else:
                                fieldnames = [
                                    "Timestamp",
                                    "Experiment Time",
                                    "Event Type",
                                    "Flow Rate",
                                    "Temperature",
                                ]
                            writer = csv.DictWriter(
                                txtfile,
                                dialect="excel-tab",
                                fieldnames=fieldnames,
                            )
                            writer.writeheader()

                            for i in range(len(self.log_ch2["times"])):
                                if self.knx.version == "1.1":
                                    writer.writerow(
                                        {
                                            "Timestamp": self.log_ch2["timestamps"][i],
                                            "Experiment Time": self.log_ch2["times"][i],
                                            "Event Type": self.log_ch2["events"][i],
                                            "Flow Rate": self.log_ch2["flow"][i],
                                            "Sensor Temp": self.log_ch2["temp"][i],
                                            "Device Temp": self.log_ch2["dev"][i],
                                        },
                                    )
                                else:
                                    writer.writerow(
                                        {
                                            "Timestamp": self.log_ch2["timestamps"][i],
                                            "Experiment Time": self.log_ch2["times"][i],
                                            "Event Type": self.log_ch2["events"][i],
                                            "Flow Rate": self.log_ch2["flow"][i],
                                            "Temperature": self.log_ch2["temp"][i],
                                        },
                                    )
                            logger.debug("Ch 2 log saved")

            except Exception as e:
                logger.exception(f" Error while saving kinetic log data: {e}")

    def update_internal_temp(self: Self, new_temp: float) -> None:
        """Update internal temperature."""
        self.temp = new_temp

    def sensor_reading_thread(self: Self) -> None:
        """Read from sensor."""
        if self.knx is not None:
            logger.debug("sensor thread started")
            time.sleep(1)
            self.clear_sensor_reading_buffers()
            temp_buffer = []
            while not self._s_kill.is_set():
                time.sleep(0.1)
                try:
                    start = time.time()
                    elapsed = 0.0
                    if self._s_stop.is_set() or (not DEV):
                        continue
                    if (
                        self.device_config["knx"] in {"KNX", "KNX2", "PicoKNX2"}
                    ) or self.device_config["ctrl"] in ["EZSPR", "PicoEZSPR"]:
                        update2 = None
                        flow1_text = ""
                        temp1_text = ""
                        flow2_text = ""
                        temp2_text = ""
                        update1 = self.knx.knx_status(1)
                        self.valve_state_check(update1, 1)
                        logger.debug(f"CH 1: {update1}")
                        time.sleep(0.3)
                        if (
                            (self.device_config["knx"] in ["KNX2", "PicoKNX2"])
                            or (self.device_config["ctrl"] in ["EZSPR", "PicoEZSPR"])
                        ) and (not self._s_stop.is_set()):
                            update2 = self.knx.knx_status(2)
                            self.valve_state_check(update2, 2)
                            logger.debug(f"CH 2: {update2}")
                            time.sleep(0.3)
                        if (
                            update1 is not None
                            and update1["flow"] is not None
                            and update1["temp"] is not None
                        ):
                            self.flow_buf_1.append(update1["flow"])
                            self.temp_buf_1.append(update1["temp"])
                            flow_time = f"{(time.time() - self.exp_start):.2f}"
                            time_now = dt.datetime.now(TIME_ZONE)
                            flow_timestamp = (
                                f"{time_now.hour:02d}"
                                f":{time_now.minute:02d}"
                                f":{time_now.second:02d}"
                            )
                            if len(self.flow_buf_1) <= SENSOR_AVG:
                                flow1_text = f"{(np.nanmean(self.flow_buf_1)):.2f}"
                                temp1_text = f"{(np.nanmean(self.temp_buf_1)):.2f}"
                            else:
                                flow1_text = (
                                    f"{(np.nanmean(self.flow_buf_1[-SENSOR_AVG:])):.2f}"
                                )
                                temp1_text = (
                                    f"{(np.nanmean(self.temp_buf_1[-SENSOR_AVG:])):.2f}"
                                )
                            self.log_ch1["timestamps"].append(flow_timestamp)
                            self.log_ch1["times"].append(flow_time)
                            self.log_ch1["events"].append("Sensor reading")
                            self.log_ch1["flow"].append(flow1_text)
                            self.log_ch1["temp"].append(temp1_text)
                            self.log_ch1["dev"].append("-")
                            logger.debug(
                                f"CH1 append flow1={flow1_text}, temp1={temp1_text}",
                            )
                        if (
                            update2 is not None
                            and update2["flow"] is not None
                            and update2["temp"] is not None
                        ):
                            self.flow_buf_2.append(update2["flow"])
                            self.temp_buf_2.append(update2["temp"])
                            flow_time = f"{(time.time() - self.exp_start):.2f}"
                            time_now = dt.datetime.now(TIME_ZONE)
                            flow_timestamp = (
                                f"{time_now.hour:02d}"
                                f":{time_now.minute:02d}"
                                f":{time_now.second:02d}"
                            )
                            if len(self.flow_buf_2) <= SENSOR_AVG:
                                flow2_text = f"{(np.nanmean(self.flow_buf_2)):.2f}"
                                temp2_text = f"{(np.nanmean(self.temp_buf_2)):.2f}"
                            else:
                                flow2_text = (
                                    f"{(np.nanmean(self.flow_buf_2[-SENSOR_AVG:])):.2f}"
                                )
                                temp2_text = (
                                    f"{(np.nanmean(self.temp_buf_2[-SENSOR_AVG:])):.2f}"
                                )
                            self.log_ch2["timestamps"].append(flow_timestamp)
                            self.log_ch2["times"].append(flow_time)
                            self.log_ch2["events"].append("Sensor reading")
                            self.log_ch2["flow"].append(flow2_text)
                            self.log_ch2["temp"].append(temp2_text)
                            self.log_ch2["dev"].append("-")
                            logger.debug(
                                f"CH2 append flow2={flow2_text}, temp2={temp2_text}",
                            )
                        sensor_data = {
                            "flow1": flow1_text,
                            "temp1": temp1_text,
                            "flow2": flow2_text,
                            "temp2": temp2_text,
                        }
                        self.update_sensor_display.emit(sensor_data)
                    if (
                        self.device_config["ctrl"] in ["QSPR", "EZSPR", "PicoEZSPR"]
                    ) or (self.device_config["knx"] in ["KNX", "KNX2", "PicoKNX2"]):
                        temp = ""
                        try:
                            if self.device_config["ctrl"] == "QSPR" and isinstance(
                                self.ctrl,
                                QSPRController,
                            ):
                                temp = f"{self.ctrl.get_status()['Temperature']:.1f}"
                            elif self.knx.version == "1.1":
                                status = self.knx.get_status()
                                if isinstance(status, dict):
                                    temp = f"{status['Temperature']:.1f}"
                                else:
                                    temp = "0.0"
                            elif (
                                self.device_config["ctrl"] == "PicoEZSPR"
                                or self.device_config["knx"] == "PicoKNX2"
                            ):
                                temp = f"{self.knx.get_status():.1f}"
                        except Exception as e:
                            logger.exception(f"Error while getting device temp: {e}")
                        if temp != "":
                            if self.device_config["ctrl"] in [
                                "QSPR",
                                "EZSPR",
                                "PicoEZSPR",
                            ]:
                                self.update_temp_display.emit(temp, "ctrl")
                            else:
                                self.update_temp_display.emit(temp, "knx")
                            dev_time = f"{(time.time() - self.exp_start):.2f}"
                            time_now = dt.datetime.now(TIME_ZONE)
                            dev_timestamp = (
                                f"{time_now.hour:02d}"
                                f":{time_now.minute:02d}"
                                f":{time_now.second:02d}"
                            )
                            self.log_ch1["timestamps"].append(dev_timestamp)
                            self.log_ch1["times"].append(dev_time)
                            self.log_ch1["events"].append("Device reading")
                            self.log_ch1["flow"].append("-")
                            self.log_ch1["temp"].append("-")
                            self.log_ch1["dev"].append(temp)
                            self.log_ch2["timestamps"].append(dev_timestamp)
                            self.log_ch2["times"].append(dev_time)
                            self.log_ch2["events"].append("Device reading")
                            self.log_ch2["flow"].append("-")
                            self.log_ch2["temp"].append("-")
                            self.log_ch2["dev"].append(temp)
                    if self.device_config["ctrl"] == "PicoP4SPR":
                        try:
                            min_temp = 5
                            max_temp = 75
                            if self.calibrated and min_temp < self.temp < max_temp:
                                temp_buffer.append(self.temp)
                                window = 5
                                if len(temp_buffer) > window:
                                    temp = f"{np.nanmean(temp_buffer[-window:]):.1f}"
                                else:
                                    temp = f"{self.temp:.1f}"
                                self.temp_log["readings"].append(temp)
                                exp_time = time.time() - self.exp_start
                                self.temp_log["exp"].append(f"{exp_time:.2f}")
                                time_now = dt.datetime.now(TIME_ZONE)
                                dev_timestamp = (
                                    f"{time_now.hour:02d}"
                                    f":{time_now.minute:02d}"
                                    f":{time_now.second:02d}"
                                )
                                self.temp_log["times"].append(dev_timestamp)
                                self.update_temp_display.emit(temp, "ctrl")
                        except Exception as e:
                            logger.exception(f"error geting device temp: {e}")
                    while (elapsed < self.sensor_interval) and not (
                        self._s_kill.is_set() or self._s_stop.is_set()
                    ):
                        time.sleep(0.1)
                        elapsed = time.time() - start

                except Exception as e:
                    logger.exception(f"Error during flow sensor reading: {e}")

    def save_default_values(self: Self) -> None:
        """Save default values."""
        if self.device_config["ctrl"] in [
            "P4SPR",
            "PicoP4SPR",
            "EZSPR",
            "PicoEZSPR",
        ] and isinstance(self.ctrl, ArduinoController | PicoEZSPR | PicoP4SPR):
            if show_message(
                msg="Save settings permanently to device?\n"
                "This will overwrite factory default settings",
                yes_no=True,
            ):
                logger.debug("New values saved to P4SPR")
                self.ctrl.flash()
            else:
                logger.debug("Values not saved")
            self.new_default_values = False

    def set_proc_filt(self: Self, filt_en: bool, filt_win: int) -> None:  # noqa: FBT001
        """Set data processing filter."""
        self.filt_on = filt_en
        if filt_win != self.proc_filt_win:
            self.med_filt_win = self.median_window(filt_win)
        if self.main_window.active_page == "data_processing":
            self.main_window.data_processing.set_filter(
                filt_en=filt_en,
                med_filt_win=self.med_filt_win,
            )

    def set_live_filt(self: Self, filt_en: bool, filt_win: int) -> None:  # noqa: FBT001
        """Set live view filter."""
        self.filt_on = filt_en
        if filt_win != self.med_filt_win:
            self.med_filt_win = self.median_window(filt_win)
            self.update_filtered_lambda()
        if self.main_window.active_page == "sensorgram":
            self.main_window.sensorgram.quick_segment_update()

    def connect_advanced_menu(self: Self) -> None:
        """Connect advanced menu."""
        if self.device_config["ctrl"] in DEVICES:
            self.main_window.advanced_menu.new_parameter_sig.connect(
                self.update_advanced_params,
            )
            self.main_window.advanced_menu.get_parameter_sig.connect(
                self.get_device_parameters,
            )
            self.adv_connected = True

    def get_device_parameters(self: Self) -> None:
        """Get device parameters."""
        if self.adv_connected:
            if self.device_config["ctrl"] == "QSPR" and isinstance(
                self.ctrl,
                QSPRController,
            ):
                params = self.ctrl.get_parameters()
                self.main_window.advanced_menu.display_settings(params)
            elif self.ctrl is not None and not isinstance(self.ctrl, QSPRController):
                s_pos = 0
                p_pos = 0
                if self.device_config["ctrl"] in [
                    "P4SPR",
                    "PicoP4SPR",
                    "EZSPR",
                    "PicoEZSPR",
                ]:
                    try:
                        polarizer_pos = self.ctrl.servo_get()
                        s_pos = int(polarizer_pos["s"][0:3])
                        p_pos = int(polarizer_pos["p"][0:3])
                    except Exception as e:
                        logger.exception(f"error reading s & p from device: {e}")
                    logger.debug(f"curr s = {s_pos}, curr p = {p_pos}")
                params = {
                    "led_del": self.led_delay,
                    "ht_req": self.ht_req,
                    "sens_interval": self.sensor_interval,
                    "intg_time": self.integration,
                    "num_scans": self.num_scans,
                    "led_int_a": self.leds_calibrated["a"],
                    "led_int_b": self.leds_calibrated["b"],
                    "led_int_c": self.leds_calibrated["c"],
                    "led_int_d": self.leds_calibrated["d"],
                    "s_pos": s_pos,
                    "p_pos": p_pos,
                    "pump_1_correction": 1,
                    "pump_2_correction": 1,
                }
                if isinstance(self.knx, PicoEZSPR):
                    corrections = self.knx.get_pump_corrections()
                    if corrections is not None:
                        params["pump_1_correction"] = corrections[0]
                        params["pump_2_correction"] = corrections[1]
                self.main_window.advanced_menu.display_settings(params)

    def update_advanced_params(self: Self, params: dict[str, str]) -> None:
        """Update advanced paramerters."""
        if self.adv_connected:
            try:
                if self.device_config["ctrl"] == "QSPR" and isinstance(
                    self.ctrl,
                    QSPRController,
                ):
                    p_string = (
                        f"{params['s_pos']},{params['p_pos']},{params['up_time']},{params['down_time']},"
                        f"{params['adj_time']},{params['debounce']},{params['start_interval']}"
                    )
                    self.ctrl.set_parameters(p_string)
                elif self.ctrl is not None and not isinstance(
                    self.ctrl,
                    QSPRController,
                ):
                    self.pause()
                    self.led_delay = float(params["led_del"])
                    self.ht_req = float(params["ht_req"])
                    self.sensor_interval = float(params["sens_interval"])
                    self.num_scans = int(params["num_scans"])
                    new_intg = float(params["intg_time"])
                    if new_intg < MIN_INTEGRATION:
                        new_intg = MIN_INTEGRATION
                    elif new_intg > MAX_INTEGRATION:
                        new_intg = MAX_INTEGRATION
                    if self.usb.serial_number == "FLMT09793":
                        new_intg = round(new_intg / 2.5) * 2.5
                    self.integration = new_intg
                    self.usb.set_integration(new_intg)
                    new_led_ints = {
                        "a": int(params["led_int_a"]),
                        "b": int(params["led_int_b"]),
                        "c": int(params["led_int_c"]),
                        "d": int(params["led_int_d"]),
                    }
                    for ch in CH_LIST:
                        min_intensity = 1
                        max_intensity = 255
                        if new_led_ints[ch] > max_intensity:
                            new_led_ints[ch] = max_intensity
                        elif new_led_ints[ch] < min_intensity:
                            new_led_ints[ch] = min_intensity
                        self.leds_calibrated[ch] = new_led_ints[ch]
                        self.ctrl.set_intensity(ch=ch, raw_val=new_led_ints[ch])
                        time.sleep(0.1)
                        self.ctrl.turn_off_channels()
                        time.sleep(0.1)

                    # Update polarizer servo position if needed
                    current_servo_positions = self.ctrl.servo_get()
                    old_s = int(current_servo_positions["s"])
                    old_p = int(current_servo_positions["p"])
                    new_s = int(params["s_pos"])
                    new_p = int(params["p_pos"])
                    if old_s != new_s or old_p != new_p:
                        self.ctrl.servo_set(s=new_s, p=new_p)
                        self.ctrl.flash()

                    # Update pump corrections if needed
                    if isinstance(self.knx, PicoEZSPR):
                        corrections = self.knx.get_pump_corrections()
                        if corrections is not None:
                            try:
                                new_corrections = (
                                    float(params["pump_1_correction"]),
                                    float(params["pump_2_correction"]),
                                )
                            except ValueError:
                                new_corrections = 1, 1
                            if corrections != new_corrections:
                                self.knx.set_pump_corrections(*new_corrections)

                    self.resume()
                    # Disable automatic new reference - manual only!

            except Exception as e:
                logger.exception(f"Error while updating advanced parameters: {e}")

    def clear_data(self: Self) -> None:
        """Clear data."""
        self.pause()
        time.sleep(0.5)
        self.lambda_values = {
            ch: np.array([]) for ch in CH_LIST
        }  # sensorgram data for each channel
        self.lambda_times = {
            ch: np.array([]) for ch in CH_LIST
        }  # sensorgram data timestamps
        self.filtered_lambda = {
            ch: np.array([]) for ch in CH_LIST
        }  # sensorgram data with median filtering
        self.buffered_lambda = {
            ch: np.array([]) for ch in CH_LIST
        }  # sensorgram data unfiltered buffered values
        self.buffered_times = {
            ch: np.array([]) for ch in CH_LIST
        }  # sensorgram data filtered buffered times
        self.ignore_warnings = {ch: False for ch in CH_LIST}
        self.no_sig_count = {ch: 0 for ch in CH_LIST}
        self.filt_buffer_index = 0
        self.set_start()
        self.clear_kin_log()
        if self.recording:
            self.recording_on()
        self.resume()

    def connect_dev(self: Self) -> None:
        """Connect a device."""
        if self.ctrl is None or self.knx is None or self.pump is None:
            self.main_window.ui.status.setText("Scanning for devices...")
            self.connection_thread()
        else:
            logger.debug("Already connected!")

    def stop(self: Self, *, knx: bool = True) -> None:
        """Stop."""
        self._c_stop.set()
        self._b_stop.set()
        if (self.knx is not None) and knx:
            self.knx.stop_kinetic()
            self.pump_states["CH1"] = "Off"
            self.pump_states["CH2"] = "Off"
        self._s_stop.set()
        if self.recording:
            self.rec_timer.stop()
            self.recording_on()
        time.sleep(0.5)

    def crt_control_handler(self: Self, command: str) -> None:
        """Crt control handler."""
        if self.device_config["ctrl"] == "QSPR" and isinstance(
            self.ctrl,
            QSPRController,
        ):
            self.pause()
            if command == "up":
                self.ctrl.crt_up()
            elif command == "down":
                self.ctrl.crt_down()
            elif command == "adj_up":
                self.ctrl.crt_adj_up()
            elif command == "adj_down":
                self.ctrl.crt_adj_down()
            self.resume()

    def shutdown_handler(self: Self, device_type: str) -> None:
        """Shutdown."""
        if self.recording:
            self.recording_on()
        if device_type == "controller":
            self.shutdown_controller()
        elif device_type == "kinetic":
            self.shutdown_kinetics()
        elif device_type == "both":
            self.shutdown_kinetics(skip_setup=True)
            self.disconnect_dev()
            self.main_window.sidebar.kinetic_widget.setup(
                self.device_config["ctrl"],
                self.device_config["knx"],
            )

    def shutdown_controller(self: Self) -> None:
        """Shutdown controller."""
        self.main_window.ui.status.setText("SPR device powering off...")
        if isinstance(self.ctrl, PicoEZSPR | QSPRController):
            self.ctrl.shutdown()
        self.disconnect_dev(knx=False)
        self.get_current_device_config()
        self.main_window.sidebar.device_widget.setup(
            self.device_config["ctrl"],
            self.device_config["knx"],
            self.pump,
        )

    def shutdown_kinetics(self: Self, *, skip_setup: bool = False) -> None:
        """Shutdown kinetics."""
        self.main_window.ui.status.setText("Kinetic unit powering off...")
        self._s_stop.set()
        if self.knx is not None:
            self.knx.shutdown()
            self.knx.close()
        self.knx = None
        if not skip_setup:
            self.get_current_device_config()
            self.main_window.sidebar.device_widget.setup(
                self.device_config["ctrl"],
                self.device_config["knx"],
                self.pump,
            )

    def disconnect_handler(self: Self, disconnect_type: str) -> None:
        """Disconnect handler."""
        self._b_no_read.set()
        if disconnect_type == "controller":
            time.sleep(0.5)
            self.disconnect_dev(knx=False, pump=False)
        elif disconnect_type == "kinetic":
            self._b_no_read.clear()
            self.disconnect_dev(ctrl=False, pump=False)
        elif disconnect_type == "both":
            time.sleep(0.5)
            self.disconnect_dev(pump=False)
        elif disconnect_type == "pump":
            self.disconnect_dev(ctrl=False, knx=False)

    def disconnect_dev(
        self: Self,
        *,
        ctrl: bool = True,
        knx: bool = True,
        pump: bool = True,
    ) -> None:
        """Disconnect a device."""
        self.main_window.ui.status.setText("Disconnecting...")
        self.main_window.ui.status.repaint()
        if self.recording:
            self.recording_on()
        self.main_window.sidebar.device_widget.allow_commands(False)  # noqa: FBT003
        if self._con_tr.is_alive():
            self._con_tr.join(0.1)
        self.stop(knx=knx)
        self.calibrated = False
        time.sleep(0.5)
        if (self.ctrl is not None) and ctrl:
            self.calibrated = False
            if self.usb is not None:
                logger.debug("closing usb")
                self.usb.close()
            logger.debug("closing device")
            self.ctrl.stop()
            self.ctrl.close()
            self.ctrl = None
        if (self.knx is not None) and knx:
            self.knx_reset_ui.emit()
            self.knx.close()
            self.knx = None
        if self.pump and pump:
            with suppress(FTDIError):
                self.pump.send_command(0x41, b"V16.667,1R")
            self.pump = None
        if not ((self.ctrl is None) and (self.knx is None)):
            logger.debug(f"No manual close for ctrl {self.ctrl} and knx {self.knx}")
        self.get_current_device_config()
        self.main_window.sidebar.device_widget.setup(
            self.device_config["ctrl"],
            self.device_config["knx"],
            self.pump,
        )
        self.main_window.sidebar.kinetic_widget.setup(
            self.device_config["ctrl"],
            self.device_config["knx"],
        )

    def close(self: Self) -> bool:
        """Close the app."""
        self.closing = True
        self.disconnect_dev()
        self._b_kill.set()
        self._c_kill.set()
        self._s_kill.set()
        time.sleep(0.5)
        if self._c_tr.is_alive():
            self._c_tr.join(0.5)
            logger.debug("calibration thread joined")
        if self._tr.is_alive():
            self._tr.join(0.5)
            logger.debug("grab data thread joined")
        if self._con_tr.is_alive():
            self._con_tr.join(0.1)
            logger.debug("connection thread joined")
        if self._s_tr.is_alive():
            self._s_tr.join(0.5)
            logger.debug("sensor reading thread joined")
        self.rec_timer.stop()
        return super().close()

    def on_crashed(self: Self) -> None:
        """Log a crash."""
        try:
            if self.ctrl is not None:
                self.ctrl.close()
            if self.usb is not None:
                self.usb.close()
        except Exception as e:
            logger.exception(f"Error during crash handling: {e}")


def main() -> None:
    """Run the application."""
    dtnow = dt.datetime.now(TIME_ZONE)
    logger.info("========== Starting Affinite Instruments Application ==========")
    logger.info(
        f"{SW_VERSION}-{dtnow.year}/{dtnow.month}/{dtnow.day}-"
        f"{dtnow.hour:02d}{dtnow.minute:02d}",
    )

    _affinite_app = QApplication(sys.argv)

    app = AffiniteApp()

    with suppress(NameError):
        pyi_splash.close()

    _excepthook = sys.excepthook
    sys.stderr = Path(ROOT_DIR, "stderr.txt").open(  # noqa: SIM115
        "w",
        encoding="utf-8",
    )
    sys.stdout = Path(ROOT_DIR, "stdout.txt").open(  # noqa: SIM115
        "w",
        encoding="utf-8",
    )

    if DEV:
        faulthandler.enable()

    def exception_hook(
        exctype: type[BaseException],
        value: BaseException,
        tb: TracebackType | None,
    ) -> None:
        logger.error("=========== Crashed!", exc_info=(exctype, value, tb))
        _excepthook(exctype, value, tb)
        sys.stderr.write(f"Crash! {exctype} : {value} : {tb}")
        app.on_crashed()
        sys.exit(1)

    sys.excepthook = exception_hook

    set_event_loop_policy(QAsyncioEventLoopPolicy())
    get_event_loop().call_soon(app.connect_dev)
    get_event_loop().run_forever()


if __name__ == "__main__":
    main()
