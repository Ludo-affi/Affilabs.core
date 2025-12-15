"""Optimize hybrid parameters to balance noise reduction with position accuracy.

Goal: Find parameters that reduce baseline noise WITHOUT sacrificing peak position accuracy.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.fftpack import dst, idct
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import curve_fit
from scipy.signal import savgol_filter
from scipy.stats import linregress

# Load baseline data
baseline_file = r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\ezControl-AI\baseline_data\baseline_recording_20251203_172554.xlsx"
df = pd.read_excel(baseline_file)

wavelengths = df["wavelength_nm"].values
time_columns = [col for col in df.columns if col.startswith("t_")]

print("=" * 80)
print("HYBRID PARAMETER OPTIMIZATION")
print("=" * 80)


def apply_method(spr_transmission, spr_wavelengths, params):
    """Apply peak finding with specified parameters."""
    try:
        # Unpack parameters
        sg_window = params["sg_window"]
        sg_poly = params["sg_poly"]
        gaussian_sigma = params["gaussian_sigma"]
        alpha = params["alpha"]
        regression_window = params["regression_window"]
        use_quadratic = params["use_quadratic"]
        gaussian_refinement_weight = params["gaussian_refinement"]

        # Apply filtering
        spectrum = savgol_filter(
            spr_transmission,
            window_length=sg_window,
            polyorder=sg_poly,
        )

        if gaussian_sigma > 0:
            spectrum = gaussian_filter1d(spectrum, sigma=gaussian_sigma)

        hint_index = np.argmin(spectrum)
        n = len(spectrum)
        n_inner = n - 1

        # Fourier derivative
        phi = np.pi / n_inner * np.arange(1, n_inner)
        phi2 = phi**2
        fourier_weights = phi / (1 + alpha * phi2 * (1 + phi2))

        fourier_coeff = np.zeros_like(spectrum)
        fourier_coeff[0] = 2 * (spectrum[-1] - spectrum[0])
        detrended = spectrum[1:-1] - np.linspace(spectrum[0], spectrum[-1], n)[1:-1]
        fourier_coeff[1:-1] = fourier_weights * dst(detrended, 1)

        derivative = idct(fourier_coeff, 1)

        # Find zero crossing
        search_start = max(0, hint_index - 50)
        search_end = min(len(derivative), hint_index + 50)
        derivative_window = derivative[search_start:search_end]
        zero_local = derivative_window.searchsorted(0)
        zero = search_start + zero_local

        # Regression
        start = max(zero - regression_window, 0)
        end = min(zero + regression_window, n - 1)

        x = spr_wavelengths[start:end]
        y = derivative[start:end]

        if use_quadratic:
            coeffs = np.polyfit(x, y, 2)
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
        else:
            line = linregress(x, y)
            peak_wavelength = -line.intercept / line.slope

        # Optional Gaussian refinement
        if gaussian_refinement_weight > 0:
            try:

                def peak_model(x, x0, A, sigma, baseline):
                    return baseline - A * np.exp(-(((x - x0) / sigma) ** 2))

                baseline_val = np.max(spectrum)
                amplitude = baseline_val - np.min(spectrum)

                p0 = [peak_wavelength, amplitude, 20.0, baseline_val]
                bounds = (
                    [spr_wavelengths[0], 0, 5, 0],
                    [spr_wavelengths[-1], 100, 80, 100],
                )

                popt, _ = curve_fit(
                    peak_model,
                    spr_wavelengths,
                    spectrum,
                    p0=p0,
                    bounds=bounds,
                    maxfev=2000,
                )
                gaussian_peak = popt[0]

                if abs(gaussian_peak - peak_wavelength) < 2.0:
                    peak_wavelength = (
                        1 - gaussian_refinement_weight
                    ) * peak_wavelength + gaussian_refinement_weight * gaussian_peak
            except:
                pass

        return peak_wavelength
    except:
        return np.nan


def evaluate_parameters(params, time_cols):
    """Evaluate parameter set on baseline noise and position accuracy."""
    peaks = []

    for time_col in time_cols:
        transmission_spectrum = df[time_col].values
        spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
        spr_wavelengths = wavelengths[spr_mask]
        spr_transmission = transmission_spectrum[spr_mask]

        peak = apply_method(spr_transmission, spr_wavelengths, params)

        if not np.isnan(peak):
            peaks.append(peak)

    if len(peaks) < 10:
        return np.nan, np.nan, np.nan

    peaks = np.array(peaks)

    # Polynomial detrending (degree 2)
    time_indices = np.arange(len(peaks))
    coeffs = np.polyfit(time_indices, peaks, 2)
    trend = np.polyval(coeffs, time_indices)
    detrended = peaks - trend

    # Convert to RU
    detrended_ru = detrended * 355

    # Calculate baseline noise (std of detrended signal)
    baseline_noise = np.std(detrended_ru)

    # Calculate position accuracy (error from minimum)
    # Use first spectrum as reference
    transmission_spectrum = df[time_cols[0]].values
    spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
    spr_wavelengths = wavelengths[spr_mask]
    spr_transmission = transmission_spectrum[spr_mask]
    min_pos = spr_wavelengths[np.argmin(spr_transmission)]

    position_error = abs(peaks[0] - min_pos)

    # Calculate DC offset (mean of detrended)
    dc_offset = np.mean(detrended_ru)

    return baseline_noise, position_error, dc_offset


# Reference: Current production method
current_params = {
    "sg_window": 11,
    "sg_poly": 3,
    "gaussian_sigma": 0,
    "alpha": 9000,
    "regression_window": 50,
    "use_quadratic": False,
    "gaussian_refinement": 0.0,
}

# Reference: Original hybrid
original_hybrid_params = {
    "sg_window": 11,
    "sg_poly": 5,
    "gaussian_sigma": 1.5,
    "alpha": 2000,
    "regression_window": 100,
    "use_quadratic": True,
    "gaussian_refinement": 0.1,
}

# Test configurations
test_configs = [
    ("Current Production", current_params),
    ("Original Hybrid", original_hybrid_params),
    # Less aggressive filtering
    (
        "Hybrid Light v1",
        {
            "sg_window": 11,
            "sg_poly": 3,
            "gaussian_sigma": 0.5,
            "alpha": 2000,
            "regression_window": 50,
            "use_quadratic": False,
            "gaussian_refinement": 0.0,
        },
    ),
    (
        "Hybrid Light v2",
        {
            "sg_window": 11,
            "sg_poly": 3,
            "gaussian_sigma": 1.0,
            "alpha": 2000,
            "regression_window": 50,
            "use_quadratic": False,
            "gaussian_refinement": 0.0,
        },
    ),
    (
        "Hybrid Light v3",
        {
            "sg_window": 11,
            "sg_poly": 4,
            "gaussian_sigma": 0.8,
            "alpha": 2000,
            "regression_window": 50,
            "use_quadratic": False,
            "gaussian_refinement": 0.0,
        },
    ),
    # Medium filtering
    (
        "Hybrid Medium v1",
        {
            "sg_window": 11,
            "sg_poly": 4,
            "gaussian_sigma": 1.0,
            "alpha": 2000,
            "regression_window": 60,
            "use_quadratic": False,
            "gaussian_refinement": 0.0,
        },
    ),
    (
        "Hybrid Medium v2",
        {
            "sg_window": 11,
            "sg_poly": 5,
            "gaussian_sigma": 0.8,
            "alpha": 2000,
            "regression_window": 60,
            "use_quadratic": False,
            "gaussian_refinement": 0.0,
        },
    ),
    (
        "Hybrid Medium v3",
        {
            "sg_window": 11,
            "sg_poly": 4,
            "gaussian_sigma": 1.2,
            "alpha": 2000,
            "regression_window": 70,
            "use_quadratic": False,
            "gaussian_refinement": 0.0,
        },
    ),
    # Alpha variations with light filtering
    (
        "Alpha 3000 Light",
        {
            "sg_window": 11,
            "sg_poly": 3,
            "gaussian_sigma": 0.8,
            "alpha": 3000,
            "regression_window": 50,
            "use_quadratic": False,
            "gaussian_refinement": 0.0,
        },
    ),
    (
        "Alpha 4000 Light",
        {
            "sg_window": 11,
            "sg_poly": 3,
            "gaussian_sigma": 1.0,
            "alpha": 4000,
            "regression_window": 50,
            "use_quadratic": False,
            "gaussian_refinement": 0.0,
        },
    ),
    (
        "Alpha 5000 Light",
        {
            "sg_window": 11,
            "sg_poly": 3,
            "gaussian_sigma": 0.8,
            "alpha": 5000,
            "regression_window": 50,
            "use_quadratic": False,
            "gaussian_refinement": 0.0,
        },
    ),
    # Regression window variations
    (
        "Reg Window 70",
        {
            "sg_window": 11,
            "sg_poly": 3,
            "gaussian_sigma": 1.0,
            "alpha": 2000,
            "regression_window": 70,
            "use_quadratic": False,
            "gaussian_refinement": 0.0,
        },
    ),
    (
        "Reg Window 80",
        {
            "sg_window": 11,
            "sg_poly": 4,
            "gaussian_sigma": 1.0,
            "alpha": 2000,
            "regression_window": 80,
            "use_quadratic": False,
            "gaussian_refinement": 0.0,
        },
    ),
    # Best from alpha optimization with minimal extra filtering
    (
        "Optimized Alpha Only",
        {
            "sg_window": 11,
            "sg_poly": 3,
            "gaussian_sigma": 0,
            "alpha": 2000,
            "regression_window": 50,
            "use_quadratic": False,
            "gaussian_refinement": 0.0,
        },
    ),
]

print("\nEvaluating parameter configurations...")
print("-" * 100)
print(
    f"{'Configuration':25s} | {'Baseline (RU)':15s} | {'Position Err (nm)':18s} | {'DC Offset (RU)':15s} | {'Score':10s}",
)
print("-" * 100)

results = []
for name, params in test_configs:
    noise, pos_error, dc_offset = evaluate_parameters(params, time_columns)

    if not np.isnan(noise):
        # Score: prioritize position accuracy, then noise
        # Normalize to current method
        noise_ref = 17.98  # Current baseline
        pos_ref = 0.3195  # Current position error

        noise_score = noise / noise_ref  # Lower is better
        pos_score = pos_error / pos_ref  # Lower is better

        # Weighted score: 60% position accuracy, 40% noise
        combined_score = 0.6 * pos_score + 0.4 * noise_score

        results.append(
            {
                "name": name,
                "params": params,
                "noise": noise,
                "position_error": pos_error,
                "dc_offset": dc_offset,
                "score": combined_score,
            },
        )

        print(
            f"{name:25s} | {noise:8.2f} RU     | {pos_error:10.4f} nm      | {dc_offset:+8.2f} RU    | {combined_score:8.4f}",
        )

print("-" * 100)

# Sort by score
results.sort(key=lambda x: x["score"])

print("\n" + "=" * 80)
print("TOP 5 CONFIGURATIONS (Best Balance)")
print("=" * 80)

for i, result in enumerate(results[:5], 1):
    print(f"\n{i}. {result['name']}")
    print(
        f"   Baseline Noise: {result['noise']:.2f} RU ({(1 - result['noise']/17.98)*100:+.1f}%)",
    )
    print(
        f"   Position Error: {result['position_error']:.4f} nm ({(result['position_error']/0.3195 - 1)*100:+.1f}%)",
    )
    print(f"   DC Offset: {result['dc_offset']:+.2f} RU")
    print(f"   Combined Score: {result['score']:.4f}")
    print(f"   Parameters: {result['params']}")

# Detailed comparison of top 3
print("\n" + "=" * 80)
print("DETAILED ANALYSIS OF TOP 3")
print("=" * 80)

fig, axes = plt.subplots(2, 3, figsize=(18, 10))
fig.suptitle("Top 3 Configuration Comparison", fontweight="bold", fontsize=16)

for idx, result in enumerate(results[:3]):
    params = result["params"]

    # Get full time series
    peaks = []
    for time_col in time_columns:
        transmission_spectrum = df[time_col].values
        spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
        spr_wavelengths = wavelengths[spr_mask]
        spr_transmission = transmission_spectrum[spr_mask]

        peak = apply_method(spr_transmission, spr_wavelengths, params)

        if not np.isnan(peak):
            peaks.append(peak)

    peaks = np.array(peaks)

    # Detrend
    time_indices = np.arange(len(peaks))
    coeffs = np.polyfit(time_indices, peaks, 2)
    trend = np.polyval(coeffs, time_indices)
    detrended = peaks - trend
    detrended_ru = detrended * 355

    # Plot raw series
    ax1 = axes[0, idx]
    ax1.plot(peaks * 355, linewidth=1, alpha=0.7)
    ax1.set_title(
        f"{result['name']}\nNoise: {result['noise']:.2f} RU",
        fontweight="bold",
    )
    ax1.set_xlabel("Time Index")
    ax1.set_ylabel("Peak Position (RU)")
    ax1.grid(True, alpha=0.3)

    # Plot detrended
    ax2 = axes[1, idx]
    ax2.plot(detrended_ru, linewidth=1, alpha=0.7)
    ax2.axhline(y=0, color="red", linestyle="--", linewidth=1)
    ax2.set_title(f"Detrended (±{np.std(detrended_ru):.2f} RU)", fontweight="bold")
    ax2.set_xlabel("Time Index")
    ax2.set_ylabel("Detrended (RU)")
    ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("hybrid_parameter_optimization.png", dpi=150, bbox_inches="tight")
print("\n[OK] Optimization plot saved to: hybrid_parameter_optimization.png")

# Create comparison table
print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)

best = results[0]
print(f"\n🏆 BEST CONFIGURATION: {best['name']}")
print("\nParameters to use in settings.py:")
print("   PEAK_FINDING_METHOD = 'hybrid'")
print(f"   HYBRID_FOURIER_ALPHA = {best['params']['alpha']}")
print(f"   HYBRID_SG_POLY = {best['params']['sg_poly']}")
print(f"   HYBRID_GAUSSIAN_SIGMA = {best['params']['gaussian_sigma']}")
print(f"   HYBRID_REGRESSION_WINDOW = {best['params']['regression_window']}")
print(f"   HYBRID_USE_QUADRATIC = {best['params']['use_quadratic']}")
print(f"   HYBRID_GAUSSIAN_REFINEMENT = {best['params']['gaussian_refinement'] > 0}")

print("\nExpected Performance:")
print(
    f"   Baseline Noise: {best['noise']:.2f} RU ({(1 - best['noise']/17.98)*100:+.1f}% vs current)",
)
print(
    f"   Position Accuracy: {(best['position_error']/0.3195 - 1)*100:+.1f}% vs current",
)
print(f"   DC Offset: {best['dc_offset']:+.2f} RU (cosmetic)")

if best["position_error"] < 0.3195 * 1.1:  # Within 10% of current
    print("\n[OK] APPROVED: Position accuracy maintained within 10%")
    print(f"[OK] Noise reduction: {(1 - best['noise']/17.98)*100:.1f}%")
else:
    print(
        f"\n[WARN]  WARNING: Position accuracy degraded by {(best['position_error']/0.3195 - 1)*100:.1f}%",
    )

print("\n" + "=" * 80)
