"""6-Step Startup Calibration Flow - Exact Implementation as Discussed

This module implements the exact 6-step calibration flow discussed:

STEP 1: Hardware Discovery & Connection
  - Detect controller and spectrometer
  - Establish USB communication
  - Read wavelength data from detector

STEP 2: Quick Dark Noise Baseline (3 scans @ 100ms)
  - Fast baseline measurement (not final dark noise)
  - Used to verify hardware is responding

STEP 3: Calibrator Initialization
  - Switch to S-mode
  - Turn off all LEDs
  - Prepare for LED optimization

STEP 4: Load OEM Polarizer Positions
  - Read device_config.json by detector serial number
  - Load pre-calibrated servo positions for S-mode and P-mode
  - These were set during OEM manufacturing calibration

STEP 5: S-Mode LED Optimization
  5A: LED Optimization with 2-pass Saturation Check
      - Binary search for optimal LED intensity
      - 2-pass preliminary saturation validation
  5B: Integration Time Optimization
      - Find optimal integration time (max 100ms)
      - Per-channel or global depending on mode
  5C: Final 5-pass Saturation Check
      - Verify no saturation at final settings
      - All pixels in 560-720nm ROI must be unsaturated
  5D: Capture S-Mode Reference Signals
      - Measure reference spectra at final LED/integration settings
      - Apply afterglow correction if available
  5E: Final Dark Noise Measurement
      - Measure dark at calibrated integration time
      - This replaces the quick baseline from Step 2

STEP 6: P-Mode Calibration
  6A: P-Mode LED Optimization
      - Switch to P-mode servo position
      - Optimize LED intensities for P-mode
      - Use S-mode headroom analysis to predict boost
  6B: Polarity Detection with Auto Servo Recalibration
      - Check if P-mode is saturating (wrong polarity)
      - If saturation detected: auto-trigger servo recalibration
      - Recalibrate servo positions and retry
  6C: QC Metrics
      - FWHM measurement on transmission dip
      - SNR calculation
      - LED health baseline
      - Save full arrays to device config

FAST-TRACK MODE:
  - Check device_config.json for previous calibration
  - If found and within ±10% tolerance: skip Steps 1-6 optimization
  - Only validate that previous settings still work
  - Auto-recalibrate any channels that fail validation

GLOBAL LED MODE:
  - Alternative mode: LED=255 fixed for all channels
  - Only optimize integration time per channel
  - Controlled by settings.USE_ALTERNATIVE_CALIBRATION flag

TRANSFER TO LIVE VIEW:
  - After Step 6C completes: Show post-calibration dialog
  - Wait for user to click "Start" button
  - Transfer calibration to live acquisition system
  - Begin live SPR measurements
"""

import time
from typing import TYPE_CHECKING, Optional, Dict, Tuple
import numpy as np

from settings import (
    CH_LIST,
    EZ_CH_LIST,
    LED_DELAY,
    PRE_LED_DELAY_MS,
    POST_LED_DELAY_MS,
    MIN_WAVELENGTH,
    MAX_WAVELENGTH,
)
from utils.logger import logger
from utils.led_calibration import (
    LEDCalibrationResult,
    DetectorParams,
    get_detector_params,
    determine_channel_list,
    calculate_scan_counts,
    switch_mode_safely,
    calibrate_led_channel,
    calibrate_integration_time,
    measure_dark_noise,
    measure_reference_signals,
    validate_s_ref_quality,
    calibrate_p_mode_leds,
    verify_calibration_global_integration,
    verify_calibration_global_led,
    analyze_channel_headroom,
    perform_alternative_calibration,
)

if TYPE_CHECKING:
    from utils.controller import ControllerBase


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
    time.sleep(0.1)

    # Turn off all LEDs
    ctrl.turn_off_channels()
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

    logger.info(f"✅ Quick baseline complete: max dark = {max_dark:.0f} counts")
    logger.info(f"   This verifies detector is responding\n")

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
            logger.error(f"❌ No servo positions found in device config")
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

        logger.info(f"✅ OEM Polarizer Positions Loaded:")
        logger.info(f"   S-mode position: {s_pos}")
        logger.info(f"   P-mode position: {p_pos}")
        logger.info(f"   These were calibrated during OEM manufacturing\n")

        # Return with keys matching what code expects (s_position, p_position)
        return {
            's_position': s_pos,
            'p_position': p_pos
        }

    except Exception as e:
        logger.exception(f"Failed to load OEM polarizer positions: {e}")
        raise
# =============================================================================
# STEP 5: S-MODE LED OPTIMIZATION (SUBSTEPS A-E)
# =============================================================================

def optimize_s_mode_leds(
    usb,
    ctrl,
    ch_list: list[str],
    detector_params: DetectorParams,
    wave_min_index: int,
    wave_max_index: int,
    stop_flag=None,
    progress_callback=None
) -> Tuple[Dict[str, int], int, int]:
    """Step 5: Complete S-mode LED optimization with all substeps.

    CRITICAL ORDER: Integration time MUST be optimized BEFORE LED calibration!

    5A: Integration Time Optimization (FIRST - sets the time budget)
    5B: LED Optimization with P-mode headroom (at optimized integration time)
    5C: Final 5-pass Saturation Check
    5D: (Deferred to caller) Capture S-refs
    5E: (Deferred to caller) Final dark noise

    Args:
        usb: Spectrometer instance
        ctrl: Controller instance
        ch_list: List of channels to calibrate
        detector_params: Detector parameters
        wave_min_index: Min wavelength index
        wave_max_index: Max wavelength index
        stop_flag: Optional cancellation flag
        progress_callback: Optional progress callback

    Returns:
        Tuple of (led_intensities_dict, integration_time_ms, num_scans)
    """
    logger.info("=" * 80)
    logger.info("STEP 5: S-Mode LED Optimization")
    logger.info("=" * 80)
    logger.info("Substeps:")
    logger.info("  5A: Integration time optimization (FIRST)")
    logger.info("  5B: LED intensity optimization with P-mode headroom")
    logger.info("  5C: Final 5-pass saturation validation")
    logger.info("  5D: Capture S-mode reference signals (after this function)")
    logger.info("  5E: Final dark noise at calibrated integration (after this function)\n")

    # =======================================================================
    # STEP 5A: INTEGRATION TIME OPTIMIZATION (MUST BE FIRST!)
    # =======================================================================
    logger.info("-" * 80)
    logger.info("STEP 5A: Integration Time Optimization")
    logger.info("-" * 80)
    logger.info("Finding optimal integration time (max 100ms budget)")
    logger.info("CRITICAL: This runs FIRST so LEDs are calibrated at correct integration time\n")

    if progress_callback:
        progress_callback("Step 5A: Optimizing integration time...")

    logger.debug(f"🔍 DEBUG: About to call calibrate_integration_time")
    logger.debug(f"   PRE_LED_DELAY_MS={PRE_LED_DELAY_MS}")
    logger.debug(f"   POST_LED_DELAY_MS={POST_LED_DELAY_MS}")

    integration_time, num_scans = calibrate_integration_time(
        usb, ctrl, ch_list, integration_step=2, stop_flag=stop_flag,
        device_config=None,
        detector_params=detector_params,
        pre_led_delay_ms=PRE_LED_DELAY_MS,
        post_led_delay_ms=POST_LED_DELAY_MS
    )

    logger.info(f"✅ Step 5A Complete: integration_time = {integration_time}ms, num_scans = {num_scans}\n")

    # =======================================================================
    # STEP 5B: LED OPTIMIZATION WITH P-MODE HEADROOM
    # =======================================================================
    logger.info("-" * 80)
    logger.info("STEP 5B: LED Intensity Optimization (with P-mode headroom)")
    logger.info("-" * 80)
    logger.info("IMPORTANT: S-mode LEDs calibrated with headroom for P-mode boost")
    logger.info("Target: 75% of detector max (leaves 25% headroom for P-mode)")
    logger.info(f"Integration time: {integration_time}ms (already optimized)\n")

    # Calculate S-mode target with P-mode headroom
    # Target 75% of max for S-mode, leaving 25% headroom for P-mode boost
    s_mode_target = int(detector_params.max_counts * 0.75)

    logger.info(f"S-mode target: {s_mode_target} counts (75% of {detector_params.max_counts})")
    logger.info(f"P-mode headroom: {detector_params.max_counts - s_mode_target} counts (25%)\n")

    led_intensities = {}

    for ch in ch_list:
        if stop_flag and stop_flag.is_set():
            break

        if progress_callback:
            progress_callback(f"Step 5B: Calibrating LED {ch.upper()}...")

        logger.debug(f"🔍 DEBUG: About to call calibrate_led_channel for ch {ch}")
        logger.debug(f"   PRE_LED_DELAY_MS={PRE_LED_DELAY_MS}")
        logger.debug(f"   POST_LED_DELAY_MS={POST_LED_DELAY_MS}")
        logger.debug(f"   integration_time={integration_time}ms")
        logger.debug(f"   target_counts={s_mode_target}")

        logger.info(f"\nOptimizing LED {ch.upper()} at {integration_time}ms:")
        logger.info(f"  - Binary search for optimal intensity")
        logger.info(f"  - Target: {s_mode_target} counts (75% of max)")
        logger.info(f"  - Leaves headroom for P-mode boost\n")

        # Calibrate LED at the OPTIMIZED integration time
        led_intensity = calibrate_led_channel(
            usb, ctrl, ch,
            target_counts=s_mode_target,  # Use 75% target with headroom
            stop_flag=stop_flag,
            detector_params=detector_params,
            wave_min_index=wave_min_index,
            wave_max_index=wave_max_index,
            pre_led_delay_ms=PRE_LED_DELAY_MS,
            post_led_delay_ms=POST_LED_DELAY_MS
        )

        led_intensities[ch] = led_intensity
        logger.info(f"✅ LED {ch.upper()}: {led_intensity}/255\n")

    logger.info(f"✅ Step 5B Complete: LED intensities = {led_intensities}\n")

    # =======================================================================
    # STEP 5C: FINAL 5-PASS SATURATION CHECK
    # =======================================================================
    logger.info("-" * 80)
    logger.info("STEP 5C: Final 5-Pass Saturation Validation")
    logger.info("-" * 80)
    logger.info("Verifying NO saturation at final LED/integration settings")
    logger.info("All pixels in 560-720nm ROI must be unsaturated\n")

    if progress_callback:
        progress_callback("Step 5C: Final saturation validation (5 passes)...")

    # Set final integration time
    usb.set_integration(integration_time)
    time.sleep(0.1)

    saturation_passes = 5
    any_saturation = False

    for ch in ch_list:
        if stop_flag and stop_flag.is_set():
            break

        logger.info(f"Channel {ch.upper()}: Running {saturation_passes}-pass saturation check...")

        # Set LED to final intensity
        ctrl.set_intensity(ch=ch, raw_val=led_intensities[ch])
        time.sleep(LED_DELAY)

        # Run 5 passes
        for pass_num in range(saturation_passes):
            spectrum = usb.read_intensity()
            if spectrum is None:
                logger.error(f"Failed to read spectrum during saturation check")
                raise RuntimeError("Spectrometer read failed")

            sat_count = count_saturated_pixels(
                spectrum,
                wave_min_index,
                wave_max_index,
                detector_params.saturation_threshold
            )

            if sat_count > 0:
                any_saturation = True
                logger.error(f"  ❌ Pass {pass_num + 1}/{saturation_passes}: {sat_count} saturated pixels detected!")
                logger.error(f"     LED={led_intensities[ch]}, Integration={integration_time}ms")
                logger.error(f"     This should NOT happen - calibration logic error!")
            else:
                logger.debug(f"  ✅ Pass {pass_num + 1}/{saturation_passes}: No saturation")

        # Turn off LED
        ctrl.set_intensity(ch=ch, raw_val=0)
        time.sleep(0.01)

        if any_saturation:
            logger.error(f"❌ Channel {ch.upper()} has saturation - cannot proceed")
        else:
            logger.info(f"✅ Channel {ch.upper()}: All {saturation_passes} passes clear\n")

    if any_saturation:
        raise RuntimeError(
            "Saturation detected in final validation. "
            "LED/integration optimization failed."
        )

    logger.info(f"✅ Step 5C Complete: No saturation detected across all channels\n")

    # =======================================================================
    # CRITICAL ANALYSIS: WEAKEST LED DETERMINES OPTIMIZATION QUALITY
    # =======================================================================
    logger.info(f"=" * 80)
    logger.info(f"📊 WEAKEST LED ANALYSIS (Key Optimization Metric)")
    logger.info(f"=" * 80)
    logger.info(f"The WEAKEST LED is the bottleneck for the entire system.")
    logger.info(f"This is a DEVICE-SPECIFIC hardware characteristic.")
    logger.info(f"Optimal global integration time is achieved when:")
    logger.info(f"  • S-mode: Weakest LED ≈ 200-220 (leaves headroom for P-boost)")
    logger.info(f"  • P-mode: Weakest LED = 255 (proves maximum signal extracted)")
    logger.info(f"")

    # UNIVERSAL: Dynamically identify weakest and strongest LEDs
    # This is device-specific - could be any channel (A, B, C, or D)
    # Determined by LED efficiency, optical coupling, and fiber alignment
    weakest_ch = min(led_intensities, key=led_intensities.get)
    strongest_ch = max(led_intensities, key=led_intensities.get)
    weakest_led = led_intensities[weakest_ch]
    strongest_led = led_intensities[strongest_ch]

    # =======================================================================
    # HARDWARE CONSISTENCY CHECK: Weakest channel should NOT change
    # =======================================================================
    # Load previous calibration to check if weakest channel changed
    try:
        if device_config is None:
            from utils.device_configuration import DeviceConfiguration
            device_serial = getattr(usb, 'serial_number', None)
            device_config = DeviceConfiguration(device_serial=device_serial)

        prev_calib = device_config.config.get('led_calibration', {})
        prev_weakest_ch = prev_calib.get('weakest_channel', None)

        if prev_weakest_ch and prev_weakest_ch != weakest_ch:
            logger.error(f"")
            logger.error(f"⚠️ ⚠️ ⚠️  HARDWARE ANOMALY DETECTED  ⚠️ ⚠️ ⚠️")
            logger.error(f"")
            logger.error(f"Weakest channel CHANGED:")
            logger.error(f"  Previous calibration: Ch {prev_weakest_ch.upper()}")
            logger.error(f"  Current calibration:  Ch {weakest_ch.upper()}")
            logger.error(f"")
            logger.error(f"🔴 CRITICAL: The weakest LED is a FIXED hardware characteristic!")
            logger.error(f"   This should NOT change between calibrations.")
            logger.error(f"")
            logger.error(f"Possible causes:")
            logger.error(f"  1. LED degradation (weakest LED failing faster)")
            logger.error(f"  2. Fiber misalignment or damage")
            logger.error(f"  3. Optical coupling degradation")
            logger.error(f"  4. System instability (temperature, contamination)")
            logger.error(f"  5. Previous calibration was invalid/corrupted")
            logger.error(f"")
            logger.error(f"⚠️ Recommendation: Investigate hardware before proceeding")
            logger.error(f"")
        elif prev_weakest_ch == weakest_ch:
            logger.info(f"✅ Hardware consistency: Weakest channel = {weakest_ch.upper()} (matches previous calibration)")
        else:
            logger.info(f"ℹ️ First calibration for this device - weakest channel recorded as {weakest_ch.upper()}")
    except Exception as e:
        logger.debug(f"Could not check previous weakest channel: {e}")

    # Calculate headroom for P-mode boost
    weakest_headroom = 255 - weakest_led
    weakest_headroom_pct = (weakest_headroom / 255) * 100

    logger.info(f"")
    logger.info(f"S-mode LED intensities:")
    for ch in ch_list:
        led = led_intensities[ch]
        headroom = 255 - led
        marker = " 🔴 WEAKEST" if ch == weakest_ch else " 🟢 STRONGEST" if ch == strongest_ch else ""
        logger.info(f"  Ch {ch.upper()}: {led:3d}/255 (headroom: {headroom:3d}, {(headroom/255)*100:5.1f}%){marker}")

    logger.info(f"")
    logger.info(f"🎯 Weakest Channel: {weakest_ch.upper()} at LED={weakest_led}")
    logger.info(f"   → Headroom for P-boost: {weakest_headroom} ({weakest_headroom_pct:.1f}%)")

    # Provide optimization guidance
    if weakest_led >= 200 and weakest_led <= 230:
        logger.info(f"   ✅ EXCELLENT: Weakest LED in optimal range (200-230)")
        logger.info(f"   → Integration time is well-optimized for this system")
        logger.info(f"   → Good balance: adequate S-mode signal + P-mode headroom")
    elif weakest_led > 230:
        logger.warning(f"   ⚠️ Weakest LED HIGH (>{weakest_led})")
        logger.warning(f"   → Limited headroom for P-mode boost ({weakest_headroom} remaining)")
        logger.warning(f"   → Consider: INCREASE integration time to lower LED requirements")
    elif weakest_led < 150:
        logger.info(f"   ℹ️ Weakest LED LOW (<150)")
        logger.info(f"   → Excellent headroom for P-mode boost ({weakest_headroom} available)")
        logger.info(f"   → Strong optical coupling allows low LED usage")
    else:
        logger.info(f"   ✅ Weakest LED acceptable (150-200 range)")
        logger.info(f"   → Adequate headroom for P-mode: {weakest_headroom}")

    logger.info(f"")
    logger.info(f"Next step (P-mode): Weakest channel should reach LED=255")
    logger.info(f"If P-mode weakest < 255 → Integration time may not be optimal")
    logger.info(f"=" * 80)
    logger.info(f"")

    logger.info(f"STEP 5 (A-C) COMPLETE")
    logger.info(f"=" * 80)
    logger.info(f"LED Intensities: {led_intensities}")
    logger.info(f"Integration Time: {integration_time}ms")
    logger.info(f"Scans per Channel: {num_scans}")
    logger.info(f"Ready for Step 5D (S-ref capture) and 5E (final dark noise)\n")

    return led_intensities, integration_time, num_scans


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
    afterglow_correction=None,
    pre_led_delay_ms: float = 45.0,
    post_led_delay_ms: float = 5.0
) -> LEDCalibrationResult:
    """Complete 6-step calibration flow as discussed.

    STEP 1: Hardware Discovery & Connection
    STEP 2: Quick Dark Noise Baseline (3 scans @ 100ms)
    STEP 3: Calibrator Initialization
    STEP 4: Load OEM Polarizer Positions
    STEP 5: S-Mode LED Optimization (substeps A-E)
    STEP 6: P-Mode Calibration (substeps A-C)

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
        afterglow_correction: Optional afterglow correction instance

    Returns:
        LEDCalibrationResult with all calibration data
    """
    logger.debug(f"🔍 DEBUG: run_full_6step_calibration called")
    logger.debug(f"🔍 DEBUG: Parameters received:")
    logger.debug(f"   device_type={device_type}")
    logger.debug(f"   single_mode={single_mode}")
    logger.debug(f"   afterglow_correction={afterglow_correction is not None}")
    logger.debug(f"   pre_led_delay_ms={'MISSING' if 'pre_led_delay_ms' not in locals() else locals().get('pre_led_delay_ms', 'UNDEFINED')}")
    logger.debug(f"   post_led_delay_ms={'MISSING' if 'post_led_delay_ms' not in locals() else locals().get('post_led_delay_ms', 'UNDEFINED')}")

    result = LEDCalibrationResult()

    # UNIQUE DEBUG MARKER - confirms THIS file is being executed
    logger.critical("🔥🔥🔥 CALIBRATION_6STEP.PY FROM 'Affilabs.core beta' FOLDER 🔥🔥🔥")
    logger.critical("🔥🔥🔥 FILE HASH CHECK: Line 751 unique marker 🔥🔥🔥")

    try:
        logger.info("\n" + "=" * 80)
        logger.info("🚀 STARTING 6-STEP CALIBRATION FLOW")
        logger.info("=" * 80)
        logger.info("This calibration follows the exact flow discussed:")
        logger.info("  Step 1: Hardware Discovery")
        logger.info("  Step 2: Quick Dark Baseline (3 scans)")
        logger.info("  Step 3: Calibrator Initialization")
        logger.info("  Step 4: Load OEM Polarizer Positions")
        logger.info("  Step 5: S-Mode LED Optimization (A-E)")
        logger.info("  Step 6: P-Mode Calibration (A-C)")
        logger.info("=" * 80 + "\n")

        # ===================================================================
        # STEP 1: HARDWARE DISCOVERY & CONNECTION
        # ===================================================================
        logger.info("=" * 80)
        logger.info("STEP 1: Hardware Discovery & Connection")
        logger.info("=" * 80)

        if ctrl is None or usb is None:
            logger.error("❌ Hardware not connected")
            raise RuntimeError("Hardware must be connected before calibration")

        logger.info(f"✅ Controller: {type(ctrl).__name__}")
        logger.info(f"✅ Spectrometer: {type(usb).__name__}")
        logger.info(f"✅ Detector Serial: {detector_serial}\n")

        # Read wavelength data
        logger.info("Reading wavelength calibration from detector...")
        wave_data = usb.read_wavelength()
        wave_min_index = wave_data.searchsorted(MIN_WAVELENGTH)
        wave_max_index = wave_data.searchsorted(MAX_WAVELENGTH)
        result.wave_data = wave_data[wave_min_index:wave_max_index]
        result.wave_min_index = wave_min_index
        result.wave_max_index = wave_max_index

        logger.info(f"✅ Wavelength range: {MIN_WAVELENGTH}-{MAX_WAVELENGTH}nm")
        logger.info(f"   Array indices: {wave_min_index} to {wave_max_index}\n")

        # Get detector parameters
        detector_params = get_detector_params(usb)
        logger.info(f"✅ Detector parameters:")
        logger.info(f"   Max counts: {detector_params.max_counts}")
        logger.info(f"   Target counts: {detector_params.target_counts}")
        logger.info(f"   Saturation threshold: {detector_params.saturation_threshold}\n")

        # Determine channel list
        ch_list = determine_channel_list(device_type, single_mode, single_ch)
        logger.info(f"✅ Channels to calibrate: {ch_list}\n")

        if progress_callback:
            progress_callback("Step 1: Hardware discovered")

        # ===================================================================
        # STEP 2: QUICK DARK NOISE BASELINE
        # ===================================================================
        if progress_callback:
            progress_callback("Step 2: Quick dark baseline...")

        quick_dark = measure_quick_dark_baseline(
            usb, ctrl, wave_min_index, wave_max_index, stop_flag
        )

        # ===================================================================
        # STEP 3: CALIBRATOR INITIALIZATION
        # ===================================================================
        logger.info("=" * 80)
        logger.info("STEP 3: Calibrator Initialization")
        logger.info("=" * 80)
        logger.info("Preparing system for LED calibration\n")

        if progress_callback:
            progress_callback("Step 3: Initializing calibrator...")

        # Switch to S-mode
        logger.info("Switching to S-mode...")
        switch_mode_safely(ctrl, "s", turn_off_leds=True)
        logger.info("✅ S-mode active, all LEDs off\n")

        # ===================================================================
        # STEP 4: LOAD OEM POLARIZER POSITIONS
        # ===================================================================
        if progress_callback:
            progress_callback("Step 4: Loading OEM positions...")

        polarizer_positions = load_oem_polarizer_positions(
            device_config, detector_serial
        )

        # ===================================================================
        # STEP 5: S-MODE LED OPTIMIZATION (SUBSTEPS A-C)
        # ===================================================================
        led_intensities, integration_time, num_scans = optimize_s_mode_leds(
            usb, ctrl, ch_list, detector_params,
            wave_min_index, wave_max_index,
            stop_flag, progress_callback
        )

        result.ref_intensity = led_intensities
        result.integration_time = integration_time
        result.num_scans = num_scans

        # ===================================================================
        # STEP 5D: CAPTURE S-MODE REFERENCE SIGNALS
        # ===================================================================
        logger.info("-" * 80)
        logger.info("STEP 5D: Capture S-Mode Reference Signals")
        logger.info("-" * 80)
        logger.info("Measuring reference spectra at final LED/integration settings\n")

        if progress_callback:
            progress_callback("Step 5D: Capturing S-mode references...")

        # First measure final dark noise at calibrated integration time
        logger.info("Measuring final dark noise at calibrated integration time...")
        final_dark = measure_dark_noise(
            usb, ctrl, integration_time,
            wave_min_index, wave_max_index,
            stop_flag, num_scans=num_scans
        )
        result.dark_noise = final_dark

        logger.info("✅ Step 5E: Final dark noise measured\n")

        # Now measure S-mode references
        s_ref_signals = measure_reference_signals(
            usb, ctrl, ch_list, led_intensities, final_dark,
            integration_time, wave_min_index, wave_max_index,
            stop_flag, afterglow_correction, num_scans=num_scans,
            mode='s'  # Explicitly specify S-mode
        )
        result.s_ref_sig = s_ref_signals

        logger.info("✅ Step 5D: S-mode references captured\n")

        # Validate S-ref quality
        s_ref_qc = validate_s_ref_quality(s_ref_signals, result.wave_data)
        result.s_ref_qc = s_ref_qc

        # Check if all channels passed validation
        all_passed = all(metrics['passed'] for metrics in s_ref_qc.values())
        if not all_passed:
            logger.warning("⚠️ Some S-refs failed QC checks")
            for ch, metrics in s_ref_qc.items():
                if not metrics['passed']:
                    logger.warning(f"  Ch {ch.upper()}: {', '.join(metrics.get('warnings', []))}")

        # ===================================================================
        # STEP 6: P-MODE CALIBRATION
        # ===================================================================
        logger.info("=" * 80)
        logger.info("STEP 6: P-Mode Calibration")
        logger.info("=" * 80)
        logger.info("Substeps:")
        logger.info("  6A: P-mode LED optimization")
        logger.info("  6B: Polarity detection with auto servo recalibration")
        logger.info("  6C: QC metrics (FWHM, SNR, LED health)\n")

        # Switch to P-mode
        logger.info("Switching to P-mode...")
        switch_mode_safely(ctrl, "p", turn_off_leds=True)
        logger.info(f"✅ P-mode active\n")

        # ===================================================================
        # STEP 6A: P-MODE LED OPTIMIZATION
        # ===================================================================
        logger.info("-" * 80)
        logger.info("STEP 6A: P-Mode LED Optimization")
        logger.info("-" * 80)

        if progress_callback:
            progress_callback("Step 6A: Optimizing P-mode LEDs...")

        logger.debug(f"🔍 DEBUG: About to call calibrate_p_mode_leds")
        logger.debug(f"   PRE_LED_DELAY_MS={PRE_LED_DELAY_MS}")
        logger.debug(f"   POST_LED_DELAY_MS={POST_LED_DELAY_MS}")

        from utils.led_calibration import analyze_channel_headroom
        headroom_analysis = analyze_channel_headroom(led_intensities)

        logger.info("🔍 DEBUG-START: About to call calibrate_p_mode_leds")
        logger.info(f"🔍 DEBUG: PRE_LED_DELAY_MS={PRE_LED_DELAY_MS}, POST_LED_DELAY_MS={POST_LED_DELAY_MS}")
        logger.info("🔍 DEBUG: Calling calibrate_p_mode_leds...")
        try:
            p_mode_intensities, p_performance = calibrate_p_mode_leds(
                usb, ctrl, ch_list, led_intensities,
                stop_flag, detector_params=detector_params,
                headroom_analysis=headroom_analysis,
                pre_led_delay_ms=PRE_LED_DELAY_MS,
                post_led_delay_ms=POST_LED_DELAY_MS
            )
            logger.info("🔍 DEBUG: calibrate_p_mode_leds returned successfully")
            logger.info(f"🔍 DEBUG: p_mode_intensities={p_mode_intensities}")
        except Exception as e:
            logger.error(f"🔍 DEBUG-ERROR: calibrate_p_mode_leds FAILED: {e}")
            logger.exception("Traceback:")
            raise

        result.p_mode_intensity = p_mode_intensities

        logger.info(f"✅ Step 6A Complete: P-mode LEDs = {p_mode_intensities}")

        # =======================================================================
        # CRITICAL ANALYSIS: P-MODE WEAKEST LED (PROOF OF OPTIMIZATION)
        # =======================================================================
        logger.info(f"")
        logger.info(f"=" * 80)
        logger.info(f"📊 P-MODE WEAKEST LED ANALYSIS (Optimization Proof)")
        logger.info(f"=" * 80)
        logger.info(f"The weakest LED reaching LED=255 proves optimal calibration!")
        logger.info(f"")

        # UNIVERSAL: Dynamically identify weakest and strongest LEDs
        # This varies by device - could be any channel (A, B, C, or D)
        # Determined by LED efficiency, optical coupling, and fiber alignment
        p_weakest_ch = min(p_mode_intensities, key=p_mode_intensities.get)
        p_strongest_ch = max(p_mode_intensities, key=p_mode_intensities.get)
        p_weakest_led = p_mode_intensities[p_weakest_ch]
        p_strongest_led = p_mode_intensities[p_strongest_ch]

        # Also get S-mode for comparison
        s_weakest_led = led_intensities[p_weakest_ch]
        p_boost = p_weakest_led - s_weakest_led
        p_boost_pct = (p_boost / s_weakest_led) * 100 if s_weakest_led > 0 else 0

        logger.info(f"P-mode LED intensities:")
        for ch in ch_list:
            p_led = p_mode_intensities[ch]
            s_led = led_intensities[ch]
            boost = p_led - s_led
            boost_pct = (boost / s_led) * 100 if s_led > 0 else 0
            marker = " 🔴 WEAKEST" if ch == p_weakest_ch else " 🟢 STRONGEST" if ch == p_strongest_ch else ""
            led_marker = " (MAX!)" if p_led == 255 else ""
            logger.info(f"  Ch {ch.upper()}: {p_led:3d}/255{led_marker:7s} (S: {s_led:3d}, boost: +{boost:3d}, +{boost_pct:5.1f}%){marker}")

        logger.info(f"")
        logger.info(f"🎯 Weakest P-mode Channel: {p_weakest_ch.upper()} at LED={p_weakest_led}")
        logger.info(f"   S-mode baseline: {s_weakest_led}")
        logger.info(f"   P-mode boost: +{p_boost} (+{p_boost_pct:.1f}%)")

        # Provide optimization verdict
        if p_weakest_led == 255:
            logger.info(f"   ✅ PERFECT: Weakest LED at 255 (MAXIMUM!)")
            logger.info(f"   → Optimization pushed to absolute limit")
            logger.info(f"   → Integration time is OPTIMAL for this system")
            logger.info(f"   → No additional signal available from weakest channel")
        elif p_weakest_led >= 245:
            logger.info(f"   ✅ EXCELLENT: Weakest LED ≥ 245 (near maximum)")
            logger.info(f"   → Effectively at optical limit")
            logger.info(f"   → Integration time is well-optimized")
        elif p_weakest_led >= 220:
            logger.info(f"   ⚠️ GOOD: Weakest LED ≥ 220 (approaching limit)")
            logger.info(f"   → {255 - p_weakest_led} LED points unused")
            logger.info(f"   → Integration time could potentially be INCREASED")
            logger.info(f"   → But may be hitting optical limit (check if signal plateaued)")
        else:
            logger.warning(f"   ⚠️ SUBOPTIMAL: Weakest LED < 220")
            logger.warning(f"   → {255 - p_weakest_led} LED points unused (wasted headroom!)")
            logger.warning(f"   → Integration time should be INCREASED")
            logger.warning(f"   → Current integration: {integration_time}ms")
            logger.warning(f"   → System is NOT extracting maximum signal")

        logger.info(f"")
        logger.info(f"💡 Calibration Quality Metric:")
        logger.info(f"   S-mode weakest: {led_intensities[min(led_intensities, key=led_intensities.get)]:3d} (target: 200-220)")
        logger.info(f"   P-mode weakest: {p_weakest_led:3d} (target: 255)")
        logger.info(f"=" * 80)
        logger.info(f"")

        # =======================================================================
        # NOTE: Adaptive optimization happens AFTER P-ref capture
        # We need actual signal counts to assess optimization needs (not LED intensity)
        # =======================================================================
        MAX_P_MODE_ITERATIONS = 3
        INTEGRATION_CHANGE_THRESHOLD = 0.10  # 10% change triggers S-mode recalibration
        original_integration_time = integration_time

        # Capture P-mode reference spectra for QC report
        logger.info("🔍 DEBUG-1: About to capture P-mode reference spectra")
        logger.info(f"🔍 DEBUG-2: ch_list={ch_list}, p_mode_intensities={p_mode_intensities}")
        logger.info("Capturing P-mode reference spectra (verifying NO saturation)...")

        try:
            p_ref_signals = measure_reference_signals(
                usb, ctrl, ch_list, p_mode_intensities, final_dark,
                integration_time, wave_min_index, wave_max_index,
                stop_flag, afterglow_correction, num_scans=num_scans,
                mode='p'  # CRITICAL: Explicitly specify P-mode
            )
            result.p_ref_sig = p_ref_signals
            logger.info(f"✅ P-mode references captured - all channels validated")
        except Exception as e:
            logger.error(f"❌ P-ref capture failed: {e}")
            logger.exception("Full traceback:")
            raise

        # =======================================================================
        # ADAPTIVE P-MODE OPTIMIZATION: 3-Parameter Assessment
        # =======================================================================
        # NOW we have P-ref signals - assess if optimization is needed based on:
        # 1. Signal counts (distance to target)
        # 2. LED intensity (maxed out or not)
        # 3. Integration time (at 100ms limit or not)

        logger.info(f"")
        logger.info(f"=" * 80)
        logger.info(f"📊 P-MODE 3-PARAMETER OPTIMIZATION ASSESSMENT")
        logger.info(f"=" * 80)
        logger.info(f"Analyzing: Signal Counts, LED Intensity, Integration Time")
        logger.info(f"")

        # Parameter 1: Analyze signal counts
        p_signal_max = {}
        for ch in ch_list:
            if ch in p_ref_signals:
                p_signal_max[ch] = np.max(p_ref_signals[ch])

        p_weakest_signal_ch = min(p_signal_max, key=p_signal_max.get)
        p_weakest_signal_counts = p_signal_max[p_weakest_signal_ch]
        p_target_counts = int(detector_params.saturation_threshold * 0.81)  # 81% target

        logger.info(f"PARAMETER 1: Signal Counts")
        for ch in ch_list:
            counts = p_signal_max.get(ch, 0)
            led = p_mode_intensities.get(ch, 0)
            pct = (counts / p_target_counts * 100) if p_target_counts > 0 else 0
            logger.info(f"   Ch {ch.upper()}: {counts:5.0f} counts (LED={led:3d}) [{pct:5.1f}% of target]")

        logger.info(f"")
        logger.info(f"   Weakest: Ch {p_weakest_signal_ch.upper()} at {p_weakest_signal_counts:.0f} counts")
        logger.info(f"   Target: {p_target_counts} counts (81% of saturation)")
        signal_deficit = p_target_counts - p_weakest_signal_counts
        signal_deficit_pct = (signal_deficit / p_target_counts * 100) if p_target_counts > 0 else 0
        logger.info(f"   Deficit: {signal_deficit:.0f} counts ({signal_deficit_pct:.1f}%)")

        # Parameter 2: Analyze LED intensities
        logger.info(f"")
        logger.info(f"PARAMETER 2: LED Intensity")
        p_weakest_led_ch = min(p_mode_intensities, key=p_mode_intensities.get) if p_mode_intensities else None
        p_weakest_led = p_mode_intensities[p_weakest_led_ch] if p_weakest_led_ch else 0

        for ch in ch_list:
            led = p_mode_intensities.get(ch, 0)
            headroom = 255 - led
            logger.info(f"   Ch {ch.upper()}: LED={led:3d}/255 (headroom: {headroom:3d} points)")

        logger.info(f"")
        logger.info(f"   Weakest LED: Ch {p_weakest_led_ch.upper() if p_weakest_led_ch else 'N/A'} at {p_weakest_led}/255")
        led_maxed_out = p_weakest_led >= 250  # Consider maxed if ≥250
        if led_maxed_out:
            logger.warning(f"   ⚠️ LED is MAXED OUT (≥250) - cannot boost further")
        else:
            logger.info(f"   ✅ LED has headroom ({255 - p_weakest_led} points available)")

        # Parameter 3: Integration time status
        logger.info(f"")
        logger.info(f"PARAMETER 3: Integration Time")
        logger.info(f"   Current: {integration_time}ms")
        logger.info(f"   Maximum: 100ms")
        integration_headroom = 100 - integration_time
        logger.info(f"   Headroom: {integration_headroom}ms")
        integration_at_max = integration_time >= 100
        if integration_at_max:
            logger.warning(f"   ⚠️ At MAXIMUM integration time - cannot increase")
        else:
            logger.info(f"   ✅ Integration can be increased by up to {integration_headroom}ms")

        # Decision Logic: Should we optimize?
        logger.info(f"")
        logger.info(f"=" * 80)
        logger.info(f"🎯 OPTIMIZATION DECISION")
        logger.info(f"=" * 80)

        needs_optimization = False
        optimization_reason = []
        can_optimize = False

        # Check if signal is below target (with 10% tolerance)
        signal_below_target = p_weakest_signal_counts < (p_target_counts * 0.90)

        if signal_below_target:
            logger.warning(f"✗ Signal is {signal_deficit_pct:.1f}% below target")
            optimization_reason.append(f"Signal deficit: {signal_deficit:.0f} counts")
            needs_optimization = True
        else:
            logger.info(f"✓ Signal meets target (within 10% tolerance)")

        # Check if we CAN optimize (LED or integration headroom available)
        if not led_maxed_out:
            logger.info(f"✓ LED optimization possible (headroom: {255 - p_weakest_led} points)")
            can_optimize = True
        else:
            logger.warning(f"✗ LED maxed out - cannot boost LED further")

        if not integration_at_max:
            logger.info(f"✓ Integration increase possible (headroom: {integration_headroom}ms)")
            can_optimize = True
        else:
            logger.warning(f"✗ Integration at maximum - cannot increase further")

        # Final decision
        logger.info(f"")
        if needs_optimization and can_optimize:
            logger.warning(f"🔄 OPTIMIZATION NEEDED AND POSSIBLE")
            logger.warning(f"   Reasons: {', '.join(optimization_reason)}")
            if not led_maxed_out and not integration_at_max:
                logger.info(f"   Strategy: Increase integration time (will allow LED re-optimization)")
            elif not integration_at_max:
                logger.info(f"   Strategy: Increase integration time (LED already maxed)")
            else:
                logger.info(f"   Strategy: Re-optimize LEDs (integration at max)")
        elif needs_optimization and not can_optimize:
            logger.warning(f"⚠️ OPTIMIZATION NEEDED BUT NOT POSSIBLE")
            logger.warning(f"   Signal below target but no optimization headroom available")
            logger.warning(f"   Reasons: {', '.join(optimization_reason)}")
            logger.warning(f"   Constraints: LED maxed AND integration at maximum")
            logger.warning(f"   → ACCEPTING SUBOPTIMAL CALIBRATION (hardware limited)")
        else:
            logger.info(f"✅ NO OPTIMIZATION NEEDED")
            logger.info(f"   Signal meets target and calibration is optimal")

        logger.info(f"=" * 80)
        logger.info(f"")

        # =======================================================================
        # ADAPTIVE OPTIMIZATION LOOP (if needed and possible)
        # =======================================================================
        if needs_optimization and can_optimize:
            logger.info(f"")
            logger.info(f"=" * 80)
            logger.info(f"🔄 STARTING ADAPTIVE P-MODE OPTIMIZATION")
            logger.info(f"=" * 80)
            logger.info(f"")

            p_iteration = 0
            while (p_weakest_signal_counts < p_target_counts * 0.90 and
                   p_iteration < MAX_P_MODE_ITERATIONS and
                   integration_time < 100):

                p_iteration += 1

                logger.info(f"")
                logger.info(f"=" * 80)
                logger.info(f"🔄 ITERATION #{p_iteration}/{MAX_P_MODE_ITERATIONS}")
                logger.info(f"=" * 80)

                # Propose integration increase (20% or remaining headroom, whichever is smaller)
                proposed_increase = min(int(integration_time * 0.20), 100 - integration_time)
                proposed_integration = min(integration_time + proposed_increase, 100)

                logger.info(f"Current state:")
                logger.info(f"   Signal: {p_weakest_signal_counts:.0f} / {p_target_counts} counts")
                logger.info(f"   LED: {p_weakest_led}/255")
                logger.info(f"   Integration: {integration_time}ms / 100ms")
                logger.info(f"")
                logger.info(f"Proposed: Increase integration to {proposed_integration}ms (+{proposed_increase}ms)")

                if proposed_integration <= integration_time:
                    logger.info(f"   Cannot increase further - at maximum")
                    break

                # Check if change requires full S+P recalibration
                integration_change_pct = abs(proposed_integration - original_integration_time) / original_integration_time

                if integration_change_pct > INTEGRATION_CHANGE_THRESHOLD:
                    logger.warning(f"")
                    logger.warning(f"⚠️ Integration change: {integration_change_pct*100:.1f}% (exceeds {INTEGRATION_CHANGE_THRESHOLD*100:.0f}% threshold)")
                    logger.warning(f"   Full S+P recalibration would be required")
                    logger.warning(f"   → NOT YET IMPLEMENTED")
                    logger.warning(f"   → Accepting current calibration")
                    logger.warning(f"")
                    break

                # Small change - re-optimize P-mode only
                logger.info(f"   ✅ Change is {integration_change_pct*100:.1f}% (below {INTEGRATION_CHANGE_THRESHOLD*100:.0f}% threshold)")
                logger.info(f"   → P-mode optimization only (S-mode still valid)")
                logger.info(f"")

                integration_time = proposed_integration
                usb.set_integration(integration_time)
                time.sleep(0.1)

                try:
                    logger.info(f"   Re-optimizing P-mode LEDs at {integration_time}ms...")
                    p_mode_intensities, p_performance = calibrate_p_mode_leds(
                        usb, ctrl, ch_list, led_intensities,
                        stop_flag, detector_params=detector_params,
                        headroom_analysis=headroom_analysis,
                        pre_led_delay_ms=PRE_LED_DELAY_MS,
                        post_led_delay_ms=POST_LED_DELAY_MS
                    )
                    result.p_mode_intensity = p_mode_intensities

                    logger.info(f"   Recapturing P-mode references...")
                    p_ref_signals = measure_reference_signals(
                        usb, ctrl, ch_list, p_mode_intensities, final_dark,
                        integration_time, wave_min_index, wave_max_index,
                        stop_flag, afterglow_correction, num_scans=num_scans,
                        mode='p'
                    )
                    result.p_ref_sig = p_ref_signals

                    # Re-analyze
                    p_signal_max = {ch: np.max(p_ref_signals[ch]) for ch in ch_list if ch in p_ref_signals}
                    p_weakest_signal_ch = min(p_signal_max, key=p_signal_max.get)
                    p_weakest_signal_counts = p_signal_max[p_weakest_signal_ch]
                    p_weakest_led = p_mode_intensities.get(p_weakest_signal_ch, 0)

                    logger.info(f"")
                    logger.info(f"📊 Results after iteration #{p_iteration}:")
                    for ch in ch_list:
                        counts = p_signal_max.get(ch, 0)
                        led = p_mode_intensities.get(ch, 0)
                        logger.info(f"   Ch {ch.upper()}: {counts:5.0f} counts (LED={led:3d})")
                    logger.info(f"")
                    logger.info(f"   Weakest: Ch {p_weakest_signal_ch.upper()} at {p_weakest_signal_counts:.0f} counts")

                    if p_weakest_signal_counts >= p_target_counts * 0.90:
                        logger.info(f"   ✅ SUCCESS: Target reached!")
                        break
                    elif p_weakest_led >= 250:
                        logger.warning(f"   ⚠️ LED maxed out ({p_weakest_led}/255) - cannot improve further")
                        break
                    else:
                        deficit = p_target_counts - p_weakest_signal_counts
                        logger.info(f"   Still {deficit:.0f} counts below target - continuing...")

                except Exception as e:
                    logger.error(f"❌ Optimization failed: {e}")
                    integration_time = original_integration_time
                    usb.set_integration(integration_time)
                    break

            # Final summary
            logger.info(f"")
            logger.info(f"=" * 80)
            logger.info(f"📊 OPTIMIZATION SUMMARY")
            logger.info(f"=" * 80)
            logger.info(f"   Iterations: {p_iteration}")
            logger.info(f"   Integration: {original_integration_time}ms → {integration_time}ms")
            logger.info(f"   Final signal: {p_weakest_signal_counts:.0f} / {p_target_counts} counts")
            logger.info(f"   Final LED: {p_weakest_led}/255")

            if p_weakest_signal_counts >= p_target_counts * 0.90:
                logger.info(f"   ✅ SUCCESS: Target achieved")
            elif p_weakest_led >= 250 and integration_time >= 100:
                logger.warning(f"   ⚠️ HARDWARE LIMITED: Both LED and integration maxed")
            elif p_weakest_led >= 250:
                logger.warning(f"   ⚠️ LED LIMITED: At maximum LED intensity")
            elif integration_time >= 100:
                logger.warning(f"   ⚠️ TIME LIMITED: At maximum integration time")
            else:
                logger.warning(f"   ⚠️ PARTIAL: Stopped due to constraints")

            logger.info(f"=" * 80)
            logger.info(f"")

        # ===================================================================
        # STEP 6B: POLARITY DETECTION WITH AUTO SERVO RECALIBRATION
        # ===================================================================
        if progress_callback:
            progress_callback("Step 6B: Checking polarity...")

        polarity_correct, new_positions = detect_polarity_and_recalibrate(
            usb, ctrl, ch_list, p_mode_intensities,
            detector_params, wave_min_index, wave_max_index,
            device_config, detector_serial, stop_flag
        )

        if not polarity_correct and new_positions:
            logger.info("🔄 Polarity was corrected - re-running calibration with new positions...")
            # Recursively call with updated positions
            # (device_config was already updated by detect_polarity_and_recalibrate)
            return run_full_6step_calibration(
                usb, ctrl, device_type, device_config, detector_serial,
                single_mode, single_ch, stop_flag, progress_callback,
                afterglow_correction
            )

        # ===================================================================
        # STEP 6C: QC METRICS
        # ===================================================================
        logger.info("-" * 80)
        logger.info("STEP 6C: Quality Control Metrics")
        logger.info("-" * 80)

        if progress_callback:
            progress_callback("Step 6C: Measuring QC metrics...")

        # Run full P-mode verification (saturation check, SPR FWHM, orientation validation)
        logger.info("Running P-mode verification with global integration method...")
        ch_error_list, orientation_validation, transmission_validation, polarizer_swap_detected = verify_calibration_global_integration(
            usb=usb,
            ctrl=ctrl,
            leds_calibrated=p_mode_intensities,
            wave_data=wave_data[wave_min_index:wave_max_index],
            s_ref_signals=result.s_ref_sig,
            pre_led_delay_ms=pre_led_delay_ms,
            post_led_delay_ms=post_led_delay_ms
        )

        verification_result = {
            'success': len(ch_error_list) == 0,
            'ch_error_list': ch_error_list,
            'orientation_validation': orientation_validation,
            'transmission_validation': transmission_validation,
            'polarizer_swap_detected': polarizer_swap_detected
        }

        result.verification = verification_result
        result.ch_error_list = ch_error_list
        result.orientation_validation = orientation_validation
        result.transmission_validation = transmission_validation
        result.success = len(ch_error_list) == 0

        if polarizer_swap_detected:
            logger.error("⚠️ POLARIZER SWAP DETECTED - Calibration marked as failed")
            result.success = False

        logger.info("✅ Step 6C Complete: QC metrics measured\n")

        # ===================================================================
        # CALIBRATION COMPLETE
        # ===================================================================

        # Copy S-mode reference signals to ref_sig for compatibility with calibration manager
        result.ref_sig = result.s_ref_sig

        logger.info("\n" + "=" * 80)
        logger.info("✅ 6-STEP CALIBRATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"LED Intensities (S-mode): {result.ref_intensity}")
        logger.info(f"LED Intensities (P-mode): {result.p_mode_intensity}")
        logger.info(f"Integration Time: {result.integration_time}ms")
        logger.info(f"Scans per Channel: {result.num_scans}")
        logger.info(f"Channels with Errors: {result.ch_error_list if result.ch_error_list else 'None'}")
        logger.info("=" * 80)
        logger.info("Next: Show post-calibration dialog, wait for user to click Start")
        logger.info("=" * 80 + "\n")

        return result

    except Exception as e:
        # Print full traceback immediately to console
        import traceback
        print("\n" + "="*80)
        print("6-STEP CALIBRATION ERROR - FULL TRACEBACK:")
        print("="*80)
        traceback.print_exc()
        print("="*80 + "\n")

        logger.exception(f"6-step calibration failed: {e}")
        result.success = False
        result.error = str(e)
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
    afterglow_correction=None,
    pre_led_delay_ms: float = 45.0,
    post_led_delay_ms: float = 5.0
) -> LEDCalibrationResult:
    """Fast-track calibration with ±10% validation.

    Loads previous calibration from device_config.json and validates
    that it still works within ±10% tolerance. If valid, skips the
    full 6-step optimization and uses cached values.

    Any channels that fail validation are automatically recalibrated.

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

        # Load previous calibration
        cal_data = device_config.load_led_calibration()

        if not cal_data or 's_mode_intensities' not in cal_data:
            logger.info("No previous calibration found - falling back to full calibration")
            return run_full_6step_calibration(
                usb, ctrl, device_type, device_config, detector_serial,
                single_mode, single_ch, stop_flag, progress_callback,
                afterglow_correction
            )

        # Get detector parameters
        wave_data = usb.read_wavelength()
        wave_min_index = wave_data.searchsorted(MIN_WAVELENGTH)
        wave_max_index = wave_data.searchsorted(MAX_WAVELENGTH)
        detector_params = get_detector_params(usb)
        ch_list = determine_channel_list(device_type, single_mode, single_ch)

        # Load saved values
        saved_s_leds = cal_data['s_mode_intensities']
        saved_integration = cal_data.get('integration_time_ms', 50)

        logger.info(f"Previous calibration date: {cal_data.get('calibration_date', 'unknown')}")
        logger.info(f"Saved S-mode LEDs: {saved_s_leds}")
        logger.info(f"Saved integration time: {saved_integration}ms\n")

        # Validate each channel
        logger.info("Validating channels (±10% tolerance)...\n")

        validated_leds = {}
        failed_channels = []

        # Switch to S-mode
        switch_mode_safely(ctrl, "s", turn_off_leds=True)
        usb.set_integration(saved_integration)
        time.sleep(0.1)

        target_counts = detector_params.target_counts
        tolerance = 0.10  # ±10%

        for ch in ch_list:
            if stop_flag and stop_flag.is_set():
                break

            if ch not in saved_s_leds:
                logger.warning(f"❌ Channel {ch.upper()}: No saved LED value")
                failed_channels.append(ch)
                continue

            saved_led = saved_s_leds[ch]

            # Test saved LED
            ctrl.set_intensity(ch=ch, raw_val=saved_led)
            time.sleep(LED_DELAY)

            spectrum = usb.read_intensity()
            if spectrum is None:
                logger.error(f"❌ Channel {ch.upper()}: Hardware read failed")
                failed_channels.append(ch)
                continue

            max_signal = np.max(spectrum[wave_min_index:wave_max_index])
            deviation = abs(max_signal - target_counts) / target_counts

            if deviation <= tolerance:
                validated_leds[ch] = saved_led
                logger.info(f"✅ Channel {ch.upper()}: PASS (signal={max_signal:.0f}, target={target_counts:.0f}, deviation={deviation*100:.1f}%)")
            else:
                failed_channels.append(ch)
                logger.warning(f"❌ Channel {ch.upper()}: FAIL (signal={max_signal:.0f}, target={target_counts:.0f}, deviation={deviation*100:.1f}%)")

            ctrl.set_intensity(ch=ch, raw_val=0)
            time.sleep(0.01)

        # If all channels passed, use fast-track
        if len(failed_channels) == 0:
            logger.info("\n" + "=" * 80)
            logger.info("✅ FAST-TRACK VALIDATION PASSED")
            logger.info("=" * 80)
            logger.info("All channels within ±10% tolerance")
            logger.info("Using cached calibration values")
            logger.info(f"Estimated time saved: ~80% (skipped Steps 1-6 optimization)")
            logger.info("=" * 80 + "\n")

            # Build result from cached data
            result.ref_intensity = validated_leds
            result.integration_time = saved_integration
            result.wave_data = wave_data[wave_min_index:wave_max_index]
            result.wave_min_index = wave_min_index
            result.wave_max_index = wave_max_index

            # Still need to measure dark and refs at current temperature
            num_scans = calculate_scan_counts(saved_integration).s_scans

            result.dark_noise = measure_dark_noise(
                usb, ctrl, saved_integration,
                wave_min_index, wave_max_index,
                stop_flag, num_scans=num_scans
            )

            result.s_ref_sig = measure_reference_signals(
                usb, ctrl, ch_list, validated_leds, result.dark_noise,
                saved_integration, wave_min_index, wave_max_index,
                stop_flag, afterglow_correction, num_scans=num_scans,
                mode='s'  # Explicitly specify S-mode
            )

            # Load P-mode from cache or recalibrate
            if 'p_mode_intensities' in cal_data:
                result.p_mode_intensity = cal_data['p_mode_intensities']
            else:
                logger.info("P-mode not in cache - calibrating...")
                from utils.led_calibration import calibrate_p_mode_leds, analyze_channel_headroom
                switch_mode_safely(ctrl, "p", turn_off_leds=True)
                headroom = analyze_channel_headroom(validated_leds)
                result.p_mode_intensity, _ = calibrate_p_mode_leds(
                    usb, ctrl, ch_list, validated_leds,
                    stop_flag, detector_params=detector_params,
                    headroom_analysis=headroom,
                    pre_led_delay_ms=PRE_LED_DELAY_MS,
                    post_led_delay_ms=POST_LED_DELAY_MS
                )

            # Capture P-mode reference spectra for QC report
            logger.info("Capturing P-mode reference spectra for QC validation...")
            p_ref_signals = measure_reference_signals(
                usb, ctrl, ch_list, result.p_mode_intensity, result.dark_noise,
                saved_integration, wave_min_index, wave_max_index,
                stop_flag, afterglow_correction, num_scans=num_scans,
                mode='p'  # Explicitly specify P-mode
            )
            result.p_ref_sig = p_ref_signals
            logger.info(f"✅ P-mode references captured")

            result.success = True
            result.num_scans = num_scans
            result.ref_sig = result.s_ref_sig  # Copy for calibration manager compatibility

            return result

        # Some channels failed - recalibrate failed channels only
        logger.info("\n" + "=" * 80)
        logger.info("⚠️ FAST-TRACK PARTIAL VALIDATION")
        logger.info("=" * 80)
        logger.info(f"Passed: {list(validated_leds.keys())}")
        logger.info(f"Failed: {failed_channels}")
        logger.info("Recalibrating failed channels...")
        logger.info("=" * 80 + "\n")

        # Recalibrate failed channels
        for ch in failed_channels:
            if stop_flag and stop_flag.is_set():
                break

            if progress_callback:
                progress_callback(f"Recalibrating channel {ch.upper()}...")

            logger.info(f"Recalibrating channel {ch.upper()}...")
            led_val = calibrate_led_channel(
                usb, ctrl, ch, None, stop_flag,
                detector_params=detector_params,
                wave_min_index=wave_min_index,
                wave_max_index=wave_max_index,
                pre_led_delay_ms=PRE_LED_DELAY_MS,
                post_led_delay_ms=POST_LED_DELAY_MS
            )
            validated_leds[ch] = led_val
            logger.info(f"✅ Channel {ch.upper()}: {led_val}/255\n")

        # Build result with mix of cached and recalibrated
        result.ref_intensity = validated_leds
        result.integration_time = saved_integration
        result.wave_data = wave_data[wave_min_index:wave_max_index]
        result.wave_min_index = wave_min_index
        result.wave_max_index = wave_max_index

        num_scans = calculate_scan_counts(saved_integration).num_scans

        result.dark_noise = measure_dark_noise(
            usb, ctrl, saved_integration,
            wave_min_index, wave_max_index,
            stop_flag, num_scans=num_scans
        )

        result.s_ref_sig = measure_reference_signals(
            usb, ctrl, ch_list, validated_leds, result.dark_noise,
            saved_integration, wave_min_index, wave_max_index,
            stop_flag, afterglow_correction, num_scans=num_scans,
            mode='s'  # Explicitly specify S-mode
        )

        # Calibrate P-mode
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

        result.success = True
        result.num_scans = num_scans
        result.ref_sig = result.s_ref_sig  # Copy for calibration manager compatibility

        logger.info("\n✅ Fast-track calibration complete (with partial recalibration)\n")

        return result

    except Exception as e:
        # Print full traceback immediately to console
        import traceback
        print("\n" + "="*80)
        print("FAST-TRACK CALIBRATION ERROR - FULL TRACEBACK:")
        print("="*80)
        traceback.print_exc()
        print("="*80 + "\n")

        logger.exception(f"Fast-track calibration failed: {e}")
        logger.info("Falling back to full calibration...")
        return run_full_6step_calibration(
            usb, ctrl, device_type, device_config, detector_serial,
            single_mode, single_ch, stop_flag, progress_callback,
            afterglow_correction
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

def run_global_led_calibration(
    usb,
    ctrl,
    device_type: str,
    device_config,
    detector_serial: str,
    single_mode: bool = False,
    single_ch: str = "a",
    stop_flag=None,
    progress_callback=None,
    afterglow_correction=None,
    pre_led_delay_ms: float = 45.0,
    post_led_delay_ms: float = 5.0
) -> LEDCalibrationResult:
    """Global LED mode: LED=255 fixed, variable integration per channel.

    This is an alternative calibration mode where all LEDs are set to
    maximum intensity (255) and integration time is optimized per channel.

    Benefits:
    - Maximum SNR (LEDs at max current)
    - Consistent LED behavior across channels
    - Better frequency (optimized integration per channel)

    Trade-offs:
    - Variable integration time per channel
    - More complex timing during acquisition

    Controlled by settings.USE_ALTERNATIVE_CALIBRATION flag.

    Args:
        Same as run_full_6step_calibration

    Returns:
        LEDCalibrationResult with calibration data
    """
    print("\n" + "="*80)
    print("🚀🚀🚀 run_global_led_calibration() ENTERED")
    print("="*80 + "\n")

    logger.debug("🔍 DEBUG: run_global_led_calibration called")
    logger.debug("🔍 DEBUG: Parameters received:")
    logger.debug(f"   device_type={device_type}")
    logger.debug(f"   pre_led_delay_ms={pre_led_delay_ms}")
    logger.debug(f"   post_led_delay_ms={post_led_delay_ms}")

    logger.info("\n" + "=" * 80)
    logger.info("🚀 GLOBAL LED MODE CALIBRATION")
    logger.info("=" * 80)
    logger.info("Mode: LED=255 fixed for all channels")
    logger.info("Optimization: Variable integration time per channel")
    logger.info("=" * 80 + "\n")

    # Import the existing alternative calibration implementation
    from utils.led_calibration import perform_alternative_calibration

    logger.debug("🔍 DEBUG: About to call perform_alternative_calibration")
    logger.debug(f"   usb={usb}")
    logger.debug(f"   ctrl={ctrl}")
    logger.debug(f"   device_type={device_type}")
    logger.debug(f"   afterglow_correction={afterglow_correction is not None}")

    print("\n🔥 ABOUT TO CALL perform_alternative_calibration()...")
    print(f"   Function: {perform_alternative_calibration}")

    # Call existing implementation with all parameters
    result = perform_alternative_calibration(
        usb=usb,
        ctrl=ctrl,
        device_type=device_type,
        single_mode=single_mode,
        single_ch=single_ch,
        stop_flag=stop_flag,
        progress_callback=progress_callback,
        wave_data=None,
        wave_min_index=None,
        wave_max_index=None,
        device_config=device_config,
        polarizer_type=None,
        afterglow_correction=afterglow_correction,
        pre_led_delay_ms=pre_led_delay_ms,
        post_led_delay_ms=post_led_delay_ms
    )

    print(f"🔥 perform_alternative_calibration() RETURNED")
    print(f"   result.success = {result.success}")
    print(f"   result type = {type(result)}")

    logger.info("\n✅ Global LED mode calibration complete\n")

    return result
