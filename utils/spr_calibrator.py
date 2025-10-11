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

from utils.detector_manager import get_detector_manager, get_current_detector_profile, DetectorProfile
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


def calculate_target_intensity(target_percent: float = TARGET_INTENSITY_PERCENT, 
                                detector_max_counts: int = DETECTOR_MAX_COUNTS) -> int:
    """Calculate target intensity from percentage using detector-specific max.

    Args:
        target_percent: Target as percentage of detector max (0-100)
        detector_max_counts: Detector-specific maximum counts (from profile)

    Returns:
        Target intensity in counts
    """
    return int(detector_max_counts * target_percent / 100.0)


def calculate_intensity_tolerance(target_percent: float = TARGET_INTENSITY_PERCENT,
                                   detector_max_counts: int = DETECTOR_MAX_COUNTS) -> int:
    """Calculate acceptable tolerance around target (±5% of detector max).

    Args:
        target_percent: Target as percentage
        detector_max_counts: Detector-specific maximum counts (from profile)

    Returns:
        Tolerance in counts
    """
    return int(detector_max_counts * 0.05)  # ±5% of max


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


class LEDResponseModel:
    """Models LED intensity vs detector counts relationship.

    Characterizes each LED's response curve using a few calibration points,
    then predicts optimal LED intensity for any target count value.
    This avoids iterative LED calibration and speeds up the process.

    The model assumes a linear relationship: counts = slope * led_intensity + offset
    (with potential saturation handling at high LED values)

    **Hardware Specification:**
    LEDs used in the system: Luminous Device MP-2016-1100-30-80
    - Part Number: MP-2016-1100-30-80
    - Manufacturer: Luminous Device
    - Type: High-power LED for spectroscopy applications
    - Wavelength: System uses 4 channels (A, B, C, D) at different wavelengths
    - LED intensity range: 20-255 (8-bit PWM control)
    - Minimum usable: 20 (below this, response may be non-linear)
    - Maximum: 255 (full power)

    This characterization allows the system to:
    1. Predict counts for any LED intensity without measuring
    2. Predict required LED intensity to achieve target counts
    3. Detect potential saturation before actually setting LEDs
    4. Speed up calibration by avoiding iterative searches
    """

    def __init__(self):
        """Initialize empty LED response models for all channels."""
        self.models: dict[str, dict] = {}  # {channel: {slope, offset, led_range, valid}}

    def characterize_led(
        self,
        channel: str,
        led_intensities: list[int],
        measured_counts: list[int],
    ) -> bool:
        """Characterize LED response using calibration measurements.

        Args:
            channel: Channel name ('a', 'b', 'c', 'd')
            led_intensities: List of LED values tested (e.g., [20, 128, 255])
            measured_counts: Corresponding detector counts

        Returns:
            True if characterization successful, False otherwise
        """
        if len(led_intensities) < 2 or len(led_intensities) != len(measured_counts):
            logger.error(f"Channel {channel}: Need at least 2 LED/count pairs")
            return False

        # Filter out saturated measurements (counts >= 65000)
        valid_pairs = [
            (led, count)
            for led, count in zip(led_intensities, measured_counts)
            if count < 65000
        ]

        if len(valid_pairs) < 2:
            logger.warning(f"Channel {channel}: All measurements saturated")
            # Use all data anyway for a rough estimate
            valid_pairs = list(zip(led_intensities, measured_counts))

        leds = np.array([p[0] for p in valid_pairs])
        counts = np.array([p[1] for p in valid_pairs])

        # Linear regression: counts = slope * led + offset
        # Using numpy polyfit for robustness
        coeffs = np.polyfit(leds, counts, deg=1)
        slope = coeffs[0]
        offset = coeffs[1]

        # Calculate R² to assess fit quality
        predicted = slope * leds + offset
        ss_res = np.sum((counts - predicted) ** 2)
        ss_tot = np.sum((counts - np.mean(counts)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        self.models[channel] = {
            'slope': float(slope),
            'offset': float(offset),
            'led_range': (int(leds.min()), int(leds.max())),
            'count_range': (int(counts.min()), int(counts.max())),
            'r_squared': float(r_squared),
            'valid': r_squared > 0.8,  # Only trust if good fit
            'calibration_points': len(valid_pairs),
        }

        logger.info(
            f"📊 Channel {channel} LED model: "
            f"counts = {slope:.1f}*LED + {offset:.1f} "
            f"(R²={r_squared:.3f})"
        )

        return self.models[channel]['valid']

    def predict_led_for_target(
        self,
        channel: str,
        target_counts: int,
        led_min: int = 20,
        led_max: int = 255,
    ) -> Optional[int]:
        """Predict LED intensity needed to achieve target counts.

        Args:
            channel: Channel name
            target_counts: Desired detector counts
            led_min: Minimum allowed LED intensity
            led_max: Maximum allowed LED intensity

        Returns:
            Predicted LED intensity, or None if model invalid
        """
        if channel not in self.models or not self.models[channel]['valid']:
            logger.warning(f"Channel {channel}: No valid LED model available")
            return None

        model = self.models[channel]
        slope = model['slope']
        offset = model['offset']

        # Solve: target_counts = slope * led + offset
        # led = (target_counts - offset) / slope
        if abs(slope) < 0.1:  # Nearly flat response - LED has minimal effect
            logger.warning(f"Channel {channel}: LED has minimal effect (slope={slope:.1f})")
            return None

        predicted_led = (target_counts - offset) / slope

        # Clamp to valid range
        predicted_led = max(led_min, min(led_max, predicted_led))

        # Round to nearest integer
        predicted_led = int(round(predicted_led))

        logger.debug(
            f"Channel {channel}: Target {target_counts} counts "
            f"→ LED={predicted_led} (model: {slope:.1f}*LED + {offset:.1f})"
        )

        return predicted_led

    def predict_counts_for_led(
        self,
        channel: str,
        led_intensity: int,
    ) -> Optional[int]:
        """Predict detector counts for a given LED intensity.

        Args:
            channel: Channel name
            led_intensity: LED intensity value

        Returns:
            Predicted counts, or None if model invalid
        """
        if channel not in self.models or not self.models[channel]['valid']:
            return None

        model = self.models[channel]
        predicted_counts = model['slope'] * led_intensity + model['offset']

        return int(round(predicted_counts))

    def is_valid(self, channel: str) -> bool:
        """Check if a valid LED model exists for a channel.

        Args:
            channel: Channel name ('a', 'b', 'c', 'd')

        Returns:
            True if channel has a valid LED model (R² > 0.8), False otherwise
        """
        return channel in self.models and self.models[channel].get('valid', False)

    def to_dict(self) -> dict:
        """Export models to dictionary for serialization.

        Converts all numpy types to Python native types for JSON serialization.
        """
        # Deep copy and convert numpy types to Python native types
        json_models = {}
        for channel, model in self.models.items():
            json_models[channel] = {
                'slope': float(model['slope']),
                'offset': float(model['offset']),
                'led_range': [int(model['led_range'][0]), int(model['led_range'][1])],
                'count_range': [int(model['count_range'][0]), int(model['count_range'][1])],
                'r_squared': float(model['r_squared']),
                'valid': bool(model['valid']),
                'calibration_points': int(model['calibration_points']),
            }
        return {'led_response_models': json_models}

    def from_dict(self, data: dict) -> bool:
        """Load models from dictionary.

        Args:
            data: Dictionary containing 'led_response_models' key

        Returns:
            True if loaded successfully
        """
        if 'led_response_models' in data:
            self.models = data['led_response_models']
            logger.info(f"✅ Loaded LED response models for {len(self.models)} channels")
            return True
        return False


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

        # Initialize LED response model for predictive calibration
        self.led_model = LEDResponseModel()
        logger.debug("LED response model initialized")

        # Initialize detector profile (will be loaded during calibration)
        self.detector_profile: Optional[DetectorProfile] = None
        self.detector_manager = get_detector_manager()
        logger.debug("Detector manager initialized")

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

    def _apply_spectral_filter(self, raw_spectrum: np.ndarray) -> np.ndarray:
        """Apply spectral range filter to raw detector data.

        Filters raw intensity data to only include the SPR-relevant wavelength range
        (580-720 nm by default). This eliminates detector noise and LED artifacts
        at extreme wavelengths, improving peak detection accuracy.

        Args:
            raw_spectrum: Full spectrum from detector (typically 3648 pixels, 441-773 nm)

        Returns:
            Filtered spectrum containing only SPR-relevant wavelengths (~1000 pixels, 580-720 nm)
            Returns original spectrum if mask not available or size mismatch occurs.

        Example:
            raw = self.usb.read_intensity()  # 3648 pixels
            filtered = self._apply_spectral_filter(raw)  # ~1000 pixels (580-720 nm)
        """
        # Check if wavelength mask is available
        if not hasattr(self.state, 'wavelength_mask'):
            logger.warning("⚠️ Wavelength mask not initialized - returning full spectrum")
            logger.warning("   Run wavelength calibration first to initialize spectral filtering")
            return raw_spectrum

        # Handle size mismatch by recreating mask (USB4000 sometimes returns 3647 or 3648 pixels)
        if len(raw_spectrum) != len(self.state.wavelength_mask):
            logger.debug(
                f"Spectrum size changed: {len(raw_spectrum)} pixels (was {len(self.state.wavelength_mask)})"
            )

            # Get current wavelengths matching the spectrum size
            try:
                current_wavelengths = None
                if hasattr(self.usb, "read_wavelength"):
                    current_wavelengths = self.usb.read_wavelength()
                elif hasattr(self.usb, "get_wavelengths"):
                    wl = self.usb.get_wavelengths()
                    if wl is not None:
                        current_wavelengths = np.array(wl)

                if current_wavelengths is None:
                    logger.warning("   Cannot get wavelengths - returning unfiltered spectrum")
                    return raw_spectrum

                if len(current_wavelengths) != len(raw_spectrum):
                    logger.debug(f"   Wavelength size mismatch - trimming to match spectrum")
                    current_wavelengths = current_wavelengths[:len(raw_spectrum)]

                # Recreate mask for current size
                new_mask = (current_wavelengths >= MIN_WAVELENGTH) & (current_wavelengths <= MAX_WAVELENGTH)
                logger.debug(f"   Recreated wavelength mask: {np.sum(new_mask)} pixels in {MIN_WAVELENGTH}-{MAX_WAVELENGTH} nm")
                return raw_spectrum[new_mask]

            except Exception as e:
                logger.warning(f"   Could not recreate mask: {e} - returning unfiltered spectrum")
                return raw_spectrum

        # Apply spectral filter
        filtered_spectrum = raw_spectrum[self.state.wavelength_mask]
        logger.debug(
            f"Spectral filter applied: {len(raw_spectrum)} → {len(filtered_spectrum)} pixels"
        )

        return filtered_spectrum

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

            # Spectral range filtering - only keep SPR-relevant wavelengths (580-720 nm)
            if len(wave_data) < 2:
                logger.error("Insufficient wavelength data")
                return False, integration_step

            # Log full detector range
            logger.info(
                f"📊 Full detector range: {wave_data[0]:.1f} - {wave_data[-1]:.1f} nm ({len(wave_data)} pixels)"
            )

            # Get SPR wavelength range from detector profile (or fall back to settings)
            if self.detector_profile:
                min_wavelength = self.detector_profile.spr_wavelength_min_nm
                max_wavelength = self.detector_profile.spr_wavelength_max_nm
                logger.info(f"Using detector profile SPR range: {min_wavelength}-{max_wavelength} nm")
            else:
                min_wavelength = MIN_WAVELENGTH
                max_wavelength = MAX_WAVELENGTH
                logger.warning("Using legacy wavelength range from settings.py")

            # Create wavelength mask for SPR-relevant range
            wavelength_mask = (wave_data >= min_wavelength) & (wave_data <= max_wavelength)
            filtered_wave_data = wave_data[wavelength_mask]

            if len(filtered_wave_data) < 10:
                logger.error(f"Insufficient pixels in SPR range ({min_wavelength}-{max_wavelength} nm)")
                return False, integration_step

            # Store wavelength filtering configuration (cleaner architecture)
            # Instead of indices, store the actual wavelength boundaries
            self.state.wavelength_min = min_wavelength
            self.state.wavelength_max = max_wavelength

            # Store the filtered wavelength array (what we actually work with)
            self.state.wave_data = filtered_wave_data.copy()
            self.state.wavelengths = filtered_wave_data.copy()

            # Store the mask for current spectrum size
            self.state.wavelength_mask = wavelength_mask

            # Store full detector wavelengths for dynamic mask recreation
            self.state.full_wavelengths = wave_data.copy()
            self.state.expected_raw_size = len(wave_data)

            # DEPRECATED (kept for backward compatibility, but confusing!)
            # These are indices into the FILTERED array (always 0 to len-1)
            self.state.wave_min_index = 0  # Always 0 for filtered data
            self.state.wave_max_index = len(filtered_wave_data) - 1

            logger.info(
                f"✅ SPECTRAL FILTERING APPLIED: {MIN_WAVELENGTH}-{MAX_WAVELENGTH} nm"
            )
            logger.info(
                f"   Filtered range: {filtered_wave_data[0]:.1f} - {filtered_wave_data[-1]:.1f} nm"
            )
            logger.info(
                f"   Pixels used: {len(filtered_wave_data)} (was {len(wave_data)})"
            )
            logger.info(
                f"   Resolution: {(filtered_wave_data[-1] - filtered_wave_data[0]) / len(filtered_wave_data):.3f} nm/pixel"
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

            # Get integration time limits from detector profile (or fall back to settings)
            if self.detector_profile:
                min_int = self.detector_profile.min_integration_time_ms / 1000.0  # Convert ms to seconds
                max_int = self.detector_profile.max_integration_time_ms / 1000.0  # Convert ms to seconds (200 ms for Flame-T!)
                logger.info(f"Using detector profile integration limits: {self.detector_profile.min_integration_time_ms}-{self.detector_profile.max_integration_time_ms} ms")
            else:
                min_int = MIN_INTEGRATION / 1000.0  # Convert ms to seconds
                max_int = MAX_INTEGRATION / 1000.0  # Convert ms to seconds
                logger.warning("Using legacy integration limits from settings.py")

            # Set minimum integration time
            self.state.integration = min_int
            self.usb.set_integration(self.state.integration)
            time.sleep(0.1)

            # ========================================================================
            # STEP 1: Identify weakest channel (test all at standard LED intensity)
            # ========================================================================
            logger.info("📊 Step 3.1: Identifying weakest channel...")

            channel_intensities = {}
            for ch in ch_list:
                if self._is_stopped():
                    return False

                self.ctrl.set_intensity(ch=ch, raw_val=S_LED_INT)
                time.sleep(LED_DELAY)

                raw_array = self.usb.read_intensity()
                if raw_array is None:
                    logger.error(f"Failed to read intensity for channel {ch}")
                    continue

                # Apply spectral filter for channel intensity measurement
                filtered_array = self._apply_spectral_filter(raw_array)
                current_count = filtered_array.max()

                channel_intensities[ch] = current_count
                logger.debug(f"Channel {ch} initial intensity: {current_count:.0f} counts")

            # Find weakest channel
            weakest_ch = min(channel_intensities, key=channel_intensities.get)

            logger.info(f"✅ Weakest channel identified: {weakest_ch} ({channel_intensities[weakest_ch]:.0f} counts at LED={S_LED_INT})")

            # Turn off all channels
            self.ctrl.turn_off_channels()
            time.sleep(LED_DELAY)

            # ========================================================================
            # STEP 2: Maximize integration time for WEAKEST channel at MAXIMUM LED
            # ========================================================================
            logger.info(f"📊 Step 3.2: Maximizing integration time for weakest channel ({weakest_ch})...")
            logger.info(f"   Strategy: Set weakest LED to MAXIMUM (255), increase integration time as high as possible")

            # CRITICAL: Set weakest channel to MAXIMUM LED intensity
            # This ensures we give it every advantage before fixing integration time
            MAX_LED = 255
            self.ctrl.set_intensity(ch=weakest_ch, raw_val=MAX_LED)
            time.sleep(LED_DELAY)

            # Increase integration time until weakest channel reaches target OR we hit max integration
            raw_array = self.usb.read_intensity()
            if raw_array is not None:
                # Apply spectral filter for integration time optimization
                filtered_array = self._apply_spectral_filter(raw_array)
                current_count = filtered_array.max()

                logger.info(f"   Starting: {self.state.integration * 1000:.1f}ms, weakest@LED=255: {current_count:.0f} counts")
            else:
                current_count = 0
                logger.error("Failed to read intensity for integration time calibration")

            # Get detector-specific max counts for target calculation
            if self.detector_profile:
                detector_max = self.detector_profile.max_intensity_counts
            else:
                detector_max = DETECTOR_MAX_COUNTS
            
            # Target: 80% of detector-specific max
            S_COUNT_TARGET = int(TARGET_INTENSITY_PERCENT / 100 * detector_max)

            # Increase integration time until target reached or max integration hit
            while current_count < S_COUNT_TARGET and self.state.integration < max_int:
                self.state.integration += (
                    integration_step / 1000.0
                )  # Convert ms to seconds

                self.usb.set_integration(self.state.integration)
                time.sleep(0.02)

                raw_array = self.usb.read_intensity()
                if raw_array is None:
                    break

                # Apply spectral filter to intensity reads during integration optimization
                filtered_array = self._apply_spectral_filter(raw_array)
                current_count = filtered_array.max()

                if current_count >= S_COUNT_TARGET:
                    logger.info(
                        f"   ✅ Target reached at {self.state.integration * 1000:.1f}ms: "
                        f"weakest@LED=255: {current_count:.0f} counts ({current_count/detector_max*100:.1f}%)"
                    )
                    break

                # Log progress every 10ms
                if int(self.state.integration * 1000) % 10 == 0:
                    logger.debug(
                        f"   {self.state.integration * 1000:.1f}ms: "
                        f"weakest@LED=255: {current_count:.0f} counts ({current_count/detector_max*100:.1f}%)"
                    )

            if current_count < S_COUNT_TARGET:
                logger.warning(
                    f"⚠️ Weakest channel could not reach target even at LED=255 and {self.state.integration * 1000:.1f}ms"
                )
                logger.warning(
                    f"   Achieved: {current_count:.0f} counts ({current_count/detector_max*100:.1f}% of max)"
                )
                logger.warning(
                    f"   This integration time ({self.state.integration * 1000:.1f}ms) will be used for all channels"
                )

            # Turn off weakest channel
            self.ctrl.set_intensity(ch=weakest_ch, raw_val=0)
            time.sleep(LED_DELAY)

            integration_ms = self.state.integration * 1000
            logger.info(f"✅ Integration time optimized at: {integration_ms:.1f}ms")
            logger.info(f"   Now checking if other channels can handle this integration time...")

            # ========================================================================
            # STEP 3.3: Check for saturation by testing at low LED intensity
            # ========================================================================
            logger.info(f"📊 Step 3.3: Checking for saturation at {integration_ms:.1f}ms")

            # Get detector-specific max for saturation threshold (91% of max)
            if self.detector_profile:
                detector_max = self.detector_profile.max_intensity_counts
            else:
                detector_max = DETECTOR_MAX_COUNTS
            
            SATURATION_THRESHOLD = int(detector_max * 0.91)  # 91% of detector-specific max
            LOW_LED_TEST = 50  # LED intensity to test for saturation check
            needs_reduction = False

            # Test each channel at low LED intensity to check for saturation
            for ch in ch_list:
                if self._is_stopped():
                    return False

                # Set channel to low LED intensity
                self.ctrl.set_intensity(ch=ch, raw_val=LOW_LED_TEST)
                time.sleep(LED_DELAY)

                # Measure intensity
                int_array = self.usb.read_intensity()
                if int_array is not None:
                    # Apply spectral filter using wavelength boundaries
                    wavelengths = self.usb.get_wavelengths()[:len(int_array)]
                    mask = (wavelengths >= MIN_WAVELENGTH) & (wavelengths <= MAX_WAVELENGTH)
                    filtered_array = int_array[mask]
                    counts = filtered_array.max()
                    counts_percent = (counts / detector_max) * 100

                    logger.debug(f"   Channel {ch} @ LED={LOW_LED_TEST}: {counts:.0f} counts ({counts_percent:.1f}%)")

                    if counts > SATURATION_THRESHOLD:
                        logger.warning(
                            f"⚠️ Channel {ch} saturating at {integration_ms:.1f}ms: "
                            f"{counts:.0f} counts ({counts_percent:.1f}%) at LED={LOW_LED_TEST}"
                        )
                        needs_reduction = True

            # Turn off all channels
            self.ctrl.turn_off_channels()
            time.sleep(LED_DELAY)

            # Reduce integration time if saturation detected
            if needs_reduction:
                logger.warning(f"⚠️ Some channels saturate at {integration_ms:.1f}ms - reducing integration time")

                # Reduce integration time iteratively until no saturation
                reduction_step = 0.005  # 5ms steps
                max_reductions = 10
                reductions = 0

                while needs_reduction and reductions < max_reductions and self.state.integration > min_int:
                    # Reduce integration time
                    self.state.integration -= reduction_step
                    self.usb.set_integration(self.state.integration)
                    time.sleep(0.02)

                    # Test all channels again
                    needs_reduction = False
                    for ch in ch_list:
                        self.ctrl.set_intensity(ch=ch, raw_val=LOW_LED_TEST)
                        time.sleep(LED_DELAY)

                        int_array = self.usb.read_intensity()
                        if int_array is not None:
                            # Apply spectral filter using wavelength boundaries
                            wavelengths = self.usb.get_wavelengths()[:len(int_array)]
                            mask = (wavelengths >= MIN_WAVELENGTH) & (wavelengths <= MAX_WAVELENGTH)
                            filtered_array = int_array[mask]
                            counts = filtered_array.max()

                            if counts > SATURATION_THRESHOLD:
                                needs_reduction = True
                                break

                    # Turn off all channels
                    self.ctrl.turn_off_channels()
                    time.sleep(LED_DELAY)

                    reductions += 1

                    if not needs_reduction:
                        integration_ms = self.state.integration * 1000
                        logger.info(
                            f"✅ Integration time reduced to {integration_ms:.1f}ms - no saturation detected"
                        )
                        break

                if needs_reduction:
                    logger.error(
                        f"❌ Could not eliminate saturation even after reducing to {integration_ms:.1f}ms"
                    )
                    logger.error(f"   Proceeding anyway - LED calibration will need to use very low intensities")
            else:
                logger.info(f"✅ No saturation detected at {integration_ms:.1f}ms - integration time is safe")

            integration_ms = self.state.integration * 1000
            logger.info(f"✅ FINAL integration time FIXED at: {integration_ms:.1f}ms")
            logger.info(f"   (This integration time will be used for ALL channels)")
            logger.info(f"   (Next step: adjust LED intensities to balance channels within 10% of weakest)")

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

        This method starts directly at LED=128 and iteratively adjusts to reach
        the target intensity using adaptive step sizes for fast convergence.

        Args:
            ch: Channel identifier ('a', 'b', 'c', or 'd')

        Returns:
            True if successful, False otherwise

        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            logger.debug(f"Starting adaptive LED calibration for channel {ch}")

            # Get detector-specific max counts (or fallback to hardcoded value)
            if self.detector_profile:
                detector_max = self.detector_profile.max_intensity_counts
                logger.debug(f"Using detector-specific max: {detector_max} counts")
            else:
                detector_max = DETECTOR_MAX_COUNTS
                logger.warning(f"No detector profile, using default max: {detector_max} counts")

            # Initialize percentage-based calibration parameters using detector-specific max
            target_intensity = calculate_target_intensity(TARGET_INTENSITY_PERCENT, detector_max)
            tolerance = calculate_intensity_tolerance(TARGET_INTENSITY_PERCENT, detector_max)
            max_iterations = ADAPTIVE_MAX_ITERATIONS
            convergence_factor = ADAPTIVE_CONVERGENCE_FACTOR

            # Get target wavelength range indices
            wave_data = self.state.wavelengths
            target_min_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MIN))
            target_max_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MAX))

            logger.info(
                f"📊 S-mode target: {TARGET_INTENSITY_PERCENT}% of {detector_max} = {target_intensity:.0f} counts "
                f"in {TARGET_WAVELENGTH_MIN}-{TARGET_WAVELENGTH_MAX}nm range"
            )

            # ========================================================================
            # DIRECT ADAPTIVE OPTIMIZATION - Start at LED=128
            # ========================================================================
            logger.info(f"📊 Starting adaptive optimization for {ch} from LED=128")

            current_led = 128
            best_led = current_led
            best_error = float("inf")

            for iteration in range(max_iterations):
                if self._is_stopped():
                    return False

                # Set LED intensity and allow stabilization
                self.ctrl.set_intensity(ch=ch, raw_val=current_led)
                time.sleep(ADAPTIVE_STABILIZATION_DELAY)

                # Measure current intensity in TARGET WAVELENGTH RANGE
                raw_spectrum = self.usb.read_intensity()
                if raw_spectrum is None:
                    logger.error(f"Failed to read spectrum for channel {ch} iteration {iteration}")
                    break

                # Apply spectral filter for adaptive calibration
                spectrum = self._apply_spectral_filter(raw_spectrum)
                signal_region = spectrum[target_min_idx:target_max_idx]
                measured_intensity = signal_region.max()
                measured_percent = (measured_intensity / detector_max) * 100

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

            # Measure dark noise - apply spectral filter to measure only SPR-relevant range
            try:
                test_spectrum = self.usb.read_intensity()
                if test_spectrum is None or len(test_spectrum) == 0:
                    logger.error("Cannot determine spectrum length for dark noise measurement")
                    return False

                # Apply spectral filter to test spectrum
                filtered_test = self._apply_spectral_filter(test_spectrum)
                filtered_spectrum_length = len(filtered_test)
                logger.info(f"Dark noise measurement: {len(test_spectrum)} → {filtered_spectrum_length} pixels (spectral filter applied)")
            except Exception as e:
                logger.error(f"Failed to read test spectrum for dark noise: {e}")
                return False

            dark_noise_sum = np.zeros(filtered_spectrum_length)

            for _scan in range(dark_scans):
                if self._is_stopped():
                    return False

                raw_intensity = self.usb.read_intensity()
                if raw_intensity is None:
                    logger.error("Failed to read intensity for dark noise")
                    return False

                # Apply spectral filter to each dark noise measurement
                filtered_intensity = self._apply_spectral_filter(raw_intensity)
                dark_noise_sum += filtered_intensity

            # Store dark noise (already filtered to SPR range)
            full_spectrum_dark_noise = dark_noise_sum / dark_scans

            # Store dark noise (already filtered to SPR-relevant range at acquisition)
            # No resampling needed - spectral filter ensures correct size
            self.state.dark_noise = full_spectrum_dark_noise
            self.state.full_spectrum_dark_noise = full_spectrum_dark_noise

            logger.info(
                f"✅ Dark noise measurement complete:"
                f"\n  • Spectrum size: {len(full_spectrum_dark_noise)} pixels (filtered to SPR range)"
                f"\n  • Max dark noise: {np.max(full_spectrum_dark_noise):.1f} counts"
                f"\n  • Mean dark noise: {np.mean(full_spectrum_dark_noise):.1f} counts"
                f"\n  • Method: Direct filtering at acquisition (no resampling needed)"
            )
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

                    raw_val = self.usb.read_intensity()
                    if raw_val is None:
                        logger.error(f"Failed to read intensity for channel {ch}")
                        return False

                    # Apply spectral filter to reference signal measurement
                    filtered_val = self._apply_spectral_filter(raw_val)

                    # Subtract dark noise (already filtered to same range)
                    ref_data_single = filtered_val - self.state.dark_noise
                    ref_data_sum += ref_data_single

                self.state.ref_sig[ch] = deepcopy(ref_data_sum / ref_scans)

                # Log reference signal strength
                ref_array = self.state.ref_sig[ch]
                if ref_array is not None:
                    logger.debug(
                        f"Channel {ch} reference signal: max={float(np.max(ref_array)):.1f} counts",
                    )
                else:
                    logger.warning(f"Channel {ch} reference signal is None")

            return True

        except Exception as e:
            logger.exception(f"Error measuring reference signals: {e}")
            return False

    # ========================================================================
    # STEP 8: LED INTENSITY CALIBRATION (P-MODE)
    # ========================================================================

    def calibrate_led_p_mode_s_based(self, ch_list: list[str]) -> bool:
        """S-mode based P-mode calibration with integration time adjustment.

        NEW STRATEGY (recommended by user):
        1. Use S-mode LED intensities (from ref_intensity) to maintain relative intensity profile
        2. Measure P-mode spectra with those same LED ratios
        3. Adjust integration time to bring P-mode max within 10% of S-mode max

        This ensures:
        - Relative intensity profile is preserved between S and P modes
        - P-mode signal strength matches S-mode for cleaner transmittance ratio
        - No iterative LED adjustments needed - just integration time tuning

        Args:
            ch_list: List of channels to calibrate

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            logger.info("=" * 70)
            logger.info("🔬 P-MODE CALIBRATION: S-mode Profile Preservation Strategy")
            logger.info("=" * 70)

            # Step 1: Calculate S-mode reference max intensity
            logger.info("📊 Step 1: Analyzing S-mode reference signals...")
            s_mode_max_counts = {}
            s_mode_led_values = {}

            for ch in ch_list:
                if ch in self.state.ref_sig and self.state.ref_sig[ch] is not None:
                    s_mode_max_counts[ch] = float(self.state.ref_sig[ch].max())
                    s_mode_led_values[ch] = self.state.ref_intensity[ch]
                    logger.info(
                        f"  • Channel {ch}: LED={s_mode_led_values[ch]}, "
                        f"max={s_mode_max_counts[ch]:.0f} counts"
                    )

            if not s_mode_max_counts:
                logger.error("❌ No S-mode reference signals available!")
                return False

            # Find the overall max across all channels
            overall_s_mode_max = max(s_mode_max_counts.values())
            logger.info(f"✅ S-mode overall max: {overall_s_mode_max:.0f} counts")

            # Step 2: Set P-mode LEDs to SAME values as S-mode (preserve relative profile)
            logger.info("📊 Step 2: Setting P-mode LEDs to match S-mode profile...")
            self.ctrl.set_mode(mode="p")
            time.sleep(0.4)

            for ch in ch_list:
                led_value = s_mode_led_values[ch]
                self.ctrl.set_intensity(ch=ch, raw_val=led_value)
                logger.info(f"  • Channel {ch}: LED={led_value} (same as S-mode)")

            time.sleep(LED_DELAY)

            # Step 3: Measure P-mode intensities with current integration time
            logger.info("📊 Step 3: Measuring P-mode with S-mode integration time...")
            p_mode_max_counts = {}

            for ch in ch_list:
                if self._is_stopped():
                    return False

                self.ctrl.set_intensity(ch=ch, raw_val=s_mode_led_values[ch])
                time.sleep(LED_DELAY)

                raw_spectrum = self.usb.read_intensity()
                if raw_spectrum is not None:
                    # Apply spectral filter to P-mode measurement
                    spectrum = self._apply_spectral_filter(raw_spectrum)
                    p_mode_max_counts[ch] = float(spectrum.max())
                    logger.info(
                        f"  • Channel {ch}: max={p_mode_max_counts[ch]:.0f} counts "
                        f"(S-mode was {s_mode_max_counts[ch]:.0f})"
                    )

            overall_p_mode_max = max(p_mode_max_counts.values())
            initial_ratio = (overall_p_mode_max / overall_s_mode_max) * 100
            logger.info(
                f"✅ P-mode overall max: {overall_p_mode_max:.0f} counts "
                f"({initial_ratio:.1f}% of S-mode)"
            )

            # Step 4: Adjust integration time to bring P-mode within 10% of S-mode
            target_p_mode_max = overall_s_mode_max  # Target: same as S-mode
            tolerance = overall_s_mode_max * 0.10  # 10% tolerance

            logger.info("📊 Step 4: Adjusting integration time to match S-mode intensity...")
            logger.info(
                f"  • Target: {target_p_mode_max:.0f} counts ±10% "
                f"({target_p_mode_max - tolerance:.0f} to {target_p_mode_max + tolerance:.0f})"
            )

            current_integration = self.state.integration  # in seconds
            max_iterations = 10

            for iteration in range(max_iterations):
                if self._is_stopped():
                    return False

                # Check if we're within tolerance
                if abs(overall_p_mode_max - target_p_mode_max) <= tolerance:
                    logger.info(
                        f"✅ P-mode intensity matched S-mode in {iteration} iterations! "
                        f"({overall_p_mode_max:.0f} counts, {(overall_p_mode_max/overall_s_mode_max)*100:.1f}% of S-mode)"
                    )
                    break

                # Calculate required integration time adjustment
                # P_counts / S_counts = P_integration / S_integration (assuming linear response)
                ratio = overall_p_mode_max / target_p_mode_max
                new_integration = current_integration / ratio

                # Clamp to reasonable limits
                min_integration = MIN_INTEGRATION / 1000.0  # 1ms
                max_integration = MAX_INTEGRATION / 1000.0  # 100ms
                new_integration = max(min_integration, min(max_integration, new_integration))

                logger.info(
                    f"  Iter {iteration + 1}: current={current_integration*1000:.1f}ms, "
                    f"P-mode={overall_p_mode_max:.0f}, ratio={ratio:.3f}, "
                    f"new={new_integration*1000:.1f}ms"
                )

                # Apply new integration time
                self.usb.set_integration(new_integration)
                self.state.integration = new_integration
                current_integration = new_integration
                time.sleep(0.2)  # Allow hardware to stabilize

                # Re-measure all channels with new integration time
                p_mode_max_counts = {}
                for ch in ch_list:
                    if self._is_stopped():
                        return False

                    self.ctrl.set_intensity(ch=ch, raw_val=s_mode_led_values[ch])
                    time.sleep(LED_DELAY)

                    raw_spectrum = self.usb.read_intensity()
                    if raw_spectrum is not None:
                        # Apply spectral filter to P-mode re-measurement
                        spectrum = self._apply_spectral_filter(raw_spectrum)
                        p_mode_max_counts[ch] = float(spectrum.max())

                overall_p_mode_max = max(p_mode_max_counts.values())

                # Check for saturation using detector-specific max
                if self.detector_profile:
                    detector_max = self.detector_profile.max_intensity_counts
                else:
                    detector_max = DETECTOR_MAX_COUNTS
                
                if overall_p_mode_max > detector_max * 0.95:
                    logger.warning(
                        f"⚠️ Approaching saturation ({overall_p_mode_max:.0f} counts), "
                        f"stopping adjustment"
                    )
                    break

                # Prevent oscillation - if change is too small, stop
                if iteration > 2 and abs(overall_p_mode_max - target_p_mode_max) / target_p_mode_max < 0.02:
                    logger.info(
                        f"✅ P-mode intensity stable within 2% "
                        f"({overall_p_mode_max:.0f} counts, {(overall_p_mode_max/overall_s_mode_max)*100:.1f}% of S-mode)"
                    )
                    break

            # Step 5: Store final P-mode LED values (same as S-mode)
            logger.info("📊 Step 5: Storing P-mode calibration results...")
            for ch in ch_list:
                self.state.leds_calibrated[ch] = s_mode_led_values[ch]
                logger.info(
                    f"  • Channel {ch}: LED={self.state.leds_calibrated[ch]} "
                    f"(P-mode max={p_mode_max_counts[ch]:.0f} counts)"
                )

            # Final summary
            final_ratio = (overall_p_mode_max / overall_s_mode_max) * 100
            logger.info("=" * 70)
            logger.info("✅ P-MODE CALIBRATION COMPLETE")
            logger.info(f"  • Integration time: {self.state.integration*1000:.1f}ms")
            logger.info(f"  • S-mode max: {overall_s_mode_max:.0f} counts")
            logger.info(f"  • P-mode max: {overall_p_mode_max:.0f} counts ({final_ratio:.1f}% of S-mode)")
            logger.info(f"  • Relative profile: PRESERVED (same LED ratios)")
            logger.info("=" * 70)

            return True

        except Exception as e:
            logger.exception(f"Error in S-based P-mode calibration: {e}")
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

                # Get detector-specific max for percentage calculations
                if self.detector_profile:
                    detector_max = self.detector_profile.max_intensity_counts
                else:
                    detector_max = DETECTOR_MAX_COUNTS

                # Just log measurements, don't validate
                for ch in CH_LIST:
                    if self._is_stopped():
                        break

                    intensity = self.state.leds_calibrated[ch]
                    self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                    time.sleep(LED_DELAY)

                    spectrum = self.usb.read_intensity()
                    max_intensity = spectrum.max()
                    max_percent = (max_intensity / detector_max) * 100

                    # Find target range
                    wave_data = self.state.wavelengths
                    target_min_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MIN))
                    target_max_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MAX))
                    target_max = spectrum[target_min_idx:target_max_idx].max()
                    target_percent = (target_max / detector_max) * 100

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
            # Get detector-specific max for threshold calculations
            if self.detector_profile:
                detector_max = self.detector_profile.max_intensity_counts
            else:
                detector_max = DETECTOR_MAX_COUNTS
            
            self.state.ch_error_list = []
            wave_data = self.state.wavelengths
            target_min_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MIN))
            target_max_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MAX))

            min_threshold = detector_max * MIN_INTENSITY_PERCENT / 100.0
            max_threshold = detector_max * MAX_INTENSITY_PERCENT / 100.0

            for ch in CH_LIST:
                if self._is_stopped():
                    break

                intensity = self.state.leds_calibrated[ch]
                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                time.sleep(LED_DELAY)

                spectrum = self.usb.read_intensity()
                target_max = spectrum[target_min_idx:target_max_idx].max()
                target_percent = (target_max / detector_max) * 100

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
            logger.info("=" * 80)
            logger.info("STEP 0: Loading Detector Profile")
            logger.info("=" * 80)

            # Auto-detect and load detector profile
            self.detector_profile = self.detector_manager.auto_detect(self.usb)

            if self.detector_profile is None:
                logger.error("❌ Failed to load detector profile - using legacy defaults")
                # Will fall back to hardcoded values from settings.py
            else:
                logger.info(f"✅ Detector Profile Loaded:")
                logger.info(f"   Manufacturer: {self.detector_profile.manufacturer}")
                logger.info(f"   Model: {self.detector_profile.model}")
                logger.info(f"   Pixels: {self.detector_profile.pixel_count}")
                logger.info(f"   Wavelength Range: {self.detector_profile.wavelength_min_nm:.1f}-{self.detector_profile.wavelength_max_nm:.1f} nm")
                logger.info(f"   Max Intensity: {self.detector_profile.max_intensity_counts} counts")
                logger.info(f"   Max Integration Time: {self.detector_profile.max_integration_time_ms} ms")
                logger.info(f"   Target Signal: {self.detector_profile.target_signal_counts} ± {self.detector_profile.signal_tolerance_counts} counts")
                logger.info(f"   SPR Range: {self.detector_profile.spr_wavelength_min_nm}-{self.detector_profile.spr_wavelength_max_nm} nm")

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

            # Step 8: LED intensity calibration (P-mode S-based)
            logger.debug("Step 8: LED intensity calibration (P-mode S-based)")
            self._emit_progress(8, "Optimizing P-mode using S-mode profile...")
            success = self.calibrate_led_p_mode_s_based(ch_list)
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
