"""SPR System State Machine for simplified hardware and operation management."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Optional, Union

from PySide6.QtCore import QObject, QTimer, Signal, QThread

from utils.logger import logger
from settings.settings import NUM_SCANS_PER_ACQUISITION, LED_DELAY, PRE_LED_DELAY_MS, POST_LED_DELAY_MS
from settings import CH_LIST

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

from utils.data_buffer_manager import DataBufferManager
from utils.spr_data_acquisition import SPRDataAcquisition
from utils.spr_data_processor import SPRDataProcessor
import threading
import numpy as np


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
        # 🚀 PERFORMANCE: Use DataBufferManager with pandas-backed TimeSeriesBuffer
        # Provides 10-100× speedup via batched operations vs repeated np.append()
        self.buffer_manager = DataBufferManager(channels=CH_LIST)

        # Reference the buffer manager's property dicts for backwards compatibility
        self.lambda_values = self.buffer_manager.lambda_values
        self.lambda_times = self.buffer_manager.lambda_times
        self.filtered_lambda = self.buffer_manager.filtered_lambda
        self.buffered_lambda = self.buffer_manager.buffered_lambda
        self.buffered_times = self.buffer_manager.buffered_times
        self.int_data = self.buffer_manager.int_data
        self.trans_data = self.buffer_manager.trans_data
        self.ref_sig = {ch: None for ch in CH_LIST}

        # Configuration defaults
        self.wave_data = np.array([])
        self.num_scans = NUM_SCANS_PER_ACQUISITION  # ✨ PHASE 2: 4 × 50ms scans = 200ms
        self.led_delay = LED_DELAY  # Back-compat single delay
        # Separate pre/post LED delays (seconds)
        try:
            self.led_on_delay = float(PRE_LED_DELAY_MS) / 1000.0
            self.led_off_delay = float(POST_LED_DELAY_MS) / 1000.0
        except Exception:
            self.led_on_delay = float(self.led_delay)
            self.led_off_delay = float(self.led_delay)
        self.med_filt_win = 5
        self.dark_noise = np.zeros(3648)  # Match USB4000 pixel count (3648)
        self.base_integration_time_factor = 1.0  # Fiber-specific speed multiplier

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

                def set_intensity(self, ch: str, raw_val: int) -> bool:
                    """Set LED intensity using HAL's normalized API.

                    Args:
                        ch: Channel identifier ('a','b','c','d') - ignored by HAL (global intensity)
                        raw_val: 0-255 intensity value

                    Returns:
                        True if set succeeded, False otherwise

                    Note:
                        HAL sets intensity for all channels; only the active channel emits light.
                        This effectively behaves as per-channel intensity when called before activation.
                    """
                    try:
                        logger.debug(f"ControllerAdapter.set_intensity -> ch={ch}, raw_val={raw_val}")
                        # Prefer per-channel API when available (activates the channel too on Pico)
                        if hasattr(self.hal, 'set_intensity'):
                            ok = bool(self.hal.set_intensity(ch=ch, raw_val=raw_val))
                            logger.warning(f"🔧 HAL.set_intensity(ch={ch}, raw={raw_val}) → {ok}")
                            return ok
                        # Fallback to global normalized intensity
                        if hasattr(self.hal, 'set_led_intensity'):
                            norm = max(0.0, min(1.0, float(raw_val) / 255.0))
                            ok = bool(self.hal.set_led_intensity(norm))
                            logger.warning(f"🔧 HAL.set_led_intensity(norm={norm:.2f}) → {ok}")
                            return ok
                    except Exception as e:
                        logger.debug(f"ControllerAdapter.set_intensity error: {e}")
                    return False

                def turn_on_channel(self, ch: str) -> None:
                    """Turn on specific channel LED.

                    ✨ PHASE 1B OPTIMIZED: Single command fire-and-forget
                    - Sends one "lX\n" command to activate channel (2ms)
                    - Skips redundant intensity setting (was 8ms for all 4 channels)
                    - Total: 2ms instead of 110ms (activate 105ms + intensity 5ms)
                    """
                    if not hasattr(self.hal, 'activate_channel'):
                        return

                    # Import ChannelID enum for proper conversion
                    from utils.hal.spr_controller_hal import ChannelID
                    channel_map = {'a': ChannelID.A, 'b': ChannelID.B, 'c': ChannelID.C, 'd': ChannelID.D}
                    ch_id = channel_map.get(ch.lower())

                    if ch_id:
                        # Single optimized call - no intensity setting needed
                        # (Intensity is already set during calibration and doesn't change)
                        self.hal.activate_channel(ch_id)

                def turn_off_channels(self) -> None:
                    """Turn off all channel LEDs."""
                    # Prefer dedicated HAL method that preserves configured intensities
                    # and only turns emission off (firmware 'lx').
                    if hasattr(self.hal, 'turn_off_channels'):
                        try:
                            self.hal.turn_off_channels()
                        except Exception:
                            # Fallbacks in case of legacy naming
                            if hasattr(self.hal, 'turn_off_all_leds'):
                                try:
                                    self.hal.turn_off_all_leds()
                                except Exception:
                                    pass
                            elif hasattr(self.hal, 'set_led_intensity'):
                                # Last resort: dim to 0 (note this wipes configured intensity)
                                try:
                                    self.hal.set_led_intensity(0)
                                except Exception:
                                    pass
                    elif hasattr(self.hal, 'turn_off_all_leds'):
                        try:
                            self.hal.turn_off_all_leds()
                        except Exception:
                            pass
                    elif hasattr(self.hal, 'set_led_intensity'):
                        # Last resort: dim to 0 (note this wipes configured intensity)
                        try:
                            self.hal.set_led_intensity(0)
                        except Exception:
                            pass

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

            # ✨ Store USB adapter so sync_from_shared_state() can access it
            self.usb_adapter = adapted_usb

            # 🎯 Sync from shared calibration state before creating acquisition
            if self.calib_state is not None:
                self.sync_from_shared_state()

            self.data_acquisition = SPRDataAcquisition(
                # Hardware references
                ctrl=adapted_ctrl,
                usb=adapted_usb,
                data_processor=data_processor,
                # Data storage - NEW: pass buffer manager for performance
                buffer_manager=self.buffer_manager,
                # Data storage references (backwards compatibility)
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
                num_scans=self.num_scans,
                led_delay=self.led_on_delay + self.led_off_delay,
                led_on_delay=self.led_on_delay,
                led_off_delay=self.led_off_delay,
                med_filt_win=self.med_filt_win,
                dark_noise=self.dark_noise,
                base_integration_time_factor=self.base_integration_time_factor,
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
                # Diagnostic signal (optional, connected later if diagnostic viewer is opened)
                processing_steps_signal=self._get_app_signal('processing_steps_signal', required=False),
            )

            # Set calibration state
            self.data_acquisition.set_configuration(calibrated=True)

            # ✨ CRITICAL FIX: Load cached integration time and calculate smart boost
            # When device is already calibrated, calib_state.integration may not be loaded
            # Load it from device_config.json and calculate the boost
            try:
                from settings import (
                    LIVE_MODE_MAX_BOOST_FACTOR,
                    LIVE_MODE_TARGET_INTENSITY_PERCENT,
                    TARGET_INTENSITY_PERCENT,
                    MIN_INTEGRATION
                )

                # Try to load from device config first
                integration_ms = None
                try:
                    cal_data = device_config.load_led_calibration()
                    if cal_data and 'integration_time_ms' in cal_data:
                        integration_ms = cal_data['integration_time_ms']
                        logger.info(f"� Loaded cached integration time: {integration_ms}ms")
                except Exception as e:
                    logger.debug(f"Could not load from device_config: {e}")

                # Fall back to calib_state if available
                if not integration_ms and self.calib_state and self.calib_state.integration > 0:
                    integration_ms = self.calib_state.integration * 1000  # Convert seconds to ms
                    logger.info(f"📥 Using calib_state integration time: {integration_ms}ms")

                # If we have an integration time, calculate and apply boost
                if integration_ms and integration_ms > MIN_INTEGRATION:
                    integration_seconds = integration_ms / 1000.0
                    desired_boost = LIVE_MODE_TARGET_INTENSITY_PERCENT / TARGET_INTENSITY_PERCENT
                    boost_factor = max(1.0, min(desired_boost, LIVE_MODE_MAX_BOOST_FACTOR))
                    live_integration_seconds = integration_seconds * boost_factor

                    # Store it on both objects
                    self.live_integration_seconds = live_integration_seconds
                    self.data_acquisition.live_integration_seconds = live_integration_seconds

                    logger.info(f"")
                    logger.info(f"🔋 SMART BOOST APPLIED (from cached calibration):")
                    logger.info(f"   Calibrated integration: {integration_ms:.1f}ms")
                    logger.info(f"   Boost factor: {boost_factor:.2f}×")
                    logger.info(f"   Live integration: {live_integration_seconds*1000:.1f}ms")
                    logger.info(f"✅ Passed smart boost integration time to DataAcquisitionWrapper: {live_integration_seconds*1000:.1f}ms")
                else:
                    logger.warning(f"⚠️ No cached integration time found or too low ({integration_ms}ms) - using fallback")

            except Exception as e:
                logger.error(f"❌ Failed to apply smart boost from cache: {e}", exc_info=True)

            # Provide per-channel dark noise if available (for per-channel mode parity)
            try:
                if self.calib_state is not None and hasattr(self.calib_state, 'per_channel_dark_noise') and self.calib_state.per_channel_dark_noise:
                    self.data_acquisition.per_channel_dark_noise = self.calib_state.per_channel_dark_noise.copy()
                    logger.debug("✅ Provided per-channel dark noise to data acquisition")
            except Exception as _e:
                logger.debug(f"Could not provide per-channel dark noise to DAQ: {_e}")

            # Provide calibrated LED map for DAQ-side fallbacks if needed
            try:
                if hasattr(self.calib_state, 'ref_intensity') and isinstance(self.calib_state.ref_intensity, dict):
                    self.data_acquisition.calibrated_leds = self.calib_state.ref_intensity.copy()
                    logger.debug("✅ Provided calibrated_leds map to data acquisition")
            except Exception as _e:
                logger.debug(f"Could not provide calibrated_leds to DAQ: {_e}")

            # ✨ Pass adjusted LED intensities to data acquisition
            if hasattr(self, 'live_led_intensities') and self.live_led_intensities:
                self.data_acquisition.live_led_intensities = self.live_led_intensities
                logger.info(f"✅ Passed adjusted LED intensities to data acquisition")

            # ✨ Pass per-channel scan counts to data acquisition (200ms budget optimization)
            if self.calib_state is not None and hasattr(self.calib_state, 'scans_per_channel'):
                self.data_acquisition.scans_per_channel = self.calib_state.scans_per_channel.copy()
                logger.info("✅ Passed per-channel scan counts to data acquisition:")
                for ch, scans in self.calib_state.scans_per_channel.items():
                    logger.info(f"   Channel {ch.upper()}: {scans} scans")

            # ✨ Pass per-channel integration times to data acquisition (per_channel mode)
            if self.calib_state is not None and hasattr(self.calib_state, 'integration_per_channel'):
                self.data_acquisition.integration_per_channel = self.calib_state.integration_per_channel.copy()
                logger.info("✅ Passed per-channel integration times to data acquisition:")
                for ch, integration in self.calib_state.integration_per_channel.items():
                    logger.info(f"   Channel {ch.upper()}: {integration*1000:.1f}ms")

            # 🚀 Live per-channel override: boosted per-channel integrations and scans=1
            if hasattr(self, 'live_integration_per_channel') and self.live_integration_per_channel:
                self.data_acquisition.integration_per_channel = self.live_integration_per_channel.copy()
                # Force scans=1 per channel in live per-channel mode
                self.data_acquisition.scans_per_channel = {ch: 1 for ch in self.live_integration_per_channel.keys()}
                logger.info("✅ Applied live-mode per-channel overrides:")
                for ch, integration in self.live_integration_per_channel.items():
                    logger.info(f"   {ch.upper()}: {integration*1000:.1f}ms, scans=1")

            logger.info("SPRDataAcquisition created successfully")

            # Prepare hardware + live policy via calibrator helper (optional, non-fatal)
            try:
                if hasattr(self, 'calibrator') and self.calibrator is not None and adapted_ctrl is not None and adapted_usb is not None:
                    self.live_config = self.calibrator.prepare_live(ctrl=adapted_ctrl, usb=adapted_usb, ch_list=CH_LIST)
                    logger.info("✅ Live preparation complete (mode-aware application and policy built)")
            except Exception as _e:
                logger.debug(f"prepare_live skipped: {_e}")

        except Exception as e:
            logger.exception(f"Failed to create SPRDataAcquisition: {e}")
            raise

    def _get_app_signal(self, signal_name: str, required: bool = True) -> Any:
        """Get a signal from the app, or create a dummy emitter.

        Args:
            signal_name: Name of the signal to get
            required: If False, returns None if signal not found instead of creating dummy
        """
        if hasattr(self.app, signal_name):
            app_signal = getattr(self.app, signal_name)
            logger.debug(f"🔗 Found app signal {signal_name}: {type(app_signal)}")
            return app_signal
        else:
            if not required:
                logger.debug(f"⚠️ Optional signal {signal_name} not found - returning None")
                return None
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
                    logger.info(f"✅ Synced wavelengths: {len(self.wave_data)} points (using wavelength-based filtering)")

                if len(self.calib_state.dark_noise) > 0:
                    self.dark_noise = self.calib_state.dark_noise
                    logger.info(f"✅ Synced dark noise: {len(self.dark_noise)} points")

                # Sync reference signals
                for ch in CH_LIST:
                    if self.calib_state.ref_sig.get(ch) is not None:
                        self.ref_sig[ch] = self.calib_state.ref_sig[ch]
                        try:
                            ref_obj = self.ref_sig[ch]
                            if ref_obj is None:
                                logger.debug(f"Ref_sig for {ch} is None; skipping normalization")
                            else:
                                import numpy as _np
                                ref_arr = _np.asarray(ref_obj, dtype=float).reshape(-1)
                                ref_len = ref_arr.shape[0]
                                wave_len = len(self.wave_data) if hasattr(self, 'wave_data') and self.wave_data is not None else 0
                                if wave_len > 0 and ref_len != wave_len:
                                    # One-time normalization: resample S-ref to match filtered wavelength length
                                    x_old = _np.linspace(0.0, 1.0, ref_len)
                                    x_new = _np.linspace(0.0, 1.0, wave_len)
                                    _resampled = _np.interp(x_new, x_old, ref_arr)
                                    # Assign via cast to avoid overzealous type checkers
                                    from typing import cast as _cast, Any as _Any
                                    self.ref_sig[ch] = _cast(_Any, _resampled)
                                    logger.warning(
                                        f"🔧 Normalized ref_sig[{ch}] size: {ref_len} → {wave_len} to match filtered wavelengths"
                                    )
                        except Exception as _e:
                            logger.debug(f"Ref_sig normalization skipped for {ch}: {_e}")
                        try:
                            import numpy as _np
                            _obj = self.ref_sig[ch]
                            _size = int(_np.size(_obj)) if _obj is not None else 0
                        except Exception:
                            _size = 0
                        logger.info(f"✅ Synced ref_sig[{ch}]: {_size} points")

                # Sync fiber-specific integration time factor
                self.base_integration_time_factor = self.calib_state.base_integration_time_factor
                logger.info(
                    f"⚡ Integration time factor: {self.base_integration_time_factor}x "
                    f"({'2x faster' if self.base_integration_time_factor == 0.5 else 'standard'})"
                )

                # Calculate dynamic scan count / boost policy for live mode
                # IMPORTANT: LED intensities from Step 6 are FIXED and never change
                # We only boost integration time by 20-40% to offset P-pol dampening
                # Global: stay within a 200ms window by adjusting scan count
                # Per-channel: scans=1; adjust per-channel integration, capped at 200ms

                # ✨ CRITICAL: Determine if we're ACTUALLY in per-channel mode
                # Check if integration > 0 (GLOBAL mode) or if integration_per_channel is the PRIMARY mode
                is_per_channel_mode = (
                    hasattr(self.calib_state, 'integration_per_channel')
                    and self.calib_state.integration_per_channel
                    and not self.calib_state.integration  # GLOBAL mode has integration > 0
                )

                if self.calib_state.integration > 0 or is_per_channel_mode:
                    from settings import (
                        LIVE_MODE_MAX_INTEGRATION_MS,
                        LIVE_MODE_TARGET_INTENSITY_PERCENT,
                        LIVE_MODE_SATURATION_THRESHOLD_PERCENT,
                        LIVE_MODE_MIN_BOOST_FACTOR,
                        LIVE_MODE_MAX_BOOST_FACTOR,
                        TARGET_INTENSITY_PERCENT,
                        DETECTOR_MAX_COUNTS
                    )
                    from utils.spr_calibrator import calculate_dynamic_scans

                    integration_seconds = float(self.calib_state.integration) if self.calib_state.integration else 0.0

                    # Calculate smart boost factor (20-40% increase for P-pol compensation)
                    # Calibration reached TARGET_INTENSITY_PERCENT (50%) with S-pol
                    # P-pol has ~30-40% lower signal, so we boost 20-40% to compensate
                    # Conservative approach: use calibrated LED values, boost integration time only
                    desired_boost = LIVE_MODE_TARGET_INTENSITY_PERCENT / TARGET_INTENSITY_PERCENT

                    # Apply safety constraints
                    # Min: 1.0× (never reduce below calibration)
                    # Max: 1.4× (40% increase - conservative, safe)
                    boost_factor = max(LIVE_MODE_MIN_BOOST_FACTOR,
                                      min(desired_boost, LIVE_MODE_MAX_BOOST_FACTOR))

                    logger.info(f"")
                    logger.info(f"🔋 SMART BOOST CALCULATION:")
                    logger.info(f"   Calibration target: {TARGET_INTENSITY_PERCENT}% (S-pol baseline)")
                    logger.info(f"   Live mode target: {LIVE_MODE_TARGET_INTENSITY_PERCENT}% (P-pol compensated)")
                    logger.info(f"   Desired boost: {desired_boost:.2f}× (= {LIVE_MODE_TARGET_INTENSITY_PERCENT}/{TARGET_INTENSITY_PERCENT})")
                    logger.info(f"   Applied boost: {boost_factor:.2f}× (capped at {LIVE_MODE_MAX_BOOST_FACTOR}×)")
                    logger.info(f"   🔒 LED intensities: FIXED from Step 6 (never change)")

                    # LED policy: Use Step 6 calibrated values directly (NO adjustment)
                    # Step 6 LEDs are optimized for S-pol and remain fixed for live P-pol measurements
                    try:
                        if hasattr(self, 'calibrator') and self.calibrator is not None:
                            self.live_led_intensities = {ch: int(self.calibrator.get_led_for_live(ch)) for ch in CH_LIST}
                        else:
                            # Conservative fallback if calibrator unavailable
                            self.live_led_intensities = {ch: int(getattr(self.calib_state, 'leds_calibrated', {}).get(ch, 255)) for ch in CH_LIST}
                    except Exception as _e:
                        logger.debug(f"live_led_intensities from calibrator failed: {_e}")
                        self.live_led_intensities = {ch: 255 for ch in CH_LIST}

                    # Per-channel live mode: boost each channel's integration, cap at 200ms, force scans=1
                    # ✨ CRITICAL FIX: Only use per-channel mode if integration is NOT set (i.e., true per-channel calibration)
                    if is_per_channel_mode:
                        max_integration_seconds = LIVE_MODE_MAX_INTEGRATION_MS / 1000.0
                        self.live_integration_per_channel = {}
                        for ch, base_int in self.calib_state.integration_per_channel.items():
                            boosted = float(base_int) * boost_factor

                            # Safety: Cap at 200ms budget
                            if boosted > max_integration_seconds:
                                boosted = max_integration_seconds
                                logger.warning(
                                    f"   ⚠️ Channel {ch.upper()}: Boost capped at {max_integration_seconds*1000:.1f}ms "
                                    f"(200ms budget limit)"
                                )

                            self.live_integration_per_channel[ch] = boosted

                        # Scans per spectrum fixed at 1 in per-channel mode
                        self.num_scans = 1

                        logger.info("")
                        logger.info("="*80)
                        logger.info("🚀 LIVE MODE (PER-CHANNEL) SMART BOOST")
                        logger.info("="*80)
                        logger.info(f"🎯 Strategy: Fixed LEDs + Boosted integration (20-40%)")
                        logger.info(f"   Target signal: {LIVE_MODE_TARGET_INTENSITY_PERCENT}% (~{int(DETECTOR_MAX_COUNTS*LIVE_MODE_TARGET_INTENSITY_PERCENT/100)} counts)")
                        logger.info(f"   Saturation threshold: {LIVE_MODE_SATURATION_THRESHOLD_PERCENT}% (~{int(DETECTOR_MAX_COUNTS*LIVE_MODE_SATURATION_THRESHOLD_PERCENT/100)} counts)")
                        logger.info(f"")
                        logger.info(f"Per-channel adjustments:")
                        for ch, boosted_int in self.live_integration_per_channel.items():
                            try:
                                base_ms = float(self.calib_state.integration_per_channel.get(ch, 0.0)) * 1000.0
                            except Exception:
                                base_ms = 0.0
                            logger.info(f"   {ch.upper()}: {base_ms:.1f}ms → {boosted_int*1000.0:.1f}ms (scans=1)")
                        logger.info("="*80)

                        # ✨ CRITICAL FIX: Apply boosted integration times to data acquisition wrapper
                        if hasattr(self, 'data_acquisition') and self.data_acquisition:
                            self.data_acquisition.integration_per_channel = self.live_integration_per_channel.copy()
                            logger.info(f"✅ Applied boosted integration_per_channel to DataAcquisitionWrapper")
                            logger.info(f"   Boosted values: {[(ch, f'{v*1000:.1f}ms') for ch, v in self.live_integration_per_channel.items()]}")
                        else:
                            logger.warning(f"⚠️ DataAcquisitionWrapper not available - boost will be applied when created")
                            logger.warning(f"   Will apply these values when DAQ is created: {[(ch, f'{v*1000:.1f}ms') for ch, v in self.live_integration_per_channel.items()]}")

                    else:
                        # Global live mode: boost integration and select dynamic scans under 200ms
                        live_integration_seconds = integration_seconds * boost_factor

                        # Enforce maximum integration time limit (200ms)
                        max_integration_seconds = LIVE_MODE_MAX_INTEGRATION_MS / 1000.0
                        if live_integration_seconds > max_integration_seconds:
                            live_integration_seconds = max_integration_seconds
                            actual_boost = live_integration_seconds / max(integration_seconds, 1e-9)
                            logger.info(
                                f"⚠️ Integration time capped at {LIVE_MODE_MAX_INTEGRATION_MS}ms "
                                f"(boost limited to {actual_boost:.2f}×)"
                            )
                        else:
                            actual_boost = boost_factor

                        # Store for later use
                        self.live_integration_seconds = live_integration_seconds
                        # Also expose to data acquisition wrapper (so the acquisition thread can see it)
                        try:
                            if hasattr(self, 'data_acquisition') and self.data_acquisition is not None:
                                setattr(self.data_acquisition, 'live_integration_seconds', live_integration_seconds)
                        except Exception as _e:
                            logger.debug(f"Could not propagate live_integration_seconds to DAQ: {_e}")
                        self.live_boost_factor = actual_boost

                        # Calculate expected signal level (for weakest channel)
                        expected_intensity_percent = TARGET_INTENSITY_PERCENT * actual_boost
                        expected_counts = int(DETECTOR_MAX_COUNTS * expected_intensity_percent / 100)

                        # Use calibrator helper for consistent 200ms target (policy parity)
                        try:
                            if hasattr(self, 'calibrator') and self.calibrator is not None:
                                self.num_scans = int(self.calibrator.get_scans_for_live(live_integration_seconds))
                            else:
                                self.num_scans = calculate_dynamic_scans(live_integration_seconds)
                        except Exception:
                            self.num_scans = calculate_dynamic_scans(live_integration_seconds)

                        logger.info("")
                        logger.info("="*80)
                        logger.info("🚀 LIVE MODE INTEGRATION TIME BOOST (GLOBAL)")
                        logger.info("="*80)
                        logger.info(f"📊 Calibration settings:")
                        logger.info(f"   Integration time: {integration_seconds*1000:.1f}ms")
                        logger.info(f"   Target signal: {TARGET_INTENSITY_PERCENT}% (~{int(DETECTOR_MAX_COUNTS*TARGET_INTENSITY_PERCENT/100)} counts)")
                        logger.info(f"")
                        logger.info(f"🎯 Live mode optimization:")
                        logger.info(f"   Target signal: {LIVE_MODE_TARGET_INTENSITY_PERCENT}% (~{int(DETECTOR_MAX_COUNTS*LIVE_MODE_TARGET_INTENSITY_PERCENT/100)} counts)")
                        logger.info(f"   Boost factor: {boost_factor:.2f}× (max: {LIVE_MODE_MAX_BOOST_FACTOR}×)")
                        logger.info(f"   Boosted integration: {integration_seconds*1000:.1f}ms → {live_integration_seconds*1000:.1f}ms")
                        logger.info(f"   Expected signal: {expected_intensity_percent:.1f}% (~{expected_counts} counts)")
                        logger.info(f"")
                        logger.info(f"⚡ Acquisition performance:")
                        logger.info(f"   Scans per channel: {self.num_scans}")
                        logger.info(f"   Time per channel: ~{live_integration_seconds*self.num_scans*1000:.0f}ms")
                        logger.info(f"   Update rate: ~{1.0/(live_integration_seconds*self.num_scans*4):.1f} Hz per channel")
                        logger.info("="*80)
                        logger.info("")

                        # Apply the boosted integration time to the spectrometer (global mode only)
                        # ✨ CRITICAL FIX: Apply to BOTH usb_adapter AND data_acquisition.usb
                        # The state machine and data acquisition may reference different wrapper objects
                        integration_applied = False

                        # Try state machine's usb_adapter first
                        if hasattr(self, 'usb_adapter') and self.usb_adapter is not None:
                            try:
                                # Log BEFORE setting
                                current_int = None
                                if hasattr(self.usb_adapter, 'get_integration_time'):
                                    current_int = float(self.usb_adapter.get_integration_time())
                                elif hasattr(self.usb_adapter, 'integration_time'):
                                    current_int = float(self.usb_adapter.integration_time)
                                logger.warning(f"⚠️ BOOST APPLICATION: BEFORE applying integration on usb_adapter")
                                logger.warning(f"   Current spectrometer integration: {current_int*1000 if current_int is not None else 'unknown'}ms")
                                logger.warning(f"   About to set to: {live_integration_seconds*1000:.1f}ms")
                            except Exception as e:
                                logger.debug(f"Could not read current integration: {e}")

                            if hasattr(self.usb_adapter, 'set_integration'):
                                self.usb_adapter.set_integration(live_integration_seconds)
                                integration_applied = True
                                logger.info(f"✅ Applied boosted integration time to usb_adapter: {live_integration_seconds*1000:.1f}ms")

                                # Verify it was actually set
                                try:
                                    time.sleep(0.1)  # Give hardware time to update
                                    new_int = None
                                    if hasattr(self.usb_adapter, 'get_integration_time'):
                                        new_int = float(self.usb_adapter.get_integration_time())
                                    elif hasattr(self.usb_adapter, 'integration_time'):
                                        new_int = float(self.usb_adapter.integration_time)
                                    logger.warning(f"⚠️ BOOST VERIFICATION: AFTER applying integration")
                                    logger.warning(f"   Spectrometer now reports: {new_int*1000 if new_int is not None else 'unknown'}ms")
                                    if new_int is not None and abs(new_int - live_integration_seconds) > 0.002:
                                        logger.error(f"❌ CRITICAL: Integration time did NOT stick! Expected {live_integration_seconds*1000:.1f}ms but got {new_int*1000:.1f}ms")
                                except Exception as e:
                                    logger.debug(f"Could not verify integration: {e}")
                            elif hasattr(self.usb_adapter, 'set_integration_time'):
                                self.usb_adapter.set_integration_time(live_integration_seconds)
                                integration_applied = True
                                logger.info(f"✅ Applied boosted integration time to usb_adapter: {live_integration_seconds*1000:.1f}ms")
                            else:
                                logger.error(f"❌ Cannot set integration time on usb_adapter - no suitable method found")

                        # ✨ CRITICAL: Also apply to data_acquisition.usb (the object grab_data() actually uses!)
                        if hasattr(self, 'data_acquisition') and self.data_acquisition is not None:
                            if hasattr(self.data_acquisition, 'usb') and self.data_acquisition.usb is not None:
                                try:
                                    if hasattr(self.data_acquisition.usb, 'set_integration'):
                                        self.data_acquisition.usb.set_integration(live_integration_seconds)
                                        integration_applied = True
                                        logger.info(f"✅ Applied boosted integration time to data_acquisition.usb: {live_integration_seconds*1000:.1f}ms")
                                    elif hasattr(self.data_acquisition.usb, 'set_integration_time'):
                                        self.data_acquisition.usb.set_integration_time(live_integration_seconds)
                                        integration_applied = True
                                        logger.info(f"✅ Applied boosted integration time to data_acquisition.usb: {live_integration_seconds*1000:.1f}ms")
                                except Exception as e:
                                    logger.error(f"❌ Failed to apply integration time to data_acquisition.usb: {e}")

                        if not integration_applied:
                            logger.error(f"❌ CRITICAL: Could not apply boosted integration time to ANY spectrometer object!")
                            logger.error(f"   This will cause weak signal (5ms instead of {live_integration_seconds*1000:.1f}ms)")

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
                logger.debug("Attempting to auto-detect PicoP4SPR controller...")
                # Let HAL auto-detect the correct port
                self.ctrl = self.HALFactory.create_controller(
                    "PicoP4SPR",
                    auto_detect=True,
                )
                if self.ctrl and self.ctrl.is_connected():
                    logger.info("Controller connected successfully")
                else:
                    logger.warning("Controller connection failed")
                    self.ctrl = None
            except Exception as e:
                logger.error(f"Controller connection error: {e}")
                self.ctrl = None

            # Try to create spectrometer using class method with timeout
            try:
                logger.warning("DEBUG: About to create spectrometer with 5s timeout...")

                # Use threading to implement timeout for blocking SeaBreeze calls
                import threading
                spec_result = [None]  # Mutable container for result
                spec_error = [None]

                def create_spec_with_timeout():
                    try:
                        spec_result[0] = self.HALFactory.create_spectrometer(auto_detect=True)
                    except Exception as e:
                        spec_error[0] = e

                spec_thread = threading.Thread(target=create_spec_with_timeout, daemon=True)
                spec_thread.start()
                spec_thread.join(timeout=5.0)  # 5 second timeout

                if spec_thread.is_alive():
                    logger.warning("Spectrometer creation timed out after 5s - SeaBreeze blocking detected")
                    self.usb = None
                elif spec_error[0]:
                    logger.error(f"Spectrometer connection error: {spec_error[0]}")
                    self.usb = None
                else:
                    self.usb = spec_result[0]
                    logger.warning("DEBUG: Spectrometer creation returned")
                    if self.usb:
                        try:
                            _ = getattr(self.usb, 'device_name', 'USB4000')
                            logger.info("Spectrometer connected successfully")
                        except Exception:
                            logger.warning("Spectrometer connection may be incomplete")
                    else:
                        logger.warning("Spectrometer connection failed")

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


class HardwareConnectionWorker(QObject):
    """Worker to perform hardware connection in background thread."""

    # Signals
    connection_completed = Signal(bool)  # success

    def __init__(self, hardware_manager):
        super().__init__()
        self.hardware_manager = hardware_manager

    def run(self):
        """Perform hardware connection in background thread."""
        try:
            logger.warning("DEBUG: Worker starting connect_all()...")
            success = self.hardware_manager.connect_all()
            logger.warning(f"DEBUG: Worker connect_all() returned: {success}")
            self.connection_completed.emit(success)
        except Exception as e:
            logger.exception(f"Hardware connection error in worker: {e}")
            self.connection_completed.emit(False)


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

        # Background thread for hardware connection
        self.connection_thread: Optional[QThread] = None
        self.connection_worker: Optional[HardwareConnectionWorker] = None
        self.connecting_in_progress = False

        # Error tracking
        self.error_count = 0
        self.max_error_count = 3
        self.last_error_time = 0

        # Single timer for all operations (only if we have an event loop)
        self.operation_timer = None
        if app is not None:
            from PySide6.QtCore import QCoreApplication
            # Only create timer if we're in the main thread with an event loop
            if QCoreApplication.instance() is not None:
                self.operation_timer = QTimer(self)
                self.operation_timer.timeout.connect(self._process_current_state)
                self.operation_timer.start(100)  # Check every 100ms
                logger.debug("✅ Operation timer created in main thread")
            else:
                logger.warning("⚠️ No Qt event loop detected - timer disabled")

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
        """Complete hardware connection using background thread."""
        if not self.hardware_manager:
            self._transition_to_error("Hardware manager not available during connection")
            return

        # Skip if already connecting
        if self.connecting_in_progress:
            return

        logger.warning("DEBUG: Starting hardware connection in background thread...")
        self.connecting_in_progress = True

        # Create worker and thread
        self.connection_worker = HardwareConnectionWorker(self.hardware_manager)
        self.connection_thread = QThread()

        # Move worker to thread
        self.connection_worker.moveToThread(self.connection_thread)

        # Connect signals
        self.connection_thread.started.connect(self.connection_worker.run)
        self.connection_worker.connection_completed.connect(self._on_connection_completed)
        self.connection_worker.connection_completed.connect(self.connection_thread.quit)
        self.connection_thread.finished.connect(self.connection_thread.deleteLater)

        # Start thread
        self.connection_thread.start()
        logger.warning("DEBUG: Background connection thread started")

    def _on_connection_completed(self, success: bool) -> None:
        """Handle completion of background hardware connection."""
        self.connecting_in_progress = False

        if success:
            logger.warning("DEBUG: Background connection succeeded, syncing to app")
            # Sync hardware to app
            self.app.ctrl = self.hardware_manager.ctrl
            self.app.usb = self.hardware_manager.usb
            self.app.knx = self.hardware_manager.knx

            logger.warning("DEBUG: Emitting hardware status")
            # Update hardware status
            ctrl_ok = self.app.ctrl is not None
            usb_ok = self.app.usb is not None
            self.hardware_status.emit(ctrl_ok, usb_ok)

            logger.warning("DEBUG: Transitioning to CONNECTED state")
            self._transition_to_state(SPRSystemState.CONNECTED)
        else:
            self._transition_to_error("Failed to connect to hardware")

    def _handle_connected(self) -> None:
        """Start calibration automatically if not already calibrated."""
        if getattr(self.app, 'calibrated', False):
            logger.info("System already calibrated, skipping to measurement")
            self._transition_to_state(SPRSystemState.CALIBRATED)
            return

        # ✨ SMART VALIDATION: Reuse stored calibration if available to skip full calibration
        try:
            from utils.device_configuration import DeviceConfiguration
            cfg = DeviceConfiguration()
            cal = cfg.load_led_calibration()
            if cal:
                # Create shared calibration state if missing
                if not hasattr(self, 'calib_state') or self.calib_state is None:
                    from utils.spr_calibrator import CalibrationState
                    self.calib_state = CalibrationState()

                cs = self.calib_state
                # Populate essential calibration fields (required by is_valid())
                try:
                    integ_ms = float(cal.get('integration_time_ms', 0))
                    if integ_ms > 0:
                        cs.integration = integ_ms / 1000.0
                        logger.info(f"✅ Loaded calibration integration: {integ_ms:.1f}ms")
                except Exception:
                    pass
                try:
                    s_leds = cal.get('s_mode_intensities', {}) or {}
                    if isinstance(s_leds, dict) and s_leds:
                        cs.ref_intensity = {ch: int(v) for ch, v in s_leds.items()}
                        cs.leds_calibrated = {ch: int(v) for ch, v in s_leds.items()}
                        logger.info(f"✅ Loaded S-mode LED intensities: {cs.ref_intensity}")
                except Exception:
                    pass
                try:
                    s_ref = cal.get('s_ref_baseline', {}) or {}
                    if isinstance(s_ref, dict) and s_ref:
                        cs.ref_sig = {ch: np.array(spec) for ch, spec in s_ref.items()}
                        logger.info(f"✅ Loaded S-ref baseline ({len(s_ref)} channels)")
                except Exception as e:
                    logger.debug(f"Failed to load s_ref: {e}")
                try:
                    wl = cal.get('s_ref_wavelengths')
                    if wl is not None:
                        cs.wavelengths = np.array(wl)
                        logger.info(f"✅ Loaded wavelengths ({len(wl)} points)")
                except Exception as e:
                    logger.debug(f"Failed to load wavelengths: {e}")

                # ✨ CRITICAL: Load dark noise (required by is_valid())
                try:
                    dark = cal.get('dark_noise')
                    if dark is not None:
                        cs.dark_noise = np.array(dark)
                        logger.info(f"✅ Loaded dark noise ({len(dark)} points)")
                    else:
                        # Fallback: create zero dark noise if missing
                        logger.warning("⚠️ No dark noise in stored calibration - using zeros")
                        cs.dark_noise = np.zeros(len(cs.wavelengths)) if len(cs.wavelengths) > 0 else np.zeros(3648)
                except Exception as e:
                    logger.warning(f"Failed to load dark noise: {e}")
                    cs.dark_noise = np.zeros(3648)  # Fallback

                # ✨ CRITICAL: Load per-channel integration times if present (per_channel mode)
                # If NOT present, CLEAR the defaults to prevent per-channel mode activation
                try:
                    per_ch_int = cal.get('integration_per_channel', {})
                    if isinstance(per_ch_int, dict) and per_ch_int:
                        cs.integration_per_channel = {ch: float(v) for ch, v in per_ch_int.items()}
                        logger.info(f"✅ Loaded per-channel integration times: {cs.integration_per_channel}")
                    else:
                        # NOT per-channel mode - clear defaults to use global integration
                        cs.integration_per_channel = {}
                        logger.info(f"✅ Using GLOBAL integration mode (per-channel cleared)")
                except Exception:
                    pass

                # ✨ CRITICAL: Load per-channel scan counts if present
                try:
                    per_ch_scans = cal.get('scans_per_channel', {})
                    if isinstance(per_ch_scans, dict) and per_ch_scans:
                        cs.scans_per_channel = {ch: int(v) for ch, v in per_ch_scans.items()}
                        logger.info(f"✅ Loaded per-channel scan counts: {cs.scans_per_channel}")
                    else:
                        # NOT per-channel mode - clear defaults
                        cs.scans_per_channel = {}
                except Exception:
                    pass

                # Validate that we have minimum required fields
                if not cs.is_valid():
                    logger.warning(f"⚠️ Smart validation incomplete - missing required fields")
                    logger.warning(f"   wavelengths: {len(cs.wavelengths) > 0}, dark_noise: {len(cs.dark_noise) > 0}, ref_sig: {cs.ref_sig is not None}, leds: {cs.leds_calibrated is not None}")
                    logger.info("Proceeding with full calibration")
                else:
                    cs.is_calibrated = True
                    self.app.calibrated = True
                    logger.info("✅ Smart validation passed - using stored calibration (skipping full calibration)")
                    self._transition_to_state(SPRSystemState.CALIBRATED)
                    return
            else:
                logger.info("No stored calibration found; proceeding with full calibration")
        except Exception as e:
            logger.warning(f"Smart validation failed ({e}); proceeding with full calibration")

        if not self.calibrator:
            logger.debug("Creating calibrator...")
            try:
                # Hardware connection status
                if isinstance(self.hardware_manager, SimpleHardwareManager):
                    logger.warning("🔌 REAL HARDWARE CONNECTED:")
                    logger.warning(f"   - Controller (PicoP4SPR): {'✅ Connected' if self.hardware_manager.ctrl else '❌ Failed'}")
                    logger.warning(f"   - Spectrometer (USB4000): {'✅ Connected' if self.hardware_manager.usb else '❌ Failed'}")

                    # Initialize device-specific configuration if spectrometer connected
                    if self.hardware_manager.usb:
                        try:
                            from utils.device_integration import initialize_device_on_connection
                            device_dir = initialize_device_on_connection(self.hardware_manager.usb)
                            if device_dir:
                                logger.info(f"✅ Device-specific config initialized: {device_dir.name}")
                        except Exception as e:
                            logger.warning(f"⚠️ Device initialization failed: {e}")

                    # Get the actual device objects from HAL wrappers
                    ctrl_device = self._get_device_from_hal(self.hardware_manager.ctrl)
                    usb_device = self._get_device_from_hal(self.hardware_manager.usb)

                    # Get device configuration from app
                    device_config = getattr(self.app, 'device_config', None)
                    optical_fiber_diameter = 100
                    led_pcb_model = "4LED"

                    if device_config:
                        try:
                            optical_fiber_diameter = device_config.get_optical_fiber_diameter()
                            led_pcb_model = device_config.get_led_pcb_model()
                            logger.info(f"🔧 Using device config: {optical_fiber_diameter}µm fiber, {led_pcb_model} LED")
                        except Exception as e:
                            logger.warning(f"⚠️ Error getting device config ({e}), using defaults (100µm, 4LED)")
                    else:
                        logger.warning("⚠️ No device config found - using defaults (100µm, 4LED)")

                    from utils.spr_calibrator import SPRCalibrator

                    # ✨ NEW (Phase 2): Get device config dict for optical calibration
                    try:
                        logger.warning("DEBUG: About to import get_device_config")
                        from utils.device_configuration import get_device_config
                        logger.warning("DEBUG: Import successful, getting config")
                        dev_cfg = get_device_config()
                        logger.warning("DEBUG: Got dev_cfg, converting to dict")
                        device_config_dict = dev_cfg.to_dict()
                        logger.warning("DEBUG: Config dict created successfully")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not get device config dict ({e})")
                        device_config_dict = None

                    logger.warning("DEBUG: About to create SPRCalibrator")
                    self.calibrator = SPRCalibrator(
                        ctrl=ctrl_device,
                        usb=usb_device,
                        device_type="PicoP4SPR",
                        calib_state=self.calib_state,  # 🎯 Pass shared state!
                        optical_fiber_diameter=optical_fiber_diameter,  # 🔧 Device-specific config
                        led_pcb_model=led_pcb_model,  # 🔧 Device-specific config
                        device_config=device_config_dict,  # ✨ NEW: Optical calibration
                    )
                    # Connect calibrator progress signals for real calibrator
                    self.calibrator.set_progress_callback(self._on_calibration_progress)

                    # ✨ NEW: Register auto-start callback for live measurements
                    def auto_start_live_measurements():
                        """Auto-start live measurements after successful calibration."""
                        logger.info("=" * 80)
                        logger.info("🚀 AUTO-STARTING LIVE MEASUREMENTS (from calibration callback)")
                        logger.info("=" * 80)
                        try:
                            # Trigger transition to CALIBRATED state, which will start acquisition
                            self._transition_to_state(SPRSystemState.CALIBRATED)
                            logger.info("✅ State transitioned to CALIBRATED - acquisition will start automatically")
                        except Exception as e:
                            logger.exception(f"❌ Failed to auto-start measurements: {e}")

                    self.calibrator.set_on_calibration_complete_callback(auto_start_live_measurements)
                    logger.info("✅ Auto-start callback registered with calibrator")

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
        """Start data acquisition after validating calibration."""
        # ✅ Validate calibration state before proceeding
        # Support both full calibration (calibrator exists) and smart validation (calibrator is None)
        if self.calibrator:
            # Full calibration path: validate through calibrator
            if not self.calibrator.state.is_valid():
                logger.error("❌ Calibration state invalid - missing required data")
                self._transition_to_error("Calibration data incomplete or invalid")
                return
        else:
            # Smart validation path: validate calib_state directly
            if not hasattr(self, 'calib_state') or not self.calib_state or not self.calib_state.is_valid():
                logger.error("❌ Calibration state invalid - missing required data (smart validation)")
                self._transition_to_error("Calibration data incomplete or invalid")
                return
            logger.info("📋 Using calibration from smart validation (no full calibration needed)")

        # Log calibration summary for diagnostics
        summary = self.calibrator.get_calibration_summary() if self.calibrator else None
        logger.info("=" * 80)
        logger.info("📊 CALIBRATION SUMMARY")
        logger.info("=" * 80)
        if summary:
            logger.info(f"✅ Success: {summary['success']}")
            logger.info(f"⏱️  Timestamp: {summary['timestamp_str']}")
            logger.info(f"🔧 Integration Time: {summary['integration_time_ms']:.1f} ms")
            logger.info(f"💡 LED Intensities: {summary['led_intensities']}")
            logger.info(f"📉 Weakest Channel: {summary['weakest_channel']}")
            logger.info(f"🔬 Detector: {summary['detector_model']}")
            if summary['failed_channels']:
                logger.warning(f"⚠️  Failed Channels: {summary['failed_channels']}")
        else:
            # Smart validation path - log from calib_state
            logger.info("✅ Success: True (loaded from device config)")
            logger.info(f"🔧 Integration Time: {self.calib_state.integration * 1000:.1f} ms")
            logger.info(f"💡 LED Intensities: {self.calib_state.leds_calibrated}")
        logger.info("=" * 80)

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
                    # Create a basic data processor using calibrated wavelengths if available
                    if self.calib_state and len(self.calib_state.wavelengths) > 0:
                        wave_data = self.calib_state.wavelengths
                        logger.info(f"✅ Using calibrated wavelengths for data processor: {len(wave_data)} points")
                    else:
                        wave_data = np.linspace(441.1, 773.2, 3648)  # Default USB4000 wavelength range
                        logger.warning("⚠️ No calibrated wavelengths - using default range")
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

        # ✨ NEW: Re-capture S-ref spectra with BOOSTED settings (BEFORE switching to P-mode)
        # This ensures QC validation compares against the actual live mode baseline
        if self.data_acquisition and hasattr(self.data_acquisition, 'live_led_intensities') and self.data_acquisition.live_led_intensities:
            logger.info("=" * 80)
            logger.info("📸 RE-CAPTURING S-REF WITH BOOSTED SETTINGS (for QC validation)")
            logger.info("=" * 80)
            try:
                # Get hardware devices
                if isinstance(self.hardware_manager, SimpleHardwareManager):
                    ctrl_device = self._get_device_from_hal(self.hardware_manager.ctrl)
                    usb_device = self._get_device_from_hal(self.hardware_manager.usb)
                else:
                    ctrl_device = self.app.ctrl
                    usb_device = self.app.usb

                # Ensure we're in S-mode
                if hasattr(ctrl_device, 'set_mode'):
                    ctrl_device.set_mode("s")
                    time.sleep(0.4)  # Wait for servo

                # Apply boosted integration time to spectrometer
                live_integration_seconds = getattr(self.data_acquisition, 'live_integration_seconds', self.calib_state.integration)
                if hasattr(usb_device, 'set_integration'):
                    usb_device.set_integration(live_integration_seconds)
                elif hasattr(usb_device, 'set_integration_time'):
                    usb_device.set_integration_time(live_integration_seconds)
                time.sleep(0.1)

                logger.info(f"   Integration time: {live_integration_seconds * 1000:.1f}ms (boosted)")

                # Measure S-ref with boosted settings for each channel
                boosted_s_ref = {}
                ch_list = ['a', 'b', 'c', 'd']

                for ch in ch_list:
                    boosted_led = self.data_acquisition.live_led_intensities.get(ch, 255)

                    # Set LED for this channel (supports multiple HALs)
                    try:
                        if hasattr(ctrl_device, 'set_intensity'):
                            # Preferred: per-channel raw intensity (0-255)
                            ctrl_device.set_intensity(ch, int(boosted_led))
                        elif hasattr(ctrl_device, 'set_led_intensity'):
                            # Fallback: global normalized intensity [0.0, 1.0]
                            norm = max(0.0, min(float(boosted_led) / 255.0, 1.0))
                            ctrl_device.set_led_intensity(norm)
                            # Try to activate the specific channel if supported
                            if hasattr(ctrl_device, 'activate_channel'):
                                try:
                                    ctrl_device.activate_channel(ch)
                                except Exception:
                                    pass
                        else:
                            # Last resort: try to activate the channel only
                            if hasattr(ctrl_device, 'activate_channel'):
                                ctrl_device.activate_channel(ch)
                    except Exception as e:
                        logger.warning(f"Failed to set LED intensity for channel {ch.upper()}: {e}")

                    time.sleep(0.1)  # LED settling time

                    # Measure spectrum (support multiple spectrometer APIs)
                    spectrum = None
                    try:
                        if hasattr(usb_device, 'get_spectrum'):
                            spectrum = usb_device.get_spectrum()
                        elif hasattr(usb_device, 'acquire_spectrum'):
                            spectrum = usb_device.acquire_spectrum()
                        elif hasattr(usb_device, 'read_intensity'):
                            spectrum = usb_device.read_intensity()
                    except Exception as e:
                        logger.warning(f"Failed to acquire spectrum for boosted S-ref on channel {ch.upper()}: {e}")
                    boosted_s_ref[ch] = spectrum

                    avg_signal = np.mean(spectrum) if spectrum is not None else 0
                    logger.info(f"   Channel {ch.upper()}: LED={boosted_led}, avg signal={avg_signal:.0f}")

                    # Turn off LED (best-effort)
                    try:
                        if hasattr(ctrl_device, 'set_intensity'):
                            ctrl_device.set_intensity(ch, 0)
                        elif hasattr(ctrl_device, 'turn_off_channels'):
                            ctrl_device.turn_off_channels()
                    except Exception:
                        pass

                logger.info("✅ S-ref re-captured with boosted settings")

                # Save to device_config with boost parameters
                logger.info("=" * 80)
                logger.info("💾 SAVING BOOSTED CALIBRATION TO DEVICE CONFIG")
                logger.info("=" * 80)

                from utils.device_configuration import DeviceConfiguration
                device_config = DeviceConfiguration()

                # Get boost parameters
                live_integration_ms = int(live_integration_seconds * 1000)
                live_boost_factor = getattr(self.data_acquisition, 'live_boost_factor', 1.0)

                device_config.save_led_calibration(
                    integration_time_ms=int(self.calib_state.integration * 1000),  # Calibration baseline
                    s_mode_intensities=self.calib_state.ref_intensity.copy(),
                    p_mode_intensities=self.calib_state.ref_intensity.copy(),
                    s_ref_spectra=boosted_s_ref,  # ✨ Use boosted S-ref
                    s_ref_wavelengths=self.calib_state.wavelengths if self.calib_state.wavelengths is not None else None,
                    live_boost_integration_ms=live_integration_ms,  # ✨ Boosted integration time
                    live_boost_led_intensities=self.data_acquisition.live_led_intensities.copy(),  # ✨ Adjusted LEDs
                    live_boost_factor=live_boost_factor  # ✨ Boost multiplier
                )

                logger.info("✅ Boosted calibration saved to device_config.json")
                logger.info(f"   Calibration baseline: {int(self.calib_state.integration * 1000)}ms")
                logger.info(f"   Live boost: {live_integration_ms}ms ({live_boost_factor:.2f}×)")
                logger.info(f"   Live LED adjustments: {self.data_acquisition.live_led_intensities}")
                logger.info("=" * 80)

            except Exception as e:
                logger.exception(f"❌ Failed to re-capture S-ref with boosted settings: {e}")
                logger.warning("   Continuing with calibration baseline S-ref")

        # ✨ CRITICAL: Switch polarizer to P-mode BEFORE starting data acquisition
        # This must happen whether data acquisition already exists or not
        if isinstance(self.hardware_manager, SimpleHardwareManager):
            ctrl_device = self._get_device_from_hal(self.hardware_manager.ctrl)
        else:
            ctrl_device = self.app.ctrl

        if hasattr(ctrl_device, 'set_mode'):
            logger.info("🔄 Switching polarizer to P-mode for live measurements...")
            try:
                ctrl_device.set_mode("p")
                time.sleep(0.4)  # Wait for servo to rotate (400ms settling time)
                logger.info("✅ Polarizer switched to P-mode")

                # ✨ Update polarizer_mode in data acquisition for metadata tracking
                if self.data_acquisition and hasattr(self.data_acquisition, 'acquisition') and hasattr(self.data_acquisition.acquisition, 'polarizer_mode'):
                    self.data_acquisition.acquisition.polarizer_mode = "p"
                    logger.debug("✅ Data acquisition metadata updated: polarizer_mode='p'")
            except Exception as e:
                logger.warning(f"⚠️ Failed to switch polarizer to P-mode: {e}")
                logger.warning("   Continuing with current polarizer position")
        else:
            logger.warning("⚠️ Controller does not support polarizer mode switching")

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
        logger.debug(f"Could not extract device from HAL object {type(hal_object)}, returning HAL object")
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
        if self.operation_timer is not None:
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
                        if controller.emergency_shutdown():
                            logger.info("✅ Emergency LED shutdown via HAL")
                        else:
                            # Try a lighter-weight fallback via HAL if available
                            if hasattr(controller, 'turn_off_channels'):
                                try:
                                    if controller.turn_off_channels():
                                        logger.info("✅ Emergency LED shutdown via HAL (turn_off_channels)")
                                except Exception:
                                    pass
                except Exception as e:
                    logger.error(f"HAL emergency shutdown failed: {e}")

            # Direct serial emergency shutdown as backup
            try:
                controller = getattr(self.hardware_manager, 'ctrl', None) if self.hardware_manager else None
                # Avoid opening the port directly if HAL is connected to prevent Access Denied
                hal_connected = bool(controller and hasattr(controller, 'is_connected') and controller.is_connected())
                if not hal_connected:
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
                else:
                    logger.debug("Skipping direct COM4 emergency command because HAL is connected")
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

    def get_calibration_info(self) -> dict:
        """Get calibration summary for UI display.

        Returns:
            Dictionary with calibration information
        """
        if self.calib_state is None:
            return {"calibrated": False}

        return {
            "calibrated": self.calib_state.is_calibrated,
            "integration_time": self.calib_state.integration,
            "num_scans": self.calib_state.num_scans,
            "led_values": self.calib_state.leds_calibrated,
        }

    def set_polarizer_mode(self, mode: str) -> None:
        """Set polarizer to S or P mode.

        Args:
            mode: 's' for S-mode (reference), 'p' for P-mode (sample)
        """
        if self.ctrl_hal is None:
            logger.warning("Cannot set polarizer - no hardware controller")
            return

        try:
            if 's' in mode.lower():
                self.ctrl_hal.set_mode('s')
                logger.info("✅ Polarizer set to S-mode (reference)")
            else:
                self.ctrl_hal.set_mode('p')
                logger.info("✅ Polarizer set to P-mode (sample)")
        except Exception as e:
            logger.error(f"❌ Failed to set polarizer mode: {e}")

    def set_single_led_mode(self, enabled: bool, channel: str = 'x') -> None:
        """Enable/disable single LED mode.

        Args:
            enabled: True to enable single LED mode, False for auto (all channels)
            channel: Which channel to light ('a', 'b', 'c', 'd', 'x' for none)
        """
        if not hasattr(self, 'data_acquisition') or self.data_acquisition is None:
            logger.warning("Cannot set single LED mode - no data acquisition running")
            return

        try:
            # Store the mode for the acquisition loop
            self.single_led_mode = enabled
            self.single_led_channel = channel

            if not enabled:
                logger.info("✅ Single LED mode: OFF (auto - all channels)")
            elif channel == 'x':
                logger.info("✅ Single LED mode: All LEDs OFF")
            else:
                logger.info(f"✅ Single LED mode: Channel {channel.upper()} only")

            # If measuring, the acquisition loop will pick up the change
            # If not measuring, this just stores the preference
        except Exception as e:
            logger.error(f"❌ Failed to set single LED mode: {e}")

    def get_calibration_summary(self) -> dict:
        """Get detailed calibration metadata.

        Returns:
            Dictionary with calibration metadata, or empty dict if not calibrated.
        """
        if self.calibrator:
            return self.calibrator.get_calibration_summary()
        return {}