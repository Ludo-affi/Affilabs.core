"""Plot optimal position sweep with noise analysis.
Shows intensity, noise (std), and coefficient of variation across PWM range.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# Load optimal position sweep with noise data
csv_path = ROOT / "optimal_position_sweep.csv"
if not csv_path.exists():
    print(f"ERROR: {csv_path} not found")
    exit(1)

df = pd.read_csv(csv_path)
p_data = df[df["region"] == "P"].copy()
s_data = df[df["region"] == "S"].copy()

# Create comprehensive figure
fig = plt.figure(figsize=(18, 12))
gs = fig.add_gridspec(4, 2, height_ratios=[2, 1, 1, 1], hspace=0.35, wspace=0.3)

# Find optimal positions (middle of stable range)
# P: within 1% of minimum
p_min_val = p_data["intensity"].min()
p_threshold = p_min_val * 1.01
p_good = p_data[p_data["intensity"] <= p_threshold]
p_optimal_pwm = int(np.median(p_good["pwm"].values))
p_optimal = p_data[p_data["pwm"] == p_optimal_pwm].iloc[0]

# S: within 1% of maximum
s_max_val = s_data["intensity"].max()
s_threshold = s_max_val * 0.99
s_good = s_data[s_data["intensity"] >= s_threshold]
s_optimal_pwm = int(np.median(s_good["pwm"].values))
s_optimal = s_data[s_data["pwm"] == s_optimal_pwm].iloc[0]

# ===== PANEL 1: Intensity with error bars =====
ax1 = fig.add_subplot(gs[0, :])
ax1.errorbar(
    p_data["pwm"],
    p_data["intensity"],
    yerr=p_data["std"],
    fmt="o-",
    color="blue",
    linewidth=2,
    markersize=6,
    capsize=4,
    capthick=2,
    label="P Region",
    alpha=0.8,
)
ax1.errorbar(
    s_data["pwm"],
    s_data["intensity"],
    yerr=s_data["std"],
    fmt="o-",
    color="green",
    linewidth=2,
    markersize=6,
    capsize=4,
    capthick=2,
    label="S Region",
    alpha=0.8,
)

# Mark optimal positions
ax1.scatter(
    [p_optimal_pwm],
    [p_optimal["intensity"]],
    s=400,
    marker="*",
    color="red",
    edgecolors="darkred",
    linewidths=3,
    zorder=10,
    label="Optimal P",
)
ax1.scatter(
    [s_optimal_pwm],
    [s_optimal["intensity"]],
    s=400,
    marker="*",
    color="orange",
    edgecolors="darkorange",
    linewidths=3,
    zorder=10,
    label="Optimal S",
)

# Shade stable regions
ax1.axvspan(
    p_good["pwm"].min(),
    p_good["pwm"].max(),
    alpha=0.1,
    color="blue",
    label="P Stable Range",
)
ax1.axvspan(
    s_good["pwm"].min(),
    s_good["pwm"].max(),
    alpha=0.1,
    color="green",
    label="S Stable Range",
)

ax1.set_xlabel("PWM Position", fontsize=13, fontweight="bold")
ax1.set_ylabel("Intensity (counts)", fontsize=13, fontweight="bold")
ax1.set_title(
    "Optimal Position Sweep with Noise Analysis (10 scans per position)\nSpectral Analysis: P=min(610-680nm), S=max(full spectrum), ±10 points average",
    fontsize=14,
    fontweight="bold",
)
ax1.grid(True, alpha=0.3)
ax1.legend(loc="upper right", fontsize=10, ncol=2)

# Annotations
ax1.annotate(
    f"Optimal P\nPWM {p_optimal_pwm}\n{p_optimal['intensity']:.1f} ± {p_optimal['std']:.1f}",
    xy=(p_optimal_pwm, p_optimal["intensity"]),
    xytext=(p_optimal_pwm + 5, p_optimal["intensity"] + 1500),
    arrowprops=dict(arrowstyle="->", color="red", lw=2),
    fontsize=11,
    color="red",
    fontweight="bold",
    bbox=dict(boxstyle="round", facecolor="yellow", alpha=0.9),
)

ax1.annotate(
    f"Optimal S\nPWM {s_optimal_pwm}\n{s_optimal['intensity']:.1f} ± {s_optimal['std']:.1f}",
    xy=(s_optimal_pwm, s_optimal["intensity"]),
    xytext=(s_optimal_pwm - 5, s_optimal["intensity"] - 1500),
    arrowprops=dict(arrowstyle="->", color="orange", lw=2),
    fontsize=11,
    color="orange",
    fontweight="bold",
    bbox=dict(boxstyle="round", facecolor="yellow", alpha=0.9),
)

# ===== PANEL 2: P Region Detail =====
ax2 = fig.add_subplot(gs[1, 0])
ax2.errorbar(
    p_data["pwm"],
    p_data["intensity"],
    yerr=p_data["std"],
    fmt="o-",
    color="blue",
    linewidth=2.5,
    markersize=8,
    capsize=5,
    capthick=2,
)
ax2.scatter(
    [p_optimal_pwm],
    [p_optimal["intensity"]],
    s=300,
    marker="*",
    color="red",
    edgecolors="darkred",
    linewidths=3,
    zorder=10,
)
ax2.axvspan(p_good["pwm"].min(), p_good["pwm"].max(), alpha=0.2, color="blue")
ax2.axhline(
    y=p_optimal["intensity"],
    color="red",
    linestyle="--",
    alpha=0.5,
    linewidth=2,
)
ax2.set_xlabel("PWM Position", fontsize=11, fontweight="bold")
ax2.set_ylabel("Intensity (counts)", fontsize=11, fontweight="bold")
ax2.set_title("P Region: Intensity ± Std Dev", fontsize=12, fontweight="bold")
ax2.grid(True, alpha=0.3)
ax2.set_xlim(0, 16)

# ===== PANEL 3: S Region Detail =====
ax3 = fig.add_subplot(gs[1, 1])
ax3.errorbar(
    s_data["pwm"],
    s_data["intensity"],
    yerr=s_data["std"],
    fmt="o-",
    color="green",
    linewidth=2.5,
    markersize=8,
    capsize=5,
    capthick=2,
)
ax3.scatter(
    [s_optimal_pwm],
    [s_optimal["intensity"]],
    s=300,
    marker="*",
    color="orange",
    edgecolors="darkorange",
    linewidths=3,
    zorder=10,
)
ax3.axvspan(s_good["pwm"].min(), s_good["pwm"].max(), alpha=0.2, color="green")
ax3.axhline(
    y=s_optimal["intensity"],
    color="orange",
    linestyle="--",
    alpha=0.5,
    linewidth=2,
)
ax3.set_xlabel("PWM Position", fontsize=11, fontweight="bold")
ax3.set_ylabel("Intensity (counts)", fontsize=11, fontweight="bold")
ax3.set_title("S Region: Intensity ± Std Dev", fontsize=12, fontweight="bold")
ax3.grid(True, alpha=0.3)
ax3.set_xlim(60, 82)

# ===== PANEL 4: Noise (Std Dev) =====
ax4 = fig.add_subplot(gs[2, 0])
ax4.plot(p_data["pwm"], p_data["std"], "o-", color="blue", linewidth=2, markersize=8)
ax4.scatter(
    [p_optimal_pwm],
    [p_optimal["std"]],
    s=300,
    marker="*",
    color="red",
    edgecolors="darkred",
    linewidths=3,
    zorder=10,
)
ax4.axvspan(p_good["pwm"].min(), p_good["pwm"].max(), alpha=0.2, color="blue")
ax4.set_xlabel("PWM Position", fontsize=11, fontweight="bold")
ax4.set_ylabel("Noise (std, counts)", fontsize=11, fontweight="bold")
ax4.set_title("P Region: Measurement Noise", fontsize=12, fontweight="bold")
ax4.grid(True, alpha=0.3)
ax4.set_xlim(0, 16)

ax5 = fig.add_subplot(gs[2, 1])
ax5.plot(s_data["pwm"], s_data["std"], "o-", color="green", linewidth=2, markersize=8)
ax5.scatter(
    [s_optimal_pwm],
    [s_optimal["std"]],
    s=300,
    marker="*",
    color="orange",
    edgecolors="darkorange",
    linewidths=3,
    zorder=10,
)
ax5.axvspan(s_good["pwm"].min(), s_good["pwm"].max(), alpha=0.2, color="green")
ax5.set_xlabel("PWM Position", fontsize=11, fontweight="bold")
ax5.set_ylabel("Noise (std, counts)", fontsize=11, fontweight="bold")
ax5.set_title("S Region: Measurement Noise", fontsize=12, fontweight="bold")
ax5.grid(True, alpha=0.3)
ax5.set_xlim(60, 82)

# ===== PANEL 5: Coefficient of Variation (CV%) =====
ax6 = fig.add_subplot(gs[3, 0])
ax6.plot(
    p_data["pwm"],
    p_data["cv_percent"],
    "o-",
    color="blue",
    linewidth=2,
    markersize=8,
)
ax6.scatter(
    [p_optimal_pwm],
    [p_optimal["cv_percent"]],
    s=300,
    marker="*",
    color="red",
    edgecolors="darkred",
    linewidths=3,
    zorder=10,
)
ax6.axvspan(p_good["pwm"].min(), p_good["pwm"].max(), alpha=0.2, color="blue")
ax6.set_xlabel("PWM Position", fontsize=11, fontweight="bold")
ax6.set_ylabel("CV (%)", fontsize=11, fontweight="bold")
ax6.set_title("P Region: Coefficient of Variation", fontsize=12, fontweight="bold")
ax6.grid(True, alpha=0.3)
ax6.set_xlim(0, 16)

ax7 = fig.add_subplot(gs[3, 1])
ax7.plot(
    s_data["pwm"],
    s_data["cv_percent"],
    "o-",
    color="green",
    linewidth=2,
    markersize=8,
)
ax7.scatter(
    [s_optimal_pwm],
    [s_optimal["cv_percent"]],
    s=300,
    marker="*",
    color="orange",
    edgecolors="darkorange",
    linewidths=3,
    zorder=10,
)
ax7.axvspan(s_good["pwm"].min(), s_good["pwm"].max(), alpha=0.2, color="green")
ax7.set_xlabel("PWM Position", fontsize=11, fontweight="bold")
ax7.set_ylabel("CV (%)", fontsize=11, fontweight="bold")
ax7.set_title("S Region: Coefficient of Variation", fontsize=12, fontweight="bold")
ax7.grid(True, alpha=0.3)
ax7.set_xlim(60, 82)

plt.suptitle(
    "Optimal Position Analysis with Noise Characterization",
    fontsize=16,
    fontweight="bold",
    y=0.995,
)

# Save plot
plot_path = ROOT / "optimal_position_noise_analysis.png"
plt.savefig(plot_path, dpi=200, bbox_inches="tight")
print(f"Plot saved to: {plot_path}")

# Print analysis
print("\n" + "=" * 80)
print("NOISE ANALYSIS SUMMARY")
print("=" * 80)

print("\nP REGION:")
print(
    f"  Stable PWM range: {p_good['pwm'].min()} - {p_good['pwm'].max()} ({len(p_good)} positions)",
)
print(f"  Optimal PWM: {p_optimal_pwm} (middle of range)")
print(f"  Intensity: {p_optimal['intensity']:.1f} ± {p_optimal['std']:.1f} counts")
print(f"  Noise CV: {p_optimal['cv_percent']:.3f}%")
print(
    f"  Best noise: PWM {p_data.loc[p_data['std'].idxmin(), 'pwm']:.0f} with {p_data['std'].min():.1f} counts std",
)

print("\nS REGION:")
print(
    f"  Stable PWM range: {s_good['pwm'].min()} - {s_good['pwm'].max()} ({len(s_good)} positions)",
)
print(f"  Optimal PWM: {s_optimal_pwm} (middle of range)")
print(f"  Intensity: {s_optimal['intensity']:.1f} ± {s_optimal['std']:.1f} counts")
print(f"  Noise CV: {s_optimal['cv_percent']:.3f}%")
print(
    f"  Best noise: PWM {s_data.loc[s_data['std'].idxmin(), 'pwm']:.0f} with {s_data['std'].min():.1f} counts std",
)

print("\nOPTIMAL POSITIONS:")
print(f"  P = PWM {p_optimal_pwm}")
print(f"  S = PWM {s_optimal_pwm}")
print(f"  S/P Ratio: {s_optimal['intensity'] / p_optimal['intensity']:.3f}x")
print(f"  Separation: {s_optimal['intensity'] - p_optimal['intensity']:.1f} counts")

print("\n" + "=" * 80)

plt.show()
