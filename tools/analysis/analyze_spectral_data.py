"""
Quick Analysis of Collected S-Mode Spectral Data
=================================================

Examine the spectral data to understand what we have and identify
opportunities for ML model improvement.
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json

# Load data
data_dir = Path('spectral_training_data/demo P4SPR 2.0/s/used/20251022_124219')

print("="*70)
print("SPECTRAL DATA ANALYSIS")
print("="*70)

# Load metadata
with open(data_dir / 'metadata.json', 'r') as f:
    metadata = json.load(f)

with open(data_dir / 'summary.json', 'r') as f:
    summary = json.load(f)

# Determine actual mode from signal characteristics
print("\n⚠️  IMPORTANT: Checking if labeled mode matches signal characteristics...")

labeled_mode = summary['mode']

print(f"\nDevice: {metadata['device_serial']}")
print(f"Sensor Quality: {metadata['sensor_quality']}")
print(f"Labeled Mode: {labeled_mode}")
print(f"Collection Date: {metadata['collection_date']}")
print(f"\nSettings:")
print(f"  Integration Time: {metadata['calibration']['A']['integration_time_ms']} ms")
print(f"  LED Intensity: {metadata['calibration']['A']['led_intensity']}%")
print(f"  LED Delay: {metadata['calibration']['A']['led_delay_ms']} ms")

# Analyze each channel
print("\n" + "="*70)
print("CHANNEL STATISTICS")
print("="*70)

channel_data = {}
for channel in ['A', 'B', 'C', 'D']:
    # Load NPZ file
    npz_file = data_dir / f'channel_{channel}.npz'
    data = np.load(npz_file)

    spectra = data['spectra']  # Shape: (num_spectra, num_pixels)
    dark = data['dark']
    timestamps = data['timestamps']

    channel_data[channel] = {
        'spectra': spectra,
        'dark': dark,
        'timestamps': timestamps
    }

    # Calculate statistics
    num_spectra, num_pixels = spectra.shape
    mean_spectrum = np.mean(spectra, axis=0)
    std_spectrum = np.std(spectra, axis=0)

    # Signal levels
    signal_min = np.min(spectra)
    signal_max = np.max(spectra)
    signal_mean = np.mean(spectra)
    signal_std = np.std(spectra)

    # Dark spectrum
    dark_mean = np.mean(dark)

    # Temporal statistics (variation over time)
    temporal_means = np.mean(spectra, axis=1)  # Mean intensity per spectrum
    temporal_drift = temporal_means[-1] - temporal_means[0]
    temporal_drift_pct = (temporal_drift / temporal_means[0]) * 100

    print(f"\n📊 Channel {channel}:")
    print(f"  Spectra collected: {num_spectra}")
    print(f"  Pixels per spectrum: {num_pixels}")
    print(f"  Duration: {timestamps[-1]:.1f} seconds")
    print(f"  Acquisition rate: {num_spectra / timestamps[-1]:.2f} Hz")
    print(f"\n  Signal Statistics:")
    print(f"    Range: {signal_min:.0f} - {signal_max:.0f} counts")
    print(f"    Mean: {signal_mean:.0f} ± {signal_std:.0f} counts")
    print(f"    Dark level: {dark_mean:.0f} counts")
    print(f"    SNR (approx): {signal_mean / dark_mean:.1f}:1")
    print(f"\n  Temporal Behavior:")
    print(f"    Initial mean: {temporal_means[0]:.0f} counts")
    print(f"    Final mean: {temporal_means[-1]:.0f} counts")
    print(f"    Drift: {temporal_drift:+.0f} counts ({temporal_drift_pct:+.2f}%)")
    print(f"  Std over time: {np.std(temporal_means):.1f} counts")

# Infer actual mode from signal characteristics
print("\n" + "="*70)
print("MODE VERIFICATION")
print("="*70)

# Check for saturation (P-mode indicator)
has_saturation = any(np.max(channel_data[ch]['spectra']) >= 65535 for ch in ['A', 'B', 'C', 'D'])
max_signals = {ch: np.max(channel_data[ch]['spectra']) for ch in ['A', 'B', 'C', 'D']}
mean_max_signal = np.mean(list(max_signals.values()))

print(f"\nLabeled mode: {labeled_mode}")
print(f"\nSignal characteristics:")
for ch, max_sig in max_signals.items():
    sat = " [SATURATED]" if max_sig >= 65535 else ""
    print(f"  Channel {ch}: max={max_sig:.0f} counts{sat}")

if has_saturation and mean_max_signal > 50000:
    actual_mode = "P"
    print(f"\n🚨 ACTUAL MODE: P-mode (sensor resonance → saturation)")
    if labeled_mode == "S":
        print(f"⚠️  MISLABELED: Folder says S-mode but signal shows P-mode characteristics!")
        print(f"   Likely cause: Polarizer didn't move from previous P-mode position")
elif mean_max_signal < 35000:
    actual_mode = "S"
    print(f"\n✅ ACTUAL MODE: S-mode (no sensor resonance → low signal)")
    if labeled_mode == "P":
        print(f"⚠️  MISLABELED: Folder says P-mode but signal shows S-mode characteristics!")
else:
    actual_mode = "Unknown"
    print(f"\n⚠️  UNCLEAR: Signal in intermediate range ({mean_max_signal:.0f} counts)")

# Cross-channel comparison
print("\n" + "="*70)
print("CROSS-CHANNEL COMPARISON")
print("="*70)

mean_signals = {ch: np.mean(channel_data[ch]['spectra']) for ch in ['A', 'B', 'C', 'D']}
print(f"\nMean Signal Levels:")
for ch, signal in mean_signals.items():
    print(f"  Channel {ch}: {signal:.0f} counts")

# Channel balance
max_signal = max(mean_signals.values())
min_signal = min(mean_signals.values())
balance = (max_signal - min_signal) / max_signal * 100
print(f"\nChannel Balance: {balance:.1f}% variation")

# Identify potential issues
print("\n" + "="*70)
print("POTENTIAL ISSUES FOR ML DETECTION")
print("="*70)

issues_found = []

for channel in ['A', 'B', 'C', 'D']:
    spectra = channel_data[channel]['spectra']
    timestamps = channel_data[channel]['timestamps']

    # Check for drift
    temporal_means = np.mean(spectra, axis=1)
    drift_pct = abs((temporal_means[-1] - temporal_means[0]) / temporal_means[0]) * 100
    if drift_pct > 1.0:
        issues_found.append(f"Channel {channel}: {drift_pct:.2f}% drift (thermal or LED aging)")

    # Check for noise spikes
    temporal_std = np.std(temporal_means)
    if temporal_std > 100:
        issues_found.append(f"Channel {channel}: High temporal noise (σ={temporal_std:.0f})")

    # Check spectral shape consistency
    first_spectrum = spectra[0, :]
    last_spectrum = spectra[-1, :]
    spectral_correlation = np.corrcoef(first_spectrum, last_spectrum)[0, 1]
    if spectral_correlation < 0.95:
        issues_found.append(f"Channel {channel}: Spectral shape changed (r={spectral_correlation:.3f})")

if issues_found:
    for issue in issues_found:
        print(f"  ⚠️  {issue}")
else:
    print("  ✅ No obvious instrumental issues detected")

# ML Training Insights
print("\n" + "="*70)
print("ML TRAINING INSIGHTS")
print("="*70)

print("\n✅ Data Quality:")
print(f"  • 4 channels × 480 spectra = 1,920 raw spectra")
print(f"  • {num_pixels} pixels per spectrum (full wavelength range)")
print(f"  • 4 Hz acquisition rate (production-matched)")
print(f"  • ~2 min per channel (good for proof of concept)")

print("\n🎯 What ML Can Learn:")
print("  • Baseline spectral signatures per channel")
print("  • Temporal drift patterns (thermal effects)")
print("  • Noise characteristics (instrumental vs signal)")
print("  • Dark spectrum correction effectiveness")
print("  • Channel-to-channel consistency")

print("\n💡 Next Steps:")
print("  1. Collect P-mode data (compare sensor resonance effects)")
print("  2. Collect afterglow data (LED phosphor characterization)")
print("  3. Calculate transmittance (T = signal / reference)")
print("  4. Build features: spectral moments, peak positions, temporal stats")
print("  5. Train classifier: instrumental vs consumable issues")

print("\n" + "="*70)
print("READY FOR VISUALIZATION")
print("="*70)
print("\nGenerating plots...")

# Create visualization
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle(f'{actual_mode}-Mode Spectral Data Analysis - {metadata["device_serial"]} ({metadata["sensor_quality"]} sensor)', fontsize=14, fontweight='bold')

for idx, channel in enumerate(['A', 'B', 'C', 'D']):
    ax = axes[idx // 2, idx % 2]

    spectra = channel_data[channel]['spectra']
    timestamps = channel_data[channel]['timestamps']

    # Plot first, middle, last spectra
    pixels = np.arange(spectra.shape[1])

    ax.plot(pixels, spectra[0, :], 'b-', alpha=0.7, linewidth=1, label=f't=0s')
    ax.plot(pixels, spectra[len(spectra)//2, :], 'g-', alpha=0.7, linewidth=1, label=f't={timestamps[len(spectra)//2]:.0f}s')
    ax.plot(pixels, spectra[-1, :], 'r-', alpha=0.7, linewidth=1, label=f't={timestamps[-1]:.0f}s')
    ax.plot(pixels, channel_data[channel]['dark'].flatten(), 'k--', alpha=0.5, linewidth=1, label='Dark')

    ax.set_xlabel('Pixel Index')
    ax.set_ylabel('Intensity (counts)')
    ax.set_title(f'Channel {channel} - Spectral Stability')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0)

plt.tight_layout()
output_dir = Path('generated-files/characterization')
output_dir.mkdir(parents=True, exist_ok=True)
plt.savefig(output_dir / f'{actual_mode.lower()}_mode_spectral_analysis.png', dpi=150, bbox_inches='tight')
print(f"✅ Saved: {output_dir / f'{actual_mode.lower()}_mode_spectral_analysis.png'}")

# Temporal analysis
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle(f'{actual_mode}-Mode Temporal Analysis - Signal Stability', fontsize=14, fontweight='bold')

for idx, channel in enumerate(['A', 'B', 'C', 'D']):
    ax = axes[idx // 2, idx % 2]

    spectra = channel_data[channel]['spectra']
    timestamps = channel_data[channel]['timestamps']

    # Calculate mean intensity per spectrum over time
    temporal_means = np.mean(spectra, axis=1)

    ax.plot(timestamps, temporal_means, 'b-', linewidth=1, alpha=0.7)
    ax.axhline(np.mean(temporal_means), color='r', linestyle='--', alpha=0.5, label=f'Mean: {np.mean(temporal_means):.0f}')

    ax.set_xlabel('Time (seconds)')
    ax.set_ylabel('Mean Intensity (counts)')
    ax.set_title(f'Channel {channel} - Temporal Stability')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(output_dir / f'{actual_mode.lower()}_mode_temporal_analysis.png', dpi=150, bbox_inches='tight')
print(f"✅ Saved: {output_dir / f'{actual_mode.lower()}_mode_temporal_analysis.png'}")

plt.show()

print("\n" + "="*70)
print("ANALYSIS COMPLETE!")
print("="*70)
