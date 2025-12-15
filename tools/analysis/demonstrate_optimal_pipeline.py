"""Demonstrate optimal pipeline performance on real Channel A data.

Show sensorgram comparison:
- Baseline (no denoising)
- Optimal pipeline (afterglow → dark → denoise S&P → transmission)

Test all peak-finding methods:
- Direct minimum
- Polynomial fit
- Centroid
- Gaussian fit
- Spline interpolation

Goal: Visualize the real improvement and compare peak-finding accuracy.
"""

import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import UnivariateSpline
from scipy.optimize import curve_fit
from scipy.signal import savgol_filter

# Configuration
DEVICE_NAME = "demo P4SPR 2.0"
SENSOR_STATE = "used"
S_TIMESTAMP = "20251022_140707"
P_TIMESTAMP = "20251022_140940"

BASE_DIR = Path("spectral_training_data") / DEVICE_NAME
S_DIR = BASE_DIR / "s" / SENSOR_STATE / S_TIMESTAMP
P_DIR = BASE_DIR / "p" / SENSOR_STATE / P_TIMESTAMP
OUTPUT_DIR = Path("analysis_results/final_pipeline_demo")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Pipeline parameters
SAVGOL_WINDOW = 51
SAVGOL_POLYORDER = 3
SEARCH_START = 400
SEARCH_END = 1400


def load_data(channel: str) -> dict:
    """Load S and P mode data."""
    data = {}

    # S-mode
    s_file = S_DIR / f"{channel}.npz"
    s_data = np.load(s_file)
    data["s_spectra"] = s_data["spectra"]
    data["s_dark"] = s_data["dark"].squeeze()
    data["s_timestamps"] = s_data["timestamps"]

    # P-mode
    p_file = P_DIR / f"{channel}.npz"
    p_data = np.load(p_file)
    data["p_spectra"] = p_data["spectra"]
    data["p_dark"] = p_data["dark"].squeeze()
    data["p_timestamps"] = p_data["timestamps"]

    return data


def process_baseline(
    s_raw: np.ndarray,
    p_raw: np.ndarray,
    s_dark: np.ndarray,
    p_dark: np.ndarray,
) -> np.ndarray:
    """Baseline: dark correction only, no denoising."""
    s_corr = s_raw - s_dark
    p_corr = p_raw - p_dark

    s_safe = np.where(s_corr < 1, 1, s_corr)
    transmission = p_corr / s_safe

    return transmission


def process_optimal_pipeline(
    s_raw: np.ndarray,
    p_raw: np.ndarray,
    s_dark: np.ndarray,
    p_dark: np.ndarray,
) -> np.ndarray:
    """Optimal pipeline: dark → denoise S&P → transmission."""
    # 1. Dark correction (use original dark, no denoising)
    s_corr = s_raw - s_dark
    p_corr = p_raw - p_dark

    # 2. Denoise S and P separately
    s_clean = savgol_filter(s_corr, SAVGOL_WINDOW, SAVGOL_POLYORDER)
    p_clean = savgol_filter(p_corr, SAVGOL_WINDOW, SAVGOL_POLYORDER)

    # 3. Calculate transmission
    s_safe = np.where(s_clean < 1, 1, s_clean)
    transmission = p_clean / s_safe

    return transmission


def find_minimum_direct(transmission: np.ndarray) -> float:
    """Direct minimum - simplest and fastest."""
    search_region = transmission[SEARCH_START:SEARCH_END]
    min_idx = np.argmin(search_region)
    return float(SEARCH_START + min_idx)


def find_minimum_polynomial(transmission: np.ndarray, degree: int = 4) -> float:
    """Polynomial fit around minimum."""
    search_region = transmission[SEARCH_START:SEARCH_END]
    min_idx = np.argmin(search_region)

    # Fit around minimum (±20 pixels)
    fit_start = max(0, min_idx - 20)
    fit_end = min(len(search_region), min_idx + 20)

    x = np.arange(fit_start, fit_end)
    y = search_region[fit_start:fit_end]

    try:
        coeffs = np.polyfit(x, y, degree)
        poly = np.poly1d(coeffs)

        # Find minimum of polynomial
        x_fine = np.linspace(fit_start, fit_end, 1000)
        y_fine = poly(x_fine)
        min_fine_idx = np.argmin(y_fine)

        return float(SEARCH_START + x_fine[min_fine_idx])
    except:
        return float(SEARCH_START + min_idx)


def find_minimum_centroid(transmission: np.ndarray, width: int = 40) -> float:
    """Weighted centroid around minimum."""
    search_region = transmission[SEARCH_START:SEARCH_END]
    min_idx = np.argmin(search_region)

    # Take window around minimum
    window_start = max(0, min_idx - width // 2)
    window_end = min(len(search_region), min_idx + width // 2)

    window = search_region[window_start:window_end]

    # Invert (so dip becomes peak for weighting)
    window_inverted = np.max(window) - window

    # Weighted centroid
    x = np.arange(window_start, window_end)
    centroid = np.sum(x * window_inverted) / np.sum(window_inverted)

    return float(SEARCH_START + centroid)


def gaussian(x, a, mu, sigma, offset):
    """Inverted Gaussian for SPR dip."""
    return offset - a * np.exp(-((x - mu) ** 2) / (2 * sigma**2))


def find_minimum_gaussian(transmission: np.ndarray) -> float:
    """Gaussian fit to SPR dip."""
    search_region = transmission[SEARCH_START:SEARCH_END]
    min_idx = np.argmin(search_region)

    # Fit around minimum (±30 pixels)
    fit_start = max(0, min_idx - 30)
    fit_end = min(len(search_region), min_idx + 30)

    x = np.arange(fit_start, fit_end)
    y = search_region[fit_start:fit_end]

    try:
        # Initial guess
        p0 = [
            np.max(y) - np.min(y),  # amplitude
            min_idx,  # center
            10,  # width
            np.max(y),  # offset
        ]

        popt, _ = curve_fit(gaussian, x, y, p0=p0, maxfev=5000)

        return float(SEARCH_START + popt[1])
    except:
        return float(SEARCH_START + min_idx)


def find_minimum_spline(transmission: np.ndarray, smoothing: float = 0.1) -> float:
    """Spline interpolation."""
    search_region = transmission[SEARCH_START:SEARCH_END]
    min_idx = np.argmin(search_region)

    # Fit around minimum (±25 pixels)
    fit_start = max(0, min_idx - 25)
    fit_end = min(len(search_region), min_idx + 25)

    x = np.arange(fit_start, fit_end)
    y = search_region[fit_start:fit_end]

    try:
        spline = UnivariateSpline(x, y, s=smoothing)

        # Find minimum of spline
        x_fine = np.linspace(fit_start, fit_end, 1000)
        y_fine = spline(x_fine)
        min_fine_idx = np.argmin(y_fine)

        return float(SEARCH_START + x_fine[min_fine_idx])
    except:
        return float(SEARCH_START + min_idx)


def analyze_with_all_methods(data: dict):
    """Process data with baseline and optimal pipeline, test all peak-finding methods."""
    print("\n" + "=" * 80)
    print("OPTIMAL PIPELINE DEMONSTRATION - CHANNEL A")
    print("=" * 80 + "\n")

    n_spectra = len(data["s_spectra"])
    print(f"Processing {n_spectra} spectra...\n")

    # Define peak-finding methods
    methods = {
        "direct": ("Direct Minimum", find_minimum_direct),
        "polynomial": ("Polynomial Fit", find_minimum_polynomial),
        "centroid": ("Centroid", find_minimum_centroid),
        "gaussian": ("Gaussian Fit", find_minimum_gaussian),
        "spline": ("Spline Interpolation", find_minimum_spline),
    }

    # Process with baseline (no denoising)
    print("=" * 80)
    print("BASELINE PROCESSING (no denoising)")
    print("=" * 80)

    baseline_results = {}

    for method_name, (method_desc, method_func) in methods.items():
        print(f"\n{method_desc}...")
        start_time = time.time()

        positions = np.zeros(n_spectra)

        for i in range(n_spectra):
            transmission = process_baseline(
                data["s_spectra"][i],
                data["p_spectra"][i],
                data["s_dark"],
                data["p_dark"],
            )
            positions[i] = method_func(transmission)

        proc_time = (time.time() - start_time) / n_spectra * 1000

        p2p = np.ptp(positions)
        mean_pos = np.mean(positions)
        std_pos = np.std(positions)

        baseline_results[method_name] = {
            "description": method_desc,
            "positions": positions,
            "p2p": p2p,
            "mean": mean_pos,
            "std": std_pos,
            "proc_time": proc_time,
        }

        print(f"  Peak-to-peak: {p2p:.2f} px")
        print(f"  Mean: {mean_pos:.2f} px")
        print(f"  Std: {std_pos:.2f} px")
        print(f"  Processing: {proc_time:.3f} ms/spectrum")

    # Process with optimal pipeline
    print("\n" + "=" * 80)
    print("OPTIMAL PIPELINE (dark → denoise S&P → transmission)")
    print("=" * 80)

    optimal_results = {}

    for method_name, (method_desc, method_func) in methods.items():
        print(f"\n{method_desc}...")
        start_time = time.time()

        positions = np.zeros(n_spectra)

        for i in range(n_spectra):
            transmission = process_optimal_pipeline(
                data["s_spectra"][i],
                data["p_spectra"][i],
                data["s_dark"],
                data["p_dark"],
            )
            positions[i] = method_func(transmission)

        proc_time = (time.time() - start_time) / n_spectra * 1000

        p2p = np.ptp(positions)
        mean_pos = np.mean(positions)
        std_pos = np.std(positions)

        optimal_results[method_name] = {
            "description": method_desc,
            "positions": positions,
            "p2p": p2p,
            "mean": mean_pos,
            "std": std_pos,
            "proc_time": proc_time,
        }

        print(f"  Peak-to-peak: {p2p:.2f} px")
        print(f"  Mean: {mean_pos:.2f} px")
        print(f"  Std: {std_pos:.2f} px")
        print(f"  Processing: {proc_time:.3f} ms/spectrum")

    # Summary comparison
    print("\n" + "=" * 80)
    print("IMPROVEMENT SUMMARY")
    print("=" * 80 + "\n")

    print(
        f"{'Method':<20} {'Baseline (px)':<15} {'Optimal (px)':<15} {'Improvement':<15}",
    )
    print("-" * 80)

    for method_name in methods:
        baseline_p2p = baseline_results[method_name]["p2p"]
        optimal_p2p = optimal_results[method_name]["p2p"]
        improvement = (baseline_p2p - optimal_p2p) / baseline_p2p * 100

        print(
            f"{methods[method_name][0]:<20} {baseline_p2p:<15.2f} {optimal_p2p:<15.2f} {improvement:>+13.1f}%",
        )

    # Find best method
    best_baseline = min(baseline_results.items(), key=lambda x: x[1]["p2p"])
    best_optimal = min(optimal_results.items(), key=lambda x: x[1]["p2p"])

    print(
        f"\n🏆 BEST BASELINE: {methods[best_baseline[0]][0]} → {best_baseline[1]['p2p']:.2f} px",
    )
    print(
        f"🏆 BEST OPTIMAL: {methods[best_optimal[0]][0]} → {best_optimal[1]['p2p']:.2f} px",
    )
    print(
        f"\n   Overall improvement: {(best_baseline[1]['p2p'] - best_optimal[1]['p2p']) / best_baseline[1]['p2p'] * 100:+.1f}%",
    )

    # Create visualization
    print(f"\n{'='*80}")
    print("Generating visualization...")
    create_comprehensive_visualization(baseline_results, optimal_results, methods, data)

    return baseline_results, optimal_results


def create_comprehensive_visualization(
    baseline_results,
    optimal_results,
    methods,
    data,
):
    """Create comprehensive comparison visualization."""
    fig = plt.figure(figsize=(20, 14))

    colors = {
        "direct": "#e74c3c",
        "polynomial": "#3498db",
        "centroid": "#2ecc71",
        "gaussian": "#f39c12",
        "spline": "#9b59b6",
    }

    # Row 1: Baseline sensorgrams (5 methods)
    for idx, (method_name, result) in enumerate(baseline_results.items(), 1):
        ax = plt.subplot(4, 5, idx)

        positions = result["positions"]
        times = np.arange(len(positions)) / 4.0

        ax.plot(times, positions, color=colors[method_name], linewidth=1.5, alpha=0.8)
        ax.set_ylabel("Position (px)", fontsize=9)
        ax.set_title(
            f"BASELINE: {result['description']}\nP-P: {result['p2p']:.1f} px",
            fontsize=10,
            fontweight="bold",
        )
        ax.grid(True, alpha=0.3)

        if idx == 1:
            ax.text(
                -0.15,
                0.5,
                "NO DENOISING",
                transform=ax.transAxes,
                fontsize=12,
                fontweight="bold",
                rotation=90,
                verticalalignment="center",
                color="red",
            )

    # Row 2: Optimal pipeline sensorgrams (5 methods)
    for idx, (method_name, result) in enumerate(optimal_results.items(), 1):
        ax = plt.subplot(4, 5, 5 + idx)

        positions = result["positions"]
        times = np.arange(len(positions)) / 4.0

        ax.plot(times, positions, color=colors[method_name], linewidth=1.5, alpha=0.8)
        ax.set_ylabel("Position (px)", fontsize=9)
        ax.set_title(
            f"OPTIMAL: {result['description']}\nP-P: {result['p2p']:.1f} px",
            fontsize=10,
            fontweight="bold",
        )
        ax.grid(True, alpha=0.3)

        if idx == 1:
            ax.text(
                -0.15,
                0.5,
                "WITH DENOISING",
                transform=ax.transAxes,
                fontsize=12,
                fontweight="bold",
                rotation=90,
                verticalalignment="center",
                color="green",
            )

    # Row 3: Direct comparison for each method
    for idx, method_name in enumerate(methods.keys(), 1):
        ax = plt.subplot(4, 5, 10 + idx)

        baseline_pos = baseline_results[method_name]["positions"]
        optimal_pos = optimal_results[method_name]["positions"]
        times = np.arange(len(baseline_pos)) / 4.0

        ax.plot(
            times,
            baseline_pos,
            color=colors[method_name],
            linewidth=1.5,
            alpha=0.5,
            linestyle="--",
            label="Baseline",
        )
        ax.plot(
            times,
            optimal_pos,
            color=colors[method_name],
            linewidth=2,
            alpha=0.9,
            label="Optimal",
        )

        baseline_p2p = baseline_results[method_name]["p2p"]
        optimal_p2p = optimal_results[method_name]["p2p"]
        improvement = (baseline_p2p - optimal_p2p) / baseline_p2p * 100

        ax.set_xlabel("Time (s)", fontsize=9)
        ax.set_ylabel("Position (px)", fontsize=9)
        ax.set_title(
            f"{methods[method_name][0]}\n{improvement:+.1f}% improvement",
            fontsize=10,
            fontweight="bold",
            color="green" if improvement > 20 else "orange",
        )
        ax.legend(fontsize=8, loc="best")
        ax.grid(True, alpha=0.3)

    # Row 4: Summary statistics

    # Comparison bar chart
    ax16 = plt.subplot(4, 5, 16)
    method_names = list(methods.keys())
    baseline_p2p = [baseline_results[m]["p2p"] for m in method_names]
    optimal_p2p = [optimal_results[m]["p2p"] for m in method_names]

    x = np.arange(len(method_names))
    width = 0.35

    ax16.bar(
        x - width / 2,
        baseline_p2p,
        width,
        label="Baseline",
        color=[colors[m] for m in method_names],
        alpha=0.5,
    )
    ax16.bar(
        x + width / 2,
        optimal_p2p,
        width,
        label="Optimal",
        color=[colors[m] for m in method_names],
        alpha=0.9,
    )

    ax16.set_ylabel("Peak-to-Peak (px)", fontsize=10)
    ax16.set_title("Performance Comparison", fontsize=11, fontweight="bold")
    ax16.set_xticks(x)
    ax16.set_xticklabels(
        [methods[m][0].split()[0] for m in method_names],
        fontsize=9,
        rotation=45,
        ha="right",
    )
    ax16.legend(fontsize=9)
    ax16.grid(True, alpha=0.3, axis="y")

    # Improvement percentages
    ax17 = plt.subplot(4, 5, 17)
    improvements = [
        (baseline_results[m]["p2p"] - optimal_results[m]["p2p"])
        / baseline_results[m]["p2p"]
        * 100
        for m in method_names
    ]

    bars = ax17.bar(x, improvements, color=[colors[m] for m in method_names], alpha=0.8)

    for i, v in enumerate(improvements):
        ax17.text(
            i,
            v + 1,
            f"{v:+.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )

    ax17.set_ylabel("Improvement (%)", fontsize=10)
    ax17.set_title("Noise Reduction", fontsize=11, fontweight="bold")
    ax17.set_xticks(x)
    ax17.set_xticklabels(
        [methods[m][0].split()[0] for m in method_names],
        fontsize=9,
        rotation=45,
        ha="right",
    )
    ax17.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax17.grid(True, alpha=0.3, axis="y")

    # Processing time comparison
    ax18 = plt.subplot(4, 5, 18)
    baseline_times = [baseline_results[m]["proc_time"] for m in method_names]
    optimal_times = [optimal_results[m]["proc_time"] for m in method_names]

    ax18.bar(x - width / 2, baseline_times, width, label="Baseline", alpha=0.5)
    ax18.bar(x + width / 2, optimal_times, width, label="Optimal", alpha=0.9)

    ax18.axhline(y=10.0, color="red", linestyle="--", linewidth=2, label="10ms budget")

    ax18.set_ylabel("Processing Time (ms)", fontsize=10)
    ax18.set_title("Speed Comparison", fontsize=11, fontweight="bold")
    ax18.set_xticks(x)
    ax18.set_xticklabels(
        [methods[m][0].split()[0] for m in method_names],
        fontsize=9,
        rotation=45,
        ha="right",
    )
    ax18.legend(fontsize=8)
    ax18.grid(True, alpha=0.3, axis="y")

    # Example spectra comparison
    ax19 = plt.subplot(4, 5, 19)

    # Get middle spectrum
    mid_idx = len(data["s_spectra"]) // 2

    baseline_trans = process_baseline(
        data["s_spectra"][mid_idx],
        data["p_spectra"][mid_idx],
        data["s_dark"],
        data["p_dark"],
    )

    optimal_trans = process_optimal_pipeline(
        data["s_spectra"][mid_idx],
        data["p_spectra"][mid_idx],
        data["s_dark"],
        data["p_dark"],
    )

    pixels = np.arange(SEARCH_START, SEARCH_END)
    ax19.plot(
        pixels,
        baseline_trans[SEARCH_START:SEARCH_END],
        "r-",
        linewidth=1.5,
        alpha=0.5,
        label="Baseline",
    )
    ax19.plot(
        pixels,
        optimal_trans[SEARCH_START:SEARCH_END],
        "g-",
        linewidth=2,
        alpha=0.8,
        label="Optimal",
    )

    ax19.set_xlabel("Pixel Position", fontsize=10)
    ax19.set_ylabel("Transmission", fontsize=10)
    ax19.set_title(
        "Example Spectrum\n(middle time point)",
        fontsize=11,
        fontweight="bold",
    )
    ax19.legend(fontsize=9)
    ax19.grid(True, alpha=0.3)

    # Recommendation box
    ax20 = plt.subplot(4, 5, 20)
    ax20.axis("off")

    best_baseline = min(baseline_results.items(), key=lambda x: x[1]["p2p"])
    best_optimal = min(optimal_results.items(), key=lambda x: x[1]["p2p"])

    overall_improvement = (
        (best_baseline[1]["p2p"] - best_optimal[1]["p2p"])
        / best_baseline[1]["p2p"]
        * 100
    )

    recommendation = f"""
RECOMMENDATION:

PIPELINE:
dark → denoise S&P → transmission

DENOISING:
Savitzky-Golay (w=51, p=3)

PEAK FINDING:
{methods[best_optimal[0]][0]}

PERFORMANCE:
Baseline: {best_baseline[1]['p2p']:.1f} px
Optimal: {best_optimal[1]['p2p']:.1f} px
Improvement: {overall_improvement:+.1f}%

Processing: {best_optimal[1]['proc_time']:.2f} ms
Status: {'PASS' if best_optimal[1]['proc_time'] < 10 else 'FAIL'}
    """

    ax20.text(
        0.5,
        0.5,
        recommendation,
        transform=ax20.transAxes,
        fontsize=10,
        verticalalignment="center",
        horizontalalignment="center",
        family="monospace",
        bbox=dict(boxstyle="round", facecolor="lightgreen", alpha=0.4, pad=1.5),
    )

    plt.suptitle(
        "Optimal Processing Pipeline Demonstration - Channel A\n"
        "Comparing Baseline vs. Optimal Pipeline with All Peak-Finding Methods",
        fontsize=16,
        fontweight="bold",
        y=0.995,
    )

    plt.tight_layout(rect=[0, 0, 1, 0.99])

    output_file = OUTPUT_DIR / "complete_pipeline_comparison_channel_A.png"
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    print(f"✓ Saved: {output_file}")

    plt.close()


def main():
    """Main execution."""
    print("\n" + "=" * 80)
    print("OPTIMAL PIPELINE FINAL DEMONSTRATION")
    print("=" * 80)
    print("\nComparing:")
    print("  1. Baseline (no denoising)")
    print("  2. Optimal pipeline (dark → denoise S&P → transmission)")
    print("\nTesting all peak-finding methods:")
    print("  • Direct minimum")
    print("  • Polynomial fit")
    print("  • Centroid")
    print("  • Gaussian fit")
    print("  • Spline interpolation")

    channel = "channel_A"

    print(f"\nLoading {channel} data...")
    data = load_data(channel)

    print(f"✓ Loaded {len(data['s_spectra'])} spectra")

    # Run analysis
    baseline_results, optimal_results = analyze_with_all_methods(data)

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\nResults saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
