"""Test WITH SNR-aware weighting using S-pol reference data.

This script loads the full calibration data to access S-pol reference
and applies the exact same SNR weighting used in live acquisition.
"""

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.fftpack import dst, idct
from scipy.stats import linregress

# Load baseline data
baseline_file = r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\ezControl-AI\baseline_data\baseline_recording_20251203_172554.xlsx"
df = pd.read_excel(baseline_file)

wavelengths = df["wavelength_nm"].values
time_columns = [col for col in df.columns if col.startswith("t_")]
n_timepoints = len(time_columns)

# Load calibration data for S-pol reference
calib_file = r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\ezControl-AI\calibration_results\latest_calibration.json"
try:
    with open(calib_file) as f:
        calib_data = json.load(f)

    # Extract S-pol reference if available
    s_pol_ref = {}
    if "s_pol_reference" in calib_data:
        for ch in ["a", "b", "c", "d"]:
            if ch in calib_data["s_pol_reference"]:
                s_pol_ref[ch] = np.array(calib_data["s_pol_reference"][ch])

    # Also check raw_data section
    elif "raw_data" in calib_data and "s_pol_spectra" in calib_data["raw_data"]:
        for ch in ["a", "b", "c", "d"]:
            if ch in calib_data["raw_data"]["s_pol_spectra"]:
                s_pol_ref[ch] = np.array(calib_data["raw_data"]["s_pol_spectra"][ch])

    has_spol = len(s_pol_ref) > 0
    print(f"S-pol reference loaded: {has_spol} ({len(s_pol_ref)} channels)")
except Exception as e:
    print(f"Warning: Could not load S-pol reference: {e}")
    s_pol_ref = {}
    has_spol = False

print("=" * 80)
print("BASELINE vs OPTIMIZED WITH SNR-AWARE WEIGHTING")
print("=" * 80)
print(f"Dataset: {n_timepoints} timepoints, {len(wavelengths)} wavelengths")
print(f"SNR weighting: {'ENABLED' if has_spol else 'DISABLED (no S-pol data)'}\n")


def apply_fourier_method(
    transmission_spectrum,
    wavelengths,
    alpha=9000,
    regression_window=50,
    regression_poly=1,
    channel="a",
    use_snr_weighting=True,
):
    """Fourier peak finding WITH optional SNR weighting."""
    # SPR region
    spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
    spr_wavelengths = wavelengths[spr_mask]
    spr_transmission = transmission_spectrum[spr_mask]

    # NO SG FILTER - use raw transmission
    spectrum = spr_transmission

    # Apply SNR-aware weighting if available
    if use_snr_weighting and has_spol and channel in s_pol_ref:
        s_ref_full = s_pol_ref[channel]

        # Make sure lengths match
        if len(s_ref_full) == len(wavelengths):
            spr_s_reference = s_ref_full[spr_mask]

            # Calculate SNR weights (exactly as in data_acquisition_manager.py)
            s_min, s_max = np.min(spr_s_reference), np.max(spr_s_reference)
            if s_max > s_min:
                normalized_s = (spr_s_reference - s_min) / (s_max - s_min)
                snr_weights = 1.0 + 0.3 * normalized_s  # 30% adjustment strength
                snr_weights = snr_weights / np.mean(
                    snr_weights,
                )  # Normalize to mean=1.0
                weighted_spectrum = spectrum * snr_weights
            else:
                weighted_spectrum = spectrum
        else:
            weighted_spectrum = spectrum
    else:
        weighted_spectrum = spectrum

    hint_index = np.argmin(weighted_spectrum)

    # Fourier transform
    n = len(weighted_spectrum)
    n_inner = n - 1
    phi = np.pi / n_inner * np.arange(1, n_inner)
    phi2 = phi**2
    fourier_weights = phi / (1 + alpha * phi2 * (1 + phi2))

    fourier_coeff = np.zeros_like(weighted_spectrum)
    fourier_coeff[0] = 2 * (weighted_spectrum[-1] - weighted_spectrum[0])
    detrended = (
        weighted_spectrum[1:-1]
        - np.linspace(weighted_spectrum[0], weighted_spectrum[-1], n)[1:-1]
    )
    fourier_coeff[1:-1] = fourier_weights * dst(detrended, 1)

    derivative = idct(fourier_coeff, 1)

    # Zero-crossing search
    search_start = max(0, hint_index - 50)
    search_end = min(len(derivative), hint_index + 50)
    derivative_window = derivative[search_start:search_end]
    zero_local = derivative_window.searchsorted(0)
    zero = search_start + zero_local

    # Peak refinement
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


def get_spr_series(
    alpha=9000,
    regression_window=50,
    regression_poly=1,
    channel="a",
    use_snr_weighting=True,
):
    """Get SPR time series."""
    wavelength_series = []

    for time_col in time_columns:
        transmission_spectrum = df[time_col].values
        try:
            wavelength = apply_fourier_method(
                transmission_spectrum,
                wavelengths,
                alpha=alpha,
                regression_window=regression_window,
                regression_poly=regression_poly,
                channel=channel,
                use_snr_weighting=use_snr_weighting,
            )
            wavelength_series.append(wavelength)
        except:
            wavelength_series.append(np.nan)

    wavelength_series = np.array(wavelength_series)
    valid_mask = np.isfinite(wavelength_series)
    wavelength_series = wavelength_series[valid_mask]

    # Convert to RU
    spr_series = (wavelength_series - wavelength_series[0]) * 355

    # Remove polynomial trend (detrend to center around 0)
    time_indices = np.arange(len(spr_series))
    poly_coeffs = np.polyfit(time_indices, spr_series, deg=2)  # Quadratic detrend
    poly_trend = np.polyval(poly_coeffs, time_indices)
    spr_detrended = spr_series - poly_trend

    return spr_detrended


# ============================================================================
# TEST WITH AND WITHOUT SNR WEIGHTING
# ============================================================================
print("\nTesting configurations...")

# Assume baseline was from channel 'a' (most common)
channel = "a"

configurations = []

# Config 1: Baseline (no SNR weighting)
spr = get_spr_series(
    alpha=9000,
    regression_window=50,
    regression_poly=1,
    channel=channel,
    use_snr_weighting=False,
)
configurations.append(
    {
        "name": "Baseline (no SNR)",
        "snr": False,
        "alpha": 9000,
        "window": 50,
        "poly": "Linear",
        "p2p": np.ptp(spr),
        "std": np.std(spr),
        "series": spr,
    },
)

# Config 2: Baseline WITH SNR weighting
if has_spol:
    spr = get_spr_series(
        alpha=9000,
        regression_window=50,
        regression_poly=1,
        channel=channel,
        use_snr_weighting=True,
    )
    configurations.append(
        {
            "name": "Baseline + SNR",
            "snr": True,
            "alpha": 9000,
            "window": 50,
            "poly": "Linear",
            "p2p": np.ptp(spr),
            "std": np.std(spr),
            "series": spr,
        },
    )

# Config 3: Optimized (no SNR weighting)
spr = get_spr_series(
    alpha=2000,
    regression_window=100,
    regression_poly=2,
    channel=channel,
    use_snr_weighting=False,
)
configurations.append(
    {
        "name": "Optimized (no SNR)",
        "snr": False,
        "alpha": 2000,
        "window": 100,
        "poly": "Quadratic",
        "p2p": np.ptp(spr),
        "std": np.std(spr),
        "series": spr,
    },
)

# Config 4: Optimized WITH SNR weighting
if has_spol:
    spr = get_spr_series(
        alpha=2000,
        regression_window=100,
        regression_poly=2,
        channel=channel,
        use_snr_weighting=True,
    )
    configurations.append(
        {
            "name": "Optimized + SNR",
            "snr": True,
            "alpha": 2000,
            "window": 100,
            "poly": "Quadratic",
            "p2p": np.ptp(spr),
            "std": np.std(spr),
            "series": spr,
        },
    )

# ============================================================================
# RESULTS
# ============================================================================
print("\n" + "=" * 80)
print("RESULTS")
print("=" * 80)

baseline = configurations[0]

print("\n📊 ALL CONFIGURATIONS:\n")
for config in configurations:
    improvement = (1 - config["p2p"] / baseline["p2p"]) * 100
    marker = "⭐" if "Optimized + SNR" in config["name"] else "  "
    snr_str = "✓" if config["snr"] else "✗"
    print(
        f"{marker} {config['name']:22s} [SNR:{snr_str}]: p2p={config['p2p']:6.2f} RU  ({improvement:+5.1f}%)",
    )

if has_spol and len(configurations) >= 4:
    baseline_no_snr = configurations[0]
    baseline_with_snr = configurations[1]
    optimized_no_snr = configurations[2]
    optimized_with_snr = configurations[3]

    print("\n" + "=" * 80)
    print("SNR WEIGHTING IMPACT")
    print("=" * 80)

    snr_impact_baseline = (1 - baseline_with_snr["p2p"] / baseline_no_snr["p2p"]) * 100
    snr_impact_optimized = (
        1 - optimized_with_snr["p2p"] / optimized_no_snr["p2p"]
    ) * 100

    print("\n📈 SNR weighting effect on BASELINE:")
    print(f"   Without SNR: {baseline_no_snr['p2p']:.2f} RU")
    print(f"   With SNR:    {baseline_with_snr['p2p']:.2f} RU")
    print(f"   Improvement: {snr_impact_baseline:.1f}%")

    print("\n✨ SNR weighting effect on OPTIMIZED:")
    print(f"   Without SNR: {optimized_no_snr['p2p']:.2f} RU")
    print(f"   With SNR:    {optimized_with_snr['p2p']:.2f} RU")
    print(f"   Improvement: {snr_impact_optimized:.1f}%")

    print("\n🎯 TOTAL IMPROVEMENT (Baseline no SNR → Optimized + SNR):")
    total_improvement = (1 - optimized_with_snr["p2p"] / baseline_no_snr["p2p"]) * 100
    print(
        f"   {baseline_no_snr['p2p']:.2f} → {optimized_with_snr['p2p']:.2f} RU  ({total_improvement:.1f}%)",
    )

    # ========================================================================
    # VISUALIZATION
    # ========================================================================
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    # Plot 1: All four configurations
    ax = axes[0, 0]
    time_points = np.arange(len(baseline_no_snr["series"]))
    colors = ["red", "orange", "lightgreen", "darkgreen"]
    for i, config in enumerate(configurations):
        ax.plot(
            time_points,
            config["series"],
            label=config["name"],
            color=colors[i],
            linewidth=2,
            alpha=0.7,
        )
    ax.set_xlabel("Time Point", fontweight="bold")
    ax.set_ylabel("SPR (RU)", fontweight="bold")
    ax.set_title("All Configurations Comparison", fontweight="bold", fontsize=13)
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Plot 2: SNR impact on baseline
    ax = axes[0, 1]
    ax.plot(
        time_points,
        baseline_no_snr["series"],
        label=f'No SNR ({baseline_no_snr["p2p"]:.2f} RU)',
        color="red",
        linewidth=2,
        alpha=0.7,
    )
    ax.plot(
        time_points,
        baseline_with_snr["series"],
        label=f'With SNR ({baseline_with_snr["p2p"]:.2f} RU)',
        color="orange",
        linewidth=2,
        alpha=0.7,
    )
    ax.set_xlabel("Time Point", fontweight="bold")
    ax.set_ylabel("SPR (RU)", fontweight="bold")
    ax.set_title(
        f"SNR Impact on Baseline ({snr_impact_baseline:+.1f}%)",
        fontweight="bold",
        fontsize=13,
    )
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Plot 3: SNR impact on optimized
    ax = axes[1, 0]
    ax.plot(
        time_points,
        optimized_no_snr["series"],
        label=f'No SNR ({optimized_no_snr["p2p"]:.2f} RU)',
        color="lightgreen",
        linewidth=2,
        alpha=0.7,
    )
    ax.plot(
        time_points,
        optimized_with_snr["series"],
        label=f'With SNR ({optimized_with_snr["p2p"]:.2f} RU)',
        color="darkgreen",
        linewidth=2,
        alpha=0.7,
    )
    ax.set_xlabel("Time Point", fontweight="bold")
    ax.set_ylabel("SPR (RU)", fontweight="bold")
    ax.set_title(
        f"SNR Impact on Optimized ({snr_impact_optimized:+.1f}%)",
        fontweight="bold",
        fontsize=13,
    )
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Plot 4: Bar chart summary
    ax = axes[1, 1]
    labels = [
        "Baseline\n(no SNR)",
        "Baseline\n(+SNR)",
        "Optimized\n(no SNR)",
        "Optimized\n(+SNR)",
    ]
    p2p_values = [c["p2p"] for c in configurations]
    bars = ax.bar(labels, p2p_values, color=colors, edgecolor="black", linewidth=1.5)
    ax.set_ylabel("Peak-to-Peak Noise (RU)", fontweight="bold")
    ax.set_title("Noise Comparison Summary", fontweight="bold", fontsize=13)
    ax.grid(True, alpha=0.3, axis="y")

    # Annotate bars
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height:.1f}",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )

    plt.tight_layout()
    plt.savefig("snr_weighting_impact.png", dpi=150, bbox_inches="tight")
    print("\n[OK] Plot saved to: snr_weighting_impact.png")

else:
    print("\n[WARN] SNR weighting test skipped - no S-pol reference data available")

print("\n" + "=" * 80)
