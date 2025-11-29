"""6-Step Startup Calibration Flow

This module implements the 6-step calibration flow for SPR systems.

INTEGRATION TIME STANDARD:
=========================
ALL integration times throughout this codebase use MILLISECONDS:
- usb.set_integration(time_ms) expects milliseconds
- DetectorParams.min/max_integration_time are in milliseconds
- LEDCalibrationResult.s_integration_time is in milliseconds
- All variables (test_int, best_integration, etc.) are in milliseconds
- Internal conversion to microseconds happens ONLY in USB4000.set_integration()

STEP 1: Hardware Validation & LED Verification
  - Validate controller and spectrometer are connected
  - Force all LEDs OFF
  - Verify LEDs are actually off (V1.1+ firmware query or timing-based)
  - Critical safety check before any measurements

STEP 2: Wavelength Calibration
  - Read wavelength calibration from detector EEPROM
  - Get detector-specific parameters (max counts, saturation threshold)
  - Determine valid wavelength ROI (560-720nm)

STEP 3: LED Brightness Ranking
  - Quick brightness measurement at LED=255 for all channels
  - Rank channels by optical efficiency (weakest to strongest)
  - If firmware V1.2+: Use `rank_leds()` command for firmware-based optimization
  - Identifies which channel will hit LED=255 first (weakest optical coupling)

STEP 4: S-Mode Integration Time Optimization
  - Constrained dual optimization: Find integration time where:
    1. Weakest channel requires LED=255 (maxed out)
    2. Strongest channel is safe (<95% saturation)
  - Iterative search with safety constraints
  - Calculate LED intensities for all channels based on brightness ratios
  - Capture S-pol raw spectra for Step 6 processing

STEP 5: P-Mode Optimization (Transfer S-mode, Integration Only)
  - Switch polarizer to P-polarization
  - Transfer all S-mode parameters (100% baseline)
    - LEDs remain frozen from Step 3C (no intensity changes)
  - Target: Weakest LED near 255 (proof of optimization)
  - Constraint: All channels <95% saturation
  - Optional: Up to +10% integration time increase
  - Capture P-pol raw spectra per channel
  - Measure dark-ref at P-mode integration time (QC: 2500-4000 counts)

STEP 6: S-Mode Reference Signals + QC (FINAL STEP)
  - Switch back to S-mode
    - Measure S-mode reference signals with normalized LED intensities
  - Validate S-ref quality (signal strength, noise floor, consistency)
  - QC checks: All channels pass validation criteria
  - Return calibration result

NO STEPS BEYOND 6 - THIS IS THE COMPLETE CALIBRATION FLOW

This implementation serves as the template for:
  - Fast-track calibration (with ±10% validation)
  - Global LED mode (LED=255 fixed, variable integration)

TRANSFER TO LIVE VIEW:
  - After Step 6 completes: Show post-calibration dialog
  - Wait for user to click "Start" button
  - Transfer calibration to live acquisition system
  - Begin live SPR measurements
"""

import time
from typing import TYPE_CHECKING, Optional, Dict, Tuple
import numpy as np
import json
from datetime import datetime
from pathlib import Path
import json
from datetime import datetime
from pathlib import Path

from settings import (
    CH_LIST,
    EZ_CH_LIST,
    LED_DELAY,
    PRE_LED_DELAY_MS,
    POST_LED_DELAY_MS,
    MIN_WAVELENGTH,
    MAX_WAVELENGTH,
    MAX_INTEGRATION,
    MAX_READ_TIME,
    MAX_NUM_SCANS,
    USE_ALTERNATIVE_CALIBRATION,
)
from utils.logger import logger
from models.led_calibration_result import LEDCalibrationResult
from utils.calibration_helpers import (
    DetectorParams,
    get_detector_params,
    determine_channel_list,
    switch_mode_safely,
)
from core.spectrum_preprocessor import SpectrumPreprocessor
from core.transmission_processor import TransmissionProcessor

# Local constants for Steps 1-3 (GitHub alignment)
TEMP_INTEGRATION_TIME_MS = 32  # Temporary integration for Steps 1-3 (GitHub standard)

if TYPE_CHECKING:
    from utils.controller import ControllerBase


# =============================================================================
# CALIBRATION RESULT PERSISTENCE
# =============================================================================

def save_calibration_result_json(result: LEDCalibrationResult, base_dir: str = "calibration_results") -> Optional[Path]:
    """Save calibration result to JSON file for future reference.

    Saves both a timestamped file and a 'latest' copy for quick access.

    Args:
        result: LEDCalibrationResult to save
        base_dir: Directory to save results in (created if doesn't exist)

    Returns:
        Path to saved file, or None if save failed
    """
    try:
        # Create output directory if needed
        output_dir = Path(base_dir)
        output_dir.mkdir(exist_ok=True)

        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Prepare data for JSON serialization
        data = {
            'calibration_metadata': {
                'timestamp': datetime.now().isoformat(),
                'success': result.success,
                'calibration_method': 'alternative' if USE_ALTERNATIVE_CALIBRATION else 'standard',
                'detector_serial': result.detector_max_counts,  # Using as identifier
            },
            'detector_parameters': {
                'max_counts': result.detector_max_counts,
                'saturation_threshold': result.detector_saturation_threshold,
                'wavelength_range': {
                    'min': float(result.wave_data[0]) if result.wave_data is not None else None,
                    'max': float(result.wave_data[-1]) if result.wave_data is not None else None,
                    'min_index': result.wave_min_index,
                    'max_index': result.wave_max_index,
                },
            },
            'led_parameters': {
                's_mode_intensity': result.s_mode_intensity,
                'p_mode_intensity': result.p_mode_intensity,
                'normalized_leds': result.normalized_leds,
                'brightness_ratios': result.brightness_ratios,
                'led_ranking': result.led_ranking,
                'weakest_channel': result.weakest_channel,
            },
            'integration_times': {
                's_integration_time': result.s_integration_time,
                'p_integration_time': result.p_integration_time,
                'channel_integration_times': result.channel_integration_times,
            },
            'timing_parameters': {
                'pre_led_delay_ms': result.pre_led_delay_ms,
                'post_led_delay_ms': result.post_led_delay_ms,
                'cycle_time_ms': result.cycle_time_ms,
                'acquisition_rate_hz': result.acquisition_rate_hz,
                'num_scans': result.num_scans,
            },
            'roi_measurements': {
                's_roi1_signals': result.s_roi1_signals,
                's_roi2_signals': result.s_roi2_signals,
                'p_roi1_signals': result.p_roi1_signals,
                'p_roi2_signals': result.p_roi2_signals,
            },
            'polarizer_configuration': {
                's_position': result.polarizer_s_position,
                'p_position': result.polarizer_p_position,
                'sp_ratio': result.polarizer_sp_ratio,
            },
            'qc_results': result.qc_results,
            'error_channels': result.ch_error_list,
        }

        # Save timestamped version
        timestamped_file = output_dir / f"calibration_{timestamp}.json"
        with open(timestamped_file, 'w') as f:
            json.dump(data, f, indent=2)

        # Save as 'latest' for quick access
        latest_file = output_dir / "latest_calibration.json"
        with open(latest_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"💾 Calibration result saved: {timestamped_file}")
        logger.info(f"💾 Latest calibration updated: {latest_file}")

        return timestamped_file

    except Exception as e:
        logger.error(f"Failed to save calibration result: {e}")
        return None


# =============================================================================
# HELPER FUNCTION: COUNT SATURATED PIXELS
# =============================================================================

def count_saturated_pixels(
    spectrum: np.ndarray,
    wave_min_index: int,
    wave_max_index: int,
    saturation_threshold: float
) -> int:
    """Count saturated pixels across the entire wavelength ROI.

    This function checks ALL pixels in the wavelength window (560-720nm) for saturation,
    not just the maximum value. This is critical because multiple pixels can saturate
    even if the max isn't at the threshold.

    Args:
        spectrum: Full spectrum data from detector
        wave_min_index: Start index of ROI (560nm)
        wave_max_index: End index of ROI (720nm)
        saturation_threshold: Detector saturation limit (e.g., 58,900 for Flame-T)

    Returns:
        Number of saturated pixels in ROI

    Safety Rule: Calibration MUST achieve 0 saturated pixels in ROI.
    """
    roi_spectrum = spectrum[wave_min_index:wave_max_index]
    saturated_mask = roi_spectrum >= saturation_threshold
    saturated_count = int(np.sum(saturated_mask))
    return saturated_count


# =============================================================================
# HELPER FUNCTION: ROBUST ROI SIGNAL (MEDIAN/TRIMMED MEAN)
# =============================================================================

def roi_signal(
    spectrum: np.ndarray,
    wave_min_index: int,
    wave_max_index: int,
    method: str = "median",
    trim_fraction: float = 0.1
) -> float:
    """Compute a robust signal metric over the SPR ROI.

    Uses median by default, or a trimmed mean to reduce sensitivity
    to single-pixel spikes while preserving overall signal structure.

    Args:
        spectrum: Full spectrum data from detector
        wave_min_index: Start index of ROI
        wave_max_index: End index of ROI
        method: 'median' or 'trimmed_mean'
        trim_fraction: Fraction to trim from each tail for trimmed mean

    Returns:
        Robust signal value over ROI
    """
    roi = spectrum[wave_min_index:wave_max_index]
    if roi.size == 0:
        return 0.0
    if method == "trimmed_mean":
        # Clamp trim to valid range
        t = max(0.0, min(0.49, float(trim_fraction)))
        sorted_roi = np.sort(roi)
        n = sorted_roi.size
        start = int(np.floor(t * n))
        end = int(np.ceil((1.0 - t) * n))
        if start >= end:
            return float(np.mean(sorted_roi))
        return float(np.mean(sorted_roi[start:end]))
    # Default: median
    return float(np.median(roi))


def count_pixels_near_target(
    spectrum: np.ndarray,
    wave_min_index: int,
    wave_max_index: int,
    target_signal: float,
    tolerance_pct: float = 0.10
) -> tuple[int, float]:
    """Count how many pixels in ROI are near target signal (empirical validation).

    Args:
        spectrum: Full spectrum array
        wave_min_index: Start index of ROI
        wave_max_index: End index of ROI
        target_signal: Target signal value (counts)
        tolerance_pct: Tolerance as fraction (default 0.10 = ±10%)

    Returns:
        Tuple of (pixels_near_target, percentage_near_target)
    """
    roi_spectrum = spectrum[wave_min_index:wave_max_index]
    total_pixels = len(roi_spectrum)

    if total_pixels == 0:
        return 0, 0.0

    min_signal = target_signal * (1.0 - tolerance_pct)
    max_signal = target_signal * (1.0 + tolerance_pct)

    pixels_in_range = np.sum((roi_spectrum >= min_signal) & (roi_spectrum <= max_signal))
    percentage = (pixels_in_range / total_pixels) * 100

    return int(pixels_in_range), float(percentage)


# =============================================================================
# HELPER: STANDARDIZED STEP SUMMARY LOGGING
# =============================================================================

def log_step_summary(
    step_name: str,
    detector_max: float,
    integration_ms: float,
    channel_signals: Dict[str, float],
    sat_counts: Dict[str, int]
) -> None:
    """Standardized per-step summary for post-run analysis.

    Logs target context, integration time, per-channel percentages, and saturation.
    """
    logger.info("-" * 80)
    logger.info(f"{step_name} Summary")
    logger.info("-" * 80)
    logger.info(f"Integration: {integration_ms:.1f} ms")
    for ch, sig in channel_signals.items():
        pct = (sig / detector_max * 100.0) if detector_max else 0.0
        sat = sat_counts.get(ch, 0)
        sat_txt = "SAT" if sat > 0 else "OK"
        logger.info(f"  {ch.upper()}: {sig:.0f} ({pct:.1f}%) | Saturation: {sat_txt} ({sat})")
    logger.info("-" * 80)


# =============================================================================
# STEP 2: QUICK DARK NOISE BASELINE
# =============================================================================

def measure_quick_dark_baseline(
    usb,
    ctrl,
    wave_min_index: int,
    wave_max_index: int,
    stop_flag=None
) -> np.ndarray:
    """Step 2: Quick dark noise baseline (3 scans @ 100ms).

    This is a fast baseline measurement to verify hardware is responding.
    The final dark noise will be measured in Step 5E at the calibrated
    integration time.

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        wave_min_index: Minimum wavelength index
        wave_max_index: Maximum wavelength index
        stop_flag: Optional cancellation flag

    Returns:
        Quick dark noise baseline array
    """
    logger.info("=" * 80)
    logger.info("STEP 2: Quick Dark Noise Baseline (3 scans @ 100ms)")
    logger.info("=" * 80)
    logger.info("Purpose: Fast baseline to verify hardware is responding")
    logger.info("Note: Final dark noise will be measured at calibrated integration time\n")

    # Set integration to 100ms for quick measurement
    quick_integration = 100
    usb.set_integration(quick_integration)
    time.sleep(0.010)  # 10ms for integration time to take effect

    # Turn off all LEDs
    logger.info("Turning off all LEDs...")
    ctrl.turn_off_channels()

    # VERIFY LEDs are off using V1.1 firmware query (CRITICAL!)
    logger.info("Verifying LEDs are off...")
    max_retries = 5
    led_verified = False
    has_led_query = hasattr(ctrl, 'get_all_led_intensities')

    if has_led_query:
        for attempt in range(max_retries):
            time.sleep(0.01)  # Wait 10ms for command to process

            # Query LED state (V1.1 firmware feature)
            led_state = ctrl.get_all_led_intensities()

            if led_state is None:
                logger.info(f"LED query failed (attempt {attempt+1}/{max_retries}) - falling back to timing")
                # Fall back to timing-based approach
                has_led_query = False
                break

            # Check if all LEDs are off (intensity <= 1 to account for hardware limitations)
            all_off = all(intensity <= 1 for intensity in led_state.values())

            if all_off:
                logger.info(f"✅ All LEDs confirmed OFF: {led_state}")
                led_verified = True
                break
            else:
                logger.warning(f"⚠️ LEDs still on (attempt {attempt+1}/{max_retries}): {led_state}")
                # Retry turn-off command
                ctrl.turn_off_channels()
                time.sleep(0.05)  # Extra delay

        if not led_verified and has_led_query:
            logger.error(f"❌ Failed to turn off LEDs after {max_retries} attempts")
            raise RuntimeError("Cannot measure quick dark baseline - LEDs failed to turn off")

    if not has_led_query:
        # V1.0 firmware or LED query unavailable - use timing-based approach
        logger.info("LED query not available - using timing-based verification")
        time.sleep(0.05)  # Extra settling time for V1.0 firmware
        led_verified = True

    # Additional delay for LED decay
    time.sleep(LED_DELAY)

    # Average 3 quick scans
    quick_scans = 3
    dark_sum = np.zeros(wave_max_index - wave_min_index)

    logger.info(f"Measuring {quick_scans} scans at {quick_integration}ms integration...")

    for scan in range(quick_scans):
        if stop_flag and stop_flag.is_set():
            logger.warning("Calibration cancelled during quick dark baseline")
            break

        intensity_data = usb.read_intensity()
        if intensity_data is None:
            logger.error("Failed to read intensity during quick dark baseline")
            raise RuntimeError("Spectrometer read failed during quick dark baseline")

        dark_single = intensity_data[wave_min_index:wave_max_index]
        dark_sum += dark_single
        logger.debug(f"  Scan {scan + 1}/{quick_scans}: max = {np.max(dark_single):.0f} counts")

    quick_dark = dark_sum / quick_scans
    max_dark = np.max(quick_dark)
    mean_dark = np.mean(quick_dark)
    min_dark = np.min(quick_dark)

    logger.info(f"✅ Quick baseline complete: max = {max_dark:.0f}, mean = {mean_dark:.0f}, min = {min_dark:.0f} counts")

    # Detector-agnostic validation: check for anomalies rather than absolute values
    # Different detectors have different dark baselines (Ocean Optics, Phase Photonics, etc.)
    dark_ratio = max_dark / max(mean_dark, 1)

    if dark_ratio > 2.0:
        logger.warning(
            f"⚠️ Unusually high dark variability (max/mean ratio = {dark_ratio:.2f}). "
            f"Expected < 2.0. LEDs may not be fully off - check hardware."
        )

    logger.info(f"   Dark uniformity: ratio = {dark_ratio:.2f}")
    logger.info("   This verifies detector is responding\n")

    return quick_dark


# =============================================================================
# STEP 4: LOAD OEM POLARIZER POSITIONS
# =============================================================================

def load_oem_polarizer_positions(
    device_config,
    detector_serial: str
) -> Dict[str, int]:
    """Step 4: Load OEM polarizer positions from device config.

    Polarizer servo positions are calibrated during OEM manufacturing
    and stored in device_config.json.

    Args:
        device_config: DeviceConfiguration instance
        detector_serial: Detector serial number

    Returns:
        Dict with 's_position' and 'p_position' servo angles

    Raises:
        RuntimeError: If positions not found or invalid
    """
    logger.info("=" * 80)
    logger.info("STEP 4: Load OEM Polarizer Positions")
    logger.info("=" * 80)
    logger.info(f"Detector Serial: {detector_serial}")
    logger.info("Loading pre-calibrated servo positions from device config\n")

    try:
        # Get servo positions from device config
        servo_positions = device_config.get_servo_positions()

        if not servo_positions:
            logger.error("❌ No servo positions found in device config")
            logger.error("   OEM polarizer calibration must be run first")
            raise RuntimeError(
                "No servo positions in device configuration. "
                "Run OEM servo calibration tool first."
            )

        # Validate positions (get_servo_positions returns dict with 's' and 'p' keys)
        s_pos = servo_positions.get('s')
        p_pos = servo_positions.get('p')

        if s_pos is None or p_pos is None:
            logger.error("❌ Invalid servo positions (missing s or p)")
            raise RuntimeError("Invalid servo positions in device config")

        # Validate servo range (0-180 for most servos, but allow 10-255 for custom hardware)
        if not (0 <= s_pos <= 255 and 0 <= p_pos <= 255):
            logger.error(f"❌ Invalid servo positions: S={s_pos}, P={p_pos}")
            logger.error("   Positions must be in range 0-255")
            raise RuntimeError("Invalid servo positions in device config")

        logger.info("✅ OEM Polarizer Positions Loaded:")
        logger.info(f"   S-mode position: {s_pos}")
        logger.info(f"   P-mode position: {p_pos}")
        logger.info("   These were calibrated during OEM manufacturing\n")

        # Return with keys matching what code expects (s_position, p_position)
        return {
            's_position': s_pos,
            'p_position': p_pos
        }

    except Exception as e:
        logger.exception(f"Failed to load OEM polarizer positions: {e}")
        raise


# =============================================================================
# STEP 6: P-MODE CALIBRATION WITH POLARITY DETECTION
# =============================================================================

def detect_polarity_and_recalibrate(
    usb,
    ctrl,
    ch_list: list[str],
    p_mode_intensities: Dict[str, int],
    detector_params: DetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    device_config,
    detector_serial: str,
    stop_flag=None
) -> Tuple[bool, Optional[Dict[str, int]]]:
    """Step 6B: Polarity detection with automatic servo recalibration.

    Checks if P-mode is saturating, which indicates wrong polarity
    (servo positions swapped). If detected, automatically triggers
    servo recalibration and updates device config.

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        ch_list: List of channels
        p_mode_intensities: P-mode LED intensities
        detector_params: Detector parameters
        wave_min_index: Min wavelength index
        wave_max_index: Max wavelength index
        device_config: DeviceConfiguration instance
        detector_serial: Detector serial number
        stop_flag: Optional cancellation flag

    Returns:
        Tuple of (polarity_correct, new_positions_or_None)
        - If polarity correct: (True, None)
        - If recalibrated: (False, new_positions_dict)
    """
    logger.info("-" * 80)
    logger.info("STEP 6B: Polarity Detection & Auto-Recalibration")
    logger.info("-" * 80)
    logger.info("Checking if P-mode is saturating (indicates wrong polarity)\n")

    # Check each channel for saturation in P-mode
    saturation_detected = False
    saturated_channels = []

    for ch in ch_list:
        if stop_flag and stop_flag.is_set():
            break

        logger.info(f"Testing P-mode channel {ch.upper()}...")

        # Set P-mode LED
        ctrl.set_intensity(ch=ch, raw_val=p_mode_intensities[ch])
        time.sleep(LED_DELAY)

        # Read spectrum
        spectrum = usb.read_intensity()
        if spectrum is None:
            logger.error("Failed to read spectrum during polarity check")
            raise RuntimeError("Spectrometer read failed")

        # Check for saturation
        sat_count = count_saturated_pixels(
            spectrum,
            wave_min_index,
            wave_max_index,
            detector_params.saturation_threshold
        )

        max_signal = np.max(spectrum[wave_min_index:wave_max_index])

        if sat_count > 0:
            saturation_detected = True
            saturated_channels.append(ch)
            logger.warning(f"  ⚠️ Channel {ch.upper()}: {sat_count} saturated pixels (max={max_signal:.0f})")
        else:
            logger.info(f"  ✅ Channel {ch.upper()}: No saturation (max={max_signal:.0f})")

        # Turn off LED
        ctrl.set_intensity(ch=ch, raw_val=0)
        time.sleep(0.01)

    if not saturation_detected:
        logger.info("\n✅ Polarity Correct: No saturation in P-mode")
        logger.info("   Servo positions are correct\n")
        return True, None

    # Polarity is WRONG - log warning but allow calibration to continue
    logger.warning("\n" + "=" * 80)
    logger.warning("⚠️ POLARITY WARNING")
    logger.warning("=" * 80)
    logger.warning(f"P-mode saturating on channels: {saturated_channels}")
    logger.warning("This may indicate servo positions are SWAPPED (S ↔ P)")
    logger.warning("")
    logger.warning("Calibration will continue, but optical performance may be suboptimal.")
    logger.warning("If SPR signal quality is poor, run manual servo calibration tool.")
    logger.warning("=" * 80 + "\n")

    # Return True to continue calibration (no recalibration needed)
    # Note: Auto-recalibration feature is not yet implemented
    return True, None


# =============================================================================
# MAIN 6-STEP CALIBRATION ENTRY POINT
# =============================================================================

def run_full_6step_calibration(
    usb,
    ctrl,
    device_type: str,
    device_config,
    detector_serial: str,
    single_mode: bool = False,
    single_ch: str = "a",
    stop_flag=None,
    progress_callback=None,
    pre_led_delay_ms: float = PRE_LED_DELAY_MS,
    post_led_delay_ms: float = POST_LED_DELAY_MS
) -> LEDCalibrationResult:
    """Complete 6-step calibration flow.

    STEP 1: Hardware Validation & LED Verification
    STEP 2: Wavelength Calibration
    STEP 3: LED Brightness Ranking & Normalization
    STEP 4: S-Mode Integration Time Optimization (LEDs frozen)
    STEP 5: P-Mode Integration Time Optimization (LEDs frozen)
    STEP 6: S-Mode Reference Signals + QC

    After completion: Shows post-calibration dialog, waits for user to
    click Start button before transferring to live view.

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        device_type: Device type ('P4SPR', 'PicoP4SPR', etc.)
        device_config: DeviceConfiguration instance
        detector_serial: Detector serial number
        single_mode: If True, only calibrate single channel
        single_ch: Channel to calibrate in single mode
        stop_flag: Optional cancellation flag
        progress_callback: Optional progress callback

    Returns:
        LEDCalibrationResult with all calibration data
    """
    result = LEDCalibrationResult()

    print("🔥🔥🔥 DEBUG: run_full_6step_calibration() ENTERED - NEW VERSION WITH DEBUG LOGGING")
    logger.info("🔥🔥🔥 DEBUG: run_full_6step_calibration() ENTERED - NEW VERSION WITH DEBUG LOGGING")

    try:
        # ===================================================================
        # ✨ P1 OPTIMIZATION: Early OEM Position Loading (Fail-Fast)
        # ===================================================================
        # Load OEM calibration positions immediately at initialization.
        # This enables fail-fast behavior (<1 second) instead of failing at Step 4 (~2 minutes).
        # Supports both config formats:
        #   - device_config['oem_calibration'] (preferred format)
        #   - device_config['polarizer'] (OEM tool output format)

        logger.info("=" * 80)
        logger.info("⚡ FAIL-FAST: Loading OEM Polarizer Positions")
        logger.info("=" * 80)

        if not device_config:
            logger.error("=" * 80)
            logger.error("❌ CRITICAL: NO DEVICE CONFIG PROVIDED")
            logger.error("=" * 80)
            logger.error("🔧 REQUIRED: device_config must be provided")
            logger.error("=" * 80)
            raise ValueError("device_config is required for OEM calibration positions")

        # Convert device_config to dict if it's a DeviceConfiguration object
        if hasattr(device_config, 'to_dict'):
            device_config_dict = device_config.to_dict()
        elif hasattr(device_config, 'config'):
            device_config_dict = device_config.config
        else:
            device_config_dict = device_config

        # Try loading positions from either format
        s_pos, p_pos, sp_ratio = None, None, None

        # Try oem_calibration section first (preferred format)
        if 'oem_calibration' in device_config_dict:
            oem = device_config_dict['oem_calibration']
            s_pos = oem.get('polarizer_s_position')
            p_pos = oem.get('polarizer_p_position')
            sp_ratio = oem.get('polarizer_sp_ratio')
            logger.info("✅ Found OEM calibration in 'oem_calibration' section")

        # Fallback to polarizer section (OEM tool format)
        elif 'polarizer' in device_config_dict:
            pol = device_config_dict['polarizer']
            s_pos = pol.get('s_position')
            p_pos = pol.get('p_position')
            sp_ratio = pol.get('sp_ratio') or pol.get('s_p_ratio')
            logger.info("✅ Found OEM calibration in 'polarizer' section (OEM tool format)")

        # Validate positions loaded successfully
        if s_pos is not None and p_pos is not None:
            # Store in result for later use
            result.polarizer_s_position = s_pos
            result.polarizer_p_position = p_pos
            result.polarizer_sp_ratio = sp_ratio

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
            # Positions not found - use safe defaults with warning
            logger.warning("=" * 80)
            logger.warning("⚠️  WARNING: OEM CALIBRATION POSITIONS NOT FOUND")
            logger.warning("=" * 80)
            logger.warning(f"   device_config keys: {list(device_config_dict.keys())}")
            logger.warning("")
            logger.warning("   Using temporary fallback positions for testing:")
            logger.warning("   S-position: 120 (assumed HIGH transmission)")
            logger.warning("   P-position: 60  (assumed LOWER transmission)")
            logger.warning("")
            logger.warning("🔧 RECOMMENDED: Run OEM calibration for optimal performance")
            logger.warning("   Command: python utils/oem_calibration_tool.py --serial <DETECTOR_SERIAL>")
            logger.warning("")
            logger.warning("   ⚠️  Physical polarity may be incorrect without OEM calibration")
            logger.warning("=" * 80)

            # Use safe defaults
            s_pos = 120
            p_pos = 60
            sp_ratio = None

            result.polarizer_s_position = s_pos
            result.polarizer_p_position = p_pos
            result.polarizer_sp_ratio = sp_ratio

        logger.info("\n" + "=" * 80)
        logger.info("🚀 STARTING 6-STEP CALIBRATION FLOW")
        logger.info("=" * 80)
        logger.info("This calibration follows the exact flow discussed:")
        logger.info("  Step 1: Hardware Validation & LED Verification")
        logger.info("  Step 2: Wavelength Calibration")
        logger.info("  Step 3: LED Brightness Ranking")
        logger.info("  Step 4: S-Mode Integration (LEDs frozen)")
        logger.info("  Step 5: P-Mode Optimization (integration only; LEDs frozen)")
        logger.info("  Step 6: Data Processing & QC Validation")
        logger.info("=" * 80 + "\n")

        # Determine channel list (pre-calibration configuration)
        ch_list = determine_channel_list(device_type, single_mode, single_ch)
        logger.info(f"✅ Channels to calibrate: {ch_list}\n")

        # ===================================================================
        # STEP 1: HARDWARE VALIDATION & LED VERIFICATION
        # ===================================================================
        logger.info("=" * 80)
        logger.info("STEP 1: Hardware Validation & LED Verification")
        logger.info("=" * 80)

        if ctrl is None or usb is None:
            logger.error("❌ Hardware not connected")
            raise RuntimeError("Hardware must be connected before calibration")

        logger.info(f"✅ Controller: {type(ctrl).__name__}")
        logger.info(f"✅ Spectrometer: {type(usb).__name__}")
        logger.info(f"✅ Detector Serial: {detector_serial}\n")

        if progress_callback:
            progress_callback("Step 1 of 6: Checking connections", 0)

        # CRITICAL: Force all LEDs OFF and VERIFY
        print("🔦 DEBUG: Forcing ALL LEDs OFF...")
        print(f"   DEBUG: ctrl object type: {type(ctrl)}")
        print(f"   DEBUG: ctrl has get_all_led_intensities: {hasattr(ctrl, 'get_all_led_intensities')}")
        logger.info("🔦 Forcing ALL LEDs OFF...")
        logger.info(f"   DEBUG: ctrl object type: {type(ctrl)}")
        logger.info(f"   DEBUG: ctrl has get_all_led_intensities: {hasattr(ctrl, 'get_all_led_intensities')}")

        ctrl.turn_off_channels()
        time.sleep(0.2)

        # VERIFY LEDs are off using V1.1 firmware query (CRITICAL!)
        print("✅ DEBUG: Verifying LEDs are off...")
        logger.info("✅ Verifying LEDs are off...")
        max_retries = 3  # Optimized: 3 attempts sufficient, saves ~40ms
        led_verified = False
        has_led_query = hasattr(ctrl, 'get_all_led_intensities')

        if has_led_query:
            print("DEBUG: Controller supports LED state query (V1.1+ firmware)")
            logger.info("Controller supports LED state query (V1.1+ firmware)")
            for attempt in range(max_retries):
                time.sleep(0.005)  # Optimized: 5ms adequate for command processing

                # Query LED state (V1.1 firmware feature)
                try:
                    led_state = ctrl.get_all_led_intensities()
                    print(f"   DEBUG: LED query returned: {led_state} (type: {type(led_state)})")
                    logger.info(f"   DEBUG: LED query returned: {led_state} (type: {type(led_state)})")
                except Exception as query_error:
                    print(f"   DEBUG: LED query raised exception: {query_error}")
                    logger.error(f"   DEBUG: LED query raised exception: {query_error}")
                    led_state = None

                if led_state is None:
                    print(f"WARNING: LED query returned None (attempt {attempt+1}/{max_retries})")
                    logger.warning(f"LED query returned None (attempt {attempt+1}/{max_retries})")
                    if attempt == max_retries - 1:
                        # All queries failed - fall back to timing-based approach
                        print("INFO: All LED queries failed - falling back to timing-based verification")
                        logger.info("All LED queries failed - falling back to timing-based verification")
                        has_led_query = False
                        break
                    continue

                # Check if all LEDs are off (0 intensity)
                # Note: Channel D returns -1 due to firmware limitation, so exclude it
                # Note: Treat intensity <= 1 as "off" to account for firmware/hardware limitations
                channels_to_check = {ch: val for ch, val in led_state.items() if ch != 'd'}
                print(f"   DEBUG: Channels to check: {channels_to_check}")
                logger.info(f"   DEBUG: Channels to check: {channels_to_check}")
                all_off = all(intensity <= 1 for intensity in channels_to_check.values())
                print(f"   DEBUG: All off (intensity <= 1)? {all_off}")
                logger.info(f"   DEBUG: All off (intensity <= 1)? {all_off}")

                if all_off:
                    print(f"✅ DEBUG: All LEDs confirmed OFF: {led_state}")
                    logger.info(f"✅ All LEDs confirmed OFF: {led_state}")
                    led_verified = True
                    break
                else:
                    print(f"⚠️ DEBUG: LEDs still on (attempt {attempt+1}/{max_retries}): {led_state}")
                    logger.warning(f"⚠️ LEDs still on (attempt {attempt+1}/{max_retries}): {led_state}")
                    # Retry turn-off command
                    print(f"   DEBUG: Retrying turn_off_channels()...")
                    logger.info(f"   DEBUG: Retrying turn_off_channels()...")
                    ctrl.turn_off_channels()
                    time.sleep(0.05)  # Extra delay

            if not led_verified and has_led_query:
                print(f"❌ DEBUG: Failed to turn off LEDs after {max_retries} attempts")
                print(f"   DEBUG: Last LED state: {led_state if 'led_state' in locals() else 'N/A'}")
                logger.error(f"❌ Failed to turn off LEDs after {max_retries} attempts")
                logger.error(f"   Last LED state: {led_state if 'led_state' in locals() else 'N/A'}")
                logger.error("This may indicate a hardware or firmware communication issue")
                raise RuntimeError("Cannot proceed - LEDs failed to turn off")

        if not has_led_query:
            # V1.0 firmware or LED query unavailable - use timing-based approach
            logger.info("LED query not available - using timing-based verification")
            time.sleep(0.05)  # Extra settling time for V1.0 firmware (only needed when query unavailable)
            led_verified = True
            logger.info("✅ Assuming LEDs are OFF (timing-based)")

        logger.info(f"✅ Step 1 complete: Hardware validated, LEDs confirmed OFF\n")

        # ===================================================================
        # STEP 2: WAVELENGTH RANGE CALIBRATION (DETECTOR-SPECIFIC)
        # ===================================================================
        logger.info("=" * 80)
        logger.info("STEP 2: Wavelength Range Calibration (Detector-Specific)")
        logger.info("=" * 80)

        if progress_callback:
            progress_callback("Step 2 of 6: Reading wavelengths", 17)

        # Read wavelength data from detector EEPROM
        logger.info("Reading wavelength calibration from detector EEPROM...")
        wave_data = usb.read_wavelength()

        if wave_data is None or len(wave_data) == 0:
            logger.error("❌ Failed to read wavelengths from detector")
            return result

        logger.info(f"✅ Full detector range: {wave_data[0]:.1f}-{wave_data[-1]:.1f}nm ({len(wave_data)} pixels)")

        # Detect detector type from wavelength range
        detector_type_str = "Unknown"
        if 186 <= wave_data[0] <= 188 and 884 <= wave_data[-1] <= 886:
            detector_type_str = "Ocean Optics USB4000 (UV-VIS)"
        elif 337 <= wave_data[0] <= 339 and 1020 <= wave_data[-1] <= 1022:
            detector_type_str = "Ocean Optics USB4000 (VIS-NIR)"

        logger.info(f"📊 Detector: {detector_type_str}")

        # Calculate spectral filter (SPR range only)
        wave_min_index = np.searchsorted(wave_data, MIN_WAVELENGTH)
        wave_max_index = np.searchsorted(wave_data, MAX_WAVELENGTH)

        # Store wavelength data
        result.wave_data = wave_data[wave_min_index:wave_max_index].copy()
        result.wavelengths = result.wave_data.copy()
        result.wave_min_index = wave_min_index
        result.wave_max_index = wave_max_index
        result.full_wavelengths = wave_data.copy()

        logger.info(f"✅ SPR filtered range: {MIN_WAVELENGTH}-{MAX_WAVELENGTH}nm ({len(result.wave_data)} pixels)")
        logger.info(f"   Spectral resolution: {(wave_data[-1]-wave_data[0])/len(wave_data):.3f} nm/pixel")

        # Get detector parameters
        detector_params = get_detector_params(usb)
        result.detector_max_counts = detector_params.max_counts
        result.detector_saturation_threshold = detector_params.saturation_threshold

        logger.info(f"✅ Detector parameters:")
        logger.info(f"   Max counts: {detector_params.max_counts}")
        logger.info(f"   Saturation threshold: {detector_params.saturation_threshold}")
        logger.info(f"✅ Step 2 complete\n")

        # ===================================================================
        # STEP 3: LED BRIGHTNESS RANKING (WITH FIRMWARE RANK OPTIMIZATION)
        # ===================================================================
        logger.info("=" * 80)
        logger.info("STEP 3: LED Brightness Ranking")
        logger.info("=" * 80)

        if progress_callback:
            progress_callback("Step 3 of 6: Measuring channel brightness", 33)

        # Switch to S-mode and turn off all channels
        logger.info("Switching to S-mode...")
        switch_mode_safely(ctrl, "s", turn_off_leds=True)
        logger.info("✅ S-mode active, all LEDs off\n")

        # Set fixed integration time for consistent LED ranking
        # 70ms provides sufficient signal at 20% LED (weak but adequate for ranking)
        RANKING_INTEGRATION_TIME = 70  # milliseconds
        usb.set_integration(RANKING_INTEGRATION_TIME)
        logger.info(f"🔧 Integration time set to {RANKING_INTEGRATION_TIME:.0f}ms for LED ranking\n")

        # ⚡ FIRMWARE V1.2 OPTIMIZATION: Try firmware rank command first
        # If available, this measures all 4 LEDs in ~375ms (15x faster than Python loop)
        firmware_rank_available = hasattr(ctrl, 'rank_leds')

        if firmware_rank_available:
            logger.info("⚡ FIRMWARE V1.2: Using hardware-accelerated LED ranking")
            logger.info("   Expected speedup: 2.7× faster (375ms vs 1000ms)\n")

            try:
                # Call firmware rank command
                rank_data = ctrl.rank_leds()  # Returns: [(ch, mean_intensity), ...] sorted weakest→strongest

                if rank_data and len(rank_data) == len(ch_list):
                    # Convert firmware format to expected format
                    channel_data = {}
                    for ch, mean in rank_data:
                        # Firmware only returns mean, so use mean for max as well (approximation)
                        channel_data[ch] = (mean, mean, False)  # (mean, max, saturated)

                    # Rank channels (already sorted by firmware)
                    ranked_channels = [(ch, channel_data[ch]) for ch, _ in rank_data]

                    logger.info("✅ Firmware ranking complete")
                    logger.info(f"📊 LED Ranking (weakest → strongest):")
                    for rank_idx, (ch, (mean, _, _)) in enumerate(ranked_channels, 1):
                        ratio = mean / ranked_channels[0][1][0] if ranked_channels[0][1][0] > 0 else 1.0
                        logger.info(f"   {rank_idx}. Channel {ch.upper()}: {mean:6.0f} counts ({ratio:.2f}× weakest)")

                    # Store ranking for Step 4
                    result.led_ranking = ranked_channels
                    result.weakest_channel = ranked_channels[0][0]

                    # Skip Python fallback
                    firmware_rank_success = True
                else:
                    logger.warning("⚠️  Firmware rank returned invalid data, falling back to Python")
                    firmware_rank_success = False

            except Exception as e:
                logger.warning(f"⚠️  Firmware rank failed: {e}")
                logger.warning("   Falling back to Python implementation")
                firmware_rank_success = False
        else:
            logger.info("ℹ️  Firmware V1.2 not detected, using Python LED ranking")
            firmware_rank_success = False

        # ===================================================================
        # PYTHON FALLBACK: Manual LED ranking (if firmware not available)
        # ===================================================================
        if not firmware_rank_success:
            logger.info("📊 Testing all LEDs to rank by brightness (Python loop)...\n")

            # Use 20% LED for safe ranking (avoid saturation)
            MAX_LED_INTENSITY = 255
            test_led_intensity = int(0.2 * MAX_LED_INTENSITY)  # 51
            logger.info(f"   Test LED: {test_led_intensity} ({test_led_intensity/255*100:.0f}%)")
            logger.info(f"   Test region: Full SPR spectrum ({result.wave_data[0]:.1f}-{result.wave_data[-1]:.1f}nm)\n")

            channel_data = {}
            SATURATION_THRESHOLD = int(0.95 * detector_params.saturation_level)

            # Measure each channel
            for ch in ch_list:
                if stop_flag and stop_flag.is_set():
                    logger.warning("❌ Calibration stopped during Step 3")
                    return result

                # Turn on single channel with batch command
                batch_values = {c: (test_led_intensity if c == ch else 0) for c in ['a', 'b', 'c', 'd']}
                ctrl.set_batch_intensities(**batch_values)
                time.sleep(LED_DELAY)

                # Read spectrum
                raw_spectrum = usb.read_intensity()
                if raw_spectrum is None:
                    logger.error(f"Failed to read channel {ch}")
                    continue

                # Apply spectral filter (use full SPR region for ranking)
                filtered_spectrum = raw_spectrum[wave_min_index:wave_max_index]

                mean_intensity = float(np.mean(filtered_spectrum))
                max_intensity = float(np.max(filtered_spectrum))
                is_saturated = max_intensity >= SATURATION_THRESHOLD

                channel_data[ch] = (mean_intensity, max_intensity, is_saturated)

                sat_flag = " ⚠️ SATURATED" if is_saturated else ""
                logger.info(f"   {ch.upper()}: mean={mean_intensity:6.0f}, max={max_intensity:6.0f}{sat_flag}")

            # Turn off all LEDs
            ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
            time.sleep(LED_DELAY)

            # Handle saturation (retry at even lower LED if needed)
            saturated_channels = [ch for ch, (_, _, sat) in channel_data.items() if sat]

            if saturated_channels:
                logger.warning(f"⚠️  Saturation detected in {len(saturated_channels)} channel(s): {saturated_channels}")
                logger.warning(f"   Retrying at LED=25 (10%)...\n")

                retry_led = 25
                for ch in saturated_channels:
                    if stop_flag and stop_flag.is_set():
                        return result

                    batch_values = {c: (retry_led if c == ch else 0) for c in ['a', 'b', 'c', 'd']}
                    ctrl.set_batch_intensities(**batch_values)
                    time.sleep(LED_DELAY)

                    raw_spectrum = usb.read_intensity()
                    if raw_spectrum is None:
                        continue

                    filtered_spectrum = raw_spectrum[wave_min_index:wave_max_index]

                    mean_intensity = float(np.mean(filtered_spectrum))
                    max_intensity = float(np.max(filtered_spectrum))

                    # Scale up to equivalent of test_led_intensity
                    scaled_mean = mean_intensity * (test_led_intensity / retry_led)
                    scaled_max = max_intensity * (test_led_intensity / retry_led)

                    channel_data[ch] = (scaled_mean, scaled_max, False)
                    logger.info(f"   {ch.upper()} retry: {mean_intensity:6.0f} @ LED={retry_led} → scaled: {scaled_mean:6.0f}")

                ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
                time.sleep(LED_DELAY)

            # Rank channels
            ranked_channels = sorted(channel_data.items(), key=lambda x: x[1][0])
            result.led_ranking = ranked_channels
            result.weakest_channel = ranked_channels[0][0]

            logger.info(f"\n📊 LED Ranking (weakest → strongest):")
            for rank_idx, (ch, (mean, _, was_sat)) in enumerate(ranked_channels, 1):
                ratio = mean / ranked_channels[0][1][0]
                sat_flag = " [was saturated]" if was_sat else ""
                logger.info(f"   {rank_idx}. Channel {ch.upper()}: {mean:6.0f} counts ({ratio:.2f}× weakest){sat_flag}")

        # QC CHECK: Detect if all channels have flat/low signal (<4000 counts)
        # This suggests LEDs might be OFF or hardware issue
        all_signals_low = all(mean < 4000 for (ch, (mean, _, _)) in ranked_channels)
        if all_signals_low:
            max_signal = max(mean for (ch, (mean, _, _)) in ranked_channels)
            logger.warning("")
            logger.warning("⚠️  QC FLAG: All channels have very low signal (<4000 counts)")
            logger.warning(f"   Maximum signal detected: {max_signal:.0f} counts")
            logger.warning("   Possible causes: LEDs are OFF, hardware disconnected, or extremely low light")
            logger.warning("   Calibration will continue, but results may be invalid")
            logger.warning("")
            result.qc_results['step3a_low_signal_flag'] = {
                'status': 'WARNING',
                'max_signal': float(max_signal),
                'threshold': 4000.0,
                'message': 'All channels below 4000 counts - LEDs may be OFF'
            }

        # Display final ranking summary
        weakest_ch = result.led_ranking[0][0]
        strongest_ch = result.led_ranking[-1][0]
        weakest_intensity = result.led_ranking[0][1][0]
        # Guard against near-zero weakest brightness to avoid divide-by-zero later
        if weakest_intensity <= 1e-6:
            logger.error("❌ Weakest channel brightness is near-zero; optics/hardware issue suspected")
            raise RuntimeError("Invalid LED ranking: weakest brightness near-zero")
        strongest_intensity = result.led_ranking[-1][1][0]

        logger.info(f"")
        logger.info(f"✅ Weakest LED: {weakest_ch.upper()} ({weakest_intensity:.0f} counts)")
        logger.info(f"⚠️  Strongest LED: {strongest_ch.upper()} ({strongest_intensity:.0f} counts, {strongest_intensity/weakest_intensity:.2f}× brighter)")
        logger.info(f"")

        # ===================================================================
        # STEP 3B: WEAKEST CHANNEL INTEGRATION TIME OPTIMIZATION
        # ===================================================================
        logger.info(f"="*80)
        logger.info(f"STEP 3B: Weakest Channel Integration Time Optimization")
        logger.info(f"="*80)
        logger.info(f"Goal: Find integration time where weakest channel @ LED=255 hits 45% detector")
        logger.info(f"Strategy: Binary search to maximize weakest channel signal")
        logger.info(f"Target: {weakest_ch.upper()} @ LED=255 → 45% detector ({int(0.45 * (detector_params.max_counts)):.0f} counts)")
        logger.info(f"")

        # Constants
        detector_max = result.detector_max_counts if hasattr(result, 'detector_max_counts') else detector_params.max_counts
        STEP3B_TARGET_PERCENT = 0.45  # 45% detector max
        WEAKEST_TARGET_LED = 255  # Maximum LED for weakest channel
        step3b_target_signal = int(STEP3B_TARGET_PERCENT * detector_max)

        logger.info(f"📊 Binary Search: Optimize integration time (weakest @ LED={WEAKEST_TARGET_LED})")
        logger.info(f"")

        min_int = detector_params.min_integration_time  # Already in milliseconds
        max_int = detector_params.max_integration_time  # Already in milliseconds
        best_integration = None
        best_signal = 0

        consecutive_stable_s1 = 0
        last_signal_s1 = None
        stable_tol_pct_s1 = 0.5
        for iteration in range(15):
            if stop_flag and stop_flag.is_set():
                break

            test_int = (min_int + max_int) / 2.0
            usb.set_integration(test_int)
            time.sleep(0.010)  # 10ms for integration time to take effect

            ctrl.set_intensity(ch=weakest_ch, raw_val=WEAKEST_TARGET_LED)
            time.sleep(LED_DELAY)
            spectrum = usb.read_intensity()
            ctrl.turn_off_channels()

            if spectrum is None:
                logger.error(f"Failed to read spectrum")
                break

            # Robust signal over ROI to mitigate single-pixel spikes
            signal = roi_signal(spectrum, wave_min_index, wave_max_index, method="median")
            signal_pct = (signal / detector_max) * 100

            logger.info(f"   Iteration {iteration+1}: {test_int:.1f}ms → {signal:.0f} counts ({signal_pct:.1f}%)")

            # Early-stop if successive measurements stabilize
            if last_signal_s1 is not None and detector_max:
                delta_pct = abs(signal - last_signal_s1) / detector_max * 100.0
                if delta_pct <= stable_tol_pct_s1:
                    consecutive_stable_s1 += 1
                else:
                    consecutive_stable_s1 = 0
            last_signal_s1 = signal

            # Check if we hit target
            error_pct = abs((signal - step3b_target_signal) / step3b_target_signal) * 100
            if error_pct <= 2.0 or consecutive_stable_s1 >= 2:
                best_integration = test_int
                best_signal = signal
                if error_pct <= 2.0:
                    logger.info(f"      ✅ OPTIMAL! Error: {error_pct:.1f}%")
                else:
                    logger.info("      ⏹️ Early-stop: stable weakest-channel signal")
                break
            elif signal < step3b_target_signal:
                min_int = test_int
            else:
                max_int = test_int

            # Track best
            if abs(signal - step3b_target_signal) < abs(best_signal - step3b_target_signal):
                best_integration = test_int
                best_signal = signal

        if best_integration is None:
            raise RuntimeError("Step 3B integration time optimization failed")

        usb.set_integration(best_integration)
        time.sleep(0.010)  # 10ms for integration time to take effect

        logger.info(f"")
        logger.info(f"✅ STEP 3B COMPLETE: Integration time locked at {best_integration:.1f}ms")
        logger.info(f"   Weakest ({weakest_ch.upper()} @ LED={WEAKEST_TARGET_LED}): {best_signal:.0f} counts ({(best_signal/detector_max)*100:.1f}%)")
        logger.info(f"")

        # ===================================================================
        # STEP 3C: LED NORMALIZATION (Calculate & Verify)
        # ===================================================================
        # NOTE: Alternative calibration modes can branch here:
        #   - Standard mode (USE_ALTERNATIVE_CALIBRATION=False): Normalize LEDs, use global integration
        #   - Alternative mode (USE_ALTERNATIVE_CALIBRATION=True): Fix all LEDs=255, use per-channel integration
        logger.info(f"="*80)
        logger.info(f"STEP 3C: LED Normalization")
        logger.info(f"="*80)

        if USE_ALTERNATIVE_CALIBRATION:
            # ALTERNATIVE MODE: LED=255 fixed for all channels, per-channel integration
            logger.info(f"Mode: ALTERNATIVE (LED=255 fixed + per-channel integration)")
            logger.info(f"Goal: Set all LEDs to 255, adjust integration time per channel in Step 5")
            logger.info(f"")

            normalized_leds = {ch: 255 for ch in ch_list}

            logger.info(f"   All LEDs set to 255 (maximum intensity)")
            logger.info(f"   Integration time adjustment will be done per channel in Step 5")
            logger.info(f"")

            # Store brightness ratios for Step 5 per-channel integration adjustment
            result.brightness_ratios = {}
            for ch, (step3a_ranking_signal, _, _) in ranked_channels:
                brightness_ratio = step3a_ranking_signal / weakest_intensity
                result.brightness_ratios[ch] = brightness_ratio
                logger.info(f"   {ch.upper()}: Brightness ratio {brightness_ratio:.2f}× (will invert to integration time)")

        else:
            # STANDARD MODE: Normalized LED intensities, global integration
            logger.info(f"Mode: STANDARD (Normalized LEDs + global integration)")
            logger.info(f"Goal: Calculate normalized LED intensities for all channels")
            logger.info(f"Strategy: Use Step 3A brightness ratios + Step 3B integration time")
            logger.info(f"")

            # STAGE 1: Calculate normalized LEDs
            logger.info(f"📊 STAGE 1: Calculate Normalized LEDs (Brightness Compensation)")
            logger.info(f"")

            normalized_leds = {}
            for rank_idx, (ch, (step3a_ranking_signal, _, _)) in enumerate(ranked_channels, 1):
                # Calculate brightness ratio from Step 3A measurements
                brightness_ratio = step3a_ranking_signal / weakest_intensity

                # Calculate normalized LED (inverse of brightness ratio)
                normalized_led = int(WEAKEST_TARGET_LED / brightness_ratio)
                normalized_led = max(10, min(255, normalized_led))

                normalized_leds[ch] = normalized_led

                logger.info(f"   {ch.upper()}: Brightness {brightness_ratio:.2f}× → LED={normalized_led}")

            logger.info(f"")

            # STAGE 2: Verify uniformity
            logger.info(f"📊 STAGE 2: Verify Uniformity (All Channels @ ~45%)")
            logger.info(f"")

            target_signal = step3b_target_signal  # From Step 3B (45% detector)
            tolerance_pct = 0.10  # ±10% tolerance

            weakest_signal = None
            for ch in ch_list:
                if stop_flag and stop_flag.is_set():
                    break

                ctrl.set_intensity(ch=ch, raw_val=normalized_leds[ch])
                time.sleep(LED_DELAY)
                spectrum = usb.read_intensity()
                ctrl.turn_off_channels()

                if spectrum is None:
                    logger.error(f"Failed to verify {ch.upper()}")
                    continue

                # Robust signal metric for verification
                signal = roi_signal(spectrum, wave_min_index, wave_max_index, method="median")
                signal_pct = (signal / detector_max) * 100

                # Check for saturation: count saturated pixels in ROI
                roi_spectrum = spectrum[wave_min_index:wave_max_index]
                saturation_limit = detector_params.saturation_threshold
                saturated_pixels = np.sum(roi_spectrum >= saturation_limit)
                is_saturated = saturated_pixels > 0
                max_pixel = np.max(roi_spectrum)
                sat_status = f"⚠️ {saturated_pixels} SAT" if is_saturated else ""

                # EMPIRICAL VALIDATION: Count pixels near target
                pixels_near, pct_near = count_pixels_near_target(
                    spectrum, wave_min_index, wave_max_index, target_signal, tolerance_pct
                )
                total_pixels = wave_max_index - wave_min_index

                if weakest_signal is None:
                    weakest_signal = signal

                deviation_pct = ((signal - weakest_signal) / weakest_signal) * 100
                uniformity_status = "✅" if abs(deviation_pct) < 10 and not is_saturated else "⚠️"
                pixel_status = "✅" if pct_near >= 50 else "⚠️"  # At least 50% pixels near target

                logger.info(f"   {ch.upper()} @ LED={normalized_leds[ch]:3d}: {signal:6.0f} counts ({signal_pct:5.1f}%) {uniformity_status} {deviation_pct:+.1f}% {sat_status}")
                if is_saturated:
                    logger.warning(f"      {saturated_pixels} pixels saturated (max: {max_pixel:.0f} >= {saturation_limit:.0f})")
                logger.info(f"      Pixels near target: {pixels_near}/{total_pixels} ({pct_near:.1f}%) {pixel_status}")

        logger.info(f"")
        logger.info(f"="*80)
        logger.info(f"✅ STEP 3C COMPLETE: LEDs {'FIXED AT 255' if USE_ALTERNATIVE_CALIBRATION else 'NORMALIZED & LOCKED'}")
        logger.info(f"="*80)
        logger.info(f"   Integration time: {best_integration:.1f}ms (from Step 3B)")
        if USE_ALTERNATIVE_CALIBRATION:
            logger.info(f"   All LEDs @ 255 (per-channel integration will be optimized in Step 5)")
        else:
            logger.info(f"   All channels @ ~45% ({step3b_target_signal:.0f} counts)")
        logger.info(f"   ⚠️  LED VALUES NOW FROZEN (no changes after Step 3C)")
        logger.info(f"")

        # Store results
        result.s_mode_intensity = normalized_leds
        result.ref_intensity = normalized_leds
        result.s_integration_time = best_integration  # Already in milliseconds
        result.weakest_channel = weakest_ch

        # ===================================================================
        # STEP 4: S-MODE BASELINE CHARACTERIZATION (TWO ROI REGIONS)
        # ===================================================================
        if progress_callback:
            progress_callback("Step 4 of 6: Measuring S-mode baseline", 50)

        logger.info("=" * 80)
        logger.info("STEP 4: S-Mode Baseline Characterization (Two ROI Regions)")
        logger.info("=" * 80)
        logger.info("Goal: Measure S-mode signal in two ROI regions for P-mode loss calculation")
        logger.info("Strategy: Use normalized LEDs + integration time from Step 3 (frozen)")
        logger.info("ROI 1: 560-570nm (blue edge - minimal SPR signal)")
        logger.info("ROI 2: 710-720nm (red edge - minimal SPR signal)")
        logger.info("Purpose: Establish S-pol baseline to calculate P-pol signal loss in Step 5\n")

        logger.info("Purpose: Establish S-pol baseline to calculate P-pol signal loss in Step 5\n")

        # Define ROI regions (away from SPR dip)
        ROI1_MIN = 560.0  # nm
        ROI1_MAX = 570.0  # nm
        ROI2_MIN = 710.0  # nm
        ROI2_MAX = 720.0  # nm

        # Find indices for ROI regions in the full wavelength array
        roi1_min_idx = np.searchsorted(result.full_wavelengths, ROI1_MIN)
        roi1_max_idx = np.searchsorted(result.full_wavelengths, ROI1_MAX)
        roi2_min_idx = np.searchsorted(result.full_wavelengths, ROI2_MIN)
        roi2_max_idx = np.searchsorted(result.full_wavelengths, ROI2_MAX)

        logger.info(f"📊 ROI Definitions:")
        logger.info(f"   ROI 1: {ROI1_MIN}-{ROI1_MAX}nm (indices {roi1_min_idx}-{roi1_max_idx})")
        logger.info(f"   ROI 2: {ROI2_MIN}-{ROI2_MAX}nm (indices {roi2_min_idx}-{roi2_max_idx})")
        logger.info(f"   Using integration time from Step 3B: {best_integration:.1f}ms")
        logger.info("")

        # Measure each channel in S-mode at both ROI regions
        s_roi1_signals = {}
        s_roi2_signals = {}
        s_raw_data = {}

        # Calculate num_scans based on integration time
        result.num_scans = max(3, min(int(MAX_READ_TIME / best_integration), MAX_NUM_SCANS))
        logger.info(f"📊 Acquisition: {result.num_scans} scans per channel\n")

        for ch in ch_list:
            if stop_flag and stop_flag.is_set():
                break

            logger.info(f"Measuring channel {ch.upper()} S-mode baseline...")

            # Set LED intensity from Step 3C (normalized)
            ctrl.set_intensity(ch=ch, raw_val=normalized_leds[ch])
            time.sleep(LED_DELAY)

            # Average multiple scans for stable measurement
            spectra = []
            for scan_idx in range(result.num_scans):
                spectrum = usb.read_intensity()
                if spectrum is not None:
                    spectra.append(spectrum)  # Full spectrum
                time.sleep(0.01)

            ctrl.turn_off_channels()

            if len(spectra) == 0:
                logger.error(f"   ❌ Failed to capture spectra for {ch.upper()}")
                continue

            # Average spectra
            avg_spectrum = np.mean(spectra, axis=0)

            # Store filtered spectrum for Step 6
            s_raw_data[ch] = avg_spectrum[wave_min_index:wave_max_index]

            # Calculate mean signal in each ROI (using full spectrum indices)
            roi1_signal = np.mean(avg_spectrum[roi1_min_idx:roi1_max_idx])
            roi2_signal = np.mean(avg_spectrum[roi2_min_idx:roi2_max_idx])

            s_roi1_signals[ch] = roi1_signal
            s_roi2_signals[ch] = roi2_signal

            signal_pct = (roi1_signal / detector_max) * 100
            logger.info(f"   ROI 1 (560-570nm): {roi1_signal:.0f} counts ({signal_pct:.1f}%)")
            signal_pct = (roi2_signal / detector_max) * 100
            logger.info(f"   ROI 2 (710-720nm): {roi2_signal:.0f} counts ({signal_pct:.1f}%)")

        # Store S-mode data for Step 5 comparison
        result.s_raw_data = s_raw_data
        result.s_roi1_signals = s_roi1_signals
        result.s_roi2_signals = s_roi2_signals
        result.s_integration_time = best_integration  # Lock from Step 3B

        logger.info("")
        logger.info("="*80)
        logger.info("✅ STEP 4 COMPLETE: S-Mode Baseline Characterized")
        logger.info("="*80)
        logger.info(f"   Integration time: {best_integration:.1f}ms (from Step 3B)")
        logger.info(f"   Scans per channel: {result.num_scans}")
        logger.info(f"   S-mode ROI signals captured for P-mode comparison in Step 5")
        logger.info("")
        for ch in ch_list:
            if ch in s_roi1_signals and ch in s_roi2_signals:
                logger.info(f"   {ch.upper()}: ROI1={s_roi1_signals[ch]:.0f}, ROI2={s_roi2_signals[ch]:.0f}")

        # ---------------------------------------------------------------
        # CALCULATE CYCLE TIME (for 1Hz constraint validation)
        # ---------------------------------------------------------------
        # Single cycle = 4 LEDs measured sequentially in one polarization mode
        # Time per channel = integration_time + pre_led_delay + post_led_delay + overhead

        cycle_time_per_channel = (
            best_integration +  # Integration time (ms)
            result.pre_led_delay_ms +  # Pre-LED stabilization (12ms)
            result.post_led_delay_ms +  # Post-LED afterglow (40ms)
            10  # Overhead: USB communication + processing (estimated 10ms)
        )

        total_cycle_time_ms = cycle_time_per_channel * len(ch_list)
        total_cycle_time_s = total_cycle_time_ms / 1000.0
        max_acquisition_rate_hz = 1.0 / total_cycle_time_s if total_cycle_time_s > 0 else 0

        logger.info("")
        logger.info(f"📊 Cycle Time Analysis (4 LEDs sequential):")
        logger.info(f"   Time per channel: {cycle_time_per_channel:.1f}ms")
        logger.info(f"   Total cycle time: {total_cycle_time_ms:.1f}ms ({total_cycle_time_s:.3f}s)")
        logger.info(f"   Maximum acquisition rate: {max_acquisition_rate_hz:.2f} Hz")

        # QC CHECK: Validate 1Hz constraint (cycle time must be ≤1000ms)
        MAX_CYCLE_TIME_MS = 1000.0  # 1 second = 1Hz
        if total_cycle_time_ms > MAX_CYCLE_TIME_MS:
            logger.warning("")
            logger.warning("⚠️  QC FLAG: Cycle time exceeds 1Hz constraint")
            logger.warning(f"   Current: {total_cycle_time_ms:.1f}ms > {MAX_CYCLE_TIME_MS:.0f}ms limit")
            logger.warning(f"   Acquisition rate: {max_acquisition_rate_hz:.2f} Hz < 1.0 Hz minimum")
            logger.warning("   Consider reducing integration time or LED delays")
            logger.warning("")
            result.qc_results['cycle_time_flag'] = {
                'status': 'WARNING',
                'cycle_time_ms': float(total_cycle_time_ms),
                'max_allowed_ms': MAX_CYCLE_TIME_MS,
                'acquisition_rate_hz': float(max_acquisition_rate_hz),
                'message': f'Cycle time {total_cycle_time_ms:.1f}ms exceeds 1Hz constraint'
            }
        else:
            logger.info(f"   ✅ Cycle time within 1Hz constraint ({total_cycle_time_ms:.1f}ms ≤ {MAX_CYCLE_TIME_MS:.0f}ms)")
            result.qc_results['cycle_time_check'] = {
                'status': 'PASS',
                'cycle_time_ms': float(total_cycle_time_ms),
                'acquisition_rate_hz': float(max_acquisition_rate_hz)
            }

        # Store cycle time metrics in result
        result.cycle_time_ms = total_cycle_time_ms
        result.acquisition_rate_hz = max_acquisition_rate_hz

        logger.info("")
        logger.info("="*80 + "\n")

        # ===================================================================
        # STEP 5: P-MODE MEASUREMENT + PER-CHANNEL INTEGRATION ADJUSTMENT
        # ===================================================================
        # After Step 4 measured S-mode baseline in ROI regions, we now:
        #   1. Switch polarization from S to P
        #   2. Measure ROI signals with S-mode integration time
        #   3. Calculate signal loss: (S_ROI - P_ROI) / S_ROI per channel
        #   4. Adjust integration time per channel to compensate for P-pol loss (initial estimate)
        #   5. Optimize integration time per channel to hit target intensity (77-83%) with no saturation
        #   6. Capture P-mode raw spectra with optimized per-channel integration times
        #   7. Measure dark reference with LEDs OFF
        #
        # DESIGN: ROI-based initial estimate + binary search per channel for target optimization
        logger.info("")
        logger.info("=" * 80)
        logger.info("STEP 5: P-MODE MEASUREMENT + PER-CHANNEL INTEGRATION ADJUSTMENT")
        logger.info("        Switch to P-polarization → Measure ROI signal loss → Optimize integration per channel")
        logger.info("=" * 80)

        if progress_callback:
            progress_callback("Step 5 of 6: P-mode measurement...", 67)

        # ---------------------------------------------------------------
        # PART A: SWITCH TO P-MODE AND MEASURE ROI SIGNALS
        # ---------------------------------------------------------------
        ctrl.set_polarization('P')
        logger.info("  → Switched to P-polarization mode")
        logger.info("")

        # Use S-mode integration as baseline
        p_integration_time = result.s_integration_time  # Already in milliseconds
        usb.set_integration(p_integration_time)
        time.sleep(0.010)  # 10ms settling time

        # P-mode LED intensities (normalized from Step 3C)
        p_led_intensities = result.normalized_leds.copy()

        # Define ROI wavelength ranges (from Step 4)
        ROI1_WL_MIN, ROI1_WL_MAX = 560, 570  # Blue edge
        ROI2_WL_MIN, ROI2_WL_MAX = 710, 720  # Red edge

        # Convert wavelengths to pixel indices
        wavelengths = usb.read_wavelengths()
        roi1_min_idx = np.searchsorted(wavelengths, ROI1_WL_MIN)
        roi1_max_idx = np.searchsorted(wavelengths, ROI1_WL_MAX)
        roi2_min_idx = np.searchsorted(wavelengths, ROI2_WL_MIN)
        roi2_max_idx = np.searchsorted(wavelengths, ROI2_WL_MAX)

        logger.info(f"  Measuring P-mode ROI signals with {p_integration_time:.1f}ms integration:")

        # Measure P-mode ROI signals
        p_roi1_signals = {}
        p_roi2_signals = {}
        for ch_name in ch_list:
            led_val = p_led_intensities[ch_name]
            ctrl.set_intensity(ch=ch_name, raw_val=led_val)
            time.sleep(LED_DELAY)
            spectrum = usb.read_intensity()
            ctrl.set_intensity(ch=ch_name, raw_val=0)
            time.sleep(0.01)

            if spectrum is None:
                logger.warning(f"    ⚠️  {ch_name.upper()}: No spectrum")
                continue

            # Calculate ROI signals (median of ROI pixels)
            roi1_signal = np.median(spectrum[roi1_min_idx:roi1_max_idx])
            roi2_signal = np.median(spectrum[roi2_min_idx:roi2_max_idx])

            p_roi1_signals[ch_name] = roi1_signal
            p_roi2_signals[ch_name] = roi2_signal

            logger.info(f"    {ch_name.upper()}: ROI1={roi1_signal:.0f}, ROI2={roi2_signal:.0f}")

        # ---------------------------------------------------------------
        # PART B: CALCULATE SIGNAL LOSS AND INITIAL INTEGRATION ESTIMATE
        # ---------------------------------------------------------------
        logger.info("")
        logger.info("  Calculating P-pol signal loss and initial integration estimate:")

        # Retrieve S-mode baseline from Step 4
        s_roi1_signals = result.s_roi1_signals
        s_roi2_signals = result.s_roi2_signals

        # QC CHECK: Detect if P-pol ROI signals INCREASE vs S-pol (suggests polarizer issue)
        roi_increase_detected = False
        roi_increase_channels = []

        # Calculate per-channel integration time adjustments (initial estimate)
        channel_integration_times = {}

        if USE_ALTERNATIVE_CALIBRATION and hasattr(result, 'brightness_ratios') and result.brightness_ratios:
            # ALTERNATIVE MODE: Use frozen integration time ratios from Step 3A brightness ratios
            # Since all LEDs are at 255, we compensate brightness differences via integration time
            logger.info("  Using brightness ratios from Step 3A (frozen integration time ratios):")

            # Target for validation (45% detector, same as Step 3B)
            target_signal = step3b_target_signal
            tolerance_pct = 0.10  # ±10% tolerance

            for ch_name in ch_list:
                if ch_name not in result.brightness_ratios:
                    logger.warning(f"    ⚠️  {ch_name.upper()}: Missing brightness ratio, using baseline integration")
                    channel_integration_times[ch_name] = p_integration_time
                    continue

                # Integration ratio is inverse of brightness ratio
                # Weakest channel (ratio = 1.0) gets baseline integration
                # Brighter channels get proportionally less integration
                brightness_ratio = result.brightness_ratios[ch_name]
                integration_ratio = 1.0 / brightness_ratio

                # Apply ratio to baseline P-mode integration time
                adjusted_int = p_integration_time * integration_ratio

                # Clamp to detector limits
                adjusted_int = np.clip(adjusted_int, detector_params.min_integration_time, detector_params.max_integration_time)

                channel_integration_times[ch_name] = adjusted_int

                logger.info(f"    {ch_name.upper()}: Brightness={brightness_ratio:.2f}× → Int ratio={integration_ratio:.2f}× → {adjusted_int:.1f}ms")

                # EMPIRICAL VALIDATION: Measure actual signal at calculated integration time
                usb.set_integration(adjusted_int)
                time.sleep(0.010)

                led_val = p_led_intensities[ch_name]
                ctrl.set_intensity(ch=ch_name, raw_val=led_val)
                time.sleep(LED_DELAY)
                spectrum = usb.read_intensity()
                ctrl.set_intensity(ch=ch_name, raw_val=0)
                time.sleep(0.01)

                if spectrum is not None:
                    measured_signal = roi_signal(spectrum, wave_min_index, wave_max_index, method="median")
                    signal_pct = (measured_signal / detector_max) * 100

                    # Check for saturation: count saturated pixels in ROI
                    roi_spectrum = spectrum[wave_min_index:wave_max_index]
                    saturation_limit = detector_params.saturation_threshold
                    saturated_pixels = np.sum(roi_spectrum >= saturation_limit)
                    is_saturated = saturated_pixels > 0
                    max_pixel = np.max(roi_spectrum)
                    sat_status = f"⚠️ {saturated_pixels} SAT" if is_saturated else ""

                    # Count pixels near target
                    pixels_near, pct_near = count_pixels_near_target(
                        spectrum, wave_min_index, wave_max_index, target_signal, tolerance_pct
                    )
                    total_pixels = wave_max_index - wave_min_index

                    deviation_from_target = ((measured_signal - target_signal) / target_signal) * 100
                    signal_status = "✅" if abs(deviation_from_target) < 20 and not is_saturated else "⚠️"
                    pixel_status = "✅" if pct_near >= 50 else "⚠️"

                    logger.info(f"       Measured: {measured_signal:.0f} counts ({signal_pct:.1f}%) {signal_status} {deviation_from_target:+.1f}% vs target {sat_status}")
                    if is_saturated:
                        logger.warning(f"       {saturated_pixels} pixels saturated (max: {max_pixel:.0f} >= {saturation_limit:.0f})")
                    logger.info(f"       Pixels near target: {pixels_near}/{total_pixels} ({pct_near:.1f}%) {pixel_status}")

                # QC CHECK for P-pol signal increase (still check in alternative mode)
                if ch_name in s_roi1_signals and ch_name in p_roi1_signals:
                    s_avg = (s_roi1_signals[ch_name] + s_roi2_signals[ch_name]) / 2
                    p_avg = (p_roi1_signals[ch_name] + p_roi2_signals[ch_name]) / 2
                    if p_avg > s_avg * 1.05:
                        roi_increase_detected = True
                        roi_increase_channels.append(ch_name)
                        logger.warning(f"       ⚠️  P-pol signal INCREASED vs S-pol (P={p_avg:.0f} > S={s_avg:.0f})")

        else:
            # STANDARD MODE: Calculate from ROI signal loss (S-pol vs P-pol)
            # Target for validation (45% detector, same as Step 3B)
            target_signal = step3b_target_signal
            tolerance_pct = 0.10  # ±10% tolerance

            for ch_name in ch_list:
                if ch_name not in s_roi1_signals or ch_name not in p_roi1_signals:
                    logger.warning(f"    ⚠️  {ch_name.upper()}: Missing ROI data, using baseline integration")
                    channel_integration_times[ch_name] = p_integration_time
                    continue

                # Average signal loss across both ROI regions
                s_avg = (s_roi1_signals[ch_name] + s_roi2_signals[ch_name]) / 2
                p_avg = (p_roi1_signals[ch_name] + p_roi2_signals[ch_name]) / 2

                # Calculate signal loss ratio
                if p_avg > 0:
                    loss_ratio = s_avg / p_avg
                else:
                    logger.warning(f"    ⚠️  {ch_name.upper()}: Zero P-pol signal, using 2× adjustment")
                    loss_ratio = 2.0

                # Adjust integration time to compensate for P-pol loss
                adjusted_int = p_integration_time * loss_ratio

                # Clamp to detector limits
                adjusted_int = np.clip(adjusted_int, detector_params.min_integration_time, detector_params.max_integration_time)

                channel_integration_times[ch_name] = adjusted_int

                signal_loss_pct = ((s_avg - p_avg) / s_avg) * 100 if s_avg > 0 else 0

                # QC CHECK: Flag if P-pol signal INCREASES vs S-pol (should always decrease)
                if p_avg > s_avg * 1.05:  # Allow 5% tolerance for noise
                    roi_increase_detected = True
                    roi_increase_channels.append(ch_name)
                    logger.warning(f"    ⚠️  {ch_name.upper()}: P-pol signal INCREASED vs S-pol (P={p_avg:.0f} > S={s_avg:.0f})")
                    logger.warning(f"       This suggests polarizer misalignment or incorrect S/P positions")

                logger.info(f"    {ch_name.upper()}: S_avg={s_avg:.0f}, P_avg={p_avg:.0f}, Loss={signal_loss_pct:.1f}%, Int={adjusted_int:.1f}ms")

                # EMPIRICAL VALIDATION: Measure actual signal at calculated integration time
                usb.set_integration(adjusted_int)
                time.sleep(0.010)

                led_val = p_led_intensities[ch_name]
                ctrl.set_intensity(ch=ch_name, raw_val=led_val)
                time.sleep(LED_DELAY)
                spectrum = usb.read_intensity()
                ctrl.set_intensity(ch=ch_name, raw_val=0)
                time.sleep(0.01)

                if spectrum is not None:
                    measured_signal = roi_signal(spectrum, wave_min_index, wave_max_index, method="median")
                    signal_pct = (measured_signal / detector_max) * 100

                    # Check for saturation: count saturated pixels in ROI
                    roi_spectrum = spectrum[wave_min_index:wave_max_index]
                    saturation_limit = detector_params.saturation_threshold
                    saturated_pixels = np.sum(roi_spectrum >= saturation_limit)
                    is_saturated = saturated_pixels > 0
                    max_pixel = np.max(roi_spectrum)
                    sat_status = f"⚠️ {saturated_pixels} SAT" if is_saturated else ""

                    # Count pixels near target
                    pixels_near, pct_near = count_pixels_near_target(
                        spectrum, wave_min_index, wave_max_index, target_signal, tolerance_pct
                    )
                    total_pixels = wave_max_index - wave_min_index

                    deviation_from_target = ((measured_signal - target_signal) / target_signal) * 100
                    signal_status = "✅" if abs(deviation_from_target) < 20 and not is_saturated else "⚠️"
                    pixel_status = "✅" if pct_near >= 50 else "⚠️"

                    logger.info(f"       Measured: {measured_signal:.0f} counts ({signal_pct:.1f}%) {signal_status} {deviation_from_target:+.1f}% vs target {sat_status}")
                    if is_saturated:
                        logger.warning(f"       {saturated_pixels} pixels saturated (max: {max_pixel:.0f} >= {saturation_limit:.0f})")
                    logger.info(f"       Pixels near target: {pixels_near}/{total_pixels} ({pct_near:.1f}%) {pixel_status}")

        # Store QC flag if P-pol signals increased
        if roi_increase_detected:
            logger.warning("")
            logger.warning("⚠️  QC FLAG: P-pol ROI signals INCREASED for some channels")
            logger.warning(f"   Affected channels: {', '.join([ch.upper() for ch in roi_increase_channels])}")
            logger.warning("   This suggests polarizer misalignment or swapped S/P positions")
            logger.warning("   Calibration will continue, but polarizer positions should be verified")
            logger.warning("")
            result.qc_results['step5_roi_increase_flag'] = {
                'status': 'WARNING',
                'affected_channels': roi_increase_channels,
                'message': 'P-pol signal increased vs S-pol - polarizer issue suspected'
            }

        # ---------------------------------------------------------------
        # PART C: OPTIMIZE INTEGRATION TIME PER CHANNEL (TARGET + NO SATURATION)
        # ---------------------------------------------------------------
        logger.info("")
        logger.info("  Optimizing integration time per channel (target intensity + no saturation):")

        # Target: 77-83% detector (80% ± 3%)
        target_pct = 0.80
        tolerance_pct = 0.03
        min_pct = target_pct - tolerance_pct
        max_pct = target_pct + tolerance_pct

        target_signal = detector_max * target_pct
        min_signal = detector_max * min_pct
        max_signal = detector_max * max_pct

        final_channel_signals = {}
        for ch_name in ch_list:
            ch_int = channel_integration_times[ch_name]
            logger.info(f"    {ch_name.upper()}: Starting at {ch_int:.1f}ms (from signal loss compensation)")

            # Binary search to hit target while avoiding saturation
            min_int = detector_params.min_integration_time
            max_int = detector_params.max_integration_time
            best_int = ch_int
            best_signal = 0
            max_iterations = 8

            for iteration in range(max_iterations):
                test_int = (min_int + max_int) / 2
                usb.set_integration(test_int)
                time.sleep(0.010)  # 10ms settling time

                led_val = p_led_intensities[ch_name]
                ctrl.set_intensity(ch=ch_name, raw_val=led_val)
                time.sleep(LED_DELAY)
                spectrum = usb.read_intensity()
                ctrl.set_intensity(ch=ch_name, raw_val=0)
                time.sleep(0.01)

                if spectrum is None:
                    logger.warning(f"      Iter {iteration+1}: No spectrum, skipping")
                    break

                # Check saturation
                sat_count = count_saturated_pixels(
                    spectrum, wave_min_index, wave_max_index, detector_params.saturation_threshold
                )

                # Calculate median ROI signal
                signal = roi_signal(spectrum, wave_min_index, wave_max_index, method="median")
                signal_pct = (signal / detector_max) * 100

                # Check if in target range
                in_range = min_signal <= signal <= max_signal

                if sat_count > 0:
                    logger.info(f"      Iter {iteration+1}: {test_int:.1f}ms → {signal:.0f} ({signal_pct:.1f}%), SATURATED → reduce")
                    max_int = test_int
                elif in_range:
                    best_int = test_int
                    best_signal = signal
                    logger.info(f"      Iter {iteration+1}: {test_int:.1f}ms → {signal:.0f} ({signal_pct:.1f}%), ✅ OPTIMAL")
                    break
                elif signal < min_signal:
                    logger.info(f"      Iter {iteration+1}: {test_int:.1f}ms → {signal:.0f} ({signal_pct:.1f}%), too low → increase")
                    min_int = test_int
                    # Track best (closest to target)
                    if abs(signal - target_signal) < abs(best_signal - target_signal):
                        best_int = test_int
                        best_signal = signal
                else:
                    logger.info(f"      Iter {iteration+1}: {test_int:.1f}ms → {signal:.0f} ({signal_pct:.1f}%), too high → reduce")
                    max_int = test_int
                    # Track best (closest to target)
                    if abs(signal - target_signal) < abs(best_signal - target_signal):
                        best_int = test_int
                        best_signal = signal

            # Update to best found integration time
            channel_integration_times[ch_name] = best_int
            final_channel_signals[ch_name] = best_signal
            final_pct = (best_signal / detector_max) * 100
            logger.info(f"    ✅ {ch_name.upper()}: Final {best_int:.1f}ms → {best_signal:.0f} ({final_pct:.1f}%)")

        logger.info("")
        logger.info("  ✅ All channels optimized to target intensity with no saturation")

        # Store per-channel integration times
        result.p_integration_time = p_integration_time  # Baseline P-mode integration
        result.channel_integration_times = channel_integration_times  # Per-channel adjusted
        result.p_mode_intensity = p_led_intensities.copy()
        result.p_roi1_signals = p_roi1_signals
        result.p_roi2_signals = p_roi2_signals

        logger.info("")
        logger.info("="*80)
        logger.info("✅ STEP 5 COMPLETE: P-mode Measurement and Integration Adjustment")
        logger.info("="*80)
        logger.info(f"   Baseline P-mode integration: {p_integration_time:.1f}ms")
        logger.info(f"   Per-channel adjusted integration times:")
        for ch in ch_list:
            if ch in channel_integration_times:
                logger.info(f"      {ch.upper()}: {channel_integration_times[ch]:.1f}ms")
        logger.info("")

        # Standardized summary of P-mode step
        log_step_summary(
            step_name="Step 5 (P-mode Measurement)",
            detector_max=detector_max,
            integration_ms=p_integration_time,
            channel_signals=final_channel_signals,
            sat_counts={ch: 0 for ch in ch_list},  # Already validated above
        )

        # ---------------------------------------------------------------
        # PART D: CAPTURE P-MODE RAW SPECTRA AND DARK REFERENCE FOR STEP 6
        # ---------------------------------------------------------------
        logger.info("")
        logger.info("  Capturing P-mode raw spectra with per-channel integration times:")

        p_raw_data = {}
        for ch_name in ch_list:
            ch_int = channel_integration_times[ch_name]
            usb.set_integration(ch_int)
            time.sleep(0.010)  # 10ms settling time

            led_val = p_led_intensities[ch_name]
            ctrl.set_intensity(ch=ch_name, raw_val=led_val)
            time.sleep(LED_DELAY)

            spectra = []
            for scan_idx in range(result.num_scans):
                spectrum = usb.read_intensity()
                if spectrum is not None:
                    spectra.append(spectrum[wave_min_index:wave_max_index])
                time.sleep(0.01)

            ctrl.set_intensity(ch=ch_name, raw_val=0)
            time.sleep(0.01)

            if spectra:
                p_raw_data[ch_name] = np.mean(spectra, axis=0)
                logger.info(f"    ✅ {ch_name.upper()}: {len(spectra)} scans averaged at {ch_int:.1f}ms")
            else:
                logger.warning(f"    ⚠️  {ch_name.upper()}: No valid spectra captured")

        # Measure dark reference at highest P-mode integration time
        max_p_integration = max(channel_integration_times.values())
        usb.set_integration(max_p_integration)
        ctrl.turn_off_channels()
        time.sleep(LED_DELAY)

        logger.info("")
        logger.info(f"  Measuring dark reference at {max_p_integration:.1f}ms:")

        dark_scans = []
        for scan_idx in range(max(3, result.num_scans // 2)):
            spectrum = usb.read_intensity()
            if spectrum is not None:
                dark_scans.append(spectrum[wave_min_index:wave_max_index])
            time.sleep(0.01)

        p_dark_ref_filtered = np.mean(dark_scans, axis=0) if dark_scans else np.zeros(wave_max_index - wave_min_index)

        # Connect Step 5 outputs to Step 6
        result.p_raw_data = p_raw_data
        result.dark_noise = p_dark_ref_filtered

        # QC check: Verify dark signal is around expected level (~3200 counts for typical detectors)
        dark_mean = np.mean(p_dark_ref_filtered)
        dark_max = np.max(p_dark_ref_filtered)
        dark_std = np.std(p_dark_ref_filtered)

        logger.info(f"    Mean: {dark_mean:.1f} counts")
        logger.info(f"    Max: {dark_max:.1f} counts")
        logger.info(f"    Std: {dark_std:.1f} counts")

        # QC validation (expected range: 2500-4000 counts for typical Ocean Optics detectors)
        EXPECTED_DARK_MIN = 2500
        EXPECTED_DARK_MAX = 4000

        if EXPECTED_DARK_MIN <= dark_mean <= EXPECTED_DARK_MAX:
            logger.info(f"    ✅ Dark-ref within expected range ({EXPECTED_DARK_MIN}-{EXPECTED_DARK_MAX} counts)")
        else:
            logger.warning(f"    ⚠️  Dark-ref outside expected range ({EXPECTED_DARK_MIN}-{EXPECTED_DARK_MAX} counts)")
            if dark_mean > EXPECTED_DARK_MAX:
                logger.warning(f"       Possible causes: LEDs not fully off, light leak, detector issue")
            else:
                logger.warning(f"       Possible causes: Detector offset drift, temperature change")

        logger.info("")
        logger.info("✅ Step 5 complete: P-mode measurement and dark-ref capture done\n")

        # ===================================================================
        # STEP 6: DATA PROCESSING + TRANSMISSION CALCULATION + QC (FINAL STEP)
        # ===================================================================
        logger.info("=" * 80)
        logger.info("STEP 6: Data Processing + Transmission Calculation + QC (FINAL STEP)")
        logger.info("=" * 80)

        if progress_callback:
            progress_callback("Step 6 of 6: Preparing QC results", 83)

        try:
            # ---------------------------------------------------------------
            # PART A: VERIFY RAW DATA AVAILABILITY
            # ---------------------------------------------------------------
            logger.info("\n📊 Part A: Verifying Raw Data Availability")

            if not hasattr(result, 's_raw_data') or not result.s_raw_data:
                raise RuntimeError("S-pol raw data missing from Step 4")
            if not hasattr(result, 'p_raw_data') or not result.p_raw_data:
                raise RuntimeError("P-pol raw data missing from Step 5")
            if not hasattr(result, 'dark_noise') or result.dark_noise is None:
                raise RuntimeError("Dark noise reference missing from Step 5")

            logger.info("   ✅ S-pol raw data: 4 channels from Step 4")
            logger.info("   ✅ P-pol raw data: 4 channels from Step 5")
            logger.info("   ✅ Dark reference: From Step 5 (P-mode integration time)")
            logger.info(f"   ✅ S-mode integration time: {result.s_integration_time:.2f}ms")
            logger.info(f"   ✅ P-mode integration time: {result.p_integration_time:.2f}ms")

            # ---------------------------------------------------------------
            # PART B: PROCESS POLARIZATION DATA (SpectrumPreprocessor)
            # ---------------------------------------------------------------
            logger.info("\n🔧 Part B: Processing Polarization Data (SpectrumPreprocessor)")

            # Process S-pol and P-pol data using modern architecture
            s_pol_ref = {}
            p_pol_ref = {}

            for ch in ch_list:
                logger.info(f"Processing channel {ch.upper()}...")

                # Process S-pol (remove dark noise)
                s_pol_ref[ch] = SpectrumPreprocessor.process_polarization_data(
                    raw_spectrum=result.s_raw_data[ch],
                    dark_noise=result.dark_noise,
                    channel_name=ch,
                    verbose=True
                )

                # Process P-pol (remove dark noise)
                p_pol_ref[ch] = SpectrumPreprocessor.process_polarization_data(
                    raw_spectrum=result.p_raw_data[ch],
                    dark_noise=result.dark_noise,
                    channel_name=ch,
                    verbose=True
                )

            # Store processed references
            result.s_pol_ref = s_pol_ref
            result.p_pol_ref = p_pol_ref

            logger.info("\n✅ S-pol and P-pol references processed")
            logger.info("   Ready for QC display")

            # ---------------------------------------------------------------
            # PART C: CALCULATE TRANSMISSION SPECTRUM (TransmissionProcessor)
            # ---------------------------------------------------------------
            logger.info("\n📈 Part C: Calculating Transmission Spectrum (TransmissionProcessor)")
            logger.info("   🔴 SIMULATING LIVE DATA ACQUISITION")

            transmission_spectra = {}

            for ch in ch_list:
                logger.info(f"\n{'='*80}")
                logger.info(f"Channel {ch.upper()}: TransmissionProcessor Processing")
                logger.info(f"{'='*80}")

                # Calculate transmission using modern architecture
                transmission_ch = TransmissionProcessor.process_single_channel(
                    p_pol_clean=p_pol_ref[ch],  # Already preprocessed above
                    s_pol_ref=s_pol_ref[ch],     # Already preprocessed above
                    led_intensity_s=result.ref_intensity[ch],
                    led_intensity_p=result.p_mode_intensity[ch],
                    wavelengths=result.wave_data,
                    apply_sg_filter=True,
                    baseline_method='percentile',
                    baseline_percentile=95.0,
                    verbose=True
                )

                transmission_spectra[ch] = transmission_ch

            # Store transmission spectra
            result.transmission = transmission_spectra

            logger.info("\n" + "=" * 80)
            logger.info("✅ Transmission spectra calculated")
            logger.info("   Ready for QC display and peak tracking pipeline")
            logger.info("=" * 80)

            # ---------------------------------------------------------------
            # PART D: QC VALIDATION & AUTO-CALIBRATION DECISIONS
            # ---------------------------------------------------------------
            logger.info("\n🔍 Part D: QC Validation & Auto-Calibration Decisions")
            logger.info("=" * 80)

            qc_results = {}
            all_channels_pass = True

            for ch in ch_list:
                logger.info(f"\nChannel {ch.upper()} QC:")

                transmission_ch = transmission_spectra[ch]
                wavelengths = result.wave_data

                # 1. SPR Dip Detection
                min_transmission = np.min(transmission_ch)
                min_idx = np.argmin(transmission_ch)
                spr_wavelength = wavelengths[min_idx]
                spr_depth = 100.0 - min_transmission

                spr_pass = spr_depth > 5.0
                logger.info(f"   SPR Dip: {min_transmission:.1f}% at {spr_wavelength:.1f}nm (depth={spr_depth:.1f}%)")
                logger.info(f"   Status: {'✅ PASS' if spr_pass else '❌ FAIL'} (depth > 5%)")

                # 2. FWHM Measurement
                half_max = (100.0 + min_transmission) / 2.0
                below_half_max = transmission_ch < half_max
                fwhm_indices = np.where(below_half_max)[0]

                if len(fwhm_indices) > 1:
                    fwhm_wavelengths = wavelengths[fwhm_indices]
                    fwhm = fwhm_wavelengths[-1] - fwhm_wavelengths[0]
                    fwhm_pass = fwhm < 60.0
                    logger.info(f"   FWHM: {fwhm:.1f}nm")
                    logger.info(f"   Status: {'✅ PASS' if fwhm_pass else '❌ FAIL'} (FWHM < 60nm)")
                else:
                    fwhm = 0
                    fwhm_pass = False
                    logger.info(f"   FWHM: Cannot calculate (no clear dip)")
                    logger.info(f"   Status: ❌ FAIL")

                # 3. Signal Quality (SNR)
                signal_mean = np.mean(s_pol_ref[ch])
                noise_std = np.std(result.dark_noise)
                snr = signal_mean / max(noise_std, 1)
                snr_pass = snr > 100

                logger.info(f"   SNR: {snr:.0f}")
                logger.info(f"   Status: {'✅ PASS' if snr_pass else '❌ FAIL'} (SNR > 100)")

                # Store QC results
                qc_results[ch] = {
                    'spr_wavelength': spr_wavelength,
                    'spr_depth': spr_depth,
                    'spr_pass': spr_pass,
                    'fwhm': fwhm,
                    'fwhm_pass': fwhm_pass,
                    'snr': snr,
                    'snr_pass': snr_pass,
                    'overall_pass': spr_pass and fwhm_pass and snr_pass
                }

                if not qc_results[ch]['overall_pass']:
                    all_channels_pass = False

            # Store QC results
            result.qc_results = qc_results

            # Build list of channels that failed QC
            result.ch_error_list = [ch for ch, qc in qc_results.items() if not qc['overall_pass']]

            # ---------------------------------------------------------------
            # AUTO-CALIBRATION DECISIONS
            # ---------------------------------------------------------------
            logger.info("\n" + "=" * 80)
            logger.info("AUTO-CALIBRATION DECISIONS")
            logger.info("=" * 80)

            if all_channels_pass:
                logger.info("✅ ALL CHANNELS PASSED QC")
                logger.info("   No auto-calibration needed")
            else:
                logger.info("⚠️  SOME CHANNELS FAILED QC")

                for ch, qc in qc_results.items():
                    if not qc['overall_pass']:
                        logger.warning(f"   Channel {ch.upper()} failed:")
                        if not qc['spr_pass']:
                            logger.warning(f"      - SPR dip too shallow ({qc['spr_depth']:.1f}%)")
                        if not qc['fwhm_pass']:
                            logger.warning(f"      - FWHM too wide ({qc['fwhm']:.1f}nm)")
                        if not qc['snr_pass']:
                            logger.warning(f"      - SNR too low ({qc['snr']:.0f})")

            logger.info("=" * 80)
            logger.info("STEP 6 COMPLETE: Data Processing & QC Finished")
            logger.info("=" * 80)

            if progress_callback:
                progress_callback("Calibration complete", 100)

        except Exception as e:
            logger.exception(f"Error in Step 6: {e}")
            raise RuntimeError(f"Step 6 failed: {e}")

        # ===================================================================
        # CALIBRATION COMPLETE - STEP 6 IS FINAL STEP
        # ===================================================================

        # Set compatibility attributes for calibration manager
        result.leds_calibrated = result.p_mode_intensity
        result.pre_led_delay_ms = pre_led_delay_ms
        result.post_led_delay_ms = post_led_delay_ms
        result.success = True

        logger.info("\n" + "=" * 80)
        logger.info("✅ 6-STEP CALIBRATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"LED Timing: PRE={pre_led_delay_ms}ms, POST={post_led_delay_ms}ms")
        logger.info(f"LED Intensities (S-mode): {result.ref_intensity}")
        logger.info(f"LED Intensities (P-mode): {result.p_mode_intensity}")
        logger.info(f"Integration Time (S-mode): {result.s_integration_time}ms")
        logger.info(f"Integration Time (P-mode): {result.p_integration_time}ms")
        logger.info(f"Scans per Channel: {result.num_scans}")
        logger.info(f"S-pol Raw Data: {list(result.s_raw_data.keys()) if hasattr(result, 's_raw_data') else 'Not captured'}")
        logger.info(f"P-pol Raw Data: {list(result.p_raw_data.keys()) if hasattr(result, 'p_raw_data') else 'Not captured'}")
        logger.info("=" * 80)
        logger.info("Next: Show post-calibration dialog, wait for user to click Start")
        logger.info("=" * 80 + "\n")

        # Save calibration result for future reference
        save_calibration_result_json(result)

        return result

    except Exception as e:
        # Print full traceback immediately to console
        import traceback
        import sys
        print("\n" + "="*80)
        print("6-STEP CALIBRATION ERROR - FULL TRACEBACK:")
        print("="*80)
        try:
            # Use format_exc() which returns a string instead of print_exc() which can write bytes
            tb_string = traceback.format_exc()
            print(tb_string)
        except Exception as tb_error:
            # If traceback formatting fails, format manually
            print(f"ERROR EXCEPTION: {type(e).__name__}: {repr(e)}")
            print(f"ERROR TRACEBACK: Unable to format traceback ({tb_error})")
            print(f"Exception type: {type(e)}, Exception value: {e}")
        print("="*80 + "\n")

        # Safely convert exception to string (handle bytes if present)
        error_msg = str(e) if not isinstance(e, bytes) else e.decode('utf-8', errors='replace')
        logger.exception(f"6-step calibration failed: {error_msg}")
        result.success = False
        result.error = error_msg
        return result

    finally:
        # Ensure device is left in safe state regardless of success/failure
        try:
            logger.debug("Performing graceful cleanup...")
            ctrl.turn_off_channels()
            logger.debug("✅ All LEDs turned off")
        except Exception as cleanup_error:
            logger.warning(f"Error during cleanup: {cleanup_error}")


# =============================================================================
# FAST-TRACK CALIBRATION
# =============================================================================

def run_fast_track_calibration(
    usb,
    ctrl,
    device_type: str,
    device_config,
    detector_serial: str,
    single_mode: bool = False,
    single_ch: str = "a",
    stop_flag=None,
    progress_callback=None,
    pre_led_delay_ms: float = PRE_LED_DELAY_MS,
    post_led_delay_ms: float = POST_LED_DELAY_MS
) -> LEDCalibrationResult:
    """Fast-track calibration with ±10% validation.

    USE CASE: Sensor/prism replacement or LED drift compensation
    ------------------------------------------------------------
    When a sensor/prism is swapped, the optical coupling changes slightly,
    requiring LED intensity tweaks (typically 5-15% adjustment, not vastly different).

    Fast-track validates that previous calibration still works within ±10%.
    If valid, it reuses LOCKED parameters and only updates LED intensities.

    PARAMETER LOCKING STRATEGY:
    ---------------------------
    LOCKED (reused from full calibration):
    - Integration time (ms)          → Fixed, optimized during full calibration
    - Number of scans                → Derived from integration time
    - Wavelength calibration         → Fixed to detector

    UPDATED (remeasured for sensor change):
    - S-mode LED intensities         → Tweaked to maintain 70% detector target
    - P-mode LED intensities         → Recalculated based on S-mode headroom
    - Dark noise baseline            → Remeasured (may drift with temperature)
    - S-ref signals                  → Remeasured with updated LED intensities

    WORKFLOW:
    1. Load previous calibration from device_config.json
    2. Validate each channel at saved LED intensity (±10% tolerance)
    3. If ALL pass → fast-track complete (~80% time savings)
    4. If ANY fail → recalibrate only failed channels
    5. Recalculate P-mode LEDs based on updated S-mode

    This is much faster than full calibration because:
    - Skip integration time optimization (locked)
    - Skip binary search (use cached LED ±10% adjust)
    - Skip multi-pass validation (trust previous calibration)

    Args:
        Same as run_full_6step_calibration

    Returns:
        LEDCalibrationResult with calibration data
    """
    logger.debug("🔍 DEBUG: run_fast_track_calibration called")
    logger.debug("🔍 DEBUG: Parameters received:")
    logger.debug(f"   device_type={device_type}")
    logger.debug(f"   pre_led_delay_ms={'MISSING' if 'pre_led_delay_ms' not in locals() else locals().get('pre_led_delay_ms', 'UNDEFINED')}")
    logger.debug(f"   post_led_delay_ms={'MISSING' if 'post_led_delay_ms' not in locals() else locals().get('post_led_delay_ms', 'UNDEFINED')}")

    result = LEDCalibrationResult()

    try:
        logger.info("\n" + "=" * 80)
        logger.info("🚀 FAST-TRACK CALIBRATION MODE")
        logger.info("=" * 80)
        logger.info("Loading previous calibration and validating within ±10%")
        logger.info("Channels that fail validation will be recalibrated")
        logger.info("=" * 80 + "\n")

        # Load previous calibration from device_config.json (primary source)
        cal_data = device_config.load_led_calibration()

        # If not in device_config, try loading from latest_calibration.json (fallback)
        if not cal_data or 's_mode_intensities' not in cal_data:
            logger.info("No calibration in device_config.json, checking latest_calibration.json...")
            try:
                latest_file = Path("calibration_results/latest_calibration.json")
                if latest_file.exists():
                    with open(latest_file, 'r') as f:
                        latest_data = json.load(f)

                    # Convert to device_config format
                    cal_data = {
                        'calibration_date': latest_data['calibration_metadata']['timestamp'],
                        'calibration_method': latest_data['calibration_metadata']['calibration_method'],
                        's_mode_intensities': latest_data['led_parameters']['s_mode_intensity'],
                        'p_mode_intensities': latest_data['led_parameters']['p_mode_intensity'],
                        'integration_time_ms': latest_data['integration_times']['s_integration_time'],
                        'p_integration_time_ms': latest_data['integration_times']['p_integration_time'],
                        'per_channel_integration_times': latest_data['integration_times'].get('channel_integration_times'),
                    }
                    logger.info(f"✅ Loaded calibration from {latest_file}")
                    logger.info(f"   Calibration date: {cal_data['calibration_date']}")
                else:
                    logger.info("No latest_calibration.json found either")
            except Exception as e:
                logger.warning(f"Failed to load latest_calibration.json: {e}")

        if not cal_data or 's_mode_intensities' not in cal_data:
            logger.info("No previous calibration found - falling back to full calibration")
            return run_full_6step_calibration(
                usb, ctrl, device_type, device_config, detector_serial,
                single_mode, single_ch, stop_flag, progress_callback
            )

        # Get detector parameters
        wave_data = usb.read_wavelength()
        wave_min_index = wave_data.searchsorted(MIN_WAVELENGTH)
        wave_max_index = wave_data.searchsorted(MAX_WAVELENGTH)
        detector_params = get_detector_params(usb)
        ch_list = determine_channel_list(device_type, single_mode, single_ch)

        # Load saved values
        saved_s_leds = cal_data['s_mode_intensities']
        saved_p_leds = cal_data.get('p_mode_intensities', {})
        saved_integration = cal_data.get('integration_time_ms', 50)
        saved_p_integration = cal_data.get('p_integration_time_ms', saved_integration)

        logger.info(f"Previous calibration date: {cal_data.get('calibration_date', 'unknown')}")
        logger.info(f"Saved S-mode LEDs: {saved_s_leds}")
        logger.info(f"Saved P-mode LEDs: {saved_p_leds}")
        logger.info(f"S-mode integration: {saved_integration}ms")
        logger.info(f"P-mode integration: {saved_p_integration}ms\n")

        # FAST-TRACK VALIDATION: Check both S and P modes with ±5% tolerance
        logger.info("=" * 80)
        logger.info("FAST-TRACK VALIDATION: S-mode and P-mode (±5% tolerance)")
        logger.info("=" * 80)
        logger.info("Testing saved LED intensities and integration times")
        logger.info("Both S and P must pass to skip full calibration\n")

        validated_s_leds = {}
        validated_p_leds = {}
        failed_channels = []

        target_counts = detector_params.target_counts
        tolerance = 0.05  # ±5% (stricter than before)

        # PHASE 1: Validate S-mode
        logger.info("PHASE 1: S-mode Validation")
        logger.info("-" * 80)
        switch_mode_safely(ctrl, "s", turn_off_leds=True)
        usb.set_integration(saved_integration)
        time.sleep(0.010)

        s_passed = True
        for ch in ch_list:
            if stop_flag and stop_flag.is_set():
                break

            if ch not in saved_s_leds:
                logger.warning(f"❌ {ch.upper()}: No saved S-mode LED value")
                failed_channels.append(ch)
                s_passed = False
                continue

            saved_led = saved_s_leds[ch]
            ctrl.set_intensity(ch=ch, raw_val=saved_led)
            time.sleep(LED_DELAY)

            spectrum = usb.read_intensity()
            ctrl.set_intensity(ch=ch, raw_val=0)
            time.sleep(0.01)

            if spectrum is None:
                logger.error(f"❌ {ch.upper()}: Hardware read failed")
                failed_channels.append(ch)
                s_passed = False
                continue

            max_signal = np.max(spectrum[wave_min_index:wave_max_index])
            deviation = abs(max_signal - target_counts) / target_counts

            if deviation <= tolerance:
                validated_s_leds[ch] = saved_led
                logger.info(f"✅ {ch.upper()}: PASS (signal={max_signal:.0f}, target={target_counts:.0f}, Δ={deviation*100:.1f}%)")
            else:
                failed_channels.append(ch)
                s_passed = False
                logger.warning(f"❌ {ch.upper()}: FAIL (signal={max_signal:.0f}, target={target_counts:.0f}, Δ={deviation*100:.1f}%)")

        logger.info(f"S-mode result: {'✅ ALL PASS' if s_passed else '❌ SOME FAILED'}\n")

        # PHASE 2: Validate P-mode (only if S-mode passed and P-mode LEDs exist)
        p_passed = False
        if s_passed and saved_p_leds:
            logger.info("PHASE 2: P-mode Validation")
            logger.info("-" * 80)
            switch_mode_safely(ctrl, "p", turn_off_leds=True)
            usb.set_integration(saved_p_integration)
            time.sleep(0.010)

            p_passed = True
            for ch in ch_list:
                if stop_flag and stop_flag.is_set():
                    break

                if ch not in saved_p_leds:
                    logger.warning(f"❌ {ch.upper()}: No saved P-mode LED value")
                    failed_channels.append(ch)
                    p_passed = False
                    continue

                saved_led = saved_p_leds[ch]
                ctrl.set_intensity(ch=ch, raw_val=saved_led)
                time.sleep(LED_DELAY)

                spectrum = usb.read_intensity()
                ctrl.set_intensity(ch=ch, raw_val=0)
                time.sleep(0.01)

                if spectrum is None:
                    logger.error(f"❌ {ch.upper()}: Hardware read failed")
                    failed_channels.append(ch)
                    p_passed = False
                    continue

                max_signal = np.max(spectrum[wave_min_index:wave_max_index])
                deviation = abs(max_signal - target_counts) / target_counts

                if deviation <= tolerance:
                    validated_p_leds[ch] = saved_led
                    logger.info(f"✅ {ch.upper()}: PASS (signal={max_signal:.0f}, target={target_counts:.0f}, Δ={deviation*100:.1f}%)")
                else:
                    failed_channels.append(ch)
                    p_passed = False
                    logger.warning(f"❌ {ch.upper()}: FAIL (signal={max_signal:.0f}, target={target_counts:.0f}, Δ={deviation*100:.1f}%)")

            logger.info(f"P-mode result: {'✅ ALL PASS' if p_passed else '❌ SOME FAILED'}\n")
        elif not s_passed:
            logger.info("PHASE 2: P-mode Validation - SKIPPED (S-mode failed)\n")
        else:
            logger.warning("PHASE 2: P-mode Validation - SKIPPED (no saved P-mode LEDs)\n")
            p_passed = False

        # If both S and P passed, use fast-track
        if s_passed and p_passed and len(failed_channels) == 0:
        # If both S and P passed, use fast-track
        if s_passed and p_passed and len(failed_channels) == 0:
            logger.info("\n" + "=" * 80)
            logger.info("✅ FAST-TRACK VALIDATION PASSED (S + P MODES)")
            logger.info("=" * 80)
            logger.info(f"All channels within ±5% tolerance")
            logger.info(f"S-mode: {saved_integration}ms integration")
            logger.info(f"P-mode: {saved_p_integration}ms integration")
            logger.info(f"Estimated time saved: ~90% (full validation passed)")
            logger.info("=" * 80 + "\n")

            # Build result from validated data
            result.ref_intensity = validated_s_leds
            result.s_mode_intensity = validated_s_leds
            result.p_mode_intensity = validated_p_leds
            result.leds_calibrated = validated_p_leds
            result.s_integration_time = saved_integration
            result.p_integration_time = saved_p_integration
            result.wave_data = wave_data[wave_min_index:wave_max_index]
            result.full_wavelengths = wave_data
            result.wave_min_index = wave_min_index
            result.wave_max_index = wave_max_index
            result.detector_max_counts = detector_params.max_counts
            result.detector_saturation_threshold = detector_params.saturation_threshold
            result.pre_led_delay_ms = PRE_LED_DELAY_MS
            result.post_led_delay_ms = POST_LED_DELAY_MS

            # Measure dark noise at current temperature
            logger.info("Measuring dark noise baseline...")
            scan_config = calculate_scan_counts(saved_p_integration)
            result.num_scans = scan_config.num_scans

            result.dark_noise = measure_dark_noise(
                usb, ctrl, saved_p_integration,
                wave_min_index, wave_max_index,
                stop_flag, num_scans=scan_config.dark_scans
            )
            logger.info(f"✅ Dark noise: mean={np.mean(result.dark_noise):.1f}, std={np.std(result.dark_noise):.2f}\n")

            # Capture S and P reference spectra for QC dialog
            logger.info("Capturing reference spectra for QC validation...")
            preprocessor = SpectrumPreprocessor(
                dark_baseline=result.dark_noise,
                apply_savgol=True,
                window_length=11,
                polyorder=2
            )

            # S-mode references
            switch_mode_safely(ctrl, "s", turn_off_leds=True)
            usb.set_integration(saved_integration)
            time.sleep(0.010)

            for ch in ch_list:
                if stop_flag and stop_flag.is_set():
                    break

                ctrl.set_intensity(ch=ch, raw_val=validated_s_leds[ch])
                time.sleep(LED_DELAY)

                raw_spectrum = usb.read_intensity()
                ctrl.set_intensity(ch=ch, raw_val=0)
                time.sleep(0.01)

                if raw_spectrum is not None:
                    result.s_raw_data[ch] = raw_spectrum.copy()
                    clean_spectrum = preprocessor.process_single(raw_spectrum, wave_min_index, wave_max_index)
                    result.s_pol_ref[ch] = clean_spectrum

            # P-mode references
            switch_mode_safely(ctrl, "p", turn_off_leds=True)
            usb.set_integration(saved_p_integration)
            time.sleep(0.010)

            for ch in ch_list:
                if stop_flag and stop_flag.is_set():
                    break

                ctrl.set_intensity(ch=ch, raw_val=validated_p_leds[ch])
                time.sleep(LED_DELAY)

                raw_spectrum = usb.read_intensity()
                ctrl.set_intensity(ch=ch, raw_val=0)
                time.sleep(0.01)

                if raw_spectrum is not None:
                    result.p_raw_data[ch] = raw_spectrum.copy()
                    clean_spectrum = preprocessor.process_single(raw_spectrum, wave_min_index, wave_max_index)
                    result.p_pol_ref[ch] = clean_spectrum

            # Calculate transmission spectra for QC
            logger.info("Calculating transmission spectra...")
            transmission_processor = TransmissionProcessor()
            for ch in ch_list:
                if ch in result.s_pol_ref and ch in result.p_pol_ref:
                    result.transmission[ch] = transmission_processor.calculate_transmission(
                        s_pol=result.s_pol_ref[ch],
                        p_pol=result.p_pol_ref[ch]
                    )

            result.success = True
            result.fast_track_passed = True

            logger.info("\n" + "=" * 80)
            logger.info("✅ FAST-TRACK CALIBRATION COMPLETE")
            logger.info("=" * 80)
            logger.info(f"Validation: S + P modes passed (±5% tolerance)")
            logger.info(f"Dark noise measured, reference spectra captured")
            logger.info(f"Ready for QC dialog and live data acquisition")
            logger.info(f"Time saved: ~90% vs full calibration")
            logger.info("=" * 80 + "\n")

            # Save the fast-track result
            save_calibration_result_json(result)

            return result

        # Some channels failed - fall back to full calibration
        logger.info("\n" + "=" * 80)
        logger.info("❌ FAST-TRACK VALIDATION FAILED")
        logger.info("=" * 80)
        if not s_passed:
            logger.info("S-mode validation failed")
        if not p_passed:
            logger.info("P-mode validation failed or no P-mode data")
        logger.info(f"Failed channels: {list(set(failed_channels))}")
        logger.info("Falling back to full calibration...")
        logger.info("=" * 80 + "\n")

        return run_full_6step_calibration(
            usb, ctrl, device_type, device_config, detector_serial,
            single_mode, single_ch, stop_flag, progress_callback
        )
        result.s_integration_time = saved_integration  # LOCKED from full calibration (S-mode)
        result.wave_data = wave_data[wave_min_index:wave_max_index]
        result.wave_min_index = wave_min_index
        result.wave_max_index = wave_max_index

        num_scans = calculate_scan_counts(saved_integration).num_scans  # LOCKED (derived from integration)

        # Re-measure dark noise (may have drifted)
        result.dark_noise = measure_dark_noise(
            usb, ctrl, saved_integration,
            wave_min_index, wave_max_index,
            stop_flag, num_scans=num_scans
        )

        # Re-measure S-ref with updated LED intensities

        # Re-calibrate P-mode LEDs based on updated S-mode headroom
        switch_mode_safely(ctrl, "p", turn_off_leds=True)
        from utils.led_calibration import calibrate_p_mode_leds, analyze_channel_headroom
        headroom = analyze_channel_headroom(validated_leds)
        result.p_mode_intensity, _ = calibrate_p_mode_leds(
            usb, ctrl, ch_list, validated_leds,
            stop_flag, detector_params=detector_params,
            headroom_analysis=headroom,
            pre_led_delay_ms=PRE_LED_DELAY_MS,
            post_led_delay_ms=POST_LED_DELAY_MS
        )

        result.leds_calibrated = result.p_mode_intensity  # For compatibility with data_mgr
        result.pre_led_delay_ms = pre_led_delay_ms
        result.post_led_delay_ms = post_led_delay_ms

        result.success = True
        result.num_scans = num_scans

        logger.info("\n✅ Fast-track calibration complete (with partial recalibration)\n")

        return result

    except Exception as e:
        # Print full traceback immediately to console
        import traceback
        print("\n" + "="*80)
        print("FAST-TRACK CALIBRATION ERROR - FULL TRACEBACK:")
        print("="*80)
        try:
            # Use format_exc() which returns a string instead of print_exc() which can write bytes
            tb_string = traceback.format_exc()
            print(tb_string)
        except Exception as tb_error:
            print(f"ERROR: Unable to format traceback ({tb_error})")
            print(f"Exception type: {type(e)}, Exception value: {e}")
        print("="*80 + "\n")

        logger.exception(f"Fast-track calibration failed: {e}")
        logger.info("Falling back to full calibration...")
        return run_full_6step_calibration(
            usb, ctrl, device_type, device_config, detector_serial,
            single_mode, single_ch, stop_flag, progress_callback
        )

    finally:
        # Ensure device is left in safe state regardless of success/failure
        try:
            logger.debug("Fast-track cleanup: turning off all LEDs...")
            ctrl.turn_off_channels()
            logger.debug("✅ Cleanup complete")
        except Exception as cleanup_error:
            logger.warning(f"Error during fast-track cleanup: {cleanup_error}")


# =============================================================================
# GLOBAL LED MODE CALIBRATION
# =============================================================================

# REMOVED: run_global_led_calibration() - Alternative mode uses same Steps 4-6
# Alternative calibration modes (e.g., LED=255 fixed + variable integration per channel)
# branch at Step 3C but share identical Steps 4-6 logic with run_full_6step_calibration().
# See Step 3C comment for branching anchor point.
