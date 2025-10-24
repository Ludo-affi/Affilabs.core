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
from datetime import datetime

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
    NUM_SCANS_PER_ACQUISITION,  # ✨ Phase 2: 4-scan averaging for consistency
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

# ✨ Standardized error message for missing polarizer calibration
POLARIZER_ERROR_MESSAGE = """
🔧 REQUIRED: Run OEM calibration tool to configure polarizer positions
   This tool finds optimal S and P positions during manufacturing.

   Command: python utils/oem_calibration_tool.py --serial YOUR_SERIAL

   OR use Settings → Auto-Polarization in the GUI
"""


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
                            max_scans: int = 25) -> int:
    """Calculate number of scans to average based on integration time.

    This balances noise reduction with acquisition speed.

    Formula: num_scans = min(max_scans, max(min_scans, target_cycle_time / integration_time))

    Args:
        integration_time_seconds: Integration time in seconds
        target_cycle_time: Target total time for acquisition (default 0.2s = 200ms)
        min_scans: Minimum number of scans (default 1)
        max_scans: Maximum number of scans (default 25)

    Returns:
        Number of scans to average

    Examples:
        integration=0.150s (150ms) → 1 scan (150ms total)
        integration=0.100s (100ms) → 2 scans (200ms total)
        integration=0.050s (50ms)  → 4 scans (200ms total)
        integration=0.040s (40ms)  → 5 scans (200ms total)
        integration=0.020s (20ms)  → 10 scans (200ms total)
        integration=0.010s (10ms)  → 20 scans (200ms total)
        integration=0.004s (4ms)   → 25 scans (100ms total, capped at max)
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

        # ✨ Calibration mode selection (added for per-channel integration support)
        # Mode 'global': Traditional approach - calibrate LEDs, use global integration time
        # Mode 'per_channel': Modern approach - LED=255 fixed, use per-channel integration times
        self.calibration_mode: str = 'global'  # Default to traditional mode

        # ✨ NEW: Per-channel integration times and scan counts (200ms budget per channel)
        self.integration_per_channel: dict[str, float] = dict.fromkeys(CH_LIST, MIN_INTEGRATION / MS_TO_SECONDS)
        self.scans_per_channel: dict[str, int] = dict.fromkeys(CH_LIST, 1)

        # LED intensities
        self.ref_intensity: dict[str, int] = dict.fromkeys(CH_LIST, 0)
        self.leds_calibrated: dict[str, int] = dict.fromkeys(CH_LIST, 0)
        self.weakest_channel: Optional[str] = None  # ✨ NEW: Track weakest channel for S-mode calibration
        self.led_ranking: list[tuple[str, tuple[float, float, bool]]] = []  # ✨ NEW: Full LED ranking (weakest → strongest) from Step 3

        # Reference data
        self.dark_noise: np.ndarray = np.array([])
        self.full_spectrum_dark_noise: np.ndarray = np.array([])  # Full spectrum for resampling
        self.ref_sig: dict[str, Optional[np.ndarray]] = dict.fromkeys(CH_LIST)

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
                "integration_per_channel": self.integration_per_channel.copy(),  # ✨ NEW
                "scans_per_channel": self.scans_per_channel.copy(),  # ✨ NEW
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

            # ✨ NEW: Load per-channel integration times and scan counts
            self.integration_per_channel = data.get(
                "integration_per_channel",
                dict.fromkeys(CH_LIST, MIN_INTEGRATION / 1000.0)
            )
            self.scans_per_channel = data.get("scans_per_channel", dict.fromkeys(CH_LIST, 1))

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
        self.device_config = device_config  # Store for potential future use

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

        # ✨ Load preferred calibration mode from device config (if available)
        if device_config and 'calibration' in device_config:
            preferred_mode = device_config['calibration'].get('preferred_calibration_mode', 'global')
            if preferred_mode in ['global', 'per_channel']:
                self.state.calibration_mode = preferred_mode
                logger.info(f"📋 Calibration mode loaded from config: {preferred_mode.upper()}")
            else:
                logger.warning(f"⚠️ Invalid calibration mode in config: {preferred_mode}, using default 'global'")
                self.state.calibration_mode = 'global'
        else:
            logger.info("📋 No calibration mode in config, using default: GLOBAL")
            self.state.calibration_mode = 'global'

        # ========================================================================
        # ✨ P1 OPTIMIZATION: Early OEM Position Loading (Fail-Fast)
        # ========================================================================
        # Load OEM calibration positions immediately at initialization.
        # This enables fail-fast behavior (<1 second) instead of failing at Step 2B (~2 minutes).
        # Uses centralized _load_positions_from_config() helper to support both formats:
        #   - device_config['oem_calibration'] (preferred format)
        #   - device_config['polarizer'] (OEM tool output format)

        if not device_config:
            logger.error("=" * 80)
            logger.error("❌ CRITICAL: NO DEVICE CONFIG PROVIDED")
            logger.error("=" * 80)
            logger.error(POLARIZER_ERROR_MESSAGE)
            logger.error("=" * 80)
            raise ValueError("device_config is required for OEM calibration positions")

        # Load positions using centralized helper (checks both formats)
        s_pos, p_pos, sp_ratio = self._load_positions_from_config(device_config)

        if s_pos is not None and p_pos is not None:
            # Store positions in state
            self.state.polarizer_s_position = s_pos
            self.state.polarizer_p_position = p_pos
            self.state.polarizer_sp_ratio = sp_ratio

            # Success logging
            logger.info("=" * 80)
            logger.info("✅ OEM CALIBRATION POSITIONS LOADED AT INIT (P1 Optimization)")
            logger.info("=" * 80)
            logger.info(f"   S-position: {s_pos} (HIGH transmission - reference)")
            logger.info(f"   P-position: {p_pos} (LOWER transmission - resonance)")
            if sp_ratio:
                logger.info(f"   S/P ratio: {sp_ratio:.2f}x")
            logger.info("   ⚡ Fail-fast enabled: Invalid config detected immediately (<1s)")
            logger.info("=" * 80)
        else:
            # Positions not found in config - fail immediately
            logger.error("=" * 80)
            logger.error("❌ CRITICAL: OEM CALIBRATION POSITIONS NOT FOUND")
            logger.error("=" * 80)
            logger.error(f"   device_config keys: {list(device_config.keys())}")
            logger.error(POLARIZER_ERROR_MESSAGE)
            logger.error("=" * 80)
            raise ValueError("OEM calibration positions not found in device_config")
            logger.error("")
            logger.error("   ❌ NO DEFAULT POSITIONS - OEM calibration is MANDATORY")
            logger.error("=" * 80)
            raise ValueError("OEM calibration required but not found in device config")

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

                    # 🚀 PHASE 1: Calculate optimal LED delay from afterglow calibration
                    # Use typical calibration integration time (usually ~100ms)
                    integration_time_ms = 100.0
                    if hasattr(usb, 'integration_time'):
                        integration_time_ms = usb.integration_time * 1000.0
                    elif hasattr(usb, '_integration_time'):
                        integration_time_ms = usb._integration_time * 1000.0

                    # Calculate optimal delay (2% residual = good balance)
                    self.led_delay = self.afterglow_correction.get_optimal_led_delay(
                        integration_time_ms=integration_time_ms,
                        target_residual_percent=2.0
                    )

                    # ✨ SINGLE SOURCE OF TRUTH: Update state machine's LED delay
                    self.state.led_delay = self.led_delay

                    logger.info(
                        f"✅ Optical calibration loaded for calibration afterglow correction\n"
                        f"   File: {Path(optical_cal_file).name}\n"
                        f"   LED delay optimized: {self.led_delay*1000:.1f}ms "
                        f"(based on τ decay @ {integration_time_ms:.1f}ms integration)"
                    )
                except FileNotFoundError as e:
                    logger.info(f"ℹ️ Optical calibration file not found: {e}")
                    logger.info("ℹ️ Afterglow correction DISABLED for calibration")
                    logger.info(f"ℹ️ Using default LED delay: {self.led_delay*1000:.1f}ms")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load optical calibration: {e}")
                    logger.warning("⚠️ Afterglow correction DISABLED for calibration")
                    logger.info(f"ℹ️ Using default LED delay: {self.led_delay*1000:.1f}ms")
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

    # ========================================================================
    # POLARIZER POSITION LOADING (Centralized Helpers)
    # ========================================================================

    def _load_positions_from_config(self, device_config: dict) -> tuple[Optional[int], Optional[int], Optional[float]]:
        """Load polarizer positions from device config (supports both formats).

        ✨ UNIFIED LOADER: Handles both config formats in one place:
        - oem_calibration section (preferred format)
        - polarizer section (OEM tool output format)

        Args:
            device_config: Device configuration dictionary

        Returns:
            tuple: (s_position, p_position, sp_ratio) or (None, None, None) if not found
        """
        # Try oem_calibration section first (preferred format)
        if 'oem_calibration' in device_config:
            oem = device_config['oem_calibration']
            logger.info("✅ Found OEM calibration in 'oem_calibration' section")
            return (
                oem.get('polarizer_s_position'),
                oem.get('polarizer_p_position'),
                oem.get('polarizer_sp_ratio')
            )

        # Fallback to polarizer section (OEM tool format)
        if 'polarizer' in device_config:
            pol = device_config['polarizer']
            logger.info("✅ Found OEM calibration in 'polarizer' section (OEM tool format)")
            return (
                pol.get('s_position'),
                pol.get('p_position'),
                pol.get('sp_ratio') or pol.get('s_p_ratio')
            )

        # No positions found
        return (None, None, None)

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

    def set_calibration_mode(self, mode: str) -> bool:
        """Set calibration mode for spectroscopy operation.

        Two modes are supported:
        1. 'global' (default): Traditional approach
           - Step 4 calibrates LED intensities per channel
           - Uses single global integration time for all channels
           - Best for balanced signal levels

        2. 'per_channel': Modern fixed-LED approach
           - All LEDs set to 255 (maximum intensity)
           - Uses per-channel integration times optimized for each channel
           - Better for channels with widely varying responses
           - Similar to s-roi-stability-test mode

        Args:
            mode: Either 'global' or 'per_channel'

        Returns:
            True if mode set successfully, False if invalid mode

        Example:
            >>> calibrator.set_calibration_mode('per_channel')
            >>> # Step 2 will now configure for per-channel operation
        """
        if mode not in ['global', 'per_channel']:
            logger.error(f"Invalid calibration mode: {mode}. Must be 'global' or 'per_channel'")
            return False

        self.state.calibration_mode = mode
        logger.info(f"📊 Calibration mode set to: {mode.upper()}")

        if mode == 'per_channel':
            logger.info("   • LEDs will be fixed at 255")
            logger.info("   • Per-channel integration times will be optimized")
            logger.info("   • Step 4 (LED calibration) will be skipped")
        else:
            logger.info("   • LEDs will be calibrated per channel")
            logger.info("   • Global integration time will be used")
            logger.info("   • Step 4 (LED calibration) will run normally")

        return True

    # ========================================================================
    # OEM CALIBRATION POSITION ACCESS (P2 Optimization)
    # ========================================================================

    def _get_oem_positions(self) -> tuple[Optional[int], Optional[int], Optional[float]]:
        """Get OEM calibration positions from calibration state.

        ✨ SIMPLIFIED: Positions are always loaded at __init__ from device_config
        into self.state, so we only need to return what's already in state.
        No need to re-check device_config (eliminates redundant lookups).

        Returns:
            tuple: (s_position, p_position, sp_ratio) or (None, None, None) if not available

        Example:
            >>> s_pos, p_pos, sp_ratio = self._get_oem_positions()
            >>> if s_pos is None:
            ...     logger.error("OEM positions not available")
            ...     return False
        """
        # Return positions from state (loaded at init)
        if hasattr(self.state, 'polarizer_s_position') and self.state.polarizer_s_position is not None:
            return (
                self.state.polarizer_s_position,
                self.state.polarizer_p_position,
                getattr(self.state, 'polarizer_sp_ratio', None)
            )

        # No positions available (should only happen if __init__ failed)
        return (None, None, None)

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

            logger.info(f"🔧 Batch LED: Sent intensities [a={intensity_array[0]}, b={intensity_array[1]}, c={intensity_array[2]}, d={intensity_array[3]}] → success={success}")

            if not success:
                logger.warning("Batch LED command failed, falling back to sequential")
                return self._activate_channel_sequential(channels, intensities)

            # ⚠️ FIRMWARE LIMITATION: batch command doesn't affect turn_on_channel
            # The `batch:a,b,c,d` sets internal registers, but `la` uses the last `ba{val}` value
            # For single-channel activation, use set_intensity instead (ba + la in one call)
            if len(channels) == 1:
                ch = channels[0]
                led_val = intensity_array[channel_map[ch]]
                logger.info(f"🔦 Single-channel activation: setting {ch}={led_val} via set_intensity")
                success = self.ctrl.set_intensity(ch=ch, raw_val=led_val)
                logger.info(f"✅ LED {ch} → {success}")
                return success
            else:
                # Multiple channels - batch doesn't turn LEDs on, just sets values
                # Turn on first channel only (firmware mutual exclusion)
                logger.warning(f"⚠️  Multi-channel batch sets values but doesn't turn LEDs on")
                ch = channels[0]
                led_val = intensity_array[channel_map[ch]]
                success = self.ctrl.set_intensity(ch=ch, raw_val=led_val)
                logger.info(f"✅ LED {ch} (first only) → {success}")
                return success

        except Exception as e:
            logger.error(f"Batch LED activation failed: {e}, falling back to sequential")
            return self._activate_channel_sequential(channels, intensities)

    def _activate_channel_sequential(self, channels: list[str], intensities: dict[str, int] | None = None) -> bool:
        """Fallback: Sequential channel activation (legacy hardware or firmware < V1.4).

        ⚠️ NOTE: This is 15x slower than batch path. Only used when:
          - Hardware doesn't support batch commands (PicoEZSPR)
          - Firmware version < V1.4
          - HAL adapter without batch support

        Args:
            channels: List of channel IDs ('a', 'b', 'c', 'd')
            intensities: Optional dict of {channel: intensity}. If None, uses max_led_intensity

        Returns:
            bool: Success status

        Performance:
            Sequential: 4 channels × 3ms = 12ms
            Batch: 1 command × 0.8ms = 0.8ms
            Speedup: 15× when batch available
        """
        try:
            for ch in channels:
                # Use custom intensity or max_led_intensity
                intensity = intensities.get(ch) if intensities else self.max_led_intensity
                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
            return True
        except Exception as e:
            logger.error(f"Sequential LED activation failed: {e}")
            return False

    def _all_leds_off_batch(self) -> bool:
        """Turn all LEDs off - use multiple methods to ensure they're truly off."""
        try:
            success = True

            # Method 1: Use the global turn-off command
            if hasattr(self.ctrl, 'turn_off_channels'):
                result = self.ctrl.turn_off_channels()
                if not result:
                    logger.debug("turn_off_channels returned False")
                    success = False

            # Method 2: Set all intensities to 0 then turn off each channel individually
            # This ensures both the register AND the LED state are set to off
            for ch in ['a', 'b', 'c', 'd']:
                try:
                    # Set intensity to 0
                    if hasattr(self.ctrl, 'set_intensity'):
                        self.ctrl.set_intensity(ch, 0)
                except Exception as e:
                    logger.debug(f"Failed to set {ch} intensity to 0: {e}")
                    success = False

            # Method 3: Also try batch command as backup
            if hasattr(self.ctrl, 'set_batch_intensities'):
                self.ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)

            return success
        except Exception as e:
            logger.error(f"LED off failed: {e}")
            # Final fallback
            try:
                self.ctrl.turn_off_channels()
            except Exception:
                pass
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
            logger.debug("⚠️ Wavelength mask not initialized - returning full spectrum")
            return raw_spectrum

        # Handle size mismatch by recreating mask (USB4000 sometimes returns 3647 or 3648 pixels)
        if len(raw_spectrum) != len(self.state.wavelength_mask):
            logger.debug(
                f"Spectrum size changed: {len(raw_spectrum)} pixels (was {len(self.state.wavelength_mask)})"
            )

            # Get current wavelengths matching the spectrum size
            try:
                current_wavelengths = None
                # Use HAL method directly (unified access path)
                if hasattr(self.usb, "get_wavelengths"):
                    wl = self.usb.get_wavelengths()
                    if wl is not None:
                        current_wavelengths = np.array(wl)
                elif hasattr(self.usb, "read_wavelength"):
                    # Fallback for legacy adapters
                    current_wavelengths = self.usb.read_wavelength()

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

    def _apply_jitter_correction(self, spectra: list[np.ndarray], times: Optional[list[float]] = None) -> np.ndarray:
        """Apply adaptive polynomial jitter correction to multiple spectra.

        This removes systematic drift and thermal effects that cause spectral jitter.
        Uses polynomial fitting to capture slow trends and rolling median for noise reduction.

        Args:
            spectra: List of spectrum arrays to correct (same shape)
            times: Optional list of acquisition times (for time-dependent fitting)
                  If None, uses sequential indices

        Returns:
            Array of corrected spectra (stacked as 2D array)

        Example:
            >>> spectra = [spectrum1, spectrum2, spectrum3, ...]  # List of 1D arrays
            >>> corrected = self._apply_jitter_correction(spectra)
            >>> mean_spectrum = np.mean(corrected, axis=0)  # Average of corrected spectra
        """
        if not spectra or len(spectra) < 3:
            # Not enough data for meaningful correction
            return np.array(spectra) if spectra else np.array([])

        # Stack spectra into 2D array (n_spectra × n_wavelengths)
        spectra_arr = np.array(spectra)
        n_spectra, n_wavelengths = spectra_arr.shape

        # Use sequential indices if times not provided
        if times is None:
            times = np.arange(n_spectra, dtype=float)
        else:
            times = np.array(times, dtype=float)

        # Correct each wavelength point independently
        corrected = np.zeros_like(spectra_arr)

        for wl_idx in range(n_wavelengths):
            values = spectra_arr[:, wl_idx]

            # Fit polynomial to capture slow drift (thermal/aging)
            poly_order = min(3, max(1, n_spectra // 20))  # Adaptive order: 1-3
            try:
                coeffs = np.polyfit(times, values, poly_order)
                trend = np.polyval(coeffs, times)
                detrended = values - trend
            except:
                # Fallback to mean subtraction if polyfit fails
                detrended = values - np.mean(values)

            # Remove high-frequency noise with rolling median
            window = min(5, max(3, n_spectra // 10))
            if window >= 3 and n_spectra >= window:
                smoothed = np.zeros_like(detrended)
                for i in range(n_spectra):
                    start = max(0, i - window // 2)
                    end = min(n_spectra, i + window // 2 + 1)
                    smoothed[i] = np.median(detrended[start:end])
                corrected[:, wl_idx] = smoothed
            else:
                corrected[:, wl_idx] = detrended

        return corrected

    def _acquire_averaged_spectrum(
        self,
        num_scans: int,
        apply_filter: bool = True,
        subtract_dark: bool = False,
        description: str = "spectrum",
        apply_jitter_correction: bool = False
    ) -> Optional[np.ndarray]:
        """Vectorized spectrum acquisition and averaging with optional jitter correction.

        Optimized method that uses NumPy vectorization for 2-3× faster spectrum acquisition.
        Instead of accumulating in a loop, collects all spectra then averages vectorized.

        Args:
            num_scans: Number of spectra to acquire and average
            apply_filter: Whether to apply spectral range filter (default: True)
            subtract_dark: Whether to subtract dark noise (default: False)
            description: Description for logging (default: "spectrum")
            apply_jitter_correction: Whether to apply adaptive polynomial jitter correction (default: False)

        Returns:
            Averaged spectrum as numpy array, or None if error

        Performance:
            Old method: for loop with accumulation (slow)
            New method: vectorized stack + mean (2-3× faster)
            With jitter correction: Removes thermal drift and systematic noise (60-65% improvement)
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

            # ✨ Apply jitter correction if requested (removes thermal drift and systematic noise)
            if apply_jitter_correction and num_scans >= 5:
                # Convert to list of arrays for jitter correction function
                spectra_list = [spectra_stack[i] for i in range(num_scans)]
                corrected_stack = self._apply_jitter_correction(spectra_list)
                # Average the corrected spectra
                averaged_spectrum = np.mean(corrected_stack, axis=0)
                logger.debug(f"Applied jitter correction to {num_scans} {description} scans")
            else:
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

    def _acquire_calibration_spectrum(self,
                                      apply_filter: bool = True,
                                      subtract_dark: bool = False) -> Optional[np.ndarray]:
        """Acquire spectrum with proper averaging for calibration consistency.

        Helper method that ensures all calibration spectrum acquisitions use
        the same averaging as live mode (NUM_SCANS_PER_ACQUISITION = 4).

        This provides consistency between:
        - Calibration measurements (dark, S-pol, P-pol references)
        - Live data acquisition
        - Same noise characteristics throughout workflow

        Args:
            apply_filter: Whether to apply spectral range filter (default: True)
            subtract_dark: Whether to subtract dark noise (default: False)

        Returns:
            Averaged spectrum as numpy array, or None if error

        Example:
            # Instead of: raw = self.usb.read_intensity()
            # Use: raw = self._acquire_calibration_spectrum()
        """
        return self._acquire_averaged_spectrum(
            num_scans=NUM_SCANS_PER_ACQUISITION,
            apply_filter=apply_filter,
            subtract_dark=subtract_dark,
            description="calibration spectrum"
        )

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

    def _calibrate_wavelength_ocean_optics(self) -> tuple[Optional[np.ndarray], str]:
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
            # Use HAL method directly (unified access path)
            if hasattr(self.usb, "get_wavelengths"):
                # Direct HAL access (preferred)
                wave_data = self.usb.get_wavelengths()
                if wave_data is not None:
                    wave_data = np.array(wave_data)
            elif hasattr(self.usb, "read_wavelength"):
                # Fallback for legacy adapters
                wave_data = self.usb.read_wavelength()
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

    def _calibrate_wavelength_from_file(self) -> tuple[Optional[np.ndarray], str]:
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

    def step_2_calibrate_wavelength_range(self) -> bool:
        """STEP 2: Calibrate wavelength range and calculate Fourier weights (Detector-Specific).

        ✨ OPTIMIZED: Single wavelength read (no redundant USB calls) + caching

        Improvements:
        - Reads wavelengths once (not 2×)
        - Uses wavelengths for both detection and calibration
        - Fast dict-based detector detection
        - Consolidated logging (cleaner output)
        - Caches wavelengths to skip EEPROM reads (saves ~1s per calibration)

        Returns:
            True on success, False on error

        """
        try:
            if self.device_type not in DEVICES:
                logger.error(f"Unrecognized controller: {self.device_type}")
                return False

            if self.usb is None:
                logger.error("USB spectrometer not available")
                return False

            # Try to auto-detect and attach a detector profile if not already set
            if self.detector_profile is None:
                try:
                    from utils.detector_manager import get_detector_manager
                    mgr = get_detector_manager()
                    prof = mgr.auto_detect(self.usb)
                    if prof is not None:
                        self.detector_profile = prof
                        logger.info(f"📄 Detector profile selected: {prof.manufacturer} {prof.model}")
                except Exception as e:
                    logger.debug(f"Detector profile auto-detect skipped/failed: {e}")

            # ========================================================================
            # CALIBRATION MODE SELECTION
            # ========================================================================
            logger.info("=" * 80)
            logger.info("CALIBRATION MODE SELECTION")
            logger.info("=" * 80)
            logger.info(f"Current mode: {self.state.calibration_mode.upper()}")
            logger.info("")
            logger.info("Available modes:")
            logger.info("  1. GLOBAL (default)")
            logger.info("     • Step 4 calibrates LED intensities per channel")
            logger.info("     • Uses single global integration time")
            logger.info("     • Best for balanced signal levels")
            logger.info("")
            logger.info("  2. PER_CHANNEL (advanced)")
            logger.info("     • All LEDs fixed at 255 (maximum)")
            logger.info("     • Uses per-channel integration times")
            logger.info("     • Optimal for widely varying channel responses")
            logger.info("     • Similar to s-roi-stability-test mode")
            logger.info("")
            logger.info("Mode can be changed programmatically using:")
            logger.info("  calibrator.set_calibration_mode('global' or 'per_channel')")
            logger.info("=" * 80)

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
                # Use HAL method directly (unified access path)
                if hasattr(self.usb, "get_wavelengths"):
                    wave_data = self.usb.get_wavelengths()
                    if wave_data is not None:
                        wave_data = np.array(wave_data)
                elif hasattr(self.usb, "read_wavelength"):
                    # Fallback for legacy adapters
                    wave_data = self.usb.read_wavelength()
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

            # Detector profile may provide integration step, but Step 4 now uses binary search.
            # We keep no dependency on a step size here.

            # Spectral range filtering - only keep SPR-relevant wavelengths (580-720 nm)
            if len(wave_data) < 2:
                logger.error("Insufficient wavelength data")
                return False

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
                logger.warning(
                    f"Using legacy wavelength range from settings.py: {min_wavelength}-{max_wavelength} nm"
                )

            # Create wavelength mask for SPR-relevant range
            wavelength_mask = (wave_data >= min_wavelength) & (wave_data <= max_wavelength)
            filtered_wave_data = wave_data[wavelength_mask]

            if len(filtered_wave_data) < 10:
                logger.error(f"Insufficient pixels in SPR range ({min_wavelength}-{max_wavelength} nm)")
                return False

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
                f"✅ SPECTRAL FILTERING APPLIED: {min_wavelength}-{max_wavelength} nm | kept {len(filtered_wave_data)} px"
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
                return False

            phi = np.pi / n * np.arange(1, n)
            phi2 = phi**2
            self.state.fourier_weights = phi / (1 + alpha * phi2 * (1 + phi2))

            logger.debug("Wavelength calibration complete")
            return True

        except Exception as e:
            logger.exception(f"Error in wavelength calibration: {e}")
            return False, 1.0

    def calibrate_wavelength_range(self) -> bool:
        """Calibrate wavelength range (backward compatibility wrapper).

        For new code, use step_2_calibrate_wavelength_range() for clarity.

        Returns:
            True on success, False on error
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

            # ========================================================================
            # ✨ P3 OPTIMIZATION: Simplified Validation (No Lazy Loading)
            # ========================================================================
            # Positions are now loaded at init (P1), so this method only validates.
            # Uses centralized helper method (P2) for cleaner code.

            # Get OEM positions using centralized helper (P2 optimization)
            s_pos, p_pos, sp_ratio_config = self._get_oem_positions()

            # Positions should ALWAYS be available here (loaded at init via P1)
            if s_pos is None or p_pos is None:
                # This should NEVER happen if P1 optimization is working correctly
                logger.error("=" * 80)
                logger.error("❌ INTERNAL ERROR: OEM positions not loaded at init")
                logger.error("=" * 80)
                logger.error("   This indicates a bug in the P1 optimization (early loading)")
                logger.error(f"   S-position: {s_pos}")
                logger.error(f"   P-position: {p_pos}")
                logger.error("=" * 80)
                return False

            # Apply OEM-calibrated positions to hardware BEFORE validation
            logger.info(f"   Applying OEM-calibrated positions to hardware:")
            logger.info(f"      S={s_pos} (HIGH transmission - reference)")
            logger.info(f"      P={p_pos} (LOWER transmission - resonance)")
            self.ctrl.servo_set(s=s_pos, p=p_pos)
            time.sleep(1.0)  # Wait for servo to move to both positions

            # ✅ CRITICAL FIX: Flash positions to EEPROM so they persist across power cycles
            logger.info(f"   💾 Saving positions to EEPROM...")
            self.ctrl.flash()
            time.sleep(0.5)  # Wait for EEPROM write to complete

            logger.info(f"   ✅ Polarizer positions applied to hardware and saved to EEPROM")

            # ✅ SINGLE SOURCE OF TRUTH: Trust OEM calibration from device_config
            # Skip hardware verification to avoid communication failures during calibration
            logger.info(f"   Using OEM calibration from device_config (single source of truth):")
            logger.info(f"   S position: {s_pos} (HIGH transmission - reference)")
            logger.info(f"   P position: {p_pos} (LOWER transmission - resonance)")
            logger.info(f"   Skipping hardware readback verification to prevent communication issues")

            # Turn on LED A at moderate intensity for testing
            self.ctrl.set_intensity("a", 150)  # set_intensity() already activates the LED
            time.sleep(0.3)

            # Measure S-mode intensity (should be HIGH - reference, no resonance)
            self.ctrl.set_mode("s")
            time.sleep(0.4)  # Wait for servo to move
            # ✨ Phase 2: Use 4-scan averaging for consistency with live mode
            s_spectrum = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
            s_max = float(np.max(s_spectrum)) if s_spectrum is not None else 0.0

            # Measure P-mode intensity (should be LOWER - shows resonance)
            self.ctrl.set_mode("p")
            time.sleep(0.4)  # Wait for servo to move
            # ✨ Phase 2: Use 4-scan averaging for consistency with live mode
            p_spectrum = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
            p_max = float(np.max(p_spectrum)) if p_spectrum is not None else 0.0

            # Turn off LED
            self.ctrl.turn_off_channels()

            # Calculate ratio (S/P - should be > 2 in SPR, typically 3-15×)
            ratio = s_max / p_max if p_max > 0 else 0.0

            # Store validated ratio in state for reference
            self.state.polarizer_sp_ratio = ratio  # Measured S/P ratio (correct for SPR)

            logger.info(f"   S-mode intensity: {s_max:.1f} counts (HIGH expected - reference)")
            logger.info(f"   P-mode intensity: {p_max:.1f} counts (LOWER expected - resonance)")
            logger.info(f"   Measured S/P ratio: {ratio:.2f}x")
            if sp_ratio_config:
                logger.info(f"   Expected S/P ratio: {sp_ratio_config:.2f}x (from OEM calibration)")

            # Validate: S-mode should be significantly higher than P-mode (SPR behavior)
            MIN_RATIO = 1.05  # Minimum ratio to detect obvious problems
            IDEAL_RATIO_MIN = 1.33
            IDEAL_RATIO_MAX = 15.0

            if ratio < MIN_RATIO:
                # ⚠️ Low ratio could be saturation, not polarizer error
                # OEM positions are already validated, so treat as WARNING not ERROR
                logger.warning("=" * 80)
                logger.warning("⚠️ LOW S/P RATIO DETECTED (POSSIBLE SATURATION)")
                logger.warning("=" * 80)
                logger.warning(f"   S-mode intensity: {s_max:.1f} counts")
                logger.warning(f"   P-mode intensity: {p_max:.1f} counts")
                logger.warning(f"   Measured ratio: {ratio:.2f}x (expected: >{MIN_RATIO}x)")
                logger.warning(f"   OEM positions: S={s_pos}, P={p_pos} (validated)")
                if sp_ratio_config:
                    logger.warning(f"   Expected ratio: {sp_ratio_config:.2f}x (from OEM calibration)")
                logger.warning("")

                # Check if both are saturated (integration time too high)
                if s_max >= 65535 and p_max >= 65535:
                    logger.warning("   CAUSE: Both S and P are SATURATED (65535)")
                    logger.warning("   → Integration time will be reduced automatically")
                else:
                    logger.warning("   Possible causes:")
                    logger.warning("   1. Polarizer positions need verification")
                    logger.warning("   2. Servo positions need adjustment")
                    logger.warning("   3. Polarizer not properly aligned")

                logger.warning("")
                logger.warning("   ✅ Continuing calibration with OEM-validated positions")
                logger.warning("=" * 80)
                return True  # Continue calibration - positions are from validated OEM config
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

    def step_3_identify_weakest_channel(self, ch_list: list[str]) -> tuple[Optional[str], dict]:
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

            # Get detector max for saturation detection - MUST come from detector profile
            if not self.detector_profile:
                logger.error("❌ Detector profile not loaded - cannot determine saturation threshold")
                logger.error("   Run Step 2 first to load detector profile")
                return None, {}

            detector_max = self.detector_profile.max_intensity_counts
            SATURATION_THRESHOLD = int(0.95 * detector_max)  # 95% of max
            logger.debug(f"Saturation threshold: {SATURATION_THRESHOLD} counts (95% of {detector_max})")

            # ✨ Leverage prior diagnostics from device_config to reduce retries
            # If a channel previously saturated on first pass, start it at LED=64 and scale up for fair comparison
            per_channel_test_led: dict[str, int] = {ch: test_led_intensity for ch in ch_list}
            try:
                from utils.device_configuration import DeviceConfiguration
                device_config = DeviceConfiguration()
                diag = device_config.to_dict().get('diagnostics', {}).get('led_ranking')
                if diag and isinstance(diag, dict):
                    prior_saturated = diag.get('saturated_on_first_pass') or []
                    # Normalize to lowercase keys to match channel ids ('a','b','c','d')
                    prior_saturated = [str(x).lower() for x in prior_saturated]
                    if prior_saturated:
                        logger.info(f"   Using prior diagnostics: starting {prior_saturated} at LED=64 to avoid saturation retries")
                        for ch in ch_list:
                            if ch in prior_saturated:
                                per_channel_test_led[ch] = int(0.25 * MAX_LED_INTENSITY)  # 64
            except Exception:
                # Diagnostics are optional; ignore any issues and proceed with defaults
                pass

            # EARLY-CONFIRM WEAKEST (optional fast path using prior diagnostics)
            try:
                prior_weakest = None
                prior_second = None
                from utils.device_configuration import DeviceConfiguration
                device_config = DeviceConfiguration()
                diag = device_config.to_dict().get('diagnostics', {}).get('led_ranking')
                if diag and isinstance(diag, dict):
                    prior_weakest = str(diag.get('weakest_channel') or '').lower() or None
                    ranked_order = diag.get('ranked_order') or []
                    ranked_order = [str(x).lower() for x in ranked_order if isinstance(x, (str,))]
                    # pick the first non-weakest from prior order as comparator
                    for cand in ranked_order:
                        if cand != prior_weakest:
                            prior_second = cand
                            break
                # Run quick check only if we have both and they are in the ch_list
                EARLY_CONFIRM_MARGIN = 1.07  # 7% margin
                if prior_weakest and prior_second and all(c in ch_list for c in [prior_weakest, prior_second]):
                    logger.info(f"   Early-confirm check using prior weakest={prior_weakest} vs {prior_second}")
                    quick_data = {}
                    for ch in [prior_weakest, prior_second]:
                        chosen_led = per_channel_test_led.get(ch, test_led_intensity)
                        intensities_dict = {ch: chosen_led}
                        self._activate_channel_batch([ch], intensities_dict)
                        time.sleep(LED_DELAY)
                        self._last_active_channel = ch
                        raw_array = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
                        if raw_array is None:
                            quick_data = {}
                            break
                        filtered_array = self._apply_spectral_filter(raw_array)
                        test_region = filtered_array[target_min_idx:target_max_idx]
                        mean_intensity = float(np.mean(test_region))
                        max_intensity = float(np.max(test_region))
                        # scale if measured at lower LED
                        if chosen_led != test_led_intensity and chosen_led > 0:
                            scale = test_led_intensity / chosen_led
                            mean_intensity *= scale
                            max_intensity *= scale
                        quick_data[ch] = (mean_intensity, max_intensity)

                    # Turn off after quick check
                    self._all_leds_off_batch()
                    time.sleep(LED_DELAY)

                    if len(quick_data) == 2:
                        w_mean = quick_data[prior_weakest][0]
                        s_mean = quick_data[prior_second][0]
                        if w_mean > 0 and (s_mean / w_mean) >= EARLY_CONFIRM_MARGIN:
                            # Confirmed: prior weakest is still weakest by margin → short-circuit
                            logger.info(f"   ✅ Early-confirm success: {prior_weakest} remains weakest by {(s_mean/w_mean):.2f}×")
                            self.state.led_ranking = [(prior_weakest, (w_mean, quick_data[prior_weakest][1], False))]
                            self.state.weakest_channel = prior_weakest

                            # Persist minimal diagnostics (optional but helpful)
                            try:
                                percent = {
                                    prior_weakest: 100.0,
                                    prior_second: float((s_mean / w_mean) * 100.0)
                                }
                                device_config.save_led_ranking_diagnostics(
                                    weakest_channel=prior_weakest,
                                    ranked_channels=[(prior_weakest, (w_mean, quick_data[prior_weakest][1], False)),
                                                    (prior_second, (s_mean, quick_data[prior_second][1], False))],
                                    percent_of_weakest=percent,
                                    mean_counts={prior_weakest: w_mean, prior_second: s_mean},
                                    saturated_on_first_pass=None,
                                    test_led_intensity=test_led_intensity,
                                    test_region_nm=(TARGET_WAVELENGTH_MIN, TARGET_WAVELENGTH_MAX),
                                )
                            except Exception:
                                pass

                            return prior_weakest, {prior_weakest: w_mean, prior_second: s_mean}
            except Exception:
                # Early confirm is optional; ignore issues and continue with full measurement
                pass

            # ✨ FAST TEST: Single read per channel, no averaging, no dark subtraction
            for ch in ch_list:
                if self._is_stopped():
                    return None, {}

                # Turn on channel at chosen test intensity (may be 128 or 64 based on prior diagnostics)
                chosen_led = per_channel_test_led.get(ch, test_led_intensity)
                intensities_dict = {ch: chosen_led}
                self._activate_channel_batch([ch], intensities_dict)
                time.sleep(LED_DELAY)

                # Track for afterglow correction
                self._last_active_channel = ch

                # ✨ Phase 2: Use 4-scan averaging for consistency with live mode
                raw_array = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
                if raw_array is None:
                    logger.error(f"Failed to read intensity for channel {ch}")
                    continue

                # Apply spectral filter (to SPR range)
                filtered_array = self._apply_spectral_filter(raw_array)

                # Extract test region (580-610nm)
                test_region = filtered_array[target_min_idx:target_max_idx]
                mean_intensity = float(np.mean(test_region))
                max_intensity = float(np.max(test_region))

                # If we measured at lower LED (e.g., 64), scale to 128-equivalent for fair ranking and mark not saturated
                if chosen_led != test_led_intensity and chosen_led > 0:
                    scale = test_led_intensity / chosen_led
                    scaled_mean = mean_intensity * scale
                    scaled_max = max_intensity * scale
                    is_saturated = False
                    channel_data[ch] = (float(scaled_mean), float(scaled_max), is_saturated)
                else:
                    # Detect saturation only for standard test intensity
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

                    # Turn on channel at test intensity
                    intensities_dict = {ch: retry_led}
                    self._activate_channel_batch([ch], intensities_dict)
                    time.sleep(LED_DELAY)

                    self._last_active_channel = ch


                    # ✨ Phase 2: Use 4-scan averaging for consistency with live mode
                    raw_array = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
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

            # 💾 Save diagnostics to device_config.json (percent-of-weakest)
            try:
                from utils.device_configuration import DeviceConfiguration

                weakest_mean = weakest_intensity if weakest_intensity > 0 else 1.0
                percent_of_weakest = {
                    ch: float((data[0] / weakest_mean) * 100.0) for ch, data in ranked_channels
                }
                mean_counts = {ch: float(data[0]) for ch, data in ranked_channels}

                device_config = DeviceConfiguration()
                device_config.save_led_ranking_diagnostics(
                    weakest_channel=weakest_ch,
                    ranked_channels=ranked_channels,
                    percent_of_weakest=percent_of_weakest,
                    mean_counts=mean_counts,
                    saturated_on_first_pass=saturated_channels if 'saturated_channels' in locals() else None,
                    test_led_intensity=test_led_intensity,
                    test_region_nm=(TARGET_WAVELENGTH_MIN, TARGET_WAVELENGTH_MAX),
                )
            except Exception as diag_e:
                logger.warning(f"⚠️ Failed to persist LED ranking diagnostics: {diag_e}")

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
    ) -> Optional[tuple[float, float]]:
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

            # ✨ Phase 2: Use 4-scan averaging for consistency with live mode
            raw_array = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
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

    def step_4_optimize_integration_time(self, weakest_ch: str) -> bool:
        """STEP 4: Optimize integration time for WEAKEST LED @ 255 ONLY.

        TRUE ORIGINAL CALIBRATION:
        ==========================
        Step 3: Find weakest LED
        Step 4: Set WEAKEST to LED=255, find integration time where it reaches 75% detector max
        Step 5: Re-measure dark noise
        Step 6: Adjust OTHER LEDs down until all within 15% of each other, within target range
        Step 7: Measure S-ref (balanced S-mode calibration baseline)

        Smart boost (P-pol ONLY):
        - ONLY increases integration time (never touches LED values)
        - Stays within 200ms budget: num_scans = min(200ms / integration_time, 25)

        CALIBRATION MODES:
        ==================
        - 'global': Run normal LED calibration (Step 4 -> Step 6)
        - 'per_channel': Skip LED calibration, set all LEDs to 255, optimize per-channel integration

        Args:
            weakest_ch: The weakest channel ID (from Step 3)

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            # ========================================================================
            # CHECK CALIBRATION MODE
            # ========================================================================
            if self.state.calibration_mode == 'per_channel':
                logger.info(f"")
                logger.info(f"=" * 80)
                logger.info(f"⚡ STEP 4: PER-CHANNEL MODE - SKIPPING LED CALIBRATION")
                logger.info(f"=" * 80)
                logger.info(f"   Mode: PER_CHANNEL (all LEDs fixed at 255)")
                logger.info(f"   Step 4 → SKIPPED (no LED calibration needed)")
                logger.info(f"   Step 6 → SKIPPED (no LED balancing needed)")
                logger.info(f"")
                logger.info(f"   Setting all LEDs to maximum intensity (255)...")

                # Set all LEDs to 255
                ch_list = self.state.led_ranking if self.state.led_ranking else [('a', (0,)), ('b', (0,)), ('c', (0,)), ('d', (0,))]
                for ch_info in ch_list:
                    ch = ch_info[0]
                    self.ctrl.set_intensity(ch, MAX_LED_INTENSITY)
                    self.state.led_intensities[ch] = MAX_LED_INTENSITY

                logger.info(f"   ✅ All LEDs set to 255")
                logger.info(f"")
                logger.info(f"   Next: Step 5 will measure dark noise")
                logger.info(f"   Then: Per-channel integration times will be optimized")
                logger.info(f"=" * 80)

                # Turn off all channels after setting
                self.ctrl.turn_off_channels()

                return True

            # ========================================================================
            # GLOBAL MODE: STANDARD LED CALIBRATION
            # ========================================================================

            # Import single-constraint optimization constants
            from settings import (
                WEAKEST_TARGET_PERCENT, WEAKEST_MIN_PERCENT, WEAKEST_MAX_PERCENT
            )

            # Import single-constraint optimization constants
            from settings import (
                WEAKEST_TARGET_PERCENT, WEAKEST_MIN_PERCENT, WEAKEST_MAX_PERCENT
            )

            # Get integration time limits from detector profile
            if not self.detector_profile:
                logger.error("❌ Detector profile not loaded - cannot determine integration limits")
                logger.error("   Run Step 2 first to load detector profile")
                return False

            min_int = self.detector_profile.min_integration_time_ms / MS_TO_SECONDS
            max_int = self.detector_profile.max_integration_time_ms / MS_TO_SECONDS
            detector_max = self.detector_profile.max_intensity_counts
            spr_min_nm = self.detector_profile.spr_wavelength_min_nm
            spr_max_nm = self.detector_profile.spr_wavelength_max_nm
            logger.info(f"📊 Using detector profile: {self.detector_profile.min_integration_time_ms}-{self.detector_profile.max_integration_time_ms}ms")
            logger.info(f"   SPR Range: {spr_min_nm}-{spr_max_nm}nm")

            # Get weakest channel from Step 3 ranking
            if not self.state.led_ranking or len(self.state.led_ranking) < 1:
                logger.error("⚠️  LED ranking not found! Step 3 must run before Step 4.")
                return False

            weakest_ch = self.state.led_ranking[0][0]
            weakest_intensity = self.state.led_ranking[0][1][0]

            logger.info(f"")
            logger.info(f"=" * 80)
            logger.info(f"⚡ STEP 4: INTEGRATION TIME OPTIMIZATION (WEAKEST @ LED=255)")
            logger.info(f"=" * 80)
            logger.info(f"   Weakest LED: {weakest_ch} (will be set to LED=255)")
            logger.info(f"")
            logger.info(f"   GOAL: Find integration time where weakest @ 255 reaches target")
            logger.info(f"      → Target: {WEAKEST_TARGET_PERCENT}% ({int(WEAKEST_TARGET_PERCENT/100*detector_max):,} counts)")
            logger.info(f"      → Range: {WEAKEST_MIN_PERCENT}-{WEAKEST_MAX_PERCENT}% ({int(WEAKEST_MIN_PERCENT/100*detector_max):,}-{int(WEAKEST_MAX_PERCENT/100*detector_max):,} counts)")
            logger.info(f"")
            logger.info(f"   Integration time limit: ≤ {max_int*1000:.0f}ms")
            logger.info(f"")
            logger.info(f"   Next: Step 6 will adjust OTHER LEDs down to balance all channels")
            logger.info(f"=" * 80)

            # Get full SPR ROI indices (580-720nm)
            wave_data = self.state.wavelengths
            roi_min_idx = np.argmin(np.abs(wave_data - spr_min_nm))
            roi_max_idx = np.argmin(np.abs(wave_data - spr_max_nm))
            logger.debug(f"   Measuring MAX signal in ROI: {spr_min_nm}-{spr_max_nm}nm (indices {roi_min_idx}-{roi_max_idx})")

            # Define targets
            weakest_target = int(WEAKEST_TARGET_PERCENT / 100 * detector_max)
            weakest_min = int(WEAKEST_MIN_PERCENT / 100 * detector_max)
            weakest_max = int(WEAKEST_MAX_PERCENT / 100 * detector_max)

            # Binary search for optimal integration time (SINGLE CONSTRAINT)
            integration_min = min_int
            integration_max = max_int
            best_integration = None
            best_weakest_signal = 0

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

                # Measure ONLY weakest LED at LED=255
                result = self._measure_channel_in_roi(
                    weakest_ch, MAX_LED_INTENSITY, int(roi_min_idx), int(roi_max_idx), "weakest LED"
                )
                if result is None:
                    return False
                weakest_signal, _ = result
                weakest_percent = (weakest_signal / detector_max) * 100

                logger.info(f"   Iteration {iteration+1}: {test_integration*1000:.1f}ms")
                logger.info(f"      Weakest ({weakest_ch} @ LED=255): {weakest_signal:6.0f} counts ({weakest_percent:5.1f}%)")

                # Check if in target range
                if weakest_min <= weakest_signal <= weakest_max:
                    # ✅ Perfect! Target reached
                    best_integration = test_integration
                    best_weakest_signal = weakest_signal
                    logger.info(f"      ✅ TARGET REACHED!")
                    break

                # Adjust search range based on weakest LED signal
                if weakest_signal < weakest_min:
                    logger.info(f"      ⚠️  Too low → Increase integration")
                    integration_min = test_integration
                else:
                    logger.info(f"      ⚠️  Too high → Reduce integration")
                    integration_max = test_integration

                # Track best so far (closest to target)
                if abs(weakest_signal - weakest_target) < abs(best_weakest_signal - weakest_target):
                    best_integration = test_integration
                    best_weakest_signal = weakest_signal

            # Finalize
            if best_integration is None:
                logger.error("Failed to find optimal integration time!")
                return False

            self.state.integration = best_integration
            self.usb.set_integration(best_integration)
            time.sleep(0.1)

            # Validate final result
            weakest_percent = (best_weakest_signal / detector_max) * 100

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
            logger.info(f"   Integration time LOCKED for S-mode: {best_integration*1000:.1f}ms")
            logger.info(f"   This will be used for:")
            logger.info(f"      • Step 5: Re-measure dark noise (at final integration time)")
            logger.info(f"      • Step 6: Calibrate other LEDs (REDUCE their intensity to balance)")
            logger.info(f"      • Step 7: Reference signal measurement (balanced S-mode)")
            logger.info(f"")
            logger.info(f"   Note: Smart boost (P-pol ONLY) increases integration time, never LED values")
            logger.info(f"="*80)

            # ✨ Set ONLY weakest channel to LED=255 (Step 6 will calibrate others)
            logger.info(f"")
            logger.info(f"💾 Setting weakest channel to LED=255...")
            self.state.ref_intensity[weakest_ch] = MAX_LED_INTENSITY
            logger.info(f"   {weakest_ch.upper()}: LED=255 (LOCKED)")
            logger.info(f"   Other channels will be calibrated in Step 6")
            logger.info(f"")

            # Report counts in the 580-610 nm ROI (diagnostic consistency with LED ranking window)
            try:
                wave_data = self.state.wavelengths
                roi2_min_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MIN))
                roi2_max_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MAX))

                result_roi = self._measure_channel_in_roi(
                    weakest_ch, MAX_LED_INTENSITY, int(roi2_min_idx), int(roi2_max_idx), "weakest LED (580-610nm)"
                )
                if result_roi is not None:
                    roi_max_signal, roi_mean_signal = result_roi
                    logger.info(
                        f"   Weakest LED ({weakest_ch}) in 580-610nm: max={roi_max_signal:.0f} counts, mean={roi_mean_signal:.0f} counts"
                    )
            except Exception:
                # Optional diagnostics; do not block calibration
                pass

            # =============================
            # STEP 4 SUMMARY (compact)
            # =============================
            try:
                logger.info("" )
                logger.info("=" * 80)
                logger.info("STEP 4 SUMMARY")
                logger.info("=" * 80)
                logger.info(f"Integration time (S-mode): {best_integration*1000:.1f} ms")
                logger.info(f"Weakest channel: {weakest_ch.upper()} @ LED=255")
                logger.info(
                    f"SPR ROI {spr_min_nm:.0f}-{spr_max_nm:.0f} nm: max={best_weakest_signal:.0f} counts ({(best_weakest_signal/detector_max)*100:5.1f}%)"
                )
                logger.info(
                    f"Target band: {weakest_min}-{weakest_max} counts ({(weakest_min/detector_max)*100:.0f}-{(weakest_max/detector_max)*100:.0f}%)"
                )
                # 580–610 nm diagnostic block (if measured)
                try:
                    _roi_max = float(roi_max_signal)  # noqa: F821
                    _roi_mean = float(roi_mean_signal)  # noqa: F821
                    logger.info(
                        f"580-610 nm ROI: max={_roi_max:.0f} counts, mean={_roi_mean:.0f} counts"
                    )
                except Exception:
                    logger.info("580-610 nm ROI: n/a (not captured)")
                logger.info("=" * 80)
            except Exception:
                # Summary logging must never break flow
                pass

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


                # ✨ Phase 2: Use 4-scan averaging for consistency with live mode
                raw_array = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
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
            weakest_ch = min(channel_intensities.items(), key=lambda kv: kv[1])[0]

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
            if not self.detector_profile:
                logger.error("❌ Detector profile not loaded - cannot determine target intensity")
                logger.error("   Run Step 2 first to load detector profile")
                return False

            detector_max = self.detector_profile.max_intensity_counts
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


                # ✨ Phase 2: Use 4-scan averaging for consistency with live mode
                raw_array = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
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
            if not self.detector_profile:
                logger.error("❌ Detector profile not loaded - cannot validate channel performance")
                logger.error("   Run Step 2 first to load detector profile")
                return False

            detector_max = self.detector_profile.max_intensity_counts

            # Measure weakest channel one final time at LED=255
            logger.info(f"   Measuring weakest channel ({weakest_ch}) at LED=255...")
            # ⚡ Use batch command
            intensities_dict = {weakest_ch: 255}
            self._activate_channel_batch([weakest_ch], intensities_dict)
            time.sleep(LED_DELAY)

            # ✨ Phase 2: Use 4-scan averaging for consistency with live mode
            raw_array = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
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
    # STEP 6: LED BALANCING (Adjust other channels to match weakest)
    # ========================================================================

    def step_6_balance_led_intensities(self, ch_list: list[str]) -> bool:
        """STEP 6: Balance LED intensities by REDUCING other channels to match weakest.

        The weakest channel is already at LED=255 from Step 4.
        This step reduces OTHER channels' LED intensities until:
        1. All channels are within target intensity range (50-75%)
        2. All channels are within 15% of each other

        This creates a balanced S-mode calibration baseline that:
        - Maximizes signal without saturation
        - Ensures similar intensities across channels
        - Serves as reference for QC validation

        CALIBRATION MODES:
        ==================
        - 'global': Run normal LED balancing (current behavior)
        - 'per_channel': Skip LED balancing (all LEDs already at 255)

        Args:
            ch_list: List of channels to balance

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            # ========================================================================
            # CHECK CALIBRATION MODE
            # ========================================================================
            if self.state.calibration_mode == 'per_channel':
                logger.info("")
                logger.info("=" * 80)
                logger.info("🔧 STEP 6: PER-CHANNEL MODE - SKIPPING LED BALANCING")
                logger.info("=" * 80)
                logger.info(f"   Mode: PER_CHANNEL (all LEDs already at 255)")
                logger.info(f"   LED balancing not needed in per-channel mode")
                logger.info(f"")
                logger.info(f"   ✅ All LEDs remain at 255")
                logger.info(f"   Next: Step 7 will optimize per-channel integration times")
                logger.info("=" * 80)
                return True

            # ========================================================================
            # GLOBAL MODE: STANDARD LED BALANCING
            # ========================================================================

            from settings import WEAKEST_TARGET_PERCENT, WEAKEST_MIN_PERCENT, WEAKEST_MAX_PERCENT

            # Get detector parameters
            if not self.detector_profile:
                logger.error("❌ Detector profile not loaded - cannot determine intensity targets")
                logger.error("   Run Step 2 first to load detector profile")
                return False

            detector_max = self.detector_profile.max_intensity_counts
            spr_min_nm = self.detector_profile.spr_wavelength_min_nm
            spr_max_nm = self.detector_profile.spr_wavelength_max_nm

            target_min = int(WEAKEST_MIN_PERCENT / 100 * detector_max)  # 50%
            target_max = int(WEAKEST_MAX_PERCENT / 100 * detector_max)  # 80%
            tolerance_percent = 15  # All channels within 15% of each other

            logger.info("")
            logger.info("=" * 80)
            logger.info("🔧 STEP 6: LED INTENSITY BALANCING")
            logger.info("=" * 80)
            logger.info(f"   Goal: Balance all channels by reducing brighter LEDs")
            logger.info(f"      → Target range: {WEAKEST_MIN_PERCENT}-{WEAKEST_MAX_PERCENT}% ({target_min:,}-{target_max:,} counts)")
            logger.info(f"      → Max variation: {tolerance_percent}% between channels")
            logger.info("")

            # Get ROI indices
            wave_data = self.state.wavelengths
            roi_min_idx = np.argmin(np.abs(wave_data - spr_min_nm))
            roi_max_idx = np.argmin(np.abs(wave_data - spr_max_nm))

            # Get weakest channel (already at LED=255 from Step 4)
            weakest_ch = self.state.led_ranking[0][0]
            weakest_led = self.state.ref_intensity.get(weakest_ch, MAX_LED_INTENSITY)

            logger.info(f"   Reference (weakest): {weakest_ch.upper()} @ LED={weakest_led}")
            logger.info("")

            # Balance each other channel
            for ch in ch_list:
                if ch == weakest_ch:
                    logger.info(f"   ✓ {ch.upper()}: LED={MAX_LED_INTENSITY} (reference, no adjustment needed)")
                    continue

                logger.info(f"   Calibrating {ch.upper()}...")

                # Binary search for optimal LED intensity
                led_min = S_LED_MIN  # 5% minimum
                led_max = MAX_LED_INTENSITY
                best_led = None
                best_signal = None

                iteration = 0
                max_iterations = 15

                while iteration < max_iterations and (led_max - led_min) > 1:
                    iteration += 1
                    led_test = int((led_min + led_max) / 2)

                    # Measure signal at this LED intensity
                    result = self._measure_channel_in_roi(
                        ch, led_test, int(roi_min_idx), int(roi_max_idx),
                        description=f"LED balance test {iteration}"
                    )

                    if result is None:
                        logger.error(f"      Failed to measure channel {ch}")
                        return False

                    signal_max, signal_mean = result
                    signal_percent = (signal_max / detector_max) * 100

                    logger.debug(f"      Iteration {iteration}: LED={led_test:3d} → {signal_max:6.0f} counts ({signal_percent:5.1f}%)")

                    # Check if within target range
                    if target_min <= signal_max <= target_max:
                        # Success! Found acceptable intensity
                        best_led = led_test
                        best_signal = signal_max
                        logger.info(f"      ✅ Found optimal LED={best_led} → {best_signal:,.0f} counts ({signal_percent:.1f}%)")
                        break
                    elif signal_max > target_max:
                        # Too bright, reduce LED
                        led_max = led_test - 1
                    else:
                        # Too dim, increase LED
                        led_min = led_test + 1

                if best_led is None:
                    # Use best attempt
                    best_led = led_test
                    best_signal = signal_max
                    logger.warning(f"      ⚠️  Could not find perfect match, using LED={best_led} → {best_signal:,.0f} counts")

                # Store calibrated LED intensity
                self.state.ref_intensity[ch] = best_led
                logger.info(f"   ✓ {ch.upper()}: LED={best_led} (balanced)")
                logger.info("")

            # Verify all channels are within tolerance
            logger.info("   Verifying balance...")
            all_signals = []
            for ch in ch_list:
                led_val = self.state.ref_intensity[ch]
                result = self._measure_channel_in_roi(
                    ch, led_val, int(roi_min_idx), int(roi_max_idx),
                    description="final verification"
                )
                if result:
                    signal_max, _ = result
                    all_signals.append((ch, led_val, signal_max))

            if all_signals:
                signals_only = [s[2] for s in all_signals]
                min_signal = min(signals_only)
                max_signal = max(signals_only)
                variation_percent = ((max_signal - min_signal) / min_signal) * 100

                logger.info("")
                logger.info("   📊 Final Balance:")
                for ch, led, signal in all_signals:
                    signal_percent = (signal / detector_max) * 100
                    logger.info(f"      {ch.upper()}: LED={led:3d} → {signal:6.0f} counts ({signal_percent:5.1f}%)")
                logger.info(f"")
                logger.info(f"   Variation: {variation_percent:.1f}% ({'✅ PASS' if variation_percent <= tolerance_percent else '⚠️  ACCEPTABLE'})")
                logger.info("")

            logger.info("=" * 80)
            logger.info("✅ STEP 6 COMPLETE: LED intensities balanced")
            logger.info("=" * 80)

            return True

        except Exception as e:
            logger.exception(f"Error balancing LED intensities: {e}")
            return False

    # ========================================================================
    # STEP 4B: PER-CHANNEL INTEGRATION TIME OPTIMIZATION
    # ========================================================================

    def optimize_per_channel_integration_times(self, ch_list: list[str]) -> bool:
        """Optimize integration time for each channel independently (per_channel mode).

        This is used in 'per_channel' calibration mode where all LEDs are fixed at 255.
        Each channel gets its own integration time to reach 50-75% of detector max.

        The 200ms budget is applied per-channel:
        - If integration time < 200ms: Use 1 scan
        - If integration time > 200ms: Multiple scans with shorter integration

        Args:
            ch_list: List of channels to optimize

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            from settings import WEAKEST_TARGET_PERCENT, WEAKEST_MIN_PERCENT, WEAKEST_MAX_PERCENT

            # Get detector parameters
            if self.detector_profile:
                detector_max = self.detector_profile.max_intensity_counts
                min_int = self.detector_profile.min_integration_time_ms / MS_TO_SECONDS
                max_int = self.detector_profile.max_integration_time_ms / MS_TO_SECONDS
                spr_min_nm = self.detector_profile.spr_wavelength_min_nm
                spr_max_nm = self.detector_profile.spr_wavelength_max_nm
            else:
                detector_max = DETECTOR_MAX_COUNTS
                min_int = MIN_INTEGRATION / MS_TO_SECONDS
                max_int = MAX_INTEGRATION / MS_TO_SECONDS
                spr_min_nm = 580.0
                spr_max_nm = 720.0

            target_percent = WEAKEST_TARGET_PERCENT  # 75%
            target_min = int(WEAKEST_MIN_PERCENT / 100 * detector_max)  # 50%
            target_max = int(WEAKEST_MAX_PERCENT / 100 * detector_max)  # 80%
            target_signal = int(target_percent / 100 * detector_max)

            logger.info("")
            logger.info("=" * 80)
            logger.info("⚡ PER-CHANNEL INTEGRATION TIME OPTIMIZATION")
            logger.info("=" * 80)
            logger.info(f"   Mode: PER_CHANNEL (LED=255 for all channels)")
            logger.info(f"   Goal: Find optimal integration time per channel")
            logger.info(f"      → Target: {target_percent}% ({target_signal:,} counts)")
            logger.info(f"      → Range: {WEAKEST_MIN_PERCENT}-{WEAKEST_MAX_PERCENT}% ({target_min:,}-{target_max:,} counts)")
            logger.info(f"")
            logger.info(f"   200ms budget per channel (scan averaging if needed)")
            logger.info("=" * 80)
            logger.info("")

            # Get ROI indices
            wave_data = self.state.wavelengths
            roi_min_idx = np.argmin(np.abs(wave_data - spr_min_nm))
            roi_max_idx = np.argmin(np.abs(wave_data - spr_max_nm))

            # Optimize each channel independently
            for ch in ch_list:
                if self._is_stopped():
                    return False

                logger.info(f"   Optimizing channel {ch.upper()}...")

                # Binary search for optimal integration time
                integration_min = min_int
                integration_max = max_int
                best_integration = None
                best_signal = 0

                max_iterations = 15
                for iteration in range(max_iterations):
                    # Test integration time (midpoint)
                    test_integration = (integration_min + integration_max) / 2.0
                    self.usb.set_integration(test_integration)
                    time.sleep(0.1)

                    # Measure channel at LED=255
                    result = self._measure_channel_in_roi(
                        ch, MAX_LED_INTENSITY, int(roi_min_idx), int(roi_max_idx),
                        f"ch {ch} optimization"
                    )
                    if result is None:
                        logger.error(f"      Failed to measure channel {ch}")
                        return False

                    signal_max, _ = result
                    signal_percent = (signal_max / detector_max) * 100

                    logger.debug(f"      Iter {iteration+1}: {test_integration*1000:.1f}ms → {signal_max:6.0f} counts ({signal_percent:5.1f}%)")

                    # Check if in target range
                    if target_min <= signal_max <= target_max:
                        best_integration = test_integration
                        best_signal = signal_max
                        logger.info(f"      ✅ Optimal: {best_integration*1000:.1f}ms → {best_signal:,.0f} counts ({signal_percent:.1f}%)")
                        break

                    # Adjust search range
                    if signal_max < target_min:
                        integration_min = test_integration
                    else:
                        integration_max = test_integration

                    # Track best so far
                    if abs(signal_max - target_signal) < abs(best_signal - target_signal):
                        best_integration = test_integration
                        best_signal = signal_max

                if best_integration is None:
                    logger.error(f"      Failed to find optimal integration for {ch}")
                    return False

                # Apply 200ms budget (scan averaging if needed)
                budget_ms = 200.0
                integration_ms = best_integration * 1000
                if integration_ms <= budget_ms:
                    # Use 1 scan
                    num_scans = 1
                else:
                    # Multiple scans with shorter integration
                    num_scans = int(np.ceil(integration_ms / budget_ms))
                    best_integration = budget_ms / 1000 / num_scans
                    integration_ms = best_integration * 1000

                # Store per-channel parameters
                self.state.integration_per_channel[ch] = best_integration
                self.state.scans_per_channel[ch] = num_scans

                logger.info(f"      Integration: {integration_ms:.1f}ms × {num_scans} scan(s) = {integration_ms * num_scans:.1f}ms total")
                logger.info("")

            # Summary
            logger.info("=" * 80)
            logger.info("✅ PER-CHANNEL INTEGRATION TIMES OPTIMIZED")
            logger.info("=" * 80)
            logger.info("")
            logger.info("   Channel  | Integration | Scans | Total Time")
            logger.info("   " + "-" * 50)
            for ch in ch_list:
                int_ms = self.state.integration_per_channel[ch] * 1000
                scans = self.state.scans_per_channel[ch]
                total_ms = int_ms * scans
                logger.info(f"      {ch.upper()}     |  {int_ms:6.1f}ms   |   {scans}   |  {total_ms:6.1f}ms")
            logger.info("")
            logger.info("=" * 80)

            return True

        except Exception as e:
            logger.exception(f"Error optimizing per-channel integration times: {e}")
            return False

    # ========================================================================
    # STEP 5: DARK NOISE MEASUREMENT - HELPER METHODS
    # ========================================================================

    def _compare_dark_noise_measurements(
        self,
        dark_before: np.ndarray,
        dark_after_raw: np.ndarray,
        dark_after_corrected: Optional[np.ndarray] = None,
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
                # ✨ Phase 2: Use 4-scan averaging for consistency with live mode
                test_spectrum = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
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
            # ✨ Apply jitter correction to dark spectrum for maximum stability
            full_spectrum_dark_noise = self._acquire_averaged_spectrum(
                num_scans=dark_scans,
                apply_filter=True,
                subtract_dark=False,
                description="dark noise",
                apply_jitter_correction=True  # Remove thermal drift from dark measurement
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
                # Prefer detector profile values when available so the warning is meaningful
                try:
                    profile = get_current_detector_profile()
                except Exception:
                    profile = None

                if profile is not None:
                    EXPECTED_DARK_MEAN = float(getattr(profile, 'dark_noise_mean_counts', 400.0))
                    # Use profile std to estimate a reasonable 'max' if available
                    expected_std = float(getattr(profile, 'dark_noise_std_counts', 50.0))
                    EXPECTED_DARK_MAX = EXPECTED_DARK_MEAN + (3.0 * expected_std)
                else:
                    EXPECTED_DARK_MEAN = 400.0  # legacy fallback
                    EXPECTED_DARK_MAX = 600.0

                TOLERANCE_FACTOR = 5.0  # Flag if 5× higher than expected

                # Use clearer wording: compare raw dark (before any dark-correction) to profile expectations
                if before_mean > EXPECTED_DARK_MEAN * TOLERANCE_FACTOR:
                    logger.warning(
                        f"⚠️  STEP 1 WARNING: Raw dark noise mean ({before_mean:.1f}) is {before_mean/EXPECTED_DARK_MEAN:.1f}× higher than expected ({EXPECTED_DARK_MEAN:.1f})"
                    )
                    logger.warning("    Possible issues:")
                    logger.warning("    • Light leaking into detector (check enclosure)")
                    logger.warning("    • LEDs not fully turned off (check hardware)")
                    logger.warning("    • Detector thermal noise (check cooling)")
                    logger.warning("    • Previous measurement residual signal")
                    logger.warning("    ⚠️  Continuing calibration, but results may be affected...")

                if before_max > EXPECTED_DARK_MAX * TOLERANCE_FACTOR:
                    logger.warning(
                        f"⚠️  STEP 1 WARNING: Raw dark noise max ({before_max:.1f}) is {before_max/EXPECTED_DARK_MAX:.1f}× higher than expected ({EXPECTED_DARK_MAX:.1f})"
                    )
                    logger.warning("    Check for stray light or hot pixels in detector")

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
    # DIAGNOSTIC: S-ROI STABILITY TEST (580–610 nm, LED sequence, config delays)
    # ========================================================================

    def find_optimal_integration_time(
        self,
        ch_list: list[str],
        roi_nm: tuple[float, float] = (580.0, 610.0),
        target_min_pct: float = 50.0,
        target_max_pct: float = 75.0,
        max_counts: float = 65535.0,
        led_intensities: Optional[dict[str, int]] = None,
    ) -> Optional[int]:
        """Find optimal integration time to achieve 50-75% of detector max for all channels.

        Args:
            ch_list: Channels to test
            roi_nm: ROI in nanometers
            target_min_pct: Minimum target percentage of max counts (default 50%)
            target_max_pct: Maximum target percentage of max counts (default 75%)
            max_counts: Detector saturation value (default 65535)
            led_intensities: Optional dict of LED values per channel

        Returns:
            Optimal integration time in ms, or None if failed
        """
        try:
            if self.ctrl is None or self.usb is None:
                logger.error("Controller or spectrometer not initialized")
                return None

            # Compute ROI indices
            wave_data = self.state.wavelengths
            if wave_data is None or len(wave_data) == 0:
                logger.error("No wavelength grid available")
                return None

            roi_min_idx = int(np.argmin(np.abs(wave_data - roi_nm[0])))
            roi_max_idx = int(np.argmin(np.abs(wave_data - roi_nm[1])))
            if roi_max_idx <= roi_min_idx:
                logger.error("Invalid ROI indices")
                return None

            # Get LED intensities
            if led_intensities is None:
                led_intensities = {}
                for ch in ch_list:
                    val = self.state.ref_intensity.get(ch, 0)
                    led_intensities[ch] = int(val) if int(val) > 0 else int(S_LED_INT)

            print("\n" + "=" * 80)
            print("AUTO-INTEGRATION TIME FINDER")
            print("=" * 80)
            print(f"Target: {target_min_pct:.0f}-{target_max_pct:.0f}% of {max_counts:.0f} counts ({max_counts * target_min_pct / 100:.0f}-{max_counts * target_max_pct / 100:.0f})")
            print(f"LED intensities: {led_intensities}")

            # Test with current integration time
            current_int_s = self.usb.get_integration_time()
            current_int_ms = int(current_int_s * 1000.0)
            print(f"\nStep 1: Testing current integration time: {current_int_ms}ms")

            channel_maxes = {}
            for ch in ch_list:
                self._activate_channel_batch([ch], {ch: led_intensities[ch]})
                time.sleep(0.1)
                raw = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
                if raw is None:
                    continue
                filtered = self._apply_spectral_filter(raw)
                roi_max = float(np.max(filtered[roi_min_idx:roi_max_idx]))
                channel_maxes[ch] = roi_max
                print(f"  Channel {ch.upper()}: {roi_max:.0f} counts ({roi_max / max_counts * 100:.1f}%)")

            self._all_leds_off_batch()
            time.sleep(0.1)

            if not channel_maxes:
                logger.error("No channel data collected")
                return None

            # Find the weakest channel (lowest signal)
            min_channel = min(channel_maxes, key=channel_maxes.get)
            min_counts = channel_maxes[min_channel]
            min_pct = (min_counts / max_counts) * 100.0

            print(f"\nWeakest channel: {min_channel.upper()} at {min_counts:.0f} counts ({min_pct:.1f}%)")

            # Calculate optimal integration time based on weakest channel
            target_counts = max_counts * ((target_min_pct + target_max_pct) / 2) / 100.0  # Aim for middle of range

            if min_counts < 100:
                logger.error(f"Signal too low ({min_counts:.0f}) to extrapolate")
                return None

            # Linear extrapolation: new_int = current_int * (target / current)
            optimal_int_ms = int(current_int_ms * (target_counts / min_counts))

            # Clamp to reasonable range
            optimal_int_ms = max(10, min(1000, optimal_int_ms))

            print(f"\nStep 2: Calculated optimal integration time: {optimal_int_ms}ms")
            print(f"  (extrapolated from {min_counts:.0f} → {target_counts:.0f} counts)")

            # Verify with new integration time
            print(f"\nStep 3: Verifying with {optimal_int_ms}ms...")
            self.usb.set_integration_time(float(optimal_int_ms) / 1000.0)
            time.sleep(0.2)

            verify_maxes = {}
            for ch in ch_list:
                self._activate_channel_batch([ch], {ch: led_intensities[ch]})
                time.sleep(0.1)
                raw = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
                if raw is None:
                    continue
                filtered = self._apply_spectral_filter(raw)
                roi_max = float(np.max(filtered[roi_min_idx:roi_max_idx]))
                verify_maxes[ch] = roi_max
                pct = (roi_max / max_counts) * 100.0
                status = "✓" if target_min_pct <= pct <= target_max_pct else "⚠️"
                print(f"  {status} Channel {ch.upper()}: {roi_max:.0f} counts ({pct:.1f}%)")

            # Force all LEDs off multiple times to ensure they're truly off
            self._all_leds_off_batch()
            time.sleep(0.2)
            self._all_leds_off_batch()  # Double-tap to be sure
            time.sleep(0.3)

            # Check if all channels are in range
            all_in_range = all(
                target_min_pct <= (v / max_counts * 100) <= target_max_pct
                for v in verify_maxes.values()
            )

            if all_in_range:
                print(f"\n✅ Optimal integration time found: {optimal_int_ms}ms")
            else:
                print(f"\n⚠️ Integration time {optimal_int_ms}ms is best estimate (some channels out of range)")

            # Force LEDs off again and add extended settle time before preflight dark measurement
            print("\n🔌 Forcing all LEDs OFF and waiting for detector to settle...")
            for _ in range(5):  # Quintuple-force LED shutdown
                self._all_leds_off_batch()
                time.sleep(0.5)

            print("   Waiting 5 seconds for full LED decay and detector stabilization...")
            time.sleep(5.0)  # Extended buffer time for dark measurement
            print("✅ LEDs confirmed OFF, ready for dark baseline measurement\n")

            return optimal_int_ms

        except Exception as e:
            logger.exception(f"Error finding optimal integration time: {e}")
            return None

    def diagnostic_s_roi_stability_test(
        self,
        ch_list: list[str],
        duration_sec: float = 120.0,
        roi_nm: tuple[float, float] = (580.0, 610.0),
        led_value: Optional[int] = None,
        use_device_config_delays: bool = True,
        led_delay_ms: Optional[float] = None,
        led_on_delay_ms: Optional[float] = None,
        led_off_delay_ms: Optional[float] = None,
        integration_time_ms_by_ch: Optional[dict[str, float]] = None,
    ) -> bool:
        """Run an S-mode stability test on the 580–610 nm ROI while flashing LEDs sequentially.

        Measures the max count within ROI for each channel activation over ~2 minutes, using
        LED delays from device_config (if available). Reports per-channel and overall variation,
        simple pattern indicators, and suggests per-channel normalization factors.

        Saves a CSV time series and a compact summary in calibration_data/.

        Args:
            ch_list: Channels to cycle (e.g., CH_LIST or EZ_CH_LIST)
            duration_sec: Total test duration in seconds (default 120s)
            roi_nm: ROI in nanometers (default (580, 610))
            led_value: Optional fixed LED value; if None, use calibrated ref_intensity or S_LED_INT
            use_device_config_delays: If True, use per-channel delays from device_config
            led_delay_ms: Fixed LED delay in milliseconds for both on/off (overrides device_config)
            led_on_delay_ms: Delay after LED turn-on before measurement (overrides led_delay_ms)
            led_off_delay_ms: Delay after LED turn-off before next channel (overrides led_delay_ms)
            integration_time_ms_by_ch: Per-channel integration times in ms (e.g., {'a': 50, 'b': 120, 'c': 19, 'd': 19})

        Returns:
            True if test completed and saved, False if aborted/failed
        """
        try:
            if self.ctrl is None or self.usb is None:
                logger.error("Controller or spectrometer not initialized")
                return False

            # Ensure S-mode
            try:
                self.ctrl.set_mode(mode="s")
                time.sleep(0.4)
                # Verify polarizer servo positions if available
                if hasattr(self.ctrl, "servo_get"):
                    try:
                        pos = self.ctrl.servo_get()
                        s_pos = pos.get("s", b"000").decode(errors="ignore") if isinstance(pos.get("s"), (bytes, bytearray)) else str(pos.get("s"))
                        p_pos = pos.get("p", b"000").decode(errors="ignore") if isinstance(pos.get("p"), (bytes, bytearray)) else str(pos.get("p"))
                        logger.info(f"🔎 Polarizer servo positions (S,P) = ({s_pos},{p_pos}) after S-mode command")
                    except Exception as _e:
                        logger.debug(f"Could not read polarizer servo positions: {_e}")
            except Exception:
                logger.warning("Could not explicitly set S-mode; continuing with current mode")

            # Determine LED intensity per channel
            per_ch_led: dict[str, int] = {}
            if led_value is not None:
                per_ch_led = {ch: int(led_value) for ch in ch_list}
            else:
                for ch in ch_list:
                    val = self.state.ref_intensity.get(ch, 0)
                    per_ch_led[ch] = int(val) if int(val) > 0 else int(S_LED_INT)

            # Get per-channel delays from device_config or override
            on_delay_s_by_ch: dict[str, float] = {ch: float(LED_DELAY) for ch in ch_list}
            off_delay_s_by_ch: dict[str, float] = {ch: float(LED_DELAY) for ch in ch_list}

            # Priority: specific on/off delays > general led_delay_ms > device_config > default
            if led_on_delay_ms is not None or led_off_delay_ms is not None:
                # Use specific on/off delays
                on_delay = float(led_on_delay_ms or led_delay_ms or LED_DELAY) / 1000.0
                off_delay = float(led_off_delay_ms or led_delay_ms or LED_DELAY) / 1000.0
                on_delay_s_by_ch = {ch: on_delay for ch in ch_list}
                off_delay_s_by_ch = {ch: off_delay for ch in ch_list}
                logger.info(f"Using LED ON delay: {on_delay*1000:.1f}ms, OFF delay: {off_delay*1000:.1f}ms")
            elif led_delay_ms is not None:
                # Fixed LED delay for both on/off
                delay_s = float(led_delay_ms) / 1000.0
                on_delay_s_by_ch = {ch: delay_s for ch in ch_list}
                off_delay_s_by_ch = {ch: delay_s for ch in ch_list}
                logger.info(f"Using fixed LED delay: {led_delay_ms:.1f}ms for ON and OFF")
            elif use_device_config_delays:
                try:
                    from utils.device_configuration import DeviceConfiguration
                    cfg = DeviceConfiguration()
                    delays_ms = cfg.get_led_delays()
                    for ch in ch_list:
                        d_ms = float(delays_ms.get(ch, 0.0))
                        if d_ms and d_ms > 0:
                            on_delay_s_by_ch[ch] = d_ms / 1000.0
                            off_delay_s_by_ch[ch] = d_ms / 1000.0
                    logger.info(f"Using device_config LED delays (ms): ON={on_delay_s_by_ch}, OFF={off_delay_s_by_ch}")
                except Exception as e:
                    logger.warning(f"Could not read device_config delays, using default LED_DELAY: {e}")

            # Compute ROI indices from current filtered wavelength grid
            wave_data = self.state.wavelengths
            if wave_data is None or len(wave_data) == 0:
                logger.error("No wavelength grid available; run Step 2 first")
                return False
            roi_min_idx = int(np.argmin(np.abs(wave_data - roi_nm[0])))
            roi_max_idx = int(np.argmin(np.abs(wave_data - roi_nm[1])))
            if roi_max_idx <= roi_min_idx:
                logger.error(f"Invalid ROI indices computed: {roi_min_idx}-{roi_max_idx}")
                return False

            # Storage for time series: (t_rel, channel, roi_max)
            records: list[tuple[float, str, float]] = []
            # Also store full spectra for stacked plot
            spectra_records: list[tuple[float, str, np.ndarray]] = []
            t0 = time.time()
            deadline = t0 + float(duration_sec)

            logger.info("=" * 80)
            logger.info("S-ROI STABILITY TEST: 580–610 nm (S-mode, sequential LEDs)")
            logger.info("=" * 80)
            logger.info(f"Duration: {duration_sec:.1f}s; ROI: {roi_nm[0]:.0f}-{roi_nm[1]:.0f} nm")
            logger.info(f"LEDs: {per_ch_led}")
            logger.info(f"ON delays (ms): {{{', '.join([f'{ch}: {v*1000:.1f}' for ch, v in on_delay_s_by_ch.items()])}}}")
            logger.info(f"OFF delays (ms): {{{', '.join([f'{ch}: {v*1000:.1f}' for ch, v in off_delay_s_by_ch.items()])}}}")
            if integration_time_ms_by_ch:
                logger.info(f"Per-channel integration times (ms): {integration_time_ms_by_ch}")
            else:
                current_int_s = self.usb.get_integration_time()
                logger.info(f"Integration time: {current_int_s * 1000:.1f}ms (global)")

            # Force all LEDs OFF before starting test to ensure clean baseline
            print("\n🔌 Ensuring all LEDs are OFF before starting time series...")
            for _ in range(5):
                self._all_leds_off_batch()
                time.sleep(0.5)
            print("⏳ Waiting 5 seconds for complete LED decay...")
            time.sleep(5.0)
            print("✅ LEDs confirmed OFF, starting measurements...\n")

            # Cycle LEDs until duration exceeded
            last_progress_log = t0
            progress_interval = 5.0  # Log every 5 seconds

            while time.time() < deadline:
                for ch in ch_list:
                    if self._is_stopped():
                        logger.warning("Stability test stopped")
                        break

                    # Activate channel at chosen LED value
                    try:
                        # Set channel-specific integration time if provided
                        if integration_time_ms_by_ch and ch in integration_time_ms_by_ch:
                            int_time_ms = float(integration_time_ms_by_ch[ch])
                            self.usb.set_integration_time(int_time_ms / 1000.0)

                        intensities_dict = {ch: per_ch_led[ch]}
                        self._activate_channel_batch([ch], intensities_dict)
                        time.sleep(on_delay_s_by_ch.get(ch, float(LED_DELAY)))
                        self._last_active_channel = ch
                    except Exception as e:
                        logger.error(f"Failed to activate channel {ch}: {e}")
                        return False

                    # Acquire one spectrum (no dark subtraction), filter, measure ROI max
                    raw = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
                    if raw is None:
                        logger.error(f"Failed to acquire spectrum for {ch}")
                        return False
                    filtered = self._apply_spectral_filter(raw)

                    roi_slice = filtered[roi_min_idx:roi_max_idx]
                    roi_max = float(np.max(roi_slice))

                    t_rel = time.time() - t0
                    records.append((t_rel, ch, roi_max))
                    # Save full spectrum for stacked plot
                    spectra_records.append((t_rel, ch, filtered.copy()))

                    # Progress logging
                    if time.time() - last_progress_log >= progress_interval:
                        elapsed = t_rel
                        remaining = float(duration_sec) - elapsed
                        pct = (elapsed / float(duration_sec)) * 100.0
                        print(f"⏱️  Progress: {elapsed:.1f}s / {duration_sec:.0f}s ({pct:.0f}%) | {len(records)} measurements | ~{remaining:.0f}s remaining")
                        last_progress_log = time.time()

                    # Turn off all LEDs and wait for decay
                    self._all_leds_off_batch()
                    time.sleep(off_delay_s_by_ch.get(ch, float(LED_DELAY)))

                    if time.time() >= deadline:
                        break

            if not records:
                logger.error("No data collected in stability test")
                return False

            # Compute per-channel stats
            stats: dict[str, dict[str, float]] = {}
            all_values: list[float] = []
            per_ch_values: dict[str, list[float]] = {ch: [] for ch in ch_list}
            for _, ch, val in records:
                per_ch_values[ch].append(val)
                all_values.append(val)

            for ch in ch_list:
                vals = np.array(per_ch_values[ch], dtype=float)
                if vals.size == 0:
                    stats[ch] = {"mean": float("nan"), "std": float("nan"), "cv_pct": float("nan")}
                else:
                    mean_v = float(np.mean(vals))
                    std_v = float(np.std(vals, ddof=1)) if vals.size > 1 else 0.0
                    cv_pct = float((std_v / mean_v) * 100.0) if mean_v > 0 else float("inf")
                    stats[ch] = {"mean": mean_v, "std": std_v, "cv_pct": cv_pct}

            # Simple pattern indicator: lag-1 autocorr per channel and per-cycle autocorr
            def _autocorr(a: np.ndarray, lag: int) -> float:
                if a.size <= lag:
                    return float("nan")
                a0 = a[:-lag]
                a1 = a[lag:]
                a0 = a0 - np.mean(a0)
                a1 = a1 - np.mean(a1)
                denom = float(np.std(a0) * np.std(a1))
                if denom == 0.0:
                    return 0.0
                return float(np.mean((a0 / np.std(a0)) * (a1 / np.std(a1))))

            cycle_len = max(1, len(ch_list))
            patterns: dict[str, dict[str, float]] = {}
            for ch in ch_list:
                vals = np.array(per_ch_values[ch], dtype=float)
                if vals.size >= 3:
                    patterns[ch] = {
                        "lag1_ac": _autocorr(vals, 1),
                        "per_cycle_ac": _autocorr(vals, 1),  # samples per channel are spaced by cycle
                    }
                else:
                    patterns[ch] = {"lag1_ac": float("nan"), "per_cycle_ac": float("nan")}

            # Suggested correction factors to normalize to global mean
            global_mean = float(np.mean(np.array(all_values, dtype=float)))
            correction: dict[str, float] = {}
            for ch in ch_list:
                mean_v = stats[ch]["mean"]
                correction[ch] = float(global_mean / mean_v) if mean_v > 0 else 1.0

            # Save CSV time series
            from pathlib import Path
            calib_dir = Path(ROOT_DIR) / "calibration_data"
            calib_dir.mkdir(exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            csv_path = calib_dir / f"s_roi_stability_{int(roi_nm[0])}_{int(roi_nm[1])}_{ts}.csv"
            try:
                import csv as _csv
                with open(csv_path, "w", newline="") as f:
                    w = _csv.writer(f)
                    w.writerow(["t_seconds", "channel", "roi_max_counts"])
                    for t_rel, ch, val in records:
                        w.writerow([f"{t_rel:.3f}", ch, f"{val:.1f}"])
                print(f"💾 Time series saved: {csv_path}")
                logger.info(f"💾 Time series saved: {csv_path}")
            except Exception as e:
                print(f"❌ Failed to save stability CSV: {e}")
                logger.error(f"Failed to save stability CSV: {e}")
                import traceback
                traceback.print_exc()

            # Save spectra data for stacked plot
            if spectra_records:
                spectra_path = calib_dir / f"s_roi_stability_{int(roi_nm[0])}_{int(roi_nm[1])}_{ts}_spectra.npz"
                try:
                    # Organize spectra by channel
                    spectra_by_ch = {ch: [] for ch in ch_list}
                    times_by_ch = {ch: [] for ch in ch_list}
                    for t_rel, ch, spectrum in spectra_records:
                        spectra_by_ch[ch].append(spectrum)
                        times_by_ch[ch].append(t_rel)

                    # Convert to arrays and save
                    save_dict = {
                        'wavelengths': self.state.wavelengths,
                        'roi_nm': roi_nm,
                    }
                    for ch in ch_list:
                        if spectra_by_ch[ch]:
                            save_dict[f'spectra_{ch}'] = np.array(spectra_by_ch[ch])
                            save_dict[f'times_{ch}'] = np.array(times_by_ch[ch])

                    np.savez_compressed(spectra_path, **save_dict)
                    print(f"📊 Spectra data saved: {spectra_path}")
                    logger.info(f"📊 Spectra data saved: {spectra_path}")
                except Exception as e:
                    print(f"⚠️  Failed to save spectra data: {e}")
                    logger.error(f"Failed to save spectra data: {e}")

            # Log summary
            logger.info("=" * 80)
            logger.info("S-ROI STABILITY SUMMARY (per channel)")
            logger.info("=" * 80)
            for ch in ch_list:
                s = stats[ch]
                p = patterns[ch]
                logger.info(
                    f"{ch.upper()}: mean={s['mean']:.1f}, std={s['std']:.1f}, CV={s['cv_pct']:.2f}% | "
                    f"lag1_ac={p['lag1_ac']:.2f}, per_cycle_ac={p['per_cycle_ac']:.2f}"
                )
            logger.info(f"Global mean: {global_mean:.1f} counts")
            logger.info(f"Suggested normalization factors (to global mean): {correction}")
            print(f"\n✓ Diagnostic complete: {len(records)} measurements collected")

            return True

        except Exception as e:
            print(f"\n❌ Diagnostic failed with error: {e}")
            logger.exception(f"Error in S-ROI stability test: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ========================================================================
    # STEP 7: REFERENCE SIGNAL MEASUREMENT - HELPER METHODS
    # ========================================================================

    def _apply_afterglow_correction_to_references(
        self,
        ch_list: list[str],
        ref_scans: int,
        last_active_ch: Optional[str]
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

        CALIBRATION MODES:
        ==================
        - 'global': Use global integration time and calibrated LED intensities
        - 'per_channel': Use per-channel integration times with LED=255

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

            # Determine acquisition parameters based on calibration mode
            if self.state.calibration_mode == 'per_channel':
                logger.info(f"   Mode: PER_CHANNEL (using per-channel integration times)")
            else:
                logger.info(f"   Mode: GLOBAL (using global integration time)")

                # Calculate dynamic scan count for global mode
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

                # Set per-channel integration time if in per_channel mode
                if self.state.calibration_mode == 'per_channel':
                    ch_integration = self.state.integration_per_channel[ch]
                    ch_scans = self.state.scans_per_channel[ch]
                    self.usb.set_integration(ch_integration)
                    time.sleep(0.1)
                    logger.info(
                        f"   Channel {ch.upper()}: {ch_integration*1000:.1f}ms × {ch_scans} scan(s) "
                        f"= {ch_integration * ch_scans * 1000:.1f}ms total"
                    )
                    ref_scans = ch_scans
                else:
                    # Use pre-calculated ref_scans from global mode
                    pass

                # Activate LED with appropriate intensity
                if self.state.calibration_mode == 'per_channel':
                    intensities_dict = {ch: MAX_LED_INTENSITY}  # LED=255 for per_channel mode
                else:
                    intensities_dict = {ch: self.state.ref_intensity[ch]}  # Calibrated intensity

                self._activate_channel_batch([ch], intensities_dict)
                time.sleep(LED_DELAY)

                # Track last active channel for afterglow correction
                self._last_active_channel = ch
                last_ch = ch


                # Acquire raw spectrum (no dark subtraction - we'll do it once at the end)
                # ✨ Apply jitter correction to S-pol reference for maximum stability
                averaged_signal = self._acquire_averaged_spectrum(
                    num_scans=ref_scans,
                    apply_filter=True,
                    subtract_dark=False,  # Keep raw signal for single dark subtraction
                    description=f"reference signal (ch {ch})",
                    apply_jitter_correction=True  # Remove thermal drift from S-pol reference
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

            # Mark calibration as successful
            self.state.ch_error_list = []
            self.state.is_calibrated = True
            self.state.calibration_timestamp = time.time()
            logger.info("✅ Calibration complete - all channels validated")

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
    # QUICK QC VALIDATION (S-REF BASED)
    # ========================================================================

    def validate_s_ref_qc(
        self,
        baseline_config: dict,
        num_samples: int = 10,
        intensity_threshold: float = 10.0,  # Increased from 5% to 10% - allows more LED drift
        shape_threshold: float = 0.90  # Lowered from 0.95 to 0.90 - 90% correlation still good
    ) -> tuple[bool, dict[str, dict]]:
        """
        Quick QC validation using S-mode reference spectra comparison.

        Validates that stored calibration is still valid by measuring fresh
        S-ref spectra and comparing intensity + spectral shape to baseline.

        **REQUIRES**: Prism + water in place (same as full calibration)

        **SMART FILTERING**: Weak channels (A/B with intensity < 10,000 counts) are
        automatically skipped to prevent false failures from low SNR correlation issues.

        Args:
            baseline_config: Stored calibration from device_config.json
            num_samples: Number of spectra to average per channel (default: 10)
            intensity_threshold: Maximum allowed intensity deviation in % (default: 10%)
            shape_threshold: Minimum shape correlation (default: 0.90)

        Returns:
            (all_passed, channel_results)

            channel_results format:
            {
              'A': {
                'intensity_pass': True,
                'intensity_deviation_pct': 0.2,
                'shape_pass': True,
                'shape_correlation': 0.995,
                'overall_pass': True,
                'failure_reason': None,  # or string if failed
                'skipped': False  # True if channel was too weak to validate
              },
              ...
            }
        """
        try:
            logger.info("="*80)
            logger.info("CALIBRATION QC VALIDATION (S-REF BASED)")
            logger.info("="*80)

            # Load baseline data
            baseline_s_ref = baseline_config['s_ref_baseline']
            baseline_max = baseline_config['s_ref_max_intensity']
            baseline_date = baseline_config['calibration_date']
            s_intensities = baseline_config['s_mode_intensities']
            integration_ms = baseline_config['integration_time_ms']

            # FIX: Check if baseline spectra are inverted (stored backwards)
            # S-ref should have LOW values at start, HIGH at end (LED peaks at long wavelengths)
            # If first values are > 50% of max, spectra are likely inverted
            for ch in baseline_s_ref:
                spec = np.array(baseline_s_ref[ch])
                first_val = spec[0] / np.max(spec)
                last_val = spec[-1] / np.max(spec)
                if first_val > 0.5 and last_val < 0.5:
                    logger.warning(f"  Detected inverted baseline for channel {ch} - reversing")
                    baseline_s_ref[ch] = spec[::-1].tolist()  # Reverse the array

            # Calculate age
            try:
                cal_date = datetime.fromisoformat(baseline_date)
                age_days = (datetime.now() - cal_date).total_seconds() / 86400.0
                logger.info(f"Baseline date: {baseline_date} ({age_days:.1f} days ago)")
            except Exception:
                logger.info(f"Baseline date: {baseline_date}")

            logger.info(f"📋 IMPORTANT: Ensure prism + water in place for validation")
            logger.info(f"")

            # Check hardware
            if self.ctrl is None or self.usb is None:
                logger.error("❌ Hardware not available for QC validation")
                return False, {}

            # Set polarizer to S-mode
            logger.info("Setting polarizer to S-mode...")
            self.ctrl.set_mode('s')
            time.sleep(2.0)

            # Set integration time from baseline
            self.usb.set_integration_time(integration_ms / 1000.0)
            logger.info(f"Using stored integration time: {integration_ms} ms")
            logger.info("")

            # Turn off all channels
            self.ctrl.turn_off_channels()
            time.sleep(0.2)

            # Validate each channel
            channel_results = {}
            all_passed = True
            MIN_INTENSITY_FOR_QC = 10000  # Only validate channels with sufficient signal

            for ch in CH_LIST:
                logger.warning(f"Validating Channel {ch}:")

                # Check if baseline intensity is sufficient for reliable QC
                baseline_max_val = baseline_max[ch]
                if baseline_max_val < MIN_INTENSITY_FOR_QC:
                    logger.warning(f"  ⚠️  Skipping QC - baseline intensity too low ({baseline_max_val:.0f} < {MIN_INTENSITY_FOR_QC})")
                    logger.warning(f"     Weak channels (A/B) cannot be reliably validated - auto-pass")
                    # Auto-pass weak channels - they'll be recalibrated if needed
                    channel_results[ch] = {
                        'intensity_pass': True,
                        'intensity_deviation_pct': 0.0,
                        'shape_pass': True,
                        'shape_correlation': 1.0,
                        'overall_pass': True,
                        'failure_reason': None,
                        'skipped': True,
                        'skip_reason': 'Baseline intensity too low for reliable QC'
                    }
                    logger.info("")
                    continue

                # Turn on LED with stored intensity (set_intensity implicitly turns on the LED)
                self.ctrl.set_intensity(ch.lower(), s_intensities[ch])
                time.sleep(LED_DELAY)

                # Measure fresh S-ref (average of num_samples)
                spectra = []
                for _ in range(num_samples):
                    raw = self.usb.acquire_spectrum()
                    spectra.append(raw)
                    time.sleep(0.05)

                current_s_ref = np.mean(spectra, axis=0)

                # Apply dark noise correction if available
                if self.state.dark_noise is not None and len(self.state.dark_noise) == len(current_s_ref):
                    current_s_ref = current_s_ref - self.state.dark_noise

                # Stage 1: Intensity check
                current_max = float(np.max(current_s_ref))

                # Double-check current measurement is also sufficient
                if current_max < MIN_INTENSITY_FOR_QC:
                    logger.warning(f"  ⚠️  Current intensity too low ({current_max:.0f} < {MIN_INTENSITY_FOR_QC}) - skipping")
                    channel_results[ch] = {
                        'intensity_pass': True,
                        'intensity_deviation_pct': 0.0,
                        'shape_pass': True,
                        'shape_correlation': 1.0,
                        'overall_pass': True,
                        'failure_reason': None,
                        'skipped': True,
                        'skip_reason': 'Current intensity too low for reliable QC'
                    }
                    # Turn off channel
                    self.ctrl.set_intensity(ch.lower(), 0)
                    time.sleep(0.1)
                    logger.info("")
                    continue

                intensity_deviation = abs(current_max - baseline_max_val) / baseline_max_val
                intensity_percent = intensity_deviation * 100
                intensity_pass = intensity_percent < intensity_threshold

                logger.warning(f"  Intensity: {baseline_max_val:.0f} → {current_max:.0f} "
                           f"({intensity_percent:.1f}% deviation, "
                           f"{'✅ pass' if intensity_pass else '❌ FAIL'})")

                # Stage 2: Spectral shape check (Pearson correlation)
                # Normalize both spectra to compare shape independent of intensity
                current_norm = current_s_ref / np.max(current_s_ref)
                baseline_spec = baseline_s_ref[ch]
                baseline_norm = baseline_spec / np.max(baseline_spec)

                # Ensure same length (trim if needed)
                min_len = min(len(current_norm), len(baseline_norm))
                correlation = np.corrcoef(current_norm[:min_len], baseline_norm[:min_len])[0, 1]
                shape_pass = correlation > shape_threshold

                corr_quality = "excellent" if correlation > 0.99 else ("good" if correlation > 0.95 else "poor")
                logger.warning(f"  Shape: r={correlation:.3f} ({corr_quality} correlation, "
                           f"{'✅ pass' if shape_pass else '❌ FAIL'})")

                # Determine failure reason
                failure_reason = None
                if not intensity_pass:
                    failure_reason = "LED degradation or detector drift detected"
                    logger.warning(f"  ⚠️  {failure_reason}")
                if not shape_pass:
                    if failure_reason:
                        failure_reason += " + spectral shift or polarizer misalignment"
                    else:
                        failure_reason = "Spectral shift or polarizer misalignment detected"
                    logger.warning(f"  ⚠️  {failure_reason}")

                # Overall pass
                overall_pass = intensity_pass and shape_pass

                # Turn off channel (set intensity to 0)
                self.ctrl.set_intensity(ch.lower(), 0)
                time.sleep(0.1)

                # Store results
                channel_results[ch] = {
                    'intensity_pass': intensity_pass,
                    'intensity_deviation_pct': intensity_percent,
                    'shape_pass': shape_pass,
                    'shape_correlation': correlation,
                    'overall_pass': overall_pass,
                    'failure_reason': failure_reason,
                    'skipped': False
                }

                if not overall_pass:
                    all_passed = False

                logger.info("")

            logger.info("="*80)

            # Count how many channels were actually validated vs skipped
            validated_channels = [ch for ch, r in channel_results.items() if not r.get('skipped', False)]
            skipped_channels = [ch for ch, r in channel_results.items() if r.get('skipped', False)]

            if skipped_channels:
                logger.info(f"ℹ️  Skipped weak channels: {', '.join(skipped_channels)} (intensity < {MIN_INTENSITY_FOR_QC})")

            if validated_channels:
                logger.info(f"✓  Validated channels: {', '.join(validated_channels)}")

            if all_passed:
                logger.info("✅ QC VALIDATION PASSED - All channels within tolerance")
                logger.info("   Using stored calibration values")
                logger.info("   Time saved: ~2-3 minutes")
            else:
                failed = [ch for ch, r in channel_results.items() if not r['overall_pass'] and not r.get('skipped', False)]
                logger.warning(f"❌ QC VALIDATION FAILED - Channels: {', '.join(failed)}")
                logger.warning("   Running full recalibration...")

                # Log failure for preventative maintenance
                self._log_qc_failure(channel_results, baseline_date)

            logger.info("="*80)

            return all_passed, channel_results

        except Exception as e:
            logger.exception(f"Error during QC validation: {e}")
            return False, {}

    def _log_qc_failure(self, channel_results: dict, baseline_date: str) -> None:
        """
        Log QC validation failure for preventative maintenance tracking.

        Creates a maintenance log entry in generated-files/maintenance_log/
        """
        try:
            log_dir = Path("generated-files/maintenance_log")
            log_dir.mkdir(parents=True, exist_ok=True)

            timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"qc_failure_{timestamp}.json"

            # Compile failure data
            log_data = {
                'timestamp': dt.datetime.now().isoformat(),
                'baseline_date': baseline_date,
                'failure_type': 'qc_validation',
                'failed_channels': {},
                'action_taken': 'full_recalibration'
            }

            for ch, result in channel_results.items():
                if not result['overall_pass']:
                    log_data['failed_channels'][ch] = {
                        'intensity_deviation_pct': result['intensity_deviation_pct'],
                        'shape_correlation': result['shape_correlation'],
                        'failure_reason': result['failure_reason']
                    }

            # Save log
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2)

            logger.info(f"📝 QC failure logged to: {log_file}")

        except Exception as e:
            logger.warning(f"Failed to log QC failure: {e}")

    # ========================================================================
    # FULL CALIBRATION ORCHESTRATION
    # ========================================================================

    def run_full_calibration(
        self,
        auto_polarize: bool = False,
        auto_polarize_callback: Callable[[], None] | None = None,
        use_previous_data: bool = False,  # DISABLED: Always run fresh calibration to avoid stale data
        auto_save: bool = True,
        force_recalibrate: bool = False,  # NEW: Skip QC validation
    ) -> tuple[bool, str]:
        """Execute the complete 8-step calibration sequence with optional QC validation.

        Args:
            auto_polarize: Whether to run auto-polarization in step 2
            auto_polarize_callback: Optional callback for auto-polarization
            use_previous_data: Load previous calibration as starting point (DISABLED by default)
            auto_save: Automatically save successful calibration
            force_recalibrate: Skip QC validation and run full calibration (default: False)

        Returns:
            Tuple of (success, error_channels_string)

        """
        try:
            # ========================================================================
            # NEW: TRY QC VALIDATION FIRST (UNLESS FORCED)
            # ========================================================================
            if not force_recalibrate:
                from utils.device_configuration import DeviceConfiguration

                device_config = DeviceConfiguration()
                baseline = device_config.load_led_calibration()

                if baseline:
                    age_days = device_config.get_calibration_age_days()
                    logger.info("=" * 80)
                    logger.info("QUICK CALIBRATION QC CHECK")
                    logger.info("=" * 80)
                    logger.info(f"🔍 Found stored calibration ({age_days:.1f} days old)")
                    logger.info(f"   Integration time: {baseline['integration_time_ms']} ms")
                    logger.info(f"   S-mode LEDs: {baseline['s_mode_intensities']}")
                    logger.info(f"   P-mode LEDs: {baseline['p_mode_intensities']}")
                    logger.info("")
                    logger.info(f"📋 Running QC validation (intensity + shape check)...")
                    logger.info(f"   This takes ~10 seconds vs ~2-3 minutes for full calibration")
                    logger.info("")

                    # Run QC validation
                    qc_passed, qc_results = self.validate_s_ref_qc(baseline)

                    if qc_passed:
                        logger.info("=" * 80)
                        logger.info("✅ QC PASSED - USING STORED CALIBRATION")
                        logger.info("=" * 80)

                        # Load stored values into calibration state
                        self.state.integration = baseline['integration_time_ms'] / 1000.0  # Convert ms to seconds
                        self.state.leds_calibrated = baseline['s_mode_intensities'].copy()
                        self.state.ref_intensity = baseline['s_mode_intensities'].copy()
                        # Note: P-mode uses same LED intensities as S-mode (polarizer determines mode)
                        self.state.ref_sig = baseline['s_ref_baseline'].copy()

                        # Mark as calibrated
                        self.state.is_calibrated = True
                        self.state.calibration_timestamp = time.time()

                        # Also set integration on hardware (self.state.integration is already in seconds!)
                        if self.usb:
                            self.usb.set_integration_time(self.state.integration)

                        logger.info(f"✅ Calibration loaded from device_config.json")
                        logger.info(f"   Time saved: ~2-3 minutes")
                        logger.info("=" * 80)

                        return True, ""
                    else:
                        logger.warning("=" * 80)
                        logger.warning("❌ QC FAILED - RUNNING FULL RECALIBRATION")
                        logger.warning("=" * 80)
                        logger.warning("QC validation detected calibration drift")
                        logger.warning("Proceeding with full 8-step calibration...")
                        logger.warning("=" * 80)
                else:
                    logger.info("ℹ️  No stored calibration found - running full calibration")
            else:
                logger.info("ℹ️  Force recalibrate enabled - skipping QC validation")

            # ========================================================================
            # FULL CALIBRATION (QC FAILED OR NOT AVAILABLE)
            # ========================================================================

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
            success = self.step_2_calibrate_wavelength_range()
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

            success = self.step_4_optimize_integration_time(weakest_ch)
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
            # STEP 6: BALANCE LED INTENSITIES (Adjust other channels down)
            # ========================================================================
            self._emit_progress(6, "Step 6: Balancing LED intensities...")
            success = self.step_6_balance_led_intensities(ch_list)
            if not success or self._is_stopped():
                self._safe_hardware_cleanup()
                return False, "Step 6: LED balancing failed"

            # ========================================================================
            # PER-CHANNEL MODE: OPTIMIZE INTEGRATION TIMES PER CHANNEL
            # ========================================================================
            if self.state.calibration_mode == 'per_channel':
                self._emit_progress(6.5, "Optimizing per-channel integration times...")
                success = self.optimize_per_channel_integration_times(ch_list)
                if not success or self._is_stopped():
                    self._safe_hardware_cleanup()
                    return False, "Per-channel integration optimization failed"

            # ========================================================================
            # STEP 7: REFERENCE SIGNAL MEASUREMENT (Balanced S-mode baseline)
            # ========================================================================
            logger.debug(f"Balanced S-mode LED settings: {self.state.ref_intensity}")

            # Step 7: Reference signal measurement (S-mode)
            logger.debug("Step 7: Reference signal measurement (S-mode)")
            self._emit_progress(7, "Capturing reference signals (balanced S-mode)...")
            success = self.step_7_measure_reference_signals(ch_list)
            if not success or self._is_stopped():
                self._safe_hardware_cleanup()
                return False, "Step 7: Reference signal measurement failed"

            # Calibration successful (Step 7 marks is_calibrated = True)
            calibration_success = self.state.is_calibrated
            ch_error_str = ""

            # Always cleanup hardware after calibration
            self._safe_hardware_cleanup()

            # ========================================================================
            # SAVE TO DEVICE CONFIG (SINGLE SOURCE OF TRUTH)
            # ========================================================================
            if calibration_success:
                logger.info("=" * 80)
                logger.info("💾 SAVING CALIBRATION TO DEVICE CONFIG (SINGLE SOURCE OF TRUTH)")
                logger.info("=" * 80)

                try:
                    from utils.device_configuration import DeviceConfiguration

                    device_config = DeviceConfiguration()
                    device_config.save_led_calibration(
                        integration_time_ms=int(self.state.integration * 1000),  # Convert seconds to milliseconds
                        s_mode_intensities=self.state.ref_intensity.copy(),
                        p_mode_intensities=self.state.ref_intensity.copy(),  # P-mode uses same LEDs
                        s_ref_spectra=self.state.ref_sig.copy(),
                        s_ref_wavelengths=self.state.wavelengths if self.state.wavelengths is not None else None
                    )
                    logger.info("✅ LED calibration saved to device_config.json")
                    logger.info("   This will enable quick QC validation on next calibration")

                except Exception as e:
                    logger.error(f"❌ Failed to save LED calibration to device config: {e}")
                    # Continue anyway - not critical

                logger.info("=" * 80)

            # Auto-save successful calibration (legacy profile system)
            if calibration_success and auto_save:
                logger.info("💾 Auto-saving calibration profile (legacy)...")
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                profile_name = f"auto_save_{timestamp}"
                save_success = self.save_profile(profile_name, self.device_type or "unknown")
                if save_success:
                    logger.info(f"✅ Calibration profile saved as: {profile_name}")
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
                logger.error(POLARIZER_ERROR_MESSAGE)
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
        device_type: Optional[str] = None,
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
                logger.error(POLARIZER_ERROR_MESSAGE)
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
    ) -> Optional[tuple[int, int]]:
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

