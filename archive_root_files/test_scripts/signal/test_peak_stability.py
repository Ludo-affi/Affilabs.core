"""5-Minute Peak Stability Study

Tracks peak position over time to assess:
1. Long-term stability (drift)
2. Short-term precision (noise)
3. Channel-to-channel consistency
4. Temperature effects

Continuously measures all 4 channels for 5 minutes and analyzes peak position drift.
"""

import io
import sys
import time
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from utils.controller import PicoP4SPR
from utils.usb4000_wrapper import USB4000


def find_peak_position(spectrum, wavelengths):
    """Find peak wavelength using centroid method."""
    peak_idx = np.argmax(spectrum)

    # Centroid around peak (more robust than max)
    window = 20
    start = max(0, peak_idx - window)
    end = min(len(spectrum), peak_idx + window)

    weights = spectrum[start:end]
    positions = wavelengths[start:end]
    centroid = np.sum(weights * positions) / np.sum(weights)

    return centroid, peak_idx


def peak_stability_study():
    """5-minute peak stability tracking."""
    print("=" * 80)
    print("5-MINUTE PEAK STABILITY STUDY")
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
    channels = ["a", "b", "c", "d"]
    led_intensity = 255
    integration_time = 70  # ms
    duration_seconds = 300  # 5 minutes

    print("Test Configuration:")
    print(f"  Channels: {[ch.upper() for ch in channels]}")
    print(f"  LED Intensity: {led_intensity}")
    print(f"  Integration time: {integration_time}ms")
    print(f"  Duration: {duration_seconds}s ({duration_seconds/60:.1f} minutes)")
    print(f"  Start time: {datetime.now().strftime('%H:%M:%S')}")
    print()

    # Set integration time
    usb.set_integration(integration_time)
    time.sleep(0.05)

    # Data storage
    data = {
        ch: {
            "timestamps": [],
            "peak_positions": [],
            "peak_intensities": [],
            "mean_signals": [],
        }
        for ch in channels
    }

    print("=" * 80)
    print("MEASUREMENT IN PROGRESS")
    print("=" * 80)
    print()
    print("Press Ctrl+C to stop early")
    print()

    start_time = time.perf_counter()
    end_time = start_time + duration_seconds

    measurement_count = 0
    cycle_count = 0
    last_report_time = start_time

    try:
        while time.perf_counter() < end_time:
            cycle_start = time.perf_counter()

            for ch in channels:
                # Turn on LED
                ctrl.set_intensity(ch=ch, raw_val=led_intensity)
                time.sleep(0.045)  # PRE-LED delay

                # Read spectrum
                spectrum = usb.read_intensity()
                timestamp = time.perf_counter() - start_time

                if spectrum is not None:
                    # Find peak
                    peak_wl, peak_idx = find_peak_position(spectrum, wavelengths)
                    peak_intensity = spectrum[peak_idx]
                    mean_signal = np.mean(spectrum)

                    # Store data
                    data[ch]["timestamps"].append(timestamp)
                    data[ch]["peak_positions"].append(peak_wl)
                    data[ch]["peak_intensities"].append(peak_intensity)
                    data[ch]["mean_signals"].append(mean_signal)

                    measurement_count += 1

                # Turn off LED
                ctrl.turn_off_channels()
                time.sleep(0.100)  # POST-LED delay

            cycle_count += 1

            # Progress report every 30 seconds
            current_time = time.perf_counter()
            if current_time - last_report_time >= 30:
                elapsed = current_time - start_time
                remaining = duration_seconds - elapsed
                progress = (elapsed / duration_seconds) * 100

                print(
                    f"[{elapsed:.0f}s / {duration_seconds}s] Progress: {progress:.1f}% | "
                    f"Cycles: {cycle_count} | Measurements: {measurement_count} | "
                    f"Remaining: {remaining:.0f}s",
                )

                last_report_time = current_time

    except KeyboardInterrupt:
        print()
        print("Measurement stopped by user")
        print()

    # Turn off LEDs
    ctrl.turn_off_channels()

    # Final statistics
    elapsed_total = time.perf_counter() - start_time

    print()
    print("=" * 80)
    print("MEASUREMENT COMPLETE")
    print("=" * 80)
    print()
    print(f"Total time: {elapsed_total:.1f}s ({elapsed_total/60:.2f} minutes)")
    print(f"Cycles completed: {cycle_count}")
    print(f"Total measurements: {measurement_count}")
    print(
        f"Measurements per channel: {[len(data[ch]['timestamps']) for ch in channels]}",
    )
    print()

    # Analysis
    print("=" * 80)
    print("PEAK STABILITY ANALYSIS")
    print("=" * 80)
    print()

    print(
        f"{'Channel':>8} | {'N':>5} | {'Mean Peak':>10} | {'Peak Std':>9} | {'Peak P-P':>9} | {'Drift':>10} | {'Mean Signal':>12}",
    )
    print(
        f"{'':>8} | {'':>5} | {'(nm)':>10} | {'(nm)':>9} | {'(nm)':>9} | {'(nm/min)':>10} | {'(counts)':>12}",
    )
    print(
        "---------+-------+------------+-----------+-----------+------------+--------------",
    )

    stability_results = {}

    for ch in channels:
        if len(data[ch]["timestamps"]) == 0:
            continue

        timestamps = np.array(data[ch]["timestamps"])
        peak_positions = np.array(data[ch]["peak_positions"])
        peak_intensities = np.array(data[ch]["peak_intensities"])
        mean_signals = np.array(data[ch]["mean_signals"])

        # Statistics
        peak_mean = np.mean(peak_positions)
        peak_std = np.std(peak_positions)
        peak_min = np.min(peak_positions)
        peak_max = np.max(peak_positions)
        peak_p2p = peak_max - peak_min
        signal_mean = np.mean(mean_signals)

        # Linear drift (nm per minute)
        if len(timestamps) > 1:
            # Fit linear trend
            coeffs = np.polyfit(
                timestamps / 60,
                peak_positions,
                1,
            )  # timestamps in minutes
            drift_rate = coeffs[0]  # nm/min
        else:
            drift_rate = 0

        stability_results[ch] = {
            "n": len(peak_positions),
            "peak_mean": peak_mean,
            "peak_std": peak_std,
            "peak_min": peak_min,
            "peak_max": peak_max,
            "peak_p2p": peak_p2p,
            "drift_rate": drift_rate,
            "signal_mean": signal_mean,
            "timestamps": timestamps,
            "peak_positions": peak_positions,
        }

        print(
            f"{ch.upper():>8} | {len(peak_positions):>5} | {peak_mean:>10.3f} | {peak_std:>9.3f} | {peak_p2p:>9.3f} | {drift_rate:>10.3f} | {signal_mean:>12.0f}",
        )

    print()

    # Overall assessment
    print("=" * 80)
    print("STABILITY ASSESSMENT")
    print("=" * 80)
    print()

    for ch in channels:
        if ch not in stability_results:
            continue

        r = stability_results[ch]

        print(f"Channel {ch.upper()}:")
        print(f"  Peak position: {r['peak_mean']:.3f} nm")
        print(f"  Short-term precision (std): {r['peak_std']:.3f} nm")
        print(f"  Peak-to-peak variation: {r['peak_p2p']:.3f} nm")
        print(
            f"  Long-term drift: {r['drift_rate']:.3f} nm/min ({r['drift_rate']*60:.2f} nm/hour)",
        )

        # Assessment
        if r["peak_std"] < 0.05:
            print("  ✓ Excellent short-term stability (<0.05nm)")
        elif r["peak_std"] < 0.1:
            print("  ✓ Good short-term stability (<0.1nm)")
        elif r["peak_std"] < 0.5:
            print("  ~ Acceptable short-term stability (<0.5nm)")
        else:
            print(f"  ✗ Poor short-term stability (>{r['peak_std']:.2f}nm)")

        if abs(r["drift_rate"]) < 0.01:
            print("  ✓ Negligible drift (<0.01nm/min)")
        elif abs(r["drift_rate"]) < 0.1:
            print("  ~ Small drift (<0.1nm/min)")
        else:
            print(f"  ⚠ Significant drift (>{abs(r['drift_rate']):.2f}nm/min)")

        print()

    # Visualization
    print("=" * 80)
    print("GENERATING PLOTS")
    print("=" * 80)
    print()

    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("5-Minute Peak Stability Study", fontsize=16, fontweight="bold")

    colors = {"a": "blue", "b": "green", "c": "red", "d": "orange"}

    # Plot 1: Peak position over time (all channels)
    ax = axes[0, 0]
    for ch in channels:
        if ch in stability_results:
            r = stability_results[ch]
            ax.plot(
                r["timestamps"] / 60,
                r["peak_positions"],
                "o-",
                color=colors[ch],
                alpha=0.7,
                markersize=3,
                label=f"Ch {ch.upper()} ({r['peak_mean']:.2f}nm)",
            )

    ax.set_xlabel("Time (minutes)", fontsize=11)
    ax.set_ylabel("Peak Position (nm)", fontsize=11)
    ax.set_title("Peak Position vs Time", fontsize=12, fontweight="bold")
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.3)

    # Plot 2: Peak position distribution (histogram)
    ax = axes[0, 1]
    for ch in channels:
        if ch in stability_results:
            r = stability_results[ch]
            ax.hist(
                r["peak_positions"],
                bins=30,
                alpha=0.5,
                color=colors[ch],
                label=f"Ch {ch.upper()} (σ={r['peak_std']:.3f}nm)",
            )

    ax.set_xlabel("Peak Position (nm)", fontsize=11)
    ax.set_ylabel("Count", fontsize=11)
    ax.set_title("Peak Position Distribution", fontsize=12, fontweight="bold")
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.3)

    # Plot 3: Peak-to-peak variation per channel
    ax = axes[1, 0]
    ch_labels = [ch.upper() for ch in channels if ch in stability_results]
    p2p_values = [
        stability_results[ch]["peak_p2p"] for ch in channels if ch in stability_results
    ]
    std_values = [
        stability_results[ch]["peak_std"] for ch in channels if ch in stability_results
    ]

    x = np.arange(len(ch_labels))
    width = 0.35

    ax.bar(
        x - width / 2,
        p2p_values,
        width,
        label="Peak-to-Peak",
        color="steelblue",
        alpha=0.7,
    )
    ax.bar(x + width / 2, std_values, width, label="Std Dev", color="coral", alpha=0.7)

    ax.set_xlabel("Channel", fontsize=11)
    ax.set_ylabel("Variation (nm)", fontsize=11)
    ax.set_title("Peak Variation Summary", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(ch_labels)
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.3, axis="y")

    # Plot 4: Drift rate per channel
    ax = axes[1, 1]
    drift_values = [
        stability_results[ch]["drift_rate"]
        for ch in channels
        if ch in stability_results
    ]

    bars = ax.bar(
        ch_labels,
        drift_values,
        color=[colors[ch.lower()] for ch in ch_labels],
        alpha=0.7,
    )

    # Color bars by drift magnitude
    for bar, drift in zip(bars, drift_values, strict=False):
        if abs(drift) < 0.01:
            bar.set_color("green")
        elif abs(drift) < 0.1:
            bar.set_color("orange")
        else:
            bar.set_color("red")

    ax.axhline(y=0, color="black", linestyle="-", linewidth=0.8)
    ax.set_xlabel("Channel", fontsize=11)
    ax.set_ylabel("Drift Rate (nm/min)", fontsize=11)
    ax.set_title("Long-Term Drift", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()

    # Save plot
    plot_filename = (
        f"peak_stability_study_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    )
    plt.savefig(plot_filename, dpi=150, bbox_inches="tight")
    print(f"Plot saved: {plot_filename}")

    # Show plot
    plt.show()

    print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()

    # Overall stability
    all_stds = [
        stability_results[ch]["peak_std"] for ch in channels if ch in stability_results
    ]
    all_drifts = [
        stability_results[ch]["drift_rate"]
        for ch in channels
        if ch in stability_results
    ]

    mean_std = np.mean(all_stds)
    max_std = np.max(all_stds)
    mean_drift = np.mean(np.abs(all_drifts))
    max_drift = np.max(np.abs(all_drifts))

    print("Overall Performance:")
    print(f"  Mean precision (std): {mean_std:.3f} nm")
    print(f"  Worst precision: {max_std:.3f} nm")
    print(f"  Mean drift rate: {mean_drift:.3f} nm/min ({mean_drift*60:.2f} nm/hour)")
    print(f"  Max drift rate: {max_drift:.3f} nm/min ({max_drift*60:.2f} nm/hour)")
    print()

    if mean_std < 0.1 and max_drift < 0.1:
        print("✓ EXCELLENT: System is highly stable for SPR measurements")
        print("  - Sub-0.1nm precision")
        print("  - Minimal drift")
        print("  - Suitable for long-term kinetic studies")
    elif mean_std < 0.5 and max_drift < 0.5:
        print("✓ GOOD: System is stable for typical SPR applications")
        print("  - Good precision for binding studies")
        print("  - Acceptable drift for experiments <30min")
    else:
        print("⚠ CAUTION: System shows significant variation")
        print("  - Consider temperature stabilization")
        print("  - Check for mechanical vibrations")
        print("  - Verify LED stability")

    print()

    # Cleanup
    usb.close()

    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    try:
        peak_stability_study()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed: {e}")
        import traceback

        traceback.print_exc()
