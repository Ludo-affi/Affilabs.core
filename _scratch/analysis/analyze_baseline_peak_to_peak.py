"""Baseline Peak-to-Peak Variation Analysis

Processes all timepoints from the Excel file and calculates peak-to-peak variation.
Uses argmin on SG-filtered data (correct method for saved Excel files).
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.signal import savgol_filter
import matplotlib.pyplot as plt

# ============================================================================
# CONFIGURATION
# ============================================================================

DATA_FILE = Path("test_data/baseline_recording_20260126_235959.xlsx")
WAVELENGTH_RANGE = (570.0, 720.0)
SG_WINDOW = 21
SG_POLY = 3

# RU conversion: User-defined calibration
# 1 RU = 1 nm / 355
def nm_to_RU(wavelength_shift_nm):
    """Convert wavelength shift (nm) to RU (Resonance Units)
    
    1 RU = 1 nm / 355
    RU = wavelength_shift (nm) × 355
    """
    RU = wavelength_shift_nm * 355
    return RU

# ============================================================================
# LOAD DATA
# ============================================================================

print("=" * 80)
print("BASELINE PEAK-TO-PEAK VARIATION ANALYSIS")
print("=" * 80)
print(f"\nLoading: {DATA_FILE}")

# Process all 4 channels
channels = ["Channel_A", "Channel_B", "Channel_C", "Channel_D"]
results = {}

for channel in channels:
    print(f"\n{'=' * 80}")
    print(f"Processing {channel}")
    print(f"{'=' * 80}")

    df = pd.read_excel(DATA_FILE, sheet_name=channel)

    # Extract wavelength array (first column)
    wavelengths_raw = df.iloc[:, 0].values

    # Filter wavelength range
    wavelength_mask = (wavelengths_raw >= WAVELENGTH_RANGE[0]) & (wavelengths_raw <= WAVELENGTH_RANGE[1])
    wavelengths = wavelengths_raw[wavelength_mask]

    print(f"Wavelengths: {len(wavelengths)} points ({wavelengths.min():.2f}-{wavelengths.max():.2f} nm)")

    # Extract time columns (all columns except wavelength)
    time_columns = [col for col in df.columns if col.startswith('t_')]
    num_timepoints = len(time_columns)
    print(f"Timepoints: {num_timepoints}")

    # Process each timepoint
    peak_wavelengths = []
    timestamps = []

    # Import Fourier pipeline for production-quality peak finding
    from scipy.fft import dst, idct
    from scipy.stats import linregress

    # Fourier parameters (from production pipeline)
    FOURIER_ALPHA = 9000
    FOURIER_WINDOW = 165

    for i, col in enumerate(time_columns):
        # Extract transmission spectrum
        transmission_raw = df[col].values
        transmission = transmission_raw[wavelength_mask]

        # Apply Savitzky-Golay filter (STAGE 1: Spectral smoothing)
        if len(transmission) >= SG_WINDOW:
            transmission_filtered = savgol_filter(transmission, window_length=SG_WINDOW, polyorder=SG_POLY)
        else:
            transmission_filtered = transmission

        # STAGE 2: Fourier transform refinement (production method)
        try:
            spectrum = transmission_filtered
            n = len(spectrum) - 1

            # Calculate Fourier weights
            phi = np.pi / n * np.arange(1, n)
            phi2 = phi**2
            fourier_weights = phi / (1 + FOURIER_ALPHA * phi2 * (1 + phi2))

            # Initialize Fourier coefficients
            fourier_coeff = np.zeros_like(spectrum)
            fourier_coeff[0] = 2 * (spectrum[-1] - spectrum[0])

            # Linear detrending
            linear_baseline = np.linspace(spectrum[0], spectrum[-1], len(spectrum))
            detrended = spectrum[1:-1] - linear_baseline[1:-1]

            # Apply DST with weights
            dst_result = dst(detrended, type=1)
            fourier_coeff[1:-1] = fourier_weights * dst_result

            # Inverse transform to get derivative
            derivative = idct(fourier_coeff, type=1)

            # Find zero-crossing
            zero_idx = np.searchsorted(derivative, 0)

            if zero_idx > 0 and zero_idx < len(derivative) - 1:
                # Linear regression refinement
                start_idx = max(zero_idx - FOURIER_WINDOW, 0)
                end_idx = min(zero_idx + FOURIER_WINDOW, len(derivative) - 1)

                wl_window = wavelengths[start_idx:end_idx]
                deriv_window = derivative[start_idx:end_idx]

                if len(wl_window) >= 3:
                    slope, intercept, r_value, p_value, std_err = linregress(wl_window, deriv_window)

                    if abs(slope) >= 1e-10:
                        peak_wavelength = -intercept / slope

                        # Sanity check: peak should be within window
                        if peak_wavelength >= wl_window.min() and peak_wavelength <= wl_window.max():
                            # Success - use Fourier refined result
                            pass
                        else:
                            # Fallback to argmin
                            peak_wavelength = wavelengths[np.argmin(transmission_filtered)]
                    else:
                        # Fallback to argmin
                        peak_wavelength = wavelengths[np.argmin(transmission_filtered)]
                else:
                    # Fallback to argmin
                    peak_wavelength = wavelengths[np.argmin(transmission_filtered)]
            else:
                # Fallback to argmin
                peak_wavelength = wavelengths[np.argmin(transmission_filtered)]

        except Exception:
            # Fallback to argmin on any error
            peak_wavelength = wavelengths[np.argmin(transmission_filtered)]

        peak_wavelengths.append(peak_wavelength)
        timestamps.append(i * 1.0)  # Assuming 1 second per timepoint

        if i % 50 == 0:
            print(f"  t={i:3d}: λ={peak_wavelength:.6f} nm")

    peak_wavelengths = np.array(peak_wavelengths)
    timestamps = np.array(timestamps)

    # Normalize to first timepoint (baseline = 0 RU)
    baseline_wavelength = peak_wavelengths[0]
    wavelength_shifts = peak_wavelengths - baseline_wavelength  # Delta from t=0

    # Convert to RU
    RU_values = nm_to_RU(wavelength_shifts)

    # Calculate statistics
    mean_wavelength = np.mean(peak_wavelengths)
    std_wavelength = np.std(peak_wavelengths)
    min_wavelength = np.min(peak_wavelengths)
    max_wavelength = np.max(peak_wavelengths)
    peak_to_peak = max_wavelength - min_wavelength

    # RU statistics (relative to first point)
    std_RU = nm_to_RU(std_wavelength)
    peak_to_peak_RU = nm_to_RU(peak_to_peak)
    min_RU = np.min(RU_values)
    max_RU = np.max(RU_values)

    print("\n📊 STATISTICS:")
    print(f"  Baseline (t=0): {baseline_wavelength:.6f} nm = 0.000 RU")
    print(f"  Mean:          {mean_wavelength:.6f} nm")
    print(f"  Std Dev:       {std_wavelength*1000:.3f} pm = {std_RU:.3f} RU (RMS noise)")
    print(f"  Min:           {min_wavelength:.6f} nm ({min_RU:.3f} RU from baseline)")
    print(f"  Max:           {max_wavelength:.6f} nm ({max_RU:.3f} RU from baseline)")
    print(f"  Peak-to-Peak:  {peak_to_peak*1000:.3f} pm = {peak_to_peak_RU:.3f} RU")

    results[channel] = {
        'timestamps': timestamps,
        'wavelengths': peak_wavelengths,
        'RU_values': RU_values,
        'baseline_wavelength': baseline_wavelength,
        'mean': mean_wavelength,
        'std': std_wavelength,
        'std_RU': std_RU,
        'min': min_wavelength,
        'max': max_wavelength,
        'peak_to_peak': peak_to_peak,
        'peak_to_peak_RU': peak_to_peak_RU,
        'min_RU': min_RU,
        'max_RU': max_RU
    }

# ============================================================================
# VISUALIZATION
# ============================================================================

print(f"\n{'=' * 80}")
print("GENERATING SENSORGRAMS")
print(f"{'=' * 80}")

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
axes = axes.flatten()

colors = ['blue', 'green', 'red', 'purple']

for idx, (channel, color) in enumerate(zip(channels, colors)):
    ax = axes[idx]
    data = results[channel]

    # Plot sensorgram in RU (relative to baseline)
    ax.plot(data['timestamps'], data['RU_values'], '-', color=color, linewidth=1, alpha=0.7)

    # Add baseline (t=0) line
    ax.axhline(0, color='black', linestyle='--', linewidth=1.5, alpha=0.5, label=f"Baseline (t=0): {data['baseline_wavelength']:.3f} nm")

    # Add ±1 std lines
    mean_RU = np.mean(data['RU_values'])
    ax.axhline(mean_RU + data['std_RU'], color='gray', linestyle=':', linewidth=1, alpha=0.5)
    ax.axhline(mean_RU - data['std_RU'], color='gray', linestyle=':', linewidth=1, alpha=0.5)

    # Shade ±1 std region
    ax.fill_between(data['timestamps'],
                     mean_RU - data['std_RU'],
                     mean_RU + data['std_RU'],
                     alpha=0.2, color=color, label=f"±1σ: {data['std_RU']:.2f} RU")

    # Labels and title
    ax.set_xlabel('Time (seconds)', fontsize=11)
    ax.set_ylabel('Response (RU)', fontsize=11)
    ax.set_title(f"{channel}: Peak-to-Peak = {data['peak_to_peak_RU']:.2f} RU",
                 fontsize=12, fontweight='bold', color=color)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9, loc='best')

plt.tight_layout()
plt.savefig('baseline_peak_to_peak_all_channels.png', dpi=300, bbox_inches='tight')
print("\n✓ Saved: baseline_peak_to_peak_all_channels.png")

# Create overlay plot
fig2, ax = plt.subplots(1, 1, figsize=(14, 8))

for idx, (channel, color) in enumerate(zip(channels, colors)):
    data = results[channel]
    # Plot RU values (already normalized to t=0 baseline)
    ax.plot(data['timestamps'], data['RU_values'], '-', color=color,
            linewidth=1.5, alpha=0.7, label=f"{channel}: {data['peak_to_peak_RU']:.2f} RU p-p")

ax.axhline(0, color='black', linestyle='--', linewidth=1.5, alpha=0.5, label='Baseline (t=0)')
ax.set_xlabel('Time (seconds)', fontsize=12)
ax.set_ylabel('Response (RU)', fontsize=12)
ax.set_title('Baseline Noise - All Channels (Relative to t=0)', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3)
ax.legend(fontsize=11, loc='best')

plt.tight_layout()
plt.savefig('baseline_peak_to_peak_overlay.png', dpi=300, bbox_inches='tight')
print("✓ Saved: baseline_peak_to_peak_overlay.png")

# ============================================================================
# SUMMARY TABLE
# ============================================================================

print(f"\n{'=' * 80}")
print("SUMMARY - BASELINE PEAK-TO-PEAK VARIATION")
print(f"{'=' * 80}")

print("CoRU Conversion: 1 RU = 1 nm / 355")
print("Conversion: 1 nm = 355 RU, 1 pm = 0.355 RU")
print("Baseline: First timepoint (t=0) set to 0 RU")

print(f"\n{'Channel':<12} {'Baseline (nm)':<14} {'RMS (RU)':<10} {'Peak-to-Peak (RU)':<18} {'Range (RU)':<20}")
print("-" * 80)
for channel in channels:
    data = results[channel]
    print(f"{channel:<12} {data['baseline_wavelength']:<14.6f} {data['std_RU']:<10.2f} {data['peak_to_peak_RU']:<18.2f} {data['min_RU']:.2f} to {data['max_RU']:.2f}")

print(f"\n{'Channel':<12} {'RMS (pm)':<10} {'Peak-to-Peak (pm)':<18}")
print("-" * 40)
for channel in channels:
    data = results[channel]
    print(f"{channel:<12} {data['std']*1000:<10.3f} {data['peak_to_peak']*1000:<18.3f}")

# Find best and worst channels
best_channel = min(channels, key=lambda c: results[c]['peak_to_peak'])
worst_channel = max(channels, key=lambda c: results[c]['peak_to_peak'])

print(f"\n✅ Best stability:  {best_channel} ({results[best_channel]['peak_to_peak_RU']:.2f} RU peak-to-peak)")
print(f"⚠  Worst stability: {worst_channel} ({results[worst_channel]['peak_to_peak_RU']:.2f} RU peak-to-peak)")

print(f"\n{'=' * 80}")
print("ANALYSIS COMPLETE")
print(f"{'=' * 80}")
