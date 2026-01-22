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

STEP 3: LED Brightness Measurement & 3-Stage LED Model Load
  - Check if 3-stage LED calibration model exists for detector
  - If missing: Automatically run OEM model training (~2 minutes)
  - Quick brightness measurement at LED=255 for all channels
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

        logger.info(f"Polarizer validated: {mode_upper}-mode position {target_pos}°")

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
    MAX_WAVELENGTH,
    MIN_WAVELENGTH,
    USE_ALTERNATIVE_CALIBRATION,
)

# =============================================================================
# CALIBRATION CONFIGURATION
# =============================================================================
# Use batch LED command in convergence & preflight for identical behavior
CONVERGENCE_USE_BATCH_COMMAND = (
    True  # ALWAYS use batch commands (more reliable, avoids LED-off race condition)
)

# Number of scans to use during calibration convergence (minimum 3)
# Live acquisition num_scans is calculated based on detector window during calibration
CALIBRATION_CONVERGENCE_SCANS = 3

# =============================================================================
# LEGACY CONSTANTS - UNUSED (convergence handled by led_convergence_algorithm.py)
# =============================================================================
# NOTE: These constants are no longer used. The actual LED convergence is performed
# by LEDconverge() in affilabs/utils/led_convergence_algorithm.py which has its own
# ConvergenceConfig class. These are kept for reference only.

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

# =============================================================================
# HARDWARE TIMING CONSTANTS (in seconds unless noted)
# =============================================================================
# LED Control Timing
LED_OFF_SETTLING_TIME_S = 0.2  # Time to wait after forcing LEDs off
LED_QUERY_SETTLING_TIME_S = 0.01  # Time before querying LED state
LED_RETRY_SETTLING_TIME_S = 0.05  # Time before retrying LED off
LED_BATCH_ENABLE_TIME_S = 0.1  # Time for firmware to process batch enable command

# Firmware Command Processing
FIRMWARE_COMMAND_PROCESSING_TIME_S = 0.01  # Standard command processing delay
FIRMWARE_EXTENDED_SETTLING_TIME_S = 0.05  # Extended settling for V1.0 firmware

# Integration Time Settling
INTEGRATION_TIME_SETTLING_MS = 10  # Time for integration time change to take effect (converted to seconds in code)

# Servo Positioning (used in servo calibration)
SERVO_POSITIONING_TIME_S = 0.3  # Time for servo to reach position
SERVO_EXTENDED_SETTLING_S = 0.5  # Extended settling for critical positions

# Hardware Stabilization
HARDWARE_STABILIZATION_TIME_S = 0.02  # General hardware stabilization delay
INTER_CHANNEL_DARK_TIME_S = 0.005  # Brief delay between channel reads

import contextlib

from affilabs.core.spectrum_preprocessor import SpectrumPreprocessor
from affilabs.core.transmission_processor import TransmissionProcessor
from affilabs.models.led_calibration_result import LEDCalibrationResult
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


# =============================================================================
# SERVO HELPER FUNCTIONS
# =============================================================================


def _get_servo_positions_from_config(device_config, detector_serial: str) -> dict:
    """Get servo S and P positions from device configuration.

    Args:
        device_config: DeviceConfiguration instance or dict with hardware.servo_s/p_position
        detector_serial: Detector serial number (unused, kept for compatibility)

    Returns:
        Dict with keys 's_position' and 'p_position' (PWM values 0-255)

    Raises:
        ValueError: If positions are not set in device_config
    """
    # Handle DeviceConfiguration object
    if hasattr(device_config, 'get_servo_positions'):
        positions = device_config.get_servo_positions()
        if positions:
            return {
                's_position': positions['s'],
                'p_position': positions['p'],
            }

    # Handle dict format
    if isinstance(device_config, dict):
        hardware = device_config.get('hardware', {})
        s_pos = hardware.get('servo_s_position')
        p_pos = hardware.get('servo_p_position')

        if s_pos is not None and p_pos is not None:
            return {
                's_position': s_pos,
                'p_position': p_pos,
            }

    # Positions not found
    msg = "Servo S/P positions not set in device_config. Run polarizer calibration first."
    raise ValueError(msg)


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
            time.sleep(SERVO_POSITIONING_TIME_S)
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
        use_batch_command: If True, use batch LED command (faster, more deterministic)

    Returns:
        Raw spectrum as numpy array (full detector range), or None if error

    Pattern:
        1. Set integration time (if specified)
        2. Set LED intensity (individual or batch)
        3. Wait for LED stabilization (new timing system)
        4. Read spectrum (with averaging if num_scans > 1)
        5. Turn off LED
        6. Wait for afterglow decay (new timing system)

    """
    try:
        # Step 1: Set integration time if specified
        if integration_time_ms is not None:
            usb.set_integration(integration_time_ms)
            time.sleep(INTEGRATION_TIME_SETTLING_MS / 1000.0)  # 10ms settling time

        # Step 2: Turn on LED channel and set intensity
        if use_batch_command:
            # Optimized batch command using direct serial (faster than set_batch_intensities)
            # Set brightness for target channel, turn on with direct serial command
            try:
                # Access the serial port safely through the controller wrapper
                if hasattr(ctrl, '_ctrl'):
                    serial_port = ctrl._ctrl._ser
                else:
                    serial_port = ctrl._ser

                # Set brightness command
                cmd = f"b{channel}{int(led_intensity):03d}\n"
                serial_port.write(cmd.encode())
                time.sleep(0.005)

                # Turn on the channel
                cmd = f"l{channel}\n"
                serial_port.write(cmd.encode())
                time.sleep(0.005)
            except AttributeError:
                # Fallback to slower batch method if direct access fails
                logger.warning("Direct serial access failed, using batch command fallback")
                led_values = {"a": 0, "b": 0, "c": 0, "d": 0}
                led_values[channel] = led_intensity
                ctrl.set_batch_intensities(**led_values)
        else:
            # Individual command (traditional calibration)
            # CRITICAL: Must call turn_on_channel BEFORE set_intensity for V2.0 firmware
            ctrl.turn_on_channel(channel)
            ctrl.set_intensity(ch=channel, raw_val=led_intensity)

        # Start timing for LED enforcement (keep LED on for full LED_ON_TIME_MS duration)
        led_on_start = time.perf_counter()

        # Step 3: LED stabilization wait
        import settings as root_settings
        detector_wait_ms = getattr(root_settings, "DETECTOR_WAIT_MS", 45.0)
        time.sleep(detector_wait_ms / 1000.0)

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
                time.sleep(FIRMWARE_COMMAND_PROCESSING_TIME_S)

            if len(spectra) == 0:
                return None

            spectrum = np.mean(spectra, axis=0)

        # Step 5: Enforce LED on time (keep LED on for full LED_ON_TIME_MS duration)
        # This prevents LED from turning off too early and ensures consistent timing
        elapsed_since_led_on = (time.perf_counter() - led_on_start) * 1000  # ms
        led_on_time_ms = getattr(root_settings, "LED_ON_TIME_MS", 225.0)
        remaining_time_ms = max(0, led_on_time_ms - elapsed_since_led_on)
        if remaining_time_ms > 0:
            time.sleep(remaining_time_ms / 1000.0)

        # Step 6: Turn off LED (only needed for non-batch mode or final cleanup)
        # In batch mode, the next acquisition automatically turns off previous LEDs
        if not use_batch_command:
            # For V2.0: set intensity to 0 disables the channel
            ctrl.set_intensity(ch=channel, raw_val=0)
            # Afterglow decay (LED_OFF_PERIOD_MS)
            led_off_period_ms = getattr(root_settings, "LED_OFF_PERIOD_MS", 5.0)
            time.sleep(led_off_period_ms / 1000.0)

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
    tolerance_pct: float = 0.06,
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
        pct = (sig_top50 / detector_max_counts * 100.0) if detector_max_counts else 0.0

        top50_signals[ch] = sig_top50
        top50_percentages[ch] = pct

    return top50_signals, top50_percentages


# =============================================================================
# CALIBRATION HELPER FUNCTIONS (Step Extraction)
# =============================================================================


def _step1_prepare_led_system(
    ctrl,
    start_at_step: int,
    progress_callback=None,
) -> None:
    """Step 1: LED System Preparation.

    Ensures all LEDs are turned off before calibration begins and enables
    batch LED commands if configured. Uses firmware query (V1.1+) or
    timing-based fallback (V1.0).

    Note: Hardware connection validation is performed by calibration_service
    before this function is called, so we don't duplicate those checks.

    Args:
        ctrl: Controller instance (already validated)
        start_at_step: Step number to start at (skip if > 1)
        progress_callback: Optional progress callback

    Raises:
        RuntimeError: If LEDs fail to turn off

    """
    if start_at_step <= 1:
        logger.info("=" * 80)
        logger.info("STEP 1: LED System Preparation")
        logger.info("=" * 80)

        if progress_callback:
            progress_callback(
                f"Step 1 of {CALIBRATION_NUM_STEPS}: Preparing LEDs",
                0,
            )

    # CRITICAL: Force all LEDs OFF and VERIFY
    logger.info("Forcing all LEDs OFF...")
    ctrl.turn_off_channels()
    time.sleep(LED_OFF_SETTLING_TIME_S)

    # VERIFY LEDs are off using V1.1 firmware query (CRITICAL!)
    has_led_query = hasattr(ctrl, "get_all_led_intensities")

    if has_led_query:
        time.sleep(LED_QUERY_SETTLING_TIME_S)  # Brief settling time

        # Try LED query once
        try:
            led_state = ctrl.get_all_led_intensities()
        except Exception as query_error:
            logger.debug(f"LED query exception: {query_error}")
            led_state = None

        if led_state is None:
            logger.debug("LED query not supported - using timing-based verification")
            has_led_query = False
        else:
            # Check if all LEDs are off (intensity <= 1)
            channels_to_check = {ch: val for ch, val in led_state.items() if ch != "d"}
            all_off = all(intensity <= 1 for intensity in channels_to_check.values())

            if all_off:
                logger.info(f"[OK] All LEDs confirmed OFF: {channels_to_check}")
            else:
                logger.warning(f"LEDs still on: {channels_to_check} - retrying turn-off")
                ctrl.turn_off_channels()
                time.sleep(0.05)

                # Check one more time
                led_state2 = ctrl.get_all_led_intensities()
                if led_state2:
                    channels_to_check2 = {
                        ch: val for ch, val in led_state2.items() if ch != "d"
                    }
                    if all(intensity <= 1 for intensity in channels_to_check2.values()):
                        logger.info(
                            f"[OK] All LEDs confirmed OFF after retry: {channels_to_check2}",
                        )
                    else:
                        logger.error(
                            f"[ERROR] Failed to turn off LEDs - last state: {channels_to_check2}",
                        )
                        msg = "Cannot proceed - LEDs failed to turn off"
                        raise RuntimeError(msg)
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

        logger.info("[OK] Step 1 complete: Hardware validated, LEDs confirmed OFF\n")
    else:
        logger.info("[OK] Step 1 complete: Hardware validated, LEDs confirmed OFF\n")

    # OPTIMIZATION: Pre-enable all LED channels for batch command operation
    # This only needs to be sent ONCE at calibration start, not on every acquisition
    if CONVERGENCE_USE_BATCH_COMMAND:
        logger.info("[BATCH] Enabling all LED channels for batch operation...")
        ctrl._ser.write(b"lm:A,B,C,D\n")
        time.sleep(LED_BATCH_ENABLE_TIME_S)  # Wait for firmware to process enable command
        logger.info("[OK] LED channels enabled for batch commands\n")


def _step2_wavelength_calibration(usb, progress_callback=None) -> dict:
    """Step 2: Wavelength Range Calibration.

    Reads wavelength data from detector EEPROM and calculates SPR spectral filter
    range for calibration.

    Args:
        usb: Spectrometer instance
        progress_callback: Optional progress callback

    Returns:
        Dict containing:
            - wave_data: Filtered wavelength array (numpy array)
            - wavelengths: Copy of wave_data
            - wave_min_index: Start index of SPR filter
            - wave_max_index: End index of SPR filter
            - full_wavelengths: Full detector wavelength range
            - detector_max_counts: Detector max counts
            - detector_saturation_threshold: Saturation threshold
            - detector_type_str: Human-readable detector type

    Raises:
        RuntimeError: If wavelength data cannot be read

    """
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
        msg = "Failed to read wavelength data from detector"
        raise RuntimeError(msg)

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

    # Calculate SPR spectral filter indices
    wave_min_index = np.argmin(np.abs(wave_data - MIN_WAVELENGTH))
    wave_max_index = np.argmin(np.abs(wave_data - MAX_WAVELENGTH))

    logger.info(f"[OK] SPR filter: {MIN_WAVELENGTH}-{MAX_WAVELENGTH}nm")
    logger.info(
        f"   Actual range: {wave_data[wave_min_index]:.1f}-{wave_data[wave_max_index]:.1f}nm",
    )
    logger.info(f"   Pixel indices: [{wave_min_index}:{wave_max_index}]")
    logger.info(f"   Filter width: {wave_max_index - wave_min_index} pixels\n")

    # Get detector parameters
    from affilabs.utils.detector_params import get_detector_params

    detector_params = get_detector_params("P4SPR")  # All use USB4000 params

    return {
        "wave_data": wave_data[wave_min_index:wave_max_index],
        "wavelengths": wave_data[wave_min_index:wave_max_index],
        "wave_min_index": wave_min_index,
        "wave_max_index": wave_max_index,
        "full_wavelengths": wave_data,
        "detector_max_counts": detector_params.max_counts,
        "detector_saturation_threshold": detector_params.saturation_threshold,
        "detector_type_str": detector_type_str,
    }


# =============================================================================
# STEP 6 HELPER FUNCTIONS (QC Results Preparation)
# =============================================================================


def _step6a_verify_data_availability(result, ch_list) -> None:
    """Verify raw data availability from convergence output.

    Args:
        result: CalibrationResult object containing convergence output
        ch_list: List of channel names to verify

    Returns:
        None (modifies result in-place if needed)

    Raises:
        RuntimeError: If required data is missing from convergence output
    """
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
    logger.info(
        "   [OK] S-mode dark references: 4 channels from convergence",
    )
    logger.info(
        "   [OK] P-mode dark references: 4 channels from convergence",
    )
    logger.info(
        f"   [OK] S-mode integration time: {result.s_integration_time:.1f}ms",
    )
    logger.info(
        f"   [OK] P-mode integration time: {result.p_integration_time:.1f}ms",
    )


def _step6b_process_polarization_with_swap_check(result, ch_list):
    """Process polarization data and detect/correct polarizer inversion.

    Args:
        result: CalibrationResult object containing raw polarization data
        ch_list: List of channel names to process

    Returns:
        tuple: (s_pol_ref dict, p_pol_ref dict, s_raw_corrected dict, p_raw_corrected dict)
            - s_pol_ref: Processed S-polarization references
            - p_pol_ref: Processed P-polarization references
            - s_raw_corrected: Raw S data (possibly swapped if inversion detected)
            - p_raw_corrected: Raw P data (possibly swapped if inversion detected)

    Notes:
        - Calculates S vs P mean/median statistics
        - Detects if P > S across all channels (polarizer inverted)
        - If inverted: swaps raw data references, logs warning, marks in QC results
        - Processes both S and P polarization data via SpectrumPreprocessor
    """
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
            logger.warning(
                "   Note: Servo EEPROM positions are NOT changed",
            )
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

    logger.info("\n[OK] S-pol and P-pol references processed")
    logger.info("   Ready for QC display")

    return s_pol_ref, p_pol_ref, s_raw_corrected, p_raw_corrected


def _step6c_calculate_transmission(result, ch_list) -> dict:
    """Calculate transmission spectrum using TransmissionProcessor.

    Args:
        result: CalibrationResult object containing polarization references
        ch_list: List of channel names to process

    Returns:
        dict: Transmission spectra for each channel

    Raises:
        Exception: If transmission calculation fails
    """
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
            p_pol_clean=result.p_pol_ref[ch],
            s_pol_ref=result.s_pol_ref[ch],
            led_intensity_s=result.ref_intensity[ch],
            led_intensity_p=result.p_mode_intensity[ch],
            wavelengths=result.wave_data,
            apply_sg_filter=True,
            baseline_method="none",
            baseline_percentile=95.0,
            verbose=True,
        )

        transmission_spectra[ch] = transmission_ch

    logger.info("\n" + "=" * 80)
    logger.info("[OK] Transmission spectra calculated")
    logger.info("   Ready for QC display and peak tracking pipeline")
    logger.info("=" * 80)

    return transmission_spectra


def _step6e_finalize_and_save(
    result,
    ch_list,
    progress_callback=None,
) -> None:
    """Finalize calibration and log summary.

    Args:
        result: CalibrationResult object to finalize
        ch_list: List of channel names
        progress_callback: Optional callback for progress updates

    Returns:
        None (modifies result in-place)

    Raises:
        None
    """
    # Finalization and summary
    result.leds_calibrated = result.p_mode_intensity
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
    # Import timing parameters from settings (single source of truth)
    import settings as root_settings
    LED_ON_TIME_MS = root_settings.LED_ON_TIME_MS
    DETECTOR_WAIT_MS = root_settings.DETECTOR_WAIT_MS
    NUM_SCANS = root_settings.NUM_SCANS
    SAFETY_BUFFER_MS = root_settings.SAFETY_BUFFER_MS
    P_MODE_INTEGRATION_CAP_MS = DETECTOR_WAIT_MS  # Per-scan cap

    if result.p_integration_time > P_MODE_INTEGRATION_CAP_MS:
        logger.warning(
            f"⚠️  P-mode integration time ({result.p_integration_time:.1f}ms) exceeds budget cap ({P_MODE_INTEGRATION_CAP_MS:.1f}ms)",
        )
        logger.warning(
            "   This may result in below-target signal intensity but is allowed to pass QC",
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


def _step6d_comprehensive_qc_validation(
    result,
    ch_list,
    device_type,
    s_pol_ref,
    p_raw_corrected,
    s_raw_corrected,
    transmission_spectra,
    convergence_result,
):
    """Step 6D: Comprehensive QC Validation.

    Validates transmission quality for each channel:
    - SPR dip analysis
    - FWHM check
    - Polarizer orientation check
    - Saturation check
    - SNR calculation
    - Model validation from convergence_result

    Args:
        result: LEDCalibrationResult object
        ch_list: List of channels to validate
        device_type: Device type string
        s_pol_ref: S-pol reference data dict
        p_raw_corrected: P-mode corrected raw data dict
        s_raw_corrected: S-mode corrected raw data dict
        transmission_spectra: Transmission spectra dict
        convergence_result: Convergence result from Step 4/5

    Returns:
        tuple: (qc_results dict, ch_error_list)
    """
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

        # Debug: Show why channel passed or failed
        logger.info(f"\n{'=' * 40}")
        logger.info("📋 PASS/FAIL Criteria:")
        logger.info(f"   Dip detected: {qc['dip_detected']} (required: True)")
        logger.info(f"   FWHM pass: {fwhm_pass} (required: True, FWHM={qc['fwhm']:.1f if qc['fwhm'] else 0}nm < 100nm)")
        logger.info(f"   Orientation: {qc['orientation_correct']} (required: not False)")
        logger.info(f"   S saturated: {qc['s_saturated']} (required: False)")
        logger.info(f"   P saturated: {qc['p_saturated']} (required: False)")
        logger.info(f"\n{'=' * 40}")
        logger.info(
            f"Channel {ch.upper()}: {'[OK] PASS ✓' if channel_pass else '[ERROR] FAIL ✗'}",
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
        result.qc_results["model_validation_s"] = convergence_result[
            "model_validation_s"
        ]
    if convergence_result.get("model_validation_p"):
        result.qc_results["model_validation_p"] = convergence_result[
            "model_validation_p"
        ]

    ch_error_list = [
        ch for ch, qc in qc_results.items() if not qc["overall_pass"]
    ]

    return qc_results, ch_error_list


def _initialize_calibration_result():
    """Initialize and validate calibration result object.

    Creates LEDCalibrationResult object and validates schema.

    Returns:
        LEDCalibrationResult: Initialized and validated result object
    """
    result = LEDCalibrationResult()

    # CRITICAL FIX #1: Validate schema immediately after creation
    _validate_calibration_result_schema(result)

    return result


def _validate_calibration_prerequisites(device_config, detector_serial, result):
    """Validate calibration prerequisites (fail-fast).

    Loads OEM polarizer positions and validates bilinear model exists.
    This enables fail-fast behavior (<1 second) instead of failing at Step 4.

    Args:
        device_config: DeviceConfiguration instance or dict
        detector_serial: Detector serial number
        result: LEDCalibrationResult object to populate

    Raises:
        ValueError: If device_config is missing
        RuntimeError: If OEM positions not found or model validation fails
    """
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
        if hasattr(device_config, "config_file_path"):
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



# ==============================================================================
# END OF FILE - All helper functions above
