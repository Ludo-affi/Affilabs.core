"""Step-by-Step Walkthrough: Peak Finding in Transmission Spectra

This script demonstrates exactly what happens during SPR peak finding,
using your actual baseline recording data.

PROCESSING PIPELINE:
===================
1. Load transmission spectrum (wavelength vs transmission %)
2. Apply wavelength filter (570-720 nm valid range)
3. Find maximum transmission point (SPR peak)
4. Extract peak wavelength
5. Repeat for all time points → Sensorgram
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Load your data
data_file = Path("test_data/baseline_recording_20260126_235959.xlsx")

print("=" * 80)
print("STEP-BY-STEP: SPR PEAK FINDING FROM TRANSMISSION SPECTRUM")
print("=" * 80)

# Load one channel for demonstration
print("\n[STEP 1] Loading transmission spectrum data...")
df = pd.read_excel(data_file, sheet_name='Channel_A')
wavelengths = df['wavelength_nm'].values
print(f"✓ Loaded {len(wavelengths)} wavelength points")
print(f"  Range: {wavelengths[0]:.2f} - {wavelengths[-1]:.2f} nm")

# Get first time point as example
first_spectrum = df['t_0000'].values
print(f"\n[STEP 2] Example spectrum at t=0:")
print(f"  Wavelengths: {len(wavelengths)} points")
print(f"  Transmission values: {len(first_spectrum)} points")
print(f"  Transmission range: {np.min(first_spectrum):.2f}% - {np.max(first_spectrum):.2f}%")

# Apply wavelength filter (570-720 nm)
print("\n[STEP 3] Applying wavelength filter (570-720 nm valid range)...")
valid_mask = (wavelengths >= 570.0) & (wavelengths <= 720.0)
filtered_wavelengths = wavelengths[valid_mask]
filtered_transmission = first_spectrum[valid_mask]

print(f"  Before filter: {len(wavelengths)} points ({wavelengths[0]:.2f}-{wavelengths[-1]:.2f} nm)")
print(f"  After filter:  {len(filtered_wavelengths)} points ({filtered_wavelengths[0]:.2f}-{filtered_wavelengths[-1]:.2f} nm)")
print(f"  Removed: {len(wavelengths) - len(filtered_wavelengths)} points below 570 nm")

# Find the dip (minimum transmission) - SAME AS MAIN.PY
print("\n[STEP 4] Finding SPR dip (minimum transmission - main.py method)...")
peak_idx = np.argmin(filtered_transmission)
peak_wavelength = filtered_wavelengths[peak_idx]
peak_transmission = filtered_transmission[peak_idx]

print(f"  Dip found at index: {peak_idx}")
print(f"  Dip wavelength: {peak_wavelength:.3f} nm")
print(f"  Dip transmission: {peak_transmission:.2f}%")

# Show neighbors
print(f"\n  Peak context (±3 points):")
for i in range(max(0, peak_idx-3), min(len(filtered_wavelengths), peak_idx+4)):
    marker = "👉" if i == peak_idx else "  "
    print(f"    {marker} λ={filtered_wavelengths[i]:.3f} nm → T={filtered_transmission[i]:.2f}%")

# Optional: Parabolic interpolation for sub-pixel accuracy
print("\n[STEP 5] Optional: Sub-pixel peak refinement...")
if 0 < peak_idx < len(filtered_transmission) - 1:
    # Use 3-point parabolic fit
    y0, y1, y2 = filtered_transmission[peak_idx-1:peak_idx+2]
    x0, x1, x2 = filtered_wavelengths[peak_idx-1:peak_idx+2]
    
    # Parabolic interpolation formula
    denom = (y0 - y1) * (x0 - x2) - (y0 - y2) * (x0 - x1)
    if abs(denom) > 1e-10:
        numer = (y0 - y1) * (x0**2 - x2**2) - (y0 - y2) * (x0**2 - x1**2)
        refined_peak = numer / (2 * denom)
        
        print(f"  Discrete peak: {peak_wavelength:.3f} nm")
        print(f"  Refined peak:  {refined_peak:.3f} nm")
        print(f"  Improvement:   {abs(refined_peak - peak_wavelength)*1000:.3f} pm (picometers)")
    else:
        print("  ⚠️  Parabolic fit not applicable (flat peak)")
        refined_peak = peak_wavelength
else:
    print("  ⚠️  Peak at boundary, no refinement possible")
    refined_peak = peak_wavelength

# Now process ALL time points
print("\n[STEP 6] Processing all time points to create sensorgram...")
time_columns = [col for col in df.columns if col.startswith('t_')]
num_timepoints = len(time_columns)

peak_wavelengths = []
peak_transmissions = []

for col in time_columns:
    spectrum = df[col].values
    filtered_spectrum = spectrum[valid_mask]
    
    # Find dip (SAME AS MAIN.PY)
    idx = np.argmin(filtered_spectrum)
    peak_wl = filtered_wavelengths[idx]
    peak_t = filtered_spectrum[idx]
    
    peak_wavelengths.append(peak_wl)
    peak_transmissions.append(peak_t)

peak_wavelengths = np.array(peak_wavelengths)
peak_transmissions = np.array(peak_transmissions)

print(f"✓ Processed {num_timepoints} spectra")
print(f"\n  Peak wavelength statistics:")
print(f"    Mean: {np.mean(peak_wavelengths):.3f} nm")
print(f"    Std:  {np.std(peak_wavelengths):.4f} nm")
print(f"    Min:  {np.min(peak_wavelengths):.3f} nm")
print(f"    Max:  {np.max(peak_wavelengths):.3f} nm")
print(f"    Range: {np.max(peak_wavelengths) - np.min(peak_wavelengths):.4f} nm")

print(f"\n  Peak transmission statistics:")
print(f"    Mean: {np.mean(peak_transmissions):.2f}%")
print(f"    Std:  {np.std(peak_transmissions):.2f}%")

# Visualize the peak finding process
print("\n[STEP 7] Visualizing peak finding...")

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('SPR Dip Finding Process - Channel A (main.py method)', fontsize=14, fontweight='bold')

# Plot 1: Full spectrum with peak marked
ax1 = axes[0, 0]
ax1.plot(wavelengths, first_spectrum, 'b-', linewidth=1, alpha=0.7, label='Full spectrum')
ax1.axvline(570, color='red', linestyle='--', alpha=0.5, label='Filter boundary (570 nm)')
ax1.plot(peak_wavelength, peak_transmission, 'ro', markersize=10, label=f'Peak: {peak_wavelength:.2f} nm')
ax1.set_xlabel('Wavelength (nm)')
ax1.set_ylabel('Transmission (%)')
ax1.set_title('Full Transmission Spectrum (t=0) - Dip marked')
ax1.grid(True, alpha=0.3)
ax1.legend()

# Plot 2: Zoomed on peak region
ax2 = axes[0, 1]
zoom_range = 20  # nm
zoom_mask = (filtered_wavelengths >= peak_wavelength - zoom_range) & \
            (filtered_wavelengths <= peak_wavelength + zoom_range)
ax2.plot(filtered_wavelengths[zoom_mask], filtered_transmission[zoom_mask], 
         'b-', linewidth=2, marker='o', markersize=4)
ax2.plot(peak_wavelength, peak_transmission, 'ro', markersize=12, 
         label=f'Peak: {peak_wavelength:.3f} nm')
ax2.set_xlabel('Wavelength (nm)')
ax2.set_ylabel('Transmission (%)')
ax2.set_title(f'Zoomed Dip Region (±{zoom_range} nm)')
ax2.grid(True, alpha=0.3)
ax2.legend()

# Plot 3: Sensorgram (peak wavelength vs time)
ax3 = axes[1, 0]
metadata = pd.read_excel(data_file, sheet_name='Metadata')
duration = metadata['duration_seconds'].iloc[0]
time_axis = np.linspace(0, duration, num_timepoints)
ax3.plot(time_axis, peak_wavelengths, 'b-', linewidth=1.5)
mean_wl = np.mean(peak_wavelengths)
ax3.axhline(mean_wl, color='red', linestyle='--', alpha=0.5, 
            label=f'Mean: {mean_wl:.3f} nm')
ax3.set_xlabel('Time (seconds)')
ax3.set_ylabel('Dip Wavelength (nm)')
ax3.set_title('Sensorgram (SPR Dip Wavelength vs Time)')
ax3.grid(True, alpha=0.3)
ax3.legend()

# Plot 4: Peak transmission vs time
ax4 = axes[1, 1]
ax4.plot(time_axis, peak_transmissions, 'g-', linewidth=1.5)
mean_t = np.mean(peak_transmissions)
ax4.axhline(mean_t, color='red', linestyle='--', alpha=0.5, 
            label=f'Mean: {mean_t:.2f}%')
ax4.set_xlabel('Time (seconds)')
ax4.set_ylabel('Dip Transmission (%)')
ax4.set_title('Dip Transmission vs Time')
ax4.grid(True, alpha=0.3)
ax4.legend()

plt.tight_layout()

output_file = data_file.parent / f"{data_file.stem}_peak_finding_walkthrough.png"
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"\n✓ Saved visualization: {output_file}")

plt.show()

# Summary
print("\n" + "=" * 80)
print("SUMMARY: WHAT HAPPENS IN PEAK FINDING")
print("=" * 80)
print("""
1. INPUT:  Transmission spectrum (wavelength vs transmission %)
           Example: 794 points from 563.79 to 719.80 nm

2. FILTER: Remove unreliable data below 570 nm
           Result: ~650 points from 570 to 720 nm (valid range)

3. FIND:   Locate MINIMUM transmission point (DIP)
           Method: np.argmin(transmission) → index of dip (SAME AS MAIN.PY)
           
4. EXTRACT: Get wavelength at dip index
           Result: Dip wavelength (SPR resonance)

5. REPEAT:  Do this for every time point
           Result: Array of dip wavelengths over time = SENSORGRAM

6. OUTPUT:  Sensorgram showing SPR dip shift
           - Baseline drift
           - Noise level
           - Binding events (if any)

KEY INSIGHT:
-----------
Your transmission spectrum already contains ALL the information.
Dip finding is just: wavelength[argmin(transmission)]

No complex algorithms needed - the dip is simply where transmission is LOWEST!
This is exactly how main.py does it.
""")

print("\nYour baseline data shows:")
print(f"  • Stable peak at {np.mean(peak_wavelengths):.3f} ± {np.std(peak_wavelengths):.4f} nm")
print(f"  • Peak transmission: {np.mean(peak_transmissions):.1f}%")
print(f"  • Baseline noise: {np.std(peak_wavelengths)*1000:.2f} pm (picometers)")
print("=" * 80)
