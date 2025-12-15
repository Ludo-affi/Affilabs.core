"""Analyze transmission spectra using centroid method with dynamic SG filtering."""

from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import savgol_filter

from settings.settings import ROOT_DIR


def calculate_spectral_centroid(wavelengths, intensity):
    """Calculate spectral centroid: λ_c = Σ(λ_i × I_i) / Σ(I_i)"""
    return np.sum(wavelengths * intensity) / np.sum(intensity)


def find_optimal_sg_params(spectrum, wavelengths, target_smoothness=0.001):
    """Find optimal SG filter parameters to achieve target smoothness.
    Returns (window_length, polyorder) that produces desired smoothness level.
    """
    # Start with moderate smoothing
    window_lengths = range(5, min(51, len(spectrum) // 2), 2)  # Must be odd
    polyorders = [2, 3, 4]

    best_params = (5, 2)
    best_diff = float("inf")

    for window in window_lengths:
        for polyorder in polyorders:
            if polyorder >= window:
                continue

            try:
                smoothed = savgol_filter(spectrum, window, polyorder)
                # Calculate smoothness as std of second derivative
                second_deriv = np.diff(smoothed, n=2)
                smoothness = np.std(second_deriv)

                diff = abs(smoothness - target_smoothness)
                if diff < best_diff:
                    best_diff = diff
                    best_params = (window, polyorder)
            except:
                continue

    return best_params


def apply_adaptive_sg_filter(spectra, wavelengths, target_smoothness=None):
    """Apply SG filter with adaptive parameters to achieve uniform smoothness.
    If target_smoothness is None, use the median smoothness across all spectra.
    """
    n_spectra = len(spectra)

    # First pass: calculate smoothness for each spectrum with default params
    if target_smoothness is None:
        smoothness_values = []
        for spec in spectra:
            try:
                smoothed = savgol_filter(spec, 11, 3)
                second_deriv = np.diff(smoothed, n=2)
                smoothness = np.std(second_deriv)
                smoothness_values.append(smoothness)
            except:
                smoothness_values.append(0.001)

        target_smoothness = np.median(smoothness_values)
        print(f"  Target smoothness (median): {target_smoothness:.6f}")

    # Second pass: apply adaptive filtering
    filtered_spectra = []
    sg_params_used = []

    for i, spec in enumerate(spectra):
        # Find optimal SG parameters for this spectrum
        window, polyorder = find_optimal_sg_params(spec, wavelengths, target_smoothness)

        try:
            smoothed = savgol_filter(spec, window, polyorder)
            filtered_spectra.append(smoothed)
            sg_params_used.append((window, polyorder))
        except:
            # Fallback to original if filtering fails
            filtered_spectra.append(spec)
            sg_params_used.append((0, 0))

    return np.array(filtered_spectra), sg_params_used


# Load the most recent transmission data
calib_dir = Path(ROOT_DIR) / "calibration_data"
npz_files = sorted(
    calib_dir.glob("transmission_spectra_*.npz"),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)

if len(npz_files) == 0:
    print("Error: No transmission spectra files found")
    exit(1)

trans_file = npz_files[0]

print("=" * 80)
print("TRANSMISSION CENTROID ANALYSIS")
print("=" * 80)
print(f"Input file: {trans_file.name}")
print()

# Load data
data = np.load(trans_file)
wavelengths = data["wavelengths"]
roi_nm = data["roi_nm"]

channels = ["a", "b", "c", "d"]

print(
    f"Wavelengths: {len(wavelengths)} pixels ({wavelengths[0]:.1f}-{wavelengths[-1]:.1f} nm)",
)
print(f"ROI: {roi_nm[0]:.1f}-{roi_nm[1]:.1f} nm")
print()

# Extract ROI indices
roi_mask = (wavelengths >= roi_nm[0]) & (wavelengths <= roi_nm[1])
roi_wavelengths = wavelengths[roi_mask]
roi_indices = np.where(roi_mask)[0]

print(f"ROI contains {len(roi_wavelengths)} wavelength points")
print()

# Process each channel
centroid_results = {}

for ch in channels:
    spec_key = f"spectra_{ch}"
    time_key = f"times_{ch}"

    if spec_key not in data:
        print(f"Channel {ch.upper()}: No data, skipping")
        continue

    spectra = data[spec_key]
    times = data[time_key]

    print(f"Channel {ch.upper()}: {len(spectra)} spectra")

    # Extract ROI spectra
    roi_spectra = spectra[:, roi_mask]

    # Apply adaptive SG filtering for uniform smoothness
    print("  Applying adaptive SG filter...")
    filtered_spectra, sg_params = apply_adaptive_sg_filter(roi_spectra, roi_wavelengths)

    # Report SG parameter statistics
    windows = [p[0] for p in sg_params if p[0] > 0]
    polyorders = [p[1] for p in sg_params if p[1] > 0]
    if windows:
        print(
            f"  SG windows: mean={np.mean(windows):.1f}, range=[{min(windows)}, {max(windows)}]",
        )
        print(
            f"  SG polyorders: mean={np.mean(polyorders):.1f}, range=[{min(polyorders)}, {max(polyorders)}]",
        )

    # Calculate centroids
    centroids = []
    for i, (spec_raw, spec_filtered) in enumerate(
        zip(roi_spectra, filtered_spectra, strict=False),
    ):
        centroid = calculate_spectral_centroid(roi_wavelengths, spec_filtered)
        centroids.append(centroid)

    centroids = np.array(centroids)

    # Calculate statistics
    centroid_mean = np.mean(centroids)
    centroid_std = np.std(centroids)
    centroid_pp = np.ptp(centroids)  # peak-to-peak

    print(f"  Centroid mean: {centroid_mean:.3f} nm")
    print(f"  Centroid std: {centroid_std:.4f} nm")
    print(f"  Centroid p-p: {centroid_pp:.4f} nm")
    print()

    centroid_results[ch] = {
        "times": times,
        "centroids": centroids,
        "mean": centroid_mean,
        "std": centroid_std,
        "pp": centroid_pp,
        "sg_params": sg_params,
        "filtered_spectra": filtered_spectra,
        "raw_spectra": roi_spectra,
    }

# Save centroid time series
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = calib_dir / f"transmission_centroid_analysis_{timestamp}.npz"

print(f"Saving centroid analysis to: {output_file.name}")

save_dict = {
    "wavelengths": wavelengths,
    "roi_wavelengths": roi_wavelengths,
    "roi_nm": roi_nm,
}

for ch in channels:
    if ch in centroid_results:
        res = centroid_results[ch]
        save_dict[f"times_{ch}"] = res["times"]
        save_dict[f"centroids_{ch}"] = res["centroids"]
        save_dict[f"centroid_mean_{ch}"] = res["mean"]
        save_dict[f"centroid_std_{ch}"] = res["std"]
        save_dict[f"centroid_pp_{ch}"] = res["pp"]

np.savez_compressed(output_file, **save_dict)

# Create comprehensive plots
fig = plt.figure(figsize=(16, 12))
gs = fig.add_gridspec(4, 3, hspace=0.3, wspace=0.3)

for idx, ch in enumerate(channels):
    if ch not in centroid_results:
        continue

    res = centroid_results[ch]
    times = res["times"]
    centroids = res["centroids"]

    # Plot 1: Centroid time series
    ax1 = fig.add_subplot(gs[idx, 0])
    ax1.plot(times, centroids, "b-", linewidth=1, alpha=0.7)
    ax1.axhline(
        res["mean"],
        color="r",
        linestyle="--",
        linewidth=1,
        label=f"Mean={res['mean']:.3f} nm",
    )
    ax1.fill_between(
        times,
        res["mean"] - res["std"],
        res["mean"] + res["std"],
        alpha=0.2,
        color="r",
        label=f"±1σ={res['std']:.4f} nm",
    )
    ax1.set_xlabel("Time (s)", fontsize=9)
    ax1.set_ylabel("Centroid (nm)", fontsize=9)
    ax1.set_title(
        f'Ch {ch.upper()} - Centroid vs Time\np-p = {res["pp"]:.4f} nm',
        fontsize=10,
        fontweight="bold",
    )
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    # Plot 2: Example spectra (raw vs filtered)
    ax2 = fig.add_subplot(gs[idx, 1])
    mid_idx = len(res["raw_spectra"]) // 2
    ax2.plot(
        roi_wavelengths,
        res["raw_spectra"][mid_idx],
        "gray",
        linewidth=1,
        alpha=0.5,
        label="Raw",
    )
    ax2.plot(
        roi_wavelengths,
        res["filtered_spectra"][mid_idx],
        "b-",
        linewidth=1.5,
        label="SG filtered",
    )
    ax2.axvline(
        res["centroids"][mid_idx],
        color="r",
        linestyle="--",
        linewidth=1,
        label=f'Centroid={res["centroids"][mid_idx]:.3f} nm',
    )
    ax2.set_xlabel("Wavelength (nm)", fontsize=9)
    ax2.set_ylabel("Transmission", fontsize=9)
    ax2.set_title(
        f"Ch {ch.upper()} - Example Spectrum (t={times[mid_idx]:.1f}s)",
        fontsize=10,
        fontweight="bold",
    )
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # Plot 3: Centroid histogram
    ax3 = fig.add_subplot(gs[idx, 2])
    n, bins, patches = ax3.hist(
        centroids,
        bins=20,
        color="steelblue",
        alpha=0.7,
        edgecolor="black",
    )
    ax3.axvline(res["mean"], color="r", linestyle="--", linewidth=2, label="Mean")
    ax3.set_xlabel("Centroid (nm)", fontsize=9)
    ax3.set_ylabel("Count", fontsize=9)
    ax3.set_title(
        f'Ch {ch.upper()} - Centroid Distribution\nσ={res["std"]:.4f} nm',
        fontsize=10,
        fontweight="bold",
    )
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.3, axis="y")

fig.suptitle(
    "Transmission Spectrum Centroid Analysis (Dynamic SG Filtering)",
    fontsize=14,
    fontweight="bold",
    y=0.995,
)

plot_file = calib_dir / f"transmission_centroid_analysis_{timestamp}.png"
plt.savefig(plot_file, dpi=150, bbox_inches="tight")
print(f"Centroid analysis plot saved: {plot_file.name}")

# Create summary comparison plot
fig2, axes = plt.subplots(2, 2, figsize=(14, 10))
fig2.suptitle("Centroid Sensorgram - All Channels", fontsize=14, fontweight="bold")

for idx, ch in enumerate(channels):
    ax = axes[idx // 2, idx % 2]

    if ch not in centroid_results:
        ax.text(
            0.5,
            0.5,
            f"Channel {ch.upper()}\nNo data",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        continue

    res = centroid_results[ch]
    times = res["times"]
    centroids = res["centroids"]

    # Detrend centroids (subtract mean)
    centroids_detrended = centroids - res["mean"]

    ax.plot(times, centroids_detrended * 1000, "b-", linewidth=1.5, alpha=0.8)
    ax.axhline(0, color="k", linestyle="-", linewidth=0.5)
    ax.fill_between(
        times,
        -res["std"] * 1000,
        res["std"] * 1000,
        alpha=0.2,
        color="gray",
        label=f'±1σ={res["std"]*1000:.2f} pm',
    )

    ax.set_xlabel("Time (s)", fontsize=10)
    ax.set_ylabel("Δ Centroid (pm)", fontsize=10)
    ax.set_title(
        f'Channel {ch.upper()}\np-p = {res["pp"]*1000:.2f} pm',
        fontsize=11,
        fontweight="bold",
    )
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plot_file2 = calib_dir / f"transmission_sensorgram_{timestamp}.png"
plt.savefig(plot_file2, dpi=150, bbox_inches="tight")
print(f"Sensorgram plot saved: {plot_file2.name}")

print()
print("=" * 80)
print("CENTROID ANALYSIS SUMMARY")
print("=" * 80)
for ch in channels:
    if ch in centroid_results:
        res = centroid_results[ch]
        print(f"Channel {ch.upper()}:")
        print(f"  Centroid mean: {res['mean']:.3f} nm")
        print(f"  Centroid std:  {res['std']*1000:.2f} pm")
        print(f"  Centroid p-p:  {res['pp']*1000:.2f} pm")
        print()

print("=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
print("Output files:")
print(f"  Data: {output_file.name}")
print(f"  Detailed plot: {plot_file.name}")
print(f"  Sensorgram: {plot_file2.name}")
