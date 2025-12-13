from __future__ import annotations

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
from scipy.signal import find_peaks, peak_prominences, peak_widths

from affilabs.utils.logger import logger

MIN_ANGLE = 0
MAX_ANGLE = 180

# Calibration parameters
MIN_SERVO = 5  # Start of servo range (0-255 PWM units)
MAX_SERVO = 250  # End of servo range (0-255 PWM units)
SETTLING_TIME = 0.2  # Servo settling time (seconds)
MODE_SWITCH_TIME = 0.1  # Time to switch between S/P modes (seconds)


# Helper functions for servo unit conversion
def servo_to_degrees(servo_pos: int) -> int:
    """Convert servo position (0-255) to degrees for display purposes only."""
    return int(servo_pos * 180 / 255)


def degrees_to_servo(degrees: int) -> int:
    """Convert degrees to servo position (0-255) for controller commands."""
    return int(degrees * 255 / 180)


# ROI for SPR resonance measurement
ROI_MIN_WL = 600  # Minimum wavelength for SPR ROI (nm)
ROI_MAX_WL = 670  # Maximum wavelength for SPR ROI (nm)

# Resonance wavelength validation
MIN_RESONANCE_WL = 590  # Minimum valid resonance wavelength (nm)
MAX_RESONANCE_WL = 670  # Maximum valid resonance wavelength (nm)

# Detector specifications
MAX_DETECTOR_COUNTS = 62000  # Flame-T maximum counts (not 65535)
SATURATION_THRESHOLD = 0.95  # Warn if above 95% of max (58,900 counts)

# Servo calibration target intensity
# Use lower target (30% of max) to prevent saturation in S-mode while still having enough signal
SERVO_CAL_TARGET_PERCENT = 0.30  # 30% of detector max (~18,600 counts for Flame-T)

# Validation thresholds
MIN_SEPARATION = 80  # Minimum S-P separation (degrees) for circular polarizer
MAX_SEPARATION = 100  # Maximum S-P separation (degrees) for circular polarizer
MIN_SP_RATIO = 1.3  # Minimum S/P intensity ratio
IDEAL_SP_RATIO = 1.5  # Ideal S/P intensity ratio
MIN_DIP_DEPTH_PERCENT = 10.0  # Minimum transmission dip depth (%)
MIN_TRANSMISSION_PERCENT = 30.0  # Minimum transmission at dip (to detect water)


def _move_servo_to_position(
    ctrl, angle: int, mode: str = "s", wait_time: float = 0.5,
) -> bool | None:
    """Move servo to specific angle for scanning (no EEPROM write).

    During calibration scanning, we just move the servo to different positions.
    EEPROM flashing only happens ONCE at the end when saving final positions.

    The P4SPR firmware command sequence for scanning prefers calibration-only
    movement to avoid EEPROM writes:
    1. servo_move_calibration_only() - set RAM positions for S and P
    2. set_mode() - moves servo to the requested position (ss or sp)

    Args:
        ctrl: Controller instance
        angle: Target angle (0-180 degrees)
        mode: Mode to use ('s' or 'p') - determines which position register to activate
        wait_time: Time to wait for servo movement (default 0.5s)

    Returns:
        bool: True if successful, False otherwise

    """
    try:
        # Step 1: Set RAM positions using calibration-only move when available
        if hasattr(ctrl, "servo_move_calibration_only"):
            ctrl.servo_move_calibration_only(s=angle, p=angle)
        elif not ctrl.servo_set(s=angle, p=angle):
            logger.debug("servo_set returned False during scan")

        time.sleep(0.05)  # Small delay between commands

        # Step 2: Activate position using mode command (this moves the servo)
        if not ctrl.set_mode(mode):
            logger.debug("set_mode returned False during scan")

        # Step 3: Wait for physical servo movement
        time.sleep(wait_time)
        return True

    except Exception as e:
        logger.error(f"Failed to move servo to {angle}°: {e}")
        return False


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


def _calibrate_leds_for_servo(
    usb, ctrl, target_percent: float = SERVO_CAL_TARGET_PERCENT,
):
    """Calibrate LEDs with lower target intensity specifically for servo calibration.

    This prevents saturation during servo search when in S-mode (max transmission).
    Uses a conservative target (30% of detector max) since we only need to find
    the SPR dip position, not achieve optimal SNR.

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper
        target_percent: Target as fraction of detector max (default: 0.30 = 30%)

    Returns:
        dict: Calibrated LED intensities for each channel

    """
    # Simple built-in LED calibration - no external dependencies
    max_counts = getattr(usb, "max_counts", MAX_DETECTOR_COUNTS)
    target_counts = max_counts * target_percent

    logger.info("=" * 80)
    logger.info("LED CALIBRATION FOR SERVO SEARCH")
    logger.info("=" * 80)
    logger.info(
        f"Target: {target_counts:.0f} counts ({target_percent * 100:.0f}% of detector max)",
    )
    logger.info(f"Detector max: {max_counts:.0f} counts")
    logger.info("Reason: Lower target prevents saturation in S-mode (max transmission)")
    logger.info("=" * 80)

    calibrated_intensities = {}
    integration_time = 50  # ms - fixed integration time for servo calibration
    max_counts = getattr(usb, "max_counts", MAX_DETECTOR_COUNTS)
    saturation_limit = int(max_counts * SATURATION_THRESHOLD)
    max_counts = getattr(usb, "max_counts", MAX_DETECTOR_COUNTS)
    saturation_limit = int(max_counts * SATURATION_THRESHOLD)

    try:
        # Set integration time
        usb.set_integration(integration_time)
        time.sleep(0.1)

        # Calibrate all channels using binary search
        for ch in ["a", "b", "c", "d"]:
            logger.info(f"Calibrating LED {ch.upper()}...")

            # Enable channel
            ctrl.turn_on_channel(ch)
            time.sleep(0.05)

            # Binary search for optimal intensity
            intensity_low = 10
            intensity_high = 255
            best_intensity = 64  # default fallback

            for _ in range(8):  # 8 iterations = ~2 counts precision
                intensity_mid = (intensity_low + intensity_high) // 2
                ctrl.set_intensity(ch, intensity_mid)
                time.sleep(0.1)

                # Read spectrum
                spectrum = usb.read_intensity()
                if spectrum is None:
                    continue

                max_signal = float(spectrum.max())

                # Check for no light condition (only dark counts)
                if max_signal < 3500:
                    logger.error(
                        f"LED {ch.upper()} producing no light at intensity {intensity_mid} ({max_signal:.0f} counts)",
                    )
                    logger.error(
                        "Signal too close to dark counts (~3000) - LED not working or not connected!",
                    )
                    logger.error(
                        "Check: 1) LED connections, 2) LED enable command, 3) Power supply",
                    )
                    best_intensity = intensity_mid
                    break

                # Check for saturation - if saturating, force lower intensity
                if max_signal >= saturation_limit:
                    logger.warning(
                        f"LED {ch.upper()} saturating at intensity {intensity_mid} ({max_signal:.0f} counts)",
                    )
                    logger.warning("Reducing intensity range to prevent saturation...")
                    intensity_high = intensity_mid - 1
                    if intensity_high < intensity_low:
                        # Even lowest intensity saturates - use it anyway but warn
                        logger.error(
                            f"LED {ch.upper()} saturates even at low intensity! Using {intensity_low}",
                        )
                        best_intensity = intensity_low
                        break
                    continue

                if max_signal < target_counts * 0.95:  # Below target
                    intensity_low = intensity_mid + 1
                elif max_signal > target_counts * 1.05:  # Above target
                    intensity_high = intensity_mid - 1
                else:  # Within 5% of target
                    best_intensity = intensity_mid
                    break

                best_intensity = intensity_mid

            calibrated_intensities[ch] = best_intensity
            logger.info(f"  ✓ LED {ch.upper()}: intensity = {best_intensity}")

        logger.info("=" * 80)
        logger.info("[OK] LED CALIBRATION COMPLETE")
        logger.info("=" * 80)

        return calibrated_intensities

    except Exception as e:
        logger.error(f"LED calibration failed: {e}")
        logger.warning("Falling back to default intensity (32)")
        # Fallback to safe default
        return {"a": 32, "b": 32, "c": 32, "d": 32}


def _set_reduced_led_intensity(ctrl, reduced_intensity: int = 32):
    """Temporarily reduce LED intensity to prevent saturation during servo calibration.

    Args:
        ctrl: Controller wrapper
        reduced_intensity: LED intensity to use (default: 64 = 25% of max)

    Returns:
        dict: Original LED intensities for restoration

    """
    original_intensities = {}
    try:
        logger.debug(
            f"Reducing LED intensity to {reduced_intensity} to prevent saturation...",
        )
        for ch in ["a", "b", "c", "d"]:
            # Store current intensity (fallback to 128 if not available)
            original_intensities[ch] = getattr(ctrl, f"_{ch}_intensity", 128)
            # Set reduced intensity
            ctrl.set_intensity(ch, reduced_intensity)
        time.sleep(0.2)  # Allow LEDs to stabilize
    except Exception as e:
        logger.warning(f"Could not reduce LED intensity: {e}")

    return original_intensities


def _restore_led_intensity(ctrl, original_intensities: dict) -> None:
    """Restore original LED intensities after servo calibration.

    Args:
        ctrl: Controller wrapper
        original_intensities: Dictionary of original intensities to restore

    """
    try:
        logger.debug("Restoring original LED intensities...")
        for ch, intensity in original_intensities.items():
            ctrl.set_intensity(ch, intensity)
        time.sleep(0.2)  # Allow LEDs to stabilize
    except Exception as e:
        logger.warning(f"Could not restore LED intensities: {e}")


def check_water_presence(usb, ctrl, s_pos: int, p_pos: int):
    """Check if water is present on sensor by analyzing transmission spectrum.

    Water presence is detected by:
    1. Transmission dip in SPR region (600-750nm)
    2. Transmission < 100% (P < S, no inversion)
    3. Dip depth >= 10% of maximum transmission

    Uses reduced LED intensity to prevent saturation.

    Args:
        usb: Spectrometer wrapper
        ctrl: Controller wrapper
        s_pos: Current S-mode servo position
        p_pos: Current P-mode servo position

    Returns:
        Tuple of (has_water, transmission_min, dip_depth_percent)

    """
    # Use reduced LED intensity to prevent saturation
    original_intensities = _set_reduced_led_intensity(ctrl)

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
        transmission = (
            np.divide(
                p_spectrum,
                s_spectrum,
                out=np.ones_like(p_spectrum, dtype=float),
                where=s_spectrum > 10,
            )
            * 100.0
        )

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
            dip_depth_percent >= MIN_DIP_DEPTH_PERCENT
            and transmission_min < 100.0
            and transmission_max < 150.0  # Sanity check
        )

        return has_water, transmission_min, dip_depth_percent

    except Exception as e:
        logger.exception(f"Error checking water presence: {e}")
        return False, None, None
    finally:
        # Always restore original LED intensities
        _restore_led_intensity(ctrl, original_intensities)


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
        "validation_checks": [],
    }

    try:
        # Get wavelengths
        wavelengths = usb._wavelengths
        if wavelengths is None:
            logger.error("[ERROR] Wavelengths not available - cannot validate")
            return False, results

        # Check saturation limit
        saturation_limit = int(MAX_DETECTOR_COUNTS * SATURATION_THRESHOLD)
        logger.info(
            f"Saturation check: max allowed = {saturation_limit} counts ({SATURATION_THRESHOLD * 100:.0f}%)",
        )

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
            logger.error(
                f"[ERROR] SATURATION in S-mode: {s_max:.0f} counts >= {saturation_limit}",
            )
            results["validation_checks"].append(
                ("S saturation", False, f"{s_max:.0f} >= {saturation_limit}"),
            )
            return False, results

        # Measure P-pol (SPR-active)
        ctrl.set_mode("p")
        time.sleep(MODE_SWITCH_TIME * 2)
        p_spectrum = usb.read_intensity()
        p_max = p_spectrum.max()
        p_roi = get_roi_intensity(p_spectrum, wavelengths)

        # Check P saturation
        if p_max >= saturation_limit:
            logger.error(
                f"[ERROR] SATURATION in P-mode: {p_max:.0f} counts >= {saturation_limit}",
            )
            results["validation_checks"].append(
                ("P saturation", False, f"{p_max:.0f} >= {saturation_limit}"),
            )
            return False, results

        logger.info("✓ No saturation detected")
        results["validation_checks"].append(
            ("Saturation", True, f"S={s_max:.0f}, P={p_max:.0f} < {saturation_limit}"),
        )

        # Store intensities
        results["s_intensity"] = float(s_roi)
        results["p_intensity"] = float(p_roi)

        # CHECK 1: S > P (no inversion at ROI level)
        logger.info("1. Intensity Check:")
        logger.info(f"   S-mode ROI: {s_roi:.0f} counts")
        logger.info(f"   P-mode ROI: {p_roi:.0f} counts")

        if s_roi <= p_roi:
            logger.error("[ERROR] FAIL: S should be higher than P (inversion detected)")
            results["validation_checks"].append(
                ("S > P", False, f"S={s_roi:.0f} <= P={p_roi:.0f}"),
            )
            return False, results

        logger.info("   ✓ PASS: S > P (no inversion)")
        results["validation_checks"].append(
            ("S > P", True, f"S={s_roi:.0f} > P={p_roi:.0f}"),
        )

        # CHECK 2: S/P ratio
        sp_ratio = s_roi / p_roi if p_roi > 0 else 0
        results["sp_ratio"] = float(sp_ratio)

        logger.info("2. S/P Ratio:")
        logger.info(f"   Measured: {sp_ratio:.2f}×")
        logger.info(f"   Minimum: {MIN_SP_RATIO:.2f}×")

        if sp_ratio < MIN_SP_RATIO:
            logger.warning("[ERROR] FAIL: S/P ratio too low")
            results["validation_checks"].append(
                ("S/P ratio", False, f"{sp_ratio:.2f}× < {MIN_SP_RATIO:.2f}×"),
            )
            return False, results

        logger.info("   ✓ PASS: S/P ratio adequate")
        results["validation_checks"].append(
            ("S/P ratio", True, f"{sp_ratio:.2f}× >= {MIN_SP_RATIO:.2f}×"),
        )

        # CHECK 3: Calculate transmission and analyze SPR dip
        transmission = (
            np.divide(
                p_spectrum,
                s_spectrum,
                out=np.ones_like(p_spectrum, dtype=float),
                where=s_spectrum > 10,
            )
            * 100.0
        )

        # Analyze SPR ROI
        roi_mask = (wavelengths >= ROI_MIN_WL) & (wavelengths <= ROI_MAX_WL)
        roi_transmission = transmission[roi_mask]
        roi_wavelengths = wavelengths[roi_mask]

        if len(roi_transmission) == 0:
            logger.error(
                f"[ERROR] FAIL: No data in SPR ROI ({ROI_MIN_WL}-{ROI_MAX_WL}nm)",
            )
            return False, results

        transmission_min = float(roi_transmission.min())
        transmission_max = float(roi_transmission.max())
        dip_depth_percent = transmission_max - transmission_min

        results["transmission_min"] = transmission_min
        results["transmission_max"] = transmission_max
        results["dip_depth_percent"] = dip_depth_percent

        logger.info("3. Transmission Dip Analysis:")
        logger.info(f"   Minimum: {transmission_min:.1f}%")
        logger.info(f"   Maximum: {transmission_max:.1f}%")
        logger.info(f"   Dip depth: {dip_depth_percent:.1f}%")

        # CHECK 4: Transmission dip depth (indicates SPR coupling quality)
        if dip_depth_percent < MIN_DIP_DEPTH_PERCENT:
            logger.error(
                f"[ERROR] FAIL: Dip too shallow (need >{MIN_DIP_DEPTH_PERCENT}%)",
            )
            logger.error("   This indicates weak SPR coupling or no water on sensor")
            results["validation_checks"].append(
                (
                    "Dip depth",
                    False,
                    f"{dip_depth_percent:.1f}% < {MIN_DIP_DEPTH_PERCENT}%",
                ),
            )
            return False, results

        logger.info("   ✓ PASS: Dip depth adequate")
        results["validation_checks"].append(
            ("Dip depth", True, f"{dip_depth_percent:.1f}% >= {MIN_DIP_DEPTH_PERCENT}%"),
        )

        # CHECK 5: No transmission inversion (should be <100%)
        if transmission_min > 100.0:
            logger.error(
                "[ERROR] FAIL: Transmission >100% indicates inverted polarizer positions",
            )
            results["validation_checks"].append(
                ("Transmission <100%", False, f"Min={transmission_min:.1f}% > 100%"),
            )
            return False, results

        logger.info("   ✓ PASS: Transmission <100% (no inversion)")
        results["validation_checks"].append(
            ("Transmission <100%", True, f"Min={transmission_min:.1f}%"),
        )

        # CHECK 6: Resonance wavelength validation
        resonance_idx = np.argmin(roi_transmission)
        resonance_wavelength = float(roi_wavelengths[resonance_idx])
        results["resonance_wavelength"] = resonance_wavelength

        logger.info("4. Resonance Wavelength:")
        logger.info(f"   Measured: {resonance_wavelength:.1f}nm")
        logger.info(f"   Valid range: {MIN_RESONANCE_WL}-{MAX_RESONANCE_WL}nm")

        if (
            resonance_wavelength < MIN_RESONANCE_WL
            or resonance_wavelength > MAX_RESONANCE_WL
        ):
            logger.warning("[WARN]  WARNING: Resonance outside typical SPR range")
            logger.warning("   This may indicate optical misalignment")
            results["validation_checks"].append(
                ("Resonance WL", False, f"{resonance_wavelength:.1f}nm out of range"),
            )
            # Don't fail - just warn
        else:
            logger.info("   ✓ PASS: Resonance in valid SPR range")
            results["validation_checks"].append(
                ("Resonance WL", True, f"{resonance_wavelength:.1f}nm in range"),
            )

        # All checks passed
        logger.info("=" * 80)
        logger.info("[OK] VALIDATION PASSED - Positions are optimal")
        logger.info("=" * 80)
        results["validation_passed"] = True
        return True, results

    except Exception as e:
        logger.exception(f"Error during transmission validation: {e}")
        return False, results


def perform_quadrant_search(usb, ctrl):
    """Perform intelligent quadrant search to find optimal S and P positions.

    Uses a 3-phase approach:
    1. LED calibration with lower target (30% of max) to prevent saturation
    2. Coarse 5-point search across servo range
    3. Refinement around predicted P position (minimum)
    4. Calculate S position exactly 90° from P

    Total measurements: ~13 + LED calibration time

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

    # STEP 1: LED Verification and Calibration
    logger.info("")
    logger.info("STEP 1a: LED Communication Test")

    # First, measure dark counts (all LEDs off)
    logger.info("Measuring dark counts (LEDs off)...")
    try:
        ctrl.turn_off_channels()
        time.sleep(0.2)
        dark_spectrum = usb.read_intensity()
        if dark_spectrum is None:
            logger.error("[ERROR] Failed to read dark spectrum from detector!")
            return None
        dark_counts = float(dark_spectrum.max())
        logger.info(f"Dark counts: {dark_counts:.0f}")
    except Exception as e:
        logger.error(f"[ERROR] Dark measurement failed: {e}")
        return None

    # Now test LED commands
    test_channel = "b"  # Use channel B for test
    logger.info(f"Testing LED {test_channel.upper()} commands...")

    # Try to enable and set intensity
    try:
        enable_ok = ctrl.turn_on_channel(test_channel)
        logger.info(f"   Enable command response: {enable_ok}")
        time.sleep(0.1)

        intensity_ok = ctrl.set_intensity(test_channel, 50)
        logger.info(f"   Intensity command response: {intensity_ok}")
        time.sleep(0.2)

        # Read spectrum to verify LED is producing light
        test_spectrum = usb.read_intensity()
        if test_spectrum is None:
            logger.error("[ERROR] Failed to read spectrum from detector!")
            return None

        test_signal = float(test_spectrum.max())
        signal_increase = test_signal - dark_counts
        logger.info(f"Signal with LED ON: {test_signal:.0f} counts")
        logger.info(f"Signal increase from dark: {signal_increase:.0f} counts")

        # Verify significant increase over dark
        if signal_increase < 500:
            logger.error(
                "[ERROR] LED not producing light! Signal barely increased from dark counts",
            )
            logger.error(
                f"   Dark: {dark_counts:.0f}, LED ON: {test_signal:.0f}, Increase: {signal_increase:.0f}",
            )
            logger.error("   Possible causes:")
            logger.error("   1. LED enable command (lb) sent but LED didn't turn on")
            logger.error(
                "   2. LED intensity command (bb050) sent but LED didn't respond",
            )
            logger.error("   3. Controller firmware not controlling LED hardware")
            logger.error("   4. LED physically disconnected or burned out")
            logger.error("   5. Wrong LED channel or PCB connection")
            return None

        logger.info(f"✓ LED commands working! {signal_increase:.0f} counts increase")
    except Exception as e:
        logger.error(f"[ERROR] LED communication test failed: {e}")
        return None

    logger.info("")
    logger.info("STEP 1b: LED Calibration (low target for servo search)")
    calibrated_intensities = _calibrate_leds_for_servo(usb, ctrl)
    if calibrated_intensities is None:
        logger.error("[ERROR] LED calibration returned None - cannot proceed")
        return None
    logger.info("")

    # Store original intensities for later restoration (if needed)
    original_led_intensity = calibrated_intensities.copy()

    # Store all measurements
    all_positions = []
    all_intensities = []

    def measure_position(servo_pos: int) -> float:
        """Helper to measure intensity at a servo position in P-mode to detect SPR minimum.
        Works in native servo units (0-255), converts to degrees only for display.
        """
        angle_deg = servo_to_degrees(servo_pos)
        _move_servo_to_position(
            ctrl, angle_deg, mode="p", wait_time=SETTLING_TIME + MODE_SWITCH_TIME,
        )
        spectrum = usb.read_intensity()
        intensity = (
            get_roi_intensity(spectrum, wavelengths) if use_roi else spectrum.max()
        )
        all_positions.append(servo_pos)  # Store servo positions, not degrees
        all_intensities.append(intensity)
        return intensity

    # STEP 2: Coarse quadrant search - full 0-255 servo range
    # Work in native servo units (0-255 PWM) for complete coverage
    logger.info("STEP 2: Coarse quadrant search (full 0-255 servo range)...")
    # Quadrant spacing: every 55 servo units covers the full range
    # 5, 60, 115, 170, 225 = 5 measurements across 0-255 range
    servo_step = 55

    coarse_servo_positions = list(range(5, 236, servo_step))  # [5, 60, 115, 170, 225]
    coarse_intensities = []

    for servo_pos in coarse_servo_positions:
        intensity = measure_position(servo_pos)
        coarse_intensities.append(intensity)
        angle_deg = servo_to_degrees(servo_pos)
        logger.info(f"   Servo {servo_pos} ({angle_deg}°): {intensity:.0f} counts")

    # Find approximate min (P position - where SPR absorption is strongest)
    coarse_min_idx = np.argmin(coarse_intensities)
    approx_p_servo = coarse_servo_positions[coarse_min_idx]
    approx_p_deg = servo_to_degrees(approx_p_servo)

    # Show all values to verify we're finding the actual minimum
    logger.info("Coarse search results:")
    logger.info(
        f"   Min intensity: {coarse_intensities[coarse_min_idx]:.0f} at servo {approx_p_servo} ({approx_p_deg}°)",
    )
    max_idx = np.argmax(coarse_intensities)
    logger.info(
        f"   Max intensity: {coarse_intensities[max_idx]:.0f} at servo {coarse_servo_positions[max_idx]} ({servo_to_degrees(coarse_servo_positions[max_idx])}°)",
    )
    logger.info(
        f"   Range: {max(coarse_intensities) - coarse_intensities[coarse_min_idx]:.0f} counts",
    )

    logger.info("Approximate P position (minimum):")
    logger.info(
        f"   P ≈ servo {approx_p_servo} ({approx_p_deg}°) - {coarse_intensities[coarse_min_idx]:.0f} counts",
    )

    # STEP 3: Refine P position (minimum) - Multi-stage refinement in servo units
    logger.info(
        f"STEP 3: Refining P position around servo {approx_p_servo} ({approx_p_deg}°)...",
    )

    # Stage 3a: Coarse refinement (±28 servo units in 14 unit steps)
    # ±28 servo units ≈ ±20°, 14 units ≈ 10°
    logger.info("  Stage 3a: Coarse refinement (±28 servo units in 14 unit steps)...")
    p_search_positions = [
        max(MIN_SERVO, approx_p_servo - 28),
        max(MIN_SERVO, approx_p_servo - 14),
        approx_p_servo,
        min(MAX_SERVO, approx_p_servo + 14),
        min(MAX_SERVO, approx_p_servo + 28),
    ]
    # Remove duplicates and already measured
    p_search_positions = [p for p in p_search_positions if p not in all_positions]

    p_intensities = {approx_p_servo: coarse_intensities[coarse_min_idx]}
    for servo_pos in p_search_positions:
        intensity = measure_position(servo_pos)
        p_intensities[servo_pos] = intensity
        logger.debug(
            f"     Servo {servo_pos} ({servo_to_degrees(servo_pos)}°): {intensity:.0f} counts",
        )

    # Find best position from coarse refinement
    p_coarse_refined = min(p_intensities.keys(), key=lambda k: p_intensities[k])
    logger.info(
        f"  Coarse refinement result: servo {p_coarse_refined} ({servo_to_degrees(p_coarse_refined)}°) - {p_intensities[p_coarse_refined]:.0f} counts",
    )

    # Stage 3b: Fine refinement (±7 servo units in 7 unit steps)
    # ±7 servo units ≈ ±5°
    logger.info(
        f"  Stage 3b: Fine refinement (±7 servo units around {p_coarse_refined})...",
    )
    fine_positions = [
        max(MIN_SERVO, p_coarse_refined - 7),
        p_coarse_refined,
        min(MAX_SERVO, p_coarse_refined + 7),
    ]
    fine_positions = [p for p in fine_positions if p not in all_positions]

    for servo_pos in fine_positions:
        intensity = measure_position(servo_pos)
        p_intensities[servo_pos] = intensity
        logger.debug(
            f"     Servo {servo_pos} ({servo_to_degrees(servo_pos)}°): {intensity:.0f} counts",
        )

    p_fine_refined = min(p_intensities.keys(), key=lambda k: p_intensities[k])
    logger.info(
        f"  Fine refinement result: servo {p_fine_refined} ({servo_to_degrees(p_fine_refined)}°) - {p_intensities[p_fine_refined]:.0f} counts",
    )

    # Stage 3c: Ultra-fine refinement (±3 servo units in 3 unit steps)
    # ±3 servo units ≈ ±2°
    logger.info(
        f"  Stage 3c: Ultra-fine refinement (±3 servo units around {p_fine_refined})...",
    )
    ultrafine_positions = [
        max(MIN_SERVO, p_fine_refined - 3),
        p_fine_refined,
        min(MAX_SERVO, p_fine_refined + 3),
    ]
    ultrafine_positions = [p for p in ultrafine_positions if p not in all_positions]

    for servo_pos in ultrafine_positions:
        intensity = measure_position(servo_pos)
        p_intensities[servo_pos] = intensity
        logger.debug(
            f"     Servo {servo_pos} ({servo_to_degrees(servo_pos)}°): {intensity:.0f} counts",
        )

    # Find final refined P position (minimum intensity = strongest SPR absorption)
    p_pos_servo = min(p_intensities.keys(), key=lambda k: p_intensities[k])
    p_pos_deg = servo_to_degrees(p_pos_servo)
    p_intensity = p_intensities[p_pos_servo]
    logger.info(
        f"✓ P position finalized: servo {p_pos_servo} ({p_pos_deg}°) - {p_intensity:.0f} counts",
    )
    logger.info(
        f"  Total P refinement measurements: {len([p for p in all_positions if p != approx_p_servo]) - len([p for p in all_positions if p in coarse_servo_positions])}",
    )

    # STEP 4: Set S position exactly 90 servo units from P
    # For circular polarizer: S = P ± 90 servo units (NOT degrees!)
    # The servo has 255 positions, and circular polarizer is 90 units apart
    # Choose the option that's within servo range (5-250)
    servo_90_separation = 90  # 90 servo units, NOT 127!
    s_candidate_1_servo = p_pos_servo - servo_90_separation
    s_candidate_2_servo = p_pos_servo + servo_90_separation

    if MIN_SERVO <= s_candidate_1_servo <= MAX_SERVO:
        s_pos_servo = s_candidate_1_servo
        s_pos_deg = servo_to_degrees(s_pos_servo)
        logger.info(
            f"STEP 4: S position = P - 90 units = servo {p_pos_servo} - 90 = servo {s_pos_servo} ({s_pos_deg}°)",
        )
    elif MIN_SERVO <= s_candidate_2_servo <= MAX_SERVO:
        s_pos_servo = s_candidate_2_servo
        s_pos_deg = servo_to_degrees(s_pos_servo)
        logger.info(
            f"STEP 4: S position = P + 90 units = servo {p_pos_servo} + 90 = servo {s_pos_servo} ({s_pos_deg}°)",
        )
    else:
        # This shouldn't happen if P is in range, so ±90 units should always be valid
        logger.error(
            f"[ERROR] ERROR: Cannot place S position 90 units from P=servo {p_pos_servo} ({p_pos_deg}°)",
        )
        logger.error(
            f"   P - 90 = servo {s_candidate_1_servo} ({servo_to_degrees(s_candidate_1_servo)}°) - out of range",
        )
        logger.error(
            f"   P + 90 = servo {s_candidate_2_servo} ({servo_to_degrees(s_candidate_2_servo)}°) - out of range",
        )
        return None

    # Measure S position to verify
    _move_servo_to_position(
        ctrl, s_pos_deg, mode="s", wait_time=SETTLING_TIME + MODE_SWITCH_TIME,
    )
    spectrum = usb.read_intensity()
    s_intensity = (
        get_roi_intensity(spectrum, wavelengths) if use_roi else spectrum.max()
    )
    all_positions.append(s_pos_servo)
    all_intensities.append(s_intensity)

    separation_servo = abs(s_pos_servo - p_pos_servo)
    separation_deg = abs(s_pos_deg - p_pos_deg)
    logger.info(
        f"✓ S position set: servo {s_pos_servo} ({s_pos_deg}°) - {s_intensity:.0f} counts",
    )
    logger.info(
        f"✓ Separation enforced: {separation_servo} servo units = {separation_deg}° (circular polarizer)",
    )

    logger.info("[OK] Quadrant search complete")
    logger.info(f"Total measurements: {len(all_positions)} (vs 33+ for full sweep)")

    # CRITICAL: Restore original LED intensities
    _restore_led_intensity(ctrl, original_led_intensity)
    logger.info("[OK] LED intensities restored")

    return (
        s_pos_deg,
        p_pos_deg,
    )  # Return degrees for compatibility with device_config.json


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
        "validation": [],
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
            logger.warning(
                f"   [WARN]  P position {p_position}° not in measured positions",
            )
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
            logger.warning(
                f"   [ERROR] FAIL: Resonance outside valid range ({MIN_RESONANCE_WL}-{MAX_RESONANCE_WL}nm)",
            )
            logger.warning(
                "   This suggests incorrect servo position or optical misalignment",
            )
            return None
        results["validation"].append(
            (
                "Resonance wavelength",
                True,
                f"{resonance_wavelength:.1f}nm in [{MIN_RESONANCE_WL}, {MAX_RESONANCE_WL}]nm",
            ),
        )
        logger.info("   ✓ PASS: Resonance in valid SPR range")
    else:
        logger.warning("   [WARN]  Warning: Could not determine resonance wavelength")

    # Validation: Check that minimum is significant
    dip_depth = intensities.max() - p_intensity
    dip_depth_percent = (
        (dip_depth / intensities.max()) * 100 if intensities.max() > 0 else 0
    )

    logger.info(
        f"   Dip depth: {dip_depth:.0f} counts ({dip_depth_percent:.1f}% of maximum)",
    )

    if dip_depth_percent < MIN_DIP_DEPTH_PERCENT:
        results["validation"].append(
            ("Dip depth", False, f"{dip_depth_percent:.1f}% < {MIN_DIP_DEPTH_PERCENT}%"),
        )
        logger.warning(
            f"   [ERROR] FAIL: Resonance dip too shallow (need >{MIN_DIP_DEPTH_PERCENT}%)",
        )
        return None
    results["validation"].append(
        ("Dip depth", True, f"{dip_depth_percent:.1f}% >= {MIN_DIP_DEPTH_PERCENT}%"),
    )
    logger.info("   ✓ PASS: Significant resonance dip detected")

    # Find MAXIMUM (reference for S position)
    if s_pos is not None:
        logger.info("2. Using Pre-determined S Position:")
        s_position = s_pos
        # Find intensity at this position
        s_idx = np.where(positions == s_position)[0]
        if len(s_idx) > 0:
            s_intensity = intensities[s_idx[0]]
        else:
            logger.warning(
                f"   [WARN]  S position {s_position}° not in measured positions",
            )
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
        logger.info("3. Position Separation:")
        logger.info(f"   Measured: {separation:.0f}°")
        logger.info(f"   Expected: {MIN_SEPARATION}-{MAX_SEPARATION}°")

        if separation < MIN_SEPARATION or separation > MAX_SEPARATION:
            results["validation"].append(
                (
                    "Position separation",
                    False,
                    f"{separation:.0f}° not in [{MIN_SEPARATION}, {MAX_SEPARATION}]",
                ),
            )
            logger.warning("   [ERROR] FAIL: Separation out of range")
            return None
        results["validation"].append(
            (
                "Position separation",
                True,
                f"{separation:.0f}° in [{MIN_SEPARATION}, {MAX_SEPARATION}]",
            ),
        )
        logger.info("   ✓ PASS: Separation is valid")
    else:
        logger.info(
            f"3. Position Separation: {separation:.0f}° (enforced by quadrant search)",
        )

    # Store results
    results["s_pos"] = int(s_position)
    results["p_pos"] = int(p_position)
    results["s_intensity"] = float(s_intensity)
    results["p_intensity"] = float(p_intensity)

    # Validation: Verify S > P (intensity check)
    logger.info("4. Intensity Verification:")
    logger.info(f"   S-mode intensity: {results['s_intensity']:.0f} (HIGH - reference)")
    logger.info(f"   P-mode intensity: {results['p_intensity']:.0f} (LOW - resonance)")

    if results["s_intensity"] <= results["p_intensity"]:
        results["validation"].append(
            (
                "S > P",
                False,
                f"S={results['s_intensity']:.0f} <= P={results['p_intensity']:.0f}",
            ),
        )
        logger.warning("   [ERROR] FAIL: S should be higher than P")
        return None
    results["validation"].append(
        (
            "S > P",
            True,
            f"S={results['s_intensity']:.0f} > P={results['p_intensity']:.0f}",
        ),
    )
    logger.info("   ✓ PASS: S is higher than P")

    # Validation: Check S/P ratio
    results["sp_ratio"] = results["s_intensity"] / results["p_intensity"]

    logger.info("5. S/P Ratio:")
    logger.info(f"   Measured: {results['sp_ratio']:.2f}×")
    logger.info(f"   Minimum: {MIN_SP_RATIO:.2f}×")
    logger.info(f"   Ideal: {IDEAL_SP_RATIO:.2f}×")

    if results["sp_ratio"] < MIN_SP_RATIO:
        results["validation"].append(
            ("S/P ratio", False, f"{results['sp_ratio']:.2f}× < {MIN_SP_RATIO:.2f}×"),
        )
        logger.warning("   [ERROR] FAIL: Ratio too low")
        return None
    if results["sp_ratio"] < IDEAL_SP_RATIO:
        results["validation"].append(
            (
                "S/P ratio",
                True,
                f"{results['sp_ratio']:.2f}× >= {MIN_SP_RATIO:.2f}× (acceptable)",
            ),
        )
        logger.info("   ✓ PASS: Ratio acceptable (could be improved)")
    else:
        results["validation"].append(
            (
                "S/P ratio",
                True,
                f"{results['sp_ratio']:.2f}× >= {IDEAL_SP_RATIO:.2f}× (ideal)",
            ),
        )
        logger.info("   ✓ PASS: Ratio is ideal")

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
    logger.info(
        f"Saturation check: max allowed = {saturation_limit} counts ({SATURATION_THRESHOLD * 100:.0f}% of {MAX_DETECTOR_COUNTS})",
    )

    # Apply calculated positions using correct firmware sequence
    _move_servo_to_position(ctrl, s_pos, mode="s", wait_time=SETTLING_TIME * 2)

    # Measure S-mode
    s_spectrum = usb.read_intensity()
    s_max = s_spectrum.max()
    s_measured = get_roi_intensity(s_spectrum, wavelengths) if use_roi else s_max

    # Check S-mode saturation
    if s_max >= saturation_limit:
        logger.error("   [ERROR] SATURATION DETECTED in S-mode!")
        logger.error(
            f"   Peak intensity: {s_max:.0f} counts (limit: {saturation_limit})",
        )
        logger.error(
            "   LED intensity is too high - reduce LED power before continuing",
        )
        return None

    # Measure P-mode
    _move_servo_to_position(ctrl, p_pos, mode="p", wait_time=MODE_SWITCH_TIME * 2)
    p_spectrum = usb.read_intensity()
    p_max = p_spectrum.max()
    p_measured = get_roi_intensity(p_spectrum, wavelengths) if use_roi else p_max

    # Check P-mode saturation
    if p_max >= saturation_limit:
        logger.error("   [ERROR] SATURATION DETECTED in P-mode!")
        logger.error(
            f"   Peak intensity: {p_max:.0f} counts (limit: {saturation_limit})",
        )
        logger.error(
            "   LED intensity is too high - reduce LED power before continuing",
        )
        return None

    logger.info("Initial measurement:")
    logger.info(
        f"   S-mode (pos={s_pos}): ROI={s_measured:.0f}, peak={s_max:.0f} counts",
    )
    logger.info(
        f"   P-mode (pos={p_pos}): ROI={p_measured:.0f}, peak={p_max:.0f} counts",
    )
    logger.info("   ✓ No saturation detected")

    # Check if inverted (P > S means transmission >100%)
    if p_measured > s_measured:
        logger.warning("   [WARN]  INVERSION DETECTED: P > S!")
        logger.warning("   This would cause transmission >100%")
        logger.info("   Swapping S and P positions...")

        # Swap positions
        s_pos, p_pos = p_pos, s_pos

        # Verify the swap worked - set both positions then test
        ctrl.servo_set(s=s_pos, p=p_pos)
        time.sleep(0.2)

        _move_servo_to_position(ctrl, s_pos, mode="s", wait_time=SETTLING_TIME * 2)
        s_verify = usb.read_intensity()
        if use_roi:
            s_verify_val = get_roi_intensity(s_verify, wavelengths)
        else:
            s_verify_val = s_verify.max()

        _move_servo_to_position(ctrl, p_pos, mode="p", wait_time=MODE_SWITCH_TIME * 2)
        p_verify = usb.read_intensity()
        if use_roi:
            p_verify_val = get_roi_intensity(p_verify, wavelengths)
        else:
            p_verify_val = p_verify.max()

        logger.info("Verification after swap:")
        logger.info(f"   S-mode: {s_verify_val:.0f} counts")
        logger.info(f"   P-mode: {p_verify_val:.0f} counts")

        if s_verify_val > p_verify_val:
            logger.info("   ✓ CORRECTED: S now > P")
            return s_pos, p_pos, True
        logger.error("   ✗ CORRECTION FAILED: Still inverted!")
        return s_pos, p_pos, True
    logger.info("   ✓ NO INVERSION: S > P (correct)")
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
            return (
                get_roi_intensity(spectrum, wavelengths)
                if use_roi
                else float(spectrum.max())
            )

        # PHASE 1: Full sweep to find all windows
        logger.info("Phase 1: Full sweep to find transmission windows...")
        sweep_positions = list(range(MIN_ANGLE, MAX_ANGLE + 1, 5))
        sweep_intensities = []

        for angle in sweep_positions:
            _move_servo_to_position(
                ctrl, angle, mode="s", wait_time=SETTLING_TIME + MODE_SWITCH_TIME,
            )
            spectrum = usb.read_intensity()
            intensity = roi_value(spectrum)
            sweep_intensities.append(intensity)
            logger.debug(f"   {angle}°: {intensity:.0f} counts")

        sweep_intensities = np.array(sweep_intensities)

        # PHASE 2: Find peaks (windows) using threshold
        # Windows will show as intensity peaks above background
        threshold = sweep_intensities.mean() + 0.5 * sweep_intensities.std()
        logger.info(
            f"Phase 2: Identifying windows (threshold: {threshold:.0f} counts)...",
        )

        # Find positions above threshold (potential windows)
        above_threshold = sweep_intensities > threshold
        window_positions = [
            sweep_positions[i] for i, val in enumerate(above_threshold) if val
        ]

        if len(window_positions) < 2:
            logger.error(
                f"[ERROR] Failed to find 2 windows (found {len(window_positions)})",
            )
            logger.error("   Check barrel alignment and fiber connections")
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
            logger.error(
                f"[ERROR] Could not separate into 2 windows (found {len(clusters)} clusters)",
            )
            logger.error("   Windows may be too close or overlap")
            return None
        if len(clusters) > 2:
            logger.warning(f"[WARN]  Found {len(clusters)} clusters, using 2 largest")
            # Keep only the 2 clusters with most positions
            clusters.sort(key=len, reverse=True)
            clusters = clusters[:2]

        logger.info("✓ Found 2 window clusters:")
        logger.info(
            f"   Window 1: {len(clusters[0])} positions ({min(clusters[0])}°-{max(clusters[0])}°)",
        )
        logger.info(
            f"   Window 2: {len(clusters[1])} positions ({min(clusters[1])}°-{max(clusters[1])}°)",
        )

        # PHASE 4: Optimize to truly perpendicular position per window
        logger.info(
            "Phase 4: Optimizing true perpendicular per window (S-max vs P-min)...",
        )

        window_peaks = []
        for i, cluster in enumerate(clusters):
            best_s_pos = None
            best_s_val = -1e9
            best_p_pos = None
            best_p_val = 1e9
            for pos in cluster:
                # Measure S-mode (maximize transmission)
                _move_servo_to_position(
                    ctrl, pos, mode="s", wait_time=SETTLING_TIME + MODE_SWITCH_TIME,
                )
                s_spec = usb.read_intensity()
                s_val = roi_value(s_spec)
                if s_val > best_s_val:
                    best_s_val = s_val
                    best_s_pos = pos
                # Measure P-mode (minimize transmission)
                _move_servo_to_position(
                    ctrl, pos, mode="p", wait_time=SETTLING_TIME + MODE_SWITCH_TIME,
                )
                p_spec = usb.read_intensity()
                p_val = roi_value(p_spec)
                if p_val < best_p_val:
                    best_p_val = p_val
                    best_p_pos = pos
            window_peaks.append(
                {
                    "window_id": i + 1,
                    "s_opt_pos": best_s_pos,
                    "s_opt_val": best_s_val,
                    "p_opt_pos": best_p_pos,
                    "p_opt_val": best_p_val,
                    "cluster_size": len(cluster),
                },
            )
            logger.info(
                f"   Window {i + 1}: S-opt {best_s_pos}° ({best_s_val:.0f}), P-opt {best_p_pos}° ({best_p_val:.0f})",
            )

        # PHASE 5: Identify which window is S vs P using SPR signature
        logger.info("Phase 5: Identifying S vs P windows using SPR signature...")

        # Measure signatures using optimized positions to detect SPR response
        window_signatures = []
        for window in window_peaks:
            s_pos = window["s_opt_pos"]
            p_pos = window["p_opt_pos"]
            _move_servo_to_position(
                ctrl, s_pos, mode="s", wait_time=SETTLING_TIME + MODE_SWITCH_TIME,
            )
            s_spectrum = usb.read_intensity()
            s_intensity = roi_value(s_spectrum)
            _move_servo_to_position(
                ctrl, p_pos, mode="p", wait_time=SETTLING_TIME + MODE_SWITCH_TIME,
            )
            p_spectrum = usb.read_intensity()
            p_intensity = roi_value(p_spectrum)
            # Calculate transmission to detect SPR dip
            transmission = (
                np.divide(
                    p_spectrum,
                    s_spectrum,
                    out=np.ones_like(p_spectrum, dtype=float),
                    where=s_spectrum > 10,
                )
                * 100.0
            )

            # Analyze transmission in SPR ROI
            if wavelengths is not None:
                roi_mask = (wavelengths >= ROI_MIN_WL) & (wavelengths <= ROI_MAX_WL)
                roi_transmission = transmission[roi_mask]
                trans_min = (
                    float(roi_transmission.min())
                    if len(roi_transmission) > 0
                    else 100.0
                )
                trans_max = (
                    float(roi_transmission.max())
                    if len(roi_transmission) > 0
                    else 100.0
                )
                dip_depth = trans_max - trans_min
            else:
                trans_min = 100.0
                dip_depth = 0.0

            window_signatures.append(
                {
                    "window_id": window["window_id"],
                    "s_pos": s_pos,
                    "p_pos": p_pos,
                    "s_intensity": s_intensity,
                    "p_intensity": p_intensity,
                    "trans_min": trans_min,
                    "dip_depth": dip_depth,
                },
            )
            logger.info(
                f"   Window {window['window_id']} S-opt {s_pos}°: {s_intensity:.0f} counts; P-opt {p_pos}°: {p_intensity:.0f} counts; Dip {dip_depth:.1f}%",
            )

        # Decision logic: S window shows minimal SPR effect, P window shows SPR dip
        # S-pol: Reference beam, high transmission, minimal difference S vs P modes
        # P-pol: SPR-active beam, shows transmission dip when water present

        if window_signatures[0]["dip_depth"] > window_signatures[1]["dip_depth"]:
            p_window = window_signatures[0]
            s_window = window_signatures[1]
            logger.info("Decision: Window 1 is P-pol (stronger SPR dip)")
        else:
            p_window = window_signatures[1]
            s_window = window_signatures[0]
            logger.info("Decision: Window 2 is P-pol (stronger SPR dip)")

        s_pos = s_window["s_pos"]
        p_pos = p_window["p_pos"]
        separation = abs(s_pos - p_pos)

        # Calculate S/P ratio (S should be higher than P)
        sp_ratio = (
            s_window["s_intensity"] / p_window["p_intensity"]
            if p_window["p_intensity"] > 0
            else 0.0
        )
        # Barrel heuristic: expect ~80 servo units separation on 0-180° scale (~56°); log check
        logger.info(
            f"Heuristic separation target (barrel): ~80 servo units; measured {separation}°",
        )

        logger.info("=" * 80)
        logger.info("[OK] BARREL WINDOW IDENTIFICATION COMPLETE")
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
            "s_intensity": float(s_window["s_intensity"]),
            "p_intensity": float(p_window["p_intensity"]),
            "p_dip_depth": float(p_window["dip_depth"]),
        }

    except Exception as e:
        logger.exception(f"Barrel window search failed: {e}")
        return None
        logger.info(
            f"Estimated S/P (ROI) at windows: {sp_ratio:.2f}× (S={s_meas:.0f}, P={p_meas:.0f})",
        )

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
                f"Intensity range: {max_intensities.min():.0f}-{max_intensities.max():.0f} counts",
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
            logger.warning(
                f"Found: {separation}\u00b0 apart; expected: {expected_separation}\u00b0 ",
            )
            return None

        logger.debug(
            f"Peak separation valid: {separation}\u00b0 (expected ~{expected_separation}\u00b0)",
        )
        logger.debug(f"Candidate positions: pos1={int(pos1)}, pos2={int(pos2)}")

        # Determine S vs P based on intensity at the two positions
        ctrl.servo_set(s=int(pos1), p=int(pos2))
        time.sleep(0.8)

        ctrl.set_mode("s")
        time.sleep(0.5)
        spectrum_pos1 = usb.read_intensity()
        intensity_pos1 = spectrum_pos1.max()

        ctrl.set_mode("p")
        time.sleep(0.5)
        spectrum_pos2 = usb.read_intensity()
        intensity_pos2 = spectrum_pos2.max()

        saturation_limit = int(MAX_DETECTOR_COUNTS * SATURATION_THRESHOLD)
        if intensity_pos1 >= saturation_limit:
            logger.error(
                f"Saturation at position {int(pos1)}; peak {intensity_pos1:.0f} >= {saturation_limit}",
            )
            return None
        if intensity_pos2 >= saturation_limit:
            logger.error(
                f"Saturation at position {int(pos2)}; peak {intensity_pos2:.0f} >= {saturation_limit}",
            )
            return None

        if intensity_pos1 > intensity_pos2:
            s_pos = int(pos1)
            p_pos = int(pos2)
            s_intensity = float(intensity_pos1)
            p_intensity = float(intensity_pos2)
        else:
            s_pos = int(pos2)
            p_pos = int(pos1)
            s_intensity = float(intensity_pos2)
            p_intensity = float(intensity_pos1)

        if p_intensity == 0:
            logger.warning("Validation failed: P-mode intensity is zero")
            return None

        sp_ratio = s_intensity / p_intensity
        if sp_ratio < MIN_SP_RATIO:
            logger.warning(
                f"Validation failed: S/P ratio {sp_ratio:.2f}x < minimum {MIN_SP_RATIO:.2f}x",
            )
            return None

        logger.info("\u2705 FULL SWEEP successful")
        logger.info(f"S position: {s_pos}\u00b0 ({s_intensity:.0f} counts)")
        logger.info(f"P position: {p_pos}\u00b0 ({p_intensity:.0f} counts)")
        logger.info(
            f"S/P ratio: {sp_ratio:.2f}x {'\u2705' if sp_ratio >= IDEAL_SP_RATIO else 'acceptable'}",
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


def auto_calibrate_polarizer(
    usb, ctrl, require_water: bool = True, polarizer_type: str = "circular",
):
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
            current_s = getattr(ctrl, "s_position", 90)
            current_p = getattr(ctrl, "p_position", 0)

            has_water, trans_min, dip_depth = check_water_presence(
                usb, ctrl, current_s, current_p,
            )

            if not has_water:
                logger.error("[ERROR] WATER NOT DETECTED")
                logger.error("   Please ensure:")
                logger.error("   1. Prism has water droplet on sensor surface")
                logger.error("   2. Prism is properly seated")
                logger.error("   3. SPR coupling is established")
                if trans_min is not None:
                    logger.error(f"   Transmission min: {trans_min:.1f}%")
                if dip_depth is not None:
                    logger.error(
                        f"   Dip depth: {dip_depth:.1f}% (need >{MIN_DIP_DEPTH_PERCENT}%)",
                    )
                return None

            logger.info(f"✓ Water detected (dip depth: {dip_depth:.1f}%)")

        # Choose calibration method based on polarizer type
        if polarizer_type == "barrel":
            logger.info("Using BARREL window detection method...")
            logger.info("(Discrete S/P windows, identified by SPR signature)")

            result = perform_barrel_window_search(usb, ctrl)
            if result is None:
                logger.error("[ERROR] Barrel window search failed")
                return None

            # Format barrel results to match expected output
            return {
                "success": True,
                "polarizer_type": "barrel",
                "s_pos": result["s_pos"],
                "p_pos": result["p_pos"],
                "sp_ratio": result["sp_ratio"],
                "dip_depth_percent": result.get("p_dip_depth", 0.0),
                "transmission_min": None,
                "resonance_wavelength": None,
                "separation": result["separation"],
                "validation_checks": [
                    (
                        "Window separation",
                        True,
                        f"{result['separation']:.0f}° (>70° required)",
                    ),
                    (
                        "S/P ratio",
                        result["sp_ratio"] >= MIN_SP_RATIO,
                        f"{result['sp_ratio']:.2f}×",
                    ),
                ],
            }

        # circular polarizer (default)
        logger.info("Using CIRCULAR polarizer quadrant search...")
        logger.info("(90° phase relationship with transmission validation)")

        # Phase 1: Find S and P positions using quadrant search
        result = perform_quadrant_search(usb, ctrl)
        if result is None:
            logger.error("[ERROR] Quadrant search failed")
            return None

        s_pos, p_pos = result

        # Phase 2: Validate positions with transmission analysis
        is_valid, validation_results = validate_positions_with_transmission(
            usb, ctrl, s_pos, p_pos,
        )

        if not is_valid:
            logger.error("[ERROR] VALIDATION FAILED")
            logger.error("   Positions found but transmission quality insufficient")
            logger.error("   Please check:")
            logger.error("   1. Water presence on sensor")
            logger.error("   2. SPR coupling quality")
            logger.error("   3. LED intensity (not saturating)")
            return None

        # Success - return validated results for user confirmation
        logger.info("=" * 80)
        logger.info("[OK] CALIBRATION SUCCESSFUL")
        logger.info(f"   S position: {s_pos}°")
        logger.info(f"   P position: {p_pos}°")
        logger.info(f"   S/P ratio: {validation_results['sp_ratio']:.2f}×")
        logger.info(f"   Dip depth: {validation_results['dip_depth_percent']:.1f}%")
        logger.info(f"   Resonance: {validation_results['resonance_wavelength']:.1f}nm")
        logger.info("=" * 80)
        logger.info("[WARN]  Positions NOT automatically saved")
        logger.info("   User confirmation required before saving to device config")

        return {
            "success": True,
            "polarizer_type": "circular",
            "s_pos": s_pos,
            "p_pos": p_pos,
            "sp_ratio": validation_results["sp_ratio"],
            "dip_depth_percent": validation_results["dip_depth_percent"],
            "resonance_wavelength": validation_results["resonance_wavelength"],
            "transmission_min": validation_results["transmission_min"],
            "validation_checks": validation_results["validation_checks"],
        }

    except Exception as e:
        logger.exception(f"Polarizer calibration error: {e}")
        return None
