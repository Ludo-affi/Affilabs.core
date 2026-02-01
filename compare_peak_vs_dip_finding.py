"""Peak vs Dip Finding - Comparison with Main.py

This clarifies the difference between:
- PEAK finding (argmax) - for transmission peaks
- DIP finding (argmin) - for transmission dips

Your baseline data shows PEAKS, so we use argmax.
Main.py uses argmin for DIPs (standard SPR configuration).
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Load your data
data_file = Path("test_data/baseline_recording_20260126_235959.xlsx")
df = pd.read_excel(data_file, sheet_name='Channel_A')
wavelengths = df['wavelength_nm'].values
first_spectrum = df['t_0000'].values

# Filter to valid range
valid_mask = (wavelengths >= 570) & (wavelengths <= 720)
filtered_wl = wavelengths[valid_mask]
filtered_trans = first_spectrum[valid_mask]

print("=" * 80)
print("PEAK vs DIP FINDING - WHAT'S THE DIFFERENCE?")
print("=" * 80)

print("\n[YOUR DATA ANALYSIS]")
print(f"Transmission range: {filtered_trans.min():.2f}% - {filtered_trans.max():.2f}%")

# Find BOTH peak and dip
peak_idx = np.argmax(filtered_trans)  # Find MAXIMUM (peak)
dip_idx = np.argmin(filtered_trans)   # Find MINIMUM (dip)

peak_wl = filtered_wl[peak_idx]
peak_val = filtered_trans[peak_idx]

dip_wl = filtered_wl[dip_idx]
dip_val = filtered_trans[dip_idx]

print("\nIf we use argmax (PEAK finding):")
print(f"  ✓ Peak at: {peak_wl:.2f} nm with transmission = {peak_val:.2f}%")

print("\nIf we use argmin (DIP finding):")
print(f"  ✗ Dip at: {dip_wl:.2f} nm with transmission = {dip_val:.2f}%")

print("\n" + "=" * 80)
print("WHICH METHOD SHOULD YOU USE?")
print("=" * 80)

print("""
Your transmission spectrum shows a PEAK (maximum), not a dip.
This means:

✅ USE: peak_wavelength = wavelengths[np.argmax(transmission)]
❌ DON'T USE: wavelengths[np.argmin(transmission)]

WHY THE DIFFERENCE?
===================

Standard SPR setup (what main.py expects):
- Transmission shows a DIP (minimum) at resonance wavelength
- SPR absorbs light at resonance → lower transmission
- Use np.argmin() to find the dip

Your current setup (based on this data):
- Transmission shows a PEAK (maximum) 
- Higher transmission at certain wavelength
- Use np.argmax() to find the peak

POSSIBLE CAUSES:
================
1. Different polarizer configuration
2. Inverted P/S ratio calculation
3. Different optical setup
4. Reference normalization method

MAIN.PY STANDARD IMPLEMENTATION:
================================
The production code in main.py uses:

    # Find SPR dip (minimum transmission)
    min_idx = np.argmin(transmission_spectrum)
    spr_wavelength = wavelengths[min_idx]

This is correct for standard SPR where resonance creates a DIP.

YOUR DATA REQUIRES:
==================
    # Find peak (maximum transmission)
    peak_idx = np.argmax(transmission_spectrum)
    spr_wavelength = wavelengths[peak_idx]

""")

# Visualize the difference
fig, axes = plt.subplots(2, 1, figsize=(12, 10))
fig.suptitle('Peak vs Dip Finding Comparison', fontsize=14, fontweight='bold')

# Plot 1: Your data with PEAK marked
ax1 = axes[0]
ax1.plot(filtered_wl, filtered_trans, 'b-', linewidth=1.5, label='Transmission spectrum')
ax1.plot(peak_wl, peak_val, 'go', markersize=15, label=f'PEAK (argmax): {peak_wl:.2f} nm', zorder=5)
ax1.plot(dip_wl, dip_val, 'rx', markersize=15, markeredgewidth=3, label=f'Wrong (argmin): {dip_wl:.2f} nm', zorder=5)
ax1.set_xlabel('Wavelength (nm)')
ax1.set_ylabel('Transmission (%)')
ax1.set_title('YOUR DATA: Shows PEAK → Use argmax()', fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend(fontsize=10)
ax1.axhline(100, color='gray', linestyle='--', alpha=0.3, linewidth=1)

# Plot 2: Simulated standard SPR with DIP
# Create simulated dip for comparison
sim_wl = filtered_wl
sim_baseline = 100  # Start at 100% transmission
dip_center = 650  # Resonance at 650 nm
dip_width = 30
dip_depth = 60  # 40% transmission at dip

# Gaussian dip
sim_trans = sim_baseline - dip_depth * np.exp(-((sim_wl - dip_center) ** 2) / (2 * (dip_width / 2.35) ** 2))

sim_dip_idx = np.argmin(sim_trans)
sim_dip_wl = sim_wl[sim_dip_idx]
sim_dip_val = sim_trans[sim_dip_idx]

ax2 = axes[1]
ax2.plot(sim_wl, sim_trans, 'r-', linewidth=1.5, label='Simulated SPR transmission')
ax2.plot(sim_dip_wl, sim_dip_val, 'go', markersize=15, label=f'DIP (argmin): {sim_dip_wl:.2f} nm', zorder=5)
ax2.set_xlabel('Wavelength (nm)')
ax2.set_ylabel('Transmission (%)')
ax2.set_title('STANDARD SPR: Shows DIP → Use argmin() [main.py default]', fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.legend(fontsize=10)
ax2.axhline(100, color='gray', linestyle='--', alpha=0.3, linewidth=1)
ax2.set_ylim(0, 120)

plt.tight_layout()

output_file = data_file.parent / "peak_vs_dip_comparison.png"
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"\n✓ Saved visualization: {output_file}\n")

plt.show()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"""
YOUR DATA:    Peak at {peak_wl:.2f} nm → USE argmax()
STANDARD SPR: Dip at resonance → main.py uses argmin()

⚠️  IMPORTANT: My walkthrough script correctly used argmax() for YOUR data.
   The standard main.py implementation uses argmin() for conventional SPR dips.

If your actual SPR setup shows dips (like standard configurations),
you should use argmin() like main.py does.

If your data consistently shows peaks like this baseline recording,
then argmax() is correct for your specific setup.
""")
