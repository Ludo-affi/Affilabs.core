"""Test where to apply Savitzky-Golay denoising in the data processing chain.

Compare different strategies:
1. denoise_raw_only: Denoise S and P separately BEFORE transmission
2. denoise_transmission: Calculate transmission first, THEN denoise
3. denoise_both: Denoise raw spectra AND denoise transmission
4. denoise_none: No denoising (baseline)

Goal: Find optimal placement for <10ms processing with best noise reduction.
"""

import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import savgol_filter

# Configuration
DEVICE_NAME = "demo P4SPR 2.0"
SENSOR_STATE = "used"
S_TIMESTAMP = "20251022_140707"  # Latest S-mode collection
P_TIMESTAMP = "20251022_140940"  # Latest P-mode collection

BASE_DIR = Path("spectral_training_data") / DEVICE_NAME
S_DIR = BASE_DIR / "s" / SENSOR_STATE / S_TIMESTAMP
P_DIR = BASE_DIR / "p" / SENSOR_STATE / P_TIMESTAMP
OUTPUT_DIR = Path("analysis_results/denoising_placement")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Denoising parameters (winner from previous analysis)
SAVGOL_WINDOW = 51
SAVGOL_POLYORDER = 3


def load_spectral_data(channel: str) -> dict[str, np.ndarray]:
    """Load S-mode and P-mode data for a channel."""
    data = {}

    # Load S-mode
    s_file = S_DIR / f"{channel}.npz"
    if s_file.exists():
        s_data = np.load(s_file)
        data["s_spectra"] = s_data["spectra"]
        data["s_dark"] = s_data["dark"].squeeze()  # Remove extra dimension
        data["s_timestamps"] = s_data["timestamps"]

    # Load P-mode
    p_file = P_DIR / f"{channel}.npz"
    if p_file.exists():
        p_data = np.load(p_file)
        data["p_spectra"] = p_data["spectra"]
        data["p_dark"] = p_data["dark"].squeeze()  # Remove extra dimension
        data["p_timestamps"] = p_data["timestamps"]

    return data


def denoise_savgol(spectrum: np.ndarray) -> np.ndarray:
    """Apply Savitzky-Golay filter."""
    return savgol_filter(spectrum, SAVGOL_WINDOW, SAVGOL_POLYORDER)


def calculate_transmission(
    p_signal: np.ndarray,
    p_dark: np.ndarray,
    s_signal: np.ndarray,
    s_dark: np.ndarray,
) -> np.ndarray:
    """Calculate transmission spectrum."""
    p_corrected = p_signal - p_dark
    s_corrected = s_signal - s_dark

    # Avoid division by zero
    s_corrected = np.where(s_corrected < 1, 1, s_corrected)

    return p_corrected / s_corrected


def find_minimum_position(
    spectrum: np.ndarray,
    search_start: int = 400,
    search_end: int = 1400,
) -> float:
    """Find minimum position in transmission spectrum."""
    # Ensure search region is valid
    search_end = min(search_end, len(spectrum))
    if search_start >= search_end:
        search_start = 0

    search_region = spectrum[search_start:search_end]

    if len(search_region) == 0:
        return float(len(spectrum) // 2)  # Return middle if invalid

    min_idx = np.argmin(search_region)
    return float(search_start + min_idx)


def process_strategy_1_denoise_raw_only(
    data: dict[str, np.ndarray],
) -> tuple[np.ndarray, float]:
    """Strategy 1: Denoise S and P separately BEFORE transmission calculation."""
    start_time = time.time()

    n_spectra = len(data["s_spectra"])
    positions = np.zeros(n_spectra)

    for i in range(n_spectra):
        # Denoise raw spectra
        s_denoised = denoise_savgol(data["s_spectra"][i])
        p_denoised = denoise_savgol(data["p_spectra"][i])

        # Calculate transmission from denoised spectra
        transmission = calculate_transmission(
            p_denoised,
            data["p_dark"],
            s_denoised,
            data["s_dark"],
        )

        # Find minimum
        positions[i] = find_minimum_position(transmission)

    processing_time = (time.time() - start_time) / n_spectra * 1000  # ms per spectrum

    return positions, processing_time


def process_strategy_2_denoise_transmission(
    data: dict[str, np.ndarray],
) -> tuple[np.ndarray, float]:
    """Strategy 2: Calculate transmission FIRST, THEN denoise."""
    start_time = time.time()

    n_spectra = len(data["s_spectra"])
    positions = np.zeros(n_spectra)

    for i in range(n_spectra):
        # Calculate transmission from raw spectra
        transmission = calculate_transmission(
            data["p_spectra"][i],
            data["p_dark"],
            data["s_spectra"][i],
            data["s_dark"],
        )

        # Denoise transmission spectrum
        transmission_denoised = denoise_savgol(transmission)

        # Find minimum
        positions[i] = find_minimum_position(transmission_denoised)

    processing_time = (time.time() - start_time) / n_spectra * 1000  # ms per spectrum

    return positions, processing_time


def process_strategy_3_denoise_both(
    data: dict[str, np.ndarray],
) -> tuple[np.ndarray, float]:
    """Strategy 3: Denoise raw spectra AND denoise transmission."""
    start_time = time.time()

    n_spectra = len(data["s_spectra"])
    positions = np.zeros(n_spectra)

    for i in range(n_spectra):
        # Denoise raw spectra
        s_denoised = denoise_savgol(data["s_spectra"][i])
        p_denoised = denoise_savgol(data["p_spectra"][i])

        # Calculate transmission from denoised spectra
        transmission = calculate_transmission(
            p_denoised,
            data["p_dark"],
            s_denoised,
            data["s_dark"],
        )

        # Denoise transmission again
        transmission_denoised = denoise_savgol(transmission)

        # Find minimum
        positions[i] = find_minimum_position(transmission_denoised)

    processing_time = (time.time() - start_time) / n_spectra * 1000  # ms per spectrum

    return positions, processing_time


def process_strategy_4_denoise_none(
    data: dict[str, np.ndarray],
) -> tuple[np.ndarray, float]:
    """Strategy 4: No denoising (baseline)."""
    start_time = time.time()

    n_spectra = len(data["s_spectra"])
    positions = np.zeros(n_spectra)

    for i in range(n_spectra):
        # Calculate transmission from raw spectra
        transmission = calculate_transmission(
            data["p_spectra"][i],
            data["p_dark"],
            data["s_spectra"][i],
            data["s_dark"],
        )

        # Find minimum
        positions[i] = find_minimum_position(transmission)

    processing_time = (time.time() - start_time) / n_spectra * 1000  # ms per spectrum

    return positions, processing_time


def analyze_denoising_placement(channel: str = "channel_A"):
    """Test all denoising placement strategies."""
    print(f"\n{'='*80}")
    print(f"DENOISING PLACEMENT ANALYSIS - {channel.upper()}")
    print(f"{'='*80}\n")

    # Load data
    print("Loading data...")
    data = load_spectral_data(channel)

    if "s_spectra" not in data or "p_spectra" not in data:
        print(f"❌ Missing data for {channel}")
        return None

    n_spectra = len(data["s_spectra"])
    print(f"✓ Loaded {n_spectra} spectra\n")

    # Test all strategies
    strategies = {
        "denoise_raw_only": (
            "Denoise S & P → Calculate T",
            process_strategy_1_denoise_raw_only,
        ),
        "denoise_transmission": (
            "Calculate T → Denoise T",
            process_strategy_2_denoise_transmission,
        ),
        "denoise_both": (
            "Denoise S & P → Calculate T → Denoise T",
            process_strategy_3_denoise_both,
        ),
        "denoise_none": ("No denoising (baseline)", process_strategy_4_denoise_none),
    }

    results = {}

    print("Testing denoising placement strategies...")
    print("-" * 80)

    for strategy_name, (description, func) in strategies.items():
        print(f"\n{strategy_name}: {description}")
        positions, proc_time = func(data)

        # Calculate statistics
        p2p = np.ptp(positions)
        mean_pos = np.mean(positions)
        std_pos = np.std(positions)

        results[strategy_name] = {
            "description": description,
            "positions": positions,
            "p2p": p2p,
            "mean": mean_pos,
            "std": std_pos,
            "processing_time": proc_time,
        }

        print(f"  Peak-to-peak: {p2p:.2f} px")
        print(f"  Mean position: {mean_pos:.2f} px")
        print(f"  Std deviation: {std_pos:.2f} px")
        print(f"  Processing time: {proc_time:.3f} ms/spectrum")

        # Check if within budget
        if proc_time < 10.0:
            print("  ✓ Within 10ms budget")
        else:
            print("  ⚠️ Exceeds 10ms budget")

    # Print summary comparison
    print(f"\n{'='*80}")
    print("SUMMARY COMPARISON")
    print(f"{'='*80}\n")

    baseline_p2p = results["denoise_none"]["p2p"]

    print(
        f"{'Strategy':<30} {'P-P (px)':<12} {'Improvement':<12} {'Time (ms)':<10} {'Status'}",
    )
    print("-" * 80)

    # Sort by p2p (best first)
    sorted_strategies = sorted(results.items(), key=lambda x: x[1]["p2p"])

    for strategy_name, result in sorted_strategies:
        p2p = result["p2p"]
        improvement = (baseline_p2p - p2p) / baseline_p2p * 100
        proc_time = result["processing_time"]

        status = "✓" if proc_time < 10.0 else "⚠️"

        print(
            f"{strategy_name:<30} {p2p:<12.2f} {improvement:>+10.1f}% {proc_time:<10.3f} {status}",
        )

    print()

    # Find best strategy
    best_strategy = sorted_strategies[0][0]
    best_result = sorted_strategies[0][1]

    print(f"\n🏆 RECOMMENDED STRATEGY: {best_strategy}")
    print(f"   {best_result['description']}")
    print(
        f"   Peak-to-peak: {best_result['p2p']:.2f} px ({(baseline_p2p - best_result['p2p']) / baseline_p2p * 100:+.1f}%)",
    )
    print(f"   Processing time: {best_result['processing_time']:.3f} ms/spectrum")

    # Create visualizations
    print("\nGenerating visualizations...")
    create_visualizations(results, channel)

    return results


def create_visualizations(results: dict, channel: str):
    """Create comprehensive visualization of denoising placement strategies."""
    fig = plt.figure(figsize=(16, 12))

    # Color scheme
    colors = {
        "denoise_raw_only": "#2ecc71",  # Green (best from previous)
        "denoise_transmission": "#3498db",  # Blue
        "denoise_both": "#9b59b6",  # Purple
        "denoise_none": "#e74c3c",  # Red (baseline)
    }

    # 1. Sensorgrams comparison (2x2 grid)
    for idx, (strategy_name, result) in enumerate(results.items()):
        ax = plt.subplot(3, 3, idx + 1)

        positions = result["positions"]
        times = np.arange(len(positions)) / 4.0  # 4 Hz sampling

        ax.plot(times, positions, color=colors[strategy_name], linewidth=1.5, alpha=0.8)
        ax.set_xlabel("Time (s)", fontsize=10)
        ax.set_ylabel("Resonance Position (px)", fontsize=10)
        ax.set_title(
            f"{strategy_name}\nP-P: {result['p2p']:.1f} px",
            fontsize=11,
            fontweight="bold",
        )
        ax.grid(True, alpha=0.3)

        # Add stats box
        stats_text = f"μ={result['mean']:.1f}\nσ={result['std']:.1f}\nt={result['processing_time']:.2f}ms"
        ax.text(
            0.98,
            0.97,
            stats_text,
            transform=ax.transAxes,
            fontsize=9,
            verticalalignment="top",
            horizontalalignment="right",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )

    # 5. Peak-to-peak comparison bar chart
    ax5 = plt.subplot(3, 3, 5)

    strategies_sorted = sorted(results.items(), key=lambda x: x[1]["p2p"])
    strategy_names = [s[0] for s in strategies_sorted]
    p2p_values = [s[1]["p2p"] for s in strategies_sorted]

    bars = ax5.barh(
        strategy_names,
        p2p_values,
        color=[colors[s] for s in strategy_names],
    )

    # Add value labels
    for i, (name, value) in enumerate(zip(strategy_names, p2p_values, strict=False)):
        baseline = results["denoise_none"]["p2p"]
        improvement = (baseline - value) / baseline * 100
        ax5.text(
            value + 2,
            i,
            f"{value:.1f} px ({improvement:+.1f}%)",
            va="center",
            fontsize=10,
            fontweight="bold",
        )

    ax5.set_xlabel("Peak-to-Peak Variation (pixels)", fontsize=10)
    ax5.set_title("Noise Reduction Performance", fontsize=11, fontweight="bold")
    ax5.grid(True, alpha=0.3, axis="x")

    # 6. Processing time comparison
    ax6 = plt.subplot(3, 3, 6)

    proc_times = [results[s]["processing_time"] for s in strategy_names]
    bars = ax6.barh(
        strategy_names,
        proc_times,
        color=[colors[s] for s in strategy_names],
    )

    # Add value labels and budget line
    for i, (name, value) in enumerate(zip(strategy_names, proc_times, strict=False)):
        ax6.text(
            value + 0.1,
            i,
            f"{value:.2f} ms",
            va="center",
            fontsize=10,
            fontweight="bold",
        )

    ax6.axvline(x=10.0, color="red", linestyle="--", linewidth=2, label="10ms budget")
    ax6.set_xlabel("Processing Time (ms/spectrum)", fontsize=10)
    ax6.set_title("Processing Speed", fontsize=11, fontweight="bold")
    ax6.legend(fontsize=9)
    ax6.grid(True, alpha=0.3, axis="x")

    # 7. Trade-off scatter plot
    ax7 = plt.subplot(3, 3, 7)

    for strategy_name, result in results.items():
        ax7.scatter(
            result["processing_time"],
            result["p2p"],
            s=200,
            color=colors[strategy_name],
            label=strategy_name,
            alpha=0.7,
            edgecolors="black",
            linewidth=2,
        )

    # Mark budget constraint
    ax7.axvline(x=10.0, color="red", linestyle="--", alpha=0.5, label="10ms budget")

    ax7.set_xlabel("Processing Time (ms/spectrum)", fontsize=10)
    ax7.set_ylabel("Peak-to-Peak Variation (px)", fontsize=10)
    ax7.set_title("Performance Trade-off", fontsize=11, fontweight="bold")
    ax7.legend(fontsize=8, loc="best")
    ax7.grid(True, alpha=0.3)

    # Annotate best point
    best_strategy = min(results.items(), key=lambda x: x[1]["p2p"])
    ax7.annotate(
        "BEST",
        xy=(best_strategy[1]["processing_time"], best_strategy[1]["p2p"]),
        xytext=(10, 10),
        textcoords="offset points",
        fontsize=12,
        fontweight="bold",
        color="green",
        arrowprops=dict(arrowstyle="->", color="green", lw=2),
    )

    # 8. Improvement vs baseline
    ax8 = plt.subplot(3, 3, 8)

    baseline_p2p = results["denoise_none"]["p2p"]
    improvements = [
        (baseline_p2p - results[s]["p2p"]) / baseline_p2p * 100
        for s in strategy_names
        if s != "denoise_none"
    ]
    strategy_names_no_baseline = [s for s in strategy_names if s != "denoise_none"]

    bars = ax8.barh(
        strategy_names_no_baseline,
        improvements,
        color=[colors[s] for s in strategy_names_no_baseline],
    )

    # Add value labels
    for i, (name, value) in enumerate(
        zip(strategy_names_no_baseline, improvements, strict=False),
    ):
        ax8.text(
            value + 1,
            i,
            f"{value:+.1f}%",
            va="center",
            fontsize=10,
            fontweight="bold",
        )

    ax8.set_xlabel("Improvement vs. Baseline (%)", fontsize=10)
    ax8.set_title("Noise Reduction Gain", fontsize=11, fontweight="bold")
    ax8.grid(True, alpha=0.3, axis="x")

    # 9. Recommendation box
    ax9 = plt.subplot(3, 3, 9)
    ax9.axis("off")

    best_strategy_name = min(results.items(), key=lambda x: x[1]["p2p"])[0]
    best = results[best_strategy_name]
    baseline = results["denoise_none"]

    recommendation = f"""
    🏆 RECOMMENDED STRATEGY

    {best_strategy_name}
    {best['description']}

    PERFORMANCE:
    • Peak-to-peak: {best['p2p']:.1f} px
    • Improvement: {(baseline['p2p'] - best['p2p']) / baseline['p2p'] * 100:+.1f}%
    • Processing: {best['processing_time']:.3f} ms/spectrum
    • Budget status: {'✓ PASS' if best['processing_time'] < 10 else '⚠️ EXCEEDS'}

    BASELINE (no denoising):
    • Peak-to-peak: {baseline['p2p']:.1f} px
    • Processing: {baseline['processing_time']:.3f} ms/spectrum

    REASON:
    Best noise reduction while maintaining
    fast processing within 10ms budget.
    """

    ax9.text(
        0.5,
        0.5,
        recommendation,
        transform=ax9.transAxes,
        fontsize=11,
        verticalalignment="center",
        horizontalalignment="center",
        family="monospace",
        bbox=dict(boxstyle="round", facecolor="lightgreen", alpha=0.3, pad=1),
    )

    plt.suptitle(
        f"Denoising Placement Strategy Comparison - {channel.upper()}\n"
        f"Savitzky-Golay Filter (window={SAVGOL_WINDOW}, polyorder={SAVGOL_POLYORDER})",
        fontsize=14,
        fontweight="bold",
        y=0.995,
    )

    plt.tight_layout()

    # Save figure
    output_file = OUTPUT_DIR / f"denoising_placement_comparison_{channel}.png"
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    print(f"✓ Saved: {output_file}")

    plt.close()


def main():
    """Main execution."""
    print("\n" + "=" * 80)
    print("DENOISING PLACEMENT OPTIMIZATION")
    print("=" * 80)
    print("\nTesting where to apply Savitzky-Golay denoising in the data chain:")
    print("  1. Denoise raw spectra (S & P) → Calculate transmission")
    print("  2. Calculate transmission → Denoise transmission")
    print("  3. Denoise raw spectra → Calculate transmission → Denoise again")
    print("  4. No denoising (baseline)")
    print("\nGoal: Minimize noise while staying under 10ms processing budget")

    # Analyze channel A
    results = analyze_denoising_placement("channel_A")

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\nResults saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
