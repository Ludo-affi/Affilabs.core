"""
Universal Polarizer Calibration with Automatic Type Detection.

Stage 1: 5-position bidirectional sweep (1->255->1) measuring mean of top 20 max points
Stage 2: Detect polarizer type (CIRCULAR vs BARREL)
Stage 3: Refine using ±10 PWM sweep around detected S and P regions

**REQUIRES FIRMWARE V1.9+** for multi-LED activation (lm:A,B,C,D command).
Earlier firmware versions do not support simultaneous multi-LED control.

Author: ezControl-AI System
Date: December 7, 2025
"""

import sys
from pathlib import Path
import time
import numpy as np
import csv

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.hardware_manager import HardwareManager


def measure_signal(hm):
    """
    Measure signal using mean of top 20 max points.

    Returns:
        float: Mean intensity of top 20 points
    """
    spectrum = hm.usb.read_intensity()
    top_20_indices = np.argsort(spectrum)[-20:]
    return float(spectrum[top_20_indices].mean())


def measure_with_spectral_analysis(hm, wavelengths, method='max'):
    """
    Measure intensity using spectral analysis for refinement.

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


def stage1_bidirectional_sweep(hm):
    """
    Stage 1: 5-position bidirectional sweep.

    Sweep: 1 -> 65 -> 128 -> 191 -> 255 -> 191 -> 128 -> 65 -> 1
    Measure signal (mean top 20) at each position.

    Returns:
        dict with forward and backward sweep data
    """
    print("\n" + "="*70)
    print("STAGE 1: BIDIRECTIONAL 5-POSITION SWEEP")
    print("="*70)
    print("Measuring mean of top 20 max points at each position\n")

    # 5 positions covering full range
    positions = [1, 65, 128, 191, 255]

    forward_data = []
    backward_data = []

    # Forward sweep
    print("Forward sweep: 1 -> 255")
    for pwm in positions:
        move_to_position(hm, pwm)
        signal = measure_signal(hm)
        forward_data.append({'pwm': pwm, 'intensity': signal})
        print(f"  PWM {pwm:3d}: {signal:7.1f} counts")

    # Backward sweep
    print("\nBackward sweep: 255 -> 1")
    for pwm in reversed(positions):
        move_to_position(hm, pwm)
        signal = measure_signal(hm)
        backward_data.append({'pwm': pwm, 'intensity': signal})
        print(f"  PWM {pwm:3d}: {signal:7.1f} counts")

    return {
        'forward': forward_data,
        'backward': backward_data,
        'positions': positions
    }


def detect_polarizer_type(sweep_data):
    """
    Stage 2: Detect polarizer type from sweep data.

    CIRCULAR: All positions above dark threshold (3000 counts)
    BARREL: Some positions at/below dark threshold

    Returns:
        tuple: (type_string, info_dict with p_region, s_region)
    """
    print("\n" + "="*70)
    print("STAGE 2: POLARIZER TYPE DETECTION")
    print("="*70)

    # Combine forward and backward for analysis
    all_data = sweep_data['forward'] + sweep_data['backward']
    intensities = np.array([d['intensity'] for d in all_data])

    # Dark threshold for this detector (Ocean Optics USB4000)
    DARK_THRESHOLD = 3000

    # Check if all positions are above dark threshold
    n_above_dark = np.sum(intensities > DARK_THRESHOLD)
    n_total = len(intensities)

    if n_above_dark == n_total:
        polarizer_type = 'CIRCULAR'
        print(f"Polarizer Type: CIRCULAR")
        print(f"  All {n_total} positions above dark threshold ({DARK_THRESHOLD} counts)")
        print(f"  Min signal: {intensities.min():.1f} counts")
        print(f"  Max signal: {intensities.max():.1f} counts")

        # Find P and S regions from forward sweep
        fwd_intensities = np.array([d['intensity'] for d in sweep_data['forward']])
        fwd_positions = np.array([d['pwm'] for d in sweep_data['forward']])

        # P region: around minimum
        p_idx = np.argmin(fwd_intensities)
        p_pwm = int(fwd_positions[p_idx])

        # S region: around maximum
        s_idx = np.argmax(fwd_intensities)
        s_pwm = int(fwd_positions[s_idx])

        print(f"  P region detected near PWM {p_pwm}")
        print(f"  S region detected near PWM {s_pwm}")

        info = {
            'p_region_center': p_pwm,
            's_region_center': s_pwm,
            'all_above_dark': True
        }

    else:
        polarizer_type = 'BARREL'
        print(f"Polarizer Type: BARREL")
        print(f"  {n_total - n_above_dark} positions at/below dark threshold")
        print(f"  Min signal: {intensities.min():.1f} counts")
        print(f"  Max signal: {intensities.max():.1f} counts")

        # For barrel: Find brightest position for S, darkest for P
        fwd_intensities = np.array([d['intensity'] for d in sweep_data['forward']])
        fwd_positions = np.array([d['pwm'] for d in sweep_data['forward']])

        s_idx = np.argmax(fwd_intensities)
        s_pwm = int(fwd_positions[s_idx])

        p_idx = np.argmin(fwd_intensities)
        p_pwm = int(fwd_positions[p_idx])

        print(f"  S region (brightest window) near PWM {s_pwm}")
        print(f"  P region (darkest window) near PWM {p_pwm}")

        info = {
            'p_region_center': p_pwm,
            's_region_center': s_pwm,
            'all_above_dark': False
        }

    return polarizer_type, info


def stage3_refine_positions(hm, wavelengths, p_center, s_center):
    """
    Stage 3: Refine positions using ±10 PWM sweep (like validate_optimal_positions_sweep.py).

    Uses 10 scans per position with spectral analysis.

    Returns:
        dict with optimal P and S positions and statistics
    """
    print("\n" + "="*70)
    print("STAGE 3: REFINING POSITIONS (±10 PWM SWEEP)")
    print("="*70)
    print(f"P region: PWM {max(1, p_center-10)} to {min(255, p_center+10)}")
    print(f"S region: PWM {max(1, s_center-10)} to {min(255, s_center+10)}")
    print("10 scans per position with spectral analysis\n")

    # === Refine P region ===
    print("Refining P region (approaching from high)...")
    p_results = []

    for pwm in range(max(1, p_center-10), min(256, p_center+11)):
        # Approach from high (PWM 255)
        move_to_position(hm, 255, settle_time=0.5)
        move_to_position(hm, pwm, settle_time=1.5)

        # 10 scans
        measurements = []
        for _ in range(10):
            intensity = measure_with_spectral_analysis(hm, wavelengths, method='min_spr')
            measurements.append(intensity)
            time.sleep(0.05)

        mean_val = np.mean(measurements)
        std_val = np.std(measurements)
        cv = (std_val / mean_val) * 100

        p_results.append({
            'pwm': pwm,
            'mean': mean_val,
            'std': std_val,
            'cv_percent': cv
        })

        print(f"  PWM {pwm:3d}: {mean_val:7.1f} ± {std_val:5.1f} (CV: {cv:.2f}%)")

    # Find optimal P (minimum + stable range)
    p_min = min(p_results, key=lambda x: x['mean'])
    p_stable = [p for p in p_results if p['mean'] <= p_min['mean'] * 1.01]
    p_optimal = int(np.median([p['pwm'] for p in p_stable]))

    print(f"\nP stable range: {len(p_stable)} positions (PWM {min(p['pwm'] for p in p_stable)}-{max(p['pwm'] for p in p_stable)})")
    print(f"Selected P: PWM {p_optimal}")

    # === Refine S region ===
    print("\nRefining S region (approaching from low)...")
    s_results = []

    for pwm in range(max(1, s_center-10), min(256, s_center+11)):
        # Approach from low (PWM 1)
        move_to_position(hm, 1, settle_time=0.5)
        move_to_position(hm, pwm, settle_time=1.5)

        # 10 scans
        measurements = []
        for _ in range(10):
            intensity = measure_with_spectral_analysis(hm, wavelengths, method='max')
            measurements.append(intensity)
            time.sleep(0.05)

        mean_val = np.mean(measurements)
        std_val = np.std(measurements)
        cv = (std_val / mean_val) * 100

        s_results.append({
            'pwm': pwm,
            'mean': mean_val,
            'std': std_val,
            'cv_percent': cv
        })

        print(f"  PWM {pwm:3d}: {mean_val:7.1f} ± {std_val:5.1f} (CV: {cv:.2f}%)")

    # Find optimal S (maximum + stable range)
    s_max = max(s_results, key=lambda x: x['mean'])
    s_stable = [s for s in s_results if s['mean'] >= s_max['mean'] * 0.99]
    s_optimal = int(np.median([s['pwm'] for s in s_stable]))

    print(f"\nS stable range: {len(s_stable)} positions (PWM {min(s['pwm'] for s in s_stable)}-{max(s['pwm'] for s in s_stable)})")
    print(f"Selected S: PWM {s_optimal}")

    # Get final stats at optimal positions
    p_final = next(p for p in p_results if p['pwm'] == p_optimal)
    s_final = next(s for s in s_results if s['pwm'] == s_optimal)

    return {
        'p_pwm': p_optimal,
        'p_intensity': p_final['mean'],
        'p_std': p_final['std'],
        'p_cv_percent': p_final['cv_percent'],
        'p_stable_range': (min(p['pwm'] for p in p_stable), max(p['pwm'] for p in p_stable)),
        's_pwm': s_optimal,
        's_intensity': s_final['mean'],
        's_std': s_final['std'],
        's_cv_percent': s_final['cv_percent'],
        's_stable_range': (min(s['pwm'] for s in s_stable), max(s['pwm'] for s in s_stable)),
        'p_all_results': p_results,
        's_all_results': s_results
    }


def main():
    """Main calibration routine."""

    print("\n" + "="*70)
    print("UNIVERSAL POLARIZER CALIBRATION")
    print("="*70)

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

        print(f"Connected: {hm.ctrl.name}, {hm.usb.serial_number}\n")

        # Set LED intensities (all 4 LEDs at 20% = 51/255)
        print("Setting LEDs to 20% (51/255)...")
        hm.ctrl._ser.write(b"lm:A,B,C,D\n")
        time.sleep(0.1)
        hm.ctrl.set_batch_intensities(a=51, b=51, c=51, d=51)

        # Set integration time to 5ms
        print("Setting integration time to 5ms...")
        hm.usb.set_integration(5.0)
        wavelengths = hm.usb.wavelengths

        time.sleep(1.0)

        # === STAGE 1: Bidirectional sweep ===
        sweep_data = stage1_bidirectional_sweep(hm)

        # === STAGE 2: Detect polarizer type ===
        polarizer_type, type_info = detect_polarizer_type(sweep_data)

        # === STAGE 3: Refine positions ===
        refinement = stage3_refine_positions(
            hm,
            wavelengths,
            type_info['p_region_center'],
            type_info['s_region_center']
        )

        # === FINAL SUMMARY ===
        print("\n" + "="*70)
        print("CALIBRATION COMPLETE")
        print("="*70)
        print(f"Polarizer Type: {polarizer_type}")
        print(f"\nP Position: PWM {refinement['p_pwm']}")
        print(f"  Stable range: PWM {refinement['p_stable_range'][0]}-{refinement['p_stable_range'][1]}")
        print(f"  Intensity: {refinement['p_intensity']:.1f} ± {refinement['p_std']:.1f} counts")
        print(f"  Noise: {refinement['p_cv_percent']:.2f}% CV")
        print(f"\nS Position: PWM {refinement['s_pwm']}")
        print(f"  Stable range: PWM {refinement['s_stable_range'][0]}-{refinement['s_stable_range'][1]}")
        print(f"  Intensity: {refinement['s_intensity']:.1f} ± {refinement['s_std']:.1f} counts")
        print(f"  Noise: {refinement['s_cv_percent']:.2f}% CV")

        ratio = refinement['s_intensity'] / refinement['p_intensity']
        separation = refinement['s_intensity'] - refinement['p_intensity']
        print(f"\nS/P Ratio: {ratio:.2f}×")
        print(f"Separation: {separation:.0f} counts")
        print("="*70)

        # Save results to CSV
        output_path = ROOT / "polarizer_calibration_results.csv"
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Parameter', 'Value'])
            writer.writerow(['Polarizer Type', polarizer_type])
            writer.writerow(['P PWM', refinement['p_pwm']])
            writer.writerow(['P Stable Range', f"{refinement['p_stable_range'][0]}-{refinement['p_stable_range'][1]}"])
            writer.writerow(['P Intensity', f"{refinement['p_intensity']:.1f}"])
            writer.writerow(['P Std', f"{refinement['p_std']:.1f}"])
            writer.writerow(['P CV%', f"{refinement['p_cv_percent']:.2f}"])
            writer.writerow(['S PWM', refinement['s_pwm']])
            writer.writerow(['S Stable Range', f"{refinement['s_stable_range'][0]}-{refinement['s_stable_range'][1]}"])
            writer.writerow(['S Intensity', f"{refinement['s_intensity']:.1f}"])
            writer.writerow(['S Std', f"{refinement['s_std']:.1f}"])
            writer.writerow(['S CV%', f"{refinement['s_cv_percent']:.2f}"])
            writer.writerow(['S/P Ratio', f"{ratio:.2f}"])
            writer.writerow(['Separation', f"{separation:.0f}"])

        print(f"\nResults saved to: {output_path}")

        # Save detailed sweep data
        detail_path = ROOT / "polarizer_calibration_detail.csv"
        with open(detail_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Region', 'PWM', 'Mean', 'Std', 'CV%'])
            for p in refinement['p_all_results']:
                writer.writerow(['P', p['pwm'], f"{p['mean']:.2f}", f"{p['std']:.2f}", f"{p['cv_percent']:.2f}"])
            for s in refinement['s_all_results']:
                writer.writerow(['S', s['pwm'], f"{s['mean']:.2f}", f"{s['std']:.2f}", f"{s['cv_percent']:.2f}"])

        print(f"Detailed data saved to: {detail_path}")

    finally:
        # Cleanup
        print("\nCleaning up...")
        try:
            hm.ctrl._ser.write(b"lx\n")
        except:
            pass
        print("Done!")


if __name__ == "__main__":
    main()
