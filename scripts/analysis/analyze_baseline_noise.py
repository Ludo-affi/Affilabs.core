"""Baseline Noise Analysis and Denoising Strategy
Analyzes the recorded baseline data to determine optimal smoothing parameters
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.fft import rfft, rfftfreq
from scipy.signal import medfilt, savgol_filter

# Load the baseline data
data_file = Path("src/baseline_data/baseline_wavelengths_20251126_223040.csv")
print(f"Loading: {data_file}")

# Read CSV - data format: wave_a, time_a, wave_b, time_b, wave_c, time_c, wave_d, time_d
# The file may have log lines mixed in, so we need to filter for numeric data only
df = pd.read_csv(data_file, header=None, on_bad_lines="skip")

# Filter rows that start with a number (valid data rows)
numeric_rows = []
for idx, row in df.iterrows():
    try:
        # Try to convert first column to float
        float(row[0])
        numeric_rows.append(row)
    except (ValueError, TypeError):
        pass

df = pd.DataFrame(numeric_rows)
df = df.apply(pd.to_numeric, errors="coerce")  # Convert all to numeric, NaN for invalid
print(f"Shape after filtering: {df.shape}")

# Extract wavelength columns (0, 2, 4, 6) and time columns (1, 3, 5, 7)
channels = {
    "a": {"wave": df[0].values, "time": df[1].values},
    "b": {"wave": df[2].values, "time": df[3].values},
    "c": {"wave": df[4].values, "time": df[5].values},
    "d": {"wave": df[6].values, "time": df[7].values},
}

print(f"\n{'='*80}")
print("BASELINE NOISE ANALYSIS")
print(f"{'='*80}\n")

# Calculate statistics for each channel
for ch_name, ch_data in channels.items():
    wave = ch_data["wave"]
    time = ch_data["time"]

    # Remove NaN values
    valid_mask = ~np.isnan(wave)
    wave = wave[valid_mask]
    time = time[valid_mask]

    if len(wave) < 10:
        print(f"Channel {ch_name.upper()}: Insufficient data (n={len(wave)})")
        continue

    # Basic statistics
    mean_wave = np.mean(wave)
    std_wave = np.std(wave)
    peak_to_peak = np.max(wave) - np.min(wave)

    # Calculate noise metrics
    # 1. High-frequency noise (difference between consecutive points)
    diffs = np.diff(wave)
    hf_noise = np.std(diffs) / np.sqrt(2)  # Normalize for differencing

    # 2. Low-frequency drift (linear trend)
    if len(wave) > 2:
        coeff = np.polyfit(time, wave, 1)
        trend = np.poly1d(coeff)
        detrended = wave - trend(time)
        lf_drift = np.std(detrended)
    else:
        lf_drift = std_wave

    # 3. Signal-to-noise ratio
    snr = mean_wave / std_wave if std_wave > 0 else np.inf

    print(f"Channel {ch_name.upper()}: n={len(wave)} points")
    print(f"  Mean wavelength: {mean_wave:.3f} nm")
    print(f"  Std deviation: {std_wave:.4f} nm")
    print(f"  Peak-to-peak: {peak_to_peak:.4f} nm")
    print(f"  High-freq noise: {hf_noise:.4f} nm")
    print(f"  Low-freq drift: {lf_drift:.4f} nm")
    print(f"  SNR: {snr:.1f}")
    print()

print(f"\n{'='*80}")
print("DENOISING STRATEGY TESTING")
print(f"{'='*80}\n")

# Test different denoising strategies on Channel A (typically best signal)
ch_a_wave = channels["a"]["wave"]
ch_a_time = channels["a"]["time"]

# Remove NaN
valid_mask = ~np.isnan(ch_a_wave)
ch_a_wave = ch_a_wave[valid_mask]
ch_a_time = ch_a_time[valid_mask]

if len(ch_a_wave) < 50:
    print("ERROR: Insufficient data for denoising analysis")
    exit(1)

print(f"Testing on Channel A: {len(ch_a_wave)} points\n")

# Original statistics
orig_std = np.std(ch_a_wave)
orig_pp = np.max(ch_a_wave) - np.min(ch_a_wave)

print("Original data:")
print(f"  Std: {orig_std:.4f} nm, Peak-to-peak: {orig_pp:.4f} nm\n")

# Strategy 1: Moving average (simple smoothing)
strategies = {}
for window in [3, 5, 7, 11, 15, 21]:
    smoothed = np.convolve(ch_a_wave, np.ones(window) / window, mode="valid")
    smoothed_std = np.std(smoothed)
    smoothed_pp = np.max(smoothed) - np.min(smoothed)
    improvement = (orig_std - smoothed_std) / orig_std * 100
    strategies[f"MovAvg_{window}"] = {
        "data": smoothed,
        "std": smoothed_std,
        "pp": smoothed_pp,
        "improvement": improvement,
    }

# Strategy 2: Savitzky-Golay filter (polynomial smoothing)
for window in [5, 7, 11, 15, 21]:
    for polyorder in [2, 3]:
        if window > polyorder:
            try:
                smoothed = savgol_filter(ch_a_wave, window, polyorder)
                smoothed_std = np.std(smoothed)
                smoothed_pp = np.max(smoothed) - np.min(smoothed)
                improvement = (orig_std - smoothed_std) / orig_std * 100
                strategies[f"SavGol_w{window}_p{polyorder}"] = {
                    "data": smoothed,
                    "std": smoothed_std,
                    "pp": smoothed_pp,
                    "improvement": improvement,
                }
            except:
                pass

# Strategy 3: Exponential moving average (EMA)
for alpha in [0.1, 0.2, 0.3, 0.5]:
    smoothed = np.zeros_like(ch_a_wave)
    smoothed[0] = ch_a_wave[0]
    for i in range(1, len(ch_a_wave)):
        smoothed[i] = alpha * ch_a_wave[i] + (1 - alpha) * smoothed[i - 1]
    smoothed_std = np.std(smoothed)
    smoothed_pp = np.max(smoothed) - np.min(smoothed)
    improvement = (orig_std - smoothed_std) / orig_std * 100
    strategies[f"EMA_alpha{alpha}"] = {
        "data": smoothed,
        "std": smoothed_std,
        "pp": smoothed_pp,
        "improvement": improvement,
    }

# Strategy 4: Median filter (removes spikes)
for kernel in [3, 5, 7, 9]:
    smoothed = medfilt(ch_a_wave, kernel_size=kernel)
    smoothed_std = np.std(smoothed)
    smoothed_pp = np.max(smoothed) - np.min(smoothed)
    improvement = (orig_std - smoothed_std) / orig_std * 100
    strategies[f"Median_{kernel}"] = {
        "data": smoothed,
        "std": smoothed_std,
        "pp": smoothed_pp,
        "improvement": improvement,
    }

# Rank strategies by improvement
ranked = sorted(strategies.items(), key=lambda x: x[1]["improvement"], reverse=True)

print("Top 10 Denoising Strategies (ranked by std reduction):")
print(
    f"{'Rank':<5} {'Strategy':<20} {'Std (nm)':<12} {'P-P (nm)':<12} {'Improvement':<15}",
)
print("-" * 80)
for i, (name, stats) in enumerate(ranked[:10], 1):
    print(
        f"{i:<5} {name:<20} {stats['std']:.4f}      {stats['pp']:.4f}      {stats['improvement']:.1f}%",
    )

print(f"\n{'='*80}")
print("FOURIER ANALYSIS")
print(f"{'='*80}\n")

# Fourier transform to identify dominant frequencies
sampling_rate = 1.0 / np.mean(np.diff(ch_a_time))  # Hz
print(f"Average sampling rate: {sampling_rate:.3f} Hz")

# Apply FFT
fft_vals = rfft(ch_a_wave - np.mean(ch_a_wave))
fft_freq = rfftfreq(len(ch_a_wave), 1 / sampling_rate)
fft_power = np.abs(fft_vals) ** 2

# Find dominant frequencies
top_indices = np.argsort(fft_power)[-5:][::-1]
print("\nTop 5 frequency components:")
for idx in top_indices:
    if fft_freq[idx] > 0:  # Skip DC component
        print(
            f"  {fft_freq[idx]:.4f} Hz (period: {1/fft_freq[idx]:.2f} s), Power: {fft_power[idx]:.2e}",
        )

print(f"\n{'='*80}")
print("RECOMMENDATION")
print(f"{'='*80}\n")

# Select best strategy
best_name, best_stats = ranked[0]
print(f"RECOMMENDED STRATEGY: {best_name}")
print(f"  Reduces std by {best_stats['improvement']:.1f}%")
print(f"  Final std: {best_stats['std']:.4f} nm")
print(f"  Final peak-to-peak: {best_stats['pp']:.4f} nm")
print()

# Extract parameters from best strategy
if "MovAvg" in best_name:
    window = int(best_name.split("_")[1])
    print(f"Implementation: Use moving average with window size {window}")
    print(f"  Python: np.convolve(data, np.ones({window})/{window}, mode='valid')")
elif "SavGol" in best_name:
    parts = best_name.split("_")
    window = int(parts[1][1:])
    polyorder = int(parts[2][1:])
    print("Implementation: Use Savitzky-Golay filter")
    print(f"  Window: {window}, Polynomial order: {polyorder}")
    print(f"  Python: scipy.signal.savgol_filter(data, {window}, {polyorder})")
elif "EMA" in best_name:
    alpha = float(best_name.split("alpha")[1])
    print("Implementation: Use Exponential Moving Average")
    print(f"  Alpha (smoothing factor): {alpha}")
    print(f"  Equivalent to time constant tau = {1/alpha:.1f} samples")
elif "Median" in best_name:
    kernel = int(best_name.split("_")[1])
    print(f"Implementation: Use median filter with kernel size {kernel}")
    print(f"  Python: scipy.signal.medfilt(data, kernel_size={kernel})")

print(f"\n{'='*80}")
print("ZERO-CROSSING OPTIMIZATION")
print(f"{'='*80}\n")

# Test zero-crossing detection with best smoothing
best_data = best_stats["data"]

# Current Fourier alpha = 9000
print("For Fourier DST/IDCT pipeline:")
print("  Current alpha: 9000")
print("  Current window: 165 points")
print()
print("The transmission data (S/P ratio) goes through:")
print("  1. LED afterglow correction")
print("  2. Division (S_ref / P_ref)")
print("  3. Fourier smoothing (alpha=9000)")
print("  4. Zero-crossing detection")
print()
print(f"Since baseline wavelengths have std ~{orig_std:.4f} nm,")
print("the transmission noise will be amplified by division.")
print()
print("RECOMMENDATION: Add pre-smoothing BEFORE Fourier pipeline")
print(f"  1. Apply {best_name} to raw transmission data")
print("  2. Then apply Fourier DST/IDCT with alpha=9000")
print("  3. This cascaded filtering will improve zero-crossing clarity")

# Save visualization
print(f"\n{'='*80}")
print("Creating visualization...")

fig, axes = plt.subplots(3, 1, figsize=(14, 10))

# Plot 1: Original data for all channels
ax = axes[0]
for ch_name, ch_data in channels.items():
    wave = ch_data["wave"]
    time = ch_data["time"]
    valid_mask = ~np.isnan(wave)
    wave = wave[valid_mask]
    time = time[valid_mask]
    if len(wave) > 0:
        # Convert Unix timestamp to relative seconds
        time_rel = time - time[0]
        ax.plot(time_rel, wave, alpha=0.7, label=f"Channel {ch_name.upper()}")

ax.set_xlabel("Time (s)")
ax.set_ylabel("Wavelength (nm)")
ax.set_title("Raw Baseline Wavelength Data - All Channels")
ax.legend()
ax.grid(True, alpha=0.3)

# Plot 2: Channel A with different smoothing strategies
ax = axes[1]
time_rel_a = ch_a_time - ch_a_time[0]
ax.plot(time_rel_a, ch_a_wave, "gray", alpha=0.3, label="Original", linewidth=0.5)

# Plot top 3 strategies
colors = ["red", "blue", "green"]
for i, (name, stats) in enumerate(ranked[:3]):
    data = stats["data"]
    # Adjust time axis for convolution edge effects
    if len(data) < len(time_rel_a):
        offset = (len(time_rel_a) - len(data)) // 2
        time_plot = time_rel_a[offset : offset + len(data)]
    else:
        time_plot = time_rel_a
    ax.plot(
        time_plot,
        data,
        colors[i],
        alpha=0.8,
        label=f'{name} (σ={stats["std"]:.4f})',
        linewidth=1.5,
    )

ax.set_xlabel("Time (s)")
ax.set_ylabel("Wavelength (nm)")
ax.set_title("Channel A: Original vs. Top 3 Smoothing Strategies")
ax.legend()
ax.grid(True, alpha=0.3)

# Plot 3: Frequency spectrum
ax = axes[2]
ax.semilogy(fft_freq[1:], fft_power[1:])  # Skip DC component
ax.set_xlabel("Frequency (Hz)")
ax.set_ylabel("Power Spectral Density")
ax.set_title("Frequency Content of Channel A Baseline")
ax.grid(True, alpha=0.3)

plt.tight_layout()
output_file = Path("baseline_noise_analysis.png")
plt.savefig(output_file, dpi=150, bbox_inches="tight")
print(f"Saved visualization: {output_file}")
print(f"\n{'='*80}")
print("Analysis complete!")
print(f"{'='*80}\n")
