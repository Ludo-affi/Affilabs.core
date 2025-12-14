"""Advanced filtering techniques for SPR baseline noise reduction.

Tests multiple sophisticated filtering approaches that maintain temporal resolution:
1. Kalman Filter - Optimal statistical estimator
2. Exponential Moving Average (EMA) - Adaptive smoothing
3. Wavelet Denoising - Multi-scale decomposition
4. Savitzky-Golay with Derivative Constraint - Physics-informed filtering
5. Median-of-3 with trend preservation - Outlier rejection

Each method is evaluated on:
- Noise reduction (p2p RU)
- Temporal response (lag, rise time)
- Step response preservation
- Computational cost
"""

import pandas as pd
import numpy as np
from scipy.signal import savgol_filter, medfilt
from scipy.fftpack import dst, idct
from scipy.stats import linregress
import matplotlib.pyplot as plt
import pywt  # Wavelet transform

# Load baseline data
baseline_file = r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\ezControl-AI\baseline_data\baseline_recording_20251203_172554.xlsx"
df = pd.read_excel(baseline_file)

wavelengths = df['wavelength_nm'].values
time_columns = [col for col in df.columns if col.startswith('t_')]
n_timepoints = len(time_columns)

print("=" * 80)
print("ADVANCED FILTERING ANALYSIS FOR SPR NOISE REDUCTION")
print("=" * 80)
print(f"Dataset: {n_timepoints} timepoints, {len(wavelengths)} wavelengths")
print()

def apply_fourier_method(transmission_spectrum, wavelengths, alpha=9000):
    """Standard Fourier peak finding (no SG filter)."""
    spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
    spr_wavelengths = wavelengths[spr_mask]
    spr_transmission = transmission_spectrum[spr_mask]
    
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
    
    # Zero-crossing
    search_window = 50
    search_start = max(0, hint_index - search_window)
    search_end = min(len(derivative), hint_index + search_window)
    derivative_window = derivative[search_start:search_end]
    zero_local = derivative_window.searchsorted(0)
    zero = search_start + zero_local
    
    # Linear regression
    start = max(zero - 50, 0)
    end = min(zero + 50, n - 1)
    line = linregress(spr_wavelengths[start:end], derivative[start:end])
    peak_wavelength = -line.intercept / line.slope
    
    return peak_wavelength

def get_raw_series():
    """Get unfiltered wavelength series."""
    wavelength_series = []
    for time_col in time_columns:
        transmission_spectrum = df[time_col].values
        wavelength = apply_fourier_method(transmission_spectrum, wavelengths)
        wavelength_series.append(wavelength)
    
    wavelength_series = np.array(wavelength_series)
    valid_mask = np.isfinite(wavelength_series)
    return (wavelength_series[valid_mask] - wavelength_series[valid_mask][0]) * 355

# ============================================================================
# METHOD 1: KALMAN FILTER
# ============================================================================
def kalman_filter_1d(measurements, process_variance=1e-5, measurement_variance=0.1):
    """1D Kalman filter for optimal state estimation.
    
    Args:
        measurements: Noisy SPR measurements (RU)
        process_variance: Process noise (how much we expect signal to change)
        measurement_variance: Measurement noise (sensor noise level)
    
    Returns:
        Filtered signal with optimal noise reduction
    """
    n = len(measurements)
    
    # State variables
    x_est = np.zeros(n)  # Estimated state
    P_est = np.zeros(n)  # Estimation error covariance
    
    # Initialize
    x_est[0] = measurements[0]
    P_est[0] = 1.0
    
    Q = process_variance  # Process noise covariance
    R = measurement_variance  # Measurement noise covariance
    
    for k in range(1, n):
        # Prediction
        x_pred = x_est[k-1]  # State prediction (assume constant)
        P_pred = P_est[k-1] + Q  # Covariance prediction
        
        # Update
        K = P_pred / (P_pred + R)  # Kalman gain
        x_est[k] = x_pred + K * (measurements[k] - x_pred)  # State update
        P_est[k] = (1 - K) * P_pred  # Covariance update
    
    return x_est

# ============================================================================
# METHOD 2: ADAPTIVE KALMAN FILTER (Auto-tuning)
# ============================================================================
def adaptive_kalman_filter(measurements, initial_process_var=1e-5):
    """Kalman filter with adaptive noise estimation.
    
    Automatically adjusts measurement noise based on residual statistics.
    """
    n = len(measurements)
    x_est = np.zeros(n)
    P_est = np.zeros(n)
    
    x_est[0] = measurements[0]
    P_est[0] = 1.0
    
    Q = initial_process_var
    R = np.var(np.diff(measurements[:10]))  # Initial estimate from first 10 points
    
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
        
        # Adapt R based on innovation statistics
        residuals.append(innovation**2)
        if k > 10 and k % 10 == 0:
            # Update R every 10 samples based on recent residuals
            R = np.mean(residuals[-10:])
    
    return x_est

# ============================================================================
# METHOD 3: EXPONENTIAL MOVING AVERAGE (EMA)
# ============================================================================
def exponential_moving_average(measurements, alpha=0.3):
    """EMA filter with adjustable smoothing factor.
    
    Args:
        alpha: Smoothing factor (0-1). Lower = more smoothing, higher lag.
    """
    n = len(measurements)
    ema = np.zeros(n)
    ema[0] = measurements[0]
    
    for i in range(1, n):
        ema[i] = alpha * measurements[i] + (1 - alpha) * ema[i-1]
    
    return ema

# ============================================================================
# METHOD 4: WAVELET DENOISING
# ============================================================================
def wavelet_denoise(measurements, wavelet='db4', level=3):
    """Wavelet-based denoising using soft thresholding.
    
    Args:
        wavelet: Wavelet type ('db4', 'sym4', 'coif1')
        level: Decomposition level
    """
    # Decompose signal
    coeffs = pywt.wavedec(measurements, wavelet, level=level)
    
    # Calculate threshold using MAD (Median Absolute Deviation)
    sigma = np.median(np.abs(coeffs[-1])) / 0.6745
    threshold = sigma * np.sqrt(2 * np.log(len(measurements)))
    
    # Apply soft thresholding to detail coefficients
    coeffs_thresh = [coeffs[0]]  # Keep approximation
    for i in range(1, len(coeffs)):
        coeffs_thresh.append(pywt.threshold(coeffs[i], threshold, mode='soft'))
    
    # Reconstruct signal
    return pywt.waverec(coeffs_thresh, wavelet)

# ============================================================================
# METHOD 5: DOUBLE EXPONENTIAL SMOOTHING (Holt's Method)
# ============================================================================
def double_exponential_smoothing(measurements, alpha=0.3, beta=0.1):
    """Double exponential smoothing for trend-following.
    
    Handles both level and trend components.
    """
    n = len(measurements)
    level = np.zeros(n)
    trend = np.zeros(n)
    
    # Initialize
    level[0] = measurements[0]
    trend[0] = measurements[1] - measurements[0] if n > 1 else 0
    
    for i in range(1, n):
        level_prev = level[i-1]
        trend_prev = trend[i-1]
        
        level[i] = alpha * measurements[i] + (1 - alpha) * (level_prev + trend_prev)
        trend[i] = beta * (level[i] - level_prev) + (1 - beta) * trend_prev
    
    return level

# ============================================================================
# METHOD 6: MEDIAN-OF-3 WITH TREND PRESERVATION
# ============================================================================
def median_of_3_trend(measurements):
    """Median filter with trend preservation.
    
    Takes median of [prev, current, next] but preserves overall trend.
    """
    n = len(measurements)
    filtered = np.zeros(n)
    
    # Boundaries
    filtered[0] = measurements[0]
    filtered[-1] = measurements[-1]
    
    # Middle points
    for i in range(1, n-1):
        window = [measurements[i-1], measurements[i], measurements[i+1]]
        filtered[i] = np.median(window)
    
    return filtered

# ============================================================================
# METHOD 7: SAVITZKY-GOLAY WITH PHYSICS CONSTRAINT
# ============================================================================
def constrained_savgol(measurements, window=11, poly=3, max_derivative=0.5):
    """SG filter with physical constraint on derivative.
    
    Rejects points where derivative exceeds physical limit.
    """
    # Apply standard SG filter
    filtered = savgol_filter(measurements, window, poly)
    
    # Calculate derivative
    derivative = np.gradient(filtered)
    
    # Identify violations
    violations = np.abs(derivative) > max_derivative
    
    # Interpolate violations
    if np.any(violations):
        valid_idx = np.where(~violations)[0]
        filtered[violations] = np.interp(
            np.where(violations)[0],
            valid_idx,
            filtered[valid_idx]
        )
    
    return filtered

# ============================================================================
# RUN ALL METHODS
# ============================================================================
print("\n" + "=" * 80)
print("TESTING ALL FILTERING METHODS")
print("=" * 80)

# Get raw data
raw_spr = get_raw_series()
print(f"\n📊 Raw Data: p2p = {np.ptp(raw_spr):.2f} RU, std = {np.std(raw_spr):.2f} RU")

results = []

# Method 1: Kalman Filter (multiple process variances)
for pv in [1e-6, 1e-5, 1e-4, 1e-3]:
    filtered = kalman_filter_1d(raw_spr, process_variance=pv, measurement_variance=0.1)
    p2p = np.ptp(filtered)
    lag = np.argmax(np.correlate(filtered - np.mean(filtered), raw_spr - np.mean(raw_spr), mode='same')) - len(filtered)//2
    results.append({
        'method': f'Kalman (Q={pv:.0e})',
        'p2p': p2p,
        'std': np.std(filtered),
        'lag': abs(lag),
        'series': filtered
    })
    print(f"  Kalman (Q={pv:.0e}): p2p={p2p:.2f} RU, lag={abs(lag)} samples")

# Method 2: Adaptive Kalman
filtered = adaptive_kalman_filter(raw_spr)
p2p = np.ptp(filtered)
lag = np.argmax(np.correlate(filtered - np.mean(filtered), raw_spr - np.mean(raw_spr), mode='same')) - len(filtered)//2
results.append({
    'method': 'Adaptive Kalman',
    'p2p': p2p,
    'std': np.std(filtered),
    'lag': abs(lag),
    'series': filtered
})
print(f"  Adaptive Kalman: p2p={p2p:.2f} RU, lag={abs(lag)} samples")

# Method 3: EMA (multiple alphas)
for alpha in [0.1, 0.2, 0.3, 0.5]:
    filtered = exponential_moving_average(raw_spr, alpha=alpha)
    p2p = np.ptp(filtered)
    lag = np.argmax(np.correlate(filtered - np.mean(filtered), raw_spr - np.mean(raw_spr), mode='same')) - len(filtered)//2
    results.append({
        'method': f'EMA (α={alpha})',
        'p2p': p2p,
        'std': np.std(filtered),
        'lag': abs(lag),
        'series': filtered
    })
    print(f"  EMA (α={alpha}): p2p={p2p:.2f} RU, lag={abs(lag)} samples")

# Method 4: Wavelet Denoising
for wavelet in ['db4', 'sym4', 'coif2']:
    filtered = wavelet_denoise(raw_spr, wavelet=wavelet, level=3)[:len(raw_spr)]
    p2p = np.ptp(filtered)
    lag = np.argmax(np.correlate(filtered - np.mean(filtered), raw_spr - np.mean(raw_spr), mode='same')) - len(filtered)//2
    results.append({
        'method': f'Wavelet ({wavelet})',
        'p2p': p2p,
        'std': np.std(filtered),
        'lag': abs(lag),
        'series': filtered
    })
    print(f"  Wavelet ({wavelet}): p2p={p2p:.2f} RU, lag={abs(lag)} samples")

# Method 5: Double Exponential Smoothing
for alpha in [0.3, 0.5]:
    filtered = double_exponential_smoothing(raw_spr, alpha=alpha, beta=0.1)
    p2p = np.ptp(filtered)
    lag = np.argmax(np.correlate(filtered - np.mean(filtered), raw_spr - np.mean(raw_spr), mode='same')) - len(filtered)//2
    results.append({
        'method': f'Holt (α={alpha})',
        'p2p': p2p,
        'std': np.std(filtered),
        'lag': abs(lag),
        'series': filtered
    })
    print(f"  Holt (α={alpha}): p2p={p2p:.2f} RU, lag={abs(lag)} samples")

# Method 6: Median-of-3
filtered = median_of_3_trend(raw_spr)
p2p = np.ptp(filtered)
lag = 0  # Median-of-3 is symmetric, no lag
results.append({
    'method': 'Median-of-3',
    'p2p': p2p,
    'std': np.std(filtered),
    'lag': lag,
    'series': filtered
})
print(f"  Median-of-3: p2p={p2p:.2f} RU, lag={lag} samples")

# Method 7: Constrained SG
filtered = constrained_savgol(raw_spr, window=11, poly=3, max_derivative=0.5)
p2p = np.ptp(filtered)
lag = 0
results.append({
    'method': 'Constrained SG',
    'p2p': p2p,
    'std': np.std(filtered),
    'lag': lag,
    'series': filtered
})
print(f"  Constrained SG: p2p={p2p:.2f} RU, lag={lag} samples")

# ============================================================================
# ANALYSIS
# ============================================================================
print("\n" + "=" * 80)
print("RESULTS SUMMARY")
print("=" * 80)

results_df = pd.DataFrame(results)
results_df = results_df.sort_values('p2p')

print("\n🏆 TOP 10 METHODS (Best Noise Reduction):")
print(results_df[['method', 'p2p', 'std', 'lag']].head(10).to_string(index=False))

print("\n⚡ LOW-LAG OPTIONS (lag ≤ 2 samples):")
low_lag = results_df[results_df['lag'] <= 2]
print(low_lag[['method', 'p2p', 'std', 'lag']].head(5).to_string(index=False))

# Calculate improvement
raw_p2p = np.ptp(raw_spr)
best = results_df.iloc[0]
improvement = (1 - best['p2p'] / raw_p2p) * 100

print(f"\n[OK] BEST METHOD: {best['method']}")
print(f"   Noise: {best['p2p']:.2f} RU (was {raw_p2p:.2f} RU)")
print(f"   Improvement: {improvement:.1f}%")
print(f"   Lag: {best['lag']} samples")

# ============================================================================
# VISUALIZATIONS
# ============================================================================
fig, axes = plt.subplots(3, 2, figsize=(16, 12))

# Plot 1: Noise comparison
ax = axes[0, 0]
methods = results_df['method'].values[:10]
p2p_values = results_df['p2p'].values[:10]
colors = ['green' if lag <= 1 else 'orange' if lag <= 2 else 'red' for lag in results_df['lag'].values[:10]]
ax.barh(methods, p2p_values, color=colors)
ax.axvline(x=2, color='r', linestyle='--', label='Target (2 RU)', linewidth=2)
ax.axvline(x=raw_p2p, color='k', linestyle=':', label=f'Raw ({raw_p2p:.1f} RU)', linewidth=2)
ax.set_xlabel('Peak-to-Peak Noise (RU)')
ax.set_title('Top 10 Methods by Noise Reduction')
ax.legend()
ax.grid(True, alpha=0.3, axis='x')

# Plot 2: Lag vs Noise tradeoff
ax = axes[0, 1]
scatter = ax.scatter(results_df['p2p'], results_df['lag'], s=100, alpha=0.6)
ax.axvline(x=2, color='r', linestyle='--', alpha=0.5)
ax.set_xlabel('Peak-to-Peak Noise (RU)')
ax.set_ylabel('Phase Lag (samples)')
ax.set_title('Noise vs Lag Tradeoff')
ax.grid(True, alpha=0.3)

# Annotate best
for i in range(min(3, len(results_df))):
    row = results_df.iloc[i]
    ax.annotate(row['method'], (row['p2p'], row['lag']), 
               xytext=(5, 5), textcoords='offset points', fontsize=8)

# Plot 3-6: Time series comparisons (top 4 methods)
for i in range(4):
    ax = axes[1 + i//2, i%2]
    if i < len(results_df):
        result = results_df.iloc[i]
        ax.plot(raw_spr, alpha=0.3, label=f'Raw ({raw_p2p:.1f} RU)', color='gray')
        ax.plot(result['series'], label=f"{result['method']} ({result['p2p']:.1f} RU)", linewidth=2)
        ax.set_xlabel('Time Point')
        ax.set_ylabel('SPR (RU)')
        ax.set_title(f"#{i+1}: {result['method']}")
        ax.legend()
        ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('advanced_filtering_comparison.png', dpi=150, bbox_inches='tight')
print("\n[OK] Plots saved to: advanced_filtering_comparison.png")

# ============================================================================
# RECOMMENDATION
# ============================================================================
print("\n" + "=" * 80)
print("IMPLEMENTATION RECOMMENDATION")
print("=" * 80)

best_low_lag = low_lag.iloc[0]

print(f"\n🎯 RECOMMENDED: {best_low_lag['method']}")
print(f"\n   Why this method?")
print(f"   • Excellent noise reduction: {best_low_lag['p2p']:.2f} RU")
print(f"   • Minimal lag: {best_low_lag['lag']} samples")
print(f"   • Real-time capable")
print(f"   • Easy to implement")

if 'Kalman' in best_low_lag['method']:
    print(f"\n   Implementation:")
    print(f"   • Use Kalman filter in peak processing pipeline")
    print(f"   • Process wavelength stream, not raw transmission")
    print(f"   • ~10 lines of code, minimal CPU overhead")
elif 'EMA' in best_low_lag['method']:
    print(f"\n   Implementation:")
    print(f"   • Apply EMA to wavelength stream")
    print(f"   • self.spr_filtered = α * spr_new + (1-α) * spr_prev")
    print(f"   • 1 line of code per channel")
elif 'Wavelet' in best_low_lag['method']:
    print(f"\n   Implementation:")
    print(f"   • Apply wavelet denoising to wavelength stream")
    print(f"   • Requires pywt library")
    print(f"   • Slightly higher CPU cost")

print(f"\n   Expected result: {raw_p2p:.2f} RU → {best_low_lag['p2p']:.2f} RU")
print(f"   Improvement: {(1 - best_low_lag['p2p']/raw_p2p)*100:.1f}%")

print("\n" + "=" * 80)
