"""Visualize Sensorgram from Baseline Recording Data

Loads the baseline recording Excel file and generates sensorgrams showing
the SPR peak wavelength shift over time for all channels.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# File path
data_file = Path("test_data/baseline_recording_20260126_235959.xlsx")

print("=" * 80)
print("BASELINE RECORDING SENSORGRAM VISUALIZATION")
print("=" * 80)

# Load metadata
print("\n[1] Loading metadata...")
metadata = pd.read_excel(data_file, sheet_name='Metadata')
print(f"Recording start: {metadata['recording_start'].iloc[0]}")
print(f"Duration: {metadata['duration_seconds'].iloc[0]} seconds")
print(f"Integration time: {metadata['integration_time_ms'].iloc[0]:.2f} ms")
print(f"Num scans: {metadata['num_scans'].iloc[0]}")
print(f"Wavelength range: {metadata['wavelength_min'].iloc[0]:.2f} - {metadata['wavelength_max'].iloc[0]:.2f} nm")
print(f"Data points: {metadata['wavelength_points'].iloc[0]}")

# Load data from all channels
print("\n[2] Loading channel data...")
channels = ['Channel_A', 'Channel_B', 'Channel_C', 'Channel_D']
channel_labels = ['A', 'B', 'C', 'D']
channel_data = {}

for channel in channels:
    df = pd.read_excel(data_file, sheet_name=channel)
    channel_data[channel] = df
    num_timepoints = len(df.columns) - 1  # Subtract wavelength column
    print(f"  {channel}: {len(df)} wavelengths × {num_timepoints} timepoints")

# Extract time points
time_columns = [col for col in channel_data['Channel_A'].columns if col.startswith('t_')]
num_points = len(time_columns)
duration = metadata['duration_seconds'].iloc[0]
time_axis = np.linspace(0, duration, num_points)

print(f"\n[3] Processing {num_points} time points over {duration} seconds...")

# Find peak wavelength at each time point for each channel
print("\n[4] Extracting SPR peak wavelengths...")

peak_wavelengths = {}

for i, channel in enumerate(channels):
    df = channel_data[channel]
    wavelengths = df['wavelength_nm'].values
    
    peaks = []
    for col in time_columns:
        spectrum = df[col].values
        
        # Find peak (maximum transmission)
        peak_idx = np.argmax(spectrum)
        peak_wl = wavelengths[peak_idx]
        peaks.append(peak_wl)
    
    peak_wavelengths[channel_labels[i]] = np.array(peaks)
    
    print(f"  Channel {channel_labels[i]}: Peak range {np.min(peaks):.2f} - {np.max(peaks):.2f} nm")

# Calculate statistics
print("\n[5] Baseline Statistics:")
for label in channel_labels:
    peaks = peak_wavelengths[label]
    mean_wl = np.mean(peaks)
    std_wl = np.std(peaks)
    drift = peaks[-1] - peaks[0]
    
    print(f"\n  Channel {label}:")
    print(f"    Mean wavelength: {mean_wl:.3f} nm")
    print(f"    Std deviation: {std_wl:.4f} nm")
    print(f"    Total drift: {drift:.4f} nm")
    print(f"    Noise (RMS): {np.sqrt(np.mean(np.diff(peaks)**2)):.4f} nm")

# Create sensorgram plot
print("\n[6] Creating sensorgram plot...")

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('Baseline Recording Sensorgrams - Phase Photonics\n' + 
             f'Integration: {metadata["integration_time_ms"].iloc[0]:.1f}ms, ' +
             f'Scans: {metadata["num_scans"].iloc[0]}, ' +
             f'Duration: {duration}s',
             fontsize=14, fontweight='bold')

colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

for i, (ax, label) in enumerate(zip(axes.flatten(), channel_labels)):
    peaks = peak_wavelengths[label]
    
    # Plot raw data
    ax.plot(time_axis, peaks, '-', color=colors[i], alpha=0.7, linewidth=1.5, 
            label=f'Channel {label}')
    
    # Add mean line
    mean_wl = np.mean(peaks)
    ax.axhline(mean_wl, color='red', linestyle='--', alpha=0.5, linewidth=1,
               label=f'Mean: {mean_wl:.3f} nm')
    
    # Statistics
    std_wl = np.std(peaks)
    drift = peaks[-1] - peaks[0]
    
    ax.set_xlabel('Time (seconds)', fontsize=11)
    ax.set_ylabel('Peak Wavelength (nm)', fontsize=11)
    ax.set_title(f'Channel {label} (σ={std_wl:.4f} nm, drift={drift:.4f} nm)', 
                 fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', fontsize=9)
    
    # Set y-axis to show small variations
    y_center = mean_wl
    y_range = max(0.5, std_wl * 5)  # At least 0.5 nm range
    ax.set_ylim(y_center - y_range, y_center + y_range)

plt.tight_layout()

# Save plot
output_file = data_file.parent / f"{data_file.stem}_sensorgram.png"
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"\n✅ Sensorgram saved to: {output_file}")

# Create combined overview plot
print("\n[7] Creating combined overview...")

fig2, ax = plt.subplots(1, 1, figsize=(14, 6))
fig2.suptitle('All Channels - Baseline Stability Comparison', 
              fontsize=14, fontweight='bold')

for i, label in enumerate(channel_labels):
    peaks = peak_wavelengths[label]
    # Normalize to first point for drift comparison
    normalized = peaks - peaks[0]
    ax.plot(time_axis, normalized, '-', color=colors[i], linewidth=2, 
            label=f'Channel {label} (σ={np.std(peaks):.4f} nm)', alpha=0.8)

ax.set_xlabel('Time (seconds)', fontsize=12)
ax.set_ylabel('Wavelength Shift from t=0 (nm)', fontsize=12)
ax.set_title('Baseline Drift Comparison (All Channels)', fontsize=13, fontweight='bold')
ax.grid(True, alpha=0.3)
ax.legend(loc='best', fontsize=10)
ax.axhline(0, color='black', linestyle='-', alpha=0.3, linewidth=0.5)

plt.tight_layout()

output_file2 = data_file.parent / f"{data_file.stem}_combined.png"
plt.savefig(output_file2, dpi=150, bbox_inches='tight')
print(f"✅ Combined plot saved to: {output_file2}")

# Show plots
plt.show()

print("\n" + "=" * 80)
print("VISUALIZATION COMPLETE")
print("=" * 80)
print(f"\nGenerated files:")
print(f"  1. {output_file}")
print(f"  2. {output_file2}")
print("\nPlots are now displayed.")
