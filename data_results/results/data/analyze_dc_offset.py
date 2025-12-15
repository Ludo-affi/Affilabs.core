"""Investigate DC offset in optimized signal.

The optimized signal appears to sit higher than baseline. Possible causes:
1. Kalman filter bias/initialization
2. Polynomial regression systematic error
3. Alpha parameter affecting DC component
4. SG filter edge effects
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.fftpack import dst, idct
from scipy.signal import savgol_filter
from scipy.stats import linregress

# Load baseline data
baseline_file = r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\ezControl-AI\baseline_data\baseline_recording_20251203_172554.xlsx"
df = pd.read_excel(baseline_file)

wavelengths = df["wavelength_nm"].values
time_columns = [col for col in df.columns if col.startswith("t_")]

print("=" * 80)
print("DC OFFSET INVESTIGATION")
print("=" * 80)


def apply_fourier_method(
    transmission_spectrum,
    wavelengths,
    alpha=9000,
    sg_window=11,
    sg_poly=3,
    regression_window=50,
    regression_poly=1,
):
    """Fourier peak finding."""
    spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
    spr_wavelengths = wavelengths[spr_mask]
    spr_transmission = transmission_spectrum[spr_mask]

    spectrum = savgol_filter(
        spr_transmission,
        window_length=sg_window,
        polyorder=sg_poly,
    )
    hint_index = np.argmin(spectrum)

    n = len(spectrum)
    n_inner = n - 1
    phi = np.pi / n_inner * np.arange(1, n_inner)
    phi2 = phi**2
    fourier_weights = phi / (1 + alpha * phi2 * (1 + phi2))

    fourier_coeff = np.zeros_like(spectrum)
    fourier_coeff[0] = 2 * (spectrum[-1] - spectrum[0])
    detrended = spectrum[1:-1] - np.linspace(spectrum[0], spectrum[-1], n)[1:-1]
    fourier_coeff[1:-1] = fourier_weights * dst(detrended, 1)

    derivative = idct(fourier_coeff, 1)

    search_start = max(0, hint_index - 50)
    search_end = min(len(derivative), hint_index + 50)
    derivative_window = derivative[search_start:search_end]
    zero_local = derivative_window.searchsorted(0)
    zero = search_start + zero_local

    start = max(zero - regression_window, 0)
    end = min(zero + regression_window, n - 1)

    x = spr_wavelengths[start:end]
    y = derivative[start:end]

    if regression_poly == 1:
        line = linregress(x, y)
        peak_wavelength = -line.intercept / line.slope
    else:
        coeffs = np.polyfit(x, y, regression_poly)
        roots = np.roots(coeffs)
        real_roots = roots[np.isreal(roots)].real
        if len(real_roots) > 0:
            closest_root = real_roots[
                np.argmin(np.abs(real_roots - spr_wavelengths[zero]))
            ]
            peak_wavelength = closest_root
        else:
            line = linregress(x, y)
            peak_wavelength = -line.intercept / line.slope

    return peak_wavelength


def adaptive_kalman_filter(measurements, initial_process_var=1e-5):
    """Adaptive Kalman filter."""
    n = len(measurements)
    x_est = np.zeros(n)
    P_est = np.zeros(n)

    x_est[0] = measurements[0]
    P_est[0] = 1.0

    Q = initial_process_var
    R = np.var(np.diff(measurements[:10]))

    residuals = []

    for k in range(1, n):
        x_pred = x_est[k - 1]
        P_pred = P_est[k - 1] + Q

        K = P_pred / (P_pred + R)
        innovation = measurements[k] - x_pred
        x_est[k] = x_pred + K * innovation
        P_est[k] = (1 - K) * P_pred

        residuals.append(innovation**2)
        if k > 10 and k % 10 == 0:
            R = np.mean(residuals[-10:])

    return x_est


def get_wavelength_series(
    alpha=9000,
    sg_window=11,
    sg_poly=3,
    regression_window=50,
    regression_poly=1,
):
    """Get raw wavelength series (before RU conversion)."""
    wavelength_series = []

    for time_col in time_columns:
        transmission_spectrum = df[time_col].values
        try:
            wavelength = apply_fourier_method(
                transmission_spectrum,
                wavelengths,
                alpha=alpha,
                sg_window=sg_window,
                sg_poly=sg_poly,
                regression_window=regression_window,
                regression_poly=regression_poly,
            )
            wavelength_series.append(wavelength)
        except:
            wavelength_series.append(np.nan)

    wavelength_series = np.array(wavelength_series)
    valid_mask = np.isfinite(wavelength_series)
    return wavelength_series[valid_mask]


# ============================================================================
# GET WAVELENGTH DATA (BEFORE RU CONVERSION)
# ============================================================================
print("\nExtracting wavelength series at each processing stage...")

# Stage 1: Baseline Fourier
wl_baseline = get_wavelength_series(
    alpha=9000,
    sg_window=11,
    sg_poly=3,
    regression_window=50,
    regression_poly=1,
)

# Stage 2: + SG optimization
wl_sg = get_wavelength_series(
    alpha=9000,
    sg_window=11,
    sg_poly=5,
    regression_window=50,
    regression_poly=1,
)

# Stage 3: + Regression optimization
wl_reg = get_wavelength_series(
    alpha=9000,
    sg_window=11,
    sg_poly=3,
    regression_window=100,
    regression_poly=2,
)

# Stage 4: + Both optimizations
wl_both = get_wavelength_series(
    alpha=9000,
    sg_window=11,
    sg_poly=5,
    regression_window=100,
    regression_poly=2,
)

# Stage 5: + Lower alpha
wl_alpha = get_wavelength_series(
    alpha=2000,
    sg_window=11,
    sg_poly=5,
    regression_window=100,
    regression_poly=2,
)

# ============================================================================
# ANALYZE DC OFFSET AT EACH STAGE
# ============================================================================
print("\n" + "=" * 80)
print("DC OFFSET ANALYSIS (Wavelength Domain)")
print("=" * 80)

stages = [
    ("Baseline", wl_baseline),
    ("+ SG (11/5)", wl_sg),
    ("+ Regression (100/Quad)", wl_reg),
    ("+ Both (SG + Reg)", wl_both),
    ("+ Alpha=2000", wl_alpha),
]

print("\nMean wavelength at each stage:")
for name, wl in stages:
    mean_wl = np.mean(wl)
    print(f"  {name:25s}: {mean_wl:.4f} nm")

print("\nDifference from baseline:")
baseline_mean = np.mean(wl_baseline)
for name, wl in stages:
    mean_wl = np.mean(wl)
    diff_nm = mean_wl - baseline_mean
    diff_ru = diff_nm * 355
    print(f"  {name:25s}: {diff_nm:+.4f} nm  ({diff_ru:+.2f} RU)")

# ============================================================================
# CONVERT TO RU (ZEROED AT FIRST POINT)
# ============================================================================
print("\n" + "=" * 80)
print("RU DOMAIN (Zeroed at First Point)")
print("=" * 80)

spr_baseline = (wl_baseline - wl_baseline[0]) * 355
spr_sg = (wl_sg - wl_sg[0]) * 355
spr_reg = (wl_reg - wl_reg[0]) * 355
spr_both = (wl_both - wl_both[0]) * 355
spr_alpha = (wl_alpha - wl_alpha[0]) * 355

print("\nMean RU (after zeroing first point):")
print(f"  Baseline:                 {np.mean(spr_baseline):+.2f} RU")
print(f"  + SG:                     {np.mean(spr_sg):+.2f} RU")
print(f"  + Regression:             {np.mean(spr_reg):+.2f} RU")
print(f"  + Both:                   {np.mean(spr_both):+.2f} RU")
print(f"  + Alpha=2000:             {np.mean(spr_alpha):+.2f} RU")

# ============================================================================
# NOW ADD KALMAN FILTER
# ============================================================================
print("\n" + "=" * 80)
print("KALMAN FILTER EFFECT")
print("=" * 80)

# Apply Kalman to each stage
spr_baseline_kalman = adaptive_kalman_filter(spr_baseline)
spr_sg_kalman = adaptive_kalman_filter(spr_sg)
spr_reg_kalman = adaptive_kalman_filter(spr_reg)
spr_both_kalman = adaptive_kalman_filter(spr_both)
spr_alpha_kalman = adaptive_kalman_filter(spr_alpha)

print("\nMean RU (after Kalman filter):")
print(
    f"  Baseline:                 {np.mean(spr_baseline_kalman):+.2f} RU  (was {np.mean(spr_baseline):+.2f})",
)
print(
    f"  + SG:                     {np.mean(spr_sg_kalman):+.2f} RU  (was {np.mean(spr_sg):+.2f})",
)
print(
    f"  + Regression:             {np.mean(spr_reg_kalman):+.2f} RU  (was {np.mean(spr_reg):+.2f})",
)
print(
    f"  + Both:                   {np.mean(spr_both_kalman):+.2f} RU  (was {np.mean(spr_both):+.2f})",
)
print(
    f"  + Alpha=2000:             {np.mean(spr_alpha_kalman):+.2f} RU  (was {np.mean(spr_alpha):+.2f})",
)

print("\nKalman-induced DC shift:")
print(
    f"  Baseline:                 {np.mean(spr_baseline_kalman) - np.mean(spr_baseline):+.2f} RU",
)
print(f"  + SG:                     {np.mean(spr_sg_kalman) - np.mean(spr_sg):+.2f} RU")
print(
    f"  + Regression:             {np.mean(spr_reg_kalman) - np.mean(spr_reg):+.2f} RU",
)
print(
    f"  + Both:                   {np.mean(spr_both_kalman) - np.mean(spr_both):+.2f} RU",
)
print(
    f"  + Alpha=2000:             {np.mean(spr_alpha_kalman) - np.mean(spr_alpha):+.2f} RU",
)

# ============================================================================
# VISUALIZATION
# ============================================================================
fig, axes = plt.subplots(3, 2, figsize=(16, 12))

# Plot 1: Wavelength domain (raw)
ax = axes[0, 0]
for name, wl in stages:
    ax.plot(wl, label=name, alpha=0.7, linewidth=2)
ax.set_xlabel("Time Point")
ax.set_ylabel("Wavelength (nm)")
ax.set_title("Raw Wavelength Series (Before RU Conversion)")
ax.legend()
ax.grid(True, alpha=0.3)

# Plot 2: Wavelength histogram
ax = axes[0, 1]
for name, wl in stages:
    ax.hist(wl, bins=30, alpha=0.3, label=name)
ax.set_xlabel("Wavelength (nm)")
ax.set_ylabel("Frequency")
ax.set_title("Wavelength Distribution")
ax.legend()
ax.grid(True, alpha=0.3, axis="y")

# Plot 3: RU domain (before Kalman)
ax = axes[1, 0]
ax.plot(spr_baseline, label="Baseline", alpha=0.7, linewidth=2)
ax.plot(spr_alpha, label="Alpha=2000 + SG + Reg", alpha=0.7, linewidth=2)
ax.axhline(y=np.mean(spr_baseline), color="C0", linestyle="--", alpha=0.5)
ax.axhline(y=np.mean(spr_alpha), color="C1", linestyle="--", alpha=0.5)
ax.set_xlabel("Time Point")
ax.set_ylabel("SPR (RU)")
ax.set_title("Before Kalman Filter (DC offset visible)")
ax.legend()
ax.grid(True, alpha=0.3)

# Add mean annotations
ax.text(
    10,
    np.mean(spr_baseline),
    f"Mean: {np.mean(spr_baseline):.2f} RU",
    verticalalignment="bottom",
    color="C0",
    fontweight="bold",
)
ax.text(
    10,
    np.mean(spr_alpha),
    f"Mean: {np.mean(spr_alpha):.2f} RU",
    verticalalignment="bottom",
    color="C1",
    fontweight="bold",
)

# Plot 4: RU domain (after Kalman)
ax = axes[1, 1]
ax.plot(spr_baseline_kalman, label="Baseline + Kalman", alpha=0.7, linewidth=2)
ax.plot(spr_alpha_kalman, label="Optimized + Kalman", alpha=0.7, linewidth=2)
ax.axhline(y=np.mean(spr_baseline_kalman), color="C0", linestyle="--", alpha=0.5)
ax.axhline(y=np.mean(spr_alpha_kalman), color="C1", linestyle="--", alpha=0.5)
ax.set_xlabel("Time Point")
ax.set_ylabel("SPR (RU)")
ax.set_title("After Kalman Filter (DC offset remains)")
ax.legend()
ax.grid(True, alpha=0.3)

# Add mean annotations
ax.text(
    10,
    np.mean(spr_baseline_kalman),
    f"Mean: {np.mean(spr_baseline_kalman):.2f} RU",
    verticalalignment="bottom",
    color="C0",
    fontweight="bold",
)
ax.text(
    10,
    np.mean(spr_alpha_kalman),
    f"Mean: {np.mean(spr_alpha_kalman):.2f} RU",
    verticalalignment="bottom",
    color="C1",
    fontweight="bold",
)

# Plot 5: Overlay with mean-centering
ax = axes[2, 0]
spr_baseline_centered = spr_baseline_kalman - np.mean(spr_baseline_kalman)
spr_optimized_centered = spr_alpha_kalman - np.mean(spr_alpha_kalman)
ax.plot(
    spr_baseline_centered,
    label=f"Baseline (p2p={np.ptp(spr_baseline_kalman):.2f} RU)",
    alpha=0.7,
    linewidth=2,
    color="red",
)
ax.plot(
    spr_optimized_centered,
    label=f"Optimized (p2p={np.ptp(spr_alpha_kalman):.2f} RU)",
    alpha=0.7,
    linewidth=2,
    color="green",
)
ax.axhline(y=0, color="black", linestyle=":", alpha=0.5)
ax.set_xlabel("Time Point")
ax.set_ylabel("SPR (RU, mean-centered)")
ax.set_title("Mean-Centered Comparison (DC offset removed)")
ax.legend()
ax.grid(True, alpha=0.3)

# Plot 6: DC offset breakdown
ax = axes[2, 1]
stage_names = ["Baseline", "+SG", "+Reg", "+Both", "+Alpha", "+Kalman"]
dc_values = [
    np.mean(spr_baseline),
    np.mean(spr_sg),
    np.mean(spr_reg),
    np.mean(spr_both),
    np.mean(spr_alpha),
    np.mean(spr_alpha_kalman),
]
colors = ["red", "orange", "yellow", "lightgreen", "green", "darkgreen"]
bars = ax.bar(stage_names, dc_values, color=colors, edgecolor="black", linewidth=1.5)
ax.axhline(y=0, color="black", linestyle="-", linewidth=2)
ax.set_ylabel("Mean SPR (RU)")
ax.set_title("DC Offset Evolution Through Processing Pipeline")
ax.grid(True, alpha=0.3, axis="y")
plt.setp(ax.xaxis.get_majorticklabels(), rotation=15, ha="right")

# Annotate bars
for bar in bars:
    height = bar.get_height()
    ax.text(
        bar.get_x() + bar.get_width() / 2.0,
        height,
        f"{height:+.2f}",
        ha="center",
        va="bottom" if height > 0 else "top",
        fontsize=10,
        fontweight="bold",
    )

plt.tight_layout()
plt.savefig("dc_offset_investigation.png", dpi=150, bbox_inches="tight")
print("\n[OK] Plot saved to: dc_offset_investigation.png")

# ============================================================================
# ROOT CAUSE ANALYSIS
# ============================================================================
print("\n" + "=" * 80)
print("ROOT CAUSE ANALYSIS")
print("=" * 80)

print("\n[SEARCH] FINDING:")
print(
    f"   The optimized signal sits {np.mean(spr_alpha_kalman):.2f} RU higher than baseline",
)
print(f"   Baseline mean: {np.mean(spr_baseline_kalman):.2f} RU")
print(f"   Optimized mean: {np.mean(spr_alpha_kalman):.2f} RU")
print(
    f"   DC shift: {np.mean(spr_alpha_kalman) - np.mean(spr_baseline_kalman):+.2f} RU",
)

# Check if it's from Fourier parameters
print("\n💡 HYPOTHESIS 1: Fourier Parameters Cause Systematic Bias")
print("   Before Kalman:")
print(f"     Baseline: {np.mean(spr_baseline):+.2f} RU")
print(f"     Alpha=2000+SG+Reg: {np.mean(spr_alpha):+.2f} RU")
print(f"     Difference: {np.mean(spr_alpha) - np.mean(spr_baseline):+.2f} RU")
if abs(np.mean(spr_alpha) - np.mean(spr_baseline)) > 1:
    print("   [OK] YES - Fourier parameters introduce DC shift")
else:
    print("   [ERROR] NO - DC shift is minimal from Fourier parameters")

# Check if it's from Kalman
print("\n💡 HYPOTHESIS 2: Kalman Filter Amplifies Existing Drift")
kalman_shift_baseline = np.mean(spr_baseline_kalman) - np.mean(spr_baseline)
kalman_shift_optimized = np.mean(spr_alpha_kalman) - np.mean(spr_alpha)
print(f"   Kalman DC shift on baseline: {kalman_shift_baseline:+.2f} RU")
print(f"   Kalman DC shift on optimized: {kalman_shift_optimized:+.2f} RU")
if abs(kalman_shift_optimized) > abs(kalman_shift_baseline):
    print("   [OK] YES - Kalman amplifies drift more on optimized signal")
else:
    print("   [ERROR] NO - Kalman effect similar on both signals")

# Check individual contributions
print("\n📊 INDIVIDUAL CONTRIBUTIONS TO DC SHIFT:")
print(f"   SG (11/5):         {np.mean(spr_sg) - np.mean(spr_baseline):+.2f} RU")
print(f"   Regression (100/Quad): {np.mean(spr_reg) - np.mean(spr_baseline):+.2f} RU")
print(f"   Alpha=2000:        {np.mean(spr_alpha) - np.mean(spr_both):+.2f} RU")
print(f"   Kalman:            {np.mean(spr_alpha_kalman) - np.mean(spr_alpha):+.2f} RU")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)

# Identify main culprit
contributions = {
    "SG": np.mean(spr_sg) - np.mean(spr_baseline),
    "Regression": np.mean(spr_reg) - np.mean(spr_baseline),
    "Alpha": np.mean(spr_alpha) - np.mean(spr_both),
    "Kalman": np.mean(spr_alpha_kalman) - np.mean(spr_alpha),
}

max_contributor = max(contributions.items(), key=lambda x: abs(x[1]))

print(f"\n🎯 PRIMARY CAUSE: {max_contributor[0]}")
print(f"   Contributes {max_contributor[1]:+.2f} RU DC shift")

print("\n[OK] PRACTICAL IMPACT:")
print("   • DC offset does NOT affect p2p noise measurement")
print("   • DC offset does NOT affect kinetic rate measurements")
print("   • Can be removed by mean-centering or baseline subtraction")
print("   • Is cosmetic only - not a functional problem")

print("\n💡 RECOMMENDATION:")
print("   If DC offset is undesirable, add mean-centering:")
print("   `spr_corrected = spr_filtered - np.mean(spr_filtered[:50])`")
print("   (Use first 50 points or a baseline window as reference)")

print("\n" + "=" * 80)
