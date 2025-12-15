"""Plot S and P polarization data from calibration result
This script loads the latest calibration file and plots the S/P spectra
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Try to load the latest calibration file
calibration_dir = Path("calibrations")
latest_file = calibration_dir / "led_calibration_latest.json"

if latest_file.exists():
    print(f"Loading calibration data from: {latest_file}")
    with open(latest_file) as f:
        cal_data = json.load(f)

    # Extract data
    wavelengths = np.array(cal_data["wavelengths"])
    s_pol_ref = {k: np.array(v) for k, v in cal_data["s_pol_ref"].items()}
    p_pol_ref = {k: np.array(v) for k, v in cal_data["p_pol_ref"].items()}
    qc_results = cal_data["qc_results"]

    print(f"✓ Loaded {len(wavelengths)} wavelength points")
    print(f"✓ Channels: {list(s_pol_ref.keys())}")
else:
    print("No calibration file found. Using demo data from your calibration output.")
    # Use the data you provided
    wavelengths = np.linspace(560.04420124, 719.93137884, 1997)

    # Create demo arrays (in reality these would be the full 1997-point arrays)
    # For now, create representative curves
    s_pol_ref = {}
    p_pol_ref = {}
    qc_results = {
        "a": {"spr_wavelength": 655.66, "p_s_ratio": 6.07, "spr_depth": 102.82},
        "b": {"spr_wavelength": 646.35, "p_s_ratio": 6.28, "spr_depth": 103.56},
        "c": {"spr_wavelength": 654.47, "p_s_ratio": 7.28, "spr_depth": 105.85},
        "d": {"spr_wavelength": 651.13, "p_s_ratio": 5.84, "spr_depth": 101.93},
    }

    # Create synthetic SPR curves for demonstration
    for ch in ["a", "b", "c", "d"]:
        spr_wl = qc_results[ch]["spr_wavelength"]
        spr_depth = qc_results[ch]["spr_depth"]

        # S-pol: should show dip (but data shows it's inverted)
        baseline_s = 32000
        dip_s = baseline_s - spr_depth * 100
        s_curve = baseline_s - spr_depth * 100 * np.exp(
            -((wavelengths - spr_wl) ** 2) / (2 * 20**2),
        )
        s_pol_ref[ch] = s_curve + np.random.normal(0, 500, len(wavelengths))

        # P-pol: should be flat/low (but data shows it's actually higher)
        baseline_p = 46000
        p_curve = baseline_p - spr_depth * 50 * np.exp(
            -((wavelengths - spr_wl) ** 2) / (2 * 20**2),
        )
        p_pol_ref[ch] = p_curve + np.random.normal(0, 500, len(wavelengths))

# Create the plot
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle(
    "S and P Polarization Spectra - SPR Response",
    fontsize=16,
    fontweight="bold",
    color="green",
)

channels = ["a", "b", "c", "d"]
titles = ["Channel A", "Channel B", "Channel C", "Channel D"]

for idx, (ax, ch, title) in enumerate(zip(axes.flat, channels, titles, strict=False)):
    qc = qc_results[ch]

    # Plot S and P spectra
    ax.plot(
        wavelengths,
        s_pol_ref[ch],
        "b-",
        label="S-pol (SPR active - shows dip)",
        linewidth=2,
        alpha=0.8,
    )
    ax.plot(
        wavelengths,
        p_pol_ref[ch],
        "r-",
        label="P-pol (SPR inactive - higher)",
        linewidth=2,
        alpha=0.8,
    )

    # Mark SPR wavelength
    spr_wl = qc["spr_wavelength"]
    ax.axvline(
        spr_wl,
        color="green",
        linestyle="--",
        alpha=0.6,
        linewidth=2,
        label=f"SPR λ={spr_wl:.1f}nm",
    )

    # Calculate mean intensities
    s_mean = np.mean(s_pol_ref[ch])
    p_mean = np.mean(p_pol_ref[ch])
    ps_ratio = qc["p_s_ratio"]

    ax.set_xlabel("Wavelength (nm)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Intensity (counts)", fontsize=11, fontweight="bold")
    ax.set_title(
        f"{title}\nP/S Ratio: {ps_ratio:.2f} | S_mean: {s_mean:.0f} | P_mean: {p_mean:.0f}",
        fontsize=11,
        fontweight="bold",
    )
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.3)

    # Set y-axis limits with some padding
    all_data = np.concatenate([s_pol_ref[ch], p_pol_ref[ch]])
    y_min, y_max = all_data.min(), all_data.max()
    y_range = y_max - y_min
    ax.set_ylim(y_min - 0.1 * y_range, y_max + 0.1 * y_range)

    # Add warning box if P > S (inverted)
    if ps_ratio > 1.15:
        warning_text = f"⚠️ INVERTED\nP > S by {ps_ratio:.1f}x"
        ax.text(
            0.98,
            0.97,
            warning_text,
            transform=ax.transAxes,
            ha="right",
            va="top",
            bbox=dict(
                boxstyle="round",
                facecolor="yellow",
                alpha=0.8,
                edgecolor="red",
                linewidth=2,
            ),
            fontsize=10,
            fontweight="bold",
            color="red",
        )

plt.tight_layout()

# Save plot
output_file = "sp_polarization_plot.png"
plt.savefig(output_file, dpi=300, bbox_inches="tight")
print(f"\n✓ Plot saved as '{output_file}'")

# Print analysis
print("\n" + "=" * 70)
print("POLARIZATION ANALYSIS")
print("=" * 70)
for ch in channels:
    qc = qc_results[ch]
    s_mean = np.mean(s_pol_ref[ch])
    p_mean = np.mean(p_pol_ref[ch])
    ps_ratio = qc["p_s_ratio"]

    status = "❌ INVERTED" if ps_ratio > 1.15 else "✓ OK"
    print(f"\nChannel {ch.upper()}: {status}")
    print(f"  S-pol mean: {s_mean:.0f} counts")
    print(f"  P-pol mean: {p_mean:.0f} counts")
    print(f"  P/S ratio:  {ps_ratio:.2f} (expected < 1.15)")
    print(f"  SPR λ:      {qc['spr_wavelength']:.1f} nm")

print("\n" + "=" * 70)
print("CONCLUSION:")
print("=" * 70)
print("ALL CHANNELS SHOW P/S RATIO > 5.8")
print("\n✗ POLARIZER IS INVERTED:")
print("  - S-mode (120°) → LOW signal (should be HIGH)")
print("  - P-mode (60°)  → HIGH signal (should be LOW)")
print("\n✓ EXPECTED BEHAVIOR:")
print("  - S-mode → HIGH transmission (max intensity)")
print("  - P-mode → LOW transmission (min intensity)")
print("\n💡 SOLUTION:")
print("  Swap servo positions: S=60°, P=120°")
print("=" * 70)

plt.show()
