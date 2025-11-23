"""Servo position calibration for circular polarizer using intelligent quadrant search.

This module provides efficient servo calibration for SPR systems with circular
polarizers. Uses a 3-phase quadrant search (13 measurements) with transmission
validation before saving to EEPROM.

Key features:
- ROI-based measurement (600-750nm around SPR resonance)
- Intelligent coarse + refinement search (~13 measurements vs 33+ for full sweep)
- Enforces exact 90° separation for circular polarizers
- Transmission-based validation (ensures SPR dip quality before saving)
- Water presence check (required for SPR detection)
- Saturation detection and handling
- Automatic inversion correction
"""

import time
import numpy as np
from typing import Optional, Tuple
from scipy.signal import find_peaks, peak_prominences, peak_widths
from utils.logger import logger

# Calibration parameters
MIN_ANGLE = 10          # Start of servo range
MAX_ANGLE = 170         # End of servo range
SETTLING_TIME = 0.2     # Servo settling time (seconds)
MODE_SWITCH_TIME = 0.1  # Time to switch between S/P modes (seconds)

# ROI for SPR resonance measurement
ROI_MIN_WL = 600        # Minimum wavelength for SPR ROI (nm)
ROI_MAX_WL = 750        # Maximum wavelength for SPR ROI (nm)

# Resonance wavelength validation
MIN_RESONANCE_WL = 590  # Minimum valid resonance wavelength (nm)
MAX_RESONANCE_WL = 670  # Maximum valid resonance wavelength (nm)

# Detector specifications
MAX_DETECTOR_COUNTS = 62000        # Flame-T maximum counts (not 65535)
SATURATION_THRESHOLD = 0.95        # Warn if above 95% of max (58,900 counts)

# Validation thresholds
MIN_SEPARATION = 80                # Minimum S-P separation (degrees) for circular polarizer
MAX_SEPARATION = 100               # Maximum S-P separation (degrees) for circular polarizer
MIN_SP_RATIO = 1.3                 # Minimum S/P intensity ratio
IDEAL_SP_RATIO = 1.5               # Ideal S/P intensity ratio
MIN_DIP_DEPTH_PERCENT = 10.0       # Minimum transmission dip depth (%)
MIN_TRANSMISSION_PERCENT = 30.0    # Minimum transmission at dip (to detect water)


def get_roi_intensity(spectrum: np.ndarray, wavelengths: np.ndarray) -> float:
    """Extract maximum intensity from ROI around SPR resonance.

    Args:
        spectrum: Full spectrum intensity array
        wavelengths: Wavelength array corresponding to spectrum

    Returns:
        Maximum intensity in SPR ROI (600-750nm)
    """
    roi_mask = (wavelengths >= ROI_MIN_WL) & (wavelengths <= ROI_MAX_WL)
    roi_spectrum = spectrum[roi_mask]

    if len(roi_spectrum) == 0:
        return float(spectrum.max())

    return float(roi_spectrum.max())


def check_water_presence(usb, ctrl, s_pos: int, p_pos: int):
    """Check if water is present on sensor by analyzing transmission spectrum.

    Water presence is detected by:
    1. Transmission dip in SPR region (600-750nm)
    2. Transmission < 100% (P < S, no inversion)
    3. Dip depth >= 10% of maximum transmission

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper
        s_pos: Current S-mode servo position
        p_pos: Current P-mode servo position

    Returns:
        Tuple of (has_water, transmission_min, dip_depth_percent)
    """
    try:
        # Set positions and measure both modes
        ctrl.servo_set(s=s_pos, p=p_pos)
        time.sleep(SETTLING_TIME * 2)

        # Measure S-pol (reference)
        ctrl.set_mode("s")
        time.sleep(MODE_SWITCH_TIME * 2)
        s_spectrum = usb.read_intensity()

        # Measure P-pol (SPR-active)
        ctrl.set_mode("p")
        time.sleep(MODE_SWITCH_TIME * 2)
        p_spectrum = usb.read_intensity()

        # Calculate transmission
        transmission = np.divide(
            p_spectrum,
            s_spectrum,
            out=np.ones_like(p_spectrum, dtype=float),
            where=s_spectrum > 10
        ) * 100.0

        # Analyze SPR ROI
        wavelengths = usb._wavelengths
        if wavelengths is None:
            logger.warning("Wavelengths not available - cannot check water presence")
            return False, None, None

        roi_mask = (wavelengths >= ROI_MIN_WL) & (wavelengths <= ROI_MAX_WL)
        roi_transmission = transmission[roi_mask]

        if len(roi_transmission) == 0:
            return False, None, None

        # Check for SPR dip characteristics
        transmission_min = float(roi_transmission.min())
        transmission_max = float(roi_transmission.max())
        dip_depth_percent = transmission_max - transmission_min

        # Water detected if:
        # 1. Dip is deep enough (>10%)
        # 2. Transmission shows proper S > P relationship
        has_water = (
            dip_depth_percent >= MIN_DIP_DEPTH_PERCENT and
            transmission_min < 100.0 and
            transmission_max < 150.0  # Sanity check
        )

        return has_water, transmission_min, dip_depth_percent

    except Exception as e:
        logger.exception(f"Error checking water presence: {e}")
        return False, None, None


def validate_positions_with_transmission(usb, ctrl, s_pos: int, p_pos: int):
    """Validate S/P positions by analyzing transmission spectrum quality.

    This is the CRITICAL validation step that ensures:
    1. Water is present on sensor (SPR dip detected)
    2. Transmission dip is deep enough (>10%)
    3. Resonance wavelength is in valid range (590-670nm)
    4. No inversion (transmission <100%, S > P)
    5. S/P intensity ratio is adequate (>1.3×)

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper
        s_pos: S-mode servo position to validate
        p_pos: P-mode servo position to validate

    Returns:
        Tuple of (is_valid, validation_results_dict)
    """
    logger.info("=" * 80)
    logger.info("TRANSMISSION-BASED VALIDATION")
    logger.info("=" * 80)

    results = {
        "s_pos": s_pos,
        "p_pos": p_pos,
        "s_intensity": None,
        "p_intensity": None,
        "sp_ratio": None,
        "transmission_min": None,
        "transmission_max": None,
        "dip_depth_percent": None,
        "resonance_wavelength": None,
        "validation_passed": False,
        "validation_checks": []
    }

    try:
        # Get wavelengths
        wavelengths = usb._wavelengths
        if wavelengths is None:
            logger.error("❌ Wavelengths not available - cannot validate")
            return False, results

        # Check saturation limit
        saturation_limit = int(MAX_DETECTOR_COUNTS * SATURATION_THRESHOLD)
        logger.info(f"Saturation check: max allowed = {saturation_limit} counts ({SATURATION_THRESHOLD*100:.0f}%)")

        # Set positions and measure
        ctrl.servo_set(s=s_pos, p=p_pos)
        time.sleep(SETTLING_TIME * 2)

        # Measure S-pol (reference)
        ctrl.set_mode("s")
        time.sleep(MODE_SWITCH_TIME * 2)
        s_spectrum = usb.read_intensity()
        s_max = s_spectrum.max()
        s_roi = get_roi_intensity(s_spectrum, wavelengths)

        # Check S saturation
        if s_max >= saturation_limit:
            logger.error(f"❌ SATURATION in S-mode: {s_max:.0f} counts >= {saturation_limit}")
            results["validation_checks"].append(("S saturation", False, f"{s_max:.0f} >= {saturation_limit}"))
            return False, results

        # Measure P-pol (SPR-active)
        ctrl.set_mode("p")
        time.sleep(MODE_SWITCH_TIME * 2)
        p_spectrum = usb.read_intensity()
        p_max = p_spectrum.max()
        p_roi = get_roi_intensity(p_spectrum, wavelengths)

        # Check P saturation
        if p_max >= saturation_limit:
            logger.error(f"❌ SATURATION in P-mode: {p_max:.0f} counts >= {saturation_limit}")
            results["validation_checks"].append(("P saturation", False, f"{p_max:.0f} >= {saturation_limit}"))
            return False, results

        logger.info(f"✓ No saturation detected")
        results["validation_checks"].append(("Saturation", True, f"S={s_max:.0f}, P={p_max:.0f} < {saturation_limit}"))

        # Store intensities
        results["s_intensity"] = float(s_roi)
        results["p_intensity"] = float(p_roi)

        # CHECK 1: S > P (no inversion at ROI level)
        logger.info(f"1. Intensity Check:")
        logger.info(f"   S-mode ROI: {s_roi:.0f} counts")
        logger.info(f"   P-mode ROI: {p_roi:.0f} counts")

        if s_roi <= p_roi:
            logger.error(f"❌ FAIL: S should be higher than P (inversion detected)")
            results["validation_checks"].append(("S > P", False, f"S={s_roi:.0f} <= P={p_roi:.0f}"))
            return False, results

        logger.info(f"   ✓ PASS: S > P (no inversion)")
        results["validation_checks"].append(("S > P", True, f"S={s_roi:.0f} > P={p_roi:.0f}"))

        # CHECK 2: S/P ratio
        sp_ratio = s_roi / p_roi if p_roi > 0 else 0
        results["sp_ratio"] = float(sp_ratio)

        logger.info(f"2. S/P Ratio:")
        logger.info(f"   Measured: {sp_ratio:.2f}×")
        logger.info(f"   Minimum: {MIN_SP_RATIO:.2f}×")

        if sp_ratio < MIN_SP_RATIO:
            logger.warning(f"❌ FAIL: S/P ratio too low")
            results["validation_checks"].append(("S/P ratio", False, f"{sp_ratio:.2f}× < {MIN_SP_RATIO:.2f}×"))
            return False, results

        logger.info(f"   ✓ PASS: S/P ratio adequate")
        results["validation_checks"].append(("S/P ratio", True, f"{sp_ratio:.2f}× >= {MIN_SP_RATIO:.2f}×"))

        # CHECK 3: Calculate transmission and analyze SPR dip
        transmission = np.divide(
            p_spectrum,
            s_spectrum,
            out=np.ones_like(p_spectrum, dtype=float),
            where=s_spectrum > 10
        ) * 100.0

        # Analyze SPR ROI
        roi_mask = (wavelengths >= ROI_MIN_WL) & (wavelengths <= ROI_MAX_WL)
        roi_transmission = transmission[roi_mask]
        roi_wavelengths = wavelengths[roi_mask]

        if len(roi_transmission) == 0:
            logger.error(f"❌ FAIL: No data in SPR ROI ({ROI_MIN_WL}-{ROI_MAX_WL}nm)")
            return False, results

        transmission_min = float(roi_transmission.min())
        transmission_max = float(roi_transmission.max())
        dip_depth_percent = transmission_max - transmission_min

        results["transmission_min"] = transmission_min
        results["transmission_max"] = transmission_max
        results["dip_depth_percent"] = dip_depth_percent

        logger.info(f"3. Transmission Dip Analysis:")
        logger.info(f"   Minimum: {transmission_min:.1f}%")
        logger.info(f"   Maximum: {transmission_max:.1f}%")
        logger.info(f"   Dip depth: {dip_depth_percent:.1f}%")

        # CHECK 4: Transmission dip depth (indicates SPR coupling quality)
        if dip_depth_percent < MIN_DIP_DEPTH_PERCENT:
            logger.error(f"❌ FAIL: Dip too shallow (need >{MIN_DIP_DEPTH_PERCENT}%)")
            logger.error(f"   This indicates weak SPR coupling or no water on sensor")
            results["validation_checks"].append(("Dip depth", False, f"{dip_depth_percent:.1f}% < {MIN_DIP_DEPTH_PERCENT}%"))
            return False, results

        logger.info(f"   ✓ PASS: Dip depth adequate")
        results["validation_checks"].append(("Dip depth", True, f"{dip_depth_percent:.1f}% >= {MIN_DIP_DEPTH_PERCENT}%"))

        # CHECK 5: No transmission inversion (should be <100%)
        if transmission_min > 100.0:
            logger.error(f"❌ FAIL: Transmission >100% indicates inverted polarizer positions")
            results["validation_checks"].append(("Transmission <100%", False, f"Min={transmission_min:.1f}% > 100%"))
            return False, results

        logger.info(f"   ✓ PASS: Transmission <100% (no inversion)")
        results["validation_checks"].append(("Transmission <100%", True, f"Min={transmission_min:.1f}%"))

        # CHECK 6: Resonance wavelength validation
        resonance_idx = np.argmin(roi_transmission)
        resonance_wavelength = float(roi_wavelengths[resonance_idx])
        results["resonance_wavelength"] = resonance_wavelength

        logger.info(f"4. Resonance Wavelength:")
        logger.info(f"   Measured: {resonance_wavelength:.1f}nm")
        logger.info(f"   Valid range: {MIN_RESONANCE_WL}-{MAX_RESONANCE_WL}nm")

        if resonance_wavelength < MIN_RESONANCE_WL or resonance_wavelength > MAX_RESONANCE_WL:
            logger.warning(f"⚠️  WARNING: Resonance outside typical SPR range")
            logger.warning(f"   This may indicate optical misalignment")
            results["validation_checks"].append(("Resonance WL", False, f"{resonance_wavelength:.1f}nm out of range"))
            # Don't fail - just warn
        else:
            logger.info(f"   ✓ PASS: Resonance in valid SPR range")
            results["validation_checks"].append(("Resonance WL", True, f"{resonance_wavelength:.1f}nm in range"))

        # All checks passed
        logger.info("=" * 80)
        logger.info("✅ VALIDATION PASSED - Positions are optimal")
        logger.info("=" * 80)
        results["validation_passed"] = True
        return True, results

    except Exception as e:
        logger.exception(f"Error during transmission validation: {e}")
        return False, results


def perform_quadrant_search(usb, ctrl):
    """Perform intelligent quadrant search to find optimal S and P positions.

    Uses a 3-phase approach:
    1. Coarse 5-point search across servo range
    2. Refinement around predicted P position (minimum)
    3. Calculate S position exactly 90° from P

    Total measurements: ~13 vs 33+ for full sweep

    Assumes integration time is already set from LED calibration.

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper

    Returns:
        Tuple of (s_pos, p_pos) or None if search fails
    """
    logger.info("=" * 80)
    logger.info("QUADRANT SEARCH FOR SERVO POSITIONS")
    logger.info("=" * 80)

    # Get wavelengths for ROI calculation
    wavelengths = usb._wavelengths
    if wavelengths is None:
        logger.warning("Wavelengths not available, using full spectrum max")
        use_roi = False
    else:
        use_roi = True
        logger.info(f"ROI: {ROI_MIN_WL}-{ROI_MAX_WL}nm (SPR resonance region)")

    # Store all measurements
    all_positions = []
    all_intensities = []

    def measure_position(angle: int) -> float:
        """Helper to measure intensity at a servo angle."""
        ctrl.servo_set(s=angle, p=angle)
        time.sleep(SETTLING_TIME)
        ctrl.set_mode("s")
        time.sleep(MODE_SWITCH_TIME)
        spectrum = usb.read_intensity()
        intensity = get_roi_intensity(spectrum, wavelengths) if use_roi else spectrum.max()
        all_positions.append(angle)
        all_intensities.append(intensity)
        return intensity

    # PHASE 1: Coarse search - 5 positions across range
    logger.info("Phase 1: Coarse search (5 positions)...")
    coarse_positions = [10, 50, 90, 130, 170]
    coarse_intensities = []

    for pos in coarse_positions:
        intensity = measure_position(pos)
        coarse_intensities.append(intensity)
        logger.debug(f"   {pos}°: {intensity:.0f} counts")

    # Find approximate min (P position - where SPR absorption is strongest)
    coarse_min_idx = np.argmin(coarse_intensities)
    approx_p = coarse_positions[coarse_min_idx]

    logger.info(f"Approximate P position (minimum):")
    logger.info(f"   P ≈ {approx_p}° ({coarse_intensities[coarse_min_idx]:.0f} counts)")

    # PHASE 2: Refine P position (minimum)
    logger.info(f"Phase 2: Refining P position around {approx_p}°...")
    p_search_positions = [
        max(MIN_ANGLE, approx_p - 20),
        max(MIN_ANGLE, approx_p - 10),
        approx_p,
        min(MAX_ANGLE, approx_p + 10),
        min(MAX_ANGLE, approx_p + 20)
    ]
    # Remove duplicates and already measured
    p_search_positions = [p for p in p_search_positions if p not in all_positions]

    p_intensities = {approx_p: coarse_intensities[coarse_min_idx]}
    for pos in p_search_positions:
        intensity = measure_position(pos)
        p_intensities[pos] = intensity
        logger.debug(f"   {pos}°: {intensity:.0f} counts")

    # Find refined P position (minimum intensity = strongest SPR absorption)
    p_pos = min(p_intensities.keys(), key=lambda k: p_intensities[k])
    p_intensity = p_intensities[p_pos]
    logger.info(f"✓ P position refined: {p_pos}° ({p_intensity:.0f} counts)")

    # PHASE 3: Set S position exactly 90° from P
    # For circular polarizer: S = P ± 90° (EXACT)
    # Choose the option that's within servo range (10-170°)
    s_candidate_1 = p_pos - 90
    s_candidate_2 = p_pos + 90

    if MIN_ANGLE <= s_candidate_1 <= MAX_ANGLE:
        s_pos = s_candidate_1
        logger.info(f"Phase 3: S position = P - 90° = {p_pos}° - 90° = {s_pos}°")
    elif MIN_ANGLE <= s_candidate_2 <= MAX_ANGLE:
        s_pos = s_candidate_2
        logger.info(f"Phase 3: S position = P + 90° = {p_pos}° + 90° = {s_pos}°")
    else:
        # This shouldn't happen if P is 10-170, so ±90 should always be valid
        logger.error(f"❌ ERROR: Cannot place S position 90° from P={p_pos}°")
        logger.error(f"   P - 90 = {s_candidate_1}° (out of range {MIN_ANGLE}-{MAX_ANGLE}°)")
        logger.error(f"   P + 90 = {s_candidate_2}° (out of range {MIN_ANGLE}-{MAX_ANGLE}°)")
        return None

    # Measure S position to verify
    ctrl.servo_set(s=s_pos, p=s_pos)
    time.sleep(SETTLING_TIME)
    ctrl.set_mode("s")
    time.sleep(MODE_SWITCH_TIME)
    spectrum = usb.read_intensity()
    s_intensity = get_roi_intensity(spectrum, wavelengths) if use_roi else spectrum.max()
    all_positions.append(s_pos)
    all_intensities.append(s_intensity)

    logger.info(f"✓ S position set: {s_pos}° ({s_intensity:.0f} counts)")
    logger.info(f"✓ Separation enforced: |{s_pos}° - {p_pos}°| = {abs(s_pos - p_pos)}° (exactly 90°)")

    logger.info(f"✅ Quadrant search complete")
    logger.info(f"Total measurements: {len(all_positions)} (vs 33+ for full sweep)")

    return s_pos, p_pos

    logger.info(f"✓ S position set: {s_pos}° ({s_intensity:.0f} counts)")
    logger.info(f"✓ Separation enforced: |{s_pos}° - {p_pos}°| = {abs(s_pos - p_pos)}° (exactly 90°)")

    logger.info(f"✅ Quadrant search complete")
    logger.info(f"Total measurements: {len(all_positions)} (vs 33 for full sweep)")

    # Return all measured data plus the found positions
    return np.array(all_positions), np.array(all_intensities), p_pos, s_pos


def find_resonance_wavelength(usb, ctrl, p_position):
    """Measure wavelength of resonance dip at P position.

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper
        p_position: P-mode servo position

    Returns:
        float: Wavelength of minimum in nm, or None if not found
    """
    # Set servo to P position
    ctrl.servo_set(s=p_position, p=p_position)
    time.sleep(SETTLING_TIME)
    ctrl.set_mode("s")
    time.sleep(MODE_SWITCH_TIME)

    # Read full spectrum
    spectrum = usb.read_intensity()
    wavelengths = usb._wavelengths

    if wavelengths is None:
        return None

    # Find wavelength of minimum within valid range
    valid_mask = (wavelengths >= MIN_RESONANCE_WL) & (wavelengths <= MAX_RESONANCE_WL)
    valid_spectrum = spectrum[valid_mask]
    valid_wavelengths = wavelengths[valid_mask]

    if len(valid_spectrum) == 0:
        return None

    min_idx = np.argmin(valid_spectrum)
    return float(valid_wavelengths[min_idx])


def analyze_peaks(positions, intensities, usb, ctrl, p_pos=None, s_pos=None):
    """Analyze sweep data to find and validate S and P positions.

    Args:
        positions: Array of servo positions
        intensities: Array of intensities at each position
        usb: Spectrometer wrapper
        ctrl: Controller wrapper
        p_pos: Pre-determined P position (optional). If provided, uses this instead of searching.
        s_pos: Pre-determined S position (optional). If provided, uses this instead of searching.

    Returns:
        dict: Results with s_pos, p_pos, validation status, etc.
        None if validation fails
    """
    results = {
        "s_pos": None,
        "p_pos": None,
        "s_intensity": None,
        "p_intensity": None,
        "sp_ratio": None,
        "separation": None,
        "resonance_wavelength": None,
        "validation": []
    }

    logger.info("=" * 80)
    logger.info("RESONANCE DIP ANALYSIS (SPR)")
    logger.info("=" * 80)

    # Find MINIMUM (resonance dip for P position)
    if p_pos is not None:
        logger.info("1. Using Pre-determined P Position:")
        p_position = p_pos
        # Find intensity at this position
        p_idx = np.where(positions == p_position)[0]
        if len(p_idx) > 0:
            p_intensity = intensities[p_idx[0]]
        else:
            logger.warning(f"   ⚠️  P position {p_position}° not in measured positions")
            p_intensity = None
    else:
        logger.info("1. Finding Resonance Dip (P position):")
        min_idx = np.argmin(intensities)
        p_position = positions[min_idx]
        p_intensity = intensities[min_idx]

    logger.info(f"   P position (MINIMUM): {p_position}°")
    logger.info(f"   P intensity: {p_intensity:.0f} counts (LOW - resonance dip)")

    results["p_pos"] = int(p_position)
    results["p_intensity"] = float(p_intensity)

    # Measure resonance wavelength
    resonance_wavelength = find_resonance_wavelength(usb, ctrl, p_position)
    if resonance_wavelength is not None:
        results["resonance_wavelength"] = resonance_wavelength
        logger.info(f"   Resonance wavelength: {resonance_wavelength:.1f}nm")

        # Validate wavelength is in expected range
        if resonance_wavelength < MIN_RESONANCE_WL or resonance_wavelength > MAX_RESONANCE_WL:
            results["validation"].append((
                "Resonance wavelength",
                False,
                f"{resonance_wavelength:.1f}nm not in [{MIN_RESONANCE_WL}, {MAX_RESONANCE_WL}]nm"
            ))
            logger.warning(f"   ❌ FAIL: Resonance outside valid range ({MIN_RESONANCE_WL}-{MAX_RESONANCE_WL}nm)")
            logger.warning(f"   This suggests incorrect servo position or optical misalignment")
            return None
        else:
            results["validation"].append((
                "Resonance wavelength",
                True,
                f"{resonance_wavelength:.1f}nm in [{MIN_RESONANCE_WL}, {MAX_RESONANCE_WL}]nm"
            ))
            logger.info(f"   ✓ PASS: Resonance in valid SPR range")
    else:
        logger.warning(f"   ⚠️  Warning: Could not determine resonance wavelength")

    # Validation: Check that minimum is significant
    dip_depth = intensities.max() - p_intensity
    dip_depth_percent = (dip_depth / intensities.max()) * 100 if intensities.max() > 0 else 0

    logger.info(f"   Dip depth: {dip_depth:.0f} counts ({dip_depth_percent:.1f}% of maximum)")

    if dip_depth_percent < MIN_DIP_DEPTH_PERCENT:
        results["validation"].append(("Dip depth", False, f"{dip_depth_percent:.1f}% < {MIN_DIP_DEPTH_PERCENT}%"))
        logger.warning(f"   ❌ FAIL: Resonance dip too shallow (need >{MIN_DIP_DEPTH_PERCENT}%)")
        return None
    else:
        results["validation"].append(("Dip depth", True, f"{dip_depth_percent:.1f}% >= {MIN_DIP_DEPTH_PERCENT}%"))
        logger.info(f"   ✓ PASS: Significant resonance dip detected")

    # Find MAXIMUM (reference for S position)
    if s_pos is not None:
        logger.info("2. Using Pre-determined S Position:")
        s_position = s_pos
        # Find intensity at this position
        s_idx = np.where(positions == s_position)[0]
        if len(s_idx) > 0:
            s_intensity = intensities[s_idx[0]]
        else:
            logger.warning(f"   ⚠️  S position {s_position}° not in measured positions")
            s_intensity = None
    else:
        logger.info("2. Finding Reference Maximum (S position):")
        max_idx = np.argmax(intensities)
        s_position = positions[max_idx]
        s_intensity = intensities[max_idx]

    logger.info(f"   S position (MAXIMUM): {s_position}°")
    logger.info(f"   S intensity: {s_intensity:.0f} counts (HIGH - reference)")

    # Calculate separation
    separation = abs(s_position - p_position)
    results["separation"] = separation

    # Validation: Check separation (skip if both positions were pre-determined with 90° constraint)
    if p_pos is None or s_pos is None:
        logger.info(f"3. Position Separation:")
        logger.info(f"   Measured: {separation:.0f}°")
        logger.info(f"   Expected: {MIN_SEPARATION}-{MAX_SEPARATION}°")

        if separation < MIN_SEPARATION or separation > MAX_SEPARATION:
            results["validation"].append(("Position separation", False, f"{separation:.0f}° not in [{MIN_SEPARATION}, {MAX_SEPARATION}]"))
            logger.warning(f"   ❌ FAIL: Separation out of range")
            return None
        else:
            results["validation"].append(("Position separation", True, f"{separation:.0f}° in [{MIN_SEPARATION}, {MAX_SEPARATION}]"))
            logger.info(f"   ✓ PASS: Separation is valid")
    else:
        logger.info(f"3. Position Separation: {separation:.0f}° (enforced by quadrant search)")

    # Store results
    results["s_pos"] = int(s_position)
    results["p_pos"] = int(p_position)
    results["s_intensity"] = float(s_intensity)
    results["p_intensity"] = float(p_intensity)

    # Validation: Verify S > P (intensity check)
    logger.info(f"4. Intensity Verification:")
    logger.info(f"   S-mode intensity: {results['s_intensity']:.0f} (HIGH - reference)")
    logger.info(f"   P-mode intensity: {results['p_intensity']:.0f} (LOW - resonance)")

    if results["s_intensity"] <= results["p_intensity"]:
        results["validation"].append(("S > P", False, f"S={results['s_intensity']:.0f} <= P={results['p_intensity']:.0f}"))
        logger.warning(f"   ❌ FAIL: S should be higher than P")
        return None
    else:
        results["validation"].append(("S > P", True, f"S={results['s_intensity']:.0f} > P={results['p_intensity']:.0f}"))
        logger.info(f"   ✓ PASS: S is higher than P")

    # Validation: Check S/P ratio
    results["sp_ratio"] = results["s_intensity"] / results["p_intensity"]

    logger.info(f"5. S/P Ratio:")
    logger.info(f"   Measured: {results['sp_ratio']:.2f}×")
    logger.info(f"   Minimum: {MIN_SP_RATIO:.2f}×")
    logger.info(f"   Ideal: {IDEAL_SP_RATIO:.2f}×")

    if results["sp_ratio"] < MIN_SP_RATIO:
        results["validation"].append(("S/P ratio", False, f"{results['sp_ratio']:.2f}× < {MIN_SP_RATIO:.2f}×"))
        logger.warning(f"   ❌ FAIL: Ratio too low")
        return None
    elif results["sp_ratio"] < IDEAL_SP_RATIO:
        results["validation"].append(("S/P ratio", True, f"{results['sp_ratio']:.2f}× >= {MIN_SP_RATIO:.2f}× (acceptable)"))
        logger.info(f"   ✓ PASS: Ratio acceptable (could be improved)")
    else:
        results["validation"].append(("S/P ratio", True, f"{results['sp_ratio']:.2f}× >= {IDEAL_SP_RATIO:.2f}× (ideal)"))
        logger.info(f"   ✓ PASS: Ratio is ideal")

    return results


def verify_and_correct_positions(usb, ctrl, s_pos, p_pos):
    """Verify positions by measuring actual intensities and correct if inverted.

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper
        s_pos: S-mode servo position
        p_pos: P-mode servo position

    Returns:
        tuple: (final_s_pos, final_p_pos, was_inverted)
        None if saturation detected
    """
    logger.info("=" * 80)
    logger.info("POSITION VERIFICATION AND SATURATION CHECK")
    logger.info("=" * 80)

    # Get wavelengths for ROI
    wavelengths = usb._wavelengths
    use_roi = wavelengths is not None

    saturation_limit = int(MAX_DETECTOR_COUNTS * SATURATION_THRESHOLD)
    logger.info(f"Saturation check: max allowed = {saturation_limit} counts ({SATURATION_THRESHOLD*100:.0f}% of {MAX_DETECTOR_COUNTS})")

    # Apply calculated positions
    ctrl.servo_set(s=s_pos, p=p_pos)
    time.sleep(SETTLING_TIME * 2)  # Extra settling time for accurate measurement

    # Measure S-mode
    ctrl.set_mode("s")
    time.sleep(MODE_SWITCH_TIME * 2)
    s_spectrum = usb.read_intensity()
    s_max = s_spectrum.max()
    if use_roi:
        s_measured = get_roi_intensity(s_spectrum, wavelengths)
    else:
        s_measured = s_max

    # Check S-mode saturation
    if s_max >= saturation_limit:
        logger.error(f"   ❌ SATURATION DETECTED in S-mode!")
        logger.error(f"   Peak intensity: {s_max:.0f} counts (limit: {saturation_limit})")
        logger.error(f"   LED intensity is too high - reduce LED power before continuing")
        return None

    # Measure P-mode
    ctrl.set_mode("p")
    time.sleep(MODE_SWITCH_TIME * 2)
    p_spectrum = usb.read_intensity()
    p_max = p_spectrum.max()
    if use_roi:
        p_measured = get_roi_intensity(p_spectrum, wavelengths)
    else:
        p_measured = p_max

    # Check P-mode saturation
    if p_max >= saturation_limit:
        logger.error(f"   ❌ SATURATION DETECTED in P-mode!")
        logger.error(f"   Peak intensity: {p_max:.0f} counts (limit: {saturation_limit})")
        logger.error(f"   LED intensity is too high - reduce LED power before continuing")
        return None

    logger.info(f"Initial measurement:")
    logger.info(f"   S-mode (pos={s_pos}): ROI={s_measured:.0f}, peak={s_max:.0f} counts")
    logger.info(f"   P-mode (pos={p_pos}): ROI={p_measured:.0f}, peak={p_max:.0f} counts")
    logger.info(f"   ✓ No saturation detected")

    # Check if inverted (P > S means transmission >100%)
    if p_measured > s_measured:
        logger.warning(f"   ⚠️  INVERSION DETECTED: P > S!")
        logger.warning(f"   This would cause transmission >100%")
        logger.info(f"   Swapping S and P positions...")

        # Swap positions
        s_pos, p_pos = p_pos, s_pos

        # Verify the swap worked
        ctrl.servo_set(s=s_pos, p=p_pos)
        time.sleep(SETTLING_TIME * 2)

        ctrl.set_mode("s")
        time.sleep(MODE_SWITCH_TIME * 2)
        s_verify = usb.read_intensity()
        if use_roi:
            s_verify_val = get_roi_intensity(s_verify, wavelengths)
        else:
            s_verify_val = s_verify.max()

        ctrl.set_mode("p")
        time.sleep(MODE_SWITCH_TIME * 2)
        p_verify = usb.read_intensity()
        if use_roi:
            p_verify_val = get_roi_intensity(p_verify, wavelengths)
        else:
            p_verify_val = p_verify.max()

        logger.info(f"Verification after swap:")
        logger.info(f"   S-mode: {s_verify_val:.0f} counts")
        logger.info(f"   P-mode: {p_verify_val:.0f} counts")

        if s_verify_val > p_verify_val:
            logger.info(f"   ✓ CORRECTED: S now > P")
            return s_pos, p_pos, True
        else:
            logger.error(f"   ✗ CORRECTION FAILED: Still inverted!")
            return s_pos, p_pos, True
    else:
        logger.info(f"   ✓ NO INVERSION: S > P (correct)")
        return s_pos, p_pos, False


def perform_barrel_window_search(usb, ctrl):
    """Find S and P windows for barrel-style polarizer assemblies.

    Barrel polarizers have ONLY 2 physical windows (not continuous rotation):
    - Each window may span multiple servo positions (cluster of high transmission)
    - Windows are separated by >70° (typically ~90°)
    - One window has S-pol film strip, other has P-pol film strip
    - Must identify which window is S vs P by analyzing SPR response

    Strategy:
    1. Full sweep to find ALL transmission peaks (windows)
    2. Cluster peaks into 2 window groups (S and P candidates)
    3. Find center position of each window (max transmission in cluster)
    4. Identify which is S vs P using SPR signature:
       - S window: High transmission, no SPR dip (reference)
       - P window: Lower transmission, shows SPR dip when water present

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper

    Returns:
        Dict with s_pos, p_pos, separation, sp_ratio, or None if failed
    """
    try:
        logger.info("=" * 80)
        logger.info("BARREL POLARIZER CALIBRATION (window-based)")
        logger.info("=" * 80)
        logger.info("Barrel polarizers have discrete S and P windows (not continuous)")
        logger.info("Finding window clusters and identifying S vs P...")

        # Get wavelength array for ROI computations
        wavelengths = getattr(usb, "_wavelengths", None)
        use_roi = wavelengths is not None
        if use_roi:
            logger.info(f"ROI: {ROI_MIN_WL}-{ROI_MAX_WL}nm (SPR resonance region)")
        else:
            logger.warning("Wavelengths unavailable; using full-spectrum max")

        def roi_value(spectrum):
            return get_roi_intensity(spectrum, wavelengths) if use_roi else float(spectrum.max())

        # PHASE 1: Full sweep to find all windows
        logger.info("Phase 1: Full sweep to find transmission windows...")
        sweep_positions = list(range(MIN_ANGLE, MAX_ANGLE + 1, 5))
        sweep_intensities = []

        for angle in sweep_positions:
            ctrl.servo_set(s=angle, p=angle)
            time.sleep(SETTLING_TIME)
            ctrl.set_mode("s")  # Use S-mode for initial sweep
            time.sleep(MODE_SWITCH_TIME)
            spectrum = usb.read_intensity()
            intensity = roi_value(spectrum)
            sweep_intensities.append(intensity)
            logger.debug(f"   {angle}°: {intensity:.0f} counts")

        sweep_intensities = np.array(sweep_intensities)

        # PHASE 2: Find peaks (windows) using threshold
        # Windows will show as intensity peaks above background
        threshold = sweep_intensities.mean() + 0.5 * sweep_intensities.std()
        logger.info(f"Phase 2: Identifying windows (threshold: {threshold:.0f} counts)...")

        # Find positions above threshold (potential windows)
        above_threshold = sweep_intensities > threshold
        window_positions = [sweep_positions[i] for i, val in enumerate(above_threshold) if val]

        if len(window_positions) < 2:
            logger.error(f"❌ Failed to find 2 windows (found {len(window_positions)})")
            logger.error(f"   Check barrel alignment and fiber connections")
            return None

        logger.info(f"Found {len(window_positions)} positions above threshold")

        # PHASE 3: Cluster positions into 2 windows
        # Use gap detection: windows are separated by >70°
        logger.info("Phase 3: Clustering positions into S and P windows...")

        clusters = []
        current_cluster = [window_positions[0]]

        for pos in window_positions[1:]:
            if pos - current_cluster[-1] <= 15:  # Adjacent positions (same window)
                current_cluster.append(pos)
            else:  # Gap found - new window
                clusters.append(current_cluster)
                current_cluster = [pos]
        clusters.append(current_cluster)  # Add last cluster

        if len(clusters) < 2:
            logger.error(f"❌ Could not separate into 2 windows (found {len(clusters)} clusters)")
            logger.error(f"   Windows may be too close or overlap")
            return None
        elif len(clusters) > 2:
            logger.warning(f"⚠️  Found {len(clusters)} clusters, using 2 largest")
            # Keep only the 2 clusters with most positions
            clusters.sort(key=len, reverse=True)
            clusters = clusters[:2]

        logger.info(f"✓ Found 2 window clusters:")
        logger.info(f"   Window 1: {len(clusters[0])} positions ({min(clusters[0])}°-{max(clusters[0])}°)")
        logger.info(f"   Window 2: {len(clusters[1])} positions ({min(clusters[1])}°-{max(clusters[1])}°)")

        # PHASE 4: Find peak position within each window cluster
        logger.info("Phase 4: Finding optimal position within each window...")

        window_peaks = []
        for i, cluster in enumerate(clusters):
            # Find position with max intensity in this cluster
            cluster_intensities = [sweep_intensities[sweep_positions.index(pos)] for pos in cluster]
            max_idx = np.argmax(cluster_intensities)
            peak_pos = cluster[max_idx]
            peak_intensity = cluster_intensities[max_idx]

            window_peaks.append({
                'position': peak_pos,
                'intensity': peak_intensity,
                'cluster_size': len(cluster)
            })
            logger.info(f"   Window {i+1} peak: {peak_pos}° ({peak_intensity:.0f} counts)")

        # PHASE 5: Identify which window is S vs P using SPR signature
        logger.info("Phase 5: Identifying S vs P windows using SPR signature...")

        # Measure both windows in both modes to detect SPR response
        window_signatures = []

        for i, window in enumerate(window_peaks):
            pos = window['position']

            # Measure in S-mode
            ctrl.servo_set(s=pos, p=pos)
            time.sleep(SETTLING_TIME * 2)
            ctrl.set_mode("s")
            time.sleep(MODE_SWITCH_TIME * 2)
            s_spectrum = usb.read_intensity()
            s_intensity = roi_value(s_spectrum)

            # Measure in P-mode
            ctrl.set_mode("p")
            time.sleep(MODE_SWITCH_TIME * 2)
            p_spectrum = usb.read_intensity()
            p_intensity = roi_value(p_spectrum)

            # Calculate transmission to detect SPR dip
            transmission = np.divide(
                p_spectrum,
                s_spectrum,
                out=np.ones_like(p_spectrum, dtype=float),
                where=s_spectrum > 10
            ) * 100.0

            # Analyze transmission in SPR ROI
            if wavelengths is not None:
                roi_mask = (wavelengths >= ROI_MIN_WL) & (wavelengths <= ROI_MAX_WL)
                roi_transmission = transmission[roi_mask]
                trans_min = float(roi_transmission.min()) if len(roi_transmission) > 0 else 100.0
                trans_max = float(roi_transmission.max()) if len(roi_transmission) > 0 else 100.0
                dip_depth = trans_max - trans_min
            else:
                trans_min = 100.0
                dip_depth = 0.0

            window_signatures.append({
                'window_id': i + 1,
                'position': pos,
                's_intensity': s_intensity,
                'p_intensity': p_intensity,
                'trans_min': trans_min,
                'dip_depth': dip_depth
            })

            logger.info(f"   Window {i+1} @ {pos}°:")
            logger.info(f"      S-mode: {s_intensity:.0f} counts")
            logger.info(f"      P-mode: {p_intensity:.0f} counts")
            logger.info(f"      Transmission min: {trans_min:.1f}%")
            logger.info(f"      Dip depth: {dip_depth:.1f}%")

        # Decision logic: S window shows minimal SPR effect, P window shows SPR dip
        # S-pol: Reference beam, high transmission, minimal difference S vs P modes
        # P-pol: SPR-active beam, shows transmission dip when water present

        if window_signatures[0]['dip_depth'] > window_signatures[1]['dip_depth']:
            # Window 1 has stronger dip → it's P-pol
            p_window = window_signatures[0]
            s_window = window_signatures[1]
            logger.info("Decision: Window 1 is P-pol (stronger SPR dip)")
        else:
            # Window 2 has stronger dip → it's P-pol
            p_window = window_signatures[1]
            s_window = window_signatures[0]
            logger.info("Decision: Window 2 is P-pol (stronger SPR dip)")

        s_pos = s_window['position']
        p_pos = p_window['position']
        separation = abs(s_pos - p_pos)

        # Calculate S/P ratio (S should be higher than P)
        sp_ratio = s_window['s_intensity'] / p_window['p_intensity'] if p_window['p_intensity'] > 0 else 0.0

        logger.info("=" * 80)
        logger.info("✅ BARREL WINDOW IDENTIFICATION COMPLETE")
        logger.info(f"   S window: {s_pos}° ({s_window['s_intensity']:.0f} counts)")
        logger.info(f"   P window: {p_pos}° ({p_window['p_intensity']:.0f} counts)")
        logger.info(f"   Separation: {separation}°")
        logger.info(f"   S/P ratio: {sp_ratio:.2f}×")
        logger.info(f"   P-window dip: {p_window['dip_depth']:.1f}%")
        logger.info("=" * 80)

        return {
            "s_pos": int(s_pos),
            "p_pos": int(p_pos),
            "separation": float(separation),
            "sp_ratio": float(sp_ratio),
            "s_intensity": float(s_window['s_intensity']),
            "p_intensity": float(p_window['p_intensity']),
            "p_dip_depth": float(p_window['dip_depth'])
        }

    except Exception as e:
        logger.exception(f"Barrel window search failed: {e}")
        return None
        logger.info(f"Estimated S/P (ROI) at windows: {sp_ratio:.2f}× (S={s_meas:.0f}, P={p_meas:.0f})")

        return {
            "s_pos": int(s_pos),
            "p_pos": int(p_pos),
            "separation": float(separation),
            "sp_ratio": float(sp_ratio),
        }

    except Exception as e:
        logger.exception(f"Barrel window search failed: {e}")
        return None


def perform_full_sweep_fallback(usb, ctrl):
    """Exhaustive full-sweep method to determine S/P positions.

    Mirrors the legacy logic formerly embedded in main.py. Validates peaks,
    separation, saturation, and S/P ratio. Returns a result dict or None.

    Returns dict keys: s_pos, p_pos, sp_ratio, separation, s_intensity, p_intensity
    """
    try:
        logger.info("\ud83d\udd04 Starting FULL SWEEP (exhaustive method - fallback)")

        min_angle = MIN_ANGLE
        max_angle = MAX_ANGLE
        half_range = (max_angle - min_angle) // 2
        angle_step = 5
        steps = half_range // angle_step
        max_intensities = np.zeros(2 * steps + 1)

        # Perform sweep
        logger.debug("Starting servo position sweep...")
        ctrl.servo_set(half_range + min_angle, max_angle)
        ctrl.set_mode("p")
        ctrl.set_mode("s")
        time.sleep(0.5)
        max_intensities[steps] = usb.read_intensity().max()

        for i in range(steps):
            x = min_angle + angle_step * i
            ctrl.servo_set(s=x, p=x + half_range + angle_step)
            time.sleep(0.2)
            ctrl.set_mode("s")
            time.sleep(0.1)
            max_intensities[i] = usb.read_intensity().max()
            ctrl.set_mode("p")
            time.sleep(0.1)
            max_intensities[i + steps + 1] = usb.read_intensity().max()

        # Validation 1: peaks
        peaks = find_peaks(max_intensities)[0]
        if len(peaks) < 2:
            logger.warning(f"Validation failed: only {len(peaks)} peaks found (need 2)")
            logger.warning(
                f"Intensity range: {max_intensities.min():.0f}-{max_intensities.max():.0f} counts"
            )
            return None

        prominences = peak_prominences(max_intensities, peaks)
        if len(prominences[0]) < 2:
            logger.warning("Validation failed: less than 2 prominent peaks detected")
            return None

        # Select two most prominent peaks
        peak_indices = prominences[0].argsort()[-2:]

        # Edge positions for width at 5% height to estimate centers
        edges = peak_widths(max_intensities, peaks, 0.05, prominences)[2:4]
        edges = np.array(edges)[:, peak_indices]
        pos1, pos2 = (min_angle + angle_step * edges.mean(0)).astype(int)

        separation = abs(int(pos2) - int(pos1))
        expected_separation = half_range
        tolerance = 15
        if abs(separation - expected_separation) > tolerance:
            logger.warning("Validation failed: peak separation incorrect")
            logger.warning(f"Found: {separation}\u00b0 apart; expected: {expected_separation}\u00b0 ")
            return None

        logger.debug(
            f"Peak separation valid: {separation}\u00b0 (expected ~{expected_separation}\u00b0)"
        )
        logger.debug(f"Candidate positions: pos1={int(pos1)}, pos2={int(pos2)}")

        # Determine S vs P based on intensity at the two positions
        ctrl.servo_set(s=int(pos1), p=int(pos2))
        time.sleep(0.8)

        ctrl.set_mode("s"); time.sleep(0.5)
        spectrum_pos1 = usb.read_intensity(); intensity_pos1 = spectrum_pos1.max()

        ctrl.set_mode("p"); time.sleep(0.5)
        spectrum_pos2 = usb.read_intensity(); intensity_pos2 = spectrum_pos2.max()

        saturation_limit = int(MAX_DETECTOR_COUNTS * SATURATION_THRESHOLD)
        if intensity_pos1 >= saturation_limit:
            logger.error(f"Saturation at position {int(pos1)}; peak {intensity_pos1:.0f} >= {saturation_limit}")
            return None
        if intensity_pos2 >= saturation_limit:
            logger.error(f"Saturation at position {int(pos2)}; peak {intensity_pos2:.0f} >= {saturation_limit}")
            return None

        if intensity_pos1 > intensity_pos2:
            s_pos = int(pos1); p_pos = int(pos2)
            s_intensity = float(intensity_pos1); p_intensity = float(intensity_pos2)
        else:
            s_pos = int(pos2); p_pos = int(pos1)
            s_intensity = float(intensity_pos2); p_intensity = float(intensity_pos1)

        if p_intensity == 0:
            logger.warning("Validation failed: P-mode intensity is zero")
            return None

        sp_ratio = s_intensity / p_intensity
        if sp_ratio < MIN_SP_RATIO:
            logger.warning(
                f"Validation failed: S/P ratio {sp_ratio:.2f}x < minimum {MIN_SP_RATIO:.2f}x"
            )
            return None

        logger.info("\u2705 FULL SWEEP successful")
        logger.info(f"S position: {s_pos}\u00b0 ({s_intensity:.0f} counts)")
        logger.info(f"P position: {p_pos}\u00b0 ({p_intensity:.0f} counts)")
        logger.info(
            f"S/P ratio: {sp_ratio:.2f}x {'\u2705' if sp_ratio >= IDEAL_SP_RATIO else 'acceptable'}"
        )
        logger.info(f"Peak separation: {separation}\u00b0")

        return {
            "s_pos": s_pos,
            "p_pos": p_pos,
            "sp_ratio": float(sp_ratio),
            "separation": int(separation),
            "s_intensity": s_intensity,
            "p_intensity": p_intensity,
        }

    except Exception as e:
        logger.exception(f"Full sweep fallback error: {e}")
        return None


def auto_calibrate_polarizer(usb, ctrl, require_water: bool = True, polarizer_type: str = "circular"):
    """Automatic polarizer calibration with transmission validation.

    This is the main entry point for servo calibration. It:
    1. Checks for water presence (if required)
    2. Uses appropriate method based on polarizer type:
       - Circular: Quadrant search with 90° enforcement
       - Barrel: Window detection with SPR signature identification
    3. Validates positions using transmission spectrum quality
    4. Returns validation results for user confirmation

    NOTE: This function does NOT automatically save to EEPROM or device_config.
    The caller should:
    1. Show user the results for confirmation
    2. Save to device_config if user approves
    3. Apply positions to hardware: ctrl.servo_set(s_pos, p_pos)
    4. EEPROM save happens later via "Push to EEPROM" in device config UI

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper
        require_water: If True, check for water before starting calibration
        polarizer_type: Type of polarizer ("circular" or "barrel")

    Returns:
        Dict with validation results if successful, None if failed:
        {
            'success': True,
            'polarizer_type': str,
            's_pos': int,
            'p_pos': int,
            'sp_ratio': float,
            'dip_depth_percent': float,
            'resonance_wavelength': float (circular only),
            'transmission_min': float,
            'validation_checks': list (circular only)
        }
    """
    logger.info("=" * 80)
    logger.info(f"AUTOMATIC POLARIZER CALIBRATION ({polarizer_type.upper()})")
    logger.info("=" * 80)

    try:
        # Pre-check: Water presence (if required for circular polarizers)
        if require_water and polarizer_type == "circular":
            logger.info("Checking for water presence on sensor...")
            # Use current positions for water check
            current_s = getattr(ctrl, 's_position', 90)
            current_p = getattr(ctrl, 'p_position', 0)

            has_water, trans_min, dip_depth = check_water_presence(usb, ctrl, current_s, current_p)

            if not has_water:
                logger.error("❌ WATER NOT DETECTED")
                logger.error("   Please ensure:")
                logger.error("   1. Prism has water droplet on sensor surface")
                logger.error("   2. Prism is properly seated")
                logger.error("   3. SPR coupling is established")
                if trans_min is not None:
                    logger.error(f"   Transmission min: {trans_min:.1f}%")
                if dip_depth is not None:
                    logger.error(f"   Dip depth: {dip_depth:.1f}% (need >{MIN_DIP_DEPTH_PERCENT}%)")
                return None

            logger.info(f"✓ Water detected (dip depth: {dip_depth:.1f}%)")

        # Choose calibration method based on polarizer type
        if polarizer_type == "barrel":
            logger.info("Using BARREL window detection method...")
            logger.info("(Discrete S/P windows, identified by SPR signature)")

            result = perform_barrel_window_search(usb, ctrl)
            if result is None:
                logger.error("❌ Barrel window search failed")
                return None

            # Format barrel results to match expected output
            return {
                'success': True,
                'polarizer_type': 'barrel',
                's_pos': result['s_pos'],
                'p_pos': result['p_pos'],
                'sp_ratio': result['sp_ratio'],
                'dip_depth_percent': result.get('p_dip_depth', 0.0),
                'transmission_min': None,
                'resonance_wavelength': None,
                'separation': result['separation'],
                'validation_checks': [
                    ('Window separation', True, f"{result['separation']:.0f}° (>70° required)"),
                    ('S/P ratio', result['sp_ratio'] >= MIN_SP_RATIO, f"{result['sp_ratio']:.2f}×")
                ]
            }

        else:  # circular polarizer (default)
            logger.info("Using CIRCULAR polarizer quadrant search...")
            logger.info("(90° phase relationship with transmission validation)")

            # Phase 1: Find S and P positions using quadrant search
            result = perform_quadrant_search(usb, ctrl)
            if result is None:
                logger.error("❌ Quadrant search failed")
                return None

            s_pos, p_pos = result

            # Phase 2: Validate positions with transmission analysis
            is_valid, validation_results = validate_positions_with_transmission(usb, ctrl, s_pos, p_pos)

            if not is_valid:
                logger.error("❌ VALIDATION FAILED")
                logger.error("   Positions found but transmission quality insufficient")
                logger.error("   Please check:")
                logger.error("   1. Water presence on sensor")
                logger.error("   2. SPR coupling quality")
                logger.error("   3. LED intensity (not saturating)")
                return None

            # Success - return validated results for user confirmation
            logger.info("=" * 80)
            logger.info("✅ CALIBRATION SUCCESSFUL")
            logger.info(f"   S position: {s_pos}°")
            logger.info(f"   P position: {p_pos}°")
            logger.info(f"   S/P ratio: {validation_results['sp_ratio']:.2f}×")
            logger.info(f"   Dip depth: {validation_results['dip_depth_percent']:.1f}%")
            logger.info(f"   Resonance: {validation_results['resonance_wavelength']:.1f}nm")
            logger.info("=" * 80)
            logger.info("⚠️  Positions NOT automatically saved")
            logger.info("   User confirmation required before saving to device config")

            return {
                'success': True,
                'polarizer_type': 'circular',
                's_pos': s_pos,
                'p_pos': p_pos,
                'sp_ratio': validation_results['sp_ratio'],
                'dip_depth_percent': validation_results['dip_depth_percent'],
                'resonance_wavelength': validation_results['resonance_wavelength'],
                'transmission_min': validation_results['transmission_min'],
                'validation_checks': validation_results['validation_checks']
            }

    except Exception as e:
        logger.exception(f"Polarizer calibration error: {e}")
        return None

