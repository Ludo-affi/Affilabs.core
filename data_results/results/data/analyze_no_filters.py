"""Baseline vs Optimized WITHOUT SG and Kalman filters.

Tests ONLY:
- Alpha parameter (9000 vs 2000)
- Regression window (50 vs 100)
- Regression polynomial (Linear vs Quadratic)

NO SG filtering, NO Kalman filtering.
"""

import pandas as pd
import numpy as np
from scipy.fftpack import dst, idct
from scipy.stats import linregress
import matplotlib.pyplot as plt

# Load baseline data
baseline_file = r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\ezControl-AI\baseline_data\baseline_recording_20251203_172554.xlsx"
df = pd.read_excel(baseline_file)

wavelengths = df['wavelength_nm'].values
time_columns = [col for col in df.columns if col.startswith('t_')]
n_timepoints = len(time_columns)

print("=" * 80)
print("BASELINE vs OPTIMIZED (NO SG, NO KALMAN)")
print("=" * 80)
print(f"Dataset: {n_timepoints} timepoints, {len(wavelengths)} wavelengths\n")

def apply_fourier_method(transmission_spectrum, wavelengths, 
                         alpha=9000,
                         regression_window=50, 
                         regression_poly=1):
    """Fourier peak finding WITHOUT SG filter."""
    # SPR region
    spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
    spr_wavelengths = wavelengths[spr_mask]
    spr_transmission = transmission_spectrum[spr_mask]
    
    # NO SG FILTER - use raw transmission
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
        # Linear regression
        line = linregress(x, y)
        peak_wavelength = -line.intercept / line.slope
    else:
        # Polynomial regression
        coeffs = np.polyfit(x, y, regression_poly)
        roots = np.roots(coeffs)
        real_roots = roots[np.isreal(roots)].real
        if len(real_roots) > 0:
            closest_root = real_roots[np.argmin(np.abs(real_roots - spr_wavelengths[zero]))]
            peak_wavelength = closest_root
        else:
            line = linregress(x, y)
            peak_wavelength = -line.intercept / line.slope
    
    return peak_wavelength

def get_spr_series(alpha=9000, regression_window=50, regression_poly=1):
    """Get SPR time series WITHOUT SG or Kalman."""
    wavelength_series = []
    
    for time_col in time_columns:
        transmission_spectrum = df[time_col].values
        try:
            wavelength = apply_fourier_method(
                transmission_spectrum, wavelengths,
                alpha=alpha,
                regression_window=regression_window,
                regression_poly=regression_poly
            )
            wavelength_series.append(wavelength)
        except:
            wavelength_series.append(np.nan)
    
    wavelength_series = np.array(wavelength_series)
    valid_mask = np.isfinite(wavelength_series)
    wavelength_series = wavelength_series[valid_mask]
    
    # Convert to RU (zero at first point)
    spr_series = (wavelength_series - wavelength_series[0]) * 355
    
    # Remove polynomial trend (detrend to center around 0)
    time_indices = np.arange(len(spr_series))
    poly_coeffs = np.polyfit(time_indices, spr_series, deg=2)  # Quadratic detrend
    poly_trend = np.polyval(poly_coeffs, time_indices)
    spr_detrended = spr_series - poly_trend
    
    return spr_detrended

# ============================================================================
# TEST CONFIGURATIONS (NO SG, NO KALMAN)
# ============================================================================
print("Testing configurations (NO SG filter, NO Kalman filter)...")

configurations = []

# Config 1: Current baseline (alpha=9000, window=50, linear)
spr = get_spr_series(alpha=9000, regression_window=50, regression_poly=1)
configurations.append({
    'name': 'Baseline',
    'alpha': 9000,
    'window': 50,
    'poly': 'Linear',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'mean': np.mean(spr),
    'series': spr
})

# Config 2: Optimal alpha only
spr = get_spr_series(alpha=2000, regression_window=50, regression_poly=1)
configurations.append({
    'name': 'Alpha=2000',
    'alpha': 2000,
    'window': 50,
    'poly': 'Linear',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'mean': np.mean(spr),
    'series': spr
})

# Config 3: Optimal regression only
spr = get_spr_series(alpha=9000, regression_window=100, regression_poly=2)
configurations.append({
    'name': 'Regression (100/Quad)',
    'alpha': 9000,
    'window': 100,
    'poly': 'Quadratic',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'mean': np.mean(spr),
    'series': spr
})

# Config 4: Both optimizations (alpha + regression)
spr = get_spr_series(alpha=2000, regression_window=100, regression_poly=2)
configurations.append({
    'name': 'Optimized (Both)',
    'alpha': 2000,
    'window': 100,
    'poly': 'Quadratic',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'mean': np.mean(spr),
    'series': spr
})

# ============================================================================
# RESULTS
# ============================================================================
print("\n" + "=" * 80)
print("RESULTS (NO SG, NO KALMAN)")
print("=" * 80)

baseline = configurations[0]
optimized = configurations[3]

print("\n📊 ALL CONFIGURATIONS:\n")
for config in configurations:
    improvement = (1 - config['p2p'] / baseline['p2p']) * 100
    marker = "⭐" if config['name'] == 'Optimized (Both)' else "  "
    print(f"{marker} {config['name']:20s}: p2p={config['p2p']:6.2f} RU, std={config['std']:5.2f} RU, mean={config['mean']:+6.2f} RU  ({improvement:+5.1f}%)")

print("\n" + "=" * 80)
print("COMPARISON: BASELINE vs OPTIMIZED")
print("=" * 80)

print(f"\n📈 BASELINE (α=9000, Window=50, Linear):")
print(f"   Noise (p2p): {baseline['p2p']:.2f} RU")
print(f"   Std Dev:     {baseline['std']:.2f} RU")
print(f"   Mean:        {baseline['mean']:+.2f} RU")

print(f"\n✨ OPTIMIZED (α=2000, Window=100, Quadratic):")
print(f"   Noise (p2p): {optimized['p2p']:.2f} RU")
print(f"   Std Dev:     {optimized['std']:.2f} RU")
print(f"   Mean:        {optimized['mean']:+.2f} RU")

print(f"\n🎯 IMPROVEMENT:")
print(f"   Noise:    {baseline['p2p']:.2f} → {optimized['p2p']:.2f} RU  ({(1-optimized['p2p']/baseline['p2p'])*100:.1f}%)")
print(f"   Std Dev:  {baseline['std']:.2f} → {optimized['std']:.2f} RU  ({(1-optimized['std']/baseline['std'])*100:.1f}%)")
print(f"   DC shift: {optimized['mean'] - baseline['mean']:+.2f} RU")

# ============================================================================
# VISUALIZATION
# ============================================================================
fig = plt.figure(figsize=(18, 12))
gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.3)

# Plot 1: Main overlay (large)
ax1 = fig.add_subplot(gs[0:2, :])
time_points = np.arange(len(baseline['series']))
ax1.plot(time_points, baseline['series'], alpha=0.6, 
         label=f"Baseline (p2p={baseline['p2p']:.2f} RU)", 
         color='red', linewidth=2.5)
ax1.plot(time_points, optimized['series'], alpha=0.8,
         label=f"Optimized (p2p={optimized['p2p']:.2f} RU)", 
         color='green', linewidth=2.5)

# Add standard deviation bands
ax1.fill_between(time_points, 
                 baseline['series'] - baseline['std'], 
                 baseline['series'] + baseline['std'],
                 alpha=0.2, color='red', label=f'±1σ Baseline ({baseline["std"]:.2f} RU)')
ax1.fill_between(time_points, 
                 optimized['series'] - optimized['std'], 
                 optimized['series'] + optimized['std'],
                 alpha=0.3, color='green', label=f'±1σ Optimized ({optimized["std"]:.2f} RU)')

ax1.axhline(y=baseline['mean'], color='red', linestyle='--', alpha=0.4, linewidth=1.5)
ax1.axhline(y=optimized['mean'], color='green', linestyle='--', alpha=0.4, linewidth=1.5)
ax1.set_xlabel('Time Point (1 Hz sampling)', fontsize=13, fontweight='bold')
ax1.set_ylabel('SPR Signal (RU)', fontsize=13, fontweight='bold')
ax1.set_title('BASELINE vs OPTIMIZED (NO SG, NO Kalman) - Detrended Overlay', 
             fontsize=16, fontweight='bold', pad=20)
ax1.legend(fontsize=11, loc='upper right', framealpha=0.95)
ax1.grid(True, alpha=0.3)

# Add improvement annotation
improvement = (1 - optimized['p2p']/baseline['p2p']) * 100
ax1.text(0.02, 0.98, 
         f'Improvement: {improvement:.1f}%\n'
         f'{baseline["p2p"]:.2f} → {optimized["p2p"]:.2f} RU\n'
         f'Alpha: {baseline["alpha"]} → {optimized["alpha"]}\n'
         f'Regression: {baseline["window"]}/{baseline["poly"]} → {optimized["window"]}/{optimized["poly"]}',
         transform=ax1.transAxes, fontsize=11, verticalalignment='top',
         bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.9, pad=0.8))

# Plot 2: Zoomed view (first 50 points)
ax2 = fig.add_subplot(gs[2, 0])
zoom_range = slice(0, 50)
ax2.plot(time_points[zoom_range], baseline['series'][zoom_range], 
         'o-', alpha=0.7, label='Baseline', color='red', markersize=5, linewidth=1.5)
ax2.plot(time_points[zoom_range], optimized['series'][zoom_range], 
         's-', alpha=0.8, label='Optimized', color='green', markersize=5, linewidth=1.5)
ax2.set_xlabel('Time Point', fontweight='bold')
ax2.set_ylabel('SPR (RU)', fontweight='bold')
ax2.set_title('Zoomed: First 50 Points', fontweight='bold')
ax2.legend(fontsize=9)
ax2.grid(True, alpha=0.3)

# Plot 3: Histogram comparison
ax3 = fig.add_subplot(gs[2, 1])
ax3.hist(baseline['series'] - baseline['mean'], bins=30, alpha=0.5, 
         label=f"Baseline (σ={baseline['std']:.2f})", 
         color='red', edgecolor='darkred', linewidth=1.2)
ax3.hist(optimized['series'] - optimized['mean'], bins=30, alpha=0.6, 
         label=f"Optimized (σ={optimized['std']:.2f})", 
         color='green', edgecolor='darkgreen', linewidth=1.2)
ax3.set_xlabel('Deviation from Mean (RU)', fontweight='bold')
ax3.set_ylabel('Frequency', fontweight='bold')
ax3.set_title('Noise Distribution', fontweight='bold')
ax3.legend(fontsize=9)
ax3.grid(True, alpha=0.3, axis='y')

# Plot 4: Bar chart comparison
ax4 = fig.add_subplot(gs[2, 2])
metrics = ['P2P\nNoise', 'Std\nDev', 'Max\nRate']
baseline_metrics = [
    baseline['p2p'], 
    baseline['std'],
    np.max(np.abs(np.diff(baseline['series'])))
]
optimized_metrics = [
    optimized['p2p'],
    optimized['std'],
    np.max(np.abs(np.diff(optimized['series'])))
]

x = np.arange(len(metrics))
width = 0.35

bars1 = ax4.bar(x - width/2, baseline_metrics, width, label='Baseline', 
                color='red', alpha=0.7, edgecolor='darkred', linewidth=1.5)
bars2 = ax4.bar(x + width/2, optimized_metrics, width, label='Optimized', 
                color='green', alpha=0.7, edgecolor='darkgreen', linewidth=1.5)

ax4.set_ylabel('Value (RU or RU/s)', fontweight='bold')
ax4.set_title('Metrics Comparison', fontweight='bold')
ax4.set_xticks(x)
ax4.set_xticklabels(metrics, fontsize=10)
ax4.legend(fontsize=9)
ax4.grid(True, alpha=0.3, axis='y')

# Annotate bars with values
for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}', ha='center', va='bottom', fontsize=8, fontweight='bold')

plt.savefig('baseline_vs_optimized_no_filters.png', dpi=150, bbox_inches='tight')
print("\n[OK] Plot saved to: baseline_vs_optimized_no_filters.png")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

print("\n[OK] TESTED (NO SG, NO KALMAN):")
print("   • Alpha optimization: 9000 → 2000")
print("   • Regression window: 50 → 100")
print("   • Regression polynomial: Linear → Quadratic")

print(f"\n📊 RESULTS:")
print(f"   • Noise reduction: {improvement:.1f}%")
print(f"   • Final noise: {optimized['p2p']:.2f} RU")
print(f"   • DC shift: {optimized['mean'] - baseline['mean']:+.2f} RU")

print(f"\n[SEARCH] INDIVIDUAL CONTRIBUTIONS:")
alpha_only = [c for c in configurations if c['name'] == 'Alpha=2000'][0]
reg_only = [c for c in configurations if c['name'] == 'Regression (100/Quad)'][0]
print(f"   • Alpha=2000 alone:       {(1-alpha_only['p2p']/baseline['p2p'])*100:+.1f}%  ({alpha_only['p2p']:.2f} RU)")
print(f"   • Regression alone:       {(1-reg_only['p2p']/baseline['p2p'])*100:+.1f}%  ({reg_only['p2p']:.2f} RU)")
print(f"   • Both combined:          {(1-optimized['p2p']/baseline['p2p'])*100:+.1f}%  ({optimized['p2p']:.2f} RU)")

print("\n" + "=" * 80)
