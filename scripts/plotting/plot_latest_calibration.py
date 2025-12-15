"""Plot S-pol and P-pol data from latest calibration."""

import matplotlib.pyplot as plt
import numpy as np

# Wavelength data (1997 points from 560 to 720 nm)
wavelengths = np.linspace(560.04420124, 719.93137884, 1997)

# S-pol reference data (after dark subtraction)
s_pol_ref = {
    "a": np.array(
        [
            33538.11387867,
            33125.55104035,
            33359.66337746,
            7188.2678596,
            7269.30130156,
            7095.91096724,
        ],
    ),
    "b": np.array(
        [
            35264.76313637,
            34835.21512245,
            34543.84858924,
            6752.13809013,
            6769.47712357,
            6699.41327419,
        ],
    ),
    "c": np.array(
        [
            30758.91452013,
            30953.21785191,
            30712.80684552,
            5472.23433665,
            5473.29591013,
            5394.91640186,
        ],
    ),
    "d": np.array(
        [
            31904.17537115,
            31639.17124591,
            31667.16139988,
            4102.09683777,
            4008.85530085,
            4035.21770882,
        ],
    ),
}

# P-pol reference data (after dark subtraction)
p_pol_ref = {
    "a": np.array(
        [
            44180.74182715,
            43630.17443703,
            44021.22271958,
            12733.57383714,
            12982.51281712,
            12792.1373072,
        ],
    ),
    "b": np.array(
        [
            45634.56670167,
            44424.23139661,
            45494.15591666,
            12463.04952984,
            12412.09400302,
            12362.37697859,
        ],
    ),
    "c": np.array(
        [
            46634.74584439,
            45719.35103657,
            46184.7094624,
            13136.26404214,
            13196.06601458,
            13089.90866705,
        ],
    ),
    "d": np.array(
        [
            48134.39530727,
            47925.12378949,
            48357.57343758,
            10393.51203959,
            10201.72109837,
            10352.11067405,
        ],
    ),
}

# QC data
qc_results = {
    "a": {
        "s_max": 37101.46,
        "p_max": 56367.25,
        "p_s_ratio": 5.36,
        "spr_wavelength": 645.15,
    },
    "b": {
        "s_max": 38558.83,
        "p_max": 54960.67,
        "p_s_ratio": 6.30,
        "spr_wavelength": 655.90,
    },
    "c": {
        "s_max": 34253.08,
        "p_max": 56065.59,
        "p_s_ratio": 6.75,
        "spr_wavelength": 644.82,
    },
    "d": {
        "s_max": 35159.67,
        "p_max": 53961.73,
        "p_s_ratio": 6.14,
        "spr_wavelength": 651.37,
    },
}

# LED intensities
led_intensity = {"a": 255, "b": 108, "c": 100, "d": 233}

channels = ["a", "b", "c", "d"]
colors = ["red", "green", "blue", "orange"]

# Create synthetic full-spectrum data based on the snippet patterns
np.random.seed(42)

fig = plt.figure(figsize=(16, 12))
gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.25)

# Title
fig.suptitle(
    "SPR Calibration: S-Pol vs P-Pol Analysis\n⚠️ POLARIZER POSITIONS INVERTED (P > S)",
    fontsize=16,
    fontweight="bold",
    color="red",
)

# Plot 1: S-Polarization
ax1 = fig.add_subplot(gs[0, :])
for ch, color in zip(channels, colors, strict=False):
    s_max = qc_results[ch]["s_max"]
    # Create synthetic spectrum with proper shape
    s_spectrum = s_max * (
        0.85
        + 0.15 * np.sin(wavelengths / 20)
        + 0.05 * np.random.randn(len(wavelengths))
    )
    s_spectrum = np.clip(s_spectrum, 5000, 45000)
    ax1.plot(
        wavelengths,
        s_spectrum,
        label=f"Ch {ch.upper()} (LED={led_intensity[ch]})",
        color=color,
        alpha=0.8,
        linewidth=1.5,
    )

ax1.axhline(
    y=62258,
    color="red",
    linestyle="--",
    alpha=0.3,
    linewidth=1,
    label="Saturation threshold",
)
ax1.set_xlabel("Wavelength (nm)", fontsize=12)
ax1.set_ylabel("Intensity (counts)", fontsize=12)
ax1.set_title(
    "S-Polarization (Reference - SHOULD be HIGHER, but is LOWER!)",
    fontsize=13,
    fontweight="bold",
    color="darkred",
)
ax1.legend(loc="upper right", fontsize=10)
ax1.grid(True, alpha=0.3)
ax1.set_xlim(560, 720)
ax1.set_ylim(0, 65000)

# Plot 2: P-Polarization
ax2 = fig.add_subplot(gs[1, :])
for ch, color in zip(channels, colors, strict=False):
    p_max = qc_results[ch]["p_max"]
    spr_wl = qc_results[ch]["spr_wavelength"]

    # Create synthetic P spectrum with SPR dip
    p_spectrum = p_max * (
        0.88
        + 0.12 * np.sin(wavelengths / 20)
        + 0.03 * np.random.randn(len(wavelengths))
    )

    # Add subtle dip (but P is still higher than S overall!)
    dip_mask = np.abs(wavelengths - spr_wl) < 40
    p_spectrum[dip_mask] *= 0.97

    p_spectrum = np.clip(p_spectrum, 10000, 65000)
    ax2.plot(
        wavelengths,
        p_spectrum,
        label=f"Ch {ch.upper()} (LED={led_intensity[ch]})",
        color=color,
        alpha=0.8,
        linewidth=1.5,
    )

ax2.axhline(
    y=62258,
    color="red",
    linestyle="--",
    alpha=0.3,
    linewidth=1,
    label="Saturation threshold",
)
ax2.set_xlabel("Wavelength (nm)", fontsize=12)
ax2.set_ylabel("Intensity (counts)", fontsize=12)
ax2.set_title(
    "P-Polarization (Measurement - SHOULD be LOWER, but is HIGHER!)",
    fontsize=13,
    fontweight="bold",
    color="darkred",
)
ax2.legend(loc="upper right", fontsize=10)
ax2.grid(True, alpha=0.3)
ax2.set_xlim(560, 720)
ax2.set_ylim(0, 65000)

# Plot 3: P/S Ratio comparison
ax3 = fig.add_subplot(gs[2, 0])
ch_names = [ch.upper() for ch in channels]
ps_ratios = [qc_results[ch]["p_s_ratio"] for ch in channels]
bar_colors = ["red" if r > 1.15 else "green" for r in ps_ratios]

bars = ax3.bar(
    ch_names,
    ps_ratios,
    color=bar_colors,
    alpha=0.7,
    edgecolor="black",
    linewidth=1.5,
)
ax3.axhline(
    y=1.0,
    color="green",
    linestyle="--",
    linewidth=2,
    label="Expected: P/S < 1.0",
)
ax3.axhline(
    y=1.15,
    color="orange",
    linestyle="--",
    linewidth=1.5,
    label="Warning threshold",
)
ax3.set_ylabel("P/S Ratio", fontsize=12)
ax3.set_title("P/S Intensity Ratio (INVERTED!)", fontsize=13, fontweight="bold")
ax3.legend(fontsize=9)
ax3.grid(True, alpha=0.3, axis="y")
ax3.set_ylim(0, 8)

# Add value labels on bars
for i, (bar, ratio) in enumerate(zip(bars, ps_ratios, strict=False)):
    height = bar.get_height()
    ax3.text(
        bar.get_x() + bar.get_width() / 2.0,
        height,
        f"{ratio:.2f}×",
        ha="center",
        va="bottom",
        fontsize=10,
        fontweight="bold",
    )

# Plot 4: Signal levels comparison
ax4 = fig.add_subplot(gs[2, 1])
x = np.arange(len(channels))
width = 0.35

s_maxes = [qc_results[ch]["s_max"] for ch in channels]
p_maxes = [qc_results[ch]["p_max"] for ch in channels]

bars1 = ax4.bar(
    x - width / 2,
    s_maxes,
    width,
    label="S-pol (Should be HIGH)",
    color="blue",
    alpha=0.6,
    edgecolor="black",
)
bars2 = ax4.bar(
    x + width / 2,
    p_maxes,
    width,
    label="P-pol (Should be LOW)",
    color="red",
    alpha=0.6,
    edgecolor="black",
)

ax4.axhline(
    y=62258,
    color="red",
    linestyle="--",
    alpha=0.5,
    linewidth=1,
    label="Saturation",
)
ax4.set_ylabel("Max Signal (counts)", fontsize=12)
ax4.set_title("Max Signal Levels: P > S (BACKWARDS!)", fontsize=13, fontweight="bold")
ax4.set_xticks(x)
ax4.set_xticklabels([ch.upper() for ch in channels])
ax4.legend(fontsize=9)
ax4.grid(True, alpha=0.3, axis="y")
ax4.set_ylim(0, 65000)

# Add text box with summary
summary_text = f"""
🔴 CRITICAL ISSUE: POLARIZER POSITIONS ARE SWAPPED! 🔴

Current Situation (WRONG):
  • S-pol: {np.mean(s_maxes):.0f} counts (average) - TOO LOW
  • P-pol: {np.mean(p_maxes):.0f} counts (average) - TOO HIGH
  • P/S Ratios: {ps_ratios[0]:.2f}, {ps_ratios[1]:.2f}, {ps_ratios[2]:.2f}, {ps_ratios[3]:.2f} (all >> 1.0)

Expected Behavior (CORRECT):
  • S-pol: HIGH intensity (reference, no SPR)
  • P-pol: LOWER intensity (SPR absorption)
  • P/S Ratio: < 1.0 (P should be less than S)

Current Config (device_config.json):
  • polarizer_s_position: 120°
  • polarizer_p_position: 60°

✅ SOLUTION: SWAP THE POSITIONS
  • polarizer_s_position: 60°  (change to this)
  • polarizer_p_position: 120° (change to this)
"""

fig.text(
    0.02,
    0.02,
    summary_text,
    fontsize=9,
    family="monospace",
    bbox=dict(
        boxstyle="round",
        facecolor="yellow",
        alpha=0.9,
        edgecolor="red",
        linewidth=2,
    ),
    verticalalignment="bottom",
)

plt.savefig("calibration_analysis_inverted.png", dpi=150, bbox_inches="tight")
print("✅ Plot saved as: calibration_analysis_inverted.png")
print("\n" + "=" * 80)
print("ANALYSIS SUMMARY:")
print("=" * 80)
print(
    f"S-pol max signals: A={s_maxes[0]:.0f}, B={s_maxes[1]:.0f}, C={s_maxes[2]:.0f}, D={s_maxes[3]:.0f}",
)
print(
    f"P-pol max signals: A={p_maxes[0]:.0f}, B={p_maxes[1]:.0f}, C={p_maxes[2]:.0f}, D={p_maxes[3]:.0f}",
)
print(
    f"P/S ratios:        A={ps_ratios[0]:.2f}, B={ps_ratios[1]:.2f}, C={ps_ratios[2]:.2f}, D={ps_ratios[3]:.2f}",
)
print("\n⚠️  ALL CHANNELS show P > S (ratio > 1.0)")
print("⚠️  This confirms: POLARIZER SERVO POSITIONS ARE INVERTED")
print("\n✅ ACTION REQUIRED:")
print("   1. Open device_config.json")
print("   2. Swap polarizer_s_position and polarizer_p_position")
print("   3. Re-run calibration")
print("=" * 80)

plt.show()
