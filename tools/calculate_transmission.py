"""Calculate transmission spectra from S and P polarization data."""
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from datetime import datetime
import csv

from settings.settings import ROOT_DIR

# Load the two most recent NPZ files
calib_dir = Path(ROOT_DIR) / "calibration_data"
npz_files = sorted(calib_dir.glob("s_roi_stability_*_spectra.npz"),
                   key=lambda p: p.stat().st_mtime, reverse=True)

if len(npz_files) < 2:
    print(f"Error: Need 2 NPZ files, found {len(npz_files)}")
    exit(1)

p_pol_file = npz_files[0]  # Most recent = P
s_pol_file = npz_files[1]  # Second most recent = S

# Get corresponding CSV files for dark noise
s_csv_file = s_pol_file.with_name(s_pol_file.stem.replace('_spectra', '') + '.csv')
p_csv_file = p_pol_file.with_name(p_pol_file.stem.replace('_spectra', '') + '.csv')

print("="*80)
print("TRANSMISSION SPECTRUM CALCULATION")
print("="*80)
print(f"S-pol file: {s_pol_file.name}")
print(f"P-pol file: {p_pol_file.name}")
print()

# Load data
s_data = np.load(s_pol_file)
p_data = np.load(p_pol_file)

wavelengths = s_data['wavelengths']
roi_nm = s_data['roi_nm']

# Use dark baseline values from the acquisition runs
# S-pol: 3035.5 counts, P-pol: 3041.3 counts
s_dark = 3035.5
p_dark = 3041.3

print(f"Wavelengths: {len(wavelengths)} pixels ({wavelengths[0]:.1f}-{wavelengths[-1]:.1f} nm)")
print(f"S-pol dark noise: {s_dark:.1f} counts")
print(f"P-pol dark noise: {p_dark:.1f} counts")
print()

# Organize data by channel
channels = ['a', 'b', 'c', 'd']

# Count measurements per channel
for ch in channels:
    s_key = f'spectra_{ch}'
    p_key = f'spectra_{ch}'
    if s_key in s_data and p_key in p_data:
        print(f"Channel {ch.upper()}: S-pol={len(s_data[s_key])}, P-pol={len(p_data[p_key])} measurements")

print()

# Calculate transmission spectra: T = (P - Dark_p) / (S - Dark_s)
print("Calculating transmission spectra per channel...")
print()

transmission_by_channel = {}

for ch in channels:
    s_spec_key = f'spectra_{ch}'
    s_time_key = f'times_{ch}'
    p_spec_key = f'spectra_{ch}'
    p_time_key = f'times_{ch}'

    if s_spec_key not in s_data or p_spec_key not in p_data:
        print(f"Channel {ch.upper()}: Missing data, skipping")
        continue

    s_spectra = s_data[s_spec_key]
    s_times = s_data[s_time_key]
    p_spectra = p_data[p_spec_key]
    p_times = p_data[p_time_key]

    # Match S and P measurements (use minimum count)
    n_pairs = min(len(s_spectra), len(p_spectra))

    transmission_spectra = []
    transmission_times = []

    for i in range(n_pairs):
        s_spec = s_spectra[i]
        p_spec = p_spectra[i]

        # Subtract dark noise
        s_corrected = s_spec - s_dark
        p_corrected = p_spec - p_dark

        # Calculate transmission: T = P / S (light transmitted through sensor)
        # Add small epsilon to avoid division by zero
        epsilon = 1.0
        transmission = p_corrected / (s_corrected + epsilon)

        transmission_spectra.append(transmission)
        transmission_times.append((s_times[i] + p_times[i]) / 2)  # Average time

    transmission_by_channel[ch] = {
        'times': np.array(transmission_times),
        'spectra': np.array(transmission_spectra)
    }

    print(f"Channel {ch.upper()}: {len(transmission_spectra)} transmission spectra")

print()

# Save transmission data
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = calib_dir / f"transmission_spectra_{timestamp}.npz"

print(f"Saving transmission data to: {output_file.name}")

save_dict = {
    'wavelengths': wavelengths,
    'roi_nm': roi_nm,
    's_dark_noise': s_dark,
    'p_dark_noise': p_dark,
}

for ch in channels:
    if ch in transmission_by_channel:
        save_dict[f'times_{ch}'] = transmission_by_channel[ch]['times']
        save_dict[f'spectra_{ch}'] = transmission_by_channel[ch]['spectra']

np.savez_compressed(
    output_file,
    **save_dict,
    s_pol_file=str(s_pol_file.name),
    p_pol_file=str(p_pol_file.name)
)

# Plot example transmission spectra
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('Transmission Spectra (T = S/P with dark subtraction)', fontsize=14, fontweight='bold')

for idx, ch in enumerate(channels):
    ax = axes[idx // 2, idx % 2]

    if ch not in transmission_by_channel:
        ax.text(0.5, 0.5, f'Channel {ch.upper()}\nNo data',
                ha='center', va='center', transform=ax.transAxes)
        continue

    trans_data = transmission_by_channel[ch]
    spectra = trans_data['spectra']
    times = trans_data['times']

    # Plot first, middle, and last spectra
    if len(spectra) > 0:
        ax.plot(wavelengths, spectra[0], 'b-', alpha=0.7, linewidth=1.5, label=f't={times[0]:.1f}s')
        if len(spectra) > 2:
            mid = len(spectra) // 2
            ax.plot(wavelengths, spectra[mid], 'g-', alpha=0.7, linewidth=1.5, label=f't={times[mid]:.1f}s')
        ax.plot(wavelengths, spectra[-1], 'r-', alpha=0.7, linewidth=1.5, label=f't={times[-1]:.1f}s')

    ax.set_xlabel('Wavelength (nm)', fontsize=10)
    ax.set_ylabel('Transmission (S/P)', fontsize=10)
    ax.set_title(f'Channel {ch.upper()} - {len(spectra)} spectra', fontsize=11, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(wavelengths[0], wavelengths[-1])

    # Print transmission range
    t_min = spectra.min()
    t_max = spectra.max()
    t_mean = spectra.mean()
    print(f"Channel {ch.upper()}: T range = [{t_min:.3f}, {t_max:.3f}], mean = {t_mean:.3f}")

plt.tight_layout()
plot_file = calib_dir / f"transmission_spectra_{timestamp}.png"
plt.savefig(plot_file, dpi=150, bbox_inches='tight')
print()
print(f"Transmission plot saved: {plot_file.name}")

print()
print("="*80)
print("TRANSMISSION CALCULATION COMPLETE")
print("="*80)
print(f"Output files:")
print(f"  Data: {output_file.name}")
print(f"  Plot: {plot_file.name}")
print()
print("Next step: Apply centroid method to analyze peak shifts")
