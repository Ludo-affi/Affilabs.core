"""LED Drift Characterization and Correction using S-mode data.

S-mode (reference polarization) captures LED spectral characteristics without
sensor resonance interference. By analyzing S-mode temporal trends, we can:
1. Characterize LED drift over the measurement period
2. Model the drift (linear, exponential, etc.)
3. Correct P-mode data for LED variations
4. Improve transmission spectrum stability

This reduces the ~86 px p-p variation in sensorgram by removing LED-induced artifacts.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit

# Data paths
BASE_DIR = Path("spectral_training_data/demo P4SPR 2.0")
S_MODE_DIR = BASE_DIR / "s" / "used"
P_MODE_DIR = BASE_DIR / "p" / "used"
OUTPUT_DIR = Path("analysis_results") / "led_drift_correction"


def find_latest_data_dir(base_path: Path) -> Path:
    """Find the most recent data collection directory."""
    timestamp_dirs = sorted([d for d in base_path.iterdir() if d.is_dir()])
    return timestamp_dirs[-1]


def load_channel_data(data_dir: Path, channel: str = "A") -> dict:
    """Load NPZ data for a specific channel."""
    npz_file = data_dir / f"channel_{channel}.npz"
    data = np.load(npz_file)
    return {
        "spectra": data["spectra"],
        "dark": data["dark"],
        "timestamps": data["timestamps"],
    }


def analyze_s_mode_drift(s_data: dict) -> dict:
    """Analyze temporal drift in S-mode spectra.

    Returns:
        drift_analysis: Dictionary with drift characteristics

    """
    spectra = s_data["spectra"]  # (N_time, N_wavelength)
    dark = s_data["dark"][0]
    timestamps = s_data["timestamps"]

    # Dark-correct S-mode spectra
    s_corrected = spectra - dark

    print("\n📊 S-MODE DRIFT ANALYSIS")
    print("=" * 70)

    # 1. Overall intensity drift (sum across all wavelengths)
    total_intensity = np.sum(s_corrected, axis=1)

    drift_percent = (
        (total_intensity[-1] - total_intensity[0]) / total_intensity[0] * 100
    )
    print(f"\nTotal intensity drift over {timestamps[-1]:.1f}s:")
    print(f"  Start: {total_intensity[0]:.0f} counts")
    print(f"  End: {total_intensity[-1]:.0f} counts")
    print(f"  Drift: {drift_percent:+.2f}%")

    # 2. Per-pixel drift analysis
    pixel_drift = (s_corrected[-1] - s_corrected[0]) / s_corrected[0] * 100

    print("\nPer-pixel drift statistics:")
    print(f"  Mean: {np.mean(pixel_drift):+.2f}%")
    print(f"  Std: {np.std(pixel_drift):.2f}%")
    print(f"  Range: {np.min(pixel_drift):+.2f}% to {np.max(pixel_drift):+.2f}%")

    # 3. Spectral shape changes (normalize by intensity)
    s_normalized = s_corrected / np.sum(s_corrected, axis=1, keepdims=True)

    shape_drift = np.std(s_normalized, axis=0)
    print("\nSpectral shape stability:")
    print(f"  Mean shape std: {np.mean(shape_drift):.6f}")
    print(f"  Max shape std: {np.max(shape_drift):.6f}")

    # 4. Temporal correlation (how systematic is the drift?)
    # Linear fit to total intensity
    linear_coeffs = np.polyfit(timestamps, total_intensity, 1)
    linear_fit = np.polyval(linear_coeffs, timestamps)
    linear_residuals = total_intensity - linear_fit
    linear_r2 = 1 - np.sum(linear_residuals**2) / np.sum(
        (total_intensity - np.mean(total_intensity)) ** 2,
    )

    print("\nDrift model fit (linear):")
    print(f"  Slope: {linear_coeffs[0]:.2f} counts/s")
    print(f"  R²: {linear_r2:.4f}")

    if linear_r2 > 0.8:
        print("  ✅ Highly systematic drift (R² > 0.8) - good for correction")
    elif linear_r2 > 0.5:
        print("  ⚠️ Moderate systematic drift (R² > 0.5) - correction may help")
    else:
        print("  ❌ Low correlation (R² < 0.5) - mostly random noise")

    return {
        "spectra_corrected": s_corrected,
        "total_intensity": total_intensity,
        "timestamps": timestamps,
        "drift_percent": drift_percent,
        "linear_coeffs": linear_coeffs,
        "linear_fit": linear_fit,
        "linear_r2": linear_r2,
        "pixel_drift": pixel_drift,
        "shape_stability": shape_drift,
    }


def model_drift_per_pixel(s_data: dict, model_type: str = "linear") -> dict:
    """Model drift for each wavelength pixel independently.

    Args:
        s_data: S-mode data
        model_type: 'linear', 'exponential', or 'polynomial'

    Returns:
        drift_model: Dictionary with drift correction functions

    """
    spectra = s_data["spectra"]
    dark = s_data["dark"][0]
    timestamps = s_data["timestamps"]

    s_corrected = spectra - dark
    n_time, n_wavelength = s_corrected.shape

    print(f"\n🔧 MODELING DRIFT (per-pixel {model_type} model)")
    print("=" * 70)

    # Fit model to each pixel
    drift_models = []
    r2_values = []

    for pixel in range(n_wavelength):
        signal = s_corrected[:, pixel]

        if model_type == "linear":
            # y = a*t + b
            coeffs = np.polyfit(timestamps, signal, 1)
            fitted = np.polyval(coeffs, timestamps)

        elif model_type == "exponential":
            # y = a * exp(b*t) + c
            try:

                def exp_func(t, a, b, c):
                    return a * np.exp(b * t) + c

                p0 = [signal[0], 0.001, np.mean(signal)]
                coeffs, _ = curve_fit(exp_func, timestamps, signal, p0=p0, maxfev=1000)
                fitted = exp_func(timestamps, *coeffs)
            except:
                # Fallback to linear if exponential fails
                coeffs = np.polyfit(timestamps, signal, 1)
                fitted = np.polyval(coeffs, timestamps)

        elif model_type == "polynomial":
            # y = a*t^2 + b*t + c
            coeffs = np.polyfit(timestamps, signal, 2)
            fitted = np.polyval(coeffs, timestamps)

        else:
            raise ValueError(f"Unknown model_type: {model_type}")

        # Calculate R² for this pixel
        residuals = signal - fitted
        r2 = 1 - np.sum(residuals**2) / np.sum((signal - np.mean(signal)) ** 2)

        drift_models.append(coeffs)
        r2_values.append(r2)

    drift_models = np.array(drift_models)
    r2_values = np.array(r2_values)

    print("\nModel fit quality (R² per pixel):")
    print(f"  Mean R²: {np.mean(r2_values):.4f}")
    print(f"  Median R²: {np.median(r2_values):.4f}")
    print(f"  Min R²: {np.min(r2_values):.4f}")
    print(
        f"  % pixels with R² > 0.8: {np.sum(r2_values > 0.8) / len(r2_values) * 100:.1f}%",
    )

    return {
        "model_type": model_type,
        "coefficients": drift_models,
        "r2_values": r2_values,
        "timestamps": timestamps,
    }


def apply_drift_correction(
    p_data: dict,
    s_data: dict,
    drift_model: dict,
    correction_method: str = "time_matched",
) -> tuple[np.ndarray, np.ndarray]:
    """Apply LED drift correction to P-mode data.

    Args:
        p_data: P-mode data
        s_data: S-mode data
        drift_model: Drift model from model_drift_per_pixel()
        correction_method:
            - 'time_matched': Use S-mode spectrum at matching timestamp
            - 'modeled': Use drift model to predict S-mode at each P-mode timestamp
            - 'ratio': Normalize by S-mode intensity ratio

    Returns:
        transmission_uncorrected: Standard transmission calculation
        transmission_corrected: Drift-corrected transmission

    """
    # Extract data
    s_spectra = s_data["spectra"]
    s_dark = s_data["dark"][0]
    s_timestamps = s_data["timestamps"]

    p_spectra = p_data["spectra"]
    p_dark = p_data["dark"][0]
    p_timestamps = p_data["timestamps"]

    # Dark correction
    s_corrected = s_spectra - s_dark
    p_corrected = p_spectra - p_dark

    print(f"\n✨ APPLYING DRIFT CORRECTION ({correction_method} method)")
    print("=" * 70)

    if correction_method == "time_matched":
        # Use S-mode spectra at matching timestamps
        # Find closest S-mode spectrum for each P-mode spectrum
        s_reference = np.zeros_like(p_corrected)

        for i, p_time in enumerate(p_timestamps):
            # Find closest S-mode timestamp
            closest_idx = np.argmin(np.abs(s_timestamps - p_time))
            s_reference[i] = s_corrected[closest_idx]

        print("  Using time-matched S-mode references")
        print(
            f"  Time offset range: {np.min(np.abs(s_timestamps[0] - p_timestamps[0])):.1f}s",
        )

    elif correction_method == "modeled":
        # Use drift model to predict S-mode at each P-mode timestamp
        s_reference = np.zeros_like(p_corrected)
        model_type = drift_model["model_type"]
        coeffs = drift_model["coefficients"]

        for i, p_time in enumerate(p_timestamps):
            if model_type == "linear":
                # y = a*t + b
                s_reference[i] = coeffs[:, 0] * p_time + coeffs[:, 1]
            elif model_type == "polynomial":
                # y = a*t^2 + b*t + c
                s_reference[i] = (
                    coeffs[:, 0] * p_time**2 + coeffs[:, 1] * p_time + coeffs[:, 2]
                )
            # Add exponential if needed

        print(f"  Using {model_type} drift model predictions")

    elif correction_method == "ratio":
        # Normalize P-mode by S-mode intensity drift ratio
        s_median = np.median(s_corrected, axis=0)
        s_intensity_trend = np.sum(s_corrected, axis=1)
        s_intensity_median = np.median(s_intensity_trend)

        # For each P-mode spectrum, correct by S-mode intensity trend
        s_reference = np.zeros_like(p_corrected)

        for i, p_time in enumerate(p_timestamps):
            # Find S-mode intensity at this time
            closest_idx = np.argmin(np.abs(s_timestamps - p_time))
            intensity_ratio = s_intensity_median / s_intensity_trend[closest_idx]

            # Use median S-mode shape, scaled by intensity ratio
            s_reference[i] = s_median * intensity_ratio

        print("  Using S-mode intensity ratio normalization")

    else:
        raise ValueError(f"Unknown correction_method: {correction_method}")

    # Calculate transmissions
    epsilon = 1e-6

    # Uncorrected: use median S-mode as reference (standard approach)
    s_median = np.median(s_corrected, axis=0)
    s_median_safe = np.where(np.abs(s_median) < epsilon, epsilon, s_median)
    transmission_uncorrected = p_corrected / s_median_safe[np.newaxis, :]

    # Corrected: use time-varying S-mode reference
    s_reference_safe = np.where(np.abs(s_reference) < epsilon, epsilon, s_reference)
    transmission_corrected = p_corrected / s_reference_safe

    print("✅ Drift correction applied")

    return transmission_uncorrected, transmission_corrected


def track_minimum_simple(
    transmission: np.ndarray,
    search_region: tuple[int, int],
) -> np.ndarray:
    """Simple direct minimum tracking."""
    start, end = search_region
    n_time = transmission.shape[0]
    positions = np.zeros(n_time)

    for t in range(n_time):
        region = transmission[t, start:end]
        positions[t] = start + np.argmin(region)

    return positions


def compare_correction_methods(
    p_data: dict,
    s_data: dict,
    drift_model: dict,
    search_region: tuple[int, int] = (1000, 2600),
) -> dict:
    """Compare different drift correction methods.

    Returns:
        results: Dictionary with sensorgram statistics for each method

    """
    print("\n" + "=" * 70)
    print("COMPARING DRIFT CORRECTION METHODS")
    print("=" * 70)

    methods = ["time_matched", "modeled", "ratio"]
    results = {}

    for method in methods:
        print(f"\n{method.upper()} METHOD:")

        # Apply correction
        trans_uncorr, trans_corr = apply_drift_correction(
            p_data,
            s_data,
            drift_model,
            correction_method=method,
        )

        # Track minimum
        pos_uncorr = track_minimum_simple(trans_uncorr, search_region)
        pos_corr = track_minimum_simple(trans_corr, search_region)

        # Calculate statistics
        pp_uncorr = np.ptp(pos_uncorr)
        std_uncorr = np.std(pos_uncorr)
        pp_corr = np.ptp(pos_corr)
        std_corr = np.std(pos_corr)

        improvement = (1 - pp_corr / pp_uncorr) * 100 if pp_uncorr > 0 else 0

        print(f"\n  Uncorrected: P-P = {pp_uncorr:.2f} px, STD = {std_uncorr:.2f} px")
        print(f"  Corrected:   P-P = {pp_corr:.2f} px, STD = {std_corr:.2f} px")
        print(f"  Improvement: {improvement:+.1f}%")

        results[method] = {
            "transmission_uncorrected": trans_uncorr,
            "transmission_corrected": trans_corr,
            "positions_uncorrected": pos_uncorr,
            "positions_corrected": pos_corr,
            "pp_uncorrected": pp_uncorr,
            "std_uncorrected": std_uncorr,
            "pp_corrected": pp_corr,
            "std_corrected": std_corr,
            "improvement": improvement,
        }

    return results


def visualize_drift_correction(
    s_data: dict,
    drift_analysis: dict,
    drift_model: dict,
    correction_results: dict,
    output_dir: Path,
):
    """Create comprehensive visualization of drift correction."""
    output_dir.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(20, 12))

    # 1. S-mode total intensity over time
    ax1 = plt.subplot(3, 4, 1)
    timestamps = drift_analysis["timestamps"]
    total_intensity = drift_analysis["total_intensity"]
    linear_fit = drift_analysis["linear_fit"]

    ax1.plot(timestamps, total_intensity, "b-", linewidth=1.5, label="Measured")
    ax1.plot(
        timestamps,
        linear_fit,
        "r--",
        linewidth=2,
        label=f'Linear fit (R²={drift_analysis["linear_r2"]:.3f})',
    )
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Total S-mode Intensity (counts)")
    ax1.set_title("LED Intensity Drift (S-mode)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. Per-pixel drift
    ax2 = plt.subplot(3, 4, 2)
    wavelength_pixels = np.arange(len(drift_analysis["pixel_drift"]))
    ax2.plot(wavelength_pixels, drift_analysis["pixel_drift"], "g-", linewidth=1)
    ax2.axhline(0, color="black", linestyle="--", linewidth=1)
    ax2.set_xlabel("Wavelength pixel")
    ax2.set_ylabel("Drift (%)")
    ax2.set_title("Per-Pixel Drift Over Measurement")
    ax2.grid(True, alpha=0.3)

    # 3. Drift model R² distribution
    ax3 = plt.subplot(3, 4, 3)
    ax3.hist(
        drift_model["r2_values"],
        bins=50,
        color="purple",
        alpha=0.7,
        edgecolor="black",
    )
    ax3.axvline(
        np.mean(drift_model["r2_values"]),
        color="red",
        linestyle="--",
        linewidth=2,
        label=f'Mean: {np.mean(drift_model["r2_values"]):.3f}',
    )
    ax3.set_xlabel("R² value")
    ax3.set_ylabel("Number of pixels")
    ax3.set_title("Drift Model Fit Quality")
    ax3.legend()
    ax3.grid(True, alpha=0.3, axis="y")

    # 4. S-mode spectral heatmap
    ax4 = plt.subplot(3, 4, 4)
    im = ax4.imshow(
        drift_analysis["spectra_corrected"].T,
        aspect="auto",
        cmap="viridis",
        extent=[timestamps[0], timestamps[-1], len(wavelength_pixels), 0],
    )
    ax4.set_xlabel("Time (s)")
    ax4.set_ylabel("Wavelength pixel")
    ax4.set_title("S-mode Spectra (Dark-corrected)")
    plt.colorbar(im, ax=ax4, label="Counts")

    # 5-7. Sensorgrams for each correction method
    methods = ["time_matched", "modeled", "ratio"]
    colors_uncorr = ["blue", "blue", "blue"]
    colors_corr = ["red", "orange", "green"]

    for idx, method in enumerate(methods):
        ax = plt.subplot(3, 4, 5 + idx)

        result = correction_results[method]
        p_timestamps = s_data["timestamps"]  # Assuming same sampling

        ax.plot(
            p_timestamps,
            result["positions_uncorrected"],
            color=colors_uncorr[idx],
            linewidth=1,
            alpha=0.7,
            label="Uncorrected",
        )
        ax.plot(
            p_timestamps,
            result["positions_corrected"],
            color=colors_corr[idx],
            linewidth=1.5,
            label="Corrected",
        )

        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Position (pixel)")
        ax.set_title(f'{method.upper()}\nImprovement: {result["improvement"]:+.1f}%')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    # 8. Correction comparison
    ax8 = plt.subplot(3, 4, 8)
    x_pos = np.arange(len(methods))
    pp_uncorr = [correction_results[m]["pp_uncorrected"] for m in methods]
    pp_corr = [correction_results[m]["pp_corrected"] for m in methods]

    width = 0.35
    ax8.bar(
        x_pos - width / 2,
        pp_uncorr,
        width,
        label="Uncorrected",
        color="steelblue",
        alpha=0.7,
    )
    ax8.bar(
        x_pos + width / 2,
        pp_corr,
        width,
        label="Corrected",
        color="coral",
        alpha=0.7,
    )

    ax8.set_ylabel("Peak-to-Peak (pixels)")
    ax8.set_title("Drift Correction Impact")
    ax8.set_xticks(x_pos)
    ax8.set_xticklabels([m.replace("_", "\n") for m in methods], fontsize=8)
    ax8.legend()
    ax8.grid(True, alpha=0.3, axis="y")

    # 9-11. Sample transmission spectra comparison
    sample_times = [0, len(timestamps) // 2, len(timestamps) - 1]
    sample_labels = ["Start", "Middle", "End"]

    for idx, (t_idx, label) in enumerate(
        zip(sample_times, sample_labels, strict=False),
    ):
        ax = plt.subplot(3, 4, 9 + idx)

        # Show uncorrected vs corrected transmission
        trans_uncorr = correction_results["time_matched"]["transmission_uncorrected"][
            t_idx
        ]
        trans_corr = correction_results["time_matched"]["transmission_corrected"][t_idx]

        ax.plot(
            wavelength_pixels,
            trans_uncorr,
            "b-",
            linewidth=1,
            alpha=0.7,
            label="Uncorrected",
        )
        ax.plot(wavelength_pixels, trans_corr, "r-", linewidth=1.5, label="Corrected")

        ax.set_xlabel("Wavelength pixel")
        ax.set_ylabel("Transmission")
        ax.set_title(f"Transmission Spectrum ({label})")
        ax.set_xlim([1000, 2600])
        ax.set_ylim([0, 1.2])
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    # 12. Summary improvement
    ax12 = plt.subplot(3, 4, 12)
    improvements = [correction_results[m]["improvement"] for m in methods]
    colors_bar = ["red", "orange", "green"]

    bars = ax12.bar(
        methods,
        improvements,
        color=colors_bar,
        alpha=0.7,
        edgecolor="black",
    )
    ax12.axhline(0, color="black", linestyle="-", linewidth=1)
    ax12.set_ylabel("Improvement (%)")
    ax12.set_title("Noise Reduction by Method")
    ax12.set_xticklabels([m.replace("_", "\n") for m in methods], fontsize=8)
    ax12.grid(True, alpha=0.3, axis="y")

    # Add value labels on bars
    for bar, improvement in zip(bars, improvements, strict=False):
        height = bar.get_height()
        ax12.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{improvement:+.1f}%",
            ha="center",
            va="bottom" if height > 0 else "top",
            fontsize=10,
            fontweight="bold",
        )

    plt.tight_layout()
    plt.savefig(output_dir / "led_drift_correction.png", dpi=150, bbox_inches="tight")
    print(f"\n📊 Visualization saved: {output_dir / 'led_drift_correction.png'}")
    plt.close()


def main():
    """Demonstrate LED drift characterization and correction."""
    print("=" * 70)
    print("LED DRIFT CHARACTERIZATION AND CORRECTION - CHANNEL A")
    print("=" * 70)

    # Load data
    print("\n📂 Loading data...")
    s_mode_dir = find_latest_data_dir(S_MODE_DIR)
    p_mode_dir = find_latest_data_dir(P_MODE_DIR)

    s_data = load_channel_data(s_mode_dir, "A")
    p_data = load_channel_data(p_mode_dir, "A")

    # Analyze S-mode drift
    drift_analysis = analyze_s_mode_drift(s_data)

    # Model drift per pixel
    drift_model = model_drift_per_pixel(s_data, model_type="linear")

    # Compare correction methods
    correction_results = compare_correction_methods(p_data, s_data, drift_model)

    # Visualize
    visualize_drift_correction(
        s_data,
        drift_analysis,
        drift_model,
        correction_results,
        OUTPUT_DIR,
    )

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print("\nLED Drift Characteristics:")
    print(f"  Total intensity drift: {drift_analysis['drift_percent']:+.2f}%")
    print(f"  Linear model R²: {drift_analysis['linear_r2']:.4f}")
    print(f"  Per-pixel model mean R²: {np.mean(drift_model['r2_values']):.4f}")

    print("\nCorrection Performance:")
    best_method = max(
        correction_results.keys(),
        key=lambda m: correction_results[m]["improvement"],
    )
    for method in correction_results.keys():
        result = correction_results[method]
        print(
            f"  {method:<15}: {result['pp_uncorrected']:.1f} → {result['pp_corrected']:.1f} px "
            f"({result['improvement']:+.1f}%)",
        )

    print(
        f"\n🏆 Best method: {best_method.upper()} "
        f"({correction_results[best_method]['improvement']:+.1f}% improvement)",
    )

    # Save summary
    summary = {
        "drift_analysis": {
            "drift_percent": float(drift_analysis["drift_percent"]),
            "linear_r2": float(drift_analysis["linear_r2"]),
            "linear_slope": float(drift_analysis["linear_coeffs"][0]),
        },
        "correction_results": {
            method: {
                "pp_uncorrected": float(result["pp_uncorrected"]),
                "pp_corrected": float(result["pp_corrected"]),
                "improvement": float(result["improvement"]),
            }
            for method, result in correction_results.items()
        },
        "best_method": best_method,
    }

    summary_file = OUTPUT_DIR / "led_drift_correction_summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n📄 Summary saved: {summary_file}")

    print(f"\n✅ Analysis complete! Results saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    main()
