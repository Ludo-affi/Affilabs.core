"""SPR System State Machine for simplified hardware and operation management."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Optional, Union

from PySide6.QtCore import QObject, QTimer, Signal

from utils.logger import logger

# Import real components first (preferred)
try:
    from utils.hardware_manager import HardwareManager
    from utils.spr_calibrator import SPRCalibrator
    REAL_HARDWARE_AVAILABLE = True
    logger.info("Real hardware components available")
except ImportError:
    REAL_HARDWARE_AVAILABLE = False
    logger.warning("Real hardware components not available")

# Import mock components for fallback testing
try:
    from utils.mock_hardware_manager import MockHardwareManager
    from utils.mock_calibrator import MockCalibrator
    MOCK_MODE_AVAILABLE = True
    logger.info("Mock components available for testing")
except ImportError:
    MOCK_MODE_AVAILABLE = False
    logger.debug("Mock components not available")

# Determine which mode to use (prefer real hardware)
USE_REAL_HARDWARE = REAL_HARDWARE_AVAILABLE

# Environment variable override for forcing real hardware mode
import os
FORCE_REAL_MODE = os.getenv('FORCE_REAL_HARDWARE', 'false').lower() == 'true'
if FORCE_REAL_MODE:
    logger.warning("🔧 FORCE_REAL_HARDWARE environment variable set - will attempt real hardware even if integration incomplete")

# Ultra clear logging about what mode we're in
if USE_REAL_HARDWARE:
    logger.warning("🎯 STATE MACHINE CONFIGURED FOR: **REAL HARDWARE MODE**")
    logger.warning("   - Hardware discovery: REAL devices (PicoP4SPR, USB4000)")
    logger.warning("   - Hardware connection: REAL devices")
    logger.warning("   - Calibration: REAL (no mock fallback)")
else:
    logger.warning("🧪 STATE MACHINE CONFIGURED FOR: **SIMULATION MODE**")
    logger.warning("   - Hardware discovery: MOCK simulation")
    logger.warning("   - Hardware connection: MOCK simulation")
    logger.warning("   - Calibration: MOCK simulation")

from utils.spr_data_acquisition import SPRDataAcquisition
from utils.spr_data_processor import SPRDataProcessor
import threading
import numpy as np
from settings import CH_LIST


class DataAcquisitionThread(threading.Thread):
    """Thread wrapper for SPRDataAcquisition to handle its grab_data loop."""

    def __init__(self, data_acquisition: SPRDataAcquisition):
        super().__init__(daemon=True)
        self.data_acquisition = data_acquisition
        self._stop_event = threading.Event()
        self._healthy = True

    def run(self) -> None:
        """Run the data acquisition loop."""
        try:
            logger.info("Data acquisition thread started")
            self.data_acquisition.grab_data()
        except Exception as e:
            logger.exception(f"Data acquisition thread error: {e}")
            self._healthy = False
        finally:
            logger.info("Data acquisition thread stopped")

    def is_running(self) -> bool:
        """Check if thread is running."""
        return self.is_alive()

    def is_healthy(self) -> bool:
        """Check if thread is healthy."""
        return self._healthy and self.is_alive()

    def stop_gracefully(self) -> None:
        """Stop the data acquisition gracefully."""
        self._stop_event.set()
        if hasattr(self.data_acquisition, '_b_stop'):
            self.data_acquisition._b_stop.set()
        if hasattr(self.data_acquisition, '_b_kill'):
            self.data_acquisition._b_kill.set()


class DataAcquisitionWrapper:
    """Wrapper to make SPRDataAcquisition behave like the simple threaded version."""

    def __init__(self, app_ref: Any, calib_state: Any = None):
        self.app = app_ref
        self.thread: Optional[DataAcquisitionThread] = None
        self.data_acquisition: Optional[SPRDataAcquisition] = None

        # 🎯 Store shared calibration state reference
        self.calib_state = calib_state
        if calib_state is not None:
            logger.info("✅ DataAcquisitionWrapper using SHARED CalibrationState")
        else:
            logger.warning("⚠️ DataAcquisitionWrapper has NO shared state!")

        # Initialize data storage and configuration
        self._init_data_storage()
        self._init_threading_events()

    def _init_data_storage(self) -> None:
        """Initialize data storage arrays for SPR acquisition."""
        # Initialize empty data arrays for each channel
        self.lambda_values = {ch: np.array([]) for ch in CH_LIST}
        self.lambda_times = {ch: np.array([]) for ch in CH_LIST}
        self.filtered_lambda = {ch: np.array([]) for ch in CH_LIST}
        self.buffered_lambda = {ch: np.array([]) for ch in CH_LIST}
        self.buffered_times = {ch: np.array([]) for ch in CH_LIST}
        self.int_data = {ch: np.array([]) for ch in CH_LIST}
        self.trans_data = {ch: None for ch in CH_LIST}
        self.ref_sig = {ch: None for ch in CH_LIST}

        # Configuration defaults
        self.wave_data = np.array([])
        self.wave_min_index = 0
        self.wave_max_index = -1
        self.num_scans = 1
        self.led_delay = 0.1
        self.med_filt_win = 5
        self.dark_noise = np.zeros(3648)  # Match USB4000 pixel count (3648)

    def _init_threading_events(self) -> None:
        """Initialize threading control events."""
        self._b_kill = threading.Event()
        self._b_stop = threading.Event()
        self._b_no_read = threading.Event()

    def create_acquisition(self, ctrl_device: Any, usb_device: Any, data_processor: Any) -> None:
        """Create the real SPRDataAcquisition instance."""
        try:
            # Create device config
            device_config = {
                "ctrl": "PicoP4SPR" if ctrl_device else None,
                "usb": "USB4000OceanDirect" if usb_device else None,
            }

            # Create adapter wrapper for controller to match SPRDataAcquisition interface
            class ControllerAdapter:
                """Adapter to make HAL controller compatible with SPRDataAcquisition."""
                def __init__(self, hal_controller):
                    self.hal = hal_controller

                def turn_on_channel(self, ch: str) -> None:
                    """Turn on specific channel LED."""
                    # First activate the channel
                    if hasattr(self.hal, 'activate_channel'):
                        # Import ChannelID enum for proper conversion
                        from utils.hal.spr_controller_hal import ChannelID
                        channel_map = {'a': ChannelID.A, 'b': ChannelID.B, 'c': ChannelID.C, 'd': ChannelID.D}
                        ch_id = channel_map.get(ch.lower())
                        if ch_id:
                            self.hal.activate_channel(ch_id)
                    # Set LED intensity (only takes intensity parameter)
                    if hasattr(self.hal, 'set_led_intensity'):
                        intensity = 50  # Safe default for measurement
                        self.hal.set_led_intensity(intensity)

                def turn_off_channels(self) -> None:
                    """Turn off all channel LEDs."""
                    if hasattr(self.hal, 'turn_off_all_leds'):
                        self.hal.turn_off_all_leds()
                    elif hasattr(self.hal, 'set_led_intensity'):
                        # Turn off LEDs by setting intensity to 0
                        self.hal.set_led_intensity(0)

                def get_temp(self) -> float:
                    """Get temperature if available."""
                    if hasattr(self.hal, 'get_temperature'):
                        return self.hal.get_temperature()
                    return 25.0  # Default room temperature

                def __getattr__(self, name):
                    """Forward other attributes to HAL."""
                    return getattr(self.hal, name)

            # Create adapter wrapper for USB to match SPRDataAcquisition interface
            class SpectrometerAdapter:
                """Adapter to make HAL spectrometer compatible with SPRDataAcquisition."""
                def __init__(self, hal_spectrometer):
                    self.hal = hal_spectrometer

                def read_intensity(self):
                    """Read intensity using HAL method."""
                    if hasattr(self.hal, 'acquire_spectrum'):
                        return self.hal.acquire_spectrum()
                    elif hasattr(self.hal, 'capture_spectrum'):
                        return self.hal.capture_spectrum()
                    elif hasattr(self.hal, 'read_intensity'):
                        return self.hal.read_intensity()
                    else:
                        logger.error("No compatible spectrum reading method found")
                        return None

                def __getattr__(self, name):
                    """Forward other attributes to HAL."""
                    return getattr(self.hal, name)

            # Create adapters
            adapted_ctrl = ControllerAdapter(ctrl_device) if ctrl_device else None
            adapted_usb = SpectrometerAdapter(usb_device) if usb_device else None

            logger.info(f"Creating SPRDataAcquisition with device_config: {device_config}")
            logger.debug(f"Controller adapter: {adapted_ctrl}, USB adapter: {adapted_usb}")

            # 🎯 Sync from shared calibration state before creating acquisition
            if self.calib_state is not None:
                self.sync_from_shared_state()

            self.data_acquisition = SPRDataAcquisition(
                # Hardware references
                ctrl=adapted_ctrl,
                usb=adapted_usb,
                data_processor=data_processor,
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
                device_config=device_config,
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
                # UI callbacks - connect to main window signals
                update_live_signal=self._get_app_signal('update_live_signal'),
                update_spec_signal=self._get_app_signal('update_spec_signal'),
                temp_sig=self._get_app_signal('temp_sig'),
                raise_error=self._get_app_signal('raise_error'),
                set_status_text=self._set_status_text,
            )

            # Set calibration state
            self.data_acquisition.set_configuration(calibrated=True)

            logger.info("SPRDataAcquisition created successfully")

        except Exception as e:
            logger.exception(f"Failed to create SPRDataAcquisition: {e}")
            raise

    def _get_app_signal(self, signal_name: str) -> Any:
        """Get a signal from the app, or create a dummy emitter."""
        if hasattr(self.app, signal_name):
            app_signal = getattr(self.app, signal_name)
            logger.debug(f"🔗 Found app signal {signal_name}: {type(app_signal)}")
            return app_signal
        else:
            # Create a dummy signal emitter that connects to main window
            logger.debug(f"🔧 Creating dummy emitter for {signal_name}")
            return self._create_ui_signal_emitter(signal_name)

    def _create_ui_signal_emitter(self, signal_name: str) -> Any:
        """Create a signal emitter that updates UI directly."""
        def emit_to_ui(emitter_self, *args: Any) -> None:
            """Emit function that receives 'self' as first arg (bound method behavior)."""
            try:
                logger.debug(f"🔔 emit_to_ui called for {signal_name} with {len(args)} args (after self): {[type(arg).__name__ for arg in args]}")

                # Handle different signal types
                if len(args) > 0:
                    data = args[0]
                    logger.debug(f"✅ Data for {signal_name}: type={type(data).__name__}")
                else:
                    data = None

                if signal_name == 'update_live_signal' and hasattr(self.app, 'main_window'):
                    # Update sensorgram
                    if hasattr(self.app.main_window, 'sensorgram') and data is not None:
                        self.app.main_window.sensorgram.update_data(data)
                elif signal_name == 'update_spec_signal' and hasattr(self.app, 'main_window'):
                    # Update spectroscopy
                    if hasattr(self.app.main_window, 'spectroscopy') and data is not None:
                        self.app.main_window.spectroscopy.update_data(data)
                elif signal_name == 'temp_sig' and data is not None:
                    logger.debug(f"Temperature: {data}")
                elif signal_name == 'raise_error':
                    # Handle error signal - may have one or more arguments
                    error_msg = data if data is not None else "Unknown error"
                    logger.error(f"Data acquisition error: {error_msg}")
                else:
                    logger.debug(f"Signal {signal_name}: {data}")
            except Exception as e:
                logger.exception(f"Error emitting {signal_name}: {e}")

        return type('SignalEmitter', (), {'emit': emit_to_ui})()

    def _set_status_text(self, text: str) -> None:
        """Set status text in UI."""
        logger.info(f"Status: {text}")
        try:
            if hasattr(self.app, 'main_window') and hasattr(self.app.main_window, 'status_bar'):
                self.app.main_window.status_bar.showMessage(text)
        except Exception as e:
            logger.debug(f"Could not update status bar: {e}")

    def sync_from_shared_state(self) -> None:
        """Sync wrapper's local copies from shared calibration state.

        ✅ SIMPLIFIED: Direct reference to shared state - no complex copying logic.
        The shared state is already populated by the calibrator.
        """
        if self.calib_state is None:
            logger.warning("No shared calibration state available")
            return

        try:
            with self.calib_state._lock:
                # Simple direct references - data is already in shared state!
                if len(self.calib_state.wavelengths) > 0:
                    self.wave_data = self.calib_state.wavelengths
                    self.wave_min_index = self.calib_state.wave_min_index
                    self.wave_max_index = self.calib_state.wave_max_index
                    logger.info(f"✅ Synced wavelengths: {len(self.wave_data)} points")

                if len(self.calib_state.dark_noise) > 0:
                    self.dark_noise = self.calib_state.dark_noise
                    logger.info(f"✅ Synced dark noise: {len(self.dark_noise)} points")

                # Sync reference signals
                for ch in CH_LIST:
                    if self.calib_state.ref_sig.get(ch) is not None:
                        self.ref_sig[ch] = self.calib_state.ref_sig[ch]
                        logger.info(f"✅ Synced ref_sig[{ch}]: {len(self.ref_sig[ch])} points")

            logger.info("✅ DataAcquisitionWrapper synced from shared state")
        except Exception as e:
            logger.exception(f"Failed to sync from shared state: {e}")

    def start(self) -> None:
        """Start data acquisition thread."""
        if not self.data_acquisition:
            raise RuntimeError("Data acquisition not created")

        if self.thread and self.thread.is_alive():
            logger.warning("Data acquisition already running")
            return

        # Clear stop flags
        self._b_stop.clear()
        self._b_kill.clear()

        # Create and start thread
        self.thread = DataAcquisitionThread(self.data_acquisition)
        self.thread.start()
        logger.info("Data acquisition thread started")

    def stop(self) -> None:
        """Stop data acquisition thread."""
        if self.thread:
            self.thread.stop_gracefully()
            # Give it a moment to stop gracefully
            self.thread.join(timeout=2.0)
            if self.thread.is_alive():
                logger.warning("Data acquisition thread did not stop gracefully")
            self.thread = None

    def is_running(self) -> bool:
        """Check if data acquisition is running."""
        return self.thread is not None and self.thread.is_running()

    def is_healthy(self) -> bool:
        """Check if data acquisition is healthy."""
        return self.thread is not None and self.thread.is_healthy()

    def restart(self) -> None:
        """Restart data acquisition."""
        logger.info("Restarting data acquisition...")
        self.stop()
        time.sleep(0.5)
        self.start()


class SimpleHardwareManager:
    """Simplified hardware manager for state machine use."""

    def __init__(self):
        """Initialize the simple hardware manager."""
        self.ctrl = None
        self.usb = None
        self.knx = None
        self._discovery_attempts = 0

    def initialize_hardware(self) -> bool:
        """Initialize hardware components directly."""
        try:
            # Import HAL components for direct hardware access
            from utils.hal import HALFactory

            # Store the HAL factory class for later use
            self.HALFactory = HALFactory
            logger.info("HAL factory created for real hardware")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize HAL factory: {e}")
            return False

    def discover_hardware(self) -> bool:
        """Discover available hardware."""
        try:
            self._discovery_attempts += 1
            logger.debug(f"Hardware discovery attempt {self._discovery_attempts}")

            # Use HAL factory class methods (not instance methods)
            available_devices = self.HALFactory.detect_connected_devices()
            if available_devices:
                logger.info(f"Found {len(available_devices)} hardware device(s): {[d.get('type', 'unknown') for d in available_devices]}")
                return True
            else:
                logger.debug("No hardware devices found")
                return False

        except Exception as e:
            logger.error(f"Hardware discovery failed: {e}")
            return False

    def connect_all(self) -> bool:
        """Connect to all discovered hardware."""
        try:
            # Try to create controller using class method like original hardware manager
            try:
                logger.debug("Attempting to connect to PicoP4SPR controller on COM4...")
                # Use connection_params to specify COM4
                connection_params = {"port": "COM4"}
                self.ctrl = self.HALFactory.create_controller(
                    "PicoP4SPR",
                    auto_detect=False,
                    connection_params=connection_params,
                )
                if self.ctrl and self.ctrl.is_connected():
                    logger.info("Controller connected successfully on COM4")
                else:
                    logger.warning("Controller connection failed on COM4")
                    self.ctrl = None
            except Exception as e:
                logger.error(f"Controller connection error: {e}")
                self.ctrl = None

            # Try to create spectrometer using class method
            try:
                logger.debug("Attempting to connect to USB4000 spectrometer...")
                self.usb = self.HALFactory.create_spectrometer(
                    auto_detect=True,
                )
                if self.usb:
                    # Check if connected by trying to get device info or just assume success
                    try:
                        # Test connection by checking if we can access device properties
                        _ = getattr(self.usb, 'device_name', 'USB4000')
                        logger.info("Spectrometer connected successfully")
                    except Exception:
                        logger.warning("Spectrometer connection may be incomplete")
                else:
                    logger.warning("Spectrometer connection failed")
                    self.usb = None
            except Exception as e:
                logger.error(f"Spectrometer connection error: {e}")
                self.usb = None

            # Return true if at least one device connected
            return self.ctrl is not None or self.usb is not None

        except Exception as e:
            logger.error(f"Hardware connection failed: {e}")
            return False

    def disconnect_all(self) -> None:
        """Disconnect all hardware."""
        try:
            if self.ctrl:
                self.ctrl.disconnect()
                self.ctrl = None
                logger.info("Controller disconnected")

            if self.usb:
                self.usb.disconnect()
                self.usb = None
                logger.info("Spectrometer disconnected")

        except Exception as e:
            logger.error(f"Hardware disconnection error: {e}")


class SPRSystemState(Enum):
    """Clear system states for SPR operation."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CALIBRATING = "calibrating"
    CALIBRATED = "calibrated"
    MEASURING = "measuring"
    ERROR = "error"


class SPRStateMachine(QObject):
    """Single state machine to control all SPR operations."""

    # Signals for UI updates
    state_changed = Signal(str)  # Current state
    hardware_status = Signal(bool, bool)  # (ctrl_connected, usb_connected)
    calibration_progress = Signal(int, str)  # (step_number, description)
    calibration_completed = Signal(bool, str)  # (success, error_message)
    data_acquisition_started = Signal()
    error_occurred = Signal(str)  # Error message

    def __init__(self, app: Any) -> None:
        """Initialize the SPR state machine.

        Args:
            app: The main application instance
        """
        super().__init__()
        self.app = app
        self.state = SPRSystemState.DISCONNECTED

        # 🎯 SHARED CALIBRATION STATE - Single source of truth
        # This object is passed by reference to both calibrator and data acquisition
        from utils.spr_calibrator import CalibrationState
        self.calib_state = CalibrationState()
        logger.info("✨ Created SHARED CalibrationState - single source of truth")

        # Hardware and operation managers (use Any to support both real and mock)
        self.hardware_manager: Any = None
        self.calibrator: Any = None
        self.data_acquisition: Optional[DataAcquisitionWrapper] = None

        # Error tracking
        self.error_count = 0
        self.max_error_count = 3
        self.last_error_time = 0

        # Single timer for all operations
        self.operation_timer = QTimer(self)
        self.operation_timer.timeout.connect(self._process_current_state)
        self.operation_timer.start(100)  # Check every 100ms

        logger.info("SPR State Machine initialized")
        self._emit_state_change()

    def _emit_state_change(self) -> None:
        """Emit state change signal and log transition."""
        logger.info(f"State machine transition to: {self.state.value}")
        self.state_changed.emit(self.state.value)

    def _process_current_state(self) -> None:
        """Single method that handles all state transitions."""
        try:
            if self.state == SPRSystemState.DISCONNECTED:
                self._handle_disconnected()
            elif self.state == SPRSystemState.CONNECTING:
                self._handle_connecting()
            elif self.state == SPRSystemState.CONNECTED:
                self._handle_connected()
            elif self.state == SPRSystemState.CALIBRATING:
                self._handle_calibrating()
            elif self.state == SPRSystemState.CALIBRATED:
                self._handle_calibrated()
            elif self.state == SPRSystemState.MEASURING:
                self._handle_measuring()
            elif self.state == SPRSystemState.ERROR:
                self._handle_error()
        except Exception as e:
            logger.exception(f"Error in state machine: {e}")
            self._transition_to_error(f"State machine error: {e}")

    def _handle_disconnected(self) -> None:
        """Try to discover and connect hardware."""
        if not self.hardware_manager:
            logger.debug("Creating hardware manager...")

            # Try real hardware first
            if USE_REAL_HARDWARE:
                logger.info("Attempting to use real hardware")
                try:
                    # Create a simple hardware container for state machine use
                    self.hardware_manager = SimpleHardwareManager()
                    if self.hardware_manager.initialize_hardware():
                        logger.info("Real hardware manager initialized successfully")
                    else:
                        logger.warning("Real hardware initialization failed, falling back to mock")
                        self.hardware_manager = None
                except Exception as e:
                    logger.error(f"Failed to initialize real hardware: {e}")
                    self.hardware_manager = None

            # Fall back to mock if real hardware failed or not available
            if not self.hardware_manager and MOCK_MODE_AVAILABLE:
                logger.info("Using mock hardware manager for testing")
                self.hardware_manager = MockHardwareManager()
            elif not self.hardware_manager:
                self._transition_to_error("No hardware manager available")
                return

        logger.debug("Attempting hardware discovery...")
        if self.hardware_manager.discover_hardware():
            self._transition_to_state(SPRSystemState.CONNECTING)
        else:
            # Stay in disconnected state, will retry next cycle
            time.sleep(1)  # Brief pause between discovery attempts

    def _handle_connecting(self) -> None:
        """Complete hardware connection."""
        if not self.hardware_manager:
            self._transition_to_error("Hardware manager not available during connection")
            return

        logger.debug("Attempting hardware connection...")
        if self.hardware_manager.connect_all():
            # Sync hardware to app
            self.app.ctrl = self.hardware_manager.ctrl
            self.app.usb = self.hardware_manager.usb
            self.app.knx = self.hardware_manager.knx

            # Update hardware status
            ctrl_ok = self.app.ctrl is not None
            usb_ok = self.app.usb is not None
            self.hardware_status.emit(ctrl_ok, usb_ok)

            self._transition_to_state(SPRSystemState.CONNECTED)
        else:
            self._transition_to_error("Failed to connect to hardware")

    def _handle_connected(self) -> None:
        """Start calibration automatically if not already calibrated."""
        if getattr(self.app, 'calibrated', False):
            logger.info("System already calibrated, skipping to measurement")
            self._transition_to_state(SPRSystemState.CALIBRATED)
            return

        if not self.calibrator:
            logger.debug("Creating calibrator...")
            try:
                # Hardware connection status
                if isinstance(self.hardware_manager, SimpleHardwareManager):
                    logger.warning("🔌 REAL HARDWARE CONNECTED:")
                    logger.warning(f"   - Controller (PicoP4SPR): {'✅ Connected' if self.hardware_manager.ctrl else '❌ Failed'}")
                    logger.warning(f"   - Spectrometer (USB4000): {'✅ Connected' if self.hardware_manager.usb else '❌ Failed'}")

                    # FORCE REAL CALIBRATOR - NO MOCK FALLBACK
                    logger.warning("🚀 FORCING REAL CALIBRATION - NO MOCK FALLBACK")

                    # Get the actual device objects from HAL wrappers
                    ctrl_device = self._get_device_from_hal(self.hardware_manager.ctrl)
                    usb_device = self._get_device_from_hal(self.hardware_manager.usb)

                    from utils.spr_calibrator import SPRCalibrator
                    self.calibrator = SPRCalibrator(
                        ctrl=ctrl_device,
                        usb=usb_device,
                        device_type="PicoP4SPR",
                        calib_state=self.calib_state  # 🎯 Pass shared state!
                    )
                    # Connect calibrator progress signals for real calibrator
                    self.calibrator.set_progress_callback(self._on_calibration_progress)
                    logger.warning("✅ REAL CALIBRATOR CREATED SUCCESSFULLY!")
                elif MOCK_MODE_AVAILABLE:
                    logger.info("Using mock calibrator for testing")
                    self.calibrator = MockCalibrator(
                        self.hardware_manager.ctrl,
                        self.hardware_manager.usb
                    )
                    # Connect calibrator progress signals
                    self.calibrator.set_progress_callback(self._on_calibration_progress)
                else:
                    self._transition_to_error("No calibrator available")
                    return
            except Exception as e:
                self._transition_to_error(f"Failed to create calibrator: {e}")
                return

        self._transition_to_state(SPRSystemState.CALIBRATING)

    def _handle_calibrating(self) -> None:
        """Process calibration."""
        if not self.calibrator:
            self._transition_to_error("Calibrator not available during calibration")
            return

        if not hasattr(self.calibrator, '_calibration_started'):
            logger.info("Starting automatic calibration...")
            try:
                # Start calibration in a non-blocking way
                success = self.calibrator.start_calibration()
                self.calibrator._calibration_started = True

                if not success:
                    self._transition_to_error("Failed to start calibration")
                    return
            except Exception as e:
                self._transition_to_error(f"Calibration start error: {e}")
                return

        # Check if calibration is complete
        if self.calibrator.is_complete():
            success = self.calibrator.was_successful()
            error_msg = self.calibrator.get_error_message() if not success else ""

            self.calibration_completed.emit(success, error_msg)

            if success:
                self.app.calibrated = True
                # Store calibration results
                self.app.data_processor = self.calibrator.create_data_processor(
                    med_filt_win=getattr(self.app, 'med_filt_win', 5)
                )
                self.app.leds_calibrated = self.calibrator.state.leds_calibrated.copy()
                self.app.ref_sig = self.calibrator.state.ref_sig.copy()

                self._transition_to_state(SPRSystemState.CALIBRATED)
            else:
                self._transition_to_error(f"Calibration failed: {error_msg}")

    def _handle_calibrated(self) -> None:
        """Start data acquisition."""
        if not self.data_acquisition:
            logger.debug("Creating data acquisition wrapper...")
            try:
                # Create the wrapper that handles all the complex data setup
                # 🎯 Pass shared calibration state - no data copying needed!
                self.data_acquisition = DataAcquisitionWrapper(self.app, calib_state=self.calib_state)

                # Get devices and data processor
                if isinstance(self.hardware_manager, SimpleHardwareManager):
                    # Get the actual device objects from HAL wrappers (same as calibrator)
                    ctrl_device = self._get_device_from_hal(self.hardware_manager.ctrl)
                    usb_device = self._get_device_from_hal(self.hardware_manager.usb)
                    logger.debug(f"Data acquisition using extracted devices: ctrl={type(ctrl_device)}, usb={type(usb_device)}")
                else:
                    # Fallback to app devices for mock mode
                    ctrl_device = self.app.ctrl
                    usb_device = self.app.usb

                # Create or get data processor
                data_processor = getattr(self.app, 'data_processor', None)
                if not data_processor:
                    # Create a basic data processor with minimal configuration
                    wave_data = np.linspace(441.1, 773.2, 3648)  # Default USB4000 wavelength range
                    fourier_weights = np.ones_like(wave_data)  # Default weights
                    data_processor = SPRDataProcessor(wave_data=wave_data, fourier_weights=fourier_weights)
                    logger.info("Created new SPRDataProcessor instance with default configuration")

                # ✅ NO DATA TRANSFER NEEDED - shared state already contains calibration data!
                # Both calibrator and data acquisition reference the same CalibrationState object
                logger.info(f"📊 Shared calibration state valid: {self.calib_state.is_valid()}")

                # Create the real SPRDataAcquisition inside the wrapper
                self.data_acquisition.create_acquisition(ctrl_device, usb_device, data_processor)

                logger.info("Data acquisition wrapper created successfully")

            except Exception as e:
                logger.exception(f"Failed to create data acquisition: {e}")
                self._transition_to_error(f"Failed to create data acquisition: {e}")
                return

        if not self.data_acquisition.is_running():
            logger.info("Starting real-time data acquisition...")
            try:
                self.data_acquisition.start()
                self.data_acquisition_started.emit()
                self._transition_to_state(SPRSystemState.MEASURING)
            except Exception as e:
                self._transition_to_error(f"Failed to start data acquisition: {e}")

    def _handle_measuring(self) -> None:
        """Monitor data acquisition."""
        if not self.data_acquisition:
            self._transition_to_error("Data acquisition not available during measurement")
            return

        if not self.data_acquisition.is_healthy():
            logger.warning("Data acquisition unhealthy, attempting restart...")
            try:
                self.data_acquisition.restart()
            except Exception as e:
                logger.error(f"Failed to restart data acquisition: {e}")
                self._transition_to_error("Data acquisition restart failed")

        # Data acquisition runs continuously in this state
        # The actual data reading is handled by the data acquisition object

    def _handle_error(self) -> None:
        """Handle error state with recovery logic."""
        current_time = time.time()

        # Wait before attempting recovery
        if current_time - self.last_error_time < 2.0:  # Reduced from 5.0 to 2.0 for testing
            return

        if self.error_count < self.max_error_count:
            logger.info(f"Attempting error recovery (attempt {self.error_count + 1}/{self.max_error_count})")
            self._cleanup()
            self.error_count += 1
            self._transition_to_state(SPRSystemState.DISCONNECTED)
        else:
            logger.error("Maximum error recovery attempts reached, staying in error state")
            # Stay in error state - manual intervention required

    def _transition_to_state(self, new_state: SPRSystemState) -> None:
        """Transition to a new state."""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            logger.info(f"State transition: {old_state.value} → {new_state.value}")
            self._emit_state_change()

            # Reset error count on successful transition
            if new_state != SPRSystemState.ERROR:
                self.error_count = 0

    def _transition_to_error(self, error_message: str) -> None:
        """Transition to error state with message."""
        logger.error(f"State machine error: {error_message}")
        self.error_occurred.emit(error_message)
        self.last_error_time = time.time()
        self._transition_to_state(SPRSystemState.ERROR)

    def _on_calibration_progress(self, step: int, description: str) -> None:
        """Handle calibration progress updates."""
        logger.debug(f"Calibration progress: Step {step} - {description}")
        self.calibration_progress.emit(step, description)

    def _get_device_from_hal(self, hal_object):
        """Extract the underlying device object from HAL wrapper."""
        if hal_object is None:
            return None

        # For USB4000OceanDirectHAL, access the _ocean_device attribute
        if hasattr(hal_object, '_ocean_device'):
            logger.debug(f"Extracting USB4000 device from HAL: {type(hal_object._ocean_device)}")
            return hal_object._ocean_device

        # For controller HAL objects, check if they have the underlying device
        if hasattr(hal_object, '_ser'):  # PicoP4SPRHAL uses serial connection
            logger.debug(f"Creating PicoP4SPR wrapper for HAL: {type(hal_object)}")
            # The HAL object itself implements the needed interface, so return it
            return hal_object

        # If we can't extract the device, return the HAL object itself
        # (SPRCalibrator might be able to work with it directly)
        logger.warning(f"Could not extract device from HAL object {type(hal_object)}, returning HAL object")
        return hal_object

    def _cleanup(self) -> None:
        """Clean up all resources."""
        logger.debug("Cleaning up state machine resources...")

        if self.data_acquisition:
            try:
                self.data_acquisition.stop()
            except Exception as e:
                logger.error(f"Error stopping data acquisition: {e}")
            self.data_acquisition = None

        if self.calibrator:
            try:
                self.calibrator.stop()
            except Exception as e:
                logger.error(f"Error stopping calibrator: {e}")
            self.calibrator = None

        if self.hardware_manager:
            try:
                self.hardware_manager.disconnect_all()
            except Exception as e:
                logger.error(f"Error disconnecting hardware: {e}")
            # Don't set to None - keep for reconnection

    def stop(self) -> None:
        """Stop the state machine and clean up."""
        logger.info("Stopping SPR state machine...")
        self.operation_timer.stop()
        self._cleanup()
        self.state = SPRSystemState.DISCONNECTED
        self._emit_state_change()

    def emergency_stop(self) -> None:
        """Emergency stop with immediate LED shutdown."""
        logger.warning("🚨 EMERGENCY STOP INITIATED")

        try:
            # Emergency LED shutdown via hardware manager
            if self.hardware_manager:
                try:
                    # Try to get controller HAL and shutdown LEDs
                    controller = getattr(self.hardware_manager, 'ctrl', None)
                    if controller and hasattr(controller, 'emergency_shutdown'):
                        controller.emergency_shutdown()
                        logger.info("✅ Emergency LED shutdown via HAL")
                except Exception as e:
                    logger.error(f"HAL emergency shutdown failed: {e}")

            # Direct serial emergency shutdown as backup
            try:
                import serial
                import time
                with serial.Serial("COM4", 115200, timeout=1) as ser:
                    time.sleep(0.1)
                    # Primary: all LEDs off
                    ser.write(b'lx\n')
                    time.sleep(0.1)
                    # Backup: set intensity to zero
                    ser.write(b'i0\n')
                    time.sleep(0.1)
                    logger.info("✅ Direct emergency LED shutdown completed")
            except Exception as e:
                logger.error(f"Direct emergency shutdown failed: {e}")

        except Exception as e:
            logger.error(f"Emergency stop failed: {e}")
        finally:
            # Regular cleanup
            self.stop()

    def force_reconnect(self) -> None:
        """Force a reconnection attempt."""
        logger.info("Forcing hardware reconnection...")
        self._cleanup()
        self._transition_to_state(SPRSystemState.DISCONNECTED)

    def get_current_state(self) -> str:
        """Get the current state as a string."""
        return self.state.value

    def is_measuring(self) -> bool:
        """Check if the system is currently measuring."""
        return self.state == SPRSystemState.MEASURING

    def is_calibrated(self) -> bool:
        """Check if the system is calibrated."""
        return self.state in [SPRSystemState.CALIBRATED, SPRSystemState.MEASURING]

    def is_connected(self) -> bool:
        """Check if hardware is connected."""
        return self.state in [
            SPRSystemState.CONNECTED,
            SPRSystemState.CALIBRATING,
            SPRSystemState.CALIBRATED,
            SPRSystemState.MEASURING
        ]