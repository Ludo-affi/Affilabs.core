"""Servo Calibration Test Script
==============================
Test and nail down the servo position calibration sequence before porting to main.py

This script implements the complete servo calibration workflow with:
- Hardware connection (spectrometer + controller)
- Position sweep (10-170°, 5° steps)
- Resonance dip detection (P = MINIMUM transmission)
- Reference maximum detection (S = MAXIMUM transmission)
- S/P intensity verification
- Retry logic with detailed diagnostics
- EEPROM persistence option

SPR Principle:
- P position = MINIMUM transmission (resonance dip at sample surface)
- S position = MAXIMUM transmission (reference, no resonance)

Usage:
    python test_servo_calibration.py [--force] [--save]

    --force: Skip fast validation, always do full sweep
    --save:  Save positions to EEPROM after successful calibration
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import hardware wrappers
# Settings
from settings.settings import LED_DELAY, MIN_INTEGRATION, POL_WAVELENGTH
from utils.controller import PicoP4SPR
from utils.usb4000_wrapper import USB4000

# Detector specifications (Ocean Optics Flame-T)
DETECTOR_MAX_COUNTS = 62000  # Actual max for Flame-T (not 65535!)
TARGET_COUNTS = int(0.75 * DETECTOR_MAX_COUNTS)  # 46,500 counts (75% of detector max)

# Calibration parameters
MIN_ANGLE = 10  # Start of servo sweep
MAX_ANGLE = 170  # End of servo sweep
ANGLE_STEP = 5  # Step size for sweep
LED_CHANNEL = "a"  # LED channel to use
LED_INTENSITY = 255  # Full intensity for sweep
SETTLING_TIME = 0.2  # Servo settling time (seconds)
MODE_SWITCH_TIME = 0.1  # Mode switch delay (seconds)

# ROI parameters for SPR resonance detection
ROI_CENTER = POL_WAVELENGTH  # 620nm - SPR resonance wavelength
ROI_WIDTH = 30  # ±15nm around center (605-635nm range)

# Resonance wavelength validation (where P position minimum should occur)
MIN_RESONANCE_WL = 590  # Minimum valid resonance wavelength (nm)
MAX_RESONANCE_WL = 670  # Maximum valid resonance wavelength (nm)
# Typical: ~620nm, sometimes 590-670nm range for safety

# Validation thresholds
MIN_SEPARATION = (
    80  # Minimum S-P separation (degrees) - tighter window for circular polarizer
)
MAX_SEPARATION = (
    100  # Maximum S-P separation (degrees) - tighter window for circular polarizer
)
MIN_SP_RATIO = 1.3  # Minimum S/P intensity ratio
IDEAL_SP_RATIO = 1.5  # Ideal S/P intensity ratio
MIN_DIP_DEPTH_PERCENT = 10.0  # Minimum resonance dip depth (% of max)
MIN_DIP_DEPTH_PERCENT = 10.0  # Minimum resonance dip depth (% of max)
MAX_RETRIES = 3  # Maximum calibration attempts

# EEPROM validation thresholds
FAST_VALIDATION_RATIO = 1.3  # Minimum ratio for fast validation


def setup_hardware():
    """Initialize spectrometer and controller.

    Returns:
        tuple: (usb, ctrl) - spectrometer and controller objects
        None if initialization fails

    """
    print("=" * 80)
    print("HARDWARE INITIALIZATION")
    print("=" * 80)

    # Initialize spectrometer
    print("\n1. Connecting to spectrometer...")
    try:
        usb = USB4000()
        if not usb.open():
            raise Exception("Failed to open spectrometer")

        wavelengths = usb._wavelengths
        if wavelengths is None:
            raise Exception("Could not read wavelengths")

        print("   ✓ Connected: USB4000/FLAME-T")
        print(f"   ✓ Serial: {usb.serial_number}")
        print(f"   ✓ Wavelength range: {wavelengths[0]:.1f} - {wavelengths[-1]:.1f} nm")
        print(f"   ✓ Pixels: {len(wavelengths)}")
    except Exception as e:
        print(f"   ✗ Failed to connect to spectrometer: {e}")
        return None, None

    # Initialize controller
    print("\n2. Connecting to controller...")
    try:
        ctrl = PicoP4SPR()
        if not ctrl.open():
            raise Exception("Failed to open controller")

        print(f"   ✓ Connected: PicoP4SPR {ctrl.version}")

        # Test servo read
        pos_dict = ctrl.servo_get()
        s_pos = int(pos_dict.get("s", b"0"))
        p_pos = int(pos_dict.get("p", b"0"))
        print(f"   ✓ Current servo positions: S={s_pos}°, P={p_pos}°")
    except Exception as e:
        print(f"   ✗ Failed to connect to controller: {e}")
        return usb, None

    print("\n✅ Hardware initialization complete")
    return usb, ctrl


def fast_validation(usb, ctrl):
    """Quick validation of stored EEPROM positions.

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper

    Returns:
        tuple: (is_valid, ratio, s_pos, p_pos)
        - is_valid: True if positions are good
        - ratio: Measured S/P intensity ratio
        - s_pos: S-mode servo position
        - p_pos: P-mode servo position

    """
    print("\n" + "=" * 80)
    print("FAST VALIDATION (EEPROM POSITIONS)")
    print("=" * 80)

    try:
        # Get current positions from EEPROM
        pos_dict = ctrl.servo_get()
        s_pos = int(pos_dict.get("s", b"0"))
        p_pos = int(pos_dict.get("p", b"0"))
        print(f"   Current EEPROM positions: S={s_pos}°, P={p_pos}°")

        # Check if positions look reasonable
        if s_pos == 0 or p_pos == 0:
            print("   ⚠️  Invalid positions (zero detected)")
            return False, 0.0, s_pos, p_pos

        separation = abs(p_pos - s_pos)
        print(f"   Position separation: {separation}°")

        if separation < MIN_SEPARATION or separation > MAX_SEPARATION:
            print(f"   ⚠️  Separation out of range ({MIN_SEPARATION}-{MAX_SEPARATION}°)")
            return False, 0.0, s_pos, p_pos

        # Measure actual intensities
        print("\n   Measuring intensities at stored positions...")

        # Set LED on
        ctrl.set_intensity(LED_CHANNEL, LED_INTENSITY)
        time.sleep(LED_DELAY)

        # Measure S-mode
        ctrl.set_mode("s")
        time.sleep(MODE_SWITCH_TIME)
        s_spectrum = usb.read_intensity()
        s_intensity = float(np.max(s_spectrum))

        # Measure P-mode
        ctrl.set_mode("p")
        time.sleep(MODE_SWITCH_TIME)
        p_spectrum = usb.read_intensity()
        p_intensity = float(np.max(p_spectrum))

        # LED off
        ctrl.turn_off_channels()

        # Calculate ratio
        sp_ratio = s_intensity / p_intensity if p_intensity > 0 else 0.0

        print(f"   S-mode intensity: {s_intensity:.0f} counts")
        print(f"   P-mode intensity: {p_intensity:.0f} counts")
        print(f"   S/P ratio: {sp_ratio:.2f}×")

        # Validate ratio
        if sp_ratio >= FAST_VALIDATION_RATIO:
            status = "✅ VALID" if sp_ratio >= IDEAL_SP_RATIO else "✅ ACCEPTABLE"
            print(f"   {status} - Stored positions are good")
            return True, sp_ratio, s_pos, p_pos
        print(f"   ❌ INVALID - Ratio too low (minimum: {FAST_VALIDATION_RATIO:.2f}×)")
        return False, sp_ratio, s_pos, p_pos

    except Exception as e:
        print(f"   ⚠️  Validation failed: {e}")
        import traceback

        traceback.print_exc()
        return False, 0.0, 0, 0


def get_roi_intensity(spectrum, wavelengths):
    """Extract maximum intensity from ROI around SPR resonance wavelength.

    Args:
        spectrum: Full spectrum intensity array
        wavelengths: Wavelength array corresponding to spectrum

    Returns:
        float: Maximum intensity in ROI

    """
    # Find indices for ROI
    roi_min = ROI_CENTER - ROI_WIDTH / 2
    roi_max = ROI_CENTER + ROI_WIDTH / 2

    roi_mask = (wavelengths >= roi_min) & (wavelengths <= roi_max)
    roi_spectrum = spectrum[roi_mask]

    if len(roi_spectrum) == 0:
        # Fallback to full spectrum if ROI is empty
        return float(spectrum.max())

    return float(roi_spectrum.max())


def perform_quadrant_search(usb, ctrl):
    """Perform smart quadrant search to find S and P positions efficiently.

    Uses a coarse 5-point search across the servo range, then refines around
    the min and max positions. Much faster than full sweep (13 vs 33 measurements).

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper

    Returns:
        tuple: (positions, intensities) - all measured positions and intensities

    """
    print("\n" + "=" * 80)
    print("QUADRANT SEARCH FOR SERVO POSITIONS")
    print("=" * 80)

    # Get wavelengths for ROI calculation
    wavelengths = usb._wavelengths
    if wavelengths is None:
        print("   ⚠️  Warning: Wavelengths not available, using full spectrum max")
        use_roi = False
    else:
        use_roi = True

    # Setup hardware
    ctrl.set_intensity(LED_CHANNEL, LED_INTENSITY)
    time.sleep(LED_DELAY)

    # Set integration time (matches main.py)
    # usb.min_integration is in seconds, MIN_INTEGRATION is in milliseconds
    integration_time_seconds = max(MIN_INTEGRATION / 1000.0, usb.min_integration)
    integration_time_ms = integration_time_seconds * 1000.0
    usb.set_integration(integration_time_ms)  # Function expects milliseconds
    print(f"   Integration time: {integration_time_ms:.1f}ms")
    print(
        f"   ROI: {ROI_CENTER - ROI_WIDTH/2:.0f}-{ROI_CENTER + ROI_WIDTH/2:.0f}nm (SPR resonance region)",
    )

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
        intensity = (
            get_roi_intensity(spectrum, wavelengths) if use_roi else spectrum.max()
        )
        all_positions.append(angle)
        all_intensities.append(intensity)
        return intensity

    # PHASE 1: Coarse search - 5 positions across range
    print("\n   Phase 1: Coarse search (5 positions)...")
    coarse_positions = [10, 50, 90, 130, 170]
    coarse_intensities = []

    for pos in coarse_positions:
        intensity = measure_position(pos)
        coarse_intensities.append(intensity)
        print(f"      {pos}°: {intensity:.0f} counts")

    # Find approximate min (P position)
    coarse_min_idx = np.argmin(coarse_intensities)
    approx_p = coarse_positions[coarse_min_idx]

    print("\n   Approximate P position found:")
    print(
        f"      P (min) ≈ {approx_p}° ({coarse_intensities[coarse_min_idx]:.0f} counts)",
    )

    # PHASE 2: Refine P position (minimum)
    print(f"\n   Phase 2: Refining P position around {approx_p}°...")
    p_search_positions = [
        max(MIN_ANGLE, approx_p - 20),
        max(MIN_ANGLE, approx_p - 10),
        approx_p,
        min(MAX_ANGLE, approx_p + 10),
        min(MAX_ANGLE, approx_p + 20),
    ]
    # Remove duplicates and already measured
    p_search_positions = [p for p in p_search_positions if p not in all_positions]

    p_intensities = {approx_p: coarse_intensities[coarse_min_idx]}
    for pos in p_search_positions:
        intensity = measure_position(pos)
        p_intensities[pos] = intensity
        print(f"      {pos}°: {intensity:.0f} counts")

    # Find refined P position
    p_pos = min(p_intensities.keys(), key=lambda k: p_intensities[k])
    p_intensity = p_intensities[p_pos]
    print(f"   ✓ P position refined: {p_pos}° ({p_intensity:.0f} counts)")

    # PHASE 3: Refine S position (maximum) - must be 90° from P
    # For circular polarizer: S = P ± 90°
    # Choose the option that's within servo range (0-180°)
    s_candidate_1 = p_pos - 90
    s_candidate_2 = p_pos + 90

    if MIN_ANGLE <= s_candidate_1 <= MAX_ANGLE:
        approx_s = s_candidate_1
    elif MIN_ANGLE <= s_candidate_2 <= MAX_ANGLE:
        approx_s = s_candidate_2
    else:
        # Fallback: use coarse max if both candidates out of range
        coarse_max_idx = np.argmax(coarse_intensities)
        approx_s = coarse_positions[coarse_max_idx]
        print(f"   ⚠️  Both S candidates out of range, using coarse max at {approx_s}°")

    print(f"\n   Phase 3: Refining S position around {approx_s}° (90° from P)...")
    s_search_positions = [
        max(MIN_ANGLE, approx_s - 20),
        max(MIN_ANGLE, approx_s - 10),
        approx_s,
        min(MAX_ANGLE, approx_s + 10),
        min(MAX_ANGLE, approx_s + 20),
    ]
    # Remove duplicates and already measured
    s_search_positions = [s for s in s_search_positions if s not in all_positions]

    # Initialize with measured value if approx_s was in coarse positions
    s_intensities = {}
    if approx_s in coarse_positions:
        idx = coarse_positions.index(approx_s)
        s_intensities[approx_s] = coarse_intensities[idx]
    elif approx_s not in all_positions:
        # Need to measure it first
        s_intensities[approx_s] = measure_position(approx_s)
        print(f"      {approx_s}°: {s_intensities[approx_s]:.0f} counts")

    for pos in s_search_positions:
        intensity = measure_position(pos)
        s_intensities[pos] = intensity
        print(f"      {pos}°: {intensity:.0f} counts")

    # Find refined S position
    s_pos = max(s_intensities.keys(), key=lambda k: s_intensities[k])
    s_intensity = s_intensities[s_pos]
    print(f"   ✓ S position refined: {s_pos}° ({s_intensity:.0f} counts)")

    # LED off
    ctrl.turn_off_channels()

    print("\n   ✅ Quadrant search complete")
    print(f"   Total measurements: {len(all_positions)} (vs 33 for full sweep)")

    # Return all measured data plus the found positions
    return np.array(all_positions), np.array(all_intensities), p_pos, s_pos


def perform_sweep(usb, ctrl):
    """Wrapper that calls the efficient quadrant search instead of full sweep.

    Kept for backwards compatibility with existing code that calls perform_sweep().
    """
    positions, intensities, p_pos, s_pos = perform_quadrant_search(usb, ctrl)
    return positions, intensities, p_pos, s_pos
    print(
        f"   Intensity range: {roi_intensities.min():.0f} - {roi_intensities.max():.0f} counts",
    )

    return positions, roi_intensities


def find_resonance_wavelength(ctrl, usb, servo_position):
    """Measure the wavelength where minimum intensity occurs at a given servo position.

    Args:
        ctrl: Controller wrapper
        usb: Spectrometer wrapper
        servo_position: Servo angle to test

    Returns:
        float: Wavelength (nm) where minimum intensity occurs, or None if unavailable

    """
    wavelengths = usb._wavelengths
    if wavelengths is None:
        return None

    # Set servo to test position
    ctrl.servo_set(servo_position, servo_position)
    time.sleep(SETTLING_TIME)

    # Turn on LED
    ctrl.set_intensity(LED_CHANNEL, LED_INTENSITY)
    time.sleep(LED_DELAY)

    # Measure P-mode spectrum (where resonance should appear)
    ctrl.set_mode("p")
    time.sleep(MODE_SWITCH_TIME)
    spectrum = usb.read_intensity()

    # LED off
    ctrl.turn_off_channels()

    # Find wavelength of minimum intensity in SPR region
    roi_min = MIN_RESONANCE_WL  # 590nm
    roi_max = MAX_RESONANCE_WL  # 670nm
    roi_mask = (wavelengths >= roi_min) & (wavelengths <= roi_max)
    roi_spectrum = spectrum[roi_mask]
    roi_wavelengths = wavelengths[roi_mask]

    if len(roi_spectrum) > 0:
        min_idx = np.argmin(roi_spectrum)
        return float(roi_wavelengths[min_idx])

    return None


def analyze_peaks(positions, intensities, usb, ctrl):
    """Analyze sweep data to find optimal S and P positions.

    For SPR:
    - P position = MINIMUM transmission (resonance dip) - LOW intensity
    - S position = MAXIMUM transmission (reference) - HIGH intensity
    - Resonance dip must occur in 590-660nm range

    Args:
        positions: Array of servo angles
        intensities: Array of max intensities
        usb: Spectrometer wrapper (for wavelength validation)
        ctrl: Controller wrapper (for wavelength validation)

    Returns:
        dict: Analysis results with keys:
            - success: True if valid positions found
            - s_pos: S-mode servo position (high transmission)
            - p_pos: P-mode servo position (low transmission - resonance dip)
            - s_intensity: S-mode intensity (high)
            - p_intensity: P-mode intensity (low)
            - separation: Distance between S and P positions
            - sp_ratio: S/P intensity ratio
            - resonance_wavelength: Wavelength where dip occurs (nm)
            - validation: List of validation results

    """
    print("\n" + "=" * 80)
    print("RESONANCE DIP ANALYSIS (SPR)")
    print("=" * 80)

    results = {
        "success": False,
        "s_pos": 0,
        "p_pos": 0,
        "s_intensity": 0.0,
        "p_intensity": 0.0,
        "separation": 0.0,
        "sp_ratio": 0.0,
        "resonance_wavelength": None,
        "validation": [],
    }

    # Find MINIMUM (resonance dip for P position)
    print("\n1. Finding Resonance Dip (P position):")
    min_idx = np.argmin(intensities)
    p_position = positions[min_idx]
    p_intensity = intensities[min_idx]

    print(f"   P position (MINIMUM): {p_position}°")
    print(f"   P intensity: {p_intensity:.0f} counts (LOW - resonance dip)")

    # Measure wavelength where resonance occurs
    resonance_wavelength = find_resonance_wavelength(ctrl, usb, p_position)
    results["resonance_wavelength"] = resonance_wavelength

    if resonance_wavelength is not None:
        print(f"   Resonance wavelength: {resonance_wavelength:.1f}nm")

        # Validation 0: Check resonance is in valid wavelength range
        MIN_RESONANCE_WL = 590  # nm
        MAX_RESONANCE_WL = 660  # nm

        if (
            resonance_wavelength < MIN_RESONANCE_WL
            or resonance_wavelength > MAX_RESONANCE_WL
        ):
            results["validation"].append(
                (
                    "Resonance wavelength",
                    False,
                    f"{resonance_wavelength:.1f}nm not in [{MIN_RESONANCE_WL}, {MAX_RESONANCE_WL}]nm",
                ),
            )
            print(
                f"   ❌ FAIL: Resonance outside valid range ({MIN_RESONANCE_WL}-{MAX_RESONANCE_WL}nm)",
            )
            print("   This suggests incorrect servo position or optical misalignment")
            return results
        results["validation"].append(
            (
                "Resonance wavelength",
                True,
                f"{resonance_wavelength:.1f}nm in [{MIN_RESONANCE_WL}, {MAX_RESONANCE_WL}]nm",
            ),
        )
        print("   ✓ PASS: Resonance in valid SPR range")
    else:
        print("   ⚠️  Warning: Could not determine resonance wavelength")

    # Validation 1: Check that minimum is significant
    intensity_range = intensities.max() - intensities.min()
    dip_depth = intensities.max() - p_intensity
    dip_depth_percent = (
        (dip_depth / intensities.max()) * 100 if intensities.max() > 0 else 0
    )

    print(f"   Dip depth: {dip_depth:.0f} counts ({dip_depth_percent:.1f}% of maximum)")

    MIN_DIP_DEPTH_PERCENT = 10.0  # Minimum 10% dip required
    if dip_depth_percent < MIN_DIP_DEPTH_PERCENT:
        results["validation"].append(
            (
                "Dip depth",
                False,
                f"{dip_depth_percent:.1f}% < {MIN_DIP_DEPTH_PERCENT}%",
            ),
        )
        print(f"   ❌ FAIL: Resonance dip too shallow (need >{MIN_DIP_DEPTH_PERCENT}%)")
        return results
    results["validation"].append(
        ("Dip depth", True, f"{dip_depth_percent:.1f}% >= {MIN_DIP_DEPTH_PERCENT}%"),
    )
    print("   ✓ PASS: Significant resonance dip detected")

    # Find MAXIMUM (reference for S position)
    print("\n2. Finding Reference Maximum (S position):")
    max_idx = np.argmax(intensities)
    s_position = positions[max_idx]
    s_intensity = intensities[max_idx]

    print(f"   S position (MAXIMUM): {s_position}°")
    print(f"   S intensity: {s_intensity:.0f} counts (HIGH - reference)")

    # Calculate separation
    separation = abs(s_position - p_position)
    results["separation"] = separation

    # Validation 2: Check separation
    print("\n3. Position Separation:")
    print(f"   Measured: {separation:.0f}°")
    print(f"   Expected: {MIN_SEPARATION}-{MAX_SEPARATION}°")

    if separation < MIN_SEPARATION or separation > MAX_SEPARATION:
        results["validation"].append(
            (
                "Position separation",
                False,
                f"{separation:.0f}° not in [{MIN_SEPARATION}, {MAX_SEPARATION}]",
            ),
        )
        print("   ❌ FAIL: Separation out of range")
        return results
    results["validation"].append(
        (
            "Position separation",
            True,
            f"{separation:.0f}° in [{MIN_SEPARATION}, {MAX_SEPARATION}]",
        ),
    )
    print("   ✓ PASS: Separation is valid")

    # Store results
    results["s_pos"] = int(s_position)
    results["p_pos"] = int(p_position)
    results["s_intensity"] = float(s_intensity)
    results["p_intensity"] = float(p_intensity)

    # Validation 3: Verify S > P (intensity check)
    print("\n4. Intensity Verification:")
    print(f"   S-mode intensity: {results['s_intensity']:.0f} (HIGH - reference)")
    print(f"   P-mode intensity: {results['p_intensity']:.0f} (LOW - resonance)")

    if results["s_intensity"] <= results["p_intensity"]:
        results["validation"].append(
            (
                "S > P",
                False,
                f"S={results['s_intensity']:.0f} <= P={results['p_intensity']:.0f}",
            ),
        )
        print("   ❌ FAIL: S should be higher than P")
        return results
    results["validation"].append(
        (
            "S > P",
            True,
            f"S={results['s_intensity']:.0f} > P={results['p_intensity']:.0f}",
        ),
    )
    print("   ✓ PASS: S is higher than P")

    # Validation 4: Check S/P ratio
    results["sp_ratio"] = results["s_intensity"] / results["p_intensity"]

    print("\n5. S/P Ratio:")
    print(f"   Measured: {results['sp_ratio']:.2f}×")
    print(f"   Minimum: {MIN_SP_RATIO:.2f}×")
    print(f"   Ideal: {IDEAL_SP_RATIO:.2f}×")

    if results["sp_ratio"] < MIN_SP_RATIO:
        results["validation"].append(
            ("S/P ratio", False, f"{results['sp_ratio']:.2f}× < {MIN_SP_RATIO:.2f}×"),
        )
        print("   ❌ FAIL: Ratio too low")
        return results
    if results["sp_ratio"] < IDEAL_SP_RATIO:
        results["validation"].append(
            (
                "S/P ratio",
                True,
                f"{results['sp_ratio']:.2f}× >= {MIN_SP_RATIO:.2f}× (acceptable)",
            ),
        )
        print("   ✓ PASS: Ratio acceptable (but below ideal)")
    else:
        results["validation"].append(
            (
                "S/P ratio",
                True,
                f"{results['sp_ratio']:.2f}× >= {IDEAL_SP_RATIO:.2f}× (ideal)",
            ),
        )
        print("   ✓ PASS: Ratio is ideal")

    # All validations passed
    results["success"] = True

    print("\n" + "=" * 80)
    print("✅ ALL VALIDATIONS PASSED")
    print("=" * 80)
    print(f"   S position: {results['s_pos']}° (HIGH transmission)")
    print(f"   P position: {results['p_pos']}° (LOW transmission - resonance dip)")
    print(f"   S/P ratio: {results['sp_ratio']:.2f}×")

    return results


def verify_and_correct_positions(ctrl, usb, s_pos, p_pos):
    """Verify positions are correct and auto-correct if inverted.

    Measures actual intensities at the calculated positions to detect if
    S and P are inverted (P > S, which leads to >100% transmission in P-mode).
    If inverted, automatically swaps the positions.

    Args:
        ctrl: Controller wrapper
        usb: Spectrometer wrapper
        s_pos: Calculated S-mode servo position
        p_pos: Calculated P-mode servo position

    Returns:
        tuple: (corrected_s_pos, corrected_p_pos, was_inverted)

    """
    print("\n" + "=" * 80)
    print("POSITION VERIFICATION & INVERSION DETECTION")
    print("=" * 80)

    # Apply calculated positions
    print(f"\n   Testing calculated positions: S={s_pos}, P={p_pos}")
    ctrl.servo_set(s_pos, p_pos)
    time.sleep(0.5)

    # Get wavelengths for ROI
    wavelengths = usb._wavelengths
    use_roi = wavelengths is not None

    # Turn on LED
    ctrl.set_intensity(LED_CHANNEL, LED_INTENSITY)
    time.sleep(LED_DELAY)

    # Measure S-mode intensity
    ctrl.set_mode("s")
    time.sleep(MODE_SWITCH_TIME)
    s_spectrum = usb.read_intensity()
    if use_roi:
        s_measured = get_roi_intensity(s_spectrum, wavelengths)
    else:
        s_measured = s_spectrum.max()

    # Measure P-mode intensity
    ctrl.set_mode("p")
    time.sleep(MODE_SWITCH_TIME)
    p_spectrum = usb.read_intensity()
    if use_roi:
        p_measured = get_roi_intensity(p_spectrum, wavelengths)
    else:
        p_measured = p_spectrum.max()

    # LED off
    ctrl.turn_off_channels()

    print("\n   Measured intensities:")
    print(f"   S-mode: {s_measured:.0f} counts")
    print(f"   P-mode: {p_measured:.0f} counts")
    print(f"   Ratio:  {s_measured / p_measured:.2f}× (S/P)")

    # Check for inversion: P > S indicates positions are swapped
    if p_measured > s_measured:
        print("\n   ⚠️  INVERSION DETECTED!")
        print(
            f"   P-mode intensity ({p_measured:.0f}) > S-mode intensity ({s_measured:.0f})",
        )
        print("   This would cause >100% transmission in P-mode")
        print("\n   🔄 AUTO-CORRECTING: Swapping S and P positions")

        # Swap positions
        corrected_s_pos = p_pos
        corrected_p_pos = s_pos

        print("\n   Corrected positions:")
        print(f"   S position: {s_pos}° → {corrected_s_pos}°")
        print(f"   P position: {p_pos}° → {corrected_p_pos}°")

        # Verify the swap worked
        ctrl.servo_set(corrected_s_pos, corrected_p_pos)
        time.sleep(0.5)

        ctrl.set_intensity(LED_CHANNEL, LED_INTENSITY)
        time.sleep(LED_DELAY)

        ctrl.set_mode("s")
        time.sleep(MODE_SWITCH_TIME)
        s_verify = usb.read_intensity()
        if use_roi:
            s_verify_val = get_roi_intensity(s_verify, wavelengths)
        else:
            s_verify_val = s_verify.max()

        ctrl.set_mode("p")
        time.sleep(MODE_SWITCH_TIME)
        p_verify = usb.read_intensity()
        if use_roi:
            p_verify_val = get_roi_intensity(p_verify, wavelengths)
        else:
            p_verify_val = p_verify.max()

        ctrl.turn_off_channels()

        print("\n   Verification after swap:")
        print(f"   S-mode: {s_verify_val:.0f} counts")
        print(f"   P-mode: {p_verify_val:.0f} counts")
        print(f"   Ratio:  {s_verify_val / p_verify_val:.2f}× (S/P)")

        if s_verify_val > p_verify_val:
            print("   ✅ Swap successful - positions now correct!")
        else:
            print("   ⚠️  Warning: Positions still look inverted after swap")

        return corrected_s_pos, corrected_p_pos, True
    print("\n   ✅ Positions are correct (S > P)")
    print("   No inversion detected")
    return s_pos, p_pos, False


def apply_positions(ctrl, s_pos, p_pos, save_to_eeprom=False):
    """Apply servo positions to hardware.

    Args:
        ctrl: Controller wrapper
        s_pos: S-mode servo position
        p_pos: P-mode servo position
        save_to_eeprom: If True, save to EEPROM for persistence

    """
    print("\n" + "=" * 80)
    print("APPLYING POSITIONS")
    print("=" * 80)

    print(f"\n   Setting servo positions: S={s_pos}, P={p_pos}")
    ctrl.servo_set(s_pos, p_pos)
    time.sleep(0.5)

    # Verify positions were set
    pos_dict = ctrl.servo_get()
    try:
        read_s = int(pos_dict.get("s", b"0"))
        read_p = int(pos_dict.get("p", b"0"))
        print(f"   Readback positions: S={read_s}°, P={read_p}°")

        if read_s == s_pos and read_p == p_pos:
            print("   ✓ Positions verified")
        else:
            print(f"   ⚠️  Readback mismatch (expected S={s_pos}, P={p_pos})")
    except (ValueError, TypeError):
        print(f"   ⚠️  Could not parse readback positions: {pos_dict}")

    if save_to_eeprom:
        print("\n   💾 Saving to EEPROM...")
        ctrl.flash()
        time.sleep(0.5)
        print("   ✓ Positions saved to EEPROM (will persist across power cycles)")
    else:
        print("\n   ⚠️  Positions NOT saved to EEPROM (temporary)")


def calibrate_servo_positions(usb, ctrl, force_full=False, save_to_eeprom=False):
    """Main calibration routine with retry logic.

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper
        force_full: If True, skip fast validation
        save_to_eeprom: If True, save to EEPROM after success

    Returns:
        dict: Calibration results or None if failed

    """
    print("\n" + "=" * 80)
    print("SERVO POSITION CALIBRATION")
    print("=" * 80)

    # Try fast validation first unless forced
    if not force_full:
        is_valid, ratio, s_pos, p_pos = fast_validation(usb, ctrl)

        if is_valid:
            print("\n✅ Fast validation successful!")
            print(f"   Using stored positions: S={s_pos}, P={p_pos}")
            print(f"   S/P ratio: {ratio:.2f}×")

            # Apply positions
            apply_positions(ctrl, s_pos, p_pos, save_to_eeprom)

            return {
                "success": True,
                "method": "fast_validation",
                "s_pos": s_pos,
                "p_pos": p_pos,
                "sp_ratio": ratio,
                "attempts": 0,
            }
        print("\n⚠️  Fast validation failed - proceeding with full sweep")
    else:
        print("\n🔧 Force full calibration requested")

    # Full calibration with retry logic
    for attempt in range(1, MAX_RETRIES + 1):
        print("\n" + "=" * 80)
        print(f"CALIBRATION ATTEMPT {attempt}/{MAX_RETRIES}")
        print("=" * 80)

        try:
            # Perform sweep
            positions, intensities, p_pos, s_pos = perform_sweep(usb, ctrl)

            # Analyze peaks with wavelength validation and pre-determined positions
            results = analyze_peaks(positions, intensities, usb, ctrl, p_pos, s_pos)

            if results["success"]:
                print(f"\n✅ Calibration successful on attempt {attempt}!")

                # Verify and auto-correct for inversion
                corrected_s_pos, corrected_p_pos, was_inverted = (
                    verify_and_correct_positions(
                        ctrl,
                        usb,
                        results["s_pos"],
                        results["p_pos"],
                    )
                )

                # Update results with corrected positions
                if was_inverted:
                    results["s_pos"] = corrected_s_pos
                    results["p_pos"] = corrected_p_pos
                    results["was_inverted"] = True
                    results["inversion_corrected"] = True
                else:
                    results["was_inverted"] = False
                    results["inversion_corrected"] = False

                # Apply corrected positions
                apply_positions(
                    ctrl,
                    results["s_pos"],
                    results["p_pos"],
                    save_to_eeprom,
                )

                results["method"] = "full_sweep"
                results["attempts"] = attempt
                return results
            print(f"\n❌ Attempt {attempt} failed validation:")
            for name, passed, detail in results["validation"]:
                status = "✓" if passed else "✗"
                print(f"   {status} {name}: {detail}")

            if attempt < MAX_RETRIES:
                print(f"\n   Retrying... ({MAX_RETRIES - attempt} attempts remaining)")
                time.sleep(1.0)

        except Exception as e:
            print(f"\n❌ Attempt {attempt} failed with error: {e}")
            import traceback

            traceback.print_exc()

            if attempt < MAX_RETRIES:
                print(f"\n   Retrying... ({MAX_RETRIES - attempt} attempts remaining)")
                time.sleep(1.0)

    # All retries exhausted
    print("\n" + "=" * 80)
    print(f"❌ CALIBRATION FAILED - All {MAX_RETRIES} attempts exhausted")
    print("=" * 80)
    return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test servo calibration sequence")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force full calibration (skip fast validation)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save positions to EEPROM after successful calibration",
    )
    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("SERVO CALIBRATION TEST")
    print("=" * 80)
    print(f"   Force full calibration: {args.force}")
    print(f"   Save to EEPROM: {args.save}")

    # Setup hardware
    usb, ctrl = setup_hardware()

    if usb is None or ctrl is None:
        print("\n❌ Hardware initialization failed - cannot proceed")
        # Turn off LED if controller was initialized
        if ctrl:
            ctrl.turn_off_channels()
            time.sleep(0.1)  # Give controller time to process
            print("\n✅ Cleanup complete")
        return 1

    try:
        # Run calibration
        results = calibrate_servo_positions(usb, ctrl, args.force, args.save)

        if results is None:
            print("\n❌ Calibration failed")
            return 1

        # Print summary
        print("\n" + "=" * 80)
        print("CALIBRATION SUMMARY")
        print("=" * 80)
        print(f"   Method: {results['method']}")
        print(f"   Attempts: {results['attempts']}")
        print(f"   S position: {results['s_pos']}°")
        print(f"   P position: {results['p_pos']}°")
        print(f"   S/P ratio: {results['sp_ratio']:.2f}×")

        # Show resonance wavelength if available
        if results.get("resonance_wavelength") is not None:
            print(f"   Resonance wavelength: {results['resonance_wavelength']:.1f}nm")

        # Show inversion info if applicable
        if results.get("was_inverted", False):
            print("   ⚠️  Inversion detected and corrected")
        else:
            print("   ✅ No inversion detected")

        print(f"   Saved to EEPROM: {args.save}")
        print("=" * 80)
        print("\n✅ CALIBRATION COMPLETE\n")

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 130

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    finally:
        # Cleanup
        if ctrl:
            ctrl.turn_off_channels()
            time.sleep(0.1)  # Give controller time to process
        print("\n✅ Cleanup complete")


if __name__ == "__main__":
    sys.exit(main())
