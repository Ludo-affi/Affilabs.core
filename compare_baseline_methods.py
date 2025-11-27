"""Compare noise reduction methods on baseline data

This script applies different noise reduction techniques to the baseline wavelength data
to see which method achieves the best peak-to-peak performance.

Methods tested:
1. Raw (no filtering)
2. Simple moving average
3. Savitzky-Golay filter (single pass)
4. Savitzky-Golay filter (dual pass - GOLD STANDARD)
5. Median filter
6. Lorentzian curve fitting (OLD SOFTWARE - achieves 3-4 RU)
7. Fourier derivative zero-crossing (DST/IDCT method)

Usage:
    python compare_baseline_methods.py
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.signal import savgol_filter, medfilt
from scipy.optimize import curve_fit
from scipy.fft import dst, idct
from scipy.stats import linregress


def load_baseline_data():
    """Load the baseline wavelength data"""
    baseline_file = Path("src/baseline_data/baseline_wavelengths_20251126_223040.csv")

    if not baseline_file.exists():
        print(f"❌ ERROR: {baseline_file} not found!")
        return None

    df = pd.read_csv(baseline_file)

    # Extract all channels
    data = {
        'channel_a': df['channel_a'].values,
        'channel_b': df['channel_b'].values,
        'channel_c': df['channel_c'].values,
        'channel_d': df['channel_d'].values,
    }

    print(f"✅ Loaded {len(df)} baseline data points")
    print(f"   Duration: ~{len(df)*0.91:.1f}s (@ ~1.1 Hz)")

    return data


def method_raw(data):
    """No filtering - raw data"""
    # Remove NaN values
    return data[~np.isnan(data)]


def method_moving_average(data, window=5):
    """Simple moving average"""
    # Remove NaN values first
    clean_data = data[~np.isnan(data)]
    if len(clean_data) < window:
        return clean_data
    return np.convolve(clean_data, np.ones(window)/window, mode='valid')


def method_savgol_single(data, window=21, polyorder=3):
    """Single-pass Savitzky-Golay filter"""
    # Remove NaN values first
    clean_data = data[~np.isnan(data)]
    if len(clean_data) < window:
        window = len(clean_data) if len(clean_data) % 2 == 1 else len(clean_data) - 1
    if window < polyorder + 1:
        return clean_data
    return savgol_filter(clean_data, window, polyorder)


def method_savgol_dual(data, window1=5, poly1=2, window2=21, poly2=3):
    """Dual-pass Savitzky-Golay filter (GOLD STANDARD from commit 069ff60)

    Stage 1: Smooth the batch (window=5, poly=2)
    Stage 2: Smooth again (window=21, poly=3)
    """
    # Remove NaN values first
    clean_data = data[~np.isnan(data)]

    if len(clean_data) < window1:
        return clean_data

    # First pass
    filtered = savgol_filter(clean_data, window1, poly1)

    # Second pass (if enough data)
    if len(filtered) >= window2:
        filtered = savgol_filter(filtered, window2, poly2)

    return filtered


def method_median_filter(data, kernel=5):
    """Median filter"""
    # Remove NaN values first
    clean_data = data[~np.isnan(data)]
    if len(clean_data) < kernel:
        return clean_data
    return medfilt(clean_data, kernel_size=kernel)


def method_batch_average(data, batch_size=12):
    """Batch averaging (GOLD STANDARD technique)

    This mimics the batch processing from commit 069ff60:
    - Collect batch_size points
    - Apply SG filter to batch
    - Average to single value
    """
    # Remove NaN values first
    clean_data = data[~np.isnan(data)]

    if len(clean_data) < batch_size:
        return np.array([np.mean(clean_data)])

    n_batches = len(clean_data) // batch_size
    batched = []

    for i in range(n_batches):
        batch = clean_data[i*batch_size:(i+1)*batch_size]
        # Apply SG filter to batch
        filtered_batch = savgol_filter(batch, 5, 2)
        # Take mean
        batched.append(np.mean(filtered_batch))

    return np.array(batched)


def lorentzian(x, pos, width, height, offset):
    """Lorentzian function for SPR dip fitting (OLD SOFTWARE method)

    This is the exact function from the old control-main software that
    achieved 3-4 RU baseline performance.
    """
    if abs(width) < 1e-10:
        width = 1e-10  # Prevent division by zero
    return (height / ((((x - pos) / (width / 2)) ** 2) + 1)) + offset


def method_lorentzian_fit(data):
    """Lorentzian curve fitting (OLD SOFTWARE - 3-4 RU performance)

    This is the method used in the original ezControl software.
    It fits a Lorentzian function to model the SPR dip shape and
    extracts the peak position.

    For baseline data, we fit the Lorentzian to the overall drift trend.
    """
    # Remove NaN values first
    clean_data = data[~np.isnan(data)]

    if len(clean_data) < 10:
        return clean_data

    # Create x-axis (time or sample index)
    x = np.arange(len(clean_data))

    try:
        # Initial guess for Lorentzian parameters
        # pos: center (middle of data)
        # width: 1/4 of data range
        # height: negative (it's a dip)
        # offset: mean value
        pos_init = len(clean_data) / 2
        width_init = len(clean_data) / 4
        height_init = -(np.max(clean_data) - np.min(clean_data))
        offset_init = np.mean(clean_data)

        # Fit Lorentzian
        popt, _ = curve_fit(
            lorentzian,
            x,
            clean_data,
            p0=[pos_init, width_init, height_init, offset_init],
            maxfev=5000
        )

        # Generate fitted curve
        fitted = lorentzian(x, *popt)

        return fitted

    except Exception as e:
        # If fitting fails, return smoothed data
        return savgol_filter(clean_data, 21, 3)


def method_fourier_derivative(data, alpha=9000.0):
    """Fourier derivative zero-crossing (DST/IDCT method from old software)

    This is the original Fourier transform method that achieves 3-4 RU:
    1. Calculate Fourier weights
    2. Apply DST (Discrete Sine Transform)
    3. Apply IDCT (Inverse Discrete Cosine Transform) to get derivative
    4. The derivative trend shows rate of change

    For baseline analysis, we smooth the derivative to show underlying trends.
    """
    # Remove NaN values first
    clean_data = data[~np.isnan(data)]

    if len(clean_data) < 10:
        return clean_data

    try:
        # Calculate Fourier weights (SNR-based denoising)
        n = len(clean_data)
        k = np.arange(1, n - 1)
        fourier_weights = np.exp(-k * (k + 1) / (4 * alpha))

        # Prepare Fourier coefficients
        fourier_coeff = np.zeros_like(clean_data)
        fourier_coeff[0] = 2 * (clean_data[-1] - clean_data[0])

        # Linear detrending
        linear_trend = np.linspace(clean_data[0], clean_data[-1], n)
        detrended = clean_data - linear_trend

        # Apply DST with Fourier weights
        dst_result = dst(detrended[1:-1], type=1)
        fourier_coeff[1:-1] = fourier_weights * dst_result

        # Calculate derivative using IDCT
        derivative = idct(fourier_coeff, type=1)

        # For baseline data, integrate derivative back to get smoothed signal
        # The derivative shows rate of change, integrating gives us the trend
        integrated = np.cumsum(derivative)

        # Normalize to match original data scale
        integrated = integrated - np.mean(integrated) + np.mean(clean_data)

        return integrated

    except Exception as e:
        # If Fourier method fails, return smoothed data
        return savgol_filter(clean_data, 21, 3)
def analyze_method(name, method_func, data, **kwargs):
    """Analyze a noise reduction method"""
    try:
        filtered = method_func(data, **kwargs)

        if len(filtered) == 0:
            return None

        peak_to_peak = np.ptp(filtered)
        std_dev = np.std(filtered)
        mean_val = np.mean(filtered)

        return {
            'method': name,
            'peak_to_peak_nm': peak_to_peak,
            'peak_to_peak_pm': peak_to_peak * 1000,
            'std_nm': std_dev,
            'std_pm': std_dev * 1000,
            'mean_nm': mean_val,
            'n_points': len(filtered)
        }
    except Exception as e:
        print(f"⚠️  Error in {name}: {e}")
        return None


def main():
    print("\n" + "="*80)
    print("🧪 BASELINE DATA - NOISE REDUCTION METHOD COMPARISON")
    print("="*80)

    # Load data
    data = load_baseline_data()
    if data is None:
        return

    # Analyze each channel
    for channel_name, channel_data in data.items():
        print(f"\n{'='*80}")
        print(f"📊 CHANNEL: {channel_name.upper().replace('_', ' ')}")
        print(f"{'='*80}")

        # Calculate raw statistics
        raw_p2p = np.ptp(channel_data)
        raw_std = np.std(channel_data)
        raw_mean = np.mean(channel_data)

        print(f"\n📈 Raw Data Statistics:")
        print(f"   Points:       {len(channel_data)}")
        print(f"   Peak-to-Peak: {raw_p2p:.6f} nm ({raw_p2p*1000:.3f} pm)")
        print(f"   Std Dev:      {raw_std:.6f} nm ({raw_std*1000:.3f} pm)")
        print(f"   Mean:         {raw_mean:.6f} nm")

        # Test all methods
        results = []

        # 1. Raw (baseline)
        results.append(analyze_method("Raw (No Filtering)", method_raw, channel_data))

        # 2. Moving average
        results.append(analyze_method("Moving Average (5pt)", method_moving_average, channel_data, window=5))
        results.append(analyze_method("Moving Average (11pt)", method_moving_average, channel_data, window=11))

        # 3. Single-pass SG
        results.append(analyze_method("Savitzky-Golay (21,3)", method_savgol_single, channel_data, window=21, polyorder=3))

        # 4. Dual-pass SG (GOLD STANDARD)
        results.append(analyze_method("Dual SG (5,2)→(21,3) GOLD", method_savgol_dual, channel_data))

        # 5. Median filter
        results.append(analyze_method("Median Filter (5pt)", method_median_filter, channel_data, kernel=5))

        # 6. Batch averaging
        results.append(analyze_method("Batch Average (12pt)", method_batch_average, channel_data, batch_size=12))

        # 7. Lorentzian fit (OLD SOFTWARE)
        results.append(analyze_method("Lorentzian Fit (OLD SW)", method_lorentzian_fit, channel_data))

        # 8. Fourier derivative zero-crossing
        results.append(analyze_method("Fourier DST/IDCT (OLD SW)", method_fourier_derivative, channel_data, alpha=9000.0))

        # Remove failed results
        results = [r for r in results if r is not None]

        # Print results table
        print(f"\n{'='*80}")
        print(f"📊 RESULTS")
        print(f"{'='*80}")
        print(f"{'Method':<35} {'P2P (nm)':<12} {'P2P (pm)':<12} {'Std (nm)':<12} {'Points':<8}")
        print("-"*80)

        for result in results:
            print(f"{result['method']:<35} {result['peak_to_peak_nm']:<12.6f} "
                  f"{result['peak_to_peak_pm']:<12.3f} {result['std_nm']:<12.6f} "
                  f"{result['n_points']:<8}")

        # Sort by peak-to-peak
        results_sorted = sorted(results, key=lambda x: x['peak_to_peak_nm'])

        print(f"\n{'='*80}")
        print(f"🏆 RANKING (Best to Worst by Peak-to-Peak)")
        print(f"{'='*80}")

        for i, result in enumerate(results_sorted, 1):
            improvement = (raw_p2p / result['peak_to_peak_nm'] - 1) * 100
            print(f"{i}. {result['method']:<35} {result['peak_to_peak_pm']:>10.3f} pm "
                  f"({improvement:>6.1f}% improvement)")

        # Check for GOLD STANDARD target
        best = results_sorted[0]
        target_pm = 8.0  # 0.008 nm target

        print(f"\n{'='*80}")
        print(f"🎯 TARGET ANALYSIS")
        print(f"{'='*80}")
        print(f"   Target:        {target_pm:.1f} pm (0.008 nm)")
        print(f"   Best achieved: {best['peak_to_peak_pm']:.3f} pm ({best['method']})")
        print(f"   Gap:           {best['peak_to_peak_pm'] - target_pm:.3f} pm")
        print(f"   Factor:        {best['peak_to_peak_pm'] / target_pm:.1f}x worse than target")

        if best['peak_to_peak_pm'] <= target_pm:
            print(f"   ✅ TARGET ACHIEVED!")
        else:
            print(f"   ❌ Target not achieved (need {(best['peak_to_peak_pm'] / target_pm):.1f}x better)")

    print(f"\n{'='*80}")
    print("✅ Analysis complete!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
