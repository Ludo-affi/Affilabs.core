"""Optimize Fourier peak finding: regression window size and polynomial order.

Current implementation uses:
- search_window = 50 (for zero-crossing search)
- window_size = 50 (for linear regression around zero)
- linregress (linear, i.e., polynomial order 1)

This script tests:
1. Different window sizes (10, 25, 50, 75, 100, 150, 200)
2. Different polynomial orders (1=linear, 2=quadratic, 3=cubic)

Hypothesis: Wider windows + higher polynomial order may better capture
the smooth derivative shape and reduce p2p noise.
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
n_timepoints = len(time_columns)

print("=" * 80)
print("FOURIER WINDOW SIZE & POLYNOMIAL ORDER OPTIMIZATION")
print("=" * 80)
print(f"Dataset: {n_timepoints} timepoints, {len(wavelengths)} wavelengths")
print()


def apply_fourier_method(
    transmission_spectrum,
    wavelengths,
    alpha=9000,
    search_window=50,
    regression_window=50,
    poly_order=1,
    apply_sg=True,
):
    """Fourier peak finding with configurable window sizes and polynomial order.

    Args:
        search_window: Window for zero-crossing search (±N points)
        regression_window: Window for peak refinement (±N points)
        poly_order: Polynomial order for peak refinement (1=linear, 2=quadratic, etc.)

    """
    # SPR region
    spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
    spr_wavelengths = wavelengths[spr_mask]
    spr_transmission = transmission_spectrum[spr_mask]

    # Optional SG filter
    if apply_sg:
        spectrum = savgol_filter(spr_transmission, window_length=11, polyorder=3)
    else:
        spectrum = spr_transmission

    hint_index = np.argmin(spectrum)

    # Fourier transform
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

    # STEP 5: Zero-crossing search with configurable window
    search_start = max(0, hint_index - search_window)
    search_end = min(len(derivative), hint_index + search_window)
    derivative_window = derivative[search_start:search_end]
    zero_local = derivative_window.searchsorted(0)
    zero = search_start + zero_local

    # STEP 6: Peak refinement with configurable window and polynomial order
    start = max(zero - regression_window, 0)
    end = min(zero + regression_window, n - 1)

    x = spr_wavelengths[start:end]
    y = derivative[start:end]

    if poly_order == 1:
        # Linear regression (current method)
        line = linregress(x, y)
        peak_wavelength = -line.intercept / line.slope
    else:
        # Polynomial regression (higher order)
        coeffs = np.polyfit(x, y, poly_order)
        poly = np.poly1d(coeffs)

        # Find zero-crossing of polynomial
        roots = np.roots(coeffs)
        # Take real root closest to zero position
        real_roots = roots[np.isreal(roots)].real
        if len(real_roots) > 0:
            # Choose root closest to the zero-crossing estimate
            closest_root = real_roots[
                np.argmin(np.abs(real_roots - spr_wavelengths[zero]))
            ]
            peak_wavelength = closest_root
        else:
            # Fallback to linear if no real roots
            line = linregress(x, y)
            peak_wavelength = -line.intercept / line.slope

    return peak_wavelength


# ============================================================================
# GRID SEARCH: Window Sizes × Polynomial Orders
# ============================================================================
print("\n" + "=" * 80)
print("GRID SEARCH: REGRESSION WINDOW × POLYNOMIAL ORDER")
print("=" * 80)

# Test parameters
window_sizes = [10, 25, 50, 75, 100, 150, 200]
poly_orders = [1, 2, 3]

results = []

for window in window_sizes:
    for poly in poly_orders:
        wavelength_series = []

        for time_col in time_columns:
            transmission_spectrum = df[time_col].values
            try:
                wavelength = apply_fourier_method(
                    transmission_spectrum,
                    wavelengths,
                    alpha=9000,
                    search_window=50,  # Keep search window fixed
                    regression_window=window,
                    poly_order=poly,
                    apply_sg=True,
                )
                wavelength_series.append(wavelength)
            except:
                # If polynomial method fails, skip this configuration
                wavelength_series.append(np.nan)

        wavelength_series = np.array(wavelength_series)
        valid_mask = np.isfinite(wavelength_series)

        if np.sum(valid_mask) < 10:
            # Too many failures, skip
            continue

        spr_series = (
            wavelength_series[valid_mask] - wavelength_series[valid_mask][0]
        ) * 355

        p2p = np.ptp(spr_series)
        std = np.std(spr_series)
        max_rate = np.max(np.abs(np.diff(spr_series)))

        results.append(
            {
                "window": window,
                "poly_order": poly,
                "p2p": p2p,
                "std": std,
                "max_rate": max_rate,
                "series": spr_series,
            },
        )

        poly_name = ["Linear", "Quadratic", "Cubic"][poly - 1]
        print(
            f"  Window={window:3d}, Poly={poly} ({poly_name:9s}): p2p={p2p:5.2f} RU, std={std:5.2f} RU, max_rate={max_rate:5.2f} RU/s",
        )

# ============================================================================
# ANALYSIS
# ============================================================================
print("\n" + "=" * 80)
print("RESULTS ANALYSIS")
print("=" * 80)

results_df = pd.DataFrame(results)

# Current baseline (window=50, poly=1)
current = results_df[(results_df["window"] == 50) & (results_df["poly_order"] == 1)]
if len(current) > 0:
    current_p2p = current.iloc[0]["p2p"]
    print(f"\n📊 CURRENT (Window=50, Linear): {current_p2p:.2f} RU")
else:
    current_p2p = None

# Best overall
best = results_df.loc[results_df["p2p"].idxmin()]
print("\n🏆 BEST OVERALL:")
print(f"   Window: {best['window']}")
print(
    f"   Polynomial: {best['poly_order']} ({'Linear' if best['poly_order']==1 else 'Quadratic' if best['poly_order']==2 else 'Cubic'})",
)
print(f"   Noise: {best['p2p']:.2f} RU")
if current_p2p:
    print(f"   Improvement: {(1 - best['p2p']/current_p2p)*100:.1f}%")

# Best per polynomial order
print("\n🎯 BEST FOR EACH POLYNOMIAL ORDER:")
for poly in [1, 2, 3]:
    subset = results_df[results_df["poly_order"] == poly]
    if len(subset) > 0:
        best_poly = subset.loc[subset["p2p"].idxmin()]
        poly_name = ["Linear", "Quadratic", "Cubic"][poly - 1]
        print(
            f"   {poly_name:9s} (order {poly}): Window={best_poly['window']:3d}, p2p={best_poly['p2p']:5.2f} RU",
        )

# Best per window size
print("\n[MEASURE] BEST FOR EACH WINDOW SIZE:")
for window in window_sizes:
    subset = results_df[results_df["window"] == window]
    if len(subset) > 0:
        best_window = subset.loc[subset["p2p"].idxmin()]
        poly_name = ["Linear", "Quadratic", "Cubic"][best_window["poly_order"] - 1]
        print(
            f"   Window={window:3d}: Poly={best_window['poly_order']} ({poly_name}), p2p={best_window['p2p']:5.2f} RU",
        )

# ============================================================================
# VISUALIZATIONS
# ============================================================================
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# Plot 1: Heatmap - Window vs Polynomial
ax = axes[0, 0]
pivot = results_df.pivot(index="poly_order", columns="window", values="p2p")
im = ax.imshow(pivot.values, cmap="RdYlGn_r", aspect="auto", interpolation="nearest")
ax.set_xticks(range(len(pivot.columns)))
ax.set_xticklabels(pivot.columns)
ax.set_yticks(range(len(pivot.index)))
ax.set_yticklabels(["Linear", "Quadratic", "Cubic"])
ax.set_xlabel("Regression Window Size")
ax.set_ylabel("Polynomial Order")
ax.set_title("Noise (RU) - Heatmap")

# Add values to heatmap
for i in range(len(pivot.index)):
    for j in range(len(pivot.columns)):
        value = pivot.values[i, j]
        if not np.isnan(value):
            text = ax.text(
                j,
                i,
                f"{value:.1f}",
                ha="center",
                va="center",
                color="white" if value > pivot.values.mean() else "black",
                fontsize=10,
            )

plt.colorbar(im, ax=ax, label="p2p Noise (RU)")

# Plot 2: Line plot - Window size effect per polynomial
ax = axes[0, 1]
for poly in [1, 2, 3]:
    subset = results_df[results_df["poly_order"] == poly].sort_values("window")
    poly_name = ["Linear", "Quadratic", "Cubic"][poly - 1]
    ax.plot(
        subset["window"],
        subset["p2p"],
        marker="o",
        label=f"Order {poly} ({poly_name})",
        linewidth=2,
    )

ax.axhline(
    y=2,
    color="r",
    linestyle="--",
    label="Target (2 RU)",
    linewidth=2,
    alpha=0.5,
)
if current_p2p:
    ax.axhline(
        y=current_p2p,
        color="k",
        linestyle=":",
        label=f"Current ({current_p2p:.1f} RU)",
        linewidth=2,
    )
ax.set_xlabel("Regression Window Size")
ax.set_ylabel("Peak-to-Peak Noise (RU)")
ax.set_title("Window Size Effect by Polynomial Order")
ax.legend()
ax.grid(True, alpha=0.3)

# Plot 3: Bar chart - Best configurations
ax = axes[1, 0]
top_10 = results_df.nsmallest(10, "p2p")
labels = [f"W={row['window']}, P={row['poly_order']}" for _, row in top_10.iterrows()]
colors = [
    "green"
    if row["poly_order"] == 1
    else "orange"
    if row["poly_order"] == 2
    else "purple"
    for _, row in top_10.iterrows()
]
ax.barh(labels, top_10["p2p"], color=colors)
ax.axvline(x=2, color="r", linestyle="--", linewidth=2, alpha=0.5)
if current_p2p:
    ax.axvline(x=current_p2p, color="k", linestyle=":", linewidth=2)
ax.set_xlabel("Peak-to-Peak Noise (RU)")
ax.set_title("Top 10 Configurations")
ax.grid(True, alpha=0.3, axis="x")

# Plot 4: Time series comparison (top 3)
ax = axes[1, 1]
if current_p2p:
    current_series = current.iloc[0]["series"]
    ax.plot(
        current_series,
        alpha=0.3,
        label=f"Current (W=50, P=1): {current_p2p:.1f} RU",
        color="gray",
        linewidth=2,
    )

colors_ts = ["green", "blue", "purple"]
for i in range(min(3, len(results_df))):
    result = results_df.nsmallest(3, "p2p").iloc[i]
    poly_name = ["Linear", "Quadratic", "Cubic"][result["poly_order"] - 1]
    label = f"W={result['window']}, P={result['poly_order']} ({poly_name}): {result['p2p']:.1f} RU"
    ax.plot(result["series"], label=label, linewidth=2, alpha=0.8, color=colors_ts[i])

ax.set_xlabel("Time Point")
ax.set_ylabel("SPR (RU)")
ax.set_title("Time Series Comparison (Top 3)")
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("fourier_window_polynomial_optimization.png", dpi=150, bbox_inches="tight")
print("\n[OK] Plots saved to: fourier_window_polynomial_optimization.png")

# ============================================================================
# RECOMMENDATION
# ============================================================================
print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)

print("\n🎯 OPTIMAL CONFIGURATION:")
print(f"   Regression Window: {best['window']} (currently 50)")
print(f"   Polynomial Order: {best['poly_order']} (currently 1)")
print(f"   Expected Noise: {best['p2p']:.2f} RU")
if current_p2p:
    print(f"   Improvement: {(1 - best['p2p']/current_p2p)*100:.1f}% from current")

# Check if wider windows help
linear_only = results_df[results_df["poly_order"] == 1].sort_values("window")
if len(linear_only) > 1:
    min_window = linear_only.iloc[0]
    max_window = linear_only.iloc[-1]
    if max_window["p2p"] < min_window["p2p"]:
        print(
            f"\n[OK] WIDER WINDOWS HELP: {max_window['window']} better than {min_window['window']} for linear regression",
        )
    else:
        print(
            f"\n[WARN] WIDER WINDOWS DON'T HELP: {min_window['window']} better than {max_window['window']} for linear regression",
        )

# Check if polynomial helps
for window in [50, 100, 150]:
    subset = results_df[results_df["window"] == window].sort_values("poly_order")
    if len(subset) >= 2:
        linear = subset[subset["poly_order"] == 1]
        higher = subset[subset["poly_order"] > 1]
        if len(linear) > 0 and len(higher) > 0:
            if higher["p2p"].min() < linear["p2p"].values[0]:
                best_higher = higher.loc[higher["p2p"].idxmin()]
                improvement = (1 - best_higher["p2p"] / linear["p2p"].values[0]) * 100
                poly_name = ["Quadratic", "Cubic"][best_higher["poly_order"] - 2]
                print(
                    f"[OK] At Window={window}: {poly_name} (P={best_higher['poly_order']}) gives {improvement:.1f}% improvement over Linear",
                )

print("\n" + "=" * 80)
