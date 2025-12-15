"""VALIDATE BILINEAR MODEL: Fixed LED intensity, variable integration time

This script validates the bilinear model by:
1. Setting LED intensity to a fixed value (e.g., 100)
2. Sweeping integration time from 10ms to 150ms
3. Measuring actual counts at each integration time
4. Comparing measured counts vs model predictions
5. Plotting results to verify linearity and model accuracy

This tests the core assumption: counts = (a*t + b)*I + (c*t + d)
At fixed I, this should be: counts = (a*I + c)*t + (b*I + d) → LINEAR in time
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

# LED intensities to test (fixed values)
TEST_INTENSITIES = {
    "LED_A": 150,
    "LED_B": 60,
    "LED_C": 50,
    "LED_D": 140,
}

# Integration times to sweep (ms) - use 0.01ms resolution
INTEGRATION_TIMES = [
    10.00,
    20.00,
    30.00,
    40.00,
    50.00,
    60.00,
    80.00,
    100.00,
    120.00,
    150.00,
]

# Polarizations to test
POLARIZATIONS = ["S", "P"]
SERVO_POSITIONS = {"S": 72, "P": 8}

# Number of scans to average
SCANS_TO_AVERAGE = 3

# ROI for peak detection
ROI_MIN = 560
ROI_MAX = 720

LEDS = ["A", "B", "C", "D"]

# ==============================================================================
# Helper Functions
# ==============================================================================


def load_calibration_models():
    """Load bilinear models from calibration file."""
    cal_file = Path(
        "LED-Counts relationship/led_calibration_spr_processed_FLMT09116.json",
    )

    if not cal_file.exists():
        raise FileNotFoundError(f"Calibration file not found: {cal_file}")

    with open(cal_file) as f:
        data = json.load(f)

    return data


def predict_bilinear(model, intensity, time_ms):
    """Predict counts using bilinear model."""
    a = model["a"]
    b = model["b"]
    c = model["c"]
    d = model["d"]

    predicted = (a * time_ms + b) * intensity + (c * time_ms + d)
    return predicted


def measure_counts_at_time(
    spectrometer,
    opt_controller,
    controller_hw,
    led_channel,
    intensity,
    time_ms,
    servo_pos,
    wavelengths,
    roi_mask,
    scans=3,
):
    """Measure peak counts at specific intensity and integration time."""
    # Set servo position
    cmd = f"sv{servo_pos:03d}{servo_pos:03d}\n"
    controller_hw._ser.write(cmd.encode())
    time.sleep(0.05)
    controller_hw._ser.write(b"ss\n")
    time.sleep(0.3)

    # Set integration time
    spectrometer.set_integration_time(time_ms)

    # Turn on LED
    opt_controller.turn_off_all_leds()
    opt_controller.configure_led_atomic(led_channel, intensity)
    time.sleep(0.1)

    # Acquire spectra
    spectra = []
    for _ in range(scans):
        spectrum = spectrometer.read_spectrum()
        spectra.append(spectrum)
        time.sleep(0.05)

    # Turn off LED
    opt_controller.turn_off_all_leds()

    # Average spectra
    avg_spectrum = np.mean(spectra, axis=0)

    # Get peak in ROI
    peak_counts = np.max(avg_spectrum[roi_mask])

    return peak_counts, avg_spectrum


def measure_validation_data(models):
    """Measure counts at fixed intensities with variable integration times."""
    print("\n" + "=" * 80)
    print("FIXED INTENSITY VALIDATION")
    print("=" * 80)
    print("Testing: Fixed LED intensity, variable integration time")
    print("=" * 80)

    # Initialize hardware
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

    # Get wavelengths and ROI mask
    wavelengths = spectrometer.get_wavelengths()
    roi_mask = (wavelengths >= ROI_MIN) & (wavelengths <= ROI_MAX)

    # Measure dark current at different integration times
    print("\n[1/3] Measuring dark current...")
    dark_data = {}
    for time_ms in INTEGRATION_TIMES:
        spectrometer.set_integration_time(time_ms)
        opt_controller.turn_off_all_leds()
        time.sleep(0.2)

        spectra = []
        for _ in range(SCANS_TO_AVERAGE):
            spectrum = spectrometer.read_spectrum()
            spectra.append(spectrum)
            time.sleep(0.05)

        avg_dark = np.mean(spectra, axis=0)
        dark_peak = np.max(avg_dark[roi_mask])
        dark_data[time_ms] = {"spectrum": avg_dark, "peak": dark_peak}
        print(f"  {time_ms:6.2f}ms: Peak={dark_peak:.0f} counts")

    # Measure for each polarization and LED
    results = {
        "wavelengths": wavelengths.tolist(),
        "roi": {"min": ROI_MIN, "max": ROI_MAX},
        "integration_times": INTEGRATION_TIMES,
        "dark": {t: {"peak": dark_data[t]["peak"]} for t in INTEGRATION_TIMES},
        "timestamp": datetime.now().isoformat(),
    }

    for pol in POLARIZATIONS:
        print(f"\n[2/3 - {pol}] Measuring {pol}-polarization...")
        servo_pos = SERVO_POSITIONS[pol]
        results[pol] = {}

        for led in LEDS:
            led_key = f"LED_{led}"
            led_channel = led.lower()
            intensity = TEST_INTENSITIES[led_key]

            print(f"\n  {led_key}: I={intensity} (fixed)")

            measurements = []

            for time_ms in INTEGRATION_TIMES:
                peak, spectrum = measure_counts_at_time(
                    spectrometer,
                    opt_controller,
                    controller_hw,
                    led_channel,
                    intensity,
                    time_ms,
                    servo_pos,
                    wavelengths,
                    roi_mask,
                    SCANS_TO_AVERAGE,
                )

                # Dark correction
                dark_peak = dark_data[time_ms]["peak"]
                peak_corrected = peak - dark_peak

                # Model prediction (use just 'A', 'B', 'C', 'D' for keys)
                model = models[pol][led]["model"]
                predicted = predict_bilinear(model, intensity, time_ms)

                error = (
                    ((peak_corrected - predicted) / predicted) * 100
                    if predicted > 0
                    else 0
                )

                measurements.append(
                    {
                        "time": time_ms,
                        "measured": float(peak_corrected),
                        "predicted": float(predicted),
                        "error_percent": float(error),
                    },
                )

                print(
                    f"    {time_ms:6.2f}ms: Measured={peak_corrected:6.0f}, "
                    f"Predicted={predicted:6.0f}, Error={error:+5.1f}%",
                )

            results[pol][led_key] = {
                "intensity": intensity,
                "measurements": measurements,
            }

    # Cleanup
    opt_controller.turn_off_all_leds()
    cmd = "sv072072\n"
    controller_hw._ser.write(cmd.encode())
    time.sleep(0.05)
    controller_hw._ser.write(b"ss\n")

    print("\n[OK] Measurements complete")
    print("=" * 80)

    return results


def plot_validation_results(results, models):
    """Plot measured vs predicted counts."""
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    fig.suptitle(
        "Bilinear Model Validation: Fixed Intensity, Variable Time",
        fontsize=14,
        fontweight="bold",
    )

    times = np.array(results["integration_times"])

    for pol_idx, pol in enumerate(POLARIZATIONS):
        for led_idx, led in enumerate(LEDS):
            led_key = f"LED_{led}"
            ax = axes[pol_idx, led_idx]

            if led_key not in results[pol]:
                continue

            data = results[pol][led_key]
            intensity = data["intensity"]
            measurements = data["measurements"]

            measured = np.array([m["measured"] for m in measurements])
            predicted = np.array([m["predicted"] for m in measurements])
            errors = np.array([m["error_percent"] for m in measurements])

            # Plot measured vs predicted
            ax.plot(
                times,
                measured,
                "o-",
                color="blue",
                linewidth=2,
                markersize=6,
                label="Measured",
            )
            ax.plot(
                times,
                predicted,
                "s--",
                color="red",
                linewidth=2,
                markersize=5,
                label="Predicted",
            )

            # Calculate statistics
            rmse = np.sqrt(np.mean((measured - predicted) ** 2))
            max_error = np.max(np.abs(errors))
            mean_error = np.mean(np.abs(errors))

            # Linear fit to measured data
            coeffs = np.polyfit(times, measured, 1)
            fit_line = np.poly1d(coeffs)
            r_squared = 1 - (
                np.sum((measured - fit_line(times)) ** 2)
                / np.sum((measured - np.mean(measured)) ** 2)
            )

            ax.plot(
                times,
                fit_line(times),
                ":",
                color="green",
                linewidth=1.5,
                alpha=0.7,
                label=f"Linear Fit (R²={r_squared:.4f})",
            )

            # Labels and styling
            ax.set_title(
                f"{pol}-pol: {led_key} (I={intensity})\n"
                f"RMSE={rmse:.0f}, Max Err={max_error:.1f}%, Mean Err={mean_error:.1f}%",
                fontsize=9,
                fontweight="bold",
            )
            ax.set_xlabel("Integration Time (ms)", fontsize=8)
            ax.set_ylabel("Counts (ROI Peak)", fontsize=8)
            ax.legend(fontsize=7, loc="upper left")
            ax.grid(True, alpha=0.3)

            # Show linearity
            ax.text(
                0.98,
                0.05,
                f"Linearity: R²={r_squared:.5f}",
                transform=ax.transAxes,
                fontsize=7,
                ha="right",
                va="bottom",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
            )

    plt.tight_layout()

    output_file = Path(
        "LED-Counts relationship/validation_fixed_intensity_FLMT09116.png",
    )
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    print(f"\n[OK] Validation plot saved: {output_file}")

    return output_file


def print_summary(results):
    """Print validation summary statistics."""
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(
        f"{'LED':<10} {'Pol':<4} {'Intensity':<10} {'RMSE':<10} {'Max Err':<10} {'Mean Err':<10} {'R²':<10}",
    )
    print("-" * 80)

    for pol in POLARIZATIONS:
        for led in LEDS:
            led_key = f"LED_{led}"

            if led_key not in results[pol]:
                continue

            data = results[pol][led_key]
            intensity = data["intensity"]
            measurements = data["measurements"]

            times = np.array([m["time"] for m in measurements])
            measured = np.array([m["measured"] for m in measurements])
            predicted = np.array([m["predicted"] for m in measurements])
            errors = np.array([m["error_percent"] for m in measurements])

            rmse = np.sqrt(np.mean((measured - predicted) ** 2))
            max_error = np.max(np.abs(errors))
            mean_error = np.mean(np.abs(errors))

            # Calculate R² for linearity
            coeffs = np.polyfit(times, measured, 1)
            fit_line = np.poly1d(coeffs)
            r_squared = 1 - (
                np.sum((measured - fit_line(times)) ** 2)
                / np.sum((measured - np.mean(measured)) ** 2)
            )

            print(
                f"{led_key:<10} {pol:<4} {intensity:<10} {rmse:<10.0f} "
                f"{max_error:<10.1f}% {mean_error:<10.1f}% {r_squared:<10.5f}",
            )

    print("=" * 80)


# ==============================================================================
# Main
# ==============================================================================


def main():
    # Load calibration models
    print("Loading calibration models...")
    models = load_calibration_models()
    print(f"[OK] Loaded models for detector: {models['detector_serial']}")

    # Display test configuration
    print("\n" + "=" * 80)
    print("TEST CONFIGURATION")
    print("=" * 80)
    print("LED Intensities (fixed):")
    for led, intensity in TEST_INTENSITIES.items():
        print(f"  {led}: {intensity}")
    print(f"\nIntegration Times: {INTEGRATION_TIMES} ms")
    print(f"ROI: {ROI_MIN}-{ROI_MAX} nm")
    print(f"Scans per point: {SCANS_TO_AVERAGE}")
    print("=" * 80)

    # Measure validation data
    results = measure_validation_data(models)

    if results is None:
        print("[ERROR] Measurement failed!")
        return

    # Save results
    detector_serial = models["detector_serial"]
    results_file = Path(
        f"LED-Counts relationship/validation_fixed_intensity_{detector_serial}.json",
    )
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[OK] Results saved: {results_file}")

    # Plot results
    plot_validation_results(results, models)

    # Print summary
    print_summary(results)

    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)
    print("\nKey findings:")
    print("- If R² ≈ 1.000: Model correctly predicts LINEAR relationship")
    print("- If RMSE < 500: Model predictions are accurate")
    print("- If Mean Err < 2%: Model error is within acceptable range")
    print("=" * 80)


if __name__ == "__main__":
    main()
