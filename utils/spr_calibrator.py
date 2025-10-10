"""SPR Calibration Module

Handles all SPR spectrometer calibration operations:
- Wavelength range calibration
- Integration time optimization
- LED intensity calibration (S-mode and P-mode)
- Dark noise measurement
- Reference signal acquisition
- Calibration validation
- Calibration history logging

Author: Refactored from main.py
Date: October 7, 2025
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import time
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

import numpy as np

from settings import (
    CH_LIST,
    DARK_NOISE_SCANS,
    DETECTOR_MAX_COUNTS,
    DEVELOPMENT_MODE,
    DEVICES,
    EZ_CH_LIST,
    LED_DELAY,
    MAX_INTENSITY_PERCENT,
    MAX_INTEGRATION,
    MAX_WAVELENGTH,
    MIN_INTENSITY_PERCENT,
    MIN_INTEGRATION,
    MIN_WAVELENGTH,
    P_COUNT_THRESHOLD,
    P_LED_MAX,
    P_MAX_INCREASE,
    REF_SCANS,
    ROOT_DIR,
    S_COUNT_MAX,
    S_LED_INT,
    S_LED_MIN,
    TARGET_INTENSITY_PERCENT,
    TARGET_WAVELENGTH_MAX,
    TARGET_WAVELENGTH_MIN,
    TIME_ZONE,
)
from utils.logger import logger
from utils.spr_data_processor import SPRDataProcessor

if TYPE_CHECKING:
    from utils.controller import PicoEZSPR, PicoP4SPR
    from utils.usb4000_adapter import USB4000  # HAL-based USB4000 adapter


# Calibration constants - Percentage-Based Approach
COARSE_ADJUSTMENT = 20  # LED intensity adjustment step for rough calibration
MEDIUM_ADJUSTMENT = 5  # LED intensity adjustment step for medium calibration
FINE_ADJUSTMENT = 1  # LED intensity adjustment step for fine calibration
INTEGRATION_STEP_THRESHOLD = 50  # Threshold for changing dark noise scan count

# NEW: Percentage-based adaptive calibration (simpler, no hard-wired values)
ADAPTIVE_CALIBRATION_ENABLED = True  # Enable adaptive algorithm
ADAPTIVE_MAX_ITERATIONS = 15  # Maximum iterations before fallback
ADAPTIVE_CONVERGENCE_FACTOR = 0.8  # Convergence damping factor
ADAPTIVE_MIN_STEP = 1  # Minimum LED intensity step
ADAPTIVE_MAX_STEP = 50  # Maximum LED intensity step
ADAPTIVE_STABILIZATION_DELAY = 0.3  # LED stabilization delay (faster)


def calculate_target_intensity(target_percent: float = TARGET_INTENSITY_PERCENT) -> int:
    """Calculate target intensity from percentage.

    Args:
        target_percent: Target as percentage of detector max (0-100)

    Returns:
        Target intensity in counts
    """
    return int(DETECTOR_MAX_COUNTS * target_percent / 100.0)


def calculate_intensity_tolerance(target_percent: float = TARGET_INTENSITY_PERCENT) -> int:
    """Calculate acceptable tolerance around target (±5% of detector max).

    Args:
        target_percent: Target as percentage

    Returns:
        Tolerance in counts
    """
    return int(DETECTOR_MAX_COUNTS * 0.05)  # ±5% of max


class CalibrationState:
    """Encapsulates calibration state and results - thread-safe shared state.
    Makes calibration data easier to test, serialize, and manage.
    """

    def __init__(self):
        """Initialize calibration state with default values."""
        import threading

        # Thread safety
        self._lock = threading.RLock()

        # Wavelength calibration
        self.wave_min_index = 0
        self.wave_max_index = 0
        self.wave_data: np.ndarray = np.array([])
        self.wavelengths: np.ndarray = np.array([])  # Cropped wavelengths for data acquisition
        self.full_spectrum_wavelengths: np.ndarray = np.array([])  # Full spectrum wavelengths
        self.fourier_weights: np.ndarray = np.array([])

        # Integration and scanning
        self.integration = MIN_INTEGRATION / 1000.0  # Convert ms to seconds
        self.num_scans = 1

        # LED intensities
        self.ref_intensity: dict[str, int] = dict.fromkeys(CH_LIST, 0)
        self.leds_calibrated: dict[str, int] = dict.fromkeys(CH_LIST, 0)

        # Reference data
        self.dark_noise: np.ndarray = np.array([])
        self.full_spectrum_dark_noise: np.ndarray = np.array([])  # Full spectrum for resampling
        self.ref_sig: dict[str, np.ndarray | None] = dict.fromkeys(CH_LIST)

        # Filter and timing settings
        self.med_filt_win = 11
        self.led_delay = LED_DELAY

        # Results
        self.ch_error_list: list[str] = []
        self.is_calibrated = False
        self.calibration_timestamp: Optional[float] = None

    def is_valid(self) -> bool:
        """Check if calibration is complete and valid.

        Returns:
            True if all required calibration data is present, False otherwise.
        """
        with self._lock:
            return (
                len(self.wavelengths) > 0 and
                len(self.dark_noise) > 0 and
                self.ref_sig is not None and
                any(ref is not None for ref in self.ref_sig.values()) and
                self.leds_calibrated is not None and
                len(self.leds_calibrated) > 0
            )

    def to_dict(self) -> dict:
        """Export calibration state to dictionary for saving."""
        with self._lock:
            return {
                "wave_min_index": self.wave_min_index,
                "wave_max_index": self.wave_max_index,
                "integration": self.integration,
                "num_scans": self.num_scans,
                "ref_intensity": self.ref_intensity.copy(),
                "leds_calibrated": self.leds_calibrated.copy(),
                "med_filt_win": self.med_filt_win,
                "led_delay": self.led_delay,
                "ch_error_list": self.ch_error_list.copy(),
                "is_calibrated": self.is_calibrated,
                "calibration_timestamp": self.calibration_timestamp,
            }

    def from_dict(self, data: dict) -> None:
        """Import calibration state from dictionary."""
        with self._lock:
            self.wave_min_index = data.get("wave_min_index", 0)
            self.wave_max_index = data.get("wave_max_index", 0)
            self.integration = data.get(
                "integration",
                MIN_INTEGRATION / 1000.0,
            )  # Convert ms to seconds
            self.num_scans = data.get("num_scans", 1)
            self.ref_intensity = data.get("ref_intensity", dict.fromkeys(CH_LIST, 0))
            self.leds_calibrated = data.get("leds_calibrated", dict.fromkeys(CH_LIST, 0))
            self.med_filt_win = data.get("med_filt_win", 11)
            self.led_delay = data.get("led_delay", LED_DELAY)
            self.ch_error_list = data.get("ch_error_list", [])
            self.is_calibrated = data.get("is_calibrated", False)
            self.calibration_timestamp = data.get("calibration_timestamp")

    def reset(self) -> None:
        """Reset calibration state to defaults."""
        with self._lock:
            self.__init__()


class SPRCalibrator:
    """Handles all SPR spectrometer calibration operations.

    This class encapsulates the calibration logic for the SPR system,
    including wavelength range, integration time, LED intensities,
    dark noise, and reference signals.

    Attributes:
        ctrl: LED/polarizer controller
        usb: USB4000 spectrometer
        state: Calibration state storage
        stop_flag: Threading event to signal stop
        device_type: Type of controller device

    """

    def __init__(
        self,
        ctrl: Union[PicoP4SPR, PicoEZSPR, None],
        usb: Union[USB4000, None],
        device_type: str,
        stop_flag: Any = None,
        calib_state: Optional["CalibrationState"] = None,
    ):
        """Initialize the SPR calibrator.

        Args:
            ctrl: LED and polarizer controller
            usb: USB4000 spectrometer
            device_type: Device type string ('PicoP4SPR', 'PicoEZSPR', etc.')
            stop_flag: Optional threading event to signal stop
            calib_state: Optional shared CalibrationState. If None, creates a new one.

        """
        self.ctrl = ctrl
        self.usb = usb
        self.device_type = device_type
        self.stop_flag = stop_flag

        # Use provided shared state or create new one
        if calib_state is not None:
            self.state = calib_state
            logger.info("✅ SPRCalibrator using SHARED CalibrationState")
        else:
            self.state = CalibrationState()
            logger.info("⚠️ SPRCalibrator created NEW CalibrationState")

        # Debug logging to check USB object type
        logger.debug(f"SPRCalibrator initialized with USB type: {type(self.usb)}")
        if hasattr(self.usb, "_hal"):
            logger.debug(f"USB adapter HAL type: {type(self.usb._hal)}")
        logger.debug(
            f"USB object methods: {[m for m in dir(self.usb) if not m.startswith('_')]}",
        )

        # Create adapter for HAL if needed
        has_acquire_spectrum = hasattr(self.usb, "acquire_spectrum")
        has_capture_spectrum = hasattr(self.usb, "capture_spectrum")
        has_read_intensity = hasattr(self.usb, "read_intensity")
        has_set_integration = hasattr(self.usb, "set_integration")
        has_set_integration_time = hasattr(self.usb, "set_integration_time")

        logger.debug(f"USB object capabilities: acquire_spectrum={has_acquire_spectrum}, capture_spectrum={has_capture_spectrum}, read_intensity={has_read_intensity}, set_integration={has_set_integration}, set_integration_time={has_set_integration_time}")

        if (has_acquire_spectrum or has_capture_spectrum) and (not has_read_intensity or not has_set_integration):
            logger.debug("Creating HAL adapter wrapper for USB4000HAL")
            self.usb = self._create_hal_adapter(self.usb)

        # Create controller adapter for PicoP4SPR HAL if needed
        if hasattr(self.ctrl, "activate_channel") and not hasattr(
            self.ctrl,
            "set_mode",
        ):
            logger.debug("Creating controller adapter wrapper for PicoP4SPR HAL")
            self.ctrl = self._create_controller_adapter(self.ctrl)

        # Progress callback (can be set externally)
        self.progress_callback: Callable[[int, str], None] | None = None

    def _create_hal_adapter(self, hal):
        """Create a simple adapter to make HAL compatible with calibrator interface."""

        class HALAdapter:
            def __init__(self, hal_instance):
                self._hal = hal_instance

            def __getattr__(self, name):
                # Pass through most attributes to the HAL
                return getattr(self._hal, name)

            def read_wavelength(self):
                """Adapter method: HAL get_wavelengths -> read_wavelength"""
                wavelengths = self._hal.get_wavelengths()
                if wavelengths is not None and len(wavelengths) > 0:
                    return np.array(wavelengths)
                return None

            def set_integration(self, integration_time):
                """Adapter method: HAL set_integration_time -> set_integration"""
                return self._hal.set_integration_time(integration_time)

            def read_intensity(self):
                """Adapter method: HAL acquire_spectrum -> read_intensity"""
                # For USB4000OceanDirect, the integration time is already set,
                # we just need to acquire the spectrum
                if hasattr(self._hal, 'acquire_spectrum'):
                    # USB4000OceanDirect uses acquire_spectrum with no parameters
                    intensities = self._hal.acquire_spectrum()
                    if intensities is not None and len(intensities) > 0:
                        return np.array(intensities)
                    return None
                elif hasattr(self._hal, 'capture_spectrum'):
                    # HAL objects use capture_spectrum with integration time
                    integration_time = self._hal.get_integration_time()
                    _, intensities = self._hal.capture_spectrum(integration_time)
                    if intensities is not None and len(intensities) > 0:
                        return np.array(intensities)
                    return None
                else:
                    logger.error("No spectrum acquisition method found")
                    return None

        return HALAdapter(hal)

    def _create_controller_adapter(self, ctrl_hal):
        """Create adapter for PicoP4SPR HAL to match expected controller interface."""

        class ControllerAdapter:
            def __init__(self, hal_instance):
                self._hal = hal_instance
                self._current_mode = None

            def __getattr__(self, name):
                # Pass through most attributes to the HAL
                return getattr(self._hal, name)

        class ControllerAdapter:
            def __init__(self, hal_instance):
                self._hal = hal_instance
                self._current_mode = None

            def __getattr__(self, name):
                # Pass through most attributes to the HAL
                return getattr(self._hal, name)

            def set_mode(self, mode):
                """Set mode: 's' for single channel, 'p' for polarized measurement."""
                logger.info(f"Setting controller mode to: {mode}")
                self._current_mode = mode
                # Use HAL's existing connection for servo commands
                try:
                    if mode == "s":
                        cmd = b"ss\n"  # S-polarization mode
                    else:
                        cmd = b"sp\n"  # P-polarization mode

                    # Use HAL's serial connection directly
                    if hasattr(self._hal, "_ser") and self._hal._ser:
                        self._hal._ser.write(cmd)
                        response = self._hal._ser.read(10)
                        success = b"1" in response
                        if success:
                            logger.info(f"Successfully set polarizer mode to {mode}")
                        else:
                            logger.warning(
                                f"Failed to set polarizer mode to {mode}, response: {response}",
                            )
                        return success
                    logger.warning(
                        "HAL serial connection not available for mode setting",
                    )
                    return False
                except Exception as e:
                    logger.error(f"Failed to set mode {mode}: {e}")
                    return False

            def servo_set(self, s=10, p=100):
                """Set servo polarizer positions."""
                logger.info(f"Setting servo positions: s={s}, p={p}")
                try:
                    if (s < 0) or (p < 0) or (s > 180) or (p > 180):
                        raise ValueError(f"Invalid polarizer position given: {s}, {p}")

                    # Use HAL's serial connection directly
                    if hasattr(self._hal, "_ser") and self._hal._ser:
                        cmd = f"sv{s:03d}{p:03d}\n".encode()
                        self._hal._ser.write(cmd)
                        response = self._hal._ser.read(10)
                        success = b"1" in response
                        if success:
                            logger.info(
                                f"Successfully set servo positions: s={s}, p={p}",
                            )
                        else:
                            logger.warning(
                                f"Failed to set servo positions, response: {response}",
                            )
                        return success
                    logger.warning(
                        "HAL serial connection not available for servo setting",
                    )
                    return False
                except Exception as e:
                    logger.error(f"Failed to set servo positions s={s}, p={p}: {e}")
                    return False

            def servo_get(self):
                """Get current servo positions."""
                logger.info("Getting servo positions")
                try:
                    # Use HAL's serial connection directly
                    if hasattr(self._hal, "_ser") and self._hal._ser:
                        self._hal._ser.reset_input_buffer()  # Clear buffer
                        self._hal._ser.write(b"sr\n")

                        # Read response - format should be "ddd,ddd"
                        for _ in range(3):  # Try a few times
                            line = (
                                self._hal._ser.readline()
                                .decode(errors="ignore")
                                .strip()
                            )
                            logger.debug(f"Servo response: {line}")
                            if (
                                len(line) >= 7
                                and line[0:3].isdigit()
                                and line[3:4] == ","
                                and line[4:7].isdigit()
                            ):
                                s_pos = line[0:3]
                                p_pos = line[4:7]
                                result = {"s": s_pos.encode(), "p": p_pos.encode()}
                                logger.info(f"Got servo positions: {result}")
                                return result

                        # Default fallback
                        logger.warning("Could not read servo positions, using defaults")
                        return {"s": b"000", "p": b"000"}
                    logger.warning("HAL serial connection not available for servo get")
                    return {"s": b"000", "p": b"000"}

                except Exception as e:
                    logger.error(f"Failed to get servo positions: {e}")
                    return {"s": b"000", "p": b"000"}

            def flash(self):
                """Save servo positions to EEPROM."""
                logger.info("Flashing servo positions to EEPROM")
                try:
                    # Use HAL's serial connection directly
                    if hasattr(self._hal, "_ser") and self._hal._ser:
                        self._hal._ser.write(b"sf\n")
                        response = self._hal._ser.read(10)
                        success = b"1" in response
                        if success:
                            logger.info("Successfully flashed servo positions")
                        else:
                            logger.warning(
                                f"Failed to flash servo positions, response: {response}",
                            )
                        return success
                    logger.warning("HAL serial connection not available for flash")
                    return False
                except Exception as e:
                    logger.error(f"Failed to flash servo positions: {e}")
                    return False

            def turn_off_channels(self):
                """Turn off all LED channels."""
                logger.info("Turning off all channels")
                # Set LED intensity to 0 to turn off
                try:
                    self._hal.set_led_intensity(0.0)
                    return True
                except Exception as e:
                    logger.error(f"Failed to turn off channels: {e}")
                    return False

            def set_intensity(self, ch, raw_val):
                """Set LED intensity for a specific channel."""
                logger.info(f"Setting intensity for channel {ch} to {raw_val}")
                try:
                    # Import ChannelID enum
                    from utils.hal.spr_controller_hal import ChannelID

                    # Convert string channel to ChannelID enum
                    channel_map = {
                        "a": ChannelID.A,
                        "b": ChannelID.B,
                        "c": ChannelID.C,
                        "d": ChannelID.D,
                    }
                    channel_id = channel_map.get(ch.lower())

                    if channel_id is None:
                        logger.error(f"Invalid channel: {ch}")
                        return False

                    # Activate the specified channel first
                    self._hal.activate_channel(channel_id)
                    # Set LED intensity (raw_val should be 0-100 range)
                    # Convert raw_val to appropriate range if needed
                    intensity = max(0.0, min(100.0, float(raw_val)))
                    self._hal.set_led_intensity(intensity)
                    return True
                except Exception as e:
                    logger.error(f"Failed to set intensity for channel {ch}: {e}")
                    return False

        return ControllerAdapter(ctrl_hal)

    def set_progress_callback(self, callback: Callable[[int, str], None]) -> None:
        """Set callback for progress updates."""
        self.progress_callback = callback

    def _emit_progress(self, step: int, message: str) -> None:
        """Emit progress update if callback is set."""
        if self.progress_callback is not None:
            self.progress_callback(step, message)

    def _is_stopped(self) -> bool:
        """Check if stop has been requested."""
        if self.stop_flag is None:
            return False
        return self.stop_flag.is_set()

    def _safe_hardware_cleanup(self) -> None:
        """Safely turn off hardware components to prevent stuck states."""
        try:
            logger.debug("Performing safe hardware cleanup...")

            # Turn off LEDs via controller
            if self.ctrl is not None:
                logger.debug("Turning off LED channels via controller...")
                self.ctrl.turn_off_channels()

            # Emergency direct serial LED shutdown as backup
            try:
                import time

                import serial

                logger.debug("Emergency direct LED shutdown via serial...")
                with serial.Serial("COM4", 115200, timeout=2) as ser:
                    # Turn off all channels
                    ser.write(b"lx\n")
                    time.sleep(0.1)
                    response1 = ser.read(10)

                    # Set LED intensity to 0
                    ser.write(b"i0\n")
                    time.sleep(0.1)
                    response2 = ser.read(10)

                    # Reset polarizer to S-mode as safe state
                    ser.write(b"ss\n")
                    time.sleep(0.1)
                    response3 = ser.read(10)

                    logger.debug(
                        f"Direct cleanup: lx={response1}, "
                        f"i0={response2}, ss={response3}",
                    )
            except Exception as serial_e:
                logger.warning(f"Direct serial LED shutdown failed: {serial_e}")

            logger.debug("Hardware cleanup completed")

        except Exception as e:
            logger.error(f"Error during hardware cleanup: {e}")
            # Even if cleanup fails, log and continue to prevent cascading failures

    # ========================================================================
    # STEP 1: WAVELENGTH RANGE CALIBRATION
    # ========================================================================

    def calibrate_wavelength_range(self) -> tuple[bool, float]:
        """Calibrate wavelength range and calculate Fourier weights.

        Returns:
            Tuple of (success, integration_step)

        """
        try:
            if self.device_type not in DEVICES:
                logger.error(f"Unrecognized controller: {self.device_type}")
                return False, 1.0

            if self.usb is None:
                logger.error("USB spectrometer not available")
                return False, 1.0

            # Get serial number from device info
            try:
                device_info = (
                    self.usb.get_device_info()
                    if hasattr(self.usb, "get_device_info")
                    else {}
                )
                serial_number = device_info.get("serial_number", "unknown")
                logger.debug(f"Spectrometer serial number: {serial_number}")
            except Exception as e:
                logger.warning(f"Could not get serial number: {e}")
                serial_number = "unknown"

            # Check if this is the HAL or adapter and use appropriate method
            if hasattr(self.usb, "read_wavelength"):
                wave_data = self.usb.read_wavelength()
            elif hasattr(self.usb, "get_wavelengths"):
                # Direct HAL access
                wave_data = self.usb.get_wavelengths()
                if wave_data is not None:
                    wave_data = np.array(wave_data)
            else:
                logger.error("USB spectrometer has no wavelength reading method")
                return False, 1.0

            if wave_data is None or len(wave_data) == 0:
                logger.error("Failed to read wavelength data")
                return False, 1.0

            # Apply serial-specific corrections
            if serial_number == "FLMT06715":
                wave_data = wave_data + 20

            integration_step = 2.5 if serial_number == "FLMT09793" else 1.0

            # NO TRUNCATION - Use full spectrum for simplified calibration
            if len(wave_data) < 2:
                logger.error("Insufficient wavelength data")
                return False, integration_step

            # Store full spectrum (no truncation)
            self.state.wave_min_index = 0
            self.state.wave_max_index = len(wave_data) - 1
            self.state.full_spectrum_wavelengths = wave_data.copy()
            self.state.wave_data = wave_data.copy()
            self.state.wavelengths = wave_data.copy()

            logger.info(
                f"✅ Using FULL SPECTRUM - no truncation: "
                f"{wave_data[0]:.1f} to {wave_data[-1]:.1f} nm ({len(wave_data)} points)"
            )

            # Find target wavelength range indices for calibration measurement
            target_min_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MIN))
            target_max_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MAX))

            logger.info(
                f"📊 Target calibration range: "
                f"{wave_data[target_min_idx]:.1f} to {wave_data[target_max_idx]:.1f} nm "
                f"(indices {target_min_idx}-{target_max_idx})"
            )

            logger.debug(
                f"Wavelength range: {self.state.wave_min_index} to {self.state.wave_max_index} "
                f"({len(self.state.wave_data)} points)",
            )

            # Calculate Fourier transform weights for smoothing
            alpha = 9e3
            n = len(self.state.wave_data) - 1
            if n <= 0:
                logger.error("Invalid wavelength data length for Fourier weights")
                return False, integration_step

            phi = np.pi / n * np.arange(1, n)
            phi2 = phi**2
            self.state.fourier_weights = phi / (1 + alpha * phi2 * (1 + phi2))

            logger.debug("Wavelength calibration complete")
            return True, integration_step

        except Exception as e:
            logger.exception(f"Error in wavelength calibration: {e}")
            return False, 1.0

    # ========================================================================
    # STEP 3: INTEGRATION TIME CALIBRATION
    # ========================================================================

    def calibrate_integration_time(
        self,
        ch_list: list[str],
        integration_step: float,
    ) -> bool:
        """Calibrate integration time optimized for the WEAKEST channel.
        
        New strategy:
        1. Identify weakest and strongest channels at standard LED intensity
        2. Optimize integration time for the weakest channel (ensure it reaches target)
        3. Check that strongest channel doesn't saturate
        4. Later steps will adjust individual LED intensities to match

        Args:
            ch_list: List of channels to calibrate
            integration_step: Step size for integration time adjustments

        Returns:
            True if successful, False otherwise

        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            # Set initial mode and turn off channels
            self.ctrl.set_mode(mode="s")
            time.sleep(0.5)
            self.ctrl.turn_off_channels()

            # Set minimum integration time (convert ms to seconds)
            self.state.integration = MIN_INTEGRATION / 1000.0  # Convert ms to seconds
            self.usb.set_integration(self.state.integration)
            time.sleep(0.1)

            max_int = MAX_INTEGRATION / 1000.0  # Convert ms to seconds
            
            # ========================================================================
            # STEP 1: Identify weakest and strongest channels
            # ========================================================================
            logger.info("📊 Step 3.1: Identifying weakest and strongest channels...")
            
            channel_intensities = {}
            for ch in ch_list:
                if self._is_stopped():
                    return False

                self.ctrl.set_intensity(ch=ch, raw_val=S_LED_INT)
                time.sleep(LED_DELAY)

                int_array = self.usb.read_intensity()
                if int_array is None:
                    logger.error(f"Failed to read intensity for channel {ch}")
                    continue

                current_count = int_array[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()
                
                channel_intensities[ch] = current_count
                logger.debug(f"Channel {ch} initial intensity: {current_count:.0f} counts")
            
            # Find weakest and strongest channels
            weakest_ch = min(channel_intensities, key=channel_intensities.get)
            strongest_ch = max(channel_intensities, key=channel_intensities.get)
            
            logger.info(f"✅ Weakest channel: {weakest_ch} ({channel_intensities[weakest_ch]:.0f} counts)")
            logger.info(f"✅ Strongest channel: {strongest_ch} ({channel_intensities[strongest_ch]:.0f} counts)")
            
            # Turn off all channels
            self.ctrl.turn_off_channels()
            time.sleep(LED_DELAY)
            
            # ========================================================================
            # STEP 2: Optimize integration time for WEAKEST channel
            # ========================================================================
            logger.info(f"📊 Step 3.2: Optimizing integration time for weakest channel ({weakest_ch})...")
            
            # Activate weakest channel
            self.ctrl.set_intensity(ch=weakest_ch, raw_val=S_LED_INT)
            time.sleep(LED_DELAY)
            
            # Increase integration time until weakest channel reaches good signal
            int_array = self.usb.read_intensity()
            if int_array is not None:
                current_count = int_array[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()
                
                # Target: Get weakest channel close to S_COUNT_MAX (good signal strength)
                while current_count < S_COUNT_MAX and self.state.integration < max_int:
                    self.state.integration += (
                        integration_step / 1000.0
                    )  # Convert ms to seconds
                    logger.debug(
                        f"Increasing integration time to {self.state.integration * 1000:.1f}ms "
                        f"(weakest channel at {current_count:.0f} counts)",
                    )

                    self.usb.set_integration(self.state.integration)
                    time.sleep(0.02)

                    int_array = self.usb.read_intensity()
                    if int_array is None:
                        break

                    current_count = int_array[
                        self.state.wave_min_index : self.state.wave_max_index
                    ].max()
            
            logger.info(f"✅ Integration time optimized for weakest channel: {self.state.integration * 1000:.1f}ms")
            
            # ========================================================================
            # STEP 3: Verify strongest channel doesn't saturate at this integration time
            # ========================================================================
            logger.info(f"📊 Step 3.3: Checking strongest channel ({strongest_ch}) for saturation...")
            
            # Switch to strongest channel
            # CRITICAL: Use LOWER LED intensity (50 instead of 168) to check saturation
            # This allows higher integration time for weak channels
            S_LED_CHECK = 50  # Reduced from 168 to allow more room for weak channels
            logger.info(f"   Checking saturation at LED={S_LED_CHECK} (reduced to allow higher integration time)")
            
            self.ctrl.set_intensity(ch=weakest_ch, raw_val=0)
            time.sleep(LED_DELAY)
            self.ctrl.set_intensity(ch=strongest_ch, raw_val=S_LED_CHECK)
            time.sleep(LED_DELAY)
            
            # Check if strongest channel saturates
            int_array = self.usb.read_intensity()
            if int_array is not None:
                current_count = int_array[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()
                
                logger.debug(f"Strongest channel intensity: {current_count:.0f} counts (limit: {S_COUNT_MAX})")
                
                # If strongest channel saturates, decrease integration time
                while (
                    current_count > S_COUNT_MAX
                    and self.state.integration > MIN_INTEGRATION / 1000.0
                ):
                    self.state.integration -= (
                        integration_step / 1000.0
                    )  # Convert ms to seconds

                    logger.debug(
                        f"Decreasing integration time to {self.state.integration * 1000:.1f}ms "
                        f"(strongest channel saturating at {current_count:.0f} counts)",
                    )

                    self.usb.set_integration(self.state.integration)
                    time.sleep(0.02)

                    int_array = self.usb.read_intensity()
                    if int_array is None:
                        break

                    current_count = int_array[
                        self.state.wave_min_index : self.state.wave_max_index
                    ].max()
                
                if current_count > S_COUNT_MAX:
                    logger.warning(f"⚠️ Strongest channel still near saturation ({current_count:.0f} counts)")
                    logger.warning(f"   Will reduce LED intensity for strong channels in next step")
                else:
                    logger.info(f"✅ Strongest channel within range: {current_count:.0f} counts")
            
            # Turn off all channels
            self.ctrl.turn_off_channels()
            time.sleep(LED_DELAY)

            integration_ms = self.state.integration * 1000
            logger.info(f"✅ Final integration time: {integration_ms:.1f}ms (optimized for weakest channel)")

            # Calculate number of scans to average (MAX_READ_TIME from settings)
            MAX_READ_TIME = 50  # milliseconds (from settings import may fail)
            self.state.num_scans = int(MAX_READ_TIME / self.state.integration)
            logger.debug(f"Scans to average: {self.state.num_scans}")

            return True

        except Exception as e:
            logger.exception(f"Error calibrating integration time: {e}")
            return False

    # ========================================================================
    # STEP 4: LED INTENSITY CALIBRATION (S-MODE)
    # ========================================================================

    def calibrate_led_s_mode_adaptive(self, ch: str) -> bool:
        """Adaptive LED intensity calibration using smart convergence algorithm.

        This method combines coarse, medium, and fine adjustments into a single
        efficient algorithm that converges faster than the traditional 3-step method.

        Args:
            ch: Channel identifier ('a', 'b', 'c', or 'd')

        Returns:
            True if successful, False otherwise

        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            logger.debug(f"Starting adaptive LED calibration for channel {ch}")

            # Initialize percentage-based calibration parameters
            target_intensity = calculate_target_intensity(TARGET_INTENSITY_PERCENT)
            tolerance = calculate_intensity_tolerance()
            max_iterations = ADAPTIVE_MAX_ITERATIONS
            convergence_factor = ADAPTIVE_CONVERGENCE_FACTOR

            # Get target wavelength range indices
            wave_data = self.state.wavelengths
            target_min_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MIN))
            target_max_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MAX))

            logger.info(
                f"📊 S-mode target: {TARGET_INTENSITY_PERCENT}% = {target_intensity:.0f} counts "
                f"in {TARGET_WAVELENGTH_MIN}-{TARGET_WAVELENGTH_MAX}nm range"
            )

            # Smart starting point: use previous S-mode data if available
            previous_s_intensity = self.state.ref_intensity.get(ch, 0)
            if previous_s_intensity > 0:
                # Estimate LED from previous intensity (rough approximation)
                intensity_ratio = previous_s_intensity / target_intensity
                estimated_led = max(1, min(255, int(128 * intensity_ratio)))
                current_led = estimated_led
                logger.info(f"🎯 Using estimated S-mode LED for {ch}: {current_led} (from intensity {previous_s_intensity:.0f})")
            else:
                # Start at mid-range intensity (fallback)
                current_led = 128
                logger.info(f"📊 Using default S-mode starting point for {ch}: {current_led}")

            best_led = current_led
            best_error = float("inf")

            for iteration in range(max_iterations):
                if self._is_stopped():
                    return False

                # Set LED intensity and allow stabilization
                self.ctrl.set_intensity(ch=ch, raw_val=current_led)
                time.sleep(ADAPTIVE_STABILIZATION_DELAY)

                # Measure current intensity in TARGET WAVELENGTH RANGE
                spectrum = self.usb.read_intensity()
                signal_region = spectrum[target_min_idx:target_max_idx]
                measured_intensity = signal_region.max()
                measured_percent = (measured_intensity / DETECTOR_MAX_COUNTS) * 100

                # Calculate error from target
                intensity_error = abs(measured_intensity - target_intensity)

                logger.debug(
                    f"Adaptive iter {iteration}: LED={current_led}, "
                    f"measured={measured_intensity:.0f} ({measured_percent:.1f}%), error={intensity_error:.0f}",
                )

                # Track best result
                if intensity_error < best_error:
                    best_error = intensity_error
                    best_led = current_led

                # Check convergence
                if intensity_error <= tolerance:
                    logger.debug(
                        f"Channel {ch} converged in {iteration + 1} iterations: "
                        f"LED={current_led}, intensity={measured_intensity:.0f} ({measured_percent:.1f}%)",
                    )
                    self.state.ref_intensity[ch] = current_led
                    return True

                # Calculate adaptive step size
                error_ratio = intensity_error / target_intensity
                base_step = error_ratio * ADAPTIVE_MAX_STEP * convergence_factor

                # Apply iteration damping (reduce step size as we iterate)
                iteration_damping = max(0.3, 1.0 - (iteration * 0.1))
                adaptive_step = base_step * iteration_damping

                # Clamp step size
                step_size = max(
                    ADAPTIVE_MIN_STEP,
                    min(ADAPTIVE_MAX_STEP, int(adaptive_step)),
                )

                # Determine direction and calculate next LED value
                if measured_intensity < target_intensity:
                    # Need more LED intensity
                    next_led = current_led + step_size
                else:
                    # Need less LED intensity
                    next_led = current_led - step_size

                # Ensure LED value is within valid bounds
                next_led = max(1, min(255, next_led))

                # Prevent oscillation by checking minimum progress
                if iteration > 3 and abs(next_led - current_led) <= 1:
                    logger.debug(
                        f"Channel {ch} reached minimum step, using best result",
                    )
                    break

                current_led = next_led

            # Use best result if we didn't converge within iterations
            logger.debug(
                f"Channel {ch} adaptive calibration complete: LED={best_led}, "
                f"final error={best_error:.0f}",
            )
            self.state.ref_intensity[ch] = best_led
            return True

        except Exception as e:
            logger.exception(f"Error in adaptive LED calibration for channel {ch}: {e}")
            return False
        finally:
            # Always turn off the LED for this channel after calibration
            try:
                if self.ctrl is not None:
                    logger.debug(f"Turning off LED for channel {ch}")
                    self.ctrl.set_intensity(ch=ch, raw_val=0)
            except Exception as e:
                logger.warning(f"Failed to turn off LED for channel {ch}: {e}")

    def calibrate_led_s_mode(self, ch: str) -> bool:
        """Calibrate LED intensity for a single channel in S-polarization mode.

        This method uses ONLY the adaptive calibration algorithm.
        Legacy 3-step method has been disabled for improved performance.

        Args:
            ch: Channel identifier ('a', 'b', 'c', or 'd')

        Returns:
            True if successful, False otherwise

        """
        try:
            if self.ctrl is None or self.usb is None:
                logger.error("Hardware not available for calibration")
                return False

            # Use ONLY adaptive calibration (no fallback)
            logger.info(f"Starting adaptive calibration for LED {ch}")
            success = self.calibrate_led_s_mode_adaptive(ch)

            if success:
                logger.info(f"Adaptive calibration successful for LED {ch}")
                return True

            logger.error(f"Adaptive calibration failed for LED {ch}")
            return False

        except Exception as e:
            logger.exception(f"Error calibrating LED {ch} in S-mode: {e}")
            return False

    def _calibrate_led_s_mode_legacy(self, ch: str) -> bool:
        """Legacy 3-step LED calibration method (coarse, medium, fine).

        Kept as backup method when adaptive calibration fails.

        Args:
            ch: Channel identifier ('a', 'b', 'c', or 'd')

        Returns:
            True if successful, False otherwise

        """
        try:
            logger.debug(f"Calibrating LED {ch} in S-mode (legacy method)...")

            # Start at maximum intensity for S-polarized light
            intensity = deepcopy(P_LED_MAX)
            self.ctrl.set_intensity(ch=ch, raw_val=intensity)
            time.sleep(LED_DELAY)

            calibration_max = self.usb.read_intensity()[
                self.state.wave_min_index : self.state.wave_max_index
            ].max()

            logger.debug(f"Initial intensity: {intensity} = {calibration_max} counts")

            # Coarse adjustment (step by 20)
            while (
                calibration_max > S_COUNT_MAX
                and intensity > COARSE_ADJUSTMENT
                and not self._is_stopped()
            ):
                intensity -= COARSE_ADJUSTMENT
                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                time.sleep(LED_DELAY)

                calibration_max = self.usb.read_intensity()[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()

            logger.debug(f"After coarse adjust: {intensity} = {calibration_max} counts")

            # Medium adjustment (step by 5)
            while (
                calibration_max < S_COUNT_MAX
                and intensity < P_LED_MAX
                and not self._is_stopped()
            ):
                intensity += MEDIUM_ADJUSTMENT
                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                time.sleep(LED_DELAY)

                calibration_max = self.usb.read_intensity()[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()

            logger.debug(f"After medium adjust: {intensity} = {calibration_max} counts")

            # Fine adjustment (step by 1)
            while calibration_max > S_COUNT_MAX and intensity > FINE_ADJUSTMENT + 1:
                intensity -= FINE_ADJUSTMENT
                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                time.sleep(LED_DELAY)

                calibration_max = self.usb.read_intensity()[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()

            logger.debug(f"After fine adjust: {intensity} = {calibration_max} counts")

            # Store calibrated intensity
            self.state.ref_intensity[ch] = deepcopy(intensity)
            return True

        except Exception as e:
            logger.exception(f"Error in legacy LED calibration for channel {ch}: {e}")
            return False

    def calibrate_led_s_mode_original(self, ch: str) -> bool:
        """DEPRECATED: Original calibrate_led_s_mode method preserved for reference.

        Args:
            ch: Channel identifier ('a', 'b', 'c', or 'd')

        Returns:
            True if successful, False otherwise

        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            logger.debug(f"Calibrating LED {ch} in S-mode...")

            # Start at maximum intensity for S-polarized light
            intensity = deepcopy(P_LED_MAX)
            self.ctrl.set_intensity(ch=ch, raw_val=intensity)
            time.sleep(LED_DELAY)

            calibration_max = self.usb.read_intensity()[
                self.state.wave_min_index : self.state.wave_max_index
            ].max()

            logger.debug(f"Initial intensity: {intensity} = {calibration_max} counts")

            # Coarse adjustment (step by 20)
            while (
                calibration_max > S_COUNT_MAX
                and intensity > COARSE_ADJUSTMENT
                and not self._is_stopped()
            ):
                intensity -= COARSE_ADJUSTMENT
                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                time.sleep(LED_DELAY)

                calibration_max = self.usb.read_intensity()[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()

            logger.debug(f"After coarse adjust: {intensity} = {calibration_max} counts")

            # Medium adjustment (step by 5)
            while (
                calibration_max < S_COUNT_MAX
                and intensity < P_LED_MAX
                and not self._is_stopped()
            ):
                intensity += MEDIUM_ADJUSTMENT
                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                time.sleep(LED_DELAY)

                calibration_max = self.usb.read_intensity()[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()

            logger.debug(f"After medium adjust: {intensity} = {calibration_max} counts")

            # Fine adjustment (step by 1)
            while calibration_max > S_COUNT_MAX and intensity > FINE_ADJUSTMENT + 1:
                intensity -= FINE_ADJUSTMENT
                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                time.sleep(LED_DELAY)

                calibration_max = self.usb.read_intensity()[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()

            logger.debug(f"After fine adjust: {intensity} = {calibration_max} counts")

            # Store calibrated intensity
            self.state.ref_intensity[ch] = deepcopy(intensity)
            return True

        except Exception as e:
            logger.exception(f"Error calibrating LED {ch} in S-mode: {e}")
            return False

    # ========================================================================
    # STEP 5: DARK NOISE MEASUREMENT
    # ========================================================================

    def measure_dark_noise(self) -> bool:
        """Measure dark noise with all LEDs off.

        Returns:
            True if successful, False otherwise

        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            self.ctrl.turn_off_channels()
            time.sleep(LED_DELAY)

            # Adjust scan count based on integration time
            if self.state.integration < INTEGRATION_STEP_THRESHOLD:
                dark_scans = DARK_NOISE_SCANS
            else:
                dark_scans = int(DARK_NOISE_SCANS / 2)

            logger.debug(f"Measuring dark noise with {dark_scans} scans")

            # Measure dark noise for full spectrum, then crop later in data acquisition
            try:
                test_spectrum = self.usb.read_intensity()
                if test_spectrum is None or len(test_spectrum) == 0:
                    logger.error("Cannot determine spectrum length for dark noise measurement")
                    return False
                full_spectrum_length = len(test_spectrum)
            except Exception as e:
                logger.error(f"Failed to read test spectrum for dark noise: {e}")
                return False

            dark_noise_sum = np.zeros(full_spectrum_length)

            for _scan in range(dark_scans):
                if self._is_stopped():
                    return False

                intensity = self.usb.read_intensity()
                if intensity is None:
                    logger.error("Failed to read intensity for dark noise")
                    return False

                # Store full spectrum dark noise
                dark_noise_sum += intensity

            # Store dark noise with explicit size logging
            full_spectrum_dark_noise = dark_noise_sum / dark_scans

            # Store full spectrum dark noise for universal resampling
            self.state.full_spectrum_dark_noise = full_spectrum_dark_noise

            # UNIVERSAL RESAMPLING: Intelligently resample dark noise to match data acquisition
            # This replaces the legacy cropping approach with adaptive resampling
            try:
                from scipy.interpolate import interp1d

                # Get target wavelength range from calibration
                target_wavelengths = self.state.wavelengths
                full_wavelengths = self.state.full_spectrum_wavelengths

                if len(target_wavelengths) > 0 and len(full_wavelengths) > 0:
                    # Create interpolation function for universal resampling
                    source_indices = np.arange(len(full_spectrum_dark_noise))
                    interpolator = interp1d(source_indices, full_spectrum_dark_noise,
                                          kind='linear', bounds_error=False,
                                          fill_value='extrapolate')

                    # Calculate target indices for resampling
                    target_indices = np.linspace(self.state.wave_min_index,
                                                self.state.wave_max_index - 1,
                                                len(target_wavelengths))

                    # Perform universal resampling
                    resampled_dark_noise = interpolator(target_indices)
                    self.state.dark_noise = resampled_dark_noise

                    logger.info(
                        f"✅ UNIVERSAL DARK NOISE RESAMPLING complete:"
                        f"\n  • Full spectrum size: {len(full_spectrum_dark_noise)} pixels"
                        f"\n  • Resampled size: {len(resampled_dark_noise)} pixels"
                        f"\n  • Target wavelength range: {len(target_wavelengths)} points"
                        f"\n  • Resampling method: Universal interpolation (scipy.interp1d)"
                        f"\n  • Max dark noise: {max(resampled_dark_noise):.1f} counts"
                    )
                else:
                    # Fallback to cropping if wavelength data unavailable
                    logger.warning("⚠️ Wavelength data unavailable, falling back to cropping")
                    cropped_dark_noise = full_spectrum_dark_noise[self.state.wave_min_index : self.state.wave_max_index]
                    self.state.dark_noise = cropped_dark_noise

            except ImportError:
                logger.warning("⚠️ scipy.interpolate unavailable, using legacy cropping")
                # Fallback to legacy cropping method
                cropped_dark_noise = full_spectrum_dark_noise[self.state.wave_min_index : self.state.wave_max_index]
                self.state.dark_noise = cropped_dark_noise
            return True

        except Exception as e:
            logger.exception(f"Error measuring dark noise: {e}")
            return False

    # ========================================================================
    # STEP 6: REFERENCE SIGNAL MEASUREMENT
    # ========================================================================

    def measure_reference_signals(self, ch_list: list[str]) -> bool:
        """Measure reference signals in S-mode for all channels.

        Args:
            ch_list: List of channels to measure

        Returns:
            True if successful, False otherwise

        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            self.ctrl.set_mode(mode="s")
            time.sleep(0.4)

            for ch in ch_list:
                if self._is_stopped():
                    return False

                logger.debug(f"Measuring reference signal for channel {ch}")

                self.ctrl.set_intensity(ch=ch, raw_val=self.state.ref_intensity[ch])
                time.sleep(LED_DELAY)

                # Adjust scan count based on integration time
                if self.state.integration < INTEGRATION_STEP_THRESHOLD:
                    ref_scans = REF_SCANS
                else:
                    ref_scans = int(REF_SCANS / 2)

                ref_data_sum = np.zeros_like(self.state.dark_noise)

                for _scan in range(ref_scans):
                    if self._is_stopped():
                        return False

                    int_val = self.usb.read_intensity()
                    if int_val is None:
                        logger.error(f"Failed to read intensity for channel {ch}")
                        return False

                    # Use FULL SPECTRUM - no truncation, subtract dark noise
                    ref_data_single = int_val - self.state.dark_noise
                    ref_data_sum += ref_data_single

                self.state.ref_sig[ch] = deepcopy(ref_data_sum / ref_scans)

                logger.debug(
                    f"Channel {ch} reference signal: max={max(self.state.ref_sig[ch]):.1f} counts",
                )

            return True

        except Exception as e:
            logger.exception(f"Error measuring reference signals: {e}")
            return False

    # ========================================================================
    # STEP 8: LED INTENSITY CALIBRATION (P-MODE)
    # ========================================================================

    def calibrate_led_p_mode_adaptive(self, ch_list: list[str]) -> bool:
        """Adaptive LED intensity calibration for P-polarization mode.

        Uses intelligent convergence algorithm to optimize P-mode LED intensities
        based on the S-mode calibration results.

        Args:
            ch_list: List of channels to calibrate

        Returns:
            True if successful, False otherwise

        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            for ch in ch_list:
                if self._is_stopped():
                    return False

                logger.debug(f"Adaptive P-mode calibration for channel {ch}")

                # Smart starting point: use previous P-mode data if available
                s_mode_intensity = self.state.ref_intensity[ch]
                previous_p_led = self.state.leds_calibrated.get(ch, 0)

                if previous_p_led > 0:
                    # Start from previous P-mode LED value (fast convergence)
                    current_led = previous_p_led
                    logger.info(f"🎯 Using previous P-mode LED for {ch}: {current_led}")
                else:
                    # Start at mid-high range for P-mode (typically needs more LED power)
                    current_led = 180
                    logger.info(f"📊 Using default P-mode starting point for {ch}: {current_led}")

                # Use SAME percentage-based target as S-mode
                # P-mode MAY naturally achieve lower signal (perpendicular polarization), but we still aim for same target
                target_intensity = calculate_target_intensity(TARGET_INTENSITY_PERCENT)
                tolerance = calculate_intensity_tolerance()
                max_iterations = ADAPTIVE_MAX_ITERATIONS // 2  # Fewer iterations if starting from good point

                # Get target wavelength range indices
                wave_data = self.state.wavelengths
                target_min_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MIN))
                target_max_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MAX))

                logger.info(
                    f"📊 P-mode target: {TARGET_INTENSITY_PERCENT}% = {target_intensity:.0f} counts "
                    f"in {TARGET_WAVELENGTH_MIN}-{TARGET_WAVELENGTH_MAX}nm range "
                    f"(Note: P-mode naturally weaker, may not reach target)"
                )
                best_led = current_led
                best_error = float("inf")

                for iteration in range(max_iterations):
                    if self._is_stopped():
                        return False

                    # Set LED intensity and allow stabilization
                    self.ctrl.set_intensity(ch=ch, raw_val=current_led)
                    time.sleep(ADAPTIVE_STABILIZATION_DELAY)

                    # Measure current intensity in TARGET WAVELENGTH RANGE
                    spectrum = self.usb.read_intensity()
                    signal_region = spectrum[target_min_idx:target_max_idx]
                    measured_intensity = signal_region.max()
                    measured_percent = (measured_intensity / DETECTOR_MAX_COUNTS) * 100

                    # Calculate error from target
                    intensity_error = abs(measured_intensity - target_intensity)

                    logger.debug(
                        f"P-mode adaptive iter {iteration}: LED={current_led}, "
                        f"measured={measured_intensity:.0f} ({measured_percent:.1f}%), target={target_intensity:.0f}, "
                        f"error={intensity_error:.0f}",
                    )

                    # Track best result
                    if intensity_error < best_error:
                        best_error = intensity_error
                        best_led = current_led

                    # Check convergence
                    if intensity_error <= tolerance:
                        logger.debug(
                            f"P-mode channel {ch} converged in {iteration + 1} iterations: "
                            f"LED={current_led}, intensity={measured_intensity:.0f} ({measured_percent:.1f}%)",
                        )
                        self.state.leds_calibrated[ch] = current_led
                        break

                    # Check if we're hitting saturation (95% of detector max)
                    saturation_threshold = DETECTOR_MAX_COUNTS * 0.95
                    if measured_intensity > saturation_threshold:
                        logger.debug(
                            f"P-mode channel {ch} approaching saturation limit ({measured_percent:.1f}%)",
                        )
                        self.state.leds_calibrated[ch] = current_led
                        break

                    # Calculate adaptive step size (more conservative for P-mode)
                    error_ratio = intensity_error / target_intensity
                    base_step = (
                        error_ratio * ADAPTIVE_MAX_STEP * 0.6
                    )  # More conservative

                    # Apply iteration damping
                    iteration_damping = max(0.2, 1.0 - (iteration * 0.15))
                    adaptive_step = base_step * iteration_damping

                    # Clamp step size (smaller for P-mode precision)
                    step_size = max(
                        ADAPTIVE_MIN_STEP,
                        min(ADAPTIVE_MAX_STEP // 2, int(adaptive_step)),
                    )

                    # Determine direction and calculate next LED value
                    if measured_intensity < target_intensity:
                        next_led = current_led + step_size
                    else:
                        next_led = current_led - step_size

                    # Ensure LED value is within valid bounds
                    next_led = max(1, min(P_LED_MAX, next_led))

                    # Prevent oscillation
                    if iteration > 5 and abs(next_led - current_led) <= 1:
                        logger.debug(
                            f"P-mode channel {ch} reached minimum step, using best result",
                        )
                        break

                    current_led = next_led

                # Use best result if we didn't converge within iterations
                if (
                    ch not in self.state.leds_calibrated
                    or self.state.leds_calibrated[ch] == 0
                ):
                    self.state.leds_calibrated[ch] = best_led

                logger.debug(
                    f"P-mode channel {ch} adaptive calibration complete: "
                    f"LED={self.state.leds_calibrated[ch]}, final error={best_error:.0f}",
                )

            return True

        except Exception as e:
            logger.exception(f"Error in adaptive P-mode LED calibration: {e}")
            return False
        finally:
            # Always turn off all LEDs after P-mode calibration
            try:
                if self.ctrl is not None:
                    for ch in ch_list:
                        self.ctrl.set_intensity(ch=ch, raw_val=0)
                        logger.debug(f"Turned off P-mode LED for channel {ch}")
            except Exception as e:
                logger.warning(f"Failed to turn off P-mode LEDs: {e}")

    def calibrate_led_p_mode(self, ch_list: list[str]) -> bool:
        """Fine-tune LED intensities in P-polarization mode.

        Args:
            ch_list: List of channels to calibrate

        Returns:
            True if successful, False otherwise

        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            for ch in ch_list:
                if self._is_stopped():
                    return False

                logger.debug(f"Fine-tuning LED {ch} in P-mode...")

                p_intensity = deepcopy(self.state.ref_intensity[ch])
                self.ctrl.set_intensity(ch=ch, raw_val=p_intensity)
                time.sleep(LED_DELAY)

                calibration_max = self.usb.read_intensity()[
                    self.state.wave_min_index : self.state.wave_max_index
                ].max()

                initial_counts = deepcopy(calibration_max)
                logger.debug(f"Initial counts in P-mode: {initial_counts}")

                # Coarse adjustment (increase to target)
                target_counts = initial_counts * P_MAX_INCREASE
                while (
                    calibration_max < target_counts
                    and calibration_max < S_COUNT_MAX
                    and p_intensity < (P_LED_MAX - COARSE_ADJUSTMENT)
                ):
                    p_intensity += COARSE_ADJUSTMENT
                    self.ctrl.set_intensity(ch=ch, raw_val=p_intensity)
                    time.sleep(LED_DELAY)

                    calibration_max = self.usb.read_intensity()[
                        self.state.wave_min_index : self.state.wave_max_index
                    ].max()

                logger.debug(
                    f"After coarse adjust: {p_intensity} = {calibration_max} counts",
                )

                # Medium adjustment (decrease if over target)
                while (
                    calibration_max > target_counts and p_intensity > MEDIUM_ADJUSTMENT
                ):
                    p_intensity -= MEDIUM_ADJUSTMENT
                    self.ctrl.set_intensity(ch=ch, raw_val=p_intensity)
                    time.sleep(LED_DELAY)

                    calibration_max = self.usb.read_intensity()[
                        self.state.wave_min_index : self.state.wave_max_index
                    ].max()

                logger.debug(
                    f"After medium adjust: {p_intensity} = {calibration_max} counts",
                )

                # Fine adjustment (increase to target)
                while (
                    calibration_max < target_counts
                    and calibration_max < S_COUNT_MAX
                    and p_intensity < P_LED_MAX
                ):
                    p_intensity += FINE_ADJUSTMENT
                    self.ctrl.set_intensity(ch=ch, raw_val=p_intensity)
                    time.sleep(LED_DELAY)

                    calibration_max = self.usb.read_intensity()[
                        self.state.wave_min_index : self.state.wave_max_index
                    ].max()

                logger.debug(
                    f"After fine adjust: {p_intensity} = {calibration_max} counts",
                )

                # Store calibrated intensity
                self.state.leds_calibrated[ch] = deepcopy(p_intensity)

            return True

        except Exception as e:
            logger.exception(f"Error calibrating LEDs in P-mode: {e}")
            return False

    # ========================================================================
    # STEP 9: VALIDATION
    # ========================================================================

    def validate_calibration(self) -> tuple[bool, str]:
        """Validate that all channels meet calibration requirements.

        In DEVELOPMENT_MODE: Always passes, just logs measurements for debugging.
        In Production Mode: Checks percentage-based thresholds in target wavelength range.

        Returns:
            Tuple of (success, error_string)

        """
        try:
            if self.ctrl is None or self.usb is None:
                return False, "No devices"

            if DEVELOPMENT_MODE:
                logger.info("🔧 DEVELOPMENT MODE - Skipping validation thresholds")
                logger.info("   Logging measurements for debugging...")

                # Just log measurements, don't validate
                for ch in CH_LIST:
                    if self._is_stopped():
                        break

                    intensity = self.state.leds_calibrated[ch]
                    self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                    time.sleep(LED_DELAY)

                    spectrum = self.usb.read_intensity()
                    max_intensity = spectrum.max()
                    max_percent = (max_intensity / DETECTOR_MAX_COUNTS) * 100

                    # Find target range
                    wave_data = self.state.wavelengths
                    target_min_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MIN))
                    target_max_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MAX))
                    target_max = spectrum[target_min_idx:target_max_idx].max()
                    target_percent = (target_max / DETECTOR_MAX_COUNTS) * 100

                    logger.info(
                        f"   Channel {ch}: LED={intensity}, "
                        f"max={max_intensity:.0f} ({max_percent:.1f}%), "
                        f"target_range={target_max:.0f} ({target_percent:.1f}%)"
                    )

                # Always pass in development mode
                self.state.ch_error_list = []
                self.state.is_calibrated = True
                self.state.calibration_timestamp = time.time()
                logger.info("✅ DEVELOPMENT MODE - Calibration accepted without validation")
                return True, ""

            # Production mode - validate with percentage thresholds
            self.state.ch_error_list = []
            wave_data = self.state.wavelengths
            target_min_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MIN))
            target_max_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MAX))

            min_threshold = DETECTOR_MAX_COUNTS * MIN_INTENSITY_PERCENT / 100.0
            max_threshold = DETECTOR_MAX_COUNTS * MAX_INTENSITY_PERCENT / 100.0

            for ch in CH_LIST:
                if self._is_stopped():
                    break

                intensity = self.state.leds_calibrated[ch]
                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                time.sleep(LED_DELAY)

                spectrum = self.usb.read_intensity()
                target_max = spectrum[target_min_idx:target_max_idx].max()
                target_percent = (target_max / DETECTOR_MAX_COUNTS) * 100

                if target_max < min_threshold or target_max > max_threshold:
                    self.state.ch_error_list.append(ch)
                    logger.warning(
                        f"Calibration failed on channel {ch}: "
                        f"intensity={target_max:.1f} ({target_percent:.1f}%) at LED={intensity} "
                        f"(range: {MIN_INTENSITY_PERCENT}-{MAX_INTENSITY_PERCENT}%)",
                    )

            # Build error string
            ch_str = (
                ", ".join(self.state.ch_error_list) if self.state.ch_error_list else ""
            )
            calibration_success = len(self.state.ch_error_list) == 0

            if calibration_success:
                logger.info("✓ Calibration validation passed for all channels")
                self.state.is_calibrated = True
                self.state.calibration_timestamp = time.time()
            else:
                logger.warning(
                    f"✗ Calibration validation failed for channels: {ch_str}",
                )

            return calibration_success, ch_str

        except Exception as e:
            logger.exception(f"Error validating calibration: {e}")
            return False, "Validation error"

    # ========================================================================
    # FULL CALIBRATION ORCHESTRATION
    # ========================================================================

    def run_full_calibration(
        self,
        auto_polarize: bool = False,
        auto_polarize_callback: Callable[[], None] | None = None,
        use_previous_data: bool = False,  # DISABLED: Always run fresh calibration to avoid stale data
        auto_save: bool = True,
    ) -> tuple[bool, str]:
        """Execute the complete 9-step calibration sequence.

        Args:
            auto_polarize: Whether to run auto-polarization in step 2
            auto_polarize_callback: Optional callback for auto-polarization
            use_previous_data: Load previous calibration as starting point (DISABLED by default)
            auto_save: Automatically save successful calibration

        Returns:
            Tuple of (success, error_channels_string)

        """
        try:
            logger.debug("=== Starting FRESH calibration sequence (no legacy data) ===")

            # DISABLED: Legacy calibration loading causes stale data and array mismatches
            # Always run fresh calibration to ensure universal resampling works correctly
            previous_loaded = False
            if use_previous_data:
                logger.warning("⚠️ Loading previous calibration data (NOT RECOMMENDED)...")
                success, message = self.load_latest_profile()
                if success:
                    logger.info(f"✅ Loaded previous calibration: {message}")
                    previous_loaded = True
                else:
                    logger.info(f"ℹ️ No previous calibration found: {message}")

            # Step 1: Wavelength range calibration
            logger.debug("Step 1: Wavelength range calibration")
            self._emit_progress(1, "Calibrating wavelength range...")
            success, integration_step = self.calibrate_wavelength_range()
            if not success or self._is_stopped():
                self._safe_hardware_cleanup()
                return False, "Wavelength calibration failed"

            # Step 2: Auto-polarize if enabled
            if auto_polarize and not self._is_stopped():
                logger.debug("Step 2: Auto-polarization")
                self._emit_progress(2, "Auto-aligning polarizer...")
                if auto_polarize_callback is not None:
                    auto_polarize_callback()

            # Determine which channels to calibrate
            ch_list = CH_LIST
            if self.device_type in ["PicoEZSPR"]:  # EZSPR disabled (obsolete)
                ch_list = EZ_CH_LIST

            # Step 3: Integration time calibration
            logger.debug(f"Step 3: Integration time calibration for channels {ch_list}")
            self._emit_progress(
                3,
                f"Optimizing integration time ({len(ch_list)} channels)...",
            )
            success = self.calibrate_integration_time(ch_list, integration_step)
            if not success or self._is_stopped():
                self._safe_hardware_cleanup()
                return False, "Integration time calibration failed"

            # Step 4: LED intensity calibration in S-mode (adaptive)
            logger.debug("Step 4: LED intensity calibration (S-mode adaptive)")
            self._emit_progress(4, "Calibrating LED intensities (adaptive S-mode)...")
            for ch in ch_list:
                if self._is_stopped():
                    break
                success = self.calibrate_led_s_mode_adaptive(ch)
                if not success:
                    logger.warning(f"Failed to calibrate LED {ch} in S-mode (adaptive)")

            if self._is_stopped():
                self._safe_hardware_cleanup()
                return False, "Stopped during S-mode calibration"

            logger.debug(f"S-mode LED calibration complete: {self.state.ref_intensity}")

            # Step 5: Dark noise measurement
            logger.debug("Step 5: Dark noise measurement")
            self._emit_progress(5, "Measuring dark noise...")
            success = self.measure_dark_noise()
            if not success or self._is_stopped():
                self._safe_hardware_cleanup()
                return False, "Dark noise measurement failed"

            # Step 6: Reference signal measurement (S-mode)
            logger.debug("Step 6: Reference signal measurement (S-mode)")
            self._emit_progress(6, "Capturing reference signals...")
            success = self.measure_reference_signals(ch_list)
            if not success or self._is_stopped():
                self._safe_hardware_cleanup()
                return False, "Reference signal measurement failed"

            # Step 7: Switch to P-mode
            logger.debug("Step 7: Switching to P-mode")
            self._emit_progress(7, "Switching to P-polarization mode...")
            if self.ctrl is None:
                self._safe_hardware_cleanup()
                return False, "No controller available"

            self.ctrl.set_mode(mode="p")
            time.sleep(0.4)

            # Step 8: LED intensity calibration (P-mode adaptive)
            logger.debug("Step 8: LED intensity calibration (P-mode adaptive)")
            self._emit_progress(8, "Fine-tuning LED intensities (adaptive P-mode)...")
            success = self.calibrate_led_p_mode_adaptive(ch_list)
            if not success or self._is_stopped():
                self._safe_hardware_cleanup()
                return False, "P-mode LED calibration failed"

            logger.debug(
                f"P-mode LED calibration complete: {self.state.leds_calibrated}",
            )

            # Step 9: Validate calibration
            logger.debug("Step 9: Validation")
            self._emit_progress(9, "Validating calibration...")
            calibration_success, ch_error_str = self.validate_calibration()

            # Always cleanup hardware after validation
            self._safe_hardware_cleanup()

            # Auto-save successful calibration
            if calibration_success and auto_save:
                logger.info("💾 Auto-saving calibration data...")
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                profile_name = f"auto_save_{timestamp}"
                save_success = self.save_profile(profile_name, self.device_type or "unknown")
                if save_success:
                    logger.info(f"✅ Calibration saved as: {profile_name}")
                else:
                    logger.warning("⚠️ Failed to auto-save calibration")

            logger.debug("=== Calibration sequence complete ===")
            return calibration_success, ch_error_str

        except Exception as e:
            logger.exception(f"Error during full calibration: {e}")
            # Emergency hardware cleanup on any exception
            self._safe_hardware_cleanup()
            return False, f"Exception: {e!s}"

    # ========================================================================
    # CALIBRATION HISTORY LOGGING
    # ========================================================================

    def log_calibration_results(
        self,
        success: bool,
        error_channels: str,
        calibrated_channels: list[str],
        device_knx: str = "",
    ) -> None:
        """Log calibration results to history files for tracking and analysis.

        Args:
            success: Whether calibration was successful
            error_channels: String of channels that failed (comma-separated)
            calibrated_channels: List of channels that were calibrated
            device_knx: KNX device identifier

        """
        try:
            # Create calibration history directory
            history_dir = Path(ROOT_DIR) / "calibration_history"
            history_dir.mkdir(exist_ok=True)

            # Prepare log entry
            timestamp = dt.datetime.now(TIME_ZONE)
            log_entry = {
                "timestamp": timestamp.isoformat(),
                "success": success,
                "device_type": self.device_type,
                "device_knx": device_knx,
                "error_channels": error_channels,
                "calibrated_channels": calibrated_channels,
                "integration_time_ms": self.state.integration * 1000,
                "num_scans": self.state.num_scans,
                "ref_intensity": self.state.ref_intensity.copy(),
                "leds_calibrated": self.state.leds_calibrated.copy(),
                "wavelength_range": f"{self.state.wave_min_index}-{self.state.wave_max_index}",
            }

            # Append to JSON lines file (one JSON object per line)
            history_file = history_dir / "calibration_history.jsonl"
            with history_file.open("a") as f:
                f.write(json.dumps(log_entry) + "\n")

            # Also create a dated CSV file for easy viewing
            csv_file = (
                history_dir
                / f"calibration_log_{timestamp.year}_{timestamp.month:02d}.csv"
            )

            # Check if CSV needs header
            needs_header = not csv_file.exists()

            with csv_file.open("a", newline="") as f:
                fieldnames = [
                    "Timestamp",
                    "Success",
                    "Device",
                    "Error Channels",
                    "Integration (ms)",
                    "Num Scans",
                    "LED A",
                    "LED B",
                    "LED C",
                    "LED D",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)

                if needs_header:
                    writer.writeheader()

                writer.writerow(
                    {
                        "Timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "Success": "Yes" if success else "No",
                        "Device": self.device_type,
                        "Error Channels": error_channels or "None",
                        "Integration (ms)": self.state.integration * 1000,
                        "Num Scans": self.state.num_scans,
                        "LED A": self.state.leds_calibrated.get("a", 0),
                        "LED B": self.state.leds_calibrated.get("b", 0),
                        "LED C": self.state.leds_calibrated.get("c", 0),
                        "LED D": self.state.leds_calibrated.get("d", 0),
                    },
                )

            logger.debug(f"Calibration results logged to {history_file}")

        except Exception as e:
            logger.exception(f"Error logging calibration results: {e}")

    # ========================================================================
    # DATA PROCESSOR CREATION
    # ========================================================================

    def create_data_processor(self, med_filt_win: int = 11) -> SPRDataProcessor:
        """Create a data processor using calibrated wavelength data.

        Args:
            med_filt_win: Median filter window size

        Returns:
            Configured SPRDataProcessor instance

        """
        return SPRDataProcessor(
            wave_data=self.state.wave_data,
            fourier_weights=self.state.fourier_weights,
            med_filt_win=med_filt_win,
        )

    # ========================================================================
    # CALIBRATION PROFILE MANAGEMENT
    # ========================================================================

    def save_profile(
        self,
        profile_name: str,
        device_type: str,
    ) -> bool:
        """Save current calibration state to a profile file.

        Args:
            profile_name: Name for the profile
            device_type: Device type (e.g., 'picop4spr')

        Returns:
            True if saved successfully, False otherwise

        """
        try:
            profiles_dir = Path(ROOT_DIR) / "calibration_profiles"
            profiles_dir.mkdir(exist_ok=True)

            # Build calibration data from state
            calibration_data = {
                "profile_name": profile_name,
                "device_type": device_type,
                "timestamp": time.time(),
                "integration": self.state.integration,
                "num_scans": self.state.num_scans,
                "ref_intensity": self.state.ref_intensity.copy(),
                "leds_calibrated": self.state.leds_calibrated.copy(),
                "wave_min_index": self.state.wave_min_index,
                "wave_max_index": self.state.wave_max_index,
                "led_delay": self.state.led_delay,
                "med_filt_win": self.state.med_filt_win,
            }

            # Save to JSON
            profile_path = profiles_dir / f"{profile_name}.json"
            with profile_path.open("w") as f:
                json.dump(calibration_data, f, indent=2)

            logger.info(f"Calibration profile saved: {profile_path}")
            return True

        except Exception as e:
            logger.exception(f"Error saving calibration profile: {e}")
            return False

    def load_profile(
        self,
        profile_name: str,
        device_type: str | None = None,
    ) -> tuple[bool, str]:
        """Load calibration state from a profile file.

        Args:
            profile_name: Name of profile to load
            device_type: Expected device type (for validation), optional

        Returns:
            Tuple of (success: bool, message: str)

        """
        try:
            profiles_dir = Path(ROOT_DIR) / "calibration_profiles"
            profile_path = profiles_dir / f"{profile_name}.json"

            if not profile_path.exists():
                return False, f"Profile '{profile_name}' not found"

            # Load from JSON
            with profile_path.open("r") as f:
                calibration_data = json.load(f)

            # Verify device type if provided
            loaded_device = calibration_data.get("device_type")
            if device_type and loaded_device != device_type:
                warning = (
                    f"Profile was created for {loaded_device} "
                    f"but current device is {device_type}"
                )
                logger.warning(warning)
                # Return warning but allow loading
                return True, warning

            # Load into state
            self.state.integration = calibration_data.get(
                "integration",
                MIN_INTEGRATION,
            )
            self.state.num_scans = calibration_data.get("num_scans", 1)
            self.state.ref_intensity = calibration_data.get(
                "ref_intensity",
                dict.fromkeys(CH_LIST, 0),
            )
            self.state.leds_calibrated = calibration_data.get(
                "leds_calibrated",
                dict.fromkeys(CH_LIST, 0),
            )
            self.state.wave_min_index = calibration_data.get("wave_min_index", 0)
            self.state.wave_max_index = calibration_data.get("wave_max_index", 0)
            self.state.led_delay = calibration_data.get("led_delay", LED_DELAY)
            self.state.med_filt_win = calibration_data.get("med_filt_win", 11)

            logger.info(f"Calibration profile loaded: {profile_path}")
            return True, "Profile loaded successfully"

        except Exception as e:
            logger.exception(f"Error loading calibration profile: {e}")
            return False, f"Failed to load profile: {e}"

    def list_profiles(self) -> list[str]:
        """Get list of available calibration profile names.

        Returns:
            List of profile names (without .json extension)

        """
        profiles_dir = Path(ROOT_DIR) / "calibration_profiles"
        if not profiles_dir.exists():
            return []
        return [p.stem for p in profiles_dir.glob("*.json")]

    def load_latest_profile(self) -> tuple[bool, str]:
        """Load the most recent calibration profile.

        Returns:
            Tuple of (success: bool, message: str)

        """
        try:
            profiles_dir = Path(ROOT_DIR) / "calibration_profiles"
            if not profiles_dir.exists():
                return False, "No profiles directory found"

            # Find all profile files
            profile_files = list(profiles_dir.glob("*.json"))
            if not profile_files:
                return False, "No calibration profiles found"

            # Sort by modification time (most recent first)
            latest_profile = max(profile_files, key=lambda p: p.stat().st_mtime)
            profile_name = latest_profile.stem

            logger.info(f"Loading latest profile: {profile_name}")
            return self.load_profile(profile_name)

        except Exception as e:
            logger.exception(f"Error loading latest profile: {e}")
            return False, f"Failed to load latest profile: {e}"

    def apply_profile_to_hardware(
        self,
        ctrl: PicoP4SPR | PicoEZSPR,
        usb: USB4000,
        ch_list: list[str] | None = None,
    ) -> bool:
        """Apply loaded calibration profile to hardware.

        Args:
            ctrl: SPR controller instance
            usb: USB4000 spectrometer instance
            ch_list: Channels to apply LED settings to (default: CH_LIST)

        Returns:
            True if applied successfully

        """
        try:
            if ch_list is None:
                ch_list = CH_LIST

            # Apply integration time
            usb.set_integration(self.state.integration)

            # Apply LED intensities
            for ch in ch_list:
                if ch in self.state.leds_calibrated:
                    ctrl.set_intensity(ch=ch, raw_val=self.state.leds_calibrated[ch])

            logger.info("Calibration profile applied to hardware")
            return True

        except Exception as e:
            logger.exception(f"Error applying profile to hardware: {e}")
            return False

    # ========================================================================
    # AUTO-POLARIZATION
    # ========================================================================

    def auto_polarize(
        self,
        ctrl: PicoP4SPR | PicoEZSPR,
        usb: USB4000,
    ) -> tuple[int, int] | None:
        """Automatically find optimal polarizer positions for P and S modes.

        Uses peak detection to find the angles where maximum light transmission
        occurs for both polarization modes.

        Args:
            ctrl: SPR controller instance
            usb: USB4000 spectrometer instance

        Returns:
            Tuple of (s_pos, p_pos) if successful, None if failed

        """
        try:
            from scipy.signal import find_peaks, peak_prominences, peak_widths

            # Set initial conditions
            ctrl.set_intensity("a", 255)
            usb.set_integration(max(MIN_INTEGRATION / 1000.0, usb.min_integration))

            # Define sweep parameters
            min_angle = 10
            max_angle = 170
            half_range = (max_angle - min_angle) // 2
            angle_step = 5
            steps = half_range // angle_step

            # Initialize intensity array
            max_intensities = np.zeros(2 * steps + 1)

            # Set starting position
            ctrl.servo_set(half_range + min_angle, max_angle)
            ctrl.set_mode("p")
            ctrl.set_mode("s")
            max_intensities[steps] = usb.read_intensity().max()

            # Sweep through angles
            for i in range(steps):
                x = min_angle + angle_step * i
                ctrl.servo_set(s=x, p=x + half_range + angle_step)
                ctrl.set_mode("s")
                max_intensities[i] = usb.read_intensity().max()
                ctrl.set_mode("p")
                max_intensities[i + steps + 1] = usb.read_intensity().max()

            # Find peaks and optimal positions
            peaks = find_peaks(max_intensities)[0]
            prominences = peak_prominences(max_intensities, peaks)
            i = prominences[0].argsort()[-2:]
            edges = peak_widths(max_intensities, peaks, 0.05, prominences)[2:4]
            edges = np.array(edges)[:, i]

            # Calculate final positions
            p_pos, s_pos = (min_angle + angle_step * edges.mean(0)).astype(int)
            ctrl.servo_set(s_pos, p_pos)

            logger.info(f"Auto-polarization complete: s={s_pos}, p={p_pos}")
            return s_pos, p_pos

        except Exception as e:
            logger.exception(f"Error during auto-polarization: {e}")
            return None

    # ========================================
    # STATE MACHINE INTERFACE METHODS
    # ========================================

    def start_calibration(self) -> bool:
        """Start calibration process (non-blocking for state machine).

        Returns:
            True if calibration started successfully, False otherwise
        """
        try:
            logger.info("Starting SPR calibration sequence...")
            self._calibration_started = True
            self._calibration_complete = False
            self._calibration_success = False
            self._error_message = ""

            # Start calibration in background
            self._start_background_calibration()
            return True

        except Exception as e:
            logger.exception(f"Failed to start calibration: {e}")
            self._error_message = str(e)
            return False

    def is_complete(self) -> bool:
        """Check if calibration is complete.

        Returns:
            True if calibration has finished (success or failure)
        """
        return getattr(self, '_calibration_complete', False)

    def was_successful(self) -> bool:
        """Check if calibration was successful.

        Returns:
            True if calibration completed successfully
        """
        return getattr(self, '_calibration_success', False)

    def get_error_message(self) -> str:
        """Get error message if calibration failed.

        Returns:
            Error message string, empty if no error
        """
        return getattr(self, '_error_message', "")

    def stop(self) -> None:
        """Stop calibration process."""
        if self.stop_flag:
            self.stop_flag.set()
        self._calibration_complete = True
        self._calibration_success = False

    def _start_background_calibration(self) -> None:
        """Start calibration in background (simulated async for now)."""
        try:
            # For now, run synchronously but set completion flags properly
            # In a full implementation, this would be truly asynchronous

            # Run the full calibration (no extra parameters needed)
            success, error_channels = self.run_full_calibration()

            self._calibration_success = success
            self._error_message = error_channels if not success else ""
            self._calibration_complete = True

            if success:
                logger.info("Calibration completed successfully")
            else:
                logger.error(f"Calibration failed: {error_channels}")

        except Exception as e:
            logger.exception(f"Background calibration error: {e}")
            self._calibration_success = False
            self._error_message = str(e)
            self._calibration_complete = True
