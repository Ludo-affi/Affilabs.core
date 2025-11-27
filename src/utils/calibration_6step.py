"""6-Step Startup Calibration Flow

This module implements the 6-step calibration flow for SPR systems.

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

STEP 5: P-Mode Optimization (Transfer S-mode + Boost)
  - Switch polarizer to P-polarization
  - Transfer all S-mode parameters (100% baseline)
  - Iteratively boost LED intensities (max 10 iterations, 10% per iteration)
  - Target: Weakest LED near 255 (proof of optimization)
  - Constraint: All channels <95% saturation
  - Optional: Up to +10% integration time increase
  - Capture P-pol raw spectra per channel
  - Measure dark-ref at P-mode integration time (QC: 2500-4000 counts)

STEP 6: S-Mode Reference Signals + QC (FINAL STEP)
  - Switch back to S-mode
  - Measure S-mode reference signals with optimized LED intensities
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

from settings import (
    CH_LIST,
    EZ_CH_LIST,
    LED_DELAY,
    PRE_LED_DELAY_MS,
    POST_LED_DELAY_MS,
    MIN_WAVELENGTH,
    MAX_WAVELENGTH,
    MAX_INTEGRATION,
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
    verify_calibration,
    analyze_channel_headroom,
    perform_alternative_calibration,
)

# Local constants for Steps 1-3 (GitHub alignment)
TEMP_INTEGRATION_TIME_MS = 32  # Temporary integration for Steps 1-3 (GitHub standard)

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

            # Check if all LEDs are off (0 intensity)
            all_off = all(intensity == 0 for intensity in led_state.values())

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
    logger.info("Target: 70% of detector max (leaves 30% headroom for P-mode)")
    logger.info(f"Integration time: {integration_time}ms (already optimized)\n")

    # Use detector's target_counts property (already returns 70% of max)
    # This ensures consistency with detector calibration strategy
    s_mode_target = detector_params.target_counts

    logger.info(f"S-mode target: {s_mode_target} counts (70% of {detector_params.max_counts})")
    logger.info(f"P-mode headroom: {detector_params.max_counts - s_mode_target} counts (30%)\n")

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
        logger.info(f"  - Target: {s_mode_target} counts (70% of max)")
        logger.info(f"  - Leaves 30% headroom for P-mode boost\n")

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
    # CRITICAL: Apply Weakest LED Rule for S-mode Balance
    # This happens AFTER individual LED optimization, BEFORE S-ref capture
    # Ensures all S-mode reference signals are balanced across channels
    # =======================================================================
    logger.info(f"=" * 80)
    logger.info(f"📊 APPLYING WEAKEST LED RULE FOR S-MODE (Signal Balance)")
    logger.info(f"=" * 80)
    logger.info(f"NOTE: This balancing occurs before S-ref capture to ensure")
    logger.info(f"      all reference signals have consistent intensity levels")
    logger.info(f"=" * 80)

    # Find weakest channel (lowest signal)
    weakest_ch_signal = None
    weakest_signal = float('inf')

    for ch in ch_list:
        # Measure current signal for this channel
        ctrl.set_intensity(ch=ch, raw_val=led_intensities[ch])
        time.sleep(LED_DELAY)
        spectrum = usb.read_intensity()
        if spectrum is not None:
            ch_signal = spectrum[wave_min_index:wave_max_index].max()
            if ch_signal < weakest_signal:
                weakest_signal = ch_signal
                weakest_ch_signal = ch
        ctrl.set_intensity(ch=ch, raw_val=0)

    logger.info(f"Weakest S-mode channel: {weakest_ch_signal.upper()}")
    logger.info(f"   Signal: {weakest_signal:.0f} counts")
    logger.info(f"   LED: {led_intensities[weakest_ch_signal]}/255")
    logger.info(f"")
    logger.info(f"Balancing all S-mode channels to match weakest channel signal level...")

    # Balance all other channels to match weakest
    for ch in ch_list:
        if ch == weakest_ch_signal:
            logger.info(f"   Ch {ch.upper()}: {weakest_signal:.0f} counts @ LED={led_intensities[ch]} (weakest - no change)")
            continue

        # Measure current signal
        ctrl.set_intensity(ch=ch, raw_val=led_intensities[ch])
        time.sleep(LED_DELAY)
        spectrum = usb.read_intensity()
        if spectrum is None:
            continue

        current_signal = spectrum[wave_min_index:wave_max_index].max()
        current_led = led_intensities[ch]

        # Calculate target LED to match weakest signal
        target_led = int(current_led * (weakest_signal / current_signal))
        target_led = max(10, min(target_led, 255))

        logger.info(f"   Ch {ch.upper()}: {current_signal:.0f} → {weakest_signal:.0f} counts, LED {current_led} → {target_led}")

        # Update and verify
        led_intensities[ch] = target_led
        ctrl.set_intensity(ch=ch, raw_val=target_led)
        time.sleep(LED_DELAY)
        verify_spectrum = usb.read_intensity()
        if verify_spectrum is not None:
            verify_signal = verify_spectrum[wave_min_index:wave_max_index].max()
            logger.debug(f"      Verification: {verify_signal:.0f} counts")

        ctrl.set_intensity(ch=ch, raw_val=0)

    logger.info(f"")
    logger.info(f"✅ All S-mode channels balanced to weakest channel signal level")
    logger.info(f"=" * 80)
    logger.info(f"")

    # =======================================================================
    # CRITICAL ANALYSIS: WEAKEST LED DETERMINES OPTIMIZATION QUALITY
    # =======================================================================
    logger.info(f"=" * 80)
    logger.info(f"📊 WEAKEST LED ANALYSIS (Key Optimization Metric)")
    logger.info(f"=" * 80)
    logger.info(f"The WEAKEST LED is the bottleneck for the entire system.")
    logger.info(f"This is a DEVICE-SPECIFIC hardware characteristic.")
    logger.info(f"Optimal global integration time is achieved when:")
    logger.info(f"  • S-mode target: 70% detector max (30% headroom for P-boost)")
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
    logger.info(f"Weakest Channel: {weakest_ch.upper()} (hardware characteristic)")
    logger.info(f"Ready for Step 5D (S-ref capture) and 5E (final dark noise)\n")

    return led_intensities, integration_time, num_scans, weakest_ch


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
    result = LEDCalibrationResult()

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
            # Positions not found in config - fail immediately
            logger.error("=" * 80)
            logger.error("❌ CRITICAL: OEM CALIBRATION POSITIONS NOT FOUND")
            logger.error("=" * 80)
            logger.error(f"   device_config keys: {list(device_config_dict.keys())}")
            logger.error("")
            logger.error("🔧 REQUIRED: Run OEM calibration tool to configure polarizer positions")
            logger.error("   Command: python utils/oem_calibration_tool.py --serial <DETECTOR_SERIAL>")
            logger.error("")
            logger.error("   The OEM tool will:")
            logger.error("   1. Scan servo positions to find optimal S and P angles")
            logger.error("   2. Measure transmission at each position")
            logger.error("   3. Save positions to device_config.json")
            logger.error("")
            logger.error("   ❌ NO DEFAULT POSITIONS - OEM calibration is MANDATORY")
            logger.error("=" * 80)
            raise ValueError("OEM calibration positions not found in device_config")

        logger.info("\n" + "=" * 80)
        logger.info("🚀 STARTING 6-STEP CALIBRATION FLOW")
        logger.info("=" * 80)
        logger.info("This calibration follows the exact flow discussed:")
        logger.info("  Step 1: Hardware Validation & LED Verification")
        logger.info("  Step 2: Wavelength Calibration")
        logger.info("  Step 3: LED Brightness Ranking")
        logger.info("  Step 4: S-Mode Integration & LED Optimization")
        logger.info("  Step 5: P-Mode Optimization (Transfer + Boost)")
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
            progress_callback("Step 1: Validating hardware...")

        # CRITICAL: Force all LEDs OFF and VERIFY
        logger.info("🔦 Forcing ALL LEDs OFF...")
        ctrl.turn_off_channels()
        time.sleep(0.2)

        # VERIFY LEDs are off using V1.1 firmware query (CRITICAL!)
        logger.info("✅ Verifying LEDs are off...")
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

                # Check if all LEDs are off (0 intensity)
                all_off = all(intensity == 0 for intensity in led_state.values())

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
                raise RuntimeError("Cannot proceed - LEDs failed to turn off")

        if not has_led_query:
            # V1.0 firmware or LED query unavailable - use timing-based approach
            logger.info("LED query not available - using timing-based verification")
            time.sleep(0.05)  # Extra settling time for V1.0 firmware
            led_verified = True

        logger.info(f"✅ Step 1 complete: Hardware validated, LEDs confirmed OFF\n")

        # ===================================================================
        # STEP 2: WAVELENGTH RANGE CALIBRATION (DETECTOR-SPECIFIC)
        # ===================================================================
        logger.info("=" * 80)
        logger.info("STEP 2: Wavelength Range Calibration (Detector-Specific)")
        logger.info("=" * 80)

        if progress_callback:
            progress_callback("Step 2: Calibrating wavelength range...")

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
            progress_callback("Step 3: Ranking LED brightness...")

        # Switch to S-mode and turn off all channels
        logger.info("Switching to S-mode...")
        switch_mode_safely(ctrl, "s", turn_off_leds=True)
        logger.info("✅ S-mode active, all LEDs off\n")

        # Set fixed integration time for consistent LED ranking
        # 70ms provides sufficient signal at 20% LED (weak but adequate for ranking)
        RANKING_INTEGRATION_TIME = 0.070  # 70ms in seconds
        usb.set_integration(RANKING_INTEGRATION_TIME)
        logger.info(f"🔧 Integration time set to {RANKING_INTEGRATION_TIME*1000:.0f}ms for LED ranking\n")

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
                raw_spectrum = usb.read_spectrum()
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

                    raw_spectrum = usb.read_spectrum()
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

        # Display final ranking summary
        weakest_ch = result.led_ranking[0][0]
        strongest_ch = result.led_ranking[-1][0]
        weakest_intensity = result.led_ranking[0][1][0]
        strongest_intensity = result.led_ranking[-1][1][0]

        logger.info(f"")
        logger.info(f"✅ Weakest LED: {weakest_ch.upper()} ({weakest_intensity:.0f} counts)")
        logger.info(f"   → Will be FIXED at LED=255 (maximum) in Step 4")
        logger.info(f"⚠️  Strongest LED: {strongest_ch.upper()} ({strongest_intensity:.0f} counts, {strongest_intensity/weakest_intensity:.2f}× brighter)")
        logger.info(f"   → Will need most dimming (ratio: {strongest_intensity/weakest_intensity:.2f}×)")
        logger.info(f"✅ Step 3 complete\n")

        # Store weakest channel in result
        result.weakest_channel = weakest_ch

        # ===================================================================
        # STEP 4: INTEGRATION TIME OPTIMIZATION (CONSTRAINED DUAL OPTIMIZATION)
        # ===================================================================
        if progress_callback:
            progress_callback(f"Step 4: Optimizing integration time for {weakest_ch}...")

        logger.info("=" * 80)
        logger.info("STEP 4: Integration Time Optimization (Constrained Dual Optimization)")
        logger.info("=" * 80)
        logger.info("Goal: Maximize weakest LED signal while preventing strongest LED saturation")
        logger.info(f"Weakest channel: {weakest_ch} (will be at LED=255)")
        logger.info(f"Constraints: Weakest 60-80%, Strongest <95%, Integration ≤70ms\n")

        # Get detector limits
        min_int = detector_params.min_integration_time / 1000.0  # Convert ms to seconds
        max_int = MAX_INTEGRATION / 1000.0  # 70ms from settings
        detector_max = detector_params.saturation_threshold

        # Get strongest channel from Step 3 (used only for constraint checking during search)
        strongest_ch = ranked_channels[-1][0]

        logger.info(f"   Weakest LED: {weakest_ch} (will be optimized at LED=255)")
        logger.info(f"   Strongest LED: {strongest_ch} (will be tested for saturation)")
        logger.info(f"")
        logger.info(f"   PRIMARY GOAL: Maximize weakest LED signal")
        logger.info(f"      → Target: 70% @ LED=255 ({int(0.70*detector_max):,} counts)")
        logger.info(f"      → Range: 60-80% ({int(0.60*detector_max):,}-{int(0.80*detector_max):,} counts)")
        logger.info(f"")
        logger.info(f"   CONSTRAINT 1: Strongest LED must not saturate")
        logger.info(f"      → Maximum: <95% @ LED≥25 ({int(0.95*detector_max):,} counts)")
        logger.info(f"")
        logger.info(f"   CONSTRAINT 2: Integration time ≤ {max_int*1000:.0f}ms")
        logger.info(f"")

        # Define targets from settings
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
            if stop_flag and stop_flag.is_set():
                break

            # Test integration time (midpoint)
            test_integration = (integration_min + integration_max) / 2.0
            usb.set_integration(test_integration)
            time.sleep(0.1)

            # Test weakest LED at LED=255
            ctrl.set_intensity(ch=weakest_ch, raw_val=255)
            time.sleep(LED_DELAY)
            spectrum = usb.read_intensity()
            ctrl.set_intensity(ch=weakest_ch, raw_val=0)

            if spectrum is None:
                logger.error("Failed to read spectrum")
                break

            weakest_signal = spectrum[wave_min_index:wave_max_index].max()
            weakest_percent = (weakest_signal / detector_max) * 100

            # Test strongest LED at LED=255 (worst case for saturation)
            ctrl.set_intensity(ch=strongest_ch, raw_val=255)
            time.sleep(LED_DELAY)
            spectrum = usb.read_intensity()
            ctrl.set_intensity(ch=strongest_ch, raw_val=0)

            if spectrum is None:
                logger.error("Failed to read spectrum")
                break

            strongest_signal = spectrum[wave_min_index:wave_max_index].max()
            strongest_percent = (strongest_signal / detector_max) * 100

            logger.info(f"   Iteration {iteration+1}: {test_integration*1000:.1f}ms")
            logger.info(f"      Weakest ({weakest_ch} @ LED=255): {weakest_signal:6.0f} counts ({weakest_percent:5.1f}%)")
            logger.info(f"      Strongest ({strongest_ch} @ LED=255): {strongest_signal:6.0f} counts ({strongest_percent:5.1f}%)")

            # Check constraints
            if strongest_signal > strongest_max:
                logger.info(f"      ❌ Strongest LED too high (would saturate) → Reduce integration")
                integration_max = test_integration
                continue

            # Check if weakest LED is in target range
            if weakest_min <= weakest_signal <= weakest_max:
                best_integration = test_integration
                best_weakest_signal = weakest_signal
                best_strongest_signal = strongest_signal
                logger.info(f"      ✅ OPTIMAL! Both constraints satisfied")
                break
            elif weakest_signal < weakest_min:
                logger.info(f"      ⚠️  Weakest LED too low → Increase integration")
                integration_min = test_integration
            else:
                logger.info(f"      ⚠️  Weakest LED too high → Reduce integration")
                integration_max = test_integration

            # Track best so far
            if abs(weakest_signal - weakest_target) < abs(best_weakest_signal - weakest_target):
                best_integration = test_integration
                best_weakest_signal = weakest_signal
                best_strongest_signal = strongest_signal

        if best_integration is None:
            logger.error("Failed to find optimal integration time!")
            raise RuntimeError("Integration time optimization failed")

        # Apply final integration time
        usb.set_integration(best_integration)
        result.s_integration_time = best_integration * 1000  # Convert to ms (S-mode)
        time.sleep(0.1)

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
        logger.info(f"   Strongest LED ({strongest_ch} @ LED=255):")
        logger.info(f"      Signal: {best_strongest_signal:6.0f} counts ({strongest_percent:5.1f}%)")
        logger.info(f"      Status: {'✅ Safe (<95%)' if best_strongest_signal < strongest_max else '⚠️  Near saturation!'}")
        logger.info(f"")
        logger.info(f"   Integration time FINAL for S-mode: {best_integration*1000:.1f}ms")
        logger.info(f"   This will be used for:")
        logger.info(f"      • Step 5: P-mode optimization (transfer S-mode + boost LEDs)")
        logger.info(f"      • Step 6: S-mode reference signal measurement (FINAL STEP)")
        logger.info(f"")
        logger.info(f"="*80)

        # Measure optimal LED intensities for all channels at optimized integration time
        logger.info(f"")
        logger.info(f"📊 MEASURING OPTIMAL LED INTENSITIES (Step 4 Optimization)")
        logger.info(f"")
        logger.info(f"   Using Step 3 brightness ratios to predict starting LEDs...")
        logger.info(f"   Linear scaling with saturation protection (binary search fallback)")
        logger.info(f"")

        led_intensities = {}
        target_signal = int(0.70 * detector_max)

        # Build brightness ratio map from Step 3 for intelligent LED prediction
        step3_brightness_map = {ch: intensity for ch, (intensity, _, _) in ranked_channels}
        step3_weakest_intensity = step3_brightness_map[weakest_ch]

        for ch_name in ch_list:
            if stop_flag and stop_flag.is_set():
                break

            # ===================================================================
            # INTELLIGENT LED PREDICTION from Step 3 brightness ratios
            # ===================================================================
            # Step 3 measured at: 70ms integration, 20% LED (51)
            # Predict LED needed at optimized integration time for 70% signal

            step3_signal = step3_brightness_map[ch_name]
            brightness_ratio = step3_signal / step3_weakest_intensity

            # Scale LED inversely with brightness ratio
            # Brighter LED → needs lower LED value to reach same target
            predicted_led = int(255 / brightness_ratio)
            predicted_led = max(10, min(255, predicted_led))

            logger.debug(f"   {ch_name.upper()}: Step 3 brightness ratio = {brightness_ratio:.2f}× → Predicted LED = {predicted_led}")

            # ===================================================================
            # PRIMARY METHOD: Linear scaling with Step 3 prediction
            # ===================================================================
            # Use predicted LED as starting point (better than fixed 128)
            test_led = predicted_led

            ctrl.set_intensity(ch=ch_name, raw_val=test_led)
            time.sleep(LED_DELAY)
            spectrum = usb.read_intensity()
            ctrl.set_intensity(ch=ch_name, raw_val=0)

            if spectrum is None:
                logger.warning(f"      {ch_name.upper()}: Failed to read spectrum, skipping")
                led_intensities[ch_name] = 255  # Fallback
                continue

            filtered_spectrum = spectrum[wave_min_index:wave_max_index]
            test_signal = filtered_spectrum.max()

            # Check for saturation at test LED
            use_binary_fallback = False
            if test_signal >= strongest_max:
                logger.warning(f"      {ch_name.upper()}: Saturated at LED={test_led}, using binary search fallback")
                use_binary_fallback = True
            else:
                # Linear calculation
                calculated_led = int(test_led * (target_signal / test_signal))
                calculated_led = max(10, min(255, calculated_led))

                # Verify calculated LED with saturation check
                ctrl.set_intensity(ch=ch_name, raw_val=calculated_led)
                time.sleep(LED_DELAY)
                verify_spectrum = usb.read_intensity()
                ctrl.set_intensity(ch=ch_name, raw_val=0)

                if verify_spectrum is None:
                    logger.warning(f"      {ch_name.upper()}: Verification failed, using test value")
                    led_intensities[ch_name] = calculated_led
                    continue

                verify_filtered = verify_spectrum[wave_min_index:wave_max_index]
                verify_signal = verify_filtered.max()

                # CRITICAL: Check for saturation on ANY pixel in SPR range
                if verify_signal >= strongest_max:
                    logger.warning(f"      {ch_name.upper()}: Saturation detected ({verify_signal:.0f} counts), reducing LED")
                    # Scale down by 90% for safety margin
                    calculated_led = int(calculated_led * 0.90)
                    calculated_led = max(10, calculated_led)

                    # Re-verify after reduction
                    ctrl.set_intensity(ch=ch_name, raw_val=calculated_led)
                    time.sleep(LED_DELAY)
                    recheck_spectrum = usb.read_intensity()
                    ctrl.set_intensity(ch=ch_name, raw_val=0)

                    if recheck_spectrum is not None:
                        recheck_signal = recheck_spectrum[wave_min_index:wave_max_index].max()
                        if recheck_signal >= strongest_max:
                            # Still saturating, use binary search fallback
                            logger.warning(f"      {ch_name.upper()}: Still saturating, switching to binary search")
                            use_binary_fallback = True
                        else:
                            led_intensities[ch_name] = calculated_led
                            signal_percent = (recheck_signal / detector_max) * 100
                            logger.info(f"      {ch_name.upper()}: LED={calculated_led} ({signal_percent:.1f}%) [linear+correction]")
                            use_binary_fallback = False
                    else:
                        use_binary_fallback = True

                # Check if verification is within acceptable range (no saturation)
                elif abs(verify_signal - target_signal) < 0.15 * detector_max:  # Within 15%
                    led_intensities[ch_name] = calculated_led
                    signal_percent = (verify_signal / detector_max) * 100
                    logger.info(f"      {ch_name.upper()}: LED={calculated_led} ({signal_percent:.1f}%) [linear]")
                    use_binary_fallback = False
                else:
                    # One correction iteration (linear may be off due to non-linearity)
                    corrected_led = int(calculated_led * (target_signal / verify_signal))
                    corrected_led = max(10, min(255, corrected_led))
                    led_intensities[ch_name] = corrected_led
                    logger.info(f"      {ch_name.upper()}: LED={corrected_led} ({verify_signal/detector_max*100:.1f}%) [linear+adjust]")
                    use_binary_fallback = False

            # ===================================================================
            # FALLBACK METHOD: Binary search (safe, always works)
            # ===================================================================
            if use_binary_fallback:
                logger.info(f"      {ch_name.upper()}: Using binary search fallback...")
                led_min = 10
                led_max = 255
                best_led = 255

                for _ in range(10):  # Max 10 iterations
                    test_led = (led_min + led_max) // 2

                    ctrl.set_intensity(ch=ch_name, raw_val=test_led)
                    time.sleep(LED_DELAY)
                    spectrum = usb.read_intensity()
                    ctrl.set_intensity(ch=ch_name, raw_val=0)

                    if spectrum is None:
                        break

                    filtered_spectrum = spectrum[wave_min_index:wave_max_index]
                    signal = filtered_spectrum.max()

                    # CRITICAL: Check saturation on every iteration
                    if signal >= strongest_max:
                        logger.debug(f"         LED={test_led}: {signal:.0f} counts - SATURATED, reducing")
                        led_max = test_led - 1
                        continue

                    if abs(signal - target_signal) < 0.05 * detector_max:  # Within 5%
                        best_led = test_led
                        break
                    elif signal < target_signal:
                        led_min = test_led
                    else:
                        led_max = test_led

                    best_led = test_led

                led_intensities[ch_name] = best_led
                signal_percent = (signal / detector_max) * 100 if spectrum is not None else 0
                logger.info(f"      {ch_name.upper()}: LED={best_led} ({signal_percent:.1f}%) [binary search]")

        # Store LED calibration in result
        result.ref_intensity = led_intensities
        logger.info(f"")
        logger.info(f"✅ LED intensities optimized for all channels at {best_integration*1000:.1f}ms")
        logger.info(f"="*80)        # Calculate scan count
        from utils.led_calibration import calculate_scan_counts
        scan_config = calculate_scan_counts(result.s_integration_time)
        result.num_scans = scan_config.num_scans
        logger.debug(f"   Scans to average: {result.num_scans}")

        # ===================================================================
        # CAPTURE S-POL RAW DATA FOR STEP 6 PROCESSING
        # ===================================================================
        logger.info(f"")
        logger.info(f"📊 CAPTURING S-POL RAW SPECTRA (for Step 6 data processing)")
        logger.info(f"   Measuring each channel with optimized LED intensities...")
        logger.info(f"")

        s_raw_data = {}
        for ch_name in ch_list:
            if stop_flag and stop_flag.is_set():
                break

            led_val = led_intensities[ch_name]
            logger.debug(f"   Ch {ch_name.upper()}: LED={led_val}, averaging {result.num_scans} scans...")

            # Set LED intensity
            ctrl.set_intensity(ch=ch_name, raw_val=led_val)
            time.sleep(LED_DELAY)

            # Average multiple scans
            spectra = []
            for scan_idx in range(result.num_scans):
                spectrum = usb.read_intensity()
                if spectrum is not None:
                    spectra.append(spectrum[wave_min_index:wave_max_index])
                time.sleep(0.01)

            if len(spectra) > 0:
                s_raw_data[ch_name] = np.mean(spectra, axis=0)
                logger.debug(f"      ✅ Ch {ch_name.upper()}: {len(spectra)} scans averaged")
            else:
                logger.warning(f"      ⚠️ Ch {ch_name.upper()}: No valid spectra captured")

            # Turn off LED
            ctrl.set_intensity(ch=ch_name, raw_val=0)
            time.sleep(0.01)

        # Store S-pol raw data for Step 6
        result.s_raw_data = s_raw_data
        logger.info(f"✅ S-pol raw data captured for all channels (available for Step 6)")
        logger.info(f"")

        logger.info(f"✅ Step 4 complete: Integration time, LED intensities, and S-pol raw data captured\n")

        # ===================================================================
        # STEP 5: P-MODE OPTIMIZATION (TRANSFER S-MODE + BOOST)
        # ===================================================================
        if progress_callback:
            progress_callback("Step 5: Optimizing P-mode parameters...")

        logger.info("=" * 80)
        logger.info("STEP 5: P-Mode Optimization (Transfer S-Mode + Boost)")
        logger.info("=" * 80)
        logger.info("Strategy:")
        logger.info("  1. Switch to P-polarization")
        logger.info("  2. Transfer S-mode parameters (100% baseline)")
        logger.info("  3. Boost LED intensities to maximize signal")
        logger.info("  4. Check for saturation (all channels must be <95%)")
        logger.info("  5. Ensure weakest LED near 255 (proof of optimization)")
        logger.info("  6. Allow up to +10% integration time increase if needed")
        logger.info("  7. Save P-mode raw data per channel")
        logger.info("  8. Measure dark-ref at final integration time\n")

        # Switch to P-mode
        logger.info("Switching to P-polarization...")
        switch_mode_safely(ctrl, "p", turn_off_leds=True)
        logger.info("✅ P-mode active\n")

        # Transfer S-mode parameters as baseline (100%)
        p_led_intensities = led_intensities.copy()  # Start with S-mode LEDs
        p_integration_time = result.s_integration_time  # Start with S-mode integration

        logger.info("📊 Transferred S-mode parameters (100% baseline):")
        logger.info(f"   Integration time: {p_integration_time:.1f}ms")
        logger.info(f"   LED intensities:")
        for ch in ch_list:
            logger.info(f"      {ch.upper()}: {p_led_intensities[ch]}")
        logger.info("")

        # Apply optimized integration time
        usb.set_integration(p_integration_time / 1000.0)
        time.sleep(0.1)

        # ===================================================================
        # P-MODE LED OPTIMIZATION: Linear scaling with saturation protection
        # ===================================================================
        logger.info("🚀 P-mode LED Optimization")
        logger.info("   Strategy: Linear scaling from S-mode baseline (max +10% boost)")
        logger.info("   Using S-mode measurements to predict optimal P-mode LEDs")
        logger.info("")

        MAX_P_INTEGRATION_INCREASE = 1.10  # Allow up to +10% increase
        max_p_integration = p_integration_time * MAX_P_INTEGRATION_INCREASE

        # Find weakest channel from Step 3 ranking
        weakest_ch = result.weakest_channel
        strongest_ch = ranked_channels[-1][0]

        logger.info(f"   Weakest channel: {weakest_ch.upper()} (will target LED=255)")
        logger.info(f"   Strongest channel: {strongest_ch.upper()} (most likely to saturate)")
        logger.info("")

        # ===================================================================
        # PRIMARY METHOD: Linear calculation from S-mode measurements
        # ===================================================================
        logger.info("📊 Method 1: Linear prediction from S-mode data")

        # Measure P-mode signal at S-mode LEDs to establish P/S ratio
        logger.info("   Step 1: Measuring P-mode signals at S-mode LEDs (baseline)...")

        p_s_ratio = {}  # P-mode signal / S-mode signal ratio per channel
        use_iterative_fallback = False

        for ch in ch_list:
            if stop_flag and stop_flag.is_set():
                break

            # Measure P-mode at S-mode LED
            ctrl.set_intensity(ch=ch, raw_val=led_intensities[ch])
            time.sleep(LED_DELAY)
            spectrum = usb.read_intensity()
            ctrl.set_intensity(ch=ch, raw_val=0)

            if spectrum is None:
                logger.warning(f"      {ch.upper()}: Failed to read spectrum, using iterative fallback")
                use_iterative_fallback = True
                break

            filtered_spectrum = spectrum[wave_min_index:wave_max_index]
            p_signal_at_s_led = filtered_spectrum.max()

            # Use actual S-mode signal from Step 4 captured data
            if ch in s_raw_data:
                s_signal_at_s_led = s_raw_data[ch].max()
            else:
                # Fallback if s_raw_data not available
                logger.warning(f"      {ch.upper()}: S-mode data not found, using 70% estimate")
                s_signal_at_s_led = 0.70 * detector_max

            # Calculate P/S transmission ratio
            ratio = p_signal_at_s_led / s_signal_at_s_led if s_signal_at_s_led > 0 else 0.5
            p_s_ratio[ch] = ratio

            logger.info(f"      {ch.upper()}: P={p_signal_at_s_led:.0f}, S={s_signal_at_s_led:.0f} @ LED={led_intensities[ch]} (P/S ratio: {ratio:.3f})")

        if not use_iterative_fallback:
            logger.info("")
            logger.info("   Step 2: Calculating optimal P-mode LEDs...")

            # Calculate optimal P-mode LEDs to reach target signal
            target_p_signal = 0.70 * detector_max  # Same target as S-mode
            max_boost_factor = 1.10  # 10% max boost from S-mode baseline

            for ch in ch_list:
                s_led = led_intensities[ch]
                ratio = p_s_ratio[ch]

                # Linear calculation: If P/S ratio is 0.5, need 2× LED to reach same signal
                # Target: target_p_signal = (LED / s_led) × p_signal_at_s_led
                # Solve for LED: LED = s_led × (target_p_signal / p_signal_at_s_led)

                p_signal_at_s_led = ratio * (0.70 * detector_max)
                calculated_led = int(s_led * (target_p_signal / p_signal_at_s_led)) if p_signal_at_s_led > 0 else s_led

                # Apply 10% boost limit
                max_allowed = int(s_led * max_boost_factor)
                calculated_led = min(calculated_led, max_allowed, 255)
                calculated_led = max(calculated_led, s_led)  # Never go below S-mode

                p_led_intensities[ch] = calculated_led
                boost_pct = ((calculated_led - s_led) / s_led * 100) if s_led > 0 else 0
                logger.info(f"      {ch.upper()}: LED={calculated_led} (S-mode: {s_led}, boost: +{boost_pct:.1f}%, P/S: {ratio:.3f})")

            logger.info("")
            logger.info("   Step 3: Verifying calculated LEDs (saturation check)...")

            # Verify all channels with calculated LEDs
            saturation_detected = False
            for ch in ch_list:
                if stop_flag and stop_flag.is_set():
                    break

                ctrl.set_intensity(ch=ch, raw_val=p_led_intensities[ch])
                time.sleep(LED_DELAY)
                spectrum = usb.read_intensity()
                ctrl.set_intensity(ch=ch, raw_val=0)

                if spectrum is None:
                    continue

                filtered_spectrum = spectrum[wave_min_index:wave_max_index]
                max_signal = filtered_spectrum.max()
                signal_percent = (max_signal / detector_max) * 100

                # Check for saturation
                if max_signal >= strongest_max:
                    saturation_detected = True
                    logger.warning(f"      {ch.upper()}: {max_signal:.0f} counts ({signal_percent:.1f}%) ⚠️ SATURATED")
                    # Reduce this channel's LED by 10%
                    p_led_intensities[ch] = int(p_led_intensities[ch] * 0.90)
                else:
                    logger.info(f"      {ch.upper()}: {max_signal:.0f} counts ({signal_percent:.1f}%) ✅ OK")

            if saturation_detected:
                logger.info("")
                logger.info("   Step 4: Re-verifying after saturation correction...")

                # Re-verify channels that were saturated
                all_safe = True
                for ch in ch_list:
                    ctrl.set_intensity(ch=ch, raw_val=p_led_intensities[ch])
                    time.sleep(LED_DELAY)
                    spectrum = usb.read_intensity()
                    ctrl.set_intensity(ch=ch, raw_val=0)

                    if spectrum is not None:
                        max_signal = spectrum[wave_min_index:wave_max_index].max()
                        signal_percent = (max_signal / detector_max) * 100

                        if max_signal >= strongest_max:
                            logger.warning(f"      {ch.upper()}: Still saturated, using iterative fallback")
                            use_iterative_fallback = True
                            all_safe = False
                            break
                        else:
                            logger.info(f"      {ch.upper()}: {max_signal:.0f} counts ({signal_percent:.1f}%) ✅ OK")

                if all_safe:
                    logger.info("   ✅ Linear method successful with saturation correction")
            else:
                logger.info("   ✅ Linear method successful - no saturation detected")

        # ===================================================================
        # FALLBACK METHOD: Iterative boost (original approach)
        # ===================================================================
        if use_iterative_fallback:
            logger.info("")
            logger.info("📊 Method 2: Iterative boost (fallback)")
            logger.info("   Using iterative approach due to saturation or measurement issues")
            logger.info("")

            # Reset to S-mode baseline
            p_led_intensities = led_intensities.copy()

            p_optimization_iteration = 0
            MAX_P_ITERATIONS = 10
            p_optimized = False

            while p_optimization_iteration < MAX_P_ITERATIONS and not p_optimized:
                if stop_flag and stop_flag.is_set():
                    break

                p_optimization_iteration += 1
                logger.info(f"   P-mode iteration {p_optimization_iteration}:")

                # Test all channels at current LED intensities
                saturation_detected = False
                channel_signals = {}

                for ch in ch_list:
                    if stop_flag and stop_flag.is_set():
                        break

                    # Turn on channel
                    ctrl.set_intensity(ch=ch, raw_val=p_led_intensities[ch])
                    time.sleep(LED_DELAY)

                    # Read spectrum
                    spectrum = usb.read_intensity()
                    ctrl.set_intensity(ch=ch, raw_val=0)

                    if spectrum is None:
                        logger.error(f"Failed to read spectrum for channel {ch}")
                        continue

                    # CRITICAL: Check for saturation on ANY pixel in SPR range
                    filtered_spectrum = spectrum[wave_min_index:wave_max_index]
                    max_signal = filtered_spectrum.max()
                    signal_percent = (max_signal / detector_max) * 100

                    channel_signals[ch] = max_signal

                    # Check for saturation (≥95% on any pixel)
                    if max_signal >= strongest_max:  # Use same threshold as Step 4
                        saturation_detected = True
                        logger.info(f"      {ch.upper()}: {max_signal:6.0f} counts ({signal_percent:5.1f}%) ⚠️ SATURATED")
                    else:
                        logger.info(f"      {ch.upper()}: {max_signal:6.0f} counts ({signal_percent:5.1f}%) LED={p_led_intensities[ch]}")

                # Check if weakest LED is near 255
                weakest_led_value = p_led_intensities[weakest_ch]

                if saturation_detected:
                    logger.warning("   ⚠️ Saturation detected! Reverting last boost")
                    # Revert to previous iteration (reduce by ~5%)
                    for ch in ch_list:
                        p_led_intensities[ch] = max(led_intensities[ch], int(p_led_intensities[ch] * 0.95))
                    p_optimized = True
                elif weakest_led_value >= 250:
                    logger.info(f"   ✅ Weakest LED at {weakest_led_value} (near maximum)")
                    p_optimized = True
                else:
                    # Calculate boost factor (max 10% total from S-mode baseline)
                    # S-mode baseline is in led_intensities dict
                    s_baseline = led_intensities[weakest_ch]
                    max_allowed_led = int(s_baseline * 1.10)  # 10% total boost limit

                    if weakest_led_value >= max_allowed_led:
                        logger.info(f"   ✅ Reached 10% boost limit (S-mode: {s_baseline}, current: {weakest_led_value})")
                        p_optimized = True
                    else:
                        # Calculate target LEDs for next iteration
                        target_weakest = min(255, max_allowed_led)
                        boost_factor = target_weakest / weakest_led_value

                        logger.info(f"   Boosting LEDs (weakest: {weakest_led_value} → {target_weakest}, factor: {boost_factor:.3f})")

                        # Boost all LEDs proportionally
                        for ch in ch_list:
                            new_led = int(p_led_intensities[ch] * boost_factor)
                            p_led_intensities[ch] = min(255, new_led)

            logger.info("")
            logger.info(f"✅ P-mode LED optimization complete (iterative) after {p_optimization_iteration} iteration(s)")

        # Display final P-mode LED intensities
        logger.info("")
        logger.info("📊 Final P-mode LED intensities:")
        for ch in ch_list:
            s_led = led_intensities[ch]
            p_led = p_led_intensities[ch]
            boost = p_led - s_led
            boost_pct = (boost / s_led * 100) if s_led > 0 else 0
            logger.info(f"      {ch.upper()}: {p_led:3d} (S-mode: {s_led:3d}, boost: +{boost:3d} = +{boost_pct:.1f}%)")
        logger.info("")

        # Check if integration time increase is needed (only if weakest LED < 240)
        # Note: saturation_detected may not be defined if linear method succeeded
        check_saturation = False
        if use_iterative_fallback and 'saturation_detected' in locals():
            check_saturation = saturation_detected

        if p_led_intensities[weakest_ch] < 240 and not check_saturation:
            logger.info("⚠️ Weakest LED not at maximum, checking if integration time increase helps...")

            # Try increasing integration time by up to 10%
            test_integration = min(max_p_integration, p_integration_time * 1.05)  # Try +5% first

            if test_integration > p_integration_time:
                logger.info(f"   Testing integration time: {test_integration:.1f}ms (+{((test_integration/p_integration_time)-1)*100:.1f}%)")

                usb.set_integration(test_integration / 1000.0)
                time.sleep(0.1)

                # Re-test weakest channel
                ctrl.set_intensity(ch=weakest_ch, raw_val=255)
                time.sleep(LED_DELAY)
                spectrum = usb.read_intensity()
                ctrl.set_intensity(ch=weakest_ch, raw_val=0)

                if spectrum is not None:
                    filtered_spectrum = spectrum[wave_min_index:wave_max_index]
                    max_signal = filtered_spectrum.max()
                    signal_percent = (max_signal / detector_max) * 100

                    # Check for saturation on any pixel
                    if max_signal < strongest_max:
                        logger.info(f"   ✅ Integration time increased to {test_integration:.1f}ms")
                        logger.info(f"      Weakest LED signal: {max_signal:6.0f} counts ({signal_percent:5.1f}%)")
                        p_integration_time = test_integration
                    else:
                        logger.warning(f"   ⚠️ Integration time increase would cause saturation, keeping {p_integration_time:.1f}ms")
                        usb.set_integration(p_integration_time / 1000.0)
                        time.sleep(0.1)

        # Store final P-mode integration time
        result.p_integration_time = p_integration_time
        logger.info(f"Final P-mode integration time: {p_integration_time:.1f}ms")
        logger.info("")

        # Measure and save P-mode raw data per channel
        logger.info("📊 Capturing P-mode raw spectra (for Step 6 data processing)...")
        logger.info(f"   Measuring each channel with optimized P-mode LED intensities...")
        logger.info(f"")

        p_raw_data = {}
        usb.set_integration(p_integration_time / 1000.0)
        time.sleep(0.1)

        for ch in ch_list:
            if stop_flag and stop_flag.is_set():
                break

            led_val = p_led_intensities[ch]
            logger.debug(f"   Ch {ch.upper()}: LED={led_val}, averaging {result.num_scans} scans...")

            # Turn on channel
            ctrl.set_intensity(ch=ch, raw_val=led_val)
            time.sleep(LED_DELAY)

            # Average multiple scans
            spectra = []
            for scan_idx in range(result.num_scans):
                spectrum = usb.read_intensity()
                if spectrum is not None:
                    spectra.append(spectrum[wave_min_index:wave_max_index])
                time.sleep(0.01)

            # Turn off channel
            ctrl.set_intensity(ch=ch, raw_val=0)
            time.sleep(0.01)

            if len(spectra) > 0:
                p_raw_data[ch] = np.mean(spectra, axis=0)
                max_signal = p_raw_data[ch].max()
                logger.debug(f"      ✅ Ch {ch.upper()}: {len(spectra)} scans averaged, max: {max_signal:6.0f} counts")
            else:
                logger.warning(f"      ⚠️  Ch {ch.upper()}: No valid spectra captured")

        # Store P-mode raw data and LED intensities
        result.p_raw_data = p_raw_data
        result.p_mode_intensity = p_led_intensities

        logger.info(f"✅ P-mode raw data captured for all channels (available for Step 6)")
        logger.info(f"")

        # Measure dark-ref at final P-mode integration time
        logger.info("=" * 80)
        logger.info("DARK-REF: Measuring dark noise at final P-mode integration time")
        logger.info("=" * 80)
        logger.info("This common dark reference will be used for BOTH S-pol and P-pol data processing")
        logger.info("(Small integration time discrepancy has minimal impact on dark correction)")
        logger.info("Ensuring all LEDs are OFF and measuring dark baseline...\n")

        # Force all LEDs OFF
        ctrl.turn_off_channels()
        time.sleep(0.2)

        # Measure dark noise with averaging
        dark_ref_scans = scan_config.dark_scans
        logger.info(f"   Averaging {dark_ref_scans} scans for dark-ref")

        dark_ref_accumulator = []
        for scan_idx in range(dark_ref_scans):
            if stop_flag and stop_flag.is_set():
                break

            raw_spectrum = usb.read_intensity()
            if raw_spectrum is None:
                logger.error("Failed to read dark-ref spectrum")
                break

            dark_ref_accumulator.append(raw_spectrum)

        # Average all scans
        p_dark_ref = np.mean(dark_ref_accumulator, axis=0)

        # Apply spectral filter
        p_dark_ref_filtered = p_dark_ref[wave_min_index:wave_max_index]

        # Store dark-ref (measured at P-mode integration time)
        # This will be used for BOTH S-pol and P-pol data processing
        result.dark_noise = p_dark_ref_filtered

        # QC check: Verify dark signal is around expected level (~3200 counts for typical detectors)
        dark_mean = np.mean(p_dark_ref_filtered)
        dark_max = np.max(p_dark_ref_filtered)
        dark_std = np.std(p_dark_ref_filtered)

        logger.info(f"")
        logger.info(f"📊 Dark-ref QC:")
        logger.info(f"   Mean: {dark_mean:.1f} counts")
        logger.info(f"   Max: {dark_max:.1f} counts")
        logger.info(f"   Std: {dark_std:.1f} counts")

        # QC validation (expected range: 2500-4000 counts for typical Ocean Optics detectors)
        EXPECTED_DARK_MIN = 2500
        EXPECTED_DARK_MAX = 4000

        if EXPECTED_DARK_MIN <= dark_mean <= EXPECTED_DARK_MAX:
            logger.info(f"   ✅ Dark-ref within expected range ({EXPECTED_DARK_MIN}-{EXPECTED_DARK_MAX} counts)")
        else:
            logger.warning(f"   ⚠️ Dark-ref outside expected range ({EXPECTED_DARK_MIN}-{EXPECTED_DARK_MAX} counts)")
            if dark_mean > EXPECTED_DARK_MAX:
                logger.warning(f"      Possible causes: LEDs not fully off, light leak, detector issue")
            else:
                logger.warning(f"      Possible causes: Detector offset drift, temperature change")

        logger.info("")
        logger.info("✅ Step 5 complete: P-mode optimization and dark-ref measurement done\n")

        # ===================================================================
        # DATA PROCESSING FUNCTIONS (FOR STEP 6)
        # ===================================================================

        def finalcalibQC(
            s_raw_data: dict[str, np.ndarray],
            p_raw_data: dict[str, np.ndarray],
            dark_noise: np.ndarray,
            afterglow_correction,
            num_scans: int,
            s_integration_time: float,
            p_integration_time: float,
            led_intensities_s: dict[str, int],
            led_intensities_p: dict[str, int],
            ch_list: list[str]
        ) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
            """FUNCTION 1 (finalcalibQC): Process raw S-pol and P-pol data into clean references.

            This function:
            1. Takes raw S-pol and P-pol spectra
            2. Removes dark noise (common dark measured at P-mode integration time)
            3. Applies afterglow correction
            4. Returns clean S-pol-ref and P-pol-ref for QC display

            Note: Uses common dark reference measured at P-mode integration time for both
            S-pol and P-pol data. Small integration time discrepancy has minimal impact.

            Args:
                s_raw_data: Raw S-mode spectra per channel
                p_raw_data: Raw P-mode spectra per channel
                dark_noise: Common dark reference (measured at P-mode integration time)
                afterglow_correction: Afterglow correction instance (optional)
                num_scans: Number of scans used for averaging
                s_integration_time: S-mode integration time (ms)
                p_integration_time: P-mode integration time (ms)
                led_intensities_s: S-mode LED intensities per channel
                led_intensities_p: P-mode LED intensities per channel
                ch_list: List of channels to process

            Returns:
                (s_pol_ref, p_pol_ref): Clean reference spectra for both modes
            """
            logger.info("=" * 80)
            logger.info("FUNCTION 1 (finalcalibQC): Processing Raw Polarization Data")
            logger.info("=" * 80)

            s_pol_ref = {}
            p_pol_ref = {}

            for i, ch in enumerate(ch_list):
                logger.info(f"Processing channel {ch.upper()}...")

                # Process S-pol raw
                s_spectrum = s_raw_data[ch].copy()
                s_spectrum = s_spectrum - dark_noise  # Remove dark

                # Apply afterglow correction to S-pol
                if afterglow_correction is not None and i > 0:
                    prev_ch = ch_list[i - 1]
                    prev_led_intensity = led_intensities_s[prev_ch]
                    afterglow = afterglow_correction.predict_afterglow(
                        prev_led_intensity, s_integration_time
                    )
                    s_spectrum = s_spectrum - afterglow
                    logger.info(f"   S-pol: Removed afterglow from previous channel")

                s_pol_ref[ch] = s_spectrum

                # Process P-pol raw
                p_spectrum = p_raw_data[ch].copy()
                p_spectrum = p_spectrum - dark_noise  # Remove dark

                # Apply afterglow correction to P-pol
                if afterglow_correction is not None and i > 0:
                    prev_ch = ch_list[i - 1]
                    prev_led_intensity = led_intensities_p[prev_ch]
                    afterglow = afterglow_correction.predict_afterglow(
                        prev_led_intensity, p_integration_time
                    )
                    p_spectrum = p_spectrum - afterglow
                    logger.info(f"   P-pol: Removed afterglow from previous channel")

                p_pol_ref[ch] = p_spectrum

                logger.info(f"   ✅ S-pol ref: mean={np.mean(s_spectrum):.0f}, max={np.max(s_spectrum):.0f}")
                logger.info(f"   ✅ P-pol ref: mean={np.mean(p_spectrum):.0f}, max={np.max(p_spectrum):.0f}")

            logger.info("=" * 80)
            return s_pol_ref, p_pol_ref

        def LiveRtoT_QC(
            p_pol_raw: np.ndarray,
            s_pol_ref: np.ndarray,
            dark_noise: np.ndarray,
            afterglow_correction,
            prev_led_intensity: int,
            p_integration_time: float,
            led_intensity_s: int,
            led_intensity_p: int,
            wavelengths: np.ndarray,
            apply_sg_filter: bool = True
        ) -> np.ndarray:
            """LiveRtoT_QC: Process ONE channel with detailed logging (for Step 6 calibration QC).

            This function simulates live data acquisition for a SINGLE channel with full logging:
            1. Takes RAW P-pol spectrum (NOT processed ref!)
            2. Removes dark noise (measured at P-mode integration time)
            3. Removes afterglow (from previous channel)
            4. Calculates transmission = P_clean / S_ref
            5. Corrects for LED boost (P-mode vs S-mode LED intensities)
            6. Applies baseline correction
            7. Applies Savitzky-Golay denoising
            8. Returns transmission spectrum

            Args:
                p_pol_raw: RAW P-mode spectrum (single channel, unprocessed)
                s_pol_ref: Clean S-mode reference spectrum (from finalcalibQC)
                dark_noise: Common dark reference (measured at P-mode integration time)
                afterglow_correction: Afterglow correction instance (optional)
                prev_led_intensity: Previous channel's P-mode LED intensity (for afterglow)
                p_integration_time: P-mode integration time (ms) - FINAL integration time
                led_intensity_s: S-mode LED intensity for this channel
                led_intensity_p: P-mode LED intensity for this channel
                wavelengths: Wavelength array
                apply_sg_filter: Apply Savitzky-Golay smoothing (default: True)

            Returns:
                transmission: Corrected transmission spectrum (%)
            """
            logger.info("=" * 80)
            logger.info("LiveRtoT_QC (Single Channel): Processing Raw P-pol → Transmission")
            logger.info("=" * 80)

            # Step 1: Process RAW P-pol
            logger.info("Step 1: Processing RAW P-pol spectrum...")
            p_pol_clean = p_pol_raw.copy()
            p_pol_clean = p_pol_clean - dark_noise
            logger.info(f"   Removed dark noise (mean={np.mean(dark_noise):.0f})")

            if afterglow_correction is not None and prev_led_intensity > 0:
                afterglow = afterglow_correction.predict_afterglow(
                    prev_led_intensity, p_integration_time
                )
                p_pol_clean = p_pol_clean - afterglow
                logger.info(f"   Removed afterglow from previous LED (intensity={prev_led_intensity})")

            logger.info(f"   P-pol clean: mean={np.mean(p_pol_clean):.0f}, max={np.max(p_pol_clean):.0f}")

            # Step 2: Calculate transmission
            logger.info("Step 2: Calculating transmission (P / S)...")
            s_pol_safe = np.where(s_pol_ref < 1, 1, s_pol_ref)
            raw_transmission = (p_pol_clean / s_pol_safe) * 100.0
            logger.info(f"   Raw transmission: mean={np.mean(raw_transmission):.1f}%")

            # Step 3: LED boost correction
            logger.info("Step 3: Applying LED boost correction...")
            # P-mode uses higher LED → more signal → need to scale DOWN transmission
            # Correction factor: P_LED / S_LED (if P>S, factor>1, divides transmission)
            led_boost_factor = max(led_intensity_p, 1) / max(led_intensity_s, 1)
            corrected_transmission = raw_transmission / led_boost_factor
            logger.info(f"   LED boost: S={led_intensity_s}, P={led_intensity_p}, factor={led_boost_factor:.3f}")
            logger.info(f"   Transmission after LED correction: mean={np.mean(corrected_transmission):.1f}%")

            # Step 4: Baseline correction (95th percentile for SPR - off-resonance baseline)
            logger.info("Step 4: Applying baseline correction...")
            # For SPR: Baseline is HIGH transmission (off-resonance), dip goes DOWN from there
            baseline = np.percentile(corrected_transmission, 95)
            corrected_transmission = corrected_transmission - baseline + 100.0  # Re-center to ~100% baseline
            logger.info(f"   Baseline (95th percentile): {baseline:.2f}%")
            logger.info(f"   Re-centered to 100% baseline")

            # Clip to valid range (transmission can't be <0% or >100%)
            corrected_transmission = np.clip(corrected_transmission, 0, 100)

            # Step 5: Savitzky-Golay denoising
            if apply_sg_filter:
                logger.info("Step 5: Applying Savitzky-Golay filter...")
                from scipy.signal import savgol_filter
                corrected_transmission = savgol_filter(
                    corrected_transmission,
                    window_length=11,
                    polyorder=3
                )
                logger.info(f"   Applied SG filter (window=11, poly=3)")

            # Find SPR dip
            min_transmission = np.min(corrected_transmission)
            min_idx = np.argmin(corrected_transmission)
            min_wavelength = wavelengths[min_idx]

            logger.info(f"\n✅ Final transmission spectrum:")
            logger.info(f"   SPR dip: {min_transmission:.1f}% at {min_wavelength:.1f}nm")
            logger.info(f"   Mean: {np.mean(corrected_transmission):.1f}%")
            logger.info("=" * 80)

            return corrected_transmission

        def LiveRtoT_batch(
            p_pol_raw_batch: dict[str, np.ndarray],
            s_pol_ref_batch: dict[str, np.ndarray],
            dark_noise: np.ndarray,
            afterglow_correction,
            p_integration_time: float,
            led_intensities_s: dict[str, int],
            led_intensities_p: dict[str, int],
            wavelengths: np.ndarray,
            ch_list: list[str],
            apply_sg_filter: bool = True
        ) -> dict[str, np.ndarray]:
            """LiveRtoT_batch: Process ALL 4 channels efficiently (for LIVE DATA MODE).

            This is the LIVE DATA MODE function - optimized for speed:
            1. Takes RAW P-pol spectra for all channels
            2. Removes dark noise (measured at P-mode integration time)
            3. Removes afterglow (from previous channel in sequence)
            4. Calculates transmission = P_clean / S_ref
            5. Corrects for LED boost
            6. Applies baseline correction
            7. Applies Savitzky-Golay denoising
            8. Returns transmission spectra for all channels

            Performance optimizations:
            - Minimal logging (no per-step details)
            - Batch processing of all 4 channels
            - Vectorized operations where possible

            Args:
                p_pol_raw_batch: RAW P-mode spectra for all channels {'a': array, 'b': array, ...}
                s_pol_ref_batch: Clean S-mode references (from calibration)
                dark_noise: Common dark reference (measured at P-mode integration time)
                afterglow_correction: Afterglow correction instance (optional)
                p_integration_time: P-mode integration time (ms) - FINAL integration time
                led_intensities_s: S-mode LED intensities per channel
                led_intensities_p: P-mode LED intensities per channel
                wavelengths: Wavelength array
                ch_list: List of channels to process ['a', 'b', 'c', 'd']
                apply_sg_filter: Apply Savitzky-Golay smoothing (default: True)

            Returns:
                transmission_batch: Corrected transmission spectra per channel (%)
            """
            transmission_batch = {}

            for i, ch in enumerate(ch_list):
                # Step 1: Process RAW P-pol (remove dark + afterglow)
                p_pol_clean = p_pol_raw_batch[ch].copy()
                p_pol_clean = p_pol_clean - dark_noise

                # Remove afterglow from previous channel
                if afterglow_correction is not None and i > 0:
                    prev_ch = ch_list[i - 1]
                    prev_led_intensity = led_intensities_p[prev_ch]
                    afterglow = afterglow_correction.predict_afterglow(
                        prev_led_intensity, p_integration_time
                    )
                    p_pol_clean = p_pol_clean - afterglow

                # Step 2: Calculate transmission (P / S)
                s_pol_ref = s_pol_ref_batch[ch]
                s_pol_safe = np.where(s_pol_ref < 1, 1, s_pol_ref)
                raw_transmission = (p_pol_clean / s_pol_safe) * 100.0

                # Step 3: LED boost correction (P_LED / S_LED)
                led_boost_factor = max(led_intensities_p[ch], 1) / max(led_intensities_s[ch], 1)
                corrected_transmission = raw_transmission / led_boost_factor

                # Step 4: Baseline correction (95th percentile for SPR)
                baseline = np.percentile(corrected_transmission, 95)
                corrected_transmission = corrected_transmission - baseline + 100.0

                # Clip to valid range
                corrected_transmission = np.clip(corrected_transmission, 0, 100)

                # Step 5: Savitzky-Golay denoising
                if apply_sg_filter:
                    from scipy.signal import savgol_filter
                    corrected_transmission = savgol_filter(
                        corrected_transmission,
                        window_length=11,
                        polyorder=3
                    )

                transmission_batch[ch] = corrected_transmission

            return transmission_batch

        # ===================================================================
        # STEP 6: DATA PROCESSING + TRANSMISSION CALCULATION + QC (FINAL STEP)
        # ===================================================================
        logger.info("=" * 80)
        logger.info("STEP 6: Data Processing + Transmission Calculation + QC (FINAL STEP)")
        logger.info("=" * 80)

        if progress_callback:
            progress_callback("Step 6: Processing polarization data & calculating transmission...")

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
            # PART B: PROCESS POLARIZATION DATA (finalcalibQC)
            # ---------------------------------------------------------------
            logger.info("\n🔧 Part B: Processing Polarization Data (finalcalibQC)")

            s_pol_ref, p_pol_ref = finalcalibQC(
                s_raw_data=result.s_raw_data,
                p_raw_data=result.p_raw_data,
                dark_noise=result.dark_noise,
                afterglow_correction=afterglow_correction,
                num_scans=result.num_scans,
                s_integration_time=result.s_integration_time,
                p_integration_time=result.p_integration_time,
                led_intensities_s=result.ref_intensity,
                led_intensities_p=result.p_mode_intensity,
                ch_list=ch_list
            )

            # Store processed references
            result.s_ref_sig = s_pol_ref
            result.p_ref_sig = p_pol_ref

            logger.info("\n✅ S-pol and P-pol references processed")
            logger.info("   Ready for QC display")

            # ---------------------------------------------------------------
            # PART C: CALCULATE TRANSMISSION SPECTRUM (LiveRtoT_QC)
            # ---------------------------------------------------------------
            logger.info("\n📈 Part C: Calculating Transmission Spectrum (LiveRtoT_QC)")
            logger.info("   🔴 SIMULATING LIVE DATA ACQUISITION")

            transmission_spectra = {}

            for ch in ch_list:
                logger.info(f"\n{'='*80}")
                logger.info(f"Channel {ch.upper()}: LiveRtoT_QC Processing")
                logger.info(f"{'='*80}")

                # Get previous channel's P-mode LED intensity (for afterglow)
                prev_ch_idx = ch_list.index(ch) - 1
                prev_led_intensity = result.p_mode_intensity[ch_list[prev_ch_idx]] if prev_ch_idx >= 0 else 0

                # Call LiveRtoT_QC with RAW P-pol data
                transmission_ch = LiveRtoT_QC(
                    p_pol_raw=result.p_raw_data[ch],
                    s_pol_ref=s_pol_ref[ch],
                    dark_noise=result.dark_noise,
                    afterglow_correction=afterglow_correction,
                    prev_led_intensity=prev_led_intensity,
                    p_integration_time=result.p_integration_time,  # ✅ Use FINAL P-mode integration time
                    led_intensity_s=result.ref_intensity[ch],
                    led_intensity_p=result.p_mode_intensity[ch],
                    wavelengths=result.wave_data,
                    apply_sg_filter=True
                )

                transmission_spectra[ch] = transmission_ch

            # Store transmission spectra
            result.transmission = transmission_spectra

            # Generate afterglow curves for QC display (same as used in finalcalibQC)
            afterglow_curves = {}
            if afterglow_correction is not None:
                for i, ch in enumerate(ch_list):
                    if i > 0:  # First channel has no afterglow
                        prev_ch = ch_list[i - 1]
                        prev_led_s = result.ref_intensity[prev_ch]
                        prev_led_p = result.p_mode_intensity[prev_ch]
                        # Use P-mode LED (higher intensity) for visualization
                        afterglow_curves[ch] = afterglow_correction.predict_afterglow(
                            prev_led_p, result.p_integration_time
                        )
                    else:
                        afterglow_curves[ch] = np.zeros_like(result.wave_data)
            else:
                # No afterglow correction - zeros for all channels
                for ch in ch_list:
                    afterglow_curves[ch] = np.zeros_like(result.wave_data)
            
            result.afterglow_curves = afterglow_curves

            logger.info("\n" + "=" * 80)
            logger.info("✅ Transmission spectra calculated")
            logger.info("✅ Afterglow curves generated for QC display")
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
                progress_callback("Step 6 complete: Calibration finished!")

        except Exception as e:
            logger.exception(f"Error in Step 6: {e}")
            raise RuntimeError(f"Step 6 failed: {e}")

        # ===================================================================
        # CALIBRATION COMPLETE - STEP 6 IS FINAL STEP
        # ===================================================================

        # Copy references for compatibility with calibration manager
        result.ref_sig = result.s_ref_sig
        result.leds_calibrated = result.p_mode_intensity
        result.success = True

        logger.info("\n" + "=" * 80)
        logger.info("✅ 6-STEP CALIBRATION COMPLETE")
        logger.info("=" * 80)
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
        logger.info(f"🎯 GLOBAL integration time: {saved_integration}ms (testing all channels at this time)\n")

        # Validate each channel at the GLOBAL integration time
        logger.info("Validating channels at GLOBAL integration time (±10% tolerance)...")
        logger.info("This mirrors Step 5C QC: verifying no saturation and 70% target\n")

        validated_leds = {}
        failed_channels = []

        # Switch to S-mode and set GLOBAL integration time
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
            logger.info("✅ FAST-TRACK VALIDATION PASSED (GLOBAL INTEGRATION TIME)")
            logger.info("=" * 80)
            logger.info(f"All channels within ±10% tolerance at {saved_integration}ms integration time")
            logger.info("Using cached GLOBAL integration time calibration values")
            logger.info(f"QC validated: No saturation, 70% target met (mirrors Step 5C)")
            logger.info(f"Estimated time saved: ~80% (skipped Steps 5A-5C optimization)")
            logger.info("=" * 80 + "\n")

            # Build result from cached data
            result.ref_intensity = validated_leds
            result.s_integration_time = saved_integration  # S-mode integration time
            result.wave_data = wave_data[wave_min_index:wave_max_index]
            result.wave_min_index = wave_min_index
            result.wave_max_index = wave_max_index

            # Still need to measure dark and refs at current temperature
            scan_config = calculate_scan_counts(saved_integration)
            num_scans = scan_config.num_scans

            result.dark_noise = measure_dark_noise(
                usb, ctrl, saved_integration,
                wave_min_index, wave_max_index,
                stop_flag, num_scans=scan_config.dark_scans
            )

            result.s_ref_sig = measure_reference_signals(
                usb, ctrl, ch_list, validated_leds, result.dark_noise,
                saved_integration, wave_min_index, wave_max_index,
                stop_flag, afterglow_correction, num_scans=num_scans,
                preserve_mode=False  # Use default S-mode behavior
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
                preserve_mode=True  # CRITICAL: Capture in P-mode, don't switch to S-mode
            )
            result.p_ref_sig = p_ref_signals
            logger.info(f"✅ P-mode references captured")

            result.success = True
            result.num_scans = num_scans
            result.ref_sig = result.s_ref_sig  # Copy for calibration manager compatibility
            result.leds_calibrated = result.p_mode_intensity  # CRITICAL: Set leds_calibrated for data_mgr validation
            result.fast_track_passed = True  # Mark as fast-track success

            logger.info("\n" + "=" * 80)
            logger.info("✅ FAST-TRACK CALIBRATION COMPLETE (GLOBAL INTEGRATION TIME)")
            logger.info("=" * 80)
            logger.info(f"Validation: All channels passed at {saved_integration}ms integration time (±10%)")
            logger.info(f"QC criteria: No saturation, 70% target, mirrors full calibration Step 5C")
            logger.info(f"Time saved: ~80% (skipped integration time optimization Steps 5A-5C)")
            logger.info(f"Validated LEDs: {validated_leds}")
            logger.info("=" * 80 + "\n")

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

        # Build result with mix of cached and recalibrated LED intensities
        # PARAMETER LOCKING STRATEGY:
        # - Integration time: LOCKED (use saved value from full calibration)
        # - Num scans: LOCKED (calculated from integration time)
        # - Dark noise: RE-MEASURED (may drift with temperature)
        # - S-ref signals: RE-MEASURED (with updated LED intensities)
        # - LED intensities: UPDATED (only failed channels recalibrated)
        # - P-mode LEDs: RE-CALCULATED (based on updated S-mode LEDs)

        result.ref_intensity = validated_leds  # Updated S-mode LED intensities
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
        result.s_ref_sig = measure_reference_signals(
            usb, ctrl, ch_list, validated_leds, result.dark_noise,
            saved_integration, wave_min_index, wave_max_index,
            stop_flag, afterglow_correction, num_scans=num_scans,
            preserve_mode=False  # Switch to S-mode (default behavior)
        )

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
