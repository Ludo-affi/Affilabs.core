# This module is riddled with long function that have too many statements, too many
# branches, and are too complex. It also contains a lot of catch all exception blocks.
# These should eventually be adressed, but for now we'll just turn off the warnings.
# ruff: noqa: PLR0912, PLR0915, C901, BLE001

"""Defines and launches the application."""

from __future__ import annotations

import asyncio
import atexit
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

# Ensure sibling packages (e.g., utils/) are importable when running as a script
_pkg_root = Path(__file__).resolve().parents[1]
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

import numpy as np
import pandas as pd
import pyqtgraph
import serial
try:
    from pump_controller import FTDIError, PumpController
except ImportError:
    # pump_controller is optional - only needed for hardware control
    FTDIError = Exception
    PumpController = None
from PySide6.QtAsyncio import QAsyncioEventLoopPolicy
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow
from utils.spr_signal_processing import (
    find_resonance_wavelength_fourier,
    apply_centered_median_filter,
    calculate_fourier_weights,
)
from utils.spectrum_processor import SpectrumProcessor, TemporalFilter
from utils.channel_manager import ChannelManager

from settings import (
    CH_LIST,
    LED_POST_DELAY,
    USE_DYNAMIC_POST_DELAY,
    # DARK_NOISE_SCANS,
    DEV,
    EZ_CH_LIST,
    FILTERING_ON,
    FLUSH_RATE,
    INTEGRATION_STEP,
    LED_DELAY,
    USE_DYNAMIC_LED_DELAY,
    LED_DELAY_TARGET_RESIDUAL,
    MAX_INTEGRATION,
    # MAX_NUM_SCANS,
    # MAX_READ_TIME,
    MAX_WAVELENGTH,
    MED_FILT_WIN,
    MIN_INTEGRATION,
    MIN_WAVELENGTH,
    # P_COUNT_THRESHOLD,
    # P_LED_MAX,
    # P_MAX_INCREASE,
    RECORDING_INTERVAL,
    REF_SCANS,
    ROOT_DIR,
    # S_COUNT_MAX,
    # S_LED_INT,
    # S_LED_MIN,
    SENSOR_AVG,
    SENSOR_POLL_INTERVAL,
    SW_VERSION,
    TRANS_SEG_H_REQ,
)
from utils.common import get_config, update_config_file
from utils.hardware_state import HardwareStateManager
from utils.led_calibration import perform_full_led_calibration
from utils.spectrum_acquisition import SpectrumAcquisition
from utils.acquisition_service import AcquisitionService
from utils.hal.adapters import CtrlLEDAdapter, UsbSpectrometerInfoAdapter, OceanSpectrometerAdapter
import sys
from pathlib import Path
_repo_root = str(Path(__file__).parent.parent.parent)
if _repo_root not in sys.path:
    sys.path.append(_repo_root)
from afterglow_correction import AfterglowCorrection
from utils.ui_styles import UIStyleManager
from utils.controller import (
    ArduinoController,
    KineticController,
    PicoEZSPR,
    PicoKNX2,
    PicoP4SPR,
    QSPRController,
    StaticController,
    FlowController,
)
from utils.logger import logger
# from utils.SpectrometerAPI import SENSOR_FRAME_T
from utils.detector_factory import create_detector
# Initialize processing pipelines
import utils.pipelines  # This auto-registers all pipelines
from widgets.datawindow import Segment
from widgets.mainwindow import MainWindow
from widgets.message import show_message
from widgets.priming import PrimingWindow

# Import modern theme system
try:
    from styles import apply_modern_theme, apply_modern_graph_style
    MODERN_THEME_AVAILABLE = True
except ImportError:
    logger.warning("Modern theme system not available, using default styling")
    MODERN_THEME_AVAILABLE = False

with suppress(ImportError):
    import pyi_splash

# Apply modern PyQtGraph styling
if MODERN_THEME_AVAILABLE:
    apply_modern_graph_style()
else:
    # Fallback to basic white background
    pyqtgraph.setConfigOption("background", "w")
    pyqtgraph.setConfigOption("foreground", "k")


os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
DEVICES = ["P4SPR", "PicoP4SPR", "EZSPR", "PicoEZSPR"]  # QSPR removed - obsolete hardware
TIME_ZONE = dt.datetime.now(dt.UTC).astimezone().tzinfo

# Type unions organized by capability
Controller = StaticController | FlowController  # All controllers
KNX = KineticController | PicoKNX2 | PicoEZSPR  # Flow controllers with pump/valve support


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
    # Thread-safe UI messaging (dispatches to main thread)
    ui_message_sig = Signal(str, str, int)
    # Update Advanced dialog delay status: led_delay, post_delay, dyn flags, cal file
    adv_delay_status_sig = Signal(float, float, bool, bool, str)
    # Direct text updates for Advanced status line (start/progress/completion)
    adv_status_text_sig = Signal(str)

    calibrated = False  # Calibration flag

    ctrl: Controller | None = None
    knx: KNX | None = None
    pump: object | None = None
    auto_polarize = False
    flow_rate: float = 0.5

    def __init__(self: Self) -> None:
        """Create the app's main window."""
        # CRITICAL: Initialize QMainWindow FIRST before creating any child widgets
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, on=True)

        # Defer garbage collection until after startup
        gc.disable()
        
        self.main_window = MainWindow(self)
        self.device_config = {"ctrl": "", "knx": ""}
        self.conf = get_config()

        # Defer detector initialization to avoid blocking startup
        self.usb = None
        QTimer.singleShot(100, self._init_detector)

        self.recording = False
        self.rec_dir = ""
        self.adv_connected = False

        # Hardware state manager
        self.hw_state = HardwareStateManager()

        # Channel manager (centralized buffer management)
        self.channel_mgr = ChannelManager()

        # reference data
        self.ref_sig = {ch: np.array([]) for ch in CH_LIST}
        # intensity data
        self.int_data = {ch: np.array([]) for ch in CH_LIST}
        # transmission data
        self.trans_data = {ch: np.array([]) for ch in CH_LIST}

        # Post-delay placeholder; finalized after core init
        self.post_delay = LED_POST_DELAY

        # Initialize attributes set later to avoid type checker warnings
        self.wave_data: np.ndarray | None = np.array([])
        self.fourier_weights: np.ndarray | None = None
        self.dark_noise: np.ndarray = np.array([])
        self.ch_error_list: list[str] = []
        self.ignore_warnings: dict[str, bool] = {ch: False for ch in CH_LIST}
        self.no_sig_count: dict[str, int] = {ch: 0 for ch in CH_LIST}

        # start with no fixed filtered data
        self.new_filtered_data = np.array([])

        # Defer advanced menu signal connections until menu is created
        self.adv_delay_status_sig.connect(self._on_adv_delay_status)
        self.adv_status_text_sig.connect(self._on_adv_status_text)

        # Spectrum acquisition helper (for vectorized acquisition)
        self.spectrum_acq = None  # Initialized after USB device is opened

        # Spectrum processor (centralized processing logic)
        self.spectrum_processor = None  # Initialized after calibration with fourier_weights
        self.temporal_filter = None  # Initialized with median window settings

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

        # Thread lock for filter parameter updates
        self._filter_lock = threading.Lock()

        self._tr = threading.Thread(target=self._grab_data)
        self._tr.start()

        self._c_kill = threading.Event()
        self._c_stop = threading.Event()
        self._c_stop.set()

        # Connect thread-safe UI messaging (simplified)
        self.ui_message_sig.connect(self._show_ui_message)
        
        self._c_kill.clear()
        self._c_tr = threading.Thread(target=self.calibrate)
        self._c_tr.start()

        self._con_tr = threading.Thread(target=self.connection_thread)
        self._new_sig_tr = threading.Thread(target=self.new_ref_thread)

        self._s_kill = threading.Event()
        self._s_stop = threading.Event()
        self._s_kill.clear()
        self._s_stop.set()
        self._s_tr = threading.Thread(target=self.sensor_reading_thread)
        self._s_tr.start()

        self.rec_timer = QTimer()
        self.rec_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.rec_timer.timeout.connect(self.save_rec_data)

        self.update_timer = QTimer()
        self.update_timer.setTimerType(Qt.TimerType.PreciseTimer)

        self.timer1 = QTimer()
        self.timer2 = QTimer()
        self.timer1.timeout.connect(self.turn_off_six_ch1)
        self.timer2.timeout.connect(self.turn_off_six_ch2)

        # Temperature log - using pandas DataFrame
        self.temp_log = pd.DataFrame(columns=["Timestamp", "Experiment Time", "Device Temp"])

        self.temp = 0.0
        self.flow_buf_1: list[float] = []
        self.temp_buf_1: list[float] = []
        self.flow_buf_2: list[float] = []
        self.temp_buf_2: list[float] = []

        # Event logs - using pandas DataFrames
        self.log_ch1 = pd.DataFrame(columns=["timestamp", "time", "event", "flow", "temp", "dev"])
        self.log_ch2 = pd.DataFrame(columns=["timestamp", "time", "event", "flow", "temp", "dev"])

        self.exp_start = time.time()
        self.exp_start_perf = time.perf_counter()
        self.reconnect_count = 2
        self.closing = False
        self.new_default_values = False

        # Connect all UI and internal signals
        self._connect_all_signals()

        self.kinetic_tasks = set()

        # Register cleanup handler for graceful shutdown
        atexit.register(self._emergency_cleanup)
        
        # Re-enable garbage collection after startup and schedule first collection
        QTimer.singleShot(1000, lambda: (gc.enable(), gc.collect()))

    def _init_detector(self: Self) -> None:
        """Deferred detector initialization to avoid blocking startup."""
        try:
            self.usb = create_detector(self, self.conf)
            if self.usb is None:
                logger.warning("No detector available - running in simulation mode")
        except Exception as e:
            logger.error(f"Detector initialization failed: {e}")
            self.usb = None

    def _on_adv_delay_status(self: Self, led, post, dled, dpost, path) -> None:
        """Handle advanced delay status updates (lazy check for menu)."""
        if (hasattr(self.main_window, "advanced_menu") and 
            self.main_window.advanced_menu is not None and 
            hasattr(self.main_window.advanced_menu, "set_delay_status")):
            self.main_window.advanced_menu.set_delay_status(
                led_delay_s=float(led),
                post_delay_s=float(post),
                dyn_led=bool(dled),
                dyn_post=bool(dpost),
                cal_path=str(path) if path else None,
            )

    def _on_adv_status_text(self: Self, txt: str) -> None:
        """Handle advanced status text updates (lazy check for menu)."""
        if (hasattr(self.main_window, "advanced_menu") and 
            self.main_window.advanced_menu is not None and 
            hasattr(self.main_window.advanced_menu, "set_status_text")):
            self.main_window.advanced_menu.set_status_text(str(txt))

    def _show_ui_message(self: Self, msg: str, msg_type: str, auto_close_time: int) -> None:
        """Show UI message (simplified wrapper)."""
        show_message(msg=msg, msg_type=msg_type, auto_close_time=auto_close_time)

    def _log_event(self: Self, channel: str, event: str, flow: str = "-", temp: str = "-", dev: str = "-") -> None:
        """Add event to log using pandas DataFrame.

        Args:
            channel: "CH1" or "CH2"
            event: Event description
            flow: Flow rate value (default "-")
            temp: Temperature value (default "-")
            dev: Device value (default "-")
        """
        time_now = dt.datetime.now(TIME_ZONE)
        log_timestamp = f"{time_now.hour:02d}:{time_now.minute:02d}:{time_now.second:02d}"
        log_time = f"{(time.perf_counter() - self.exp_start_perf):.2f}"

        new_event = pd.DataFrame([{
            'timestamp': log_timestamp,
            'time': log_time,
            'event': event,
            'flow': flow,
            'temp': temp,
            'dev': dev
        }])

        if channel == "CH1":
            self.log_ch1 = pd.concat([self.log_ch1, new_event], ignore_index=True)
        else:
            self.log_ch2 = pd.concat([self.log_ch2, new_event], ignore_index=True)

    def _connect_all_signals(self: Self) -> None:
        """Centralized signal connection management.

        All UI widget signals and internal signals are connected here for easy
        maintenance and modification. Organized by category for clarity.
        """
        # === Internal Application Signals ===
        self.calibration_status.connect(self._on_calibration_status)
        self.calibration_started.connect(self._on_calibration_started)
        self.connected.connect(self.open_device)
        self.raise_error.connect(self.error_handler)
        self.new_ref_done_sig.connect(self.new_ref_done)
        self.temp_sig.connect(self.update_internal_temp)

        # === Data Update Signals (App -> UI) ===
        if hasattr(self.main_window, "sidebar_spectroscopy"):
            self.update_spec_signal.connect(self.main_window.sidebar_spectroscopy.update_data)
        self.update_live_signal.connect(self.main_window.sensorgram.update_data)
        self.update_temp_display.connect(
            self.main_window.sidebar.device_widget.update_temp,
        )
        self.update_sensor_display.connect(
            self.main_window.sidebar.kinetic_widget.update_readings,
        )
        self.update_pump_display.connect(
            self.main_window.sidebar.kinetic_widget.update_pump_ui,
        )
        self.update_valve_display.connect(
            self.main_window.sidebar.kinetic_widget.update_valve_ui,
        )
        self.sync_speed_sig.connect(self.main_window.sidebar.kinetic_widget.sync_speeds)
        self.knx_reset_ui.connect(self.main_window.sidebar.kinetic_widget.reset_ui)

        # === Main Window Control Signals ===
        self.main_window.set_start_sig.connect(self.set_start)
        self.main_window.clear_flow_buf_sig.connect(self.clear_sensor_reading_buffers)
        self.main_window.record_sig.connect(self.recording_on)
        self.main_window.pause_sig.connect(self.handle_pause)

        # === Sensorgram Window Signals ===
        self.main_window.sensorgram.reset_graphs_sig.connect(self.clear_data)
        self.main_window.sensorgram.reference_channel_dlg.live_filt_sig.connect(
            self.set_live_filt,
        )
        self.main_window.sensorgram.reference_channel_dlg.colorblind_mode_signal.connect(
            self.toggle_colorblind_mode,
        )
        self.main_window.sensorgram.save_sig.connect(self.manual_export_raw_data)
        self.main_window.sensorgram.ui.inject_button.clicked.connect(
            self.handle_inject_button,
        )
        self.main_window.sensorgram.ui.regen_button.clicked.connect(
            self.handle_regen_button,
        )
        self.main_window.sensorgram.ui.flush_button.clicked.connect(self.handle_flush_button)
        self.main_window.sensorgram.ui.prime_button.clicked.connect(self.prime)
        self.main_window.sensorgram.ui.flow_rate.editingFinished.connect(
            self.change_flow_rate,
        )

        # === Data Processing Window Signals ===
        self.main_window.data_processing.send_to_analysis_sig.connect(
            self.send_to_analysis,
        )
        self.main_window.data_processing.reference_channel_dlg.proc_filt_sig.connect(
            self.set_proc_filt,
        )
        self.main_window.data_processing.reference_channel_dlg.colorblind_mode_signal.connect(
            self.toggle_colorblind_mode,
        )
        self.main_window.data_processing.pull_sensorgram_sig.connect(
            self.transfer_sens_data,
        )

        # === Device Control Signals (Sidebar) ===
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

        # === Kinetic Control Signals (Sidebar) ===
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
        self.main_window.sidebar.kinetic_widget.channel_visibility_sig.connect(
            self.update_channel_visibility,
        )

        # === Spectroscopy Window Signals ===

        # === Sidebar Spectroscopy Signals ===
        if hasattr(self.main_window, "sidebar_spectroscopy"):
            self.main_window.sidebar_spectroscopy.full_cal_sig.connect(self.full_recalibration)
            logger.info("Connected sidebar spectroscopy full_calibrate_btn to full_recalibration")

        # === Advanced Menu ===
        self.main_window.connect_adv_sig.connect(self.connect_advanced_menu)

        # === Pipeline Selector Signal ===
        if hasattr(self.main_window.sidebar, 'pipeline_widget') and self.main_window.sidebar.pipeline_widget:
            self.main_window.sidebar.pipeline_widget.pipeline_changed.connect(self._on_pipeline_changed)
            logger.info("Connected pipeline selector signal")

    def _on_pipeline_changed(self: Self, pipeline_id: str) -> None:
        """Handle pipeline selection change"""
        try:
            from utils.processing_pipeline import get_pipeline_registry
            registry = get_pipeline_registry()
            active = registry.get_active_pipeline()
            metadata = active.get_metadata()

            logger.info(f"🔄 Pipeline changed to: {metadata.name}")

            # Show confirmation message to user
            from widgets.message import show_message
            show_message(
                msg=f"Processing pipeline changed to:\n{metadata.name}\n\nNew pipeline will be used for all subsequent spectra.",
                msg_type="Information",
                auto_close_time=3
            )
        except Exception as e:
            logger.exception(f"Error handling pipeline change: {e}")

    def connection_thread(self: Self) -> None:
        """Attempt to connect to different controlers."""
        # Skip connection if spectrometer not available
        if self.usb is None:
            logger.warning("Spectrometer not available, skipping hardware connection")
            return

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
                        # Initialize device-specific configuration
                        try:
                            from utils.device_integration import initialize_device_on_connection
                            device_dir = initialize_device_on_connection(self.usb)
                            if device_dir:
                                logger.info(f"✅ Device-specific config initialized: {device_dir.name}")
                        except Exception as e:
                            logger.warning(f"⚠️ Device initialization failed: {e}")
                    else:
                        self.raise_error.emit("spec")
                elif pico_ezspr.open():
                    logger.debug(f" Pico EZSPR Fw: {pico_ezspr.version}")
                    logger.debug("attempting spectrometer connection")
                    if self.usb.open():
                        self.ctrl = pico_ezspr
                        self.knx = pico_ezspr
                    if self.ctrl == pico_ezspr and (
                        pico_ezspr.version in pico_ezspr.UPDATABLE_VERSIONS
                        and show_message(
                            "Would you like to update the firmware on your device?",
                            "Question",
                            yes_no=True,
                        )
                    ):
                        if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
                            base_dir = getattr(sys, "_MEIPASS")  # noqa: SLF001 - runtime attribute set by PyInstaller
                            firmware = Path(base_dir) / "affinite_ezspr.uf2"
                        else:
                            firmware = Path("affinite_ezspr.uf2")
                        if firmware.exists() and pico_ezspr.update_firmware(firmware):
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
                self.main_window.sensorgram.ui.preset_functions_frame.setEnabled(True)

            # Only emit connected signal if at least one device was found
            if self.ctrl is not None or self.knx is not None:
                self.connected.emit()
            else:
                logger.info("No SPR or Kinetics hardware detected")
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
        # Device display removed
        if dev_str == "No Devices":
            logger.info("Status updated")
        else:
            logger.info("Status updated")
        self.main_window.on_device_config(self.device_config)

    def open_device(self: Self) -> None:
        """Open connection to devices."""
        if self._con_tr.is_alive():
            logger.info("Status updated")
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
                # ✨ MODIFIED: Calculate contact time as 20% of injection time
                # Injection time = 80 µL / flow_rate (mL/min converted to µL/min)
                # Contact time = 20% of injection time
                injection_time_minutes = 80 / (self.flow_rate * 1000)  # 80 µL / (flow_rate in µL/min)
                contact_time = injection_time_minutes * 0.20 * 60  # 20% converted to seconds
                logger.debug(f"Regeneration contact time: {contact_time:.1f}s (20% of {injection_time_minutes*60:.1f}s injection)")

                self.pump.send_command(0x41, b"T")
                cmd = (
                    "IS15A181490"
                    "OV4.167,1A0"
                    "IS15A181490"
                    f"OV{self.flow_rate:.3f},1A0R"
                ).encode()
                self.pump.send_command(0x41, cmd)
                self.main_window.sensorgram.start_progress_bar(
                    int(48_000 + 1125 * contact_time),  # ✨ MODIFIED: Adjusted for 3s delay (was 67s + 1.125*contact)
                )
                await asyncio.sleep(3)  # ✨ MODIFIED: Reduced from 22 to 3 seconds
                self.knx.knx_six(state=1, ch=3)
                await asyncio.sleep(contact_time)
                self.knx.knx_six(state=0, ch=3)
                self.pump.send_command(0x41, b"V6,1R")  # ✨ MODIFIED: Changed from 83.333 to 6 mL/min
                await asyncio.sleep(0.8)
                self.pump.send_command(0x41, b"V6000R")
            except ValueError as e:
                logger.exception(f"Invalid contact time: {e}")
            except FTDIError as e:
                logger.exception(f"Error communicating with pumps: {e}")

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
                    "IS12A181490"
                    "OS15A0"
                    "IS12A181490"
                    f"OV{self.flow_rate:.3f},1A0R"
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

                self.main_window.sensorgram.ui.preset_functions_frame.setEnabled(False)
                await asyncio.sleep(15)  # ✨ MODIFIED: Reduced from 50 to 15 seconds
                self.main_window.sensorgram.ui.preset_functions_frame.setEnabled(True)
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
            or (self.usb is not None and self.usb.opened)
        )

    @Slot()
    def set_start(self: Self) -> None:
        """Set recording start time."""
        start_time = time.time()
        start_perf = time.perf_counter()
        # Use monotonic diff for data arrays; keep wall-clock for logs
        time_diff = start_perf - self.exp_start_perf
        self.exp_start = start_time
        self.exp_start_perf = start_perf

        # Update ChannelManager timestamps (only valid data, not preallocated space)
        for ch in CH_LIST:
            n = self.channel_mgr._current_length[ch]
            self.channel_mgr.lambda_times[ch][:n] -= time_diff
            self.channel_mgr.buffered_times[ch][:n] -= time_diff

        # Force UI update with shifted timestamps BEFORE reloading segments
        # This ensures self.data in datawindow has the correct shifted times
        if self.main_window.active_page == "sensorgram":
            from PySide6.QtCore import QCoreApplication
            self.update_live_signal.emit(self.sensorgram_data())
            # Process events to ensure data update is applied before segment reload
            QCoreApplication.processEvents()

        # Now reload segments with the updated data
        self.main_window.sensorgram.reload_segments(time_diff)

    def startup(self: Self) -> None:
        """Start device calibration, I think."""
        if self.ctrl is not None and self.device_config["ctrl"] in DEVICES:
            # Initialize AfterglowCorrection instance using device-specific calibration
            if getattr(self, "afterglow_correction", None) is None:
                try:
                    from utils.device_integration import get_device_optical_calibration_path

                    optical_cal_path = get_device_optical_calibration_path()

                    if optical_cal_path and optical_cal_path.exists():
                        self.afterglow_correction = AfterglowCorrection(optical_cal_path)
                        logger.info(f"✅ Device-specific afterglow correction loaded")
                        logger.info(f"   Calibration file: {optical_cal_path.name}")
                    else:
                        logger.info("No device-specific optical calibration found")
                        logger.info("   Afterglow correction disabled (run manual calibration from settings)")
                except Exception as e:
                    logger.warning(f"AfterglowCorrection unavailable: {e}")
            # Initialize spectrum acquisition helper
            if self.usb is not None and self.spectrum_acq is None:
                # Wrap USB spectrometer with HAL adapter and use it in acquisition helper
                self.spec_adapter = OceanSpectrometerAdapter(self.usb)
                self.spectrum_acq = SpectrumAcquisition(self.spec_adapter)
                logger.debug("Initialized spectrum acquisition helper")
                # Initialize HAL adapters and acquisition service once helper is ready
                try:
                    self.led_controller = CtrlLEDAdapter(self.ctrl) if self.ctrl is not None else None
                    self.spec_info = UsbSpectrometerInfoAdapter(self.usb)
                    if self.led_controller is not None and self.spectrum_acq is not None:
                        self.acq_service = AcquisitionService(self.led_controller, self.spec_info, self.spectrum_acq)
                        logger.debug("Initialized AcquisitionService (HAL)")
                except Exception as e:
                    logger.exception(f"Failed to initialize AcquisitionService (HAL): {e}")

            # If enabled, attempt to compute dynamic LED delay based on afterglow model
            if USE_DYNAMIC_LED_DELAY:
                try:
                    if getattr(self, "integration", None) is not None and getattr(self, "afterglow_correction", None) is not None:
                        dyn_delay = float(self.afterglow_correction.get_optimal_led_delay(
                            integration_time_ms=float(self.integration),
                            target_residual_percent=float(LED_DELAY_TARGET_RESIDUAL),
                        ))
                        logger.info(f"Dynamic LED delay computed: {dyn_delay*1000:.1f} ms (was {self.led_delay*1000:.1f} ms)")
                        # Only adopt if sane (e.g., 5 ms <= delay <= 200 ms)
                        if 0.005 <= dyn_delay <= 0.200:
                            self.led_delay = dyn_delay
                        else:
                            logger.warning(f"Dynamic LED delay {dyn_delay:.3f}s out of range; keeping legacy {self.led_delay:.3f}s")
                    else:
                        logger.info("Dynamic LED delay enabled, but integration/afterglow not ready.")
                except Exception as e:
                    logger.warning(f"Dynamic LED delay unavailable: {e}. Using legacy fixed delay {self.led_delay:.3f}s")

            # If enabled, compute dynamic post delay (dark time after LED off)
            if USE_DYNAMIC_POST_DELAY:
                try:
                    if getattr(self, "integration", None) is not None and getattr(self, "afterglow_correction", None) is not None:
                        dyn_post = float(self.afterglow_correction.get_optimal_led_delay(
                            integration_time_ms=float(self.integration),
                            target_residual_percent=float(LED_DELAY_TARGET_RESIDUAL),
                        ))
                        logger.info(f"Dynamic post delay computed: {dyn_post*1000:.1f} ms (was {self.post_delay*1000:.1f} ms)")
                        if 0.000 <= dyn_post <= 0.300:
                            self.post_delay = dyn_post
                    else:
                        logger.info("Dynamic post delay enabled, but integration/afterglow not ready.")
                except Exception as e:
                    logger.debug(f"Dynamic post delay unavailable: {e}. Using configured post delay {self.post_delay:.3f}s")

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
        self.pause_live_read()
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
                    # DEV MODE: Try to load cached calibration to skip calibration
                    cached_loaded = False
                    CACHE_VERSION = "1.0"  # Increment when cache format changes
                    if DEV:
                        try:
                            import json
                            from pathlib import Path
                            cache_file = Path(__file__).parent / ".dev_calibration_cache.json"
                            if cache_file.exists():
                                with open(cache_file, 'r', encoding='utf-8') as f:
                                    cache = json.load(f)

                                # Validate cache version
                                if cache.get("version") != CACHE_VERSION:
                                    logger.warning(f"Cache version mismatch: {cache.get('version')} != {CACHE_VERSION}, ignoring cache")
                                    cache_file.unlink()
                                    raise ValueError("Cache version mismatch")

                                # Load cached values
                                self.integration = cache.get("integration_time", 15)
                                self.num_scans = cache.get("num_scans", 5)
                                self.hw_state.ref_intensity = cache.get("ref_intensity", 255)
                                self.hw_state.leds_calibrated = cache.get("leds_calibrated", {ch: 180 for ch in CH_LIST})

                                # Still need wavelength data and fourier weights from hardware
                                if self.device_config["ctrl"] in DEVICES:
                                    wave_data = self.usb.read_wavelength()
                                    self.wave_min_index = wave_data.searchsorted(MIN_WAVELENGTH)
                                    self.wave_max_index = wave_data.searchsorted(MAX_WAVELENGTH)
                                    self.wave_data = wave_data[self.wave_min_index:self.wave_max_index]

                                    # Get dark noise
                                    self.dark_noise = self.usb.read_spectrum()

                                    # Read reference spectrum
                                    self.ctrl.ref_on()
                                    time.sleep(0.1)
                                    self.usb.set_integration(self.integration)
                                    self.ref_sig = self.usb.read_spectrum()
                                    self.ctrl.ref_off()

                                    # Compute Fourier weights
                                    from utils.spr_signal_processing import compute_fourier_weights
                                    self.fourier_weights = compute_fourier_weights(self.wave_data)

                                    cached_loaded = True
                                    self.calibration_status.emit(True, "")
                                    logger.info("✅ DEV MODE: Loaded cached calibration parameters")
                                    logger.info(f"   Integration: {self.integration}ms, Scans: {self.num_scans}")
                                    logger.info(f"   LED intensities: {self.hw_state.leds_calibrated}")
                        except Exception as e:
                            logger.warning(f"Failed to load dev calibration cache: {e}")
                            cached_loaded = False

                    if not cached_loaded:
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

                                # Standardize Fourier weights calculation via utility
                                self.fourier_weights = calculate_fourier_weights(len(self.wave_data))

                            # Automatically calibrate polarizer servo alignment if option is
                            # enabled
                            if self.auto_polarize and not self._c_stop.is_set():
                                self.auto_polarize = False
                                self.auto_polarization()

                            # Perform LED calibration using refactored module
                            if not (self._c_stop.is_set() or (self.ctrl is None)):
                                if self.device_config["ctrl"] in DEVICES:
                                    logger.info("Starting LED calibration...")

                                    # Perform full LED calibration
                                    # Calibrate all 4 channels (a, b, c, d) by default
                                    cal_result = perform_full_led_calibration(
                                        usb=self.usb,
                                        ctrl=self.ctrl,
                                        device_type=self.device_config["ctrl"],
                                        single_mode=False,  # Always calibrate all channels
                                        single_ch="a",  # Not used when single_mode=False
                                        integration_step=INTEGRATION_STEP,
                                        stop_flag=self._c_stop,
                                    )

                                    if not self._c_stop.is_set():
                                        # Update application state with calibration results
                                        self.integration = cal_result.integration_time
                                        self.num_scans = cal_result.num_scans
                                        self.hw_state.ref_intensity = cal_result.ref_intensity
                                        self.hw_state.leds_calibrated = cal_result.leds_calibrated
                                        self.dark_noise = cal_result.dark_noise
                                        self.ref_sig = cal_result.ref_sig
                                        self.wave_data = cal_result.wave_data
                                        self.wave_min_index = cal_result.wave_min_index
                                        self.wave_max_index = cal_result.wave_max_index
                                        self.fourier_weights = cal_result.fourier_weights
                                        self.ch_error_list = cal_result.ch_error_list

                                        # Format error message for UI
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
                                        self.calibration_status.emit(calibration_success, ch_str)

                                        # Compute spectral correction from S-mode reference
                                        spectral_correction = self._compute_spectral_correction()

                                        # Initialize or update SpectrumProcessor with spectral correction
                                        if self.spectrum_processor is None and self.fourier_weights is not None:
                                            self.spectrum_processor = SpectrumProcessor(
                                                fourier_weights=self.fourier_weights,
                                                fourier_window_size=165,
                                                spectral_correction=spectral_correction,
                                            )
                                            logger.info("SpectrumProcessor initialized with spectral correction")
                                        elif self.spectrum_processor is not None:
                                            self.spectrum_processor.spectral_correction = spectral_correction
                                            logger.info("Spectral correction updated in SpectrumProcessor")

                                        # Auto-trigger optical calibration if device doesn't have one
                                        from utils.device_integration import get_device_manager
                                        device_manager = get_device_manager()
                                        if device_manager.needs_optical_calibration():
                                            logger.info("🔄 No optical calibration found - auto-starting afterglow measurement...")
                                            try:
                                                self.ui_message_sig.emit(
                                                    "Running first-time optical calibration\n\nThis measures LED phosphor decay for accurate corrections.",
                                                    "Information",
                                                    5,
                                                )
                                            except Exception:
                                                pass
                                            # Trigger afterglow measurement in background
                                            self.measure_afterglow()

                                        # Recompute dynamic LED delay after calibration, if enabled
                                        if USE_DYNAMIC_LED_DELAY:
                                            try:
                                                if getattr(self, "afterglow_correction", None) is not None:
                                                    dyn_delay = float(self.afterglow_correction.get_optimal_led_delay(
                                                        integration_time_ms=float(self.integration),
                                                        target_residual_percent=float(LED_DELAY_TARGET_RESIDUAL),
                                                    ))
                                                else:
                                                    raise RuntimeError("AfterglowCorrection not initialized")
                                                logger.info(f"[Calib] Dynamic LED delay: {dyn_delay*1000:.1f} ms (legacy {self.led_delay*1000:.1f} ms)")
                                                if 0.005 <= dyn_delay <= 0.200:
                                                    self.led_delay = dyn_delay
                                                else:
                                                    logger.warning(f"[Calib] Dynamic delay {dyn_delay:.3f}s out of range; keeping {self.led_delay:.3f}s")
                                            except Exception as e:
                                                logger.warning(f"[Calib] Dynamic LED delay unavailable: {e}. Using legacy delay {self.led_delay:.3f}s")

                                        # Recompute dynamic post delay after calibration, if enabled
                                        if USE_DYNAMIC_POST_DELAY:
                                            try:
                                                if getattr(self, "afterglow_correction", None) is not None:
                                                    dyn_post = float(self.afterglow_correction.get_optimal_led_delay(
                                                        integration_time_ms=float(self.integration),
                                                        target_residual_percent=float(LED_DELAY_TARGET_RESIDUAL),
                                                    ))
                                                    logger.info(f"[Calib] Dynamic post delay: {dyn_post*1000:.1f} ms (legacy {self.post_delay*1000:.1f} ms)")
                                                    if 0.000 <= dyn_post <= 0.300:
                                                        self.post_delay = dyn_post
                                                else:
                                                    raise RuntimeError("AfterglowCorrection not initialized")
                                            except Exception as e:
                                                logger.debug(f"[Calib] Dynamic post delay not updated: {e}")

                                else:
                                    logger.debug("controller does not match in config")
                                    self._c_stop.set()

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
            self.pause_live_read()
            time.sleep(1)
            self.calibrated = False
            self.main_window.adv_btn.setEnabled(False)
            self._c_stop.clear()

    def full_recalibration(self: Self) -> None:
        """Recalibrate."""
        if self._c_stop.is_set():
            self.pause_live_read()
            time.sleep(1)
            self.calibrated = False
            self.main_window.adv_btn.setEnabled(False)
            self.auto_polarize = True
            self._c_stop.clear()

    def start_new_ref(self: Self, *, new_settings: bool = False) -> None:
        """Create a new reference spectrum."""
        try:
            if self.device_config["ctrl"] in DEVICES and self._c_stop.is_set():
                logger.debug("starting new reference")
                self.pause_live_read()
                time.sleep(1)
                logger.info("Status updated")
                if hasattr(self.main_window, "sidebar_spectroscopy"):
                    self.main_window.sidebar_spectroscopy.enable_controls(False)
                self.main_window.sidebar.device_widget.allow_commands(state=False)
                if new_settings:
                    try:
                        if getattr(self, "spec_adapter", None) is not None:
                            self.spec_adapter.set_integration(self.integration)
                        else:
                            self.usb.set_integration(self.integration)
                    except Exception as e:
                        logger.debug(f"HAL set_integration failed; falling back to USB: {e}")
                        with suppress(Exception):
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
            logger.info("Status updated")
            if hasattr(self.main_window, "sidebar_spectroscopy"):
                self.main_window.sidebar_spectroscopy.enable_controls(True)
            self.main_window.sidebar.device_widget.allow_commands(state=True)
            self.resume_live_read()
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
                    self.ctrl.set_intensity(ch=ch, raw_val=self.hw_state.ref_intensity[ch])
                    time.sleep(self.led_delay)
                    ref_data_sum = np.zeros_like(self.dark_noise)
                    ref_scans = REF_SCANS
                    # No idea why 75
                    if self.integration > 75:  # noqa: PLR2004
                        ref_scans = int(REF_SCANS / 2)
                    for _scan in range(ref_scans):
                        int_val = self.usb.read_intensity()
                        if int_val is None:
                            logger.error("USB disconnected during reference acquisition")
                            self._on_spec_error()
                            return
                        ref_data_single = (
                            int_val[self.wave_min_index : self.wave_max_index]
                            - self.dark_noise
                        )
                        ref_data_sum += ref_data_single
                    self.ref_sig[ch] = deepcopy(ref_data_sum / REF_SCANS)
                    self.ctrl.set_intensity(ch=ch, raw_val=self.hw_state.leds_calibrated[ch])
                    self.ctrl.turn_off_channels()
                self.ctrl.set_mode(mode="p")
                self.new_ref_done_sig.emit()
                time.sleep(0.1)
                logger.debug("new reference signal")
            except Exception as e:
                logger.exception(f"Error during new reference: {e}")

    def single_led(self: Self, led_setting: str) -> None:
        """Turn on only one LED.

        Note: This is for UI display purposes only, not used in calibration.
        Calibration always processes all 4 channels (a, b, c, d).
        """
        # This function can be removed or kept for future single-channel features
        pass

    def _compute_spectral_correction(self: Self) -> dict[str, np.ndarray]:
        """Compute per-channel spectral response correction from S-mode reference.

        Uses the S-mode reference spectrum (max transmission, no sample) to normalize
        out fiber coupling differences, LED variations, and detector non-uniformity.
        This is a flat-field correction technique that significantly improves:
        - Channel-to-channel consistency (2-5× improvement)
        - Wavelength precision, especially at red end (2-3× improvement)
        - Baseline stability by correcting for LED/fiber variations

        Returns:
            Dictionary mapping channel -> correction weight array
        """
        spectral_correction = {}

        try:
            for ch in CH_LIST:
                if ch not in self.ref_sig or len(self.ref_sig[ch]) == 0:
                    logger.warning(f"No reference spectrum available for channel {ch}")
                    continue

                ref_spectrum = self.ref_sig[ch]

                # Compute correction weights (invert to correct)
                # Add small epsilon to prevent division by zero
                epsilon = 1e-6
                weights = 1.0 / (ref_spectrum + epsilon)

                # Normalize weights so median correction is 1.0
                # This preserves count levels and dynamic range
                median_weight = np.nanmedian(weights)
                if median_weight > 0 and np.isfinite(median_weight):
                    weights = weights / median_weight
                else:
                    logger.warning(f"Invalid median weight for channel {ch}, skipping correction")
                    continue

                # Sanity check: clip extreme weights to prevent noise amplification
                # Allow 10× correction range (0.1 to 10.0)
                weights = np.clip(weights, 0.1, 10.0)

                spectral_correction[ch] = weights

                logger.info(f"Spectral correction computed for channel {ch}")
                logger.info(f"  Weight range: {weights.min():.3f} - {weights.max():.3f}")
                logger.info(f"  Median weight: {np.nanmedian(weights):.3f}")
                logger.info(f"  Mean weight: {np.nanmean(weights):.3f}")

        except Exception as e:
            logger.exception(f"Error computing spectral correction: {e}")
            return {}

        return spectral_correction

    def set_polarizer(self: Self, pos: str) -> None:
        """Move polariizer."""
        if self.ctrl is not None:
            self.pause_live_read()
            time.sleep(0.5)
            if "s" in pos or "S" in pos:
                for ch in CH_LIST:
                    self.ctrl.set_intensity(ch=ch, raw_val=self.hw_state.ref_intensity[ch])
                logger.debug(f"set to S intensities: {self.hw_state.ref_intensity}")
                set_pos = "s"
            else:
                for ch in CH_LIST:
                    self.ctrl.set_intensity(ch=ch, raw_val=self.hw_state.leds_calibrated[ch])
                logger.debug(f"set to P intensities: {self.hw_state.leds_calibrated}")
                set_pos = "p"
            self.ctrl.set_mode(mode=set_pos)
            logger.debug(f"set polarizer: {set_pos}")
            time.sleep(0.1)
            self.resume_live_read()

    # === Live Data Helpers ===
    def pause_live_read(self: Self) -> None:
        """Pause the live acquisition loop safely."""
        self._b_no_read.set()

    def resume_live_read(self: Self) -> None:
        """Resume the live acquisition loop safely."""
        if self._b_no_read.is_set():
            self._b_no_read.clear()
        if self._b_stop.is_set():
            self._b_stop.clear()

    def handle_pause(self: Self, paused: bool) -> None:
        """Handle pause/resume button from UI."""
        if paused:
            self.pause_live_read()
            # Turn off all LEDs when paused
            if self.ctrl is not None:
                try:
                    self.ctrl.all_off()
                    logger.info("Paused acquisition - LEDs off")
                except Exception as e:
                    logger.warning(f"Failed to turn off LEDs on pause: {e}")
        else:
            self.resume_live_read()
            logger.info("Resumed acquisition")

    # === Device Helpers ===
    def _read_servo_positions_decoded(self: Self) -> tuple[int, int]:
        """Read S/P servo positions from controller and decode to integers.

        Returns (s_pos, p_pos). Returns (0, 0) on failure or default values.
        """
        s_pos = 0
        p_pos = 0
        try:
            if self.ctrl is None:
                return s_pos, p_pos
            polarizer_pos = self.ctrl.servo_get()
            s_bytes = polarizer_pos.get("s", b"0000")
            p_bytes = polarizer_pos.get("p", b"0000")

            def _decode(val) -> int:
                if isinstance(val, bytes):
                    s = val.decode("utf-8", errors="ignore").strip()
                else:
                    s = str(val).strip()
                if not s or s == "0000":
                    return 0
                try:
                    return int(s)
                except Exception:
                    return 0

            s_pos = _decode(s_bytes)
            p_pos = _decode(p_bytes)
        except Exception as e:
            logger.error(f"error reading s & p from device: {e}")
        return s_pos, p_pos

    def _on_calibration_started(self: Self) -> None:
        logger.info("Status updated")
        self.main_window.sensorgram.enable_controls(data_ready=False)
        if hasattr(self.main_window, "sidebar_spectroscopy"):
            self.main_window.sidebar_spectroscopy.enable_controls(False)
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
        if self.adv_connected:
            self.main_window.adv_btn.setEnabled(True)
        current_text = "Connected"
        if current_text.endswith("Calibrating"):
            logger.info("Status updated")
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
            logger.debug("manually passing calibration - allowing live data anyway")
            self.calibrated = True

        # Initialize SpectrumProcessor now that fourier_weights are available
        if self.spectrum_processor is None and self.fourier_weights is not None:
            self.spectrum_processor = SpectrumProcessor(
                fourier_weights=self.fourier_weights,
                fourier_window_size=165,
            )
            logger.info("SpectrumProcessor initialized with Fourier fallback")

        # Initialize TemporalFilter for time-series smoothing
        if self.temporal_filter is None:
            self.temporal_filter = TemporalFilter(
                method='median',
                window_size=self.med_filt_win,
            )
            logger.debug(f"TemporalFilter initialized (method=median, window={self.med_filt_win})")

        if hasattr(self.main_window, "sidebar_spectroscopy"):
            self.main_window.sidebar_spectroscopy.enable_controls(True)
        self.main_window.sidebar.device_widget.allow_commands(True)  # noqa: FBT003
        # ✨ MODIFIED: Allow live data even if calibration fails (removed "and state" condition)
        if not self._b_kill.is_set():
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
                logger.info("Status updated")

    def _on_spec_error(self: Self) -> None:
        if self.usb is not None and self.usb.opened:
            self.disconnect_dev(knx=False)
            if not self.closing:
                show_message(
                    msg="Error: Device Disconnected!\nCheck connection and USB cable",
                    msg_type="Warning",
                )
                logger.info("Status updated")

    @Slot(dict, list, str)
    def send_to_analysis(
        self: Self,
        data_dict: dict[str, np.ndarray],
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
                # Warn user about data loss
                from PySide6.QtWidgets import QMessageBox
                warning = QMessageBox(self)
                warning.setIcon(QMessageBox.Warning)
                warning.setWindowTitle("Start Recording")
                warning.setText("Starting recording will erase all unsaved data.")
                warning.setInformativeText(
                    "To save current data before recording:\n"
                    "• Right-click on the graph\n"
                    "• Select 'Export unsaved data'\n\n"
                    "Do you want to start recording?"
                )
                warning.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
                warning.setDefaultButton(QMessageBox.Cancel)

                if warning.exec() != QMessageBox.Yes:
                    logger.debug("Recording cancelled by user")
                    return None

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
                    # Clear sensor reading buffers FIRST to ensure fresh data
                    self.clear_sensor_reading_buffers()

                    # Fully clear spectral data buffers including time arrays
                    self.channel_mgr.clear_data()

                    # Reset experiment time so new data starts at time zero
                    self.exp_start = time.time()
                    self.exp_start_perf = time.perf_counter()
                    # Also update channel manager's time references
                    self.channel_mgr.exp_start_time = self.exp_start
                    self.channel_mgr.exp_start_perf = self.exp_start_perf
                    logger.debug("Experiment time reset - recording will start at time zero")

                    # Start recording - this will reset time reference and move yellow cursor to 0
                    if self.device_config["ctrl"] != "":
                        self.main_window.sensorgram.start_recording(self.rec_dir)
                        # Save initial data after timestamps are adjusted
                        self.main_window.sensorgram.save_data(self.rec_dir)

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
        """Save recorded data using DataExporter."""
        from pathlib import Path
        from utils.data_exporter import DataExporter

        # Get experiment name from rec_dir
        rec_path = Path(self.rec_dir)
        exp_name = rec_path.name if rec_path.name else "Recording"

        # Create DataExporter (reuse from sensorgram if possible)
        exporter = DataExporter(base_dir=self.rec_dir, experiment_name=exp_name)

        if self.device_config["ctrl"] != "":
            logger.debug("saving SPR data")
            self.main_window.sensorgram.save_data(self.rec_dir)

            # Export temperature log if available
            if self.device_config["ctrl"] == "PicoP4SPR":
                try:
                    if self.temp_log is not None and not self.temp_log.empty:
                        exporter.export_temperature_log(self.temp_log)
                except Exception as e:
                    logger.error(f"Failed to export temperature log: {e}")

        if self.device_config["knx"] != "" or self.device_config["ctrl"] in [
            "EZSPR",
            "PicoEZSPR",
        ]:
            logger.debug("saving kinetic log")
            try:
                if self.log_ch1 is not None and not self.log_ch1.empty:
                    version = self.knx.version if self.knx else "1.0"
                    log_ch2 = self.log_ch2 if hasattr(self, 'log_ch2') and self.log_ch2 is not None else None
                    exporter.export_kinetic_log(self.log_ch1, log_ch2, version)
            except Exception as e:
                logger.error(f"Failed to export kinetic logs: {e}")

        # Save experiment metadata and manifest
        try:
            settings = {
                "integration_time": self.usb.integration_time if self.usb else None,
                "channels": CH_LIST,
                "temperature": self.temp if hasattr(self, 'temp') else None
            }
            exporter.save_metadata(self.device_config, settings)
            exporter.save_manifest()
        except Exception as e:
            logger.error(f"Failed to save metadata/manifest: {e}")

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
        """Main data acquisition loop - orchestrates spectrum acquisition and processing.

        This method has been refactored to pure orchestration:
        1. Check if acquisition should run
        2. Initialize on first run
        3. For each channel: acquire → process → buffer
        4. Update UI
        5. Handle errors gracefully

        All complex logic has been extracted to:
        - SpectrumProcessor (spectrum processing)
        - ChannelManager (buffer management)
        - AcquisitionService (spectrum acquisition)
        """
        first_run = True

        while not self._b_kill.is_set():
            ch = CH_LIST[0]  # For error reporting
            try:
                # Check if we should pause acquisition
                if self._should_pause_acquisition():
                    time.sleep(0.2)
                    continue

                # Initialize on first run
                if first_run:
                    self._initialize_acquisition()
                    first_run = False

                # Ensure all channels are synchronized
                self._ensure_channel_synchronization()

                # Process all channels
                active_channels = self.channel_mgr.get_active_channels()
                for ch in CH_LIST:
                    if self._b_stop.is_set():
                        break

                    # Acquire spectrum and capture timestamp immediately after hardware read
                    wavelength, acquisition_timestamp = self._process_channel_with_timing(ch, active_channels)

                    # Buffer the data point with accurate acquisition timestamp
                    self._buffer_channel_data(ch, wavelength, active_channels, acquisition_timestamp)

                # Increment buffer index after all channels processed
                self.channel_mgr.increment_buffer_index()

                # Update UI with latest data
                if not self._b_stop.is_set():
                    self._update_ui_displays()

                # Update temperature if P4SPR device
                self._update_temperature_display()

            except Exception as e:
                self._handle_acquisition_error(e, ch)

    def _should_pause_acquisition(self: Self) -> bool:
        """Check if acquisition should be paused.

        Returns:
            True if acquisition should pause, False otherwise
        """
        return (
            self._b_stop.is_set()
            or self.device_config["ctrl"] not in DEVICES
        )

    def _initialize_acquisition(self: Self) -> None:
        """Initialize acquisition on first run."""
        self.exp_start = time.time()
        self.exp_start_perf = time.perf_counter()

        # Initialize ChannelManager with experiment start time
        self.channel_mgr.reset_experiment_time()

        # Configure channel manager with current device settings
        self.channel_mgr.configure(
            device_type=self.device_config["ctrl"],
            single_mode=False,  # Always process all 4 channels
            single_channel="a",  # Not used when single_mode=False
        )

        logger.info(
            f"Acquisition initialized: device={self.device_config['ctrl']}"
        )

    def _ensure_channel_synchronization(self: Self) -> None:
        """Ensure all channel buffers are synchronized."""
        if not self.channel_mgr.check_synchronization():
            self.channel_mgr.pad_missing_values()

    def _process_channel(
        self: Self,
        channel: str,
        active_channels: list[str]
    ) -> float:
        """Acquire and process data for a single channel.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            active_channels: List of currently active channels

        Returns:
            Resonance wavelength (nm), or NaN if channel inactive/error
        """
        # Skip if channel is inactive or acquisition disabled
        if not self._should_acquire_channel(channel, active_channels):
            time.sleep(0.01)  # Brief sleep for inactive channels
            return np.nan

        # Acquire spectrum data
        int_data, trans_data = self._acquire_spectrum(channel)
        if trans_data is None:
            return np.nan

        # Store raw data
        self.int_data[channel] = int_data
        self.trans_data[channel] = trans_data

        # Process transmission spectrum to find resonance wavelength
        return self._find_resonance_wavelength(channel, trans_data)

    def _process_channel_with_timing(
        self: Self,
        channel: str,
        active_channels: list[str]
    ) -> tuple[float, float]:
        """Acquire and process data for a single channel with accurate timing.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            active_channels: List of currently active channels

        Returns:
            Tuple of (resonance_wavelength, acquisition_timestamp)
            - resonance_wavelength: Wavelength in nm, or NaN if inactive/error
            - acquisition_timestamp: Time immediately after hardware acquisition
        """
        # Skip if channel is inactive or acquisition disabled
        if not self._should_acquire_channel(channel, active_channels):
            time.sleep(0.01)  # Brief sleep for inactive channels
            return np.nan, self.channel_mgr.get_current_time()

        # Acquire spectrum data
        int_data, trans_data = self._acquire_spectrum(channel)

        # Capture timestamp immediately after hardware acquisition (before processing)
        acquisition_timestamp = self.channel_mgr.get_current_time()

        if trans_data is None:
            return np.nan, acquisition_timestamp

        # Store raw data
        self.int_data[channel] = int_data
        self.trans_data[channel] = trans_data

        # Process transmission spectrum to find resonance wavelength
        # (Processing happens AFTER timestamp, so overhead doesn't affect timing)
        wavelength = self._find_resonance_wavelength(channel, trans_data)

        return wavelength, acquisition_timestamp

    def _should_acquire_channel(
        self: Self,
        channel: str,
        active_channels: list[str]
    ) -> bool:
        """Check if channel should be acquired.

        Args:
            channel: Channel to check
            active_channels: List of active channels

        Returns:
            True if channel should be acquired
        """
        return (
            channel in active_channels
            and not self._b_no_read.is_set()
            and self.calibrated
            and self.ctrl is not None
        )

    def _acquire_spectrum(self: Self, channel: str) -> tuple:
        """Acquire spectrum for a channel.

        Args:
            channel: Channel identifier

        Returns:
            Tuple of (intensity_data, transmission_data)
        """
        if getattr(self, "acq_service", None) is None:
            logger.error("AcquisitionService not initialized")
            return None, None

        return self.acq_service.acquire_channel(
            ch=channel,
            wave_min_index=self.wave_min_index,
            wave_max_index=self.wave_max_index,
            num_scans=self.num_scans,
            led_delay=self.led_delay,
            post_delay=self.post_delay,
            dark_noise=self.dark_noise,
            ref_sig=self.ref_sig,
            wave_data=self.wave_data,
        )

    def _find_resonance_wavelength(
        self: Self,
        channel: str,
        transmission: np.ndarray
    ) -> float:
        """Find resonance wavelength from transmission spectrum.

        Args:
            channel: Channel identifier
            transmission: Transmission spectrum

        Returns:
            Resonance wavelength (nm), or NaN on error
        """
        if self._b_stop.is_set() or transmission is None:
            return np.nan

        # Use SpectrumProcessor for clean processing
        if self.spectrum_processor is not None:
            try:
                result = self.spectrum_processor.process_transmission(
                    transmission=transmission,
                    wavelengths=self.wave_data,
                    channel=channel,
                )
                return result.resonance_wavelength
            except Exception as e:
                logger.error(f"Spectrum processor error for channel {channel}: {e}")
                return np.nan
        else:
            # Fallback if processor not initialized
            logger.warning("SpectrumProcessor not initialized, using legacy Fourier method")
            return find_resonance_wavelength_fourier(
                transmission_spectrum=transmission,
                wavelengths=self.wave_data,
                fourier_weights=self.fourier_weights,
                window_size=165,
            )

    def _buffer_channel_data(
        self: Self,
        channel: str,
        wavelength: float,
        active_channels: list[str],
        acquisition_timestamp: float
    ) -> None:
        """Buffer channel data point with filtering.

        Args:
            channel: Channel identifier
            wavelength: Raw resonance wavelength (nm)
            active_channels: List of currently active channels
            acquisition_timestamp: Timestamp captured immediately after hardware acquisition
        """
        # Use the provided timestamp (captured right after hardware read)
        current_time = acquisition_timestamp

        # Apply temporal filtering for active channels (only if filter is enabled)
        if channel in active_channels and self.temporal_filter is not None and self.filt_on:
            # Get current values from ChannelManager for filtering
            # (slice to actual data length for THIS CHANNEL, excluding preallocated space)
            n = self.channel_mgr._current_length[channel]
            channel_values = self.channel_mgr.lambda_values[channel][:n]
            buffer_index = self.channel_mgr.buffer_index

            # Apply filter (with lock to prevent race condition during filter updates)
            with self._filter_lock:
                if len(channel_values) > buffer_index:
                    filtered_value = self.temporal_filter.apply(
                        values=channel_values,
                        current_index=buffer_index,
                    )
                else:
                    filtered_value = wavelength
        else:
            # Filter disabled or inactive channel - no filtering
            filtered_value = None

        # Add to ChannelManager
        self.channel_mgr.add_data_point(
            channel=channel,
            wavelength=wavelength,
            timestamp=current_time,
            filtered_value=filtered_value,
        )



    def _update_ui_displays(self: Self) -> None:
        """Update UI with latest sensorgram and spectroscopy data."""
        self.update_live_signal.emit(self.sensorgram_data())
        self.update_spec_signal.emit(self.spectroscopy_data())

    def _update_temperature_display(self: Self) -> None:
        """Update temperature display if using P4SPR-based device."""
        # PicoP4SPR and PicoEZSPR support temperature readout
        if (
            self.device_config["ctrl"] in ["PicoP4SPR", "PicoEZSPR"]
            and isinstance(self.ctrl, (PicoP4SPR, PicoEZSPR))
        ):
            self.temp_sig.emit(self.ctrl.get_temp())

    def _handle_acquisition_error(self: Self, error: Exception, channel: str) -> None:
        """Handle errors during data acquisition.

        Args:
            error: Exception that occurred
            channel: Channel being processed when error occurred
        """
        logger.exception(
            f"Error while grabbing data: {type(error)}: {error}: channel {channel}"
        )

        # Ensure buffers are synchronized after error
        self.channel_mgr.pad_missing_values()

        # Stop acquisition
        self._b_stop.set()
        logger.info("Status updated")

        # Show appropriate error message
        if isinstance(error, IndexError):
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
        """Filter data with vectorized median filtering (optimized)."""
        try:
            for ch in CH_LIST:
                n = self.channel_mgr._current_length[ch]  # Actual data length for THIS CHANNEL
                if n == 0:
                    continue

                # Work with slices of the valid data
                lambda_values = self.channel_mgr.lambda_values[ch][:n]
                lambda_times = self.channel_mgr.lambda_times[ch][:n]
                buffered_times = self.channel_mgr.buffered_times[ch][:n]

                if len(lambda_values) > 0 and len(lambda_times) > 0 and len(buffered_times) > 0:
                    # VECTORIZED median filter - much faster than loop
                    half_win = self.med_filt_win // 2
                    new_filtered = np.empty(len(lambda_values))

                    for i in range(len(lambda_values)):
                        start_idx = max(0, i - half_win)
                        end_idx = min(len(lambda_values), i + half_win + 1)
                        new_filtered[i] = np.nanmedian(lambda_values[start_idx:end_idx])

                    # Find offset to match buffered times
                    offset = 0
                    max_offset = min(len(lambda_times), len(buffered_times))
                    while offset < max_offset and lambda_times[offset] != buffered_times[0]:
                        offset += 1

                    # Only update if we found a valid offset
                    if offset < max_offset:
                        # Write directly to the preallocated buffer
                        filtered_slice = new_filtered[offset:]
                        self.channel_mgr.filtered_lambda[ch][:len(filtered_slice)] = filtered_slice
                    else:
                        logger.warning(f"Could not find matching times for channel {ch}")
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

    def sensorgram_data(self: Self) -> object:
        """Return sensorgram data (only valid data points, not preallocated space)."""
        # Get maximum data length across all channels
        max_n = max(self.channel_mgr._current_length.values()) if self.channel_mgr._current_length else 0

        sens_data = {
            # Only copy valid data per channel, not entire preallocated buffers
            "lambda_values": {ch: self.channel_mgr.lambda_values[ch][:self.channel_mgr._current_length[ch]].copy() for ch in CH_LIST},
            "lambda_times": {ch: self.channel_mgr.lambda_times[ch][:self.channel_mgr._current_length[ch]].copy() for ch in CH_LIST},
            "buffered_lambda_values": {ch: self.channel_mgr.buffered_lambda[ch][:self.channel_mgr._current_length[ch]].copy() for ch in CH_LIST},
            "filtered_lambda_values": {ch: self.channel_mgr.filtered_lambda[ch][:self.channel_mgr._current_length[ch]].copy() for ch in CH_LIST},
            "buffered_lambda_times": {ch: self.channel_mgr.buffered_times[ch][:self.channel_mgr._current_length[ch]].copy() for ch in CH_LIST},
            "filt": self.filt_on,
            "start": self.exp_start,
            "start_perf": self.exp_start_perf,
            "rec": self.recording,
        }
        return sens_data  # Already copied, no need for deepcopy

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

    def validate_existing_polarizer_positions(self) -> tuple[bool, float, int, int]:
        """Quickly validate existing polarizer positions stored in device.

        Returns:
            Tuple of (is_valid, sp_ratio, s_pos, p_pos)
        """
        try:
            logger.info("=== Quick Polarizer Validation ===")
            # Read current positions from device (decoded safely)
            s_pos, p_pos = self._read_servo_positions_decoded()

            logger.info(f"   Current stored positions: S={s_pos}, P={p_pos}")

            # Check if positions are reasonable (not defaults like 0,0 or 255,255)
            if s_pos == 0 or p_pos == 0 or s_pos == p_pos:
                logger.warning("   ⚠️ Invalid stored positions detected")
                return False, 0.0, s_pos, p_pos

            # Quick validation: measure S and P intensities
            self.ctrl.set_intensity("a", 255)
            # Use HAL to set integration; convert seconds→milliseconds
            try:
                detector = getattr(self, "spec_adapter", self.usb)
                min_sec = max(MIN_INTEGRATION / 1000.0, detector.min_integration if detector else 0.001)
                integ_ms = int(round(min_sec * 1000.0))
                if getattr(self, "spec_adapter", None) is not None:
                    self.spec_adapter.set_integration(integ_ms)
                else:
                    self.usb.set_integration(integ_ms)
            except Exception as e:
                logger.debug(f"Failed to set min integration via HAL; fallback: {e}")
                with suppress(Exception):
                    # Final fallback to legacy path with ms
                    if self.usb is not None:
                        min_sec = max(MIN_INTEGRATION / 1000.0, self.usb.min_integration)
                        self.usb.set_integration(int(round(min_sec * 1000.0)))

            # Measure S-mode (should be HIGH)
            self.ctrl.set_mode("s")
            time.sleep(0.5)
            s_reading = self.usb.read_intensity()
            if s_reading is None:
                logger.error("USB disconnected during S-mode measurement")
                return False, 0.0, s_pos, p_pos
            s_intensity = s_reading.max()

            # Measure P-mode (should be LOWER)
            self.ctrl.set_mode("p")
            time.sleep(0.5)
            p_reading = self.usb.read_intensity()
            if p_reading is None:
                logger.error("USB disconnected during P-mode measurement")
                return False, 0.0, s_pos, p_pos
            p_intensity = p_reading.max()

            # Calculate ratio
            if p_intensity == 0:
                logger.warning("   ⚠️ P-mode intensity is zero")
                return False, 0.0, s_pos, p_pos

            sp_ratio = s_intensity / p_intensity

            logger.info(f"   S-mode intensity: {s_intensity:.0f} counts")
            logger.info(f"   P-mode intensity: {p_intensity:.0f} counts")
            logger.info(f"   S/P ratio: {sp_ratio:.2f}×")

            # Validate ratio
            MIN_RATIO = 1.3
            IDEAL_RATIO = 1.5

            if sp_ratio >= MIN_RATIO:
                status = "✅ VALID" if sp_ratio >= IDEAL_RATIO else "✅ ACCEPTABLE"
                logger.info(f"   {status} - Stored positions are good")
                return True, sp_ratio, s_pos, p_pos
            else:
                logger.warning(f"   ❌ INVALID - Ratio too low (minimum: {MIN_RATIO:.2f}×)")
                return False, sp_ratio, s_pos, p_pos

        except Exception as e:
            logger.warning(f"   ⚠️ Validation failed: {e}")
            return False, 0.0, 0, 0

    def auto_polarization(self: Self, force_full_calibration: bool = False) -> None:
        """Find polarizer positions with comprehensive validation.

        Uses efficient quadrant search (13 measurements) with fallback to full sweep (33 measurements).

        Args:
            force_full_calibration: If True, skip validation and always do full sweep
        """
        from utils.servo_calibration import (
            perform_quadrant_search,
            analyze_peaks,
            verify_and_correct_positions,
            perform_full_sweep_fallback,
            perform_barrel_window_search,
        )

        # Try quick validation first unless forced to do full calibration
        if not force_full_calibration:
            is_valid, sp_ratio, s_pos, p_pos = self.validate_existing_polarizer_positions()

            if is_valid:
                logger.info("✅ POLARIZER VALIDATION SUCCESSFUL (fast mode)")
                logger.info(f"   Using stored positions: S={s_pos}, P={p_pos}")
                logger.info(f"   S/P ratio: {sp_ratio:.2f}×")
                logger.info("   Skipping full calibration sweep")
                self.ctrl.servo_set(s_pos, p_pos)
                logger.info(
                    "   Note: Validation path does NOT flash EEPROM. Positions will not persist across power cycles."
                )
                return
            else:
                logger.info("⚠️ Validation failed - proceeding with full calibration sweep")
        else:
            logger.info("🔧 Full calibration requested - skipping validation")

        # Full calibration with retry logic
        max_retries = 2
        retry_count = 0
        calibration_channel = "b"  # Default LED channel for servo calibration (can be changed in config)
        # Use calibrated LED intensity if available, otherwise start lower than max to avoid saturation
        if self.hw_state.leds_calibrated and calibration_channel in self.hw_state.leds_calibrated:
            led_intensity = self.hw_state.leds_calibrated[calibration_channel]
            logger.info(f"📊 Using calibrated LED intensity: {led_intensity}")
        else:
            led_intensity = 180  # Start at 70% to avoid immediate saturation
            logger.info(f"⚠️ No calibrated LED intensity - starting at {led_intensity}")

        # Determine polarizer type by serial number (legacy path)
        serial_number = None
        try:
            serial_number = getattr(self.usb, 'serial_number', None)
        except Exception:
            serial_number = None
        # Known barrel units (can expand or move to config later)
        BARREL_SERIALS = {"FLMT09788"}

        while retry_count < max_retries:
            try:
                if self.device_config["ctrl"] in DEVICES and self.ctrl is not None:
                    logger.info(f"=== Auto-Polarization Attempt {retry_count + 1}/{max_retries} ===")

                    # Setup hardware - LED only (integration time already set by LED calibration)
                    self.ctrl.set_intensity(calibration_channel, led_intensity)

                    # Choose calibration strategy based on polarizer type
                    is_barrel = bool(serial_number in BARREL_SERIALS)
                    if is_barrel:
                        try:
                            logger.info("🔍 Using BARREL WINDOW SEARCH (serial-based)")
                            ws = perform_barrel_window_search(self.usb, self.ctrl)
                            if ws is not None:
                                # Verify and correct (handles inversion + saturation)
                                verification = verify_and_correct_positions(
                                    self.usb,
                                    self.ctrl,
                                    ws["s_pos"],
                                    ws["p_pos"],
                                )
                                if verification is None:
                                    logger.warning("⚠️ SATURATION DETECTED during barrel verify - reducing LED intensity")
                                    led_intensity = int(led_intensity * 0.8)
                                    logger.info(f"   Reducing LED intensity to {led_intensity}")
                                    retry_count += 1
                                    continue

                                s_pos, p_pos, was_inverted = verification
                                logger.info("✅ AUTO-POLARIZATION SUCCESSFUL (barrel window)")
                                logger.info(f"   S position: {s_pos}°")
                                logger.info(f"   P position: {p_pos}°")
                                if was_inverted:
                                    logger.info("   ⚠️  Inversion corrected")

                                self.ctrl.servo_set(s_pos, p_pos)
                                time.sleep(0.2)
                                self.ctrl.flash()
                                logger.info(
                                    f"   Saved polarizer positions to EEPROM: S={s_pos}, P={p_pos}"
                                )
                                self.new_default_values = True
                                self.get_device_parameters()
                                return
                            else:
                                logger.warning("⚠️ Barrel window search returned no result - falling back to full sweep")
                        except Exception as e:
                            logger.warning(f"⚠️ Barrel window search failed: {e} - falling back to full sweep")
                    else:
                        # Try quadrant search first (faster - 13 measurements)
                        try:
                            logger.info("🔍 Attempting QUADRANT SEARCH (fast method)")
                            positions, intensities, p_pos, s_pos = perform_quadrant_search(
                                self.usb,
                                self.ctrl
                            )

                            # Analyze results with pre-determined positions
                            results = analyze_peaks(positions, intensities, self.usb, self.ctrl, p_pos, s_pos)

                            if results is not None:
                                # Verify and correct for inversion + saturation check
                                verification = verify_and_correct_positions(
                                    self.usb,
                                    self.ctrl,
                                    results["s_pos"],
                                    results["p_pos"]
                                )

                                if verification is None:
                                    logger.warning("⚠️ SATURATION DETECTED - Reducing LED intensity")
                                    # Reduce LED intensity by 20% and retry
                                    led_intensity = int(led_intensity * 0.8)
                                    logger.info(f"   Reducing LED intensity to {led_intensity}")
                                    retry_count += 1
                                    continue  # Retry with lower LED intensity

                                s_pos, p_pos, was_inverted = verification
                                sp_ratio = results["sp_ratio"]

                                logger.info("✅ AUTO-POLARIZATION SUCCESSFUL (quadrant search)")
                                logger.info(f"   S position: {s_pos}°")
                                logger.info(f"   P position: {p_pos}°")
                                logger.info(f"   S/P ratio: {sp_ratio:.2f}×")
                                logger.info(f"   Separation: {results['separation']:.0f}°")
                                if was_inverted:
                                    logger.info("   ⚠️  Inversion corrected")

                                self.ctrl.servo_set(s_pos, p_pos)
                                time.sleep(0.2)  # Wait for servo to settle
                                self.ctrl.flash()  # Save to EEPROM
                                logger.info(
                                    f"   Saved polarizer positions to EEPROM: S={s_pos}, P={p_pos}"
                                )
                                self.new_default_values = True
                                self.get_device_parameters()  # Update UI with new S/P positions
                                return  # Success - exit
                            else:
                                logger.warning("⚠️ Quadrant search validation failed - falling back to full sweep")

                        except Exception as e:
                            logger.warning(f"⚠️ Quadrant search failed: {e} - falling back to full sweep")

                    # Fallback to full sweep in utils
                    fs_results = perform_full_sweep_fallback(self.usb, self.ctrl)
                    if fs_results is None:
                        retry_count += 1
                        continue

                    s_pos = fs_results["s_pos"]; p_pos = fs_results["p_pos"]
                    self.ctrl.servo_set(s_pos, p_pos)
                    time.sleep(0.2)
                    self.ctrl.flash()
                    logger.info(
                        f"   Saved polarizer positions to EEPROM: S={s_pos}, P={p_pos}"
                    )
                    self.new_default_values = True
                    self.get_device_parameters()
                    return

            except Exception as e:
                logger.exception(f"Error during auto-polarization attempt {retry_count + 1}: {e}")
                retry_count += 1

        # All retries failed
        logger.error(f"❌ AUTO-POLARIZATION FAILED after {max_retries} attempts")
        logger.error("   Please check:")
        logger.error("   1. Polarizer is properly installed")
        logger.error("   2. Servo is responding correctly")
        logger.error("   3. LED intensity is sufficient")
        logger.error("   4. Spectrometer is working properly")
        show_message(
            "Auto-polarization failed. Please check hardware and try again.",
            msg_type="Critical"
        )

    def stop_pump(self: Self, stop_ch: str) -> None:
        """Stop a pump."""
        if self.knx is not None:
            try:
                log1 = False
                log2 = True
                self._s_stop.set()
                if stop_ch == "CH1":
                    log1 = True
                    if self.hw_state.synced:
                        log2 = True
                        self.knx.knx_stop(3)
                        self.hw_state.pump_states["CH2"] = "Off"
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
                self.hw_state.pump_states[stop_ch] = "Off"
                logger.debug("pump stopped")
                if log1:
                    self._log_event("CH1", "CH 1 Stop")
                if log2:
                    self._log_event("CH2", "CH 2 Stop")
                self._s_stop.clear()
                self.update_pump_display.emit(self.hw_state.pump_states, self.hw_state.synced)
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
                    if self.hw_state.synced:
                        log2 = True
                        self.knx.knx_start(run_rate, 3)
                        self.hw_state.pump_states["CH2"] = deepcopy(state)
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
                self.hw_state.pump_states[run_ch] = state
                if log1:
                    self._log_event("CH1", f"CH 1 {state} ({run_rate})")
                if log2:
                    self._log_event("CH2", f"CH 2 {state} ({run_rate})")
                self._s_stop.clear()
                self.update_pump_display.emit(self.hw_state.pump_states, self.hw_state.synced)
            except Exception as e:
                logger.exception(f"Error running pump: {e}")

    def three_way(self: Self, ch: str, state: object) -> None:
        """Switch a three-way valve."""
        if self.knx is not None:
            try:
                self._s_stop.set()
                if ch == "CH1":
                    if self.hw_state.synced:
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
                    if self.hw_state.synced:
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
        if self.hw_state.pump_states[ch] == "Running":
            self.run_pump(ch, rate)
            if not self.pump:
                self.flow_rate = rate / 60
                self.main_window.sensorgram.ui.flow_rate_now.setText(str(rate))

    @Slot(str, int)
    def run_button_handler(self: Self, ch: str, rate: int) -> None:
        """Run a pump."""
        if self.hw_state.pump_states[ch] == "Off":
            self.run_pump(ch, rate)
        elif self.hw_state.pump_states[ch] == "Running":
            self.stop_pump(ch)

    @Slot(str)
    def flush_button_handler(self: Self, ch: str) -> None:
        """Flush a tube."""
        if self.hw_state.pump_states[ch] == "Off":
            self.run_pump(ch, FLUSH_RATE)
        elif self.hw_state.pump_states[ch] == "Flushing":
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
            if self.hw_state.valve_states[ch_name] != fw_state:
                self.hw_state.valve_states[ch_name] = fw_state
                logger.debug(f"correcting valve state error on ch {ch}")
                self.update_valve_display.emit(self.hw_state.valve_states, self.hw_state.synced)

    @Slot(str)
    def three_way_handler(self: Self, ch: str) -> None:
        """Switch three wayy valve."""
        self.update_timer.start(5000)
        if self.hw_state.valve_states[ch] == "Waste":
            self.three_way(ch, 1)
            self.hw_state.valve_states[ch] = "Load"
        elif self.hw_state.valve_states[ch] == "Dispose":
            self.three_way(ch, 1)
            self.hw_state.valve_states[ch] = "Inject"
        elif self.hw_state.valve_states[ch] == "Inject":
            self.three_way(ch, 0)
            self.hw_state.valve_states[ch] = "Dispose"
        else:
            self.three_way(ch, 0)
            self.hw_state.valve_states[ch] = "Waste"
        if self.hw_state.synced:
            self.hw_state.valve_states["CH2"] = deepcopy(self.hw_state.valve_states["CH1"])
        self.update_valve_display.emit(self.hw_state.valve_states, self.hw_state.synced)

    @Slot(str)
    def six_port_handler(self: Self, ch: str) -> None:
        """Switch a six port valve."""
        self.update_timer.start(5000)
        inject_time: int | str = 0
        timeout_mins = 0
        if self.hw_state.valve_states[ch] in ["Load", "Waste"]:
            self.six_port(ch, 1)
            if self.hw_state.valve_states[ch] == "Load":
                self.hw_state.valve_states[ch] = "Inject"
            elif self.hw_state.valve_states[ch] == "Waste":
                self.hw_state.valve_states[ch] = "Dispose"
            inject_time = f"{(time.perf_counter() - self.exp_start_perf):.2f}"
            if ch == "CH1":
                self._log_event("CH1", "Inject sample")
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
            if (ch == "CH2") or self.hw_state.synced:
                self._log_event("CH2", "Inject sample")
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
                if self.hw_state.synced:
                    self.hw_state.valve_states["CH2"] = deepcopy(self.hw_state.valve_states["CH1"])
                else:
                    self.timer2.start(int(1000 * 60 * timeout_mins))
                self.main_window.sidebar.kinetic_widget.ui.inject_time_ch2.setText(
                    f"{inject_time}",
                )
            logger.debug(f"starting timer on {ch} for {timeout_mins} min")
        else:
            if self.hw_state.valve_states[ch] == "Inject":
                self.hw_state.valve_states[ch] = "Load"
            elif self.hw_state.valve_states[ch] == "Dispose":
                self.hw_state.valve_states[ch] = "Waste"
            self.six_port(ch, 0)
            if ch == "CH1":
                self.timer1.stop()
            if (ch == "CH2") or self.hw_state.synced:
                self.timer2.stop()
            if self.hw_state.synced:
                self.hw_state.valve_states["CH2"] = deepcopy(self.hw_state.valve_states["CH1"])
        self.update_valve_display.emit(self.hw_state.valve_states, self.hw_state.synced)

    def turn_off_six_ch1(self: Self) -> None:
        """Turn off six way valve channnel 1."""
        if self.hw_state.valve_states["CH1"] in ["Inject", "Dispose"]:
            self.six_port_handler("CH1")
            logger.debug("Auto shutoff 6P1")

    def turn_off_six_ch2(self: Self) -> None:
        """Turn off six way valve channel 2."""
        if self.hw_state.valve_states["CH2"] in ["Inject", "Dispose"]:
            self.six_port_handler("CH2")
            logger.debug("Auto shutoff 6P2")

    def sync_handler(self: Self, sync: bool) -> None:  # noqa: FBT001
        """Handle sync."""
        self.hw_state.synced = sync
        if sync:
            self.timer2.stop()
            self.sync_speed_sig.emit()
            if self.hw_state.pump_states["CH1"] == "Running":
                self.run_pump(
                    "CH2",
                    int(
                        self.main_window.sidebar.kinetic_widget.ui.run_rate_ch1.currentText(),
                    ),
                )
            elif self.hw_state.pump_states["CH1"] == "Flushing":
                self.run_pump("CH2", FLUSH_RATE)
            else:
                self.stop_pump("CH2")
            if (
                (self.hw_state.valve_states["CH2"] in ["Waste", "Dispose"])
                and (self.hw_state.valve_states["CH1"] in ["Load", "Inject"])
            ) or (
                (self.hw_state.valve_states["CH2"] in ["Load", "Inject"])
                and (self.hw_state.valve_states["CH1"] in ["Waste", "Dispose"])
            ):
                self.three_way_handler("CH2")
            if (
                (self.hw_state.valve_states["CH2"] in ["Waste", "Load"])
                and (self.hw_state.valve_states["CH1"] in ["Dispose", "Inject"])
            ) or (
                (self.hw_state.valve_states["CH2"] in ["Dispose", "Inject"])
                and (self.hw_state.valve_states["CH1"] in ["Waste", "Load"])
            ):
                self.six_port_handler("CH2")
        elif self.timer1.isActive():
            self.timer2.start(self.timer1.remainingTime())

    @Slot(list)
    def update_channel_visibility(self: Self, visible_channels: list) -> None:
        """Update which channels are visible in sensorgram based on valve position."""
        # Update checkboxes in sensorgram
        for ch in ['a', 'b', 'c', 'd']:
            checkbox = getattr(self.main_window.sensorgram.ui, f"segment_{ch.upper()}", None)
            if checkbox:
                should_be_checked = ch in visible_channels
                if checkbox.isChecked() != should_be_checked:
                    checkbox.setChecked(should_be_checked)

    def _on_advanced_smoothing_changed(self: Self, enabled: bool, mode: str, level: str) -> None:
        """Handle advanced smoothing settings change from kinetics widget."""
        logger.info(f"Advanced smoothing changed: enabled={enabled}, mode={mode}, level={level}")
        # Update sensorgram window (DataWindow instance)
        if hasattr(self.main_window, 'sensorgram') and hasattr(self.main_window.sensorgram, 'set_advanced_smoothing'):
            self.main_window.sensorgram.set_advanced_smoothing(enabled, mode, level)
        # Update spectroscopy window if it has the method
        # Update processing window if exists and has the method
        if hasattr(self.main_window, 'processing') and hasattr(self.main_window.processing, 'set_advanced_smoothing'):
            self.main_window.processing.set_advanced_smoothing(enabled, mode, level)

    def enable_sensor_reading(self: Self) -> None:
        """Enable sensor reading."""
        self._s_stop.clear()

    def clear_kin_log(self: Self) -> None:
        """Clear kinetics log."""
        self.clear_sensor_reading_buffers()
        self.log_ch1 = pd.DataFrame(columns=["timestamp", "time", "event", "flow", "temp", "dev"])
        self.log_ch2 = pd.DataFrame(columns=["timestamp", "time", "event", "flow", "temp", "dev"])

    def clear_sensor_reading_buffers(self: Self) -> None:
        """Clear sensor reading buffer."""
        self.flow_buf_1 = []
        self.temp_buf_1 = []
        self.flow_buf_2 = []
        self.temp_buf_2 = []
        self.update_sensor_display.emit(
            {"flow1": "", "temp1": "", "flow2": "", "temp2": ""},
        )
        self.temp_log = pd.DataFrame(columns=["Timestamp", "Experiment Time", "Device Temp"])
        self.update_temp_display.emit(0.0, "ctrl")

    # Note: save_temp_log and save_kinetic_log are now handled by DataExporter in save_rec_data

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
                    start = time.perf_counter()
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
                            flow_time = f"{(time.perf_counter() - self.exp_start_perf):.2f}"
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
                            self._log_event("CH1", "Sensor reading", flow=flow1_text, temp=temp1_text)
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
                            flow_time = f"{(time.perf_counter() - self.exp_start_perf):.2f}"
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
                            self._log_event("CH2", "Sensor reading", flow=flow2_text, temp=temp2_text)
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
                        self.device_config["ctrl"] in ["EZSPR", "PicoEZSPR"]  # QSPR removed
                    ) or (self.device_config["knx"] in ["KNX", "KNX2", "PicoKNX2"]):
                        temp = ""
                        try:
                            # QSPR temperature check disabled - obsolete hardware
                            if self.knx.version == "1.1":
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
                            self._log_event("CH1", "Device reading", dev=temp)
                            self._log_event("CH2", "Device reading", dev=temp)
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
                                exp_time = time.perf_counter() - self.exp_start_perf
                                time_now = dt.datetime.now(TIME_ZONE)
                                dev_timestamp = (
                                    f"{time_now.hour:02d}"
                                    f":{time_now.minute:02d}"
                                    f":{time_now.second:02d}"
                                )
                                new_row = pd.DataFrame([{
                                    "Timestamp": dev_timestamp,
                                    "Experiment Time": f"{exp_time:.2f}",
                                    "Device Temp": temp,
                                }])
                                self.temp_log = pd.concat([self.temp_log, new_row], ignore_index=True)
                                self.update_temp_display.emit(temp, "ctrl")
                        except Exception as e:
                            logger.exception(f"error geting device temp: {e}")
                    while (elapsed < self.sensor_interval) and not (
                        self._s_kill.is_set() or self._s_stop.is_set()
                    ):
                        time.sleep(0.1)
                        elapsed = time.perf_counter() - start

                except Exception as e:
                    logger.exception(f"Error during flow sensor reading: {e}")

    def save_default_values(self: Self) -> None:
        """Save default values."""
        # All controllers with detector (static + ezSPR) support EEPROM flash
        if self.device_config["ctrl"] in [
            "P4SPR",
            "PicoP4SPR",
            "EZSPR",
            "PicoEZSPR",
        ] and hasattr(self.ctrl, 'flash'):
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
            # Validate filter window size
            if filt_win < 3:
                logger.warning(f"Filter window too small ({filt_win}), using minimum of 3")
                filt_win = 3
            elif filt_win > 51:
                logger.warning(f"Filter window too large ({filt_win}), using maximum of 51")
                filt_win = 51

            with self._filter_lock:
                self.med_filt_win = self.median_window(filt_win)

        if self.main_window.active_page == "data_processing":
            self.main_window.data_processing.set_filter(
                filt_en=filt_en,
                med_filt_win=self.med_filt_win,
            )

    def set_live_filt(self: Self, filt_en: bool, filt_win: int) -> None:  # noqa: FBT001
        """Set live view filter."""
        filter_state_changed = (filt_en != self.filt_on)
        self.filt_on = filt_en

        logger.info(f"Filter {'enabled' if filt_en else 'disabled'} with window size {filt_win}")

        window_changed = False
        if filt_win != self.med_filt_win:
            # Validate filter window size
            if filt_win < 3:
                logger.warning(f"Filter window too small ({filt_win}), using minimum of 3")
                filt_win = 3
            elif filt_win > 51:
                logger.warning(f"Filter window too large ({filt_win}), using maximum of 51")
                filt_win = 51

            with self._filter_lock:
                self.med_filt_win = self.median_window(filt_win)

                # Recreate TemporalFilter with new window size
                if self.temporal_filter is not None:
                    self.temporal_filter = TemporalFilter(
                        method='median',
                        window_size=self.med_filt_win,
                    )
                    logger.debug(f"TemporalFilter updated (window={self.med_filt_win})")

                window_changed = True

        # Retroactively apply filter to all existing data when filter settings change
        if filter_state_changed or window_changed:
            logger.info(f"Filter settings changed - reprocessing all data (enabled={filt_en}, window={self.med_filt_win})")
            self.update_filtered_lambda()

            # Force immediate display update
            if self.main_window.active_page == "sensorgram":
                # Get fresh data with updated filter settings
                fresh_data = self.sensorgram_data()

                # Update the main sensorgram display immediately
                self.update_live_signal.emit(fresh_data)

                # Process Qt events to ensure the signal is handled
                QApplication.processEvents()

                logger.debug("Display updated with new filter settings")
                from PySide6.QtCore import QCoreApplication
                QCoreApplication.processEvents()

                # Now update the segment (cycle of interest) display with fresh filtered data
                self.main_window.sensorgram.quick_segment_update()
        elif self.main_window.active_page == "sensorgram":
            self.main_window.sensorgram.quick_segment_update()

    def toggle_colorblind_mode(self: Self, enabled: bool) -> None:  # noqa: FBT001
        """Toggle between standard and colorblind-friendly color palettes."""
        import settings

        if enabled:
            settings.ACTIVE_GRAPH_COLORS = settings.GRAPH_COLORS_COLORBLIND.copy()
            logger.info("Switched to colorblind-friendly palette")
        else:
            settings.ACTIVE_GRAPH_COLORS = settings.GRAPH_COLORS.copy()
            logger.info("Switched to standard palette")

        # Update all graph colors
        if hasattr(self.main_window, 'sensorgram'):
            self.main_window.sensorgram.full_segment_view.update_colors()
            self.main_window.sensorgram.SOI_view.update_colors()
        if hasattr(self.main_window, 'data_processing'):
            self.main_window.data_processing.full_segment_view.update_colors()
            self.main_window.data_processing.SOI_view.update_colors()

    def connect_advanced_menu(self: Self) -> None:
        """Connect advanced menu."""
        if self.device_config["ctrl"] in DEVICES:
            self.main_window.advanced_menu.new_parameter_sig.connect(
                self.update_advanced_params,
            )
            self.main_window.advanced_menu.get_parameter_sig.connect(
                self.get_device_parameters,
            )
            # Enable hidden afterglow measurement button in DEV builds, if available
            try:
                if DEV and hasattr(self.main_window.advanced_menu, "enable_afterglow_button"):
                    self.main_window.advanced_menu.enable_afterglow_button(True)
                # Also enable delay status display in DEV mode
                if DEV and hasattr(self.main_window.advanced_menu, "enable_delay_status"):
                    self.main_window.advanced_menu.enable_delay_status(True)
                # Connect measurement signal if present
                if hasattr(self.main_window.advanced_menu, "measure_afterglow_sig"):
                    self.main_window.advanced_menu.measure_afterglow_sig.connect(self.measure_afterglow)
                # Connect session quality monitoring toggle
                if hasattr(self.main_window.advanced_menu, "quality_monitoring_toggled"):
                    self.main_window.advanced_menu.quality_monitoring_toggled.connect(self._toggle_quality_monitoring)
                    # Set initial state
                    if hasattr(self.main_window.advanced_menu, "set_quality_monitoring_state"):
                        from settings.settings import ENABLE_SESSION_QUALITY_MONITORING
                        self.main_window.advanced_menu.set_quality_monitoring_state(ENABLE_SESSION_QUALITY_MONITORING)
            except Exception as _adv_err:
                logger.debug(f"Advanced afterglow controls not fully wired: {_adv_err}")
            self.adv_connected = True

    def get_device_parameters(self: Self) -> None:
        """Get device parameters."""
        # Only update if advanced menu exists and is connected
        if not self.adv_connected or self.main_window.advanced_menu is None:
            return

        # Get device parameters and display in advanced settings
        if self.ctrl is not None:  # QSPRController check removed - obsolete
            s_pos = 0
            p_pos = 0
            if self.device_config["ctrl"] in [
                "P4SPR",
                "PicoP4SPR",
                "EZSPR",
                "PicoEZSPR",
            ]:
                s_pos, p_pos = self._read_servo_positions_decoded()
                if s_pos == 0 and p_pos == 0:
                    logger.debug("Servo positions will display as 0 - try re-calibrating servo")
                logger.debug(f"curr s = {s_pos}, curr p = {p_pos}")
            params = {
                "led_del": self.led_delay,
                "ht_req": self.ht_req,
                "sens_interval": self.sensor_interval,
                "intg_time": self.integration,
                "num_scans": self.num_scans,
                "led_int_a": self.hw_state.leds_calibrated["a"],
                "led_int_b": self.hw_state.leds_calibrated["b"],
                "led_int_c": self.hw_state.leds_calibrated["c"],
                "led_int_d": self.hw_state.leds_calibrated["d"],
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
            # Refresh status line again after display
            try:
                cal_file = None
                try:
                    optical_cfg = (self.conf or {}).get('optical_calibration', {}) if hasattr(self, 'conf') else {}
                    cal_file = optical_cfg.get('optical_calibration_file') or (self.conf or {}).get('optical_calibration_file')
                except Exception:
                    pass
                self.adv_delay_status_sig.emit(
                    float(getattr(self, "led_delay", LED_DELAY)),
                    float(getattr(self, "post_delay", LED_POST_DELAY)),
                    bool(USE_DYNAMIC_LED_DELAY),
                    bool(USE_DYNAMIC_POST_DELAY),
                    str(cal_file) if cal_file else "",
                )
            except Exception:
                pass

    def update_advanced_params(self: Self, params: dict[str, str]) -> None:
        """Update advanced paramerters."""
        if self.adv_connected:
            paused = False
            try:
                if False:  # QSPR disabled - obsolete hardware
                    # self.device_config["ctrl"] == "QSPR" and isinstance(
                    #     self.ctrl,
                    #     QSPRController,
                    # ):
                    p_string = (
                        f"{params['s_pos']},{params['p_pos']},{params['up_time']},{params['down_time']},"
                        f"{params['adj_time']},{params['debounce']},{params['start_interval']}"
                    )
                    self.ctrl.set_parameters(p_string)
                elif self.ctrl is not None:  # QSPRController check removed - obsolete
                    self.pause()
                    paused = True
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
                    # Recompute dynamic LED delay on integration change
                    if USE_DYNAMIC_LED_DELAY:
                        try:
                            if getattr(self, "afterglow_correction", None) is not None:
                                dyn_delay = float(self.afterglow_correction.get_optimal_led_delay(
                                    integration_time_ms=float(self.integration),
                                    target_residual_percent=float(LED_DELAY_TARGET_RESIDUAL),
                                ))
                            else:
                                raise RuntimeError("AfterglowCorrection not initialized")
                            logger.info(f"[UI] Dynamic LED delay: {dyn_delay*1000:.1f} ms (legacy {self.led_delay*1000:.1f} ms)")
                            if 0.005 <= dyn_delay <= 0.200:
                                self.led_delay = dyn_delay
                        except Exception as e:
                            logger.debug(f"[UI] Dynamic LED delay not updated: {e}")
                    # Recompute dynamic post delay on integration change
                    if USE_DYNAMIC_POST_DELAY:
                        try:
                            if getattr(self, "afterglow_correction", None) is not None:
                                dyn_post = float(self.afterglow_correction.get_optimal_led_delay(
                                    integration_time_ms=float(self.integration),
                                    target_residual_percent=float(LED_DELAY_TARGET_RESIDUAL),
                                ))
                                logger.info(f"[UI] Dynamic post delay: {dyn_post*1000:.1f} ms (legacy {self.post_delay*1000:.1f} ms)")
                                if 0.000 <= dyn_post <= 0.300:
                                    self.post_delay = dyn_post
                        except Exception as e:
                            logger.debug(f"[UI] Dynamic post delay not updated: {e}")
                    # Emit updated delay status to Advanced UI
                    try:
                        cal_file = None
                        try:
                            optical_cfg = (self.conf or {}).get('optical_calibration', {}) if hasattr(self, 'conf') else {}
                            cal_file = optical_cfg.get('optical_calibration_file') or (self.conf or {}).get('optical_calibration_file')
                        except Exception:
                            pass
                        self.adv_delay_status_sig.emit(
                            float(getattr(self, "led_delay", LED_DELAY)),
                            float(getattr(self, "post_delay", LED_POST_DELAY)),
                            bool(USE_DYNAMIC_LED_DELAY),
                            bool(USE_DYNAMIC_POST_DELAY),
                            str(cal_file) if cal_file else "",
                        )
                    except Exception:
                        pass
                    try:
                        if getattr(self, "spec_adapter", None) is not None:
                            self.spec_adapter.set_integration(new_intg)
                        else:
                            self.usb.set_integration(new_intg)
                    except Exception as e:
                        logger.debug(f"HAL set_integration failed; falling back to USB: {e}")
                        with suppress(Exception):
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
                        if self.hw_state.leds_calibrated[ch] != new_led_ints[ch]:
                            logger.info(f"Updating LED {ch.upper()}: {self.hw_state.leds_calibrated[ch]}→{new_led_ints[ch]}")
                        self.hw_state.leds_calibrated[ch] = new_led_ints[ch]
                        self.ctrl.set_intensity(ch=ch, raw_val=new_led_ints[ch])
                        time.sleep(0.1)
                        self.ctrl.turn_off_channels()
                        time.sleep(0.1)

                    # Update polarizer servo position if needed
                    # ✨ FIX: Wrap servo_get in try-except to prevent freeze on timeout
                    try:
                        current_servo_positions = self.ctrl.servo_get()
                        # ✨ FIX: Decode bytes to string before converting to int
                        s_bytes = current_servo_positions["s"]
                        p_bytes = current_servo_positions["p"]
                        if isinstance(s_bytes, bytes):
                            old_s = int(s_bytes.decode('utf-8').strip())
                        else:
                            old_s = int(str(s_bytes).strip())
                        if isinstance(p_bytes, bytes):
                            old_p = int(p_bytes.decode('utf-8').strip())
                        else:
                            old_p = int(str(p_bytes).strip())
                    except Exception as e:
                        logger.warning(f"Could not read current servo positions: {e}, using defaults")
                        old_s = 0
                        old_p = 0

                    # Robust parsing of manual S/P entries with clamping
                    def _safe_int(val: object) -> int | None:
                        try:
                            s = str(val).strip()
                            if s == "" or s.lower() == "none":
                                return None
                            return int(float(s))  # allow "45.0" or numeric strings
                        except Exception:
                            return None

                    new_s = _safe_int(params.get("s_pos"))
                    new_p = _safe_int(params.get("p_pos"))

                    # Only attempt servo update when both values are valid
                    if new_s is not None and new_p is not None:
                        # Clamp to a safe mechanical range
                        new_s = max(0, min(180, new_s))
                        new_p = max(0, min(180, new_p))
                        if old_s != new_s or old_p != new_p:
                            logger.info(f"Updating servo positions: S {old_s}→{new_s}, P {old_p}→{new_p}")

                            # Set the servo positions
                            self.ctrl.servo_set(s=new_s, p=new_p)
                            time.sleep(0.3)  # Allow servos to settle before verification

                            # Verify and correct inversion if detected (non-QSPR path)
                            try:
                                from utils.servo_calibration import verify_and_correct_positions
                                verification = verify_and_correct_positions(self.usb, self.ctrl, new_s, new_p)
                                if verification is not None:
                                    vs, vp, was_inverted = verification
                                    if was_inverted and (vs != new_s or vp != new_p):
                                        logger.info(f"   Applied inversion correction → S={vs}, P={vp}")
                                        self.ctrl.servo_set(s=vs, p=vp)
                                        new_s, new_p = vs, vp
                                        time.sleep(0.3)  # Allow servos to settle after correction
                            except Exception as _verr:
                                logger.debug(f"Advanced S/P verify skipped: {_verr}")

                            # Flash EEPROM to persist servo positions
                            logger.info(f"💾 Flashing EEPROM to save S={new_s}, P={new_p}...")
                            logger.info(f"   This will make the positions persist across power cycles")
                            try:
                                flash_result = self.ctrl.flash()
                                if flash_result:
                                    logger.info(f"✅ EEPROM flash successful - S/P persisted: {new_s}/{new_p}")
                                    logger.info(f"   The device will now remember these positions even after power off/on")
                                else:
                                    logger.error(f"❌ EEPROM flash FAILED - S/P may not persist across power cycles!")
                                    logger.error(f"   The device will revert to old values (likely 30/120) when powered off")
                                    logger.error(f"   Check serial connection and device firmware")
                            except Exception as flash_err:
                                logger.error(f"❌ EEPROM flash error: {flash_err}")
                                logger.error(f"   Servo positions set temporarily but NOT saved to EEPROM")
                            time.sleep(0.3)  # Wait for flash to complete
                            self.get_device_parameters()  # Refresh UI after saving
                        else:
                            logger.debug(f"Servo positions unchanged: S={new_s}, P={new_p}")

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

                    if paused:
                        self.resume()
                    # Disable automatic new reference - manual only!

            except Exception as e:
                logger.exception(f"Error while updating advanced parameters: {e}")
            finally:
                # Always resume if we paused, even on error
                if paused:
                    self.resume()
                    logger.debug("Resumed acquisition after advanced parameter update")

    def _toggle_quality_monitoring(self: Self, enabled: bool) -> None:
        """Toggle session-based FWHM quality monitoring.

        Args:
            enabled: True to enable quality monitoring, False to disable
        """
        try:
            from settings import settings
            # Update the setting dynamically
            settings.ENABLE_SESSION_QUALITY_MONITORING = enabled

            if enabled:
                # Initialize quality monitor if not already done
                if self.quality_monitor is None and self.usb is not None:
                    from utils.device_integration import get_device_directory
                    from utils.session_quality_monitor import SessionQualityMonitor
                    from settings.settings import (
                        FWHM_EXCELLENT_THRESHOLD_NM,
                        FWHM_GOOD_THRESHOLD_NM,
                        QC_WAVELENGTH_MIN_NM,
                        QC_WAVELENGTH_MAX_NM,
                        QC_DEGRADATION_ALERT_THRESHOLD,
                        QC_MAX_SESSION_HISTORY,
                    )

                    device_dir = get_device_directory(self.usb)
                    if device_dir:
                        self.quality_monitor = SessionQualityMonitor(
                            device_directory=device_dir,
                            excellent_threshold_nm=FWHM_EXCELLENT_THRESHOLD_NM,
                            good_threshold_nm=FWHM_GOOD_THRESHOLD_NM,
                            valid_wavelength_min_nm=QC_WAVELENGTH_MIN_NM,
                            valid_wavelength_max_nm=QC_WAVELENGTH_MAX_NM,
                            degradation_alert_threshold=QC_DEGRADATION_ALERT_THRESHOLD,
                            max_session_history=QC_MAX_SESSION_HISTORY,
                        )
                        logger.info(f"✅ Session quality monitoring ENABLED: {device_dir.name}")
                    else:
                        logger.warning("⚠️  Cannot enable quality monitoring: no device directory")
                        if hasattr(self.main_window.advanced_menu, "set_quality_monitoring_state"):
                            self.main_window.advanced_menu.set_quality_monitoring_state(False)
                        return
                else:
                    logger.info("✅ Session quality monitoring ENABLED")
            else:
                # Disable but keep the monitor instance
                logger.info("⚠️  Session quality monitoring DISABLED")

        except Exception as e:
            logger.error(f"❌ Failed to toggle quality monitoring: {e}")
            # Revert UI state on error
            if hasattr(self.main_window.advanced_menu, "set_quality_monitoring_state"):
                self.main_window.advanced_menu.set_quality_monitoring_state(not enabled)

    def measure_afterglow(self: Self) -> None:
        """Handle user-triggered optical afterglow calibration.

        Currently a guarded stub: pauses live read, informs the user,
        and resumes. Full calibration workflow can be implemented here.
        """
        try:
            if not DEV:
                # Provide a small hint in non-DEV builds
                try:
                    self.adv_status_text_sig.emit("Afterglow calibration is a DEV feature.")
                except Exception:
                    pass
                return

            if self.ctrl is None or self.usb is None:
                show_message(
                    msg="Device not connected. Connect controller and spectrometer first.",
                    msg_type="Warning",
                )
                return

            # Immediate user feedback on main thread
            try:
                self.ui_message_sig.emit(
                    "Afterglow calibration starting…",
                    "Information",
                    3,
                )
            except Exception:
                pass
            try:
                self.adv_status_text_sig.emit("Starting afterglow calibration…")
            except Exception:
                pass

            # Launch in background thread to avoid UI freeze
            import threading

            def _run_afterglow() -> None:
                from utils.afterglow_calibration import run_afterglow_calibration

                try:
                    self.pause_live_read()
                    time.sleep(0.2)

                    # Notify via main-thread UI signal (guard if source deleted)
                    try:
                        self.ui_message_sig.emit(
                            "Afterglow calibration started\n\nMeasuring LED decay across integration times.",
                            "Information",
                            5,
                        )
                    except Exception:
                        pass
                    try:
                        self.adv_status_text_sig.emit("Afterglow calibration running…")
                    except Exception:
                        pass

                    # Use parameters consistent with new software defaults
                    # Grid favors coverage while keeping acquisition short
                    integration_grid = [10.0, 25.0, 40.0, 55.0, 70.0, 85.0]
                    # Ensure within configured limits
                    from settings import MIN_INTEGRATION, MAX_INTEGRATION
                    integration_grid = [
                        float(max(MIN_INTEGRATION, min(MAX_INTEGRATION, x))) for x in integration_grid
                    ]

                    # LED intensities (use calibrated P-mode intensities if available)
                    led_ints = getattr(self.hw_state, "leds_calibrated", None)

                    data = run_afterglow_calibration(
                        ctrl=self.ctrl,
                        usb=self.usb,
                        wave_min_index=self.wave_min_index,
                        wave_max_index=self.wave_max_index,
                        channels=CH_LIST,
                        integration_grid_ms=integration_grid,
                        pre_on_duration_s=max(0.20, float(self.led_delay)),
                        acquisition_duration_ms=250,
                        settle_delay_s=0.10,
                        led_intensities=led_ints,
                    )

                    # Save to device-specific directory
                    from utils.device_integration import (
                        get_device_manager,
                        save_optical_calibration_result
                    )

                    device_manager = get_device_manager()

                    if device_manager.current_device_serial is None:
                        logger.error("❌ No device set - cannot save optical calibration")
                        try:
                            self.ui_message_sig.emit(
                                "Error: No device detected. Cannot save calibration.",
                                "Error",
                                5,
                            )
                        except Exception:
                            pass
                        return

                    device_dir = device_manager.current_device_dir
                    out_path = device_dir / "optical_calibration.json"

                    import json
                    with out_path.open("w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)

                    # Update device configuration
                    save_optical_calibration_result(out_path)

                    logger.info(f"✅ Optical calibration saved to device directory")
                    logger.info(f"   Device: {device_manager.current_device_serial}")
                    logger.info(f"   File: {out_path}")

                    # Load into active model
                    try:
                        self.afterglow_correction = AfterglowCorrection(out_path)
                        logger.info(f"[Afterglow] Calibration saved: {out_path}")
                        try:
                            import os
                            done_msg = f"Afterglow calibration completed — saved: {os.path.basename(str(out_path))}"
                        except Exception:
                            done_msg = f"Afterglow calibration completed — saved: {out_path}"
                        try:
                            self.adv_status_text_sig.emit(done_msg)
                        except Exception:
                            pass
                        try:
                            self.ui_message_sig.emit(
                                f"Afterglow calibration completed\n\nSaved file:\n{out_path}",
                                "Information",
                                7,
                            )
                        except Exception:
                            pass
                    except Exception as e:
                        logger.warning(f"[Afterglow] Could not load saved calibration: {e}")

                    # Optionally update dynamic LED delay if feature enabled
                    try:
                        if USE_DYNAMIC_LED_DELAY and getattr(self, "afterglow_correction", None) is not None:
                            dyn_delay = float(self.afterglow_correction.get_optimal_led_delay(
                                integration_time_ms=float(self.integration),
                                target_residual_percent=float(LED_DELAY_TARGET_RESIDUAL),
                            ))
                            if 0.005 <= dyn_delay <= 0.200:
                                logger.info(
                                    f"[Afterglow] Dynamic LED delay updated: {dyn_delay*1000:.1f} ms"
                                )
                                self.led_delay = dyn_delay
                    except Exception as e:
                        logger.debug(f"Afterglow dynamic delay refresh skipped: {e}")
                    # Optionally update dynamic post delay if feature enabled
                    try:
                        if USE_DYNAMIC_POST_DELAY and getattr(self, "afterglow_correction", None) is not None:
                            dyn_post = float(self.afterglow_correction.get_optimal_led_delay(
                                integration_time_ms=float(self.integration),
                                target_residual_percent=float(LED_DELAY_TARGET_RESIDUAL),
                            ))
                            if 0.000 <= dyn_post <= 0.300:
                                logger.info(
                                    f"[Afterglow] Dynamic post delay updated: {dyn_post*1000:.1f} ms"
                                )
                                self.post_delay = dyn_post
                    except Exception as e:
                        logger.debug(f"Afterglow dynamic post delay refresh skipped: {e}")
                    # Refresh Advanced dialog status line with new delays and calibration file
                    try:
                        cal_file = None
                        try:
                            optical_cfg = (self.conf or {}).get('optical_calibration', {}) if hasattr(self, 'conf') else {}
                            cal_file = optical_cfg.get('optical_calibration_file') or (self.conf or {}).get('optical_calibration_file')
                        except Exception:
                            pass
                        self.adv_delay_status_sig.emit(
                            float(getattr(self, "led_delay", LED_DELAY)),
                            float(getattr(self, "post_delay", LED_POST_DELAY)),
                            bool(USE_DYNAMIC_LED_DELAY),
                            bool(USE_DYNAMIC_POST_DELAY),
                            str(cal_file) if cal_file else "",
                        )
                    except Exception:
                        pass
                except Exception as e:
                    logger.exception(f"Afterglow calibration failed: {e}")
                    # Notify failure on main thread
                    try:
                        self.ui_message_sig.emit(f"Afterglow calibration failed: {e}", "Warning", 0)
                    except Exception:
                        pass
                    try:
                        self.adv_status_text_sig.emit("Afterglow calibration failed. See logs.")
                    except Exception:
                        pass
                finally:
                    self.resume_live_read()

            threading.Thread(target=_run_afterglow, daemon=True).start()

        except Exception as e:
            logger.exception(f"Error in afterglow calibration handler: {e}")

    def clear_data(self: Self) -> None:
        """Clear data."""
        self.pause()
        time.sleep(0.5)

        # Clear ChannelManager
        self.channel_mgr.clear_data()

        # Clear other state variables
        self.ignore_warnings = {ch: False for ch in CH_LIST}
        self.no_sig_count = {ch: 0 for ch in CH_LIST}

        self.set_start()
        self.clear_kin_log()
        if self.recording:
            self.recording_on()
        self.resume()

    def connect_dev(self: Self) -> None:
        """Connect a device - follows same path as autoconnect at startup."""
        if self.ctrl is None or self.knx is None or self.pump is None:
            logger.info("Status updated")

            # Use threaded connection like autoconnect does at startup
            # This ensures the same connection path is followed
            if self._con_tr.is_alive():
                logger.warning("Connection thread already running, waiting for it to complete")
                self._con_tr.join(timeout=5.0)

            # Create and start connection thread (same as startup)
            self._con_tr = threading.Thread(target=self.connection_thread)
            self._con_tr.start()

            # Wait for connection to complete
            self._con_tr.join(timeout=10.0)

            # Open/initialize the devices (same as startup via connected signal)
            # But call directly since we're already in main thread
            self.open_device()

            logger.info("Manual device connection completed")
        else:
            logger.debug("Already connected!")

    def stop(self: Self, *, knx: bool = True) -> None:
        """Stop."""
        self._c_stop.set()
        self._b_stop.set()
        if (self.knx is not None) and knx:
            self.knx.stop_kinetic()
            self.hw_state.pump_states["CH1"] = "Off"
            self.hw_state.pump_states["CH2"] = "Off"
        self._s_stop.set()
        if self.recording:
            self.rec_timer.stop()
            self.recording_on()
        time.sleep(0.5)

    def crt_control_handler(self: Self, command: str) -> None:
        """Crt control handler - QSPR cartridge control disabled (obsolete hardware)."""
        # QSPR cartridge control disabled
        pass

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
        logger.info("Status updated")
        if isinstance(self.ctrl, PicoEZSPR):  # QSPRController removed - obsolete
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
        logger.info("Status updated")
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
        try:
            logger.info("Status updated")
            # Status bar removed
        except:
            pass

        try:
            if self.recording:
                self.recording_on()
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")

        try:
            self.main_window.sidebar.device_widget.allow_commands(False)  # noqa: FBT003
        except:
            pass

        if self._con_tr.is_alive():
            self._con_tr.join(0.1)

        try:
            self.stop(knx=knx)
        except Exception as e:
            logger.error(f"Error in stop(): {e}")

        self.calibrated = False
        time.sleep(0.5)

        # Close USB spectrometer first (independent of ctrl)
        if self.usb is not None:
            try:
                logger.debug("closing usb")
                self.usb.close()
            except Exception as e:
                logger.error(f"Error closing USB: {e}")

        # Close controller
        if (self.ctrl is not None) and ctrl:
            self.calibrated = False
            try:
                logger.debug("closing device")
                self.ctrl.stop()
            except Exception as e:
                logger.error(f"Error stopping ctrl: {e}")

            try:
                self.ctrl.close()
            except Exception as e:
                logger.error(f"Error closing ctrl: {e}")
            finally:
                self.ctrl = None

        # Close kinetics controller
        if (self.knx is not None) and knx:
            try:
                self.knx_reset_ui.emit()
            except:
                pass

            try:
                self.knx.close()
            except Exception as e:
                logger.error(f"Error closing knx: {e}")
            finally:
                self.knx = None

        # Close pump
        if self.pump and pump:
            try:
                with suppress(FTDIError):
                    self.pump.send_command(0x41, b"V16.667,1R")
            except Exception as e:
                logger.error(f"Error closing pump: {e}")
            finally:
                self.pump = None

        if not ((self.ctrl is None) and (self.knx is None)):
            logger.debug(f"No manual close for ctrl {self.ctrl} and knx {self.knx}")

        try:
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
        except Exception as e:
            logger.error(f"Error updating UI after disconnect: {e}")

    def close(self: Self) -> bool:
        """Close the app."""
        self.closing = True
        try:
            self.disconnect_dev()
        except Exception as e:
            logger.error(f"Error during disconnect_dev in close(): {e}")

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

        try:
            self.rec_timer.stop()
        except Exception as e:
            logger.error(f"Error stopping rec_timer: {e}")

        return super().close()

    def _emergency_cleanup(self: Self) -> None:
        """Emergency cleanup for unexpected exits (called by atexit)."""
        if hasattr(self, 'closing') and self.closing:
            return  # Normal close already happened

        logger.warning("Emergency cleanup triggered - forcing resource release")

        # Force close all hardware connections without waiting
        try:
            if hasattr(self, 'ctrl') and self.ctrl is not None:
                try:
                    self.ctrl.close()
                except Exception as e:
                    logger.error(f"Emergency cleanup - ctrl.close() failed: {e}")
        except:
            pass

        try:
            if hasattr(self, 'usb') and self.usb is not None:
                try:
                    self.usb.close()
                except Exception as e:
                    logger.error(f"Emergency cleanup - usb.close() failed: {e}")
        except:
            pass

        try:
            if hasattr(self, 'knx') and self.knx is not None:
                try:
                    self.knx.close()
                except Exception as e:
                    logger.error(f"Emergency cleanup - knx.close() failed: {e}")
        except:
            pass

        logger.info("Emergency cleanup completed")

    def __del__(self: Self) -> None:
        """Destructor to ensure resources are cleaned up."""
        try:
            if not self.closing:
                logger.warning("__del__ called without proper close - forcing cleanup")
                self._emergency_cleanup()
        except:
            pass

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
    # Suppress Qt warning messages BEFORE QApplication init
    os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.*=false"
    os.environ["QT_ASSUME_STDERR_HAS_CONSOLE"] = "1"

    dtnow = dt.datetime.now(TIME_ZONE)
    logger.info("========== Starting Affinite Instruments Application ==========")
    logger.info(
        f"{SW_VERSION}-{dtnow.year}/{dtnow.month}/{dtnow.day}-"
        f"{dtnow.hour:02d}{dtnow.minute:02d}",
    )

    _affinite_app = QApplication(sys.argv)

    # Apply modern theme system
    if MODERN_THEME_AVAILABLE:
        logger.info("✨ Applying modern UI theme...")
        apply_modern_theme(_affinite_app)
        logger.info("✅ Modern theme applied successfully")
    else:
        # Fallback: Apply centralized UI theme (legacy)
        UIStyleManager.apply_app_theme(_affinite_app)

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
