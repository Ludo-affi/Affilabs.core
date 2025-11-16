"""Servo position calibration for circular polarizer using quadrant search.

This module provides efficient servo calibration for SPR systems with circular
polarizers. Uses a 3-phase quadrant search (13 measurements) instead of full
sweep (33 measurements) for faster calibration.

Key features:
- ROI-based measurement (605-635nm around SPR resonance)
- Resonance wavelength validation (590-670nm)
- Automatic inversion detection and correction
- Dip depth validation (≥10% required)
- S/P separation validation (80-100° for circular polarizer)
"""

import time
import numpy as np
from scipy.signal import find_peaks, peak_prominences, peak_widths
from utils.logger import logger

# Calibration parameters
MIN_ANGLE = 10          # Start of servo range
MAX_ANGLE = 170         # End of servo range
SETTLING_TIME = 0.2     # Servo settling time (seconds)
MODE_SWITCH_TIME = 0.1  # Time to switch between S/P modes (seconds)

# ROI for SPR resonance measurement
ROI_CENTER = 620        # Center wavelength for ROI (nm)
ROI_WIDTH = 30          # Width of ROI (nm) - measures 605-635nm

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
MIN_DIP_DEPTH_PERCENT = 10.0       # Minimum resonance dip depth (% of max)


def get_roi_intensity(spectrum, wavelengths):
    """Extract maximum intensity from ROI around SPR resonance.

    Args:
        spectrum: Full spectrum intensity array
        wavelengths: Wavelength array corresponding to spectrum

    Returns:
        float: Maximum intensity in ROI
    """
    roi_min = ROI_CENTER - ROI_WIDTH / 2
    roi_max = ROI_CENTER + ROI_WIDTH / 2

    roi_mask = (wavelengths >= roi_min) & (wavelengths <= roi_max)
    roi_spectrum = spectrum[roi_mask]

    if len(roi_spectrum) == 0:
        return float(spectrum.max())

    return float(roi_spectrum.max())


def perform_quadrant_search(usb, ctrl):
    """Perform smart quadrant search to find S and P positions efficiently.

    Uses a coarse 5-point search across the servo range, then refines around
    the min and max positions. Much faster than full sweep (13 vs 33 measurements).

    Assumes integration time is already set from LED calibration.

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper

    Returns:
        tuple: (positions, intensities) - all measured positions and intensities
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

    # Note: Integration time already set by LED calibration
    logger.info(f"ROI: {ROI_CENTER - ROI_WIDTH/2:.0f}-{ROI_CENTER + ROI_WIDTH/2:.0f}nm (SPR resonance region)")

    # Store all measurements
    all_positions = []
    all_intensities = []

    def measure_position(angle):
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

    # Find approximate min (P position)
    coarse_min_idx = np.argmin(coarse_intensities)
    approx_p = coarse_positions[coarse_min_idx]

    logger.info(f"Approximate P position found:")
    logger.info(f"   P (min) ≈ {approx_p}° ({coarse_intensities[coarse_min_idx]:.0f} counts)")

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

    # Find refined P position
    p_pos = min(p_intensities.keys(), key=lambda k: p_intensities[k])
    p_intensity = p_intensities[p_pos]
    logger.info(f"✓ P position refined: {p_pos}° ({p_intensity:.0f} counts)")

    # PHASE 3: Set S position exactly 90° from P
    # For circular polarizer: S = P ± 90° (EXACT)
    # Choose the option that's within servo range (0-180°)
    s_candidate_1 = p_pos - 90
    s_candidate_2 = p_pos + 90

    if MIN_ANGLE <= s_candidate_1 <= MAX_ANGLE:
        s_pos = s_candidate_1
        logger.info(f"Phase 3: S position = P - 90° = {p_pos}° - 90° = {s_pos}°")
    elif MIN_ANGLE <= s_candidate_2 <= MAX_ANGLE:
        s_pos = s_candidate_2
        logger.info(f"Phase 3: S position = P + 90° = {p_pos}° + 90° = {s_pos}°")
    else:
        # This shouldn't happen if P is found correctly (P should be 10-170, so ±90 always gives valid range)
        logger.error(f"❌ ERROR: Cannot place S position 90° from P={p_pos}°")
        logger.error(f"   P - 90 = {s_candidate_1}° (out of range)")
        logger.error(f"   P + 90 = {s_candidate_2}° (out of range)")
        return None, None, None, None

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

    Barrel assemblies present transmission "windows" for S and P modes. We:
    - Sweep the servo and measure P-mode ROI intensity to find the P window (max).
    - Set S target exactly 90° from P, then refine S around that target by S-mode ROI max.
    - Return positions and quick stats (separation, S/P ratio at ROI).

    Assumptions:
    - Valid servo range is 10-170°.
    - Integration time already configured.
    """
    try:
        logger.info("=" * 80)
        logger.info("BARREL POLARIZER CALIBRATION (window-based)")
        logger.info("=" * 80)

        # Get wavelength array for ROI computations
        wavelengths = getattr(usb, "_wavelengths", None)
        use_roi = wavelengths is not None
        if use_roi:
            logger.info(f"ROI: {ROI_CENTER - ROI_WIDTH/2:.0f}-{ROI_CENTER + ROI_WIDTH/2:.0f}nm")
        else:
            logger.warning("Wavelengths unavailable; using full-spectrum max for window search")

        def roi_value(spectrum):
            return get_roi_intensity(spectrum, wavelengths) if use_roi else float(spectrum.max())

        # Sweep to find P window (P-mode max transmission)
        logger.info("Phase 1: P-window sweep (max ROI in P-mode)")
        sweep_positions = list(range(MIN_ANGLE, MAX_ANGLE + 1, 5))
        p_curve = []

        for angle in sweep_positions:
            ctrl.servo_set(s=angle, p=angle)
            time.sleep(SETTLING_TIME)
            ctrl.set_mode("p")
            time.sleep(MODE_SWITCH_TIME)
            spectrum = usb.read_intensity()
            p_curve.append(roi_value(spectrum))

        p_idx = int(np.argmax(p_curve))
        p_pos_coarse = sweep_positions[p_idx]
        p_val_coarse = p_curve[p_idx]
        logger.info(f"   Coarse P window at {p_pos_coarse}° (ROI={p_val_coarse:.0f})")

        # Refine P window around coarse maximum within ±20°
        logger.info("Phase 2: P-window refinement (±20°)")
        refine_P = []
        refine_P_pos = []
        for delta in (-20, -10, 0, 10, 20):
            pos = int(np.clip(p_pos_coarse + delta, MIN_ANGLE, MAX_ANGLE))
            if pos in refine_P_pos:
                continue
            ctrl.servo_set(s=pos, p=pos)
            time.sleep(SETTLING_TIME)
            ctrl.set_mode("p")
            time.sleep(MODE_SWITCH_TIME)
            spectrum = usb.read_intensity()
            refine_P_pos.append(pos)
            refine_P.append(roi_value(spectrum))
            logger.debug(f"   P {pos}° -> {refine_P[-1]:.0f}")

        p_pos = int(refine_P_pos[int(np.argmax(refine_P))])
        p_val = float(max(refine_P))
        logger.info(f"✓ P window refined: {p_pos}° (ROI={p_val:.0f})")

        # Choose S target 90° from refined P
        s_target1 = p_pos - 90
        s_target2 = p_pos + 90
        if MIN_ANGLE <= s_target1 <= MAX_ANGLE:
            s_target = s_target1
        elif MIN_ANGLE <= s_target2 <= MAX_ANGLE:
            s_target = s_target2
        else:
            # Unlikely with our range; fallback to opposite extreme
            s_target = int(np.clip(p_pos + 90, MIN_ANGLE, MAX_ANGLE))
        logger.info(f"Phase 3: S-window refinement around {s_target}° (±20°)")

        refine_S = []
        refine_S_pos = []
        for delta in (-20, -10, 0, 10, 20):
            pos = int(np.clip(s_target + delta, MIN_ANGLE, MAX_ANGLE))
            if pos in refine_S_pos:
                continue
            ctrl.servo_set(s=pos, p=pos)
            time.sleep(SETTLING_TIME)
            ctrl.set_mode("s")
            time.sleep(MODE_SWITCH_TIME)
            spectrum = usb.read_intensity()
            refine_S_pos.append(pos)
            refine_S.append(roi_value(spectrum))
            logger.debug(f"   S {pos}° -> {refine_S[-1]:.0f}")

        s_pos = int(refine_S_pos[int(np.argmax(refine_S))])
        s_val = float(max(refine_S))
        separation = abs(s_pos - p_pos)
        logger.info(f"✓ S window refined: {s_pos}° (ROI={s_val:.0f})")
        logger.info(f"✓ Separation ~ {separation}° (target 90°)")

        # Quick measure S and P at final positions for ratio
        ctrl.servo_set(s=s_pos, p=p_pos)
        time.sleep(SETTLING_TIME)
        ctrl.set_mode("s")
        time.sleep(MODE_SWITCH_TIME)
        s_meas = roi_value(usb.read_intensity())
        ctrl.set_mode("p")
        time.sleep(MODE_SWITCH_TIME)
        p_meas = roi_value(usb.read_intensity())
        sp_ratio = s_meas / p_meas if p_meas > 0 else 0.0
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
