"""Analyze DC bias/offset in Hybrid Fourier + Multi-Feature method.

Check if the hybrid method introduces DC shift compared to baseline.
"""

import pandas as pd
import numpy as np
from scipy.signal import savgol_filter
from scipy.fftpack import dst, idct
from scipy.stats import linregress
from scipy.ndimage import gaussian_filter1d
import matplotlib.pyplot as plt

# Load baseline data
baseline_file = r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\ezControl-AI\baseline_data\baseline_recording_20251203_172554.xlsx"
df = pd.read_excel(baseline_file)

wavelengths = df['wavelength_nm'].values
time_columns = [col for col in df.columns if col.startswith('t_')]
n_timepoints = len(time_columns)

print("=" * 80)
print("DC BIAS ANALYSIS: HYBRID FOURIER + MULTI-FEATURE")
print("=" * 80)
print(f"Dataset: {n_timepoints} timepoints\n")

def get_current_production():
    """Current production method (baseline for comparison)."""
    wavelength_series = []
    
    for time_col in time_columns:
        transmission_spectrum = df[time_col].values
        try:
            spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
            spr_wavelengths = wavelengths[spr_mask]
            spr_transmission = transmission_spectrum[spr_mask]
            
            spectrum = savgol_filter(spr_transmission, window_length=11, polyorder=3)
            hint_index = np.argmin(spectrum)
            
            n = len(spectrum)
            n_inner = n - 1
            phi = np.pi / n_inner * np.arange(1, n_inner)
            phi2 = phi**2
            fourier_weights = phi / (1 + 9000 * phi2 * (1 + phi2))
            
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
            
            start = max(zero - 50, 0)
            end = min(zero + 50, n - 1)
            
            x = spr_wavelengths[start:end]
            y = derivative[start:end]
            
            line = linregress(x, y)
            peak_wavelength = -line.intercept / line.slope
            
            wavelength_series.append(peak_wavelength)
        except:
            wavelength_series.append(np.nan)
    
    wavelength_series = np.array(wavelength_series)
    valid_mask = np.isfinite(wavelength_series)
    wavelength_series = wavelength_series[valid_mask]
    
    spr_series = (wavelength_series - wavelength_series[0]) * 355
    return spr_series

def get_hybrid_full():
    """Hybrid Fourier + Multi-Feature (Full)."""
    wavelength_series = []
    
    for time_col in time_columns:
        transmission_spectrum = df[time_col].values
        try:
            spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
            spr_wavelengths = wavelengths[spr_mask]
            spr_transmission = transmission_spectrum[spr_mask]
            
            # Multi-feature filtering
            spectrum = savgol_filter(spr_transmission, window_length=11, polyorder=5)
            spectrum = gaussian_filter1d(spectrum, sigma=1.5)
            
            # Fourier derivative
            hint_index = np.argmin(spectrum)
            n = len(spectrum)
            n_inner = n - 1
            phi = np.pi / n_inner * np.arange(1, n_inner)
            phi2 = phi**2
            fourier_weights = phi / (1 + 2000 * phi2 * (1 + phi2))
            
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
            
            # Quadratic regression
            start = max(zero - 100, 0)
            end = min(zero + 100, n - 1)
            
            x = spr_wavelengths[start:end]
            y = derivative[start:end]
            
            coeffs = np.polyfit(x, y, 2)
            roots = np.roots(coeffs)
            real_roots = roots[np.isreal(roots)].real
            
            if len(real_roots) > 0:
                closest_root = real_roots[np.argmin(np.abs(real_roots - spr_wavelengths[zero]))]
                peak_wavelength = closest_root
            else:
                line = linregress(x, y)
                peak_wavelength = -line.intercept / line.slope
            
            # Gaussian refinement
            try:
                from scipy.optimize import curve_fit
                
                def peak_model(x, x0, A, sigma, baseline):
                    return baseline - A * np.exp(-((x - x0) / sigma) ** 2)
                
                baseline_val = np.max(spectrum)
                amplitude = baseline_val - np.min(spectrum)
                
                p0 = [peak_wavelength, amplitude, 20.0, baseline_val]
                bounds = (
                    [spr_wavelengths[0], 0, 5, 0],
                    [spr_wavelengths[-1], 100, 80, 100]
                )
                
                popt, _ = curve_fit(peak_model, spr_wavelengths, spectrum, p0=p0, 
                                   bounds=bounds, maxfev=2000)
                gaussian_peak = popt[0]
                
                if abs(gaussian_peak - peak_wavelength) < 2.0:
                    peak_wavelength = 0.9 * peak_wavelength + 0.1 * gaussian_peak
            except:
                pass
            
            wavelength_series.append(peak_wavelength)
        except:
            wavelength_series.append(np.nan)
    
    wavelength_series = np.array(wavelength_series)
    valid_mask = np.isfinite(wavelength_series)
    wavelength_series = wavelength_series[valid_mask]
    
    spr_series = (wavelength_series - wavelength_series[0]) * 355
    return spr_series

# Get both series (RAW, no detrending to see DC bias)
current = get_current_production()
hybrid = get_hybrid_full()

# Calculate statistics
print("\n📊 DC BIAS ANALYSIS (Raw signals, no detrending):\n")
print(f"Current Production:")
print(f"  Mean: {np.mean(current):+.2f} RU")
print(f"  P2P:  {np.ptp(current):.2f} RU")
print(f"  Std:  {np.std(current):.2f} RU")

print(f"\nHybrid Fourier+Multi:")
print(f"  Mean: {np.mean(hybrid):+.2f} RU")
print(f"  P2P:  {np.ptp(hybrid):.2f} RU")
print(f"  Std:  {np.std(hybrid):.2f} RU")

dc_offset = np.mean(hybrid) - np.mean(current)
print(f"\n[SEARCH] DC OFFSET:")
print(f"  Hybrid - Current = {dc_offset:+.2f} RU")

if abs(dc_offset) < 1.0:
    print(f"  [OK] MINIMAL DC BIAS (< 1 RU)")
elif abs(dc_offset) < 3.0:
    print(f"  [WARN]  MODERATE DC BIAS (1-3 RU)")
else:
    print(f"  [ERROR] SIGNIFICANT DC BIAS (> 3 RU)")

print(f"\n  Interpretation: {'Cosmetic only, does not affect noise measurement' if abs(dc_offset) < 5.0 else 'May affect absolute RU values'}")

# Visualization
fig, axes = plt.subplots(2, 2, figsize=(15, 10))

# Plot 1: Raw traces
time_points = np.arange(len(current))
axes[0, 0].plot(time_points, current, label='Current Production', alpha=0.7, linewidth=2)
axes[0, 0].plot(time_points, hybrid, label='Hybrid Fourier+Multi', alpha=0.7, linewidth=2)
axes[0, 0].axhline(y=0, color='black', linestyle=':', linewidth=1)
axes[0, 0].axhline(y=np.mean(current), color='blue', linestyle='--', linewidth=1, alpha=0.5, label=f'Current Mean ({np.mean(current):.2f})')
axes[0, 0].axhline(y=np.mean(hybrid), color='orange', linestyle='--', linewidth=1, alpha=0.5, label=f'Hybrid Mean ({np.mean(hybrid):.2f})')
axes[0, 0].set_xlabel('Time Point', fontweight='bold')
axes[0, 0].set_ylabel('SPR Signal (RU, raw)', fontweight='bold')
axes[0, 0].set_title('Raw Signals - DC Bias Check', fontweight='bold', fontsize=14)
axes[0, 0].legend(fontsize=9)
axes[0, 0].grid(True, alpha=0.3)

# Plot 2: Difference (Hybrid - Current)
difference = hybrid - current
axes[0, 1].plot(time_points, difference, color='green', linewidth=2)
axes[0, 1].axhline(y=0, color='black', linestyle='-', linewidth=2)
axes[0, 1].axhline(y=np.mean(difference), color='red', linestyle='--', linewidth=2, 
                   label=f'Mean Difference = {np.mean(difference):+.2f} RU')
axes[0, 1].fill_between(time_points, difference, 0, alpha=0.3, color='green')
axes[0, 1].set_xlabel('Time Point', fontweight='bold')
axes[0, 1].set_ylabel('Difference (RU)', fontweight='bold')
axes[0, 1].set_title(f'Hybrid - Current (DC Offset = {dc_offset:+.2f} RU)', fontweight='bold', fontsize=14)
axes[0, 1].legend(fontsize=10)
axes[0, 1].grid(True, alpha=0.3)

# Plot 3: Histograms
axes[1, 0].hist(current, bins=30, alpha=0.5, label=f'Current (μ={np.mean(current):.2f})', color='blue', edgecolor='darkblue')
axes[1, 0].hist(hybrid, bins=30, alpha=0.5, label=f'Hybrid (μ={np.mean(hybrid):.2f})', color='orange', edgecolor='darkorange')
axes[1, 0].axvline(x=0, color='black', linestyle=':', linewidth=2)
axes[1, 0].axvline(x=np.mean(current), color='blue', linestyle='--', linewidth=2, alpha=0.7)
axes[1, 0].axvline(x=np.mean(hybrid), color='orange', linestyle='--', linewidth=2, alpha=0.7)
axes[1, 0].set_xlabel('SPR Value (RU)', fontweight='bold')
axes[1, 0].set_ylabel('Frequency', fontweight='bold')
axes[1, 0].set_title('Distribution Comparison', fontweight='bold', fontsize=14)
axes[1, 0].legend(fontsize=10)
axes[1, 0].grid(True, alpha=0.3, axis='y')

# Plot 4: Centered comparison (remove mean to see noise only)
current_centered = current - np.mean(current)
hybrid_centered = hybrid - np.mean(hybrid)
axes[1, 1].plot(time_points, current_centered, label=f'Current (σ={np.std(current):.2f})', alpha=0.7, linewidth=2)
axes[1, 1].plot(time_points, hybrid_centered, label=f'Hybrid (σ={np.std(hybrid):.2f})', alpha=0.7, linewidth=2)
axes[1, 1].axhline(y=0, color='black', linestyle='-', linewidth=1)
axes[1, 1].set_xlabel('Time Point', fontweight='bold')
axes[1, 1].set_ylabel('Centered Signal (RU)', fontweight='bold')
axes[1, 1].set_title('Centered Signals (DC Removed)', fontweight='bold', fontsize=14)
axes[1, 1].legend(fontsize=10)
axes[1, 1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('hybrid_dc_bias_analysis.png', dpi=150, bbox_inches='tight')
print("\n[OK] Plot saved to: hybrid_dc_bias_analysis.png")

# Additional analysis: Does DC bias change over time?
print("\n" + "=" * 80)
print("TIME-DEPENDENT DC ANALYSIS")
print("=" * 80)

# Split into thirds
n_third = len(time_points) // 3
first_third = slice(0, n_third)
second_third = slice(n_third, 2*n_third)
third_third = slice(2*n_third, None)

for i, (name, s) in enumerate([("First third", first_third), 
                                 ("Second third", second_third), 
                                 ("Final third", third_third)]):
    offset = np.mean(hybrid[s]) - np.mean(current[s])
    print(f"{name:15s}: DC offset = {offset:+.2f} RU")

print("\n" + "=" * 80)
