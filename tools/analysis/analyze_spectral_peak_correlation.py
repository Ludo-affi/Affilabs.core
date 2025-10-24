"""
Analyze Channel A Spectral Data - Peak Variation Correlation
=============================================================

Goal: Understand how RAW spectral characteristics influence SPR peak variation.

This is the core insight:
- If ML can learn which spectral features predict poor peak stability,
- Then we can detect consumable/instrumental issues BEFORE they affect measurements
- No need to monitor downstream - just monitor raw spectra quality

Analysis:
1. Load S-mode and P-mode spectral data (Channel A)
2. Calculate transmittance spectra (T = P / S)
3. Compute SPR peak position for each spectrum (time series)
4. Measure peak variation (RU stability)
5. Correlate spectral features with peak variation
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json
from scipy.signal import find_peaks, savgol_filter
from scipy.ndimage import gaussian_filter1d

# Load the latest S-mode and P-mode data for Channel A
data_root = Path('spectral_training_data/demo P4SPR 2.0')

# Find latest folders
s_folders = sorted((data_root / 's' / 'used').glob('*'), reverse=True)
p_folders = sorted((data_root / 'p' / 'used').glob('*'), reverse=True)

if not s_folders or not p_folders:
    print("❌ No data found!")
    exit(1)

s_latest = s_folders[0]
p_latest = p_folders[0]

print("="*70)
print("SPECTRAL CHARACTERISTICS → PEAK VARIATION ANALYSIS")
print("="*70)
print(f"\nS-mode data: {s_latest.name}")
print(f"P-mode data: {p_latest.name}")

# Load Channel A data
s_data = np.load(s_latest / 'channel_A.npz')
p_data = np.load(p_latest / 'channel_A.npz')

s_spectra = s_data['spectra']  # Shape: (N, 3648)
s_dark = s_data['dark']
s_timestamps = s_data['timestamps']

p_spectra = p_data['spectra']  # Shape: (N, 3648)
p_dark = p_data['dark']
p_timestamps = p_data['timestamps']

print(f"\nS-mode: {len(s_spectra)} spectra over {s_timestamps[-1]:.1f}s")
print(f"P-mode: {len(p_spectra)} spectra over {p_timestamps[-1]:.1f}s")

# Verify we have matching number of spectra
min_spectra = min(len(s_spectra), len(p_spectra))
s_spectra = s_spectra[:min_spectra]
p_spectra = p_spectra[:min_spectra]
s_timestamps = s_timestamps[:min_spectra]
p_timestamps = p_timestamps[:min_spectra]

print(f"\nUsing {min_spectra} matching spectra for analysis")

print("\n" + "="*70)
print("STEP 1: CALCULATE TRANSMITTANCE SPECTRA")
print("="*70)

# Dark correction
s_corrected = s_spectra - s_dark
p_corrected = p_spectra - p_dark

# Avoid divide by zero
s_corrected = np.maximum(s_corrected, 1)

# Transmittance: T = P / S
transmittance = p_corrected / s_corrected

print(f"\nTransmittance shape: {transmittance.shape}")
print(f"T range: {np.min(transmittance):.3f} - {np.max(transmittance):.3f}")

# Smooth transmittance spectra (reduce noise)
transmittance_smooth = np.array([
    savgol_filter(t, window_length=51, polyorder=3)
    for t in transmittance
])

print("\n" + "="*70)
print("STEP 2: FIND SPR PEAK (RESONANCE DIP) IN EACH SPECTRUM")
print("="*70)

# SPR shows up as a DIP in transmittance
# Find minimum (peak of -T)
peak_positions = []
peak_depths = []
peak_widths = []

pixel_range = np.arange(transmittance.shape[1])

for i, t in enumerate(transmittance_smooth):
    # Invert to find dip as peak
    inverted = -t

    # Find peaks (dips in original)
    peaks, properties = find_peaks(inverted, prominence=0.1, width=10)

    if len(peaks) > 0:
        # Take strongest peak
        strongest_idx = np.argmax(properties['prominences'])
        peak_pixel = peaks[strongest_idx]
        peak_positions.append(peak_pixel)
        peak_depths.append(-inverted[peak_pixel])  # Depth in transmittance
        peak_widths.append(properties['widths'][strongest_idx])
    else:
        # No clear peak found
        peak_positions.append(np.nan)
        peak_depths.append(np.nan)
        peak_widths.append(np.nan)

peak_positions = np.array(peak_positions)
peak_depths = np.array(peak_depths)
peak_widths = np.array(peak_widths)

# Remove NaN values
valid_mask = ~np.isnan(peak_positions)
peak_positions_valid = peak_positions[valid_mask]
timestamps_valid = s_timestamps[valid_mask]

print(f"\nFound SPR peaks in {np.sum(valid_mask)}/{len(peak_positions)} spectra")
print(f"Peak position range: {np.min(peak_positions_valid):.1f} - {np.max(peak_positions_valid):.1f} pixels")

# Convert pixel variation to RU (rough approximation: 1 pixel ≈ 0.1 nm ≈ 100 RU)
# This is device-specific, but gives relative variation
pixel_to_ru = 100  # Approximate conversion factor

peak_variation_pixels = np.std(peak_positions_valid)
peak_variation_ru = peak_variation_pixels * pixel_to_ru

print(f"\n📊 PEAK VARIATION (Sensorgram Stability):")
print(f"   Pixel variation: {peak_variation_pixels:.2f} pixels")
print(f"   RU variation (approx): {peak_variation_ru:.1f} RU p-p")

print("\n" + "="*70)
print("STEP 3: EXTRACT SPECTRAL FEATURES")
print("="*70)

# Features that might predict peak variation:
# 1. Signal level (P-mode intensity)
# 2. Signal stability (temporal drift)
# 3. Signal-to-noise ratio
# 4. Spectral shape consistency

# Feature 1: Mean P-mode signal over time
p_mean_intensity = np.mean(p_corrected, axis=1)

# Feature 2: Temporal drift (signal change over time)
p_drift = p_mean_intensity[-1] - p_mean_intensity[0]
p_drift_pct = (p_drift / p_mean_intensity[0]) * 100

# Feature 3: Signal noise (std across wavelengths)
p_noise = np.std(p_corrected, axis=1)

# Feature 4: Spectral correlation (shape consistency)
reference_spectrum = transmittance_smooth[0]
spectral_correlations = []
for t in transmittance_smooth:
    corr = np.corrcoef(reference_spectrum, t)[0, 1]
    spectral_correlations.append(corr)
spectral_correlations = np.array(spectral_correlations)

print("\n📊 SPECTRAL FEATURES:")
print(f"   P-mode signal: {np.mean(p_mean_intensity):.0f} ± {np.std(p_mean_intensity):.0f} counts")
print(f"   Temporal drift: {p_drift:+.0f} counts ({p_drift_pct:+.1f}%)")
print(f"   Noise level: {np.mean(p_noise):.0f} counts")
print(f"   Spectral correlation: {np.mean(spectral_correlations):.4f} (min: {np.min(spectral_correlations):.4f})")

print("\n" + "="*70)
print("STEP 4: CORRELATE SPECTRAL FEATURES WITH PEAK VARIATION")
print("="*70)

# Calculate rolling peak variation (window-based)
window = 50  # 50 spectra = ~12.5 seconds @ 4 Hz
rolling_peak_std = []
rolling_times = []

for i in range(0, len(peak_positions_valid) - window, 10):
    window_peaks = peak_positions_valid[i:i+window]
    rolling_peak_std.append(np.std(window_peaks))
    rolling_times.append(timestamps_valid[i + window//2])

rolling_peak_std = np.array(rolling_peak_std)
rolling_times = np.array(rolling_times)

# Correlate with features in same windows
rolling_p_mean = []
rolling_p_noise = []
rolling_corr = []

for i in range(0, len(peak_positions_valid) - window, 10):
    indices = np.where(valid_mask)[0][i:i+window]
    rolling_p_mean.append(np.mean(p_mean_intensity[indices]))
    rolling_p_noise.append(np.mean(p_noise[indices]))
    rolling_corr.append(np.mean(spectral_correlations[indices]))

rolling_p_mean = np.array(rolling_p_mean)
rolling_p_noise = np.array(rolling_p_noise)
rolling_corr = np.array(rolling_corr)

# Calculate correlations
corr_intensity = np.corrcoef(rolling_p_mean, rolling_peak_std)[0, 1]
corr_noise = np.corrcoef(rolling_p_noise, rolling_peak_std)[0, 1]
corr_shape = np.corrcoef(rolling_corr, rolling_peak_std)[0, 1]

print("\n🎯 FEATURE CORRELATIONS WITH PEAK VARIATION:")
print(f"   Signal intensity ↔ Peak variation: r = {corr_intensity:+.3f}")
print(f"   Signal noise ↔ Peak variation:     r = {corr_noise:+.3f}")
print(f"   Spectral shape ↔ Peak variation:   r = {corr_shape:+.3f}")

print("\n💡 INTERPRETATION:")
if abs(corr_intensity) > 0.3:
    direction = "increases" if corr_intensity > 0 else "decreases"
    print(f"   • Peak variation {direction} when signal intensity changes (r={corr_intensity:+.2f})")
    print(f"     → Thermal drift or LED aging affects peak stability")

if abs(corr_noise) > 0.3:
    direction = "increases" if corr_noise > 0 else "decreases"
    print(f"   • Peak variation {direction} with signal noise (r={corr_noise:+.2f})")
    print(f"     → Noisy spectra → unstable peak detection")

if abs(corr_shape) < -0.3:
    print(f"   • Peak variation increases when spectral shape changes (r={corr_shape:+.2f})")
    print(f"     → Spectral distortion → poor peak fitting")

print("\n" + "="*70)
print("STEP 5: VISUALIZE RESULTS")
print("="*70)

fig = plt.figure(figsize=(16, 12))

# Plot 1: Transmittance spectra over time
ax1 = plt.subplot(3, 2, 1)
# Show every 20th spectrum with color gradient
indices = np.linspace(0, len(transmittance_smooth)-1, 20, dtype=int)
colors = plt.cm.viridis(np.linspace(0, 1, len(indices)))
for i, idx in enumerate(indices):
    ax1.plot(transmittance_smooth[idx], color=colors[i], alpha=0.6, linewidth=0.5)
ax1.set_xlabel('Pixel Index')
ax1.set_ylabel('Transmittance (P/S)')
ax1.set_title('Transmittance Spectra Evolution (20 samples)')
ax1.grid(True, alpha=0.3)

# Plot 2: Peak position over time
ax2 = plt.subplot(3, 2, 2)
ax2.plot(timestamps_valid, peak_positions_valid, 'b-', linewidth=1, alpha=0.7)
ax2.axhline(np.mean(peak_positions_valid), color='r', linestyle='--',
            label=f'Mean: {np.mean(peak_positions_valid):.1f} px')
ax2.fill_between(timestamps_valid,
                  np.mean(peak_positions_valid) - peak_variation_pixels,
                  np.mean(peak_positions_valid) + peak_variation_pixels,
                  color='r', alpha=0.2, label=f'±{peak_variation_pixels:.2f} px')
ax2.set_xlabel('Time (s)')
ax2.set_ylabel('Peak Position (pixels)')
ax2.set_title(f'SPR Peak Stability ({peak_variation_ru:.1f} RU p-p variation)')
ax2.legend()
ax2.grid(True, alpha=0.3)

# Plot 3: Signal intensity vs peak variation
ax3 = plt.subplot(3, 2, 3)
ax3.scatter(rolling_p_mean, rolling_peak_std * pixel_to_ru, alpha=0.6, s=20)
ax3.set_xlabel('P-mode Signal Intensity (counts)')
ax3.set_ylabel('Local Peak Variation (RU)')
ax3.set_title(f'Signal Intensity vs Peak Variation (r={corr_intensity:+.2f})')
ax3.grid(True, alpha=0.3)

# Plot 4: Signal noise vs peak variation
ax4 = plt.subplot(3, 2, 4)
ax4.scatter(rolling_p_noise, rolling_peak_std * pixel_to_ru, alpha=0.6, s=20, color='orange')
ax4.set_xlabel('Signal Noise (counts)')
ax4.set_ylabel('Local Peak Variation (RU)')
ax4.set_title(f'Signal Noise vs Peak Variation (r={corr_noise:+.2f})')
ax4.grid(True, alpha=0.3)

# Plot 5: Spectral shape correlation vs peak variation
ax5 = plt.subplot(3, 2, 5)
ax5.scatter(rolling_corr, rolling_peak_std * pixel_to_ru, alpha=0.6, s=20, color='green')
ax5.set_xlabel('Spectral Correlation (vs t=0)')
ax5.set_ylabel('Local Peak Variation (RU)')
ax5.set_title(f'Spectral Shape vs Peak Variation (r={corr_shape:+.2f})')
ax4.grid(True, alpha=0.3)

# Plot 6: Temporal drift visualization
ax6 = plt.subplot(3, 2, 6)
ax6.plot(s_timestamps, p_mean_intensity, 'b-', linewidth=1, label='P-mode signal')
ax6.set_xlabel('Time (s)')
ax6.set_ylabel('Mean Intensity (counts)')
ax6.set_title(f'P-mode Temporal Drift ({p_drift_pct:+.1f}%)')
ax6.legend()
ax6.grid(True, alpha=0.3)

plt.tight_layout()

output_dir = Path('generated-files/ml_analysis')
output_dir.mkdir(parents=True, exist_ok=True)
plt.savefig(output_dir / 'spectral_features_peak_variation_analysis.png', dpi=150, bbox_inches='tight')
print(f"\n✅ Plot saved: {output_dir / 'spectral_features_peak_variation_analysis.png'}")

plt.show()

print("\n" + "="*70)
print("ML TRAINING INSIGHTS")
print("="*70)

print("\n🎯 What ML should learn from this data:")
print("\n1. **Temporal Drift Pattern**:")
print(f"   - {p_drift_pct:+.1f}% signal decay over {s_timestamps[-1]:.0f}s")
print(f"   - This is INSTRUMENTAL (thermal/LED aging)")
print(f"   - ML can flag when drift exceeds normal bounds")

print("\n2. **Peak Variation Predictors**:")
strongest_predictor = max(
    [('Signal Intensity', abs(corr_intensity)),
     ('Signal Noise', abs(corr_noise)),
     ('Spectral Shape', abs(corr_shape))],
    key=lambda x: x[1]
)
print(f"   - Strongest predictor: {strongest_predictor[0]} (r={strongest_predictor[1]:.2f})")
print(f"   - ML can detect when this feature goes out of bounds")

print("\n3. **Raw Data Features for ML**:")
print(f"   - Signal level: {np.mean(p_mean_intensity):.0f} counts")
print(f"   - Signal stability: {np.std(p_mean_intensity):.0f} counts std")
print(f"   - Noise level: {np.mean(p_noise):.0f} counts")
print(f"   - Spectral consistency: r={np.mean(spectral_correlations):.4f}")

print("\n4. **Prediction Goal**:")
print(f"   Current peak variation: {peak_variation_ru:.1f} RU")
print(f"   Good quality threshold: < 50 RU")
print(f"   Poor quality threshold: > 150 RU")
print(f"   → ML classifies: GOOD / WARNING / BAD based on raw spectra")

print("\n5. **Action Items**:")
print(f"   ✅ Collect data from multiple devices/sensors")
print(f"   ✅ Label with known good/bad conditions")
print(f"   ✅ Extract features: signal, noise, drift, shape")
print(f"   ✅ Train classifier: predict peak variation from raw spectra")
print(f"   ✅ Deploy: Monitor raw spectra → predict downstream quality")

print("\n" + "="*70)
print("ANALYSIS COMPLETE!")
print("="*70)
