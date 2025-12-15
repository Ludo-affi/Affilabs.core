"""Sweep ±10 PWM positions around optimal S and P positions.
Tests PWM 1-15 for P (centered on 5) and PWM 61-81 for S (centered on 71).
Uses directional approach for consistency.

For S: Finds max point and takes mean of ±10 points around it
For P: Finds min point in 610-680nm range and takes mean of ±10 points around it
"""

import sys
import time
from pathlib import Path

import numpy as np

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.hardware_manager import HardwareManager


def calculate_intensity(spectrum, wavelengths, region_name):
    """Calculate intensity based on spectral analysis.

    For S: Find max point, take mean of ±10 points around it
    For P: Find min point in 610-680nm range, take mean of ±10 points around it

    Args:
        spectrum: Intensity array from spectrometer
        wavelengths: Wavelength array from spectrometer
        region_name: "P" or "S"

    Returns:
        intensity value (float)

    """
    if region_name == "S":
        # Find maximum point across entire spectrum
        max_idx = np.argmax(spectrum)
        # Take mean of ±10 points around max
        start_idx = max(0, max_idx - 10)
        end_idx = min(len(spectrum), max_idx + 11)
        intensity = spectrum[start_idx:end_idx].mean()
        return intensity

    if region_name == "P":
        # Find wavelength range 610-680 nm
        mask = (wavelengths >= 610) & (wavelengths <= 680)
        if not np.any(mask):
            # Fallback if range not available
            return spectrum.min()

        # Find minimum point within this range
        spectrum_range = spectrum[mask]
        min_idx_in_range = np.argmin(spectrum_range)

        # Get absolute index in full spectrum
        indices = np.where(mask)[0]
        min_idx = indices[min_idx_in_range]

        # Take mean of ±10 points around min
        start_idx = max(0, min_idx - 10)
        end_idx = min(len(spectrum), min_idx + 11)
        intensity = spectrum[start_idx:end_idx].mean()
        return intensity

    return spectrum.max()  # Fallback


def sweep_position(
    hm,
    center_pwm,
    approach_pwm,
    region_name,
    wavelengths,
    num_scans=10,
):
    """Sweep ±10 PWM around center position with directional approach.

    Args:
        hm: HardwareManager instance
        center_pwm: Center PWM position
        approach_pwm: PWM to approach from (for consistency)
        region_name: "P" or "S"
        wavelengths: Wavelength array from spectrometer
        num_scans: Number of scans to accumulate per position (default: 10)

    """
    print(f"\n{'='*70}")
    print(f"SWEEPING {region_name} REGION: PWM {center_pwm-10} to {center_pwm+10}")
    print(f"Approach direction: from PWM {approach_pwm}")
    if region_name == "S":
        print("Method: Max point + mean of ±10 points")
    else:
        print("Method: Min point in 610-680nm + mean of ±10 points")
    print(f"Scans per position: {num_scans}")
    print(f"{'='*70}\n")

    results = []

    # Sweep from center-10 to center+10
    for pwm in range(center_pwm - 10, center_pwm + 11):
        # Ensure PWM is in valid range [1, 255]
        if pwm < 1 or pwm > 255:
            continue

        # Always approach from the same direction for consistency
        print(
            f"[PWM {pwm:3d}] Approaching from PWM {approach_pwm}...",
            end=" ",
            flush=True,
        )

        # Step 1: Move to approach position
        cmd = f"sv{approach_pwm:03d}000\n"
        hm.ctrl._ser.write(cmd.encode())
        resp = hm.ctrl._ser.readline().decode().strip()
        hm.ctrl._ser.write(b"ss\n")
        resp = hm.ctrl._ser.readline().decode().strip()
        time.sleep(0.5)  # Short settle

        # Step 2: Move to target position
        cmd = f"sv{pwm:03d}000\n"
        hm.ctrl._ser.write(cmd.encode())
        resp = hm.ctrl._ser.readline().decode().strip()
        hm.ctrl._ser.write(b"ss\n")
        resp = hm.ctrl._ser.readline().decode().strip()
        time.sleep(1.5)  # Full settle

        # Accumulate multiple measurements
        intensities = []
        for scan in range(num_scans):
            spectrum = hm.usb.read_intensity()
            intensity = calculate_intensity(spectrum, wavelengths, region_name)
            intensities.append(intensity)
            time.sleep(0.05)  # Small delay between scans

        # Calculate statistics
        intensities_array = np.array(intensities)
        mean_intensity = intensities_array.mean()
        std_intensity = intensities_array.std()

        results.append(
            {
                "pwm": pwm,
                "intensity": mean_intensity,
                "std": std_intensity,
                "measurements": intensities,
            },
        )

        print(f"{mean_intensity:7.1f} ± {std_intensity:5.1f} counts")

    return results


def main():
    print("\n" + "=" * 70)
    print("OPTIMAL POSITION SWEEP VALIDATION")
    print("Testing ±10 PWM around P (PWM 5) and S (PWM 71)")
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

        print(f"Connected: {hm.ctrl.name}, {hm.usb.serial_number}\n")

        # Set LED intensities (all 4 LEDs at 20% = 51/255)
        print("Setting LEDs to 20% (51/255)...")
        hm.ctrl._ser.write(b"lm:A,B,C,D\n")
        time.sleep(0.1)
        hm.ctrl.set_batch_intensities(a=51, b=51, c=51, d=51)

        # Set integration time to 5ms
        print("Setting integration time to 5ms...")
        hm.usb.set_integration(5.0)

        # Get wavelengths for spectral analysis
        print("Reading wavelength calibration...")
        wavelengths = hm.usb.wavelengths
        print(
            f"Wavelength range: {wavelengths.min():.1f} - {wavelengths.max():.1f} nm\n",
        )

        time.sleep(1.0)

        # Sweep P region: PWM 1-15 (center at 5, approach from above)
        p_results = sweep_position(
            hm,
            center_pwm=5,
            approach_pwm=100,
            region_name="P",
            wavelengths=wavelengths,
        )

        # Sweep S region: PWM 61-81 (center at 71, approach from below)
        s_results = sweep_position(
            hm,
            center_pwm=71,
            approach_pwm=1,
            region_name="S",
            wavelengths=wavelengths,
        )

        # Print summary
        print("\n" + "=" * 70)
        print("SWEEP SUMMARY WITH NOISE ANALYSIS")
        print("=" * 70)

        # Analyze P region
        print("\n" + "=" * 70)
        print("P REGION (PWM 1-15) - NOISE ANALYSIS:")
        print("=" * 70)
        p_min = min(p_results, key=lambda x: x["intensity"])
        p_max = max(p_results, key=lambda x: x["intensity"])

        # Find optimal stable range (low noise, near minimum)
        # Define "good" positions as those within 1% of minimum and with low std
        p_threshold = p_min["intensity"] * 1.01
        p_good_positions = [r for r in p_results if r["intensity"] <= p_threshold]

        # Sort by noise (std) to find most stable
        p_good_positions.sort(key=lambda x: x["std"])

        print(
            f"  Minimum intensity: PWM {p_min['pwm']} = {p_min['intensity']:.1f} ± {p_min['std']:.1f} counts",
        )
        print(
            f"  Maximum intensity: PWM {p_max['pwm']} = {p_max['intensity']:.1f} ± {p_max['std']:.1f} counts",
        )
        print(f"  Range: {p_max['intensity'] - p_min['intensity']:.1f} counts")

        print(
            f"\n  Positions within 1% of minimum ({len(p_good_positions)} positions):",
        )
        for r in p_good_positions[:5]:  # Show top 5 most stable
            print(
                f"    PWM {r['pwm']:2d}: {r['intensity']:7.1f} ± {r['std']:5.1f} counts (CV: {r['std']/r['intensity']*100:.2f}%)",
            )

        # Find middle PWM in good range
        if len(p_good_positions) > 0:
            p_pwm_values = [r["pwm"] for r in p_good_positions]
            p_optimal_pwm = int(np.median(p_pwm_values))
            p_optimal = next(r for r in p_results if r["pwm"] == p_optimal_pwm)
            print(
                f"\n  → OPTIMAL P POSITION: PWM {p_optimal_pwm} (middle of stable range)",
            )
            print(
                f"    Intensity: {p_optimal['intensity']:.1f} ± {p_optimal['std']:.1f} counts",
            )
            print(
                f"    Noise: {p_optimal['std']:.1f} counts (CV: {p_optimal['std']/p_optimal['intensity']*100:.2f}%)",
            )

        # Analyze S region
        print("\n" + "=" * 70)
        print("S REGION (PWM 61-81) - NOISE ANALYSIS:")
        print("=" * 70)
        s_min = min(s_results, key=lambda x: x["intensity"])
        s_max = max(s_results, key=lambda x: x["intensity"])

        # Find optimal stable range (high intensity, low noise)
        # Define "good" positions as those within 1% of maximum and with low std
        s_threshold = s_max["intensity"] * 0.99
        s_good_positions = [r for r in s_results if r["intensity"] >= s_threshold]

        # Sort by noise (std) to find most stable
        s_good_positions.sort(key=lambda x: x["std"])

        print(
            f"  Minimum intensity: PWM {s_min['pwm']} = {s_min['intensity']:.1f} ± {s_min['std']:.1f} counts",
        )
        print(
            f"  Maximum intensity: PWM {s_max['pwm']} = {s_max['intensity']:.1f} ± {s_max['std']:.1f} counts",
        )
        print(f"  Range: {s_max['intensity'] - s_min['intensity']:.1f} counts")

        print(
            f"\n  Positions within 1% of maximum ({len(s_good_positions)} positions):",
        )
        for r in s_good_positions[:5]:  # Show top 5 most stable
            print(
                f"    PWM {r['pwm']:2d}: {r['intensity']:7.1f} ± {r['std']:5.1f} counts (CV: {r['std']/r['intensity']*100:.2f}%)",
            )

        # Find middle PWM in good range
        if len(s_good_positions) > 0:
            s_pwm_values = [r["pwm"] for r in s_good_positions]
            s_optimal_pwm = int(np.median(s_pwm_values))
            s_optimal = next(r for r in s_results if r["pwm"] == s_optimal_pwm)
            print(
                f"\n  → OPTIMAL S POSITION: PWM {s_optimal_pwm} (middle of stable range)",
            )
            print(
                f"    Intensity: {s_optimal['intensity']:.1f} ± {s_optimal['std']:.1f} counts",
            )
            print(
                f"    Noise: {s_optimal['std']:.1f} counts (CV: {s_optimal['std']/s_optimal['intensity']*100:.2f}%)",
            )

        # Final summary
        print("\n" + "=" * 70)
        print("FINAL OPTIMAL POSITIONS:")
        print("=" * 70)
        print(
            f"  P: PWM {p_optimal_pwm} ({p_optimal['intensity']:.1f} ± {p_optimal['std']:.1f} counts)",
        )
        print(
            f"  S: PWM {s_optimal_pwm} ({s_optimal['intensity']:.1f} ± {s_optimal['std']:.1f} counts)",
        )
        print(f"  S/P Ratio: {s_optimal['intensity'] / p_optimal['intensity']:.2f}x")
        print(
            f"  Intensity increase: {(s_optimal['intensity'] / p_optimal['intensity'] - 1) * 100:.1f}%",
        )
        print(
            f"  Separation: {s_optimal['intensity'] - p_optimal['intensity']:.1f} counts",
        )
        print("=" * 70)

        # Save results to CSV with noise data
        csv_path = ROOT / "optimal_position_sweep.csv"
        with open(csv_path, "w") as f:
            f.write("region,pwm,intensity,std,cv_percent\n")
            for r in p_results:
                cv = r["std"] / r["intensity"] * 100
                f.write(f"P,{r['pwm']},{r['intensity']:.2f},{r['std']:.2f},{cv:.3f}\n")
            for r in s_results:
                cv = r["std"] / r["intensity"] * 100
                f.write(f"S,{r['pwm']},{r['intensity']:.2f},{r['std']:.2f},{cv:.3f}\n")

        print(f"\nResults saved to: {csv_path}")

        print("\n" + "=" * 70)
        print("SWEEP COMPLETE")
        print("=" * 70)

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
