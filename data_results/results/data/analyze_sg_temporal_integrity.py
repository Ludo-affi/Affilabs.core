"""Test SG filter parameters for noise reduction while preserving temporal integrity.

Tests various SG window sizes and polynomial orders to find the sweet spot where:
1. Noise is minimized (lower p2p)
2. Temporal response is preserved (no lag or distortion)
3. Sharp transitions are not over-smoothed

Key Insight:
- Window size controls smoothing strength (bigger = more smoothing)
- Polynomial order controls edge/peak preservation (higher = better preservation)
- For temporal data, we want minimum phase lag and group delay distortion
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

print("=" * 80)
print("SG FILTER TEMPORAL INTEGRITY ANALYSIS")
print("=" * 80)

# Data structure: wavelength_nm column + t_0000, t_0001, ... columns
wavelengths = df['wavelength_nm'].values
time_columns = [col for col in df.columns if col.startswith('t_')]
n_timepoints = len(time_columns)

print(f"Dataset: {n_timepoints} timepoints, {len(wavelengths)} wavelengths")
print(f"Wavelength range: {wavelengths.min():.1f} - {wavelengths.max():.1f} nm")
print()

# Get SPR region wavelengths (620-680nm)
spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
spr_wavelengths = wavelengths[spr_mask]
print(f"SPR region: {spr_wavelengths.min():.1f} - {spr_wavelengths.max():.1f} nm ({len(spr_wavelengths)} points)")
print()

def apply_fourier_method(transmission_spectrum, wavelengths, alpha=9000, 
                        step5_window=50, step6_window=50, 
                        sg_window=11, sg_poly=3, apply_sg=True):
    """Apply Fourier peak finding with optional SG filtering."""
    # Extract SPR region
    spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
    spr_wavelengths = wavelengths[spr_mask]
    spr_transmission = transmission_spectrum[spr_mask]
    
    # Apply SG filter if requested
    if apply_sg and len(spr_transmission) >= sg_window:
        spectrum = savgol_filter(spr_transmission, sg_window, sg_poly)
    else:
        spectrum = spr_transmission
    
    # Find minimum hint
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
    
    # Calculate derivative
    derivative = idct(fourier_coeff, 1)
    
    # Find zero-crossing (Step 5)
    search_start = max(0, hint_index - step5_window)
    search_end = min(len(derivative), hint_index + step5_window)
    derivative_window = derivative[search_start:search_end]
    zero_local = derivative_window.searchsorted(0)
    zero = search_start + zero_local
    
    # Linear regression refinement (Step 6)
    start = max(zero - step6_window, 0)
    end = min(zero + step6_window, n - 1)
    line = linregress(spr_wavelengths[start:end], derivative[start:end])
    peak_wavelength = -line.intercept / line.slope
    
    return peak_wavelength

def test_temporal_response(sg_window, sg_poly):
    """Test temporal response with given SG parameters.
    
    Measures:
    1. Noise (p2p variation)
    2. Response delay (lag from filtering)
    3. Peak smoothing (distortion of sharp features)
    """
    wavelength_series = []
    
    # Process each time point
    for time_col in time_columns:
        # Get transmission spectrum at this time point
        transmission_spectrum = df[time_col].values
        
        # Apply Fourier with current SG parameters
        wavelength = apply_fourier_method(
            transmission_spectrum, wavelengths, alpha=9000,
            step5_window=50, step6_window=50,
            sg_window=sg_window, sg_poly=sg_poly, apply_sg=True
        )
        
        wavelength_series.append(wavelength)
    
    wavelength_series = np.array(wavelength_series)
    valid_mask = np.isfinite(wavelength_series)
    wavelength_series = wavelength_series[valid_mask]
    
    if len(wavelength_series) == 0:
        return None
    
    # Convert to RU (355 RU/nm)
    spr_ru = (wavelength_series - wavelength_series[0]) * 355
    
    # Noise metrics
    p2p = np.ptp(spr_ru)
    std = np.std(spr_ru)
    
    # Temporal response metrics
    # 1. Calculate first derivative (rate of change) - should be small for stable baseline
    time_derivative = np.abs(np.diff(spr_ru))
    max_rate = np.max(time_derivative)
    mean_rate = np.mean(time_derivative)
    
    # 2. Calculate phase lag by comparing with unfiltered version
    # (Use sg_window=5 as minimal filtering baseline)
    wavelength_minimal = []
    for time_col in time_columns:
        transmission_spectrum = df[time_col].values
        wl = apply_fourier_method(
            transmission_spectrum, wavelengths, alpha=9000,
            step5_window=50, step6_window=50,
            sg_window=5, sg_poly=2, apply_sg=True
        )
        wavelength_minimal.append(wl)
    
    wavelength_minimal = np.array(wavelength_minimal)
    valid_minimal = np.isfinite(wavelength_minimal)
    wavelength_minimal = wavelength_minimal[valid_minimal]
    spr_minimal = (wavelength_minimal - wavelength_minimal[0]) * 355
    
    # Cross-correlation to measure lag
    if len(spr_ru) == len(spr_minimal):
        correlation = np.correlate(spr_ru - np.mean(spr_ru), 
                                  spr_minimal - np.mean(spr_minimal), 
                                  mode='same')
        lag_samples = np.argmax(correlation) - len(correlation) // 2
    else:
        lag_samples = 0
    
    return {
        'sg_window': sg_window,
        'sg_poly': sg_poly,
        'p2p_ru': p2p,
        'std_ru': std,
        'max_rate': max_rate,
        'mean_rate': mean_rate,
        'lag_samples': abs(lag_samples),
        'series': spr_ru
    }

# Test range of SG parameters
print("\n" + "=" * 80)
print("TESTING SG PARAMETERS FOR NOISE vs TEMPORAL RESPONSE TRADEOFF")
print("=" * 80)

# Define test grid
window_sizes = [5, 7, 9, 11, 13, 15, 17, 19, 21, 25, 31, 41, 51]  # Must be odd
poly_orders = [2, 3, 4, 5]

results = []

for window in window_sizes:
    for poly in poly_orders:
        # Skip invalid combinations (window must be > poly)
        if window <= poly:
            continue
        
        print(f"\nTesting: window={window:2d}, poly={poly} ... ", end='', flush=True)
        
        result = test_temporal_response(window, poly)
        
        if result is None:
            print("FAILED")
            continue
        
        results.append(result)
        
        print(f"p2p={result['p2p_ru']:5.2f} RU, lag={result['lag_samples']} samples, "
              f"max_rate={result['max_rate']:.3f} RU/s")

# Analyze results
print("\n" + "=" * 80)
print("ANALYSIS: OPTIMAL PARAMETERS")
print("=" * 80)

results_df = pd.DataFrame(results)

# Sort by p2p (best noise)
best_noise = results_df.nsmallest(5, 'p2p_ru')
print("\n🎯 BEST NOISE REDUCTION (Top 5):")
print(best_noise[['sg_window', 'sg_poly', 'p2p_ru', 'lag_samples', 'max_rate']].to_string(index=False))

# Find optimal balance: low p2p + low lag + low rate
# Score = p2p + 5*lag + 100*max_rate (penalize lag and rate changes)
results_df['score'] = results_df['p2p_ru'] + 5*results_df['lag_samples'] + 100*results_df['max_rate']
best_balanced = results_df.nsmallest(5, 'score')
print("\n⚖  BEST BALANCED (Noise + Temporal Response):")
print(best_balanced[['sg_window', 'sg_poly', 'p2p_ru', 'lag_samples', 'max_rate', 'score']].to_string(index=False))

# Find low-lag options (lag < 2 samples)
low_lag = results_df[results_df['lag_samples'] < 2].nsmallest(5, 'p2p_ru')
print("\n⏱  LOW LAG OPTIONS (< 2 sample delay):")
print(low_lag[['sg_window', 'sg_poly', 'p2p_ru', 'lag_samples', 'max_rate']].to_string(index=False))

# Visualize tradeoffs
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Plot 1: Noise vs Window Size (by poly order)
ax = axes[0, 0]
for poly in poly_orders:
    subset = results_df[results_df['sg_poly'] == poly]
    ax.plot(subset['sg_window'], subset['p2p_ru'], marker='o', label=f'poly={poly}')
ax.axhline(y=2, color='r', linestyle='--', label='Target (2 RU)')
ax.set_xlabel('SG Window Size')
ax.set_ylabel('Peak-to-Peak Noise (RU)')
ax.set_title('Noise vs Window Size')
ax.legend()
ax.grid(True, alpha=0.3)

# Plot 2: Lag vs Window Size
ax = axes[0, 1]
for poly in poly_orders:
    subset = results_df[results_df['sg_poly'] == poly]
    ax.plot(subset['sg_window'], subset['lag_samples'], marker='o', label=f'poly={poly}')
ax.set_xlabel('SG Window Size')
ax.set_ylabel('Phase Lag (samples)')
ax.set_title('Temporal Lag vs Window Size')
ax.legend()
ax.grid(True, alpha=0.3)

# Plot 3: Max Rate vs Window Size
ax = axes[1, 0]
for poly in poly_orders:
    subset = results_df[results_df['sg_poly'] == poly]
    ax.plot(subset['sg_window'], subset['max_rate'], marker='o', label=f'poly={poly}')
ax.set_xlabel('SG Window Size')
ax.set_ylabel('Max Rate of Change (RU/s)')
ax.set_title('Peak Rate vs Window Size')
ax.legend()
ax.grid(True, alpha=0.3)

# Plot 4: Pareto Front (Noise vs Lag)
ax = axes[1, 1]
scatter = ax.scatter(results_df['p2p_ru'], results_df['lag_samples'], 
                    c=results_df['sg_window'], s=100, alpha=0.6, cmap='viridis')
ax.axvline(x=2, color='r', linestyle='--', alpha=0.5, label='Target Noise')
ax.set_xlabel('Peak-to-Peak Noise (RU)')
ax.set_ylabel('Phase Lag (samples)')
ax.set_title('Noise vs Lag Tradeoff')
cbar = plt.colorbar(scatter, ax=ax)
cbar.set_label('Window Size')
ax.grid(True, alpha=0.3)

# Annotate best points
best = results_df.nsmallest(3, 'score')
for _, row in best.iterrows():
    ax.annotate(f"w={int(row['sg_window'])},p={int(row['sg_poly'])}", 
               (row['p2p_ru'], row['lag_samples']),
               xytext=(5, 5), textcoords='offset points', fontsize=8)

plt.tight_layout()
plt.savefig('sg_temporal_integrity_analysis.png', dpi=150, bbox_inches='tight')
print("\n[OK] Plots saved to: sg_temporal_integrity_analysis.png")

# Plot comparison of best candidates
print("\n" + "=" * 80)
print("TIME SERIES COMPARISON (Best 3 Configurations)")
print("=" * 80)

fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

# Plot current configuration (11, 3)
current = [r for r in results if r['sg_window'] == 11 and r['sg_poly'] == 3]
if current:
    ax = axes[0]
    ax.plot(current[0]['series'], label=f"Current (11,3): {current[0]['p2p_ru']:.2f} RU", linewidth=1.5)
    ax.set_ylabel('SPR (RU)')
    ax.set_title('Current Configuration')
    ax.legend()
    ax.grid(True, alpha=0.3)

# Plot best noise configuration
best_config = best_balanced.iloc[0]
best_result = [r for r in results if r['sg_window'] == best_config['sg_window'] 
               and r['sg_poly'] == best_config['sg_poly']][0]
ax = axes[1]
ax.plot(best_result['series'], 
       label=f"Best ({int(best_config['sg_window'])},{int(best_config['sg_poly'])}): {best_config['p2p_ru']:.2f} RU", 
       linewidth=1.5, color='green')
ax.set_ylabel('SPR (RU)')
ax.set_title('Best Balanced Configuration')
ax.legend()
ax.grid(True, alpha=0.3)

# Plot most aggressive (highest window)
aggressive = results_df.nlargest(1, 'sg_window').iloc[0]
aggressive_result = [r for r in results if r['sg_window'] == aggressive['sg_window'] 
                    and r['sg_poly'] == aggressive['sg_poly']][0]
ax = axes[2]
ax.plot(aggressive_result['series'], 
       label=f"Aggressive ({int(aggressive['sg_window'])},{int(aggressive['sg_poly'])}): {aggressive['p2p_ru']:.2f} RU", 
       linewidth=1.5, color='orange')
ax.set_xlabel('Time Point')
ax.set_ylabel('SPR (RU)')
ax.set_title('Most Aggressive Configuration')
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('sg_timeseries_comparison.png', dpi=150, bbox_inches='tight')
print("[OK] Comparison saved to: sg_timeseries_comparison.png")

print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)

recommended = best_balanced.iloc[0]
print(f"\n🎯 RECOMMENDED CONFIGURATION:")
print(f"   SG Window: {int(recommended['sg_window'])} (currently 11)")
print(f"   SG Poly: {int(recommended['sg_poly'])} (currently 3)")
print(f"\n   Performance:")
print(f"   • Noise: {recommended['p2p_ru']:.2f} RU (vs current {current[0]['p2p_ru']:.2f} RU)")
print(f"   • Phase lag: {int(recommended['lag_samples'])} samples")
print(f"   • Max rate: {recommended['max_rate']:.3f} RU/s")
print(f"\n   Improvement: {(1 - recommended['p2p_ru']/current[0]['p2p_ru'])*100:.1f}% noise reduction")

if recommended['lag_samples'] <= 1:
    print("   [OK] Minimal phase lag - temporal integrity preserved")
else:
    print(f"   [WARN]  Phase lag of {int(recommended['lag_samples'])} samples - may affect fast transients")

print("\n" + "=" * 80)
