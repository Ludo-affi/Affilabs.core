"""
Fast-Track Servo Polarizer Calibration Script (FT)

Validates stored calibration positions (P and S) against OEM baseline without full sweep.
Uses the same spectral analysis methods as the full calibration.

**REQUIRES FIRMWARE V1.9+** for multi-LED activation (lm:A,B,C,D command).
Earlier firmware versions do not support simultaneous multi-LED control.

IMPORTANT: Absolute intensity values may vary between detectors/sensors.
           This script compares RELATIVE metrics (ratio, CV%) against baseline.
           If your sensor has different absolute counts, adjust thresholds accordingly.

Usage:
    python calibrate_polarizer_ft.py --p-pwm 6 --s-pwm 69

    Or reads from polarizer_calibration_results.csv if it exists

Fast-track validation takes ~30 seconds vs ~60 seconds for full calibration.
Use this for routine checks when you have known-good P/S positions.
"""

import sys
from pathlib import Path
import time
import numpy as np
import argparse
import csv

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.hardware_manager import HardwareManager


def measure_with_spectral_analysis(hm, wavelengths, method='max'):
    """
    Measure intensity using spectral analysis.

    Args:
        method: 'max' (for S - mean top 20), 'min_spr' (for P in 610-680nm ±10)

    Returns:
        float: Intensity value
    """
    spectrum = hm.usb.read_intensity()

    if method == 'max':
        # S position: Mean of top 20 max points
        top_20_indices = np.argsort(spectrum)[-20:]
        return float(spectrum[top_20_indices].mean())

    elif method == 'min_spr':
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


def move_to_position(hm, target_pwm, settle_time=1.5):
    """Move to position and settle."""
    cmd = f"sv{target_pwm:03d}000\n"
    hm.ctrl._ser.write(cmd.encode())
    hm.ctrl._ser.readline()
    hm.ctrl._ser.write(b"ss\n")
    hm.ctrl._ser.readline()
    time.sleep(settle_time)


def validate_position(hm, wavelengths, pwm, method, approach_from, n_measurements=20):
    """
    Validate a single position with multiple measurements.

    Args:
        hm: HardwareManager instance
        wavelengths: Wavelength array
        pwm: PWM position to validate
        method: 'max' or 'min_spr'
        approach_from: PWM to approach from
        n_measurements: Number of measurements (default 20)

    Returns:
        dict with statistics
    """
    # Approach from direction
    move_to_position(hm, approach_from, settle_time=0.5)
    move_to_position(hm, pwm, settle_time=1.5)

    # Take measurements
    measurements = []
    for _ in range(n_measurements):
        intensity = measure_with_spectral_analysis(hm, wavelengths, method=method)
        measurements.append(intensity)
        time.sleep(0.05)

    measurements = np.array(measurements)
    mean_val = measurements.mean()
    std_val = measurements.std()
    cv = (std_val / mean_val) * 100
    min_val = measurements.min()
    max_val = measurements.max()

    return {
        'pwm': pwm,
        'mean': float(mean_val),
        'std': float(std_val),
        'cv_percent': float(cv),
        'min': float(min_val),
        'max': float(max_val),
        'n_measurements': n_measurements
    }


def quick_validation(hm, wavelengths, p_pwm, s_pwm, verbose=True):
    """
    Fast-track validation of stored P and S positions.

    NOTE: Absolute intensity values are detector-specific. Your sensor may show
          different count values than the OEM baseline (e.g., 5000 vs 3000 counts).
          The validation criteria focus on RELATIVE metrics:
          - S/P ratio (should be >1.5×, typically 2.5×)
          - Noise (CV% should be <2%, typically <0.5%)
          - Separation (S-P should be >50% of P value)

    Args:
        hm: HardwareManager instance
        wavelengths: Wavelength array
        p_pwm: P position PWM
        s_pwm: S position PWM
        verbose: Print detailed output

    Returns:
        dict with validation results and pass/fail status
    """
    if verbose:
        print("\n" + "="*70)
        print("FAST-TRACK SERVO POLARIZER CALIBRATION (FT)")
        print("="*70)
        print(f"Testing stored positions: P={p_pwm}, S={s_pwm}")
        print("20 measurements per position with spectral analysis")
        print("\nNOTE: Intensity values are detector-specific.")
        print("      Validation uses relative metrics (ratio, CV%, separation).\n")

    # Validate P position
    if verbose:
        print(f"Validating P position (PWM {p_pwm})...")
    p_results = validate_position(
        hm, wavelengths, p_pwm,
        method='min_spr',
        approach_from=255,
        n_measurements=20
    )
    if verbose:
        print(f"  Mean: {p_results['mean']:.1f} ± {p_results['std']:.1f} counts")
        print(f"  Range: {p_results['min']:.1f} - {p_results['max']:.1f} counts")
        print(f"  Noise: {p_results['cv_percent']:.2f}% CV")

    # Validate S position
    if verbose:
        print(f"\nValidating S position (PWM {s_pwm})...")
    s_results = validate_position(
        hm, wavelengths, s_pwm,
        method='max',
        approach_from=1,
        n_measurements=20
    )
    if verbose:
        print(f"  Mean: {s_results['mean']:.1f} ± {s_results['std']:.1f} counts")
        print(f"  Range: {s_results['min']:.1f} - {s_results['max']:.1f} counts")
        print(f"  Noise: {s_results['cv_percent']:.2f}% CV")

    # Calculate metrics
    ratio = s_results['mean'] / p_results['mean']
    separation = s_results['mean'] - p_results['mean']

    # Validation checks (same as full calibration)
    checks = {
        'ratio_good': ratio > 1.5,
        'p_stable': p_results['cv_percent'] < 2.0,
        's_stable': s_results['cv_percent'] < 2.0,
        'separation_good': separation > (p_results['mean'] * 0.5)
    }

    all_passed = all(checks.values())

    if verbose:
        print(f"\n" + "="*70)
        print("VALIDATION RESULTS")
        print("="*70)
        print(f"S/P Ratio: {ratio:.2f}× {'✓' if checks['ratio_good'] else '✗'} (need > 1.5×)")
        print(f"P Noise: {p_results['cv_percent']:.2f}% CV {'✓' if checks['p_stable'] else '✗'} (need < 2.0%)")
        print(f"S Noise: {s_results['cv_percent']:.2f}% CV {'✓' if checks['s_stable'] else '✗'} (need < 2.0%)")
        print(f"Separation: {separation:.0f} counts {'✓' if checks['separation_good'] else '✗'} (need > {p_results['mean']*0.5:.0f})")
        print(f"\nOverall: {'✓✓✓ PASS ✓✓✓' if all_passed else '✗✗✗ FAIL ✗✗✗'}")
        print("\nNOTE: Compare with OEM baseline for your sensor:")
        print("      - OEM (USB4000): P~5250 counts, S~13450 counts")
        print("      - Your values may differ - focus on ratio and CV%")
        print("="*70)

    return {
        'p_pwm': p_pwm,
        'p_results': p_results,
        's_pwm': s_pwm,
        's_results': s_results,
        'ratio': float(ratio),
        'separation': float(separation),
        'checks': checks,
        'passed': all_passed
    }


def load_stored_calibration(csv_path=None):
    """
    Load stored calibration from CSV file.

    Args:
        csv_path: Path to calibration results CSV (default: polarizer_calibration_results.csv)

    Returns:
        tuple: (p_pwm, s_pwm) or (None, None) if not found
    """
    if csv_path is None:
        csv_path = ROOT / "polarizer_calibration_results.csv"

    if not Path(csv_path).exists():
        return None, None

    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            results = {row['Parameter']: row['Value'] for row in reader}

        p_pwm = int(results.get('P PWM', 0))
        s_pwm = int(results.get('S PWM', 0))

        if p_pwm > 0 and s_pwm > 0:
            return p_pwm, s_pwm
    except:
        pass

    return None, None


def main():
    """Main fast-track calibration routine."""

    parser = argparse.ArgumentParser(
        description='Fast-track servo polarizer calibration (validates stored positions)'
    )
    parser.add_argument('--p-pwm', type=int, help='P position PWM (default: load from file)')
    parser.add_argument('--s-pwm', type=int, help='S position PWM (default: load from file)')
    parser.add_argument('--csv', type=str, help='Path to calibration results CSV')
    parser.add_argument('--quiet', action='store_true', help='Minimal output')

    args = parser.parse_args()

    # Load positions
    if args.p_pwm and args.s_pwm:
        p_pwm = args.p_pwm
        s_pwm = args.s_pwm
        source = "command line arguments"
    else:
        p_pwm, s_pwm = load_stored_calibration(args.csv)
        if p_pwm is None:
            print("ERROR: No stored calibration found")
            print("  Either provide --p-pwm and --s-pwm arguments")
            print("  Or ensure polarizer_calibration_results.csv exists")
            print("\n  For first-time setup, run full calibration:")
            print("    python calibrate_polarizer.py")
            sys.exit(1)
        source = args.csv if args.csv else "polarizer_calibration_results.csv"

    if not args.quiet:
        print(f"\n{'='*70}")
        print("FAST-TRACK CALIBRATION MODE")
        print(f"{'='*70}")
        print(f"Loaded positions from {source}")
        print(f"  P position: PWM {p_pwm}")
        print(f"  S position: PWM {s_pwm}")
        print("\nThis validates stored positions (~30s) vs full calibration (~60s)")
        print("For unknown/new hardware, use: python calibrate_polarizer.py")

    # Connect hardware
    hm = HardwareManager()

    try:
        if not args.quiet:
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

        if not args.quiet:
            print(f"Connected: {hm.ctrl.name}, {hm.usb.serial_number}\n")

        # Set LED intensities (all 4 LEDs at 20% = 51/255)
        if not args.quiet:
            print("Setting LEDs to 20% (51/255)...")
        hm.ctrl._ser.write(b"lm:A,B,C,D\n")
        time.sleep(0.1)
        hm.ctrl.set_batch_intensities(a=51, b=51, c=51, d=51)

        # Set integration time to 5ms
        if not args.quiet:
            print("Setting integration time to 5ms...")
        hm.usb.set_integration(5.0)
        wavelengths = hm.usb.wavelengths

        time.sleep(1.0)

        # Run validation
        results = quick_validation(hm, wavelengths, p_pwm, s_pwm, verbose=not args.quiet)

        # Save results
        output_path = ROOT / "polarizer_validation_results.csv"
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Parameter', 'Value'])
            writer.writerow(['Calibration Mode', 'Fast-Track (FT)'])
            writer.writerow(['Validation Date', time.strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow(['P PWM', results['p_pwm']])
            writer.writerow(['P Intensity', f"{results['p_results']['mean']:.1f}"])
            writer.writerow(['P Std', f"{results['p_results']['std']:.1f}"])
            writer.writerow(['P CV%', f"{results['p_results']['cv_percent']:.2f}"])
            writer.writerow(['S PWM', results['s_pwm']])
            writer.writerow(['S Intensity', f"{results['s_results']['mean']:.1f}"])
            writer.writerow(['S Std', f"{results['s_results']['std']:.1f}"])
            writer.writerow(['S CV%', f"{results['s_results']['cv_percent']:.2f}"])
            writer.writerow(['S/P Ratio', f"{results['ratio']:.2f}"])
            writer.writerow(['Separation', f"{results['separation']:.0f}"])
            writer.writerow(['Status', 'PASS' if results['passed'] else 'FAIL'])
            writer.writerow(['Note', 'Intensity values are detector-specific'])
            writer.writerow(['OEM Baseline', 'USB4000: P~5250, S~13450 counts'])

        if not args.quiet:
            print(f"\nValidation results saved to: {output_path}")
            print("\nREMINDER: Intensity values may differ from OEM baseline.")
            print("          This is normal for different sensors/detectors.")
            print("          Focus on relative metrics (ratio, CV%) for validation.")

        # Exit code
        sys.exit(0 if results['passed'] else 1)

    finally:
        # Cleanup
        if not args.quiet:
            print("\nCleaning up...")
        try:
            hm.ctrl._ser.write(b"lx\n")
        except:
            pass
        if not args.quiet:
            print("Done!")


if __name__ == "__main__":
    main()
