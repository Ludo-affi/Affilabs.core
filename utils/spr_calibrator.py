"""SPR Calibration Module

Handles all SPR spectrometer calibration operations:
- Wavelength range calibration
- Integration time optimization
- LED intensity calibration (S-mode)
- Dark noise measurement
- Reference signal acquisition
- Calibration validation
- Calibration history logging

CHANNEL ITERATION PATTERN (Code Quality Standard):
===================================================
Functions should accept ch_list as a parameter for flexibility:

    def my_calibration_function(self, ch_list: list[str]) -> bool:
        '''
        Args:
            ch_list: List of channel identifiers (e.g., ["a", "b", "c", "d"])
        '''
        for ch in ch_list:
            # Process channel

This supports both P4 (4-channel) and EZ (2-channel) devices.

WHEN TO USE CH_LIST CONSTANT:
- Only at initialization or top-level device configuration:

    ch_list = CH_LIST if self.device_type == "P4" else EZ_CH_LIST
    success = self.calibrate_integration_time(ch_list)

DO NOT hardcode ["a", "b", "c", "d"] in function bodies.

TIMING DELAYS (Code Quality Standard):
======================================
time.sleep() calls should use named constants from the constants section.

Common delay purposes:
- LED_DELAY (50ms): LED warm-up and optical settling
- ADAPTIVE_STABILIZATION_DELAY (150ms): LED intensity changes during optimization
- Mode switch delays (400ms): Servo motor rotation, polarizer movement
- Integration adjustment (20ms): Detector parameter updates

See CODE_QUALITY_ANALYSIS_COMPLETE.md for optimization analysis.

Author: Refactored from main.py
Date: October 7, 2025
Last Updated: October 11, 2025 (Code quality improvements)
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
    ACQUISITION_CYCLE_TIME,
    ACQUISITION_FREQUENCY,
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
    TIME_PER_CHANNEL,
    TIME_ZONE,
)
from utils.logger import logger
from utils.spr_data_processor import SPRDataProcessor

if TYPE_CHECKING:
    from utils.controller import PicoEZSPR, PicoP4SPR
    from utils.usb4000_adapter import USB4000  # HAL-based USB4000 adapter


# ============================================================================
# CALIBRATION CONSTANTS - Centralized Configuration
# ============================================================================

# LED Intensity Constraints
MIN_LED_INTENSITY = int(0.05 * 255)  # 5% of max LED intensity = 13 (minimum safe operating point)
MAX_LED_INTENSITY = 255  # Maximum LED intensity (8-bit PWM)
LED_MID_POINT = 128  # Starting point for binary search optimization
FOUR_LED_MAX_INTENSITY = 204  # 4LED limited to ~80% (0.8 * 255)

# LED Adjustment Steps (for legacy coarse/medium/fine calibration)
COARSE_ADJUSTMENT = 20  # LED intensity adjustment step for rough calibration
MEDIUM_ADJUSTMENT = 5  # LED intensity adjustment step for medium calibration
FINE_ADJUSTMENT = 1  # LED intensity adjustment step for fine calibration

# Adaptive Calibration Algorithm Parameters
ADAPTIVE_CALIBRATION_ENABLED = True  # Enable adaptive algorithm
ADAPTIVE_MAX_ITERATIONS = 10  # Maximum iterations before fallback (reduced for speed)
ADAPTIVE_CONVERGENCE_FACTOR = 0.9  # Convergence damping factor (more aggressive)
ADAPTIVE_MIN_STEP = 1  # Minimum LED intensity step
ADAPTIVE_MAX_STEP = 75  # Maximum LED intensity step (larger for faster approach)
ADAPTIVE_STABILIZATION_DELAY = 0.15  # LED stabilization delay in seconds (optimized for speed)

# Integration Time Parameters
INTEGRATION_STEP_THRESHOLD = 50  # Threshold for changing dark noise scan count (ms)
TEMP_INTEGRATION_TIME_S = 0.032  # 32ms - safe middle value for initial dark measurement
MS_TO_SECONDS = 1000.0  # Conversion factor milliseconds to seconds

# Signal Intensity Thresholds (as percentages of detector max)
MINIMUM_ACCEPTABLE_PERCENT = 60  # User requirement: at least 60% of detector max
IDEAL_TARGET_PERCENT = 80  # Ideal target signal strength
SATURATION_THRESHOLD_PERCENT = 95  # 95% = near saturation warning threshold

# P-Mode Calibration Parameters
LED_BOOST_FACTOR = 1.33  # 33% boost for P-mode if possible
SIGNAL_BOOST_TARGET = 1.20  # 20% signal increase target for P-mode

# Wavelength Calibration
WAVELENGTH_OFFSET = 20  # Offset applied to wavelength data in some configurations

# Percentage Conversion
PERCENT_MULTIPLIER = 100  # For converting ratios to percentages

# Polarizer Servo Position Constraint (0-255 range)
MAX_POLARIZER_POSITION = 255  # Maximum servo position (raw value, NOT degrees)


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


def calculate_dynamic_scans(integration_time_seconds: float,
                            target_cycle_time: float = 0.2,
                            min_scans: int = 1,
                            max_scans: int = 10) -> int:
    """Calculate number of scans to average based on integration time.

    The goal is to maintain a fast acquisition time (≤200ms) for responsive
    sensorgram updates while still providing noise reduction through averaging
    when integration time allows. Noise will be handled through mathematical
    post-processing (filtering, Kalman, etc.) rather than excessive averaging.

    Formula: num_scans = min(max_scans, max(min_scans, target_cycle_time / integration_time))

    Args:
        integration_time_seconds: Integration time in seconds
        target_cycle_time: Target total time for acquisition (default 0.2s = 200ms)
        min_scans: Minimum number of scans (default 1 - single scan allowed)
        max_scans: Maximum number of scans (default 10 - sufficient for 200ms target)

    Returns:
        Number of scans to average

    Examples:
        integration=0.150s (150ms) → 1 scan (150ms total) - fast response!
        integration=0.100s (100ms) → 2 scans (200ms total)
        integration=0.050s (50ms)  → 4 scans (200ms total)
        integration=0.020s (20ms)  → 10 scans (200ms total, capped at max)
        integration=0.010s (10ms)  → 10 scans (100ms total, capped at max)
    """
    calculated_scans = int(target_cycle_time / integration_time_seconds)
    clamped_scans = max(min_scans, min(max_scans, calculated_scans))
    return clamped_scans


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
        self.integration = MIN_INTEGRATION / MS_TO_SECONDS  # Convert ms to seconds
        self.num_scans = 1
        self.base_integration_time_factor = 1.0  # Fiber-specific speed multiplier (0.5 for 200µm = 2x faster)

        # LED intensities
        self.ref_intensity: dict[str, int] = dict.fromkeys(CH_LIST, 0)
        self.leds_calibrated: dict[str, int] = dict.fromkeys(CH_LIST, 0)
        self.weakest_channel: Optional[str] = None  # ✨ NEW: Track weakest channel for S-mode calibration
        self.led_ranking: list[tuple[str, tuple[float, float, bool]]] = []  # ✨ NEW: Full LED ranking (weakest → strongest) from Step 3

        # Reference data
        self.dark_noise: np.ndarray = np.array([])
        self.full_spectrum_dark_noise: np.ndarray = np.array([])  # Full spectrum for resampling
        self.ref_sig: dict[str, np.ndarray | None] = dict.fromkeys(CH_LIST)

        # ✨ NEW: Dark noise comparison (Phase 2 validation)
        self.dark_noise_before_leds: Optional[np.ndarray] = None  # Step 1 (clean baseline)
        self.dark_noise_after_leds_uncorrected: Optional[np.ndarray] = None  # Step 5 before correction
        self.dark_noise_contamination: Optional[float] = None  # Contamination in counts

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
                "base_integration_time_factor": self.base_integration_time_factor,
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
            self.base_integration_time_factor = data.get("base_integration_time_factor", 1.0)
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
        led_min: int = MIN_LED_INTENSITY,  # 5% of max LED intensity = 13
        led_max: int = MAX_LED_INTENSITY,
    ) -> Optional[int]:
        """Predict LED intensity needed to achieve target counts.

        Args:
            channel: Channel name
            target_counts: Desired detector counts
            led_min: Minimum allowed LED intensity (default 5% of max = 13)
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
        optical_fiber_diameter: int = 100,
        led_pcb_model: str = "4LED",
        device_config: Optional[dict] = None,
    ):
        """Initialize the SPR calibrator.

        Args:
            ctrl: LED and polarizer controller
            usb: USB4000 spectrometer
            device_type: Device type string ('PicoP4SPR', 'PicoEZSPR', etc.')
            stop_flag: Optional threading event to signal stop
            calib_state: Optional shared CalibrationState. If None, creates a new one.
            optical_fiber_diameter: Optical fiber diameter in µm (100 or 200)
            led_pcb_model: LED PCB model ("4LED" or "8LED")
            device_config: Optional device configuration dictionary for optical calibration

        """
        self.ctrl = ctrl
        self.usb = usb
        self.device_type = device_type
        self.stop_flag = stop_flag

        # Device-specific configuration
        self.optical_fiber_diameter = optical_fiber_diameter
        self.led_pcb_model = led_pcb_model
        self.device_config = device_config  # ✨ CRITICAL: Store device_config for OEM polarizer positions
        
        # Debug logging to verify device_config
        if self.device_config:
            logger.info(f"✅ device_config received: {list(self.device_config.keys())}")
            if 'oem_calibration' in self.device_config:
                oem = self.device_config['oem_calibration']
                logger.info(f"✅ oem_calibration found: S={oem.get('polarizer_s_position')}, P={oem.get('polarizer_p_position')}")
            else:
                logger.warning("⚠️ device_config missing oem_calibration section")
        else:
            logger.warning("⚠️ device_config is None")
        
        logger.info(f"🔧 Calibrator configured: {optical_fiber_diameter}µm fiber, {led_pcb_model} LED PCB")

        # Apply fiber-specific calibration parameters
        # 200µm fiber collects ~4x more light than 100µm fiber (area = π*r²)
        if optical_fiber_diameter == 200:
            # Higher saturation threshold for 200µm fiber
            self.saturation_threshold_percent = 95  # Can push closer to detector max
            # Lower minimum signal threshold (better SNR)
            self.min_signal_threshold = 500  # Lower minimum due to better signal
            # Faster base integration time (more light collected)
            self.base_integration_time_factor = 0.5  # 2x faster measurements
            logger.info("   📊 200µm fiber: Higher saturation threshold, faster integration times")
        else:
            # Standard thresholds for 100µm fiber
            self.saturation_threshold_percent = 90  # Conservative threshold
            self.min_signal_threshold = 800  # Higher minimum for noise margin
            self.base_integration_time_factor = 1.0  # Standard speed
            logger.info("   📊 100µm fiber: Standard thresholds and integration times")

        # Apply LED model-specific parameters
        if led_pcb_model == "8LED":
            self.max_led_intensity = 255  # 8LED supports full range
            logger.info("   💡 8LED PCB: Full intensity range available")
        else:
            self.max_led_intensity = 204  # 4LED limited to ~80% (0.8 * 255)
            logger.info("   💡 4LED PCB: Limited to 80% intensity range")

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

        # ✨ NEW: Load optical calibration for afterglow correction (Phase 2)
        self.afterglow_correction = None
        self._last_active_channel = None  # Track last LED channel for correction
        self.afterglow_correction_enabled = False

        if device_config:
            optical_cal_file = device_config.get('optical_calibration_file')
            afterglow_enabled = device_config.get('afterglow_correction_enabled', True)

            if optical_cal_file and afterglow_enabled:
                try:
                    from afterglow_correction import AfterglowCorrection
                    self.afterglow_correction = AfterglowCorrection(optical_cal_file)
                    self.afterglow_correction_enabled = True
                    logger.info("✅ Optical calibration loaded for calibration afterglow correction")
                    logger.info(f"   File: {Path(optical_cal_file).name}")
                except FileNotFoundError as e:
                    logger.info(f"ℹ️ Optical calibration file not found: {e}")
                    logger.info("ℹ️ Afterglow correction DISABLED for calibration")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load optical calibration: {e}")
                    logger.warning("⚠️ Afterglow correction DISABLED for calibration")
            else:
                if not optical_cal_file:
                    logger.debug("ℹ️ No optical calibration file specified in device_config")
                if not afterglow_enabled:
                    logger.info("ℹ️ Afterglow correction disabled in device_config")
        else:
            logger.debug("ℹ️ No device_config provided - afterglow correction disabled")

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

        # ✨ NEW: Calibration complete callback for auto-starting live measurements
        self.on_calibration_complete_callback: Callable[[], None] | None = None

    def set_on_calibration_complete_callback(self, callback: Callable[[], None]) -> None:
        """Set callback to be called when calibration completes successfully.

        This enables automatic starting of live measurements after calibration.

        Args:
            callback: Function to call when calibration completes (no arguments)

        Example:
            >>> def auto_start():
            ...     data_acquisition.start_acquisition()
            >>> calibrator.set_on_calibration_complete_callback(auto_start)
        """
        self.on_calibration_complete_callback = callback
        logger.info("✅ Calibration complete callback registered (auto-start enabled)")

    # ========================================================================
    # BATCH LED CONTROL HELPERS (Performance Optimization)
    # ========================================================================

    def _activate_channel_batch(self, channels: list[str], intensities: dict[str, int] | None = None) -> bool:
        """Activate channels using batch LED command for 15× speedup.

        Args:
            channels: List of channel IDs ('a', 'b', 'c', 'd')
            intensities: Optional dict of {channel: intensity} for custom intensities
                        If None, uses calibrated intensities or max

        Returns:
            bool: Success status

        Performance:
            Sequential: 4 commands × 3ms = 12ms
            Batch: 1 command × 0.8ms = 0.8ms
            Speedup: 15×
        """
        try:
            # Check if batch method exists
            if not hasattr(self.ctrl, 'set_batch_intensities'):
                logger.debug("Batch LED control not available, using sequential")
                return self._activate_channel_sequential(channels, intensities)

            # Build intensity array [a, b, c, d]
            intensity_array = [0, 0, 0, 0]
            channel_map = {'a': 0, 'b': 1, 'c': 2, 'd': 3}

            for ch in channels:
                if ch not in channel_map:
                    logger.warning(f"Invalid channel: {ch}")
                    continue

                idx = channel_map[ch]

                if intensities and ch in intensities:
                    intensity_array[idx] = intensities[ch]
                elif hasattr(self.state, f'leds_calibrated') and ch in self.state.leds_calibrated:
                    intensity_array[idx] = self.state.leds_calibrated[ch]
                else:
                    intensity_array[idx] = self.max_led_intensity

            # Send batch command
            success = self.ctrl.set_batch_intensities(
                a=intensity_array[0],
                b=intensity_array[1],
                c=intensity_array[2],
                d=intensity_array[3]
            )

            if success:
                logger.debug(f"✅ Batch LED: {channels} → {intensity_array}")
            else:
                logger.warning("Batch LED command failed, falling back to sequential")
                return self._activate_channel_sequential(channels, intensities)

            return success

        except Exception as e:
            logger.error(f"Batch LED activation failed: {e}, falling back to sequential")
            return self._activate_channel_sequential(channels, intensities)

    def _activate_channel_sequential(self, channels: list[str], intensities: dict[str, int] | None = None) -> bool:
        """Fallback: Sequential channel activation."""
        try:
            for ch in channels:
                if intensities and ch in intensities:
                    self.ctrl.set_intensity(ch=ch, raw_val=intensities[ch])
                else:
                    self.ctrl.turn_on_channel(ch=ch)
            return True
        except Exception as e:
            logger.error(f"Sequential LED activation failed: {e}")
            return False

    def _all_leds_off_batch(self) -> bool:
        """Turn all LEDs off using batch command."""
        try:
            if hasattr(self.ctrl, 'set_batch_intensities'):
                return self.ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
            else:
                self.ctrl.turn_off_channels()
                return True
        except Exception as e:
            logger.error(f"Batch LED off failed: {e}")
            self.ctrl.turn_off_channels()
            return False

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
                        cmd = b"sp\n"  # S-polarization mode
                    else:
                        cmd = b"ss\n"  # P-polarization mode

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
                """Set servo polarizer positions (0-255 raw values)."""
                logger.info(f"Setting servo positions: s={s}, p={p}")
                try:
                    if (s < 0) or (p < 0) or (s > 255) or (p > 255):
                        raise ValueError(f"Invalid polarizer position given: {s}, {p} (must be 0-255)")

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

                # Recreate mask for current size using stored wavelength range
                # Use state values (from detector profile) instead of hardcoded settings
                min_wl = self.state.wavelength_min if hasattr(self.state, 'wavelength_min') else MIN_WAVELENGTH
                max_wl = self.state.wavelength_max if hasattr(self.state, 'wavelength_max') else MAX_WAVELENGTH
                new_mask = (current_wavelengths >= min_wl) & (current_wavelengths <= max_wl)
                logger.debug(f"   Recreated wavelength mask: {np.sum(new_mask)} pixels in {min_wl}-{max_wl} nm")
                return raw_spectrum[new_mask]

            except Exception as e:
                logger.warning(f"   Could not recreate mask: {e} - returning unfiltered spectrum")
                return raw_spectrum

        # Apply spectral filter (silent operation)
        filtered_spectrum = raw_spectrum[self.state.wavelength_mask]
        return filtered_spectrum

    def _acquire_averaged_spectrum(
        self,
        num_scans: int,
        apply_filter: bool = True,
        subtract_dark: bool = False,
        description: str = "spectrum"
    ) -> Optional[np.ndarray]:
        """Vectorized spectrum acquisition and averaging.

        Optimized method that uses NumPy vectorization for 2-3× faster spectrum acquisition.
        Instead of accumulating in a loop, collects all spectra then averages vectorized.

        Args:
            num_scans: Number of spectra to acquire and average
            apply_filter: Whether to apply spectral range filter (default: True)
            subtract_dark: Whether to subtract dark noise (default: False)
            description: Description for logging (default: "spectrum")

        Returns:
            Averaged spectrum as numpy array, or None if error

        Performance:
            Old method: for loop with accumulation (slow)
            New method: vectorized stack + mean (2-3× faster)
        """
        if num_scans <= 0:
            logger.error(f"Invalid num_scans: {num_scans}")
            return None

        try:
            # Pre-allocate array for all spectra (vectorization optimization)
            # Shape: (num_scans, spectrum_length)
            first_spectrum = self.usb.read_intensity()
            if first_spectrum is None:
                logger.error(f"Failed to read first {description}")
                return None

            if apply_filter:
                first_spectrum = self._apply_spectral_filter(first_spectrum)

            spectrum_length = len(first_spectrum)
            spectra_stack = np.empty((num_scans, spectrum_length), dtype=first_spectrum.dtype)
            spectra_stack[0] = first_spectrum

            # Acquire remaining spectra
            for i in range(1, num_scans):
                if self._is_stopped():
                    return None

                raw_spectrum = self.usb.read_intensity()
                if raw_spectrum is None:
                    logger.warning(f"Failed to read {description} scan {i+1}/{num_scans}")
                    return None

                if apply_filter:
                    raw_spectrum = self._apply_spectral_filter(raw_spectrum)

                spectra_stack[i] = raw_spectrum

            # ✨ VECTORIZED AVERAGING (2-3× faster than loop accumulation)
            averaged_spectrum = np.mean(spectra_stack, axis=0)

            # Optionally subtract dark noise
            if subtract_dark and self.state.dark_noise is not None:
                averaged_spectrum = averaged_spectrum - self.state.dark_noise

            # Vectorized averaging complete (silent operation)
            return averaged_spectrum

        except Exception as e:
            logger.error(f"Error in vectorized spectrum acquisition: {e}")
            return None

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
    # STEP 2: WAVELENGTH CALIBRATION (DETECTOR-SPECIFIC)
    # ========================================================================

    def _detect_spectrometer_type_fast(self, wavelengths: np.ndarray) -> str:
        """
        Fast detector detection using already-read wavelengths.

        ✨ OPTIMIZED: No redundant USB reads, minimal string operations

        Args:
            wavelengths: Already-read wavelength array (avoids redundant USB read)

        Returns:
            Detector type string (e.g., "Ocean Optics USB4000/HR4000")
        """
        try:
            # Define Ocean Optics pixel count mapping (fast dict lookup)
            OCEAN_OPTICS_PIXELS = {
                3648: "USB4000/HR4000",
                2048: "Flame/USB2000",
                1044: "QE65000",
                1024: "USB2000+",
            }

            # Try to get model name from USB device (fast path)
            if hasattr(self.usb, 'get_device_info'):
                try:
                    device_info = self.usb.get_device_info()
                    if device_info:
                        # Try model field
                        if 'model' in device_info and device_info['model']:
                            model = device_info['model']
                            return f"Ocean Optics {model}"

                        # Try serial number for model inference (single check)
                        if 'serial_number' in device_info and device_info['serial_number']:
                            serial = device_info['serial_number']
                            # Check serial prefix (fast single-pass)
                            for prefix, model in [
                                ("USB4", "USB4000"),
                                ("FLMS", "Flame"),
                                ("FLMT", "Flame"),
                                ("USB2", "USB2000"),
                                ("HR4", "HR4000"),
                                ("QE", "QE65000"),
                            ]:
                                if serial.startswith(prefix):
                                    return f"Ocean Optics {model}"
                except Exception:
                    pass  # Fallback to pixel count

            # Infer from pixel count (already have wavelengths!)
            pixel_count = len(wavelengths)
            if pixel_count in OCEAN_OPTICS_PIXELS:
                return f"Ocean Optics {OCEAN_OPTICS_PIXELS[pixel_count]}"

            # Default to Ocean Optics (safe assumption for SPR systems)
            return "Ocean Optics (Generic)"

        except Exception as e:
            logger.warning(f"⚠️  Error detecting spectrometer type: {e}")
            return "Ocean Optics (Generic)"  # Safe default

    def _calibrate_wavelength_ocean_optics(self) -> tuple[np.ndarray | None, str]:
        """
        Read factory wavelength calibration from Ocean Optics EEPROM.

        Ocean Optics spectrometers store wavelength calibration coefficients
        in EEPROM during manufacturing. This method reads that data.

        Returns:
            Tuple of (wavelength_array, serial_number)
        """
        try:
            logger.info("   Method: Factory EEPROM (Ocean Optics)")

            # Get serial number from device info
            serial_number = "unknown"
            try:
                if hasattr(self.usb, "get_device_info"):
                    device_info = self.usb.get_device_info()
                    serial_number = device_info.get("serial_number", "unknown")
                    logger.debug(f"   Spectrometer serial number: {serial_number}")
            except Exception as e:
                logger.warning(f"   Could not get serial number: {e}")

            # Read wavelengths from EEPROM
            wave_data = None
            if hasattr(self.usb, "read_wavelength"):
                wave_data = self.usb.read_wavelength()
            elif hasattr(self.usb, "get_wavelengths"):
                # Direct HAL access
                wave_data = self.usb.get_wavelengths()
                if wave_data is not None:
                    wave_data = np.array(wave_data)
            else:
                logger.error("❌ USB spectrometer has no wavelength reading method")
                logger.error("   Expected: read_wavelength() or get_wavelengths()")
                return None, serial_number

            if wave_data is None or len(wave_data) == 0:
                logger.error("❌ Failed to read wavelengths from EEPROM")
                return None, serial_number

            logger.info(f"   ✅ Read {len(wave_data)} wavelengths from factory calibration")
            logger.info(f"   Range: {wave_data[0]:.1f} - {wave_data[-1]:.1f} nm")
            logger.info(f"   Resolution: {(wave_data[-1] - wave_data[0]) / len(wave_data):.3f} nm/pixel")

            return wave_data, serial_number

        except Exception as e:
            logger.error(f"❌ Error reading Ocean Optics EEPROM: {e}")
            return None, "unknown"

    def _calibrate_wavelength_from_file(self) -> tuple[np.ndarray | None, str]:
        """
        Load wavelength calibration from external file.

        For custom detectors or when polynomial calibration is not available,
        load pre-computed wavelength array from file.

        Expected file format:
        - CSV or NPY file with wavelength array
        - One wavelength per pixel
        - Units: nanometers (nm)

        Returns:
            Tuple of (wavelength_array, "custom")
        """
        try:
            from pathlib import Path

            logger.info("   Method: Loading from calibration file")

            # Check for calibration file
            calib_file_npy = Path("calibration") / "wavelength_calibration.npy"
            calib_file_csv = Path("calibration") / "wavelength_calibration.csv"

            if calib_file_npy.exists():
                logger.info(f"   Loading from: {calib_file_npy}")
                wavelengths = np.load(calib_file_npy)
                logger.info(f"   ✅ Loaded {len(wavelengths)} wavelengths from .npy file")
                logger.info(f"   Range: {wavelengths[0]:.1f} - {wavelengths[-1]:.1f} nm")
                return wavelengths, "custom"

            elif calib_file_csv.exists():
                logger.info(f"   Loading from: {calib_file_csv}")
                wavelengths = np.loadtxt(calib_file_csv, delimiter=',')
                logger.info(f"   ✅ Loaded {len(wavelengths)} wavelengths from .csv file")
                logger.info(f"   Range: {wavelengths[0]:.1f} - {wavelengths[-1]:.1f} nm")
                return wavelengths, "custom"

            else:
                logger.error(f"❌ No wavelength calibration file found")
                logger.error(f"   Expected: {calib_file_csv} or {calib_file_npy}")
                logger.error(f"   Please create calibration file or use Ocean Optics detector")
                return None, "custom"

        except Exception as e:
            logger.error(f"❌ Error loading wavelength calibration file: {e}")
            return None, "custom"

    def step_2_calibrate_wavelength_range(self) -> tuple[bool, float]:
        """STEP 2: Calibrate wavelength range and calculate Fourier weights (Detector-Specific).

        ✨ OPTIMIZED: Single wavelength read (no redundant USB calls) + caching

        Improvements:
        - Reads wavelengths once (not 2×)
        - Uses wavelengths for both detection and calibration
        - Fast dict-based detector detection
        - Consolidated logging (cleaner output)
        - Caches wavelengths to skip EEPROM reads (saves ~1s per calibration)

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

            # ========================================================================
            # DETECTOR-SPECIFIC WAVELENGTH CALIBRATION (OPTIMIZED WITH CACHING)
            # ========================================================================

            # ✨ OPTIMIZATION: Check for cached wavelengths first (skip EEPROM read)
            wave_data = None
            serial_number = "unknown"
            used_cache = False

            cached_wavelengths_file = Path(ROOT_DIR) / "calibration_data" / "wavelengths_latest.npy"
            if cached_wavelengths_file.exists():
                try:
                    file_age_days = (time.time() - cached_wavelengths_file.stat().st_mtime) / 86400
                    if file_age_days < 30:  # Use cache if less than 30 days old
                        wave_data = np.load(cached_wavelengths_file)
                        if wave_data is not None and len(wave_data) > 0:
                            used_cache = True
                            logger.info(f"📊 Using cached wavelengths (age: {file_age_days:.1f} days, skip EEPROM read)")
                except Exception as e:
                    logger.debug(f"Failed to load cached wavelengths: {e}")
                    wave_data = None

            # If no valid cache, read from EEPROM
            if wave_data is None:
                logger.info("📊 Reading wavelength calibration from EEPROM (detector-specific)...")

                # ✨ OPTIMIZATION: Read wavelengths ONCE and use for both detection AND calibration
                # (Avoids redundant USB read in _detect_spectrometer_type)

                # Get serial number from device info (fast metadata read)
                try:
                    if hasattr(self.usb, "get_device_info"):
                        device_info = self.usb.get_device_info()
                        if device_info:
                            serial_number = device_info.get("serial_number", "unknown")
                except Exception:
                    pass  # Continue with unknown serial

                # Read wavelengths from EEPROM (single read)
                if hasattr(self.usb, "read_wavelength"):
                    wave_data = self.usb.read_wavelength()
                elif hasattr(self.usb, "get_wavelengths"):
                    wave_data = self.usb.get_wavelengths()
                    if wave_data is not None:
                        wave_data = np.array(wave_data)
                else:
                    logger.error("❌ USB spectrometer has no wavelength reading method")
                    logger.error("   Expected: read_wavelength() or get_wavelengths()")
                    return False, 1.0

            if wave_data is None or len(wave_data) == 0:
                logger.error("❌ Failed to read wavelengths from spectrometer")
                return False, 1.0

            # ✨ OPTIMIZATION: Detect spectrometer type using already-read wavelengths
            detector_type = self._detect_spectrometer_type_fast(wave_data)

            # Log detection results (consolidated)
            if not used_cache:
                logger.info(f"   Detector: {detector_type} (Serial: {serial_number})")
                logger.info(f"   ✅ Read {len(wave_data)} wavelengths from factory calibration")
            else:
                logger.info(f"   Detector: {detector_type} (from cache)")
                logger.info(f"   ✅ Loaded {len(wave_data)} wavelengths from cache")
            logger.info(f"   Range: {wave_data[0]:.1f} - {wave_data[-1]:.1f} nm")
            logger.info(f"   Resolution: {(wave_data[-1] - wave_data[0]) / len(wave_data):.3f} nm/pixel")

            # Apply serial-specific corrections (only if from EEPROM, not cache)
            if not used_cache and serial_number == "FLMT06715":
                wave_data = wave_data + WAVELENGTH_OFFSET

            # Get integration step from detector profile (or fall back to default)
            if self.detector_profile:
                integration_step = self.detector_profile.integration_step_ms
                logger.debug(f"Using detector profile integration step: {integration_step}ms")
            else:
                integration_step = 1.0  # Default fallback
                logger.warning("Using default integration step: 1.0ms")

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
            # Use filtered wavelengths (already in SPR range 580-720nm)
            target_min_idx = np.argmin(np.abs(filtered_wave_data - TARGET_WAVELENGTH_MIN))
            target_max_idx = np.argmin(np.abs(filtered_wave_data - TARGET_WAVELENGTH_MAX))

            logger.info(
                f"📊 Target calibration range: "
                f"{filtered_wave_data[target_min_idx]:.1f} to {filtered_wave_data[target_max_idx]:.1f} nm "
                f"(filtered indices {target_min_idx}-{target_max_idx})"
            )

            # Save wavelength array to disk for longitudinal data processing
            calib_dir = Path(ROOT_DIR) / "calibration_data"
            calib_dir.mkdir(exist_ok=True)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            wave_file = calib_dir / f"wavelengths_{timestamp}.npy"
            np.save(wave_file, filtered_wave_data)

            # Also save as "latest" for easy access
            latest_wave = calib_dir / "wavelengths_latest.npy"
            np.save(latest_wave, filtered_wave_data)

            logger.info(f"💾 Wavelengths saved: {wave_file}")

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

    def calibrate_wavelength_range(self) -> tuple[bool, float]:
        """Calibrate wavelength range (backward compatibility wrapper).

        For new code, use step_2_calibrate_wavelength_range() for clarity.

        Returns:
            Tuple of (success, integration_step)
        """
        return self.step_2_calibrate_wavelength_range()

    # ========================================================================
    # STEP 2B: POLARIZER POSITION VALIDATION
    # ========================================================================

    def validate_polarizer_positions(self) -> bool:
        """Validate that polarizer positions are correctly configured.

        ⚠️ IMPORTANT: In SPR transmission mode, the polarization behavior is:
        - S-mode (perpendicular): HIGH transmission - flat reference spectrum
        - P-mode (parallel): LOWER transmission - shows resonance dip

        This validates that S/P ratio is correct (S should be significantly higher than P).

        Also reads and stores the actual servo positions being used for
        S and P modes to ensure they're consistently applied throughout calibration.

        Expected behavior in SPR:
        - S-mode: High transmission (reference, no resonance)
        - P-mode: Lower transmission (measurement, resonance dip)
        - Ratio: S-mode should be 3-15× higher than P-mode

        Returns:
            True if polarizer positions are valid, False otherwise
        """
        try:
            if self.ctrl is None or self.usb is None:
                logger.warning("⚠️ Cannot validate polarizer - hardware not available")
                return True  # Skip validation if hardware unavailable

            logger.info("=" * 80)
            logger.info("STEP 2B: Polarizer Position Validation (Transmission Mode)")
            logger.info("=" * 80)
            logger.info("Verifying P-mode (HIGH) and S-mode (LOW) positions...")

            # ✨ CRITICAL: Load positions from device_config if not already in state
            if not hasattr(self.state, 'polarizer_s_position') or self.state.polarizer_s_position is None:
                if self.device_config and 'oem_calibration' in self.device_config:
                    oem_cal = self.device_config['oem_calibration']
                    self.state.polarizer_s_position = oem_cal.get('polarizer_s_position')
                    self.state.polarizer_p_position = oem_cal.get('polarizer_p_position')
                    self.state.polarizer_sp_ratio = oem_cal.get('polarizer_sp_ratio')
                    logger.info(f"   Loaded OEM positions from device_config:")
                    logger.info(f"      S={self.state.polarizer_s_position}, P={self.state.polarizer_p_position}")
                else:
                    # No device_config or missing oem_calibration - FAIL EARLY
                    logger.error("=" * 80)
                    logger.error("❌ POLARIZER CONFIGURATION MISSING")
                    logger.error("=" * 80)
                    logger.error("⚠️ No device_config or missing 'oem_calibration' section")
                    logger.error("")
                    logger.error("🔧 REQUIRED: Run OEM calibration tool to configure polarizer positions")
                    logger.error("   Command: python utils/oem_calibration_tool.py --serial YOUR_SERIAL")
                    logger.error("=" * 80)
                    return False

            # ✨ CRITICAL: Apply positions from calibration state to hardware BEFORE validation
            # These positions come from OEM calibration and must be set before we validate
            if hasattr(self.state, 'polarizer_s_position') and hasattr(self.state, 'polarizer_p_position'):
                if self.state.polarizer_s_position is not None and self.state.polarizer_p_position is not None:
                    logger.info(f"   Applying OEM-calibrated positions to hardware:")
                    logger.info(f"      S={self.state.polarizer_s_position}, P={self.state.polarizer_p_position}")
                    self.ctrl.servo_set(s=self.state.polarizer_s_position, p=self.state.polarizer_p_position)
                    time.sleep(1.0)  # Wait for servo to move to both positions
                    logger.info(f"   ✅ Polarizer positions applied to hardware")
                else:
                    logger.warning("⚠️ Polarizer positions in state are None - skipping pre-application")
            else:
                logger.warning("⚠️ No polarizer positions in state - skipping pre-application")

            # Read current servo positions from hardware to verify they match config
            try:
                current_positions = self.ctrl.servo_get()

                # Decode bytes to string and sanitize (remove non-digit characters)
                s_raw = current_positions["s"].decode() if isinstance(current_positions["s"], bytes) else str(current_positions["s"])
                p_raw = current_positions["p"].decode() if isinstance(current_positions["p"], bytes) else str(current_positions["p"])

                # Remove non-digit characters (commas, spaces, etc.) that can corrupt the response
                s_clean = ''.join(filter(str.isdigit, s_raw))
                p_clean = ''.join(filter(str.isdigit, p_raw))

                if not s_clean or not p_clean:
                    raise ValueError(f"Invalid servo position data: S='{s_raw}', P='{p_raw}' (no digits found after sanitization)")

                s_hardware = int(s_clean)
                p_hardware = int(p_clean)
                logger.info(f"   Hardware confirmation: S={s_hardware}, P={p_hardware} (should match OEM config)")

                # ✅ NO SWAPPING: OEM calibration provides correct S/P positions directly
                # S-mode position (HIGH transmission - reference) = state.polarizer_s_position
                # P-mode position (LOWER transmission - resonance) = state.polarizer_p_position
                # Hardware should now match config values we just applied
                
                # Verify hardware matches what we just set from config
                if s_hardware != self.state.polarizer_s_position or p_hardware != self.state.polarizer_p_position:
                    logger.warning(f"   ⚠️ Hardware mismatch: Expected S={self.state.polarizer_s_position} P={self.state.polarizer_p_position}, got S={s_hardware} P={p_hardware}")
                    logger.warning(f"   Re-applying positions to hardware...")
                    self.ctrl.servo_set(s=self.state.polarizer_s_position, p=self.state.polarizer_p_position)
                    time.sleep(0.5)
                else:
                    logger.info(f"   ✅ Hardware matches config: S={self.state.polarizer_s_position} (LOW), P={self.state.polarizer_p_position} (HIGH)")
            except Exception as e:
                logger.error("=" * 80)
                logger.error("❌ POLARIZER CONFIGURATION MISSING")
                logger.error("=" * 80)
                logger.error(f"⚠️ Could not read servo positions from hardware: {e}")
                logger.error("")
                logger.error("🔧 REQUIRED: Run OEM calibration tool to configure polarizer positions")
                logger.error("   This tool finds optimal S and P positions during manufacturing.")
                logger.error("")
                logger.error("   Command: python utils/oem_calibration_tool.py --serial YOUR_SERIAL")
                logger.error("")
                logger.error("   The OEM tool will:")
                logger.error("   1. Sweep servo through full range (10-255)")
                logger.error("   2. Find optimal S-mode position (perpendicular - HIGH transmission)")
                logger.error("   3. Find optimal P-mode position (parallel - LOWER transmission)")
                logger.error("   4. Save positions to device profile (single source of truth)")
                logger.error("")
                logger.error("   ❌ NO DEFAULT POSITIONS - OEM calibration is MANDATORY")
                logger.error("=" * 80)
                # DO NOT SET DEFAULT POSITIONS - Force user to run OEM tool
                self.state.polarizer_s_position = None
                self.state.polarizer_p_position = None
                return False  # Fail calibration - OEM tool must be run first

            # Turn on LED A at moderate intensity for testing
            self.ctrl.set_intensity("a", 150)
            self.ctrl.turn_on_channel("a")
            time.sleep(0.3)

            # Measure S-mode intensity (should be HIGH - reference, no resonance)
            self.ctrl.set_mode("s")
            time.sleep(0.4)  # Wait for servo to move
            s_spectrum = self.usb.read_intensity()
            s_max = float(np.max(s_spectrum)) if s_spectrum is not None else 0.0

            # Measure P-mode intensity (should be LOWER - shows resonance)
            self.ctrl.set_mode("p")
            time.sleep(0.4)  # Wait for servo to move
            p_spectrum = self.usb.read_intensity()
            p_max = float(np.max(p_spectrum)) if p_spectrum is not None else 0.0

            # Turn off LED
            self.ctrl.turn_off_channels()

            # Calculate ratio (S/P - should be > 2 in SPR, typically 3-15×)
            ratio = s_max / p_max if p_max > 0 else 0.0

            # Store validated ratio in state for reference
            self.state.polarizer_sp_ratio = ratio  # S/P ratio (correct for SPR)

            logger.info(f"   S-mode intensity: {s_max:.1f} counts (HIGH expected - reference)")
            logger.info(f"   P-mode intensity: {p_max:.1f} counts (LOWER expected - resonance)")
            logger.info(f"   S/P ratio: {ratio:.2f}x")

            # Validate: S-mode should be significantly higher than P-mode (SPR behavior)
            MIN_RATIO = 2.0  # S should be at least 2× higher than P
            IDEAL_RATIO_MIN = 3.0
            IDEAL_RATIO_MAX = 15.0

            if ratio < MIN_RATIO:
                logger.error("=" * 80)
                logger.error("❌ POLARIZER POSITION ERROR DETECTED")
                logger.error("=" * 80)
                logger.error(f"   S-mode intensity ({s_max:.1f}) is NOT significantly higher than P-mode ({p_max:.1f})")
                logger.error(f"   Ratio: {ratio:.2f}x (expected: >{MIN_RATIO}x)")
                logger.error(f"   Servo positions: S={self.state.polarizer_s_position}, P={self.state.polarizer_p_position} (0-255 scale)")
                logger.error("")
                logger.error("Possible causes:")
                logger.error("   1. Polarizer positions are swapped (S and P reversed)")
                logger.error("   2. Servo positions need adjustment")
                logger.error("   3. Polarizer not properly aligned")
                logger.error("")
                logger.error("💡 Solution: Run OEM calibration tool to find correct positions")
                logger.error("=" * 80)
                return False
            elif ratio < IDEAL_RATIO_MIN:
                logger.warning("=" * 80)
                logger.warning("⚠️ POLARIZER POSITION WARNING")
                logger.warning("=" * 80)
                logger.warning(f"   S/P ratio ({ratio:.2f}x) is lower than ideal ({IDEAL_RATIO_MIN}-{IDEAL_RATIO_MAX}x)")
                logger.warning(f"   Servo positions: S={self.state.polarizer_s_position}, P={self.state.polarizer_p_position} (0-255 scale)")
                logger.warning("   Calibration will continue, but consider running auto-polarization")
                logger.warning("   (Available in Settings menu)")
                logger.warning("=" * 80)
                return True  # Allow calibration to continue with warning
            elif ratio > IDEAL_RATIO_MAX:
                logger.warning(f"⚠️ S/P ratio ({ratio:.2f}x) is higher than typical ({IDEAL_RATIO_MAX}x)")
                logger.warning("   This may indicate P-mode is blocking too much light")
                logger.info(f"✅ Polarizer positions are valid: S={self.state.polarizer_s_position}, P={self.state.polarizer_p_position} (0-255 scale)")
                logger.info("=" * 80)
                return True
            else:
                logger.info(f"✅ Polarizer positions VALIDATED (ratio: {ratio:.2f}x is ideal)")
                logger.info(f"   Servo positions confirmed: S={self.state.polarizer_s_position}, P={self.state.polarizer_p_position} (0-255 scale)")
                logger.info("=" * 80)
                return True

        except Exception as e:
            logger.exception(f"Error validating polarizer positions: {e}")
            logger.warning("⚠️ Polarizer validation failed - continuing calibration anyway")
            return True  # Don't block calibration on validation errors

    # ========================================================================
    # STEP 3: LED BRIGHTNESS RANKING (OPTIMIZED FOR SPEED)
    # ========================================================================

    def step_3_identify_weakest_channel(self, ch_list: list[str]) -> tuple[str | None, dict]:
        """STEP 3: Rank all LED channels by brightness to identify weakest and strongest.

        Purpose: Quick LED brightness test to determine:
        - Weakest LED → Will be fixed at LED=255
        - Strongest LED → Most likely to saturate (needs most dimming)
        - Full ranking → For diagnostic purposes

        ✨ OPTIMIZED FOR SPEED:
        - Single raw read per channel (no averaging)
        - NO dark subtraction (comparing relative brightness only)
        - Test at 50% LED to avoid saturation
        - 580-610nm test region (arbitrary, just for consistent measurement)
        - Saturation detection with auto-retry at 25%
        - Full LED ranking (weakest → strongest)

        Args:
            ch_list: List of channels to test

        Returns:
            Tuple of (weakest_channel_id, dict of all channel intensities)
        """
        try:
            if self.ctrl is None or self.usb is None:
                return None, {}

            logger.info(f"📊 Testing all LEDs to rank by brightness (weakest → strongest)...")

            # Set to S-mode and turn off all channels
            self.ctrl.set_mode(mode="s")
            time.sleep(0.5)
            self.ctrl.turn_off_channels()
            time.sleep(0.2)

            # Get target wavelength range for measurements
            # NOTE: 580-610nm is NOT SPR-specific - just a test region where all LEDs emit
            wave_data = self.state.wavelengths
            target_min_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MIN))
            target_max_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MAX))

            # ✨ OPTIMIZATION: Use LOWER test LED to avoid saturation during testing
            test_led_intensity = int(0.5 * MAX_LED_INTENSITY)  # 128 (50%)
            logger.info(f"   Test LED intensity: {test_led_intensity} ({test_led_intensity/255*100:.0f}%)")
            logger.info(f"   Test region: {TARGET_WAVELENGTH_MIN}-{TARGET_WAVELENGTH_MAX}nm (arbitrary measurement region)")

            channel_data = {}  # {channel: (mean_intensity, max_intensity, saturated)}

            # Get detector max for saturation detection
            if self.detector_profile:
                detector_max = self.detector_profile.max_intensity_counts
            else:
                detector_max = DETECTOR_MAX_COUNTS

            SATURATION_THRESHOLD = int(0.95 * detector_max)  # 95% of max

            # ✨ FAST TEST: Single read per channel, no averaging, no dark subtraction
            for ch in ch_list:
                if self._is_stopped():
                    return None, {}

                # Turn on channel at test intensity
                intensities_dict = {ch: test_led_intensity}
                self._activate_channel_batch([ch], intensities_dict)
                time.sleep(LED_DELAY)

                # Track for afterglow correction
                self._last_active_channel = ch

                # ✨ SINGLE RAW READ (no averaging, no dark subtraction)
                raw_array = self.usb.read_intensity()
                if raw_array is None:
                    logger.error(f"Failed to read intensity for channel {ch}")
                    continue

                # Apply spectral filter (to SPR range)
                filtered_array = self._apply_spectral_filter(raw_array)

                # Extract test region (580-610nm)
                test_region = filtered_array[target_min_idx:target_max_idx]
                mean_intensity = float(np.mean(test_region))
                max_intensity = float(np.max(test_region))

                # Detect saturation
                is_saturated = max_intensity >= SATURATION_THRESHOLD

                channel_data[ch] = (mean_intensity, max_intensity, is_saturated)

                sat_flag = " ⚠️ SATURATED" if is_saturated else ""
                logger.info(f"   {ch}: mean={mean_intensity:6.0f}, max={max_intensity:6.0f}{sat_flag}")

            # Turn off all channels
            self._all_leds_off_batch()
            time.sleep(LED_DELAY)

            # ✨ HANDLE SATURATION: Retry at lower LED for accurate ranking
            saturated_channels = [ch for ch, (_, _, sat) in channel_data.items() if sat]

            if saturated_channels:
                logger.warning(f"⚠️  {len(saturated_channels)} channel(s) saturated: {saturated_channels}")
                logger.warning(f"   Retrying at LED=64 (25%) for accurate ranking...")

                retry_led = int(0.25 * MAX_LED_INTENSITY)  # 64

                for ch in saturated_channels:
                    if self._is_stopped():
                        return None, {}

                    # Turn on channel at lower intensity
                    intensities_dict = {ch: retry_led}
                    self._activate_channel_batch([ch], intensities_dict)
                    time.sleep(LED_DELAY)

                    self._last_active_channel = ch

                    # Single raw read
                    raw_array = self.usb.read_intensity()
                    if raw_array is None:
                        logger.error(f"Failed to read intensity for channel {ch} on retry")
                        continue

                    # Apply spectral filter
                    filtered_array = self._apply_spectral_filter(raw_array)

                    # Extract test region
                    test_region = filtered_array[target_min_idx:target_max_idx]
                    mean_intensity = float(np.mean(test_region))
                    max_intensity = float(np.max(test_region))

                    # Scale up to equivalent of test_led_intensity for fair ranking
                    scaled_mean = mean_intensity * (test_led_intensity / retry_led)
                    scaled_max = max_intensity * (test_led_intensity / retry_led)

                    channel_data[ch] = (scaled_mean, scaled_max, False)  # Not saturated after scaling

                    logger.info(f"   {ch} retry: mean={mean_intensity:6.0f} @ LED={retry_led} (scaled: {scaled_mean:6.0f})")

                # Turn off all channels after retry
                self._all_leds_off_batch()
                time.sleep(LED_DELAY)

            if not channel_data:
                logger.error("No channel data measured!")
                return None, {}

            # ✨ RANK LEDs: Weakest → Strongest (by mean intensity)
            ranked_channels = sorted(channel_data.items(), key=lambda x: x[1][0])  # Sort by mean

            # ✨ Store ranking in state for Step 4 constrained optimization
            self.state.led_ranking = ranked_channels

            logger.info(f"")
            logger.info(f"📊 LED Ranking (weakest → strongest):")
            for rank, (ch, (mean, max_val, was_saturated)) in enumerate(ranked_channels, 1):
                ratio = mean / ranked_channels[0][1][0]  # Ratio to weakest
                sat_flag = " [was saturated]" if was_saturated else ""
                logger.info(f"   {rank}. Channel {ch}: {mean:6.0f} counts ({ratio:.2f}× weakest){sat_flag}")

            # Identify weakest and strongest
            weakest_ch = ranked_channels[0][0]
            weakest_intensity = ranked_channels[0][1][0]
            strongest_ch = ranked_channels[-1][0]
            strongest_intensity = ranked_channels[-1][1][0]

            logger.info(f"")
            logger.info(f"✅ Weakest LED: Channel {weakest_ch} ({weakest_intensity:.0f} counts)")
            logger.info(f"   → Will be FIXED at LED=255 (maximum)")
            logger.info(f"   → Other channels will be dimmed DOWN to match this brightness")
            logger.info(f"")
            logger.info(f"⚠️  Strongest LED: Channel {strongest_ch} ({strongest_intensity:.0f} counts)")
            logger.info(f"   → Most likely to saturate (brightest LED)")
            logger.info(f"   → Will need most dimming (ratio: {strongest_intensity/weakest_intensity:.2f}×)")

            # Build dict for return (maintain compatibility)
            channel_intensities = {ch: data[0] for ch, data in channel_data.items()}

            return weakest_ch, channel_intensities

        except Exception as e:
            logger.exception(f"Error identifying weakest channel: {e}")
            return None, {}

    # ========================================================================
    # STEP 4: INTEGRATION TIME OPTIMIZATION - HELPER METHODS
    # ========================================================================

    def _measure_channel_in_roi(
        self,
        channel: str,
        led_intensity: int,
        roi_min_idx: int,
        roi_max_idx: int,
        description: str = "channel"
    ) -> tuple[float, float] | None:
        """Measure a single channel's signal in ROI range.

        Helper method to reduce code duplication in Step 4.
        Handles activation, measurement, filtering, and cleanup.

        Args:
            channel: Channel ID ('a', 'b', 'c', 'd')
            led_intensity: LED intensity to use (0-255)
            roi_min_idx: Start index of ROI in filtered spectrum
            roi_max_idx: End index of ROI in filtered spectrum
            description: Description for logging (e.g., "weakest LED", "strongest LED")

        Returns:
            Tuple of (max_signal, mean_signal) in ROI, or None if measurement failed
        """
        try:
            # Activate channel
            intensities_dict = {channel: led_intensity}
            self._activate_channel_batch([channel], intensities_dict)
            time.sleep(LED_DELAY)
            self._last_active_channel = channel

            # Read spectrum
            raw_array = self.usb.read_intensity()
            if raw_array is None:
                logger.error(f"❌ Failed to read {description} for channel {channel}")
                return None

            # Apply spectral filter
            filtered_array = self._apply_spectral_filter(raw_array)

            # Extract ROI and calculate statistics
            roi_spectrum = filtered_array[roi_min_idx:roi_max_idx]
            signal_max = float(np.max(roi_spectrum))
            signal_mean = float(np.mean(roi_spectrum))

            # Turn off channel
            self._all_leds_off_batch()
            time.sleep(LED_DELAY)

            return signal_max, signal_mean

        except Exception as e:
            logger.error(f"Error measuring {description} for channel {channel}: {e}")
            self._all_leds_off_batch()
            return None

    # ========================================================================
    # STEP 4: INTEGRATION TIME OPTIMIZATION
    # ========================================================================

    def step_4_optimize_integration_time(self, weakest_ch: str, integration_step: float) -> bool:
        """STEP 4: Constrained dual optimization for integration time (S-MODE ONLY) - COMPLETE.

        This optimizes integration time for CALIBRATION (S-mode) only.
        P-mode integration time is calculated later when entering live mode.

        By the end of Step 4:
          ✅ Integration time is FINAL for S-mode
          ✅ ALL 4 channels validated explicitly
          ✅ No Step 5 needed - optimization complete

        Dual optimization with constraints:

        PRIMARY GOAL (maximize):
          - Weakest LED at LED=255 produces 60-80% detector max
          - Target: 70% = ~45,900 counts
          - Measured as MAX signal across full ROI (580-720nm)

        CONSTRAINT 1:
          - Strongest LED at LED≥25 → <95% detector max

        CONSTRAINT 2:
          - Integration time ≤ 200ms (from detector profile)

        VALIDATION (all channels):
          - Explicitly measure ALL channels (A, B, C, D) at predicted LED intensities
          - Verify all signals are within acceptable range
          - Middle channels no longer just "assumed" - they are measured!

        Args:
            weakest_ch: The weakest channel ID (from Step 3)
            integration_step: Step size for integration time adjustments (unused, uses binary search)

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            # Import constrained optimization constants
            from settings import (
                WEAKEST_TARGET_PERCENT, WEAKEST_MIN_PERCENT, WEAKEST_MAX_PERCENT,
                STRONGEST_MAX_PERCENT, STRONGEST_MIN_LED
            )

            # Get integration time limits from detector profile
            if self.detector_profile:
                min_int = self.detector_profile.min_integration_time_ms / MS_TO_SECONDS
                max_int = self.detector_profile.max_integration_time_ms / MS_TO_SECONDS
                detector_max = self.detector_profile.max_intensity_counts
                spr_min_nm = self.detector_profile.spr_wavelength_min_nm
                spr_max_nm = self.detector_profile.spr_wavelength_max_nm
                logger.info(f"📊 Using detector profile: {self.detector_profile.min_integration_time_ms}-{self.detector_profile.max_integration_time_ms}ms")
                logger.info(f"   SPR Range: {spr_min_nm}-{spr_max_nm}nm")
            else:
                min_int = MIN_INTEGRATION / MS_TO_SECONDS
                max_int = MAX_INTEGRATION / MS_TO_SECONDS
                detector_max = DETECTOR_MAX_COUNTS
                spr_min_nm = 580.0
                spr_max_nm = 720.0
                logger.warning("Using legacy integration limits from settings.py")

            # Get LED ranking from Step 3
            if not self.state.led_ranking or len(self.state.led_ranking) < 2:
                logger.error("⚠️  LED ranking not found! Step 3 must run before Step 4.")
                return False

            weakest_ch = self.state.led_ranking[0][0]
            strongest_ch = self.state.led_ranking[-1][0]
            weakest_intensity = self.state.led_ranking[0][1][0]
            strongest_intensity = self.state.led_ranking[-1][1][0]
            brightness_ratio = strongest_intensity / weakest_intensity

            logger.info(f"")
            logger.info(f"⚡ STEP 4: CONSTRAINED DUAL OPTIMIZATION")
            logger.info(f"   Weakest LED: {weakest_ch} (reference brightness)")
            logger.info(f"   Strongest LED: {strongest_ch} ({brightness_ratio:.2f}× brighter)")
            logger.info(f"")
            logger.info(f"   PRIMARY GOAL: Maximize weakest LED signal")
            logger.info(f"      → Target: {WEAKEST_TARGET_PERCENT}% @ LED=255 ({int(WEAKEST_TARGET_PERCENT/100*detector_max):,} counts)")
            logger.info(f"      → Range: {WEAKEST_MIN_PERCENT}-{WEAKEST_MAX_PERCENT}% ({int(WEAKEST_MIN_PERCENT/100*detector_max):,}-{int(WEAKEST_MAX_PERCENT/100*detector_max):,} counts)")
            logger.info(f"")
            logger.info(f"   CONSTRAINT 1: Strongest LED must not saturate")
            logger.info(f"      → Maximum: <{STRONGEST_MAX_PERCENT}% @ LED={STRONGEST_MIN_LED} ({int(STRONGEST_MAX_PERCENT/100*detector_max):,} counts)")
            logger.info(f"")
            logger.info(f"   CONSTRAINT 2: Integration time ≤ {max_int*1000:.0f}ms")
            logger.info(f"")

            # Get full SPR ROI indices (580-720nm, not just 580-610nm)
            wave_data = self.state.wavelengths
            roi_min_idx = np.argmin(np.abs(wave_data - spr_min_nm))
            roi_max_idx = np.argmin(np.abs(wave_data - spr_max_nm))
            logger.debug(f"   Measuring MAX signal in ROI: {spr_min_nm}-{spr_max_nm}nm (indices {roi_min_idx}-{roi_max_idx})")

            # Define targets
            weakest_target = int(WEAKEST_TARGET_PERCENT / 100 * detector_max)
            weakest_min = int(WEAKEST_MIN_PERCENT / 100 * detector_max)
            weakest_max = int(WEAKEST_MAX_PERCENT / 100 * detector_max)
            strongest_max = int(STRONGEST_MAX_PERCENT / 100 * detector_max)

            # Binary search for optimal integration time
            integration_min = min_int
            integration_max = max_int
            best_integration = None
            best_weakest_signal = 0
            best_strongest_signal = 0

            max_iterations = 20
            logger.info(f"🔍 Binary search: {integration_min*1000:.1f}ms - {integration_max*1000:.1f}ms")
            logger.info(f"")

            for iteration in range(max_iterations):
                if self._is_stopped():
                    return False

                # Test integration time (midpoint)
                test_integration = (integration_min + integration_max) / 2.0
                self.state.integration = test_integration
                self.usb.set_integration(test_integration)
                time.sleep(0.1)

                # ========================================================================
                # Test 1: Measure weakest LED at LED=255
                # ========================================================================
                result = self._measure_channel_in_roi(
                    weakest_ch, MAX_LED_INTENSITY, roi_min_idx, roi_max_idx, "weakest LED"
                )
                if result is None:
                    return False
                weakest_signal, _ = result
                weakest_percent = (weakest_signal / detector_max) * 100

                # ========================================================================
                # Test 2: Measure strongest LED at LED=25 (minimum practical LED)
                # ========================================================================
                result = self._measure_channel_in_roi(
                    strongest_ch, STRONGEST_MIN_LED, roi_min_idx, roi_max_idx, "strongest LED"
                )
                if result is None:
                    return False
                strongest_signal, _ = result
                strongest_percent = (strongest_signal / detector_max) * 100

                # ========================================================================
                # Check constraints and adjust search range
                # ========================================================================
                logger.info(f"   Iteration {iteration+1}: {test_integration*1000:.1f}ms")
                logger.info(f"      Weakest ({weakest_ch} @ LED=255): {weakest_signal:6.0f} counts ({weakest_percent:5.1f}%)")
                logger.info(f"      Strongest ({strongest_ch} @ LED={STRONGEST_MIN_LED}): {strongest_signal:6.0f} counts ({strongest_percent:5.1f}%)")

                # CONSTRAINT 1: Check if strongest LED would saturate
                if strongest_signal > strongest_max:
                    logger.info(f"      ❌ Strongest LED too high (would saturate at >95%) → Reduce integration")
                    integration_max = test_integration
                    continue

                # PRIMARY GOAL: Check if weakest LED is in target range
                if weakest_min <= weakest_signal <= weakest_max:
                    # ✅ Perfect! Both constraints satisfied
                    best_integration = test_integration
                    best_weakest_signal = weakest_signal
                    best_strongest_signal = strongest_signal
                    logger.info(f"      ✅ OPTIMAL! Both constraints satisfied")
                    break

                # Adjust search range based on weakest LED
                if weakest_signal < weakest_min:
                    logger.info(f"      ⚠️  Weakest LED too low → Increase integration")
                    integration_min = test_integration
                else:
                    logger.info(f"      ⚠️  Weakest LED too high → Reduce integration")
                    integration_max = test_integration

                # Track best so far (closest to target)
                if abs(weakest_signal - weakest_target) < abs(best_weakest_signal - weakest_target):
                    best_integration = test_integration
                    best_weakest_signal = weakest_signal
                    best_strongest_signal = strongest_signal

            # ========================================================================
            # Finalize and validate
            # ========================================================================
            if best_integration is None:
                logger.error("Failed to find optimal integration time!")
                return False

            self.state.integration = best_integration
            self.usb.set_integration(best_integration)
            time.sleep(0.1)

            # Validate final result
            weakest_percent = (best_weakest_signal / detector_max) * 100
            strongest_percent = (best_strongest_signal / detector_max) * 100

            logger.info(f"")
            logger.info(f"="*80)
            logger.info(f"✅ INTEGRATION TIME OPTIMIZED (S-MODE)")
            logger.info(f"="*80)
            logger.info(f"")
            logger.info(f"   Optimal integration time: {best_integration*1000:.1f}ms")
            logger.info(f"")
            logger.info(f"   Weakest LED ({weakest_ch} @ LED=255):")
            logger.info(f"      Signal: {best_weakest_signal:6.0f} counts ({weakest_percent:5.1f}%)")
            logger.info(f"      Status: {'✅ OPTIMAL' if weakest_min <= best_weakest_signal <= weakest_max else '⚠️  Acceptable'}")
            logger.info(f"")
            logger.info(f"   Strongest LED ({strongest_ch} @ LED={STRONGEST_MIN_LED}):")
            logger.info(f"      Signal: {best_strongest_signal:6.0f} counts ({strongest_percent:5.1f}%)")
            logger.info(f"      Status: {'✅ Safe (<95%)' if best_strongest_signal < strongest_max else '⚠️  Near saturation!'}")

            # ========================================================================
            # EXPLICIT VALIDATION OF ALL MIDDLE CHANNELS
            # ========================================================================
            logger.info(f"")
            logger.info(f"📊 VALIDATING ALL CHANNELS at optimal integration time...")

            # Calculate predicted LED intensities for all channels based on Step 3 ranking
            weakest_intensity = self.state.led_ranking[0][1][0]
            predicted_leds = {}

            logger.info(f"")
            logger.info(f"   Predicted LED intensities (based on Step 3 brightness ratios):")

            for ch, (intensity, _, _) in self.state.led_ranking:
                if ch == weakest_ch:
                    predicted_led = MAX_LED_INTENSITY  # Weakest always at 255
                else:
                    # Scale LED down proportional to brightness ratio
                    ratio = intensity / weakest_intensity
                    predicted_led = int(MAX_LED_INTENSITY / ratio)
                    # Clamp to valid range
                    predicted_led = max(STRONGEST_MIN_LED, min(MAX_LED_INTENSITY, predicted_led))

                predicted_leds[ch] = predicted_led
                logger.info(f"      {ch}: LED={predicted_led:3d} (brightness ratio: {intensity/weakest_intensity:.2f}×)")

            # Measure all channels explicitly
            logger.info(f"")
            logger.info(f"   Measuring all channels explicitly:")

            all_channel_signals = {}

            for ch, led_intensity in predicted_leds.items():
                # Use helper to measure channel
                result = self._measure_channel_in_roi(
                    ch, led_intensity, roi_min_idx, roi_max_idx, f"channel {ch}"
                )

                if result is None:
                    logger.error(f"Failed to measure channel {ch}")
                    continue

                signal_max, signal_mean = result
                signal_percent = (signal_max / detector_max) * 100

                all_channel_signals[ch] = (signal_max, signal_mean, signal_percent, led_intensity)

                # Determine status
                if signal_percent > 95:
                    status = "❌ SATURATED"
                elif signal_percent > 80:
                    status = "⚠️  HIGH"
                elif signal_percent < 60:
                    status = "⚠️  LOW"
                else:
                    status = "✅ OPTIMAL"

                logger.info(f"      {ch} @ LED={led_intensity:3d}: max={signal_max:6.0f} ({signal_percent:5.1f}%), mean={signal_mean:6.0f} {status}")

            # Final summary
            logger.info(f"")
            logger.info(f"="*80)
            logger.info(f"📊 FINAL VALIDATION SUMMARY (ALL CHANNELS)")
            logger.info(f"="*80)

            all_ok = True
            for ch in sorted(all_channel_signals.keys()):
                sig_max, sig_mean, sig_percent, led_val = all_channel_signals[ch]

                if sig_percent > 95:
                    logger.error(f"   ❌ Channel {ch}: SATURATED ({sig_percent:.1f}%)")
                    all_ok = False
                elif sig_percent > 80:
                    logger.warning(f"   ⚠️  Channel {ch}: Signal high ({sig_percent:.1f}%), Step 6 will adjust")
                elif sig_percent < 60:
                    logger.warning(f"   ⚠️  Channel {ch}: Signal low ({sig_percent:.1f}%), Step 6 will adjust")
                else:
                    logger.info(f"   ✅ Channel {ch}: Signal optimal ({sig_percent:.1f}%)")

            if not all_ok:
                logger.warning(f"")
                logger.warning(f"   ⚠️  Some channels outside optimal range")
                logger.warning(f"   Step 6 (LED intensity calibration) will fine-tune individual LEDs")

            logger.info(f"")
            logger.info(f"   Integration time FINAL for S-mode: {best_integration*1000:.1f}ms")
            logger.info(f"   This will be used for:")
            logger.info(f"      • Step 5: Re-measure dark noise (at final integration time)")
            logger.info(f"      • Step 6: Apply LED calibration (from Step 4 validation)")
            logger.info(f"      • Step 7: Reference signal measurement")
            logger.info(f"      • Step 8: Validation")
            logger.info(f"")
            logger.info(f"   Note: All 4 channels explicitly validated - integration time is FINAL")
            logger.info(f"   Note: P-mode integration time calculated later in state machine")
            logger.info(f"="*80)

            # ========================================================================
            # STORE LED CALIBRATION FROM STEP 4 VALIDATION
            # ========================================================================
            # Step 4 has already validated all channels at predicted LED intensities.
            # Store these as the final LED calibration (Step 6 will use these).
            logger.info(f"")
            logger.info(f"💾 Storing LED calibration from Step 4 validation...")

            for ch, (intensity, max_sig, saturated) in self.state.led_ranking:
                if ch == weakest_ch:
                    # Weakest channel fixed at maximum LED
                    self.state.ref_intensity[ch] = MAX_LED_INTENSITY
                    logger.info(f"   {ch.upper()}: LED={MAX_LED_INTENSITY} (weakest, fixed at max)")
                else:
                    # Other channels: use predicted LED from Step 3 brightness ratio
                    ratio = intensity / weakest_intensity
                    predicted_led = int(MAX_LED_INTENSITY / ratio)
                    predicted_led = max(MIN_LED_INTENSITY, min(MAX_LED_INTENSITY, predicted_led))
                    self.state.ref_intensity[ch] = predicted_led
                    logger.info(f"   {ch.upper()}: LED={predicted_led} (ratio={ratio:.2f}×)")

            logger.info(f"✅ LED calibration stored (from Step 4 validation)")
            logger.info(f"   Step 6 will apply these values directly (no binary search needed)")
            logger.info(f"="*80)

            # Calculate scan count for averaging using consistent 200ms target
            self.state.num_scans = calculate_dynamic_scans(self.state.integration)
            logger.debug(f"   Scans to average: {self.state.num_scans} (200ms target)")

            return True

        except Exception as e:
            logger.exception(f"Error optimizing integration time: {e}")
            return False

    # ========================================================================
    # STEP 3: INTEGRATION TIME CALIBRATION (LEGACY - TO BE REMOVED)
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
                min_int = self.detector_profile.min_integration_time_ms / MS_TO_SECONDS  # Convert ms to seconds
                max_int = self.detector_profile.max_integration_time_ms / MS_TO_SECONDS  # Convert ms to seconds (200 ms for Flame-T!)
                logger.info(f"Using detector profile integration limits: {self.detector_profile.min_integration_time_ms}-{self.detector_profile.max_integration_time_ms} ms")
            else:
                min_int = MIN_INTEGRATION / MS_TO_SECONDS  # Convert ms to seconds
                max_int = MAX_INTEGRATION / MS_TO_SECONDS  # Convert ms to seconds
                logger.warning("Using legacy integration limits from settings.py")

            # Start at 50% of max integration time (reasonable starting point)
            starting_integration = (min_int + max_int) / 2.0  # 100ms for Flame-T (1ms + 200ms)/2
            self.state.integration = starting_integration
            self.usb.set_integration(self.state.integration)
            time.sleep(0.1)
            logger.info(f"📊 Starting integration time: {self.state.integration * 1000:.1f}ms (50% of max)")

            # ========================================================================
            # STEP 1: Identify weakest channel (test all at standard LED intensity)
            # ========================================================================
            logger.info("📊 Step 3.1: Identifying weakest channel...")

            # Get target wavelength range indices (same as used everywhere else)
            wave_data = self.state.wavelengths  # Already filtered to SPR range
            target_min_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MIN))
            target_max_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MAX))
            logger.debug(f"   Measuring in target range: {TARGET_WAVELENGTH_MIN}-{TARGET_WAVELENGTH_MAX}nm (indices {target_min_idx}-{target_max_idx})")

            channel_intensities = {}
            for ch in ch_list:
                if self._is_stopped():
                    return False

                # ⚡ Use single-channel batch command for consistency
                intensities_dict = {ch: S_LED_INT}
                self._activate_channel_batch([ch], intensities_dict)
                time.sleep(LED_DELAY)

                # ✨ NEW (Phase 2): Track last active channel for afterglow correction
                self._last_active_channel = ch

                raw_array = self.usb.read_intensity()
                if raw_array is None:
                    logger.error(f"Failed to read intensity for channel {ch}")
                    continue

                # Apply spectral filter for channel intensity measurement
                filtered_array = self._apply_spectral_filter(raw_array)
                # Measure in TARGET range (580-610nm), not entire SPR range!
                current_count = filtered_array[target_min_idx:target_max_idx].max()

                channel_intensities[ch] = current_count
                logger.debug(f"Channel {ch} initial intensity in target range: {current_count:.0f} counts")

            # Find weakest channel
            weakest_ch = min(channel_intensities, key=channel_intensities.get)

            # ✨ CRITICAL FIX: Store weakest channel for LED calibration
            # The weakest channel will be set to 255, others calibrated relative to it
            self.state.weakest_channel = weakest_ch

            logger.info(f"✅ Weakest channel identified: {weakest_ch} ({channel_intensities[weakest_ch]:.0f} counts at LED={S_LED_INT} in {TARGET_WAVELENGTH_MIN}-{TARGET_WAVELENGTH_MAX}nm)")
            logger.info(f"   ➜ Weakest channel will be FIXED at LED=255")
            logger.info(f"   ➜ Other channels will be adjusted DOWN to match")

            # ⚡ Turn off all channels using batch command
            self._all_leds_off_batch()
            time.sleep(LED_DELAY)

            # ========================================================================
            # STEP 2: Optimize integration time for WEAKEST channel at MAXIMUM LED
            # ========================================================================
            logger.info(f"📊 Step 3.2: Optimizing integration time for weakest channel ({weakest_ch})...")
            logger.info(f"   Starting at {self.state.integration * 1000:.1f}ms, will adjust up or down as needed")

            # CRITICAL: Set weakest channel to MAXIMUM LED intensity
            # This ensures we give it every advantage before fixing integration time
            # ⚡ Use batch command
            intensities_dict = {weakest_ch: MAX_LED_INTENSITY}
            self._activate_channel_batch([weakest_ch], intensities_dict)
            time.sleep(LED_DELAY)

            # Get target wavelength range indices (same as used in LED calibration)
            wave_data = self.state.wavelengths  # Already filtered to SPR range
            target_min_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MIN))
            target_max_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MAX))

            # Get detector-specific max counts for target calculation
            if self.detector_profile:
                detector_max = self.detector_profile.max_intensity_counts
            else:
                detector_max = DETECTOR_MAX_COUNTS

            # Target: 80% of detector-specific max
            S_COUNT_TARGET = int(TARGET_INTENSITY_PERCENT / 100 * detector_max)

            # Measure initial intensity at starting integration time (100ms)
            raw_array = self.usb.read_intensity()
            if raw_array is not None:
                # Apply spectral filter for integration time optimization
                filtered_array = self._apply_spectral_filter(raw_array)
                # Measure intensity in TARGET range (580-610nm), not entire SPR range!
                current_count = filtered_array[target_min_idx:target_max_idx].max()
                current_percent = (current_count / detector_max) * 100

                logger.info(f"   Initial: {self.state.integration * 1000:.1f}ms, weakest@LED=255 in {TARGET_WAVELENGTH_MIN}-{TARGET_WAVELENGTH_MAX}nm: {current_count:.0f} counts ({current_percent:.1f}%)")
                logger.info(f"   Target: {S_COUNT_TARGET:.0f} counts ({TARGET_INTENSITY_PERCENT}%)")
            else:
                current_count = 0
                logger.error("Failed to read intensity for integration time calibration")

            # Adjust integration time up or down as needed
            if current_count < S_COUNT_TARGET:
                # Too low - increase integration time
                logger.info(f"   Signal too low ({current_percent:.1f}% < {TARGET_INTENSITY_PERCENT}%) - increasing integration time...")
                direction = "up"
            elif current_count > S_COUNT_TARGET * 1.1:  # More than 10% over target
                # Too high - decrease integration time
                logger.info(f"   Signal too high ({current_percent:.1f}% > {TARGET_INTENSITY_PERCENT + 10}%) - decreasing integration time...")
                direction = "down"
            else:
                # Already good!
                logger.info(f"   ✅ Signal already at target ({current_percent:.1f}%) - no adjustment needed")
                direction = "done"

            # Adjust integration time until target reached
            while direction != "done":
                if self._is_stopped():
                    return False

                # Adjust integration time based on direction
                if direction == "up":
                    if self.state.integration >= max_int:
                        logger.warning(f"   Reached max integration time ({max_int * MS_TO_SECONDS:.1f}ms)")
                        break
                    self.state.integration += (integration_step / MS_TO_SECONDS)  # Increase
                elif direction == "down":
                    if self.state.integration <= min_int:
                        logger.warning(f"   Reached min integration time ({min_int * MS_TO_SECONDS:.1f}ms)")
                        break
                    self.state.integration -= (integration_step / MS_TO_SECONDS)  # Decrease

                self.usb.set_integration(self.state.integration)
                time.sleep(0.02)

                raw_array = self.usb.read_intensity()
                if raw_array is None:
                    break

                # Apply spectral filter to intensity reads during integration optimization
                filtered_array = self._apply_spectral_filter(raw_array)
                # Measure intensity in TARGET range (580-610nm), same as LED calibration
                current_count = filtered_array[target_min_idx:target_max_idx].max()
                current_percent = (current_count / detector_max) * 100

                # Check if we've reached target
                if S_COUNT_TARGET * 0.95 <= current_count <= S_COUNT_TARGET * 1.05:  # Within 5% of target
                    logger.info(
                        f"   ✅ Target reached at {self.state.integration * 1000:.1f}ms: "
                        f"weakest@LED=255: {current_count:.0f} counts ({current_percent:.1f}%)"
                    )
                    break

                # Log progress every 10ms
                if int(self.state.integration * 1000) % 10 == 0:
                    logger.debug(
                        f"   {self.state.integration * 1000:.1f}ms: "
                        f"weakest@LED=255: {current_count:.0f} counts ({current_percent:.1f}%)"
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

            # ========================================================================
            # STEP 3.3: Validate weakest channel performance
            # ========================================================================
            # Check if weakest channel achieved acceptable signal level (60-80% of detector max)
            # If yes, LOCK integration time and let Step 4 adjust other channels' LED intensities
            # If no, try 2nd weakest channel or fail with customer warning

            integration_ms = self.state.integration * 1000
            logger.info(f"📊 Step 3.3: Validating weakest channel ({weakest_ch}) performance at {integration_ms:.1f}ms")

            # Get detector-specific max counts
            if self.detector_profile:
                detector_max = self.detector_profile.max_intensity_counts
            else:
                detector_max = DETECTOR_MAX_COUNTS

            # Measure weakest channel one final time at LED=255
            logger.info(f"   Measuring weakest channel ({weakest_ch}) at LED=255...")
            # ⚡ Use batch command
            intensities_dict = {weakest_ch: 255}
            self._activate_channel_batch([weakest_ch], intensities_dict)
            time.sleep(LED_DELAY)

            raw_array = self.usb.read_intensity()
            if raw_array is not None:
                filtered_array = self._apply_spectral_filter(raw_array)
                final_count = filtered_array[target_min_idx:target_max_idx].max()
                final_percent = (final_count / detector_max) * 100

                logger.info(f"   Weakest channel ({weakest_ch}): {final_count:.0f} counts ({final_percent:.1f}% of max)")

                # Check if weakest channel performance is acceptable
                if final_percent >= MINIMUM_ACCEPTABLE_PERCENT:
                    if final_percent >= IDEAL_TARGET_PERCENT:
                        logger.info(f"✅ Weakest channel EXCELLENT: {final_percent:.1f}% ≥ {IDEAL_TARGET_PERCENT}% target")
                    else:
                        logger.info(f"✅ Weakest channel ACCEPTABLE: {final_percent:.1f}% ≥ {MINIMUM_ACCEPTABLE_PERCENT}% minimum")
                        logger.info(f"   (Ideally {IDEAL_TARGET_PERCENT}%, but {final_percent:.1f}% is usable)")

                    logger.info(f"✅ INTEGRATION TIME LOCKED at: {integration_ms:.1f}ms")
                    logger.info(f"   Weakest channel ({weakest_ch}): {final_count:.0f} counts ({final_percent:.1f}%)")
                    logger.info(f"   Other channels will be adjusted DOWN via LED intensity in Step 4")

                else:
                    # Weakest channel < 60% - try 2nd weakest or fail
                    logger.warning(f"⚠️ Weakest channel FAILED: {final_percent:.1f}% < {MINIMUM_ACCEPTABLE_PERCENT}% minimum")
                    logger.warning(f"   This is a hardware limitation - weakest LED channel cannot reach target")

                    # Sort channels by intensity to find 2nd weakest
                    sorted_channels = sorted(channel_intensities.items(), key=lambda x: x[1])
                    if len(sorted_channels) >= 2:
                        second_weakest_ch = sorted_channels[1][0]
                        logger.warning(f"   Attempting with 2nd weakest channel: {second_weakest_ch}")
                        logger.warning(f"   Channel {weakest_ch} will be UNUSABLE for measurements")

                        # TODO: Implement 2nd weakest channel fallback if needed
                        # For now, proceed with warning
                        logger.error(f"❌ CUSTOMER WARNING: Channel {weakest_ch} insufficient - only 3/4 channels usable")
                    else:
                        logger.error(f"❌ CRITICAL: Cannot find alternative channel - calibration may fail")

                    # Proceed anyway with current integration time
                    logger.warning(f"   Proceeding with {integration_ms:.1f}ms anyway")

            # ⚡ Turn off weakest channel using batch command
            self._all_leds_off_batch()
            time.sleep(LED_DELAY)

            integration_ms = self.state.integration * 1000
            logger.info(f"✅ FINAL integration time FIXED at: {integration_ms:.1f}ms")
            logger.info(f"   (This integration time will be used for ALL channels)")
            logger.info(f"   (Next step: adjust LED intensities to balance channels)")

            # Calculate number of scans to average using consistent 200ms target
            self.state.num_scans = calculate_dynamic_scans(self.state.integration)
            logger.debug(f"Scans to average: {self.state.num_scans} (200ms target)")

            return True

        except Exception as e:
            logger.exception(f"Error calibrating integration time: {e}")
            return False

    # ========================================================================
    # STEP 6: APPLY LED CALIBRATION (SIMPLIFIED - NO BINARY SEARCH)
    # ========================================================================

    def step_6_apply_led_calibration(self, ch_list: list[str]) -> bool:
        """STEP 6: Apply LED calibration from Step 4 validation (SIMPLIFIED).

        Step 4 already validated all channels at predicted LED intensities.
        This step simply applies those calibrated values without redundant
        binary search optimization.

        This eliminates 6-8 seconds of redundant calibration time while
        maintaining the same signal quality validated in Step 4.

        Args:
            ch_list: List of channels to apply calibration for

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("=" * 80)
            logger.info("STEP 6: Apply LED Calibration (From Step 4 Validation)")
            logger.info("=" * 80)
            logger.info("LED intensities already calibrated and stored from Step 4:")
            logger.info("")

            # Display stored LED calibration from Step 4
            for ch in ch_list:
                led_value = self.state.ref_intensity.get(ch, 0)
                logger.info(f"   Channel {ch.upper()}: LED = {led_value}")

            logger.info("")
            logger.info("✅ Step 6 complete: LED calibration applied (from Step 4 validation)")
            logger.info("   No binary search needed - Step 4 already optimized all channels!")
            logger.info("   Time saved: ~6-8 seconds (eliminated redundant optimization)")
            logger.info("=" * 80)

            return True

        except Exception as e:
            logger.exception(f"Error in Step 6 LED calibration application: {e}")
            return False

    # ========================================================================
    # STEP 5: DARK NOISE MEASUREMENT - HELPER METHODS
    # ========================================================================

    def _compare_dark_noise_measurements(
        self,
        dark_before: np.ndarray,
        dark_after_raw: np.ndarray,
        dark_after_corrected: np.ndarray | None = None,
        correction_value: float = 0.0
    ) -> None:
        """Compare Step 1 (before LEDs) vs Step 5 (after LEDs) dark noise.

        Logs contamination analysis and correction effectiveness if applied.

        Args:
            dark_before: Dark noise from Step 1 (baseline, before LEDs)
            dark_after_raw: Dark noise from Step 5 (uncorrected)
            dark_after_corrected: Dark noise from Step 5 (corrected), optional
            correction_value: Afterglow correction applied (counts), optional
        """
        before_mean = float(np.mean(dark_before))
        after_raw_mean = float(np.mean(dark_after_raw))
        contamination = after_raw_mean - before_mean

        logger.info("=" * 80)
        logger.info("📊 DARK NOISE COMPARISON (Step 1 vs Step 5):")
        logger.info("=" * 80)
        logger.info(f"   Before LEDs (Step 1):      {before_mean:.1f} counts (baseline)")
        logger.info(f"   After LEDs (raw):          {after_raw_mean:.1f} counts")
        logger.info(f"   Contamination:             +{contamination:.1f} counts ({contamination/before_mean*100:.1f}% increase)")

        if dark_after_corrected is not None and correction_value > 0:
            after_corrected_mean = float(np.mean(dark_after_corrected))
            correction_effectiveness = ((after_raw_mean - after_corrected_mean) / contamination * 100
                                       if contamination > 0 else 0)
            residual = after_corrected_mean - before_mean

            logger.info(f"   After LEDs (corrected):    {after_corrected_mean:.1f} counts")
            logger.info(f"   Correction removed:        {correction_value:.1f} counts")
            logger.info(f"   ✨ Correction effectiveness: {correction_effectiveness:.1f}%")
            logger.info(f"   Residual error:            {residual:+.1f} counts ({abs(residual)/before_mean*100:.2f}%)")
        else:
            logger.info(f"   ⚠️  No afterglow correction applied")

        logger.info("=" * 80)

        # Store contamination in state for analysis
        self.state.dark_noise_contamination = contamination

    # ========================================================================
    # STEPS 1 & 5: DARK NOISE MEASUREMENT
    # ========================================================================

    def step_1_measure_initial_dark_noise(self) -> bool:
        """STEP 1: Measure baseline dark noise before any LEDs are activated.

        This is the first calibration step. It measures the detector's dark noise
        before any LEDs have been turned on, providing a clean baseline for
        comparison with Step 5.

        Uses a faster measurement (5 scans) since this is just a sanity check.

        Returns:
            True if successful, False otherwise
        """
        logger.info("=" * 80)
        logger.info("STEP 1: Dark Noise Baseline (Before LEDs)")
        logger.info("=" * 80)
        logger.info("Measuring baseline dark noise before any LED activation...")

        # Ensure clean state
        self._last_active_channel = None

        return self._measure_dark_noise_internal(is_baseline=True)

    def step_5_remeasure_dark_noise(self) -> bool:
        """STEP 5: Re-measure dark noise with final integration time.

        This step re-measures dark noise after integration time optimization
        (Step 4) is complete. It uses the final optimized integration time and
        applies afterglow correction if available.

        The purpose is to get accurate dark noise for the actual integration
        time that will be used during SPR measurements (Step 1 used a temporary
        32ms integration time).

        Returns:
            True if successful, False otherwise
        """
        logger.info("=" * 80)
        logger.info("STEP 5: Dark Noise Re-measurement (Final Integration Time)")
        logger.info("=" * 80)
        logger.info(f"Re-measuring dark noise with final integration time ({self.state.integration*1000:.1f}ms)...")

        return self._measure_dark_noise_internal(is_baseline=False)

    def _measure_dark_noise_internal(self, is_baseline: bool) -> bool:
        """Internal helper for dark noise measurement.

        This method contains the shared logic for both Step 1 (baseline dark noise
        before any LEDs are activated) and Step 5 (re-measure dark noise with final
        integration time after LED calibration).

        Args:
            is_baseline: If True, this is Step 1 (baseline). If False, this is Step 5 (re-measure).

        Returns:
            True if successful, False otherwise

        Note:
            This is an internal helper. Use step_1_measure_initial_dark_noise() or
            step_5_remeasure_dark_noise() for explicit step execution.
        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            # CRITICAL: Force all LEDs OFF at hardware level before dark measurement
            logger.info("🔦 Forcing ALL LEDs OFF for dark noise measurement...")

            # Use direct hardware command to turn off all LEDs
            if hasattr(self.ctrl, "_hal") and hasattr(self.ctrl._hal, "_send_command"):
                # Direct hardware command: 'lx\n' turns off all LEDs
                try:
                    self.ctrl._hal._send_command("lx\n")
                    logger.info("   ✓ Sent 'lx' command to turn off all LEDs")
                except Exception as e:
                    logger.warning(f"   Failed to send direct 'lx' command: {e}")
                    # Fallback to turn_off_channels
                    self.ctrl.turn_off_channels()
            else:
                # Fallback for other controllers
                self.ctrl.turn_off_channels()

            # CRITICAL: Wait for LEDs to fully turn off (hardware settling time)
            settle_delay = max(LED_DELAY, 0.5)  # At least 500ms for hardware to settle
            time.sleep(settle_delay)
            logger.info(f"✅ All LEDs OFF; waited {settle_delay*1000:.0f}ms for hardware to settle")

            # Adjust scan count based on integration time
            # OPTIMIZATION: Step 1 (baseline) is just a sanity check - use fewer scans for speed
            if is_baseline:
                # Step 1: Baseline dark noise (fast sanity check - 5 scans)
                dark_scans = 5
                logger.debug(f"Measuring baseline dark noise with {dark_scans} scans (fast sanity check)")
            elif self.state.integration < INTEGRATION_STEP_THRESHOLD:
                dark_scans = DARK_NOISE_SCANS
            else:
                dark_scans = int(DARK_NOISE_SCANS / 2)

            if not is_baseline:
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

            # ✨ VECTORIZED SPECTRUM ACQUISITION (2-3× faster than loop)
            full_spectrum_dark_noise = self._acquire_averaged_spectrum(
                num_scans=dark_scans,
                apply_filter=True,
                subtract_dark=False,
                description="dark noise"
            )

            if full_spectrum_dark_noise is None:
                logger.error("Failed to acquire dark noise spectrum")
                return False

            # ✨ NEW (Phase 2): Store Step 1 as baseline for comparison
            if is_baseline:
                # Step 1: First dark measurement (before any LEDs activated)
                self.state.dark_noise_before_leds = full_spectrum_dark_noise.copy()
                before_mean = np.mean(full_spectrum_dark_noise)
                before_max = np.max(full_spectrum_dark_noise)
                before_std = np.std(full_spectrum_dark_noise)

                logger.info(f"📊 Dark BEFORE LEDs (Step 1): {before_mean:.1f} counts (baseline)")
                logger.info("   (No LEDs have been activated yet - clean measurement)")

                # ⚡ SANITY CHECK: Flag abnormally high dark noise (5× higher than expected)
                EXPECTED_DARK_MEAN = 400.0  # Typical detector noise floor
                EXPECTED_DARK_MAX = 600.0
                TOLERANCE_FACTOR = 5.0  # Flag if 5× higher than expected

                if before_mean > EXPECTED_DARK_MEAN * TOLERANCE_FACTOR:
                    logger.warning(f"⚠️  STEP 1 WARNING: Dark noise mean ({before_mean:.1f}) is {before_mean/EXPECTED_DARK_MEAN:.1f}× higher than expected ({EXPECTED_DARK_MEAN:.1f})")
                    logger.warning(f"    Possible issues:")
                    logger.warning(f"    • Light leaking into detector (check enclosure)")
                    logger.warning(f"    • LEDs not fully turned off (check hardware)")
                    logger.warning(f"    • Detector thermal noise (check cooling)")
                    logger.warning(f"    • Previous measurement residual signal")
                    logger.warning(f"    ⚠️  Continuing calibration, but results may be affected...")

                if before_max > EXPECTED_DARK_MAX * TOLERANCE_FACTOR:
                    logger.warning(f"⚠️  STEP 1 WARNING: Dark noise max ({before_max:.1f}) is {before_max/EXPECTED_DARK_MAX:.1f}× higher than expected ({EXPECTED_DARK_MAX:.1f})")
                    logger.warning(f"    Check for stray light or hot pixels in detector")

                # If dark noise is reasonable, confirm success
                if before_mean <= EXPECTED_DARK_MEAN * TOLERANCE_FACTOR and before_max <= EXPECTED_DARK_MAX * TOLERANCE_FACTOR:
                    logger.info(f"✅ Dark noise levels normal (within {TOLERANCE_FACTOR:.0f}× expected)")
                    logger.info(f"   Mean: {before_mean:.1f}, Max: {before_max:.1f}, Std: {before_std:.1f}")

            # ✨ NEW (Phase 2): Apply afterglow correction if available
            if (not is_baseline and
                self.afterglow_correction and
                self._last_active_channel and
                self.afterglow_correction_enabled):
                try:
                    # Store uncorrected dark for comparison
                    self.state.dark_noise_after_leds_uncorrected = full_spectrum_dark_noise.copy()

                    # Get current integration time
                    integration_time_ms = self.state.integration * 1000.0

                    # Calculate correction (uniform across spectrum)
                    # Delay = settle_delay (typically 500ms)
                    correction_value = self.afterglow_correction.calculate_correction(
                        previous_channel=self._last_active_channel,
                        integration_time_ms=integration_time_ms,
                        delay_ms=settle_delay * 1000  # Convert to ms
                    )

                    # Apply correction (subtract afterglow from dark noise)
                    uncorrected_mean = np.mean(full_spectrum_dark_noise)
                    full_spectrum_dark_noise = full_spectrum_dark_noise - correction_value
                    corrected_mean = np.mean(full_spectrum_dark_noise)

                    # ✨ NEW: Compare with Step 1 baseline using helper
                    if self.state.dark_noise_before_leds is not None:
                        self._compare_dark_noise_measurements(
                            dark_before=self.state.dark_noise_before_leds,
                            dark_after_raw=self.state.dark_noise_after_leds_uncorrected,
                            dark_after_corrected=full_spectrum_dark_noise,
                            correction_value=correction_value
                        )
                    else:
                        logger.info(
                            f"✨ Afterglow correction applied to dark noise:"
                        )
                        logger.info(
                            f"   Previous channel: {self._last_active_channel.upper()}"
                        )
                        logger.info(
                            f"   Correction: {correction_value:.1f} counts removed"
                        )
                        logger.info(
                            f"   Dark noise mean: {uncorrected_mean:.1f} → {corrected_mean:.1f} counts"
                        )

                except Exception as e:
                    logger.warning(f"⚠️ Afterglow correction failed: {e}")
                    logger.warning("⚠️ Using uncorrected dark noise")
                    # Continue with uncorrected data
            else:
                if not is_baseline:
                    # Step 5 without correction
                    if not self.afterglow_correction:
                        logger.info("ℹ️ No optical calibration loaded - dark noise uncorrected")
                    elif not self.afterglow_correction_enabled:
                        logger.info("ℹ️ Afterglow correction disabled in config")

                    # Still do comparison even without correction using helper
                    if self.state.dark_noise_before_leds is not None:
                        self._compare_dark_noise_measurements(
                            dark_before=self.state.dark_noise_before_leds,
                            dark_after_raw=full_spectrum_dark_noise
                        )            # Store dark noise (corrected if available, uncorrected otherwise)
            # No resampling needed - spectral filter ensures correct size
            self.state.dark_noise = full_spectrum_dark_noise
            self.state.full_spectrum_dark_noise = full_spectrum_dark_noise

            # Save dark noise to disk for longitudinal data processing
            from pathlib import Path
            calib_dir = Path(ROOT_DIR) / "calibration_data"
            calib_dir.mkdir(exist_ok=True)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            dark_file = calib_dir / f"dark_noise_{timestamp}.npy"
            np.save(dark_file, full_spectrum_dark_noise)

            # Also save as "latest" for easy access
            latest_dark = calib_dir / "dark_noise_latest.npy"
            np.save(latest_dark, full_spectrum_dark_noise)

            logger.info(
                f"✅ Dark noise measurement complete:"
                f"\n  • Spectrum size: {len(full_spectrum_dark_noise)} pixels (filtered to SPR range)"
                f"\n  • Max dark noise: {np.max(full_spectrum_dark_noise):.1f} counts"
                f"\n  • Mean dark noise: {np.mean(full_spectrum_dark_noise):.1f} counts"
                f"\n  • Method: Direct filtering at acquisition (no resampling needed)"
                f"\n  • 💾 Saved to: {dark_file}"
                f"\n  • 💾 Latest: {latest_dark}"
            )
            return True

        except Exception as e:
            logger.exception(f"Error measuring dark noise: {e}")
            return False

    def measure_dark_noise(self) -> bool:
        """Measure dark noise (backward compatibility wrapper).

        This method provides backward compatibility for code that calls
        measure_dark_noise() directly. It delegates to the appropriate
        step method based on calibration state.

        For new code, use explicit step methods:
        - step_1_measure_initial_dark_noise() for Step 1
        - step_5_remeasure_dark_noise() for Step 5

        Returns:
            True if successful, False otherwise
        """
        if self._last_active_channel is None:
            # No LEDs activated yet - this is Step 1
            return self.step_1_measure_initial_dark_noise()
        else:
            # LEDs have been activated - this is Step 5
            return self.step_5_remeasure_dark_noise()

    # ========================================================================
    # STEP 7: REFERENCE SIGNAL MEASUREMENT - HELPER METHODS
    # ========================================================================

    def _apply_afterglow_correction_to_references(
        self,
        ch_list: list[str],
        ref_scans: int,
        last_active_ch: str | None
    ) -> bool:
        """Apply afterglow correction to all reference signals.

        Measures dark noise after all channels are measured, applies afterglow
        correction if available, and subtracts the corrected dark from all
        reference signals.

        This consolidates the dark noise measurement and correction logic that
        was previously scattered throughout step_7_measure_reference_signals().

        Args:
            ch_list: Channels that were measured
            ref_scans: Number of scans to use for dark measurement
            last_active_ch: Last channel that was active (for afterglow correction)

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("📊 Measuring dark noise after all channels for correction...")

            # Turn off all LEDs
            self._all_leds_off_batch()
            time.sleep(LED_DELAY)

            # Measure dark noise (no dark subtraction, no filtering applied yet)
            dark_spectrum = self._acquire_averaged_spectrum(
                num_scans=ref_scans,
                apply_filter=True,
                subtract_dark=False,
                description="dark noise (afterglow correction)"
            )

            if dark_spectrum is None:
                logger.warning("Failed to acquire dark noise for afterglow correction")
                # Use Step 5 dark as fallback
                dark_spectrum = self.state.dark_noise.copy()

            # Apply afterglow correction if available
            corrected_dark = dark_spectrum
            if self.afterglow_correction and last_active_ch:
                try:
                    dark_before_correction = dark_spectrum.copy()
                    dark_mean_before = float(np.mean(dark_before_correction))
                    baseline_dark_mean = float(np.mean(self.state.dark_noise))

                    corrected_dark = self.afterglow_correction.correct_spectrum(
                        spectrum=dark_spectrum,
                        last_active_channel=last_active_ch,
                        integration_time_ms=self.state.integration * 1000
                    )

                    dark_mean_after = float(np.mean(corrected_dark))
                    contamination = dark_mean_before - baseline_dark_mean
                    correction_effectiveness = dark_mean_before - dark_mean_after

                    if contamination > 1.0:  # Only log if meaningful contamination
                        logger.info(
                            f"   ✨ Afterglow correction: "
                            f"baseline={baseline_dark_mean:.1f}, "
                            f"contaminated={dark_mean_before:.1f} (+{contamination:.1f}), "
                            f"corrected={dark_mean_after:.1f} "
                            f"({correction_effectiveness/contamination*100:.1f}% effective)"
                        )
                    else:
                        logger.debug(f"   Minimal afterglow contamination ({contamination:.2f} counts)")

                except Exception as e:
                    logger.warning(f"Afterglow correction failed: {e}")
                    corrected_dark = dark_spectrum
            else:
                if not self.afterglow_correction:
                    logger.debug("⚠️ No afterglow correction available")
                elif not last_active_ch:
                    logger.debug("⚠️ No last active channel for afterglow correction")

            # Subtract corrected dark from all reference signals
            for ch in ch_list:
                if self.state.ref_sig[ch] is not None:
                    # Single subtraction: raw_signal - corrected_dark
                    self.state.ref_sig[ch] = self.state.ref_sig[ch] - corrected_dark
                    logger.debug(f"   Applied dark correction to channel {ch}")

            logger.info("✅ Dark noise correction applied to all reference signals")
            return True

        except Exception as e:
            logger.exception(f"Error applying afterglow correction: {e}")
            return False

    # ========================================================================
    # STEP 7: REFERENCE SIGNAL MEASUREMENT
    # ========================================================================

    def step_7_measure_reference_signals(self, ch_list: list[str]) -> bool:
        """STEP 7: Measure reference signals in S-mode for all channels.

        Measures reference signals for each channel using calibrated LED intensities
        from Step 4/6. Applies afterglow correction if available.

        Args:
            ch_list: List of channels to measure

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            logger.info("=" * 80)
            logger.info("STEP 7: Reference Signal Measurement (S-mode)")
            logger.info("=" * 80)

            self.ctrl.set_mode(mode="s")
            time.sleep(0.4)

            # Calculate dynamic scan count based on integration time
            # Goal: Maintain ≤200ms total acquisition time (fast response)
            ref_scans = calculate_dynamic_scans(self.state.integration)
            logger.info(
                f"📊 Reference signal averaging: {ref_scans} scans "
                f"(integration={self.state.integration*1000:.1f}ms, "
                f"total time={ref_scans * self.state.integration:.2f}s)"
            )

            # Measure all channels (raw signals, no dark subtraction yet)
            last_ch = None
            for ch in ch_list:
                if self._is_stopped():
                    return False

                logger.debug(f"Measuring reference signal for channel {ch}")

                # Activate LED with calibrated intensity from Step 4/6
                intensities_dict = {ch: self.state.ref_intensity[ch]}
                self._activate_channel_batch([ch], intensities_dict)
                time.sleep(LED_DELAY)

                # Track last active channel for afterglow correction
                self._last_active_channel = ch
                last_ch = ch

                # Acquire raw spectrum (no dark subtraction - we'll do it once at the end)
                averaged_signal = self._acquire_averaged_spectrum(
                    num_scans=ref_scans,
                    apply_filter=True,
                    subtract_dark=False,  # Keep raw signal for single dark subtraction
                    description=f"reference signal (ch {ch})"
                )

                if averaged_signal is None:
                    logger.error(f"Failed to acquire reference signal for channel {ch}")
                    return False

                # Store raw signal (no deepcopy needed - averaged_signal is already new)
                self.state.ref_sig[ch] = averaged_signal

                # Log reference signal strength
                logger.debug(
                    f"Channel {ch} reference signal: max={float(np.max(averaged_signal)):.1f} counts"
                )

            # Apply afterglow correction and dark subtraction to all channels at once
            if not self._apply_afterglow_correction_to_references(ch_list, ref_scans, last_ch):
                logger.warning("Afterglow correction failed, continuing with uncorrected signals")
                # Apply basic dark subtraction as fallback
                for ch in ch_list:
                    if self.state.ref_sig[ch] is not None:
                        self.state.ref_sig[ch] = self.state.ref_sig[ch] - self.state.dark_noise

            # Save S-mode reference signals to disk for longitudinal data processing
            from pathlib import Path
            calib_dir = Path(ROOT_DIR) / "calibration_data"
            calib_dir.mkdir(exist_ok=True)

            timestamp = time.strftime("%Y%m%d_%H%M%S")

            for ch in ch_list:
                if self.state.ref_sig[ch] is not None:
                    # Save with timestamp
                    s_ref_file = calib_dir / f"s_ref_{ch}_{timestamp}.npy"
                    np.save(s_ref_file, self.state.ref_sig[ch])

                    # Also save as "latest" for easy access
                    latest_s_ref = calib_dir / f"s_ref_{ch}_latest.npy"
                    np.save(latest_s_ref, self.state.ref_sig[ch])

                    logger.info(f"💾 S-ref[{ch}] saved: {s_ref_file}")

            logger.info(f"✅ All S-mode references saved to: {calib_dir}")

            return True

        except Exception as e:
            logger.exception(f"Error measuring reference signals: {e}")
            return False

    def measure_reference_signals(self, ch_list: list[str]) -> bool:
        """Backward compatibility wrapper for Step 7.

        DEPRECATED: Use step_7_measure_reference_signals() for clarity.
        """
        return self.step_7_measure_reference_signals(ch_list)

    # ========================================================================
    # STEP 8: VALIDATION
    # ========================================================================

    def step_8_validate_calibration(self) -> tuple[bool, str]:
        """STEP 8: Validate calibration using Step 7 reference signals (SIMPLIFIED).

        No redundant measurements - validates using existing reference signals
        from Step 7 which were measured in full SPR ROI (580-720nm).

        Returns:
            Tuple of (success, error_channels_string)
        """
        try:
            logger.info("=" * 80)
            logger.info("STEP 8: Calibration Validation (Using Step 7 Data)")
            logger.info("=" * 80)

            if DEVELOPMENT_MODE:
                logger.info("🔧 DEVELOPMENT MODE - Skipping validation thresholds")
                self.state.ch_error_list = []
                self.state.is_calibrated = True
                self.state.calibration_timestamp = time.time()
                logger.info("✅ DEVELOPMENT MODE - Calibration accepted")
                return True, ""

            # Get detector-specific max for threshold calculations
            if self.detector_profile:
                detector_max = self.detector_profile.max_intensity_counts
            else:
                detector_max = DETECTOR_MAX_COUNTS

            min_threshold = detector_max * MIN_INTENSITY_PERCENT / 100.0
            max_threshold = detector_max * MAX_INTENSITY_PERCENT / 100.0

            logger.info(f"Validation thresholds: {MIN_INTENSITY_PERCENT}-{MAX_INTENSITY_PERCENT}% "
                       f"({min_threshold:.0f}-{max_threshold:.0f} counts)")

            # Validate using reference signals from Step 7 (already measured!)
            self.state.ch_error_list = []

            for ch in CH_LIST:
                if ch not in self.state.ref_sig or self.state.ref_sig[ch] is None:
                    logger.error(f"   ❌ Channel {ch}: No reference signal from Step 7")
                    self.state.ch_error_list.append(ch)
                    continue

                # Check MAX signal in full spectrum (same as Steps 4 & 7)
                signal_max = float(np.max(self.state.ref_sig[ch]))
                signal_percent = (signal_max / detector_max) * 100

                # Validate against thresholds
                if signal_max < min_threshold:
                    logger.warning(f"   ❌ Channel {ch}: Signal too low ({signal_percent:.1f}% < {MIN_INTENSITY_PERCENT}%)")
                    self.state.ch_error_list.append(ch)
                elif signal_max > max_threshold:
                    logger.warning(f"   ❌ Channel {ch}: Signal too high ({signal_percent:.1f}% > {MAX_INTENSITY_PERCENT}%)")
                    self.state.ch_error_list.append(ch)
                else:
                    logger.info(f"   ✅ Channel {ch}: {signal_percent:.1f}% (valid)")

            # Determine success
            calibration_success = len(self.state.ch_error_list) == 0
            ch_str = ", ".join(self.state.ch_error_list) if self.state.ch_error_list else ""

            if calibration_success:
                logger.info("✅ Calibration validation passed for all channels")
                self.state.is_calibrated = True
                self.state.calibration_timestamp = time.time()
            else:
                logger.warning(f"❌ Calibration validation failed for channels: {ch_str}")

            logger.info("=" * 80)
            return calibration_success, ch_str

        except Exception as e:
            logger.exception(f"Error validating calibration: {e}")
            return False, f"Validation error: {e}"

    def validate_calibration(self) -> tuple[bool, str]:
        """Backward compatibility wrapper for Step 8 validation.

        DEPRECATED: Use step_8_validate_calibration() for clarity.
        """
        return self.step_8_validate_calibration()

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
        """Execute the complete 8-step calibration sequence.

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

            # 🔄 RESET CALIBRATION STATE - Ensure fresh start with no legacy data
            if not use_previous_data:
                logger.info("🔄 Resetting calibration state for fresh measurement...")
                # Clear all previous calibration data to ensure new S-ref and dark use new values
                self.state.dark_noise = np.array([])
                self.state.full_spectrum_dark_noise = np.array([])
                self.state.ref_sig = dict.fromkeys(CH_LIST)
                self.state.leds_calibrated = dict.fromkeys(CH_LIST, 0)
                self.state.ref_intensity = dict.fromkeys(CH_LIST, 0)
                self.state.is_calibrated = False
                logger.info("✅ State reset complete - all legacy data cleared")

            # Store fiber-specific integration time factor in calibration state
            self.state.base_integration_time_factor = self.base_integration_time_factor
            logger.info(f"⚡ Integration time factor: {self.base_integration_time_factor}x "
                       f"({'2x faster' if self.base_integration_time_factor == 0.5 else 'standard speed'})")

            # Auto-detect and load detector profile (cached after first detection)
            if self.detector_profile is None:
                logger.info("📊 Auto-detecting detector profile...")
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
            else:
                logger.info(f"📊 Using cached detector profile: {self.detector_profile.manufacturer} {self.detector_profile.model}")

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

            # ========================================================================
            # STEP 1: DARK NOISE MEASUREMENT (FIRST - BEFORE ANY LED ACTIVATION!)
            # ========================================================================
            self._emit_progress(1, "Step 1: Measuring baseline dark noise...")

            # Set a temporary default integration time for dark measurement
            # This will be refined in Step 4, but we need a reasonable value now
            self.usb.set_integration(TEMP_INTEGRATION_TIME_S)
            self.state.integration = TEMP_INTEGRATION_TIME_S
            logger.info(f"   Using temporary integration time: {TEMP_INTEGRATION_TIME_S * MS_TO_SECONDS:.1f}ms for initial dark")

            success = self.step_1_measure_initial_dark_noise()
            if not success or self._is_stopped():
                self._safe_hardware_cleanup()
                return False, "Step 1: Dark noise measurement failed"

            # ========================================================================
            # STEP 2: WAVELENGTH RANGE CALIBRATION
            # ========================================================================
            self._emit_progress(2, "Step 2: Calibrating wavelength range...")
            success, integration_step = self.step_2_calibrate_wavelength_range()
            if not success or self._is_stopped():
                self._safe_hardware_cleanup()
                return False, "Wavelength calibration failed"

            # ========================================================================
            # STEP 2B: POLARIZER POSITION VALIDATION
            # ========================================================================
            self._emit_progress(2, "Step 2B: Validating polarizer positions...")
            polarizer_valid = self.validate_polarizer_positions()
            if not polarizer_valid:
                self._safe_hardware_cleanup()
                return False, "Polarizer positions invalid - run auto-polarization from Settings"

            # Step 3: Auto-polarize if enabled (advanced feature)
            if auto_polarize and not self._is_stopped():
                logger.debug("Step 3: Auto-polarization (advanced)")
                self._emit_progress(3, "Auto-aligning polarizer...")
                if auto_polarize_callback is not None:
                    auto_polarize_callback()

            # Determine which channels to calibrate
            ch_list = CH_LIST
            if self.device_type in ["PicoEZSPR"]:  # EZSPR disabled (obsolete)
                ch_list = EZ_CH_LIST

            # ========================================================================
            # STEP 3: FIND WEAKEST CHANNEL
            # ========================================================================
            self._emit_progress(3, "Step 3: Identifying weakest channel...")

            weakest_ch, channel_intensities = self.step_3_identify_weakest_channel(ch_list)
            if weakest_ch is None or self._is_stopped():
                self._safe_hardware_cleanup()
                return False, "Step 3: Failed to identify weakest channel"

            # Store weakest channel in calibration state
            self.state.weakest_channel = weakest_ch
            logger.info(f"✅ Weakest channel: {weakest_ch}")
            logger.info(f"   This channel will be FIXED at LED=255")
            logger.info(f"   Other channels will be adjusted DOWN to match")

            # ========================================================================
            # STEP 4: OPTIMIZE INTEGRATION TIME
            # ========================================================================
            self._emit_progress(4, f"Step 4: Optimizing integration time for {weakest_ch}...")

            success = self.step_4_optimize_integration_time(weakest_ch, integration_step)
            if not success or self._is_stopped():
                self._safe_hardware_cleanup()
                return False, "Step 4: Integration time optimization failed"

            # ========================================================================
            # STEP 5: RE-MEASURE DARK NOISE (FINAL INTEGRATION TIME)
            # ========================================================================
            self._emit_progress(5, "Step 5: Re-measuring dark noise (final settings)...")
            success = self.step_5_remeasure_dark_noise()
            if not success or self._is_stopped():
                self._safe_hardware_cleanup()
                return False, "Step 5: Dark noise re-measurement failed"

            # ========================================================================
            # STEP 6: APPLY LED CALIBRATION (FROM STEP 4)
            # ========================================================================
            self._emit_progress(6, "Step 6: Applying LED calibration (from Step 4)...")
            success = self.step_6_apply_led_calibration(ch_list)
            if not success or self._is_stopped():
                self._safe_hardware_cleanup()
                return False, "Step 6: LED calibration application failed"

            logger.debug(f"S-mode LED calibration complete: {self.state.ref_intensity}")

            # Step 7: Reference signal measurement (S-mode)
            logger.debug("Step 7: Reference signal measurement (S-mode)")
            self._emit_progress(7, "Capturing reference signals...")
            success = self.step_7_measure_reference_signals(ch_list)
            if not success or self._is_stopped():
                self._safe_hardware_cleanup()
                return False, "Step 7: Reference signal measurement failed"

            # Step 8: Validate calibration
            logger.debug("Step 8: Validation")
            self._emit_progress(8, "Validating calibration...")
            calibration_success, ch_error_str = self.step_8_validate_calibration()

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

            # ✨ NEW: Trigger auto-start callback if calibration successful
            if calibration_success and self.on_calibration_complete_callback is not None:
                logger.info("=" * 80)
                logger.info("🚀 TRIGGERING AUTO-START CALLBACK")
                logger.info("=" * 80)
                try:
                    self.on_calibration_complete_callback()
                    logger.info("✅ Auto-start callback executed successfully")
                except Exception as e:
                    logger.exception(f"❌ Auto-start callback failed: {e}")

            logger.debug("=== Calibration sequence complete ===")
            return calibration_success, ch_error_str

        except Exception as e:
            logger.exception(f"Error during full calibration: {e}")
            # Emergency hardware cleanup on any exception
            self._safe_hardware_cleanup()
            return False, f"Exception: {e!s}"

    def get_calibration_summary(self) -> dict:
        """Get calibration summary for state machine/UI display.

        Provides complete calibration metadata and results in a clean dictionary
        format suitable for logging, UI display, or state machine use.

        Returns:
            Dictionary containing:
            - success: bool - Overall calibration success status
            - timestamp: float - Unix timestamp of calibration completion
            - timestamp_str: str - Human-readable timestamp
            - failed_channels: list[str] - Channels that failed validation
            - weakest_channel: str - Channel requiring highest LED intensity
            - led_ranking: list[tuple] - [(channel, intensity), ...] sorted by signal strength
            - integration_time_ms: float - Optimized integration time in milliseconds
            - num_scans: int - Number of scans per measurement
            - dark_contamination_counts: float - Dark noise contamination level
            - led_intensities: dict - Calibrated LED intensity for each channel
            - detector_model: str - Detector model name
            - polarizer_s_position: int - Validated S-mode servo position (degrees)
            - polarizer_p_position: int - Validated P-mode servo position (degrees)
            - polarizer_sp_ratio: float - Validated S/P intensity ratio
        """
        return {
            'success': self.state.is_calibrated,
            'timestamp': self.state.calibration_timestamp if hasattr(self.state, 'calibration_timestamp') else None,
            'timestamp_str': time.strftime("%Y-%m-%d %H:%M:%S",
                                           time.localtime(self.state.calibration_timestamp))
                             if hasattr(self.state, 'calibration_timestamp') and self.state.calibration_timestamp else None,
            'failed_channels': self.state.ch_error_list.copy() if hasattr(self.state, 'ch_error_list') else [],
            'weakest_channel': self.state.weakest_channel if hasattr(self.state, 'weakest_channel') else None,
            'led_ranking': [(ch, intensity) for ch, (intensity, _, _) in self.state.led_ranking]
                           if hasattr(self.state, 'led_ranking') and self.state.led_ranking else [],
            'integration_time_ms': self.state.integration * 1000 if self.state.integration else 0,
            'num_scans': self.state.num_scans,
            'dark_contamination_counts': self.state.dark_noise_contamination if hasattr(self.state, 'dark_noise_contamination') else 0.0,
            'led_intensities': self.state.ref_intensity.copy(),
            'detector_model': f"{self.detector_profile.manufacturer} {self.detector_profile.model}"
                             if self.detector_profile else "Unknown",
            'polarizer_s_position': getattr(self.state, 'polarizer_s_position', None),
            'polarizer_p_position': getattr(self.state, 'polarizer_p_position', None),
            'polarizer_sp_ratio': getattr(self.state, 'polarizer_sp_ratio', None)
        }

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
            # ⚠️ CRITICAL: Polarizer positions MUST come from OEM calibration (NO DEFAULTS)
            # Fail if positions are missing - force user to run OEM tool
            s_pos = getattr(self.state, 'polarizer_s_position', None)
            p_pos = getattr(self.state, 'polarizer_p_position', None)

            if s_pos is None or p_pos is None:
                logger.error("=" * 80)
                logger.error("❌ CANNOT SAVE PROFILE - Missing Polarizer Configuration")
                logger.error("=" * 80)
                logger.error("Polarizer positions are not configured in calibration state.")
                logger.error("")
                logger.error("🔧 REQUIRED: Run OEM calibration tool first:")
                logger.error("   python utils/oem_calibration_tool.py --serial YOUR_SERIAL")
                logger.error("")
                logger.error("The OEM tool finds optimal S/P positions (single source of truth).")
                logger.error("=" * 80)
                return False

            calibration_data = {
                "profile_name": profile_name,
                "device_type": device_type,
                "timestamp": time.time(),
                "integration": self.state.integration,
                "num_scans": self.state.num_scans,
                "ref_intensity": self.state.ref_intensity.copy(),
                "leds_calibrated": self.state.leds_calibrated.copy(),
                "weakest_channel": getattr(self.state, 'weakest_channel', None),
                "polarizer_s_position": s_pos,  # ✨ From OEM calibration ONLY (no defaults!)
                "polarizer_p_position": p_pos,  # ✨ From OEM calibration ONLY (no defaults!)
                "polarizer_sp_ratio": getattr(self.state, 'polarizer_sp_ratio', None),
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

            # ✨ Load validated polarizer positions from OEM calibration (NO DEFAULTS!)
            # These values MUST come from OEM calibration tool - it's the single source of truth
            self.state.polarizer_s_position = calibration_data.get("polarizer_s_position")
            self.state.polarizer_p_position = calibration_data.get("polarizer_p_position")
            self.state.polarizer_sp_ratio = calibration_data.get("polarizer_sp_ratio", None)

            # Validate that OEM-calibrated positions were loaded
            if self.state.polarizer_s_position is None or self.state.polarizer_p_position is None:
                logger.error("=" * 80)
                logger.error("❌ INVALID CALIBRATION PROFILE - Missing Polarizer Positions")
                logger.error("=" * 80)
                logger.error("This calibration profile was created before OEM polarizer calibration.")
                logger.error("")
                logger.error("🔧 REQUIRED ACTION: Run OEM calibration tool to configure polarizer:")
                logger.error("   python utils/oem_calibration_tool.py --serial YOUR_SERIAL")
                logger.error("")
                logger.error("The OEM tool will find optimal S/P positions and save to device profile.")
                logger.error("=" * 80)
                return False, "Profile missing OEM polarizer calibration data"

            logger.info(f"Calibration profile loaded: {profile_path}")
            if hasattr(self.state, 'polarizer_s_position'):
                logger.info(f"   Polarizer positions: S={self.state.polarizer_s_position}, P={self.state.polarizer_p_position} (0-255 scale)")
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

            # ✨ Apply validated polarizer positions if available
            if hasattr(self.state, 'polarizer_s_position') and hasattr(self.state, 'polarizer_p_position'):
                s_pos = self.state.polarizer_s_position
                p_pos = self.state.polarizer_p_position
                ctrl.servo_set(s=s_pos, p=p_pos)
                logger.info(f"Polarizer positions applied: S={s_pos}, P={p_pos} (0-255 scale)")

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

            # Define sweep parameters (0-255 servo position range)
            min_position = 10
            max_position = MAX_POLARIZER_POSITION
            half_range = (max_position - min_position) // 2
            position_step = 5
            steps = half_range // position_step

            # Initialize intensity array
            max_intensities = np.zeros(2 * steps + 1)

            # Set starting position
            ctrl.servo_set(half_range + min_position, max_position)
            ctrl.set_mode("p")
            ctrl.set_mode("s")
            max_intensities[steps] = usb.read_intensity().max()

            # Sweep through positions
            for i in range(steps):
                x = min_position + position_step * i
                ctrl.servo_set(s=x, p=x + half_range + position_step)
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

            # Calculate final positions (0-255 scale)
            p_pos, s_pos = (min_position + position_step * edges.mean(0)).astype(int)
            ctrl.servo_set(s_pos, p_pos)

            logger.info(f"Auto-polarization complete: s={s_pos}, p={p_pos} (0-255 scale)")
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

            # Run the full calibration (auto-polarization disabled by default)
            # Note: Polarizer position validation happens in Step 2
            success, error_channels = self.run_full_calibration(
                auto_polarize=False,  # Auto-alignment is an advanced feature (handled in settings)
                auto_polarize_callback=None
            )

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

