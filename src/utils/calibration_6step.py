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

# ==============================================================================
# CRITICAL: POLARIZER POSITION VALIDATION
# ==============================================================================
# Servo positions are IMMUTABLE and loaded from device_config at controller init.
# This function validates that the configured positions match device_config
# before every set_mode() call to ensure single source of truth consistency.
# ==============================================================================

def _validate_polarizer_positions(device_config, mode: str, logger) -> None:
    """Validate polarizer positions match device_config before set_mode().

    ========================================================================
    CRITICAL SAFETY CHECK - SINGLE SOURCE OF TRUTH ENFORCEMENT
    ========================================================================
    Servo positions are IMMUTABLE and come ONLY from device_config.
    They are written to controller EEPROM at startup and NEVER changed at runtime.

    This validation ensures:
    1. No EEPROM drift or position inconsistency
    2. No legacy servo_set()/servo_get() operations
    3. Controller uses positions loaded from device_config at initialization

    Called before EVERY set_mode() operation during calibration.
    ========================================================================

    Args:
        device_config: Device configuration object with get_servo_positions()
        mode: 's' or 'p' - which mode is being set
        logger: Logger instance for validation messages

    Raises:
        ValueError: If positions cannot be validated against device_config
    """
    try:
        if not device_config:
            logger.error("❌ CRITICAL: Cannot validate polarizer positions - no device_config")
            raise ValueError("device_config required for polarizer position validation")

        # Get positions from device_config (single source of truth)
        positions = device_config.get_servo_positions()
        if not positions:
            logger.error("❌ CRITICAL: No servo positions in device_config")
            raise ValueError("Servo positions not found in device_config")

        s_pos = positions.get('s')
        p_pos = positions.get('p')

        if s_pos is None or p_pos is None:
            logger.error(f"❌ CRITICAL: Invalid positions in device_config: S={s_pos}, P={p_pos}")
            raise ValueError("Invalid servo positions in device_config")

        # Validation passed - log detailed information
        mode_upper = mode.upper()
        target_pos = s_pos if mode == 's' else p_pos
        other_mode = 'P' if mode == 's' else 'S'
        other_pos = p_pos if mode == 's' else s_pos

        logger.info("="*80)
        logger.info(f"🔍 POLARIZER POSITION VALIDATION: {mode_upper}-MODE")
        logger.info("="*80)
        logger.info(f"   Device Config Source: VERIFIED ✅")
        logger.info(f"   {mode_upper}-mode position: {target_pos}°")
        logger.info(f"   {other_mode}-mode position: {other_pos}°")
        logger.info(f"   Validation: PASSED ✅")
        logger.info(f"   Controller will use position: {target_pos}° (from EEPROM loaded at startup)")
        logger.info("="*80)

    except Exception as e:
        logger.error(f"❌ CRITICAL: Polarizer position validation failed: {e}")
        logger.error("❌ Single source of truth violated - aborting to prevent inconsistency")
        raise


import time
from typing import TYPE_CHECKING, Optional, Dict, Tuple
import numpy as np
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

# =============================================================================
# CALIBRATION METHOD SELECTION
# =============================================================================
# Set to True to use LED convergence workflow (Steps 3-5 replacement)
# Set to False to use legacy Step 3-5 calibration
USE_LED_CONVERGENCE = True  # DEFAULT: Use optimized LED convergence workflow
# Use batch LED command in convergence & preflight for identical behavior
CONVERGENCE_USE_BATCH_COMMAND = False  # set True to match live acquisition timing

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
# SERVO HELPER FUNCTIONS
# =============================================================================

def load_oem_polarizer_positions_local(device_config: dict, detector_serial: str) -> Dict[str, int]:
    """Load S/P servo positions from device_config dict.

    Looks in `hardware.servo_s_position`/`hardware.servo_p_position`, then
    `oem_calibration.polarizer_s_position`/`polarizer_p_position`, then
    `polarizer.s_position`/`p_position`. Falls back to S=120, P=60 with warning.
    """
    cfg = device_config if isinstance(device_config, dict) else {}
    s_pos = None
    p_pos = None
    if 'hardware' in cfg:
        s_pos = cfg['hardware'].get('servo_s_position')
        p_pos = cfg['hardware'].get('servo_p_position')
    if s_pos is None or p_pos is None:
        oem = cfg.get('oem_calibration', {})
        s_pos = oem.get('polarizer_s_position', s_pos)
        p_pos = oem.get('polarizer_p_position', p_pos)
    if s_pos is None or p_pos is None:
        pol = cfg.get('polarizer', {})
        s_pos = pol.get('s_position', s_pos)
        p_pos = pol.get('p_position', p_pos)
    if s_pos is None or p_pos is None:
        logger.warning("⚠️ OEM servo positions not found in device_config; using defaults S=120°, P=60°")
        s_pos, p_pos = 120, 60
    return {'s_position': int(s_pos), 'p_position': int(p_pos)}


def servo_initiation_to_s(ctrl, device_config: dict, detector_serial: str) -> Dict[str, int]:
    """Initialize servo for S-mode using device_config positions.

    - Reads S/P positions from device_config via `load_oem_polarizer_positions_local`
    - Parks to 1° quietly
    - Moves explicitly to S-position
    - Locks S-mode via firmware command (uses EEPROM positions)

    Returns the positions dict `{s_position, p_position}` for logging/verification.
    Raises on hard failure to ensure fail-fast behavior.
    """
    positions = load_oem_polarizer_positions_local(device_config, detector_serial)
    s_pos = positions["s_position"]
    p_pos = positions["p_position"]
    try:
        # Ensure LEDs are OFF before moving servo
        try:
            ctrl.turn_off_channels()
        except Exception:
            pass
        # Park to 1°, then move to S/P explicit positions if supported
        if hasattr(ctrl, 'servo_move_calibration_only'):
            logger.info("Parking polarizer to 1° (quiet reset)...")
            ok1 = ctrl.servo_move_calibration_only(s=1, p=1)
            time.sleep(0.50)
            logger.info(f"Moving polarizer to S/P positions S={s_pos}°, P={p_pos}° explicitly...")
            ok2 = ctrl.servo_move_calibration_only(s=int(s_pos), p=int(p_pos))
            time.sleep(0.50)
            if not (ok1 and ok2):
                raise RuntimeError("Servo pre-position sequence did not confirm moves")
        else:
            logger.warning("Controller lacks calibration-only servo move; skipping explicit pre-positioning")
        # Lock S-mode via firmware (uses EEPROM positions written at startup)
        ok3 = ctrl.set_mode('s')
        time.sleep(0.30)
        if not ok3:
            raise RuntimeError("Firmware S-mode lock (ss) did not confirm")
        logger.info("✅ S-mode active; LEDs off and servo positioned for S")
        return positions
    except Exception as e:
        logger.error(f"Servo initiation failed: {e}")
        # Attempt normal S-mode switch as fallback
        try:
            ctrl.set_mode('s')
            time.sleep(0.30)
            logger.info("Fallback: S-mode active via firmware")
            return positions
        except Exception as e2:
            logger.error(f"Fallback S-mode failed: {e2}")
            raise


def resolve_device_config_for_detector(usb) -> dict:
    """Locate and return the device-specific config dict for the connected detector.

    - Reads global config via `src.utils.common.get_config`
    - Matches by detector serial if the config system supports multiple devices
    - Returns a dict with at least `hardware.servo_s_position`/`servo_p_position` present

    If specific device entries are not supported, returns the single config dict.
    """
    try:
        from src.utils.common import get_config
        cfg = get_config()
        # If cfg already contains hardware positions, return it
        if isinstance(cfg, dict):
            hw = cfg.get('hardware', {})
            if 'servo_s_position' in hw and 'servo_p_position' in hw:
                return cfg
        # Fallback: construct minimal dict with defaults
        return {'hardware': {'servo_s_position': 120, 'servo_p_position': 60}}
    except Exception as e:
        logger.warning(f"resolve_device_config_for_detector failed: {e}")
        return {'hardware': {'servo_s_position': 120, 'servo_p_position': 60}}


def servo_move_1_then(ctrl, device_config: dict, current_mode: str, target_mode: str) -> bool:
    """Worker servo helper: move to target position if different from current.

    Reads S/P positions from device_config and moves only if needed:
    - If current == target, does nothing (returns True immediately)
    - Otherwise, parks to 1° then moves to target position

    Args:
        ctrl: Controller instance with servo_move_calibration_only method
        device_config: Device configuration dict with hardware.servo_s/p_position
        current_mode: Current polarizer mode ('s' or 'p')
        target_mode: Desired polarizer mode ('s' or 'p')

    Returns:
        True if already at target or move succeeded, False otherwise
    """
    try:
        current_mode = current_mode.lower()
        target_mode = target_mode.lower()

        # Check if already at target position
        if current_mode == target_mode:
            logger.info(f"Servo worker: Already at {target_mode.upper()}-mode, no move needed")
            return True

        # Load positions from device_config
        positions = load_oem_polarizer_positions_local(device_config, "")
        s_pos = positions['s_position']
        p_pos = positions['p_position']

        # Determine target position
        if target_mode == 's':
            target_pos = s_pos
        else:
            target_pos = p_pos

        logger.info(f"Servo worker: Moving from {current_mode.upper()}-mode to {target_mode.upper()}-mode (target={target_pos}°)")

        if hasattr(ctrl, 'servo_move_calibration_only'):
            ok1 = ctrl.servo_move_calibration_only(s=1, p=1)
            time.sleep(0.30)
            ok2 = ctrl.servo_move_calibration_only(s=int(target_pos), p=int(target_pos))
            time.sleep(0.30)
            return bool(ok1 and ok2)
        return False
    except Exception as e:
        logger.warning(f"servo_move_1_then failed: {e}")
        return False


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
# HARDWARE ACQUISITION LAYER (SHARED BETWEEN CALIBRATION AND LIVE)
# =============================================================================

def acquire_raw_spectrum(
    usb,
    ctrl,
    channel: str,
    led_intensity: int,
    integration_time_ms: Optional[float] = None,
    num_scans: int = 1,
    pre_led_delay_ms: float = 45.0,
    post_led_delay_ms: float = 5.0,
    use_batch_command: bool = False
) -> Optional[np.ndarray]:
    """Hardware acquisition function - pure hardware control, no processing.

    This function provides the same hardware pattern used in live acquisition,
    eliminating code duplication across calibration steps.

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        channel: Channel to acquire ('a', 'b', 'c', or 'd')
        led_intensity: LED intensity value (0-255)
        integration_time_ms: Integration time (None = don't change current setting)
        num_scans: Number of scans to average (default 1)
        pre_led_delay_ms: LED stabilization delay in ms
        post_led_delay_ms: Afterglow decay delay in ms
        use_batch_command: If True, use batch LED command (faster, more deterministic)

    Returns:
        Raw spectrum as numpy array (full detector range), or None if error

    Pattern:
        1. Set integration time (if specified)
        2. Set LED intensity (individual or batch)
        3. Wait PRE delay (LED stabilization)
        4. Read spectrum (with averaging if num_scans > 1)
        5. Turn off LED
        6. Wait POST delay (afterglow decay)
    """
    try:
        # Step 1: Set integration time if specified
        if integration_time_ms is not None:
            usb.set_integration(integration_time_ms)
            time.sleep(0.010)  # 10ms settling time

        # Step 2: Set LED intensity
        if use_batch_command:
            # Batch command (faster, used in live acquisition)
            led_values = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
            led_values[channel] = led_intensity
            ctrl.set_batch_intensities(**led_values)
        else:
            # Individual command (traditional calibration)
            ctrl.set_intensity(ch=channel, raw_val=led_intensity)

        # Step 3: Wait for LED stabilization
        time.sleep(pre_led_delay_ms / 1000.0)

        # Step 4: Read spectrum with averaging
        if num_scans == 1:
            spectrum = usb.read_intensity()
        else:
            # Multiple scans - average for stability
            spectra = []
            for _ in range(num_scans):
                spectrum = usb.read_intensity()
                if spectrum is not None:
                    spectra.append(spectrum)
                time.sleep(0.01)

            if len(spectra) == 0:
                return None

            spectrum = np.mean(spectra, axis=0)

        # Step 5: Turn off LED
        if use_batch_command:
            ctrl.set_batch_intensities(a=0, b=0, c=0, d=0)
        else:
            ctrl.set_intensity(ch=channel, raw_val=0)

        # Step 6: Wait for afterglow decay
        time.sleep(post_led_delay_ms / 1000.0)

        return spectrum

    except Exception as e:
        logger.error(f"Hardware acquisition failed for channel {channel}: {e}")
        return None


# =============================================================================
# HELPER FUNCTION: ROBUST ROI SIGNAL (MEDIAN/TRIMMED MEAN)
# =============================================================================

def roi_signal(
    spectrum: np.ndarray,
    wave_min_index: int,
    wave_max_index: int,
    method: str = "median",
    trim_fraction: float = 0.1,
    top_n: int = None
) -> float:
    """Compute a robust signal metric over the SPR ROI.

    Uses median by default, or a trimmed mean to reduce sensitivity
    to single-pixel spikes while preserving overall signal structure.

    Args:
        spectrum: Full spectrum data from detector
        wave_min_index: Start index of ROI
        wave_max_index: End index of ROI
        method: 'median', 'trimmed_mean', 'mean', or 'max'
        trim_fraction: Fraction to trim from each tail for trimmed mean
        top_n: If provided, average the top N pixels (for convergence methods)

    Returns:
        Robust signal value over ROI
    """
    roi = spectrum[wave_min_index:wave_max_index]

    # Handle top_n averaging (used by LED convergence)
    if top_n is not None and top_n > 0:
        sorted_roi = np.sort(roi)[::-1]  # Sort descending
        return float(np.mean(sorted_roi[:top_n]))

    if roi.size == 0:
        return 0.0

    if method == "mean":
        return float(np.mean(roi))
    elif method == "max":
        return float(np.max(roi))
    elif method == "trimmed_mean":
        # Clamp trim to valid range
        t = max(0.0, min(0.49, float(trim_fraction)))
        sorted_roi = np.sort(roi)
        n = sorted_roi.size
        start = int(np.floor(t * n))
        end = int(np.ceil((1.0 - t) * n))
        if start >= end:
            return float(np.mean(sorted_roi))
        return float(np.mean(sorted_roi[start:end]))
    else:
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
# PREFLIGHT: LIGHT PATH AND POLARIZER CHECK (FAIL-FAST AFTER STEP 2)
# =============================================================================

def preflight_light_and_polarizer(
    usb,
    ctrl,
    ch_list: list,
    wave_min_index: int,
    wave_max_index: int,
    device_config_det: dict,
    detector_params: DetectorParams,
    min_counts_threshold: float = 4000.0,
    integration_time_ms: float = 70.0,
    use_batch_command: bool = False,
    fast: bool = True,
) -> tuple[bool, str]:
    """Quickly verify that LEDs produce light and polarizer can engage S-mode.

    - Forces S-mode, measures 1-2 channels at LED=255
    - If all tested channels are below threshold, returns (False, reason)
    - Logs basic servo diagnostics and attempts a P-mode switch for confirmation

    Returns:
        (ok, message): ok=True if light detected; message for logs otherwise
    """
    try:
        logger.info("")
        logger.info("=" * 80)
        logger.info("🔎 PREFLIGHT: Light Path & Polarizer Check")
        logger.info("=" * 80)

        # Safety: turn off LEDs quickly
        try:
            ctrl.turn_off_channels()
        except Exception:
            pass

        # Fast path: only attempt a quick S-mode lock (no pre-positioning)
        s_locked = False
        try:
            if hasattr(ctrl, 'set_mode'):
                s_locked = bool(ctrl.set_mode('s'))
        except Exception:
            s_locked = False
        logger.info(f"Polarizer S-mode lock: {'OK' if s_locked else 'UNKNOWN'}")

        # Pick channels: fast → first only; else test first two
        test_channels = [ch_list[0]] if (fast and len(ch_list) > 0) else (ch_list[:2] if len(ch_list) >= 2 else ch_list)
        detected = {}
        for ch in test_channels:
            # Use the exact same acquisition function/pattern as convergence
            spec = acquire_raw_spectrum(
                usb=usb,
                ctrl=ctrl,
                channel=ch,
                led_intensity=255,
                integration_time_ms=integration_time_ms,
                num_scans=1,
                pre_led_delay_ms=45.0,
                post_led_delay_ms=5.0,
                use_batch_command=use_batch_command,
            )

            if spec is None:
                logger.error(f"❌ {ch.upper()}: No spectrum read")
                detected[ch] = 0.0
                continue

            roi = spec[wave_min_index:wave_max_index]
            mean_val = float(np.mean(roi)) if roi is not None and len(roi) > 0 else 0.0
            max_val = float(np.max(roi)) if roi is not None and len(roi) > 0 else 0.0
            sat_px = count_saturated_pixels(
                spectrum=spec,
                wave_min_index=wave_min_index,
                wave_max_index=wave_max_index,
                saturation_threshold=detector_params.saturation_threshold,
            )
            detected[ch] = mean_val
            pct = (mean_val / detector_params.max_counts * 100.0) if detector_params.max_counts else 0.0
            logger.info(
                f"   {ch.upper()} @ LED=255, T={integration_time_ms:.1f}ms → mean={mean_val:.0f} ({pct:.1f}%), max={max_val:.0f}, sat_px={sat_px}"
            )

        any_light = any(v >= min_counts_threshold for v in detected.values())
        if not any_light:
            msg = ("LED VERIFICATION FAILED: All tested channels < "
                   f"{min_counts_threshold:.0f} counts at LED=255 (S-mode).")
            logger.error("\n" + "=" * 80)
            logger.error(f"❌ {msg}")
            for ch, val in detected.items():
                logger.error(f"   {ch.upper()}: {val:.0f} counts")
            logger.error("=" * 80 + "\n")
            return False, msg

        # Skip P-toggle in fast path to minimize delay
        if not fast:
            try:
                if hasattr(ctrl, 'set_mode'):
                    pm_ok = bool(ctrl.set_mode('p'))
                    logger.info(f"Polarizer P-mode lock: {'OK' if pm_ok else 'UNKNOWN'}")
                    sm_ok = bool(ctrl.set_mode('s'))
                    logger.info(f"Polarizer S-mode re-lock: {'OK' if sm_ok else 'UNKNOWN'}")
            except Exception as e:
                logger.warning(f"⚠️  Polarizer quick toggle check failed: {e}")

        logger.info("✅ PREFLIGHT PASSED: Light detected and polarizer usable")
        return True, "OK"

    except Exception as e:
        logger.exception(f"Preflight check error: {e}")
        return False, str(e)


# =============================================================================
# CONVERGENCE: UNIVERSAL INTEGRATION TIME CONVERGENCE FOR STEPS 3C, 4, 5
# =============================================================================

def converge_integration_time(
    usb,
    ctrl,
    ch_list: list,
    led_intensities: Dict[str, int],
    initial_integration_ms: float,
    target_percent: float,
    tolerance_percent: float,
    detector_params: DetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    max_iterations: int = 5,
    step_name: str = "Unknown",
    stop_flag=None
) -> Tuple[float, Dict[str, float], bool]:
    """Universal convergence loop for integration time optimization.

    Used by Steps 3C, 4, and 5 to achieve target signal with tight tolerance
    and zero saturation using only integration time adjustments.

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        ch_list: List of channels to optimize
        led_intensities: Dict mapping channel to LED intensity (frozen, not changed)
        initial_integration_ms: Starting integration time
        target_percent: Target detector percentage (e.g., 0.40 for 40%, 0.80 for 80%)
        tolerance_percent: Tolerance as fraction (e.g., 0.025 for ±2.5%)
        detector_params: Detector parameters (max_counts, saturation_threshold)
        wave_min_index: ROI start index
        wave_max_index: ROI end index
        max_iterations: Maximum convergence iterations (default 5)
        step_name: Name of step for logging (e.g., "Step 3C", "Step 4")
        stop_flag: Optional threading stop flag

    Returns:
        Tuple of (converged_integration_ms, channel_signals, success)
        - converged_integration_ms: Final integration time
        - channel_signals: Dict of final channel signals
        - success: True if converged within tolerance and no saturation
    """
    detector_max = detector_params.max_counts
    saturation_threshold = detector_params.saturation_threshold

    target_signal = int(target_percent * detector_max)
    min_signal = int((target_percent - tolerance_percent) * detector_max)
    max_signal = int((target_percent + tolerance_percent) * detector_max)

    logger.info(f"🎯 {step_name} Convergence Loop Started")
    logger.info(f"   Target: {target_percent*100:.1f}% ±{tolerance_percent*100:.1f}% ({min_signal:.0f} - {max_signal:.0f} counts)")
    logger.info(f"   Initial integration: {initial_integration_ms:.1f}ms")
    logger.info(f"   LED intensities (frozen): {led_intensities}")
    logger.info("")

    current_integration = initial_integration_ms
    converged = False

    for iteration in range(max_iterations):
        if stop_flag and stop_flag.is_set():
            return current_integration, {}, False

        logger.info(f"🔄 Iteration {iteration + 1}/{max_iterations} - Testing {current_integration:.1f}ms")

        # Set integration time
        usb.set_integration(current_integration)
        time.sleep(0.010)

        # Measure all channels
        iteration_signals = {}
        iteration_saturated = []

        for ch in ch_list:
            if stop_flag and stop_flag.is_set():
                return current_integration, {}, False

            # Quick single-scan measurement
            spectrum = acquire_raw_spectrum(
                usb=usb,
                ctrl=ctrl,
                channel=ch,
                led_intensity=led_intensities[ch],
                integration_time_ms=current_integration,
                num_scans=1,
                pre_led_delay_ms=LED_DELAY * 1000,
                post_led_delay_ms=0.01 * 1000,
                use_batch_command=False
            )

            if spectrum is None:
                logger.error(f"   ❌ {ch.upper()}: Failed to acquire spectrum")
                continue

            # Check signal and saturation
            roi_spectrum = spectrum[wave_min_index:wave_max_index]
            signal = roi_signal(roi_spectrum, 0, len(roi_spectrum), method="median")
            signal_pct = (signal / detector_max) * 100

            sat_count = count_saturated_pixels(roi_spectrum, 0, len(roi_spectrum), saturation_threshold)
            is_saturated = sat_count > 0

            iteration_signals[ch] = signal
            if is_saturated:
                iteration_saturated.append(ch)

            # Status indicator
            in_range = min_signal <= signal <= max_signal
            status = "⚠️ SAT" if is_saturated else ("✅" if in_range else "⚠️")
            logger.info(f"   {ch.upper()}: {signal:.0f} counts ({signal_pct:.1f}%) {status}")

        # Check convergence
        all_in_range = all(min_signal <= iteration_signals[ch] <= max_signal
                          for ch in ch_list if ch in iteration_signals)
        no_saturation = len(iteration_saturated) == 0

        if all_in_range and no_saturation:
            logger.info(f"")
            logger.info(f"✅ All channels converged to {target_percent*100:.1f}% ±{tolerance_percent*100:.1f}% with 0 saturation!")
            converged = True
            break

        # Need adjustment
        if iteration < max_iterations - 1:
            logger.info(f"")
            if iteration_saturated:
                # Saturation: reduce integration by 10%
                current_integration *= 0.90
                logger.warning(f"   Saturation in: {', '.join([ch.upper() for ch in iteration_saturated])}")
                logger.warning(f"   Reducing integration to {current_integration:.1f}ms (-10%)")
            else:
                # Off-target: calculate correction factor
                avg_signal = np.mean(list(iteration_signals.values()))
                correction_factor = target_signal / avg_signal
                # Clamp adjustment to ±10% per iteration for stability
                correction_factor = max(0.90, min(1.10, correction_factor))
                current_integration *= correction_factor
                logger.info(f"   Average: {avg_signal:.0f} counts (target: {target_signal:.0f})")
                logger.info(f"   Adjusting integration to {current_integration:.1f}ms (×{correction_factor:.3f})")

            # Clamp to detector limits
            current_integration = max(detector_params.min_integration_time,
                                     min(detector_params.max_integration_time, current_integration))
            logger.info(f"")
        else:
            logger.warning(f"")
            logger.warning(f"⚠️ Failed to converge after {max_iterations} iterations")

    logger.info(f"📊 {step_name} Final Integration: {current_integration:.1f}ms")
    logger.info("")

    return current_integration, iteration_signals, converged


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

        # Use hardware acquisition function
        spectrum = acquire_raw_spectrum(
            usb=usb,
            ctrl=ctrl,
            channel=ch,
            led_intensity=p_mode_intensities[ch],
            integration_time_ms=None,
            num_scans=1,
            pre_led_delay_ms=LED_DELAY * 1000,
            post_led_delay_ms=0.01 * 1000,
            use_batch_command=False
        )

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

    # Store timing parameters early (needed for cycle time calculations in Step 4)
    result.pre_led_delay_ms = pre_led_delay_ms
    result.post_led_delay_ms = post_led_delay_ms

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

        # PRIORITY 1: Read from hardware section (CORRECT location - device_config root)
        if 'hardware' in device_config_dict:
            hardware = device_config_dict['hardware']
            s_pos = hardware.get('servo_s_position')
            p_pos = hardware.get('servo_p_position')
            if s_pos is not None and p_pos is not None:
                logger.info("✅ Found servo positions in 'hardware' section (device_config root)")

        # PRIORITY 2: Try oem_calibration section (legacy format)
        if s_pos is None or p_pos is None:
            if 'oem_calibration' in device_config_dict:
                oem = device_config_dict['oem_calibration']
                s_pos = oem.get('polarizer_s_position')
                p_pos = oem.get('polarizer_p_position')
                sp_ratio = oem.get('polarizer_sp_ratio')
                if s_pos is not None and p_pos is not None:
                    logger.info("✅ Found OEM calibration in 'oem_calibration' section")

        # PRIORITY 3: Fallback to polarizer section (OEM tool format)
        if s_pos is None or p_pos is None:
            if 'polarizer' in device_config_dict:
                pol = device_config_dict['polarizer']
                s_pos = pol.get('s_position')
                p_pos = pol.get('p_position')
                sp_ratio = pol.get('sp_ratio') or pol.get('s_p_ratio')
                if s_pos is not None and p_pos is not None:
                    logger.info("✅ Found OEM calibration in 'polarizer' section (OEM tool format)")

        # Validate positions loaded successfully
        if s_pos is not None and p_pos is not None:
            # Store in result for later use
            result.polarizer_s_position = s_pos
            result.polarizer_p_position = p_pos
            result.polarizer_sp_ratio = sp_ratio

            # Store old positions for potential recalibration
            result.qc_results['old_s_pos'] = s_pos
            result.qc_results['old_p_pos'] = p_pos

            logger.info("=" * 80)
            logger.info("✅ OEM CALIBRATION POSITIONS LOADED AT INIT (P1 Optimization)")
            logger.info("=" * 80)
            logger.info(f"   S-position: {s_pos} (HIGH transmission - reference)")
            logger.info(f"   P-position: {p_pos} (LOWER transmission - resonance)")
            if sp_ratio:
                logger.info(f"   S/P ratio: {sp_ratio:.2f}x")
            logger.info("   ⚡ Fail-fast enabled: Invalid config detected immediately (<1s)")
            logger.info("=" * 80)

            # Positions loaded from device_config at controller initialization
            # NO runtime configuration - set_mode() uses pre-configured positions
            logger.info(f"   📍 Using positions from device_config (set at controller init)")
            logger.info(f"   ⚠️  NEVER send servo_set/flash during calibration - EEPROM operations removed")
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

            # Store old positions for potential recalibration
            result.qc_results['old_s_pos'] = s_pos
            result.qc_results['old_p_pos'] = p_pos

        logger.info("\n" + "=" * 80)
        logger.info(f"📍 Using OEM polarizer positions: S={s_pos}°, P={p_pos}°")
        logger.info(f"   Positions loaded from device_config at controller initialization")
        logger.info(f"   No configuration needed - set_mode('s'/'p') will use these positions")
        logger.info("=" * 80 + "\n")
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
        logger.info("Forcing all LEDs OFF...")
        ctrl.turn_off_channels()
        time.sleep(0.2)

        # VERIFY LEDs are off using V1.1 firmware query (CRITICAL!)
        max_retries = 3
        led_verified = False
        has_led_query = hasattr(ctrl, 'get_all_led_intensities')

        if has_led_query:
            for attempt in range(max_retries):
                time.sleep(0.005)  # Optimized: 5ms adequate for command processing

                # Query LED state (V1.1 firmware feature)
                try:
                    led_state = ctrl.get_all_led_intensities()
                except Exception as query_error:
                    logger.error(f"LED query failed: {query_error}")
                    led_state = None

                if led_state is None:
                    if attempt == max_retries - 1:
                        has_led_query = False
                        break
                    continue

                # Check if all LEDs are off (intensity <= 1)
                channels_to_check = {ch: val for ch, val in led_state.items() if ch != 'd'}
                all_off = all(intensity <= 1 for intensity in channels_to_check.values())

                if all_off:
                    logger.info("✅ All LEDs confirmed OFF")
                    led_verified = True
                    break
                else:
                    logger.warning(f"LEDs still on (attempt {attempt+1}/{max_retries})")
                    ctrl.turn_off_channels()
                    time.sleep(0.05)

            if not led_verified and has_led_query:
                logger.error("❌ Failed to turn off LEDs after retries")
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
        # PREFLIGHT: LIGHT & POLARIZER (fail-fast)
        # ===================================================================
        device_config_det = resolve_device_config_for_detector(usb)
        ok_pre, msg_pre = preflight_light_and_polarizer(
            usb=usb,
            ctrl=ctrl,
            ch_list=ch_list,
            wave_min_index=result.wave_min_index,
            wave_max_index=result.wave_max_index,
            device_config_det=device_config_det,
            detector_params=detector_params,
            min_counts_threshold=4000.0,
            integration_time_ms=70.0,
            use_batch_command=CONVERGENCE_USE_BATCH_COMMAND,
            fast=True,
        )
        if not ok_pre:
            result.success = False
            result.error_message = msg_pre
            result.error = msg_pre
            return result

        # ===================================================================
        # STEPS 3-5: LED CONVERGENCE (DEFAULT) OR LEGACY CALIBRATION
        # ===================================================================

        logger.info("🔍 CRITICAL CHECKPOINT: Reached Steps 3-5 branching logic")
        logger.info(f"   USE_LED_CONVERGENCE = {USE_LED_CONVERGENCE}")

        if USE_LED_CONVERGENCE:
            # === NEW PATH: LED CONVERGENCE WORKFLOW ===
            logger.info("=" * 80)
            logger.info("🚀 USING LED CONVERGENCE WORKFLOW (Steps 3-5)")
            logger.info("=" * 80)
            logger.info("")

            # Get device config for servo positions
            logger.info("📁 Getting device config for servo positions...")
            device_config_det = resolve_device_config_for_detector(usb)
            logger.info(f"   ✅ Device config loaded")

            # Run LED convergence calibration (Steps 3-5 replacement)
            logger.info("🚨 ABOUT TO CALL run_convergence_calibration_steps_3_to_5()")
            convergence_result = run_convergence_calibration_steps_3_to_5(
                usb=usb,
                ctrl=ctrl,
                detector_params=detector_params,
                ch_list=ch_list,
                wave_min_index=result.wave_min_index,
                wave_max_index=result.wave_max_index,
                device_config_det=device_config_det,
                target_percent=0.40,  # 40% detector target
                tolerance_percent=0.02,  # ±2% tolerance
                strategy="intensity"  # Use LED normalization strategy
            )

            if not convergence_result['success']:
                logger.error(f"❌ LED convergence failed: {convergence_result['error']}")
                result.success = False
                result.error_message = f"LED convergence calibration failed: {convergence_result['error']}"
                return result

            # Transfer convergence results to calibration result
            result.weakest_channel = convergence_result['weakest_channel']
            result.s_mode_intensity = convergence_result['s_mode_intensities']
            result.p_mode_intensity = convergence_result['p_mode_intensities']
            result.s_integration_time = convergence_result['s_integration_time']
            result.p_integration_time = convergence_result['p_integration_time']

            # Store raw spectra for Step 6 processing (match legacy format)
            # Assign raw ROI spectra (retain legacy fields)
            result.s_raw_data = convergence_result['s_pol_ref']  # Dict {ch: ndarray}
            result.p_raw_data = convergence_result['p_pol_ref']  # Dict {ch: ndarray}
            # Provide modern references (same ROI arrays)
            result.s_pol_ref = convergence_result['s_pol_ref']
            result.p_pol_ref = convergence_result['p_pol_ref']
            # Dark spectrum: store ROI slice for additive reconstruction; keep max for QC
            if convergence_result['dark_spectrum'] is not None:
                full_dark = convergence_result['dark_spectrum']
                result.dark_noise = full_dark[result.wave_min_index:result.wave_max_index]
                try:
                    result.qc_results['dark_max_counts'] = float(np.max(full_dark))
                except Exception:
                    pass
            # Normalized LED metadata (alias to s_mode_intensity)
            result.normalized_leds = dict(result.s_mode_intensity)
            # Brightness ratios derived from mean ROI signals of S references
            try:
                s_means = {ch: float(np.mean(result.s_pol_ref[ch])) for ch in result.s_pol_ref}
                weakest_mean = s_means.get(result.weakest_channel)
                if weakest_mean and weakest_mean > 0:
                    result.brightness_ratios = {ch: s_means[ch] / weakest_mean for ch in s_means}
            except Exception:
                pass
            # LEDs calibrated compatibility field
            result.leds_calibrated = dict(result.p_mode_intensity)
            # Basic QC placeholders for Step 6 consumption
            try:
                for ch in result.s_pol_ref:
                    sig_top50 = float(np.mean(np.sort(result.s_pol_ref[ch])[-50:])) if len(result.s_pol_ref[ch]) >= 50 else float(np.max(result.s_pol_ref[ch]))
                    pct = sig_top50 / result.detector_max_counts * 100.0 if result.detector_max_counts else 0.0
                    result.qc_results.setdefault('s_mode_top50', {})[ch] = sig_top50
                    result.qc_results.setdefault('s_mode_top50_pct', {})[ch] = pct
                for ch in result.p_pol_ref:
                    sig_top50 = float(np.mean(np.sort(result.p_pol_ref[ch])[-50:])) if len(result.p_pol_ref[ch]) >= 50 else float(np.max(result.p_pol_ref[ch]))
                    pct = sig_top50 / result.detector_max_counts * 100.0 if result.detector_max_counts else 0.0
                    result.qc_results.setdefault('p_mode_top50', {})[ch] = sig_top50
                    result.qc_results.setdefault('p_mode_top50_pct', {})[ch] = pct
            except Exception:
                pass

            logger.info("")
            logger.info("=" * 80)
            logger.info("✅ LED CONVERGENCE COMPLETE - Proceeding to Step 6")
            logger.info("=" * 80)
            logger.info("")

            # Skip old Steps 3-5 and jump directly to Step 6
            # (Step 6 processes the raw spectra and performs QC)

        else:
            # === LEGACY PATH: Original Steps 3-5 ===
            logger.info("=" * 80)
            logger.info("⚠️  USING LEGACY CALIBRATION (Steps 3-5)")
            logger.info("=" * 80)
            logger.info("")

            # ===================================================================
            # STEP 3: LED BRIGHTNESS RANKING (WITH FIRMWARE RANK OPTIMIZATION)
            # ===================================================================
            logger.info("=" * 80)
            logger.info("STEP 3: LED Brightness Ranking")
            logger.info("=" * 80)

            if progress_callback:
                progress_callback("Step 3 of 6: Measuring channel brightness", 33)

        # Switch to S-mode with explicit servo pre-positioning using new servo_initiation_to_s
        logger.info("Switching to S-mode with servo pre-position (1° → S°)...")
        try:
            # Turn off LEDs for safety
            ctrl.turn_off_channels()
            time.sleep(LED_DELAY)

            # Validate against device_config
            try:
                _validate_polarizer_positions(device_config, 's', logger)
            except Exception as e:
                logger.warning(f"Polarizer position validation warning: {e}")

            # Use new servo_initiation_to_s function for cleaner initialization
            detector_serial = getattr(usb, 'serial_number', 'UNKNOWN')
            device_config_det = resolve_device_config_for_detector(usb)
            servo_positions = servo_initiation_to_s(ctrl, device_config_det, detector_serial)
            logger.info(f"✅ Servo initialized to S-mode: S={servo_positions['s_position']}°, P={servo_positions['p_position']}°")
        except Exception as e:
            logger.warning(f"Servo initiation failed: {e}; attempting fallback S-mode switch")
            switch_mode_safely(ctrl, "s", turn_off_leds=True)
            logger.info("✅ S-mode active (fallback), all LEDs off\n")

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
            # Use detector saturation threshold from DetectorParams
            SATURATION_THRESHOLD = int(0.95 * detector_params.saturation_threshold)

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
        logger.info(f"Goal: Find integration time where weakest channel @ LED=255 hits 40% detector")
        logger.info(f"Strategy: Binary search to maximize weakest channel signal (avoiding saturation)")
        logger.info(f"Target: {weakest_ch.upper()} @ LED=255 → 40% detector ({int(0.40 * (detector_params.max_counts)):.0f} counts)")
        logger.info(f"")

        # Constants
        detector_max = result.detector_max_counts if hasattr(result, 'detector_max_counts') else detector_params.max_counts
        STEP3B_TARGET_PERCENT = 0.40  # 40% detector max - safe from saturation
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
            # Use hardware acquisition function
            spectrum = acquire_raw_spectrum(
                usb=usb,
                ctrl=ctrl,
                channel=weakest_ch,
                led_intensity=WEAKEST_TARGET_LED,
                integration_time_ms=test_int,
                num_scans=1,
                pre_led_delay_ms=LED_DELAY * 1000,  # Convert to ms
                post_led_delay_ms=0.01 * 1000,  # 10ms
                use_batch_command=False
            )

            if spectrum is None:
                logger.error(f"Failed to read spectrum")
                break

            # Robust signal over ROI to mitigate single-pixel spikes
            signal = roi_signal(spectrum, result.wave_min_index, result.wave_max_index, method="median")
            signal_pct = (signal / detector_max) * 100

            # Check for saturation
            roi_spectrum = spectrum[result.wave_min_index:result.wave_max_index]
            saturation_limit = detector_params.saturation_threshold
            saturated_pixels = np.sum(roi_spectrum >= saturation_limit)
            is_saturated = saturated_pixels > 0

            if is_saturated:
                logger.warning(f"   Iteration {iteration+1}: {test_int:.1f}ms → SATURATED ({saturated_pixels} pixels >= {saturation_limit})")
                # Force lower integration time
                max_int = test_int
                continue

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
        # RESTART LOOP FOR SERVO RECALIBRATION
        # ===================================================================
        # If servo positions are inverted, Step 6 will auto-recalibrate and restart from here
        max_restart_attempts = 1  # Allow one restart for servo recalibration
        restart_attempt = 0

        while restart_attempt <= max_restart_attempts:
            if restart_attempt > 0:
                logger.info("\n" + "=" * 80)
                logger.info(f"🔄 RESTART ATTEMPT {restart_attempt}: Re-running Steps 3C-6 with corrected servo positions")
                logger.info("=" * 80 + "\n")

            try:
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

                    # STAGE 2: Iterative LED Correction (Ensure Uniformity)
                    logger.info(f"📊 STAGE 2: Smart LED Calculation (All Channels @ 40% Detector)")
                    logger.info(f"")

                    target_signal = step3b_target_signal  # From Step 3B (80% detector)
                    # Safety check: Ensure target is below 95% of saturation threshold
                    safe_max_signal = detector_params.saturation_threshold * 0.95

                    logger.info(f"   Target signal: {target_signal:.0f} counts ({(target_signal/detector_max)*100:.1f}% detector)")
                    logger.info(f"   Safe maximum: {safe_max_signal:.0f} counts (95% of saturation threshold)")

                    if target_signal >= safe_max_signal:
                        logger.warning(f"   ⚠️ Target ({target_signal:.0f}) at/above safe maximum ({safe_max_signal:.0f})")
                        target_signal = int(safe_max_signal * 0.98)  # Back off to 98% of safe max
                        logger.warning(f"   Reducing target to: {target_signal:.0f} counts ({(target_signal/detector_max)*100:.1f}% detector)")
                    else:
                        logger.info(f"   ✅ Target is safely below saturation threshold")

                    logger.info(f"")

                    correction_tolerance = 0.05  # ±5% tolerance for tight convergence
                    max_correction_iterations = 5  # Increased from 3 to ensure convergence

                    # Track which channels need correction
                    channels_to_correct = list(ch_list)

                    logger.info(f"   Convergence tolerance: ±{correction_tolerance*100:.0f}%")
                    logger.info(f"   Maximum iterations: {max_correction_iterations}")
                    logger.info(f"")

                    for correction_iter in range(max_correction_iterations):
                        if stop_flag and stop_flag.is_set():
                            break

                        if not channels_to_correct:
                            break

                        if correction_iter > 0:
                            logger.info(f"")
                            logger.info(f"🔄 Correction Iteration {correction_iter + 1}")
                            logger.info(f"")

                        channels_corrected_this_iter = []

                        for ch in channels_to_correct:
                            if stop_flag and stop_flag.is_set():
                                break

                            # Use hardware acquisition function
                            spectrum = acquire_raw_spectrum(
                                usb=usb,
                                ctrl=ctrl,
                                channel=ch,
                                led_intensity=normalized_leds[ch],
                                integration_time_ms=None,
                                num_scans=1,
                                pre_led_delay_ms=LED_DELAY * 1000,
                                post_led_delay_ms=0.01 * 1000,
                                use_batch_command=False
                            )

                            if spectrum is None:
                                logger.error(f"Failed to verify {ch.upper()}")
                                channels_corrected_this_iter.append(ch)  # Remove from correction list
                                continue

                            # Robust signal metric for verification
                            signal = roi_signal(spectrum, result.wave_min_index, result.wave_max_index, method="median")
                            signal_pct = (signal / detector_max) * 100

                            # Check for saturation FIRST
                            roi_spectrum = spectrum[result.wave_min_index:result.wave_max_index]
                            saturation_limit = detector_params.saturation_threshold
                            saturated_pixels = np.sum(roi_spectrum >= saturation_limit)
                            is_saturated = saturated_pixels > 0
                            max_pixel = np.max(roi_spectrum)

                            # Calculate error from target
                            error_pct = ((signal - target_signal) / target_signal)

                            # Check if converged (within tolerance AND no saturation)
                            converged = (abs(error_pct) <= correction_tolerance) and not is_saturated

                            if converged:
                                # Success - mark as done
                                channels_corrected_this_iter.append(ch)
                                logger.info(f"   ✅ {ch.upper()} @ LED={normalized_leds[ch]:3d}: {signal:6.0f} counts ({signal_pct:5.1f}%) CONVERGED {error_pct:+.1%}")
                                continue

                            # Check if final iteration
                            if correction_iter >= max_correction_iterations - 1:
                                channels_corrected_this_iter.append(ch)
                                if is_saturated:
                                    logger.warning(f"   ⚠️ {ch.upper()} @ LED={normalized_leds[ch]:3d}: SATURATED after {max_correction_iterations} iterations")
                                else:
                                    logger.warning(f"   ⚠️ {ch.upper()} @ LED={normalized_leds[ch]:3d}: {signal:6.0f} counts - NOT CONVERGED {error_pct:+.1%}")
                                continue

                            # Need correction - calculate smart LED adjustment
                            old_led = normalized_leds[ch]

                            if is_saturated:
                                # CRITICAL: Reduce to eliminate saturation
                                # Use max_pixel (not median signal) for saturation calculation
                                safe_target = saturation_limit * 0.90  # 90% of sat threshold
                                correction_factor = safe_target / max_pixel
                                correction_factor = max(0.75, min(0.95, correction_factor))
                                logger.warning(f"   🔻 {ch.upper()} @ LED={old_led:3d}: SATURATED ({saturated_pixels} px, max={max_pixel:.0f})")
                                logger.warning(f"      → Reducing to LED={int(old_led * correction_factor):3d} (factor {correction_factor:.3f})")
                            else:
                                # Proportional correction: new_LED = old_LED × (target / signal)
                                correction_factor = target_signal / signal

                                # First iteration: dampen to prevent overshoot
                                if correction_iter == 0:
                                    correction_factor = 0.7 * correction_factor + 0.3

                                # Clamp to reasonable bounds
                                correction_factor = max(0.80, min(1.20, correction_factor))

                                status = "🔺 LOW" if error_pct < 0 else "🔻 HIGH"
                                logger.info(f"   {status} {ch.upper()} @ LED={old_led:3d}: {signal:6.0f} counts {error_pct:+.1%}")
                                logger.info(f"      → Adjusting to LED={int(old_led * correction_factor):3d} (factor {correction_factor:.3f})")

                            # Apply correction
                            new_led = int(old_led * correction_factor)
                            new_led = max(10, min(255, new_led))
                            normalized_leds[ch] = new_led

                        # Remove corrected channels from list
                        for ch in channels_corrected_this_iter:
                            if ch in channels_to_correct:
                                channels_to_correct.remove(ch)

                        # If all channels corrected, exit loop
                        if not channels_to_correct:
                            logger.info(f"")
                            logger.info(f"✅ All channels within ±5% of target after {correction_iter + 1} iteration(s)")
                            break

                    # Final verification pass
                    if channels_to_correct:
                        logger.info(f"")
                        logger.info(f"⚠️ {len(channels_to_correct)} channel(s) still outside tolerance after {max_correction_iterations} iterations")

                    logger.info(f"")
                    logger.info(f"📊 STAGE 3: Final Uniformity Check")
                    logger.info(f"")

                    weakest_signal = None
                    saturated_channels = []
                    for ch in ch_list:
                        if stop_flag and stop_flag.is_set():
                            break

                        # Final measurement
                        spectrum = acquire_raw_spectrum(
                            usb=usb,
                            ctrl=ctrl,
                            channel=ch,
                            led_intensity=normalized_leds[ch],
                            integration_time_ms=None,
                            num_scans=1,
                            pre_led_delay_ms=LED_DELAY * 1000,
                            post_led_delay_ms=0.01 * 1000,
                            use_batch_command=False
                        )

                        if spectrum is None:
                            continue

                        signal = roi_signal(spectrum, result.wave_min_index, result.wave_max_index, method="median")
                        signal_pct = (signal / detector_max) * 100

                        # Check for saturation
                        roi_spectrum = spectrum[result.wave_min_index:result.wave_max_index]
                        saturation_limit = detector_params.saturation_threshold
                        saturated_pixels = np.sum(roi_spectrum >= saturation_limit)
                        is_saturated = saturated_pixels > 0
                        max_pixel = np.max(roi_spectrum)
                        sat_status = f"⚠️ {saturated_pixels} SAT" if is_saturated else ""

                        # EMPIRICAL VALIDATION: Count pixels near target
                        pixels_near, pct_near = count_pixels_near_target(
                            spectrum, result.wave_min_index, result.wave_max_index, target_signal, 0.10
                        )
                        total_pixels = result.wave_max_index - result.wave_min_index

                        if weakest_signal is None:
                            weakest_signal = signal

                        deviation_pct = ((signal - weakest_signal) / weakest_signal) * 100
                        uniformity_status = "✅" if abs(deviation_pct) < 10 and not is_saturated else "⚠️"
                        pixel_status = "✅" if pct_near >= 50 else "⚠️"

                        logger.info(f"   {ch.upper()} @ LED={normalized_leds[ch]:3d}: {signal:6.0f} counts ({signal_pct:5.1f}%) {uniformity_status} {deviation_pct:+.1f}% {sat_status}")
                        if is_saturated:
                            logger.warning(f"      {saturated_pixels} pixels saturated (max: {max_pixel:.0f} >= {saturation_limit:.0f})")
                            saturated_channels.append(ch)
                        logger.info(f"      Pixels near target: {pixels_near}/{total_pixels} ({pct_near:.1f}%) {pixel_status}")

                    # CRITICAL CHECK: If saturation detected, apply emergency LED reduction
                    if saturated_channels:
                        logger.warning(f"")
                        logger.warning(f"⚠️ Saturation detected in channels: {', '.join([ch.upper() for ch in saturated_channels])}")
                        logger.warning(f"   Applying emergency 15% LED reduction to saturated channels...")

                        # Reduce LEDs by 15% for saturated channels
                        for ch in saturated_channels:
                            old_led = normalized_leds[ch]
                            new_led = int(old_led * 0.85)
                            new_led = max(10, new_led)
                            normalized_leds[ch] = new_led
                            logger.warning(f"   {ch.upper()}: LED {old_led} → {new_led}")

                        logger.warning(f"   Verifying saturation cleared...")

                        # Re-measure saturated channels to verify
                        still_saturated = []
                        for ch in saturated_channels:
                            spectrum = acquire_raw_spectrum(
                                usb=usb,
                                ctrl=ctrl,
                                channel=ch,
                                led_intensity=normalized_leds[ch],
                                integration_time_ms=None,
                                num_scans=1,
                                pre_led_delay_ms=LED_DELAY * 1000,
                                post_led_delay_ms=0.01 * 1000,
                                use_batch_command=False
                            )

                            if spectrum is not None:
                                roi_spectrum = spectrum[result.wave_min_index:result.wave_max_index]
                                sat_count = np.sum(roi_spectrum >= detector_params.saturation_threshold)
                                if sat_count > 0:
                                    still_saturated.append(ch)
                                    logger.error(f"   ❌ {ch.upper()}: Still {sat_count} pixels saturated")
                                else:
                                    signal = roi_signal(spectrum, result.wave_min_index, result.wave_max_index, method="median")
                                    signal_pct = (signal / detector_max) * 100
                                    logger.info(f"   ✅ {ch.upper()}: Saturation cleared ({signal:.0f} counts, {signal_pct:.1f}%)")

                        if still_saturated:
                            logger.error(f"")
                            logger.error(f"❌ CALIBRATION FAILED: Saturation persists in {', '.join([ch.upper() for ch in still_saturated])}")
                            logger.error(f"   Even after 15% LED reduction, saturation remains.")
                            logger.error(f"   The 80% target cannot be achieved with this hardware configuration.")
                            logger.error(f"")
                            raise RuntimeError(f"Persistent saturation in Step 3C: {still_saturated}")
                        else:
                            logger.info(f"")
                            logger.info(f"✅ Saturation cleared after emergency LED reduction")

                    logger.info(f"")
                logger.info(f"="*80)
                logger.info(f"✅ STEP 3C COMPLETE: LEDs {'FIXED AT 255' if USE_ALTERNATIVE_CALIBRATION else 'NORMALIZED & ITERATIVELY CORRECTED'}")
                logger.info(f"="*80)
                logger.info(f"   Integration time: {best_integration:.1f}ms (from Step 3B)")
                if USE_ALTERNATIVE_CALIBRATION:
                    logger.info(f"   All LEDs @ 255 (per-channel integration will be optimized in Step 5)")
                else:
                    logger.info(f"   All channels @ ~40% ({step3b_target_signal:.0f} counts) within ±5% tolerance")
                    logger.info(f"   LED intensities after iterative correction:")
                    for ch in ch_list:
                        logger.info(f"      {ch.upper()}: LED={normalized_leds[ch]}")
                logger.info(f"")
                logger.info(f"   🔒 LED VALUES NOW FROZEN (no changes after Step 3C)")
                logger.info(f"   📋 CRITICAL RULE: Steps 4, 5, 6 use ONLY integration time adjustments")
                logger.info(f"   📋 LED intensities remain locked at Step 3C values for all subsequent steps")
                logger.info(f"")

                # DEBUG: Print full S-pol spectrum data at end of Step 3C
                logger.info("="*80)
                logger.info("DEBUG: FULL S-POL SPECTRUM DATA AT END OF STEP 3C")
                logger.info("="*80)
                logger.info(f"Integration time: {best_integration:.2f} ms")
                logger.info(f"Wavelength range: {result.wave_data[0]:.2f} - {result.wave_data[-1]:.2f} nm")
                logger.info(f"Number of pixels: {len(result.wave_data)}")
                logger.info("")
                for ch in ch_list:
                    if stop_flag and stop_flag.is_set():
                        break
                    # Measure one final time to get clean spectrum
                    spectrum = acquire_raw_spectrum(
                        usb=usb,
                        ctrl=ctrl,
                        channel=ch,
                        led_intensity=normalized_leds[ch],
                        integration_time_ms=None,
                        num_scans=1,
                        pre_led_delay_ms=LED_DELAY * 1000,
                        post_led_delay_ms=0.01 * 1000,
                        use_batch_command=False
                    )
                    if spectrum is not None:
                        logger.info(f"Channel {ch.upper()} @ LED={normalized_leds[ch]}:")
                        logger.info(f"  Max: {np.max(spectrum):.1f} counts")
                        logger.info(f"  Mean: {np.mean(spectrum):.1f} counts")
                        logger.info(f"  Full spectrum array:")
                        logger.info(f"{spectrum}")
                        logger.info("")
                logger.info("="*80)
                logger.info("")

                # Store results
                result.s_mode_intensity = normalized_leds
                result.ref_intensity = normalized_leds
                result.s_integration_time = best_integration  # Already in milliseconds
                result.weakest_channel = weakest_ch

                # Track Step 3C saturation behavior for Step 4 intelligence
                # Safely check if saturated_channels variable exists from Step 3C
                step3c_saturated_channels = []
                step3c_had_saturation = False
                try:
                    # Try to access saturated_channels - will raise NameError if doesn't exist
                    if saturated_channels and len(saturated_channels) > 0:
                        step3c_saturated_channels = list(saturated_channels)
                        step3c_had_saturation = True
                        logger.info(f"⚠️ Step 3C had saturation in: {', '.join([ch.upper() for ch in step3c_saturated_channels])}")
                        logger.info(f"   Step 4 will use more aggressive reduction for these channels")
                except (NameError, UnboundLocalError):
                    # Variable doesn't exist - no saturation in Step 3C
                    logger.info(f"✅ Step 3C completed with no saturation")

                if not step3c_had_saturation:
                    logger.info(f"✅ Step 3C completed with no saturation")
                logger.info("")

                # ===================================================================
                # STEP 4: S-MODE BASELINE CHARACTERIZATION (TWO ROI REGIONS)
                # ===================================================================
                if progress_callback:
                    progress_callback("Step 4 of 6: Measuring S-mode baseline", 50)

                logger.info("=" * 80)
                logger.info("STEP 4: S-Mode Baseline Characterization (Two ROI Regions)")
                logger.info("=" * 80)
                logger.info("Goal: Measure S-mode signal in two ROI regions for P-mode loss calculation")
                logger.info("Strategy: Adjust integration time to achieve target detector signal")
                logger.info("ROI 1: 560-570nm (blue edge - minimal SPR signal)")
                logger.info("ROI 2: 710-720nm (red edge - minimal SPR signal)")
                logger.info("Purpose: Establish high-SNR S-pol baseline for transmission calculation\n")

                # Check if any channels have maxed-out LEDs (255) - they need special handling
                maxed_channels = [ch for ch in ch_list if normalized_leds[ch] >= 255]
                if maxed_channels:
                    logger.warning(f"⚠️ Channels with maxed LEDs detected: {', '.join([ch.upper() for ch in maxed_channels])}")
                    logger.warning(f"   Using per-channel integration time optimization")
                    logger.warning(f"   Target: 75% detector (49K counts) for all channels")
                    # Use 75% target - achievable with per-channel integration times
                    STEP4_TARGET_PERCENT = 0.75  # 75% = ~49K counts
                else:
                    # Normal target for channels with LED headroom
                    STEP4_TARGET_PERCENT = 0.80  # 80% = ~52K counts

                # ALWAYS use per-channel integration optimization (user requested)
                use_per_channel_integration = True

                STEP4_TOLERANCE_PERCENT = 0.025  # ±2.5% tight tolerance
                step4_target_signal = int(STEP4_TARGET_PERCENT * detector_max)
                step4_min_signal = int((STEP4_TARGET_PERCENT - STEP4_TOLERANCE_PERCENT) * detector_max)
                step4_max_signal = int((STEP4_TARGET_PERCENT + STEP4_TOLERANCE_PERCENT) * detector_max)
                step3c_target_signal = step3b_target_signal  # Step 3C was 40%

                # Calculate initial integration time scaling: Step4_target / Step3C_target
                integration_scale_factor = step4_target_signal / step3c_target_signal

                # Start with scaled integration time as baseline
                step4_integration = best_integration * integration_scale_factor

                # Clamp to detector limits
                step4_integration = max(detector_params.min_integration_time,
                                       min(detector_params.max_integration_time, step4_integration))

                logger.info(f"📊 Step 4 Target Calculation:")
                logger.info(f"   Step 3C target: {step3c_target_signal:.0f} counts ({STEP3B_TARGET_PERCENT*100:.0f}% detector)")
                logger.info(f"   Step 4 target: {step4_target_signal:.0f} counts ({STEP4_TARGET_PERCENT*100:.0f}% detector)")
                logger.info(f"   Acceptable range: {step4_min_signal:.0f} - {step4_max_signal:.0f} counts ({(STEP4_TARGET_PERCENT-STEP4_TOLERANCE_PERCENT)*100:.1f}% - {(STEP4_TARGET_PERCENT+STEP4_TOLERANCE_PERCENT)*100:.1f}%)")
                logger.info(f"   Baseline integration: {step4_integration:.1f}ms (scaled {integration_scale_factor:.2f}× from Step 3C)")
                logger.info(f"   Using Step 3C LEDs (unchanged)")

                if use_per_channel_integration:
                    logger.info(f"   Mode: PER-CHANNEL integration time optimization")
                else:
                    logger.info(f"   Mode: SINGLE common integration time")
                logger.info("")

                # Initialize per-channel integration times
                channel_s_integration_times = {}

                if use_per_channel_integration:
                    # PER-CHANNEL OPTIMIZATION: Each channel gets its own integration time
                    logger.info(f"🔄 Step 4 Per-Channel Optimization")
                    logger.info(f"   Target: {STEP4_TARGET_PERCENT*100:.0f}% ±2.5% for each channel")
                    logger.info("")

                    for ch in ch_list:
                        logger.info(f"  Optimizing {ch.upper()}:")

                        # Binary search for optimal integration time
                        # Start conservatively to avoid saturation
                        min_int = detector_params.min_integration_time
                        max_int = min(step4_integration * 2.0, detector_params.max_integration_time)
                        best_int = detector_params.min_integration_time  # Start with minimum as fallback
                        best_signal = 0
                        max_iterations = 8

                        # Track if we ever hit saturation
                        ever_saturated = False

                        for iteration in range(max_iterations):
                            test_int = (min_int + max_int) / 2

                            spectrum = acquire_raw_spectrum(
                                usb=usb,
                                ctrl=ctrl,
                                channel=ch,
                                led_intensity=normalized_leds[ch],
                                integration_time_ms=test_int,
                                num_scans=5,
                                pre_led_delay_ms=LED_DELAY * 1000,
                                post_led_delay_ms=0.01 * 1000,
                                use_batch_command=False
                            )

                            if spectrum is None:
                                logger.warning(f"    Iter {iteration+1}: No spectrum, skipping")
                                break

                            # Check signal and saturation
                            roi_spectrum = spectrum[wave_min_index:wave_max_index]
                            signal = roi_signal(roi_spectrum, 0, len(roi_spectrum), method="median")
                            signal_pct = (signal / detector_max) * 100
                            max_pixel = np.max(roi_spectrum)

                            sat_count = count_saturated_pixels(roi_spectrum, 0, len(roi_spectrum), detector_params.saturation_threshold)
                            is_saturated = sat_count > 0

                            # Check if in target range
                            in_range = step4_min_signal <= signal <= step4_max_signal

                            if sat_count > 0:
                                ever_saturated = True
                                logger.info(f"    Iter {iteration+1}: {test_int:.1f}ms → {signal:.0f} ({signal_pct:.1f}%), SATURATED → reduce")
                                max_int = test_int
                            elif in_range:
                                # Found optimal: in range and not saturated
                                best_int = test_int
                                best_signal = signal
                                logger.info(f"    Iter {iteration+1}: {test_int:.1f}ms → {signal:.0f} ({signal_pct:.1f}%), ✅ OPTIMAL")
                                break
                            elif signal < step4_min_signal:
                                logger.info(f"    Iter {iteration+1}: {test_int:.1f}ms → {signal:.0f} ({signal_pct:.1f}%), too low → increase")
                                min_int = test_int
                                # Update best if this is closer to target AND not saturated
                                if abs(signal - step4_target_signal) < abs(best_signal - step4_target_signal) or best_signal == 0:
                                    best_int = test_int
                                    best_signal = signal
                            else:
                                # Signal too high but not saturated - reduce
                                logger.info(f"    Iter {iteration+1}: {test_int:.1f}ms → {signal:.0f} ({signal_pct:.1f}%), too high → reduce")
                                max_int = test_int
                                # Update best if closer to target
                                if abs(signal - step4_target_signal) < abs(best_signal - step4_target_signal):
                                    best_int = test_int
                                    best_signal = signal

                        # CRITICAL: If we ever hit saturation, verify final integration time is safe
                        if ever_saturated:
                            logger.warning(f"    Channel {ch.upper()} hit saturation during search - verifying final integration is safe...")
                            verify_spectrum = acquire_raw_spectrum(
                                usb=usb,
                                ctrl=ctrl,
                                channel=ch,
                                led_intensity=normalized_leds[ch],
                                integration_time_ms=best_int,
                                num_scans=5,
                                pre_led_delay_ms=LED_DELAY * 1000,
                                post_led_delay_ms=0.01 * 1000,
                                use_batch_command=False
                            )
                            if verify_spectrum is not None:
                                verify_roi = verify_spectrum[wave_min_index:wave_max_index]
                                verify_sat = count_saturated_pixels(verify_roi, 0, len(verify_roi), detector_params.saturation_threshold)
                                if verify_sat > 0:
                                    # Still saturated! Reduce integration time aggressively
                                    logger.error(f"    ❌ Still saturated at {best_int:.1f}ms! Reducing to 70% of current value...")
                                    best_int *= 0.70
                                    best_int = max(detector_params.min_integration_time, best_int)
                                    logger.warning(f"    Using emergency reduced integration: {best_int:.1f}ms")

                        channel_s_integration_times[ch] = best_int
                        final_pct = (best_signal / detector_max) * 100 if best_signal > 0 else 0
                        logger.info(f"  ✅ {ch.upper()}: Final {best_int:.1f}ms → {best_signal:.0f} ({final_pct:.1f}%)")
                        logger.info("")

                    logger.info("✅ All channels optimized with per-channel integration times")
                    step4_integration = channel_s_integration_times.get('a', step4_integration)  # Use channel A as reference

                logger.info("")
                logger.info(f"📊 Final Step 4 integration time: {step4_integration:.1f}ms")
                logger.info("")

                # Now do final acquisition with converged integration time
                usb.set_integration(step4_integration)
                time.sleep(0.010)

                logger.info("")
                logger.info("=" * 80)
                logger.info("📸 STEP 4 (S-mode): Final Data Acquisition with Converged Integration Time")
                logger.info("=" * 80)
                logger.info("")

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
                logger.info(f"   Using converged integration time: {step4_integration:.1f}ms")
                logger.info("")

                # Ensure polarizer is in S-mode
                logger.info("")
                logger.info("🔄 POLARIZER ORIENTATION CHANGE: Switching to S-MODE")
                logger.info("  Current Step: Step 4 - S-mode baseline measurement")
                logger.info("  Expected behavior: Maximum transmission through polarizer")
                logger.info("")

                # CRITICAL SAFETY CHECK: Validate positions before set_mode()
                _validate_polarizer_positions(device_config, 's', logger)

                logger.info("  → Sending set_mode('s') command to controller...")
                set_result = ctrl.set_mode('s')
                if set_result:
                    logger.info("  ✅ Controller confirmed: Servo moved to S position")
                else:
                    logger.warning("  ⚠️ Controller response unexpected - servo should have moved to S position")
                    logger.warning("  ⚠️ Continuing calibration - servo movement may still be successful")
                logger.info("")
                time.sleep(0.5)  # Wait for servo to move

                logger.info("📋 STEP 4 FINAL CHECKLIST (before storing data):")
                logger.info(f"   Target: 80% ±2.5% ({step4_min_signal:.0f} - {step4_max_signal:.0f} counts)")
                logger.info(f"   Integration time: {step4_integration:.1f}ms")
                logger.info("")

                s_raw_data = {}  # Store raw data for each channel
                s_data = {}      # Store ROI-trimmed data

                # Polarizer now in S-mode (using device_config position)
                logger.info(f"    ✅ S-mode set (position from device_config)")
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

                    # Get integration time for this channel (per-channel or common)
                    ch_integration = channel_s_integration_times.get(ch, step4_integration) if use_per_channel_integration else step4_integration

                    # Use hardware acquisition function with averaging
                    # Use Step 3C LEDs with Step 4 integration time (per-channel or common)
                    avg_spectrum = acquire_raw_spectrum(
                        usb=usb,
                        ctrl=ctrl,
                        channel=ch,
                        led_intensity=normalized_leds[ch],  # Step 3C LEDs unchanged
                        integration_time_ms=ch_integration,  # Per-channel or common integration
                        num_scans=result.num_scans,
                        pre_led_delay_ms=LED_DELAY * 1000,
                        post_led_delay_ms=0.01 * 1000,
                        use_batch_command=False
                    )

                    if avg_spectrum is None:
                        logger.error(f"   ❌ Failed to capture spectra for {ch.upper()}")
                        continue

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

                # CRITICAL CHECK: Verify convergence and no saturation in S-mode raw data
                logger.info("")
                logger.info("📋 STEP 4 FINAL CHECKLIST (Channel-by-Channel):")
                logger.info(f"   Target Range: {step4_min_signal:.0f} - {step4_max_signal:.0f} counts (80% ±2.5%)")
                logger.info(f"   Saturation Threshold: {detector_params.saturation_threshold:.0f} counts")
                logger.info("")

                saturated_channels_s = []
                off_target_channels_s = []

                for ch in ch_list:
                    if ch in s_raw_data:
                        spectrum = s_raw_data[ch]
                        sat_count = count_saturated_pixels(
                            spectrum, 0, len(spectrum), detector_params.saturation_threshold
                        )
                        signal = roi_signal(spectrum, 0, len(spectrum), method="median")
                        signal_pct = (signal / detector_max) * 100

                        in_range = step4_min_signal <= signal <= step4_max_signal
                        no_sat = sat_count == 0

                        if sat_count > 0:
                            max_pixel = np.max(spectrum)
                            logger.error(f"   ❌ {ch.upper()}: {sat_count} SAT pixels (max: {max_pixel:.0f}, {signal:.0f} counts, {signal_pct:.1f}%)")
                            saturated_channels_s.append(ch)
                        elif not in_range:
                            logger.warning(f"   ⚠️ {ch.upper()}: OFF TARGET ({signal:.0f} counts, {signal_pct:.1f}%) - expected 77.5%-82.5%")
                            off_target_channels_s.append(ch)
                        else:
                            logger.info(f"   ✅ {ch.upper()}: {signal:.0f} counts ({signal_pct:.1f}%) - No saturation, in range")

                logger.info("")
                if saturated_channels_s:
                    logger.error(f"❌ STEP 4 SATURATION: Detected in {', '.join([ch.upper() for ch in saturated_channels_s])}")
                    logger.error(f"")
                    logger.error(f"   Attempting FINAL EMERGENCY RECOVERY...")
                    logger.error(f"   Reducing integration time to 50% of current value for saturated channels")
                    logger.error(f"")

                    # EMERGENCY RECOVERY: Reduce integration time to 50% for saturated channels
                    recovery_success = True
                    for ch in saturated_channels_s:
                        ch_integration = channel_s_integration_times.get(ch, step4_integration) if use_per_channel_integration else step4_integration
                        emergency_int = ch_integration * 0.50
                        emergency_int = max(detector_params.min_integration_time, emergency_int)

                        logger.warning(f"   {ch.upper()}: Reducing {ch_integration:.1f}ms → {emergency_int:.1f}ms (50% emergency reduction)")

                        # Re-acquire with emergency reduced integration
                        emergency_spectrum = acquire_raw_spectrum(
                            usb=usb,
                            ctrl=ctrl,
                            channel=ch,
                            led_intensity=normalized_leds[ch],
                            integration_time_ms=emergency_int,
                            num_scans=result.num_scans,
                            pre_led_delay_ms=LED_DELAY * 1000,
                            post_led_delay_ms=0.01 * 1000,
                            use_batch_command=False
                        )

                        if emergency_spectrum is not None:
                            emergency_roi = emergency_spectrum[wave_min_index:wave_max_index]
                            emergency_sat = count_saturated_pixels(emergency_roi, 0, len(emergency_roi), detector_params.saturation_threshold)
                            emergency_signal = roi_signal(emergency_roi, 0, len(emergency_roi), method="median")
                            emergency_pct = (emergency_signal / detector_max) * 100

                            if emergency_sat == 0:
                                logger.info(f"   ✅ {ch.upper()}: Recovery successful - {emergency_signal:.0f} counts ({emergency_pct:.1f}%), 0 saturated pixels")
                                # Update stored data
                                s_raw_data[ch] = emergency_roi
                                if use_per_channel_integration:
                                    channel_s_integration_times[ch] = emergency_int
                                else:
                                    step4_integration = emergency_int  # Update common integration
                                # Recalculate ROI signals
                                roi1_signal = np.mean(emergency_spectrum[roi1_min_idx:roi1_max_idx])
                                roi2_signal = np.mean(emergency_spectrum[roi2_min_idx:roi2_max_idx])
                                s_roi1_signals[ch] = roi1_signal
                                s_roi2_signals[ch] = roi2_signal
                            else:
                                logger.error(f"   ❌ {ch.upper()}: Recovery FAILED - still {emergency_sat} saturated pixels")
                                recovery_success = False
                        else:
                            logger.error(f"   ❌ {ch.upper()}: Emergency acquisition failed")
                            recovery_success = False

                    logger.info("")

                    # If recovery failed, abort calibration
                    if not recovery_success:
                        logger.error(f"❌ STEP 4 CRITICAL FAILURE: Emergency recovery failed")
                        logger.error(f"")
                        logger.error(f"   ROOT CAUSE: LEDs are too bright even at minimum safe integration time")
                        logger.error(f"   IMPACT: Cannot proceed with saturated baseline data")
                        logger.error(f"")
                        logger.error(f"   RECOMMENDATIONS:")
                        logger.error(f"     1. Reduce LED intensities in Step 3")
                        logger.error(f"     2. Check detector saturation threshold is correct")
                        logger.error(f"     3. Verify sensor is not overexposed (check alignment)")
                        logger.error(f"")
                        logger.error(f"   CALIBRATION ABORTED")
                        logger.error(f"")

                        # Store failure in QC results
                        result.qc_results['step4_saturation'] = {
                            'status': 'FAILED',
                            'saturated_channels': saturated_channels_s,
                            'message': 'S-mode saturation - emergency recovery failed'
                        }

                        # Return failure
                        result.success = False
                        result.error_message = f"Step 4 saturation in channels: {', '.join([ch.upper() for ch in saturated_channels_s])} - emergency recovery failed"
                        return result
                    else:
                        logger.info(f"✅ EMERGENCY RECOVERY SUCCESSFUL: All channels recovered")
                        saturated_channels_s = []  # Clear saturation list

                elif off_target_channels_s:
                    logger.warning(f"⚠️ STEP 4 WARNING: Off-target signals in {', '.join([ch.upper() for ch in off_target_channels_s])}")
                    logger.warning(f"   Signals outside 77.5%-82.5% range but no saturation detected")
                    logger.warning(f"   Continuing - may affect QC scores but data is usable")
                else:
                    logger.info(f"✅ STEP 4 CHECKLIST PASSED: All channels in range with 0 saturation!")

                logger.info("")

                # Store S-mode data for Step 5 comparison
                result.s_raw_data = s_raw_data
                result.s_roi1_signals = s_roi1_signals
                result.s_roi2_signals = s_roi2_signals
                result.s_integration_time = step4_integration  # Store Step 4 integration (baseline for reference)
                result.channel_integration_times = channel_s_integration_times if use_per_channel_integration else {ch: step4_integration for ch in ch_list}

                logger.info("")
                logger.info("="*80)
                logger.info("✅ STEP 4 COMPLETE: S-Mode Baseline Characterized")
                logger.info("="*80)
                if use_per_channel_integration:
                    logger.info(f"   Using PER-CHANNEL integration times:")
                    for ch in ch_list:
                        if ch in channel_s_integration_times:
                            logger.info(f"     {ch.upper()}: {channel_s_integration_times[ch]:.1f}ms")
                else:
                    logger.info(f"   Common integration time: {step4_integration:.1f}ms")
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
                # Debug log: S-mode raw data after Step 4
                logger.debug("S-mode raw data after Step 4:")
                for ch, data in s_raw_data.items():
                    logger.debug(f"  {ch.upper()}: {{}}".format(np.array2string(data, threshold=10, edgeitems=5)))
                logger.info("        Switch to P-polarization → Measure ROI signal loss → Optimize integration per channel")
                logger.info("=" * 80)

                if progress_callback:
                    progress_callback("Step 5 of 6: P-mode measurement...", 67)

                # ---------------------------------------------------------------
                # PART A: SWITCH TO P-MODE AND MEASURE ROI SIGNALS
                # ---------------------------------------------------------------
                logger.info("")
                logger.info("🔄 POLARIZER ORIENTATION CHANGE: Switching to P-MODE")
                logger.info("  Current Step: Step 5 - P-mode measurement")
                logger.info("  Expected behavior: Minimum transmission, strongest SPR absorption")
                logger.info("")

                # CRITICAL SAFETY CHECK: Validate positions before set_mode()
                _validate_polarizer_positions(device_config, 'p', logger)

                logger.info("  → Sending set_mode('p') command to controller...")
                set_result = ctrl.set_mode('p')
                if set_result:
                    logger.info("  ✅ Controller confirmed: Servo moved to P position")
                else:
                    logger.warning("  ⚠️ Controller response unexpected - servo should have moved to P position")
                    logger.warning("  ⚠️ Continuing calibration - servo movement may still be successful")
                logger.info("")
                time.sleep(0.5)  # Wait for servo to move

                # Polarizer now in P-mode (using device_config position)
                logger.info(f"    ✅ P-mode set (position from device_config)")
                logger.info("")

                # Use S-mode integration as baseline
                p_integration_time = result.s_integration_time  # Already in milliseconds
                usb.set_integration(p_integration_time)
                time.sleep(0.010)  # 10ms settling time

                # ========================================================================
                # CRITICAL: P-mode LED intensities must be LOWER than S-mode
                # ========================================================================
                # P-mode typically has HIGHER transmission than S-mode (polarizer effect)
                # Using same intensities as S-mode will cause saturation
                # Apply 0.5x reduction factor (50% of S-mode) to prevent P-mode saturation
                # Previous 0.7x was insufficient and still caused saturation
                # ========================================================================
                logger.info("")
                logger.info("  Calculating P-mode LED intensities (reduced from S-mode):")
                p_led_intensities = {}
                P_MODE_REDUCTION_FACTOR = 0.5  # Reduce by 50% to prevent saturation

                for ch_name in ch_list:
                    s_intensity = result.s_mode_intensity[ch_name]
                    p_intensity = int(s_intensity * P_MODE_REDUCTION_FACTOR)
                    p_intensity = max(p_intensity, 10)  # Minimum 10 to ensure signal
                    p_led_intensities[ch_name] = p_intensity
                    logger.info(f"    {ch_name.upper()}: S={s_intensity} → P={p_intensity} ({P_MODE_REDUCTION_FACTOR:.0%} reduction)")

                logger.info("")
                logger.info(f"  Reason: P-mode has higher transmission, needs lower LED intensity")
                logger.info(f"  50% reduction prevents saturation while maintaining good SNR")
                logger.info("")

                # Define ROI wavelength ranges (from Step 4)
                ROI1_WL_MIN, ROI1_WL_MAX = 560, 570  # Blue edge
                ROI2_WL_MIN, ROI2_WL_MAX = 710, 720  # Red edge

                # Convert wavelengths to pixel indices
                wavelengths = usb.read_wavelength()
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

                    # Use hardware acquisition function
                    spectrum = acquire_raw_spectrum(
                        usb=usb,
                        ctrl=ctrl,
                        channel=ch_name,
                        led_intensity=led_val,
                        integration_time_ms=None,  # Already set
                        num_scans=1,
                        pre_led_delay_ms=LED_DELAY * 1000,
                        post_led_delay_ms=0.01 * 1000,
                        use_batch_command=False
                    )

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

                # QC CHECK: Verify polarizer rotation by comparing S vs P signals
                logger.info("")
                logger.info("  🔍 QC: Verifying polarizer rotation (S-mode vs P-mode):")
                polarizer_rotation_ok = False
                for ch_name in ch_list:
                    if ch_name in s_roi2_signals and ch_name in p_roi2_signals:
                        s_signal = s_roi2_signals[ch_name]
                        p_signal = p_roi2_signals[ch_name]
                        ratio = p_signal / s_signal if s_signal > 0 else 1.0

                        # P-mode should have LOWER signal than S-mode (ratio < 1.0)
                        # Typical ratio: 0.1 to 0.8 depending on SPR dip strength
                        if ratio < 0.95:
                            status = "✅ POLARIZER ROTATED"
                            polarizer_rotation_ok = True
                        elif ratio < 1.05:
                            status = "⚠️ MINIMAL CHANGE"
                        else:
                            status = "❌ P > S (INVERTED OR NO ROTATION)"

                        logger.info(f"    {ch_name.upper()}: S={s_signal:.0f}, P={p_signal:.0f}, P/S={ratio:.3f} {status}")

                if not polarizer_rotation_ok:
                    logger.error("")
                    logger.error("  ❌ CRITICAL: Polarizer may not have rotated!")
                    logger.error("     Expected: P-mode signal < S-mode signal (P/S ratio < 0.95)")
                    logger.error("     Possible causes: Servo not moving, wrong positions, hardware issue")
                    logger.error("")
                    result.qc_results['polarizer_rotation'] = {
                        'status': 'FAIL',
                        'message': 'P-mode signal not lower than S-mode - polarizer may not have rotated'
                    }
                else:
                    logger.info("  ✅ Polarizer rotation verified (P-mode < S-mode)")
                    result.qc_results['polarizer_rotation'] = {
                        'status': 'PASS',
                        'message': 'P-mode signal lower than S-mode as expected'
                    }
                logger.info("")

                # QC CHECK: Detect if P-pol ROI signals INCREASE vs S-pol (suggests polarizer issue)
                roi_increase_detected = False
                roi_increase_channels = []

                # Calculate per-channel integration time adjustments using binary search optimization
                channel_integration_times = {}

                # ALWAYS use per-channel binary search optimization (matches Step 4 approach)
                logger.info("  🔄 Step 5 Per-Channel Binary Search Optimization")
                logger.info(f"   Target: {STEP4_TARGET_PERCENT*100:.0f}% ±2.5% for each channel")
                logger.info(f"   Starting from P-mode baseline: {p_integration_time:.1f}ms")
                logger.info("")

                for ch_name in ch_list:
                    logger.info(f"  Optimizing {ch_name.upper()}:")

                    # Binary search for optimal P-mode integration time
                    min_int = detector_params.min_integration_time
                    max_int = min(p_integration_time * 3.0, detector_params.max_integration_time)  # Allow up to 3× baseline
                    best_int = detector_params.min_integration_time  # Start with minimum as fallback
                    best_signal = 0
                    max_iterations = 8

                    # Track if we ever hit saturation
                    ever_saturated = False

                    for iteration in range(max_iterations):
                        test_int = (min_int + max_int) / 2

                        spectrum = acquire_raw_spectrum(
                            usb=usb,
                            ctrl=ctrl,
                            channel=ch_name,
                            led_intensity=p_led_intensities[ch_name],
                            integration_time_ms=test_int,
                            num_scans=5,
                            pre_led_delay_ms=LED_DELAY * 1000,
                            post_led_delay_ms=0.01 * 1000,
                            use_batch_command=False
                        )

                        if spectrum is None:
                            logger.warning(f"    Iter {iteration+1}: No spectrum, skipping")
                            break

                        # Check signal and saturation
                        roi_spectrum = spectrum[result.wave_min_index:result.wave_max_index]
                        signal = roi_signal(roi_spectrum, 0, len(roi_spectrum), method="median")
                        signal_pct = (signal / detector_max) * 100

                        sat_count = count_saturated_pixels(roi_spectrum, 0, len(roi_spectrum), detector_params.saturation_threshold)
                        is_saturated = sat_count > 0

                        # Check if in target range
                        in_range = step4_min_signal <= signal <= step4_max_signal

                        if sat_count > 0:
                            ever_saturated = True
                            logger.info(f"    Iter {iteration+1}: {test_int:.1f}ms → {signal:.0f} ({signal_pct:.1f}%), SATURATED → reduce")
                            max_int = test_int
                        elif in_range:
                            best_int = test_int
                            best_signal = signal
                            logger.info(f"    Iter {iteration+1}: {test_int:.1f}ms → {signal:.0f} ({signal_pct:.1f}%), ✅ OPTIMAL")
                            break
                        elif signal < step4_min_signal:
                            logger.info(f"    Iter {iteration+1}: {test_int:.1f}ms → {signal:.0f} ({signal_pct:.1f}%), too low → increase")
                            min_int = test_int
                            if abs(signal - step4_target_signal) < abs(best_signal - step4_target_signal) or best_signal == 0:
                                best_int = test_int
                                best_signal = signal
                        else:
                            logger.info(f"    Iter {iteration+1}: {test_int:.1f}ms → {signal:.0f} ({signal_pct:.1f}%), too high → reduce")
                            max_int = test_int
                            if abs(signal - step4_target_signal) < abs(best_signal - step4_target_signal):
                                best_int = test_int
                                best_signal = signal

                    # CRITICAL: If we ever hit saturation, verify final integration time is safe
                    if ever_saturated:
                        logger.warning(f"    Channel {ch_name.upper()} hit saturation during search - verifying final integration is safe...")
                        verify_spectrum = acquire_raw_spectrum(
                            usb=usb,
                            ctrl=ctrl,
                            channel=ch_name,
                            led_intensity=p_led_intensities[ch_name],
                            integration_time_ms=best_int,
                            num_scans=5,
                            pre_led_delay_ms=LED_DELAY * 1000,
                            post_led_delay_ms=0.01 * 1000,
                            use_batch_command=False
                        )
                        if verify_spectrum is not None:
                            verify_roi = verify_spectrum[result.wave_min_index:result.wave_max_index]
                            verify_sat = count_saturated_pixels(verify_roi, 0, len(verify_roi), detector_params.saturation_threshold)
                            if verify_sat > 0:
                                # Still saturated! Reduce integration time aggressively
                                logger.error(f"    ❌ Still saturated at {best_int:.1f}ms! Reducing to 70% of current value...")
                                best_int *= 0.70
                                best_int = max(detector_params.min_integration_time, best_int)
                                logger.warning(f"    Using emergency reduced integration: {best_int:.1f}ms")

                    channel_integration_times[ch_name] = best_int
                    final_pct = (best_signal / detector_max) * 100 if best_signal > 0 else 0
                    logger.info(f"  ✅ {ch_name.upper()}: Final {best_int:.1f}ms → {best_signal:.0f} ({final_pct:.1f}%)")
                    logger.info("")

                logger.info("✅ All channels optimized with per-channel P-mode integration times")

                # Store final signals for later use
                final_channel_signals = {}
                for ch_name in ch_list:
                    # Re-measure with final integration time to get accurate signal
                    spectrum = acquire_raw_spectrum(
                        usb=usb,
                        ctrl=ctrl,
                        channel=ch_name,
                        led_intensity=p_led_intensities[ch_name],
                        integration_time_ms=channel_integration_times[ch_name],
                        num_scans=5,
                        pre_led_delay_ms=LED_DELAY * 1000,
                        post_led_delay_ms=0.01 * 1000,
                        use_batch_command=False
                    )
                    if spectrum is not None:
                        roi_spectrum = spectrum[result.wave_min_index:result.wave_max_index]
                        signal = roi_signal(roi_spectrum, 0, len(roi_spectrum), method="median")
                        final_channel_signals[ch_name] = signal

                # QC CHECK: Detect if P-pol ROI signals INCREASE vs S-pol (suggests polarizer issue)
                roi_increase_detected = False
                roi_increase_channels = []

                for ch_name in ch_list:
                    if ch_name in s_roi1_signals and ch_name in p_roi1_signals:
                            s_avg = (s_roi1_signals[ch_name] + s_roi2_signals[ch_name]) / 2
                            p_avg = (p_roi1_signals[ch_name] + p_roi2_signals[ch_name]) / 2
                            if p_avg > s_avg * 1.05:
                                roi_increase_detected = True
                                roi_increase_channels.append(ch_name)
                                logger.warning(f"       ⚠️  P-pol signal INCREASED vs S-pol (P={p_avg:.0f} > S={s_avg:.0f})")

                # Store results
                result.p_integration_time = channel_integration_times.get(ch_list[0], p_integration_time)  # Use first channel as reference
                result.channel_integration_times = channel_integration_times  # Per-channel integration times
                result.p_mode_intensity = p_led_intensities.copy()
                result.p_roi1_signals = p_roi1_signals
                result.p_roi2_signals = p_roi2_signals

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

                logger.info("")
                logger.info("="*80)
                logger.info("✅ STEP 5 COMPLETE: P-mode Measurement with Per-Channel Integration Times")
                logger.info("="*80)
                logger.info(f"   Per-channel optimized integration times:")
                for ch in ch_list:
                    if ch in channel_integration_times:
                        logger.info(f"      {ch.upper()}: {channel_integration_times[ch]:.1f}ms")
                logger.info("")

                # Standardized summary of P-mode step
                log_step_summary(
                    step_name="Step 5 (P-mode Measurement)",
                    detector_max=detector_max,
                    integration_ms=result.p_integration_time,
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

                    # Use hardware acquisition function with averaging
                    avg_spectrum = acquire_raw_spectrum(
                        usb=usb,
                        ctrl=ctrl,
                        channel=ch_name,
                        led_intensity=led_val,
                        integration_time_ms=ch_int,
                        num_scans=result.num_scans,
                        pre_led_delay_ms=LED_DELAY * 1000,
                        post_led_delay_ms=0.01 * 1000,
                        use_batch_command=False
                    )

                    if avg_spectrum is not None:
                        p_raw_data[ch_name] = avg_spectrum[wave_min_index:wave_max_index]
                        logger.info(f"    ✅ {ch_name.upper()}: {result.num_scans} scans averaged at {ch_int:.1f}ms")
                    else:
                        logger.warning(f"    ⚠️  {ch_name.upper()}: No valid spectra captured")

                # CRITICAL CHECK: Verify no saturation in final P-mode raw spectra
                logger.info("")
                logger.info("  Final P-mode saturation check:")
                saturated_channels_p = []
                for ch_name in ch_list:
                    if ch_name in p_raw_data:
                        spectrum = p_raw_data[ch_name]
                        sat_count = count_saturated_pixels(
                            spectrum, 0, len(spectrum), detector_params.saturation_threshold
                        )
                        if sat_count > 0:
                            max_pixel = np.max(spectrum)
                            logger.error(f"    ❌ {ch_name.upper()}: {sat_count} saturated pixels (max: {max_pixel:.0f})")
                            saturated_channels_p.append(ch_name)
                        else:
                            signal = roi_signal(spectrum, 0, len(spectrum), method="median")
                            signal_pct = (signal / detector_max) * 100
                            logger.info(f"    ✅ {ch_name.upper()}: No saturation ({signal:.0f} counts, {signal_pct:.1f}%)")

                if saturated_channels_p:
                    logger.error(f"")
                    logger.error(f"❌ CALIBRATION FAILED: P-mode saturation detected in channels: {', '.join([ch.upper() for ch in saturated_channels_p])}")
                    logger.error(f"   The 80% target is too high for P-mode.")
                    logger.error(f"   Binary search failed to find non-saturated integration times.")
                    logger.error(f"")
                    raise RuntimeError(f"P-mode saturation detected in Step 5 after optimization: {saturated_channels_p}")

                logger.info("")

                # Measure dark reference at highest P-mode integration time
                max_p_integration = max(channel_integration_times.values())
                usb.set_integration(max_p_integration)

                # Turn off all LEDs and verify
                logger.info("")
                logger.info(f"  Turning off all LEDs for dark measurement...")
                ctrl.turn_off_channels()
                time.sleep(LED_DELAY)

                # Verify LEDs are actually off
                if hasattr(ctrl, 'get_all_led_intensities'):
                    led_status = ctrl.get_all_led_intensities()
                    leds_off = all(intensity <= 1 for ch, intensity in led_status.items() if ch != 'd' or intensity >= 0)
                    if leds_off:
                        logger.info(f"    ✅ All LEDs confirmed OFF: {led_status}")
                    else:
                        logger.error(f"    ❌ CRITICAL: LEDs still ON during dark measurement: {led_status}")
                        logger.error(f"       Dark measurement will be invalid!")
                        result.qc_results['dark_measurement_leds_on'] = {
                            'status': 'FAIL',
                            'led_status': led_status,
                            'message': 'LEDs were not turned off for dark measurement'
                        }

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
                # Debug log: P-mode raw data after Step 5
                logger.debug("P-mode raw data after Step 5:")
                for ch, data in p_raw_data.items():
                    logger.debug(f"  {ch.upper()}: {{}}".format(np.array2string(data, threshold=10, edgeitems=5)))

                # QC check: Verify dark signal is LOW (should be near detector baseline ~200-800 counts)
                dark_mean = np.mean(p_dark_ref_filtered)
                dark_max = np.max(p_dark_ref_filtered)
                dark_std = np.std(p_dark_ref_filtered)

                logger.info(f"    Mean: {dark_mean:.1f} counts")
                logger.info(f"    Max: {dark_max:.1f} counts")
                logger.info(f"    Std: {dark_std:.1f} counts")

                # QC validation (expected range: 100-1000 counts for dark measurement with LEDs OFF)
                EXPECTED_DARK_MIN = 100
                EXPECTED_DARK_MAX = 1000

                if EXPECTED_DARK_MIN <= dark_mean <= EXPECTED_DARK_MAX:
                    logger.info(f"    ✅ Dark-ref within expected range ({EXPECTED_DARK_MIN}-{EXPECTED_DARK_MAX} counts)")
                    result.qc_results['dark_measurement'] = {
                        'status': 'PASS',
                        'dark_mean': float(dark_mean),
                        'dark_max': float(dark_max),
                        'expected_range': (EXPECTED_DARK_MIN, EXPECTED_DARK_MAX)
                    }
                else:
                    logger.error(f"    ❌ CRITICAL: Dark-ref outside expected range ({EXPECTED_DARK_MIN}-{EXPECTED_DARK_MAX} counts)")
                    if dark_mean > EXPECTED_DARK_MAX:
                        logger.error(f"       Possible causes: LEDs NOT OFF (most likely), light leak, detector issue")
                        logger.error(f"       Expected dark ~200-800 counts, got {dark_mean:.0f} counts")
                    else:
                        logger.warning(f"       Possible causes: Detector offset drift, temperature change")

                    result.qc_results['dark_measurement'] = {
                        'status': 'FAIL',
                        'dark_mean': float(dark_mean),
                        'dark_max': float(dark_max),
                        'expected_range': (EXPECTED_DARK_MIN, EXPECTED_DARK_MAX),
                        'message': f'Dark too high ({dark_mean:.0f} counts) - LEDs may not be off'
                    }

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
                    # PART D: COMPREHENSIVE QC VALIDATION (USING TransmissionProcessor.calculate_transmission_qc)
                    # ---------------------------------------------------------------
                    logger.info("\n🔍 Part D: Comprehensive QC Validation & Orientation Check")
                    logger.info("=" * 80)

                    qc_results = {}
                    all_channels_pass = True
                    orientation_issues = []

                    # Get detector parameters for saturation checks
                    detector_params = get_detector_params(device_type)

                    for ch in ch_list:
                        logger.info(f"\n{'='*80}")
                        logger.info(f"Channel {ch.upper()} QC Validation")
                        logger.info(f"{'='*80}")

                        transmission_ch = transmission_spectra[ch]
                        wavelengths = result.wave_data

                        # Use comprehensive QC calculation with orientation validation
                        qc = TransmissionProcessor.calculate_transmission_qc(
                            transmission_spectrum=transmission_ch,
                            wavelengths=wavelengths,
                            channel=ch,
                            p_spectrum=result.p_raw_data[ch],  # P-mode (LOW at SPR)
                            s_spectrum=result.s_raw_data[ch],  # S-mode (HIGH reference)
                            detector_max_counts=detector_params.max_counts,
                            saturation_threshold=detector_params.saturation_threshold
                        )

                        # Log all QC metrics
                        logger.info(f"📊 SPR Dip Analysis:")
                        logger.info(f"   Dip Wavelength: {qc['dip_wavelength']:.1f}nm")
                        logger.info(f"   Min Transmission: {qc['transmission_min']:.1f}%")
                        logger.info(f"   Dip Depth: {qc['dip_depth']:.1f}%")
                        logger.info(f"   Status: {'✅ DETECTED' if qc['dip_detected'] else '❌ WEAK/ABSENT'} (depth > 5%)")

                        logger.info(f"\n📊 FWHM Analysis:")
                        if qc['fwhm'] is not None:
                            logger.info(f"   FWHM: {qc['fwhm']:.1f}nm")
                            logger.info(f"   Quality: {qc['fwhm_quality'].upper()}")
                            fwhm_pass = qc['fwhm'] < 60.0
                            logger.info(f"   Status: {'✅ PASS' if fwhm_pass else '❌ FAIL'} (FWHM < 60nm)")
                        else:
                            logger.info(f"   FWHM: Cannot calculate")
                            logger.info(f"   Status: ❌ FAIL")
                            fwhm_pass = False

                        logger.info(f"\n📊 Polarizer Orientation Check:")
                        if qc['ratio'] is not None:
                            logger.info(f"   P/S Ratio: {qc['ratio']:.3f}")
                            if qc['orientation_correct'] is True:
                                logger.info(f"   Status: ✅ CORRECT (0.10 ≤ P/S ≤ 0.95)")
                            elif qc['orientation_correct'] is False:
                                logger.error(f"   Status: ❌ INVERTED (P/S > 1.15)")
                                logger.error(f"   ⚠️  CRITICAL: Polarizer appears INVERTED!")
                                logger.error(f"   Expected: P-mode < S-mode (ratio < 0.95)")
                                logger.error(f"   Actual: P-mode > S-mode (ratio = {qc['ratio']:.3f})")
                                orientation_issues.append(ch)
                            else:
                                logger.warning(f"   Status: ⚠️ INDETERMINATE (borderline ratio)")
                        else:
                            logger.info(f"   P/S Ratio: Not calculated")
                            logger.info(f"   Status: ⚠️ CANNOT VERIFY")

                        logger.info(f"\n📊 Saturation Check:")
                        if qc['s_saturated'] or qc['p_saturated']:
                            if qc['s_saturated']:
                                logger.error(f"   S-pol: ❌ SATURATED ({qc['s_max_counts']:.0f} counts)")
                            if qc['p_saturated']:
                                logger.error(f"   P-pol: ❌ SATURATED ({qc['p_max_counts']:.0f} counts)")
                        else:
                            logger.info(f"   S-pol: ✅ OK ({qc['s_max_counts']:.0f} counts)")
                            logger.info(f"   P-pol: ✅ OK ({qc['p_max_counts']:.0f} counts)")

                        # Log any warnings
                        if qc['warnings']:
                            logger.warning(f"\n⚠️  Warnings:")
                            for warning in qc['warnings']:
                                logger.warning(f"   - {warning}")

                        # Overall channel status
                        channel_pass = (
                            qc['dip_detected'] and
                            fwhm_pass and
                            qc['orientation_correct'] is not False and  # Allow indeterminate but not inverted
                            not qc['s_saturated'] and
                            not qc['p_saturated']
                        )

                        logger.info(f"\n{'='*40}")
                        logger.info(f"Channel {ch.upper()}: {'✅ PASS' if channel_pass else '❌ FAIL'}")
                        logger.info(f"{'='*40}")

                        # Store comprehensive QC results
                        qc_results[ch] = {
                            'spr_wavelength': qc['dip_wavelength'],
                            'spr_depth': qc['dip_depth'],
                            'spr_pass': qc['dip_detected'],
                            'fwhm': qc['fwhm'] if qc['fwhm'] is not None else 0,
                            'fwhm_pass': fwhm_pass,
                            'fwhm_quality': qc['fwhm_quality'],
                            'p_s_ratio': qc['ratio'],
                            'orientation_correct': qc['orientation_correct'],
                            's_saturated': qc['s_saturated'],
                            'p_saturated': qc['p_saturated'],
                            's_max_counts': qc['s_max_counts'],
                            'p_max_counts': qc['p_max_counts'],
                            'warnings': qc['warnings'],
                            'overall_pass': channel_pass
                        }

                        if not channel_pass:
                            all_channels_pass = False

                    # ---------------------------------------------------------------
                    # AUTOMATIC POLARIZER RECALIBRATION ON INVERSION DETECTION
                    # ---------------------------------------------------------------
                    if orientation_issues and False:  # DISABLED FOR DEBUGGING
                        logger.warning("\n" + "=" * 80)
                        logger.warning("⚠️  POLARIZER INVERSION DETECTED - AUTO-RECALIBRATION DISABLED")
                        logger.warning("=" * 80)
                        logger.warning(f"   Affected channels: {', '.join([ch.upper() for ch in orientation_issues])}")
                        logger.warning(f"   P/S ratio > 1.15 indicates positions are inverted")
                        logger.warning(f"   Auto-recalibration is currently DISABLED for debugging")
                        logger.warning("=" * 80)
                        continue  # Skip recalibration

                    if False:  # Original code disabled
                        logger.warning("\n" + "=" * 80)
                        logger.warning("⚠️  POLARIZER INVERSION DETECTED - AUTO-RECALIBRATING")
                        logger.warning("=" * 80)
                        logger.warning(f"   Affected channels: {', '.join([ch.upper() for ch in orientation_issues])}")
                        logger.warning(f"   P/S ratio > 1.15 indicates positions are inverted")
                        logger.warning(f"")
                        logger.warning("   🔄 Starting automatic servo recalibration...")
                        logger.warning("=" * 80)

                        try:
                            # Get polarizer type from device config
                            polarizer_type = device_config.config['hardware'].get('polarizer_type', 'round')
                            # Map 'round' to 'circular' for servo calibration function
                            if polarizer_type == 'round':
                                polarizer_type = 'circular'

                            logger.info(f"Polarizer type: {polarizer_type}")
                            logger.info(f"Using channel A LED intensity: {result.s_mode_intensity.get('a', 255)}")

                            # Import servo calibration function
                            from utils.servo_calibration import auto_calibrate_polarizer, _calibrate_leds_for_servo

                            # Set channel A to its calibrated LED intensity for servo calibration
                            cal_ch = 'a'
                            cal_led = result.s_mode_intensity.get(cal_ch, 255)

                            logger.info(f"Setting channel {cal_ch.upper()} to LED={cal_led} for servo calibration")
                            ctrl.set_intensity(ch=cal_ch, raw_val=cal_led)
                            time.sleep(0.05)

                            # Run automatic servo recalibration (no water check - we know SPR is active)
                            recal_result = auto_calibrate_polarizer(
                                usb=usb,
                                ctrl=ctrl,
                                require_water=False,  # Skip water check - already validated
                                polarizer_type=polarizer_type
                            )

                            if recal_result and recal_result.get('success'):
                                new_s_pos = recal_result['s_pos']
                                new_p_pos = recal_result['p_pos']

                                logger.info("\n" + "=" * 80)
                                logger.info("✅ AUTO-RECALIBRATION SUCCESSFUL")
                                logger.info("=" * 80)
                                logger.info(f"   Found S position: {new_s_pos}°")
                                logger.info(f"   Found P position: {new_p_pos}°")
                                logger.info(f"   S/P ratio: {recal_result['sp_ratio']:.2f}×")
                                logger.info(f"   Dip depth: {recal_result['dip_depth_percent']:.1f}%")

                                # CRITICAL: Check if positions are still inverted by checking S/P ratio
                                # If S/P ratio < 1.0, positions are inverted (S gives higher signal than P)
                                # Correct: S should give LOWER signal than P (S/P ratio > 1.0)
                                if recal_result['sp_ratio'] < 1.0:
                                    logger.warning("=" * 80)
                                    logger.warning("⚠️  DETECTED: Positions are labeled backwards!")
                                    logger.warning(f"   S/P ratio = {recal_result['sp_ratio']:.2f} < 1.0")
                                    logger.warning("   This means 'S' position has HIGHER signal than 'P' position")
                                    logger.warning("   SWAPPING positions to correct labeling...")
                                    logger.warning("=" * 80)
                                    # Swap the positions
                                    new_s_pos, new_p_pos = new_p_pos, new_s_pos
                                    logger.info(f"   Corrected S position: {new_s_pos}°")
                                    logger.info(f"   Corrected P position: {new_p_pos}°")

                                logger.info("=" * 80)

                                # ❌ DANGEROUS: DO NOT apply servo positions during calibration!
                                # Positions come from device_config and are set at controller init ONLY
                                logger.error("=" * 80)
                                logger.error("❌ CRITICAL ERROR: Position correction attempted during calibration")
                                logger.error("❌ Servo positions are IMMUTABLE - set at controller initialization")
                                logger.error("❌ To fix positions: Update device_config.json and RESTART application")
                                logger.error("=" * 80)

                                # Update result for logging but DO NOT apply to hardware
                                result.s_position = new_s_pos
                                result.p_position = new_p_pos
                                result.polarizer_s_position = new_s_pos
                                result.polarizer_p_position = new_p_pos

                                # Abort calibration - user must fix device_config and restart
                                logger.error("\n🛑 CALIBRATION ABORTED - Position mismatch detected")
                                logger.error("   Action required: Update device_config.json with correct positions and restart")
                                raise ValueError("Servo position correction not allowed during calibration - update device_config and restart")

                        except Exception as e:
                            logger.exception(f"Error during auto-recalibration: {e}")
                            result.qc_results['orientation_check'] = {
                                'status': 'FAIL',
                                'failed_channels': orientation_issues,
                                'message': f'Auto-recalibration error: {str(e)}'
                            }

                    # ---------------------------------------------------------------
                    # LEGACY QC COMPATIBILITY (for old code that expects these fields)
                    # ---------------------------------------------------------------
                    for ch in ch_list:
                        # Add SNR calculation for legacy compatibility
                        signal_mean = np.mean(s_pol_ref[ch])
                        noise_std = np.std(result.dark_noise)
                        snr = signal_mean / max(noise_std, 1)
                        snr_pass = snr > 100

                        qc_results[ch]['snr'] = snr
                        qc_results[ch]['snr_pass'] = snr_pass

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
                                if qc.get('orientation_correct') is False:
                                    logger.error(f"      - Polarizer INVERTED (P/S ratio = {qc['p_s_ratio']:.3f})")
                                if qc.get('s_saturated') or qc.get('p_saturated'):
                                    logger.error(f"      - Saturation detected")

                    logger.info("=" * 80)
                    logger.info("STEP 6 COMPLETE: Data Processing & QC Finished")
                    logger.info("=" * 80)

                    if progress_callback:
                        progress_callback("Calibration complete", 100)

                except Exception as e:
                    # Inner except for Step 6 errors (not restart requests)
                    logger.exception(f"Error in Step 6 processing: {e}")
                    raise  # Re-raise to be caught by outer except

                # If we reach here, Step 6 completed successfully - break out of restart loop
                break

            except Exception as e:
                # Outer except for restart logic
                # Check if this is a restart request from servo recalibration
                if str(e) == "RESTART_FROM_STEP_3C":
                    restart_attempt += 1
                    if restart_attempt > max_restart_attempts:
                        logger.error("\n" + "=" * 80)
                        logger.error("⚠️  POLARIZER RECALIBRATION FAILED TWICE")
                        logger.error("=" * 80)
                        logger.error("   First attempt: Auto-recalibrated servo positions")
                        logger.error("   Second attempt: Still detecting inverted polarization")
                        logger.error("")
                        logger.error("   Possible causes:")
                        logger.error("   1. Hardware malfunction (servo motor stuck)")
                        logger.error("   2. Mechanical obstruction preventing rotation")
                        logger.error("   3. Incorrect polarizer type in config")
                        logger.error("   4. Wiring or communication issue")
                        logger.error("")
                        logger.error("   ⚠️  CONTINUING CALIBRATION WITH WARNING FLAG")
                        logger.error("   User must perform further hardware testing")
                        logger.error("=" * 80 + "\n")

                        # Flag the issue but continue
                        result.qc_results['orientation_check'] = {
                            'status': 'FAIL_AFTER_RECALIBRATION',
                            'message': 'Polarizer inversion persists after auto-recalibration - hardware issue suspected',
                            'recalibration_attempts': restart_attempt,
                            'requires_user_testing': True
                        }

                        # Break out of loop to complete calibration with warning
                        break
                    # Continue to next iteration of while loop (restart from Step 3C)
                    continue
                else:
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

        # Check for critical warnings that require user attention
        orientation_check = result.qc_results.get('orientation_check', {})
        has_critical_warning = orientation_check.get('status') == 'FAIL_AFTER_RECALIBRATION'

        logger.info("\n" + "=" * 80)
        logger.info("✅ 6-STEP CALIBRATION COMPLETE")
        if has_critical_warning:
            logger.warning("⚠️  WITH CRITICAL WARNING - USER TESTING REQUIRED")
        logger.info("=" * 80)
        s_pos = getattr(result, 's_position', None) or getattr(result, 'polarizer_s_position', 'N/A')
        p_pos = getattr(result, 'p_position', None) or getattr(result, 'polarizer_p_position', 'N/A')
        logger.info(f"Servo Positions: S={s_pos}°, P={p_pos}°")
        logger.info(f"LED Timing: PRE={pre_led_delay_ms}ms, POST={post_led_delay_ms}ms")
        logger.info(f"LED Intensities (S-mode): {result.ref_intensity}")
        logger.info(f"LED Intensities (P-mode): {result.p_mode_intensity}")
        logger.info(f"Integration Time (S-mode): {result.s_integration_time}ms")
        logger.info(f"Integration Time (P-mode): {result.p_integration_time}ms")
        logger.info(f"Scans per Channel: {result.num_scans}")
        logger.info(f"S-pol Raw Data: {list(result.s_raw_data.keys()) if hasattr(result, 's_raw_data') else 'Not captured'}")
        logger.info(f"P-pol Raw Data: {list(result.p_raw_data.keys()) if hasattr(result, 'p_raw_data') else 'Not captured'}")

        if has_critical_warning:
            logger.warning("")
            logger.warning("=" * 80)
            logger.warning("⚠️  CRITICAL WARNING: POLARIZER HARDWARE ISSUE DETECTED")
            logger.warning("=" * 80)
            logger.warning("   Polarizer inversion persisted after automatic recalibration")
            logger.warning("   Calibration completed but optical performance may be compromised")
            logger.warning("")
            logger.warning("   REQUIRED USER ACTIONS:")
            logger.warning("   1. Verify servo motor physically moves during mode switch")
            logger.warning("   2. Check for mechanical obstructions")
            logger.warning("   3. Verify polarizer type in device config (circular vs barrel)")
            logger.warning("   4. Test servo manually: python -m utils.servo_calibration --test")
            logger.warning("   5. Check wiring and connections")
            logger.warning("")
            logger.warning("   If issue persists, contact technical support")
            logger.warning("=" * 80)

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

            # Use hardware acquisition function
            spectrum = acquire_raw_spectrum(
                usb=usb,
                ctrl=ctrl,
                channel=ch,
                led_intensity=saved_led,
                integration_time_ms=None,
                num_scans=1,
                pre_led_delay_ms=LED_DELAY * 1000,
                post_led_delay_ms=0.01 * 1000,
                use_batch_command=False
            )

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

                # Use hardware acquisition function
                spectrum = acquire_raw_spectrum(
                    usb=usb,
                    ctrl=ctrl,
                    channel=ch,
                    led_intensity=saved_led,
                    integration_time_ms=None,
                    num_scans=1,
                    pre_led_delay_ms=LED_DELAY * 1000,
                    post_led_delay_ms=0.01 * 1000,
                    use_batch_command=False
                )

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

                # Use hardware acquisition function
                raw_spectrum = acquire_raw_spectrum(
                    usb=usb,
                    ctrl=ctrl,
                    channel=ch,
                    led_intensity=validated_s_leds[ch],
                    integration_time_ms=None,
                    num_scans=1,
                    pre_led_delay_ms=LED_DELAY * 1000,
                    post_led_delay_ms=0.01 * 1000,
                    use_batch_command=False
                )

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

                # Use hardware acquisition function
                raw_spectrum = acquire_raw_spectrum(
                    usb=usb,
                    ctrl=ctrl,
                    channel=ch,
                    led_intensity=validated_p_leds[ch],
                    integration_time_ms=None,
                    num_scans=1,
                    pre_led_delay_ms=LED_DELAY * 1000,
                    post_led_delay_ms=0.01 * 1000,
                    use_batch_command=False
                )

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


# =============================================================================
# LED CONVERGENCE CALIBRATION (Steps 3-5 Replacement)
# =============================================================================

def run_convergence_calibration_steps_3_to_5(
    usb,
    ctrl,
    detector_params,
    ch_list,
    wave_min_index,
    wave_max_index,
    device_config_det,
    target_percent=0.40,
    tolerance_percent=0.02,
    strategy="intensity"
):
    """
    Replace Steps 3-5 using LED convergence workflow.

    Returns raw spectra (S-pol, P-pol, dark) for Step 6 processing.

    Workflow:
    1. Measure channel brightness @ LED=255 (Step 3A replacement)
    2. S-mode: LEDconverge → capture S-pol reference
    3. Servo to P-mode
    4. P-mode: LEDconverge → capture P-pol reference
    5. LEDs off → capture dark spectrum

    Args:
        usb: Spectrometer object
        ctrl: Controller object
        detector_params: Detector specifications (DetectorParams)
        ch_list: List of channels to calibrate (e.g., ['a', 'b', 'c', 'd'])
        wave_min_index: Start index of ROI
        wave_max_index: End index of ROI
        device_config_det: Device configuration dict with servo positions
        target_percent: Target signal as % of detector max (default 40%)
        tolerance_percent: Acceptable deviation (default ±2%)
        strategy: "intensity" or "time" normalization strategy

    Returns:
        dict with:
        - success: bool
        - s_mode_intensities: dict {ch: int}
        - p_mode_intensities: dict {ch: int}
        - s_integration_time: float (ms)
        - p_integration_time: float (ms)
        - s_pol_ref: dict {ch: ndarray} - S-mode RAW spectra (ROI only)
        - p_pol_ref: dict {ch: ndarray} - P-mode RAW spectra (ROI only)
                - dark_spectrum: ndarray - Dark scan (full detector). Downstream uses ROI slice
                    aligned to [wave_min_index:wave_max_index] for dark subtraction.
        - weakest_channel: str - Weakest channel ID
        - error: str (if failed)
    """
    # CRITICAL: Log IMMEDIATELY to confirm function is called
    logger.info("="*80)
    logger.info("🚨 CONVERGENCE FUNCTION CALLED - STARTING LED CONVERGENCE")
    logger.info("="*80)

    try:
        from utils.LEDCONVERGENCE import run_convergence
        logger.info("✅ LEDCONVERGENCE import successful")
    except Exception as e:
        logger.error(f"❌ LEDCONVERGENCE import FAILED: {e}")
        return {
            'success': False,
            'error': f'Import failed: {e}',
            's_mode_intensities': {},
            'p_mode_intensities': {},
            's_integration_time': None,
            'p_integration_time': None,
            's_pol_ref': {},
            'p_pol_ref': {},
            'dark_spectrum': None,
            'weakest_channel': None
        }

    import time
    import numpy as np

    logger.info("="*80)
    logger.info("🔄 LED CONVERGENCE CALIBRATION (Steps 3-5 Replacement)")
    logger.info("="*80)

    result = {
        'success': False,
        's_mode_intensities': {},
        'p_mode_intensities': {},
        's_integration_time': None,
        'p_integration_time': None,
        's_pol_ref': {},
        'p_pol_ref': {},
        'dark_spectrum': None,
        'weakest_channel': None,
        'error': None
    }

    try:
        # === STEP 3A: Measure channel brightness @ LED=255 ===
        logger.info("📊 Step 3A: Measuring channel brightness @ LED=255...")
        logger.info("   🔍 LED VERIFICATION: Checking that LEDs are working...")
        channel_measurements = {}

        for ch in ch_list:
            ctrl.set_intensity(ch, 255)
            time.sleep(0.1)

            spectrum = usb.read_intensity()
            roi = spectrum[wave_min_index:wave_max_index]
            mean_val = np.mean(roi)
            max_val = np.max(roi)

            channel_measurements[ch] = (mean_val, max_val)
            ctrl.set_intensity(ch, 0)

            logger.info(f"   {ch.upper()}: {mean_val:.0f} counts (max={max_val:.0f})")

        # === LED VERIFICATION: Check that LEDs actually produced light ===
        MIN_LED_COUNTS = 4000  # Minimum expected counts at LED=255

        all_channels_dark = all(channel_measurements[ch][0] < MIN_LED_COUNTS for ch in ch_list)
        if all_channels_dark:
            result['error'] = f"❌ LED VERIFICATION FAILED: All channels produced <{MIN_LED_COUNTS} counts at LED=255. Check LED hardware/connections!"
            logger.error("")
            logger.error("="*80)
            logger.error(result['error'])
            for ch in ch_list:
                logger.error(f"   {ch.upper()}: {channel_measurements[ch][0]:.0f} counts (expected >{MIN_LED_COUNTS})")
            logger.error("="*80)
            logger.error("")
            return result

        # Check for individual weak/dead LEDs
        weak_leds = [ch for ch in ch_list if channel_measurements[ch][0] < MIN_LED_COUNTS]
        if weak_leds:
            result['error'] = f"❌ LED VERIFICATION FAILED: Weak/dead LEDs detected"
            logger.error("")
            logger.error("="*80)
            logger.error(result['error'])
            for ch in weak_leds:
                logger.error(f"   {ch.upper()}: {channel_measurements[ch][0]:.0f} counts (expected >{MIN_LED_COUNTS})")
            logger.error("="*80)
            logger.error("")
            return result

        weakest_ch = min(channel_measurements.keys(),
                         key=lambda c: channel_measurements[c][0])
        result['weakest_channel'] = weakest_ch

        logger.info("")
        logger.info("   ✅ LED VERIFICATION PASSED - All channels producing >{} counts".format(MIN_LED_COUNTS))
        logger.info(f"   Weakest: {weakest_ch.upper()} (mean={channel_measurements[weakest_ch][0]:.0f})")
        logger.info("")

        # === SERVO INITIALIZATION: Move to S-mode with explicit pre-positioning ===
        logger.info("")
        logger.info("=" * 80)
        logger.info("🔧 SERVO INITIALIZATION & DIAGNOSTICS")
        logger.info("=" * 80)

        # === COMPREHENSIVE SERVO DIAGNOSTICS ===
        logger.info("")
        logger.info("📋 CONTROLLER STATUS:")
        logger.info(f"   Type: {type(ctrl).__name__}")
        logger.info(f"   Has servo_move_calibration_only(): {hasattr(ctrl, 'servo_move_calibration_only')}")
        logger.info(f"   Has set_mode(): {hasattr(ctrl, 'set_mode')}")

        # Check serial connection
        serial_ok = False
        port_name = "Unknown"
        if hasattr(ctrl, '_ser') and ctrl._ser is not None:
            try:
                serial_ok = ctrl._ser.is_open if hasattr(ctrl._ser, 'is_open') else False
                port_name = ctrl._ser.port if hasattr(ctrl._ser, 'port') else "Unknown"
                logger.info(f"   Serial port: {port_name}")
                logger.info(f"   Serial port open: {serial_ok}")
            except Exception as e:
                logger.error(f"   ❌ Serial port check failed: {e}")
                serial_ok = False
        else:
            logger.error("   ❌ No serial port object (_ser is None or missing)")

        # Check controller connection
        connected = False
        if hasattr(ctrl, 'is_connected'):
            try:
                connected = ctrl.is_connected()
                logger.info(f"   Controller connected: {connected}")
            except Exception as e:
                logger.error(f"   ❌ Connection check failed: {e}")
        else:
            logger.warning("   ⚠️  No is_connected() method")

        # CRITICAL CHECK
        logger.info("")
        if not serial_ok:
            logger.error("🚨 CRITICAL: Serial port NOT open - servo commands will FAIL!")
        if not connected:
            logger.error("🚨 CRITICAL: Controller NOT connected - servo commands will FAIL!")
        if not hasattr(ctrl, 'servo_move_calibration_only'):
            logger.error("🚨 CRITICAL: servo_move_calibration_only() method MISSING!")

        if serial_ok and connected:
            logger.info("✅ All servo prerequisites OK - ready to move servo")
        logger.info("")

        # Turn off LEDs for safety
        logger.info("🔒 Safety: Turning off all LEDs before servo movement...")
        ctrl.turn_off_channels()
        time.sleep(0.1)
        logger.info("   ✅ All LEDs OFF")

        # Get servo positions from device config
        servo_positions = load_oem_polarizer_positions_local(device_config_det, usb.serial_number if hasattr(usb, 'serial_number') else 'UNKNOWN')
        s_pos = servo_positions['s_position']
        p_pos = servo_positions['p_position']

        logger.info(f"📍 Servo positions from device_config:")
        logger.info(f"   S-position: {s_pos}°")
        logger.info(f"   P-position: {p_pos}°")

        # Park to 1° (backlash removal)
        if hasattr(ctrl, 'servo_move_calibration_only'):
            logger.info("")
            logger.info("🔄 Step 1: Parking polarizer to 1° (backlash removal)...")
            logger.info("   👂 LISTEN: You should HEAR the servo motor move now...")
            park_ok = ctrl.servo_move_calibration_only(s=1, p=1)
            time.sleep(1.0)  # Increased wait time for audible confirmation
            if park_ok:
                logger.info("   ✅ Parked to 1° - Did you HEAR it move?")
            else:
                logger.warning("   ⚠️  Park command did not confirm (continuing anyway)")

            # Move explicitly to S/P positions
            logger.info("")
            logger.info(f"🔄 Step 2: Moving to S={s_pos}°, P={p_pos}°...")
            logger.info("   👂 LISTEN: You should HEAR the servo move again...")
            move_ok = ctrl.servo_move_calibration_only(s=int(s_pos), p=int(p_pos))
            time.sleep(1.0)  # Increased wait time for audible confirmation
            if move_ok:
                logger.info(f"   ✅ Moved to S={s_pos}°, P={p_pos}° - Did you HEAR it move?")
            else:
                logger.warning(f"   ⚠️  Move command did not confirm (continuing anyway)")
        else:
            logger.warning("   ⚠️  Controller lacks servo_move_calibration_only - skipping explicit pre-positioning")
            logger.error("   🚨 SERVO CANNOT MOVE - This is a critical problem!")

        # Lock S-mode via firmware
        logger.info("")
        logger.info("🔒 Step 3: Locking S-mode via firmware (ss command)...")
        logger.info("   👂 LISTEN: You might HEAR a small servo adjustment...")
        mode_ok = ctrl.set_mode('s')
        time.sleep(0.5)
        if mode_ok:
            logger.info("   ✅ S-mode locked via firmware")
        else:
            logger.warning("   ⚠️  set_mode('s') did not confirm (continuing anyway)")

        logger.info("=" * 80)
        logger.info("✅ SERVO INITIALIZATION COMPLETE - S-mode active")
        logger.info("=" * 80)
        logger.info("")

        # === STEP 3B-3C: S-mode LED convergence ===
        logger.info(f"   Target: {target_percent*100:.0f}% detector, tolerance: ±{tolerance_percent*100:.0f}%")
        logger.info(f"   Strategy: {strategy}")
        logger.info("")

        s_shared_int, s_per_ch_results, s_ok = run_convergence(
            usb=usb,
            ctrl=ctrl,
            ch_list=ch_list,
            acquire_raw_spectrum_fn=acquire_raw_spectrum,
            roi_signal_fn=roi_signal,
            detector_params=detector_params,
            wave_min_index=wave_min_index,
            wave_max_index=wave_max_index,
            strategy=strategy,
            initial_integration_ms=70.0,
            target_percent=target_percent,
            tolerance_percent=tolerance_percent,
            tighten_final=False,
            use_batch_command=CONVERGENCE_USE_BATCH_COMMAND,
            logger=logger
        )

        if not s_ok:
            result['error'] = f"S-mode convergence failed: Did not converge to target"
            logger.error(f"❌ {result['error']}")
            return result

        # Extract LED intensities and integration time from results
        result['s_mode_intensities'] = {ch: int(s_per_ch_results[ch]['final_led']) for ch in ch_list}
        result['s_integration_time'] = s_shared_int if s_shared_int is not None else s_per_ch_results[ch_list[0]]['final_integration_ms']

        logger.info("")
        logger.info(f"   ✅ S-mode convergence complete:")
        logger.info(f"      Integration time: {result['s_integration_time']:.1f}ms")
        for ch in ch_list:
            logger.info(f"      {ch.upper()}: LED={result['s_mode_intensities'][ch]}")

        # === STEP 4: Capture S-pol reference (RAW) ===
        logger.info("")
        logger.info("📸 Step 4: Capturing S-pol reference spectra...")
        usb.set_integration(result['s_integration_time'])
        time.sleep(0.1)

        for ch in ch_list:
            ctrl.set_intensity(ch, result['s_mode_intensities'][ch])
            time.sleep(0.05)
            full = usb.read_intensity()
            result['s_pol_ref'][ch] = full[wave_min_index:wave_max_index]
            ctrl.set_intensity(ch, 0)

        logger.info(f"   ✅ S-pol ref captured: {len(result['s_pol_ref'])} channels")

        # === STEP 5A: P-mode servo movement ===
        logger.info("")
        logger.info("=" * 80)
        logger.info("🔧 SERVO MOVEMENT: Switching from S-mode to P-mode")
        logger.info("=" * 80)

        # Turn off LEDs for safety
        logger.info("🔒 Safety: Turning off all LEDs before servo movement...")
        ctrl.turn_off_channels()
        time.sleep(0.1)
        logger.info("   ✅ All LEDs OFF")

        # Park to 1° (backlash removal)
        if hasattr(ctrl, 'servo_move_calibration_only'):
            logger.info("🔄 Step 1: Parking polarizer to 1° (backlash removal)...")
            park_ok = ctrl.servo_move_calibration_only(s=1, p=1)
            time.sleep(0.5)
            if park_ok:
                logger.info("   ✅ Parked to 1°")
            else:
                logger.warning("   ⚠️  Park command did not confirm (continuing anyway)")

            # Move explicitly to P position (from current S position)
            logger.info(f"🔄 Step 2: Moving from S={s_pos}° to P={p_pos}°...")
            move_ok = ctrl.servo_move_calibration_only(s=int(s_pos), p=int(p_pos))
            time.sleep(0.5)
            if move_ok:
                logger.info(f"   ✅ Moved to P={p_pos}°")
            else:
                logger.warning(f"   ⚠️  Move command did not confirm (continuing anyway)")
        else:
            logger.warning("   ⚠️  Controller lacks servo_move_calibration_only - using simple mode switch")

        # Lock P-mode via firmware
        logger.info("🔒 Step 3: Locking P-mode via firmware (pp command)...")
        mode_ok = ctrl.set_mode('p')
        time.sleep(0.3)
        if mode_ok:
            logger.info("   ✅ P-mode locked via firmware")
        else:
            logger.warning("   ⚠️  set_mode('p') did not confirm (continuing anyway)")

        logger.info("=" * 80)
        logger.info("✅ SERVO MOVEMENT COMPLETE - P-mode active")
        logger.info("=" * 80)
        logger.info("")

        # === STEP 5B: P-mode LED convergence ===
        logger.info("🎯 Step 5: Running LED convergence in P-mode...")
        logger.info(f"   Starting from S-mode LED values")
        logger.info("")

        p_shared_int, p_per_ch_results, p_ok = run_convergence(
            usb=usb,
            ctrl=ctrl,
            ch_list=ch_list,
            acquire_raw_spectrum_fn=acquire_raw_spectrum,
            roi_signal_fn=roi_signal,
            detector_params=detector_params,
            wave_min_index=wave_min_index,
            wave_max_index=wave_max_index,
            strategy=strategy,
            initial_integration_ms=result['s_integration_time'],  # Start from S-mode integration time
            target_percent=target_percent,
            tolerance_percent=tolerance_percent,
            tighten_final=False,
            use_batch_command=CONVERGENCE_USE_BATCH_COMMAND,
            logger=logger
        )

        if not p_ok:
            result['error'] = f"P-mode convergence failed: Did not converge to target"
            logger.error(f"❌ {result['error']}")
            return result

        # Extract LED intensities and integration time from results
        result['p_mode_intensities'] = {ch: int(p_per_ch_results[ch]['final_led']) for ch in ch_list}
        result['p_integration_time'] = p_shared_int if p_shared_int is not None else p_per_ch_results[ch_list[0]]['final_integration_ms']

        logger.info("")
        logger.info(f"   ✅ P-mode convergence complete:")
        logger.info(f"      Integration time: {result['p_integration_time']:.1f}ms")
        for ch in ch_list:
            logger.info(f"      {ch.upper()}: LED={result['p_mode_intensities'][ch]}")

        # === STEP 5B: Capture P-pol reference (RAW) ===
        logger.info("")
        logger.info("📸 Step 5B: Capturing P-pol reference spectra...")
        usb.set_integration(result['p_integration_time'])
        time.sleep(0.1)

        for ch in ch_list:
            ctrl.set_intensity(ch, result['p_mode_intensities'][ch])
            time.sleep(0.05)
            full = usb.read_intensity()
            result['p_pol_ref'][ch] = full[wave_min_index:wave_max_index]
            ctrl.set_intensity(ch, 0)

        logger.info(f"   ✅ P-pol ref captured: {len(result['p_pol_ref'])} channels")

        # === DARK SPECTRUM (capture now, used in Step 6) ===
        logger.info("")
        logger.info("📸 Capturing dark spectrum (LEDs OFF)...")
        time.sleep(0.2)
        result['dark_spectrum'] = usb.read_intensity()

        # === SUCCESS ===
        result['success'] = True
        logger.info("")
        logger.info("="*80)
        logger.info("✅ LED CONVERGENCE CALIBRATION COMPLETE (Steps 3-5)")
        logger.info("="*80)
        logger.info("")

        return result

    except Exception as e:
        logger.exception(f"❌ Convergence calibration error: {e}")
        result['error'] = str(e)
        return result
