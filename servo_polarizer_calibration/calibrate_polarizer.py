"""Universal Polarizer Calibration with Automatic Type Detection.

Stage 1: 5-position bidirectional sweep (1->255->1) measuring mean of top 20 max points
Stage 2: Detect polarizer type (CIRCULAR vs BARREL)
Stage 3: Refine using ±10 PWM sweep around detected S and P regions

**REQUIRES FIRMWARE V1.9+** for multi-LED activation (lm:A,B,C,D command).
Earlier firmware versions do not support simultaneous multi-LED control.

Author: ezControl-AI System
Date: December 7, 2025
"""

import csv
import sys
import time
from pathlib import Path

import numpy as np

# Add parent directory to path for affilabs imports
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from affilabs.core.hardware_manager import HardwareManager
from affilabs.utils.oem_calibration_tool import DeviceProfileManager


def measure_signal(hm):
    """Measure signal using mean of top 20 max points.

    Returns:
        float: Mean intensity of top 20 points

    """
    spectrum = hm.usb.read_intensity()
    top_20_indices = np.argsort(spectrum)[-20:]
    return float(spectrum[top_20_indices].mean())


def measure_with_spectral_analysis(hm, wavelengths, method="max"):
    """Measure intensity using spectral analysis for refinement.

    Args:
        method: 'max' (for S - mean top 20), 'min_spr' (for P in 610-680nm ±10)

    Returns:
        float: Intensity value

    """
    spectrum = hm.usb.read_intensity()

    if method == "max":
        # S position: Mean of top 20 max points
        top_20_indices = np.argsort(spectrum)[-20:]
        return float(spectrum[top_20_indices].mean())

    if method == "min_spr":
        # P position: min in SPR range (610-680nm) + average ±10 points
        mask = (wavelengths >= 610) & (wavelengths <= 680)
        if not np.any(mask):
            # Fallback: use middle 20% of spectrum
            q40 = np.percentile(wavelengths, 40)
            q60 = np.percentile(wavelengths, 60)
            mask = (wavelengths >= q40) & (wavelengths <= q60)

        spectrum_range = spectrum[mask]
        min_idx_in_range = np.argmin(spectrum_range)
        indices = np.where(mask)[0]
        min_idx = indices[min_idx_in_range]

        start = max(0, min_idx - 10)
        end = min(len(spectrum), min_idx + 11)
        return float(spectrum[start:end].mean())

    return float(spectrum.max())


def move_to_position(hm, target_pwm, settle_time=0.3):
    """Move to position using controller HAL method.

    Uses the controller's servo_move_raw_pwm() method which automatically
    handles the correct command format for each firmware type:
    - P4SPR: servo:ANGLE,DURATION (V2.4 firmware)
    - P4PRO: servo:ANGLE,DURATION (V2.0+ firmware)

    Args:
        hm: Hardware manager
        target_pwm: PWM value 0-255 (controller converts to angle)
        settle_time: Additional settle time after movement
    """
    try:
        if target_pwm < 0 or target_pwm > 255:
            print(f"❌ Invalid PWM value: {target_pwm}")
            return False

        ctrl = hm.ctrl
        pwm_val = int(target_pwm)

        # Use the controller's HAL method (handles firmware differences)
        if hasattr(ctrl, 'servo_move_raw_pwm'):
            success = ctrl.servo_move_raw_pwm(pwm_val)

            if success:
                print(f"✅ Servo moved to PWM {pwm_val}")
                # Additional settle time for measurement stability
                time.sleep(settle_time)
                return True
            else:
                print(f"❌ Failed to move servo to PWM {pwm_val}")
                return False
        else:
            print("❌ Controller does not support servo_move_raw_pwm()")
            return False

    except Exception as e:
        print(f"❌ Servo movement failed: {e}")
        return False


def stage1_bidirectional_sweep(hm):
    """Stage 1: 5-position bidirectional sweep.

    Sweep: 1 -> 65 -> 128 -> 191 -> 255 -> 191 -> 128 -> 65 -> 1
    Measure signal (mean top 20) at each position.

    Returns:
        dict with forward and backward sweep data

    """
    print("\n" + "=" * 70)
    print("STAGE 1: BIDIRECTIONAL 5-POSITION SWEEP")
    print("=" * 70)
    print("Measuring mean of top 20 max points at each position\n")

    # 5 positions covering full range
    forward_positions = [1, 65, 128, 191, 255]
    # Backward sweep uses intermediate positions for better coverage
    backward_positions = [255, 223, 159, 96, 32, 1]

    forward_data = []
    backward_data = []

    # Forward sweep
    print("Forward sweep: 1 -> 255")
    for pwm in forward_positions:
        move_to_position(hm, pwm)
        signal = measure_signal(hm)
        forward_data.append({"pwm": pwm, "intensity": signal})
        print(f"  PWM {pwm:3d}: {signal:7.1f} counts")

    # Backward sweep (intermediate positions)
    print("\nBackward sweep: 255 -> 1 (intermediate positions)")
    for pwm in backward_positions:
        move_to_position(hm, pwm)
        signal = measure_signal(hm)
        backward_data.append({"pwm": pwm, "intensity": signal})
        print(f"  PWM {pwm:3d}: {signal:7.1f} counts")

    return {
        "forward": forward_data,
        "backward": backward_data,
        "forward_positions": forward_positions,
        "backward_positions": backward_positions,
    }


def detect_polarizer_type(hm, sweep_data):
    """Stage 2: Detect polarizer type from sweep data.

    CIRCULAR: All positions above dark threshold (3000 counts)
    BARREL: Some positions at/below dark threshold

    Args:
        hm: Hardware manager (needed for testing P candidates in CIRCULAR mode)
        sweep_data: Sweep data from stage 1

    Returns:
        tuple: (type_string, info_dict with p_region, s_region)

    """
    print("\n" + "=" * 70)
    print("STAGE 2: POLARIZER TYPE DETECTION")
    print("=" * 70)

    # Combine forward and backward for analysis
    all_data = sweep_data["forward"] + sweep_data["backward"]
    intensities = np.array([d["intensity"] for d in all_data])

    # Dark threshold for this detector (Ocean Optics USB4000)
    DARK_THRESHOLD = 3000
    BRIGHT_WINDOW_THRESHOLD = 30000  # BARREL windows are significantly above 30K
    SATURATION_THRESHOLD = 60000  # USB4000 saturates at 65535

    # Calculate dynamic range
    min_signal = intensities.min()
    max_signal = intensities.max()
    dynamic_range = max_signal / max(min_signal, 1.0)

    # Check if we have saturation or near-saturation - this will trigger restart
    has_saturation = max_signal > SATURATION_THRESHOLD

    if has_saturation:
        print(f"\n⚠️  SATURATION DETECTED: {max_signal:.1f} counts (threshold: {SATURATION_THRESHOLD})")
        print("    Calibration will restart with 5% LED intensity")
        return "SATURATED", {"max_signal": max_signal}

    # BARREL detection: 2 transmission windows separated by ~80-100 PWM
    # With all 4 LEDs ON at 20%, bright windows should be 10,000+ counts
    DETECTOR_DARK_CURRENT = 3000
    NEAR_DARK_THRESHOLD = 500  # Positions within 500 counts of dark = BARREL
    BRIGHT_THRESHOLD = 6000  # Bright window must be above 6000 counts (all LEDs on)

    # Count positions at different thresholds
    n_above_dark = np.sum(intensities > BRIGHT_THRESHOLD)
    n_near_dark = np.sum(intensities < (DETECTOR_DARK_CURRENT + NEAR_DARK_THRESHOLD))
    n_total = len(intensities)

    # BARREL indicators:
    # 1. Min signal very close to dark threshold (< 500 counts above)
    # 2. Dynamic range > 3.5 (bright windows vs dark regions)
    # 3. Has positions near dark threshold (some < 3500 counts)
    min_above_dark = min_signal - DETECTOR_DARK_CURRENT

    is_barrel = (
        (min_above_dark < NEAR_DARK_THRESHOLD) or  # Min signal barely above dark
        (dynamic_range > 3.5 and n_near_dark >= 2) or  # High dynamic range + dark positions
        (n_above_dark >= 2 and n_near_dark >= 3)  # Bright windows + dark regions
    )

    if is_barrel:
        polarizer_type = "BARREL"
        print("Polarizer Type: BARREL")
        print(f"  Min signal: {min_signal:.1f} counts ({min_above_dark:.1f} above dark threshold)")
        print(f"  Max signal: {max_signal:.1f} counts")
        print(f"  Dynamic range: {dynamic_range:.1f}×")
        print(f"  {n_near_dark} positions near dark (< {DETECTOR_DARK_CURRENT + NEAR_DARK_THRESHOLD})")
        print(f"  {n_above_dark} positions clearly bright (> {BRIGHT_THRESHOLD})")

        # Find 2 SEPARATE transmission windows (spatially separated)
        fwd_intensities = np.array([d["intensity"] for d in sweep_data["forward"]])
        fwd_positions = np.array([d["pwm"] for d in sweep_data["forward"]])

        # Find all positions above bright threshold (with all LEDs on)
        above_dark_mask = fwd_intensities > BRIGHT_THRESHOLD
        above_dark_pwm = fwd_positions[above_dark_mask]
        above_dark_signal = fwd_intensities[above_dark_mask]

        # CRITICAL: MINIMUM SEPARATION for barrel windows
        # Windows must be at least 60 PWM apart (60 degrees) - ideally 80-100 PWM
        MIN_WINDOW_SEPARATION_PWM = 60

        if len(above_dark_pwm) >= 2:
            # Found 2+ bright positions - CHECK if they're on SEPARATE windows
            sorted_indices = np.argsort(above_dark_pwm)
            window1_pwm = int(above_dark_pwm[sorted_indices[0]])
            window1_signal = above_dark_signal[sorted_indices[0]]
            window2_pwm = int(above_dark_pwm[sorted_indices[-1]])
            window2_signal = above_dark_signal[sorted_indices[-1]]

            separation_pwm = abs(window2_pwm - window1_pwm)

            # CHECK: Are these positions far enough apart to be SEPARATE windows?
            if separation_pwm >= MIN_WINDOW_SEPARATION_PWM:
                # YES - Found TWO SEPARATE windows!
                print(f"  ✅ Found 2 SEPARATE windows (separation: {separation_pwm} PWM)")

                # Assign S (STRONGER) and P (WEAKER)
                if window1_signal > window2_signal:
                    s_pwm = window1_pwm
                    p_pwm = window2_pwm
                    s_intensity = window1_signal
                    p_intensity = window2_signal
                else:
                    s_pwm = window2_pwm
                    p_pwm = window1_pwm
                    s_intensity = window2_signal
                    p_intensity = window1_signal

                print(f"  S window (STRONGER) at PWM {s_pwm}: {s_intensity:.1f} counts")
                print(f"  P window (WEAKER) at PWM {p_pwm}: {p_intensity:.1f} counts")
                print(f"  Angular separation: {separation_pwm} PWM units ({separation_pwm * 180 / 255:.0f}°)")

                alternate_s = p_pwm
                alternate_p = s_pwm
            else:
                # NO - Both positions are on the SAME window!
                print(f"  ⚠️  Found 2 positions only {separation_pwm} PWM apart - SAME WINDOW!")
                print(f"  Treating as 1 window found (other window in blind spot)")

                # Use the STRONGER signal as the found window
                if window1_signal > window2_signal:
                    found_pwm = window1_pwm
                    found_signal = window1_signal
                else:
                    found_pwm = window2_pwm
                    found_signal = window2_signal

                print(f"  Found window at PWM {found_pwm}: {found_signal:.1f} counts")
                print(f"  Other window is in BLIND SPOT - calculating position...")

                # Barrel windows separated by ~90 PWM (average of 80-100)
                candidate1_pwm = (found_pwm + 90) % 256
                candidate2_pwm = (found_pwm - 90 + 256) % 256

                print(f"  Candidates: PWM {candidate1_pwm} or PWM {candidate2_pwm}")

                # Choose candidate further from sparse sampling points
                sparse_points = [1, 65, 128, 191, 255]
                dist1 = min(abs(candidate1_pwm - sp) for sp in sparse_points)
                dist2 = min(abs(candidate2_pwm - sp) for sp in sparse_points)

                if dist1 > dist2:
                    p_pwm = candidate1_pwm
                    alternate_p = candidate2_pwm
                else:
                    p_pwm = candidate2_pwm
                    alternate_p = candidate1_pwm

                print(f"  Choosing P at PWM {p_pwm} (dist from sparse: {max(dist1, dist2)})")
                print(f"  Alternate P at PWM {alternate_p}")

                s_pwm = found_pwm
                s_intensity = found_signal
                p_intensity = 0
                alternate_s = found_pwm

        elif len(above_dark_pwm) == 1:
            # Found only 1 window - the other is in a BLIND SPOT!
            # Barrel windows are separated by 80-100 PWM units
            found_pwm = int(above_dark_pwm[0])
            found_signal = above_dark_signal[0]

            print(f"  Found 1 window at PWM {found_pwm}: {found_signal:.1f} counts")
            print(f"  Other window is in BLIND SPOT - calculating position...")

            # Barrel windows separated by ~90 PWM (average of 80-100)
            # Try both directions: +90 and -90
            candidate1_pwm = (found_pwm + 90) % 256  # Wrap around
            candidate2_pwm = (found_pwm - 90 + 256) % 256  # Handle negative wrap

            print(f"  Candidates: PWM {candidate1_pwm} or PWM {candidate2_pwm}")

            # Choose candidate that's MORE LIKELY in blind spot (further from sparse sampling points)
            # Sparse points: 1, 65, 128, 191, 255
            sparse_points = [1, 65, 128, 191, 255]
            dist1 = min(abs(candidate1_pwm - sp) for sp in sparse_points)
            dist2 = min(abs(candidate2_pwm - sp) for sp in sparse_points)

            # Prefer the candidate that's FURTHER from all sparse points (more likely to be in blind spot)
            if dist1 > dist2:
                p_pwm = candidate1_pwm
                alternate_p = candidate2_pwm
            else:
                p_pwm = candidate2_pwm
                alternate_p = candidate1_pwm

            print(f"  Choosing P at PWM {p_pwm} (dist from sparse: {max(dist1, dist2)})")
            print(f"  Alternate P at PWM {alternate_p} (dist from sparse: {min(dist1, dist2)})")

            # Assign strongest as S, blind spot as P
            s_pwm = found_pwm
            s_intensity = found_signal
            p_intensity = 0  # Unknown - in blind spot

            # Store both candidates as alternates
            alternate_s = found_pwm

            print(f"  S window (found) at PWM {s_pwm}: {s_intensity:.1f} counts")
            print(f"  P window (blind spot) estimated at PWM {p_pwm}")
            print(f"  Alternate P at PWM {alternate_p}")

        else:
            # Found 0 windows - BOTH windows in blind spots!
            # Need FULL SWEEP to find transmission windows
            print("  ⚠️  NO bright windows found in sparse sweep!")
            print("  Both transmission windows are in BLIND SPOTS")
            print("  Running FAST SWEEP to locate windows...")

            # Fast sweep every 15 PWM positions (17 total positions)
            full_sweep_data = []
            for pwm in range(1, 256, 15):
                move_to_position(hm, pwm, settle_time=0.2)  # Faster settle
                signal = measure_signal(hm)
                full_sweep_data.append({"pwm": pwm, "intensity": signal})
                if signal > 8000:  # Found a window!
                    print(f"    PWM {pwm:3d}: {signal:7.1f} counts ✓ WINDOW")
                else:
                    print(f"    PWM {pwm:3d}: {signal:7.1f} counts")

            # Find windows from full sweep
            full_intensities = np.array([d["intensity"] for d in full_sweep_data])
            full_positions = np.array([d["pwm"] for d in full_sweep_data])

            # Find positions above 5000 (transmission windows)
            window_mask = full_intensities > 5000
            window_pwm = full_positions[window_mask]
            window_signal = full_intensities[window_mask]

            if len(window_pwm) >= 2:
                # Found 2+ windows
                sorted_idx = np.argsort(window_pwm)
                s_pwm = int(window_pwm[sorted_idx[np.argmax(window_signal[sorted_idx])]])
                # Find second window (spatially separated)
                remaining_idx = [i for i in sorted_idx if abs(window_pwm[i] - s_pwm) > 60]
                if remaining_idx:
                    p_pwm = int(window_pwm[remaining_idx[0]])
                else:
                    p_pwm = (s_pwm + 90) % 256
                alternate_p = (s_pwm - 90 + 256) % 256
                alternate_s = p_pwm
                print(f"  ✅ Found S at PWM {s_pwm}, P at PWM {p_pwm}")
            else:
                # Still couldn't find windows - use brightest from full sweep
                s_idx = np.argmax(full_intensities)
                s_pwm = int(full_positions[s_idx])
                p_pwm = (s_pwm + 90) % 256
                alternate_p = (s_pwm - 90 + 256) % 256
                alternate_s = s_pwm
                print(f"  Using brightest from full sweep: S at PWM {s_pwm}")

        info = {
            "p_region_center": p_pwm,
            "s_region_center": s_pwm,
            "all_above_dark": False,
            # Store alternate windows for fallback (in case we need to swap)
            "alternate_p": alternate_p,  # If P is dark, try this
            "alternate_s": alternate_s,  # If S is dark, try this
        }

    else:
        polarizer_type = "CIRCULAR"
        print("Polarizer Type: CIRCULAR")
        print(f"  Moderate dynamic range: {dynamic_range:.1f}×")
        print(f"  All {n_total} positions above dark threshold ({DARK_THRESHOLD} counts)")
        print(f"  Min signal: {min_signal:.1f} counts")
        print(f"  Max signal: {max_signal:.1f} counts")

        # Find S region from forward sweep (S is easier - maximum transmission)
        fwd_intensities = np.array([d["intensity"] for d in sweep_data["forward"]])
        fwd_positions = np.array([d["pwm"] for d in sweep_data["forward"]])

        # S region: around maximum (perpendicular - HIGH transmission)
        s_idx = np.argmax(fwd_intensities)
        s_pwm = int(fwd_positions[s_idx])

        print(f"  S region (maximum) found at PWM {s_pwm}")

        # CIRCULAR POLARIZER 90 PWM RULE: P = S + 90
        # HS-65MG servo has 180° range (PWM 0-255 maps to 0-180°)
        p_pwm = (s_pwm + 90) % 256

        print(f"  Calculating P using 90 PWM rule")
        print(f"  P = S + 90 = {s_pwm} + 90 = {p_pwm} PWM")

        info = {
            "p_region_center": p_pwm,
            "s_region_center": s_pwm,
            "all_above_dark": True,
        }

    return polarizer_type, info


def stage3_refine_positions(hm, wavelengths, p_center, s_center, is_barrel=False, alternate_p=None, alternate_s=None):
    """Stage 3: Refine positions using ±10 PWM sweep (like validate_optimal_positions_sweep.py).

    Uses 10 scans per position with spectral analysis.

    For BARREL polarizers: Only scans around bright windows (skips dark regions below 10K).
    If all positions are dark, tries alternate window (±80-100 degrees away).

    Args:
        hm: Hardware manager
        wavelengths: Wavelength array
        p_center: Initial P region center
        s_center: Initial S region center
        is_barrel: True for barrel polarizers
        alternate_p: Alternate P window to try if first is all dark
        alternate_s: Alternate S window to try if first is all dark

    Returns:
        dict with optimal P and S positions and statistics

    """
    print("\n" + "=" * 70)
    print("STAGE 3: REFINING POSITIONS (±10 PWM SWEEP)")
    print("=" * 70)

    if is_barrel:
        print("BARREL polarizer: Scanning around estimated window positions\n")

    print(f"P region: PWM {max(1, p_center-10)} to {min(255, p_center+10)}")
    print(f"S region: PWM {max(1, s_center-10)} to {min(255, s_center+10)}")
    print("2 scans per position with spectral analysis (optimized for speed)\n")

    # === Refine P region ===
    print("Refining P region (3 PWM steps)...")
    p_results = []

    # DON'T skip positions for BARREL - we might be scanning a blind spot!
    # Scan full ±10 range to characterize window width and stability
    # Use 3 PWM steps for faster scanning

    for idx, pwm in enumerate(range(max(1, p_center - 10), min(256, p_center + 11), 3)):
        # Approach from high only on first position to establish reference
        if idx == 0:
            move_to_position(hm, 255, settle_time=0.2)
        move_to_position(hm, pwm, settle_time=0.1)

        # 2 scans (reduced for speed)
        measurements = []
        for _ in range(2):
            intensity = measure_with_spectral_analysis(
                hm,
                wavelengths,
                method="min_spr",
            )
            measurements.append(intensity)

        mean_val = np.mean(measurements)
        std_val = np.std(measurements)
        cv = (std_val / mean_val) * 100

        p_results.append(
            {
                "pwm": pwm,
                "mean": mean_val,
                "std": std_val,
                "cv_percent": cv,
            },
        )

        print(f"  PWM {pwm:3d}: {mean_val:7.1f} ± {std_val:5.1f} (CV: {cv:.2f}%)")

    # BARREL: If all positions were dark (below 5000), try alternate window
    all_p_dark = all(r["mean"] < 5000 for r in p_results)
    if is_barrel and all_p_dark and alternate_p is not None:
        print(f"\n⚠️  All positions dark! Trying alternate P window at PWM {alternate_p}")
        p_results = []  # Clear dark results
        p_center = alternate_p
        for idx, pwm in enumerate(range(max(1, p_center - 10), min(256, p_center + 11), 3)):
            # Approach from high only on first position
            if idx == 0:
                move_to_position(hm, 255, settle_time=0.2)
            move_to_position(hm, pwm, settle_time=0.1)

            measurements = []
            for _ in range(2):
                intensity = measure_with_spectral_analysis(hm, wavelengths, method="min_spr")
                measurements.append(intensity)

            mean_val = np.mean(measurements)
            std_val = np.std(measurements)
            cv = (std_val / mean_val) * 100

            p_results.append({"pwm": pwm, "mean": mean_val, "std": std_val, "cv_percent": cv})
            print(f"  PWM {pwm:3d}: {mean_val:7.1f} ± {std_val:5.1f} (CV: {cv:.2f}%)")

    # Find optimal P (minimum + stable range)
    p_min = min(p_results, key=lambda x: x["mean"])
    p_stable = [p for p in p_results if p["mean"] <= p_min["mean"] * 1.01]
    p_optimal_median = int(np.median([p["pwm"] for p in p_stable]))

    # Find closest scanned position (needed when using 3 PWM steps)
    p_optimal = min(p_stable, key=lambda x: abs(x["pwm"] - p_optimal_median))["pwm"]

    print(
        f"\nP stable range: {len(p_stable)} positions (PWM {min(p['pwm'] for p in p_stable)}-{max(p['pwm'] for p in p_stable)})",
    )
    print(f"Selected P: PWM {p_optimal}")

    # === Refine S region ===
    print("\nRefining S region (3 PWM steps)...")

    s_results = []

    for idx, pwm in enumerate(range(max(1, s_center - 10), min(256, s_center + 11), 3)):
        # Approach from low only on first position to establish reference
        if idx == 0:
            move_to_position(hm, 1, settle_time=0.2)
        move_to_position(hm, pwm, settle_time=0.3)

        # 5 scans
        measurements = []
        for _ in range(5):
            intensity = measure_with_spectral_analysis(hm, wavelengths, method="max")
            measurements.append(intensity)
            time.sleep(0.05)

        mean_val = np.mean(measurements)
        std_val = np.std(measurements)
        cv = (std_val / mean_val) * 100

        s_results.append(
            {
                "pwm": pwm,
                "mean": mean_val,
                "std": std_val,
                "cv_percent": cv,
            },
        )

        print(f"  PWM {pwm:3d}: {mean_val:7.1f} ± {std_val:5.1f} (CV: {cv:.2f}%)")

    # BARREL: If all positions were dark (below 5000 for S), try alternate window
    all_s_dark = all(r["mean"] < 5000 for r in s_results)
    if is_barrel and all_s_dark and alternate_s is not None:
        print(f"\n⚠️  All positions dark! Trying alternate S window at PWM {alternate_s}")
        s_results = []  # Clear dark results
        s_center = alternate_s
        for idx, pwm in enumerate(range(max(1, s_center - 10), min(256, s_center + 11), 3)):
            # Approach from low only on first position
            if idx == 0:
                move_to_position(hm, 1, settle_time=0.1)
            move_to_position(hm, pwm, settle_time=0.1)

            measurements = []
            for _ in range(2):
                intensity = measure_with_spectral_analysis(hm, wavelengths, method="max")
                measurements.append(intensity)

            mean_val = np.mean(measurements)
            std_val = np.std(measurements)
            cv = (std_val / mean_val) * 100

            s_results.append({"pwm": pwm, "mean": mean_val, "std": std_val, "cv_percent": cv})
            print(f"  PWM {pwm:3d}: {mean_val:7.1f} ± {std_val:5.1f} (CV: {cv:.2f}%)")

    # Find optimal S (maximum + stable range)
    s_max = max(s_results, key=lambda x: x["mean"])
    s_stable = [s for s in s_results if s["mean"] >= s_max["mean"] * 0.99]
    s_optimal_median = int(np.median([s["pwm"] for s in s_stable]))

    # Find closest scanned position (needed when using 3 PWM steps)
    s_optimal = min(s_stable, key=lambda x: abs(x["pwm"] - s_optimal_median))["pwm"]

    print(
        f"\nS stable range: {len(s_stable)} positions (PWM {min(s['pwm'] for s in s_stable)}-{max(s['pwm'] for s in s_stable)})",
    )
    print(f"Selected S: PWM {s_optimal}")

    # Get final stats at optimal positions
    p_final = next(p for p in p_results if p["pwm"] == p_optimal)
    s_final = next(s for s in s_results if s["pwm"] == s_optimal)

    # CRITICAL VALIDATION: Check separation (all polarizer types)
    separation_pwm = abs(s_optimal - p_optimal)
    separation_deg = (separation_pwm / 255.0) * 180.0

    MIN_SEPARATION_PWM = 60  # 60 degrees minimum

    if separation_pwm < MIN_SEPARATION_PWM:
        print("\n" + "=" * 70)
        print("❌ CRITICAL ERROR: POSITIONS TOO CLOSE TOGETHER")
        print("=" * 70)
        print(f"S position: PWM {s_optimal} ({(s_optimal/255.0)*180:.1f}°)")
        print(f"P position: PWM {p_optimal} ({(p_optimal/255.0)*180:.1f}°)")
        print(f"Separation: {separation_pwm} PWM ({separation_deg:.1f}°)")
        print(f"MINIMUM REQUIRED: {MIN_SEPARATION_PWM} PWM (60°)")
        print("")
        print("This indicates:")
        print("  1. Both positions may be on the SAME window")
        print("  2. Mechanical coupling may be slipping")
        print("  3. Polarizer may not be rotating with servo")
        print("")
        print("CALIBRATION CANNOT CONTINUE - FIX HARDWARE ISSUE")
        print("=" * 70)
        raise RuntimeError(
            f"Stage 3 refinement failed: S and P positions only {separation_deg:.1f}° apart "
            f"(minimum required: 60°). Check mechanical coupling."
        )

    return {
        "p_pwm": p_optimal,
        "p_intensity": p_final["mean"],
        "p_std": p_final["std"],
        "p_cv_percent": p_final["cv_percent"],
        "p_stable_range": (
            min(p["pwm"] for p in p_stable),
            max(p["pwm"] for p in p_stable),
        ),
        "s_pwm": s_optimal,
        "s_intensity": s_final["mean"],
        "s_std": s_final["std"],
        "s_cv_percent": s_final["cv_percent"],
        "s_stable_range": (
            min(s["pwm"] for s in s_stable),
            max(s["pwm"] for s in s_stable),
        ),
        "p_all_results": p_results,
        "s_all_results": s_results,
    }


def main():
    """Main calibration routine with automatic saturation handling."""
    print("\n" + "=" * 70)
    print("UNIVERSAL POLARIZER CALIBRATION")
    print("=" * 70)

    hm = HardwareManager()

    try:
        # Connect to hardware
        print("\nConnecting hardware...")
        hm.scan_and_connect(auto_connect=True)

        # Wait for connection
        t0 = time.time()
        while time.time() - t0 < 15.0:
            if hm.ctrl and hm.usb:
                break
            time.sleep(0.5)

        if not hm.ctrl or not hm.usb:
            print("ERROR: Hardware not connected")
            sys.exit(1)

        # Get serial number FIRST for device identification
        serial_number = hm.usb.serial_number
        ctrl_name = hm.ctrl.get_device_type() if hasattr(hm.ctrl, 'get_device_type') else 'Controller'
        print(f"Connected: {ctrl_name}, {serial_number}")
        print(f"Device Serial: {serial_number}\n")

        # Detect if this is P4PRO firmware (requires channel enable before batch command)
        is_p4pro = hasattr(hm.ctrl, 'firmware_id') and 'P4PRO' in hm.ctrl.firmware_id

        # P4PRO uses 40% initial intensity, others use 20%
        led_intensity_percent = 40 if is_p4pro else 20
        max_attempts = 2

        for attempt in range(max_attempts):
            led_intensity = int(led_intensity_percent * 255 / 100)

            # Set all LEDs
            print(f"Setting all 4 LEDs to {led_intensity_percent}% ({led_intensity}/255)...")
            try:
                if is_p4pro:
                    # P4PRO: Enable channels first, then set batch intensity
                    print("  (P4PRO detected - enabling channels before batch command)")
                    for ch in ['a', 'b', 'c', 'd']:
                        hm.ctrl.turn_on_channel(ch=ch)
                    time.sleep(0.05)  # Allow channels to enable

                # Set all intensities via batch command
                hm.ctrl.set_batch_intensities(a=led_intensity, b=led_intensity, c=led_intensity, d=led_intensity)
            except Exception as e:
                print(f"  Warning: Batch LED setup failed: {e}")
                # Fallback: Set individual LEDs
                print("  (Using individual LED commands for compatibility)")
                for ch in ['a', 'b', 'c', 'd']:
                    try:
                        hm.ctrl.turn_on_channel(ch=ch)
                        hm.ctrl.set_intensity(ch=ch, raw_val=led_intensity)
                    except Exception:
                        pass  # Skip if channel doesn't exist
            time.sleep(0.2)  # Allow LEDs to stabilize

            # Set integration time to 5ms
            print("Setting integration time to 5ms...")
            hm.usb.set_integration(5.0)

            # Get wavelengths (HAL OceanSpectrometerAdapter uses read_wavelength)
            wavelengths = hm.usb.read_wavelength()

            time.sleep(1.0)

            # === STAGE 1: Bidirectional sweep ===
            sweep_data = stage1_bidirectional_sweep(hm)

            # === STAGE 2: Detect polarizer type ===
            polarizer_type, type_info = detect_polarizer_type(hm, sweep_data)

            # Check if saturated - restart with lower intensity
            if polarizer_type == "SATURATED":
                if attempt < max_attempts - 1:
                    print(f"\n🔄 Restarting calibration (Attempt {attempt + 2}/{max_attempts})")
                    led_intensity_percent = 5  # Lower to 5%
                    time.sleep(1.0)
                    continue
                else:
                    print("\n❌ Still saturated at 5% LED intensity!")
                    sys.exit(1)

            is_barrel = (polarizer_type == "BARREL")

            # === STAGE 3: Refine positions ===
            refinement = stage3_refine_positions(
                hm,
                wavelengths,
                type_info["p_region_center"],
                type_info["s_region_center"],
                is_barrel=is_barrel,
                alternate_p=type_info.get("alternate_p"),
                alternate_s=type_info.get("alternate_s"),
            )

            # Success - break out of retry loop
            break

        # === FINAL SUMMARY ===
        print("\n" + "=" * 70)
        print("CALIBRATION COMPLETE")
        print("=" * 70)
        print(f"Polarizer Type: {polarizer_type}")
        print(f"\nP Position: PWM {refinement['p_pwm']}")
        print(
            f"  Stable range: PWM {refinement['p_stable_range'][0]}-{refinement['p_stable_range'][1]}",
        )
        print(
            f"  Intensity: {refinement['p_intensity']:.1f} ± {refinement['p_std']:.1f} counts",
        )
        print(f"  Noise: {refinement['p_cv_percent']:.2f}% CV")
        print(f"\nS Position: PWM {refinement['s_pwm']}")
        print(
            f"  Stable range: PWM {refinement['s_stable_range'][0]}-{refinement['s_stable_range'][1]}",
        )
        print(
            f"  Intensity: {refinement['s_intensity']:.1f} ± {refinement['s_std']:.1f} counts",
        )
        print(f"  Noise: {refinement['s_cv_percent']:.2f}% CV")

        ratio = refinement["s_intensity"] / refinement["p_intensity"]
        separation = refinement["s_intensity"] - refinement["p_intensity"]
        print(f"\nS/P Ratio: {ratio:.2f}×")
        print(f"Separation: {separation:.0f} counts")
        print("=" * 70)

        # Save results to CSV
        output_path = ROOT / "polarizer_calibration_results.csv"
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Parameter", "Value"])
            writer.writerow(["Polarizer Type", polarizer_type])
            writer.writerow(["P PWM", refinement["p_pwm"]])
            writer.writerow(
                [
                    "P Stable Range",
                    f"{refinement['p_stable_range'][0]}-{refinement['p_stable_range'][1]}",
                ],
            )
            writer.writerow(["P Intensity", f"{refinement['p_intensity']:.1f}"])
            writer.writerow(["P Std", f"{refinement['p_std']:.1f}"])
            writer.writerow(["P CV%", f"{refinement['p_cv_percent']:.2f}"])
            writer.writerow(["S PWM", refinement["s_pwm"]])
            writer.writerow(
                [
                    "S Stable Range",
                    f"{refinement['s_stable_range'][0]}-{refinement['s_stable_range'][1]}",
                ],
            )
            writer.writerow(["S Intensity", f"{refinement['s_intensity']:.1f}"])
            writer.writerow(["S Std", f"{refinement['s_std']:.1f}"])
            writer.writerow(["S CV%", f"{refinement['s_cv_percent']:.2f}"])
            writer.writerow(["S/P Ratio", f"{ratio:.2f}"])
            writer.writerow(["Separation", f"{separation:.0f}"])

        print(f"\nResults saved to: {output_path}")

        # Save detailed sweep data
        detail_path = ROOT / "polarizer_calibration_detail.csv"
        with open(detail_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Region", "PWM", "Mean", "Std", "CV%"])
            for p in refinement["p_all_results"]:
                writer.writerow(
                    [
                        "P",
                        p["pwm"],
                        f"{p['mean']:.2f}",
                        f"{p['std']:.2f}",
                        f"{p['cv_percent']:.2f}",
                    ],
                )
            for s in refinement["s_all_results"]:
                writer.writerow(
                    [
                        "S",
                        s["pwm"],
                        f"{s['mean']:.2f}",
                        f"{s['std']:.2f}",
                        f"{s['cv_percent']:.2f}",
                    ],
                )

        print(f"Detailed data saved to: {detail_path}")

        # === SAVE TO DEVICE PROFILE ===
        print("\n" + "=" * 70)
        print("SAVING TO DEVICE PROFILE")
        print("=" * 70)

        polarizer_results = {
            "s_position": refinement["s_pwm"],
            "p_position": refinement["p_pwm"],
            "sp_ratio": ratio,
            "polarizer_type": polarizer_type,
            "method": "servo_calibration_barrel_detection",
            "led_intensity_used": f"{led_intensity_percent}%",
            "s_intensity": refinement["s_intensity"],
            "p_intensity": refinement["p_intensity"],
            "s_stable_range": refinement["s_stable_range"],
            "p_stable_range": refinement["p_stable_range"],
        }

        try:
            profile_mgr = DeviceProfileManager(ROOT / "calibration_data")
            profile_path = profile_mgr.save_profile(
                serial_number=serial_number,
                polarizer_results=polarizer_results,
                afterglow_results=None,
                detector_model="USB4000",
                led_type="LCW",
            )
            print(f"✅ Device profile saved: {profile_path}")

            # Also update device_config.json
            profile_mgr.update_device_config(polarizer_results, serial_number=serial_number)
            print("✅ Updated device_config.json")

        except Exception as e:
            print(f"⚠️  Failed to save device profile: {e}")
            print("   (CSV files were still saved successfully)")

    finally:
        # Cleanup
        print("\nCleaning up...")
        try:
            hm.ctrl._ser.write(b"lx\n")
        except:
            pass
        print("Done!")


def run_servo_calibration_from_hardware_mgr(hardware_mgr, progress_callback=None):
    """Wrapper function to run servo calibration from hardware manager.

    This is called from the OEM model training workflow.

    Args:
        hardware_mgr: Hardware manager with ctrl and usb attributes
        progress_callback: Optional callback for progress updates (message, percent)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        ctrl = hardware_mgr.ctrl
        usb = hardware_mgr.usb

        if not ctrl or not usb:
            print("ERROR: Hardware not connected")
            return False

        serial_number = usb.serial_number
        print(f"Starting servo calibration for {serial_number}...")

        # Start with very low LED intensity to avoid saturation
        # Try 20% first, fallback to 5%/2%/1% if saturated
        led_intensity_options = [20, 5, 2, 1]
        max_attempts = len(led_intensity_options)

        for attempt in range(max_attempts):
            led_intensity_percent = led_intensity_options[attempt]
            led_intensity = int(led_intensity_percent * 255 / 100)

            # Enable all 4 LEDs first (CRITICAL for P4PRO firmware)
            print(f"\nAttempt {attempt+1}/{max_attempts}: Enabling LEDs with lm:ABCD...")
            if hasattr(ctrl, 'enable_multi_led'):
                result = ctrl.enable_multi_led(a=True, b=True, c=True, d=True)
                print(f"  enable_multi_led() returned: {result}")
            else:
                print(f"  WARNING: Controller type {type(ctrl).__name__} has no enable_multi_led() method!")

            # Brief delay for LED enable to take effect
            time.sleep(0.2)

            # Set LED intensities
            print(f"Setting LEDs to {led_intensity_percent}% ({led_intensity}/255) using set_batch_intensities()...")
            result = ctrl.set_batch_intensities(a=led_intensity, b=led_intensity, c=led_intensity, d=led_intensity)
            print(f"  set_batch_intensities() returned: {result}")

            # Brief delay for intensity to settle
            time.sleep(0.2)

            # Set integration time to 5ms
            print("Setting integration time to 5ms...")
            usb.set_integration(5.0)

            # Get wavelengths
            wavelengths = usb.read_wavelength()
            time.sleep(1.0)

            # === STAGE 1: Bidirectional sweep ===
            if progress_callback:
                progress_callback("Servo cal: Stage 1 - Bidirectional sweep...", 10)
            sweep_data = stage1_bidirectional_sweep(hardware_mgr)

            # === STAGE 2: Detect polarizer type ===
            if progress_callback:
                progress_callback("Servo cal: Stage 2 - Polarizer type detection...", 30)
            polarizer_type, type_info = detect_polarizer_type(hardware_mgr, sweep_data)

            # Check if saturated - restart with lower intensity
            if polarizer_type == "SATURATED":
                if attempt < max_attempts - 1:
                    print(f"\n🔄 Restarting calibration (Attempt {attempt + 2}/{max_attempts})")
                    led_intensity_percent = 5  # Lower to 5%
                    time.sleep(1.0)
                    continue
                else:
                    print("\n❌ Still saturated at 5% LED intensity!")
                    return False

            is_barrel = (polarizer_type == "BARREL")

            # === STAGE 3: Refine positions ===
            if progress_callback:
                progress_callback("Servo cal: Stage 3 - Position refinement...", 60)
            refinement = stage3_refine_positions(
                hardware_mgr,
                wavelengths,
                type_info["p_region_center"],
                type_info["s_region_center"],
                is_barrel=is_barrel,
                alternate_p=type_info.get("alternate_p"),
                alternate_s=type_info.get("alternate_s"),
            )

            # Success - break out of retry loop
            break

        # ===== CRITICAL VALIDATION: DEGREE SEPARATION =====
        # HS-65MG servo: PWM 0-255 maps to 0-180 degrees
        def pwm_to_degrees(pwm):
            return (pwm / 255.0) * 180.0

        s_degrees = pwm_to_degrees(refinement['s_pwm'])
        p_degrees = pwm_to_degrees(refinement['p_pwm'])
        separation_degrees = abs(s_degrees - p_degrees)

        # BARREL polarizers REQUIRE 80-110° separation (typically ~90°)
        MIN_SEPARATION_DEGREES = 80.0
        MAX_SEPARATION_DEGREES = 110.0

        if polarizer_type == "BARREL" and (separation_degrees < MIN_SEPARATION_DEGREES or separation_degrees > MAX_SEPARATION_DEGREES):
            print("\n" + "=" * 70)
            print("❌ CALIBRATION FAILED - INVALID SERVO POSITIONS")
            print("=" * 70)
            print(f"S Position: PWM {refinement['s_pwm']} = {s_degrees:.1f}°")
            print(f"P Position: PWM {refinement['p_pwm']} = {p_degrees:.1f}°")
            print(f"Separation: {separation_degrees:.1f}° (REQUIRED: {MIN_SEPARATION_DEGREES}-{MAX_SEPARATION_DEGREES}°)")
            print("")
            print("BARREL polarizers have two transmission windows that MUST be")
            print(f"separated by {MIN_SEPARATION_DEGREES}-{MAX_SEPARATION_DEGREES} degrees (typically ~90 degrees).")
            print("")
            print("Possible causes:")
            print("  1. Polarizer barrel not rotating with servo")
            print("  2. Mechanical slippage in coupling")
            print("  3. Wrong polarizer type detected")
            print("  4. Incorrect window detection (both windows on same quadrant)")
            print("")
            print("ACTION REQUIRED: Check mechanical coupling and re-run calibration")
            print("=" * 70)
            return False

        # Print results
        ratio = refinement["s_intensity"] / refinement["p_intensity"]
        separation = refinement["s_intensity"] - refinement["p_intensity"]

        print("\n" + "=" * 70)
        print("SERVO CALIBRATION COMPLETE")
        print("=" * 70)
        print(f"Polarizer Type: {polarizer_type}")
        print(f"\nP Position: PWM {refinement['p_pwm']} ({p_degrees:.1f}°)")
        print(f"S Position: PWM {refinement['s_pwm']} ({s_degrees:.1f}°)")
        print(f"Angular Separation: {separation_degrees:.1f}° {'✅' if MIN_SEPARATION_DEGREES <= separation_degrees <= MAX_SEPARATION_DEGREES else '⚠️'}")
        print(f"\nS/P Ratio: {ratio:.2f}×")
        print(f"Separation: {separation:.0f} counts")
        print("=" * 70)

        # Save to device profile
        polarizer_results = {
            "s_position": refinement["s_pwm"],
            "p_position": refinement["p_pwm"],
            "sp_ratio": ratio,
            "polarizer_type": polarizer_type,
            "method": "servo_calibration_barrel_detection",
            "led_intensity_used": f"{led_intensity_percent}%",
            "s_intensity": refinement["s_intensity"],
            "p_intensity": refinement["p_intensity"],
            "s_stable_range": refinement["s_stable_range"],
            "p_stable_range": refinement["p_stable_range"],
        }

        try:
            # Use project root instead of ROOT to ensure correct path when called from OEM training
            from pathlib import Path as PathLib
            project_root = PathLib(__file__).resolve().parents[1]

            profile_mgr = DeviceProfileManager(project_root / "calibration_data")
            profile_path = profile_mgr.save_profile(
                serial_number=serial_number,
                polarizer_results=polarizer_results,
                afterglow_results=None,
                detector_model="USB4000",
                led_type="LCW",
            )
            print(f"✅ Device profile saved: {profile_path}")

            # Also update device_config.json
            profile_mgr.update_device_config(polarizer_results, serial_number=serial_number)
            print("✅ Updated device_config.json")

            if progress_callback:
                progress_callback("Servo calibration complete!", 100)

            return True

        except Exception as e:
            print(f"⚠️  Failed to save device profile: {e}")
            return False

    except Exception as e:
        print(f"❌ Servo calibration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # CRITICAL: Always turn off LEDs on exit (graceful or crash)
        print("\n[CLEANUP] Turning off all LEDs...")
        try:
            if ctrl and ctrl._ser:
                # Use lx command (turn off all LEDs)
                ctrl._ser.write(b"lx\n")
                time.sleep(0.1)
                print("[CLEANUP] ✅ LEDs turned off")
        except Exception as cleanup_err:
            print(f"[CLEANUP] ⚠️  Failed to turn off LEDs: {cleanup_err}")


def run_calibration_with_hardware(hardware_manager, progress_callback=None):
    """Run polarizer calibration using existing hardware connection.

    This function is called from the main application and uses the hardware
    that's already connected, avoiding COM port conflicts.

    Args:
        hardware_manager: HardwareManager instance with connected hardware
        progress_callback: Optional callback for progress updates

    Returns:
        bool: True if successful, False otherwise
    """
    from affilabs.utils.logger import logger

    hm = hardware_manager
    ctrl = hm.ctrl
    usb = hm.usb

    if not ctrl or not usb:
        logger.error("Hardware not available for polarizer calibration")
        return False

    try:
        logger.info("=" * 70)
        logger.info("POLARIZER CALIBRATION (Using Connected Hardware)")
        logger.info("=" * 70)

        # Get serial number for device identification
        serial_number = usb.serial_number
        ctrl_name = ctrl.get_device_type() if hasattr(ctrl, 'get_device_type') else 'Controller'
        logger.info(f"Connected: {ctrl_name}, {serial_number}")
        logger.info(f"Device Serial: {serial_number}")

        # Try 20% first, fallback to 5% if saturated
        led_intensity_percent = 20
        max_attempts = 2

        for attempt in range(max_attempts):
            led_intensity = int(led_intensity_percent * 255 / 100)

            # Set LED intensities
            logger.info(f"Setting LEDs to {led_intensity_percent}% ({led_intensity}/255)...")
            ctrl.set_batch_intensities(a=led_intensity, b=led_intensity, c=led_intensity, d=led_intensity)

            # Set integration time to 5ms
            logger.info("Setting integration time to 5ms...")
            usb.set_integration(5.0)

            # Get wavelengths
            wavelengths = usb.read_wavelength()

            time.sleep(1.0)

            # === STAGE 1: Bidirectional sweep ===
            sweep_data = stage1_bidirectional_sweep(hm)

            # === STAGE 2: Detect polarizer type ===
            polarizer_type, type_info = detect_polarizer_type(hm, sweep_data)

            # Check if saturated - restart with lower intensity
            if polarizer_type == "SATURATED":
                if attempt < max_attempts - 1:
                    logger.warning(f"🔄 Restarting calibration (Attempt {attempt + 2}/{max_attempts})")
                    led_intensity_percent = 5  # Lower to 5%
                    time.sleep(1.0)
                    continue
                else:
                    logger.error("❌ Saturation persists at 5% - cannot calibrate")
                    return False

            # Success - break out of retry loop
            break

        logger.info(f"\n📊 Polarizer Type Detected: {polarizer_type}")
        logger.info(f"   Detection Confidence: {type_info.get('confidence', 'N/A')}")

        if progress_callback:
            progress_callback(f"Detected: {polarizer_type}", 40)

        # === STAGE 3: Refinement ===
        logger.info("\n" + "=" * 70)
        logger.info("STAGE 3: REFINEMENT")
        logger.info("=" * 70)

        is_barrel = (polarizer_type == "BARREL")
        refinement = stage3_refine_positions(
            hm,
            wavelengths,
            type_info["p_region_center"],
            type_info["s_region_center"],
            is_barrel=is_barrel,
            alternate_p=type_info.get("alternate_p"),
            alternate_s=type_info.get("alternate_s"),
        )

        # ===== CRITICAL VALIDATION: DEGREE SEPARATION =====
        # HS-65MG servo: PWM 0-255 maps to 0-180 degrees
        def pwm_to_degrees(pwm):
            return (pwm / 255.0) * 180.0

        s_degrees = pwm_to_degrees(refinement['s_pwm'])
        p_degrees = pwm_to_degrees(refinement['p_pwm'])
        separation_degrees = abs(s_degrees - p_degrees)

        # BARREL polarizers REQUIRE 80-110° separation (typically ~90°)
        MIN_SEPARATION_DEGREES = 80.0
        MAX_SEPARATION_DEGREES = 110.0

        if is_barrel and (separation_degrees < MIN_SEPARATION_DEGREES or separation_degrees > MAX_SEPARATION_DEGREES):
            logger.error("\n" + "=" * 70)
            logger.error("❌ CALIBRATION FAILED - INVALID SERVO POSITIONS")
            logger.error("=" * 70)
            logger.error(f"S Position: PWM {refinement['s_pwm']} = {s_degrees:.1f}°")
            logger.error(f"P Position: PWM {refinement['p_pwm']} = {p_degrees:.1f}°")
            logger.error(f"Separation: {separation_degrees:.1f}° (REQUIRED: {MIN_SEPARATION_DEGREES}-{MAX_SEPARATION_DEGREES}°)")
            logger.error("")
            logger.error("BARREL polarizers have two transmission windows that MUST be")
            logger.error(f"separated by {MIN_SEPARATION_DEGREES}-{MAX_SEPARATION_DEGREES} degrees (typically ~90 degrees).")
            logger.error("")
            logger.error("Possible causes:")
            logger.error("  1. Polarizer barrel not rotating with servo")
            logger.error("  2. Mechanical slippage in coupling")
            logger.error("  3. Wrong polarizer type detected")
            logger.error("  4. Incorrect window detection (both windows on same quadrant)")
            logger.error("")
            logger.error("ACTION REQUIRED: Check mechanical coupling and re-run calibration")
            logger.error("=" * 70)
            return False

        # Display results
        ratio = refinement["s_intensity"] / refinement["p_intensity"] if refinement["p_intensity"] > 0 else 0

        logger.info("\n" + "=" * 70)
        logger.info("✅ CALIBRATION COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Polarizer Type:    {polarizer_type}")
        logger.info(f"S Position (PWM):  {refinement['s_pwm']} ({s_degrees:.1f}°)")
        logger.info(f"P Position (PWM):  {refinement['p_pwm']} ({p_degrees:.1f}°)")
        logger.info(f"Angular Separation: {separation_degrees:.1f}° {'✅' if MIN_SEPARATION_DEGREES <= separation_degrees <= MAX_SEPARATION_DEGREES else '⚠️'}")
        logger.info(f"S/P Ratio:         {ratio:.2f}")
        logger.info(f"S Intensity:       {refinement['s_intensity']:.1f}")
        logger.info(f"P Intensity:       {refinement['p_intensity']:.1f}")
        logger.info(f"S Stable Range:    {refinement['s_stable_range']}")
        logger.info(f"P Stable Range:    {refinement['p_stable_range']}")
        logger.info("=" * 70)

        if progress_callback:
            progress_callback(f"Calibration Complete! S={refinement['s_pwm']} P={refinement['p_pwm']}", 80)

        # Save to device profile
        polarizer_results = {
            "s_position": refinement["s_pwm"],
            "p_position": refinement["p_pwm"],
            "sp_ratio": ratio,
            "polarizer_type": polarizer_type,
            "method": "servo_calibration_barrel_detection",
            "led_intensity_used": f"{led_intensity_percent}%",
            "s_intensity": refinement["s_intensity"],
            "p_intensity": refinement["p_intensity"],
            "s_stable_range": refinement["s_stable_range"],
            "p_stable_range": refinement["p_stable_range"],
        }

        try:
            from pathlib import Path as PathLib
            project_root = PathLib(__file__).resolve().parents[1]

            profile_mgr = DeviceProfileManager(project_root / "calibration_data")
            profile_path = profile_mgr.save_profile(
                serial_number=serial_number,
                polarizer_results=polarizer_results,
                afterglow_results=None,
                detector_model="USB4000",
                led_type="LCW",
            )
            logger.info(f"✅ Device profile saved: {profile_path}")

            # Update device_config.json
            profile_mgr.update_device_config(polarizer_results, serial_number=serial_number)
            logger.info("✅ Updated device_config.json")

            if progress_callback:
                progress_callback("Servo calibration complete!", 100)

            return True

        except Exception as e:
            logger.error(f"⚠️  Failed to save device profile: {e}")
            return False

    except Exception as e:
        logger.error(f"❌ Servo calibration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup - turn off LEDs
        try:
            ctrl._ser.write(b"lx\n")
        except:
            pass


if __name__ == "__main__":
    main()
