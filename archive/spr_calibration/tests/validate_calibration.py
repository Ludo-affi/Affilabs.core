"""VALIDATE CALIBRATION: Measure transmission spectra at optimal settings.

This script:
1. Loads bilinear models
2. Calculates optimal LED intensities for fixed integration time
3. Measures S-pol and P-pol spectra for all 4 LEDs
4. Applies dark correction
5. Calculates transmission (P/S ratio) per wavelength
6. Plots results to verify calibration accuracy

Target: 50,000 counts (76% detector) for validation
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Add parent directory to path for hardware imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from src.hardware.controller_adapter import wrap_existing_controller
from src.hardware.optimized_led_controller import create_optimized_controller
from src.hardware.spectrometer_adapter import wrap_existing_spectrometer

# ==============================================================================
# Configuration
# ==============================================================================

TARGET_COUNTS = 50000  # Target detector counts for validation
INTEGRATION_TIME_S = 50  # ms for S-pol (from analysis: 50ms works for S)
INTEGRATION_TIME_P = 100  # ms for P-pol (from analysis: 100ms works for P)

DETECTOR_MAX = 65535
SCANS_TO_AVERAGE = 3

LEDS = ["A", "B", "C", "D"]

# ==============================================================================
# Load Bilinear Models
# ==============================================================================


def predict_bilinear(model, intensity, time):
    """Predict counts using bilinear model."""
    a = model["a"]
    b = model["b"]
    c = model["c"]
    d = model["d"]
    return (a * time + b) * intensity + (c * time + d)


def solve_for_intensity(model, target_counts, time):
    """Solve for intensity given target counts and integration time.

    counts = (a*t + b)*I + (c*t + d)
    I = (counts - c*t - d) / (a*t + b)
    """
    a = model["a"]
    b = model["b"]
    c = model["c"]
    d = model["d"]

    numerator = target_counts - (c * time + d)
    denominator = a * time + b

    if denominator == 0:
        return None

    intensity = numerator / denominator

    # Clip to valid range
    intensity = np.clip(intensity, 0, 255)

    return intensity


def load_optimal_settings(calib_file: Path):
    """Load bilinear models and calculate optimal intensities."""
    with open(calib_file) as f:
        data = json.load(f)

    # Load dark current
    detector_serial = data.get("detector_serial", "unknown")
    dark_rate = data["dark"]["rate"]
    dark_offset = data["dark"]["offset"]

    # Calculate optimal intensities for each LED
    optimal_settings = {
        "S": {"time": INTEGRATION_TIME_S, "leds": {}},
        "P": {"time": INTEGRATION_TIME_P, "leds": {}},
        "dark": {"rate": dark_rate, "offset": dark_offset},
        "detector_serial": detector_serial,
    }

    print("\n" + "=" * 80)
    print("CALCULATING OPTIMAL LED INTENSITIES")
    print("=" * 80)
    print(
        f"Target counts: {TARGET_COUNTS:,} ({TARGET_COUNTS/DETECTOR_MAX*100:.1f}% detector)",
    )
    print(f"S-pol integration time: {INTEGRATION_TIME_S}ms")
    print(f"P-pol integration time: {INTEGRATION_TIME_P}ms")
    print("=" * 80)

    for pol in ["S", "P"]:
        time_ms = INTEGRATION_TIME_S if pol == "S" else INTEGRATION_TIME_P
        print(f"\n{pol}-Polarization @ {time_ms}ms:")

        for led in LEDS:
            led_key = led

            if "model" not in data[pol][led_key]:
                print(f"  LED_{led}: No model")
                continue

            model = data[pol][led_key]["model"]

            # Solve for intensity
            intensity = solve_for_intensity(model, TARGET_COUNTS, time_ms)

            if intensity is None:
                print(f"  LED_{led}: Cannot calculate (model error)")
                continue

            # Predict actual counts
            predicted_counts = predict_bilinear(model, intensity, time_ms)

            # Check if valid
            is_valid = bool(0 <= intensity <= 255)  # Convert to native Python bool
            status = "✓" if is_valid else "✗"

            optimal_settings[pol]["leds"][f"LED_{led}"] = {
                "intensity": int(np.round(intensity)),
                "predicted_counts": float(
                    predicted_counts,
                ),  # Convert to native Python float
                "valid": is_valid,
            }

            print(
                f"  LED_{led}: I={intensity:5.1f} → {predicted_counts:6.0f} counts {status}",
            )

    print("\n" + "=" * 80)

    return optimal_settings


# ==============================================================================
# Measure Spectra
# ==============================================================================


def measure_spectrum(
    spectrometer,
    opt_controller,
    controller_hw,
    led_name,
    intensity,
    time_ms,
    polarization,
    scans=3,
):
    """Measure spectrum at specified settings."""
    # Map LED name to channel
    led_map = {"LED_A": "a", "LED_B": "b", "LED_C": "c", "LED_D": "d"}
    channel = led_map[led_name]

    # Set servo position
    if polarization == "S":
        servo_pos = 72  # S-pol position
    else:
        servo_pos = 8  # P-pol position

    cmd = f"sv{servo_pos:03d}{servo_pos:03d}\n"
    controller_hw._ser.write(cmd.encode())
    time.sleep(0.05)
    controller_hw._ser.write(b"ss\n")
    time.sleep(0.5)  # Wait for servo to settle

    # Set spectrometer integration time
    spectrometer.set_integration_time(time_ms)

    # Turn on LED
    opt_controller.turn_off_all_leds()
    opt_controller.configure_led_atomic(channel, intensity)
    time.sleep(0.1)  # Wait for LED to stabilize

    # Acquire spectra
    spectra = []

    for scan in range(scans):
        counts = spectrometer.read_spectrum()  # Returns 1D counts array
        spectra.append(counts)
        time.sleep(0.05)

    # Turn off LED
    opt_controller.turn_off_all_leds()

    # Average spectra
    avg_spectrum = np.mean(spectra, axis=0)

    # Calculate peak counts
    peak_counts = np.max(avg_spectrum)

    # Get wavelengths
    wavelengths = spectrometer.get_wavelengths()

    return wavelengths, avg_spectrum, peak_counts


def measure_all_spectra(optimal_settings):
    """Measure S-pol, P-pol, and dark spectra for all LEDs."""
    print("\n" + "=" * 80)
    print("MEASURING VALIDATION SPECTRA")
    print("=" * 80)

    # Initialize hardware - copied from measure.py
    print("\nInitializing hardware...")

    from src.utils.controller import PicoP4SPR
    from src.utils.usb4000_wrapper import USB4000

    controller_hw = PicoP4SPR()
    spec_hw = USB4000()

    controller = wrap_existing_controller(controller_hw)
    spectrometer = wrap_existing_spectrometer(spec_hw)

    if not controller.connect():
        print("[ERROR] Could not connect to LED controller!")
        return None

    if not spectrometer.connect():
        print("[ERROR] Could not connect to spectrometer!")
        controller.disconnect()
        return None

    print("[OK] Connected to hardware")

    # Create optimized LED controller
    opt_controller = create_optimized_controller(controller_hw)

    if opt_controller.enter_calibration_mode():
        print("[OK] Calibration mode enabled")

    # Measure dark spectrum (LEDs off, shorter integration time)
    print("\n[1/3] Measuring dark spectrum...")
    dark_time_s = optimal_settings["S"]["time"]
    dark_time_p = optimal_settings["P"]["time"]

    spectrometer.set_integration_time(dark_time_s)
    opt_controller.turn_off_all_leds()
    time.sleep(0.2)

    # Get wavelengths once
    wavelengths = spectrometer.get_wavelengths()

    dark_spectra_s = []
    for _ in range(SCANS_TO_AVERAGE):
        spectrum = spectrometer.read_spectrum()  # Returns 1D counts array
        dark_spectra_s.append(spectrum)
        time.sleep(0.05)
    dark_spectrum_s = np.mean(dark_spectra_s, axis=0)

    spectrometer.set_integration_time(dark_time_p)
    dark_spectra_p = []
    for _ in range(SCANS_TO_AVERAGE):
        spectrum = spectrometer.read_spectrum()  # Returns 1D counts array
        dark_spectra_p.append(spectrum)
        time.sleep(0.05)
    dark_spectrum_p = np.mean(dark_spectra_p, axis=0)

    print(f"  Dark S ({dark_time_s}ms): Peak={np.max(dark_spectrum_s):.0f} counts")
    print(f"  Dark P ({dark_time_p}ms): Peak={np.max(dark_spectrum_p):.0f} counts")

    results = {
        "wavelengths": wavelengths,
        "dark": {"S": dark_spectrum_s, "P": dark_spectrum_p},
        "S": {},
        "P": {},
        "timestamp": datetime.now().isoformat(),
        "settings": optimal_settings,
    }

    # Measure S-pol spectra
    print("\n[2/3] Measuring S-polarization spectra...")
    time_s = optimal_settings["S"]["time"]

    for led in LEDS:
        led_key = f"LED_{led}"

        if led_key not in optimal_settings["S"]["leds"]:
            print(f"  {led_key}: Skipped (no settings)")
            continue

        settings = optimal_settings["S"]["leds"][led_key]
        intensity = settings["intensity"]

        print(f"  {led_key}: I={intensity}, T={time_s}ms...", end=" ")

        wavelengths, spectrum, peak = measure_spectrum(
            spectrometer,
            opt_controller,
            controller_hw,
            led_key,
            intensity,
            time_s,
            "S",
            SCANS_TO_AVERAGE,
        )

        # Apply dark correction
        spectrum_corrected = spectrum - dark_spectrum_s
        peak_corrected = np.max(spectrum_corrected)

        results["S"][led_key] = {
            "spectrum_raw": spectrum,
            "spectrum_corrected": spectrum_corrected,
            "peak_raw": peak,
            "peak_corrected": peak_corrected,
            "intensity": intensity,
            "time": time_s,
        }

        print(f"Peak={peak:.0f} → {peak_corrected:.0f} counts (corrected)")

    # Measure P-pol spectra
    print("\n[3/3] Measuring P-polarization spectra...")
    time_p = optimal_settings["P"]["time"]

    for led in LEDS:
        led_key = f"LED_{led}"

        if led_key not in optimal_settings["P"]["leds"]:
            print(f"  {led_key}: Skipped (no settings)")
            continue

        settings = optimal_settings["P"]["leds"][led_key]
        intensity = settings["intensity"]

        print(f"  {led_key}: I={intensity}, T={time_p}ms...", end=" ")

        wavelengths, spectrum, peak = measure_spectrum(
            spectrometer,
            opt_controller,
            controller_hw,
            led_key,
            intensity,
            time_p,
            "P",
            SCANS_TO_AVERAGE,
        )

        # Apply dark correction
        spectrum_corrected = spectrum - dark_spectrum_p
        peak_corrected = np.max(spectrum_corrected)

        results["P"][led_key] = {
            "spectrum_raw": spectrum,
            "spectrum_corrected": spectrum_corrected,
            "peak_raw": peak,
            "peak_corrected": peak_corrected,
            "intensity": intensity,
            "time": time_p,
        }

        print(f"Peak={peak:.0f} → {peak_corrected:.0f} counts (corrected)")

    # Cleanup
    opt_controller.turn_off_all_leds()
    cmd = "sv072072\n"
    controller_hw._ser.write(cmd.encode())
    time.sleep(0.05)
    controller_hw._ser.write(b"ss\n")
    time.sleep(0.3)  # Return servo to S position

    print("\n[OK] Measurement complete")
    print("=" * 80)

    return results


# ==============================================================================
# Visualization
# ==============================================================================


def plot_validation_results(results, optimal_settings):
    """Plot transmission spectra and validation results."""
    wavelengths = results["wavelengths"]

    fig, axes = plt.subplots(4, 3, figsize=(18, 16))
    fig.suptitle(
        'CALIBRATION VALIDATION: Transmission Spectra at Optimal Settings\n'
        f'S-pol: {optimal_settings["S"]["time"]}ms | P-pol: {optimal_settings["P"]["time"]}ms | '
        f'Target: {TARGET_COUNTS:,} counts',
        fontsize=14,
        fontweight="bold",
    )

    for idx, led in enumerate(LEDS):
        led_key = f"LED_{led}"

        # Column 1: S-pol spectrum
        ax_s = axes[idx, 0]

        if led_key in results["S"]:
            spectrum_s = results["S"][led_key]["spectrum_corrected"]
            peak_s = results["S"][led_key]["peak_corrected"]
            intensity_s = results["S"][led_key]["intensity"]

            ax_s.plot(wavelengths, spectrum_s, "g-", linewidth=2, label="S-pol")
            ax_s.axhline(
                TARGET_COUNTS,
                color="blue",
                linestyle="--",
                linewidth=1,
                alpha=0.7,
                label=f"Target ({TARGET_COUNTS:,})",
            )
            ax_s.axhline(
                peak_s,
                color="red",
                linestyle=":",
                linewidth=1,
                alpha=0.7,
                label=f"Peak ({peak_s:.0f})",
            )

            error_pct = ((peak_s - TARGET_COUNTS) / TARGET_COUNTS) * 100
            ax_s.set_title(
                f"{led_key} S-pol (I={intensity_s})\n"
                f"Peak: {peak_s:.0f} | Error: {error_pct:+.1f}%",
                fontsize=10,
                fontweight="bold",
            )
            ax_s.legend(fontsize=8)
        else:
            ax_s.text(
                0.5,
                0.5,
                "No data",
                ha="center",
                va="center",
                transform=ax_s.transAxes,
                fontsize=12,
            )
            ax_s.set_title(f"{led_key} S-pol", fontsize=10)

        ax_s.set_xlabel("Wavelength (nm)", fontsize=9)
        ax_s.set_ylabel("Counts", fontsize=9)
        ax_s.grid(True, alpha=0.3)

        # Column 2: P-pol spectrum
        ax_p = axes[idx, 1]

        if led_key in results["P"]:
            spectrum_p = results["P"][led_key]["spectrum_corrected"]
            peak_p = results["P"][led_key]["peak_corrected"]
            intensity_p = results["P"][led_key]["intensity"]

            ax_p.plot(wavelengths, spectrum_p, "b-", linewidth=2, label="P-pol")
            ax_p.axhline(
                TARGET_COUNTS,
                color="blue",
                linestyle="--",
                linewidth=1,
                alpha=0.7,
                label=f"Target ({TARGET_COUNTS:,})",
            )
            ax_p.axhline(
                peak_p,
                color="red",
                linestyle=":",
                linewidth=1,
                alpha=0.7,
                label=f"Peak ({peak_p:.0f})",
            )

            error_pct = ((peak_p - TARGET_COUNTS) / TARGET_COUNTS) * 100
            ax_p.set_title(
                f"{led_key} P-pol (I={intensity_p})\n"
                f"Peak: {peak_p:.0f} | Error: {error_pct:+.1f}%",
                fontsize=10,
                fontweight="bold",
            )
            ax_p.legend(fontsize=8)
        else:
            ax_p.text(
                0.5,
                0.5,
                "No data",
                ha="center",
                va="center",
                transform=ax_p.transAxes,
                fontsize=12,
            )
            ax_p.set_title(f"{led_key} P-pol", fontsize=10)

        ax_p.set_xlabel("Wavelength (nm)", fontsize=9)
        ax_p.set_ylabel("Counts", fontsize=9)
        ax_p.grid(True, alpha=0.3)

        # Column 3: Transmission (P/S ratio)
        ax_t = axes[idx, 2]

        if led_key in results["S"] and led_key in results["P"]:
            spectrum_s = results["S"][led_key]["spectrum_corrected"]
            spectrum_p = results["P"][led_key]["spectrum_corrected"]

            # Normalize spectra by their peak in ROI
            roi_mask = (wavelengths >= 560) & (wavelengths <= 720)
            peak_s_roi = (
                np.max(spectrum_s[roi_mask]) if np.any(roi_mask) else np.max(spectrum_s)
            )
            peak_p_roi = (
                np.max(spectrum_p[roi_mask]) if np.any(roi_mask) else np.max(spectrum_p)
            )

            spectrum_s_norm = spectrum_s / peak_s_roi if peak_s_roi > 0 else spectrum_s
            spectrum_p_norm = spectrum_p / peak_p_roi if peak_p_roi > 0 else spectrum_p

            # Calculate transmission ratio (avoid division by zero)
            transmission = np.divide(
                spectrum_p_norm,
                spectrum_s_norm,
                where=spectrum_s_norm > 0.01,
                out=np.ones_like(spectrum_s_norm),
            )

            # Calculate mean transmission in ROI 560-720nm
            valid_mask = roi_mask & (spectrum_p > 1000) & (spectrum_s > 1000)
            if np.any(valid_mask):
                mean_transmission = np.mean(transmission[valid_mask])
            else:
                mean_transmission = np.nan

            ax_t.plot(wavelengths, transmission, "purple", linewidth=2)
            ax_t.axhline(
                mean_transmission,
                color="orange",
                linestyle="--",
                linewidth=1.5,
                alpha=0.7,
                label=f"Mean (560-720nm): {mean_transmission:.3f}",
            )
            ax_t.axhline(
                1.0,
                color="black",
                linestyle=":",
                linewidth=1,
                alpha=0.5,
                label="Unity",
            )

            # Shade ROI region
            ax_t.axvspan(560, 720, alpha=0.1, color="green", label="ROI")

            ax_t.set_title(
                f"{led_key} Transmission (P/S)\n"
                f"Normalized, Mean: {mean_transmission:.3f}",
                fontsize=10,
                fontweight="bold",
            )
            ax_t.legend(fontsize=8)
            ax_t.set_ylim([0, 1])
        else:
            ax_t.text(
                0.5,
                0.5,
                "No data",
                ha="center",
                va="center",
                transform=ax_t.transAxes,
                fontsize=12,
            )
            ax_t.set_title(f"{led_key} Transmission", fontsize=10)

        ax_t.set_xlabel("Wavelength (nm)", fontsize=9)
        ax_t.set_ylabel("P/S Ratio", fontsize=9)
        ax_t.grid(True, alpha=0.3)

    plt.tight_layout()

    detector_serial = optimal_settings["detector_serial"]
    output_file = Path(
        f"LED-Counts relationship/validation_transmission_spectra_{detector_serial}.png",
    )
    plt.savefig(output_file, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"\n[OK] Validation plot saved: {output_file}")
    plt.close()

    # Print summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY (ROI: 560-720nm)")
    print("=" * 80)
    print(
        f"{'LED':<8} {'S Peak':<12} {'S Error':<12} {'P Peak':<12} {'P Error':<12} {'P/S Ratio':<12}",
    )
    print("-" * 80)

    wavelengths = results["wavelengths"]
    roi_mask = (wavelengths >= 560) & (wavelengths <= 720)

    for led in LEDS:
        led_key = f"LED_{led}"

        if led_key in results["S"] and led_key in results["P"]:
            spectrum_s = results["S"][led_key]["spectrum_corrected"]
            spectrum_p = results["P"][led_key]["spectrum_corrected"]

            # Calculate peaks in ROI 560-720nm
            peak_s = (
                np.max(spectrum_s[roi_mask]) if np.any(roi_mask) else np.max(spectrum_s)
            )
            peak_p = (
                np.max(spectrum_p[roi_mask]) if np.any(roi_mask) else np.max(spectrum_p)
            )

            error_s = ((peak_s - TARGET_COUNTS) / TARGET_COUNTS) * 100
            error_p = ((peak_p - TARGET_COUNTS) / TARGET_COUNTS) * 100
            ratio = peak_p / peak_s if peak_s > 0 else 0

            print(
                f"{led_key:<8} {peak_s:>10.0f}  {error_s:>+9.1f}%  "
                f"{peak_p:>10.0f}  {error_p:>+9.1f}%  {ratio:>10.3f}",
            )

    print("=" * 80)


# ==============================================================================
# Main
# ==============================================================================


def main():
    # Load calibration and calculate optimal settings
    calib_file = Path(
        "LED-Counts relationship/led_calibration_spr_processed_FLMT09116.json",
    )
    optimal_settings = load_optimal_settings(calib_file)

    # Measure spectra
    results = measure_all_spectra(optimal_settings)

    # Save results
    detector_serial = optimal_settings["detector_serial"]
    results_file = Path(
        f"LED-Counts relationship/validation_results_{detector_serial}.json",
    )

    # Convert numpy arrays to lists for JSON
    results_json = {
        "wavelengths": results["wavelengths"].tolist(),
        "timestamp": results["timestamp"],
        "settings": optimal_settings,
        "dark": {
            "S": results["dark"]["S"].tolist(),
            "P": results["dark"]["P"].tolist(),
        },
        "S": {},
        "P": {},
    }

    for pol in ["S", "P"]:
        for led_key, data in results[pol].items():
            results_json[pol][led_key] = {
                "spectrum_corrected": data["spectrum_corrected"].tolist(),
                "peak_corrected": float(data["peak_corrected"]),
                "intensity": data["intensity"],
                "time": data["time"],
            }

    with open(results_file, "w") as f:
        json.dump(results_json, f, indent=2)

    print(f"\n[OK] Results saved: {results_file}")

    # Plot results
    plot_validation_results(results, optimal_settings)

    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
