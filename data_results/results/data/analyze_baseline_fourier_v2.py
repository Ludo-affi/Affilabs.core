"""
Analyze Baseline Recording to Optimize Fourier Peak Finding Parameters

This script analyzes transmission spectra from a 5-minute baseline recording
to identify the best Fourier parameters to achieve <2 RU peak-to-peak noise.

Target: <2 RU peak-to-peak (0.006 nm @ 355 RU/nm)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter
from scipy.fftpack import dst, idct
from scipy.stats import linregress

# ============================================================================
# Load Data
# ============================================================================
print("="*80)
print("BASELINE FOURIER OPTIMIZATION ANALYSIS")
print("="*80)

file_path = r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\ezControl-AI\baseline_data\baseline_recording_20251203_172554.xlsx"

# Read Excel file - transmission spectra over time
df = pd.read_excel(file_path)
print(f"\n[OK] Loaded baseline data")
print(f"   Shape: {df.shape} (wavelengths × time samples)")

# Extract wavelength array
wavelengths = df['wavelength_nm'].values
print(f"   Wavelength range: {wavelengths.min():.1f} - {wavelengths.max():.1f} nm")
print(f"   Wavelength points: {len(wavelengths)}")

# Get time columns (all columns except 'wavelength_nm')
time_columns = [col for col in df.columns if col.startswith('t_')]
num_samples = len(time_columns)
print(f"   Time samples: {num_samples} (~{num_samples} seconds @ 1 Hz)")

# ============================================================================
# Fourier Peak Finding Function
# ============================================================================
def fourier_peak_finding(wavelength, transmission_spectrum, alpha=9000, 
                        step5_window=50, step6_window=50, 
                        sg_window=11, sg_poly=3, apply_sg=True):
    """
    Replicate Fourier peak finding from data_acquisition_manager.py
    
    Returns: peak wavelength in nm
    """
    # Extract SPR region (620-680nm)
    spr_mask = (wavelength >= 620.0) & (wavelength <= 680.0)
    spr_wavelengths = wavelength[spr_mask]
    spr_transmission = transmission_spectrum[spr_mask]
    
    if len(spr_transmission) < 10:
        return None
    
    # Apply SG filter if enabled
    if apply_sg and len(spr_transmission) >= sg_window:
        spectrum = savgol_filter(spr_transmission, sg_window, sg_poly)
    else:
        spectrum = spr_transmission.copy()
    
    # Find minimum hint
    hint_index = np.argmin(spectrum)
    
    # Calculate Fourier coefficients
    n = len(spectrum)
    n_inner = n - 1
    
    phi = np.pi / n_inner * np.arange(1, n_inner)
    phi2 = phi**2
    fourier_weights = phi / (1 + alpha * phi2 * (1 + phi2))
    
    fourier_coeff = np.zeros_like(spectrum)
    fourier_coeff[0] = 2 * (spectrum[-1] - spectrum[0])
    
    detrended = spectrum[1:-1] - np.linspace(spectrum[0], spectrum[-1], n)[1:-1]
    fourier_coeff[1:-1] = fourier_weights * dst(detrended, 1)
    
    # Calculate derivative
    derivative = idct(fourier_coeff, 1)
    
    # Find zero-crossing near minimum hint
    search_start = max(0, hint_index - step5_window)
    search_end = min(len(derivative), hint_index + step5_window)
    
    derivative_window = derivative[search_start:search_end]
    zero_local = derivative_window.searchsorted(0)
    zero = search_start + zero_local
    
    # Refine with linear regression
    start = max(zero - step6_window, 0)
    end = min(zero + step6_window, n - 1)
    
    x_vals = np.arange(start, end)
    y_vals = derivative[start:end]
    
    if len(x_vals) > 2:
        line = linregress(x_vals, y_vals)
        peak_index = -line.intercept / line.slope
    else:
        peak_index = zero
    
    # Convert index to wavelength
    if 0 <= peak_index < len(spr_wavelengths):
        peak_wavelength = np.interp(peak_index, np.arange(len(spr_wavelengths)), spr_wavelengths)
    else:
        peak_wavelength = spr_wavelengths[hint_index]
    
    return peak_wavelength

# ============================================================================
# Analyze Current Settings
# ============================================================================
print(f"\n{'='*80}")
print("ANALYZING CURRENT SETTINGS (alpha=9000, windows=50, SG=11/3)")
print(f"{'='*80}")

current_peaks = []
for col in time_columns:
    spectrum = df[col].values
    peak = fourier_peak_finding(wavelengths, spectrum, 
                                alpha=9000, step5_window=50, step6_window=50,
                                sg_window=11, sg_poly=3, apply_sg=True)
    if peak is not None:
        current_peaks.append(peak)

current_peaks = np.array(current_peaks)
current_mean = np.mean(current_peaks)
current_std = np.std(current_peaks)
current_p2p = np.ptp(current_peaks)
current_ru_p2p = current_p2p * 355  # Convert nm to RU

print(f"\n📊 BASELINE PERFORMANCE:")
print(f"   Mean wavelength: {current_mean:.4f} nm")
print(f"   Std deviation: {current_std:.6f} nm ({current_std*355:.3f} RU)")
print(f"   Peak-to-Peak: {current_p2p:.6f} nm ({current_ru_p2p:.3f} RU)")
print(f"   RMS: {np.sqrt(np.mean((current_peaks - current_mean)**2)):.6f} nm")

if current_ru_p2p < 2.0:
    print(f"\n[OK] ALREADY MEETS TARGET! (<2 RU peak-to-peak)")
else:
    print(f"\n[WARN]  Target: <2 RU, Current: {current_ru_p2p:.3f} RU (need {current_ru_p2p/2:.1f}x improvement)")

# ============================================================================
# Test Alpha Values
# ============================================================================
print(f"\n{'='*80}")
print("1. TESTING ALPHA (Smoothing Strength)")
print(f"{'='*80}")

alpha_values = [3000, 5000, 7000, 9000, 11000, 13000, 15000, 20000]
alpha_results = []

for alpha in alpha_values:
    peaks = []
    for col in time_columns[:100]:  # Test on first 100 samples for speed
        spectrum = df[col].values
        peak = fourier_peak_finding(wavelengths, spectrum,
                                    alpha=alpha, step5_window=50, step6_window=50,
                                    sg_window=11, sg_poly=3, apply_sg=True)
        if peak is not None:
            peaks.append(peak)
    
    peaks = np.array(peaks)
    p2p_nm = np.ptp(peaks)
    p2p_ru = p2p_nm * 355
    std_nm = np.std(peaks)
    
    alpha_results.append({
        'alpha': alpha,
        'p2p_nm': p2p_nm,
        'p2p_ru': p2p_ru,
        'std_nm': std_nm
    })
    
    symbol = "[OK]" if p2p_ru < 2.0 else "  "
    print(f"   {symbol} Alpha={alpha:>6}: p2p={p2p_nm:.6f} nm ({p2p_ru:.3f} RU), std={std_nm:.6f} nm")

best_alpha = min(alpha_results, key=lambda x: x['p2p_ru'])
print(f"\n🎯 Best Alpha: {best_alpha['alpha']} → {best_alpha['p2p_ru']:.3f} RU")

# ============================================================================
# Test Window Sizes with Best Alpha
# ============================================================================
print(f"\n{'='*80}")
print("2. TESTING WINDOW SIZES (Step 5 & 6)")
print(f"{'='*80}")

window_values = [20, 30, 40, 50, 75, 100, 150]
window_results = []

for window in window_values:
    peaks = []
    for col in time_columns[:100]:
        spectrum = df[col].values
        peak = fourier_peak_finding(wavelengths, spectrum,
                                    alpha=best_alpha['alpha'],
                                    step5_window=window, step6_window=window,
                                    sg_window=11, sg_poly=3, apply_sg=True)
        if peak is not None:
            peaks.append(peak)
    
    peaks = np.array(peaks)
    p2p_nm = np.ptp(peaks)
    p2p_ru = p2p_nm * 355
    
    window_results.append({
        'window': window,
        'p2p_nm': p2p_nm,
        'p2p_ru': p2p_ru
    })
    
    symbol = "[OK]" if p2p_ru < 2.0 else "  "
    print(f"   {symbol} Window={window:>3}: p2p={p2p_nm:.6f} nm ({p2p_ru:.3f} RU)")

best_window = min(window_results, key=lambda x: x['p2p_ru'])
print(f"\n🎯 Best Window: {best_window['window']} → {best_window['p2p_ru']:.3f} RU")

# ============================================================================
# Test SG Filter Parameters
# ============================================================================
print(f"\n{'='*80}")
print("3. TESTING SG FILTER (Window & Polynomial)")
print(f"{'='*80}")

sg_configs = [
    (7, 2), (7, 3),
    (9, 2), (9, 3), (9, 4),
    (11, 2), (11, 3), (11, 4),
    (13, 2), (13, 3), (13, 4), (13, 5),
    (15, 3), (15, 4), (15, 5),
    (17, 3), (17, 4), (17, 5)
]

sg_results = []

for sg_win, sg_poly in sg_configs:
    try:
        peaks = []
        for col in time_columns[:100]:
            spectrum = df[col].values
            peak = fourier_peak_finding(wavelengths, spectrum,
                                        alpha=best_alpha['alpha'],
                                        step5_window=best_window['window'],
                                        step6_window=best_window['window'],
                                        sg_window=sg_win, sg_poly=sg_poly, apply_sg=True)
            if peak is not None:
                peaks.append(peak)
        
        peaks = np.array(peaks)
        p2p_nm = np.ptp(peaks)
        p2p_ru = p2p_nm * 355
        
        sg_results.append({
            'sg_window': sg_win,
            'sg_poly': sg_poly,
            'p2p_nm': p2p_nm,
            'p2p_ru': p2p_ru
        })
        
        symbol = "[OK]" if p2p_ru < 2.0 else "  "
        print(f"   {symbol} SG({sg_win},{sg_poly}): p2p={p2p_nm:.6f} nm ({p2p_ru:.3f} RU)")
    except:
        pass

best_sg = min(sg_results, key=lambda x: x['p2p_ru'])
print(f"\n🎯 Best SG: window={best_sg['sg_window']}, poly={best_sg['sg_poly']} → {best_sg['p2p_ru']:.3f} RU")

# ============================================================================
# Test Final Optimized Configuration on Full Dataset
# ============================================================================
print(f"\n{'='*80}")
print("4. VALIDATING OPTIMIZED SETTINGS ON FULL DATASET")
print(f"{'='*80}")

optimized_peaks = []
for col in time_columns:
    spectrum = df[col].values
    peak = fourier_peak_finding(wavelengths, spectrum,
                                alpha=best_alpha['alpha'],
                                step5_window=best_window['window'],
                                step6_window=best_window['window'],
                                sg_window=best_sg['sg_window'],
                                sg_poly=best_sg['sg_poly'],
                                apply_sg=True)
    if peak is not None:
        optimized_peaks.append(peak)

optimized_peaks = np.array(optimized_peaks)
opt_mean = np.mean(optimized_peaks)
opt_std = np.std(optimized_peaks)
opt_p2p = np.ptp(optimized_peaks)
opt_ru_p2p = opt_p2p * 355

print(f"\n📊 OPTIMIZED PERFORMANCE ({len(optimized_peaks)} samples):")
print(f"   Mean wavelength: {opt_mean:.4f} nm")
print(f"   Std deviation: {opt_std:.6f} nm ({opt_std*355:.3f} RU)")
print(f"   Peak-to-Peak: {opt_p2p:.6f} nm ({opt_ru_p2p:.3f} RU)")
print(f"   RMS: {np.sqrt(np.mean((optimized_peaks - opt_mean)**2)):.6f} nm")

# ============================================================================
# Final Recommendations
# ============================================================================
print(f"\n{'='*80}")
print("OPTIMIZATION RESULTS & RECOMMENDATIONS")
print(f"{'='*80}")

print(f"\n📌 CURRENT SETTINGS:")
print(f"   FOURIER_ALPHA = 9000")
print(f"   Step 5 Window = 50")
print(f"   Step 6 Window = 50")
print(f"   SG Window = 11, Poly = 3")
print(f"   Performance: {current_p2p:.6f} nm ({current_ru_p2p:.3f} RU p2p)")

print(f"\n🎯 OPTIMIZED SETTINGS:")
print(f"   FOURIER_ALPHA = {best_alpha['alpha']}")
print(f"   Step 5 Window = {best_window['window']}")
print(f"   Step 6 Window = {best_window['window']}")
print(f"   SG Window = {best_sg['sg_window']}, Poly = {best_sg['sg_poly']}")
print(f"   Performance: {opt_p2p:.6f} nm ({opt_ru_p2p:.3f} RU p2p)")

improvement = ((current_ru_p2p - opt_ru_p2p) / current_ru_p2p * 100) if current_ru_p2p > opt_ru_p2p else 0
print(f"\n📈 Improvement: {improvement:.1f}% reduction in noise")

if opt_ru_p2p < 2.0:
    print(f"\n[OK] [OK] [OK] TARGET ACHIEVED! ({opt_ru_p2p:.3f} RU < 2 RU)")
else:
    print(f"\n[WARN]  Still above target: {opt_ru_p2p:.3f} RU (need {opt_ru_p2p-2:.3f} RU further improvement)")

print(f"\n💡 IMPLEMENTATION:")
print(f"Update in affilabs/settings/settings.py:")
print(f"  FOURIER_ALPHA = {best_alpha['alpha']}")
print(f"  FOURIER_WINDOW_SIZE = {best_window['window']}")
print(f"\nUpdate in data_acquisition_manager.py:")
print(f"  step5_window = {best_window['window']}")
print(f"  step6_window = {best_window['window']}")
print(f"  sg_window = {best_sg['sg_window']}")
print(f"  sg_poly = {best_sg['sg_poly']}")

print(f"\n{'='*80}")

# Save plot
plt.figure(figsize=(14, 8))

plt.subplot(2, 2, 1)
plt.plot(current_peaks - current_mean, 'b-', alpha=0.6, linewidth=0.5)
plt.axhline(y=current_p2p/2, color='r', linestyle='--', label=f'±{current_p2p/2:.6f} nm')
plt.axhline(y=-current_p2p/2, color='r', linestyle='--')
plt.axhline(y=0.006/2, color='g', linestyle=':', label='Target (±0.003 nm)')
plt.axhline(y=-0.006/2, color='g', linestyle=':')
plt.title(f'Current Settings: {current_ru_p2p:.3f} RU p2p')
plt.ylabel('Wavelength Deviation (nm)')
plt.xlabel('Sample Number')
plt.legend()
plt.grid(alpha=0.3)

plt.subplot(2, 2, 2)
plt.plot(optimized_peaks - opt_mean, 'b-', alpha=0.6, linewidth=0.5)
plt.axhline(y=opt_p2p/2, color='r', linestyle='--', label=f'±{opt_p2p/2:.6f} nm')
plt.axhline(y=-opt_p2p/2, color='r', linestyle='--')
plt.axhline(y=0.006/2, color='g', linestyle=':', label='Target (±0.003 nm)')
plt.axhline(y=-0.006/2, color='g', linestyle=':')
plt.title(f'Optimized Settings: {opt_ru_p2p:.3f} RU p2p')
plt.ylabel('Wavelength Deviation (nm)')
plt.xlabel('Sample Number')
plt.legend()
plt.grid(alpha=0.3)

plt.subplot(2, 2, 3)
alphas = [r['alpha'] for r in alpha_results]
p2ps = [r['p2p_ru'] for r in alpha_results]
plt.plot(alphas, p2ps, 'bo-')
plt.axhline(y=2.0, color='g', linestyle='--', label='2 RU Target')
plt.axvline(x=best_alpha['alpha'], color='r', linestyle=':', label=f"Best: {best_alpha['alpha']}")
plt.title('Alpha vs Noise')
plt.xlabel('FOURIER_ALPHA')
plt.ylabel('Peak-to-Peak Noise (RU)')
plt.legend()
plt.grid(alpha=0.3)

plt.subplot(2, 2, 4)
windows = [r['window'] for r in window_results]
p2ps_win = [r['p2p_ru'] for r in window_results]
plt.plot(windows, p2ps_win, 'go-')
plt.axhline(y=2.0, color='g', linestyle='--', label='2 RU Target')
plt.axvline(x=best_window['window'], color='r', linestyle=':', label=f"Best: {best_window['window']}")
plt.title('Window Size vs Noise')
plt.xlabel('Window Size (points)')
plt.ylabel('Peak-to-Peak Noise (RU)')
plt.legend()
plt.grid(alpha=0.3)

plt.tight_layout()
plt.savefig('baseline_optimization_results.png', dpi=150)
print(f"\n💾 Saved plot: baseline_optimization_results.png")
