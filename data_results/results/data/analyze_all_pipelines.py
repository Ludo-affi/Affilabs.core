"""Compare all peak finding methods on baseline data (detrended around zero).

Methods tested:
1. Current implementation (α=9000, SG 11/3, window 50, linear)
2. Optimized Fourier only (α=2000, window 100, quadratic)
3. With SG optimization (SG 11/5)
4. With Kalman filter
5. Full optimization (α=2000 + SG 11/5 + window 100/quad + Kalman)

All centered at 0 RU with polynomial detrending.
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
print("COMPLETE PIPELINE COMPARISON (ALL DETRENDED)")
print("=" * 80)
print(f"Dataset: {n_timepoints} timepoints, {len(wavelengths)} wavelengths\n")

def apply_fourier_method(transmission_spectrum, wavelengths, 
                         alpha=9000,
                         apply_sg=False, sg_window=11, sg_poly=3,
                         regression_window=50, 
                         regression_poly=1):
    """Fourier peak finding with all options."""
    # SPR region
    spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
    spr_wavelengths = wavelengths[spr_mask]
    spr_transmission = transmission_spectrum[spr_mask]
    
    # Optional SG filter
    if apply_sg:
        spectrum = savgol_filter(spr_transmission, window_length=sg_window, polyorder=sg_poly)
    else:
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
        line = linregress(x, y)
        peak_wavelength = -line.intercept / line.slope
    else:
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
    """Adaptive Kalman filter."""
    n = len(measurements)
    x_est = np.zeros(n)
    P_est = np.zeros(n)
    
    x_est[0] = measurements[0]
    P_est[0] = 1.0
    
    Q = initial_process_var
    R = np.var(np.diff(measurements[:10]))
    
    residuals = []
    
    for k in range(1, n):
        x_pred = x_est[k-1]
        P_pred = P_est[k-1] + Q
        
        K = P_pred / (P_pred + R)
        innovation = measurements[k] - x_pred
        x_est[k] = x_pred + K * innovation
        P_est[k] = (1 - K) * P_pred
        
        residuals.append(innovation**2)
        if k > 10 and k % 10 == 0:
            R = np.mean(residuals[-10:])
    
    return x_est

def get_spr_series(alpha=9000, apply_sg=False, sg_window=11, sg_poly=3,
                   regression_window=50, regression_poly=1, apply_kalman=False):
    """Get SPR time series with detrending."""
    wavelength_series = []
    
    for time_col in time_columns:
        transmission_spectrum = df[time_col].values
        try:
            wavelength = apply_fourier_method(
                transmission_spectrum, wavelengths,
                alpha=alpha,
                apply_sg=apply_sg,
                sg_window=sg_window,
                sg_poly=sg_poly,
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
    
    # Apply Kalman if requested
    if apply_kalman:
        spr_series = adaptive_kalman_filter(spr_series)
    
    # Detrend (remove polynomial drift)
    time_indices = np.arange(len(spr_series))
    poly_coeffs = np.polyfit(time_indices, spr_series, deg=2)
    poly_trend = np.polyval(poly_coeffs, time_indices)
    spr_detrended = spr_series - poly_trend
    
    return spr_detrended

def get_centroid_series():
    """Get SPR series using centroid (center of mass) method with detrending."""
    wavelength_series = []
    
    for time_col in time_columns:
        transmission_spectrum = df[time_col].values
        try:
            # SPR region
            spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
            spr_wavelengths = wavelengths[spr_mask]
            spr_transmission = transmission_spectrum[spr_mask]
            
            # Apply Gaussian smoothing
            smoothed = gaussian_filter1d(spr_transmission, sigma=2.0)
            
            # Find minimum
            min_idx = np.argmin(smoothed)
            
            # Extract window around minimum (±50 pixels)
            search_window = 50
            start_idx = max(0, min_idx - search_window)
            end_idx = min(len(smoothed), min_idx + search_window)
            
            window_spectrum = smoothed[start_idx:end_idx]
            window_wavelengths = spr_wavelengths[start_idx:end_idx]
            
            # Invert spectrum (make dip into peak)
            inverted = np.max(window_spectrum) - window_spectrum
            inverted = np.maximum(inverted, 0)
            
            # Calculate centroid (weighted average)
            if np.sum(inverted) > 0:
                centroid_wavelength = np.sum(window_wavelengths * inverted) / np.sum(inverted)
            else:
                centroid_wavelength = spr_wavelengths[min_idx]
            
            wavelength_series.append(centroid_wavelength)
        except:
            wavelength_series.append(np.nan)
    
    wavelength_series = np.array(wavelength_series)
    valid_mask = np.isfinite(wavelength_series)
    wavelength_series = wavelength_series[valid_mask]
    
    # Convert to RU
    spr_series = (wavelength_series - wavelength_series[0]) * 355
    
    # Detrend
    time_indices = np.arange(len(spr_series))
    poly_coeffs = np.polyfit(time_indices, spr_series, deg=2)
    poly_trend = np.polyval(poly_coeffs, time_indices)
    spr_detrended = spr_series - poly_trend
    
    return spr_detrended

def get_minimum_series():
    """Get SPR series using simple minimum finding with detrending."""
    wavelength_series = []
    
    for time_col in time_columns:
        transmission_spectrum = df[time_col].values
        try:
            # SPR region
            spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
            spr_wavelengths = wavelengths[spr_mask]
            spr_transmission = transmission_spectrum[spr_mask]
            
            # Apply light Gaussian smoothing
            smoothed = gaussian_filter1d(spr_transmission, sigma=1.0)
            
            # Find minimum
            min_idx = np.argmin(smoothed)
            min_wavelength = spr_wavelengths[min_idx]
            
            wavelength_series.append(min_wavelength)
        except:
            wavelength_series.append(np.nan)
    
    wavelength_series = np.array(wavelength_series)
    valid_mask = np.isfinite(wavelength_series)
    wavelength_series = wavelength_series[valid_mask]
    
    # Convert to RU
    spr_series = (wavelength_series - wavelength_series[0]) * 355
    
    # Detrend
    time_indices = np.arange(len(spr_series))
    poly_coeffs = np.polyfit(time_indices, spr_series, deg=2)
    poly_trend = np.polyval(poly_coeffs, time_indices)
    spr_detrended = spr_series - poly_trend
    
    return spr_detrended

def get_consensus_series():
    """Get SPR series using consensus method (60% centroid + 40% parabolic) with detrending."""
    wavelength_series = []
    
    for time_col in time_columns:
        transmission_spectrum = df[time_col].values
        try:
            # SPR region
            spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
            spr_wavelengths = wavelengths[spr_mask]
            spr_transmission = transmission_spectrum[spr_mask]
            
            # Method 1: Adaptive Centroid
            inverted = 100.0 - spr_transmission
            max_signal = np.max(inverted)
            
            # Adaptive threshold to get ~15 points
            threshold = 0.5
            for threshold_test in [0.5, 0.4, 0.3, 0.6, 0.7]:
                threshold_value = max_signal * threshold_test
                significant_mask = inverted >= threshold_value
                n_points = np.sum(significant_mask)
                if 10 <= n_points <= 25:
                    threshold = threshold_test
                    break
            
            threshold_value = max_signal * threshold
            significant_mask = inverted >= threshold_value
            
            if np.sum(significant_mask) >= 3:
                weights = inverted[significant_mask]
                positions = spr_wavelengths[significant_mask]
                peak_centroid = np.sum(weights * positions) / np.sum(weights)
            else:
                peak_centroid = spr_wavelengths[np.argmin(spr_transmission)]
            
            # Method 2: Parabolic Interpolation
            min_idx = np.argmin(spr_transmission)
            
            if 0 < min_idx < len(spr_transmission) - 1:
                x = spr_wavelengths[min_idx-1:min_idx+2]
                y = spr_transmission[min_idx-1:min_idx+2]
                
                denom = (x[0] - x[1]) * (x[0] - x[2]) * (x[1] - x[2])
                if abs(denom) > 1e-10:
                    A = (x[2] * (y[1] - y[0]) + x[1] * (y[0] - y[2]) + x[0] * (y[2] - y[1])) / denom
                    B = (x[2]**2 * (y[0] - y[1]) + x[1]**2 * (y[2] - y[0]) + x[0]**2 * (y[1] - y[2])) / denom
                    peak_parabolic = -B / (2 * A) if A > 0 else spr_wavelengths[min_idx]
                    
                    if abs(peak_parabolic - spr_wavelengths[min_idx]) > 2.0:
                        peak_parabolic = spr_wavelengths[min_idx]
                else:
                    peak_parabolic = spr_wavelengths[min_idx]
            else:
                peak_parabolic = spr_wavelengths[min_idx]
            
            # Consensus: 60% centroid + 40% parabolic
            consensus_wavelength = 0.6 * peak_centroid + 0.4 * peak_parabolic
            wavelength_series.append(consensus_wavelength)
        except:
            wavelength_series.append(np.nan)
    
    wavelength_series = np.array(wavelength_series)
    valid_mask = np.isfinite(wavelength_series)
    wavelength_series = wavelength_series[valid_mask]
    
    # Convert to RU
    spr_series = (wavelength_series - wavelength_series[0]) * 355
    
    # Detrend
    time_indices = np.arange(len(spr_series))
    poly_coeffs = np.polyfit(time_indices, spr_series, deg=2)
    poly_trend = np.polyval(poly_coeffs, time_indices)
    spr_detrended = spr_series - poly_trend
    
    return spr_detrended

def get_multifeature_series():
    """Get SPR series using IMPROVED Adaptive Multi-Feature method with better filtering."""
    wavelength_series = []
    
    for time_col in time_columns:
        transmission_spectrum = df[time_col].values
        try:
            # SPR region
            spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
            spr_wavelengths = wavelengths[spr_mask]
            spr_transmission = transmission_spectrum[spr_mask]
            
            # Step 1: Aggressive filtering (like your Fourier method's effective filtering)
            # SG filter for shape preservation
            filtered = savgol_filter(spr_transmission, window_length=11, polyorder=5)
            # Additional Gaussian for noise suppression
            filtered = gaussian_filter1d(filtered, sigma=2.0)
            
            # Step 2: Find minimum as robust starting point
            min_idx = np.argmin(filtered)
            
            # Step 3: Local window regression (like Fourier method's refinement)
            # Use wider window for stability
            window_size = 50
            start = max(0, min_idx - window_size)
            end = min(len(filtered), min_idx + window_size)
            
            x_window = spr_wavelengths[start:end]
            y_window = filtered[start:end]
            
            # Fit quadratic around minimum
            try:
                coeffs = np.polyfit(x_window, y_window, 2)
                # Find vertex: x = -b/(2a)
                if coeffs[0] > 0:  # Concave up (dip)
                    peak_wavelength = -coeffs[1] / (2 * coeffs[0])
                    
                    # Validate: must be in reasonable range
                    if peak_wavelength < spr_wavelengths[0] or peak_wavelength > spr_wavelengths[-1]:
                        peak_wavelength = spr_wavelengths[min_idx]
                else:
                    peak_wavelength = spr_wavelengths[min_idx]
            except:
                peak_wavelength = spr_wavelengths[min_idx]
            
            # Step 4: Optional Gaussian refinement (conservative blend)
            def peak_model(x, x0, A, sigma, baseline):
                return baseline - A * np.exp(-((x - x0) / sigma) ** 2)
            
            try:
                from scipy.optimize import curve_fit
                baseline = np.max(filtered)
                amplitude = baseline - np.min(filtered)
                
                # Symmetric Gaussian (simpler, more stable)
                p0 = [peak_wavelength, amplitude, 20.0, baseline]
                bounds = (
                    [spr_wavelengths[0], 0, 5, 0],
                    [spr_wavelengths[-1], 100, 80, 100]
                )
                
                popt, _ = curve_fit(peak_model, spr_wavelengths, filtered, p0=p0, 
                                   bounds=bounds, maxfev=3000)
                gaussian_peak = popt[0]
                
                # Conservative blend: 80% regression + 20% Gaussian
                if abs(gaussian_peak - peak_wavelength) < 3.0:
                    peak_wavelength = 0.8 * peak_wavelength + 0.2 * gaussian_peak
            except:
                pass  # Keep regression result
            
            wavelength_series.append(peak_wavelength)
        except:
            wavelength_series.append(np.nan)
    
    wavelength_series = np.array(wavelength_series)
    valid_mask = np.isfinite(wavelength_series)
    wavelength_series = wavelength_series[valid_mask]
    
    # Convert to RU
    spr_series = (wavelength_series - wavelength_series[0]) * 355
    
    # Detrend
    time_indices = np.arange(len(spr_series))
    poly_coeffs = np.polyfit(time_indices, spr_series, deg=2)
    poly_trend = np.polyval(poly_coeffs, time_indices)
    spr_detrended = spr_series - poly_trend
    
    return spr_detrended

def get_fourier_multifeature_series(alpha=2000, sg_window=11, sg_poly=5, 
                                     regression_window=100, use_gaussian_refinement=True):
    """Get SPR series using HYBRID Fourier + Multi-Feature method with full optimization."""
    wavelength_series = []
    
    for time_col in time_columns:
        transmission_spectrum = df[time_col].values
        try:
            # SPR region
            spr_mask = (wavelengths >= 620) & (wavelengths <= 680)
            spr_wavelengths = wavelengths[spr_mask]
            spr_transmission = transmission_spectrum[spr_mask]
            
            # Step 1: Multi-feature filtering (SG + Gaussian)
            spectrum = savgol_filter(spr_transmission, window_length=sg_window, polyorder=sg_poly)
            spectrum = gaussian_filter1d(spectrum, sigma=1.5)
            
            # Step 2: Fourier derivative for optimal smoothing
            hint_index = np.argmin(spectrum)
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
            
            # Step 3: Zero-crossing search (Fourier method)
            search_start = max(0, hint_index - 50)
            search_end = min(len(derivative), hint_index + 50)
            derivative_window = derivative[search_start:search_end]
            zero_local = derivative_window.searchsorted(0)
            zero = search_start + zero_local
            
            # Step 4: Quadratic regression refinement (wider window for stability)
            start = max(zero - regression_window, 0)
            end = min(zero + regression_window, n - 1)
            
            x = spr_wavelengths[start:end]
            y = derivative[start:end]
            
            # Quadratic regression for better peak fitting
            coeffs = np.polyfit(x, y, 2)
            roots = np.roots(coeffs)
            real_roots = roots[np.isreal(roots)].real
            
            if len(real_roots) > 0:
                closest_root = real_roots[np.argmin(np.abs(real_roots - spr_wavelengths[zero]))]
                peak_wavelength = closest_root
            else:
                # Fallback to linear
                line = linregress(x, y)
                peak_wavelength = -line.intercept / line.slope
            
            # Step 5: Optional Gaussian fit refinement (multi-feature contribution)
            if use_gaussian_refinement:
                def peak_model(x, x0, A, sigma, baseline):
                    return baseline - A * np.exp(-((x - x0) / sigma) ** 2)
                
                try:
                    from scipy.optimize import curve_fit
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
                    
                    # Blend: 90% Fourier + 10% Gaussian (Fourier is more stable)
                    if abs(gaussian_peak - peak_wavelength) < 2.0:
                        peak_wavelength = 0.9 * peak_wavelength + 0.1 * gaussian_peak
                except:
                    pass  # Keep Fourier result
            
            wavelength_series.append(peak_wavelength)
        except:
            wavelength_series.append(np.nan)
    
    wavelength_series = np.array(wavelength_series)
    valid_mask = np.isfinite(wavelength_series)
    wavelength_series = wavelength_series[valid_mask]
    
    # Convert to RU
    spr_series = (wavelength_series - wavelength_series[0]) * 355
    
    # Detrend
    time_indices = np.arange(len(spr_series))
    poly_coeffs = np.polyfit(time_indices, spr_series, deg=2)
    poly_trend = np.polyval(poly_coeffs, time_indices)
    spr_detrended = spr_series - poly_trend
    
    return spr_detrended

# ============================================================================
# TEST ALL PIPELINES
# ============================================================================
print("Testing all peak finding pipelines...")

pipelines = []

# Pipeline 1: Current baseline (what's in production)
spr = get_spr_series(alpha=9000, apply_sg=True, sg_window=11, sg_poly=3,
                     regression_window=50, regression_poly=1, apply_kalman=False)
pipelines.append({
    'name': '1. Current (Production)',
    'short': 'Current',
    'config': 'α=9000, SG 11/3, W=50/Linear',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Pipeline 2: No SG filter
spr = get_spr_series(alpha=9000, apply_sg=False,
                     regression_window=50, regression_poly=1, apply_kalman=False)
pipelines.append({
    'name': '2. No SG Filter',
    'short': 'No SG',
    'config': 'α=9000, No SG, W=50/Linear',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Pipeline 3: Optimized alpha only
spr = get_spr_series(alpha=2000, apply_sg=False,
                     regression_window=50, regression_poly=1, apply_kalman=False)
pipelines.append({
    'name': '3. Optimized Alpha',
    'short': 'α=2000',
    'config': 'α=2000, No SG, W=50/Linear',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Pipeline 4: Optimized alpha + SG
spr = get_spr_series(alpha=2000, apply_sg=True, sg_window=11, sg_poly=5,
                     regression_window=50, regression_poly=1, apply_kalman=False)
pipelines.append({
    'name': '4. Alpha + SG Optimized',
    'short': 'α=2000+SG',
    'config': 'α=2000, SG 11/5, W=50/Linear',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Pipeline 5: Optimized alpha + regression
spr = get_spr_series(alpha=2000, apply_sg=False,
                     regression_window=100, regression_poly=2, apply_kalman=False)
pipelines.append({
    'name': '5. Alpha + Regression',
    'short': 'α=2000+Reg',
    'config': 'α=2000, No SG, W=100/Quad',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Pipeline 6: Full Fourier optimization (no Kalman)
spr = get_spr_series(alpha=2000, apply_sg=True, sg_window=11, sg_poly=5,
                     regression_window=100, regression_poly=2, apply_kalman=False)
pipelines.append({
    'name': '6. Full Fourier Optimized',
    'short': 'Full Fourier',
    'config': 'α=2000, SG 11/5, W=100/Quad',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Pipeline 7: Current + Kalman
spr = get_spr_series(alpha=9000, apply_sg=True, sg_window=11, sg_poly=3,
                     regression_window=50, regression_poly=1, apply_kalman=True)
pipelines.append({
    'name': '7. Current + Kalman',
    'short': 'Current+Kal',
    'config': 'α=9000, SG 11/3, W=50/Linear, Kalman',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Pipeline 8: Full optimization (Fourier + Kalman)
spr = get_spr_series(alpha=2000, apply_sg=True, sg_window=11, sg_poly=5,
                     regression_window=100, regression_poly=2, apply_kalman=True)
pipelines.append({
    'name': '8. Full Optimization',
    'short': 'OPTIMIZED',
    'config': 'α=2000, SG 11/5, W=100/Quad, Kalman',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Pipeline 9: Centroid method
spr = get_centroid_series()
pipelines.append({
    'name': '9. Centroid Method',
    'short': 'Centroid',
    'config': 'Center of Mass, Gaussian σ=2.0',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Pipeline 10: Multiparametric (simple version - minimum only)
spr = get_minimum_series()
pipelines.append({
    'name': '10. Simple Minimum',
    'short': 'Minimum',
    'config': 'Simple minimum finding',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Pipeline 11: Consensus (Multi-parametric)
spr = get_consensus_series()
pipelines.append({
    'name': '11. Consensus Multi-parametric',
    'short': 'Consensus',
    'config': '60% Centroid + 40% Parabolic',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Pipeline 12: Adaptive Multi-Feature
spr = get_multifeature_series()
pipelines.append({
    'name': '12. Adaptive Multi-Feature',
    'short': 'Multi-Feature',
    'config': 'SG 11/5+Gauss+Quad Regression+Gauss Fit',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Pipeline 13: Hybrid Fourier + Multi-Feature (no Gaussian refinement)
spr = get_fourier_multifeature_series(alpha=2000, sg_window=11, sg_poly=5, 
                                      regression_window=100, use_gaussian_refinement=False)
pipelines.append({
    'name': '13. Hybrid Fourier+Multi (No Gauss)',
    'short': 'Hybrid-NoG',
    'config': 'α=2000, SG 11/5, Fourier Deriv, W=100/Quad',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# Pipeline 14: Hybrid Fourier + Multi-Feature (with Gaussian refinement)
spr = get_fourier_multifeature_series(alpha=2000, sg_window=11, sg_poly=5, 
                                      regression_window=100, use_gaussian_refinement=True)
pipelines.append({
    'name': '14. Hybrid Fourier+Multi (Full)',
    'short': 'Hybrid-Full',
    'config': 'α=2000, SG 11/5, Fourier, W=100/Quad, Gauss',
    'p2p': np.ptp(spr),
    'std': np.std(spr),
    'series': spr
})

# ============================================================================
# RESULTS
# ============================================================================# ============================================================================
# RESULTS
# ============================================================================
print("\n" + "=" * 80)
print("RESULTS (ALL DETRENDED TO ZERO)")
print("=" * 80)

baseline = pipelines[0]

print("\n📊 ALL PIPELINES (sorted by noise):\n")
sorted_pipelines = sorted(pipelines, key=lambda x: x['p2p'])

for i, pipeline in enumerate(sorted_pipelines):
    improvement = (1 - pipeline['p2p'] / baseline['p2p']) * 100
    marker = "🏆" if i == 0 else "⭐" if i == 1 else "  "
    print(f"{marker} {pipeline['name']:30s}: {pipeline['p2p']:6.2f} RU  ({improvement:+6.1f}%)  [{pipeline['short']}]")

print("\n" + "=" * 80)
print("KEY COMPARISONS")
print("=" * 80)

current = pipelines[0]
best = sorted_pipelines[0]
best_no_kalman = [p for p in sorted_pipelines if 'Kalman' not in p['config']][0]

print(f"\n🔵 CURRENT (Production):")
print(f"   {current['config']}")
print(f"   Noise: {current['p2p']:.2f} RU, Std: {current['std']:.2f} RU")

print(f"\n🟢 BEST WITHOUT KALMAN:")
print(f"   {best_no_kalman['name']}")
print(f"   {best_no_kalman['config']}")
print(f"   Noise: {best_no_kalman['p2p']:.2f} RU, Std: {best_no_kalman['std']:.2f} RU")
print(f"   Improvement: {(1 - best_no_kalman['p2p']/current['p2p'])*100:.1f}%")

print(f"\n🟡 BEST OVERALL:")
print(f"   {best['name']}")
print(f"   {best['config']}")
print(f"   Noise: {best['p2p']:.2f} RU, Std: {best['std']:.2f} RU")
print(f"   Improvement: {(1 - best['p2p']/current['p2p'])*100:.1f}%")

# ============================================================================
# VISUALIZATION
# ============================================================================
fig = plt.figure(figsize=(20, 14))
gs = fig.add_gridspec(4, 3, hspace=0.35, wspace=0.3)

# Plot 1: All pipelines overlay (large)
ax1 = fig.add_subplot(gs[0:2, :])
time_points = np.arange(len(current['series']))
colors = plt.cm.tab20(np.linspace(0, 1, len(pipelines)))  # Use tab20 for more colors

for i, pipeline in enumerate(pipelines):
    alpha_val = 0.9 if 'OPTIMIZED' in pipeline['short'] else 0.5 if 'Current' in pipeline['short'] else 0.6
    linewidth = 3 if 'OPTIMIZED' in pipeline['short'] else 2.5 if 'Current' in pipeline['short'] else 1.5
    ax1.plot(time_points, pipeline['series'], 
             label=f"{pipeline['short']} ({pipeline['p2p']:.2f} RU)",
             color=colors[i], linewidth=linewidth, alpha=alpha_val)

ax1.axhline(y=0, color='black', linestyle=':', linewidth=1.5, alpha=0.5)
ax1.set_xlabel('Time Point (1 Hz sampling)', fontsize=13, fontweight='bold')
ax1.set_ylabel('SPR Signal (RU, detrended)', fontsize=13, fontweight='bold')
ax1.set_title('All Peak Finding Pipelines Comparison (Detrended to Zero)', 
             fontsize=16, fontweight='bold', pad=20)
ax1.legend(fontsize=8, loc='upper right', ncol=3, framealpha=0.95)  # 3 columns for more entries
ax1.grid(True, alpha=0.3)

# Add improvement box
improvement_text = (f"Best: {best['short']}\n"
                   f"{best['p2p']:.2f} RU\n"
                   f"{(1-best['p2p']/current['p2p'])*100:.1f}% improvement")
ax1.text(0.02, 0.98, improvement_text,
         transform=ax1.transAxes, fontsize=12, verticalalignment='top',
         bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.9, pad=0.8))

# Plot 2: Bar chart - all pipelines
ax2 = fig.add_subplot(gs[2, 0])
names = [p['short'] for p in pipelines]
p2p_values = [p['p2p'] for p in pipelines]
colors_bar = ['red' if 'Current' in n else 'darkgreen' if 'OPTIMIZED' in n else 'lightblue' 
              for n in names]
bars = ax2.bar(names, p2p_values, color=colors_bar, edgecolor='black', linewidth=1.5)
ax2.set_ylabel('P2P Noise (RU)', fontweight='bold')
ax2.set_title('Noise Comparison', fontweight='bold')
ax2.grid(True, alpha=0.3, axis='y')
plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=8)

# Annotate bars
for bar in bars:
    height = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2., height,
            f'{height:.1f}', ha='center', va='bottom', fontsize=8, fontweight='bold')

# Plot 3: Improvement percentages
ax3 = fig.add_subplot(gs[2, 1])
improvements = [(1 - p['p2p']/baseline['p2p'])*100 for p in pipelines]
colors_imp = ['red' if imp < 0 else 'green' if imp > 30 else 'orange' for imp in improvements]
bars = ax3.barh(names, improvements, color=colors_imp, edgecolor='black', linewidth=1.5)
ax3.axvline(x=0, color='black', linestyle='-', linewidth=2)
ax3.set_xlabel('Improvement vs Current (%)', fontweight='bold')
ax3.set_title('Relative Improvement', fontweight='bold')
ax3.grid(True, alpha=0.3, axis='x')

# Plot 4: Zoomed comparison (top 3 + current)
ax4 = fig.add_subplot(gs[2, 2])
zoom_range = slice(50, 100)
top_3 = sorted_pipelines[:3]
for pipeline in [current] + top_3:
    if pipeline != current:
        ax4.plot(time_points[zoom_range], pipeline['series'][zoom_range],
                label=f"{pipeline['short']} ({pipeline['p2p']:.2f})",
                linewidth=2, alpha=0.8)
ax4.plot(time_points[zoom_range], current['series'][zoom_range],
        label=f"Current ({current['p2p']:.2f})", linewidth=2, alpha=0.6, color='red', linestyle='--')
ax4.axhline(y=0, color='black', linestyle=':', linewidth=1)
ax4.set_xlabel('Time Point', fontweight='bold')
ax4.set_ylabel('SPR (RU)', fontweight='bold')
ax4.set_title('Zoomed: Points 50-100', fontweight='bold')
ax4.legend(fontsize=8)
ax4.grid(True, alpha=0.3)

# Plot 5: Histogram comparison (current vs best)
ax5 = fig.add_subplot(gs[3, 0])
ax5.hist(current['series'], bins=30, alpha=0.5, label=f"Current (σ={current['std']:.2f})",
        color='red', edgecolor='darkred', linewidth=1.2)
ax5.hist(best['series'], bins=30, alpha=0.6, label=f"Optimized (σ={best['std']:.2f})",
        color='green', edgecolor='darkgreen', linewidth=1.2)
ax5.axvline(x=0, color='black', linestyle=':', linewidth=2)
ax5.set_xlabel('SPR Value (RU)', fontweight='bold')
ax5.set_ylabel('Frequency', fontweight='bold')
ax5.set_title('Noise Distribution', fontweight='bold')
ax5.legend(fontsize=10)
ax5.grid(True, alpha=0.3, axis='y')

# Plot 6: Standard deviation comparison
ax6 = fig.add_subplot(gs[3, 1])
std_values = [p['std'] for p in pipelines]
colors_std = ['red' if 'Current' in n else 'darkgreen' if 'OPTIMIZED' in n else 'lightblue' 
              for n in names]
bars = ax6.bar(names, std_values, color=colors_std, edgecolor='black', linewidth=1.5)
ax6.set_ylabel('Std Dev (RU)', fontweight='bold')
ax6.set_title('Standard Deviation', fontweight='bold')
ax6.grid(True, alpha=0.3, axis='y')
plt.setp(ax6.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=8)

# Plot 7: Summary table
ax7 = fig.add_subplot(gs[3, 2])
ax7.axis('tight')
ax7.axis('off')

table_data = []
table_data.append(['Pipeline', 'P2P (RU)', 'Std (RU)', 'Improv'])
for i, pipeline in enumerate(sorted_pipelines[:5]):
    improvement = (1 - pipeline['p2p']/baseline['p2p'])*100
    table_data.append([
        pipeline['short'],
        f"{pipeline['p2p']:.2f}",
        f"{pipeline['std']:.2f}",
        f"{improvement:+.1f}%"
    ])

table = ax7.table(cellText=table_data, cellLoc='center', loc='center',
                 colWidths=[0.4, 0.2, 0.2, 0.2])
table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1, 2)

# Style header row
for i in range(4):
    table[(0, i)].set_facecolor('#4CAF50')
    table[(0, i)].set_text_props(weight='bold', color='white')

# Style first row (best)
for i in range(4):
    table[(1, i)].set_facecolor('#C8E6C9')

ax7.set_title('Top 5 Pipelines', fontweight='bold', pad=20)

plt.savefig('all_pipelines_comparison_detrended.png', dpi=150, bbox_inches='tight')
print("\n[OK] Plot saved to: all_pipelines_comparison_detrended.png")

print("\n" + "=" * 80)
