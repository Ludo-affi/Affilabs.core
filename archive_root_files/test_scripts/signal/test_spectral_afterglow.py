"""Spectral Afterglow Analysis

Measures how afterglow decays as a FUNCTION OF WAVELENGTH.

Key questions:
1. Does afterglow have the same spectral shape as LED spectrum?
2. Is decay rate uniform across wavelengths?
3. Does afterglow baseline vary by wavelength?

Method:
- Turn on LED
- Turn off LED
- Measure full spectrum at multiple time delays
- Analyze decay per wavelength bin
"""

import io
import sys
import time
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from utils.controller import PicoP4SPR
from utils.usb4000_wrapper import USB4000


def exponential_decay(t, A, tau, baseline):
    """Exponential decay model: y = A * exp(-t/tau) + baseline"""
    return A * np.exp(-t / tau) + baseline


def test_spectral_afterglow():
    """Measure afterglow decay across full spectrum."""
    print("=" * 80)
    print("SPECTRAL AFTERGLOW ANALYSIS")
    print("=" * 80)
    print()

    # Initialize hardware
    print("Initializing hardware...")
    ctrl = PicoP4SPR()
    usb = USB4000()

    if not ctrl.open():
        print("ERROR: Controller not found")
        return

    if not usb.open():
        print("ERROR: Detector not found")
        return

    print("OK: Hardware connected")
    print()

    # Get wavelengths
    wavelengths = usb.wavelengths
    if wavelengths is None:
        print("ERROR: Failed to read wavelengths")
        return

    print(
        f"Detector: {len(wavelengths)} pixels, {wavelengths[0]:.1f}-{wavelengths[-1]:.1f}nm",
    )
    print()

    # Test parameters
    led_channel = "c"  # Use brightest channel
    led_intensity = 255
    integration_time = 70  # ms

    # Time delays to measure after LED turns off (ms)
    delay_times = [0, 5, 10, 20, 30, 50, 75, 100, 150, 200, 300]

    print("Test Configuration:")
    print(f"  LED Channel: {led_channel.upper()}")
    print(f"  LED Intensity: {led_intensity}")
    print(f"  Integration time: {integration_time}ms")
    print(f"  Delay times: {delay_times} ms")
    print()

    # Set integration time
    usb.set_integration(integration_time)
    time.sleep(0.05)

    print("=" * 80)
    print("STEP 1: MEASURE DARK SPECTRUM")
    print("=" * 80)
    print()

    # Ensure LEDs off
    ctrl.turn_off_channels()
    time.sleep(0.2)

    # Measure dark
    dark_spectrum = usb.read_intensity()
    if dark_spectrum is None:
        print("ERROR: Failed to read dark spectrum")
        return

    dark_mean = np.mean(dark_spectrum)
    dark_max = np.max(dark_spectrum)

    print("Dark spectrum:")
    print(f"  Mean: {dark_mean:.1f} counts")
    print(f"  Max: {dark_max:.1f} counts")
    print()

    print("=" * 80)
    print("STEP 2: MEASURE LED SPECTRUM (baseline)")
    print("=" * 80)
    print()

    # Turn on LED
    ctrl.set_intensity(ch=led_channel, raw_val=led_intensity)
    time.sleep(0.1)  # Wait for LED to stabilize

    # Measure LED spectrum
    led_spectrum = usb.read_intensity()
    if led_spectrum is None:
        print("ERROR: Failed to read LED spectrum")
        return

    led_mean = np.mean(led_spectrum)
    led_max = np.max(led_spectrum)
    peak_idx = np.argmax(led_spectrum)
    peak_wavelength = wavelengths[peak_idx]

    print("LED spectrum:")
    print(f"  Mean: {led_mean:.1f} counts")
    print(f"  Max: {led_max:.1f} counts at {peak_wavelength:.1f}nm")
    print()

    print("=" * 80)
    print("STEP 3: MEASURE AFTERGLOW DECAY")
    print("=" * 80)
    print()

    afterglow_spectra = {}

    print("Measuring afterglow at different delays...")
    print()

    for delay_ms in delay_times:
        # Turn on LED
        ctrl.set_intensity(ch=led_channel, raw_val=led_intensity)
        time.sleep(0.1)  # Stabilize

        # Turn off LED
        ctrl.turn_off_channels()

        # Wait for specified delay
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

        # Measure spectrum
        spectrum = usb.read_intensity()

        if spectrum is not None:
            afterglow_spectra[delay_ms] = spectrum
            mean_signal = np.mean(spectrum)
            max_signal = np.max(spectrum)
            print(f"  {delay_ms:3d}ms: mean={mean_signal:.0f}, max={max_signal:.0f}")
        else:
            print(f"  {delay_ms:3d}ms: FAILED")

    print()

    # Turn off LED
    ctrl.turn_off_channels()

    if len(afterglow_spectra) == 0:
        print("ERROR: No afterglow spectra collected")
        return

    print("=" * 80)
    print("STEP 4: ANALYZE SPECTRAL DECAY")
    print("=" * 80)
    print()

    # Dark-subtract all spectra
    afterglow_corrected = {}
    for delay_ms, spectrum in afterglow_spectra.items():
        afterglow_corrected[delay_ms] = spectrum - dark_spectrum

    led_corrected = led_spectrum - dark_spectrum

    # Analyze decay at different wavelength regions
    # Define regions of interest
    regions = {
        "Blue (480-500nm)": (480, 500),
        "Peak region": (peak_wavelength - 10, peak_wavelength + 10),
        "Red (580-600nm)": (580, 600),
        "Full spectrum": (wavelengths[0], wavelengths[-1]),
    }

    print("Decay analysis by wavelength region:")
    print()

    decay_results = {}

    for region_name, (wl_min, wl_max) in regions.items():
        # Find wavelength indices
        idx_min = np.argmin(np.abs(wavelengths - wl_min))
        idx_max = np.argmin(np.abs(wavelengths - wl_max))

        # Extract region
        region_slice = slice(idx_min, idx_max + 1)

        # Calculate mean signal in region for each delay
        times = []
        signals = []

        for delay_ms in sorted(afterglow_spectra.keys()):
            spectrum = afterglow_corrected[delay_ms]
            region_signal = np.mean(spectrum[region_slice])

            times.append(delay_ms)
            signals.append(region_signal)

        times = np.array(times)
        signals = np.array(signals)

        # Fit exponential decay
        try:
            # Initial guess
            A_guess = signals[0] - signals[-1]
            tau_guess = 20
            baseline_guess = signals[-1]

            popt, pcov = curve_fit(
                exponential_decay,
                times,
                signals,
                p0=[A_guess, tau_guess, baseline_guess],
                maxfev=5000,
            )

            A_fit, tau_fit, baseline_fit = popt

            # Calculate R²
            residuals = signals - exponential_decay(times, *popt)
            ss_res = np.sum(residuals**2)
            ss_tot = np.sum((signals - np.mean(signals)) ** 2)
            r_squared = 1 - (ss_res / ss_tot)

            decay_results[region_name] = {
                "times": times,
                "signals": signals,
                "A": A_fit,
                "tau": tau_fit,
                "baseline": baseline_fit,
                "r_squared": r_squared,
                "wavelength_range": (wl_min, wl_max),
            }

            print(f"{region_name} ({wl_min:.0f}-{wl_max:.0f}nm):")
            print(f"  Initial afterglow (A): {A_fit:.0f} counts")
            print(f"  Decay constant (tau): {tau_fit:.1f} ms")
            print(f"  Baseline: {baseline_fit:.0f} counts")
            print(f"  R²: {r_squared:.4f}")
            print()

        except Exception as e:
            print(f"{region_name}: Fit failed - {e}")
            print()

    print("=" * 80)
    print("STEP 5: SPECTRAL SHAPE ANALYSIS")
    print("=" * 80)
    print()

    # Compare spectral shapes
    print("Comparing afterglow spectral shape to LED spectrum:")
    print()

    # Normalize spectra for shape comparison
    led_normalized = led_corrected / np.max(led_corrected)

    # Select a few delay times for comparison
    compare_delays = [0, 50, 100, 200]

    for delay_ms in compare_delays:
        if delay_ms in afterglow_corrected:
            afterglow_norm = afterglow_corrected[delay_ms] / np.max(
                afterglow_corrected[delay_ms],
            )

            # Calculate correlation with LED spectrum
            correlation = np.corrcoef(led_normalized, afterglow_norm)[0, 1]

            # Calculate shape difference (RMS of normalized difference)
            shape_diff = np.sqrt(np.mean((led_normalized - afterglow_norm) ** 2))

            print(f"  {delay_ms:3d}ms afterglow:")
            print(f"    Correlation with LED: {correlation:.4f}")
            print(f"    Shape difference (RMS): {shape_diff:.4f}")
            print()

    print("=" * 80)
    print("STEP 6: VISUALIZATION")
    print("=" * 80)
    print()

    # Create comprehensive plot
    fig = plt.figure(figsize=(16, 12))

    # Plot 1: Full spectra at different delays
    ax1 = plt.subplot(3, 2, 1)

    # Plot LED spectrum
    ax1.plot(wavelengths, led_corrected, "k-", linewidth=2, label="LED ON", alpha=0.8)

    # Plot afterglow spectra with color gradient
    colors = plt.cm.hot_r(np.linspace(0.2, 0.9, len(compare_delays)))

    for i, delay_ms in enumerate(compare_delays):
        if delay_ms in afterglow_corrected:
            ax1.plot(
                wavelengths,
                afterglow_corrected[delay_ms],
                color=colors[i],
                linewidth=1.5,
                label=f"{delay_ms}ms delay",
                alpha=0.7,
            )

    ax1.set_xlabel("Wavelength (nm)", fontsize=11)
    ax1.set_ylabel("Intensity (counts)", fontsize=11)
    ax1.set_title("Spectral Afterglow Decay", fontsize=12, fontweight="bold")
    ax1.legend(loc="best", fontsize=9)
    ax1.grid(True, alpha=0.3)

    # Plot 2: Normalized spectra (shape comparison)
    ax2 = plt.subplot(3, 2, 2)

    ax2.plot(wavelengths, led_normalized, "k-", linewidth=2, label="LED ON", alpha=0.8)

    for i, delay_ms in enumerate(compare_delays):
        if delay_ms in afterglow_corrected:
            afterglow_norm = afterglow_corrected[delay_ms] / np.max(
                afterglow_corrected[delay_ms],
            )
            ax2.plot(
                wavelengths,
                afterglow_norm,
                color=colors[i],
                linewidth=1.5,
                label=f"{delay_ms}ms",
                alpha=0.7,
            )

    ax2.set_xlabel("Wavelength (nm)", fontsize=11)
    ax2.set_ylabel("Normalized Intensity", fontsize=11)
    ax2.set_title("Normalized Spectral Shapes", fontsize=12, fontweight="bold")
    ax2.legend(loc="best", fontsize=9)
    ax2.grid(True, alpha=0.3)

    # Plot 3: Decay curves by wavelength region
    ax3 = plt.subplot(3, 2, 3)

    region_colors = ["blue", "red", "orange", "black"]

    for (region_name, result), color in zip(
        decay_results.items(),
        region_colors,
        strict=False,
    ):
        times = result["times"]
        signals = result["signals"]

        # Plot data
        ax3.plot(
            times,
            signals,
            "o",
            color=color,
            markersize=6,
            label=region_name,
            alpha=0.6,
        )

        # Plot fit
        t_fit = np.linspace(0, max(times), 100)
        y_fit = exponential_decay(t_fit, result["A"], result["tau"], result["baseline"])
        ax3.plot(t_fit, y_fit, "-", color=color, linewidth=2, alpha=0.8)

    ax3.set_xlabel("Time after LED off (ms)", fontsize=11)
    ax3.set_ylabel("Mean Intensity (counts)", fontsize=11)
    ax3.set_title("Decay by Wavelength Region", fontsize=12, fontweight="bold")
    ax3.legend(loc="best", fontsize=9)
    ax3.grid(True, alpha=0.3)
    ax3.set_yscale("log")

    # Plot 4: Decay time constants by region
    ax4 = plt.subplot(3, 2, 4)

    region_names = [name.split("(")[0].strip() for name in decay_results]
    tau_values = [result["tau"] for result in decay_results.values()]

    bars = ax4.bar(range(len(region_names)), tau_values, color=region_colors, alpha=0.7)
    ax4.set_xticks(range(len(region_names)))
    ax4.set_xticklabels(region_names, rotation=45, ha="right")
    ax4.set_ylabel("Decay Time Constant (ms)", fontsize=11)
    ax4.set_title("Decay Rate by Wavelength", fontsize=12, fontweight="bold")
    ax4.grid(True, alpha=0.3, axis="y")

    # Add value labels on bars
    for bar, tau in zip(bars, tau_values, strict=False):
        height = bar.get_height()
        ax4.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{tau:.1f}ms",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    # Plot 5: Baseline levels by region
    ax5 = plt.subplot(3, 2, 5)

    baseline_values = [result["baseline"] for result in decay_results.values()]

    bars = ax5.bar(
        range(len(region_names)),
        baseline_values,
        color=region_colors,
        alpha=0.7,
    )
    ax5.set_xticks(range(len(region_names)))
    ax5.set_xticklabels(region_names, rotation=45, ha="right")
    ax5.set_ylabel("Baseline Level (counts)", fontsize=11)
    ax5.set_title("Persistent Baseline by Wavelength", fontsize=12, fontweight="bold")
    ax5.grid(True, alpha=0.3, axis="y")

    # Add value labels
    for bar, baseline in zip(bars, baseline_values, strict=False):
        height = bar.get_height()
        ax5.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{baseline:.0f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    # Plot 6: Spectral difference (LED - afterglow)
    ax6 = plt.subplot(3, 2, 6)

    for i, delay_ms in enumerate([50, 100, 200]):
        if delay_ms in afterglow_corrected:
            diff = led_corrected - afterglow_corrected[delay_ms]
            ax6.plot(
                wavelengths,
                diff,
                color=colors[i + 1],
                linewidth=1.5,
                label=f"{delay_ms}ms",
                alpha=0.7,
            )

    ax6.axhline(y=0, color="k", linestyle="--", linewidth=1)
    ax6.set_xlabel("Wavelength (nm)", fontsize=11)
    ax6.set_ylabel("Intensity Difference (counts)", fontsize=11)
    ax6.set_title("LED - Afterglow Difference", fontsize=12, fontweight="bold")
    ax6.legend(loc="best", fontsize=9)
    ax6.grid(True, alpha=0.3)

    plt.tight_layout()

    # Save plot
    plot_filename = (
        f"spectral_afterglow_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    )
    plt.savefig(plot_filename, dpi=150, bbox_inches="tight")
    print(f"Plot saved: {plot_filename}")

    plt.show()

    print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()

    print("Key findings:")
    print()

    # Check if decay is uniform across wavelengths
    tau_values_list = [result["tau"] for result in decay_results.values()]
    tau_mean = np.mean(tau_values_list)
    tau_std = np.std(tau_values_list)
    tau_cv = (tau_std / tau_mean * 100) if tau_mean > 0 else 0

    print("1. Decay time constant:")
    print(f"   Mean: {tau_mean:.1f} ms")
    print(f"   Std: {tau_std:.1f} ms")
    print(f"   CV: {tau_cv:.1f}%")

    if tau_cv < 10:
        print("   → Uniform decay across wavelengths ✓")
    else:
        print("   → Wavelength-dependent decay! ⚠")

    print()

    # Check spectral shape preservation
    if 0 in afterglow_corrected and 200 in afterglow_corrected:
        corr_0 = np.corrcoef(
            led_normalized,
            afterglow_corrected[0] / np.max(afterglow_corrected[0]),
        )[0, 1]
        corr_200 = np.corrcoef(
            led_normalized,
            afterglow_corrected[200] / np.max(afterglow_corrected[200]),
        )[0, 1]

        print("2. Spectral shape preservation:")
        print(f"   Immediate (0ms): correlation = {corr_0:.4f}")
        print(f"   After decay (200ms): correlation = {corr_200:.4f}")

        if corr_0 > 0.95 and corr_200 > 0.95:
            print("   → Spectral shape preserved ✓")
        elif corr_0 > 0.95:
            print("   → Shape changes as afterglow decays ⚠")
        else:
            print("   → Afterglow has different spectral shape! ⚠")

    print()

    # Baseline uniformity
    baseline_values_list = [result["baseline"] for result in decay_results.values()]
    baseline_mean = np.mean(baseline_values_list)
    baseline_std = np.std(baseline_values_list)
    baseline_cv = (baseline_std / baseline_mean * 100) if baseline_mean > 0 else 0

    print("3. Persistent baseline:")
    print(f"   Mean: {baseline_mean:.0f} counts")
    print(f"   Std: {baseline_std:.0f} counts")
    print(f"   CV: {baseline_cv:.1f}%")

    if baseline_cv < 20:
        print("   → Uniform baseline (likely optical scatter) ✓")
    else:
        print("   → Wavelength-dependent baseline ⚠")

    print()

    # Cleanup
    usb.close()

    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_spectral_afterglow()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed: {e}")
        import traceback

        traceback.print_exc()
