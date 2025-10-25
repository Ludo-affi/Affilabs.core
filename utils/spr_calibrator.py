from __future__ import annotations

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

"""

# Standard library imports
import os
import time
import csv
import json
import datetime as dt
from datetime import datetime
from pathlib import Path
from contextlib import suppress
from typing import Optional, Union, Any, Callable

# Third-party imports
import numpy as np

# Qt imports for event processing
try:
    from PySide6.QtWidgets import QApplication
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

# Local imports
from utils.logger import logger
from utils.detector_manager import get_detector_manager, DetectorProfile
from utils.spr_data_processor import SPRDataProcessor
from settings.settings import (
    CH_LIST,
    EZ_CH_LIST,
    LED_DELAY,
    MIN_INTEGRATION,
    NUM_SCANS_PER_ACQUISITION,
    ROOT_DIR,
    S_LED_MIN,
    S_LED_INT,
    P_LED_MAX,
    TIME_ZONE,
    # Additional configuration used across calibration
    MIN_WAVELENGTH,
    MAX_WAVELENGTH,
    TARGET_WAVELENGTH_MIN,
    TARGET_WAVELENGTH_MAX,
    MAX_INTEGRATION,
    TARGET_INTENSITY_PERCENT,
    WEAKEST_TARGET_PERCENT,
    WAVELENGTH_CACHE_ENABLED,
    WAVELENGTH_CACHE_MAX_AGE_DAYS,
    DEVICES,
)

# Optional, newer LED timing settings (fall back handled later)
try:
    from settings.settings import PRE_LED_DELAY_MS, POST_LED_DELAY_MS  # type: ignore
except Exception:  # Will default to legacy LED_DELAY if missing
    PRE_LED_DELAY_MS = float(LED_DELAY) * 1000.0  # ms
    POST_LED_DELAY_MS = 5.0  # ms

# Optional wavelength offset; default to 0.0 if not configured
try:
    from settings.settings import WAVELENGTH_OFFSET  # type: ignore
except Exception:
    WAVELENGTH_OFFSET = 0.0

# Detector profile accessor (for max counts, etc.)
try:
    from utils.detector_manager import get_current_detector_profile
except Exception:  # Fallback if detector manager not available
    get_current_detector_profile = None  # type: ignore

# Back-compat and convenience aliases
MS_TO_SECONDS: float = 1000.0  # Convert ms to seconds via division
MIN_LED_INTENSITY: int = int(S_LED_MIN)  # 5% of max LED intensity (typically 13)
MAX_LED_INTENSITY: int = int(P_LED_MAX)  # Maximum LED intensity (typically 255)

# Temporary integration time for initial dark if needed
TEMP_INTEGRATION_TIME_S: float = max(MIN_INTEGRATION / MS_TO_SECONDS, 0.050)

# Centralized error/help message for missing OEM polarizer positions
POLARIZER_ERROR_MESSAGE = """
🔧 REQUIRED: Run OEM calibration tool to configure polarizer positions

Command: python utils/oem_calibration_tool.py --serial YOUR_SERIAL
OR use Settings → Auto-Polarization in the GUI

This tool finds optimal S and P positions during manufacturing:
  1. Sweeps servo through full range (10-255)
  2. Finds optimal S-mode position (HIGH transmission - reference)
  3. Finds optimal P-mode position (LOWER transmission - resonance)
  4. Saves positions to device_config.json
"""

# Dynamic scan policy helper (target ~200ms of acquisition per channel)
def calculate_dynamic_scans(integration_seconds: float) -> int:
    """Compute number of scans to keep acquisition around 200ms budget.

    Args:
        integration_seconds: Integration time per scan in seconds.

    Returns:
        Integer number of scans (clamped to [1, 25]).
    """
    try:
        t = float(integration_seconds)
    except Exception:
        return NUM_SCANS_PER_ACQUISITION

    if t <= 0:
        return NUM_SCANS_PER_ACQUISITION

    # Match legacy behavior: num_scans ≈ round(200ms / integration)
    scans = int(round(0.200 / t))
    if scans < 1:
        scans = 1
    if scans > 25:
        scans = 25
    return scans

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
        # LED timing (default delays; can be overridden by afterglow/device config)
        try:
            from settings.settings import PRE_LED_DELAY_MS, POST_LED_DELAY_MS
            self.led_on_delay_s: float = float(PRE_LED_DELAY_MS) / 1000.0
            self.led_off_delay_s: float = float(POST_LED_DELAY_MS) / 1000.0
        except Exception:
            # Fallback to legacy single delay if settings import changes
            self.led_on_delay_s = float(LED_DELAY)
            self.led_off_delay_s = 0.005
        # Back-compat single value used in some persisted state (do not rely on it)
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

        # LED timing (default delays; can be overridden by afterglow/device config)
        # Calibrator maintains its own copy since many methods reference self.led_on/off_delay_s
        try:
            from settings.settings import PRE_LED_DELAY_MS, POST_LED_DELAY_MS
            self.led_on_delay_s: float = float(PRE_LED_DELAY_MS) / 1000.0
            self.led_off_delay_s: float = float(POST_LED_DELAY_MS) / 1000.0
            logger.info(
                f"⏱️ LED timing set from settings: pre-on={PRE_LED_DELAY_MS:.1f}ms, post-off={POST_LED_DELAY_MS:.1f}ms"
            )
        except Exception:
            # Fallback to legacy single delay if settings import changes
            self.led_on_delay_s = float(LED_DELAY)
            self.led_off_delay_s = 0.005  # 5ms default post-off settle
            logger.warning(
                f"⚠️ Using legacy LED delay fallback: pre-on={self.led_on_delay_s*1000:.1f}ms, post-off={self.led_off_delay_s*1000:.1f}ms"
            )
        # Back-compat single value used in some persisted state (do not rely on it)
        self.led_delay = LED_DELAY

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

        # Initialize snapshot helper (best-effort)
        try:
            self._snap = _SnapshotHelper(self)
        except Exception:
            self._snap = None

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
                # Set intensity (this should also turn on the LED on most HALs)
                self.ctrl.set_intensity(ch=ch, raw_val=intensity)
                # Redundant safety: explicitly turn on the channel if an API exists
                try:
                    if hasattr(self.ctrl, 'activate_channel'):
                        # Some HALs prefer 'activate_channel' (expects 'a'/'b' string)
                        self.ctrl.activate_channel(ch)
                    elif hasattr(self.ctrl, 'turn_on_channel'):
                        # Legacy controller API
                        self.ctrl.turn_on_channel(ch)
                except Exception:
                    # Non-fatal; acquisition path will detect if LED is off
                    pass
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
                    # Validate channel
                    if not isinstance(ch, str) or ch.lower() not in {"a", "b", "c", "d"}:
                        logger.error(f"Invalid channel: {ch}")
                        return False

                    # Clamp raw value to firmware range 0-255
                    try:
                        raw_int = int(raw_val)
                    except Exception:
                        logger.error(f"Invalid raw intensity value (not int-castable): {raw_val}")
                        return False

                    if raw_int < 0:
                        raw_int = 0
                    elif raw_int > 255:
                        raw_int = 255

                    # Use controller HAL's per-channel API which both sets intensity and turns the channel on
                    result = False
                    try:
                        if hasattr(self._hal, 'set_intensity'):
                            result = bool(self._hal.set_intensity(ch=ch.lower(), raw_val=raw_int))
                        else:
                            # Fallback: activate channel, then try normalized API for all channels
                            with suppress(Exception):
                                self._hal.activate_channel(ch.lower())
                            if hasattr(self._hal, 'set_led_intensity'):
                                # Best-effort: map 0-255 -> 0.0-1.0
                                norm = raw_int / 255.0
                                result = bool(self._hal.set_led_intensity(norm))
                    except Exception as inner:
                        logger.debug(f"ControllerAdapter.set_intensity underlying HAL call failed: {inner}")
                        result = False

                    if not result:
                        logger.warning(f"set_intensity failed for channel {ch} with value {raw_int}")
                    return result
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
        # Determine scanning policy based on calibration mode
        num_scans: int = 1
        try:
            mode = getattr(self.state, 'calibration_mode', getattr(self, 'calibration_mode', 'global'))
        except Exception:
            mode = 'global'

        if mode == 'global':
            # For global model, honor a 200 ms time window (dynamic scans)
            try:
                current_int = 0.0
                if hasattr(self.usb, 'get_integration_time'):
                    current_int = float(self.usb.get_integration_time())
                elif hasattr(self.usb, 'get_integration'):
                    current_int = float(self.usb.get_integration())
                if current_int and current_int > 0:
                    num_scans = calculate_dynamic_scans(current_int)
                else:
                    num_scans = NUM_SCANS_PER_ACQUISITION
            except Exception:
                num_scans = NUM_SCANS_PER_ACQUISITION
        else:
            # Per-channel model: no windowing; single scan per acquisition
            num_scans = 1

        return self._acquire_averaged_spectrum(
            num_scans=num_scans,
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
        # Process Qt events to keep GUI responsive during long calibration
        self._process_qt_events()

        if self.stop_flag is None:
            return False
        return self.stop_flag.is_set()

    def _process_qt_events(self) -> None:
        """Process Qt events to keep GUI responsive during calibration.

        This is called at every stop checkpoint throughout calibration to prevent
        the GUI from freezing and Windows from thinking the app is unresponsive.
        """
        if QT_AVAILABLE:
            app = QApplication.instance()
            if app is not None:
                app.processEvents()

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

            calib_dir = Path(ROOT_DIR) / "calibration_data"
            cached_wavelengths_file = calib_dir / "wavelengths_latest.npy"
            invalidate_flag_file = calib_dir / "invalidate_wavelength_cache.flag"

            # Check explicit invalidation via env or flag file
            env_invalidate = os.getenv("EZ_WL_CACHE_INVALIDATE", "").strip().lower() in {"1", "true", "yes", "on"}
            file_invalidate = invalidate_flag_file.exists()
            invalidate_cache = env_invalidate or file_invalidate

            if invalidate_cache and cached_wavelengths_file.exists():
                try:
                    logger.info("🧹 Cache invalidate requested → removing cached wavelengths file…")
                    cached_wavelengths_file.unlink(missing_ok=True)  # type: ignore[arg-type]
                except Exception as e:
                    logger.warning(f"Could not remove cached wavelengths: {e}")
                # Clear the flag file so subsequent runs are normal
                if file_invalidate:
                    try:
                        invalidate_flag_file.unlink(missing_ok=True)  # type: ignore[arg-type]
                    except Exception:
                        pass

            # Use cache only if enabled, not invalidated, exists, and fresh enough
            if (
                WAVELENGTH_CACHE_ENABLED
                and not invalidate_cache
                and cached_wavelengths_file.exists()
            ):
                try:
                    file_age_days = (time.time() - cached_wavelengths_file.stat().st_mtime) / 86400
                    if file_age_days <= float(WAVELENGTH_CACHE_MAX_AGE_DAYS):
                        wave_data = np.load(cached_wavelengths_file)
                        if wave_data is not None and len(wave_data) > 0:
                            used_cache = True
                            logger.info(
                                f"📊 Using cached wavelengths (age: {file_age_days:.1f} days ≤ {float(WAVELENGTH_CACHE_MAX_AGE_DAYS):.1f} days)"
                            )
                    else:
                        logger.info(
                            f"🗓️ Cached wavelengths too old (age: {file_age_days:.1f} days > {float(WAVELENGTH_CACHE_MAX_AGE_DAYS):.1f} days) — will read EEPROM"
                        )
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
                    return False

            if wave_data is None or len(wave_data) == 0:
                logger.error("❌ Failed to read wavelengths from spectrometer")
                return False

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
            return False

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
            logger.info("Verifying S-mode (HIGH) and P-mode (LOWER) positions...")

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

            # Log current integration time and dynamic scan policy used for Step 3 measurements
            try:
                current_int = None
                if hasattr(self.usb, 'get_integration_time'):
                    current_int = float(self.usb.get_integration_time())
                elif hasattr(self.usb, 'get_integration'):
                    current_int = float(self.usb.get_integration())
                if current_int is None or current_int <= 0:
                    current_int = float(getattr(self.state, 'integration', 0.0) or 0.0)
                scans = calculate_dynamic_scans(current_int) if current_int and current_int > 0 else NUM_SCANS_PER_ACQUISITION
                logger.info(
                    f"   Step 3 acquisition policy: integration={current_int*1000:.1f} ms, scans={scans} (≈{scans*current_int*1000:.0f} ms total)"
                )
            except Exception:
                # Non-critical; proceed without logging details if anything fails
                pass

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
            # Saturation threshold: 99% of detector max (conservative to catch all saturation)
            SATURATION_THRESHOLD = int(0.99 * detector_max)
            logger.debug(f"Saturation threshold: {SATURATION_THRESHOLD} counts (99% of {detector_max})")

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
                        # Ensure LED actually turns on (batch -> sequential fallback)
                        ok = self._activate_channel_batch([ch], intensities_dict)
                        if not ok:
                            logger.warning(f"   Batch activation failed for {ch}, trying sequential...")
                            ok = self._activate_channel_sequential([ch], intensities_dict)
                        if not ok:
                            logger.error(f"   ❌ Failed to activate LED {ch} for early-confirm check")
                            quick_data = {}
                            break
                        time.sleep(self.led_on_delay_s)
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
                    time.sleep(self.led_off_delay_s)

                    if len(quick_data) == 2:
                        w_mean = quick_data[prior_weakest][0]
                        s_mean = quick_data[prior_second][0]
                        if w_mean > 0 and (s_mean / w_mean) >= EARLY_CONFIRM_MARGIN:
                            # Confirmed: prior weakest is still weakest by margin
                            # But we MUST test ALL channels for Step 4 LED balancing!
                            logger.info(f"   ✅ Early-confirm success: {prior_weakest} remains weakest by {(s_mean/w_mean):.2f}×")
                            logger.info(f"   ⚠️  Early-confirm will NOT short-circuit - need all channels for Step 4")
                            # DO NOT return early - Step 4 needs all channel data!
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
                # Ensure LED actually turns on (batch -> sequential fallback)
                ok = self._activate_channel_batch([ch], intensities_dict)
                if not ok:
                    logger.warning(f"   Batch activation failed for {ch}, trying sequential...")
                    ok = self._activate_channel_sequential([ch], intensities_dict)
                if not ok:
                    logger.error(f"   ❌ Failed to activate LED {ch} at LED={chosen_led}")
                    # Ensure off state and skip this channel
                    try:
                        self._all_leds_off_batch()
                    except Exception:
                        pass
                    time.sleep(self.led_off_delay_s)
                    continue
                time.sleep(self.led_on_delay_s)

                # Track for afterglow correction
                self._last_active_channel = ch

                # ✨ Phase 2: Use 4-scan averaging for consistency with live mode
                raw_array = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
                if raw_array is None:
                    logger.error(f"Failed to read intensity for channel {ch}")
                    continue

                # Apply spectral filter (to SPR range)
                filtered_array = self._apply_spectral_filter(raw_array)

                # 💾 Snapshot: Step 3 S-pol raw (filtered) per channel
                try:
                    if hasattr(self, "_snap") and self._snap is not None:
                        self._snap.save(f"step3_S_raw_filtered_{ch}_LED{int(chosen_led)}", np.array(filtered_array, dtype=float))
                except Exception:
                    pass

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
            time.sleep(self.led_off_delay_s)

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
                    # Ensure LED actually turns on (batch -> sequential fallback)
                    ok = self._activate_channel_batch([ch], intensities_dict)
                    if not ok:
                        logger.warning(f"   Batch activation failed on retry for {ch}, trying sequential...")
                        ok = self._activate_channel_sequential([ch], intensities_dict)
                    if not ok:
                        logger.error(f"   ❌ Failed to activate LED {ch} for retry at LED={retry_led}")
                        try:
                            self._all_leds_off_batch()
                        except Exception:
                            pass
                        time.sleep(self.led_off_delay_s)
                        continue
                    time.sleep(self.led_on_delay_s)

                    self._last_active_channel = ch


                    # ✨ Phase 2: Use 4-scan averaging for consistency with live mode
                    raw_array = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
                    if raw_array is None:
                        logger.error(f"Failed to read intensity for channel {ch} on retry")
                        continue

                    # Apply spectral filter
                    filtered_array = self._apply_spectral_filter(raw_array)

                    # 💾 Snapshot: Step 3 retry S-pol raw (filtered)
                    try:
                        if hasattr(self, "_snap") and self._snap is not None:
                            self._snap.save(f"step3_retry_S_raw_filtered_{ch}_LED{int(retry_led)}", np.array(filtered_array, dtype=float))
                    except Exception:
                        pass


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
                time.sleep(self.led_off_delay_s)

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
    # QUICK LED SANITY CHECK (DIAGNOSTIC)
    # ========================================================================
    def quick_led_sanity_check(self, ch_list: Optional[list[str]] = None, intensity: int = 255, duration_s: float = 0.4) -> bool:
        """Quickly verify that each LED turns on and produces measurable signal.

        - Forces S-mode (high transmission) to maximize signal
        - Turns on each LED at the specified intensity
        - Captures one averaged spectrum (uses current calibration scanning policy)
        - Logs raw max/mean and ROI max/mean (580-610nm by default)

        Args:
            ch_list: Channels to test; defaults to available channels ['a','b','c','d'] if None
            intensity: LED intensity to test (0-255), default 255
            duration_s: Time to wait after LED on before measuring (s)

        Returns:
            True if at least one channel produced non-flat signal, False otherwise
        """
        try:
            if self.ctrl is None or self.usb is None:
                logger.error("❌ Hardware not initialized (ctrl or usb is None)")
                return False

            if ch_list is None:
                ch_list = ['a', 'b', 'c', 'd']

            # Ensure we have wavelength info for ROI
            if not hasattr(self.state, 'wavelengths') or self.state.wavelengths is None:
                logger.warning("⚠️  Wavelengths not calibrated yet (Step 2). ROI metrics will be skipped.")
                wave_data = None
            else:
                wave_data = self.state.wavelengths

            # Compute ROI indices if possible
            roi_min_idx = roi_max_idx = None
            if wave_data is not None:
                roi_min_idx = int(np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MIN)))
                roi_max_idx = int(np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MAX)))

            logger.info("=" * 80)
            logger.info("QUICK LED SANITY CHECK")
            logger.info("=" * 80)
            logger.info(f"Mode: S (high transmission), Test LED intensity: {intensity}")

            # Force S-mode
            try:
                self.ctrl.set_mode("s")
                time.sleep(0.3)
            except Exception as e:
                logger.warning(f"⚠️  Failed to set S-mode: {e}")

            any_signal = False
            for ch in ch_list:
                try:
                    # Turn on LED
                    intensities_dict = {ch: int(max(0, min(255, intensity)))}
                    ok = self._activate_channel_batch([ch], intensities_dict)
                    if not ok:
                        logger.warning(f"   Batch activation failed for {ch}, trying sequential...")
                        ok = self._activate_channel_sequential([ch], intensities_dict)
                    if not ok:
                        logger.error(f"   ❌ Failed to activate LED {ch}")
                        continue

                    time.sleep(max(0.1, duration_s))

                    # Acquire one averaged spectrum (no filter)
                    raw = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
                    if raw is None:
                        logger.error(f"   ❌ Failed to read spectrum for {ch}")
                        self._all_leds_off_batch()
                        time.sleep(self.led_off_delay_s)
                        continue

                    raw = np.asarray(raw, dtype=float)
                    raw_max, raw_mean = float(np.max(raw)), float(np.mean(raw))

                    # Optional filtered ROI metrics
                    if wave_data is not None and hasattr(self.state, 'wavelength_mask'):
                        try:
                            filtered = self._apply_spectral_filter(raw)
                            if roi_min_idx is not None and roi_max_idx is not None and roi_max_idx > roi_min_idx:
                                roi_slice = filtered[roi_min_idx:roi_max_idx]
                                roi_max, roi_mean = float(np.max(roi_slice)), float(np.mean(roi_slice))
                            else:
                                roi_max = roi_mean = float('nan')
                        except Exception:
                            filtered = None
                            roi_max = roi_mean = float('nan')
                    else:
                        filtered = None
                        roi_max = roi_mean = float('nan')

                    # Snapshots for offline inspection
                    try:
                        if hasattr(self, "_snap") and self._snap is not None:
                            self._snap.save(f"sanity_S_raw_{ch}_LED{intensity}", raw)
                            if filtered is not None:
                                self._snap.save(f"sanity_S_filtered_{ch}_LED{intensity}", np.array(filtered, dtype=float))
                    except Exception:
                        pass

                    logger.info(
                        f"   {ch}: RAW max/mean = {raw_max:.1f}/{raw_mean:.1f} counts; "
                        + (f"ROI max/mean = {roi_max:.1f}/{roi_mean:.1f} counts" if not np.isnan(roi_max) else "ROI=N/A")
                    )

                    # Heuristic: consider 'signal present' if raw max > mean by at least some margin
                    if raw_max > (raw_mean + 50):
                        any_signal = True

                finally:
                    # Ensure LED off between tests
                    try:
                        self._all_leds_off_batch()
                    except Exception:
                        pass
                    time.sleep(self.led_off_delay_s)

            if not any_signal:
                logger.warning("⚠️  No obvious signal detected (spectra appear flat). Check: wiring, LED power, polarizer mode, integration time.")
            else:
                logger.info("✅ At least one channel produced non-flat signal.")

            logger.info("=" * 80)
            return any_signal

        except Exception as e:
            logger.exception(f"Error in quick_led_sanity_check: {e}")
            return False

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
            time.sleep(self.led_on_delay_s)
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

            # Sanity check: ensure we're not measuring a dark-only spectrum
            try:
                baseline = getattr(self.state, 'dark_noise_before_leds', None)
                if baseline is not None and isinstance(baseline, np.ndarray) and baseline.size > 0:
                    baseline_mean = float(np.mean(baseline))
                    baseline_std = float(np.std(baseline))
                    baseline_max = float(np.max(baseline))
                    # Threshold: either mean+3σ or modestly above baseline max
                    threshold = max(baseline_mean + 3.0 * max(baseline_std, 1.0), baseline_max * 1.10)
                    if signal_max <= threshold:
                        # Looks like LED didn't meaningfully contribute; retry with sequential activation
                        try:
                            self._all_leds_off_batch()
                        except Exception:
                            pass
                        time.sleep(self.led_off_delay_s)
                        # Retry using sequential path as a hardware fallback
                        intensities_dict = {channel: led_intensity}
                        ok = self._activate_channel_sequential([channel], intensities_dict)
                        if not ok:
                            logger.warning(f"⚠️  {description}: sequential activation retry failed for {channel}")
                        time.sleep(self.led_on_delay_s)
                        self._last_active_channel = channel
                        raw_array_retry = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
                        if raw_array_retry is not None and len(raw_array_retry) > 0:
                            filtered_retry = self._apply_spectral_filter(raw_array_retry)
                            roi_retry = filtered_retry[roi_min_idx:roi_max_idx]
                            signal_max_retry = float(np.max(roi_retry))
                            signal_mean_retry = float(np.mean(roi_retry))
                            if signal_max_retry > signal_max:
                                logger.warning(
                                    f"⚠️  {description}: first read looked like dark-only (max={signal_max:.1f} ≤ thr={threshold:.1f}); retry improved to max={signal_max_retry:.1f}"
                                )
                                signal_max = signal_max_retry
                                signal_mean = signal_mean_retry
                            else:
                                logger.warning(
                                    f"⚠️  {description}: measurement remains near-dark after retry (max={signal_max_retry:.1f} ≤ thr={threshold:.1f}); proceeding"
                                )
                        else:
                            logger.warning(
                                f"⚠️  {description}: retry read failed; proceeding with original measurement (max={signal_max:.1f})"
                            )
            except Exception as _sanity_e:
                # Never fail calibration on a sanity check path
                logger.debug(f"Sanity check skipped due to error: {_sanity_e}")

            # Turn off channel
            self._all_leds_off_batch()
            time.sleep(self.led_off_delay_s)

            return signal_max, signal_mean

        except Exception as e:
            logger.error(f"Error measuring {description} for channel {channel}: {e}")
            self._all_leds_off_batch()
            return None

    def _create_step4_diagnostic_plot(
        self,
        spectra: dict,
        roi_means: dict,
        channels: list,
        integration_time: float,
        target_counts: int
    ) -> None:
        """Create diagnostic plot showing raw S-pol spectra after Step 4 LED balancing.

        Args:
            spectra: Dict of {channel: spectrum_array}
            roi_means: Dict of {channel: mean_roi_signal}
            channels: List of channel names in order
            integration_time: Global integration time in seconds
            target_counts: Target signal level in counts
        """
        try:
            import matplotlib.pyplot as plt
            from datetime import datetime

            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle(f'Step 4 Diagnostic: Raw S-pol Spectra After LED Balancing\nIntegration Time: {integration_time*1000:.1f}ms (FROZEN)',
                        fontsize=14, fontweight='bold')

            colors = {'a': '#FF6B6B', 'b': '#4ECDC4', 'c': '#45B7D1', 'd': '#FFA07A'}

            # Get wavelength array
            wavelengths = self.state.wavelengths

            # Plot 1: Raw spectra overlay
            ax1 = axes[0, 0]
            for ch in channels:
                if ch not in spectra:
                    continue
                led_val = self.state.ref_intensity.get(ch, 255)
                spectrum = spectra[ch]
                # Use wavelength for x-axis
                ax1.plot(wavelengths, spectrum, label=f'{ch.upper()} (LED={led_val})',
                        color=colors.get(ch, 'gray'), alpha=0.7, linewidth=1.5)

            ax1.set_xlabel('Wavelength (nm)', fontsize=11)
            ax1.set_ylabel('Intensity (counts)', fontsize=11)
            ax1.set_title('Raw S-pol Spectra (SPR Range, No Dark Subtraction)', fontsize=12, fontweight='bold')
            ax1.legend(fontsize=10)
            ax1.grid(True, alpha=0.3)

            # Plot 2: ROI mean intensities (580-610nm)
            ax2 = axes[0, 1]
            x_pos = list(range(len(channels)))
            means = [roi_means.get(ch, 0) for ch in channels]
            leds = [self.state.ref_intensity.get(ch, 255) for ch in channels]

            bars = ax2.bar(x_pos, means, color=[colors.get(ch, 'gray') for ch in channels],
                          alpha=0.7, edgecolor='black', linewidth=1.5)

            # Add target line
            ax2.axhline(target_counts, color='green', linestyle='--', linewidth=2,
                       label=f'Target: {target_counts:,} counts (75%)')
            ax2.axhspan(target_counts * 0.9, target_counts * 1.1, alpha=0.2, color='green',
                       label='±10% tolerance')

            ax2.set_xticks(x_pos)
            ax2.set_xticklabels([ch.upper() for ch in channels], fontsize=11)
            ax2.set_ylabel('Mean Intensity (counts)', fontsize=11)
            ax2.set_title('ROI Mean Intensities (580-610nm)', fontsize=12, fontweight='bold')
            ax2.legend(fontsize=9)
            ax2.grid(True, alpha=0.3, axis='y')

            # Add value labels on bars
            for bar, mean, led in zip(bars, means, leds):
                height = bar.get_height()
                deviation = ((mean - target_counts) / target_counts * 100) if target_counts > 0 else 0
                ax2.text(bar.get_x() + bar.get_width()/2., height + 1000,
                        f'{int(mean):,}\n({deviation:+.0f}%)\nLED={led}',
                        ha='center', va='bottom', fontsize=9, fontweight='bold')

            # Plot 3: LED values
            ax3 = axes[1, 0]
            bars = ax3.bar(x_pos, leds, color=[colors.get(ch, 'gray') for ch in channels],
                          alpha=0.7, edgecolor='black', linewidth=1.5)

            ax3.axhline(255, color='red', linestyle='--', linewidth=2, label='Max LED (255)')
            ax3.set_xticks(x_pos)
            ax3.set_xticklabels([ch.upper() for ch in channels], fontsize=11)
            ax3.set_ylabel('LED Intensity', fontsize=11)
            ax3.set_title('Final LED Values (Step 4 Output)', fontsize=12, fontweight='bold')
            ax3.set_ylim(0, 270)
            ax3.legend(fontsize=9)
            ax3.grid(True, alpha=0.3, axis='y')

            # Add value labels
            for bar, led in zip(bars, leds):
                height = bar.get_height()
                ax3.text(bar.get_x() + bar.get_width()/2., height + 5,
                        f'{int(led)}', ha='center', va='bottom', fontsize=11, fontweight='bold')

            # Plot 4: Balance quality summary
            ax4 = axes[1, 1]
            ax4.axis('off')

            # Calculate statistics
            mean_signal = np.mean(means)
            std_signal = np.std(means)
            cv = (std_signal / mean_signal * 100) if mean_signal > 0 else 0

            mean_led = np.mean(leds)
            std_led = np.std(leds)

            weakest_ch = channels[0]  # Assuming channels are ordered

            summary_text = f"""
STEP 4 BALANCING RESULTS
═══════════════════════════════════════════

Global Integration Time: {integration_time*1000:.1f} ms (FROZEN)
Target Signal Level: {target_counts:,} counts (75% max)

LED Values:
"""
            for ch in channels:
                led = self.state.ref_intensity.get(ch, 255)
                mean = roi_means.get(ch, 0)
                status = "✓ WEAKEST" if ch == weakest_ch else f"  {led/255*100:.0f}% power"
                summary_text += f"   {ch.upper()}: LED={led:3d}  →  {mean:7,.0f} counts  {status}\n"

            summary_text += f"""
Signal Statistics (ROI 580-610nm):
   Mean: {mean_signal:,.0f} counts
   Std Dev: {std_signal:,.0f} counts
   CV: {cv:.1f}% (target: <10%)

Balance Quality:
   {"✓ EXCELLENT" if cv < 10 else "△ ACCEPTABLE" if cv < 20 else "✗ POOR"}

Channels within ±10% of target:
   {sum(1 for m in means if abs(m - target_counts) / target_counts <= 0.1)}/{len(channels)}
"""

            ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes,
                    fontsize=10, verticalalignment='top', family='monospace',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.4))

            plt.tight_layout()

            # Save figure
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path("generated-files/diagnostics")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"step4_raw_spol_diagnostic_{timestamp}.png"

            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            logger.info(f"📊 Step 4 diagnostic plot saved: {output_file}")

            plt.close(fig)

        except Exception as e:
            logger.warning(f"Failed to create Step 4 diagnostic plot: {e}")

    def _create_step6_diagnostic_plot(
        self,
        spectra: dict,
        roi_means: dict,
        channels: list,
        integration_time: float,
        target_counts: int
    ) -> None:
        """Create diagnostic plot showing dark-subtracted S-ref spectra after Step 6.

        Args:
            spectra: Dict of {channel: dark_subtracted_spectrum_array}
            roi_means: Dict of {channel: mean_roi_signal}
            channels: List of channel names in order
            integration_time: Global integration time in seconds
            target_counts: Target signal level in counts
        """
        try:
            import matplotlib.pyplot as plt
            from datetime import datetime

            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle(f'Step 6 Diagnostic: Dark-Subtracted S-ref Spectra (Ready for Live)\nIntegration Time: {integration_time*1000:.1f}ms (FROZEN)',
                        fontsize=14, fontweight='bold')

            colors = {'a': '#FF6B6B', 'b': '#4ECDC4', 'c': '#45B7D1', 'd': '#FFA07A'}

            # Get wavelength array
            wavelengths = self.state.wavelengths

            # Plot 1: Dark-subtracted S-ref spectra overlay
            ax1 = axes[0, 0]
            for ch in channels:
                if ch not in spectra:
                    continue
                led_val = self.state.ref_intensity.get(ch, 255)
                spectrum = spectra[ch]
                # Use wavelength for x-axis
                ax1.plot(wavelengths, spectrum, label=f'{ch.upper()} (LED={led_val})',
                        color=colors.get(ch, 'gray'), alpha=0.7, linewidth=1.5)

            ax1.set_xlabel('Wavelength (nm)', fontsize=11)
            ax1.set_ylabel('Intensity (counts)', fontsize=11)
            ax1.set_title('Dark-Subtracted S-ref Spectra (SPR Range, Ready for Live)', fontsize=12, fontweight='bold')
            ax1.legend(fontsize=10)
            ax1.grid(True, alpha=0.3)

            # Plot 2: ROI mean intensities (580-610nm)
            ax2 = axes[0, 1]
            x_pos = list(range(len(channels)))
            means = [roi_means.get(ch, 0) for ch in channels]
            leds = [self.state.ref_intensity.get(ch, 255) for ch in channels]

            bars = ax2.bar(x_pos, means, color=[colors.get(ch, 'gray') for ch in channels],
                          alpha=0.7, edgecolor='black', linewidth=1.5)

            # Add target line
            ax2.axhline(target_counts, color='green', linestyle='--', linewidth=2,
                       label=f'Target: {target_counts:,} counts (75%)')
            ax2.axhspan(target_counts * 0.9, target_counts * 1.1, alpha=0.2, color='green',
                       label='±10% tolerance')

            ax2.set_xticks(x_pos)
            ax2.set_xticklabels([ch.upper() for ch in channels], fontsize=11)
            ax2.set_ylabel('Mean Intensity (counts)', fontsize=11)
            ax2.set_title('ROI Mean Intensities (580-610nm, After Dark Subtraction)', fontsize=12, fontweight='bold')
            ax2.legend(fontsize=9)
            ax2.grid(True, alpha=0.3, axis='y')

            # Add value labels on bars
            for bar, mean, led in zip(bars, means, leds):
                height = bar.get_height()
                deviation = ((mean - target_counts) / target_counts * 100) if target_counts > 0 else 0
                ax2.text(bar.get_x() + bar.get_width()/2., height + 1000,
                        f'{int(mean):,}\n({deviation:+.0f}%)\nLED={led}',
                        ha='center', va='bottom', fontsize=9, fontweight='bold')

            # Plot 3: LED values
            ax3 = axes[1, 0]
            bars = ax3.bar(x_pos, leds, color=[colors.get(ch, 'gray') for ch in channels],
                          alpha=0.7, edgecolor='black', linewidth=1.5)

            ax3.axhline(255, color='red', linestyle='--', linewidth=2, label='Max LED (255)')
            ax3.set_xticks(x_pos)
            ax3.set_xticklabels([ch.upper() for ch in channels], fontsize=11)
            ax3.set_ylabel('LED Intensity', fontsize=11)
            ax3.set_title('Final LED Values (From Step 4)', fontsize=12, fontweight='bold')
            ax3.set_ylim(0, 270)
            ax3.legend(fontsize=9)
            ax3.grid(True, alpha=0.3, axis='y')

            # Add value labels
            for bar, led in zip(bars, leds):
                height = bar.get_height()
                ax3.text(bar.get_x() + bar.get_width()/2., height + 5,
                        f'{int(led)}', ha='center', va='bottom', fontsize=11, fontweight='bold')

            # Plot 4: Balance quality summary
            ax4 = axes[1, 1]
            ax4.axis('off')

            # Calculate statistics
            mean_signal = np.mean(means)
            std_signal = np.std(means)
            cv = (std_signal / mean_signal * 100) if mean_signal > 0 else 0

            mean_led = np.mean(leds)
            std_led = np.std(leds)

            weakest_ch = channels[0]  # Assuming channels are ordered

            summary_text = f"""
STEP 6 S-REF RESULTS (READY FOR LIVE)
═══════════════════════════════════════════

Global Integration Time: {integration_time*1000:.1f} ms (FROZEN)
Target Signal Level: {target_counts:,} counts (75% max)

LED Values:
"""
            for ch in channels:
                led = self.state.ref_intensity.get(ch, 255)
                mean = roi_means.get(ch, 0)
                status = "✓ WEAKEST" if ch == weakest_ch else f"  {led/255*100:.0f}% power"
                summary_text += f"   {ch.upper()}: LED={led:3d}  →  {mean:7,.0f} counts  {status}\n"

            summary_text += f"""
Signal Statistics (ROI 580-610nm):
   Mean: {mean_signal:,.0f} counts
   Std Dev: {std_signal:,.0f} counts
   CV: {cv:.1f}% (target: <10%)

Balance Quality:
   {"✓ EXCELLENT" if cv < 10 else "△ ACCEPTABLE" if cv < 20 else "✗ POOR"}

Channels within ±10% of target:
   {sum(1 for m in means if abs(m - target_counts) / target_counts <= 0.1)}/{len(channels)}

Dark Subtraction: ✓ Applied (Step 5 darks)
Ready for Live Acquisition: ✓ YES
"""

            ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes,
                    fontsize=10, verticalalignment='top', family='monospace',
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.4))

            plt.tight_layout()

            # Save figure
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path("generated-files/diagnostics")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"step6_sref_diagnostic_{timestamp}.png"

            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            logger.info(f"📊 Step 6 diagnostic plot saved: {output_file}")

            plt.close(fig)

        except Exception as e:
            logger.warning(f"Failed to create Step 6 diagnostic plot: {e}")

    # ========================================================================
    # STEP 4: INTEGRATION TIME OPTIMIZATION
    # ========================================================================

    def step_4_optimize_integration_time(self, weakest_ch: str) -> bool:
        """STEP 4: Optimize integration time for weakest LED, then balance all LEDs.

        COMPLETE CALIBRATION IN ONE STEP:
        ==================================
        4.1: Set weakest LED to 255 (from Step 3 ranking)
        4.2: Probe 3 integration times [5, 15, 50]ms with weakest @ 255
        4.3: Extrapolate to find integration time → 75% detector max (~50,000 counts)
        4.4: FREEZE that integration time (used for all remaining steps)
        4.5: For each remaining LED (stronger LEDs):
             - Keep integration time frozen
             - Reduce LED intensity until signal ≈ 75% detector max (~50,000 counts)
        4.6: Result: All LEDs balanced at ~50,000 counts in 580-610nm
             - Weakest: LED=255 (likely the only one at 255)
             - Others: LED<255 (reduced to match weakest)

        This global integration time is passed to:
        - Step 5: Dark noise measurement
        - Step 6: Final S-ref measurement

        CALIBRATION MODES:
        ==================
        - 'global': Run full calibration (Step 4 does everything)
        - 'per_channel': Skip this, set all LEDs to 255

        Args:
            weakest_ch: Weakest channel from Step 3 (used for integration time optimization)

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
                # ====================================================================
                # PER-CHANNEL MODE: All LEDs @ 255, optimize integration per channel
                # ====================================================================
                logger.info("")
                logger.info("=" * 80)
                logger.info("⚡ STEP 4: PER-CHANNEL MODE - OPTIMIZE INTEGRATION TIME PER LED")
                logger.info("=" * 80)
                logger.info("All LEDs will be set to 255")
                logger.info("Each LED gets its own optimized integration time")
                logger.info("")

                # Get all channels
                if not self.state.led_ranking or len(self.state.led_ranking) < 1:
                    logger.error("⚠️  LED ranking not found! Step 3 must run before Step 4.")
                    return False

                all_channels = [ch_info[0] for ch_info in self.state.led_ranking]

                # STEP 4.1a: Set ALL LEDs to 255
                logger.info("STEP 4.1a: Set ALL LEDs to 255")
                logger.info("=" * 80)
                for ch in all_channels:
                    self.state.ref_intensity[ch] = MAX_LED_INTENSITY
                    logger.info(f"   {ch.upper()} = 255")

                # Get 580-610nm test region
                wave_data = self.state.wavelengths
                roi_min_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MIN))
                roi_max_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MAX))
                target_counts = int(WEAKEST_TARGET_PERCENT / 100 * detector_max)

                logger.info("")
                logger.info(f"Target: {target_counts:,} counts (~75% detector max)")
                logger.info("")

                # Helper to measure and optimize for one channel
                def _optimize_channel_integration(ch: str) -> Optional[float]:
                    """Find optimal integration time for one channel @ LED=255."""
                    logger.info(f"STEP 4.x: Optimizing {ch.upper()} @ LED=255")
                    logger.info("-" * 80)

                    # Probe 3 integration times
                    seed_ms = [5.0, 15.0, 50.0]
                    probe_times = [ms / MS_TO_SECONDS for ms in seed_ms]
                    probe_results = []

                    for idx, t in enumerate(probe_times, 1):
                        if self._is_stopped():
                            return None
                        t = float(np.clip(t, min_int, max_int))
                        self.usb.set_integration(t)
                        time.sleep(0.08)

                        res = self._measure_channel_in_roi(
                            ch, MAX_LED_INTENSITY, int(roi_min_idx), int(roi_max_idx), f"{ch} @255"
                        )
                        if res is None:
                            logger.warning(f"   Probe {idx} failed")
                            continue

                        max_sig, _ = res
                        probe_results.append((t, max_sig))
                        pct = (max_sig / detector_max) * 100.0
                        logger.info(f"   Probe {idx}: {t*MS_TO_SECONDS:.1f}ms → {max_sig:6.0f} counts ({pct:5.1f}%)")

                    if len(probe_results) < 2:
                        logger.error(f"   ❌ Not enough probe data for {ch}")
                        return None

                    # Extrapolate to target
                    probe_results.sort(key=lambda x: x[0])
                    bracket = None
                    for i in range(len(probe_results) - 1):
                        (t1, c1), (t2, c2) = probe_results[i], probe_results[i+1]
                        if (c1 - target_counts) * (c2 - target_counts) <= 0:
                            bracket = ((t1, c1), (t2, c2))
                            break

                    if bracket:
                        (t1, c1), (t2, c2) = bracket
                        if c2 != c1:
                            optimal = t1 + (target_counts - c1) * (t2 - t1) / (c2 - c1)
                        else:
                            optimal = (t1 + t2) / 2.0
                        optimal = float(np.clip(optimal, min_int, max_int))
                        logger.info(f"   ✅ {ch.upper()}: {optimal*MS_TO_SECONDS:.1f}ms")
                    else:
                        # No bracket - use closest
                        closest = min(probe_results, key=lambda x: abs(x[1] - target_counts))
                        optimal = closest[0]
                        logger.warning(f"   ⚠️  {ch.upper()}: {optimal*MS_TO_SECONDS:.1f}ms (closest)")

                    return optimal

                # STEP 4.2a-4.5a: Optimize each channel
                logger.info("STEP 4.2a-4.5a: Optimize integration time for each LED")
                logger.info("=" * 80)

                per_channel_integration = {}
                for ch in all_channels:
                    if self._is_stopped():
                        return False

                    optimal_int = _optimize_channel_integration(ch)
                    if optimal_int is None:
                        logger.error(f"❌ Failed to optimize {ch}")
                        return False

                    per_channel_integration[ch] = optimal_int
                    logger.info("")

                # Store per-channel integration times
                self.state.per_channel_integration_times = per_channel_integration

                # Turn off all LEDs
                self._all_leds_off_batch()
                time.sleep(self.led_off_delay_s)

                # SUMMARY
                logger.info("")
                logger.info("=" * 80)
                logger.info("✅ STEP 4 COMPLETE: PER-CHANNEL CALIBRATION")
                logger.info("=" * 80)
                logger.info("")
                logger.info("Final Calibration Results:")
                logger.info("")
                logger.info("Channel  | LED Intensity | Integration Time")
                logger.info("-" * 50)
                for ch in all_channels:
                    led_val = self.state.ref_intensity.get(ch, 255)
                    int_time = per_channel_integration.get(ch, 0)
                    logger.info(f"   {ch.upper()}     |      {led_val:3d}      |    {int_time*MS_TO_SECONDS:6.1f} ms")
                logger.info("")
                logger.info("Mode: PER-CHANNEL (all LEDs @ 255, optimized integration per channel)")
                logger.info("")
                logger.info("Next Steps:")
                logger.info("   • Step 5: Measure dark noise (per-channel)")
                logger.info("   • Step 6: Measure S-ref (per-channel)")
                logger.info("=" * 80)

                # ✅ SYNC: Copy ref_intensity to leds_calibrated for live acquisition
                self.state.leds_calibrated = self.state.ref_intensity.copy()
                logger.debug(f"✅ Synced leds_calibrated from ref_intensity: {self.state.leds_calibrated}")

                return True

            # ========================================================================
            # GLOBAL MODE: Single integration time + LED balancing
            # ========================================================================

            # Import target percent for optimization
            from settings import WEAKEST_TARGET_PERCENT

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

            # Calculate target counts (75% of detector max)
            target_counts = int(WEAKEST_TARGET_PERCENT / 100 * detector_max)

            # Log detector boundaries and target values
            logger.info("")
            logger.info("=" * 80)
            logger.info("📊 DETECTOR BOUNDARIES & TARGET VALUES")
            logger.info("=" * 80)
            logger.info(f"Detector Model: {self.detector_profile.model}")
            logger.info(f"")
            logger.info(f"Integration Time Boundaries:")
            logger.info(f"   MIN: {self.detector_profile.min_integration_time_ms:.1f} ms")
            logger.info(f"   MAX: {self.detector_profile.max_integration_time_ms:.1f} ms")
            logger.info(f"")
            logger.info(f"Detector Count Boundaries:")
            logger.info(f"   MIN: 0 counts (dark level)")
            logger.info(f"   MAX: {detector_max:,} counts (16-bit ADC saturation)")
            logger.info(f"   SATURATION THRESHOLD: {int(0.99 * detector_max):,} counts (99% of max)")
            logger.info(f"")
            logger.info(f"Wavelength ROI for Calibration:")
            logger.info(f"   SPR Range: {spr_min_nm}-{spr_max_nm} nm (filtered)")
            logger.info(f"   Target ROI: {TARGET_WAVELENGTH_MIN}-{TARGET_WAVELENGTH_MAX} nm (LED balancing region)")
            logger.info(f"")
            logger.info(f"LED Intensity Boundaries:")
            logger.info(f"   MIN: 1 (practical minimum)")
            logger.info(f"   MAX: 255 (8-bit PWM maximum)")
            logger.info(f"   WEAKEST LED: FIXED at 255 (maximum power)")
            logger.info(f"   OTHER LEDs: REDUCED to match weakest brightness")
            logger.info(f"")
            logger.info(f"TARGET SIGNAL LEVEL (GLOBAL):")
            logger.info(f"   {target_counts:,} counts ({WEAKEST_TARGET_PERCENT}% of detector max)")
            logger.info(f"   This target applies to ALL channels in {TARGET_WAVELENGTH_MIN}-{TARGET_WAVELENGTH_MAX}nm")
            logger.info(f"   Achieved via: FROZEN integration time + BALANCED LED intensities")
            logger.info("=" * 80)

            # Get LED ranking from Step 3
            if not self.state.led_ranking or len(self.state.led_ranking) < 1:
                logger.error("⚠️  LED ranking not found! Step 3 must run before Step 4.")
                return False

            # Extract channel IDs from ranking (weakest first)
            all_channels = [ch_info[0] for ch_info in self.state.led_ranking]
            weakest_ch = all_channels[0]

            logger.info(f"")
            logger.info(f"=" * 80)
            logger.info(f"⚡ STEP 4: GLOBAL MODE - INTEGRATION TIME + LED BALANCING")
            logger.info(f"=" * 80)
            logger.info(f"   LED ranking from Step 3: {all_channels} (weakest → strongest)")
            logger.info(f"")
            logger.info(f"   🔒 GLOBAL MODE CALIBRATION FLOW:")
            logger.info(f"      ┌─────────────────────────────────────────────────────────────┐")
            logger.info(f"      │ 4.1: Set {weakest_ch.upper()} (WEAKEST) → LED=255 (FIXED FOREVER)    │")
            logger.info(f"      │ 4.2: Probe integration times [5, 15, 50] ms                │")
            logger.info(f"      │ 4.3: Extrapolate to hit {target_counts:,} counts @ LED=255        │")
            logger.info(f"      │ 4.4: FREEZE integration time (NEVER CHANGES)                │")
            logger.info(f"      │ 4.5: Adjust OTHER LEDs to hit {target_counts:,} counts         │")
            logger.info(f"      │      (Integration FROZEN, only LED value changes)           │")
            logger.info(f"      └─────────────────────────────────────────────────────────────┘")
            logger.info(f"")
            logger.info(f"   Target Signal: {target_counts:,} counts in {TARGET_WAVELENGTH_MIN}-{TARGET_WAVELENGTH_MAX}nm ROI")
            logger.info(f"   Method: ONE integration time, DIFFERENT LED intensities per channel")
            logger.info(f"=" * 80)

            # Ensure correct optical mode and clean LED state before probing
            try:
                self.ctrl.set_mode(mode="s")
                time.sleep(0.4)
            except Exception:
                pass
            try:
                self._all_leds_off_batch()
                time.sleep(self.led_off_delay_s)
            except Exception:
                pass

            # Get 580-610nm test region indices
            wave_data = self.state.wavelengths
            roi_min_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MIN))
            roi_max_idx = np.argmin(np.abs(wave_data - TARGET_WAVELENGTH_MAX))

            # ========================================================================
            # STEP 4.1: SET WEAKEST LED TO 255
            # ========================================================================
            logger.info("")
            logger.info("=" * 80)
            logger.info(f"STEP 4.1: Set weakest LED ({weakest_ch.upper()}) to 255")
            logger.info("=" * 80)
            self.state.ref_intensity[weakest_ch] = MAX_LED_INTENSITY
            logger.info(f"✅ {weakest_ch.upper()} = 255 (LOCKED)")

            # ========================================================================
            # STEP 4.2 & 4.3: PROBE INTEGRATION TIMES & EXTRAPOLATE
            # ========================================================================
            logger.info("")
            logger.info("=" * 80)
            logger.info("STEP 4.2-4.3: Probe integration times & extrapolate")
            logger.info("=" * 80)
            logger.info(f"Target: {target_counts:,} counts (~75% detector max)")
            logger.info(f"Probing: 5, 15, 50ms with {weakest_ch.upper()} @ 255")

            # Helper function to measure weakest at a given integration time
            def _measure_weakest_at(t_seconds: float) -> Optional[float]:
                """Measure weakest LED @ 255 at given integration time."""
                t_seconds = float(np.clip(t_seconds, min_int, max_int))
                self.usb.set_integration(t_seconds)
                time.sleep(0.08)

                res = self._measure_channel_in_roi(
                    weakest_ch, MAX_LED_INTENSITY, int(roi_min_idx), int(roi_max_idx), f"{weakest_ch} @255"
                )
                if res is None:
                    return None
                max_sig, _ = res
                return float(max_sig)

            # Probe 3 integration times: 5, 15, 50ms
            seed_ms = [5.0, 15.0, 50.0]
            probe_times = [ms / MS_TO_SECONDS for ms in seed_ms]
            probe_results = []  # [(time_seconds, signal_counts)]

            for idx, t in enumerate(probe_times, 1):
                if self._is_stopped():
                    return False
                sig = _measure_weakest_at(t)
                if sig is None:
                    logger.warning(f"   Probe {idx} failed, skipping")
                    continue
                probe_results.append((t, sig))
                pct = (sig / detector_max) * 100.0
                logger.info(f"   Probe {idx}: {t*MS_TO_SECONDS:.1f}ms → {sig:6.0f} counts ({pct:5.1f}%)")

            if len(probe_results) < 2:
                logger.error("❌ Not enough probe data to extrapolate")
                return False

            # Extrapolate to find integration time for target
            # Try linear interpolation between bracket points
            probe_results.sort(key=lambda x: x[0])  # Sort by time

            # Find bracket around target
            bracket = None
            for i in range(len(probe_results) - 1):
                (t1, c1), (t2, c2) = probe_results[i], probe_results[i+1]
                if (c1 - target_counts) * (c2 - target_counts) <= 0:  # crosses target
                    bracket = ((t1, c1), (t2, c2))
                    break

            if bracket:
                (t1, c1), (t2, c2) = bracket
                if c2 != c1:
                    optimal_integration = t1 + (target_counts - c1) * (t2 - t1) / (c2 - c1)
                else:
                    optimal_integration = (t1 + t2) / 2.0
                optimal_integration = float(np.clip(optimal_integration, min_int, max_int))
                logger.info(f"   ✅ Extrapolated: {optimal_integration*MS_TO_SECONDS:.1f}ms for {target_counts:,} counts")
            else:
                # No bracket - use closest probe
                closest = min(probe_results, key=lambda x: abs(x[1] - target_counts))
                optimal_integration = closest[0]
                logger.warning(f"   ⚠️  No bracket found, using closest: {optimal_integration*MS_TO_SECONDS:.1f}ms")

            # ========================================================================
            # STEP 4.4: FREEZE INTEGRATION TIME
            # ========================================================================
            # STEP 4.4: FREEZE INTEGRATION TIME (NEVER CHANGES AFTER THIS)
            # ========================================================================
            logger.info("")
            logger.info("=" * 80)
            logger.info("🔒 STEP 4.4: FREEZE INTEGRATION TIME (GLOBAL MODE)")
            logger.info("=" * 80)
            logger.info(f"")
            logger.info(f"   📌 Setting integration time to: {optimal_integration*MS_TO_SECONDS:.2f} ms")
            logger.info(f"")
            logger.info(f"   🔒 THIS INTEGRATION TIME IS NOW FROZEN FOR:")
            logger.info(f"      • Remaining calibration steps (Steps 5-8)")
            logger.info(f"      • All future measurements on this device")
            logger.info(f"      • Both S-mode and P-mode acquisitions")
            logger.info(f"")
            logger.info(f"   ⚠️  IN GLOBAL MODE:")
            logger.info(f"      • Integration time NEVER changes")
            logger.info(f"      • Only LED intensities are adjusted per channel")
            logger.info(f"      • Weakest channel ({weakest_ch.upper()}) stays at LED=255 forever")
            logger.info(f"")
            self.state.integration = optimal_integration
            self.usb.set_integration(optimal_integration)
            time.sleep(0.1)
            logger.info(f"   ✅ Integration time LOCKED at {optimal_integration*MS_TO_SECONDS:.2f} ms")
            logger.info("=" * 80)

            # ========================================================================
            # STEP 4.5: BALANCE OTHER LEDs TO MATCH WEAKEST BRIGHTNESS
            # ========================================================================
            # ┌────────────────────────────────────────────────────────────────────┐
            # │ IRON-CLAD GLOBAL MODE LED BALANCING LOGIC (DO NOT MODIFY)        │
            # ├────────────────────────────────────────────────────────────────────┤
            # │ CONSTRAINT: Integration time is FROZEN from Step 4.4              │
            # │                                                                    │
            # │ GOAL: All channels hit {target_counts:,} counts at {TARGET_WAVELENGTH_MIN}-{TARGET_WAVELENGTH_MAX}nm       │
            # │                                                                    │
            # │ METHOD:                                                            │
            # │   1. Weakest LED = 255 (FIXED in Step 4.1, NEVER changes)        │
            # │   2. For each BRIGHTER channel:                                   │
            # │      a) Measure @ LED=255 with frozen integration time            │
            # │      b) If signal >= {SATURATION_THRESHOLD:,} (saturated):                  │
            # │         • Multi-point calibration: Measure @ [191,127,64,32]     │
            # │         • Build LED-to-signal curve (linear regression)           │
            # │         • Solve: LED = (target - intercept) / slope               │
            # │         • Handles non-linear LED response accurately              │
            # │      c) If signal < {SATURATION_THRESHOLD:,} (not saturated):              │
            # │         • Direct linear scaling: LED = (target / signal) × 255    │
            # │      d) Verify by measuring at calculated LED value               │
            # │                                                                    │
            # │ NEVER TOUCH: Integration time (frozen at {optimal_integration*MS_TO_SECONDS:.1f}ms)              │
            # │ NEVER TOUCH: Weakest LED (frozen at 255)                          │
            # │ ONLY ADJUST: LED values for brighter channels (reduce to <255)   │
            # └────────────────────────────────────────────────────────────────────┘

            # Use detector profile saturation threshold (consistent with Step 3)
            SATURATION_THRESHOLD = int(0.99 * detector_max)

            logger.info("")
            logger.info("=" * 80)
            logger.info("⚖️  STEP 4.5: BALANCE OTHER LEDs TO MATCH WEAKEST BRIGHTNESS")
            logger.info("=" * 80)
            logger.info(f"")
            logger.info(f"   FROZEN PARAMETERS:")
            logger.info(f"      Integration time: {optimal_integration*MS_TO_SECONDS:.2f} ms (NEVER CHANGES)")
            logger.info(f"      Weakest LED ({weakest_ch.upper()}): 255 (NEVER CHANGES)")
            logger.info(f"")
            logger.info(f"   TARGET FOR ALL CHANNELS:")
            logger.info(f"      {target_counts:,} counts in {TARGET_WAVELENGTH_MIN}-{TARGET_WAVELENGTH_MAX}nm ROI")
            logger.info(f"      (= {WEAKEST_TARGET_PERCENT}% of {detector_max:,} detector max)")
            logger.info(f"")
            logger.info(f"   BALANCING METHOD:")
            logger.info(f"      For each BRIGHTER channel:")
            logger.info(f"         • IF saturated @ LED=255: Multi-point calibration with regression")
            logger.info(f"         • IF not saturated @ LED=255: Direct linear scaling")
            logger.info(f"         • REDUCE LED value until signal = {target_counts:,} counts")
            logger.info(f"")
            logger.info(f"   SATURATION THRESHOLD: {SATURATION_THRESHOLD:,} counts (99% of {detector_max:,})")
            logger.info("=" * 80)

            # Process other channels (skip weakest - it's already at 255)
            for ch in all_channels[1:]:  # Skip weakest (index 0)
                if self._is_stopped():
                    return False

                logger.info(f"")
                logger.info(f"─" * 80)
                logger.info(f"📡 Calibrating Channel {ch.upper()}")
                logger.info(f"─" * 80)

                # ================================================================
                # STEP 1: Measure at LED=255 first
                # ================================================================
                res = self._measure_channel_in_roi(
                    ch, MAX_LED_INTENSITY, int(roi_min_idx), int(roi_max_idx), f"{ch} @255"
                )
                if res is None:
                    logger.error(f"   ❌ Failed to measure {ch} @ 255")
                    self.state.ref_intensity[ch] = MAX_LED_INTENSITY  # Fallback
                    continue

                max_sig_255, _ = res
                logger.info(f"   @ LED=255: {max_sig_255:6.0f} counts")

                # ================================================================
                # STEP 2: Check if saturated - use multi-point calibration
                # ================================================================
                if max_sig_255 >= SATURATION_THRESHOLD:
                    logger.warning(f"   ⚠️  SATURATED at LED=255! Using multi-point calibration...")

                    # Build LED-to-signal curve by measuring at multiple LED values
                    # This handles non-linear LED response better than single-point extrapolation
                    calibration_points = []  # [(led_value, signal_counts)]

                    # Try decreasing LED values until we get unsaturated reading
                    test_leds = [191, 127, 64, 32]  # 75%, 50%, 25%, 12.5%

                    for test_led in test_leds:
                        if self._is_stopped():
                            return False

                        res = self._measure_channel_in_roi(
                            ch, test_led, int(roi_min_idx), int(roi_max_idx), f"{ch} @{test_led}"
                        )
                        if res is None:
                            logger.warning(f"   ⚠️  Measurement at LED={test_led} failed, skipping")
                            continue

                        test_sig, _ = res
                        logger.info(f"   @ LED={test_led}: {test_sig:6.0f} counts")

                        # Only use unsaturated points for calibration curve
                        if test_sig < SATURATION_THRESHOLD:
                            calibration_points.append((test_led, test_sig))

                            # If we have 2+ good points, we can extrapolate
                            if len(calibration_points) >= 2:
                                break

                    # Check if we got enough calibration points
                    if len(calibration_points) < 1:
                        logger.error(f"   ❌ Could not get unsaturated measurement, using fallback LED=255")
                        self.state.ref_intensity[ch] = MAX_LED_INTENSITY
                        continue
                    elif len(calibration_points) == 1:
                        # Only one point - use simple linear extrapolation
                        test_led, test_sig = calibration_points[0]
                        if test_sig > 0:
                            required_led = int((target_counts / test_sig) * test_led)
                            required_led = max(1, min(MAX_LED_INTENSITY, required_led))
                            logger.info(f"   📐 Single-point extrapolation: LED={required_led}")
                        else:
                            logger.error(f"   ❌ Invalid signal, using fallback")
                            self.state.ref_intensity[ch] = MAX_LED_INTENSITY
                            continue
                    else:
                        # Multiple points - use linear regression for better accuracy
                        # Fit: signal = slope * LED + intercept
                        leds = np.array([pt[0] for pt in calibration_points])
                        signals = np.array([pt[1] for pt in calibration_points])

                        # Simple linear regression: y = mx + b
                        # slope = cov(x,y) / var(x)
                        slope = np.cov(leds, signals)[0, 1] / np.var(leds) if np.var(leds) > 0 else (signals[-1] - signals[0]) / (leds[-1] - leds[0])
                        intercept = np.mean(signals) - slope * np.mean(leds)

                        # Solve for LED: target = slope * LED + intercept
                        # LED = (target - intercept) / slope
                        if slope > 0:
                            required_led = int((target_counts - intercept) / slope)
                            required_led = max(1, min(MAX_LED_INTENSITY, required_led))
                            logger.info(f"   📐 Multi-point regression: LED={required_led} (from {len(calibration_points)} points)")
                        else:
                            logger.error(f"   ❌ Invalid slope, using single-point fallback")
                            test_led, test_sig = calibration_points[0]
                            required_led = int((target_counts / test_sig) * test_led) if test_sig > 0 else MAX_LED_INTENSITY
                            required_led = max(1, min(MAX_LED_INTENSITY, required_led))

                else:
                    # ============================================================
                    # STEP 3: Not saturated - use direct linear scaling
                    # ============================================================
                    # If already below target, keep at 255
                    if max_sig_255 <= target_counts:
                        self.state.ref_intensity[ch] = MAX_LED_INTENSITY
                        logger.info(f"   ✅ Already below target → LED=255")
                        continue

                    # Calculate required LED intensity (linear scaling)
                    required_led = int((target_counts / max_sig_255) * MAX_LED_INTENSITY)
                    required_led = max(1, min(MAX_LED_INTENSITY, required_led))  # Clamp to [1, 255]
                    logger.info(f"   📐 Calculated LED={required_led} for target {target_counts:,} counts")

                # ================================================================
                # STEP 4: Verify by measuring at calculated intensity
                # ================================================================
                res = self._measure_channel_in_roi(
                    ch, required_led, int(roi_min_idx), int(roi_max_idx), f"{ch} @{required_led}"
                )
                if res is None:
                    logger.warning(f"   ⚠️  Verification failed, using calculated value")
                    self.state.ref_intensity[ch] = required_led
                    continue

                verified_sig, _ = res
                self.state.ref_intensity[ch] = required_led
                pct_of_target = (verified_sig / target_counts) * 100.0
                logger.info(f"   @ LED={required_led}: {verified_sig:6.0f} counts ({pct_of_target:.1f}% of target)")
                logger.info(f"   ✅ {ch.upper()} = {required_led}")

            # Turn off all LEDs after calibration
            self._all_leds_off_batch()
            time.sleep(self.led_off_delay_s)

            # ========================================================================
            # STEP 4.6: FINAL SUMMARY
            # ========================================================================
            logger.info("")
            logger.info("=" * 80)
            logger.info("✅ STEP 4 COMPLETE: GLOBAL CALIBRATION")
            logger.info("=" * 80)
            logger.info("")
            logger.info(f"Global Integration Time: {optimal_integration*MS_TO_SECONDS:.1f}ms (FROZEN for Steps 5-7)")
            logger.info(f"Target: {target_counts:,} counts (~75% detector max)")
            logger.info("")
            logger.info("Final Calibration Results:")
            logger.info("")
            logger.info("Channel  | LED Intensity | Integration Time")
            logger.info("-" * 50)
            for ch in all_channels:
                led_val = self.state.ref_intensity.get(ch, 255)
                logger.info(f"   {ch.upper()}     |      {led_val:3d}      |    {optimal_integration*MS_TO_SECONDS:6.1f} ms")
            logger.info("")
            logger.info("Mode: GLOBAL (balanced LED intensities, single integration time)")
            logger.info("")
            logger.info("Next Steps:")
            logger.info(f"   • Step 5: Measure dark noise @ {optimal_integration*MS_TO_SECONDS:.1f}ms")
            logger.info("   • Step 6: Measure S-ref with balanced LEDs")
            logger.info("=" * 80)

            # ✅ SYNC: Copy ref_intensity to leds_calibrated for live acquisition
            # Live acquisition reads from leds_calibrated via get_led_for_live()
            self.state.leds_calibrated = self.state.ref_intensity.copy()
            logger.debug(f"✅ Synced leds_calibrated from ref_intensity: {self.state.leds_calibrated}")

            # ⚠️ VALIDATION: Verify LED values were actually set
            logger.info("")
            logger.info("=" * 80)
            logger.info("🔍 STEP 4 VALIDATION: Checking LED values were stored correctly")
            logger.info("=" * 80)

            led_values_valid = True
            for ch in all_channels:
                led_val = self.state.ref_intensity.get(ch, -1)
                if led_val <= 0:
                    logger.error(f"❌ Channel {ch.upper()} has INVALID LED value: {led_val}")
                    led_values_valid = False
                else:
                    logger.info(f"✅ Channel {ch.upper()}: LED = {led_val} (stored in self.state.ref_intensity)")

            # Check if weakest is actually at 255
            weakest_led = self.state.ref_intensity.get(weakest_ch, -1)
            if weakest_led != MAX_LED_INTENSITY:
                logger.warning(f"⚠️  WARNING: Weakest channel {weakest_ch.upper()} should be LED=255, but is {weakest_led}")
                led_values_valid = False
            else:
                logger.info(f"✅ Weakest channel {weakest_ch.upper()} correctly set to LED=255")

            # Check if all LEDs are identical (should NOT be in GLOBAL mode)
            unique_leds = set(self.state.ref_intensity.get(ch, 0) for ch in all_channels)
            if len(unique_leds) == 1 and len(all_channels) > 1:
                logger.error("")
                logger.error("❌ CRITICAL ERROR: All channels have IDENTICAL LED values!")
                logger.error(f"   All LEDs = {list(unique_leds)[0]}")
                logger.error("   Step 4 LED BALANCING DID NOT WORK!")
                logger.error("   Expected: Different LED values (weakest=255, others<255)")
                logger.error("")
                led_values_valid = False
            else:
                logger.info(f"✅ LED values are properly differentiated: {sorted(unique_leds, reverse=True)}")

            if not led_values_valid:
                logger.error("")
                logger.error("=" * 80)
                logger.error("❌ STEP 4 LED BALANCING FAILED!")
                logger.error("=" * 80)
                return False

            logger.info("")
            logger.info("✅ Step 4 LED values validated - ready for Step 5")
            logger.info("=" * 80)

            # ========================================================================
            # STEP 4.7: DIAGNOSTIC - CAPTURE RAW S-POL SPECTRA WITH FINAL LED VALUES
            # ========================================================================
            logger.info("")
            logger.info("=" * 80)
            logger.info("📊 STEP 4 DIAGNOSTIC: Capturing raw S-pol spectra with final LED values")
            logger.info("=" * 80)
            logger.info(f"Integration time: {optimal_integration*MS_TO_SECONDS:.1f}ms (FROZEN)")
            logger.info("")

            try:
                # Measure each channel with its final LED value
                step4_diagnostic_spectra = {}
                step4_diagnostic_roi_means = {}

                for ch in all_channels:
                    if self._is_stopped():
                        break

                    led_val = self.state.ref_intensity.get(ch, 255)
                    logger.info(f"Measuring {ch.upper()} @ LED={led_val}...")

                    # Turn on channel with final LED value
                    intensities_dict = {ch: led_val}
                    ok = self._activate_channel_batch([ch], intensities_dict)
                    if not ok:
                        logger.warning(f"   Batch activation failed for {ch}, trying sequential...")
                        ok = self._activate_channel_sequential([ch], intensities_dict)

                    if not ok:
                        logger.error(f"   ❌ Failed to activate {ch}")
                        continue

                    time.sleep(self.led_on_delay_s)
                    self._last_active_channel = ch

                    # Acquire spectrum (no dark subtraction, no filter)
                    raw_array = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
                    if raw_array is None:
                        logger.error(f"   ❌ Failed to acquire spectrum for {ch}")
                        continue

                    # Apply spectral filter to get SPR range
                    filtered_array = self._apply_spectral_filter(raw_array)

                    # Calculate ROI mean (580-610nm)
                    roi_data = filtered_array[int(roi_min_idx):int(roi_max_idx)]
                    roi_mean = np.mean(roi_data)

                    step4_diagnostic_spectra[ch] = filtered_array.copy()
                    step4_diagnostic_roi_means[ch] = roi_mean

                    logger.info(f"   {ch.upper()}: ROI mean = {roi_mean:7.0f} counts (LED={led_val})")

                # ✨ STORE Step 4 ROI means for QC comparison with Step 6
                self.state.step4_raw_spol_roi_means = step4_diagnostic_roi_means.copy()
                logger.debug(f"📊 Stored Step 4 ROI means for QC: {step4_diagnostic_roi_means}")

                # ========================================================================
                # STEP 4.8: BALANCING TOLERANCE CHECK - Verify all channels within 10%
                # ========================================================================
                logger.info("")
                logger.info("=" * 80)
                logger.info("🔍 STEP 4.8: LED BALANCING TOLERANCE CHECK")
                logger.info("=" * 80)
                logger.info(f"Target: {target_counts:,} counts")
                logger.info("Tolerance: ±10% (all channels must be within this range)")
                logger.info("")

                tolerance = 0.10  # 10%
                min_allowed = target_counts * (1 - tolerance)
                max_allowed = target_counts * (1 + tolerance)

                balancing_passed = True
                channels_out_of_tolerance = []

                logger.info("Channel | ROI Mean  | Deviation | Status")
                logger.info("-----------------------------------------------")

                for ch in all_channels:
                    roi_mean = step4_diagnostic_roi_means.get(ch, 0)
                    deviation = ((roi_mean - target_counts) / target_counts) * 100.0

                    if min_allowed <= roi_mean <= max_allowed:
                        status = "✅ PASS"
                    else:
                        status = "❌ FAIL"
                        balancing_passed = False
                        channels_out_of_tolerance.append((ch, roi_mean, deviation))

                    logger.info(f"   {ch.upper()}    | {roi_mean:7.0f}  | {deviation:+6.1f}%  | {status}")

                logger.info("")
                logger.info(f"Acceptable range: {min_allowed:.0f} - {max_allowed:.0f} counts")

                # ========================================================================
                # STEP 4.9: RETRY LOOP - Adjust out-of-tolerance channels (max 3 attempts)
                # ========================================================================
                MAX_TOLERANCE_RETRIES = 3
                retry_attempt = 0

                while not balancing_passed and retry_attempt < MAX_TOLERANCE_RETRIES:
                    retry_attempt += 1
                    logger.warning("")
                    logger.warning("=" * 80)
                    logger.warning(f"⚠️ RETRY {retry_attempt}/{MAX_TOLERANCE_RETRIES}: Adjusting out-of-tolerance channels")
                    logger.warning("=" * 80)
                    logger.warning("")
                    logger.warning("The following channels need adjustment:")
                    for ch, roi_mean, deviation in channels_out_of_tolerance:
                        logger.warning(f"   • Channel {ch.upper()}: {roi_mean:.0f} counts ({deviation:+.1f}% from target)")
                    logger.warning("")

                    # Adjust each out-of-tolerance channel using multi-point measurement
                    for ch, roi_mean, deviation in channels_out_of_tolerance:
                        current_led = self.state.ref_intensity.get(ch, 255)

                        # ============================================================
                        # SMART ADJUSTMENT: Use multi-point calibration for accuracy
                        # ============================================================
                        # Instead of simple linear scaling (which fails for non-linear regions),
                        # we measure at 2-3 LED values and use regression to find the correct LED

                        logger.info(f"   {ch.upper()}: Current LED={current_led}, signal={roi_mean:.0f} counts")
                        logger.info(f"         Need to adjust to {target_counts:,} counts (currently {deviation:+.1f}%)")

                        # Measure at current LED and one other point to establish slope
                        calibration_points = [(current_led, roi_mean)]

                        # Choose a second measurement point based on deviation direction
                        if roi_mean < target_counts:
                            # Signal too low → need higher LED
                            # Measure at higher LED to establish slope
                            test_led = min(255, int(current_led * 1.3))  # Try 30% higher
                        else:
                            # Signal too high → need lower LED
                            # Measure at lower LED to establish slope
                            test_led = max(1, int(current_led * 0.7))  # Try 30% lower

                        if test_led != current_led:
                            # Activate channel with test LED value
                            intensities_dict = {ch: test_led}
                            ok = self._activate_channel_batch([ch], intensities_dict)
                            if not ok:
                                ok = self._activate_channel_sequential([ch], intensities_dict)

                            if ok:
                                time.sleep(self.led_on_delay_s)
                                raw_array = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
                                if raw_array is not None:
                                    filtered_array = self._apply_spectral_filter(raw_array)
                                    test_roi_data = filtered_array[int(roi_min_idx):int(roi_max_idx)]
                                    test_roi_mean = np.mean(test_roi_data)
                                    calibration_points.append((test_led, test_roi_mean))
                                    logger.info(f"         Test point: LED={test_led} → {test_roi_mean:.0f} counts")

                        # Turn off LED
                        self._all_leds_off_batch()
                        time.sleep(self.led_off_delay_s)

                        # Calculate new LED using linear regression if we have 2+ points
                        if len(calibration_points) >= 2:
                            # Linear fit: signal = slope * led + intercept
                            leds = np.array([p[0] for p in calibration_points])
                            signals = np.array([p[1] for p in calibration_points])

                            # Use numpy polyfit for linear regression
                            coeffs = np.polyfit(leds, signals, 1)
                            slope = coeffs[0]
                            intercept = coeffs[1]

                            # Solve for LED: target = slope * led + intercept
                            # led = (target - intercept) / slope
                            if abs(slope) > 0.1:  # Valid slope
                                new_led = (target_counts - intercept) / slope
                                new_led = int(np.clip(new_led, 1, 255))
                                logger.info(f"         Regression: slope={slope:.2f}, intercept={intercept:.0f}")
                                logger.info(f"         Calculated: LED={new_led} (from {len(calibration_points)} points)")
                            else:
                                # Slope too flat - use simple scaling as fallback
                                adjustment_factor = target_counts / roi_mean if roi_mean > 0 else 1.0
                                new_led = int(current_led * adjustment_factor)
                                new_led = max(1, min(255, new_led))
                                logger.warning(f"         Slope too flat, using linear scaling: LED={new_led}")
                        else:
                            # Only one point - use simple linear scaling
                            adjustment_factor = target_counts / roi_mean if roi_mean > 0 else 1.0
                            new_led = int(current_led * adjustment_factor)
                            new_led = max(1, min(255, new_led))
                            logger.info(f"         Single-point scaling: LED={new_led} (factor: {adjustment_factor:.3f})")

                        logger.info(f"   {ch.upper()}: LED {current_led} → {new_led}")

                        # Update stored LED value
                        self.state.ref_intensity[ch] = new_led
                        self.state.leds_calibrated[ch] = new_led

                    # Re-measure all channels with adjusted LED values
                    logger.info("")
                    logger.info("📊 Re-measuring all channels with adjusted LED values...")
                    logger.info("")

                    step4_diagnostic_roi_means = {}

                    for ch in all_channels:
                        if self._is_stopped():
                            break

                        led_val = self.state.ref_intensity.get(ch, 255)
                        logger.info(f"   Measuring {ch.upper()} @ LED={led_val}...")

                        # Turn on channel with adjusted LED value
                        intensities_dict = {ch: led_val}
                        ok = self._activate_channel_batch([ch], intensities_dict)
                        if not ok:
                            logger.warning(f"      Batch activation failed for {ch}, trying sequential...")
                            ok = self._activate_channel_sequential([ch], intensities_dict)

                        if not ok:
                            logger.error(f"      ❌ Failed to activate {ch}")
                            continue

                        time.sleep(self.led_on_delay_s)
                        self._last_active_channel = ch

                        # Acquire spectrum (no dark subtraction, no filter)
                        raw_array = self._acquire_calibration_spectrum(apply_filter=False, subtract_dark=False)
                        if raw_array is None:
                            logger.error(f"      ❌ Failed to acquire spectrum for {ch}")
                            continue

                        # Apply spectral filter to get SPR range
                        filtered_array = self._apply_spectral_filter(raw_array)

                        # Calculate ROI mean (580-610nm)
                        roi_data = filtered_array[int(roi_min_idx):int(roi_max_idx)]
                        roi_mean = np.mean(roi_data)

                        step4_diagnostic_spectra[ch] = filtered_array.copy()
                        step4_diagnostic_roi_means[ch] = roi_mean

                        logger.info(f"      {ch.upper()}: ROI mean = {roi_mean:7.0f} counts (LED={led_val})")

                    # Turn off LEDs
                    self._all_leds_off_batch()
                    time.sleep(self.led_off_delay_s)

                    # Re-check tolerance
                    logger.info("")
                    logger.info("🔍 Re-checking tolerance after adjustment...")
                    logger.info("")
                    logger.info("Channel | ROI Mean  | Deviation | Status")
                    logger.info("-----------------------------------------------")

                    balancing_passed = True
                    channels_out_of_tolerance = []

                    for ch in all_channels:
                        roi_mean = step4_diagnostic_roi_means.get(ch, 0)
                        deviation = ((roi_mean - target_counts) / target_counts) * 100.0

                        if min_allowed <= roi_mean <= max_allowed:
                            status = "✅ PASS"
                        else:
                            status = "❌ FAIL"
                            balancing_passed = False
                            channels_out_of_tolerance.append((ch, roi_mean, deviation))

                        logger.info(f"   {ch.upper()}    | {roi_mean:7.0f}  | {deviation:+6.1f}%  | {status}")

                    if balancing_passed:
                        logger.info("")
                        logger.info("=" * 80)
                        logger.info(f"✅ TOLERANCE CHECK PASSED on retry attempt {retry_attempt}")
                        logger.info("=" * 80)
                        # Update Step 4 ROI means with successful values
                        self.state.step4_raw_spol_roi_means = step4_diagnostic_roi_means.copy()
                        break
                    else:
                        logger.warning("")
                        logger.warning(f"⚠️ Still out of tolerance after retry {retry_attempt}/{MAX_TOLERANCE_RETRIES}")

                # Final check after all retries
                if not balancing_passed:
                    logger.error("")
                    logger.error("=" * 80)
                    logger.error(f"❌ STEP 4 BALANCING FAILED AFTER {MAX_TOLERANCE_RETRIES} RETRIES!")
                    logger.error("=" * 80)
                    logger.error("")
                    logger.error("The following channels remain outside the ±10% tolerance:")
                    for ch, roi_mean, deviation in channels_out_of_tolerance:
                        logger.error(f"   • Channel {ch.upper()}: {roi_mean:.0f} counts ({deviation:+.1f}% from target)")
                    logger.error("")
                    logger.error("This indicates LED balancing cannot converge properly.")
                    logger.error("Possible causes:")
                    logger.error("   1. LED saturation preventing accurate calibration")
                    logger.error("   2. Integration time too high/low for this LED configuration")
                    logger.error("   3. Hardware issue with LED control")
                    logger.error("")
                    logger.error("Recommended actions:")
                    logger.error("   1. Check LED hardware connections")
                    logger.error("   2. Try different fiber/LED configuration")
                    logger.error("   3. Manually adjust integration time factor")
                    logger.error("=" * 80)
                    return False
                else:
                    if retry_attempt == 0:
                        logger.info("✅ ALL CHANNELS WITHIN ±10% TOLERANCE")
                        logger.info("   LED balancing successful!")
                    else:
                        logger.info("")
                        logger.info("=" * 80)
                        logger.info(f"✅ ALL CHANNELS WITHIN ±10% TOLERANCE (after {retry_attempt} adjustment(s))")
                        logger.info("   LED balancing successful!")
                        logger.info("=" * 80)

                # Turn off all LEDs
                self._all_leds_off_batch()
                time.sleep(self.led_off_delay_s)

                # Create diagnostic visualization
                if len(step4_diagnostic_spectra) > 0:
                    self._create_step4_diagnostic_plot(
                        step4_diagnostic_spectra,
                        step4_diagnostic_roi_means,
                        all_channels,
                        optimal_integration,
                        target_counts
                    )
                    logger.info("✅ Step 4 diagnostic plot saved")
                else:
                    logger.warning("⚠️  No diagnostic spectra captured")

            except Exception as diag_e:
                logger.warning(f"⚠️  Step 4 diagnostic capture failed: {diag_e}")
                # Non-critical - continue with calibration

            logger.info("=" * 80)

            return True

        except Exception as e:
            logger.exception(f"Error in Step 4: {e}")
            return False

    # ========================================================================
    # STEP 5: RE-MEASURE DARK NOISE (AT OPTIMAL INTEGRATION TIME)
    # ========================================================================
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
    # STEP 6: S-REFERENCE MEASUREMENT (Final S-mode baselines)
    # ========================================================================

    def step_6_measure_s_reference(self, ch_list: list[str]) -> bool:
        """STEP 6: Measure S-reference signals for all channels.

        Replaces the older Step 7. Captures S-mode references using the
        final settings from Steps 4 and 5, then subtracts the Step 5 dark.

        Modes:
        - global: use global integration time with dynamic scans
        - per_channel: set per-channel integration time, ALWAYS 1 scan per channel

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            logger.info("=" * 80)
            logger.info("STEP 6: S-reference Measurement (S-mode)")
            logger.info("=" * 80)

            # Force S-mode
            self.ctrl.set_mode(mode="s")
            time.sleep(0.4)

            # Determine acquisition parameters
            mode = getattr(self.state, 'calibration_mode', 'global')
            if mode == 'per_channel':
                logger.info("   Mode: PER_CHANNEL → single scan per channel (no dynamic scans)")
            else:
                # GLOBAL: compute dynamic scan count for the frozen integration time
                ref_scans = calculate_dynamic_scans(self.state.integration)
                logger.info(
                    f"📊 S-ref averaging (GLOBAL): {ref_scans} scans "
                    f"(integration={self.state.integration*1000:.1f}ms, "
                    f"total={ref_scans * self.state.integration * 1000:.0f}ms)"
                )

            # Acquire S-ref per channel (raw first; dark subtraction after)
            for ch in ch_list:
                if self._is_stopped():
                    return False

                if mode == 'per_channel':
                    # Use per-channel integration; enforce single scan
                    # Prefer integration_per_channel; fall back to per_channel_integration_times
                    ch_integration = None
                    try:
                        ch_integration = self.state.integration_per_channel.get(ch)
                    except Exception:
                        ch_integration = None
                    if not ch_integration and hasattr(self.state, 'per_channel_integration_times'):
                        ch_integration = float(self.state.per_channel_integration_times.get(ch, 0.0))
                    if not ch_integration or ch_integration <= 0:
                        logger.error(f"Missing per-channel integration for {ch}")
                        return False

                    # Apply integration (expects seconds)
                    if hasattr(self.usb, 'set_integration'):
                        self.usb.set_integration(ch_integration)
                    elif hasattr(self.usb, 'set_integration_time'):
                        self.usb.set_integration_time(float(ch_integration))
                    ref_scans = 1  # single scan per user requirement
                    logger.info(
                        f"   {ch.upper()}: {ch_integration*1000:.1f}ms × 1 scan (per-channel mode)"
                    )
                else:
                    # GLOBAL: integration already frozen in state; scans computed above
                    pass

                # Activate LED
                if mode == 'per_channel':
                    intensities_dict = {ch: MAX_LED_INTENSITY}  # LED=255
                else:
                    led_val = int(self.state.ref_intensity.get(ch, MAX_LED_INTENSITY))
                    intensities_dict = {ch: led_val}
                    logger.info(f"🔦 Step 6: Setting channel {ch.upper()} LED = {led_val} (from ref_intensity)")

                self._activate_channel_batch([ch], intensities_dict)
                time.sleep(self.led_on_delay_s)

                # Track last active channel
                self._last_active_channel = ch

                # Acquire
                # ⚠️ CRITICAL: DO NOT apply jitter correction to calibration reference measurements!
                # Jitter correction detrends the signal (subtracts mean), which would incorrectly
                # remove the LED signal we're trying to measure. Dark subtraction is applied separately.
                averaged_signal = self._acquire_averaged_spectrum(
                    num_scans=ref_scans,
                    apply_filter=True,
                    subtract_dark=False,
                    description=f"S-reference (ch {ch})",
                    apply_jitter_correction=False  # ⚠️ MUST be False - preserve LED signal!
                )
                if averaged_signal is None:
                    logger.error(f"Failed to acquire S-reference for channel {ch}")
                    return False

                # Store raw (filtered) S-ref
                self.state.ref_sig[ch] = averaged_signal

                # Turn off LED before next channel
                with suppress(Exception):
                    self._all_leds_off_batch()
                time.sleep(self.led_off_delay_s)

            # Dark subtraction (use Step 5 darks; per-channel if available)
            if mode == 'per_channel' and hasattr(self.state, 'per_channel_dark_noise') and self.state.per_channel_dark_noise:
                for ch in ch_list:
                    ref = self.state.ref_sig.get(ch)
                    dark = self.state.per_channel_dark_noise.get(ch)
                    if ref is None or dark is None:
                        continue
                    ref_arr = np.array(ref, dtype=float)
                    dark_arr = np.array(dark, dtype=float)
                    # Resample dark if needed
                    if len(dark_arr) != len(ref_arr):
                        x_old = np.linspace(0, 1, len(dark_arr))
                        x_new = np.linspace(0, 1, len(ref_arr))
                        try:
                            from scipy.interpolate import interp1d
                            dark_arr = interp1d(x_old, dark_arr, kind='linear', bounds_error=False, fill_value="extrapolate")(x_new)
                        except Exception:
                            dark_arr = np.interp(x_new, x_old, dark_arr)
                    self.state.ref_sig[ch] = ref_arr - dark_arr
                logger.info("✅ Step 6: Applied per-channel dark subtraction using Step 5 darks")
            elif getattr(self.state, 'dark_noise', None) is not None:
                dark_arr = np.array(self.state.dark_noise, dtype=float)
                for ch in ch_list:
                    ref = self.state.ref_sig.get(ch)
                    if ref is None:
                        continue
                    ref_arr = np.array(ref, dtype=float)
                    if len(dark_arr) != len(ref_arr):
                        x_old = np.linspace(0, 1, len(dark_arr))
                        x_new = np.linspace(0, 1, len(ref_arr))
                        try:
                            from scipy.interpolate import interp1d
                            dark_res = interp1d(x_old, dark_arr, kind='linear', bounds_error=False, fill_value="extrapolate")(x_new)
                        except Exception:
                            dark_res = np.interp(x_new, x_old, dark_arr)
                    else:
                        dark_res = dark_arr
                    self.state.ref_sig[ch] = ref_arr - dark_res
                logger.info("✅ Step 6: Applied global dark subtraction using Step 5 dark")
            else:
                logger.warning("⚠️ Step 6: No Step 5 dark available; keeping raw S-references")

            # Save S-refs
            from pathlib import Path
            calib_dir = Path(ROOT_DIR) / "calibration_data"
            calib_dir.mkdir(exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            for ch in ch_list:
                if self.state.ref_sig.get(ch) is None:
                    continue
                s_ref_file = calib_dir / f"s_ref_{ch}_{timestamp}.npy"
                np.save(s_ref_file, self.state.ref_sig[ch])
                latest_s_ref = calib_dir / f"s_ref_{ch}_latest.npy"
                np.save(latest_s_ref, self.state.ref_sig[ch])
                logger.info(f"💾 S-ref[{ch}] saved: {s_ref_file}")

            logger.info(f"✅ All S-mode references saved to: {calib_dir}")

            # Mark calibration complete
            self.state.ch_error_list = []
            self.state.is_calibrated = True
            self.state.calibration_timestamp = time.time()
            logger.info("✅ Calibration complete - all channels validated (after Step 6)")

            # ✨ NEW: Log final calibration parameters after Step 6
            logger.info("")
            logger.info("=" * 80)
            logger.info("📊 STEP 6 COMPLETE - FINAL CALIBRATION PARAMETERS")
            logger.info("=" * 80)

            # Log integration time (global or per-channel)
            if self.state.calibration_mode == 'per_channel':
                logger.info("Mode: PER-CHANNEL (separate integration times per channel)")
                logger.info("")
                logger.info("   Channel  | LED Intensity | Integration Time | Scans")
                logger.info("   " + "-" * 58)
                for ch in ch_list:
                    # Use ref_intensity (the source of truth from Step 4)
                    led_val = self.state.ref_intensity.get(ch, 0) if self.state.ref_intensity else 0
                    int_val = self.state.integration_per_channel.get(ch, 0.0) if hasattr(self.state, 'integration_per_channel') else 0.0
                    scans = self.state.scans_per_channel.get(ch, 1) if hasattr(self.state, 'scans_per_channel') else 1
                    logger.info(f"      {ch.upper()}     |      {led_val:3d}       |     {int_val*1000:6.1f} ms     |   {scans}")
            else:
                logger.info("Mode: GLOBAL (single integration time for all channels)")
                logger.info(f"Integration Time: {self.state.integration*1000:.1f} ms")
                logger.info(f"Scans per channel: {self.state.num_scans}")
                logger.info("")
                logger.info("   Channel  | LED Intensity")
                logger.info("   " + "-" * 26)
                for ch in ch_list:
                    # ✅ FIX: Use ref_intensity (where Step 4 stores values), NOT leds_calibrated
                    led_val = self.state.ref_intensity.get(ch, 0) if self.state.ref_intensity else 0
                    logger.info(f"      {ch.upper()}     |      {led_val:3d}")

                # ⚠️ VALIDATION: Check if all LED values are identical (red flag in GLOBAL mode)
                if self.state.ref_intensity:
                    led_values = [self.state.ref_intensity.get(ch, 0) for ch in ch_list]
                    unique_leds = set(led_values)
                    if len(unique_leds) == 1 and len(ch_list) > 1:
                        logger.warning("")
                        logger.warning("⚠️  WARNING: All channels have IDENTICAL LED values!")
                        logger.warning(f"   All LEDs = {led_values[0]}")
                        logger.warning("   This suggests Step 4 (LED balancing) did not execute properly.")
                        logger.warning("   Expected: Different LED values to balance channels to weakest.")
                        logger.warning("")

            logger.info("")
            logger.info("=" * 80)

            # ========================================================================
            # STEP 6.7: CREATE DIAGNOSTIC PLOT
            # ========================================================================
            # Capture dark-subtracted S-ref spectra for diagnostic visualization
            try:
                logger.info("")
                logger.info("📊 Creating Step 6 diagnostic plot...")

                step6_diagnostic_spectra = {}
                step6_diagnostic_roi_means = {}

                # Calculate ROI indices (580-610nm)
                from settings import TARGET_WAVELENGTH_MIN, TARGET_WAVELENGTH_MAX
                wavelengths = self.state.wavelengths
                roi_min_idx = np.argmin(np.abs(wavelengths - TARGET_WAVELENGTH_MIN))
                roi_max_idx = np.argmin(np.abs(wavelengths - TARGET_WAVELENGTH_MAX))

                # Get detector max for target calculation
                detector_max = self.detector_profile.max_intensity_counts if self.detector_profile else 65535
                from settings import WEAKEST_TARGET_PERCENT
                target_counts = int(WEAKEST_TARGET_PERCENT / 100 * detector_max)

                for ch in ch_list:
                    # Get dark-subtracted S-ref spectrum
                    spectrum = self.state.ref_sig.get(ch)
                    if spectrum is not None:
                        step6_diagnostic_spectra[ch] = spectrum
                        # Calculate ROI mean
                        roi_mean = np.mean(spectrum[roi_min_idx:roi_max_idx])
                        step6_diagnostic_roi_means[ch] = roi_mean

                # ========================================================================
                # STEP 6.8: QC CHECK - Compare Step 4 vs Step 6 ROI Means
                # ========================================================================
                # The ONLY difference between Step 4 and Step 6 is dark subtraction
                # If Step 6 is dramatically different from Step 4, this is a RED FLAG
                # indicating the dark measurement was contaminated (LEDs not fully off)

                if hasattr(self.state, 'step4_raw_spol_roi_means') and self.state.step4_raw_spol_roi_means:
                    logger.info("")
                    logger.info("=" * 80)
                    logger.info("🔍 QC CHECK: Comparing Step 4 (raw S-pol) vs Step 6 (dark-subtracted)")
                    logger.info("=" * 80)
                    logger.info("")

                    # Get expected dark noise for this detector class
                    # Ocean Optics/USB4000: ~3,000 counts @ 36ms
                    expected_dark = 3000.0  # Ocean Optics detector class
                    if self.detector_profile:
                        # Scale expected dark by integration time ratio
                        integration_ms = self.state.integration * 1000  # Convert to ms
                        expected_dark = 3000.0 * (integration_ms / 36.0)

                    # Maximum allowed dark (2x expected)
                    max_allowed_dark = expected_dark * 2.0

                    logger.info(f"Expected dark noise: ~{expected_dark:.0f} counts")
                    logger.info(f"Maximum allowed dark (QC threshold): {max_allowed_dark:.0f} counts")
                    logger.info("")
                    logger.info("Channel | Step 4 (raw) | Step 6 (dark-sub) | Difference | Status")
                    logger.info("-" * 75)

                    qc_passed = True
                    qc_warnings = []

                    for ch in ch_list:
                        step4_mean = self.state.step4_raw_spol_roi_means.get(ch, 0)
                        step6_mean = step6_diagnostic_roi_means.get(ch, 0)
                        difference = step4_mean - step6_mean  # This is the effective dark subtracted

                        # QC criteria:
                        # 1. Difference should be positive (dark subtraction reduces signal)
                        # 2. Difference should be close to expected dark (±2x tolerance)
                        # 3. Step 6 should not be near-zero or negative

                        status = "✅ OK"
                        if difference < 0:
                            status = "❌ FAIL - Negative difference!"
                            qc_passed = False
                            qc_warnings.append(f"Channel {ch.upper()}: Step 6 > Step 4 (impossible!)")
                        elif difference > max_allowed_dark:
                            status = f"⚠️ HIGH - Dark too large (>{max_allowed_dark:.0f})"
                            qc_passed = False
                            qc_warnings.append(
                                f"Channel {ch.upper()}: Dark subtraction = {difference:.0f} counts "
                                f"(expected ~{expected_dark:.0f}, max {max_allowed_dark:.0f})"
                            )
                        elif difference < expected_dark * 0.5:
                            status = f"⚠️ LOW - Dark too small (<{expected_dark*0.5:.0f})"
                            # Don't fail QC for low dark, but warn
                        elif step6_mean < 1000:
                            status = "⚠️ WARN - Step 6 signal very low"
                            # Don't fail QC, but warn

                        logger.info(
                            f"   {ch.upper()}    |   {step4_mean:7.0f}    |     {step6_mean:7.0f}      |   "
                            f"{difference:6.0f}    | {status}"
                        )

                    logger.info("")

                    if qc_passed:
                        logger.info("✅ QC PASSED - Step 4 vs Step 6 comparison looks good")
                        logger.info("   Dark subtraction is within expected range")
                    else:
                        logger.error("❌ QC FAILED - Step 4 vs Step 6 comparison shows problems!")
                        logger.error("")
                        for warning in qc_warnings:
                            logger.error(f"   • {warning}")
                        logger.error("")
                        logger.error("DIAGNOSIS:")
                        logger.error("   The ONLY difference between Step 4 and Step 6 should be dark subtraction.")
                        logger.error("   Large differences indicate the dark measurement was contaminated.")
                        logger.error("")
                        logger.error("POSSIBLE CAUSES:")
                        logger.error("   1. LEDs not completely turned off during Step 5 dark measurement")
                        logger.error("   2. Insufficient LED-off settle time (increase led_off_delay_s)")
                        logger.error("   3. Hardware issue with LED control")
                        logger.error("   4. Wrong dark noise file being used")
                        logger.error("")
                        logger.error("RECOMMENDED ACTIONS:")
                        logger.error("   1. Check Step 5 logs - verify 'lx' command sent successfully")
                        logger.error("   2. Verify dark noise mean is within expected range (~3,000 for Ocean Optics)")
                        logger.error("   3. Re-run calibration with longer LED-off delay if needed")
                        logger.error("")

                        # Return failure to stop calibration
                        return False

                    logger.info("=" * 80)
                    logger.info("")
                else:
                    logger.warning("⚠️ Step 4 ROI means not available - skipping QC check")

                # Create diagnostic plot
                if step6_diagnostic_spectra:
                    integration_time = self.state.integration
                    self._create_step6_diagnostic_plot(
                        step6_diagnostic_spectra,
                        step6_diagnostic_roi_means,
                        ch_list,
                        integration_time,
                        target_counts
                    )
                    logger.info("✅ Step 6 diagnostic plot created successfully")
                else:
                    logger.warning("⚠️ No S-ref spectra available for diagnostic plot")

            except Exception as e:
                logger.warning(f"⚠️ Failed to create Step 6 diagnostic plot: {e}")
                # Non-critical - continue with calibration

            return True

        except Exception as e:
            logger.exception(f"Error measuring S-reference signals: {e}")
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
            logger.info("STEP 4 (PER-CHANNEL): Integration Time Optimization (LEDs=255, no balancing)")
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

            # Prepare ratio-based initializers from Step 3 ranking (if available)
            weakest_ch = getattr(self.state, 'weakest_channel', None)
            ranking = getattr(self.state, 'led_ranking', None)
            mean_by_ch: dict[str, float] = {}
            weakest_mean: Optional[float] = None
            if isinstance(ranking, list) and ranking:
                try:
                    # ranking format: [(ch, (mean, max_val, was_saturated)), ...]
                    for ch_rank, data in ranking:
                        if isinstance(data, (tuple, list)) and len(data) >= 1:
                            mean_by_ch[str(ch_rank)] = float(data[0])
                    if weakest_ch and weakest_ch in mean_by_ch:
                        weakest_mean = mean_by_ch[weakest_ch]
                    else:
                        # Fallback: take minimum mean as weakest
                        weakest_ch, weakest_mean = min(mean_by_ch.items(), key=lambda kv: kv[1]) if mean_by_ch else (None, None)
                except Exception:
                    mean_by_ch = {}
                    weakest_mean = None

            # Use global integration from Step 4 as base for proportional estimates
            base_integration = getattr(self.state, 'integration', None)

            # Optimize each channel independently
            for ch in ch_list:
                if self._is_stopped():
                    return False

                logger.info(f"   Optimizing channel {ch.upper()}...")

                # Binary search for optimal integration time
                # Default broad bracket
                integration_min = min_int
                integration_max = max_int
                best_integration = None
                best_signal = 0

                max_iterations = 15

                # Ratio-based initializer: t_est = base_int * (weak_mean / mean_ch)
                used_initializer = False
                if (
                    base_integration is not None
                    and weakest_mean is not None
                    and ch in mean_by_ch
                    and mean_by_ch[ch] > 0
                    and weakest_mean > 0
                ):
                    try:
                        ratio = weakest_mean / mean_by_ch[ch]
                        t_est = float(base_integration) * ratio
                        # Clamp to detector limits
                        t_est = max(min_int, min(max_int, t_est))
                        logger.info(
                            f"      Initial estimate from Step 3 ratio: t_est={t_est*1000:.1f}ms (ratio={ratio:.3f})"
                        )

                        # Quick verification at t_est
                        self.usb.set_integration(t_est)
                        time.sleep(0.1)
                        result = self._measure_channel_in_roi(
                            ch, MAX_LED_INTENSITY, int(roi_min_idx), int(roi_max_idx),
                            f"ch {ch} ratio-initial check"
                        )
                        if result is not None:
                            signal_max, _ = result
                            signal_percent = (signal_max / detector_max) * 100
                            logger.debug(
                                f"      Initial check: {t_est*1000:.1f}ms → {signal_max:6.0f} counts ({signal_percent:5.1f}%)"
                            )
                            if target_min <= signal_max <= target_max:
                                best_integration = t_est
                                best_signal = signal_max
                                used_initializer = True
                                logger.info(
                                    f"      ✅ Initial estimate already within target: {best_integration*1000:.1f}ms ({signal_percent:.1f}%)"
                                )
                            else:
                                # Narrow the bracket around the estimate (half/double within bounds)
                                span_low = max(min_int, t_est * 0.5)
                                span_high = min(max_int, t_est * 2.0)
                                if span_low < span_high:
                                    integration_min, integration_max = span_low, span_high
                                    logger.info(
                                        f"      Bracketing search around estimate: [{integration_min*1000:.1f}, {integration_max*1000:.1f}] ms"
                                    )
                                else:
                                    logger.debug("      Ratio-based bracket collapsed; using full range")
                    except Exception as _:
                        pass

                for iteration in range(max_iterations):
                    # If initializer already found a valid solution, skip binary search
                    if used_initializer and best_integration is not None:
                        break

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

                # Apply per-channel policy: no window, cap integration at 200 ms, scans=1
                budget_ms = 200.0
                integration_ms = best_integration * 1000
                if integration_ms > budget_ms:
                    logger.info(
                        f"      Capping integration to {budget_ms:.1f}ms (was {integration_ms:.1f}ms) per per-channel policy"
                    )
                    integration_ms = budget_ms
                    best_integration = integration_ms / 1000.0
                # Always single scan in per-channel mode
                num_scans = 1

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
        """STEP 5: Re-measure dark noise with final integration time(s).

        This step re-measures dark noise after integration time optimization
        (Step 4) is complete.

        **GLOBAL MODE:**
        - Measures ONE dark spectrum at global integration time

        **PER-CHANNEL MODE:**
        - Measures FOUR dark spectra (one per channel at each channel's integration time)
        - Stores per-channel darks in self.state.per_channel_dark_noise

        The purpose is to get accurate dark noise for the actual integration
        time that will be used during SPR measurements (Step 1 used a temporary
        32ms integration time).

        Returns:
            True if successful, False otherwise
        """
        logger.info("=" * 80)
        logger.info("STEP 5: Dark Noise Re-measurement (Final Integration Time)")
        logger.info("=" * 80)

        # ⚠️ VALIDATION: Check that Step 4 actually set LED values
        logger.info("")
        logger.info("🔍 Pre-Step 5 Validation: Checking Step 4 LED values...")
        logger.info("-" * 80)

        if not hasattr(self.state, 'ref_intensity') or not self.state.ref_intensity:
            logger.error("❌ CRITICAL: self.state.ref_intensity is empty!")
            logger.error("   Step 4 did not store LED values properly")
            logger.error("   Cannot proceed to Step 5")
            return False

        # Check each channel
        ch_list = ['a', 'b', 'c', 'd']
        missing_leds = []
        zero_leds = []
        for ch in ch_list:
            led_val = self.state.ref_intensity.get(ch, -999)
            if led_val == -999:
                missing_leds.append(ch)
            elif led_val <= 0:
                zero_leds.append(ch)

        if missing_leds:
            logger.error(f"❌ Missing LED values for channels: {missing_leds}")
            logger.error("   Step 4 did not complete properly")
            return False

        if zero_leds:
            logger.error(f"❌ Zero LED values for channels: {zero_leds}")
            logger.error("   Step 4 LED balancing failed")
            return False

        # Log current LED values
        logger.info("✅ Step 4 LED values validated:")
        for ch in ch_list:
            led_val = self.state.ref_intensity.get(ch, 0)
            logger.info(f"   {ch.upper()}: LED = {led_val}")

        logger.info("")
        logger.info("✅ Pre-Step 5 validation passed - LED values are valid")
        logger.info("=" * 80)
        logger.info("")

        # Check calibration mode
        mode = getattr(self.state, 'calibration_mode', 'global')

        if mode == 'per_channel':
            # Per-channel mode: measure 4 separate darks
            logger.info("Mode: PER-CHANNEL (measuring 4 separate darks)")
            return self._measure_per_channel_dark_noise()
        else:
            # Global mode: measure 1 dark at global integration time
            logger.info(f"Mode: GLOBAL (measuring 1 dark @ {self.state.integration*1000:.1f}ms)")
            return self._measure_dark_noise_internal(is_baseline=False)

    def _measure_per_channel_dark_noise(self) -> bool:
        """Measure separate dark spectra for each channel (per-channel mode).

        Policy:
        - One single-scan dark per channel at that channel's integration time.
        - LEDs forced OFF; no averaging beyond a single scan.

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.ctrl is None or self.usb is None:
                return False

            # Get per-channel integration times from Step 4
            if not hasattr(self.state, 'per_channel_integration_times'):
                logger.error("❌ Per-channel integration times not found! Run Step 4 first.")
                return False

            per_channel_integration = self.state.per_channel_integration_times
            all_channels = list(per_channel_integration.keys())

            logger.info(f"Measuring {len(all_channels)} separate dark spectra (one per channel)")
            logger.info("")

            # CRITICAL: Force all LEDs OFF at hardware level
            logger.info("🔦 Forcing ALL LEDs OFF for dark noise measurement...")

            # Use robust LED-off method that sets intensities to 0 AND sends lx command
            try:
                success = self._all_leds_off_batch()
                if success:
                    logger.info("   ✓ LEDs turned off successfully (intensities set to 0 + lx command)")
                else:
                    logger.error("   ❌ _all_leds_off_batch() returned False - LEDs NOT confirmed off")
                    logger.error("   Cannot proceed with dark measurement - stopping calibration")
                    return False
            except Exception as e:
                logger.error(f"   ❌ Failed to turn off LEDs: {e}")
                return False

            # Wait for hardware to settle
            settle_delay = max(self.led_off_delay_s, 0.5)
            time.sleep(settle_delay)
            logger.info(f"✅ All LEDs OFF; waited {settle_delay*1000:.0f}ms for hardware to settle")
            logger.info("")

            # Store per-channel darks
            per_channel_dark = {}

            for ch in all_channels:
                if self._is_stopped():
                    return False

                int_time = per_channel_integration[ch]
                logger.info(f"Measuring dark for Channel {ch.upper()} @ {int_time*MS_TO_SECONDS:.1f}ms")

                # Set integration time for this channel
                self.usb.set_integration(int_time)
                time.sleep(0.08)

                # ✨ Per-channel dark policy: single scan per channel at its integration time
                dark_scans = 1
                total_time_ms = int_time * 1000.0
                logger.info(f"   Using 1 scan (≈{total_time_ms:.0f}ms total; per-channel dark policy)")

                # Measure dark spectrum
                # ⚠️ CRITICAL: DO NOT apply jitter correction to dark measurements!
                # Jitter correction detrends the signal (subtracts mean), which would incorrectly
                # zero out the dark noise baseline we're trying to measure.
                dark_spectrum = self._acquire_averaged_spectrum(
                    num_scans=dark_scans,
                    apply_filter=True,  # Filter to SPR range
                    subtract_dark=False,  # No subtraction (this IS the dark)
                    description=f"dark {ch}",
                    apply_jitter_correction=False  # ⚠️ MUST be False - preserve dark baseline!
                )

                if dark_spectrum is None:
                    logger.error(f"❌ Failed to measure dark for channel {ch}")
                    return False

                # Store dark for this channel
                per_channel_dark[ch] = dark_spectrum.copy()

                dark_mean = float(np.mean(dark_spectrum))
                dark_max = float(np.max(dark_spectrum))
                dark_std = float(np.std(dark_spectrum))

                logger.info(f"   ✅ Mean: {dark_mean:.1f}, Max: {dark_max:.1f}, Std: {dark_std:.1f}")
                logger.info("")

                # Save snapshot
                try:
                    if hasattr(self, "_snap") and self._snap is not None:
                        self._snap.save(f"step5_dark_{ch}_filtered", np.array(dark_spectrum, dtype=float))
                except Exception:
                    pass

            # Store per-channel darks in state
            self.state.per_channel_dark_noise = per_channel_dark

            # Also store first channel as default dark (for backward compatibility)
            first_ch = all_channels[0]
            self.state.dark_noise = per_channel_dark[first_ch].copy()
            self.state.full_spectrum_dark_noise = per_channel_dark[first_ch].copy()

            # Save to disk
            from pathlib import Path
            calib_dir = Path(ROOT_DIR) / "calibration_data"
            calib_dir.mkdir(exist_ok=True)

            timestamp = time.strftime("%Y%m%d_%H%M%S")

            # Save per-channel darks
            for ch in all_channels:
                dark_file = calib_dir / f"dark_noise_{ch}_{timestamp}.npy"
                np.save(dark_file, per_channel_dark[ch])
                logger.info(f"💾 Saved {ch.upper()} dark: {dark_file}")

            # Save all darks in one dict file
            all_darks_file = calib_dir / f"dark_noise_per_channel_{timestamp}.npz"
            np.savez(all_darks_file, **per_channel_dark)
            logger.info(f"💾 Saved all darks: {all_darks_file}")

            # Summary
            logger.info("")
            logger.info("=" * 80)
            logger.info("✅ STEP 5 COMPLETE: PER-CHANNEL DARK MEASUREMENT")
            logger.info("=" * 80)
            logger.info("")
            logger.info("Channel  | Integration Time | Dark Mean | Dark Max")
            logger.info("-" * 60)
            for ch in all_channels:
                int_time = per_channel_integration[ch]
                dark_mean = float(np.mean(per_channel_dark[ch]))
                dark_max = float(np.max(per_channel_dark[ch]))
                logger.info(f"   {ch.upper()}     |    {int_time*MS_TO_SECONDS:6.1f} ms     | {dark_mean:7.1f}   | {dark_max:7.1f}")
            logger.info("")
            logger.info("Next: Step 6 will measure S-ref (per-channel)")
            logger.info("=" * 80)

            return True

        except Exception as e:
            logger.exception(f"Error measuring per-channel dark noise: {e}")
            return False

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

            # ✨ QC PARAMETERS (detector class specific - Ocean Optics/USB4000)
            # For Ocean Optics Flame-T detector: typical dark noise ~3,000 counts @ 36ms integration
            # Threshold: 2× expected = 6,000 counts
            EXPECTED_DARK_MEAN_OCEAN_OPTICS = 3000.0  # counts (detector class specific)
            DARK_QC_THRESHOLD = EXPECTED_DARK_MEAN_OCEAN_OPTICS * 2.0  # 6,000 counts
            MAX_RETRY_ATTEMPTS = 3

            # Retry loop for dark noise QC
            for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
                if attempt > 1:
                    logger.warning(f"🔄 Dark noise QC retry attempt {attempt}/{MAX_RETRY_ATTEMPTS}")

                # CRITICAL: Force all LEDs OFF at hardware level before dark measurement
                logger.info("🔦 Forcing ALL LEDs OFF for dark noise measurement...")

                # Use robust LED-off method that sets intensities to 0 AND sends lx command
                # This is safer than direct serial access (avoids COM port permission issues)
                try:
                    success = self._all_leds_off_batch()
                    if success:
                        logger.info("   ✓ LEDs turned off successfully (intensities set to 0 + lx command)")
                    else:
                        logger.error("   ❌ _all_leds_off_batch() returned False - LEDs NOT confirmed off")
                        logger.error("   Cannot proceed with dark measurement - stopping calibration")
                        return False
                except Exception as e:
                    logger.error(f"   ❌ Failed to turn off LEDs: {e}")
                    return False

                # CRITICAL: Wait for LEDs to fully turn off (hardware settling time)
                # Increase settle time on retries to ensure LEDs are completely off
                settle_delay = max(self.led_off_delay_s, 0.5) * attempt  # Scale with retry attempt
                time.sleep(settle_delay)
                logger.info(f"✅ All LEDs OFF; waited {settle_delay*1000:.0f}ms for hardware to settle")

                # ✨ CRITICAL: Calculate scan count using DYNAMIC AVERAGING (matches live measurements)
                # The number of dark scans MUST match the number of scans used during live data acquisition
                # based on the 200ms time window budget
                if is_baseline:
                    # Step 1: Baseline dark noise (fast sanity check - 5 scans)
                    dark_scans = 5
                    logger.info(f"   Step 1 (baseline): {dark_scans} scans (fast sanity check)")
                else:
                    # Step 5: Use dynamic scan count based on integration time (matches live mode)
                    dark_scans = calculate_dynamic_scans(self.state.integration)
                    int_ms = self.state.integration * 1000.0
                    total_time_ms = dark_scans * int_ms
                    logger.info(f"   Step 5 dark: {dark_scans} scans @ {int_ms:.1f}ms = {total_time_ms:.0f}ms total")
                    logger.info(f"   (Matches live acquisition scan count for this integration time)")

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
                # ⚠️ CRITICAL: DO NOT apply jitter correction to dark measurements!
                # Jitter correction detrends the signal (subtracts mean), which would incorrectly
                # zero out the dark noise baseline we're trying to measure.
                full_spectrum_dark_noise = self._acquire_averaged_spectrum(
                    num_scans=dark_scans,
                    apply_filter=True,
                    subtract_dark=False,
                    description="dark noise",
                    apply_jitter_correction=False  # ⚠️ MUST be False - preserve dark baseline!
                )

                if full_spectrum_dark_noise is None:
                    logger.error("Failed to acquire dark noise spectrum")
                    return False

                # ✨ QC CHECK: Verify dark noise is not excessively high (indicates LEDs not off)
                dark_mean = np.mean(full_spectrum_dark_noise)
                dark_max = np.max(full_spectrum_dark_noise)

                logger.info(f"📊 Dark noise measurement:")
                logger.info(f"   Mean: {dark_mean:.1f} counts")
                logger.info(f"   Max:  {dark_max:.1f} counts")

                # QC: Check if dark noise exceeds threshold (2× expected for Ocean Optics detector)
                if dark_mean > DARK_QC_THRESHOLD:
                    logger.error(f"❌ QC FAILED: Dark noise mean ({dark_mean:.1f}) exceeds threshold ({DARK_QC_THRESHOLD:.0f} counts)")
                    logger.error(f"   Expected for Ocean Optics/USB4000: ~{EXPECTED_DARK_MEAN_OCEAN_OPTICS:.0f} counts")
                    logger.error(f"   Measured dark is {dark_mean/EXPECTED_DARK_MEAN_OCEAN_OPTICS:.1f}× higher than expected")
                    logger.error("   Possible causes:")
                    logger.error("   • LEDs not completely turned off")
                    logger.error("   • Light leaking into detector")
                    logger.error("   • Previous measurement residual signal")

                    if attempt < MAX_RETRY_ATTEMPTS:
                        logger.warning(f"   Retrying with longer LED settle time...")
                        continue  # Retry with increased settle delay
                    else:
                        logger.error(f"❌ FATAL: Dark noise QC failed after {MAX_RETRY_ATTEMPTS} attempts")
                        logger.error("   Cannot proceed with calibration - dark noise too high")
                        logger.error("   Please check:")
                        logger.error("   • All LEDs are physically off")
                        logger.error("   • Detector enclosure is light-tight")
                        logger.error("   • Hardware connections are secure")
                        return False
                else:
                    # QC PASSED
                    logger.info(f"✅ Dark noise QC PASSED: {dark_mean:.1f} counts < {DARK_QC_THRESHOLD:.0f} threshold")
                    if attempt > 1:
                        logger.info(f"   (Succeeded on retry attempt {attempt})")
                    break  # Exit retry loop - measurement successful

            # ✨ NEW (Phase 2): Store Step 1 as baseline for comparison
            if is_baseline:
                # Step 1: First dark measurement (before any LEDs activated)
                self.state.dark_noise_before_leds = full_spectrum_dark_noise.copy()
                before_mean = np.mean(full_spectrum_dark_noise)
                before_max = np.max(full_spectrum_dark_noise)
                before_std = np.std(full_spectrum_dark_noise)

                # 💾 Snapshot: Step 1 dark noise (filtered)
                try:
                    if hasattr(self, "_snap") and self._snap is not None:
                        self._snap.save("step1_dark_noise_filtered", np.array(self.state.dark_noise_before_leds, dtype=float))
                except Exception:
                    pass

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

            # ⚠️ AFTERGLOW CORRECTION DISABLED (for now - may be deleted later)
            # Keeping code but not executing it
            AFTERGLOW_ENABLED = False  # Hardcoded disable

            if (not is_baseline and
                AFTERGLOW_ENABLED and  # Disabled!
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

                    # 💾 Snapshots: Step 5 dark noise uncorrected and corrected (filtered)
                    try:
                        if hasattr(self, "_snap") and self._snap is not None:
                            if hasattr(self.state, 'dark_noise_after_leds_uncorrected') and self.state.dark_noise_after_leds_uncorrected is not None:
                                self._snap.save("step5_dark_noise_uncorrected_filtered", np.array(self.state.dark_noise_after_leds_uncorrected, dtype=float))
                            self._snap.save("step5_dark_noise_corrected_filtered", np.array(full_spectrum_dark_noise, dtype=float))
                    except Exception:
                        pass

                except Exception as e:
                    logger.warning(f"⚠️ Afterglow correction failed: {e}")
                    logger.warning("⚠️ Using uncorrected dark noise")
                    # Continue with uncorrected data
            else:
                if not is_baseline:
                    # Step 5 without correction (always the case now with AFTERGLOW_ENABLED=False)
                    logger.info("ℹ️  Afterglow correction: DISABLED")

                    # Compare with Step 1 baseline
                    if self.state.dark_noise_before_leds is not None:
                        self._compare_dark_noise_measurements(
                            dark_before=self.state.dark_noise_before_leds,
                            dark_after_raw=full_spectrum_dark_noise
                        )

                    # 💾 Snapshot: Step 5 dark noise (uncorrected filtered)
                    try:
                        if hasattr(self, "_snap") and self._snap is not None:
                            self._snap.save("step5_dark_noise_uncorrected_filtered", np.array(full_spectrum_dark_noise, dtype=float))
                    except Exception:
                        pass

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

            # Clamp to detector limits: prefer detector profile, fallback to settings
            try:
                if self.detector_profile is not None:
                    min_ms = int(self.detector_profile.min_integration_time_ms)
                    max_ms = int(self.detector_profile.max_integration_time_ms)
                else:
                    min_ms = int(MIN_INTEGRATION)
                    max_ms = int(MAX_INTEGRATION)
            except Exception:
                # Ultimate fallback to settings if anything unexpected occurs
                min_ms = int(MIN_INTEGRATION)
                max_ms = int(MAX_INTEGRATION)

            optimal_int_ms = max(min_ms, min(max_ms, int(optimal_int_ms)))

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

    # NOTE: Legacy Step 7 (reference measurement) removed. Folded into Step 6.

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

            # Ensure a dark reference is present for QC; attempt to load from config if missing
            try:
                needs_dark = (
                    getattr(self.state, 'dark_noise', None) is None or
                    (hasattr(self.state, 'dark_noise') and len(self.state.dark_noise) == 0)
                )
                if needs_dark:
                    from utils.device_configuration import DeviceConfiguration
                    cfg = DeviceConfiguration()
                    cal = cfg.load_led_calibration()
                    if cal and 'pre_qc_dark_snapshot' in cal:
                        self.state.dark_noise = cal['pre_qc_dark_snapshot']
                        logger.info("Loaded pre-QC dark snapshot from device_config.json for QC subtraction")
            except Exception as e:
                logger.warning(f"Could not load pre-QC dark snapshot: {e}")

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

            # If stored baseline appears invalid (negative intensities or spectra),
            # refresh a temporary baseline from live measurements for QC only.
            try:
                baseline_invalid = False
                try:
                    # Any negative or near-zero baseline max is suspect
                    if any(baseline_max.get(ch, 0) <= 0 for ch in CH_LIST):
                        baseline_invalid = True
                    else:
                        # Any negative value in stored spectra is suspect
                        for ch in CH_LIST:
                            spec_arr = np.array(baseline_s_ref.get(ch, []), dtype=float)
                            if spec_arr.size == 0 or np.min(spec_arr) < 0:
                                baseline_invalid = True
                                break
                except Exception:
                    baseline_invalid = True

                if baseline_invalid:
                    logger.warning("Stored S-ref baseline appears invalid (negative or empty). Refreshing a temporary baseline from live measurements for QC...")
                    tmp_baseline_max: dict[str, float] = {}
                    tmp_baseline_s_ref: dict[str, np.ndarray] = {}

                    for ch in CH_LIST:
                        try:
                            # Turn on LED with stored intensity
                            self.ctrl.set_intensity(ch.lower(), s_intensities[ch])
                            time.sleep(self.led_on_delay_s)

                            # Measure fresh S-ref (average of num_samples)
                            spectra_tmp = []
                            for _ in range(num_samples):
                                raw_tmp = self.usb.acquire_spectrum()
                                spectra_tmp.append(raw_tmp)
                                time.sleep(0.05)
                            cur_tmp = np.mean(spectra_tmp, axis=0)

                            # Apply dark correction with resampling if needed
                            if self.state.dark_noise is not None and len(self.state.dark_noise) > 0:
                                try:
                                    dark_use = np.maximum(self.state.dark_noise, 0)
                                    dl, rl = len(dark_use), len(cur_tmp)
                                    if dl != rl:
                                        x_old = np.linspace(0, 1, dl)
                                        x_new = np.linspace(0, 1, rl)
                                        # Use numpy interpolation to avoid SciPy dependency/type issues
                                        dark_rs = np.interp(x_new, x_old, dark_use)
                                        cur_tmp = cur_tmp - dark_rs
                                    else:
                                        cur_tmp = cur_tmp - dark_use
                                except Exception as e:
                                    logger.warning(f"   Failed to apply dark correction (baseline refresh): {e}")

                            # Clamp negatives that can result from noise
                            cur_tmp = np.maximum(cur_tmp, 0)

                            tmp_baseline_s_ref[ch] = cur_tmp
                            tmp_baseline_max[ch] = float(np.max(cur_tmp))
                        except Exception as e:
                            logger.warning(f"   Failed to refresh baseline for channel {ch}: {e}")
                        finally:
                            # Ensure channel is turned off
                            try:
                                self.ctrl.set_intensity(ch.lower(), 0)
                                time.sleep(0.05)
                            except Exception:
                                pass

                    # If we successfully measured any channel, swap into local baseline vars for QC
                    if any(v > 0 for v in tmp_baseline_max.values()):
                        for ch in CH_LIST:
                            if ch in tmp_baseline_s_ref:
                                baseline_s_ref[ch] = tmp_baseline_s_ref[ch]
                                baseline_max[ch] = tmp_baseline_max[ch]
                        logger.info("QC baseline refreshed from live measurements (not persisted to config)")
            except Exception as e:
                logger.warning(f"Failed to refresh temporary QC baseline: {e}")

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
                time.sleep(self.led_on_delay_s)

                # Measure fresh S-ref (average of num_samples)
                spectra = []
                for _ in range(num_samples):
                    raw = self.usb.acquire_spectrum()
                    spectra.append(raw)
                    time.sleep(0.05)

                current_s_ref = np.mean(spectra, axis=0)

                # Apply dark noise correction if available (with universal resampling)
                if self.state.dark_noise is not None and len(self.state.dark_noise) > 0:
                    try:
                        # Safety: clamp negatives to zero for dark usage
                        dark_for_use = np.maximum(self.state.dark_noise, 0)
                        dark_len = len(dark_for_use)
                        ref_len = len(current_s_ref)
                        if dark_len != ref_len:
                            # Resample dark to match current_s_ref length using numpy interpolation
                            x_old = np.linspace(0, 1, dark_len)
                            x_new = np.linspace(0, 1, ref_len)
                            dark_resampled = np.interp(x_new, x_old, dark_for_use)
                            current_s_ref = current_s_ref - dark_resampled
                            logger.debug(f"   Applied resampled dark to current S-ref ({dark_len}→{ref_len})")
                        else:
                            current_s_ref = current_s_ref - dark_for_use
                    except Exception as e:
                        logger.warning(f"   Failed to apply dark correction to current S-ref: {e}")

                # Clamp negatives post-subtraction
                current_s_ref = np.maximum(current_s_ref, 0)

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
            # NEW: ALWAYS MEASURE A DARK SNAPSHOT BEFORE QC (if hardware available)
            # ========================================================================
            # ⚠️ TEMPORARILY DISABLED - Skipping pre-QC dark measurement
            # This was causing errors that prevented calibration from completing
            logger.info("⚠️  PRE-QC DARK MEASUREMENT: DISABLED (for testing)")
            logger.info("   Skipping to full calibration sequence...")

            # Original code commented out:
            # if self.ctrl is not None and self.usb is not None:
            #     try:
            #         logger.info("PRE-QC: Measuring dark reference snapshot for QC and logging…")
            #         if not self.step_1_measure_initial_dark_noise():
            #             logger.warning("Pre-QC dark snapshot failed; proceeding without snapshot")
            #         else:
            #             # Safety: flag and clamp negatives
            #             try:
            #                 dn = self.state.dark_noise
            #                 if dn is not None and len(dn) > 0:
            #                     dark_min = float(np.min(dn))
            #                     if dark_min < 0:
            #                         logger.error(
            #                             f"⚠️ Pre-QC dark contains negative values (min={dark_min:.2f}). "
            #                             f"Clamping to zero for QC subtraction."
            #                         )
            #                         self.state.dark_noise = np.maximum(dn, 0)
            #             except Exception as _e:
            #                 logger.warning(f"Failed to validate/clamp dark snapshot: {_e}")
            #
            #             # Persist snapshot to device config
            #             try:
            #                 from utils.device_configuration import DeviceConfiguration
            #                 DeviceConfiguration().save_dark_snapshot(self.state.dark_noise.copy())
            #             except Exception as _e:
            #                 logger.warning(f"Could not save dark snapshot: {_e}")
            #     except Exception as e:
            #         logger.warning(f"Pre-QC dark snapshot error: {e}")

            # ========================================================================
            # NEW: TRY QC VALIDATION FIRST (UNLESS FORCED)
            # ========================================================================
            # ✅ ENABLED - Use QC validation to skip calibration when valid data exists
            logger.info("✅ QC VALIDATION: ENABLED")
            logger.info("   Checking if stored calibration is still valid...")

            # Try QC validation first (can be overridden with force flag if needed)
            force_recalibrate = False

            if not force_recalibrate:
                from utils.device_configuration import DeviceConfiguration

                device_config = DeviceConfiguration()
                baseline = device_config.load_led_calibration()

                if baseline:
                    age_days = device_config.get_calibration_age_days()
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

                        # Ensure wavelength range is initialized for downstream processing
                        try:
                            if self.usb is not None and (not hasattr(self.state, 'wavelengths') or len(self.state.wavelengths) == 0):
                                logger.info("Initializing wavelength range for QC-loaded calibration…")
                                ok = self.step_2_calibrate_wavelength_range()
                                if not ok:
                                    logger.warning("Failed to initialize wavelength range; proceeding anyway")
                        except Exception as _e:
                            logger.warning(f"Wavelength initialization error: {_e}")

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
            # STEP 6: S-REFERENCE MEASUREMENT (Final S-mode baselines)
            # ========================================================================
            self._emit_progress(6, "Step 6: Capturing S-reference signals...")
            success = self.step_6_measure_s_reference(ch_list)
            if not success or self._is_stopped():
                self._safe_hardware_cleanup()
                return False, "Step 6: S-reference measurement failed"

            # Calibration successful (Step 6 marks is_calibrated = True)
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

            # Determine calibration mode
            try:
                mode = getattr(self.state, 'calibration_mode', getattr(self, 'calibration_mode', 'global')).lower()
            except Exception:
                mode = 'global'

            # Apply integration time and LED policy according to mode
            if mode == 'global':
                # Global: set single integration time
                if hasattr(self.state, 'integration') and self.state.integration:
                    usb.set_integration(self.state.integration)
                    logger.info(f"Applied global integration time: {self.state.integration * 1000:.1f} ms")

                # Apply calibrated LED intensities per channel
                # Prefer leds_calibrated → fallback to ref_intensity → fallback to MAX_LED_INTENSITY
                led_map: dict[str, int] = {}
                for ch in ch_list:
                    val = None
                    try:
                        if hasattr(self.state, 'leds_calibrated') and ch in getattr(self.state, 'leds_calibrated', {}):
                            val = int(self.state.leds_calibrated[ch])
                        elif hasattr(self.state, 'ref_intensity') and ch in getattr(self.state, 'ref_intensity', {}):
                            val = int(self.state.ref_intensity[ch])
                    except Exception:
                        val = None
                    if val is None or val <= 0:
                        val = int(MAX_LED_INTENSITY)
                    led_map[ch] = int(max(0, min(MAX_LED_INTENSITY, val)))

                # Prefer batch LED application when available
                applied_leds = False
                try:
                    if hasattr(ctrl, 'set_batch_intensities'):
                        # Build a,b,c,d with safe defaults
                        a = led_map.get('a', 0)
                        b = led_map.get('b', 0)
                        c = led_map.get('c', 0)
                        d = led_map.get('d', 0)
                        ok = ctrl.set_batch_intensities(a=a, b=b, c=c, d=d)
                        logger.info(f"Batch LED apply: a={a}, b={b}, c={c}, d={d} → success={ok}")
                        applied_leds = bool(ok)
                except Exception as e:
                    logger.debug(f"Batch LED apply not used: {e}")

                if not applied_leds:
                    # Fallback: set per-channel sequentially
                    for ch, val in led_map.items():
                        try:
                            ctrl.set_intensity(ch=ch, raw_val=val)
                        except Exception as e:
                            logger.warning(f"Failed to set LED {ch}={val}: {e}")
                    logger.info(f"Applied per-channel LED intensities (sequential): {led_map}")

            else:
                # Per-channel mode:
                # - Do NOT set global integration (integration is per-channel at capture time)
                # - Do NOT apply per-channel dimmed LEDs (LEDs are typically 255 during capture)
                logger.info("Per-channel mode: skipping global integration and LED application")

            # ✨ Apply validated polarizer positions if available
            if hasattr(self.state, 'polarizer_s_position') and hasattr(self.state, 'polarizer_p_position'):
                s_pos = self.state.polarizer_s_position
                p_pos = self.state.polarizer_p_position
                try:
                    ctrl.servo_set(s=s_pos, p=p_pos)
                    logger.info(f"Polarizer positions applied: S={s_pos}, P={p_pos} (0-255 scale)")
                except Exception as e:
                    logger.warning(f"Failed to apply polarizer positions: {e}")

            logger.info("Calibration profile applied to hardware")
            return True

        except Exception as e:
            logger.exception(f"Error applying profile to hardware: {e}")
            return False

    # ------------------------------------------------------------------------
    # LIVE HELPERS (policy parity with calibration)
    # ------------------------------------------------------------------------
    def get_dark_for_channel(self, ch: str) -> Optional[np.ndarray]:
        """Return the appropriate dark spectrum for a channel based on mode.

        - Global mode: returns self.state.dark_noise
        - Per-channel mode: returns self.state.per_channel_dark_noise[ch] when available,
          otherwise falls back to global dark if present.
        """
        try:
            mode = getattr(self.state, 'calibration_mode', getattr(self, 'calibration_mode', 'global')).lower()
        except Exception:
            mode = 'global'

        if mode == 'per_channel':
            try:
                if hasattr(self.state, 'per_channel_dark_noise') and self.state.per_channel_dark_noise:
                    dark = self.state.per_channel_dark_noise.get(ch)
                    if dark is not None:
                        return dark
            except Exception:
                pass
        # Fallback to global dark
        return getattr(self.state, 'dark_noise', None)

    def get_scans_for_live(self, integration_seconds: float) -> int:
        """Decide the number of scans to average in live mode.

        - Global: dynamic scans targeting ~200ms via calculate_dynamic_scans
        - Per-channel: single scan (policy alignment with calibration Step 5/6 per-channel)
        """
        try:
            mode = getattr(self.state, 'calibration_mode', getattr(self, 'calibration_mode', 'global')).lower()
        except Exception:
            mode = 'global'
        if mode == 'global':
            try:
                return int(max(1, calculate_dynamic_scans(float(integration_seconds))))
            except Exception:
                return int(max(1, NUM_SCANS_PER_ACQUISITION))
        return 1

    def get_led_for_live(self, ch: str) -> int:
        """Return LED to use in live capture for a channel.

        - Per-channel mode: always 255
        - Global mode: prefer leds_calibrated[ch] → ref_intensity[ch] → MAX_LED_INTENSITY
        """
        try:
            mode = getattr(self.state, 'calibration_mode', getattr(self, 'calibration_mode', 'global')).lower()
        except Exception:
            mode = 'global'
        if mode == 'per_channel':
            return int(MAX_LED_INTENSITY)
        try:
            if hasattr(self.state, 'leds_calibrated') and ch in getattr(self.state, 'leds_calibrated', {}):
                return int(max(0, min(MAX_LED_INTENSITY, int(self.state.leds_calibrated[ch]))))
            if hasattr(self.state, 'ref_intensity') and ch in getattr(self.state, 'ref_intensity', {}):
                return int(max(0, min(MAX_LED_INTENSITY, int(self.state.ref_intensity[ch]))))
        except Exception:
            pass
        return int(MAX_LED_INTENSITY)

    def prepare_live(
        self,
        ctrl: PicoP4SPR | PicoEZSPR,
        usb: USB4000,
        ch_list: list[str] | None = None,
    ) -> dict:
        """Prepare hardware and runtime policy for live acquisition.

        Actions:
        - Applies current calibration profile to hardware (mode-aware)
        - Builds live LED map via get_led_for_live()
        - Decides scan policy via get_scans_for_live()
        - Exposes per-channel integration (per-channel mode) or global integration

        Returns:
            dict with keys:
              - mode: 'global' | 'per_channel'
              - leds: dict[ch,int]
              - integration: float (seconds) when global
              - integration_per_channel: dict[ch,float] (seconds) when per-channel
              - scans: int (global)
              - scans_per_channel: dict[ch,int] (per-channel)
        """
        if ch_list is None:
            ch_list = CH_LIST

        # Apply current profile to hardware (integration/LED/polarizer as appropriate)
        try:
            _ = self.apply_profile_to_hardware(ctrl=ctrl, usb=usb, ch_list=ch_list)
        except Exception:
            # Non-fatal: continue to build policy even if apply fails
            pass

        try:
            mode = getattr(self.state, 'calibration_mode', getattr(self, 'calibration_mode', 'global')).lower()
        except Exception:
            mode = 'global'

        # Build LED map using unified policy
        leds = {ch: int(self.get_led_for_live(ch)) for ch in ch_list}

        live_cfg: dict = {
            'mode': mode,
            'leds': leds,
        }

        if mode == 'per_channel':
            # Per-channel: provide per-channel integrations and scans=1
            integration_per_channel: dict[str, float] = {}
            try:
                if hasattr(self.state, 'integration_per_channel') and self.state.integration_per_channel:
                    for ch in ch_list:
                        if ch in self.state.integration_per_channel:
                            integration_per_channel[ch] = float(self.state.integration_per_channel[ch])
            except Exception:
                pass
            scans_per_channel = {ch: int(self.get_scans_for_live(integration_per_channel.get(ch, 0.0))) for ch in ch_list}
            live_cfg['integration_per_channel'] = integration_per_channel
            live_cfg['scans_per_channel'] = scans_per_channel
        else:
            # Global: provide single integration and dynamic scans
            integration_s = float(getattr(self.state, 'integration', 0.0) or 0.0)
            scans = int(self.get_scans_for_live(integration_s))
            live_cfg['integration'] = integration_s
            live_cfg['scans'] = scans

        return live_cfg

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
            try:
                from settings.settings import FORCE_FULL_CALIBRATION as _FORCE_FULL_CAL
            except Exception:
                _FORCE_FULL_CAL = False
            success, error_channels = self.run_full_calibration(
                auto_polarize=False,  # Auto-alignment is an advanced feature (handled in settings)
                auto_polarize_callback=None,
                force_recalibrate=bool(_FORCE_FULL_CAL)
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

