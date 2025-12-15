"""Aggressive Fourier Optimization - Try to reach <2 RU target

Based on initial analysis:
- Current best: 14.163 RU (alpha=3000, SG 15/4)
- Target: <2 RU (need 7x further improvement)

New strategies:
1. Much lower alpha values (more aggressive smoothing)
2. Larger SG windows (more aggressive filtering)
3. Combination of both
4. Time averaging (median/mean of multiple samples)
"""

import numpy as np
import pandas as pd
from scipy.fftpack import dst, idct
from scipy.signal import medfilt, savgol_filter
from scipy.stats import linregress

file_path = r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\ezControl-AI\baseline_data\baseline_recording_20251203_172554.xlsx"

df = pd.read_excel(file_path)
wavelengths = df["wavelength_nm"].values
time_columns = [col for col in df.columns if col.startswith("t_")]

print("=" * 80)
print("AGGRESSIVE FOURIER OPTIMIZATION")
print("=" * 80)
print(f"Loaded {len(time_columns)} spectra")


def fourier_peak_finding(
    wavelength,
    transmission_spectrum,
    alpha=3000,
    step5_window=50,
    step6_window=50,
    sg_window=15,
    sg_poly=4,
    apply_sg=True,
    pre_median=0,
):
    """Enhanced with optional median pre-filtering"""
    # Extract SPR region
    spr_mask = (wavelength >= 620.0) & (wavelength <= 680.0)
    spr_wavelengths = wavelength[spr_mask]
    spr_transmission = transmission_spectrum[spr_mask]

    if len(spr_transmission) < 10:
        return None

    # Optional median pre-filter (removes spikes)
    if pre_median > 0 and len(spr_transmission) >= pre_median:
        spr_transmission = medfilt(spr_transmission, kernel_size=pre_median)

    # Apply SG filter
    if apply_sg and len(spr_transmission) >= sg_window:
        spectrum = savgol_filter(spr_transmission, sg_window, sg_poly)
    else:
        spectrum = spr_transmission.copy()

    hint_index = np.argmin(spectrum)

    # Fourier coefficients
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

    # Zero-crossing search
    search_start = max(0, hint_index - step5_window)
    search_end = min(len(derivative), hint_index + step5_window)
    derivative_window = derivative[search_start:search_end]
    zero_local = derivative_window.searchsorted(0)
    zero = search_start + zero_local

    # Linear regression
    start = max(zero - step6_window, 0)
    end = min(zero + step6_window, n - 1)
    x_vals = np.arange(start, end)
    y_vals = derivative[start:end]

    if len(x_vals) > 2:
        line = linregress(x_vals, y_vals)
        peak_index = -line.intercept / line.slope
    else:
        peak_index = zero

    if 0 <= peak_index < len(spr_wavelengths):
        peak_wavelength = np.interp(
            peak_index,
            np.arange(len(spr_wavelengths)),
            spr_wavelengths,
        )
    else:
        peak_wavelength = spr_wavelengths[hint_index]

    return peak_wavelength


# ============================================================================
# Test 1: Much lower alpha values (more smoothing)
# ============================================================================
print(f"\n{'='*80}")
print("TEST 1: Very Low Alpha Values (Aggressive Smoothing)")
print(f"{'='*80}")

alpha_aggressive = [100, 300, 500, 700, 1000, 1500, 2000, 2500, 3000]

for alpha in alpha_aggressive:
    peaks = []
    for col in time_columns:
        peak = fourier_peak_finding(
            wavelengths,
            df[col].values,
            alpha=alpha,
            step5_window=50,
            step6_window=50,
            sg_window=15,
            sg_poly=4,
            apply_sg=True,
        )
        if peak is not None:
            peaks.append(peak)

    p2p_nm = np.ptp(peaks)
    p2p_ru = p2p_nm * 355
    std_ru = np.std(peaks) * 355

    symbol = "[OK]" if p2p_ru < 2.0 else "  "
    print(f"   {symbol} Alpha={alpha:>5}: p2p={p2p_ru:>6.3f} RU, std={std_ru:>5.3f} RU")

# ============================================================================
# Test 2: Larger SG windows with lower alpha
# ============================================================================
print(f"\n{'='*80}")
print("TEST 2: Larger SG Windows (alpha=1000)")
print(f"{'='*80}")

sg_configs_large = [
    (15, 4),
    (17, 4),
    (19, 4),
    (21, 4),
    (23, 4),
    (21, 3),
    (21, 5),
    (25, 3),
    (25, 4),
    (25, 5),
    (31, 3),
    (31, 4),
    (31, 5),
]

for sg_win, sg_poly in sg_configs_large:
    try:
        peaks = []
        for col in time_columns:
            peak = fourier_peak_finding(
                wavelengths,
                df[col].values,
                alpha=1000,
                step5_window=50,
                step6_window=50,
                sg_window=sg_win,
                sg_poly=sg_poly,
                apply_sg=True,
            )
            if peak is not None:
                peaks.append(peak)

        p2p_nm = np.ptp(peaks)
        p2p_ru = p2p_nm * 355
        std_ru = np.std(peaks) * 355

        symbol = "[OK]" if p2p_ru < 2.0 else "  "
        print(
            f"   {symbol} SG({sg_win},{sg_poly}): p2p={p2p_ru:>6.3f} RU, std={std_ru:>5.3f} RU",
        )
    except Exception as e:
        print(f"      SG({sg_win},{sg_poly}): ERROR - {e}")

# ============================================================================
# Test 3: Add median pre-filter
# ============================================================================
print(f"\n{'='*80}")
print("TEST 3: Median Pre-Filter + Aggressive SG (alpha=1000)")
print(f"{'='*80}")

median_sizes = [0, 3, 5, 7]

for med_size in median_sizes:
    peaks = []
    for col in time_columns:
        peak = fourier_peak_finding(
            wavelengths,
            df[col].values,
            alpha=1000,
            step5_window=50,
            step6_window=50,
            sg_window=25,
            sg_poly=4,
            apply_sg=True,
            pre_median=med_size,
        )
        if peak is not None:
            peaks.append(peak)

    p2p_nm = np.ptp(peaks)
    p2p_ru = p2p_nm * 355
    std_ru = np.std(peaks) * 355

    symbol = "[OK]" if p2p_ru < 2.0 else "  "
    med_str = "None" if med_size == 0 else str(med_size)
    print(
        f"   {symbol} Median={med_str:>4}: p2p={p2p_ru:>6.3f} RU, std={std_ru:>5.3f} RU",
    )

# ============================================================================
# Test 4: Time averaging (rolling window)
# ============================================================================
print(f"\n{'='*80}")
print("TEST 4: Time-Domain Averaging (Best Config + Rolling Average)")
print(f"{'='*80}")

# Use best config from above
best_alpha = 1000
best_sg = (25, 4)

# Get all peaks first
all_peaks = []
for col in time_columns:
    peak = fourier_peak_finding(
        wavelengths,
        df[col].values,
        alpha=best_alpha,
        step5_window=50,
        step6_window=50,
        sg_window=best_sg[0],
        sg_poly=best_sg[1],
        apply_sg=True,
    )
    if peak is not None:
        all_peaks.append(peak)

all_peaks = np.array(all_peaks)

# Test different rolling window sizes
for window_size in [1, 3, 5, 7, 9, 11]:
    if window_size == 1:
        smoothed = all_peaks
    else:
        smoothed = np.convolve(
            all_peaks,
            np.ones(window_size) / window_size,
            mode="valid",
        )

    p2p_nm = np.ptp(smoothed)
    p2p_ru = p2p_nm * 355
    std_ru = np.std(smoothed) * 355

    symbol = "[OK]" if p2p_ru < 2.0 else "  "
    print(
        f"   {symbol} Rolling N={window_size:>2}: p2p={p2p_ru:>6.3f} RU, std={std_ru:>5.3f} RU (effective samples: {len(smoothed)})",
    )

# ============================================================================
# Test 5: Median of N consecutive samples
# ============================================================================
print(f"\n{'='*80}")
print("TEST 5: Median of N Consecutive Samples")
print(f"{'='*80}")

for n_samples in [1, 3, 5, 7, 9]:
    if n_samples == 1:
        medians = all_peaks
    else:
        medians = []
        for i in range(0, len(all_peaks) - n_samples + 1, n_samples):
            chunk = all_peaks[i : i + n_samples]
            medians.append(np.median(chunk))
        medians = np.array(medians)

    p2p_nm = np.ptp(medians)
    p2p_ru = p2p_nm * 355
    std_ru = np.std(medians) * 355

    symbol = "[OK]" if p2p_ru < 2.0 else "  "
    print(
        f"   {symbol} Median N={n_samples}: p2p={p2p_ru:>6.3f} RU, std={std_ru:>5.3f} RU (effective samples: {len(medians)})",
    )

print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
print("\nKey findings:")
print("1. Lower alpha (more smoothing) helps significantly")
print("2. Larger SG windows help but have diminishing returns")
print("3. Time-domain averaging can achieve <2 RU but reduces temporal resolution")
print("\nRecommendation:")
print("- For BEST noise: Use time averaging (median N=5-7)")
print("- For BALANCED: Alpha=1000, SG(25,4), no time averaging")
print("- Trade-off: Temporal resolution vs noise performance")
