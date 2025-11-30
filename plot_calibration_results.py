"""Plot calibration results from the latest calibration run.

This script visualizes:
- S-polarization reference spectra (all channels)
- P-polarization reference spectra (all channels)
- Transmission (P/S ratio) for all channels
- QC metrics and warnings
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json

# Hardcoded calibration data from the log output
wavelengths = np.linspace(560.04, 719.93, 1997)

# S-pol reference signals (approximate from log data)
s_pol_ref = {
    'a': np.array([33830, 33139, 33505]),  # Simplified - just showing the pattern
    'b': np.array([35134, 34814, 34517]),
    'c': np.array([31192, 31282, 31043]),
    'd': np.array([32093, 31884, 31828])
}

# P-pol reference signals
p_pol_ref = {
    'a': np.array([44133, 43508, 43883]),
    'b': np.array([47454, 46096, 47206]),
    'c': np.array([46856, 46093, 46545]),
    'd': np.array([46137, 45880, 46269])
}

# QC Results
qc_results = {
    'a': {
        'spr_wavelength': 645.07,
        'spr_depth': 100.87,
        'fwhm': 159.89,
        'p_s_ratio': 5.35,
        's_max_counts': 37183,
        'p_max_counts': 56519,
        'warnings': ['Wide FWHM (159.9nm) - poor sensor contact', 'P/S ratio (5.35) > 1.15 - polarizer may be inverted']
    },
    'b': {
        'spr_wavelength': 655.74,
        'spr_depth': 105.98,
        'fwhm': 159.89,
        'p_s_ratio': 6.54,
        's_max_counts': 38350,
        'p_max_counts': 57070,
        'warnings': ['Wide FWHM (159.9nm) - poor sensor contact', 'P/S ratio (6.54) > 1.15 - polarizer may be inverted']
    },
    'c': {
        'spr_wavelength': 644.82,
        'spr_depth': 102.46,
        'fwhm': 159.89,
        'p_s_ratio': 6.73,
        's_max_counts': 34640,
        'p_max_counts': 56478,
        'warnings': ['Wide FWHM (159.9nm) - poor sensor contact', 'P/S ratio (6.73) > 1.15 - polarizer may be inverted']
    },
    'd': {
        'spr_wavelength': 660.95,
        'spr_depth': 102.81,
        'fwhm': 159.89,
        'p_s_ratio': 6.20,
        's_max_counts': 35312,
        'p_max_counts': 51869,
        'warnings': ['Wide FWHM (159.9nm) - poor sensor contact', 'P/S ratio (6.20) > 1.15 - polarizer may be inverted']
    }
}

# LED intensities
led_intensities = {'a': 255, 'd': 223, 'b': 107, 'c': 101}

# Integration times
s_integration = 35.56  # ms
p_integration = 33.60  # ms

# Create figure with subplots
fig = plt.figure(figsize=(16, 10))
fig.suptitle('Calibration Results - CRITICAL: P/S Ratios Inverted (P > S)',
             fontsize=16, fontweight='bold', color='red')

# Plot 1: S-pol max counts (bar chart)
ax1 = plt.subplot(2, 3, 1)
channels = ['A', 'B', 'C', 'D']
s_max = [qc_results[ch.lower()]['s_max_counts'] for ch in channels]
colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
bars1 = ax1.bar(channels, s_max, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
ax1.set_ylabel('Max Counts', fontsize=12, fontweight='bold')
ax1.set_title('S-Polarization Peak Intensity\n(Should be HIGHER than P)', fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.set_ylim(0, 70000)
for bar, val in zip(bars1, s_max):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1000,
             f'{val:.0f}', ha='center', va='bottom', fontweight='bold')

# Plot 2: P-pol max counts (bar chart)
ax2 = plt.subplot(2, 3, 2)
p_max = [qc_results[ch.lower()]['p_max_counts'] for ch in channels]
bars2 = ax2.bar(channels, p_max, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
ax2.set_ylabel('Max Counts', fontsize=12, fontweight='bold')
ax2.set_title('P-Polarization Peak Intensity\n(Should be LOWER than S)', fontsize=12, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.set_ylim(0, 70000)
for bar, val in zip(bars2, p_max):
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1000,
             f'{val:.0f}', ha='center', va='bottom', fontweight='bold')

# Plot 3: P/S Ratio (bar chart) - THE PROBLEM!
ax3 = plt.subplot(2, 3, 3)
ps_ratios = [qc_results[ch.lower()]['p_s_ratio'] for ch in channels]
bars3 = ax3.bar(channels, ps_ratios, color='red', alpha=0.7, edgecolor='black', linewidth=2)
ax3.axhline(y=1.0, color='green', linestyle='--', linewidth=3, label='Expected: P/S < 1.0')
ax3.axhline(y=1.15, color='orange', linestyle='--', linewidth=2, label='Warning Threshold: 1.15')
ax3.set_ylabel('P/S Ratio', fontsize=12, fontweight='bold')
ax3.set_title('P/S Ratio (ALL INVERTED!)\nExpected: < 1.0, Got: 5-7',
              fontsize=12, fontweight='bold', color='red')
ax3.grid(True, alpha=0.3)
ax3.legend(loc='upper right')
ax3.set_ylim(0, 8)
for bar, val in zip(bars3, ps_ratios):
    ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
             f'{val:.2f}x', ha='center', va='bottom', fontweight='bold', color='red')

# Plot 4: LED Intensities
ax4 = plt.subplot(2, 3, 4)
led_vals = [led_intensities[ch.lower()] for ch in channels]
bars4 = ax4.bar(channels, led_vals, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
ax4.set_ylabel('LED Intensity (0-255)', fontsize=12, fontweight='bold')
ax4.set_title('LED Intensities (Calibrated)', fontsize=12, fontweight='bold')
ax4.set_ylim(0, 280)
ax4.grid(True, alpha=0.3)
for bar, val in zip(bars4, led_vals):
    ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
             f'{val}', ha='center', va='bottom', fontweight='bold')

# Plot 5: SPR Wavelengths
ax5 = plt.subplot(2, 3, 5)
spr_wl = [qc_results[ch.lower()]['spr_wavelength'] for ch in channels]
bars5 = ax5.bar(channels, spr_wl, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
ax5.set_ylabel('Wavelength (nm)', fontsize=12, fontweight='bold')
ax5.set_title('SPR Peak Wavelengths', fontsize=12, fontweight='bold')
ax5.set_ylim(620, 680)
ax5.grid(True, alpha=0.3)
for bar, val in zip(bars5, spr_wl):
    ax5.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
             f'{val:.1f}nm', ha='center', va='bottom', fontweight='bold')

# Plot 6: QC Summary Table
ax6 = plt.subplot(2, 3, 6)
ax6.axis('off')

summary_text = "CRITICAL ISSUES DETECTED:\n\n"
summary_text += "1. ALL P/S RATIOS INVERTED (5-7x instead of <1.0)\n"
summary_text += "   -> Indicates polarizer positions SWAPPED\n"
summary_text += "   -> S=120deg, P=60deg should be S=60deg, P=120deg\n\n"
summary_text += "2. Wide FWHM (159.9nm) on ALL channels\n"
summary_text += "   -> Poor sensor-to-prism contact\n"
summary_text += "   -> Check water application\n\n"
summary_text += "Configuration:\n"
summary_text += f"  S Integration: {s_integration:.2f} ms\n"
summary_text += f"  P Integration: {p_integration:.2f} ms\n"
summary_text += f"  Polarizer: S=120deg, P=60deg (INVERTED)\n\n"
summary_text += "Action Required:\n"
summary_text += "  1. Swap positions: S=60deg, P=120deg\n"
summary_text += "  2. Restart application\n"
summary_text += "  3. Re-run calibration\n"

ax6.text(0.05, 0.95, summary_text, transform=ax6.transAxes,
         fontsize=10, verticalalignment='top', fontfamily='monospace',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.tight_layout()

# Save figure
output_file = 'calibration_analysis_inverted.png'
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"Plot saved to: {output_file}")

# Show plot
plt.show()

# Print summary to console
print("\n" + "=" * 80)
print("CALIBRATION ANALYSIS SUMMARY")
print("=" * 80)
print("\nCRITICAL: Polarizer positions are INVERTED!")
print("\nP/S Ratios (Expected < 1.0):")
for ch in channels:
    ratio = qc_results[ch.lower()]['p_s_ratio']
    print(f"  Channel {ch}: {ratio:.2f}x  (INVERTED)")

print("\nSignal Levels:")
for ch in channels:
    s = qc_results[ch.lower()]['s_max_counts']
    p = qc_results[ch.lower()]['p_max_counts']
    print(f"  Channel {ch}: S={s:>5.0f} counts, P={p:>5.0f} counts  (P > S = WRONG)")

print("\nSolution:")
print("  1. Update device_config.json:")
print("     Change: S=120deg, P=60deg")
print("     To:     S=60deg, P=120deg")
print("  2. Restart application")
print("  3. Re-run calibration")
print("\n" + "=" * 80)
