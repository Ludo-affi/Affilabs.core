"""Main application module for Affinite Instruments SPR system."""

from __future__ import annotations

import asyncio
import csv
import datetime as dt
import faulthandler
import sys
import threading
import time
from asyncio import create_task
from contextlib import suppress
from copy import deepcopy
from pathlib import Path
from types import TracebackType
from typing import Any, cast
try:
    from typing import Self  # Python 3.11+
except ImportError:
    from typing_extensions import Self  # Python < 3.11

import numpy as np
import serial
from PySide6.QtCore import QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication
import qasync
from scipy.fft import dst, idct
from scipy.signal import find_peaks, peak_prominences, peak_widths
from scipy.stats import linregress

from settings import (
    CH_LIST,
    DARK_NOISE_SCANS,
    DEV,
    DEVICES,
    EZ_CH_LIST,
    FLUSH_RATE,
    LED_DELAY,
    MAX_INTEGRATION,
    MAX_READ_TIME,
    MAX_WAVELENGTH,
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
    SW_VERSION,
    TIME_ZONE,
)
from utils.cavro_pump_manager import CavroPumpManager, PumpAddress
from utils.controller import KineticController, PicoEZSPR, PicoP4SPR  # PicoKNX2 disabled (obsolete)
from utils.data_buffer_manager import DataBufferManager
from utils.data_io_manager import DataIOManager
from utils.kinetic_manager import KineticManager
from utils.kinetic_operations import KineticOperations
from utils.recording_manager import RecordingManager
from utils.spr_data_acquisition import SPRDataAcquisition
from utils.parameter_manager import ParameterManager
from utils.ui_state_manager import UIStateManager
from utils.hardware_manager import HardwareManager
from utils.thread_manager import ThreadManager
from widgets.message import show_message
from utils.logger import logger
from utils.spr_calibrator import SPRCalibrator
from utils.spr_data_processor import SPRDataProcessor
from utils.usb4000_adapter import USB4000  # HAL-based USB4000 adapter
from utils.config_manager import ConfigurationManager
from widgets.mainwindow import MainWindow
from widgets.datawindow import Segment, DataDict
from widgets.message import show_message
from widgets.priming import PrimingWindow

# HAL-based pump controller
try:
    from utils.affi_pump_controller_adapter import PumpController
    from utils.hal.affi_pump_hal import AffiPumpError as FTDIError
except ImportError:
    class FTDIError(Exception):
        """FTDI pump error stub."""
    PumpController = None


# === APPLICATION CONSTANTS ===
# Calibration constants - extracted from magic numbers
COARSE_ADJUSTMENT = 20  # LED intensity adjustment step for rough calibration
MEDIUM_ADJUSTMENT = 5   # LED intensity adjustment step for medium calibration
FINE_ADJUSTMENT = 1     # LED intensity adjustment step for fine calibration
TEMP_CHECK_MIN = 5      # Minimum valid temperature (°C)
TEMP_CHECK_MAX = 75     # Maximum valid temperature (°C)
TEMP_AVG_WINDOW = 5     # Window for temperature averaging
MIN_LED_INTENSITY = 1   # Minimum LED intensity value
MAX_LED_INTENSITY = 255 # Maximum LED intensity value
INTEGRATION_STEP_THRESHOLD = 50  # Threshold for changing dark noise scan count

# Timing constants - extracted from magic numbers throughout code
LED_STABILIZATION_DELAY = 0.4    # Time for LED to stabilize after intensity change
HARDWARE_PAUSE_DELAY = 0.5       # General hardware operation pause
CALIBRATION_DELAY = 1.0          # Delay during calibration steps
VALVE_UPDATE_TIMEOUT = 5000      # Timer interval for valve state updates (ms)
INTEGRATION_THRESHOLD = 75       # Threshold for integration time adjustments

# Hardware operation constants
PUMP_STOP_ATTEMPTS = 3           # Number of attempts to stop pump before giving up
TEMPERATURE_READ_INTERVAL = 1000 # Temperature reading interval (ms)
SPECTRO_READ_TIMEOUT = 2.0       # Timeout for spectrometer reading
DEFAULT_FLOW_RATE = 100          # Default pump flow rate (μL/min)


class AffiniteApp(QApplication):
    """Main application class for Affinite Instruments SPR system."""

    # Signals
    calibration_started = Signal()
    calibration_status = Signal(bool, str)
    calibration_progress = Signal(int, str)  # (step_number, step_description)
    new_ref_done_sig = Signal()
    raise_error = Signal(str)
    update_live_signal = Signal(object)
    update_spec_signal = Signal(dict)
    temp_sig = Signal(float)
    update_sensor_display = Signal(dict)
    update_temp_display = Signal(object, str)
    update_pump_display = Signal(dict, bool)
    update_valve_display = Signal(dict, bool)
    sync_speed_sig = Signal()
    knx_reset_ui = Signal()

    def __init__(self) -> None:
        """Initialize the application."""
        super().__init__(sys.argv)
        
        # Initialize main window
        self.main_window = MainWindow(self)
        self.main_window.show()
        
        # Configuration Manager (centralized configuration management)
        self.config = ConfigurationManager()
        self.config.initialize_defaults()
        
        # Device hardware instances  
        self.ctrl: PicoP4SPR | PicoEZSPR | None = None
        self.knx: KineticController | PicoEZSPR | None = None  # PicoKNX2 disabled (obsolete)
        self.pump = None
        self.usb: USB4000 | None = None

        # Helper: kinetic operations builder (constructed on demand)
        self._kin_ops: KineticOperations | None = None
        self._data_acq: SPRDataAcquisition | None = None
        self._param_mgr: ParameterManager | None = None
        self._hw_mgr: HardwareManager | None = None
        
        # Calibration state
        self.calibrated = False
        self.auto_polarize = False
        self.new_default_values = False
        
        # Thread control flags
        self._b_kill = threading.Event()
        self._b_stop = threading.Event()
        self._b_no_read = threading.Event()
        self._c_kill = threading.Event()
        self._c_stop = threading.Event()
        self._s_kill = threading.Event()
        self._s_stop = threading.Event()
        
        # Set initial stop states
        self._b_stop.set()
        self._c_stop.set()
        
        # Calibration data (now using config manager for primary storage)
        self.wave_min_index = 0
        self.wave_max_index = 0
        self.num_scans = 1
        self.leds_calibrated: dict[str, int] = {ch: 0 for ch in CH_LIST}
        self.ref_sig: dict[str, np.ndarray | None] = {ch: None for ch in CH_LIST}
        self.ch_error_list: list[str] = []
        
        # Data buffer manager (centralized buffer management)
        self.data_buffers = DataBufferManager(CH_LIST)
        
        # Direct references to buffer dictionaries for backward compatibility
        self.lambda_values = self.data_buffers.lambda_values
        self.lambda_times = self.data_buffers.lambda_times  
        self.filtered_lambda = self.data_buffers.filtered_lambda
        self.buffered_lambda = self.data_buffers.buffered_lambda
        self.buffered_times = self.data_buffers.buffered_times
        self.int_data = self.data_buffers.int_data
        self.trans_data = self.data_buffers.trans_data
        
        # Data processing
        self.filt_on = False
        self.med_filt_win = 11
        self.proc_filt_win = 11
        self.filt_buffer_index = 0
        
        # Data processor (initialized after calibration with wave_data and fourier_weights)
        self.data_processor: SPRDataProcessor | None = None
        
        # Calibrator (initialized after hardware connection)
        self.calibrator: SPRCalibrator | None = None
        
        # Data I/O Manager (initialized immediately)
        self.data_io = DataIOManager()
        
        # Single channel mode
        self.single_mode = False
        self.single_ch = "x"
        
        # Timing
        self.exp_start = time.time()
        self.led_delay = LED_DELAY
        self.ht_req = 0.5
        self.sensor_interval = 10
        
        # Recording (synced with RecordingManager)
        self.recording = False
        self.rec_dir = ""
        self.rec_timer = QTimer()
        self.rec_timer.timeout.connect(self.save_rec_data)
        
        # Initialize recording manager after main window is available
        self._init_recording_manager()
        
        # Initialize UI state manager after main window is available
        self._init_ui_state_manager()
        
        # Sync recording state with manager
        self._sync_recording_state()
        
        # Temperature logging (now managed by config manager)
        self.temp = 0.0
        
        # Kinetics (now managed by config manager)  
        self.pump_states: dict[str, str] = {"CH1": "Off", "CH2": "Off"}
        self.valve_states: dict[str, str] = {"CH1": "Waste", "CH2": "Waste"}
        self.kinetic_tasks: set = set()
        
        # Pump manager (initialized after hardware connection)
        self.pump_manager: CavroPumpManager | None = None
        
        # Kinetic manager (initialized after KNX hardware connection)
        self.kinetic_manager: KineticManager | None = None
        
        # Recording manager (initialized after main window setup)
        self.recording_manager: RecordingManager | None = None
        
        # UI state manager (initialized after main window setup)
        self.ui_state_manager: UIStateManager | None = None
        
        # DEPRECATED: These are now handled by kinetic_manager
        # Kept temporarily for backward compatibility with log export
        self.log_ch1: dict[str, list] = {
            "timestamps": [], "times": [], "events": [], 
            "flow": [], "temp": [], "dev": []
        }
        self.log_ch2: dict[str, list] = {
            "timestamps": [], "times": [], "events": [], 
            "flow": [], "temp": [], "dev": []
        }
        
        # Timers
        self.timer1 = QTimer()
        self.timer1.timeout.connect(self.turn_off_six_ch1)
        self.timer2 = QTimer()
        self.timer2.timeout.connect(self.turn_off_six_ch2)
        self.update_timer = QTimer()
        
        # Advanced settings
        self.adv_connected = False
        
        # Error tracking
        self.ignore_warnings: dict[str, bool] = {ch: False for ch in CH_LIST}
        self.no_sig_count: dict[str, int] = {ch: 0 for ch in CH_LIST}
        
        # Closing flag
        self.closing = False
        
        # Start background threads - delegated to ThreadManager
        self._init_thread_manager()
        
        # Set up all signal connections
        self._setup_signal_connections()
        
        logger.info("AffiniteApp initialized")

    def _setup_signal_connections(self) -> None:
        """Set up all signal-slot connections for the application."""
        # Core application signals
        self.calibration_started.connect(self._on_calibration_started)
        self.calibration_status.connect(self._on_calibration_status)
        self.new_ref_done_sig.connect(self.new_ref_done)
        self.raise_error.connect(self.error_handler)
        
        # Data update signals
        self.update_live_signal.connect(self.main_window.sensorgram.update_data)
        self.update_spec_signal.connect(self.main_window.spectroscopy.update_data)
        self.temp_sig.connect(self.update_internal_temp)
        
        # UI widget connections
        self._setup_kinetic_widget_connections()
        self._setup_device_widget_connections()

    def _setup_kinetic_widget_connections(self) -> None:
        """Set up kinetic widget specific signal connections."""
        sidebar = self.main_window.sidebar
        kw = getattr(sidebar, "kinetic_widget", None)
        if kw is not None:
            # Display update signals
            self.update_sensor_display.connect(kw.update_readings)
            self.update_pump_display.connect(kw.update_pump_ui)
            self.update_valve_display.connect(kw.update_valve_ui)
            
            # Control signals
            kw.run_sig.connect(self.run_button_handler)
            kw.change_speed_sig.connect(self.speed_change_handler)
            kw.flush_sig.connect(self.flush_button_handler)
            kw.three_way_sig.connect(self.three_way_handler)
            kw.six_port_sig.connect(self.six_port_handler)
            kw.sync_sig.connect(self.sync_handler)

    def _setup_device_widget_connections(self) -> None:
        """Set up device widget specific signal connections."""
        sidebar = self.main_window.sidebar
        dw = getattr(sidebar, "device_widget", None)
        if dw is not None:
            self.update_temp_display.connect(dw.update_temp)

    # ========================================
    # CONFIGURATION PROPERTIES (Backward Compatibility)
    # ========================================
    
    @property
    def device_config(self) -> dict[str, str | None]:
        """Get device configuration as dictionary (backward compatibility)."""
        return self.config.get_device_config_dict()
    
    @property
    def wave_data(self) -> np.ndarray:
        """Get wavelength calibration data."""
        return self.config.calibration.wave_data or np.array([])
    
    @wave_data.setter
    def wave_data(self, value: np.ndarray) -> None:
        """Set wavelength calibration data."""
        self.config.calibration.wave_data = value
    
    @property
    def integration(self) -> int:
        """Get integration time."""
        return self.config.calibration.integration
    
    @integration.setter  
    def integration(self, value: int) -> None:
        """Set integration time."""
        self.config.calibration.integration = value
    
    @property
    def ref_intensity(self) -> dict[str, int]:
        """Get reference intensity values."""
        return self.config.calibration.ref_intensity
    
    @ref_intensity.setter
    def ref_intensity(self, value: dict[str, int]) -> None:
        """Set reference intensity values."""
        self.config.calibration.ref_intensity = value
    
    @property
    def dark_noise(self) -> np.ndarray:
        """Get dark noise calibration data."""
        return self.config.calibration.dark_noise or np.array([])
    
    @dark_noise.setter
    def dark_noise(self, value: np.ndarray) -> None:
        """Set dark noise calibration data."""
        self.config.calibration.dark_noise = value
    
    @property
    def fourier_weights(self) -> np.ndarray:
        """Get Fourier transform weights."""
        return self.config.calibration.fourier_weights or np.array([])
    
    @fourier_weights.setter
    def fourier_weights(self, value: np.ndarray) -> None:
        """Set Fourier transform weights."""
        self.config.calibration.fourier_weights = value
    
    @property
    def temp_log(self) -> dict[str, list]:
        """Get temperature log as dictionary (backward compatibility)."""
        return self.config.get_temp_log_dict()
    
    @property
    def flow_rate(self) -> float:
        """Get kinetic flow rate."""
        return float(self.config.kinetic.flow_rate)
    
    @flow_rate.setter
    def flow_rate(self, value: float) -> None:
        """Set kinetic flow rate."""
        self.config.set_flow_rate(int(value))
    
    @property
    def recording(self) -> bool:
        """Get recording state."""
        return self.config.kinetic.recording
    
    @recording.setter
    def recording(self, value: bool) -> None:
        """Set recording state."""
        self.config.set_recording_state(value)
    
    @property
    def synced(self) -> bool:
        """Get sync state."""
        return self.config.kinetic.synced
    
    @synced.setter
    def synced(self, value: bool) -> None:
        """Set sync state."""
        self.config.set_sync_state(value)
    
    @property
    def filt_on(self) -> bool:
        """Get data filtering state."""
        return self.config.ui.filt_on
    
    @filt_on.setter
    def filt_on(self, value: bool) -> None:
        """Set data filtering state."""
        self.config.set_filter_state(value)

    # ========================================
    # HARDWARE CONNECTION & DEVICE MANAGEMENT
    # ========================================

    def connection_thread(self) -> None:
        """Hardware connection thread - delegated to HardwareManager."""
        try:
            logger.debug("Connection thread started")
            
            # Hardware discovery and connection process
            time.sleep(1)  # Simulate connection time
            
            # Open devices after connection
            self.open_device()
            
        except Exception as e:
            self._handle_error("connection thread", e, show_user=False)
            if self.ui_state_manager:
                self.ui_state_manager.set_connection_state(connected=False)

    def get_current_device_config(self) -> None:
        """Update device configuration - delegated to HardwareManager."""
        try:
            hw_mgr = self._get_hw_mgr()
            hw_mgr.get_current_device_config()
            # Trigger UI callback if needed
            if hasattr(self.main_window, 'on_device_config'):
                self.main_window.on_device_config(self.device_config)
        except Exception as e:
            self._handle_error("device config update", e, show_user=False)

    def open_device(self) -> None:
        """Open connection to devices - delegated to HardwareManager."""
        if self._con_tr.is_alive() and threading.current_thread() != self._con_tr:
            self.main_window.ui.status.setText(
                "Connection Error: Check USB cables & drivers",
            )
            self._con_tr.join(0.5)
        
        try:
            hw_mgr = self._get_hw_mgr()
            hw_mgr.get_current_device_config()
            
            if self.ctrl is None and self.knx is None:
                logger.debug("no device")
                self.stop()
                self.ctrl = None
                self.knx = None
            else:
                logger.debug("start")
                self.startup()
                
                # Initialize hardware managers
                success, errors = hw_mgr.initialize_hardware_managers()
                if not success:
                    logger.warning(f"Hardware manager initialization issues: {errors}")
                else:
                    # Sync manager references back to main app
                    self.pump_manager = hw_mgr.pump_manager
                    self.kinetic_manager = hw_mgr.kinetic_manager
                    self.calibrator = hw_mgr.calibrator
                
                # Setup UI widgets
                hw_mgr.setup_ui_widgets()
                
                # Setup kinetic widget sync if available
                if (hasattr(self.main_window.sidebar, 'kinetic_widget') 
                    and self.main_window.sidebar.kinetic_widget is not None):
                    self.main_window.sidebar.kinetic_widget.set_sync(prompt=False)
        except Exception as e:
            logger.exception(f"Error opening device: {e}")
            if self.ui_state_manager:
                self.ui_state_manager.set_initialization_error_state()

    # ========================================
    # EVENT HANDLERS & SIGNAL CALLBACKS
    # ========================================

    def _on_pump_state_changed(self, address: int, description: str) -> None:
        """Handle pump state changes from pump manager."""
        try:
            # Map pump address to channel name
            ch_name = "CH1" if address == PumpAddress.PUMP_1 else "CH2"
            
            # Update internal state
            if "Running" in description or "Flowing" in description:
                self.pump_states[ch_name] = "Running"
            elif "Stopped" in description or description == "Stopped":
                self.pump_states[ch_name] = "Off"
            else:
                self.pump_states[ch_name] = description
            
            # Emit signal to update UI
            if hasattr(self, 'update_pump_display'):
                self.update_pump_display.emit(self.pump_states, self.synced)
            
            logger.debug(f"Pump {ch_name} state: {description}")
        except Exception as e:
            logger.exception(f"Error handling pump state change: {e}")
    
    def _on_pump_error(self, address: int, error: str) -> None:
        """Handle pump errors from pump manager."""
        try:
            ch_name = "CH1" if address == PumpAddress.PUMP_1 else "CH2"
            logger.error(f"Pump {ch_name} error: {error}")
            show_message(f"Pump {ch_name} Error: {error}", msg_type="Warning")
        except Exception as e:
            logger.exception(f"Error handling pump error: {e}")
    
    def _on_valve_state_changed(self, channel: str, position_name: str) -> None:
        """Handle valve state changes from kinetic manager."""
        try:
            self.valve_states[channel] = position_name
            logger.debug(f"Valve {channel} state: {position_name}")
            # propagate to UI
            self.update_valve_display.emit(self.valve_states, self.synced)
        except Exception as e:
            logger.exception(f"Error handling valve state change: {e}")
    
    def _on_sensor_reading(self, readings: dict) -> None:
        """Handle sensor readings from kinetic manager."""
        try:
            # Update UI with sensor readings
            # readings dict has keys: "temp1", "temp2" (no flow keys)
            self.update_sensor_display.emit(readings)
        except Exception as e:
            logger.exception(f"Error handling sensor reading: {e}")
    
    def _on_device_temp_updated(self, temperature: str, source: str) -> None:
        """Handle device temperature updates from kinetic manager."""
        try:
            logger.debug(f"Device temp ({source}): {temperature}°C")
            # Update UI if needed
        except Exception as e:
            logger.exception(f"Error handling device temp update: {e}")
    
    def _on_injection_started(self, channel: str, exp_time: float) -> None:
        """Handle injection start from kinetic manager."""
        try:
            logger.info(f"Injection started on {channel} at {exp_time:.2f}s")
            # Update inject time labels in kinetics UI if present
            kw = getattr(self.main_window.sidebar, "kinetic_widget", None)
            if kw is not None:
                if channel == "CH1" and hasattr(kw.ui, "inject_time_ch1"):
                    kw.ui.inject_time_ch1.setText(f"{exp_time:.2f}")
                if channel == "CH2" and hasattr(kw.ui, "inject_time_ch2"):
                    kw.ui.inject_time_ch2.setText(f"{exp_time:.2f}")
        except Exception as e:
            logger.exception(f"Error handling injection start: {e}")
    
    def _on_injection_ended(self, channel: str) -> None:
        """Handle injection end from kinetic manager."""
        try:
            logger.info(f"Injection ended on {channel}")
        except Exception as e:
            logger.exception(f"Error handling injection end: {e}")
    
    def _on_kinetic_error(self, channel: str, error_message: str) -> None:
        """Handle kinetic errors from kinetic manager."""
        try:
            logger.error(f"Kinetic {channel} error: {error_message}")
            show_message(f"Kinetic {channel} Error: {error_message}", msg_type="Warning")
        except Exception as e:
            logger.exception(f"Error handling kinetic error: {e}")

    # ========================================
    # KINETIC OPERATIONS & PUMP CONTROL
    # ========================================

    @Slot()
    def prime(self: Any) -> None:
        """Start a priming sequence."""
        if self.pump and self.knx:
            priming_window = PrimingWindow(self.pump, self.knx, self)
            # priming_window.accepted.connect(self.quick_calibration)
            priming_window.show()

    @Slot()
    def handle_regen_button(self: Any) -> None:
        """Handle the regenerate button being pressed."""
        task = create_task(self.regenerate())
        self.kinetic_tasks.add(task)
        task.add_done_callback(self.kinetic_tasks.discard)

    async def regenerate(self: Any) -> None:
        """Regenerate via KineticOperations (no flow sensor)."""
        try:
            contact_time = float(self.main_window.advanced_menu.ui.contact_time.text())
        except Exception as e:
            logger.exception(f"Invalid contact time: {e}")
            show_message(f"Invalid contact time: {e}", msg_type="Warning")
            return
        kin = self._get_kin_ops()
        await kin.regenerate(contact_time_s=contact_time, flow_rate_ml_min=self.flow_rate * 60)

    @Slot()
    def handle_flush_button(self: Any) -> None:
        """Handle the flush button being pressed."""
        task = create_task(self.flush())
        self.kinetic_tasks.add(task)
        task.add_done_callback(self.kinetic_tasks.discard)

    async def flush(self: Any) -> None:
        """Flush via KineticOperations (no flow sensor)."""
        kin = self._get_kin_ops()
        await kin.flush(flow_rate_ml_min=self.flow_rate * 60)

    @Slot()
    def handle_inject_button(self: Any) -> None:
        """Handle the inject button being pressed."""
        if self.main_window.sensorgram.ui.inject_button.text() == "Inject":
            task = create_task(self.inject())
            self.kinetic_tasks.add(task)
            task.add_done_callback(self.kinetic_tasks.discard)
        else:
            self.cancel_injection()

    async def inject(self: Any) -> None:
        """Start an injection via KineticOperations (no flow sensor)."""
        if self.flow_rate <= 0:
            logger.warning("Cannot inject with zero flow rate")
            show_message("Please set a flow rate first", msg_type="Warning")
            return
        
        try:
            injection_time = 80 / self.flow_rate
            kin = self._get_kin_ops()
            await kin.inject(flow_rate_ml_min=self.flow_rate * 60, injection_time_s=injection_time)
        except ZeroDivisionError:
            logger.error("Division by zero in injection time calculation")
            return
        except Exception as e:
            logger.exception(f"Error during injection: {e}")
            show_message(f"Injection error: {e}", msg_type="Warning")

    def cancel_injection(self: Any) -> None:
        """Cancel a currently ongoing injection (close valves, stop pumps)."""
        self.main_window.sensorgram.cancel_progress_bar()
        for task in list(self.kinetic_tasks):
            task.cancel()
        kin = self._get_kin_ops()
        kin.cancel_injection()
        logger.info("Injection cancelled")

    # ========================================
    # MANAGER FACTORY METHODS
    # ========================================

    # -- Helper: KineticOperations orchestrator --
    def _get_kin_ops(self) -> KineticOperations:
        """Build or return a KineticOperations orchestrator instance."""
        def _warn(msg: str) -> None:
            show_message(msg, msg_type="Warning")
        # Rebuild if missing or dependencies changed
        if (
            self._kin_ops is None
            or self._kin_ops.pump_manager is not self.pump_manager
            or self._kin_ops.kinetic_manager is not self.kinetic_manager
            or self._kin_ops.knx is not self.knx
        ):
            self._kin_ops = KineticOperations(
                pump_manager=self.pump_manager,
                kinetic_manager=self.kinetic_manager,
                knx=self.knx,
                start_progress_bar=self.main_window.sensorgram.start_progress_bar,
                show_message=_warn,
                set_inject_enabled=self.main_window.sensorgram.set_inject_enabled,
                new_segment=self.main_window.sensorgram.new_segment,
                set_flow_rate_now=self.main_window.sensorgram.set_flow_rate_now,
                update_pump_display=lambda states, synced: self.update_pump_display.emit(states, synced),
                update_valve_display=lambda states, synced: self.update_valve_display.emit(states, synced),
            )
        return self._kin_ops

    def _get_data_acq(self) -> SPRDataAcquisition:
        """Build or return an SPRDataAcquisition instance."""
        # Rebuild if missing or dependencies changed
        if (
            self._data_acq is None
            or self._data_acq.ctrl is not self.ctrl
            or self._data_acq.usb is not self.usb
            or self._data_acq.data_processor is not self.data_processor
        ):
            self._data_acq = SPRDataAcquisition(
                # Hardware references
                ctrl=self.ctrl,
                usb=self.usb,
                data_processor=self.data_processor,
                # Data storage references
                lambda_values=self.lambda_values,
                lambda_times=self.lambda_times,
                filtered_lambda=self.filtered_lambda,
                buffered_lambda=self.buffered_lambda,
                buffered_times=self.buffered_times,
                int_data=self.int_data,
                trans_data=self.trans_data,
                ref_sig=self.ref_sig,
                wave_data=self.wave_data,
                # Configuration
                device_config=self.device_config,
                wave_min_index=self.wave_min_index,
                wave_max_index=self.wave_max_index,
                num_scans=self.num_scans,
                led_delay=self.led_delay,
                med_filt_win=self.med_filt_win,
                dark_noise=self.dark_noise,
                # State management
                _b_kill=self._b_kill,
                _b_stop=self._b_stop,
                _b_no_read=self._b_no_read,
                # UI callbacks
                update_live_signal=self.update_live_signal,
                update_spec_signal=self.update_spec_signal,
                temp_sig=self.temp_sig,
                raise_error=self.raise_error,
                set_status_text=self.ui_state_manager.get_status_callback() if self.ui_state_manager else lambda text: None,
            )
            # Set configuration state
            self._data_acq.set_configuration(
                single_mode=self.single_mode,
                single_ch=self.single_ch,
                calibrated=self.calibrated,
                filt_on=self.filt_on,
                recording=self.recording,
                med_filt_win=self.med_filt_win,
            )
        return self._data_acq

    def _get_param_mgr(self) -> ParameterManager:
        """Build or return a ParameterManager instance."""
        # Rebuild if missing or dependencies changed
        if (
            self._param_mgr is None
            or self._param_mgr.ctrl is not self.ctrl
            or self._param_mgr.usb is not self.usb
            or self._param_mgr.knx is not self.knx
        ):
            self._param_mgr = ParameterManager(
                # Hardware references
                ctrl=self.ctrl,
                usb=self.usb,
                knx=self.knx,
                # Configuration state
                device_config=self.device_config,
                leds_calibrated=self.leds_calibrated,
                # Current parameter values
                led_delay=self.led_delay,
                ht_req=self.ht_req,
                sensor_interval=self.sensor_interval,
                integration=self.integration,
                num_scans=self.num_scans,
                # Callbacks for state management
                pause_acquisition=self.pause,
                resume_acquisition=self.resume,
                # UI callbacks
                display_settings=lambda params: (
                    self.main_window.advanced_menu.display_settings(params)
                    if hasattr(self.main_window, 'advanced_menu') 
                    and self.main_window.advanced_menu is not None
                    else None
                ),
            )
        return self._param_mgr

    def _get_hw_mgr(self) -> HardwareManager:
        """Build or return a HardwareManager instance."""
        # Rebuild if missing or dependencies changed
        if (
            self._hw_mgr is None
            or self._hw_mgr.ctrl is not self.ctrl
            or self._hw_mgr.usb is not self.usb
            or self._hw_mgr.knx is not self.knx
            or self._hw_mgr.pump is not self.pump
        ):
            self._hw_mgr = HardwareManager(
                # Hardware state references
                ctrl=self.ctrl,
                usb=self.usb,
                knx=self.knx,
                pump=self.pump,
                # Manager references
                pump_manager=self.pump_manager,
                kinetic_manager=self.kinetic_manager,
                calibrator=self.calibrator,
                # Configuration
                device_config=self.device_config,
                # State flags
                _c_stop=self._c_stop,
                exp_start=self.exp_start,
                # UI callbacks
                update_device_display=lambda text: self.main_window.ui.device.setText(text),
                update_status=self.ui_state_manager.get_status_callback() if self.ui_state_manager else lambda text: None,
                setup_device_widget=lambda ctrl, knx, pump: (
                    self.main_window.sidebar.device_widget.setup(ctrl, knx, pump)
                    if hasattr(self.main_window.sidebar, 'device_widget')
                    and self.main_window.sidebar.device_widget is not None
                    else None
                ),
                setup_kinetic_widget=lambda ctrl, knx: (
                    self.main_window.sidebar.kinetic_widget.setup(ctrl, knx)
                    if hasattr(self.main_window.sidebar, 'kinetic_widget')
                    and self.main_window.sidebar.kinetic_widget is not None
                    else None
                ),
                # Signal callbacks
                pump_state_changed=lambda states, synced: self.update_pump_display.emit(states, synced),
                valve_state_changed=lambda states, synced: self.update_valve_display.emit(states, synced),
                sensor_reading_updated=lambda readings: self.update_sensor_display.emit(readings),
                temp_display_updated=lambda temp: self.update_temp_display.emit(temp),
                calibration_progress=lambda progress, msg: self.calibration_progress.emit(progress),
                on_kinetic_error=lambda ch, msg: (show_message(f"Kinetic {ch} Error: {msg}", msg_type="Warning"), None)[1],
                on_pump_error=lambda ch, msg: (show_message(f"Pump {ch} Error: {msg}", msg_type="Warning"), None)[1],
            )
        return self._hw_mgr

    def _init_thread_manager(self) -> None:
        """Initialize ThreadManager for background thread coordination."""
        try:
            self.thread_manager = ThreadManager(
                data_acquisition_target=self._grab_data,
                calibration_target=self.calibrate,
                data_kill_flag=self._b_kill,
                calibration_kill_flag=self._c_kill,
                sensor_kill_flag=self._s_kill,  # Keep flag for compatibility
                status_callback=self.ui_state_manager.get_status_callback() if self.ui_state_manager else lambda text: None,
            )
            self.thread_manager.start_threads()
        except Exception as e:
            logger.exception(f"Error initializing thread manager: {e}")

    def _init_recording_manager(self) -> None:
        """Initialize RecordingManager for recording coordination."""
        try:
            self.recording_manager = RecordingManager(
                main_window=self.main_window,
                rec_timer=self.rec_timer,
                data_io=self.data_io,
            )
        except Exception as e:
            logger.exception(f"Error initializing recording manager: {e}")

    def _init_ui_state_manager(self) -> None:
        """Initialize UIStateManager for UI state coordination."""
        try:
            self.ui_state_manager = UIStateManager(main_window=self.main_window)
        except Exception as e:
            logger.exception(f"Error initializing UI state manager: {e}")

    def _sync_recording_state(self) -> None:
        """Sync recording state between main app and RecordingManager."""
        if self.recording_manager:
            state = self.recording_manager.get_recording_state()
            self.recording = state["recording"]
            self.rec_dir = state["rec_dir"]

    @Slot()
    def change_flow_rate(self: Any) -> None:
        """Change flow rate based on user input."""
        try:
            text = self.main_window.sensorgram.ui.flow_rate.text()
            self.main_window.sensorgram.ui.flow_rate.clear()
            
            # Convert from ml/min to ml/sec
            v = float(text) / 60
            self.flow_rate = abs(v)
            
            # Update display
            self.main_window.sensorgram.set_flow_rate_now(text)
            
            if self.pump_manager:
                if self.flow_rate > 0:
                    # Set flow rate using pump manager (expects ml/min)
                    rate_ml_per_min = float(text)
                    direction_forward = v > 0
                    
                    # Start flow on both pumps
                    self.pump_manager.start_flow(
                        PumpAddress.BROADCAST,
                        rate_ml_per_min,
                        direction_forward
                    )
                    
                    logger.info(f"Flow rate set to {rate_ml_per_min} ml/min")
                else:
                    # Stop pumps
                    self.pump_manager.stop()
                    self.main_window.sensorgram.set_flow_rate_now("0")
                    logger.info("Flow stopped")
            else:
                logger.warning("Change flow rate called but pump manager not available")
                
        except ValueError as e:
            logger.error(f"Invalid flow rate value: {e}")
            show_message(f"Invalid flow rate: {e}", msg_type="Warning")
        except Exception as e:
            logger.exception(f"Error changing flow rate: {e}")
            show_message(f"Flow rate error: {e}", msg_type="Warning")

    @Slot()
    def initialize_pumps(self: Any) -> None:
        """Initialize the pumps using kinetic operations."""
        try:
            kin = self._get_kin_ops()
            kin.initialize_pumps()
        except Exception as e:
            logger.exception(f"Error initializing pumps: {e}")
            show_message(f"Pump initialization error: {e}", msg_type="Warning")

    def usb_ok(self: Any) -> bool:
        """Check if usb is connected."""
        return (
            self.ctrl is None
            or self.device_config["ctrl"]
            not in ["PicoP4SPR", "PicoEZSPR"]  # EZSPR disabled (obsolete)
            or self.usb.spec is not None
        )

    @Slot()
    def set_start(self: Any) -> None:
        """Set recording start time."""
        start_time = time.time()
        time_diff = start_time - self.exp_start
        self.exp_start = start_time
        # Use data buffer manager for time shifting
        self.data_buffers.shift_time_reference(time_diff)
        self.main_window.sensorgram.reload_segments(time_diff)

    def startup(self: Any) -> None:
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

    def calibrate(self) -> None:
        """Main calibration loop - delegates to SPRCalibrator."""
        self._b_no_read.set()
        time.sleep(1)
        
        while not self._c_kill.is_set():
            time.sleep(0.01)
            
            if not self._c_stop.is_set() and (self.ctrl is not None) and self.usb_ok():
                self.ignore_warnings = {ch: False for ch in CH_LIST}
                self.no_sig_count = {ch: 0 for ch in CH_LIST}
                
                if self.calibrated:
                    self.calibration_status.emit(True, "")
                    self._c_stop.set()
                    logger.debug("Already calibrated")
                else:
                    logger.debug("=== Starting calibration sequence ===")
                    self.calibration_started.emit()
                    
                    try:
                        # Ensure calibrator is initialized
                        if self.calibrator is None:
                            device_type = self.device_config.get("ctrl", "") or ""
                            self.calibrator = SPRCalibrator(
                                ctrl=self.ctrl,
                                usb=self.usb,
                                device_type=device_type,
                                stop_flag=self._c_stop,
                            )
                            self.calibrator.set_progress_callback(self.calibration_progress.emit)
                        
                        # Run full calibration using the calibrator
                        auto_polarize_callback = None
                        if self.auto_polarize:
                            self.auto_polarize = False
                            auto_polarize_callback = self.auto_polarization
                        
                        calibration_success, ch_error_str = self.calibrator.run_full_calibration(
                            auto_polarize=auto_polarize_callback is not None,
                            auto_polarize_callback=auto_polarize_callback,
                        )
                        
                        # Sync calibration state back to main
                        self.wave_min_index = self.calibrator.state.wave_min_index
                        self.wave_max_index = self.calibrator.state.wave_max_index
                        # Update configuration from calibrator state
                        self.config.update_calibration_from_state(self.calibrator.state)
                        self.fourier_weights = self.calibrator.state.fourier_weights
                        self.num_scans = self.calibrator.state.num_scans
                        self.leds_calibrated = self.calibrator.state.leds_calibrated.copy()
                        self.ref_sig = self.calibrator.state.ref_sig.copy()
                        self.ch_error_list = self.calibrator.state.ch_error_list.copy()
                        
                        # Update calibration status
                        if not self._c_stop.is_set():
                            self.calibration_status.emit(calibration_success, ch_error_str)
                        
                        # Determine which channels were calibrated
                        ch_list = CH_LIST
                        if self.single_mode:
                            ch_list = [self.single_ch]
                        elif self.device_config["ctrl"] in ["PicoEZSPR"]:  # EZSPR disabled (obsolete)
                            ch_list = EZ_CH_LIST
                        
                        # Log calibration results to file
                        if self.calibrator:
                            self.calibrator.log_calibration_results(
                                success=calibration_success,
                                error_channels=ch_error_str,
                                calibrated_channels=ch_list,
                                device_knx=self.device_config.get("knx", "") or "",
                            )
                        
                        # Create data processor from calibrated wavelength data
                        if calibration_success and self.calibrator:
                            self.data_processor = self.calibrator.create_data_processor(
                                med_filt_win=self.med_filt_win
                            )
                        
                        self._c_stop.set()
                        logger.debug("=== Calibration sequence complete ===")

                    except Exception as e:
                        logger.exception(f"Device error during calibration: {e}, type: {type(e)}")
                        self._c_stop.set()
                        if self.ui_state_manager:
                            self.ui_state_manager.set_advanced_settings_enabled(True)
                        
                        if isinstance(e, serial.SerialException):
                            self.raise_error.emit("ctrl")
            else:
                time.sleep(0.2)

    def quick_calibration(self) -> None:
        """Calibrate quickly."""
        if self._c_stop.is_set():
            self._b_no_read.set()
            time.sleep(1)
            self.calibrated = False
            self.main_window.ui.adv_btn.setEnabled(False)
            self._c_stop.clear()

    def full_recalibration(self: Any) -> None:
        """Recalibrate."""
        if self._c_stop.is_set():
            self._b_no_read.set()
            time.sleep(1)
            self.calibrated = False
            self.main_window.ui.adv_btn.setEnabled(False)
            self.auto_polarize = True
            self._c_stop.clear()

    def start_new_ref(self: Any, *, new_settings: bool = False) -> None:
        """Create a new reference spectrum."""
        try:
            if self.device_config["ctrl"] in DEVICES and self._c_stop.is_set():
                logger.debug("starting new reference")
                self._b_no_read.set()
                time.sleep(1)
                
                # Delegate new reference start UI state to UIStateManager
                if self.ui_state_manager:
                    self.ui_state_manager.set_new_reference_state(starting=True)
                
                if new_settings:
                    self.usb.set_integration(self.integration)
                self._new_sig_tr = threading.Thread(target=self.new_ref_thread)
                self._new_sig_tr.start()
                show_message(msg="New reference started", auto_close_time=5)
        except Exception as e:
            logger.exception(f"Error starting new reference thread: {e}")

    def new_ref_done(self: Any) -> None:
        """Finilize new reference spectrum."""
        try:
            logger.debug("done new reference")
            if self._new_sig_tr.is_alive():
                self._new_sig_tr.join(0.1)
            
            # Delegate new reference completion UI state to UIStateManager
            if self.ui_state_manager:
                self.ui_state_manager.set_new_reference_state(starting=False)
            
            self._b_no_read.clear()
            show_message(msg="New reference completed", auto_close_time=5)
        except Exception as e:
            logger.exception(f"Error ending new reference thread: {e}")

    def new_ref_thread(self: Any) -> None:
        """Make new reference."""
        if self.ctrl is not None:
            try:
                logger.debug("new reference thread")
                # Reference Signal - S-position intensity reading on each channel
                self.ctrl.set_mode(mode="s")
                self.ctrl.turn_off_channels()
                time.sleep(LED_STABILIZATION_DELAY)
                for ch in CH_LIST:
                    self.ctrl.set_intensity(ch=ch, raw_val=self.ref_intensity[ch])
                    time.sleep(LED_DELAY)
                    ref_data_sum = np.zeros_like(self.dark_noise)
                    ref_scans = REF_SCANS
                    if self.integration > INTEGRATION_THRESHOLD:
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

    def single_led(self: Any, led_setting: str) -> None:
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

    def set_polarizer(self: Any, pos: str) -> None:
        """Move polariizer."""
        if self.ctrl is not None:
            self._b_no_read.set()
            time.sleep(HARDWARE_PAUSE_DELAY)
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

    def _on_calibration_started(self: Any) -> None:
        """Handle calibration start - delegated to UIStateManager."""
        if self.ui_state_manager:
            self.ui_state_manager.set_calibration_state(calibrating=True)
        show_message(
            msg="Calibration Started:\nThis process may take a few minutes to complete",
            auto_close_time=10,
        )

    def _on_calibration_status(
        self: Any,
        state: bool,  # noqa: FBT001
        ch_error_str: str,
    ) -> None:
        self.calibrated = state
        if self.adv_connected and DEV:
            self.main_window.ui.adv_btn.setEnabled(True)
        current_text = self.main_window.ui.status.text()
        if current_text.endswith("Calibrating"):
            if self.ui_state_manager:
                self.ui_state_manager.set_connection_state(connected=True)
        if ch_error_str != "":
            if (
                self.device_config["ctrl"] in ["PicoEZSPR"]  # EZSPR disabled (obsolete)
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
            # Proceed without full calibration but allow live data to run
            logger.debug("continuing without calibration; enabling live data")
            self.calibrated = True
        
        # Delegate calibration completion UI state to UIStateManager
        if self.ui_state_manager:
            self.ui_state_manager.set_calibration_state(calibrating=False)
        
        # Start live data regardless of calibration result unless shutting down
        if not self._b_kill.is_set():
            self._b_no_read.clear()
            if self._b_stop.is_set():
                self._b_stop.clear()

    def error_handler(self: Any, error_type: object) -> None:
        """Handle error."""
        logger.debug(f"Error handler:{error_type}")
        if error_type == "ctrl":
            self._on_ctrl_error()
        if error_type == "spec":
            self._on_spec_error()

    def _on_ctrl_error(self: Any) -> None:
        if self.ctrl is not None:
            self.disconnect_dev(knx=False)
            if not self.closing:
                show_message(
                    msg="Error: Device Disconnected!\nCheck connection and USB cable",
                    msg_type="Warning",
                )
                if self.ui_state_manager:
                    self.ui_state_manager.set_connection_error_state()

    def _on_spec_error(self: Any) -> None:
        if self.usb.spec is not None:
            self.disconnect_dev(knx=False)
            if not self.closing:
                show_message(
                    msg="Error: Device Disconnected!\nCheck connection and USB cable",
                    msg_type="Warning",
                )
                if self.ui_state_manager:
                    self.ui_state_manager.set_connection_error_state()

    @Slot(dict, list, str)
    def send_to_analysis(
        self: Any,
        data_dict: dict[str, np.ndarray],
        seg_list: list[Segment],
        unit: str,
    ) -> None:
        """Send data from processing tab to analysis tab."""
        self.main_window.set_main_widget("data_analysis")
        self.main_window.data_analysis.load_data(data_dict, seg_list, unit)

    @Slot()
    def recording_on(self: Any) -> bool | None:
        """Start/stop recording data - delegated to RecordingManager."""
        if self.recording_manager:
            result = self.recording_manager.toggle_recording(
                device_config=self.device_config,
                set_start_callback=self.set_start,
                clear_buffers_callback=self.clear_sensor_reading_buffers,
                parent_widget=self,
            )
            # Sync state after operation
            self._sync_recording_state()
            return result
        return None

    def save_rec_data(self: Any) -> None:
        """Save recorded data - delegated to RecordingManager."""
        if self.recording_manager:
            self.recording_manager.save_recorded_data(
                device_config=self.device_config,
                temp_log=self.temp_log,
                log_ch1=self.log_ch1,
                log_ch2=self.log_ch2,
                knx=self.knx,
            )

    def manual_export_raw_data(self: Any) -> None:
        """Export raw data - delegated to RecordingManager."""
        if self.recording_manager:
            self.recording_manager.manual_export_data(parent_widget=self)

    def _grab_data(self: Any) -> None:
        """Main data acquisition loop - delegated to SPRDataAcquisition."""
        try:
            data_acq = self._get_data_acq()
            data_acq.grab_data()
        except Exception as e:
            logger.exception(f"Error in data acquisition: {e}")
            self._b_stop.set()

    @staticmethod
    def median_window(win_size: int) -> int:
        """Make an odd integer."""
        if (win_size % 2) == 0:
            win_size += 1
        return win_size

    def update_filtered_lambda(self: Self) -> None:
        """Filter data - delegated to SPRDataAcquisition."""
        try:
            data_acq = self._get_data_acq()
            data_acq.update_filtered_lambda()
        except Exception as e:
            logger.exception(f"Error updating filtered lambda: {e}")

    def pause(self: Self) -> None:
        """Pause sensor."""
        self._b_stop.set()
        self._s_stop.set()

    def resume(self: Self) -> None:
        """Resume sensor."""
        self._b_stop.clear()
        self._s_stop.clear()

    # ========================================
    # ERROR HANDLING & UTILITIES
    # ========================================

    # ========================================
    # CONFIGURATION MANAGEMENT
    # ========================================

    def update_device_configuration(self, ctrl: str = "", knx: str = "", 
                                   pump: str | None = None, usb: str = "") -> None:
        """Update device configuration through config manager.
        
        Args:
            ctrl: SPR controller device name
            knx: Kinetic controller device name
            pump: Pump controller device name
            usb: USB spectrometer device name
        """
        self.config.update_device_config(ctrl, knx, pump, usb)
        logger.debug(f"Device configuration updated: {self.device_config}")

    def load_configuration_profile(self, file_path: Path) -> bool:
        """Load configuration from file.
        
        Args:
            file_path: Path to configuration file
            
        Returns:
            True if loaded successfully
        """
        return self.config.load_configuration(file_path)

    def save_configuration_profile(self, file_path: Path) -> bool:
        """Save current configuration to file.
        
        Args:
            file_path: Path to save configuration
            
        Returns:
            True if saved successfully
        """
        return self.config.save_configuration(file_path)

    def reset_all_configuration(self) -> None:
        """Reset all configuration to defaults."""
        self.config.reset_all_configurations()
        logger.info("All configuration reset to defaults")

    def get_configuration_summary(self) -> dict[str, Any]:
        """Get summary of current configuration state."""
        return self.config.get_configuration_summary()

    def add_temperature_reading(self, temperature: float, timestamp: float, exp_time: float = 0.0) -> None:
        """Add temperature reading to log through config manager."""
        self.config.add_temperature_reading(temperature, timestamp, exp_time)

    # ========================================
    # ERROR HANDLING & UTILITIES
    # ========================================

    def _handle_error(self, operation: str, error: Exception, 
                      show_user: bool = True, level: str = "error") -> None:
        """Standardized error handling for consistent logging and user feedback.
        
        Args:
            operation: Description of the operation that failed
            error: The exception that occurred
            show_user: Whether to show message to user
            level: Logging level ("error", "warning", "debug")
        """
        if level == "error":
            logger.exception(f"Error in {operation}: {error}")
        elif level == "warning":
            logger.warning(f"Warning in {operation}: {error}")
        else:
            logger.debug(f"Debug in {operation}: {error}")
        
        if show_user:
            msg_type = "Warning" if level in ("warning", "debug") else "Error"
            show_message(f"{operation.title()} {level}: {error}", msg_type=msg_type)

    # ========================================
    # DATA PROCESSING & BUFFER MANAGEMENT  
    # ========================================

    def pad_values(self: Self) -> None:
        """Pad values - delegated to DataBufferManager."""
        try:
            self.data_buffers.pad_values()
        except Exception as e:
            logger.exception(f"Error padding values: {e}")

    def sensorgram_data(self: Self) -> DataDict:
        """Return sensorgram data - delegated to DataBufferManager."""
        try:
            data = self.data_buffers.get_sensorgram_data(filtered=self.filt_on)
            # Convert to DataDict with required fields
            return {
                "lambda_values": data["lambda_values"],
                "lambda_times": data["lambda_times"],
                "buffered_lambda_times": data.get("buffered_lambda_times", data["lambda_times"]),
                "filtered_lambda_values": data.get("filtered_lambda_values", data["lambda_values"]),
                "filt": self.filt_on,
                "start": getattr(self, 'exp_start', 0.0),
                "rec": self.recording,
            }
        except Exception as e:
            logger.exception(f"Error getting sensorgram data: {e}")
            # Return fallback data
            return {
                "lambda_values": self.lambda_values,
                "lambda_times": self.lambda_times,
                "buffered_lambda_times": self.buffered_times,
                "filtered_lambda_values": self.filtered_lambda,
                "filt": self.filt_on,
                "start": getattr(self, 'exp_start', 0.0),
                "rec": self.recording,
            }

    def transfer_sens_data(self: Self) -> None:
        """Transfer sensorgram data."""
        raw_data = self.sensorgram_data()
        seg_table = self.main_window.sensorgram.saved_segments
        self.main_window.data_processing.update_sensorgram_data(raw_data, seg_table)

    def spectroscopy_data(self: Self) -> dict[str, object]:
        """Return spectroscopy data - delegated to DataBufferManager."""
        try:
            spec_data = self.data_buffers.get_spectroscopy_data()
            # Add wave_data which is stored separately
            spec_data["wave_data"] = self.wave_data
            return spec_data
        except Exception as e:
            logger.exception(f"Error getting spectroscopy data: {e}")
            # Return fallback data
            return {
                "wave_data": self.wave_data,
                "int_data": self.int_data,
                "trans_data": self.trans_data,
            }

    def auto_polarization(self: Self) -> None:
        """Find polarizer positions using calibrator."""
        try:
            if self.device_config["ctrl"] not in DEVICES or self.ctrl is None or self.usb is None:
                return
            
            # Ensure calibrator is available
            if self.calibrator is None:
                from utils.spr_calibrator import SPRCalibrator
                self.calibrator = SPRCalibrator(
                    ctrl=self.ctrl,
                    usb=self.usb,
                    device_type=self.device_config["ctrl"] or "unknown"
                )
            
            # Delegate to calibrator
            result = self.calibrator.auto_polarize(ctrl=self.ctrl, usb=self.usb)
            
            if result is not None:
                s_pos, p_pos = result
                logger.debug(f"Auto-polarization complete: s={s_pos}, p={p_pos}")
                self.new_default_values = True
            
        except Exception as e:
            logger.exception(f"Error in auto_polarization: {e}")

    def stop_pump(self: Self, stop_ch: str) -> None:
        """Stop a pump via kinetic operations."""
        try:
            self._s_stop.set()
            kin = self._get_kin_ops()
            self.pump_states = kin.stop_pump(stop_ch, self.pump_states, self.synced)
            self._s_stop.clear()
        except Exception as e:
            logger.exception(f"Error stopping pump: {e}")
            self._s_stop.clear()

    def three_way(self: Self, ch: str, state: int | str) -> None:
        """Switch a three-way valve using kinetic manager."""
        if self.kinetic_manager is not None:
            try:
                self._s_stop.set()
                position = int(state)
                success = self.kinetic_manager.set_three_way_valve(ch, position)
                if not success:
                    logger.warning(f"Failed to set 3-way valve {ch} to position {position}")
                self._s_stop.clear()
            except Exception as e:
                logger.exception(f"Error setting 3-way valve: {e}")
                self._s_stop.clear()

    def six_port(self: Self, ch: str, state: int | str) -> None:
        """Change a six port valve using kinetic manager."""
        if self.kinetic_manager is not None:
            try:
                self._s_stop.set()
                position = int(state)
                success = self.kinetic_manager.set_six_port_valve(ch, position)
                if not success:
                    logger.warning(f"Failed to set 6-port valve {ch} to position {position}")
                self._s_stop.clear()
            except Exception as e:
                logger.exception(f"Error setting 6-port valve: {e}")
                self._s_stop.clear()

    @Slot(str, int)
    def speed_change_handler(self: Self, ch: str, rate: int) -> None:
        """Change a pump speed via kinetic operations."""
        try:
            kin = self._get_kin_ops()
            self.pump_states = kin.handle_speed_change(ch, rate, self.pump_states, self.synced)
        except Exception as e:
            logger.exception(f"Error handling speed change: {e}")

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

    def run_pump(self: Self, ch: str, rate: int) -> None:
        """Start or change pump flow via kinetic operations."""
        try:
            # Update flow rate for convenience (ml/sec)
            self.flow_rate = abs(rate) / 60.0
            
            kin = self._get_kin_ops()
            self.pump_states = kin.run_pump(ch, rate, self.pump_states, self.synced)
        except Exception as e:
            logger.exception(f"Error starting pump {ch} at rate {rate}: {e}")

    def valve_state_check(self: Self, curr_status: object, ch: int) -> None:
        """Check valve state via kinetic manager (ignores curr_status)."""
        if not self.update_timer.isActive() and self.kinetic_manager is not None:
            ch_name = "CH1" if ch == 1 else "CH2"
            fw_state = self.kinetic_manager.get_valve_position_name(ch_name)
            if self.valve_states.get(ch_name) != fw_state:
                self.valve_states[ch_name] = fw_state
                logger.debug(f"synchronized valve state on {ch_name}: {fw_state}")
                self.update_valve_display.emit(self.valve_states, self.synced)

    @Slot(str)
    def three_way_handler(self: Self, ch: str) -> None:
        """Toggle three-way valve via kinetic manager."""
        self.update_timer.start(VALVE_UPDATE_TIMEOUT)
        if self.kinetic_manager is not None:
            self.kinetic_manager.toggle_three_way_valve(ch)

    @Slot(str)
    def six_port_handler(self: Self, ch: str) -> None:
        """Toggle six-port valve via kinetic manager."""
        self.update_timer.start(VALVE_UPDATE_TIMEOUT)
        if self.kinetic_manager is not None:
            self.kinetic_manager.toggle_six_port_valve(ch)

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
                run_rate = FLUSH_RATE
                try:
                    kw = getattr(self.main_window.sidebar, "kinetic_widget", None)
                    if kw is not None:
                        run_rate = int(kw.ui.run_rate_ch1.currentText())
                except Exception:
                    pass
                self.run_pump("CH2", run_rate)
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
        """Clear sensor reading buffers using kinetic manager."""
        # Clear kinetic manager sensor buffers (clears all channels)
        if self.kinetic_manager:
            self.kinetic_manager.clear_sensor_buffers()
        
        # Clear display (temperature only; flow removed)
        self.update_sensor_display.emit({"temp1": "", "temp2": ""})
        
        # Clear temperature log (P4SPR specific) - use config manager
        self.config.clear_temperature_log()
        self.update_temp_display.emit(0.0, "ctrl")

    def save_temp_log(self: Self, rec_dir: str) -> None:
        """Save temperature log using DataIOManager."""
        try:
            self.data_io.save_temperature_log(rec_dir, self.temp_log)
        except Exception as e:
            logger.exception(f"Error while saving temperature log data: {e}")

    def save_kinetic_log(self: Self, rec_dir: str) -> None:
        """Save kinetics log using DataIOManager."""
        if self.knx is not None:
            try:
                knx_version = self.knx.version if hasattr(self.knx, 'version') else "1.0"
                
                # Save Channel A log
                self.data_io.save_kinetic_log(rec_dir, self.log_ch1, "A", knx_version)
                
                # Save Channel B log for dual-channel devices
                if (self.device_config["ctrl"] in ["PicoEZSPR"]) or (  # EZSPR disabled (obsolete)
                    self.device_config["knx"] in ["KNX2"]  # PicoKNX2 disabled (obsolete)
                ):
                    self.data_io.save_kinetic_log(rec_dir, self.log_ch2, "B", knx_version)
                
            except Exception as e:
                logger.exception(f"Error while saving kinetic log data: {e}")

    def update_internal_temp(self: Self, new_temp: float) -> None:
        """Update internal temperature."""
        self.temp = new_temp

    def save_calibration_profile(self, profile_name: str | None = None) -> bool:
        """Save current calibration settings to a profile file."""
        try:
            if self.calibrator is None:
                show_message(
                    msg="No calibration data to save. Please calibrate first.",
                    msg_type="Warning",
                )
                return False
            
            # Handle UI prompt for profile name if needed
            if profile_name is None:
                from PySide6.QtWidgets import QInputDialog
                profile_name, ok = QInputDialog.getText(
                    self.main_window,
                    "Save Calibration Profile",
                    "Enter profile name:",
                )
                if not ok or not profile_name:
                    return False
            
            # Delegate to calibrator
            device_type = self.device_config["ctrl"] or "unknown"
            success = self.calibrator.save_profile(
                profile_name=profile_name,
                device_type=device_type
            )
            
            if success:
                show_message(
                    msg=f"Calibration profile '{profile_name}' saved successfully!",
                    msg_type="Information",
                    auto_close_time=3,
                )
            else:
                show_message(
                    msg="Failed to save calibration profile.",
                    msg_type="Warning",
                )
            
            return success
            
        except Exception as e:
            logger.exception(f"Error saving calibration profile: {e}")
            show_message(
                msg=f"Failed to save calibration profile: {e}",
                msg_type="Warning",
            )
            return False
    
    def load_calibration_profile(self, profile_name: str | None = None) -> bool:
        """Load calibration settings from a profile file."""
        try:
            if self.calibrator is None:
                # Create temporary calibrator to list profiles
                from utils.spr_calibrator import SPRCalibrator
                temp_calibrator = SPRCalibrator(
                    ctrl=None,
                    usb=None,
                    device_type=self.device_config["ctrl"] or "unknown"
                )
                profiles = temp_calibrator.list_profiles()
            else:
                profiles = self.calibrator.list_profiles()
            
            # Handle UI prompt for profile selection if needed
            if profile_name is None:
                if not profiles:
                    show_message(
                        msg="No calibration profiles found.",
                        msg_type="Information",
                    )
                    return False
                
                from PySide6.QtWidgets import QInputDialog
                profile_name, ok = QInputDialog.getItem(
                    self.main_window,
                    "Load Calibration Profile",
                    "Select profile:",
                    profiles,
                    0,
                    False,
                )
                if not ok:
                    return False
            
            # Create calibrator if needed
            if self.calibrator is None:
                from utils.spr_calibrator import SPRCalibrator
                self.calibrator = SPRCalibrator(
                    ctrl=self.ctrl,
                    usb=self.usb,
                    device_type=self.device_config["ctrl"] or "unknown"
                )
            
            # Load profile via calibrator
            device_type = self.device_config["ctrl"]
            success, message = self.calibrator.load_profile(
                profile_name=profile_name,
                device_type=device_type
            )
            
            if not success:
                show_message(msg=message, msg_type="Warning")
                return False
            
            # Check for device mismatch warning
            if "was created for" in message:
                if not show_message(msg=f"{message}. Load anyway?", yes_no=True):
                    return False
            
            # Apply to hardware if connected
            if self.ctrl is not None and self.usb is not None:
                self.calibrator.apply_profile_to_hardware(
                    ctrl=self.ctrl,
                    usb=self.usb,
                    ch_list=CH_LIST
                )
            
            # Sync state from calibrator
            self.integration = self.calibrator.state.integration
            self.num_scans = self.calibrator.state.num_scans
            self.ref_intensity = self.calibrator.state.ref_intensity.copy()
            self.leds_calibrated = self.calibrator.state.leds_calibrated.copy()
            self.wave_min_index = self.calibrator.state.wave_min_index
            self.wave_max_index = self.calibrator.state.wave_max_index
            self.led_delay = self.calibrator.state.led_delay
            self.med_filt_win = self.calibrator.state.med_filt_win
            
            show_message(
                msg=f"Calibration profile '{profile_name}' loaded successfully!",
                msg_type="Information",
                auto_close_time=3,
            )
            return True
            
        except Exception as e:
            logger.exception(f"Error loading calibration profile: {e}")
            show_message(
                msg=f"Failed to load calibration profile: {e}",
                msg_type="Warning",
            )
            return False

    def save_default_values(self: Self) -> None:
        """Save default values."""
        if self.device_config["ctrl"] in [
            "PicoP4SPR",
            "PicoEZSPR",
        ] and isinstance(self.ctrl, PicoEZSPR | PicoP4SPR):
            if show_message(
                msg="Save settings permanently to device?\n"
                "This will overwrite factory default settings",
                yes_no=True,
            ):
                logger.debug("New values saved to device")
                self.ctrl.flash()
            else:
                logger.debug("Values not saved")
            self.new_default_values = False

    def _update_filter_settings(self: Self, filt_en: bool, filt_win: int, is_live: bool = False) -> None:  # noqa: FBT001, FBT002
        """Update filter settings - helper for processing and live filters."""
        self.filt_on = filt_en
        
        # Update filter window if changed
        reference_win = self.med_filt_win if is_live else self.proc_filt_win
        if filt_win != reference_win:
            self.med_filt_win = self.median_window(filt_win)
            # Update data processor window size
            if self.data_processor is not None:
                self.data_processor.update_filter_window(self.med_filt_win)
            if is_live:
                self.update_filtered_lambda()

    def set_proc_filt(self: Self, filt_en: bool, filt_win: int) -> None:  # noqa: FBT001
        """Set data processing filter."""
        self._update_filter_settings(filt_en, filt_win, is_live=False)
        if self.main_window.active_page == "data_processing":
            self.main_window.data_processing.set_filter(
                filt_en=filt_en,
                med_filt_win=self.med_filt_win,
            )

    def set_live_filt(self: Self, filt_en: bool, filt_win: int) -> None:  # noqa: FBT001
        """Set live view filter."""
        self._update_filter_settings(filt_en, filt_win, is_live=True)
        if self.main_window.active_page == "sensorgram":
            self.main_window.sensorgram.quick_segment_update()

    def connect_advanced_menu(self: Self) -> None:
        """Connect advanced menu using parameter manager."""
        if (self.device_config["ctrl"] in DEVICES 
            and hasattr(self.main_window, 'advanced_menu')
            and self.main_window.advanced_menu is not None):
            try:
                self.main_window.advanced_menu.new_parameter_sig.connect(
                    self.update_advanced_params,
                )
                self.main_window.advanced_menu.get_parameter_sig.connect(
                    self.get_device_parameters,
                )
                self.adv_connected = True
            except Exception as e:
                logger.exception(f"Error connecting advanced menu: {e}")
                self.adv_connected = False

    def get_device_parameters(self: Self) -> None:
        """Get device parameters - delegated to ParameterManager."""
        if self.adv_connected:
            try:
                param_mgr = self._get_param_mgr()
                param_mgr.get_device_parameters()
            except Exception as e:
                logger.exception(f"Error getting device parameters: {e}")

    def update_advanced_params(self: Self, params: dict[str, str]) -> None:
        """Update advanced parameters - delegated to ParameterManager."""
        if self.adv_connected:
            try:
                param_mgr = self._get_param_mgr()
                success = param_mgr.update_advanced_parameters(params)
                if not success:
                    logger.warning("Some parameters could not be updated")
                    
                # Sync updated parameter values back to main app
                current_params = param_mgr.get_current_parameters()
                self.led_delay = current_params["led_delay"]
                self.ht_req = current_params["ht_req"]
                self.sensor_interval = current_params["sensor_interval"]
                self.integration = current_params["integration"]
                self.num_scans = current_params["num_scans"]
                self.leds_calibrated = current_params["leds_calibrated"]
                
            except Exception as e:
                logger.exception(f"Error updating advanced parameters: {e}")

    def clear_data(self: Self) -> None:
        """Clear data."""
        self.pause()
        time.sleep(HARDWARE_PAUSE_DELAY)
        # Reset all data buffers through the buffer manager
        self.data_buffers.clear_all_buffers()
        
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
            if self.ui_state_manager:
                self.ui_state_manager.set_scanning_state()
            try:
                # Ensure only one connection attempt thread runs at a time
                if getattr(self, "_con_tr", None) and self._con_tr.is_alive():
                    logger.debug("Connection already in progress")
                else:
                    self._c_stop.set()  # pause calibration while connecting
                    self._con_tr = threading.Thread(target=self.connection_thread, daemon=True)
                    self._con_tr.start()
            except Exception as e:
                logger.exception(f"Failed to start connection thread: {e}")
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
        """Shutdown controller - delegated to HardwareManager."""
        try:
            hw_mgr = self._get_hw_mgr()
            hw_mgr.shutdown_controller()
        except Exception as e:
            logger.exception(f"Error shutting down controller: {e}")
            self.main_window.ui.status.setText("Shutdown error")

    def shutdown_kinetics(self: Self, *, skip_setup: bool = False) -> None:
        """Shutdown kinetics - delegated to HardwareManager."""
        try:
            hw_mgr = self._get_hw_mgr()
            hw_mgr.shutdown_kinetics(skip_setup=skip_setup)
        except Exception as e:
            logger.exception(f"Error shutting down kinetics: {e}")
            self.main_window.ui.status.setText("Shutdown error")

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
        """Disconnect devices - delegated to HardwareManager."""
        try:
            self.main_window.ui.status.setText("Disconnecting...")
            self.main_window.ui.status.repaint()
            
            # Stop any ongoing spectrometer retry attempts
            try:
                _t = getattr(self, "_spec_retry_timer", None)
                if _t is not None and _t.isActive():
                    _t.stop()
            except Exception:
                pass
                
            if self.recording:
                self.recording_on()
                
            if self._con_tr.is_alive():
                self._con_tr.join(0.1)
                
            self.stop(knx=knx)
            self.calibrated = False
            
            # Delegate hardware disconnection to HardwareManager
            hw_mgr = self._get_hw_mgr()
            success = hw_mgr.disconnect_hardware(ctrl=ctrl, knx=knx, pump=pump)
            
            if not success:
                logger.warning("Some hardware disconnection issues occurred")
                
            # Update state references
            if ctrl and self.ctrl is not None:
                self.ctrl = None
                self.calibrated = False
                if self.usb is not None:
                    self.usb = None
                    
            if knx and self.knx is not None:
                self.knx_reset_ui.emit()
                self.knx = None
                self.kinetic_manager = None
                
            if pump and self.pump is not None:
                self.pump = None
                self.pump_manager = None
                
            self.get_current_device_config()
            self.main_window.ui.status.setText("Disconnected")
            
        except Exception as e:
            logger.exception(f"Error during device disconnection: {e}")
            self.main_window.ui.status.setText("Disconnect error")

    def close(self: Self) -> bool:
        """Close the app - delegated to ThreadManager."""
        self.closing = True
        self.disconnect_dev()
        
        # Stop threads using ThreadManager
        if hasattr(self, 'thread_manager'):
            self.thread_manager.stop_threads()
        else:
            # Fallback to manual flag setting
            self._b_kill.set()
            self._c_kill.set()
            self._s_kill.set()
            time.sleep(0.5)
        
        self.rec_timer.stop()
        self.quit()  # Use QApplication.quit() instead of super().close()
        return True

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

    # Set up qasync event loop for Qt integration
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    # Schedule connection and run the event loop
    loop.call_soon(app.connect_dev)
    
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
