"""Test optimal order of data processing operations.

Compare different processing sequences:
1. afterglow → dark → denoise S&P → transmission
2. dark → afterglow → denoise S&P → transmission
3. dark → denoise S&P → afterglow → transmission
4. dark → denoise S&P → transmission (no afterglow)
5. dark → transmission (baseline, no processing)

Also test: Should we denoise dark spectrum?

Goal: Find optimal sequence for best noise reduction.
"""

import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import savgol_filter

# Configuration
DEVICE_NAME = "demo P4SPR 2.0"
SENSOR_STATE = "used"
S_TIMESTAMP = "20251022_140707"
P_TIMESTAMP = "20251022_140940"

BASE_DIR = Path("spectral_training_data") / DEVICE_NAME
S_DIR = BASE_DIR / "s" / SENSOR_STATE / S_TIMESTAMP
P_DIR = BASE_DIR / "p" / SENSOR_STATE / P_TIMESTAMP
OUTPUT_DIR = Path("analysis_results/processing_order")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Denoising parameters
SAVGOL_WINDOW = 51
SAVGOL_POLYORDER = 3


def load_data(channel: str) -> dict:
    """Load all data including afterglow."""
    data = {}

    # S-mode
    s_file = S_DIR / f"{channel}.npz"
    if s_file.exists():
        s_data = np.load(s_file)
        data["s_spectra"] = s_data["spectra"]
        data["s_dark"] = s_data["dark"].squeeze()
        data["s_timestamps"] = s_data["timestamps"]
        # Check for afterglow
        if "afterglow" in s_data:
            data["s_afterglow"] = s_data["afterglow"].squeeze()
        else:
            data["s_afterglow"] = np.zeros_like(data["s_dark"])

    # P-mode
    p_file = P_DIR / f"{channel}.npz"
    if p_file.exists():
        p_data = np.load(p_file)
        data["p_spectra"] = p_data["spectra"]
        data["p_dark"] = p_data["dark"].squeeze()
        data["p_timestamps"] = p_data["timestamps"]
        # Check for afterglow
        if "afterglow" in p_data:
            data["p_afterglow"] = p_data["afterglow"].squeeze()
        else:
            data["p_afterglow"] = np.zeros_like(data["p_dark"])

    return data


def denoise_spectrum(spectrum: np.ndarray) -> np.ndarray:
    """Apply Savitzky-Golay filter."""
    return savgol_filter(spectrum, SAVGOL_WINDOW, SAVGOL_POLYORDER)


def apply_afterglow_correction(
    spectrum: np.ndarray,
    afterglow: np.ndarray,
) -> np.ndarray:
    """Apply afterglow correction."""
    return spectrum - afterglow


def apply_dark_correction(spectrum: np.ndarray, dark: np.ndarray) -> np.ndarray:
    """Apply dark subtraction."""
    return spectrum - dark


def calculate_transmission(p: np.ndarray, s: np.ndarray) -> np.ndarray:
    """Calculate transmission spectrum."""
    s_safe = np.where(s < 1, 1, s)
    return p / s_safe


def find_minimum_position(
    spectrum: np.ndarray,
    search_start: int = 400,
    search_end: int = 1400,
) -> float:
    """Find minimum position."""
    search_end = min(search_end, len(spectrum))
    if search_start >= search_end:
        search_start = 0

    search_region = spectrum[search_start:search_end]
    if len(search_region) == 0:
        return float(len(spectrum) // 2)

    min_idx = np.argmin(search_region)
    return float(search_start + min_idx)


def process_sequence_1(data: dict) -> tuple[np.ndarray, float, str]:
    """Sequence 1: afterglow → dark → denoise S&P → transmission"""
    description = "afterglow → dark → denoise S&P → transmission"
    start_time = time.time()

    n_spectra = len(data["s_spectra"])
    positions = np.zeros(n_spectra)

    for i in range(n_spectra):
        # 1. Afterglow correction
        s_corr = apply_afterglow_correction(data["s_spectra"][i], data["s_afterglow"])
        p_corr = apply_afterglow_correction(data["p_spectra"][i], data["p_afterglow"])

        # 2. Dark correction
        s_corr = apply_dark_correction(s_corr, data["s_dark"])
        p_corr = apply_dark_correction(p_corr, data["p_dark"])

        # 3. Denoise
        s_corr = denoise_spectrum(s_corr)
        p_corr = denoise_spectrum(p_corr)

        # 4. Transmission
        transmission = calculate_transmission(p_corr, s_corr)
        positions[i] = find_minimum_position(transmission)

    proc_time = (time.time() - start_time) / n_spectra * 1000
    return positions, proc_time, description


def process_sequence_2(data: dict) -> tuple[np.ndarray, float, str]:
    """Sequence 2: dark → afterglow → denoise S&P → transmission"""
    description = "dark → afterglow → denoise S&P → transmission"
    start_time = time.time()

    n_spectra = len(data["s_spectra"])
    positions = np.zeros(n_spectra)

    for i in range(n_spectra):
        # 1. Dark correction
        s_corr = apply_dark_correction(data["s_spectra"][i], data["s_dark"])
        p_corr = apply_dark_correction(data["p_spectra"][i], data["p_dark"])

        # 2. Afterglow correction
        s_corr = apply_afterglow_correction(s_corr, data["s_afterglow"])
        p_corr = apply_afterglow_correction(p_corr, data["p_afterglow"])

        # 3. Denoise
        s_corr = denoise_spectrum(s_corr)
        p_corr = denoise_spectrum(p_corr)

        # 4. Transmission
        transmission = calculate_transmission(p_corr, s_corr)
        positions[i] = find_minimum_position(transmission)

    proc_time = (time.time() - start_time) / n_spectra * 1000
    return positions, proc_time, description


def process_sequence_3(data: dict) -> tuple[np.ndarray, float, str]:
    """Sequence 3: dark → denoise S&P → afterglow → transmission"""
    description = "dark → denoise S&P → afterglow → transmission"
    start_time = time.time()

    n_spectra = len(data["s_spectra"])
    positions = np.zeros(n_spectra)

    for i in range(n_spectra):
        # 1. Dark correction
        s_corr = apply_dark_correction(data["s_spectra"][i], data["s_dark"])
        p_corr = apply_dark_correction(data["p_spectra"][i], data["p_dark"])

        # 2. Denoise
        s_corr = denoise_spectrum(s_corr)
        p_corr = denoise_spectrum(p_corr)

        # 3. Afterglow correction
        s_corr = apply_afterglow_correction(s_corr, data["s_afterglow"])
        p_corr = apply_afterglow_correction(p_corr, data["p_afterglow"])

        # 4. Transmission
        transmission = calculate_transmission(p_corr, s_corr)
        positions[i] = find_minimum_position(transmission)

    proc_time = (time.time() - start_time) / n_spectra * 1000
    return positions, proc_time, description


def process_sequence_4(data: dict) -> tuple[np.ndarray, float, str]:
    """Sequence 4: dark → denoise S&P → transmission (no afterglow)"""
    description = "dark → denoise S&P → transmission (no afterglow)"
    start_time = time.time()

    n_spectra = len(data["s_spectra"])
    positions = np.zeros(n_spectra)

    for i in range(n_spectra):
        # 1. Dark correction
        s_corr = apply_dark_correction(data["s_spectra"][i], data["s_dark"])
        p_corr = apply_dark_correction(data["p_spectra"][i], data["p_dark"])

        # 2. Denoise
        s_corr = denoise_spectrum(s_corr)
        p_corr = denoise_spectrum(p_corr)

        # 3. Transmission
        transmission = calculate_transmission(p_corr, s_corr)
        positions[i] = find_minimum_position(transmission)

    proc_time = (time.time() - start_time) / n_spectra * 1000
    return positions, proc_time, description


def process_sequence_5(data: dict) -> tuple[np.ndarray, float, str]:
    """Sequence 5: dark → transmission (baseline, no processing)"""
    description = "dark → transmission (baseline)"
    start_time = time.time()

    n_spectra = len(data["s_spectra"])
    positions = np.zeros(n_spectra)

    for i in range(n_spectra):
        # 1. Dark correction only
        s_corr = apply_dark_correction(data["s_spectra"][i], data["s_dark"])
        p_corr = apply_dark_correction(data["p_spectra"][i], data["p_dark"])

        # 2. Transmission
        transmission = calculate_transmission(p_corr, s_corr)
        positions[i] = find_minimum_position(transmission)

    proc_time = (time.time() - start_time) / n_spectra * 1000
    return positions, proc_time, description


def test_dark_denoising(data: dict) -> dict:
    """Test: Should we denoise the dark spectrum?"""
    print("\n" + "=" * 80)
    print("DARK SPECTRUM DENOISING TEST")
    print("=" * 80 + "\n")

    results = {}

    # Test 1: Don't denoise dark
    print("Test 1: Original dark (no denoising)")
    start_time = time.time()
    n_spectra = len(data["s_spectra"])
    positions_1 = np.zeros(n_spectra)

    for i in range(n_spectra):
        s_corr = apply_dark_correction(data["s_spectra"][i], data["s_dark"])
        p_corr = apply_dark_correction(data["p_spectra"][i], data["p_dark"])
        s_corr = denoise_spectrum(s_corr)
        p_corr = denoise_spectrum(p_corr)
        transmission = calculate_transmission(p_corr, s_corr)
        positions_1[i] = find_minimum_position(transmission)

    proc_time_1 = (time.time() - start_time) / n_spectra * 1000
    p2p_1 = np.ptp(positions_1)

    print(f"  Peak-to-peak: {p2p_1:.2f} px")
    print(f"  Processing: {proc_time_1:.3f} ms/spectrum")

    results["original_dark"] = {
        "positions": positions_1,
        "p2p": p2p_1,
        "proc_time": proc_time_1,
        "description": "Original dark (no denoising)",
    }

    # Test 2: Denoise dark
    print("\nTest 2: Denoised dark")
    s_dark_denoised = denoise_spectrum(data["s_dark"])
    p_dark_denoised = denoise_spectrum(data["p_dark"])

    start_time = time.time()
    positions_2 = np.zeros(n_spectra)

    for i in range(n_spectra):
        s_corr = apply_dark_correction(data["s_spectra"][i], s_dark_denoised)
        p_corr = apply_dark_correction(data["p_spectra"][i], p_dark_denoised)
        s_corr = denoise_spectrum(s_corr)
        p_corr = denoise_spectrum(p_corr)
        transmission = calculate_transmission(p_corr, s_corr)
        positions_2[i] = find_minimum_position(transmission)

    proc_time_2 = (time.time() - start_time) / n_spectra * 1000
    p2p_2 = np.ptp(positions_2)

    print(f"  Peak-to-peak: {p2p_2:.2f} px")
    print(f"  Processing: {proc_time_2:.3f} ms/spectrum")

    results["denoised_dark"] = {
        "positions": positions_2,
        "p2p": p2p_2,
        "proc_time": proc_time_2,
        "description": "Denoised dark",
    }

    # Compare
    improvement = (p2p_1 - p2p_2) / p2p_1 * 100
    print(f"\n  → Difference: {improvement:+.1f}%")

    if improvement > 1:
        print("  ✓ Denoising dark is BENEFICIAL")
    elif improvement < -1:
        print("  ✗ Denoising dark is HARMFUL")
    else:
        print("  ≈ Denoising dark has NEGLIGIBLE effect")

    return results


def main():
    """Main execution."""
    print("\n" + "=" * 80)
    print("PROCESSING ORDER OPTIMIZATION")
    print("=" * 80)
    print("\nTesting different sequences of processing operations:")
    print("  • Dark correction")
    print("  • Afterglow correction")
    print("  • Spectral denoising (Savitzky-Golay)")
    print("  • Transmission calculation")

    channel = "channel_A"

    print(f"\nLoading {channel} data...")
    data = load_data(channel)

    if "s_spectra" not in data or "p_spectra" not in data:
        print(f"❌ Missing data for {channel}")
        return

    n_spectra = len(data["s_spectra"])
    print(f"✓ Loaded {n_spectra} spectra")

    # Check if afterglow data exists
    has_afterglow = np.any(data["s_afterglow"] != 0) or np.any(data["p_afterglow"] != 0)
    print(
        f"  Afterglow data: {'✓ Present' if has_afterglow else '✗ Not present (zeros)'}",
    )

    # Test processing sequences
    print("\n" + "=" * 80)
    print("TESTING PROCESSING SEQUENCES")
    print("=" * 80)

    sequences = [
        ("seq1", process_sequence_1),
        ("seq2", process_sequence_2),
        ("seq3", process_sequence_3),
        ("seq4", process_sequence_4),
        ("seq5", process_sequence_5),
    ]

    results = {}

    for seq_name, seq_func in sequences:
        print(f"\n{seq_name}: ", end="")
        positions, proc_time, description = seq_func(data)
        print(description)

        p2p = np.ptp(positions)
        print(f"  Peak-to-peak: {p2p:.2f} px")
        print(f"  Processing: {proc_time:.3f} ms/spectrum")
        print(f"  Status: {'✓ Under budget' if proc_time < 10 else '⚠️ Over budget'}")

        results[seq_name] = {
            "description": description,
            "positions": positions,
            "p2p": p2p,
            "proc_time": proc_time,
        }

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80 + "\n")

    baseline_p2p = results["seq5"]["p2p"]

    sorted_results = sorted(results.items(), key=lambda x: x[1]["p2p"])

    print(f"{'Sequence':<10} {'P-P (px)':<12} {'Improvement':<12} {'Time (ms)':<10}")
    print("-" * 80)

    for seq_name, result in sorted_results:
        p2p = result["p2p"]
        improvement = (baseline_p2p - p2p) / baseline_p2p * 100
        proc_time = result["proc_time"]

        print(f"{seq_name:<10} {p2p:<12.2f} {improvement:>+10.1f}% {proc_time:<10.3f}")

    best_seq = sorted_results[0]
    print(f"\n🏆 BEST: {best_seq[0]}")
    print(f"   {best_seq[1]['description']}")
    print(
        f"   {best_seq[1]['p2p']:.2f} px ({(baseline_p2p - best_seq[1]['p2p']) / baseline_p2p * 100:+.1f}%)",
    )
    print(f"   {best_seq[1]['proc_time']:.3f} ms/spectrum")

    # Test dark denoising
    dark_results = test_dark_denoising(data)

    # Create visualization
    print(f"\n{'='*80}")
    print("Generating visualization...")
    create_visualization(results, dark_results, channel)

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


def create_visualization(results: dict, dark_results: dict, channel: str):
    """Create comprehensive visualization."""
    fig = plt.figure(figsize=(18, 10))

    colors = {
        "seq1": "#e74c3c",
        "seq2": "#3498db",
        "seq3": "#2ecc71",
        "seq4": "#f39c12",
        "seq5": "#95a5a6",
    }

    # Sensorgrams for each sequence
    for idx, (seq_name, result) in enumerate(results.items(), 1):
        ax = plt.subplot(3, 4, idx)
        positions = result["positions"]
        times = np.arange(len(positions)) / 4.0

        ax.plot(times, positions, color=colors[seq_name], linewidth=1.5, alpha=0.8)
        ax.set_xlabel("Time (s)", fontsize=9)
        ax.set_ylabel("Position (px)", fontsize=9)
        ax.set_title(
            f"{seq_name}: {result['p2p']:.0f} px",
            fontsize=10,
            fontweight="bold",
        )
        ax.grid(True, alpha=0.3)

        # Truncate description if too long
        desc_short = result["description"].replace(" → ", "→")
        if len(desc_short) > 30:
            desc_short = desc_short[:27] + "..."
        ax.text(
            0.02,
            0.98,
            desc_short,
            transform=ax.transAxes,
            fontsize=8,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )

    # Comparison bar chart
    ax6 = plt.subplot(3, 4, 6)
    sorted_seqs = sorted(results.items(), key=lambda x: x[1]["p2p"])
    seq_names = [s[0] for s in sorted_seqs]
    p2p_values = [s[1]["p2p"] for s in sorted_seqs]

    bars = ax6.barh(seq_names, p2p_values, color=[colors[s] for s in seq_names])

    baseline = results["seq5"]["p2p"]
    for i, (name, value) in enumerate(zip(seq_names, p2p_values, strict=False)):
        improvement = (baseline - value) / baseline * 100
        ax6.text(
            value + 10,
            i,
            f"{value:.0f} px ({improvement:+.1f}%)",
            va="center",
            fontsize=9,
            fontweight="bold",
        )

    ax6.set_xlabel("Peak-to-Peak (px)", fontsize=10)
    ax6.set_title("Performance Comparison", fontsize=11, fontweight="bold")
    ax6.grid(True, alpha=0.3, axis="x")

    # Dark denoising test
    ax7 = plt.subplot(3, 4, 7)
    dark_names = list(dark_results.keys())
    dark_p2p = [dark_results[k]["p2p"] for k in dark_names]

    bars = ax7.bar(range(len(dark_names)), dark_p2p, color=["#3498db", "#e74c3c"])
    ax7.set_xticks(range(len(dark_names)))
    ax7.set_xticklabels(["Original\nDark", "Denoised\nDark"], fontsize=9)
    ax7.set_ylabel("Peak-to-Peak (px)", fontsize=10)
    ax7.set_title("Dark Denoising Test", fontsize=11, fontweight="bold")
    ax7.grid(True, alpha=0.3, axis="y")

    for i, value in enumerate(dark_p2p):
        ax7.text(
            i,
            value + 5,
            f"{value:.1f} px",
            ha="center",
            fontsize=9,
            fontweight="bold",
        )

    # Processing time comparison
    ax8 = plt.subplot(3, 4, 8)
    proc_times = [results[s]["proc_time"] for s in seq_names]

    bars = ax8.barh(seq_names, proc_times, color=[colors[s] for s in seq_names])
    ax8.axvline(x=10.0, color="red", linestyle="--", linewidth=2, label="10ms budget")

    for i, (name, value) in enumerate(zip(seq_names, proc_times, strict=False)):
        ax8.text(
            value + 0.1,
            i,
            f"{value:.2f} ms",
            va="center",
            fontsize=9,
            fontweight="bold",
        )

    ax8.set_xlabel("Processing Time (ms)", fontsize=10)
    ax8.set_title("Speed Comparison", fontsize=11, fontweight="bold")
    ax8.legend(fontsize=8)
    ax8.grid(True, alpha=0.3, axis="x")

    # Recommendation box
    ax9 = plt.subplot(3, 4, 9)
    ax9.axis("off")

    best = min(results.items(), key=lambda x: x[1]["p2p"])
    baseline = results["seq5"]

    dark_best = min(dark_results.items(), key=lambda x: x[1]["p2p"])
    dark_improvement = (
        (dark_results["original_dark"]["p2p"] - dark_best[1]["p2p"])
        / dark_results["original_dark"]["p2p"]
        * 100
    )

    recommendation = f"""
RECOMMENDED PROCESSING ORDER:

{best[1]['description']}

Performance: {best[1]['p2p']:.0f} px
Improvement: {(baseline['p2p'] - best[1]['p2p']) / baseline['p2p'] * 100:+.1f}%
Speed: {best[1]['proc_time']:.2f} ms

DARK DENOISING:
{'Recommended' if dark_improvement > 1 else 'Not recommended'}
Effect: {dark_improvement:+.1f}%

KEY INSIGHTS:
• Apply corrections before denoising
• Denoise raw spectra (S & P)
• Don't denoise dark unless beneficial
    """

    ax9.text(
        0.5,
        0.5,
        recommendation,
        transform=ax9.transAxes,
        fontsize=10,
        verticalalignment="center",
        horizontalalignment="center",
        family="monospace",
        bbox=dict(boxstyle="round", facecolor="lightgreen", alpha=0.3, pad=1),
    )

    plt.suptitle(
        f"Processing Order Optimization - {channel.upper()}",
        fontsize=14,
        fontweight="bold",
    )
    plt.tight_layout()

    output_file = OUTPUT_DIR / f"processing_order_comparison_{channel}.png"
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    print(f"✓ Saved: {output_file}")
    plt.close()


if __name__ == "__main__":
    main()
