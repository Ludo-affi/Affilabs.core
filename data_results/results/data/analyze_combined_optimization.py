"""Combined optimization: Fourier + Kalman Filter.

Tests the complete optimized pipeline:
1. Optimal Fourier parameters (α, SG window/poly, regression window/poly)
2. Adaptive Kalman filter on wavelength stream

Goal: Achieve maximum noise reduction while maintaining temporal resolution.
"""

import pandas as pd
import numpy as np
from scipy.signal import savgol_filter
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
print("COMBINED OPTIMIZATION: FOURIER + KALMAN")
print("=" * 80)
print(f"Dataset: {n_timepoints} timepoints, {len(wavelengths)} wavelengths\n")

def apply_fourier_method(transmission_spectrum, wavelengths, 
                         alpha=9000,
                         sg_window=11, sg_poly=3,
                         search_window=50, 
                         regression_window=50, 
                         regression_poly=1):
    """Fourier peak finding with all configurable parameters."""
    # SPR region
    spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
    spr_wavelengths = wavelengths[spr_mask]
    spr_transmission = transmission_spectrum[spr_mask]
    
    # SG filter
    spectrum = savgol_filter(spr_transmission, window_length=sg_window, polyorder=sg_poly)
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
    search_start = max(0, hint_index - search_window)
    search_end = min(len(derivative), hint_index + search_window)
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

def adaptive_kalman_filter(measurements, initial_process_var=1e-5):
    """Adaptive Kalman filter with automatic noise estimation."""
    n = len(measurements)
    x_est = np.zeros(n)
    P_est = np.zeros(n)
    
    x_est[0] = measurements[0]
    P_est[0] = 1.0
    
    Q = initial_process_var
    R = np.var(np.diff(measurements[:10]))  # Initial estimate
    
    residuals = []
    
    for k in range(1, n):
        # Prediction
        x_pred = x_est[k-1]
        P_pred = P_est[k-1] + Q
        
        # Update
        K = P_pred / (P_pred + R)
        innovation = measurements[k] - x_pred
        x_est[k] = x_pred + K * innovation
        P_est[k] = (1 - K) * P_pred
        
        # Adapt R every 10 samples
        residuals.append(innovation**2)
        if k > 10 and k % 10 == 0:
            R = np.mean(residuals[-10:])
    
    return x_est

def get_spr_series(alpha=9000, sg_window=11, sg_poly=3, 
                   regression_window=50, regression_poly=1, 
                   apply_kalman=False):
    """Get SPR time series with specified parameters."""
    wavelength_series = []
    
    for time_col in time_columns:
        transmission_spectrum = df[time_col].values
        try:
            wavelength = apply_fourier_method(
                transmission_spectrum, wavelengths,
                alpha=alpha,
                sg_window=sg_window,
                sg_poly=sg_poly,
                search_window=50,
                regression_window=regression_window,
                regression_poly=regression_poly
            )
            wavelength_series.append(wavelength)
        except:
            wavelength_series.append(np.nan)
    
    wavelength_series = np.array(wavelength_series)
    valid_mask = np.isfinite(wavelength_series)
    wavelength_series = wavelength_series[valid_mask]
    
    # Convert to RU
    spr_series = (wavelength_series - wavelength_series[0]) * 355
    
    # Apply Kalman filter if requested
    if apply_kalman:
        spr_series = adaptive_kalman_filter(spr_series)
    
    # Remove polynomial trend (detrend to center around 0)
    time_indices = np.arange(len(spr_series))
    poly_coeffs = np.polyfit(time_indices, spr_series, deg=2)  # Quadratic detrend
    poly_trend = np.polyval(poly_coeffs, time_indices)
    spr_detrended = spr_series - poly_trend
    
    return spr_detrended

# ============================================================================
# TEST CONFIGURATIONS
# ============================================================================
print("=" * 80)
print("TESTING OPTIMIZATION COMBINATIONS")
print("=" * 80)

configurations = []

# Config 1: Current baseline
spr = get_spr_series(alpha=9000, sg_window=11, sg_poly=3, 
                     regression_window=50, regression_poly=1, 
                     apply_kalman=False)
configurations.append({
    'name': 'Current Baseline',
    'alpha': 9000,
    'sg': '11/3',
    'regression': '50/Linear',
    'kalman': 'No',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Config 2: Optimal SG (11/5)
spr = get_spr_series(alpha=9000, sg_window=11, sg_poly=5, 
                     regression_window=50, regression_poly=1, 
                     apply_kalman=False)
configurations.append({
    'name': 'Optimal SG',
    'alpha': 9000,
    'sg': '11/5',
    'regression': '50/Linear',
    'kalman': 'No',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Config 3: Optimal Regression (100/Quadratic)
spr = get_spr_series(alpha=9000, sg_window=11, sg_poly=3, 
                     regression_window=100, regression_poly=2, 
                     apply_kalman=False)
configurations.append({
    'name': 'Optimal Regression',
    'alpha': 9000,
    'sg': '11/3',
    'regression': '100/Quadratic',
    'kalman': 'No',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Config 4: Optimal SG + Regression
spr = get_spr_series(alpha=9000, sg_window=11, sg_poly=5, 
                     regression_window=100, regression_poly=2, 
                     apply_kalman=False)
configurations.append({
    'name': 'SG + Regression',
    'alpha': 9000,
    'sg': '11/5',
    'regression': '100/Quadratic',
    'kalman': 'No',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Config 5: Kalman only (on baseline)
spr_baseline = get_spr_series(alpha=9000, sg_window=11, sg_poly=3, 
                              regression_window=50, regression_poly=1, 
                              apply_kalman=False)
spr = adaptive_kalman_filter(spr_baseline)
configurations.append({
    'name': 'Kalman Only',
    'alpha': 9000,
    'sg': '11/3',
    'regression': '50/Linear',
    'kalman': 'Yes',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Config 6: SG + Kalman
spr = get_spr_series(alpha=9000, sg_window=11, sg_poly=5, 
                     regression_window=50, regression_poly=1, 
                     apply_kalman=True)
configurations.append({
    'name': 'SG + Kalman',
    'alpha': 9000,
    'sg': '11/5',
    'regression': '50/Linear',
    'kalman': 'Yes',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Config 7: Regression + Kalman
spr = get_spr_series(alpha=9000, sg_window=11, sg_poly=3, 
                     regression_window=100, regression_poly=2, 
                     apply_kalman=True)
configurations.append({
    'name': 'Regression + Kalman',
    'alpha': 9000,
    'sg': '11/3',
    'regression': '100/Quadratic',
    'kalman': 'Yes',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Config 8: ALL OPTIMIZATIONS (SG + Regression + Kalman)
spr = get_spr_series(alpha=9000, sg_window=11, sg_poly=5, 
                     regression_window=100, regression_poly=2, 
                     apply_kalman=True)
configurations.append({
    'name': '⭐ ALL OPTIMIZATIONS ⭐',
    'alpha': 9000,
    'sg': '11/5',
    'regression': '100/Quadratic',
    'kalman': 'Yes',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Config 9: Alternative - Lower alpha + all optimizations
spr = get_spr_series(alpha=2000, sg_window=11, sg_poly=5, 
                     regression_window=100, regression_poly=2, 
                     apply_kalman=True)
configurations.append({
    'name': 'Alpha=2000 + All',
    'alpha': 2000,
    'sg': '11/5',
    'regression': '100/Quadratic',
    'kalman': 'Yes',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# ============================================================================
# RESULTS
# ============================================================================
print("\n" + "=" * 80)
print("RESULTS SUMMARY")
print("=" * 80)

results_df = pd.DataFrame(configurations)
results_df = results_df.sort_values('p2p')

print("\n📊 ALL CONFIGURATIONS (sorted by noise):\n")
for idx, row in results_df.iterrows():
    baseline_p2p = configurations[0]['p2p']
    improvement = (1 - row['p2p'] / baseline_p2p) * 100
    marker = "🏆" if idx == results_df.index[0] else "  "
    print(f"{marker} {row['name']:25s}: {row['p2p']:6.2f} RU  ({improvement:+5.1f}%)  "
          f"[SG:{row['sg']}, Reg:{row['regression']}, Kalman:{row['kalman']}]")

best = results_df.iloc[0]
baseline = configurations[0]

print("\n" + "=" * 80)
print("BEST CONFIGURATION")
print("=" * 80)
print(f"\n🎯 {best['name']}")
print(f"\n   Parameters:")
print(f"   • Fourier Alpha: {best['alpha']}")
print(f"   • SG Filter: Window={best['sg'].split('/')[0]}, Poly={best['sg'].split('/')[1]}")
print(f"   • Regression: Window={best['regression'].split('/')[0]}, Type={best['regression'].split('/')[1]}")
print(f"   • Kalman Filter: {best['kalman']}")
print(f"\n   Performance:")
print(f"   • Noise (p2p): {best['p2p']:.2f} RU  (was {baseline['p2p']:.2f} RU)")
print(f"   • Std Dev: {best['std']:.2f} RU  (was {baseline['std']:.2f} RU)")
print(f"   • Improvement: {(1 - best['p2p']/baseline['p2p'])*100:.1f}%")
print(f"   • Distance to 2 RU target: {best['p2p'] - 2:.2f} RU")

# ============================================================================
# ADDITIVE ANALYSIS
# ============================================================================
print("\n" + "=" * 80)
print("ADDITIVE CONTRIBUTION ANALYSIS")
print("=" * 80)

baseline_p2p = baseline['p2p']

# Find each individual contribution
sg_only = [c for c in configurations if c['name'] == 'Optimal SG'][0]
reg_only = [c for c in configurations if c['name'] == 'Optimal Regression'][0]
kalman_only = [c for c in configurations if c['name'] == 'Kalman Only'][0]

print(f"\nStarting Point: {baseline_p2p:.2f} RU")
print(f"\n  Step 1: Add SG optimization (11/5)")
print(f"          → {sg_only['p2p']:.2f} RU  ({(1-sg_only['p2p']/baseline_p2p)*100:+.1f}%)")
print(f"\n  Step 2: Add Regression optimization (100/Quadratic)")
print(f"          → {reg_only['p2p']:.2f} RU  ({(1-reg_only['p2p']/baseline_p2p)*100:+.1f}%)")
print(f"\n  Step 3: Add Kalman filter")
print(f"          → {kalman_only['p2p']:.2f} RU  ({(1-kalman_only['p2p']/baseline_p2p)*100:+.1f}%)")
print(f"\n  Combined: All three optimizations")
print(f"          → {best['p2p']:.2f} RU  ({(1-best['p2p']/baseline_p2p)*100:+.1f}%)")

# ============================================================================
# VISUALIZATIONS
# ============================================================================
fig, axes = plt.subplots(3, 2, figsize=(16, 14))

# Plot 1: Bar chart of all configurations
ax = axes[0, 0]
names = [c['name'][:20] for c in configurations]
p2p_values = [c['p2p'] for c in configurations]
colors = ['red' if i == 0 else 'green' if c['name'].startswith('⭐') else 'lightblue' 
          for i, c in enumerate(configurations)]
bars = ax.barh(names, p2p_values, color=colors)
ax.axvline(x=2, color='r', linestyle='--', label='Target (2 RU)', linewidth=2, alpha=0.7)
ax.set_xlabel('Peak-to-Peak Noise (RU)')
ax.set_title('All Configurations')
ax.legend()
ax.grid(True, alpha=0.3, axis='x')

# Plot 2: Improvement stacking
ax = axes[0, 1]
improvements = [
    ('Baseline', baseline_p2p),
    ('+ SG', sg_only['p2p']),
    ('+ Regression', reg_only['p2p']),
    ('+ Kalman', kalman_only['p2p']),
    ('All Combined', best['p2p'])
]
stages = [x[0] for x in improvements]
values = [x[1] for x in improvements]
colors_stack = ['red', 'orange', 'yellow', 'lightgreen', 'green']
bars = ax.bar(stages, values, color=colors_stack, edgecolor='black', linewidth=1.5)
ax.axhline(y=2, color='r', linestyle='--', label='Target (2 RU)', linewidth=2, alpha=0.7)
ax.set_ylabel('Peak-to-Peak Noise (RU)')
ax.set_title('Incremental Improvement Steps')
ax.legend()
ax.grid(True, alpha=0.3, axis='y')
plt.setp(ax.xaxis.get_majorticklabels(), rotation=15, ha='right')

# Annotate bars with values
for bar in bars:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
           f'{height:.2f}', ha='center', va='bottom', fontsize=10, fontweight='bold')

# Plot 3: Time series - Baseline vs Best
ax = axes[1, 0]
ax.plot(baseline['series'], alpha=0.5, label=f"Baseline: {baseline['p2p']:.2f} RU", 
        color='gray', linewidth=2)
ax.plot(best['series'], label=f"Optimized: {best['p2p']:.2f} RU", 
        color='green', linewidth=2)
ax.set_xlabel('Time Point')
ax.set_ylabel('SPR (RU)')
ax.set_title('Time Series: Baseline vs Optimized')
ax.legend()
ax.grid(True, alpha=0.3)

# Plot 4: Time series - Progressive improvements
ax = axes[1, 1]
ax.plot(baseline['series'], alpha=0.3, label=f"Baseline: {baseline['p2p']:.2f} RU", 
        color='red', linewidth=1)
ax.plot(sg_only['series'], alpha=0.5, label=f"+ SG: {sg_only['p2p']:.2f} RU", 
        color='orange', linewidth=1.5)
ax.plot(kalman_only['series'], alpha=0.7, label=f"+ Kalman: {kalman_only['p2p']:.2f} RU", 
        color='lightgreen', linewidth=2)
ax.plot(best['series'], label=f"All: {best['p2p']:.2f} RU", 
        color='darkgreen', linewidth=2.5)
ax.set_xlabel('Time Point')
ax.set_ylabel('SPR (RU)')
ax.set_title('Progressive Improvements')
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# Plot 5: Noise distribution histogram
ax = axes[2, 0]
ax.hist(baseline['series'] - np.mean(baseline['series']), bins=30, alpha=0.5, 
        label=f"Baseline (σ={baseline['std']:.2f})", color='red', edgecolor='black')
ax.hist(best['series'] - np.mean(best['series']), bins=30, alpha=0.5, 
        label=f"Optimized (σ={best['std']:.2f})", color='green', edgecolor='black')
ax.set_xlabel('Deviation from Mean (RU)')
ax.set_ylabel('Frequency')
ax.set_title('Noise Distribution')
ax.legend()
ax.grid(True, alpha=0.3, axis='y')

# Plot 6: Comparison matrix
ax = axes[2, 1]
comparison_data = []
labels = []
for i, config in enumerate(configurations):
    if config['name'] in ['Current Baseline', 'Optimal SG', 'Optimal Regression', 
                          'Kalman Only', '⭐ ALL OPTIMIZATIONS ⭐']:
        comparison_data.append([config['p2p'], config['std'], 
                               np.max(np.abs(np.diff(config['series'])))])
        labels.append(config['name'][:15])

comparison_data = np.array(comparison_data)
x = np.arange(len(labels))
width = 0.25

ax.bar(x - width, comparison_data[:, 0], width, label='P2P (RU)', color='steelblue')
ax.bar(x, comparison_data[:, 1], width, label='Std Dev (RU)', color='orange')
ax.bar(x + width, comparison_data[:, 2]/5, width, label='Max Rate (RU/s) / 5', color='green')

ax.set_ylabel('Value')
ax.set_title('Multi-Metric Comparison')
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=15, ha='right', fontsize=8)
ax.legend()
ax.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig('combined_optimization_results.png', dpi=150, bbox_inches='tight')
print("\n[OK] Plots saved to: combined_optimization_results.png")

print("\n" + "=" * 80)
