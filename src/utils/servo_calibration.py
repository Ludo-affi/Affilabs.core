"""Servo position calibration for circular polarizer using intelligent quadrant search.

This module provides efficient servo calibration for SPR systems with circular
polarizers. Uses a 3-phase quadrant search working in native servo units (0-255).

Key features:
- Native servo unit operation (0-255 PWM range)
- ROI-based measurement (600-670nm SPR resonance)
- Quadrant search: 5 coarse + refinement (~12 measurements total)
- 90 servo unit separation for circular polarizers
- LED verification and calibration
- Saturation detection and dark count validation
"""

import time
import numpy as np
from typing import Optional, Tuple, Dict
from utils.logger import logger
import time

# ============================================================================
# CONSTANTS
# ============================================================================

# Servo range (PWM units)
MIN_SERVO = 5           # Start of servo range (0-255 PWM units)
MAX_SERVO = 250         # End of servo range (0-255 PWM units)
SETTLING_TIME = 0.4     # Servo settling time (seconds) - increased for HS-55MG servo
MODE_SWITCH_TIME = 0.15 # Time to switch between S/P modes (seconds)
MEASUREMENT_AVERAGES = 3  # Number of measurements to average per position

# ROI for SPR resonance measurement (legacy single range retained for fallback)
ROI_MIN_WL = 600        # Minimum wavelength for SPR ROI (nm)
ROI_MAX_WL = 670        # Maximum wavelength for SPR ROI (nm)

# New multi-bucket ROI definition (three buckets)
ROI_BUCKETS = [
    (600, 620),
    (620, 640),
    (640, 660)
]

# Detector specifications
MAX_DETECTOR_COUNTS = 62000        # Flame-T maximum counts
SATURATION_THRESHOLD = 0.95        # Warn if above 95% of max
SERVO_CAL_TARGET_PERCENT = 0.30    # 30% of detector max for LED calibration


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def servo_to_degrees(servo_pos: int) -> int:
    """Convert servo position (0-255) to degrees for display purposes only."""
    return int(servo_pos * 180 / 255)


def degrees_to_servo(degrees: int) -> int:
    """Convert degrees to servo position (0-255) for controller commands."""
    return int(degrees * 255 / 180)


def _move_servo_to_angle(ctrl, angle: int, mode: str = 's', wait_time: float = 0.5) -> bool:
    """Move servo to specific angle for calibration scanning (CALIBRATION ONLY).

    ========================================================================
    FOR SERVO CALIBRATION WORKFLOW ONLY
    ========================================================================
    This function is used ONLY during servo calibration to scan different
    angles and find optimal S and P positions.

    Uses servo_move_calibration_only() which does NOT write to EEPROM.
    Results are saved to device_config.json after calibration completes.
    ========================================================================

    Args:
        ctrl: Controller instance
        angle: Target angle (0-180 degrees)
        mode: Mode to use ('s' or 'p')
        wait_time: Time to wait for servo movement

    Returns:
        bool: True if successful
    """
    try:
        # Use calibration-only move function (does not write EEPROM)
        if not ctrl.servo_move_calibration_only(s=angle, p=angle):
            logger.debug(f"servo_move_calibration_only retry may be needed for angle {angle}")

        time.sleep(0.05)

        if not ctrl.set_mode(mode):
            logger.debug(f"set_mode('{mode}') retry may be needed for angle {angle}")

        time.sleep(wait_time)
        return True

    except Exception as e:
        logger.error(f"Failed to move servo to {angle}°: {e}")
        return False


def get_roi_bucket_intensities(spectrum: np.ndarray, wavelengths: np.ndarray) -> list:
    """Return mean intensities for each defined ROI bucket.

    Args:
        spectrum: Full spectrum array
        wavelengths: Wavelength array

    Returns:
        list: Mean intensity per bucket (fallback to full spectrum mean if empty)
    """
    if wavelengths is None or len(wavelengths) != len(spectrum):
        # Fallback: treat all buckets as same (full spectrum mean)
        mean_val = float(spectrum.mean())
        return [mean_val] * len(ROI_BUCKETS)
    bucket_means = []
    for (lo, hi) in ROI_BUCKETS:
        mask = (wavelengths >= lo) & (wavelengths <= hi)
        sub = spectrum[mask]
        if len(sub) == 0:
            bucket_means.append(float(spectrum.mean()))
        else:
            bucket_means.append(float(sub.mean()))
    return bucket_means

def get_roi_intensity(spectrum: np.ndarray, wavelengths: np.ndarray) -> float:
    """Legacy single ROI mean (kept for backward compatibility)."""
    bucket_means = get_roi_bucket_intensities(spectrum, wavelengths)
    # Use average across all buckets as legacy equivalent
    return float(np.mean(bucket_means))


# ============================================================================
# LED CALIBRATION
# ============================================================================

def _calibrate_leds_for_servo(usb, ctrl, target_percent: float = SERVO_CAL_TARGET_PERCENT, allow_saturation: bool = True):
    """Calibrate LED intensities to target level for servo scanning.

    Uses binary search to find optimal intensity for each LED that achieves
    target signal level without saturation.

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper
        target_percent: Target as fraction of detector max (default 0.30 = 30%)

    Returns:
        dict: Calibrated intensities {'a': int, 'b': int, 'c': int, 'd': int}
    """
    logger.info("=" * 80)
    logger.info("LED CALIBRATION FOR SERVO SEARCH")
    logger.info("=" * 80)

    max_counts = getattr(usb, 'max_counts', MAX_DETECTOR_COUNTS)
    target_counts = int(max_counts * target_percent)
    saturation_limit = int(max_counts * SATURATION_THRESHOLD)

    logger.info(f"Target: {target_counts} counts ({int(target_percent*100)}% of detector max)")
    logger.info(f"Detector max: {max_counts} counts")
    logger.info(f"Reason: Lower target prevents saturation in S-mode (max transmission)")
    logger.info("=" * 80)

    calibrated_intensities = {}
    integration_time = 50  # ms - fixed integration time

    try:
        usb.set_integration(integration_time)
        time.sleep(0.1)

        for ch in ['a', 'b', 'c', 'd']:
            logger.info(f"Calibrating LED {ch.upper()}...")

            ctrl.turn_on_channel(ch)
            time.sleep(0.05)

            # Binary search for optimal intensity
            intensity_low = 10
            intensity_high = 255
            best_intensity = 64

            for _ in range(8):  # 8 iterations for precision
                intensity_mid = (intensity_low + intensity_high) // 2
                ctrl.set_intensity(ch, intensity_mid)
                time.sleep(0.1)

                spectrum = usb.read_intensity()
                if spectrum is None:
                    continue

                max_signal = float(spectrum.max())

                # Check for dark counts (LED not working)
                if max_signal < 3500:
                    logger.error(f"LED {ch.upper()} producing no light at intensity {intensity_mid} ({max_signal:.0f} counts)")
                    logger.error(f"Signal too close to dark counts (~3000) - LED not working!")
                    best_intensity = intensity_mid
                    break

                # Check for saturation
                if max_signal >= saturation_limit:
                    logger.warning(f"LED {ch.upper()} saturating at intensity {intensity_mid} ({max_signal:.0f} counts)")
                    if allow_saturation:
                        # Allow saturation to proceed; keep search but prefer current mid as best
                        best_intensity = intensity_mid
                    else:
                        logger.warning("Reducing intensity range to prevent saturation...")
                        intensity_high = intensity_mid - 1
                        if intensity_high < intensity_low:
                            logger.error(f"LED {ch.upper()} saturates even at low intensity! Using {intensity_low}")
                            best_intensity = intensity_low
                            break
                        continue

                # Adjust search range based on signal
                if max_signal < target_counts * 0.95:
                    intensity_low = intensity_mid + 1
                elif max_signal > target_counts * 1.05:
                    intensity_high = intensity_mid - 1
                else:
                    best_intensity = intensity_mid
                    break

                best_intensity = intensity_mid

            calibrated_intensities[ch] = best_intensity
            logger.info(f"  ✓ LED {ch.upper()}: intensity = {best_intensity}")

        logger.info("=" * 80)
        logger.info("✅ LED CALIBRATION COMPLETE")
        logger.info("=" * 80)

        return calibrated_intensities

    except Exception as e:
        logger.error(f"LED calibration failed: {e}")
        logger.warning("Falling back to default intensity (32)")
        return {'a': 32, 'b': 32, 'c': 32, 'd': 32}


def _restore_led_intensity(ctrl, original_intensities: dict):
    """Restore original LED intensities after servo calibration.

    Args:
        ctrl: Controller wrapper
        original_intensities: Dict of original LED intensities
    """
    logger.debug("Restoring original LED intensities...")
    try:
        for ch, intensity in original_intensities.items():
            ctrl.turn_on_channel(ch)
            ctrl.set_intensity(ch, intensity)
        time.sleep(0.2)
        logger.info("✅ LED intensities restored")
    except Exception as e:
        logger.warning(f"Could not restore LED intensities: {e}")


# ============================================================================
# QUADRANT SEARCH
# ============================================================================

def perform_quadrant_search_prod(usb, ctrl):
    """PRODUCTION: Perform intelligent quadrant search to find optimal S and P positions.

    Uses native servo units (0-255) throughout:
    1. LED verification and calibration
    2. Coarse 5-point quadrant search in S-mode (finds maximum first)
    3. Three-bucket ROI evaluation (600-620, 620-640, 640-660 nm)
    4. Best bucket selection based on maximum Δ(S-P)
    5. Three-stage refinement for S position (±28, ±7, ±3 servo units)
    6. P position = S ± 90 servo units, measures both, picks minimum
    7. Extinction ratio calculation: (S-P)/S in best bucket

    Total measurements: ~14 (vs 33+ for full sweep)
    S/P ratio: >2.5x typical for good SPR

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper

    Returns:
        Tuple of (s_pos_deg, p_pos_deg, extinction_ratio) or None if search fails
    """
    logger.info("=" * 80)
    logger.info("QUADRANT SEARCH FOR SERVO POSITIONS")
    logger.info("=" * 80)

    # Get wavelengths for ROI calculation
    # Retrieve wavelength array robustly (attribute names vary across wrappers)
    wavelengths = getattr(usb, 'wavelengths', None) or getattr(usb, '_wavelengths', None)
    multi_bucket_available = wavelengths is not None
    if not multi_bucket_available:
        logger.warning("Wavelength array unavailable → multi-bucket ROI disabled (fallback to full spectrum)")
    else:
        logger.info("Multi-bucket ROI enabled: " + ", ".join([f"{lo}-{hi}nm" for lo, hi in ROI_BUCKETS]))

    # STEP 1a: LED Communication Test
    logger.info("")
    logger.info("STEP 1a: LED Communication Test")
    logger.info("Measuring dark counts (LEDs off)...")

    try:
        ctrl.turn_off_channels()
        time.sleep(0.2)
        dark_spectrum = usb.read_intensity()
        if dark_spectrum is None:
            logger.error("❌ Failed to read dark spectrum from detector!")
            return None
        dark_counts = float(dark_spectrum.max())
        logger.info(f"Dark counts: {dark_counts:.0f}")
    except Exception as e:
        logger.error(f"❌ Dark measurement failed: {e}")
        return None

    # Test LED commands
    test_channel = 'b'
    logger.info(f"Testing LED {test_channel.upper()} commands...")

    try:
        enable_ok = ctrl.turn_on_channel(test_channel)
        logger.info(f"   Enable command response: {enable_ok}")
        time.sleep(0.1)

        intensity_ok = ctrl.set_intensity(test_channel, 50)
        logger.info(f"   Intensity command response: {intensity_ok}")
        time.sleep(0.2)

        test_spectrum = usb.read_intensity()
        if test_spectrum is None:
            logger.error("❌ Failed to read spectrum from detector!")
            return None

        test_signal = float(test_spectrum.max())
        signal_increase = test_signal - dark_counts
        logger.info(f"Signal with LED ON: {test_signal:.0f} counts")
        logger.info(f"Signal increase from dark: {signal_increase:.0f} counts")

        if signal_increase < 500:
            logger.error("❌ LED not producing light! Signal barely increased from dark counts")
            logger.error(f"   Dark: {dark_counts:.0f}, LED ON: {test_signal:.0f}, Increase: {signal_increase:.0f}")
            logger.error("   Possible causes: LED enable/intensity commands not working, hardware disconnected")
            return None

        logger.info(f"✓ LED commands working! {signal_increase:.0f} counts increase")
    except Exception as e:
        logger.error(f"❌ LED communication test failed: {e}")
        return None

    # STEP 1b: LED Calibration
    logger.info("")
    logger.info("STEP 1b: LED Calibration (low target for servo search)")
    calibrated_intensities = _calibrate_leds_for_servo(usb, ctrl)
    if calibrated_intensities is None:
        logger.error("❌ LED calibration returned None - cannot proceed")
        return None
    logger.info("")

    original_led_intensity = calibrated_intensities.copy()

    # Storage for all measurements
    all_positions = []
    all_intensities = []

    def measure_position(servo_pos: int, mode: str = 'p', buckets_for_stage: list = None) -> tuple:
        """Measure intensity at a servo position in specified mode.

        Args:
            servo_pos: Servo position in 0-255 range
            mode: 'p' for minimum (SPR absorption) or 's' for maximum (transmission)

        Takes multiple measurements and averages them for stability.
        Waits for full servo settling before measurements.
        """
        angle_deg = servo_to_degrees(servo_pos)
        # Explicitly ensure mode and servo alignment before measuring
        s_expected = angle_deg if mode == 's' else None
        p_expected = angle_deg if mode == 'p' else None
        # If one of the expected is None, use current best-known for the other axis
        if s_expected is None:
            # Keep S at current refined best; do not change S here
            s_expected = servo_to_degrees(s_pos_servo) if 's_pos_servo' in locals() else angle_deg
        if p_expected is None:
            # When measuring S, keep P at S±90 candidate if available
            p_expected = servo_to_degrees(p_candidate_1_servo) if 'p_candidate_1_servo' in locals() else angle_deg
        _ensure_mode_and_position(ctrl, mode, int(round(s_expected)), int(round(p_expected)), tolerance=3)

        # Take multiple measurements and average
        measurements = []
        for i in range(MEASUREMENT_AVERAGES):
            if i > 0:
                time.sleep(0.05)  # Small delay between readings
            spectrum = usb.read_intensity()
            if spectrum is not None:
                if multi_bucket_available:
                    bucket_vals = get_roi_bucket_intensities(spectrum, wavelengths)
                else:
                    bucket_vals = [float(spectrum.mean())] * len(ROI_BUCKETS)
                measurements.append(bucket_vals)

        if len(measurements) == 0:
            logger.error(f"Failed to measure servo position {servo_pos}")
            # Return zero vector for buckets and aggregate 0
            return [0.0] * len(ROI_BUCKETS), 0.0

        # Use mean of measurements for stability
        # Average bucket values across repeats
        bucket_matrix = np.array(measurements)  # shape (repeats, buckets)
        bucket_means = list(np.mean(bucket_matrix, axis=0))
        # Stage bucket selection: if buckets_for_stage provided, aggregate only those indices else all
        if buckets_for_stage is None:
            selected_vals = bucket_means
        else:
            selected_vals = [bucket_means[i] for i in buckets_for_stage]
        aggregate_intensity = float(np.mean(selected_vals))
        std_intensity = float(np.std(selected_vals)) if len(selected_vals) > 1 else 0.0

        all_positions.append(servo_pos)
        all_intensities.append(aggregate_intensity)

        if std_intensity > avg_intensity * 0.1:  # More than 10% variation
            logger.debug(f"   High variation at servo {servo_pos}: {avg_intensity:.0f} ± {std_intensity:.0f}")

        return bucket_means, aggregate_intensity

    # STEP 2: Coarse quadrant search - full 0-255 servo range
    # SEARCH FOR S (MAXIMUM) FIRST - stronger signal, easier to find!
    logger.info("STEP 2: Coarse quadrant search for S position (maximum transmission)...")
    logger.info("   Searching in S-mode (parallel to analyzer) - strongest signal")
    servo_step = 55

    coarse_servo_positions = list(range(5, 236, servo_step))  # [5, 60, 115, 170, 225]
    coarse_intensities = []

    # Switch to S-mode for maximum search
    _ensure_mode_and_position(ctrl, 's', int(round(servo_to_degrees(coarse_servo_positions[0]))), int(round(servo_to_degrees(coarse_servo_positions[0]))), tolerance=3)

    coarse_bucket_maps = {}
    for servo_pos in coarse_servo_positions:
        bucket_means, agg = measure_position(servo_pos, mode='s')  # Stay in S-mode
        coarse_intensities.append(agg)
        coarse_bucket_maps[servo_pos] = bucket_means
        logger.info(f"   Servo {servo_pos}: agg={agg:.0f} buckets=" + ", ".join([f"{bm:.0f}" for bm in bucket_means]))

    # Find MAXIMUM (S position) - strongest signal!
    coarse_max_idx = np.argmax(coarse_intensities)
    approx_s_servo = coarse_servo_positions[coarse_max_idx]

    logger.info(f"Coarse search results:")
    logger.info(f"   Max intensity: {coarse_intensities[coarse_max_idx]:.0f} at servo {approx_s_servo}")
    min_idx = np.argmin(coarse_intensities)
    logger.info(f"   Min intensity: {coarse_intensities[min_idx]:.0f} at servo {coarse_servo_positions[min_idx]}")
    logger.info(f"   Range: {coarse_intensities[coarse_max_idx] - min(coarse_intensities):.0f} counts")
    logger.info(f"Approximate S position (maximum):")
    logger.info(f"   S ≈ servo {approx_s_servo} - {coarse_intensities[coarse_max_idx]:.0f} counts")

    # STEP 3: Refine S position - Multi-stage refinement in servo units
    logger.info(f"STEP 3: Refining S position around servo {approx_s_servo}...")
    logger.info("   Staying in S-mode to find true maximum...")

    # Stage 3a: Coarse refinement (±28 servo units in 14 unit steps)
    logger.info(f"  Stage 3a: Coarse refinement (±28 servo units in 14 unit steps)...")
    s_search_positions = [
        max(MIN_SERVO, approx_s_servo - 28),
        max(MIN_SERVO, approx_s_servo - 14),
        approx_s_servo,
        min(MAX_SERVO, approx_s_servo + 14),
        min(MAX_SERVO, approx_s_servo + 28)
    ]
    s_search_positions = [p for p in s_search_positions if p not in all_positions]

    s_intensities = {approx_s_servo: coarse_intensities[coarse_max_idx]}
    # Determine optimal ROI buckets based on S-P contrast at approximate S
    logger.info("Selecting ROI buckets based on S-P contrast (delta S-P)...")
    # Measure P candidates at S ± 90 for bucket deltas (without committing)
    p_candidate_positions = []
    for delta in (-90, 90):
        cand = approx_s_servo + delta
        if MIN_SERVO <= cand <= MAX_SERVO:
            p_candidate_positions.append(cand)
    bucket_s = coarse_bucket_maps.get(approx_s_servo, [0.0]*len(ROI_BUCKETS))
    bucket_p_min = [float('inf')] * len(ROI_BUCKETS)
    for p_servo in p_candidate_positions:
        p_bucket_vals, _ = measure_position(p_servo, mode='p', buckets_for_stage=None)
        for i, val in enumerate(p_bucket_vals):
            if val < bucket_p_min[i]:
                bucket_p_min[i] = val
    bucket_deltas = [bucket_s[i] - bucket_p_min[i] for i in range(len(ROI_BUCKETS))]
    for i, (rng, delta) in enumerate(zip(ROI_BUCKETS, bucket_deltas)):
        logger.info(f"  Bucket {rng[0]}-{rng[1]}nm: Δ(S-P)={delta:.0f} (S={bucket_s[i]:.0f} P={bucket_p_min[i]:.0f})")
    # Rank buckets by delta descending
    bucket_order = sorted(range(len(ROI_BUCKETS)), key=lambda i: bucket_deltas[i], reverse=True)
    best_bucket = bucket_order[0]
    second_bucket = bucket_order[1] if len(bucket_order) > 1 else bucket_order[0]
    logger.info(f"Selected best bucket: {ROI_BUCKETS[best_bucket][0]}-{ROI_BUCKETS[best_bucket][1]}nm")
    logger.info(f"Second bucket: {ROI_BUCKETS[second_bucket][0]}-{ROI_BUCKETS[second_bucket][1]}nm")
    refinement_bucket_indices_stage_coarse = [best_bucket, second_bucket]
    refinement_bucket_index_fine = best_bucket
    for servo_pos in s_search_positions:
        bucket_vals, agg = measure_position(servo_pos, mode='s', buckets_for_stage=refinement_bucket_indices_stage_coarse)
        s_intensities[servo_pos] = agg
        logger.debug(f"     Servo {servo_pos}: agg={agg:.0f} buckets=" + ", ".join([f"{v:.0f}" for v in bucket_vals]))

    s_coarse_refined = max(s_intensities.keys(), key=lambda k: s_intensities[k])
    logger.info(f"  Coarse refinement result: servo {s_coarse_refined} - {s_intensities[s_coarse_refined]:.0f} counts")

    # Stage 3b: Fine refinement (±7 servo units in 7 unit steps)
    logger.info(f"  Stage 3b: Fine refinement (±7 servo units around {s_coarse_refined})...")
    fine_positions = [
        max(MIN_SERVO, s_coarse_refined - 7),
        s_coarse_refined,
        min(MAX_SERVO, s_coarse_refined + 7)
    ]
    fine_positions = [p for p in fine_positions if p not in all_positions]

    for servo_pos in fine_positions:
        bucket_vals, agg = measure_position(servo_pos, mode='s', buckets_for_stage=refinement_bucket_indices_stage_coarse)
        s_intensities[servo_pos] = agg
        logger.debug(f"     Servo {servo_pos}: agg={agg:.0f} buckets=" + ", ".join([f"{v:.0f}" for v in bucket_vals]))

    s_fine_refined = max(s_intensities.keys(), key=lambda k: s_intensities[k])
    logger.info(f"  Fine refinement result: servo {s_fine_refined} - {s_intensities[s_fine_refined]:.0f} counts")

    # Stage 3c: Ultra-fine refinement (±3 servo units in 3 unit steps)
    logger.info(f"  Stage 3c: Ultra-fine refinement (±3 servo units around {s_fine_refined})...")
    ultrafine_positions = [
        max(MIN_SERVO, s_fine_refined - 3),
        s_fine_refined,
        min(MAX_SERVO, s_fine_refined + 3)
    ]
    ultrafine_positions = [p for p in ultrafine_positions if p not in all_positions]

    for servo_pos in ultrafine_positions:
        bucket_vals, agg = measure_position(servo_pos, mode='s', buckets_for_stage=[refinement_bucket_index_fine])
        s_intensities[servo_pos] = agg
        logger.debug(f"     Servo {servo_pos}: agg={agg:.0f} bucket=" + ", ".join([f"{v:.0f}" for v in bucket_vals]))

    # Final S position - TRUE MAXIMUM found!
    s_pos_servo = max(s_intensities.keys(), key=lambda k: s_intensities[k])
    s_intensity = s_intensities[s_pos_servo]
    logger.info(f"✓ S position finalized: servo {s_pos_servo} - {s_intensity:.0f} counts")
    logger.info(f"  Total S refinement measurements: {len([p for p in all_positions if p != approx_s_servo]) - len([p for p in all_positions if p in coarse_servo_positions])}")

    # STEP 4: Calculate P position at S ± 90 servo units
    logger.info(f"STEP 4: Finding P position (minimum) at S ± 90 servo units...")
    servo_90_separation = 90  # 90 servo units for circular polarizer

    # Check both candidates: S - 90 and S + 90
    p_candidate_1_servo = s_pos_servo - servo_90_separation
    p_candidate_2_servo = s_pos_servo + servo_90_separation

    p_candidates = []
    if MIN_SERVO <= p_candidate_1_servo <= MAX_SERVO:
        p_candidates.append(p_candidate_1_servo)
    if MIN_SERVO <= p_candidate_2_servo <= MAX_SERVO:
        p_candidates.append(p_candidate_2_servo)

    if len(p_candidates) == 0:
        logger.error(f"❌ ERROR: Cannot place P position 90 units from S=servo {s_pos_servo}")
        logger.error(f"   S - 90 = servo {p_candidate_1_servo} - out of range")
        logger.error(f"   S + 90 = servo {p_candidate_2_servo} - out of range")
        return None

    # Measure both P candidates in P-mode and pick the MINIMUM
    logger.info(f"  Measuring P candidates at ±90 servo units from S...")
    logger.info("  Switching to P-mode (perpendicular to analyzer)...")
    p_measurements = {}
    for candidate_servo in p_candidates:
        bucket_vals, agg = measure_position(candidate_servo, mode='p', buckets_for_stage=[refinement_bucket_index_fine])
        p_measurements[candidate_servo] = agg
        logger.info(f"    Servo {candidate_servo}: agg={agg:.0f} bucket={ROI_BUCKETS[refinement_bucket_index_fine][0]}-{ROI_BUCKETS[refinement_bucket_index_fine][1]}nm vals=" + ", ".join([f"{v:.0f}" for v in bucket_vals]))

    # Pick the position with MINIMUM intensity (strongest SPR absorption)
    if len(p_measurements) == 0:
        logger.error("❌ Failed to measure any P candidates")
        return None

    p_pos_servo = min(p_measurements.keys(), key=lambda k: p_measurements[k])
    p_intensity = p_measurements[p_pos_servo]

    all_positions.append(s_pos_servo)
    all_intensities.append(s_intensity)

    separation_servo = abs(s_pos_servo - p_pos_servo)
    sp_ratio = s_intensity / p_intensity if p_intensity > 0 else 0.0
    sp_delta = s_intensity - p_intensity

    # Calculate extinction ratio: (S-P)/S as percentage
    # This is a sensor-specific reference value for tracking calibration quality over time
    extinction_ratio = (sp_delta / s_intensity * 100.0) if s_intensity > 0 else 0.0

    logger.info(f"✓ S-P delta: {sp_delta:.0f} counts (positive confirms orientation)")
    logger.info(f"✓ Extinction ratio: {extinction_ratio:.2f}% (sensor-specific reference for recalibration tracking)")

    logger.info(f"✓ S position finalized: servo {s_pos_servo} - {s_intensity:.0f} counts")
    logger.info(f"✓ P position: servo {p_pos_servo} - {p_intensity:.0f} counts")
    logger.info(f"✓ Separation: {separation_servo} servo units (circular polarizer)")
    logger.info(f"✓ S/P ratio: {sp_ratio:.2f}x (higher is better, >1.3x expected for good SPR)")

    logger.info(f"✅ Quadrant search complete")
    logger.info(f"Total measurements: {len(all_positions)} (vs 33+ for full sweep)")

    # Restore original LED intensities
    _restore_led_intensity(ctrl, original_led_intensity)

    # Convert to degrees for device_config.json compatibility
    s_pos_deg = servo_to_degrees(s_pos_servo)
    p_pos_deg = servo_to_degrees(p_pos_servo)

    return s_pos_deg, p_pos_deg, extinction_ratio  # Return degrees and extinction ratio


# ============================================================================
# SERVO VERIFICATION
# ============================================================================

def verify_servo_positions(ctrl, expected_s: int, expected_p: int, tolerance: int = 3, retry_on_mismatch: bool = True) -> tuple[bool, int, int]:
    """Verify servo positions match expected values, with one optional retry.

    Args:
        ctrl: Controller instance
        expected_s: Expected S position (0-180 degrees)
        expected_p: Expected P position (0-180 degrees)
        tolerance: Acceptable deviation in degrees (default 3°)

    Returns:
        Tuple of (success, actual_s, actual_p)
        - success: True if positions match within tolerance
        - actual_s: Actual S position read from controller
        - actual_p: Actual P position read from controller
    """
    try:
        # Read current positions from controller
        current_positions = ctrl.servo_get()

        # Parse response (handle both bytes and string formats)
        s_bytes = current_positions.get("s", b"0")
        p_bytes = current_positions.get("p", b"0")

        if isinstance(s_bytes, bytes):
            actual_s = int(s_bytes.decode('utf-8').strip())
        else:
            actual_s = int(str(s_bytes).strip())

        if isinstance(p_bytes, bytes):
            actual_p = int(p_bytes.decode('utf-8').strip())
        else:
            actual_p = int(str(p_bytes).strip())

        # Check if within tolerance
        s_diff = abs(actual_s - expected_s)
        p_diff = abs(actual_p - expected_p)

        success = (s_diff <= tolerance) and (p_diff <= tolerance)

        if success:
            logger.info(f"✅ Servo verification passed: S={actual_s}° (expected {expected_s}°), P={actual_p}° (expected {expected_p}°)")
        else:
            logger.warning(f"⚠️ Servo verification failed:")
            logger.warning(f"   S: actual={actual_s}° expected={expected_s}° diff={s_diff}° (tolerance={tolerance}°)")
            logger.warning(f"   P: actual={actual_p}° expected={expected_p}° diff={p_diff}° (tolerance={tolerance}°)")
            # Perform one retry: command move then re-read
            if retry_on_mismatch:
                try:
                    ctrl.servo_set(expected_s, expected_p)
                    time.sleep(0.3)
                    current_positions = ctrl.servo_get()
                    s_bytes = current_positions.get("s", b"0")
                    p_bytes = current_positions.get("p", b"0")
                    if isinstance(s_bytes, bytes):
                        actual_s = int(s_bytes.decode('utf-8').strip())
                    else:
                        actual_s = int(str(s_bytes).strip())
                    if isinstance(p_bytes, bytes):
                        actual_p = int(p_bytes.decode('utf-8').strip())
                    else:
                        actual_p = int(str(p_bytes).strip())
                    s_diff = abs(actual_s - expected_s)
                    p_diff = abs(actual_p - expected_p)
                    success = (s_diff <= tolerance) and (p_diff <= tolerance)
                    if success:
                        logger.info(f"✅ Servo verification passed after retry: S={actual_s}°, P={actual_p}°")
                    else:
                        logger.warning(f"❌ Servo mismatch persists after retry: S diff={s_diff}°, P diff={p_diff}°")
                except Exception as re:
                    logger.error(f"Retry to set/verify servo failed: {re}")

        return success, actual_s, actual_p

    except Exception as e:
        logger.error(f"❌ Servo verification error: {e}")
        return False, 0, 0


def _ensure_mode_and_position(ctrl, mode: str, s_expected: int, p_expected: int, tolerance: int = 3) -> bool:
    """Set controller mode and ensure servos match expected positions.

    Returns True when in the requested `mode` and S/P are within tolerance
    of expected, performing one retry if needed.
    """
    try:
        # Set mode first for consistent firmware behavior
        if not ctrl.set_mode(mode):
            logger.warning(f"Failed to set controller mode '{mode}'")
        # Command expected positions
        ctrl.servo_set(s_expected, p_expected)
        time.sleep(0.3)
        ok, actual_s, actual_p = verify_servo_positions(ctrl, s_expected, p_expected, tolerance=tolerance, retry_on_mismatch=True)
        if not ok:
            logger.warning(f"Servo not aligned after retry for mode '{mode}': expected S={s_expected},P={p_expected} got S={actual_s},P={actual_p}")
        else:
            logger.info(f"Mode '{mode}' with servos aligned: S={actual_s}, P={actual_p}")
        return ok
    except Exception as e:
        logger.error(f"_ensure_mode_and_position error: {e}")
        return False


# ============================================================================
# BACKWARD COMPATIBILITY WRAPPER
# ============================================================================

def perform_quadrant_search(usb, ctrl):
    """Backward compatibility wrapper - calls production version.

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper

    Returns:
        Tuple of (s_pos, p_pos, extinction_ratio) or None if search fails
    """
    return perform_quadrant_search_prod(usb, ctrl)


# ============================================================================
# MAIN CALIBRATION FUNCTION
# ============================================================================

def auto_calibrate_polarizer(usb, ctrl, require_water: bool = True, polarizer_type: str = "circular"):
    """Automatically calibrate polarizer servo positions using quadrant search.

    This is the main entry point called by the application.

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper
        require_water: Not used (legacy parameter for compatibility)
        polarizer_type: Type of polarizer (only "circular" supported)

    Returns:
        Tuple of (s_pos, p_pos, extinction_ratio) or None if calibration fails
    """
    if polarizer_type != "circular":
        logger.warning(f"Polarizer type '{polarizer_type}' not supported, using 'circular'")

    logger.info("Starting automatic polarizer calibration...")
    logger.info(f"Using PRODUCTION quadrant search with native servo units (0-255)")

    result = perform_quadrant_search_prod(usb, ctrl)

    if result:
        s_pos, p_pos, extinction_ratio = result
        logger.info("")
        logger.info("=" * 80)
        logger.info("CALIBRATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"S Position: {s_pos}°")
        logger.info(f"P Position: {p_pos}°")
        logger.info(f"Separation: {abs(s_pos - p_pos)}°")
        logger.info(f"Extinction Ratio: {extinction_ratio:.2f}% (reference baseline)")
        logger.info("=" * 80)
    else:
        logger.error("Calibration failed!")

    return result

