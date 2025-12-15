"""Mechanical validation test with directional approach control.

To eliminate hysteresis effects, this test always approaches each position
from the same direction by first moving to a reference position.

Strategy:
- For P position: Always approach from above (move to PWM 50, then down to P)
- For S position: Always approach from below (move to PWM 1, then up to S)
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from core.hardware_manager import HardwareManager


def move_and_measure(hm, target_pwm, approach_pwm, num_samples=10, settle_time=1.5):
    """Move to position with directional approach and take measurements.

    Args:
        hm: Hardware manager
        target_pwm: Target position
        approach_pwm: Position to move to first (to control direction)
        num_samples: Number of measurements to take
        settle_time: Time to wait after reaching target

    """
    # Step 1: Move to approach position
    cmd = f"sv{approach_pwm:03d}000\n"
    hm.ctrl._ser.reset_input_buffer()
    hm.ctrl._ser.write(cmd.encode())
    time.sleep(0.05)
    hm.ctrl._ser.write(b"ss\n")
    time.sleep(1.0)  # Wait to reach approach position

    # Step 2: Move to target position
    cmd = f"sv{target_pwm:03d}000\n"
    hm.ctrl._ser.reset_input_buffer()
    hm.ctrl._ser.write(cmd.encode())
    time.sleep(0.05)
    hm.ctrl._ser.write(b"ss\n")

    # Wait for servo to settle
    time.sleep(settle_time)

    # Take measurements
    intensities = []
    for _ in range(num_samples):
        spectrum = hm.usb.read_intensity()
        if spectrum is not None:
            intensity = float(spectrum.max())
            intensities.append(intensity)
        time.sleep(0.05)  # Small delay between samples

    return intensities


def main():
    print("=== DIRECTIONAL S AND P POSITION VALIDATION TEST ===\n")

    print("Connecting hardware...")
    hm = HardwareManager()
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

    print(f"Connected: {hm.ctrl.name}, {hm.usb.serial_number}\n")

    # Turn on LEDs
    print("Turning on LEDs (A,B,C,D at 20%)...")
    hm.ctrl._ser.write(b"lm:A,B,C,D\n")
    time.sleep(0.1)
    hm.ctrl.set_batch_intensities(a=51, b=51, c=51, d=51)

    # Set integration time
    integration_time_ms = 5.0
    hm.usb.set_integration(integration_time_ms)
    print(f"Integration time: {integration_time_ms} ms\n")

    # Define positions to test
    s_pwm = 71  # S position from refined sweep
    p_pwm = 5  # P position from refined sweep

    # Approach positions (to control direction)
    s_approach = 1  # Approach S from below
    p_approach = 100  # Approach P from above

    print("=" * 70)
    print("TEST PLAN - DIRECTIONAL APPROACH")
    print("=" * 70)
    print(f"S Position: PWM {s_pwm}")
    print(f"  Approach: Always from PWM {s_approach} (from below)")
    print(f"\nP Position: PWM {p_pwm}")
    print(f"  Approach: Always from PWM {p_approach} (from above)")
    print("\nTest sequence:")
    print("  1. Approach P from above → measure 10 times")
    print("  2. Approach S from below → measure 10 times")
    print("  3. Approach P from above → measure 10 times")
    print("  4. Approach S from below → measure 10 times")
    print("  5. Verify consistency with directional approach")
    print("=" * 70)
    print()

    input("Press Enter to start directional validation test...")
    print()

    results = []

    # Test cycle 1: P → S
    print("CYCLE 1: P → S (with directional approach)")
    print("-" * 70)

    print(
        f"\n[1/4] Approaching P position (PWM {p_pwm}) from above (PWM {p_approach})...",
    )
    p1_intensities = move_and_measure(hm, p_pwm, p_approach, num_samples=10)
    p1_mean = sum(p1_intensities) / len(p1_intensities)
    p1_std = (
        sum((x - p1_mean) ** 2 for x in p1_intensities) / len(p1_intensities)
    ) ** 0.5
    print(f"  Measurements: {[f'{x:.0f}' for x in p1_intensities]}")
    print(f"  Mean: {p1_mean:.0f} counts, Std: {p1_std:.1f}")
    results.append(("P1", p_pwm, p1_intensities, p1_mean, p1_std))

    print(
        f"\n[2/4] Approaching S position (PWM {s_pwm}) from below (PWM {s_approach})...",
    )
    s1_intensities = move_and_measure(hm, s_pwm, s_approach, num_samples=10)
    s1_mean = sum(s1_intensities) / len(s1_intensities)
    s1_std = (
        sum((x - s1_mean) ** 2 for x in s1_intensities) / len(s1_intensities)
    ) ** 0.5
    print(f"  Measurements: {[f'{x:.0f}' for x in s1_intensities]}")
    print(f"  Mean: {s1_mean:.0f} counts, Std: {s1_std:.1f}")
    results.append(("S1", s_pwm, s1_intensities, s1_mean, s1_std))

    # Test cycle 2: P → S (repeatability check)
    print("\n\nCYCLE 2: P → S (Repeatability Check with directional approach)")
    print("-" * 70)

    print(
        f"\n[3/4] Approaching P position (PWM {p_pwm}) from above (PWM {p_approach})...",
    )
    p2_intensities = move_and_measure(hm, p_pwm, p_approach, num_samples=10)
    p2_mean = sum(p2_intensities) / len(p2_intensities)
    p2_std = (
        sum((x - p2_mean) ** 2 for x in p2_intensities) / len(p2_intensities)
    ) ** 0.5
    print(f"  Measurements: {[f'{x:.0f}' for x in p2_intensities]}")
    print(f"  Mean: {p2_mean:.0f} counts, Std: {p2_std:.1f}")
    results.append(("P2", p_pwm, p2_intensities, p2_mean, p2_std))

    print(
        f"\n[4/4] Approaching S position (PWM {s_pwm}) from below (PWM {s_approach})...",
    )
    s2_intensities = move_and_measure(hm, s_pwm, s_approach, num_samples=10)
    s2_mean = sum(s2_intensities) / len(s2_intensities)
    s2_std = (
        sum((x - s2_mean) ** 2 for x in s2_intensities) / len(s2_intensities)
    ) ** 0.5
    print(f"  Measurements: {[f'{x:.0f}' for x in s2_intensities]}")
    print(f"  Mean: {s2_mean:.0f} counts, Std: {s2_std:.1f}")
    results.append(("S2", s_pwm, s2_intensities, s2_mean, s2_std))

    # Turn off LEDs
    hm.ctrl._ser.write(b"lx\n")

    # Analysis
    print("\n\n" + "=" * 70)
    print("VALIDATION RESULTS - DIRECTIONAL APPROACH")
    print("=" * 70)

    # Calculate overall means
    p_overall_mean = (p1_mean + p2_mean) / 2
    s_overall_mean = (s1_mean + s2_mean) / 2

    print(f"\nP Position (PWM {p_pwm}) - approached from ABOVE:")
    print(f"  Cycle 1 mean: {p1_mean:.0f} ± {p1_std:.1f} counts")
    print(f"  Cycle 2 mean: {p2_mean:.0f} ± {p2_std:.1f} counts")
    print(f"  Overall mean: {p_overall_mean:.0f} counts")
    print(
        f"  Repeatability: {abs(p1_mean - p2_mean):.0f} counts difference ({abs(p1_mean - p2_mean)/p_overall_mean*100:.2f}%)",
    )

    print(f"\nS Position (PWM {s_pwm}) - approached from BELOW:")
    print(f"  Cycle 1 mean: {s1_mean:.0f} ± {s1_std:.1f} counts")
    print(f"  Cycle 2 mean: {s2_mean:.0f} ± {s2_std:.1f} counts")
    print(f"  Overall mean: {s_overall_mean:.0f} counts")
    print(
        f"  Repeatability: {abs(s1_mean - s2_mean):.0f} counts difference ({abs(s1_mean - s2_mean)/s_overall_mean*100:.2f}%)",
    )

    # S/P Ratio
    intensity_ratio = (s_overall_mean / p_overall_mean - 1) * 100
    print(f"\n** S/P Intensity Ratio: {intensity_ratio:.1f}% increase **")

    # Validation checks
    print("\n" + "=" * 70)
    print("VALIDATION CHECKS")
    print("=" * 70)

    checks_passed = 0
    checks_total = 0

    # Check 1: S position is significantly higher than P
    checks_total += 1
    if s_overall_mean > p_overall_mean * 1.3:  # At least 30% higher
        print("✓ PASS: S position intensity is significantly higher than P")
        checks_passed += 1
    else:
        print("✗ FAIL: S position intensity is NOT significantly higher than P")

    # Check 2: P position repeatability with directional approach
    checks_total += 1
    p_repeatability = abs(p1_mean - p2_mean) / p_overall_mean * 100
    if p_repeatability < 2.0:  # Within 2% (tighter due to directional control)
        print(
            f"✓ PASS: P position is highly repeatable with directional approach (±{p_repeatability:.2f}%)",
        )
        checks_passed += 1
    else:
        print(
            f"⚠ WARN: P position repeatability is ±{p_repeatability:.2f}% (expected <2%)",
        )
        if p_repeatability < 5.0:
            checks_passed += 1
            print("  (Still acceptable, marked as pass)")

    # Check 3: S position repeatability with directional approach
    checks_total += 1
    s_repeatability = abs(s1_mean - s2_mean) / s_overall_mean * 100
    if s_repeatability < 2.0:  # Within 2% (tighter due to directional control)
        print(
            f"✓ PASS: S position is highly repeatable with directional approach (±{s_repeatability:.2f}%)",
        )
        checks_passed += 1
    else:
        print(
            f"⚠ WARN: S position repeatability is ±{s_repeatability:.2f}% (expected <2%)",
        )
        if s_repeatability < 5.0:
            checks_passed += 1
            print("  (Still acceptable, marked as pass)")

    # Check 4: S/P separation is clear
    checks_total += 1
    separation = s_overall_mean - p_overall_mean
    if separation > 3000:  # At least 3000 counts difference
        print(f"✓ PASS: Clear S/P separation ({separation:.0f} counts)")
        checks_passed += 1
    else:
        print(f"✗ FAIL: Insufficient S/P separation ({separation:.0f} counts)")

    # Check 5: Low noise (standard deviations)
    checks_total += 1
    avg_std = (p1_std + p2_std + s1_std + s2_std) / 4
    if avg_std < 100:  # Average std < 100 counts
        print(f"✓ PASS: Low measurement noise (avg std: {avg_std:.1f} counts)")
        checks_passed += 1
    else:
        print(f"✗ FAIL: High measurement noise (avg std: {avg_std:.1f} counts)")

    # Final verdict
    print("\n" + "=" * 70)
    print(f"FINAL VERDICT: {checks_passed}/{checks_total} checks passed")
    print("=" * 70)

    if checks_passed == checks_total:
        print("✓✓✓ VALIDATION SUCCESSFUL ✓✓✓")
        print("\nConfirmed positions (with directional approach):")
        print(
            f"  S = PWM {s_pwm} ({s_overall_mean:.0f} counts) - approach from PWM {s_approach}",
        )
        print(
            f"  P = PWM {p_pwm} ({p_overall_mean:.0f} counts) - approach from PWM {p_approach}",
        )
        print(
            "\n** IMPORTANT: Always use directional approach for consistent results! **",
        )
    elif checks_passed >= checks_total * 0.6:
        print("⚠ VALIDATION PARTIAL - Most checks passed")
        print("\nRecommended positions (with directional approach):")
        print(
            f"  S = PWM {s_pwm} ({s_overall_mean:.0f} counts) - approach from PWM {s_approach}",
        )
        print(
            f"  P = PWM {p_pwm} ({p_overall_mean:.0f} counts) - approach from PWM {p_approach}",
        )
        print(
            "\n** IMPORTANT: Always use directional approach for consistent results! **",
        )
    else:
        print("✗✗✗ VALIDATION FAILED ✗✗✗")
        print("\nPositions may need recalibration with different approach directions")

    print("\nDone!")


if __name__ == "__main__":
    main()
