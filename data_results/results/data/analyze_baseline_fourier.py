"""
Analyze Baseline Recording to Optimize Fourier Peak Finding Parameters

This script analyzes a 5-minute baseline recording to identify the best
Fourier parameters to achieve <2 RU peak-to-peak noise.

Parameters to optimize:
1. FOURIER_ALPHA - Smoothing strength (currently 9000)
2. Window sizes - Step 5 & 6 search windows (currently 50)
3. SG filter - Window size and polynomial order (currently 11, 3)
4. SNR weighting strength (currently 0.3)

Target: <2 RU peak-to-peak variation (0.006 nm @ 355 RU/nm)
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

# Read Excel file
df = pd.read_excel(file_path)
print(f"\n[OK] Loaded baseline data")
print(f"   Shape: {df.shape} (wavelengths × time samples)")
print(f"   Wavelength range: {df['wavelength_nm'].min():.1f} - {df['wavelength_nm'].max():.1f} nm")

# Get time columns (all columns except 'wavelength_nm')
time_columns = [col for col in df.columns if col.startswith('t_')]
num_samples = len(time_columns)
print(f"   Time samples: {num_samples} (~{num_samples} seconds @ 1 Hz)")

# Extract wavelength array
wavelengths = df['wavelength_nm'].values

# Extract transmission spectra for each time point
transmission_spectra = df[time_columns].values  # Shape: (n_wavelengths, n_timepoints)
print(f"   Data shape: {transmission_spectra.shape}")

# Analyze each spectrum to find peak wavelengths
print(f"\n📊 Analyzing {num_samples} transmission spectra...")

# Store peak wavelengths for each timepoint
peak_wavelengths_all = []

# ============================================================================
# Fourier Peak Finding Function (From data_acquisition_manager.py)
# ============================================================================
def fourier_peak_finding(transmission_spectrum, alpha=9000, step5_window=50, 
                        step6_window=50, sg_window=11, sg_poly=3,
                        snr_weight_strength=0.3, apply_sg=True):
    """
    Replicate the Fourier peak finding algorithm from data_acquisition_manager.py
    
    Returns: peak position index in spectrum
    """
    # Apply SG filter if enabled
    if apply_sg and len(transmission_spectrum) >= sg_window:
        spectrum = savgol_filter(transmission_spectrum, sg_window, sg_poly)
    else:
        spectrum = transmission_spectrum.copy()
    
    # Find minimum hint
    hint_index = np.argmin(spectrum)
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 3: Calculate Fourier coefficients with denoising weights
    # ═══════════════════════════════════════════════════════════════
    n = len(spectrum)
    n_inner = n - 1
    
    # Fourier denoising weights
    phi = np.pi / n_inner * np.arange(1, n_inner)
    phi2 = phi**2
    fourier_weights = phi / (1 + alpha * phi2 * (1 + phi2))
    
    # Calculate Fourier coefficients
    fourier_coeff = np.zeros_like(spectrum)
    fourier_coeff[0] = 2 * (spectrum[-1] - spectrum[0])
    
    # Apply DST with linear detrending
    detrended = spectrum[1:-1] - np.linspace(spectrum[0], spectrum[-1], n)[1:-1]
    fourier_coeff[1:-1] = fourier_weights * dst(detrended, 1)
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 4: Calculate derivative using IDCT
    # ═══════════════════════════════════════════════════════════════
    derivative = idct(fourier_coeff, 1)
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 5: Find zero-crossing near minimum hint
    # ═══════════════════════════════════════════════════════════════
    search_start = max(0, hint_index - step5_window)
    search_end = min(len(derivative), hint_index + step5_window)
    
    derivative_window = derivative[search_start:search_end]
    zero_local = derivative_window.searchsorted(0)
    zero = search_start + zero_local
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 6: Refine position using linear regression
    # ═══════════════════════════════════════════════════════════════
    start = max(zero - step6_window, 0)
    end = min(zero + step6_window, n - 1)
    
    x_vals = np.arange(start, end)
    y_vals = derivative[start:end]
    
    if len(x_vals) > 2:
        line = linregress(x_vals, y_vals)
        peak_index = -line.intercept / line.slope
    else:
        peak_index = zero
    
    return peak_index, derivative, hint_index, zero

# ============================================================================
# Test Different Parameter Combinations
# ============================================================================
print("\n" + "="*80)
print("TESTING FOURIER PARAMETER COMBINATIONS")
print("="*80)

# Parameter ranges to test
alpha_values = [5000, 7000, 9000, 11000, 13000, 15000]
window_values = [30, 40, 50, 75, 100]
sg_window_values = [7, 9, 11, 13, 15]
sg_poly_values = [2, 3, 4]
snr_strengths = [0.0, 0.1, 0.2, 0.3, 0.5]

# Store results for each channel
results = {ch: [] for ch in channels}

# Test on Channel A first (then apply best to others)
test_channel = 'A'
transmission_samples = channel_data[test_channel]

print(f"\nOptimizing on Channel {test_channel} ({len(transmission_samples)} samples)")
print(f"Current performance baseline needed...")

# Run current settings first
current_peaks = []
for trans in transmission_samples:
    peak_idx, _, _, _ = fourier_peak_finding(
        np.full(300, trans),  # Simulate spectrum
        alpha=9000, step5_window=50, step6_window=50,
        sg_window=11, sg_poly=3, apply_sg=True
    )
    current_peaks.append(peak_idx)

current_peaks = np.array(current_peaks)
current_std = np.std(current_peaks)
current_p2p = np.ptp(current_peaks)

print(f"\n📊 CURRENT SETTINGS (alpha=9000, windows=50, SG=11/3):")
print(f"   Std Dev: {current_std:.3f} indices")
print(f"   Peak-to-Peak: {current_p2p:.3f} indices")
print(f"   RMS: {np.sqrt(np.mean(current_peaks**2)):.3f}")

# ============================================================================
# Optimize Alpha (most impactful parameter)
# ============================================================================
print(f"\n{'='*80}")
print("1. OPTIMIZING ALPHA (Smoothing Strength)")
print(f"{'='*80}")

alpha_results = []
for alpha in alpha_values:
    peaks = []
    for trans in transmission_samples:
        peak_idx, _, _, _ = fourier_peak_finding(
            np.full(300, trans),
            alpha=alpha, step5_window=50, step6_window=50,
            sg_window=11, sg_poly=3, apply_sg=True
        )
        peaks.append(peak_idx)
    
    peaks = np.array(peaks)
    std = np.std(peaks)
    p2p = np.ptp(peaks)
    
    alpha_results.append({
        'alpha': alpha,
        'std': std,
        'p2p': p2p,
        'peaks': peaks
    })
    
    print(f"   Alpha={alpha:>6}: std={std:.4f}, p2p={p2p:.4f}")

# Find best alpha
best_alpha = min(alpha_results, key=lambda x: x['p2p'])
print(f"\n[OK] Best Alpha: {best_alpha['alpha']} (p2p={best_alpha['p2p']:.4f})")

# ============================================================================
# Optimize Window Sizes with Best Alpha
# ============================================================================
print(f"\n{'='*80}")
print("2. OPTIMIZING WINDOW SIZES (Step 5 & 6)")
print(f"{'='*80}")

window_results = []
for window in window_values:
    peaks = []
    for trans in transmission_samples:
        peak_idx, _, _, _ = fourier_peak_finding(
            np.full(300, trans),
            alpha=best_alpha['alpha'], 
            step5_window=window, 
            step6_window=window,
            sg_window=11, sg_poly=3, apply_sg=True
        )
        peaks.append(peak_idx)
    
    peaks = np.array(peaks)
    std = np.std(peaks)
    p2p = np.ptp(peaks)
    
    window_results.append({
        'window': window,
        'std': std,
        'p2p': p2p
    })
    
    print(f"   Window={window:>3}: std={std:.4f}, p2p={p2p:.4f}")

best_window = min(window_results, key=lambda x: x['p2p'])
print(f"\n[OK] Best Window: {best_window['window']} (p2p={best_window['p2p']:.4f})")

# ============================================================================
# Optimize SG Filter Parameters
# ============================================================================
print(f"\n{'='*80}")
print("3. OPTIMIZING SG FILTER (Window Size & Polynomial Order)")
print(f"{'='*80}")

sg_results = []
for sg_win in sg_window_values:
    for sg_poly in sg_poly_values:
        if sg_poly >= sg_win:
            continue  # Invalid combination
        
        try:
            peaks = []
            for trans in transmission_samples:
                peak_idx, _, _, _ = fourier_peak_finding(
                    np.full(300, trans),
                    alpha=best_alpha['alpha'],
                    step5_window=best_window['window'],
                    step6_window=best_window['window'],
                    sg_window=sg_win, sg_poly=sg_poly, apply_sg=True
                )
                peaks.append(peak_idx)
            
            peaks = np.array(peaks)
            std = np.std(peaks)
            p2p = np.ptp(peaks)
            
            sg_results.append({
                'sg_window': sg_win,
                'sg_poly': sg_poly,
                'std': std,
                'p2p': p2p
            })
            
            print(f"   SG Window={sg_win:>2}, Poly={sg_poly}: std={std:.4f}, p2p={p2p:.4f}")
        except:
            pass

best_sg = min(sg_results, key=lambda x: x['p2p'])
print(f"\n[OK] Best SG: window={best_sg['sg_window']}, poly={best_sg['sg_poly']} (p2p={best_sg['p2p']:.4f})")

# ============================================================================
# Final Recommendations
# ============================================================================
print(f"\n{'='*80}")
print("FINAL OPTIMIZATION RECOMMENDATIONS")
print(f"{'='*80}")

print(f"\n📌 CURRENT SETTINGS:")
print(f"   FOURIER_ALPHA = 9000")
print(f"   Step 5 Window = 50")
print(f"   Step 6 Window = 50")
print(f"   SG Window = 11, Poly = 3")
print(f"   Performance: {current_p2p:.4f} indices p2p")

print(f"\n🎯 OPTIMIZED SETTINGS:")
print(f"   FOURIER_ALPHA = {best_alpha['alpha']}")
print(f"   Step 5 Window = {best_window['window']}")
print(f"   Step 6 Window = {best_window['window']}")
print(f"   SG Window = {best_sg['sg_window']}, Poly = {best_sg['sg_poly']}")
print(f"   Expected Performance: {best_sg['p2p']:.4f} indices p2p")

improvement = ((current_p2p - best_sg['p2p']) / current_p2p * 100)
print(f"\n📈 Improvement: {improvement:.1f}% reduction in noise")

# Convert to RU (assuming 355 RU/nm and wavelength calibration)
# Need actual wavelength spacing to convert indices to nm
print(f"\n💡 NEXT STEPS:")
print(f"1. Update settings.py with optimized values")
print(f"2. Test on all 4 channels to verify consistency")
print(f"3. Run 5-minute baseline with new settings")
print(f"4. Target: <2 RU peak-to-peak (0.006 nm)")

print(f"\n{'='*80}")
