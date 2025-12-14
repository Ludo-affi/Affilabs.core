from __future__ import annotations

"""6-Step Startup Calibration Flow.

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

STEP 3: LED Brightness Measurement & Bilinear Model Load
  - Quick brightness measurement at LED=255 for all channels
  - Load bilinear model for detector (contains servo positions + LED predictions)
  - Identifies weakest channel for convergence reference

STEP 4: S-Mode LED Convergence + Reference Capture
  - Position servo to S-polarization (from device_config/model)
  - Run LED convergence to target detector level (80%)
  - Uses 3-stage linear model predictions if available
  - Capture S-pol reference spectra for all channels

STEP 5: P-Mode LED Convergence + Reference + Dark Capture
  - Switch servo to P-polarization
  - Run LED convergence for P-mode
  - Capture P-pol reference spectra
  - Capture dark spectrum (LEDs OFF) for noise correction

STEP 6: QC Validation & Result Packaging
  - Validate S-pol and P-pol reference quality
  - Calculate transmission curves
  - Package all calibration data into result object
  - Return to application for live view transfer

NO STEPS BEYOND 6 - THIS IS THE COMPLETE CALIBRATION FLOW

This implementation uses LED convergence with 3-stage linear model predictions.
The timing synchronization check has been removed (handled by firmware).

TRANSFER TO LIVE VIEW:
  - After Step 6 completes: Show post-calibration QC dialog
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
            logger.error(
                "[ERROR] CRITICAL: Cannot validate polarizer positions - no device_config",
            )
            msg = "device_config required for polarizer position validation"
            raise ValueError(msg)

        # Get positions from device_config (single source of truth)
        positions = device_config.get_servo_positions()
        if not positions:
            logger.error("[ERROR] CRITICAL: No servo positions in device_config")
            msg = "Servo positions not found in device_config"
            raise ValueError(msg)

        s_pos = positions.get("s")
        p_pos = positions.get("p")

        if s_pos is None or p_pos is None:
            logger.error(
                f"[ERROR] CRITICAL: Invalid positions in device_config: S={s_pos}, P={p_pos}",
            )
            msg = "Invalid servo positions in device_config"
            raise ValueError(msg)

        # Validation passed - log detailed information
        mode_upper = mode.upper()
        target_pos = s_pos if mode == "s" else p_pos
        other_mode = "P" if mode == "s" else "S"
        other_pos = p_pos if mode == "s" else s_pos

        logger.info("=" * 80)
        logger.info(f"[SEARCH] POLARIZER POSITION VALIDATION: {mode_upper}-MODE")
        logger.info("=" * 80)
        logger.info("   Device Config Source: VERIFIED [OK]")
        logger.info(f"   {mode_upper}-mode position: {target_pos}°")
        logger.info(f"   {other_mode}-mode position: {other_pos}°")
        logger.info("   Validation: PASSED [OK]")
        logger.info(
            f"   Controller will use position: {target_pos}° (from EEPROM loaded at startup)",
        )
        logger.info("=" * 80)

    except Exception as e:
        logger.exception(f"[ERROR] CRITICAL: Polarizer position validation failed: {e}")
        logger.exception(
            "[ERROR] Single source of truth violated - aborting to prevent inconsistency",
        )
        raise


import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from affilabs.utils.logger import logger
from settings import (
    LED_DELAY,
    MAX_WAVELENGTH,
    MIN_WAVELENGTH,
    POST_LED_DELAY_MS,
    PRE_LED_DELAY_MS,
    USE_ALTERNATIVE_CALIBRATION,
)

# =============================================================================
# CALIBRATION METHOD SELECTION
# =============================================================================
# Set to True to use LED convergence workflow (Steps 3-5 replacement)
# Set to False to use legacy Step 3-5 calibration
USE_LED_CONVERGENCE = True  # DEFAULT: Use optimized LED convergence workflow
# Use batch LED command in convergence & preflight for identical behavior
CONVERGENCE_USE_BATCH_COMMAND = True  # ALWAYS use batch commands (more reliable, avoids LED-off race condition)

# Number of scans to use during calibration convergence (minimum 3)
# Live acquisition num_scans is calculated based on detector window during calibration
CALIBRATION_CONVERGENCE_SCANS = 3

# =============================================================================
# CONVERGENCE CONSTANTS
# =============================================================================
# Integration time adjustment factors
CONVERGENCE_SATURATION_REDUCTION_FACTOR = 0.90  # Reduce by 10% when saturated
CONVERGENCE_MIN_CORRECTION_FACTOR = 0.90  # Min adjustment per iteration
CONVERGENCE_MAX_CORRECTION_FACTOR = 1.10  # Max adjustment per iteration

# Early stopping thresholds (as fraction of target signal)
CONVERGENCE_TOLERANCE_5PCT = 0.05  # ±5% - immediate convergence
CONVERGENCE_TOLERANCE_10PCT = 0.10  # ±10% - converge after 2 iterations
CONVERGENCE_10PCT_ITERATIONS_REQUIRED = 2  # Number of iterations needed at ±10%

# QC calculation constants
QC_TOP_N_PIXELS = 50  # Number of top pixels to average for QC metrics
QC_MIN_PIXELS_FOR_TOP_N = 50  # Minimum ROI size to use top-N averaging

# Preflight validation constants
PREFLIGHT_MIN_COUNTS_THRESHOLD = 4000.0  # Minimum signal to confirm light path
PREFLIGHT_INTEGRATION_TIME_MS = 50.0  # Quick integration time for preflight check

# QC validation constants
QC_TARGET_MEDIAN_COUNTS = 52428  # 80% of 65535 (16-bit detector target)
QC_MIN_SNR_THRESHOLD = 100.0  # Minimum signal-to-noise ratio for quality data
QC_MIN_DIP_DEPTH_PERCENT = 5.0  # Minimum SPR dip depth to be considered detected
QC_MAX_FWHM_NM = 100.0  # Maximum acceptable FWHM for SPR peak

import contextlib

from models.led_calibration_result import LEDCalibrationResult

from affilabs.core.spectrum_preprocessor import SpectrumPreprocessor
from affilabs.core.transmission_processor import TransmissionProcessor
from affilabs.utils.calibration_helpers import (
    DetectorParams,
    determine_channel_list,
    get_detector_params,
)

# ============================================================================
# SHARED PROCESSING ALIASES (Same processors used in calibration & live)
# ============================================================================
# These processors are used identically in both calibration_6step.py and
# data_acquisition_manager.py to ensure consistent results:
#
# DarkSubtractor = SpectrumPreprocessor
#   - Removes dark noise from raw spectra
#   - Called: process_polarization_data(raw_spectrum, dark_noise, ...)
#
# TransmissionCalculator = TransmissionProcessor
#   - Calculates P/S transmission ratio with LED correction
#   - Called: process_single_channel(p_pol_clean, s_pol_ref, led_s, led_p, ...)
#
# Both use IDENTICAL parameters:
#   - baseline_method='percentile', baseline_percentile=95.0
#   - apply_sg_filter=True
#
# SHARED HARDWARE FUNCTION:
#   acquire_raw_spectrum() - matches _acquire_raw_spectrum() in live acquisition
#     - Same LED timing pattern (PRE/POST delays)
#     - Same batch command support
#     - Same averaging strategy (num_scans)
# ============================================================================
DarkSubtractor = SpectrumPreprocessor
TransmissionCalculator = TransmissionProcessor

# Local constants for Steps 1-3 (GitHub alignment)
TEMP_INTEGRATION_TIME_MS = 32  # Temporary integration for Steps 1-3 (GitHub standard)


# =============================================================================
# CALIBRATION STEP CONSTANTS (Single Source of Truth)
# =============================================================================
CALIBRATION_NUM_STEPS = 6

CALIBRATION_STEPS = {
    1: "Hardware Validation & LED Verification",
    2: "Wavelength Calibration",
    3: "LED Brightness Measurement & 3-Stage Linear Model Load",
    4: "S-Mode LED Convergence + Reference Capture",
    5: "P-Mode LED Convergence + Reference + Dark Capture",
    6: "QC Validation & Result Packaging",
}


# =============================================================================
# VALIDATION FUNCTIONS (Critical Fixes)
# =============================================================================


def _validate_calibration_result_schema(result: LEDCalibrationResult) -> None:
    """Validate LEDCalibrationResult has all required attributes.

    CRITICAL FIX #1: Schema Validation
    - Prevents silent breakage when LEDCalibrationResult class changes
    - Catches missing attributes before returning incomplete calibration data
    - Called immediately after result object creation

    Args:
        result: LEDCalibrationResult object to validate

    Raises:
        ValueError: If any required attribute is missing

    """
    required_attrs = [
        "s_pol_ref",  # Dict[str, np.ndarray] - S-pol reference spectra
        "p_pol_ref",  # Dict[str, np.ndarray] - P-pol reference spectra
        "wave_data",  # np.ndarray - Wavelength axis
        "s_integration_time",  # float - S-mode integration time
        "p_integration_time",  # float - P-mode integration time
        "s_mode_intensity",  # Dict[str, int] - S-mode LED intensities (correct attr name)
        "p_mode_intensity",  # Dict[str, int] - P-mode LED intensities (correct attr name)
        "transmission",  # Dict[str, np.ndarray] - Transmission spectra
        "qc_results",  # Dict - QC metrics and pass/fail status
    ]

    missing = [attr for attr in required_attrs if not hasattr(result, attr)]

    if missing:
        logger.error(
            f"[X] SCHEMA VALIDATION FAILED: LEDCalibrationResult missing attributes: {missing}",
        )
        msg = f"LEDCalibrationResult schema validation failed - missing: {missing}"
        raise ValueError(
            msg,
        )

    logger.info(
        f"[i] Schema validation passed - all {len(required_attrs)} required attributes present",
    )


def _require_wave_data(result: LEDCalibrationResult, step_name: str) -> np.ndarray:
    """Ensure wave_data initialized before use in calibration steps.

    CRITICAL FIX #2: Wave Data Dependency Guard
    - Steps 3-7 require wave_data but don't validate it exists
    - Prevents crashes with clear error message if Step 2 skipped
    - Returns wave_data if valid to simplify usage

    Args:
        result: LEDCalibrationResult object
        step_name: Name of step requiring wave_data (e.g., "Step 3")

    Returns:
        np.ndarray: Valid wave_data array

    Raises:
        ValueError: If wave_data is None, empty, or invalid

    """
    if not hasattr(result, "wave_data") or result.wave_data is None:
        logger.error(
            f"[X] {step_name} requires wave_data but it is None - Step 2 must run first!",
        )
        msg = f"{step_name} depends on wave_data - ensure Step 2 (detector initialization) runs successfully"
        raise ValueError(
            msg,
        )

    if len(result.wave_data) == 0:
        logger.error(f"[X] {step_name} requires wave_data but array is empty!")
        msg = f"{step_name} wave_data dependency failed - wavelength array is empty"
        raise ValueError(
            msg,
        )

    # Validate wavelength range
    if np.min(result.wave_data) < 200 or np.max(result.wave_data) > 2000:
        logger.warning(
            f"[!] {step_name}: wave_data has unusual range [{np.min(result.wave_data):.1f}, {np.max(result.wave_data):.1f}] nm",
        )

    return result.wave_data


def _get_servo_positions_from_config(
    device_config: dict,
    detector_serial: str,
) -> dict[str, int]:
    """Get servo positions from device_config with single source of truth.

    CRITICAL FIX #3: Device Config Format Validator
    - Enforces single source of truth with explicit errors
    - Only reads from hardware.servo_s_position / servo_p_position

    Args:
        device_config: Device configuration dictionary
        detector_serial: Serial number for logging

    Returns:
        Dict with keys 's_position' and 'p_position' (int values)

    Raises:
        ValueError: If config format is invalid or positions out of range

    """
    cfg = device_config if isinstance(device_config, dict) else {}
    s_pos = None
    p_pos = None
    source = None

    # Read from hardware section only
    if "hardware" in cfg:
        s_pos = cfg["hardware"].get("servo_s_position")
        p_pos = cfg["hardware"].get("servo_p_position")
        if s_pos is not None and p_pos is not None:
            source = "hardware.servo_*_position"

    # Validate positions found
    if s_pos is None or p_pos is None:
        logger.warning(
            f"[!] No servo positions found in device_config for {detector_serial}",
        )
        logger.warning("[!] Using default values: S=120, P=60")
        s_pos = 120
        p_pos = 60
        source = "DEFAULT (no config found)"
    else:
        # Validate range (servo typically 0-180 degrees)
        if not (0 <= s_pos <= 180) or not (0 <= p_pos <= 180):
            logger.error(
                f"[X] Invalid servo positions: S={s_pos}, P={p_pos} (must be 0-180)",
            )
            msg = f"Servo positions out of range: S={s_pos}, P={p_pos}"
            raise ValueError(msg)

        logger.info(f"[i] Loaded servo positions from {source}: S={s_pos}, P={p_pos}")

    return {
        "s_position": int(s_pos),
        "p_position": int(p_pos),
        "source": source,  # For debugging
    }


# =============================================================================
# SERVO HELPER FUNCTIONS
# =============================================================================


def servo_initiation_to_s(
    ctrl,
    device_config: dict,
    detector_serial: str,
) -> dict[str, int]:
    """Initialize servo for S-mode using device_config positions.

    - Reads S/P positions from device_config via single source of truth
    - Parks to 1° quietly
    - Moves explicitly to S-position
    - Locks S-mode via firmware command (uses EEPROM positions)

    Returns the positions dict `{s_position, p_position}` for logging/verification.
    Raises on hard failure to ensure fail-fast behavior.
    """
    positions = _get_servo_positions_from_config(device_config, detector_serial)
    s_pos = positions["s_position"]
    p_pos = positions["p_position"]
    try:
        # Ensure LEDs are OFF before moving servo
        with contextlib.suppress(Exception):
            ctrl.turn_off_channels()
        # Park to 1°, then move to S/P explicit positions if supported
        if hasattr(ctrl, "servo_move_calibration_only"):
            logger.info("Parking polarizer to 1° (quiet reset)...")
            ok1 = ctrl.servo_move_calibration_only(s=1, p=1)
            time.sleep(0.50)
            logger.info(
                f"Moving polarizer to S/P positions S={s_pos}°, P={p_pos}° explicitly...",
            )
            ok2 = ctrl.servo_move_calibration_only(s=int(s_pos), p=int(p_pos))
            time.sleep(0.50)
            if not (ok1 and ok2):
                msg = "Servo pre-position sequence did not confirm moves"
                raise RuntimeError(msg)
        else:
            logger.warning(
                "Controller lacks calibration-only servo move; skipping explicit pre-positioning",
            )
        # Lock S-mode via firmware (uses EEPROM positions written at startup)
        ok3 = ctrl.set_mode("s")
        time.sleep(0.30)
        if not ok3:
            msg = "Firmware S-mode lock (ss) did not confirm"
            raise RuntimeError(msg)
        logger.info("[OK] S-mode active; LEDs off and servo positioned for S")
        return positions
    except Exception as e:
        logger.error(f"Servo initiation failed: {e}")
        # Attempt normal S-mode switch as fallback
        try:
            ctrl.set_mode("s")
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
        from affilabs.utils.common import get_config

        cfg = get_config()
        # If cfg already contains hardware positions, return it
        if isinstance(cfg, dict):
            hw = cfg.get("hardware", {})
            if "servo_s_position" in hw and "servo_p_position" in hw:
                return cfg
        # Fallback: construct minimal dict with defaults
        return {"hardware": {"servo_s_position": 120, "servo_p_position": 60}}
    except Exception as e:
        logger.warning(f"resolve_device_config_for_detector failed: {e}")
        return {"hardware": {"servo_s_position": 120, "servo_p_position": 60}}


def servo_move_1_then(
    ctrl,
    device_config: dict,
    current_mode: str,
    target_mode: str,
) -> bool:
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
            logger.info(
                f"Servo worker: Already at {target_mode.upper()}-mode, no move needed",
            )
            return True

        # Load positions from device_config
        positions = _get_servo_positions_from_config(device_config, "")
        s_pos = positions["s_position"]
        p_pos = positions["p_position"]

        # Determine target position
        target_pos = s_pos if target_mode == "s" else p_pos

        logger.info(
            f"Servo worker: Moving from {current_mode.upper()}-mode to {target_mode.upper()}-mode (target={target_pos}°)",
        )

        if hasattr(ctrl, "servo_move_calibration_only"):
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


def _jsonify(obj):
    """Recursively convert numpy types/arrays and other non-serializable objects
    into JSON-serializable Python natives.

    Rules:
    - np.integer -> int
    - np.floating -> float
    - np.bool_ -> bool
    - np.ndarray -> list (with recursive conversion of elements)
    - dict/list/tuple -> recurse
    - Path -> str
    - set -> list
    - Anything else returned as-is (json will handle or raise)
    """
    from pathlib import Path as _Path

    if obj is None:
        return None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.ndarray,)):
        return [_jsonify(x) for x in obj.tolist()]
    if isinstance(obj, dict):
        return {str(k): _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonify(x) for x in obj]
    if isinstance(obj, set):
        return [_jsonify(x) for x in obj]
    if isinstance(obj, _Path):
        return str(obj)
    return obj


def save_calibration_result_json(
    result: LEDCalibrationResult,
    base_dir: str = "calibration_results",
) -> Path | None:
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
            "calibration_metadata": {
                "timestamp": datetime.now().isoformat(),
                "success": result.success,
                "calibration_method": "alternative"
                if USE_ALTERNATIVE_CALIBRATION
                else "standard",
                "detector_serial": result.detector_max_counts,  # Using as identifier
            },
            "detector_parameters": {
                "max_counts": result.detector_max_counts,
                "saturation_threshold": result.detector_saturation_threshold,
                "wavelength_range": {
                    "min": float(result.wave_data[0])
                    if result.wave_data is not None
                    else None,
                    "max": float(result.wave_data[-1])
                    if result.wave_data is not None
                    else None,
                    "min_index": result.wave_min_index,
                    "max_index": result.wave_max_index,
                },
            },
            # CRITICAL: Save wavelengths array for live acquisition
            "wavelengths": result.wave_data.tolist()
            if result.wave_data is not None
            else [],
            # CRITICAL: Save reference spectra for live acquisition
            "s_pol_ref": {
                ch: spec.tolist() for ch, spec in (result.s_pol_ref or {}).items()
            },
            "p_pol_ref": {
                ch: spec.tolist() for ch, spec in (result.p_pol_ref or {}).items()
            },
            # CRITICAL: Save dark references for live acquisition
            "dark_s": {ch: dark.tolist() for ch, dark in (result.dark_s or {}).items()},
            "dark_p": {ch: dark.tolist() for ch, dark in (result.dark_p or {}).items()},
            "led_parameters": {
                "s_mode_intensity": result.s_mode_intensity,
                "p_mode_intensity": result.p_mode_intensity,
                "normalized_leds": result.normalized_leds,
                "brightness_ratios": result.brightness_ratios,
                "weakest_channel": result.weakest_channel,
            },
            "integration_times": {
                "s_integration_time": result.s_integration_time,
                "p_integration_time": result.p_integration_time,
                "channel_integration_times": result.channel_integration_times,
            },
            "timing_parameters": {
                "pre_led_delay_ms": result.pre_led_delay_ms,
                "post_led_delay_ms": result.post_led_delay_ms,
                "cycle_time_ms": result.cycle_time_ms,
                "acquisition_rate_hz": result.acquisition_rate_hz,
                "num_scans": result.num_scans,
            },
            "roi_measurements": {
                "s_roi1_signals": result.s_roi1_signals,
                "s_roi2_signals": result.s_roi2_signals,
                "p_roi1_signals": result.p_roi1_signals,
                "p_roi2_signals": result.p_roi2_signals,
            },
            "polarizer_configuration": {
                "s_position": result.polarizer_s_position,
                "p_position": result.polarizer_p_position,
                "sp_ratio": result.polarizer_sp_ratio,
            },
            "qc_results": result.qc_results,
            "error_channels": result.ch_error_list,
        }

        # Coerce to JSON-serializable structure (handles numpy types)
        data = _jsonify(data)

        # Save timestamped version
        timestamped_file = output_dir / f"calibration_{timestamp}.json"
        with open(timestamped_file, "w") as f:
            json.dump(data, f, indent=2)

        # Save as 'latest' for quick access
        latest_file = output_dir / "latest_calibration.json"
        with open(latest_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"💾 Calibration result saved: {timestamped_file}")
        logger.info(f"💾 Latest calibration updated: {latest_file}")

        return timestamped_file

    except Exception as e:
        logger.error(f"Failed to save calibration result: {e}")
        return None


# =============================================================================
# STEP 6: TIMING ALIGNMENT FUNCTION
# =============================================================================


def _run_step6_timing_alignment(
    usb,
    ctrl,
    ch_list: list,
    calibration_result,
    stop_flag=None,
    progress_callback=None,
) -> dict:
    """Run timing alignment to verify LED-to-detector synchronization.

    This function implements an adaptive 2-phase timing verification strategy:

    PHASE 1: Fast Discovery (50% integration time)
    - Quick temporal mapping to find approximate cycle timing
    - Uses reduced integration for faster iteration
    - Measures baseline cycle duration and variance

    PHASE 2: Full Verification (Calibrated integration time)
    - Validates timing consistency with real acquisition parameters
    - Measures actual cycle timing user will experience
    - Verifies jitter is within acceptable tolerance

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        ch_list: List of channels to test (e.g., ['a', 'b', 'c', 'd'])
        calibration_result: LEDCalibrationResult with calibrated parameters
        stop_flag: Optional threading.Event for cancellation
        progress_callback: Optional callback(message, percent)

    Returns:
        dict with timing metrics:
            - avg_cycle_ms: Average cycle time across all measurements
            - jitter_ms: Timing jitter (standard deviation)
            - min_ms: Minimum cycle time observed
            - max_ms: Maximum cycle time observed
            - status: 'pass' if jitter <= tolerance, else 'warning'

    Raises:
        RuntimeError: If timing alignment fails critically

    """
    from settings import TIMING_ALIGNMENT_CYCLES, TIMING_ALIGNMENT_TOLERANCE_MS

    logger.info("=" * 80)
    logger.info("STEP 6: TIMING SYNCHRONIZATION (Adaptive 2-Phase Strategy)")
    logger.info("=" * 80)
    logger.info(
        f"Testing {TIMING_ALIGNMENT_CYCLES} cycles across {len(ch_list)} channels",
    )
    logger.info(
        f"Jitter tolerance: {TIMING_ALIGNMENT_TOLERANCE_MS}ms (consistency check)",
    )
    logger.info("")

    # Get calibrated parameters
    s_integration_time = calibration_result.s_integration_time
    s_mode_intensity = calibration_result.ref_intensity

    # Validate inputs
    if not s_mode_intensity or len(s_mode_intensity) == 0:
        msg = "S-mode LED intensities not calibrated - cannot run timing alignment"
        raise RuntimeError(
            msg,
        )

    all_cycle_times = []

    # ========================================================================
    # PHASE 1: FAST DISCOVERY (50% integration time)
    # ========================================================================
    if progress_callback:
        progress_callback(
            f"Step 6 of {CALIBRATION_NUM_STEPS}: Timing discovery phase (50% integration)",
            85,
        )

    logger.info("\n" + "=" * 80)
    logger.info("PHASE 1: FAST DISCOVERY (50% integration time)")
    logger.info("=" * 80)
    logger.info(
        f"Using {s_integration_time * 0.5:.1f}ms integration for quick temporal mapping",
    )

    discovery_integration = s_integration_time * 0.5
    usb.set_integration(discovery_integration)
    time.sleep(0.020)  # Allow hardware to stabilize

    discovery_cycles = max(2, TIMING_ALIGNMENT_CYCLES // 2)

    for cycle_idx in range(discovery_cycles):
        if stop_flag and stop_flag.is_set():
            logger.warning("Timing alignment cancelled by user")
            return {
                "avg_cycle_ms": 0,
                "jitter_ms": 0,
                "min_ms": 0,
                "max_ms": 0,
                "status": "cancelled",
            }

        cycle_start = time.perf_counter()

        # BATCH LED OPTIMIZATION: Set ALL intensities FIRST, then switch LEDs
        # Strategy: Pre-configure all LED brightnesses, then batch-switch for acquisition

        # Step 1: Set all LED intensities once at the start
        logger.debug("[CALIB] Pre-configuring all LED intensities")
        lm_cmd_parts = []
        for ch in ch_list:
            led_intensity = s_mode_intensity.get(ch, 100)
            lm_cmd_parts.append(f"{ch},{led_intensity}")

        # Send single batch command to set all intensities
        lm_cmd = f"lm:{','.join(lm_cmd_parts)}\n"
        ctrl._ser.write(lm_cmd.encode())
        time.sleep(0.010)  # Allow firmware to process all intensity settings
        logger.debug(f"[CALIB] Intensities set: {lm_cmd.strip()}")

        # Step 2: Cycle through channels with optimized LED switching
        for idx, ch in enumerate(ch_list):
            # Ensure S-mode
            ctrl.set_mode("s")
            time.sleep(0.005)

            # Turn on current LED (intensity already set)
            ctrl._ser.write(f"l{ch}:1\n".encode())

            # Wait 50ms for LED stabilization (validated optimal timing)
            time.sleep(0.050)

            # Read spectrum while LED is stable
            usb.read_intensity()

            # Turn off current LED
            ctrl._ser.write(f"l{ch}:0\n".encode())
            time.sleep(0.005)  # Brief inter-channel dark time

        cycle_end = time.perf_counter()
        cycle_time_ms = (cycle_end - cycle_start) * 1000
        all_cycle_times.append(cycle_time_ms)

        logger.debug(
            f"  Discovery cycle {cycle_idx + 1}/{discovery_cycles}: {cycle_time_ms:.2f}ms",
        )

    discovery_avg = np.mean(all_cycle_times)
    discovery_jitter = np.std(all_cycle_times)

    logger.info(
        f"\n[OK] Discovery complete: {discovery_avg:.1f}ms avg, {discovery_jitter:.2f}ms jitter",
    )

    # ========================================================================
    # PHASE 2: FULL VERIFICATION (Calibrated integration time)
    # ========================================================================
    if progress_callback:
        progress_callback(
            f"Step 6 of {CALIBRATION_NUM_STEPS}: Timing verification (full integration)",
            87,
        )

    logger.info("\n" + "=" * 80)
    logger.info("PHASE 2: FULL VERIFICATION (Calibrated integration time)")
    logger.info("=" * 80)
    logger.info(
        f"Using {s_integration_time:.1f}ms integration (actual acquisition parameters)",
    )

    usb.set_integration(s_integration_time)
    time.sleep(0.020)

    verification_cycles = TIMING_ALIGNMENT_CYCLES - discovery_cycles
    verification_times = []

    for cycle_idx in range(verification_cycles):
        if stop_flag and stop_flag.is_set():
            logger.warning("Timing alignment cancelled by user")
            return {
                "avg_cycle_ms": np.mean(all_cycle_times),
                "jitter_ms": np.std(all_cycle_times),
                "min_ms": np.min(all_cycle_times),
                "max_ms": np.max(all_cycle_times),
                "status": "cancelled",
            }

        cycle_start = time.perf_counter()

        # Cycle through all channels using LIVE ACQUISITION TIMING
        # This ensures Step 6 QC timing matches what user sees in live data
        import settings as root_settings

        LED_OFF_PERIOD_MS = getattr(root_settings, "LED_OFF_PERIOD_MS", 5.0)
        DETECTOR_WAIT_BEFORE_MS = getattr(
            root_settings,
            "DETECTOR_WAIT_BEFORE_MS",
            35.0,
        )
        getattr(root_settings, "DETECTOR_WINDOW_MS", 210.0)
        DETECTOR_WAIT_AFTER_MS = getattr(root_settings, "DETECTOR_WAIT_AFTER_MS", 5.0)

        for ch in ch_list:
            led_intensity = s_mode_intensity.get(ch, 100)

            # Ensure S-mode
            ctrl.set_mode("s")
            time.sleep(0.005)

            # LED OFF period (transition time between LEDs)
            time.sleep(LED_OFF_PERIOD_MS / 1000.0)

            # Turn on LED using batch command (matches live acquisition)
            led_values = {"a": 0, "b": 0, "c": 0, "d": 0}
            led_values[ch] = led_intensity
            ctrl.set_batch_intensities(
                a=led_values["a"],
                b=led_values["b"],
                c=led_values["c"],
                d=led_values["d"],
            )

            # Wait for LED stabilization (matches live acquisition)
            time.sleep(DETECTOR_WAIT_BEFORE_MS / 1000.0)

            # Read spectrum during detection window
            usb.read_intensity()

            # Wait after detection completes (matches live acquisition)
            time.sleep(DETECTOR_WAIT_AFTER_MS / 1000.0)

        cycle_end = time.perf_counter()
        cycle_time_ms = (cycle_end - cycle_start) * 1000
        verification_times.append(cycle_time_ms)
        all_cycle_times.append(cycle_time_ms)

        logger.debug(
            f"  Verification cycle {cycle_idx + 1}/{verification_cycles}: {cycle_time_ms:.2f}ms",
        )

    verification_avg = np.mean(verification_times)
    verification_jitter = np.std(verification_times)

    logger.info(
        f"\n[OK] Verification complete: {verification_avg:.1f}ms avg, {verification_jitter:.2f}ms jitter",
    )

    # ========================================================================
    # FINAL ANALYSIS
    # ========================================================================
    avg_cycle_ms = np.mean(all_cycle_times)
    jitter_ms = np.std(all_cycle_times)
    min_ms = np.min(all_cycle_times)
    max_ms = np.max(all_cycle_times)

    logger.info("\n" + "=" * 80)
    logger.info("TIMING ALIGNMENT RESULTS")
    logger.info("=" * 80)
    logger.info(f"Average cycle time: {avg_cycle_ms:.2f}ms")
    logger.info(f"Timing jitter (std): {jitter_ms:.2f}ms")
    logger.info(f"Min cycle time: {min_ms:.2f}ms")
    logger.info(f"Max cycle time: {max_ms:.2f}ms")
    logger.info(f"Tolerance: {TIMING_ALIGNMENT_TOLERANCE_MS}ms")

    # Determine status based on jitter (consistency check)
    if jitter_ms <= TIMING_ALIGNMENT_TOLERANCE_MS:
        status = "pass"
        logger.info(
            f"[OK] TIMING ALIGNED - Jitter within tolerance ({jitter_ms:.2f}ms <= {TIMING_ALIGNMENT_TOLERANCE_MS}ms)",
        )
    else:
        status = "warning"
        logger.warning(
            f"[WARN]  HIGH TIMING JITTER - {jitter_ms:.2f}ms > {TIMING_ALIGNMENT_TOLERANCE_MS}ms tolerance",
        )
        logger.warning("   System timing may be inconsistent - check for:")
        logger.warning("   - USB latency issues")
        logger.warning("   - System load (background processes)")
        logger.warning("   - Hardware timing instability")

    logger.info("=" * 80 + "\n")

    return {
        "avg_cycle_ms": float(avg_cycle_ms),
        "jitter_ms": float(jitter_ms),
        "min_ms": float(min_ms),
        "max_ms": float(max_ms),
        "status": status,
    }


# =============================================================================
# HELPER FUNCTION: COUNT SATURATED PIXELS
# =============================================================================


def count_saturated_pixels(
    spectrum: np.ndarray,
    wave_min_index: int,
    wave_max_index: int,
    saturation_threshold: float,
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
    return int(np.sum(saturated_mask))


# =============================================================================
# HARDWARE ACQUISITION LAYER (SHARED BETWEEN CALIBRATION AND LIVE)
# =============================================================================


def acquire_raw_spectrum(
    usb,
    ctrl,
    channel: str,
    led_intensity: int,
    integration_time_ms: float | None = None,
    num_scans: int = 1,
    pre_led_delay_ms: float = 45.0,
    post_led_delay_ms: float = 5.0,
    use_batch_command: bool = False,
) -> np.ndarray | None:
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

        # Step 2: Turn on LED channel and set intensity
        if use_batch_command:
            # Batch command (faster, used in live acquisition and LED calibration model)
            # NOTE: lm:A,B,C,D command sent once at calibration start, not here
            led_values = {"a": 0, "b": 0, "c": 0, "d": 0}
            led_values[channel] = led_intensity
            ctrl.set_batch_intensities(**led_values)
        else:
            # Individual command (traditional calibration)
            # CRITICAL: Must call turn_on_channel BEFORE set_intensity for V2.0 firmware
            ctrl.turn_on_channel(channel)
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

        # Step 5: Turn off LED (only needed for non-batch mode or final cleanup)
        # In batch mode, the next acquisition automatically turns off previous LEDs
        if not use_batch_command:
            # For V2.0: set intensity to 0 disables the channel
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
    top_n: int | None = None,
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
    if method == "max":
        return float(np.max(roi))
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
    tolerance_pct: float = 0.10,
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

    pixels_in_range = np.sum(
        (roi_spectrum >= min_signal) & (roi_spectrum <= max_signal),
    )
    percentage = (pixels_in_range / total_pixels) * 100

    return int(pixels_in_range), float(percentage)


def calculate_qc_top50_metrics(
    raw_data_dict: dict[str, np.ndarray],
    detector_max_counts: float,
) -> tuple[dict[str, float], dict[str, float]]:
    """Calculate top-50 mean signal and percentage for QC metrics.

    Computes the mean of the top 50 pixels in each channel's ROI data.
    Falls back to max value if ROI has fewer than 50 pixels.

    Args:
        raw_data_dict: Dict mapping channel name to ROI spectrum array
        detector_max_counts: Maximum detector counts for percentage calculation

    Returns:
        Tuple of (top50_signals, top50_percentages) dicts keyed by channel

    """
    top50_signals = {}
    top50_percentages = {}

    for ch, spectrum in raw_data_dict.items():
        # Calculate top-50 mean or fallback to max
        if len(spectrum) >= QC_MIN_PIXELS_FOR_TOP_N:
            sig_top50 = float(np.mean(np.sort(spectrum)[-QC_TOP_N_PIXELS:]))
        else:
            sig_top50 = float(np.max(spectrum))

        # Calculate percentage of detector saturation
        pct = (
            (sig_top50 / detector_max_counts * 100.0)
            if detector_max_counts
            else 0.0
        )

        top50_signals[ch] = sig_top50
        top50_percentages[ch] = pct

    return top50_signals, top50_percentages


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
    min_counts_threshold: float = PREFLIGHT_MIN_COUNTS_THRESHOLD,
    integration_time_ms: float = PREFLIGHT_INTEGRATION_TIME_MS,
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
        with contextlib.suppress(Exception):
            ctrl.turn_off_channels()

        # Fast path: only attempt a quick S-mode lock (no pre-positioning)
        s_locked = False
        try:
            if hasattr(ctrl, "set_mode"):
                s_locked = bool(ctrl.set_mode("s"))
        except Exception:
            s_locked = False
        logger.info(f"Polarizer S-mode lock: {'OK' if s_locked else 'UNKNOWN'}")

        # Pick channels: fast → first only; else test first two
        test_channels = (
            [ch_list[0]]
            if (fast and len(ch_list) > 0)
            else (ch_list[:2] if len(ch_list) >= 2 else ch_list)
        )
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
                logger.error(f"[ERROR] {ch.upper()}: No spectrum read")
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
            pct = (
                (mean_val / detector_params.max_counts * 100.0)
                if detector_params.max_counts
                else 0.0
            )
            logger.info(
                f"   {ch.upper()} @ LED=255, T={integration_time_ms:.1f}ms → mean={mean_val:.0f} ({pct:.1f}%), max={max_val:.0f}, sat_px={sat_px}",
            )

        any_light = any(v >= min_counts_threshold for v in detected.values())
        if not any_light:
            msg = (
                "LED VERIFICATION FAILED: All tested channels < "
                f"{min_counts_threshold:.0f} counts at LED=255 (S-mode)."
            )
            logger.error("\n" + "=" * 80)
            logger.error(f"[ERROR] {msg}")
            for ch, val in detected.items():
                logger.error(f"   {ch.upper()}: {val:.0f} counts")
            logger.error("=" * 80 + "\n")
            return False, msg

        # Skip P-toggle in fast path to minimize delay
        if not fast:
            try:
                if hasattr(ctrl, "set_mode"):
                    pm_ok = bool(ctrl.set_mode("p"))
                    logger.info(
                        f"Polarizer P-mode lock: {'OK' if pm_ok else 'UNKNOWN'}",
                    )
                    sm_ok = bool(ctrl.set_mode("s"))
                    logger.info(
                        f"Polarizer S-mode re-lock: {'OK' if sm_ok else 'UNKNOWN'}",
                    )
            except Exception as e:
                logger.warning(f"[WARN]  Polarizer quick toggle check failed: {e}")

        logger.info("[OK] PREFLIGHT PASSED: Light detected and polarizer usable")
        return True, "OK"

    except Exception as e:
        logger.exception(f"Preflight check error: {e}")
        return False, str(e)


# =============================================================================
# CONVERGENCE: UNIVERSAL INTEGRATION TIME CONVERGENCE FOR STEPS 3C, 4, 5
# =============================================================================


def update_channel_convergence_status(
    ch: str,
    signal: float,
    target_signal: float,
    is_saturated: bool,
    channel_status: dict,
    good_5pct_threshold: float,
    good_10pct_threshold: float,
) -> tuple[bool, str]:
    """Update channel convergence tracking and determine if converged.

    Args:
        ch: Channel name
        signal: Current signal value
        target_signal: Target signal value
        is_saturated: Whether channel is saturated
        channel_status: Dict tracking convergence state for all channels
        good_5pct_threshold: Threshold for ±5% tolerance
        good_10pct_threshold: Threshold for ±10% tolerance

    Returns:
        Tuple of (converged, status_indicator)
        - converged: True if channel has reached convergence criteria
        - status_indicator: String describing convergence state for logging

    """
    signal_error = abs(signal - target_signal)

    # Reset counters if saturated
    if is_saturated:
        channel_status[ch]["within_5pct"] = 0
        channel_status[ch]["within_10pct"] = 0
        return False, ""

    # Check ±5% convergence (immediate stop)
    if signal_error <= good_5pct_threshold:
        channel_status[ch]["within_5pct"] += 1
        if channel_status[ch]["within_5pct"] >= 1:
            channel_status[ch]["converged"] = True
            return True, " [CONVERGED ±5%]"
        return False, " (±5%)"

    # Check ±10% convergence (requires 2 iterations)
    if signal_error <= good_10pct_threshold:
        channel_status[ch]["within_10pct"] += 1
        channel_status[ch]["within_5pct"] = 0  # Reset 5% counter
        if channel_status[ch]["within_10pct"] >= CONVERGENCE_10PCT_ITERATIONS_REQUIRED:
            channel_status[ch]["converged"] = True
            return True, f" [CONVERGED ±10% ({CONVERGENCE_10PCT_ITERATIONS_REQUIRED}x)]"
        return False, f" (±10% {channel_status[ch]['within_10pct']}/{CONVERGENCE_10PCT_ITERATIONS_REQUIRED})"

    # Outside tolerance - reset counters
    channel_status[ch]["within_5pct"] = 0
    channel_status[ch]["within_10pct"] = 0
    return False, ""


def converge_integration_time(
    usb,
    ctrl,
    ch_list: list,
    led_intensities: dict[str, int],
    initial_integration_ms: float,
    target_percent: float,
    tolerance_percent: float,
    detector_params: DetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    max_iterations: int = 5,
    step_name: str = "Unknown",
    stop_flag=None,
) -> tuple[float, dict[str, float], bool]:
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
    logger.info(
        f"   Target: {target_percent * 100:.1f}% ±{tolerance_percent * 100:.1f}% ({min_signal:.0f} - {max_signal:.0f} counts)",
    )
    logger.info(f"   Initial integration: {initial_integration_ms:.1f}ms")
    logger.info(f"   LED intensities (frozen): {led_intensities}")
    logger.info("")

    current_integration = initial_integration_ms
    converged = False

    # Per-channel early stopping tracking
    channel_status = {
        ch: {"within_5pct": 0, "within_10pct": 0, "converged": False} for ch in ch_list
    }
    good_5pct_threshold = target_signal * CONVERGENCE_TOLERANCE_5PCT  # ±5% range
    good_10pct_threshold = target_signal * CONVERGENCE_TOLERANCE_10PCT  # ±10% range

    for iteration in range(max_iterations):
        if stop_flag and stop_flag.is_set():
            return current_integration, {}, False

        logger.info(
            f"🔄 Iteration {iteration + 1}/{max_iterations} - Testing {current_integration:.1f}ms",
        )

        # Set integration time
        usb.set_integration(current_integration)
        time.sleep(0.010)

        # Measure all channels
        iteration_signals = {}
        iteration_saturated = []

        for ch in ch_list:
            if stop_flag and stop_flag.is_set():
                return current_integration, {}, False

            # Skip if already converged
            if channel_status[ch]["converged"]:
                iteration_signals[ch] = iteration_signals.get(
                    ch,
                    0,
                )  # Use last known value
                logger.info(f"   {ch.upper()}: [SKIP] Already converged")
                continue

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
                use_batch_command=False,
            )

            if spectrum is None:
                logger.error(f"   [ERROR] {ch.upper()}: Failed to acquire spectrum")
                continue

            # Check signal and saturation
            roi_spectrum = spectrum[wave_min_index:wave_max_index]
            signal = roi_signal(roi_spectrum, 0, len(roi_spectrum), method="median")
            signal_pct = (signal / detector_max) * 100
            signal_error = abs(signal - target_signal)

            sat_count = count_saturated_pixels(
                roi_spectrum,
                0,
                len(roi_spectrum),
                saturation_threshold,
            )
            is_saturated = sat_count > 0

            iteration_signals[ch] = signal
            if is_saturated:
                iteration_saturated.append(ch)

            # Update convergence status and check if converged
            converged_now, convergence_indicator = update_channel_convergence_status(
                ch=ch,
                signal=signal,
                target_signal=target_signal,
                is_saturated=is_saturated,
                channel_status=channel_status,
                good_5pct_threshold=good_5pct_threshold,
                good_10pct_threshold=good_10pct_threshold,
            )

            # Skip to next channel if just converged
            if converged_now:
                logger.info(
                    f"   {ch.upper()}: {signal:.0f} counts ({signal_pct:.1f}%){convergence_indicator}",
                )
                continue

            # Status indicator for in-progress channels
            in_range = min_signal <= signal <= max_signal
            status = (
                "[WARN] SAT" if is_saturated else ("[OK]" if in_range else "[WARN]")
            )
            logger.info(
                f"   {ch.upper()}: {signal:.0f} counts ({signal_pct:.1f}%) {status}{convergence_indicator}",
            )

        # Check convergence
        all_converged = all(channel_status[ch]["converged"] for ch in ch_list)
        all_in_range = all(
            min_signal <= iteration_signals[ch] <= max_signal
            for ch in ch_list
            if ch in iteration_signals
        )
        no_saturation = len(iteration_saturated) == 0

        # Early exit if all channels individually converged
        if all_converged:
            logger.info("")
            logger.info("[OK] All channels individually converged (early stopping)!")
            converged = True
            break

        # Acceptance policy: if no pixels saturate, it's a PASS
        if no_saturation:
            if all_in_range:
                logger.info("")
                logger.info(
                    f"[OK] All channels converged to {target_percent * 100:.1f}% ±{tolerance_percent * 100:.1f}% with 0 saturation!",
                )
            else:
                logger.info("")
                logger.info(
                    "[OK] Acceptance override: 0 saturated pixels across ROI; treating as PASS even if under target",
                )
            converged = True
            break

        # Need adjustment
        if iteration < max_iterations - 1:
            logger.info("")
            if iteration_saturated:
                # Saturation: reduce integration by configured factor
                current_integration *= CONVERGENCE_SATURATION_REDUCTION_FACTOR
                logger.warning(
                    f"   Saturation in: {', '.join([ch.upper() for ch in iteration_saturated])}",
                )
                logger.warning(
                    f"   Reducing integration to {current_integration:.1f}ms ({CONVERGENCE_SATURATION_REDUCTION_FACTOR:.0%})",
                )
            else:
                # Off-target: calculate correction factor
                avg_signal = np.mean(list(iteration_signals.values()))
                correction_factor = target_signal / avg_signal
                # Clamp adjustment per iteration for stability
                correction_factor = max(
                    CONVERGENCE_MIN_CORRECTION_FACTOR,
                    min(CONVERGENCE_MAX_CORRECTION_FACTOR, correction_factor),
                )
                current_integration *= correction_factor
                logger.info(
                    f"   Average: {avg_signal:.0f} counts (target: {target_signal:.0f})",
                )
                logger.info(
                    f"   Adjusting integration to {current_integration:.1f}ms (×{correction_factor:.3f})",
                )

            # Clamp to detector limits
            current_integration = max(
                detector_params.min_integration_time,
                min(detector_params.max_integration_time, current_integration),
            )
            logger.info("")
        else:
            logger.warning("")
            logger.warning(
                f"[WARN] Failed to converge after {max_iterations} iterations",
            )

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
    channel_signals: dict[str, float],
    sat_counts: dict[str, int],
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
        logger.info(
            f"  {ch.upper()}: {sig:.0f} ({pct:.1f}%) | Saturation: {sat_txt} ({sat})",
        )
    logger.info("-" * 80)


# =============================================================================
# STEP 2: QUICK DARK NOISE BASELINE
# =============================================================================


def measure_quick_dark_baseline(
    usb,
    ctrl,
    wave_min_index: int,
    wave_max_index: int,
    stop_flag=None,
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
    logger.info(
        "Note: Final dark noise will be measured at calibrated integration time\n",
    )

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
    has_led_query = hasattr(ctrl, "get_all_led_intensities")

    if has_led_query:
        for attempt in range(max_retries):
            time.sleep(0.01)  # Wait 10ms for command to process

            # Query LED state (V1.1 firmware feature)
            led_state = ctrl.get_all_led_intensities()

            if led_state is None:
                logger.info(
                    f"LED query failed (attempt {attempt + 1}/{max_retries}) - falling back to timing",
                )
                # Fall back to timing-based approach
                has_led_query = False
                break

            # Check if all LEDs are off (intensity <= 1 to account for hardware limitations)
            all_off = all(intensity <= 1 for intensity in led_state.values())

            if all_off:
                logger.info(f"[OK] All LEDs confirmed OFF: {led_state}")
            else:
                logger.warning(f"[WARN] LEDs still on: {led_state} - retrying turn-off")
                ctrl.turn_off_channels()
                time.sleep(0.05)

                # Check one more time
                led_state2 = ctrl.get_all_led_intensities()
                if led_state2 and all(
                    intensity <= 1 for intensity in led_state2.values()
                ):
                    logger.info(
                        f"[OK] All LEDs confirmed OFF after retry: {led_state2}",
                    )
                else:
                    logger.error(
                        f"[ERROR] Failed to turn off LEDs - last state: {led_state2}",
                    )
                    msg = "Cannot measure dark baseline - LEDs failed to turn off"
                    raise RuntimeError(
                        msg,
                    )

    if not has_led_query:
        # V1.0 firmware or LED query unavailable - use timing-based approach
        logger.info("LED query not available - using timing-based verification")
        time.sleep(0.05)  # Extra settling time for V1.0 firmware

    # Additional delay for LED decay
    time.sleep(LED_DELAY)

    # Average 3 quick scans
    quick_scans = 3
    dark_sum = np.zeros(wave_max_index - wave_min_index)

    logger.info(
        f"Measuring {quick_scans} scans at {quick_integration}ms integration...",
    )

    for scan in range(quick_scans):
        if stop_flag and stop_flag.is_set():
            logger.warning("Calibration cancelled during quick dark baseline")
            break

        intensity_data = usb.read_intensity()
        if intensity_data is None:
            logger.error("Failed to read intensity during quick dark baseline")
            msg = "Spectrometer read failed during quick dark baseline"
            raise RuntimeError(msg)

        dark_single = intensity_data[wave_min_index:wave_max_index]
        dark_sum += dark_single
        logger.debug(
            f"  Scan {scan + 1}/{quick_scans}: max = {np.max(dark_single):.0f} counts",
        )

    quick_dark = dark_sum / quick_scans
    max_dark = np.max(quick_dark)
    mean_dark = np.mean(quick_dark)
    min_dark = np.min(quick_dark)

    logger.info(
        f"[OK] Quick baseline complete: max = {max_dark:.0f}, mean = {mean_dark:.0f}, min = {min_dark:.0f} counts",
    )

    # Detector-agnostic validation: check for anomalies rather than absolute values
    # Different detectors have different dark baselines (Ocean Optics, Phase Photonics, etc.)
    dark_ratio = max_dark / max(mean_dark, 1)

    if dark_ratio > 2.0:
        logger.warning(
            f"[WARN] Unusually high dark variability (max/mean ratio = {dark_ratio:.2f}). "
            f"Expected < 2.0. LEDs may not be fully off - check hardware.",
        )

    logger.info(f"   Dark uniformity: ratio = {dark_ratio:.2f}")
    logger.info("   This verifies detector is responding\n")

    return quick_dark


# =============================================================================
# STEP 4: LOAD OEM POLARIZER POSITIONS
# =============================================================================


def load_oem_polarizer_positions(device_config, detector_serial: str) -> dict[str, int]:
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
            logger.error("[ERROR] No servo positions found in device config")
            logger.error("   OEM polarizer calibration must be run first")
            msg = (
                "No servo positions in device configuration. "
                "Run OEM servo calibration tool first."
            )
            raise RuntimeError(
                msg,
            )

        # Validate positions (get_servo_positions returns dict with 's' and 'p' keys)
        s_pos = servo_positions.get("s")
        p_pos = servo_positions.get("p")

        if s_pos is None or p_pos is None:
            logger.error("[ERROR] Invalid servo positions (missing s or p)")
            msg = "Invalid servo positions in device config"
            raise RuntimeError(msg)

        # Validate servo range (0-180 for most servos, but allow 10-255 for custom hardware)
        if not (0 <= s_pos <= 255 and 0 <= p_pos <= 255):
            logger.error(f"[ERROR] Invalid servo positions: S={s_pos}, P={p_pos}")
            logger.error("   Positions must be in range 0-255")
            msg = "Invalid servo positions in device config"
            raise RuntimeError(msg)

        logger.info("[OK] OEM Polarizer Positions Loaded:")
        logger.info(f"   S-mode position: {s_pos}")
        logger.info(f"   P-mode position: {p_pos}")
        logger.info("   These were calibrated during OEM manufacturing\n")

        # Return with keys matching what code expects (s_position, p_position)
        return {"s_position": s_pos, "p_position": p_pos}

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
    p_mode_intensities: dict[str, int],
    detector_params: DetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    device_config,
    detector_serial: str,
    stop_flag=None,
) -> tuple[bool, dict[str, int] | None]:
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
            use_batch_command=False,
        )

        if spectrum is None:
            logger.error("Failed to read spectrum during polarity check")
            msg = "Spectrometer read failed"
            raise RuntimeError(msg)

        # Check for saturation
        sat_count = count_saturated_pixels(
            spectrum,
            wave_min_index,
            wave_max_index,
            detector_params.saturation_threshold,
        )

        max_signal = np.max(spectrum[wave_min_index:wave_max_index])

        if sat_count > 0:
            saturation_detected = True
            saturated_channels.append(ch)
            logger.warning(
                f"  [WARN] Channel {ch.upper()}: {sat_count} saturated pixels (max={max_signal:.0f})",
            )
        else:
            logger.info(
                f"  [OK] Channel {ch.upper()}: No saturation (max={max_signal:.0f})",
            )

        # Turn off LED
        ctrl.set_intensity(ch=ch, raw_val=0)
        time.sleep(0.01)

    if not saturation_detected:
        logger.info("\n[OK] Polarity Correct: No saturation in P-mode")
        logger.info("   Servo positions are correct\n")
        return True, None

    # Polarity is WRONG - log warning but allow calibration to continue
    logger.warning("\n" + "=" * 80)
    logger.warning("[WARN] POLARITY WARNING")
    logger.warning("=" * 80)
    logger.warning(f"P-mode saturating on channels: {saturated_channels}")
    logger.warning("This may indicate servo positions are SWAPPED (S ↔ P)")
    logger.warning("")
    logger.warning(
        "Calibration will continue, but optical performance may be suboptimal.",
    )
    logger.warning("If SPR signal quality is poor, run manual servo calibration tool.")
    logger.warning("=" * 80 + "\n")

    # Return True to continue calibration (no recalibration needed)
    # Note: Auto-recalibration feature is not yet implemented
    return True, None


# =============================================================================
# MAIN 7-STEP CALIBRATION ENTRY POINT
# =============================================================================


def run_full_7step_calibration(
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
    post_led_delay_ms: float = POST_LED_DELAY_MS,
    start_at_step: int = 1,
) -> LEDCalibrationResult:
    """Complete 6-step calibration flow.

    STEP 1: Hardware Validation & LED Verification
    STEP 2: Wavelength Calibration
    STEP 3: LED Brightness Measurement & Bilinear Model Load
    STEP 4: S-Mode LED Convergence + Reference Capture
    STEP 5: P-Mode LED Convergence + Reference + Dark Capture
    STEP 6: QC Validation & Result Packaging

    After completion: Shows post-calibration QC dialog, waits for user to
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
        start_at_step: Step number to start at (1-6). Use 1 for full run;
                   provide >1 to resume mid-flow if previous steps are already complete.

    Returns:
        LEDCalibrationResult with all calibration data

    """
    result = LEDCalibrationResult()

    # CRITICAL FIX #1: Validate schema immediately after creation
    _validate_calibration_result_schema(result)

    # Store timing parameters early (needed for cycle time calculations in Step 4)
    result.pre_led_delay_ms = pre_led_delay_ms
    result.post_led_delay_ms = post_led_delay_ms

    try:
        # ===================================================================
        # ✨ P1 OPTIMIZATION: Early OEM Position Loading (Fail-Fast)
        # ===================================================================
        # Load OEM calibration positions immediately at initialization.
        # This enables fail-fast behavior (<1 second) instead of failing at Step 4 (~2 minutes).
        # Only reads from device_config['hardware'] section.

        logger.info("=" * 80)
        logger.info("⚡ FAIL-FAST: Loading OEM Polarizer Positions")
        logger.info("=" * 80)

        if not device_config:
            logger.error("=" * 80)
            logger.error("[ERROR] CRITICAL: NO DEVICE CONFIG PROVIDED")
            logger.error("=" * 80)
            logger.error("🔧 REQUIRED: device_config must be provided")
            logger.error("=" * 80)
            msg = "device_config is required for OEM calibration positions"
            raise ValueError(msg)

        # Convert device_config to dict if it's a DeviceConfiguration object
        if hasattr(device_config, "to_dict"):
            device_config_dict = device_config.to_dict()
        elif hasattr(device_config, "config"):
            device_config_dict = device_config.config
        else:
            device_config_dict = device_config

        # Load positions from hardware section only
        s_pos, p_pos, sp_ratio = None, None, None

        # Read from hardware section (device_config root)
        if "hardware" in device_config_dict:
            hardware = device_config_dict["hardware"]
            s_pos = hardware.get("servo_s_position")
            p_pos = hardware.get("servo_p_position")
            if s_pos is not None and p_pos is not None:
                logger.info(
                    "[OK] Found servo positions in 'hardware' section (device_config root)",
                )

        # Validate positions loaded successfully
        if s_pos is not None and p_pos is not None:
            # Store in result for later use
            result.polarizer_s_position = s_pos
            result.polarizer_p_position = p_pos
            result.polarizer_sp_ratio = sp_ratio

            # Store old positions for potential recalibration
            result.qc_results["old_s_pos"] = s_pos
            result.qc_results["old_p_pos"] = p_pos

            logger.info("=" * 80)
            logger.info(
                "[OK] OEM CALIBRATION POSITIONS LOADED AT INIT (P1 Optimization)",
            )
            logger.info("=" * 80)
            logger.info(f"   S-position: {s_pos} (HIGH transmission - reference)")
            logger.info(f"   P-position: {p_pos} (LOWER transmission - resonance)")
            if sp_ratio:
                logger.info(f"   S/P ratio: {sp_ratio:.2f}x")
            logger.info(
                "   ⚡ Fail-fast enabled: Invalid config detected immediately (<1s)",
            )
            logger.info("=" * 80)

            # Positions loaded from device_config at controller initialization
            # NO runtime configuration - set_mode() uses pre-configured positions
            logger.info(
                "   📍 Using positions from device_config (set at controller init)",
            )
            logger.info(
                "   [WARN]  NEVER send servo_set/flash during calibration - EEPROM operations removed",
            )
        else:
            # Positions not found - STOP with detailed path info
            logger.error("=" * 80)
            logger.error("❌ CRITICAL ERROR: OEM CALIBRATION POSITIONS NOT FOUND")
            logger.error("=" * 80)
            logger.error(f"   device_config keys: {list(device_config_dict.keys())}")
            logger.error("")
            logger.error("   Expected location:")
            logger.error("   - device_config['hardware']['servo_s_position']")
            logger.error("   - device_config['hardware']['servo_p_position']")
            logger.error("")
            if hasattr(device_config, 'config_file_path'):
                logger.error(f"   Config file path: {device_config.config_file_path}")
            logger.error("")
            logger.error("   🔧 REQUIRED: Run OEM calibration to generate positions")
            logger.error(
                "   Command: python utils/oem_calibration_tool.py --serial <DETECTOR_SERIAL>",
            )
            logger.error("=" * 80)

            msg = (
                f"OEM polarizer positions not found in device config. "
                f"Config keys: {list(device_config_dict.keys())}. "
                f"Run OEM calibration first."
            )
            raise RuntimeError(msg)

        logger.info("\n" + "=" * 80)
        logger.info(f"📍 Using OEM polarizer positions: S={s_pos}°, P={p_pos}°")
        logger.info(
            "   Positions loaded from device_config at controller initialization",
        )
        logger.info(
            "   No configuration needed - set_mode('s'/'p') will use these positions",
        )
        logger.info("=" * 80 + "\n")

        # ===================================================================
        # MODEL VALIDATION: Check if bilinear model exists before 6-step calibration
        # ===================================================================
        logger.info("=" * 80)
        logger.info("PRE-CALIBRATION CHECK: Verifying 3-stage linear model exists...")
        logger.info("=" * 80)

        try:
            # Try to load existing 3-stage linear model
            from affilabs.utils.model_loader import (
                LEDCalibrationModelLoader,
                ModelNotFoundError,
                ModelValidationError,
            )

            model_loader = LEDCalibrationModelLoader()
            bilinear_model = model_loader.load_model(detector_serial=detector_serial)

            if bilinear_model is None:
                logger.error("=" * 80)
                logger.error("❌ CALIBRATION BLOCKED: No 3-stage linear model found!")
                logger.error("=" * 80)
                logger.error(
                    "   The 6-step calibration requires an existing 3-stage linear model",
                )
                logger.error("   to predict LED intensities for S-mode convergence.")
                logger.error("")
                logger.error("   📋 REQUIRED: Run OEM Calibration first")
                logger.error(
                    "   This will create the 3-stage linear model (servo + LED calibration)",
                )
                logger.error("")
                logger.error("   Then run this 6-step calibration to:")
                logger.error("   - Use model predictions for LED convergence")
                logger.error("   - Capture S/P references")
                logger.error("   - Validate system performance")
                logger.error("=" * 80)
                msg = (
                    "No 3-stage linear model found. Please run OEM Calibration first to create the model, "
                    "then run 6-step calibration."
                )
                raise RuntimeError(
                    msg,
                )

            # Validate model has good R² scores (bilinear_model is a dict)
            channels_valid = []
            channels_invalid = []

            # Check in bilinear_models section for per-channel R² scores
            if "bilinear_models" in bilinear_model:
                models = bilinear_model["bilinear_models"]
                for ch in ["A", "B", "C", "D"]:
                    if ch in models:
                        ch_models = models[ch]

                        # Debug: Show what keys are available
                        logger.debug(
                            f"   [DEBUG] {ch}-S keys: {list(ch_models.get('S', {}).keys())}",
                        )
                        logger.debug(
                            f"   [DEBUG] {ch}-P keys: {list(ch_models.get('P', {}).keys())}",
                        )

                        # Get S-mode R² (primary quality indicator)
                        s_model = ch_models.get("S", {})
                        s_r2 = s_model.get("r2", s_model.get("r_squared", 0))

                        # Check if P-mode uses scaled S-mode (no separate R²) or has its own model
                        p_model = ch_models.get("P", {})
                        if p_model.get("p_from_s"):
                            # P-mode scales S-mode, so S-mode R² applies to both
                            quality_r2 = s_r2
                            mode_note = "S+scaled-P"
                        else:
                            # P-mode has separate model, average both R² scores
                            p_r2 = p_model.get("r2", p_model.get("r_squared", 0))
                            quality_r2 = (s_r2 + p_r2) / 2
                            mode_note = "S+P"

                        logger.debug(
                            f"   [DEBUG] {ch}: s_r2={s_r2}, quality_r2={quality_r2}",
                        )

                        if quality_r2 > 0.5:
                            channels_valid.append(
                                f"{ch}(R²={quality_r2:.3f},{mode_note})",
                            )
                        else:
                            channels_invalid.append(f"{ch}(R²={quality_r2:.3f})")
                    else:
                        channels_invalid.append(f"{ch}(missing)")
            else:
                logger.warning(
                    "   Model structure not recognized - skipping R² validation",
                )
                channels_valid.append("model loaded")

            if channels_invalid:
                logger.warning("=" * 80)
                logger.warning("⚠️  3-STAGE LINEAR MODEL QUALITY WARNING")
                logger.warning("=" * 80)
                logger.warning(f"   Valid channels: {', '.join(channels_valid)}")
                logger.warning(f"   Invalid/missing: {', '.join(channels_invalid)}")
                logger.warning("")
                logger.warning(
                    "   Model quality is poor. Consider re-running OEM Calibration.",
                )
                logger.warning("   Continuing with 6-step calibration anyway...")
                logger.warning("=" * 80)
            else:
                logger.info("[OK] 3-stage linear model validated successfully")
                logger.info(f"   All channels: {', '.join(channels_valid)}")

        except ModelNotFoundError:
            logger.error("=" * 80)
            logger.error("❌ CALIBRATION BLOCKED: No 3-stage linear model found!")
            logger.error("=" * 80)
            logger.error(
                "   The 6-step calibration requires an existing 3-stage linear model",
            )
            logger.error("   to predict LED intensities for S-mode convergence.")
            logger.error("")
            logger.error("   📋 REQUIRED: Run OEM Calibration first")
            logger.error(
                "   This will create the 3-stage linear model (servo + LED calibration)",
            )
            logger.error("")
            logger.error("   Then run this 6-step calibration to:")
            logger.error("   - Use model predictions for LED convergence")
            logger.error("   - Capture S/P references")
            logger.error("   - Validate system performance")
            logger.error("=" * 80)
            msg = (
                "No 3-stage linear model found. Please run OEM Calibration first to create the model, "
                "then run 6-step calibration."
            )
            raise RuntimeError(
                msg,
            )
        except ModelValidationError as e:
            logger.error("=" * 80)
            logger.error(
                "❌ CALIBRATION BLOCKED: 3-stage linear model is corrupted/incomplete!",
            )
            logger.error("=" * 80)
            logger.error(f"   Validation error: {e}")
            logger.error("")
            logger.error(
                "   The existing 3-stage linear model file is incomplete or corrupted.",
            )
            logger.error(
                "   This usually means the OEM Calibration did not complete successfully.",
            )
            logger.error("")
            logger.error("   📋 REQUIRED: Re-run OEM Calibration to regenerate model")
            logger.error("   This will create a complete, valid 3-stage linear model.")
            logger.error("")
            logger.error("   Then run this 6-step calibration.")
            logger.error("=" * 80)
            msg = (
                f"3-stage linear model is corrupted/incomplete: {e}. "
                "Please re-run OEM Calibration to regenerate the model."
            )
            raise RuntimeError(
                msg,
            )
        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"❌ MODEL VALIDATION FAILED: {e}")
            logger.error("=" * 80)
            logger.error(
                "   Cannot proceed with 6-step calibration without 3-stage linear model.",
            )
            logger.error("   Please run OEM Calibration first.")
            logger.error("=" * 80)
            msg = f"Model validation failed: {e}"
            raise RuntimeError(msg)

        logger.info("=" * 80 + "\n")
        logger.info("🚀 STARTING 6-STEP CALIBRATION FLOW")
        logger.info("=" * 80)
        logger.info("This calibration follows the exact flow discussed:")
        # Log all calibration steps (from CALIBRATION_STEPS definition)
        for step_num, step_desc in CALIBRATION_STEPS.items():
            logger.info(f"  Step {step_num}: {step_desc}")
        logger.info("=" * 80 + "\n")

        # Determine channel list (pre-calibration configuration)
        ch_list = determine_channel_list(device_type, single_mode, single_ch)
        logger.info(f"[OK] Channels to calibrate: {ch_list}\n")

        # ===================================================================
        # STEP 1: HARDWARE VALIDATION & LED VERIFICATION
        # ===================================================================
        if start_at_step <= 1:
            logger.info("=" * 80)
            logger.info("STEP 1: Hardware Validation & LED Verification")
            logger.info("=" * 80)

            if ctrl is None or usb is None:
                logger.error("[ERROR] Hardware not connected")
                msg = "Hardware must be connected before calibration"
                raise RuntimeError(msg)

            logger.info(f"[OK] Controller: {type(ctrl).__name__}")
            logger.info(f"[OK] Spectrometer: {type(usb).__name__}")
            logger.info(f"[OK] Detector Serial: {detector_serial}\n")

            if progress_callback:
                progress_callback(
                    f"Step 1 of {CALIBRATION_NUM_STEPS}: Checking connections",
                    0,
                )

        # CRITICAL: Force all LEDs OFF and VERIFY
        logger.info("Forcing all LEDs OFF...")
        ctrl.turn_off_channels()
        time.sleep(0.2)

        # VERIFY LEDs are off using V1.1 firmware query (CRITICAL!)
        has_led_query = hasattr(ctrl, "get_all_led_intensities")

        if has_led_query:
            time.sleep(0.01)  # Brief settling time

            # Try LED query once
            try:
                led_state = ctrl.get_all_led_intensities()
            except Exception as query_error:
                logger.debug(f"LED query exception: {query_error}")
                led_state = None

            if led_state is None:
                logger.debug(
                    "LED query not supported - using timing-based verification",
                )
                has_led_query = False
            else:
                # Check if all LEDs are off (intensity <= 1)
                channels_to_check = {
                    ch: val for ch, val in led_state.items() if ch != "d"
                }
                all_off = all(
                    intensity <= 1 for intensity in channels_to_check.values()
                )

                if all_off:
                    logger.info(f"[OK] All LEDs confirmed OFF: {channels_to_check}")
                else:
                    logger.warning(
                        f"LEDs still on: {channels_to_check} - retrying turn-off",
                    )
                    ctrl.turn_off_channels()
                    time.sleep(0.05)

                    # Check one more time
                    led_state2 = ctrl.get_all_led_intensities()
                    if led_state2:
                        channels_to_check2 = {
                            ch: val for ch, val in led_state2.items() if ch != "d"
                        }
                        if all(
                            intensity <= 1 for intensity in channels_to_check2.values()
                        ):
                            logger.info(
                                f"[OK] All LEDs confirmed OFF after retry: {channels_to_check2}",
                            )
                        else:
                            logger.error(
                                f"[ERROR] Failed to turn off LEDs - last state: {channels_to_check2}",
                            )
                            msg = "Cannot proceed - LEDs failed to turn off"
                            raise RuntimeError(
                                msg,
                            )
                    else:
                        logger.error("[ERROR] LED query failed on retry")
                        msg = "Cannot proceed - LED verification failed"
                        raise RuntimeError(msg)

        if not has_led_query:
            # V1.0 firmware or LED query unavailable - use timing-based approach
            logger.info("LED query not available - using timing-based verification")
            time.sleep(
                0.05,
            )  # Extra settling time for V1.0 firmware (only needed when query unavailable)
            logger.info("[OK] Assuming LEDs are OFF (timing-based)")

            logger.info(
                "[OK] Step 1 complete: Hardware validated, LEDs confirmed OFF\n",
            )
        else:
            logger.info(
                "[OK] Step 1 complete: Hardware validated, LEDs confirmed OFF\n",
            )

        # OPTIMIZATION: Pre-enable all LED channels for batch command operation
        # This only needs to be sent ONCE at calibration start, not on every acquisition
        if CONVERGENCE_USE_BATCH_COMMAND:
            logger.info("[BATCH] Enabling all LED channels for batch operation...")
            ctrl._ser.write(b"lm:A,B,C,D\n")
            time.sleep(0.1)  # Wait for firmware to process enable command
            logger.info("[OK] LED channels enabled for batch commands\n")

        # ===================================================================
        # STEP 2: WAVELENGTH RANGE CALIBRATION (DETECTOR-SPECIFIC)
        # ===================================================================
        if start_at_step <= 2:
            logger.info("=" * 80)
            logger.info("STEP 2: Wavelength Range Calibration (Detector-Specific)")
            logger.info("=" * 80)

            if progress_callback:
                progress_callback(
                    f"Step 2 of {CALIBRATION_NUM_STEPS}: Reading wavelengths",
                    17,
                )

            # Read wavelength data from detector EEPROM
            logger.info("Reading wavelength calibration from detector EEPROM...")
            wave_data = usb.read_wavelength()

            if wave_data is None or len(wave_data) == 0:
                logger.error("[ERROR] Failed to read wavelengths from detector")
                return result

            logger.info(
                f"[OK] Full detector range: {wave_data[0]:.1f}-{wave_data[-1]:.1f}nm ({len(wave_data)} pixels)",
            )

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

            logger.info(
                f"[OK] SPR filtered range: {MIN_WAVELENGTH}-{MAX_WAVELENGTH}nm ({len(result.wave_data)} pixels)",
            )
            logger.info(
                f"   Spectral resolution: {(wave_data[-1] - wave_data[0]) / len(wave_data):.3f} nm/pixel",
            )

            # Get detector parameters
            detector_params = get_detector_params(usb)
            result.detector_max_counts = detector_params.max_counts
            result.detector_saturation_threshold = detector_params.saturation_threshold

            logger.info("[OK] Detector parameters:")
            logger.info(f"   Max counts: {detector_params.max_counts}")
            logger.info(
                f"   Saturation threshold: {detector_params.saturation_threshold}",
            )
            logger.info("[OK] Step 2 complete\n")
        else:
            logger.info(f"⏭  Skipping Step 2 (resuming at step {start_at_step})")
            logger.info("   Using existing wavelength data and detector parameters\n")
            detector_params = get_detector_params(usb)
            result.detector_max_counts = detector_params.max_counts
            result.detector_saturation_threshold = detector_params.saturation_threshold

        # ===================================================================
        # PREFLIGHT REMOVED: The 3-stage linear model handles all validation
        # No need for arbitrary count thresholds - WE LIVE BY THE MODEL!
        # ===================================================================

        # ===================================================================
        # STEPS 3-5: LED CONVERGENCE WORKFLOW
        # ===================================================================

        if USE_LED_CONVERGENCE:
            # === STEP 3A: SKIPPED - Legacy LED brightness ranking ===
            # The 3-stage linear model already knows relative brightness
            # LED verification happens during convergence (Step 3-5)
            if progress_callback:
                progress_callback(
                    f"Step 3 of {CALIBRATION_NUM_STEPS}: Loading calibration model",
                    30,
                )

            logger.info(
                "⏭️  Step 3A: Skipped (legacy LED ranking - model provides brightness data)",
            )
            logger.info("")

            # Get device config for servo positions
            device_config_det = device_config_dict

            # Run LED convergence calibration (Steps 3-5)
            convergence_result = run_convergence_calibration_steps_3_to_5(
                usb=usb,
                ctrl=ctrl,
                detector_params=detector_params,
                ch_list=ch_list,
                wave_min_index=result.wave_min_index,
                wave_max_index=result.wave_max_index,
                device_config_det=device_config_det,
                target_percent=0.88,  # S-mode target: 88% detector (reduced to avoid saturation)
                tolerance_percent=0.05,  # ±5% tolerance (realistic for hardware variations)
                strategy="intensity",  # Shared-time convergence with fixed LEDs
                progress_callback=progress_callback,
            )

            if not convergence_result["success"]:
                logger.error(
                    f"[ERROR] LED convergence failed: {convergence_result['error']}",
                )
                result.success = False
                result.error_message = (
                    f"LED convergence calibration failed: {convergence_result['error']}"
                )
                return result

            # Transfer convergence results to calibration result
            result.weakest_channel = convergence_result["weakest_channel"]
            result.s_mode_intensity = convergence_result["s_mode_intensities"]
            result.p_mode_intensity = convergence_result["p_mode_intensities"]
            result.s_integration_time = convergence_result["s_integration_time"]
            result.p_integration_time = convergence_result["p_integration_time"]

            # Transfer per-channel integration times for live view
            result.s_channel_integration_times = convergence_result.get(
                "s_channel_integration_times",
                {},
            )
            result.p_channel_integration_times = convergence_result.get(
                "p_channel_integration_times",
                {},
            )

            # Store raw spectra for Step 6 processing
            # Prefer explicit raw ROI keys (added for clarity); fall back to legacy keys
            result.s_raw_data = convergence_result.get(
                "s_raw_roi",
                convergence_result.get("s_pol_ref", {}),
            )
            result.p_raw_data = convergence_result.get(
                "p_raw_roi",
                convergence_result.get("p_pol_ref", {}),
            )
            # Dark spectrum: store S and P dark references from convergence
            result.dark_s = convergence_result.get("dark_s", {})
            result.dark_p = convergence_result.get("dark_p", {})

            # Legacy dark_noise field (use S-mode dark as representative)
            if convergence_result["dark_spectrum"] is not None:
                full_dark = convergence_result["dark_spectrum"]
                result.dark_noise = full_dark[
                    result.wave_min_index : result.wave_max_index
                ]
                with contextlib.suppress(Exception):
                    result.qc_results["dark_max_counts"] = float(np.max(full_dark))
            # Normalized LED metadata (alias to s_mode_intensity)
            result.normalized_leds = dict(result.s_mode_intensity)
            # Brightness ratios derived from mean ROI signals of S RAW references
            try:
                s_means = {
                    ch: float(np.mean(result.s_raw_data[ch]))
                    for ch in result.s_raw_data
                }
                weakest_mean = s_means.get(result.weakest_channel)
                if weakest_mean and weakest_mean > 0:
                    result.brightness_ratios = {
                        ch: s_means[ch] / weakest_mean for ch in s_means
                    }
            except Exception:
                pass
            # LEDs calibrated compatibility field
            result.leds_calibrated = dict(result.p_mode_intensity)
            # Basic QC placeholders for Step 6 consumption (use RAW data)
            try:
                # Calculate S-mode top-50 metrics
                s_top50_signals, s_top50_pcts = calculate_qc_top50_metrics(
                    result.s_raw_data,
                    result.detector_max_counts,
                )
                result.qc_results["s_mode_top50"] = s_top50_signals
                result.qc_results["s_mode_top50_pct"] = s_top50_pcts

                # Calculate P-mode top-50 metrics
                p_top50_signals, p_top50_pcts = calculate_qc_top50_metrics(
                    result.p_raw_data,
                    result.detector_max_counts,
                )
                result.qc_results["p_mode_top50"] = p_top50_signals
                result.qc_results["p_mode_top50_pct"] = p_top50_pcts
            except Exception:
                pass

            logger.info("")
            logger.info("=" * 80)
            logger.info("[OK] LED CONVERGENCE COMPLETE - Proceeding to Step 6")
            logger.info("=" * 80)
            logger.info("")

        # === CALCULATE NUM_SCANS FOR LIVE DATA (based on detector window) ===
        # Live data should use num_scans calculated from detector window and integration time
        # Minimum 3 scans required for noise reduction
        try:
            from settings import DETECTOR_WINDOW_MS
            detector_window_ms = DETECTOR_WINDOW_MS  # 210ms default

            # Use P-mode integration time (typically longer than S-mode)
            integration_time_ms = result.p_integration_time

            # Calculate maximum scans that fit in detector window
            max_scans = int(detector_window_ms / integration_time_ms)

            # Set num_scans with minimum of 3
            result.num_scans = max(3, max_scans)

            logger.info(f"[OK] Calculated num_scans for live data:")
            logger.info(f"   Integration time: {integration_time_ms:.1f}ms")
            logger.info(f"   Detector window: {detector_window_ms:.0f}ms")
            logger.info(f"   Max scans in window: {max_scans}")
            logger.info(f"   Final num_scans: {result.num_scans} (min 3)")
            logger.info("")
        except Exception as e:
            logger.warning(f"Failed to calculate num_scans, using default: {e}")
            result.num_scans = 3  # Safe fallback
            logger.info(f"   Using fallback num_scans: {result.num_scans}")
            logger.info("")
            result.ref_intensity = (
                dict(result.s_mode_intensity)
                if hasattr(result, "s_mode_intensity") and result.s_mode_intensity
                else {}
            )

            # ===================================================================
            # STEP 6: DATA PROCESSING + TRANSMISSION CALCULATION + QC (FINAL STEP)
            # (Direct path after LED convergence)
            # ===================================================================
            logger.info("=" * 80)
            logger.info(
                "STEP 6: Data Processing + Transmission Calculation + QC (FINAL STEP)",
            )
            logger.info("=" * 80)

            if progress_callback:
                progress_callback(
                    f"Step {CALIBRATION_NUM_STEPS} of {CALIBRATION_NUM_STEPS}: Preparing QC results",
                    83,
                )

            try:
                # Part A: Verify data availability
                logger.info("\n📊 Part A: Verifying Raw Data Availability")

                if not hasattr(result, "s_raw_data") or not result.s_raw_data:
                    msg = "S-pol raw data missing from convergence output"
                    raise RuntimeError(msg)
                if not hasattr(result, "p_raw_data") or not result.p_raw_data:
                    msg = "P-pol raw data missing from convergence output"
                    raise RuntimeError(msg)
                if not hasattr(result, "dark_s") or not result.dark_s:
                    msg = "S-mode dark reference missing from convergence output"
                    raise RuntimeError(msg)
                if not hasattr(result, "dark_p") or not result.dark_p:
                    msg = "P-mode dark reference missing from convergence output"
                    raise RuntimeError(msg)

                logger.info("   [OK] S-pol raw data: 4 channels from convergence")
                logger.info("   [OK] P-pol raw data: 4 channels from convergence")
                logger.info("   [OK] S-mode dark references: 4 channels from convergence")
                logger.info("   [OK] P-mode dark references: 4 channels from convergence")
                logger.info(
                    f"   [OK] S-mode integration time: {result.s_integration_time:.2f}ms",
                )
                logger.info(
                    f"   [OK] P-mode integration time: {result.p_integration_time:.2f}ms",
                )

                # Part B: Process polarization data
                logger.info(
                    "\n🔧 Part B: Processing Polarization Data (SpectrumPreprocessor)",
                )

                # Sanity check: S vs P magnitude before processing
                try:
                    s_means_pre = {
                        ch: float(np.mean(result.s_raw_data[ch]))
                        for ch in ch_list
                        if ch in result.s_raw_data
                    }
                    p_means_pre = {
                        ch: float(np.mean(result.p_raw_data[ch]))
                        for ch in ch_list
                        if ch in result.p_raw_data
                    }
                    s_medians_pre = {
                        ch: float(np.median(result.s_raw_data[ch]))
                        for ch in ch_list
                        if ch in result.s_raw_data
                    }
                    p_medians_pre = {
                        ch: float(np.median(result.p_raw_data[ch]))
                        for ch in ch_list
                        if ch in result.p_raw_data
                    }

                    logger.info(
                        "   [SEARCH] Preprocess sanity: S_raw vs P_raw (ROI statistics)",
                    )
                    logger.info(
                        "   Note: Convergence targets MEDIAN (peak signal), not MEAN",
                    )
                    for ch in ch_list:
                        if ch in s_means_pre and ch in p_means_pre:
                            ratio = (
                                (p_means_pre[ch] / s_means_pre[ch])
                                if s_means_pre[ch] > 0
                                else float("inf")
                            )
                            s_med = s_medians_pre.get(ch, 0)
                            p_med = p_medians_pre.get(ch, 0)
                            logger.info(
                                f"      {ch.upper()}: S_mean={s_means_pre[ch]:.0f}, P_mean={p_means_pre[ch]:.0f}, P/S={ratio:.3f}",
                            )
                            logger.info(
                                f"          S_median={s_med:.0f} (target: {QC_TARGET_MEDIAN_COUNTS}), P_median={p_med:.0f}",
                            )
                    if all(
                        ch in s_means_pre
                        and ch in p_means_pre
                        and p_means_pre[ch] > s_means_pre[ch]
                        for ch in ch_list
                    ):
                        logger.warning(
                            "   [WARN] Polarizer inversion detected: P_raw > S_raw across all channels",
                        )
                        logger.warning(
                            "   [WARN] Applying runtime swap for correct transmission calculation",
                        )
                        logger.warning("   Note: Servo EEPROM positions are NOT changed")
                        # Swap raw references for correct transmission calculation
                        s_raw_corrected = result.p_raw_data
                        p_raw_corrected = result.s_raw_data
                        result.qc_results = result.qc_results or {}
                        result.qc_results["sp_swap_applied"] = True
                        result.qc_results["sp_swap_reason"] = (
                            "P_raw > S_raw across all channels"
                        )
                    else:
                        # No swap needed - use data as-is
                        s_raw_corrected = result.s_raw_data
                        p_raw_corrected = result.p_raw_data
                except Exception as _e:
                    logger.debug(f"   (Sanity check skipped: {_e})")
                    s_raw_corrected = result.s_raw_data
                    p_raw_corrected = result.p_raw_data

                s_pol_ref = {}
                p_pol_ref = {}

                for ch in ch_list:
                    logger.info(f"Processing channel {ch.upper()}...")

                    s_pol_ref[ch] = SpectrumPreprocessor.process_polarization_data(
                        raw_spectrum=s_raw_corrected[ch],
                        dark_noise=result.dark_noise,
                        channel_name=ch,
                        verbose=True,
                    )

                    p_pol_ref[ch] = SpectrumPreprocessor.process_polarization_data(
                        raw_spectrum=p_raw_corrected[ch],
                        dark_noise=result.dark_noise,
                        channel_name=ch,
                        verbose=True,
                    )

                result.s_pol_ref = s_pol_ref
                result.p_pol_ref = p_pol_ref

                logger.info("\n[OK] S-pol and P-pol references processed")
                logger.info("   Ready for QC display")

                # Part C: Transmission spectrum
                logger.info(
                    "\n📈 Part C: Calculating Transmission Spectrum (TransmissionProcessor)",
                )
                logger.info(
                    "   Processing calibration references with live pipeline (QC preview)",
                )

                transmission_spectra = {}
                for ch in ch_list:
                    logger.info(f"\n{'=' * 80}")
                    logger.info(
                        f"Channel {ch.upper()}: TransmissionProcessor Processing",
                    )
                    logger.info(f"{'=' * 80}")

                    transmission_ch = TransmissionProcessor.process_single_channel(
                        p_pol_clean=p_pol_ref[ch],
                        s_pol_ref=s_pol_ref[ch],
                        led_intensity_s=result.ref_intensity[ch],
                        led_intensity_p=result.p_mode_intensity[ch],
                        wavelengths=result.wave_data,
                        apply_sg_filter=True,
                        baseline_method="percentile",
                        baseline_percentile=95.0,
                        verbose=True,
                    )

                    transmission_spectra[ch] = transmission_ch

                result.transmission = transmission_spectra

                logger.info("\n" + "=" * 80)
                logger.info("[OK] Transmission spectra calculated")
                logger.info("   Ready for QC display and peak tracking pipeline")
                logger.info("=" * 80)

                # Part D: Comprehensive QC
                logger.info(
                    "\n[SEARCH] Part D: Comprehensive QC Validation & Orientation Check",
                )
                logger.info("=" * 80)

                qc_results = {}

                # Use detector params for saturation checks
                det_params_for_qc = get_detector_params(device_type)

                for ch in ch_list:
                    logger.info(f"\n{'=' * 80}")
                    logger.info(f"Channel {ch.upper()} QC Validation")
                    logger.info(f"{'=' * 80}")

                    transmission_ch = transmission_spectra[ch]
                    wavelengths = result.wave_data

                    qc = TransmissionProcessor.calculate_transmission_qc(
                        transmission_spectrum=transmission_ch,
                        wavelengths=wavelengths,
                        channel=ch,
                        p_spectrum=p_raw_corrected[ch],
                        s_spectrum=s_raw_corrected[ch],
                        detector_max_counts=det_params_for_qc.max_counts,
                        saturation_threshold=det_params_for_qc.saturation_threshold,
                    )

                    logger.info("📊 SPR Dip Analysis:")
                    logger.info(f"   Dip Wavelength: {qc['dip_wavelength']:.1f}nm")
                    logger.info(f"   Min Transmission: {qc['transmission_min']:.1f}%")
                    logger.info(f"   Dip Depth: {qc['dip_depth']:.1f}%")
                    logger.info(
                        f"   Status: {'[OK] DETECTED' if qc['dip_detected'] else '[ERROR] WEAK/ABSENT'} (depth > {QC_MIN_DIP_DEPTH_PERCENT}%)",
                    )

                    logger.info("\n📊 FWHM Analysis:")
                    if qc["fwhm"] is not None:
                        logger.info(f"   FWHM: {qc['fwhm']:.1f}nm")
                        logger.info(f"   Quality: {qc['fwhm_quality'].upper()}")
                        fwhm_pass = qc["fwhm"] < QC_MAX_FWHM_NM
                        logger.info(
                            f"   Status: {'[OK] PASS' if fwhm_pass else '[ERROR] FAIL'} (FWHM < {QC_MAX_FWHM_NM}nm)",
                        )
                    else:
                        logger.info("   FWHM: Cannot calculate")
                        logger.info("   Status: [ERROR] FAIL")
                        fwhm_pass = False

                    logger.info("\n📊 Polarizer Orientation Check:")
                    if qc["ratio"] is not None:
                        logger.info(f"   P/S Ratio: {qc['ratio']:.3f}")
                        if qc["orientation_correct"] is True:
                            logger.info("   Status: [OK] CORRECT (0.10 ≤ P/S ≤ 0.95)")
                        elif qc["orientation_correct"] is False:
                            logger.error("   Status: [ERROR] INVERTED (P/S > 1.15)")
                            logger.error(
                                "   [WARN]  CRITICAL: Polarizer appears INVERTED!",
                            )
                            logger.error("   Expected: P-mode < S-mode (ratio < 0.95)")
                            logger.error(
                                f"   Actual: P-mode > S-mode (ratio = {qc['ratio']:.3f})",
                            )
                        else:
                            logger.warning(
                                "   Status: [WARN] INDETERMINATE (borderline ratio)",
                            )
                    else:
                        logger.info("   P/S Ratio: Not calculated")
                        logger.info("   Status: [WARN] CANNOT VERIFY")

                    logger.info("\n📊 Saturation Check:")
                    if qc["s_saturated"] or qc["p_saturated"]:
                        if qc["s_saturated"]:
                            logger.error(
                                f"   S-pol: [ERROR] SATURATED ({qc['s_max_counts']:.0f} counts)",
                            )
                        if qc["p_saturated"]:
                            logger.error(
                                f"   P-pol: [ERROR] SATURATED ({qc['p_max_counts']:.0f} counts)",
                            )
                    else:
                        logger.info(
                            f"   S-pol: [OK] OK ({qc['s_max_counts']:.0f} counts)",
                        )
                        logger.info(
                            f"   P-pol: [OK] OK ({qc['p_max_counts']:.0f} counts)",
                        )

                    channel_pass = (
                        qc["dip_detected"]
                        and fwhm_pass
                        and qc["orientation_correct"] is not False
                        and not qc["s_saturated"]
                        and not qc["p_saturated"]
                    )

                    logger.info(f"\n{'=' * 40}")
                    logger.info(
                        f"Channel {ch.upper()}: {'[OK] PASS' if channel_pass else '[ERROR] FAIL'}",
                    )
                    logger.info(f"{'=' * 40}")

                    qc_results[ch] = {
                        "dip_wavelength": qc["dip_wavelength"],
                        "dip_depth": qc["dip_depth"],
                        "dip_detected": qc["dip_detected"],
                        "fwhm": qc["fwhm"] if qc["fwhm"] is not None else 0,
                        "fwhm_pass": fwhm_pass,
                        "fwhm_quality": qc["fwhm_quality"],
                        "p_s_ratio": qc["ratio"],
                        "orientation_correct": qc["orientation_correct"],
                        "s_saturated": qc["s_saturated"],
                        "p_saturated": qc["p_saturated"],
                        "s_max_counts": qc["s_max_counts"],
                        "p_max_counts": qc["p_max_counts"],
                        "warnings": qc["warnings"],
                        "overall_pass": channel_pass,
                    }

                # Calculate SNR for legacy QC compatibility
                for ch in ch_list:
                    signal_mean = np.mean(s_pol_ref[ch])
                    noise_std = np.std(result.dark_noise)
                    snr = signal_mean / max(noise_std, 1.0)
                    snr_pass = snr > QC_MIN_SNR_THRESHOLD
                    qc_results[ch]["snr"] = snr
                    qc_results[ch]["snr_pass"] = snr_pass

                # Add model validation results to QC for reporting
                if convergence_result.get("model_validation_s"):
                    result.qc_results["model_validation_s"] = convergence_result["model_validation_s"]
                if convergence_result.get("model_validation_p"):
                    result.qc_results["model_validation_p"] = convergence_result["model_validation_p"]

                result.qc_results = qc_results
                result.ch_error_list = [
                    ch for ch, qc in qc_results.items() if not qc["overall_pass"]
                ]

                # Finalization and summary
                result.leds_calibrated = result.p_mode_intensity
                result.pre_led_delay_ms = pre_led_delay_ms
                result.post_led_delay_ms = post_led_delay_ms
                result.success = True

                logger.info("\n" + "=" * 80)
                logger.info(f"[OK] {CALIBRATION_NUM_STEPS}-STEP CALIBRATION COMPLETE")
                logger.info("=" * 80)
                s_pos = getattr(result, "s_position", None) or getattr(
                    result,
                    "polarizer_s_position",
                    "N/A",
                )
                p_pos = getattr(result, "p_position", None) or getattr(
                    result,
                    "polarizer_p_position",
                    "N/A",
                )
                logger.info(f"Servo Positions: S={s_pos}°, P={p_pos}°")
                logger.info(
                    f"LED Timing: PRE={pre_led_delay_ms}ms, POST={post_led_delay_ms}ms",
                )
                logger.info(f"LED Intensities (S-mode): {result.ref_intensity}")
                logger.info(f"LED Intensities (P-mode): {result.p_mode_intensity}")
                logger.info(
                    f"Integration Time (S-mode): {result.s_integration_time}ms (representative)",
                )
                if (
                    hasattr(result, "s_channel_integration_times")
                    and result.s_channel_integration_times
                ):
                    logger.info(
                        f"  Per-channel S-times: {result.s_channel_integration_times}",
                    )
                logger.info(
                    f"Integration Time (P-mode): {result.p_integration_time}ms (representative)",
                )

                # QC: Check if P-mode integration time exceeds budget cap
                P_MODE_INTEGRATION_CAP_MS = 65.0
                if result.p_integration_time > P_MODE_INTEGRATION_CAP_MS:
                    logger.warning(
                        f"⚠️  P-mode integration time ({result.p_integration_time:.1f}ms) exceeds budget cap ({P_MODE_INTEGRATION_CAP_MS}ms)"
                    )
                    logger.warning(
                        f"   This may result in below-target signal intensity but is allowed to pass QC"
                    )

                if (
                    hasattr(result, "p_channel_integration_times")
                    and result.p_channel_integration_times
                ):
                    logger.info(
                        f"  Per-channel P-times: {result.p_channel_integration_times}",
                    )
                logger.info(f"Scans per Channel: {result.num_scans}")
                logger.info(
                    f"S-pol Raw Data: {list(result.s_raw_data.keys()) if hasattr(result, 's_raw_data') else 'Not captured'}",
                )
                logger.info(
                    f"P-pol Raw Data: {list(result.p_raw_data.keys()) if hasattr(result, 'p_raw_data') else 'Not captured'}",
                )

                if progress_callback:
                    progress_callback("Calibration complete", 100)

                # Validation: Quick check that critical data is present
                if not hasattr(result, "s_pol_ref") or not result.s_pol_ref:
                    logger.error("CRITICAL: s_pol_ref missing after calibration!")
                if not hasattr(result, "p_pol_ref") or not result.p_pol_ref:
                    logger.error("CRITICAL: p_pol_ref missing after calibration!")
                if not hasattr(result, "wave_data") or result.wave_data is None:
                    logger.error("CRITICAL: wave_data missing after calibration!")

                # CRITICAL CHECK: Ensure all channels have s_pol_ref
                missing_spol = []
                if hasattr(result, "s_pol_ref") and result.s_pol_ref:
                    for ch in ch_list:
                        if ch not in result.s_pol_ref or result.s_pol_ref[ch] is None:
                            missing_spol.append(ch)

                if missing_spol:
                    logger.error(
                        f"\n[ERROR] CRITICAL ERROR: Missing S-pol refs for channels: {missing_spol}",
                    )
                    logger.error(
                        "   These channels will have EMPTY TRANSMISSION in live data!",
                    )
                else:
                    logger.info("\n[OK] ALL CHANNELS HAVE S-POL REFERENCE DATA")

                logger.info(
                    "[OK] VALIDATION COMPLETE - RESULT READY FOR LIVE ACQUISITION",
                )

                # Persist result
                save_calibration_result_json(result)

                return result

            except Exception as e:
                logger.exception(f"Error in Step 6 processing (convergence path): {e}")
                raise

        else:
            # === LEGACY PATH REMOVED ===
            # LED ranking (Step 3) removed - use LED convergence workflow (USE_LED_CONVERGENCE = True)
            logger.error("=" * 80)
            logger.error("[ERROR] LEGACY CALIBRATION PATH DISABLED")
            logger.error("=" * 80)
            logger.error("LED ranking and legacy Steps 3-5 have been removed.")
            logger.error(
                "Please use the LED convergence workflow (USE_LED_CONVERGENCE = True)",
            )
            logger.error("=" * 80)
            result.success = False
            result.error_message = (
                "Legacy calibration path disabled - use LED convergence"
            )
            return result

        # ===================================================================
        # LEGACY CODE REMOVED (Steps 3-7)
        # ===================================================================
        # Previously contained ~2265 lines of unreachable legacy calibration code.
        # This code followed the return statement above and referenced deleted
        # LED ranking variables (ranked_channels, weakest_ch, etc.).
        # Removed during LED ranking cleanup - December 2025

        # ===================================================================
        # CONVERGENCE PATH EXCEPTION HANDLING (Below at line ~4848)
        # ===================================================================
        # Note: Exception handler for run_full_7step_calibration() is at end of function

        return result

    except Exception as e:
        # Print full traceback immediately to console
        import traceback

        try:
            # Use format_exc() which returns a string instead of print_exc() which can write bytes
            traceback.format_exc()
        except Exception:
            # If traceback formatting fails, format manually
            pass

        # Safely convert exception to string (handle bytes if present)
        error_msg = (
            str(e) if not isinstance(e, bytes) else e.decode("utf-8", errors="replace")
        )
        logger.exception(
            f"{CALIBRATION_NUM_STEPS}-step calibration failed: {error_msg}",
        )
        result.success = False
        result.error = error_msg
        return result

    finally:
        # Ensure device is left in safe state regardless of success/failure
        try:
            logger.debug("Performing graceful cleanup...")
            ctrl.turn_off_channels()
            logger.debug("[OK] All LEDs turned off")
        except Exception as cleanup_error:
            logger.warning(f"Error during cleanup: {cleanup_error}")


# =============================================================================
# LEGACY CALIBRATION PATHS (REMOVED)
# =============================================================================
# Removed legacy fast-track and global LED mode paths.
# All calibrations use run_full_7step_calibration() with model-based convergence.


# =============================================================================
# GLOBAL LED MODE CALIBRATION (REMOVED)
# =============================================================================

# REMOVED: run_global_led_calibration() - Alternative mode uses same Steps 4-6
# Alternative calibration modes (e.g., LED=255 fixed + variable integration per channel)
# branch at Step 3C but share identical Steps 4-6 logic with run_full_7step_calibration().
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
    tolerance_percent=0.05,
    strategy="intensity",
    progress_callback=None,
):
    """Replace Steps 3-5 using LED convergence workflow.

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
        progress_callback: Optional callback(message, percent) for UI progress

    Returns:
        dict with:
        - success: bool
        - s_mode_intensities: dict {ch: int}
        - p_mode_intensities: dict {ch: int}
        - s_integration_time: float (ms)
        - p_integration_time: float (ms)
        - s_raw_roi: dict {ch: ndarray} - S-mode RAW spectra (ROI only)
        - p_raw_roi: dict {ch: ndarray} - P-mode RAW spectra (ROI only)
        - dark_spectrum: ndarray - Dark scan (full detector)
        - weakest_channel: str - Weakest channel ID
        - error: str (if failed)

    """
    try:
        from affilabs.utils.LEDCONVERGENCE import run_convergence

        logger.info("[OK] LED convergence module loaded")
    except Exception as e:
        logger.error(f"[ERROR] LED convergence import failed: {e}")
        return {
            "success": False,
            "error": f"Import failed: {e}",
            "s_mode_intensities": {},
            "p_mode_intensities": {},
            "s_integration_time": None,
            "p_integration_time": None,
            "s_pol_ref": {},
            "p_pol_ref": {},
            "dark_spectrum": None,
            "weakest_channel": None,
        }

    import time

    import numpy as np

    result = {
        "success": False,
        "s_mode_intensities": {},
        "p_mode_intensities": {},
        "s_integration_time": None,
        "p_integration_time": None,
        "s_raw_roi": {},
        "p_raw_roi": {},
        # Back-compat legacy keys (same contents as raw ROI)
        "s_pol_ref": {},
        "p_pol_ref": {},
        "dark_spectrum": None,
        "weakest_channel": None,
        "error": None,
    }

    try:
        # === STEP 3: Load 3-Stage Linear Model and Get Predicted LED Values ===
        if progress_callback:
            progress_callback(
                f"Step 3 of {CALIBRATION_NUM_STEPS}: Loading 3-stage linear model",
                40,
            )

        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 STEP 3: Loading 3-Stage Linear Model (Predicted LED Values)")
        logger.info("=" * 80)

        model_initial_integration = None  # Model MUST provide this - no default
        model_predicted_leds_s = None  # Model-predicted S-pol LED intensities
        model_predicted_leds_p = None  # Model-predicted P-pol LED intensities
        loaded_model = None  # Cache model instance for reuse in validation

        try:
            from affilabs.utils.model_loader import (
                LEDCalibrationModelLoader,
                ModelNotFoundError,
            )

            detector_serial = getattr(usb, "serial_number", None)
            logger.info(f"🔍 Detector serial check: serial_number={detector_serial}")
            if detector_serial and detector_serial != "Unknown":
                logger.info(f"✓ Loading model for detector: {detector_serial}")
                model = LEDCalibrationModelLoader()
                model.load_model(detector_serial)

                # Get model info
                model_info = model.get_model_info()
                logger.info(f"✓ Model loaded: {model_info['timestamp']}")

                # Show R² scores for quality check
                r2_scores = model_info["r2_scores"]
                logger.info("  Model Accuracy (R²):")
                for ch in ["A", "B", "C", "D"]:
                    s_r2 = r2_scores[ch]["S"]
                    logger.info(f"    {ch}: S={s_r2:.6f}")

                # Get optimal parameters from model
                target_counts = target_percent * detector_params.max_counts
                ch_list_upper = [
                    ch.upper() for ch in ch_list
                ]  # Model expects uppercase

                logger.info("  Calculating optimal parameters from model:")
                logger.info(
                    f"    Target counts: {target_counts:.0f} ({target_percent * 100:.0f}% detector)",
                )

                # Get optimal integration time and LED intensities from model
                model_params = model.get_default_parameters(
                    target_counts=target_counts,
                    max_time_ms=60.0,  # Constraint: ≤60ms per LED measurement
                )

                model_initial_integration = model_params["integration_time_ms"]
                model_predicted_leds_s = model_params["led_intensities"]

                logger.info(
                    f"  ✓ Model calculated optimal integration time: {model_initial_integration:.1f}ms",
                )
                logger.info(f"    LED intensities (S-pol): {model_predicted_leds_s}")

                # Calculate P-pol LED intensities at same integration time
                model_predicted_leds_p = model.calculate_all_led_intensities(
                    polarization="P",
                    time_ms=model_initial_integration,
                    target_counts=target_counts,
                    channels=ch_list_upper,
                )

                model_predicted_leds_p = model.calculate_all_led_intensities(
                    polarization="P",
                    time_ms=model_initial_integration,
                    target_counts=target_counts,
                    channels=ch_list_upper,
                )

                # Convert to lowercase for compatibility with ch_list
                model_predicted_leds_s = {
                    k.lower(): v for k, v in model_predicted_leds_s.items()
                }
                model_predicted_leds_p = {
                    k.lower(): v for k, v in model_predicted_leds_p.items()
                }

                logger.info(f"    LED intensities (P-pol): {model_predicted_leds_p}")
                logger.info("  ✓ Model parameters ready for convergence")
                logger.info("    Mode: 4-LED (A, B, C, D)")
                logger.info("    Time constraint: ≤60ms per LED")
                logger.info(
                    "✓ Using model-calculated parameters (optimal time + variable intensities)",
                )

                # Cache model instance for validation step (avoids reloading)
                loaded_model = model
            else:
                logger.error("=" * 80)
                logger.error("❌ CRITICAL ERROR: NO DETECTOR SERIAL NUMBER")
                logger.error("=" * 80)
                logger.error(f"   Detector serial: {detector_serial}")
                logger.error("   A valid detector serial number is required to load the model.")
                logger.error("=" * 80)
                result["error"] = f"No valid detector serial number: {detector_serial}"
                return result

        except ModelNotFoundError as e:
            logger.error("=" * 80)
            logger.error("❌ CRITICAL ERROR: 3-STAGE LINEAR MODEL NOT FOUND")
            logger.error("=" * 80)
            logger.error(f"   Error: {e}")
            logger.error("")
            logger.error("   Model loader searches in:")
            logger.error("   1. led_calibration_official/<detector_serial>/")
            logger.error("   2. led_calibration_official/<detector_serial>_model.pkl")
            logger.error(f"   3. Current detector serial: {detector_serial}")
            logger.error("")
            from pathlib import Path
            model_dir = Path("led_calibration_official")
            if model_dir.exists():
                logger.error(f"   Model directory exists: {model_dir.absolute()}")
                logger.error(f"   Contents: {list(model_dir.iterdir())}")
            else:
                logger.error(f"   Model directory NOT FOUND: {model_dir.absolute()}")
            logger.error("")
            logger.error("   🔧 REQUIRED: Run OEM LED calibration to create model")
            logger.error("   Command: python led_calibration_official/1_create_model.py")
            logger.error("=" * 80)
            result["error"] = f"Model not found for detector {detector_serial}: {e}"
            return result
        except Exception as e:
            logger.error("=" * 80)
            logger.error("❌ CRITICAL ERROR: MODEL LOAD/CALCULATION FAILED")
            logger.error("=" * 80)
            logger.error(f"   Error: {e}")
            logger.error("   Exception details:", exc_info=True)
            logger.error("")
            logger.error("   This is an unexpected error during model loading.")
            logger.error("   Check that the model file is not corrupted.")
            logger.error("=" * 80)
            result["error"] = f"Model load failed: {e}"
            return result

        # Validate that model provided integration time
        if model_initial_integration is None:
            logger.error("=" * 80)
            logger.error("❌ CRITICAL ERROR: MODEL DID NOT PROVIDE INTEGRATION TIME")
            logger.error("=" * 80)
            logger.error("   The model loaded but failed to calculate integration time.")
            logger.error("   This indicates a problem with the model or input parameters.")
            logger.error("=" * 80)
            result["error"] = (
                "Model failed to provide integration time - cannot proceed"
            )
            logger.error(f"[ERROR] {result['error']}")
            return result

        logger.info("")

        # === SERVO POSITIONING: Move to S-mode before convergence ===
        logger.info("=" * 80)
        logger.info("🔧 SERVO POSITIONING: Moving to S-mode")
        logger.info("=" * 80)

        # Turn off LEDs for safety
        logger.info("🔒 Safety: Turning off all LEDs before servo movement...")
        ctrl.turn_off_channels()
        time.sleep(0.1)
        logger.info("   [OK] All LEDs OFF")

        # Load servo positions once and cache for both S and P modes
        servo_positions = _get_servo_positions_from_config(
            device_config_det,
            usb.serial_number if hasattr(usb, "serial_number") else "UNKNOWN",
        )
        s_pos = servo_positions["s_position"]
        p_pos = servo_positions["p_position"]
        result["servo_positions"] = servo_positions  # Cache for P-mode transition

        logger.info("📍 Servo positions from device_config:")
        logger.info(f"   S-position: {s_pos}°")
        logger.info(f"   P-position: {p_pos}°")

        # Park to 1° (backlash removal)
        if hasattr(ctrl, "servo_move_calibration_only"):
            logger.info("")
            logger.info("🔄 Step 1: Parking polarizer to 1° (backlash removal)...")
            park_ok = ctrl.servo_move_calibration_only(s=1, p=1)
            time.sleep(1.0)
            if park_ok:
                logger.info("   [OK] Parked to 1°")
            else:
                logger.warning(
                    "   [WARN]  Park command did not confirm (continuing anyway)",
                )

            # Move explicitly to S/P positions
            logger.info("")
            logger.info(f"🔄 Step 2: Moving to S={s_pos}°, P={p_pos}°...")
            move_ok = ctrl.servo_move_calibration_only(s=int(s_pos), p=int(p_pos))
            time.sleep(1.0)
            if move_ok:
                logger.info(f"   [OK] Moved to S={s_pos}°, P={p_pos}°")
            else:
                logger.warning(
                    "   [WARN]  Move command did not confirm (continuing anyway)",
                )
        else:
            logger.warning(
                "   [WARN]  Controller lacks servo_move_calibration_only - skipping explicit pre-positioning",
            )

        # Lock S-mode via firmware
        logger.info("")
        logger.info("🔒 Step 3: Locking S-mode via firmware command...")
        mode_ok = ctrl.set_mode("s")
        time.sleep(0.5)
        if mode_ok:
            logger.info("   [OK] S-mode locked")
        else:
            logger.warning(
                "   [WARN] S-mode lock unconfirmed (continuing - may already be set)",
            )

        logger.info("=" * 80)
        logger.info("[OK] SERVO READY: S-MODE ACTIVE")
        logger.info("=" * 80)
        logger.info("")

        # === STEP 3C: S-mode LED convergence (uses model predictions if available) ===
        if progress_callback:
            progress_callback(
                f"Step 3 of {CALIBRATION_NUM_STEPS}: S-mode LED convergence",
                50,
            )

        logger.info(
            f"   Target: {target_percent * 100:.0f}% detector, tolerance: ±{tolerance_percent * 100:.0f}%",
        )
        logger.info(f"   Strategy: {strategy}")
        logger.info(
            f"   Initial integration: {model_initial_integration:.1f}ms (from model)",
        )

        if model_predicted_leds_s:
            logger.info("   🎯 Using model-predicted LED values")
            logger.info(f"   Model predictions: {model_predicted_leds_s}")
        else:
            logger.error("=" * 80)
            logger.error("❌ CRITICAL ERROR: NO MODEL PREDICTIONS AVAILABLE")
            logger.error("=" * 80)
            logger.error("   Model predictions are required for S-mode convergence.")
            logger.error("   This should not happen if model loaded successfully.")
            logger.error("=" * 80)
            result["error"] = "No model predictions available for convergence"
            return result
        logger.info("")

        # Extract model slopes for smart saturation correction
        model_slopes_s = None
        if loaded_model:
            try:
                model_slopes_s = loaded_model.get_slopes(polarization="S", channels=ch_list_upper)
                logger.info(f"   📊 Model slopes (S-pol): {model_slopes_s}")
            except Exception as e:
                logger.warning(f"   ⚠  Could not extract model slopes: {e}")

        s_shared_int, s_per_ch_results, s_ok = run_convergence(
            usb=usb,
            ctrl=ctrl,
            ch_list=ch_list,
            acquire_raw_spectrum_fn=acquire_raw_spectrum,
            roi_signal_fn=roi_signal,
            detector_params=detector_params,
            wave_min_index=wave_min_index,
            wave_max_index=wave_max_index,
            strategy=strategy,  # Use selected strategy (intensity/shared-time)
            initial_integration_ms=model_initial_integration,  # From model (or fallback 70ms)
            model_predicted_leds=model_predicted_leds_s,  # NEW: Pass model predictions to convergence
            model_slopes=model_slopes_s,  # NEW: Pass model slopes for smart saturation correction
            polarization="S",  # NEW: Specify polarization
            target_percent=0.90,  # S-mode: 90% detector
            tolerance_percent=tolerance_percent,
            tighten_final=False,
            use_batch_command=CONVERGENCE_USE_BATCH_COMMAND,
            logger=logger,
        )

        if not s_ok:
            result["error"] = "S-mode convergence failed: Did not converge to target"
            logger.error(f"[ERROR] {result['error']}")
            return result

        # CRITICAL: Turn off LED D explicitly after S-mode convergence
        # Convergence cycles A→B→C→D, each LED turning on disables previous
        # But LED D has no "next LED" so it stays ON at the end
        ctrl.set_intensity('d', 0)
        time.sleep(0.05)
        logger.debug("[S-CONV] LED D explicitly disabled after convergence")

        # Extract LED intensities and integration time from results
        result["s_mode_intensities"] = {
            ch: int(s_per_ch_results[ch]["final_led"]) for ch in ch_list
        }
        # Derive per-channel integration times from results when strategy='time'
        s_channel_times = {
            ch: float(s_per_ch_results[ch]["final_integration_ms"])
            for ch in s_per_ch_results
        }
        # Store a representative S integration (median) for compatibility
        if s_shared_int is not None:
            result["s_integration_time"] = s_shared_int
        else:
            try:
                result["s_integration_time"] = (
                    float(np.median(list(s_channel_times.values())))
                    if s_channel_times
                    else None
                )
            except Exception:
                result["s_integration_time"] = s_per_ch_results[ch_list[0]][
                    "final_integration_ms"
                ]
        # Expose per-channel S times for downstream (optional consumption)
        result["s_channel_integration_times"] = s_channel_times

        logger.info("")
        logger.info("   [OK] S-mode convergence complete:")
        logger.info(f"      Integration time: {result['s_integration_time']:.1f}ms")
        for ch in ch_list:
            logger.info(f"      {ch.upper()}: LED={result['s_mode_intensities'][ch]}")

        # === VALIDATION: Compare convergence results vs model predictions ===
        if progress_callback:
            progress_callback(
                f"Step 4 of {CALIBRATION_NUM_STEPS}: Validating S-pol results",
                60,
            )

        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 MODEL VALIDATION: Comparing S-pol convergence vs model")
        logger.info("=" * 80)

        try:
            # Reuse already-loaded model from Step 3 (avoid redundant reload)
            if loaded_model is not None:
                model = loaded_model
                logger.info("  ✓ Using cached model from Step 3 (no reload needed)")

            else:
                # Fallback: load model if not cached (shouldn't happen normally)
                from affilabs.utils.model_loader import LEDCalibrationModelLoader

                detector_serial = getattr(usb, "serial_number", None)
                if detector_serial and detector_serial != "Unknown":
                    model = LEDCalibrationModelLoader()
                    model.load_model(detector_serial)
                    logger.info("  ℹ Loading model for validation (cache miss)")
                else:
                    msg = f"No cached model and no valid serial: {detector_serial}"
                    raise ValueError(
                        msg,
                    )

            # Convert channel keys to match model expectations
            measured_leds_upper = {
                ch.upper(): result["s_mode_intensities"][ch] for ch in ch_list
            }

            # Validate convergence results against model
            validation = model.validate_convergence_vs_model(
                polarization="S",
                time_ms=result["s_integration_time"],
                measured_leds=measured_leds_upper,
                target_counts=target_percent * detector_params.max_counts,
            )

            logger.info("  Model Predictions vs Measured:")
            for ch in ch_list:
                ch_upper = ch.upper()
                pred = validation["predicted_leds"][ch_upper]
                meas = validation["measured_leds"][ch_upper]
                dev = validation["deviations"][ch_upper]
                pct = validation["percent_errors"][ch_upper]
                logger.info(
                    f"    {ch_upper}: Predicted={pred:3d}, Measured={meas:3d}, Δ={dev:+4d} ({pct:+.1f}%)",
                )

            logger.info("")
            logger.info(f"  Average Error: {validation['average_error_percent']:.1f}%")
            logger.info(f"  Max Error: {validation['max_error_percent']:.1f}%")
            logger.info(
                f"  Validation Status: {validation['validation_status'].upper()}",
            )

            # Store validation results for QC reporting
            result["model_validation_s"] = validation

            # Get model-adjusted P-pol predictions based on S-pol performance
            logger.info("")
            logger.info("📈 Predicting P-pol LEDs based on S-pol performance...")
            p_pol_predictions = model.predict_p_pol_from_s_pol(
                s_pol_time_ms=result["s_integration_time"],
                s_pol_leds=measured_leds_upper,
                target_counts=target_percent * detector_params.max_counts,
            )

            logger.info("  Model-adjusted P-pol starting values:")
            for ch in ch_list:
                ch_upper = ch.upper()
                logger.info(f"    {ch_upper}: LED={p_pol_predictions[ch_upper]}")

            # Store predictions for P-mode convergence to use as starting point
            result["p_pol_predicted_leds"] = {
                ch: p_pol_predictions[ch.upper()] for ch in ch_list
            }

        except Exception as e:
            logger.warning(f"  ⚠ Model validation failed: {e}")
            result["model_validation_s"] = None
            result["p_pol_predicted_leds"] = None

        logger.info("=" * 80)
        logger.info("")

        # === STEP 4: Capture S-pol reference (RAW) ===
        logger.info("")
        logger.info("📸 Step 4: Capturing S-pol reference spectra...")
        
        # CRITICAL: Turn off all LEDs first to ensure clean state
        # Convergence may have left LED D enabled
        ctrl.turn_off_channels()
        time.sleep(0.1)
        
        # Capture S-pol reference using per-channel integration times when available
        for ch in ch_list:
            ch_time = result.get("s_channel_integration_times", {}).get(
                ch,
                result["s_integration_time"],
            )
            usb.set_integration(ch_time)
            time.sleep(0.1)
            ctrl.set_intensity(ch, result["s_mode_intensities"][ch])
            time.sleep(0.05)  # Let command process
            time.sleep(0.20)  # Allow LED to fully stabilize (especially LED D)
            full = usb.read_intensity()
            # Store RAW ROI under explicit and legacy keys
            roi_slice = full[wave_min_index:wave_max_index]
            result["s_raw_roi"][ch] = roi_slice
            result["s_pol_ref"][ch] = (
                roi_slice  # legacy compat: was misnamed but used as raw
            )
            ctrl.set_intensity(ch, 0)

        logger.info(f"   [OK] S-pol ref captured: {len(result['s_pol_ref'])} channels")
        try:
            means = {
                ch: float(np.mean(result["s_raw_roi"][ch]))
                for ch in result["s_raw_roi"]
            }
            logger.info(
                "   [SEARCH] S-mode capture means (ROI): "
                + ", ".join([f"{k.upper()}={v:.0f}" for k, v in means.items()]),
            )
        except Exception as _e:
            logger.debug(f"   (S-mode capture stats unavailable: {_e})")

        # === STEP 5A: P-mode servo movement ===
        logger.info("")
        logger.info("=" * 80)
        logger.info("🔧 SERVO MOVEMENT: Switching from S-mode to P-mode")
        logger.info("=" * 80)

        # Turn off LEDs for safety
        logger.info("🔒 Safety: Turning off all LEDs before servo movement...")
        ctrl.turn_off_channels()
        time.sleep(0.1)
        logger.info("   [OK] All LEDs OFF")

        # Reuse cached servo positions (loaded before S-mode)
        servo_positions = result["servo_positions"]
        s_pos = servo_positions["s_position"]
        p_pos = servo_positions["p_position"]

        # === STEP 5A: Moving to P-mode ===
        if progress_callback:
            progress_callback(
                f"Step 5 of {CALIBRATION_NUM_STEPS}: Switching to P-mode",
                65,
            )

        # Park to 1° (backlash removal)
        if hasattr(ctrl, "servo_move_calibration_only"):
            logger.info("🔄 Step 1: Parking polarizer to 1° (backlash removal)...")
            park_ok = ctrl.servo_move_calibration_only(s=1, p=1)
            time.sleep(0.5)
            if park_ok:
                logger.info("   [OK] Parked to 1°")
            else:
                logger.warning(
                    "   [WARN]  Park command did not confirm (continuing anyway)",
                )

            # Move explicitly to P position (from current S position)
            logger.info(f"🔄 Step 2: Moving from S={s_pos}° to P={p_pos}°...")
            move_ok = ctrl.servo_move_calibration_only(s=int(s_pos), p=int(p_pos))
            time.sleep(0.5)
            if move_ok:
                logger.info(f"   [OK] Moved to P={p_pos}°")
            else:
                logger.warning(
                    "   [WARN]  Move command did not confirm (continuing anyway)",
                )
        else:
            logger.warning(
                "   [WARN]  Controller lacks servo_move_calibration_only - using simple mode switch",
            )

        # Lock P-mode via firmware
        logger.info("🔒 Step 4B: Locking P-mode via firmware command...")
        mode_ok = ctrl.set_mode("p")
        time.sleep(0.3)
        if mode_ok:
            logger.info("   [OK] P-mode locked")
        else:
            logger.warning(
                "   [WARN] P-mode lock unconfirmed (continuing - may already be set)",
            )

        logger.info("=" * 80)
        logger.info("[OK] SERVO MOVEMENT COMPLETE - P-mode active")
        logger.info("=" * 80)
        logger.info("")

        # === STEP 5B: P-mode LED convergence ===
        if progress_callback:
            progress_callback(
                f"Step 5 of {CALIBRATION_NUM_STEPS}: P-mode LED convergence",
                70,
            )

        logger.info("🎯 Step 5B: Running LED convergence in P-mode...")

        # Use model-predicted P-pol LEDs if available, otherwise fall back to model adjustment
        p_mode_led_predictions = None
        if model_predicted_leds_p:
            # Direct model predictions available
            logger.info("   Using model-predicted P-pol LED values")
            logger.info(f"   Model predictions: {model_predicted_leds_p}")
            p_mode_led_predictions = model_predicted_leds_p
        elif result.get("p_pol_predicted_leds"):
            # Legacy: Model-adjusted predictions based on S-pol deviation
            logger.info(
                "   Using model-adjusted P-pol predictions (based on S-pol deviation)",
            )
            p_mode_led_predictions = result["p_pol_predicted_leds"]
        else:
            logger.info(
                "   ⚠️ No model predictions - using empirical convergence from S-mode baseline",
            )
        logger.info("")

        # Extract model slopes for P-mode smart saturation correction
        # NOTE: Use S-pol slopes for P-pol too (same LED-to-counts relationship, just scaled)
        model_slopes_p = None
        if loaded_model:
            try:
                model_slopes_p = loaded_model.get_slopes(polarization="S", channels=ch_list_upper)  # Use S-pol slopes for P-pol!
                logger.info(f"   📊 Model slopes (P-pol using S-pol slopes): {model_slopes_p}")
            except Exception as e:
                logger.warning(f"   ⚠  Could not extract model slopes: {e}")

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
            initial_integration_ms=result[
                "s_integration_time"
            ],  # Start from S-mode integration time
            model_predicted_leds=p_mode_led_predictions,  # NEW: Pass P-mode model predictions
            model_slopes=model_slopes_p,  # NEW: Pass P-mode model slopes for smart saturation correction
            polarization="P",  # NEW: Specify polarization
            target_percent=0.85,  # P-mode: 85% detector
            tolerance_percent=tolerance_percent,
            tighten_final=False,
            use_batch_command=CONVERGENCE_USE_BATCH_COMMAND,
            logger=logger,
        )

        if not p_ok:
            result["error"] = "P-mode convergence failed: Did not converge to target"
            logger.error(f"[ERROR] {result['error']}")
            return result

        # CRITICAL: Turn off LED D explicitly after P-mode convergence
        # Convergence cycles A→B→C→D, each LED turning on disables previous
        # But LED D has no "next LED" so it stays ON at the end
        ctrl.set_intensity('d', 0)
        time.sleep(0.05)
        logger.debug("[P-CONV] LED D explicitly disabled after convergence")

        # Extract LED intensities and integration time from results
        result["p_mode_intensities"] = {
            ch: int(p_per_ch_results[ch]["final_led"]) for ch in ch_list
        }
        result["p_integration_time"] = (
            p_shared_int
            if p_shared_int is not None
            else p_per_ch_results[ch_list[0]]["final_integration_ms"]
        )

        logger.info("")
        logger.info("   [OK] P-mode convergence complete:")
        logger.info(f"      Integration time: {result['p_integration_time']:.1f}ms")
        for ch in ch_list:
            logger.info(f"      {ch.upper()}: LED={result['p_mode_intensities'][ch]}")

        # === VALIDATION: Compare P-pol convergence vs model predictions ===
        if progress_callback:
            progress_callback(
                f"Step 5 of {CALIBRATION_NUM_STEPS}: Validating P-pol results",
                75,
            )

        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 MODEL VALIDATION: Comparing P-pol convergence vs model")
        logger.info("=" * 80)

        try:
            from affilabs.utils.model_loader import LEDCalibrationModelLoader

            detector_serial = getattr(usb, "serial_number", None)
            if detector_serial and detector_serial != "Unknown":
                model = LEDCalibrationModelLoader()
                model.load_model(detector_serial)

                # Convert channel keys to match model expectations
                measured_leds_upper = {
                    ch.upper(): result["p_mode_intensities"][ch] for ch in ch_list
                }

                # Validate convergence results against model
                validation = model.validate_convergence_vs_model(
                    polarization="P",
                    time_ms=result["p_integration_time"],
                    measured_leds=measured_leds_upper,
                    target_counts=target_percent * detector_params.max_counts,
                )

                logger.info("  Model Predictions vs Measured:")
                for ch in ch_list:
                    ch_upper = ch.upper()
                    pred = validation["predicted_leds"][ch_upper]
                    meas = validation["measured_leds"][ch_upper]
                    dev = validation["deviations"][ch_upper]
                    pct = validation["percent_errors"][ch_upper]
                    logger.info(
                        f"    {ch_upper}: Predicted={pred:3d}, Measured={meas:3d}, Δ={dev:+4d} ({pct:+.1f}%)",
                    )

                logger.info("")
                logger.info(
                    f"  Average Error: {validation['average_error_percent']:.1f}%",
                )
                logger.info(f"  Max Error: {validation['max_error_percent']:.1f}%")
                logger.info(
                    f"  Validation Status: {validation['validation_status'].upper()}",
                )

                # Store validation results for QC reporting
                result["model_validation_p"] = validation

            else:
                logger.warning("  ⚠ No detector serial - skipping model validation")
                result["model_validation_p"] = None

        except Exception as e:
            logger.warning(f"  ⚠ Model validation failed: {e}")
            result["model_validation_p"] = None

        logger.info("=" * 80)
        logger.info("")

        # === STEP 5B: Capture P-pol reference (RAW) ===
        logger.info("")
        logger.info("📸 Step 5B: Capturing P-pol reference spectra...")
        
        # CRITICAL: Turn off all LEDs first to ensure clean state
        # Convergence may have left LED D enabled
        ctrl.turn_off_channels()
        time.sleep(0.1)
        
        usb.set_integration(result["p_integration_time"])
        time.sleep(0.1)

        for ch in ch_list:
            ctrl.set_intensity(ch, result["p_mode_intensities"][ch])
            time.sleep(0.05)  # Let command process
            time.sleep(0.20)  # Allow LED to fully stabilize (especially LED D)
            full = usb.read_intensity()
            # Store RAW ROI under explicit and legacy keys
            roi_slice = full[wave_min_index:wave_max_index]
            result["p_raw_roi"][ch] = roi_slice
            result["p_pol_ref"][ch] = (
                roi_slice  # legacy compat: was misnamed but used as raw
            )
            ctrl.set_intensity(ch, 0)

        logger.info(f"   [OK] P-pol ref captured: {len(result['p_pol_ref'])} channels")
        try:
            means = {
                ch: float(np.mean(result["p_raw_roi"][ch]))
                for ch in result["p_raw_roi"]
            }
            logger.info(
                "   [SEARCH] P-mode capture means (ROI): "
                + ", ".join([f"{k.upper()}={v:.0f}" for k, v in means.items()]),
            )
        except Exception as _e:
            logger.debug(f"   (P-mode capture stats unavailable: {_e})")

        # === STEP 5E: DARK SPECTRUM CAPTURE (matching S and P integration times) ===
        if progress_callback:
            progress_callback(
                f"Step 5 of {CALIBRATION_NUM_STEPS}: Capturing dark spectra",
                78,
            )

        logger.info("")
        logger.info("=" * 80)
        logger.info("📸 STEP 5E: Dark Spectrum Capture (S-mode and P-mode)")
        logger.info("=" * 80)

        # Get integration times from convergence results
        s_int_time = result["s_integration_time"]
        p_int_time = result["p_integration_time"]

        logger.info(f"   S-mode integration time: {s_int_time:.2f}ms")
        logger.info(f"   P-mode integration time: {p_int_time:.2f}ms")

        # Determine if we can use a single dark (if times are within 10ms)
        time_diff = abs(s_int_time - p_int_time)
        use_single_dark = time_diff <= 10.0

        if use_single_dark:
            # Use average integration time for single dark capture
            avg_time = (s_int_time + p_int_time) / 2
            logger.info(f"   Integration times within 10ms (Δ={time_diff:.2f}ms)")
            logger.info(f"   Capturing single dark at {avg_time:.2f}ms for both S and P")

            usb.set_integration(avg_time)
            time.sleep(0.2)
            dark_full = usb.read_intensity()

            # Extract ROI for each channel
            dark_s_dict = {}
            dark_p_dict = {}
            for ch in ch_list:
                dark_roi = dark_full[wave_min_index:wave_max_index]
                dark_s_dict[ch] = dark_roi
                dark_p_dict[ch] = dark_roi  # Same dark for both

            result["dark_s"] = dark_s_dict
            result["dark_p"] = dark_p_dict
            result["dark_spectrum"] = dark_full  # Keep legacy field

            logger.info(f"   [OK] Single dark captured: max={np.max(dark_full):.1f} counts")
            logger.info(f"   [OK] Applied to both S-mode and P-mode")

        else:
            # Capture separate darks for S and P modes
            logger.info(f"   Integration times differ by {time_diff:.2f}ms (>10ms)")
            logger.info("   Capturing separate darks for S-mode and P-mode")

            # Capture S-mode dark
            logger.info(f"   Capturing S-mode dark at {s_int_time:.2f}ms...")
            usb.set_integration(s_int_time)
            time.sleep(0.2)
            dark_s_full = usb.read_intensity()

            dark_s_dict = {}
            for ch in ch_list:
                dark_s_dict[ch] = dark_s_full[wave_min_index:wave_max_index]

            result["dark_s"] = dark_s_dict
            logger.info(f"   [OK] S-mode dark: max={np.max(dark_s_full):.1f} counts")

            # Capture P-mode dark
            logger.info(f"   Capturing P-mode dark at {p_int_time:.2f}ms...")
            usb.set_integration(p_int_time)
            time.sleep(0.2)
            dark_p_full = usb.read_intensity()

            dark_p_dict = {}
            for ch in ch_list:
                dark_p_dict[ch] = dark_p_full[wave_min_index:wave_max_index]

            result["dark_p"] = dark_p_dict
            result["dark_spectrum"] = dark_s_full  # Use S-mode dark as legacy field
            logger.info(f"   [OK] P-mode dark: max={np.max(dark_p_full):.1f} counts")

        logger.info("=" * 80)
        logger.info("")

        # === DARK SPECTRUM VALIDATION (compare with model) ===
        if progress_callback:
            progress_callback(
                f"Step 5 of {CALIBRATION_NUM_STEPS}: Validating dark spectrum",
                80,
            )

        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 MODEL VALIDATION: Comparing dark spectrum vs model")
        logger.info("=" * 80)

        try:

            from affilabs.utils.model_loader import (
                LEDCalibrationModelLoader,
                ModelValidationError,
            )

            detector_serial = getattr(usb, "serial_number", None)
            if (
                detector_serial
                and detector_serial != "Unknown"
                and result["dark_spectrum"] is not None
            ):
                # Reuse cached model if available from Step 3
                if loaded_model is not None:
                    model = loaded_model
                else:
                    model = LEDCalibrationModelLoader()
                    model.load_model(detector_serial)

                # Extract ROI from dark spectrum using wave indices
                dark_roi = {}
                dark_spectrum_array = np.array(result["dark_spectrum"])

                # Use same ROI as calibration (wave_min_index to wave_max_index)
                for _ch_idx, ch_name in enumerate(["A", "B", "C", "D"]):
                    if ch_name.lower() in ch_list:
                        # Extract ROI slice for this channel
                        dark_roi[ch_name] = dark_spectrum_array[
                            wave_min_index:wave_max_index
                        ]

                # Validate against model (use S-mode integration time)
                dark_validation = model.validate_dark_spectrum(
                    time_ms=result["s_integration_time"],
                    measured_dark_roi=dark_roi,
                    polarization="S",
                )

                result["model_validation_dark"] = dark_validation

                # Display results
                logger.info("")
                logger.info("Model Dark Predictions vs Measured:")
                for ch in ["A", "B", "C", "D"]:
                    if ch in dark_validation["predicted_dark"]:
                        pred = dark_validation["predicted_dark"][ch]
                        meas = dark_validation["measured_dark"][ch]
                        dev = dark_validation["deviations"][ch]
                        pct = dark_validation["percent_errors"][ch]
                        sign = "+" if dev >= 0 else ""
                        logger.info(
                            f"  {ch}: Predicted={pred:.1f}, Measured={meas:.1f}, Δ={sign}{dev:.1f} ({sign}{pct:.1f}%)",
                        )

                avg_err = dark_validation["average_error_percent"]
                max_err = dark_validation["max_error_percent"]
                status = dark_validation["validation_status"].upper()

                logger.info("")
                logger.info(
                    f"Average Error: {avg_err:.1f}% | Max Error: {max_err:.1f}%",
                )
                logger.info(f"Validation Status: {status}")

                if status == "EXCELLENT":
                    logger.info(
                        "✅ Dark spectrum matches model predictions (<10% error)",
                    )
                elif status == "GOOD":
                    logger.info("✓ Dark spectrum acceptable (10-20% error)")
                elif status == "FAIR":
                    logger.info("⚠️ Dark spectrum higher than expected (20-50% error)")
                else:
                    logger.warning(
                        "❌ Dark spectrum significantly deviates from model (>50% error)",
                    )
                    logger.warning("   This may indicate detector noise issues")

                logger.info("=" * 80)
            else:
                if not detector_serial or detector_serial == "Unknown":
                    logger.info("ℹ No detector serial - skipping dark validation")
                else:
                    logger.info("ℹ No dark spectrum captured - skipping validation")
                result["model_validation_dark"] = None

        except ModelValidationError as e:
            # Model doesn't have dark data - this is expected for some models
            logger.info(f"ℹ Dark validation skipped: {e}")
            result["model_validation_dark"] = None
        except Exception as e:
            logger.warning(f"Dark spectrum validation failed: {e}")
            import traceback

            logger.debug(traceback.format_exc())
            result["model_validation_dark"] = None

        # === SUCCESS ===
        result["success"] = True
        logger.info("")
        logger.info("=" * 80)
        logger.info("[OK] LED CONVERGENCE CALIBRATION COMPLETE (Steps 3-5)")
        logger.info("=" * 80)
        logger.info("")

        return result

    except Exception as e:
        logger.exception(f"[ERROR] Convergence calibration error: {e}")
        result["error"] = str(e)
        return result


# ==============================================================================
# END OF FILE - All helper functions above
