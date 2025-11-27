"""
Test Fourier zero-crossing refinement combined with batch strategies

The Fourier zero-crossing is applied DURING peak detection (on each spectrum).
The batch strategies are applied AFTER detection (on the wavelength time series).

This tests if the Fourier refinement improves the input to batch processing.
"""

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from scipy.fft import dst, idct
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.pipelines.fourier_pipeline import FourierPipeline
from utils.pipelines.direct_argmin_pipeline import DirectArgminPipeline

# SPR simulation parameters
SPR_CENTER = 646.5
SPR_WIDTH = 10.0
WAVELENGTH_RANGE = (560, 720)
NUM_PIXELS = 3648

def create_mock_spectrum(wavelength_nm):
    wavelengths = np.linspace(WAVELENGTH_RANGE[0], WAVELENGTH_RANGE[1], NUM_PIXELS)
    width = SPR_WIDTH / 2.355
    baseline = 90.0
    depth = 60.0
    transmission = baseline - depth / (1 + ((wavelengths - wavelength_nm) / width)**2)
    return transmission, wavelengths


def load_baseline_data():
    baseline_file = "src/baseline_data/baseline_wavelengths_20251127_013519.csv"
    if not os.path.exists(baseline_file):
        return None
    
    df = pd.read_csv(baseline_file)
    wavelength_data = df['channel_a'].values
    
    print(f"✅ Loaded {len(wavelength_data)} baseline data points")
    return wavelength_data


def detect_wavelengths(wavelength_data, pipeline_class):
    """Detect wavelengths using specified pipeline"""
    pipeline = pipeline_class()
    detected = []
    
    for true_wl in wavelength_data:
        transmission, wavelengths = create_mock_spectrum(true_wl)
        detected_wl = pipeline.find_resonance_wavelength(transmission, wavelengths)
        detected.append(float(detected_wl) if detected_wl is not None else np.nan)
    
    return np.array(detected, dtype=float)[~np.isnan(np.array(detected, dtype=float))]


def batch_mean(data, batch_size=3):
    """Simple batch mean"""
    result = []
    for i in range(0, len(data) - batch_size + 1, batch_size):
        result.append(np.mean(data[i:i+batch_size]))
    return np.array(result)


def batch_then_savgol(data, batch_size=3, savgol_window=7):
    """Batch mean, then Savgol"""
    batched = batch_mean(data, batch_size)
    if len(batched) >= savgol_window:
        return savgol_filter(batched, window_length=savgol_window, polyorder=2)
    return batched


def kalman_filter_tight(data, process_var=1e-6, measurement_var=1e-4):
    """Tight Kalman filter"""
    estimate = data[0]
    estimate_error = 1.0
    result = []
    
    for measurement in data:
        prediction = estimate
        prediction_error = estimate_error + process_var
        kalman_gain = prediction_error / (prediction_error + measurement_var)
        estimate = prediction + kalman_gain * (measurement - prediction)
        estimate_error = (1 - kalman_gain) * prediction_error
        result.append(estimate)
    
    return np.array(result)


def exponential_smoothing(data, alpha=0.2):
    """Exponential smoothing"""
    result = [data[0]]
    for i in range(1, len(data)):
        result.append(alpha * data[i] + (1 - alpha) * result[-1])
    return np.array(result)


def calculate_stats(data, name):
    if len(data) == 0:
        return None
    valid = data[~np.isnan(data)]
    return {
        'name': name,
        'points': len(valid),
        'peak_to_peak_pm': np.ptp(valid) * 1000,
        'std_pm': np.std(valid) * 1000,
    }


def main():
    print("\n" + "="*80)
    print("🔬 FOURIER ZERO-CROSSING + BATCH STRATEGIES")
    print("="*80)
    
    wavelength_data = load_baseline_data()
    if wavelength_data is None:
        return
    
    print(f"📊 Raw Input: P2P={np.ptp(wavelength_data)*1000:.3f} pm\n")
    
    # Test both pipelines
    pipelines = [
        ("Fourier (with zero-crossing)", FourierPipeline),
        ("Direct ArgMin (no Fourier)", DirectArgminPipeline),
    ]
    
    all_results = []
    
    for pipeline_name, pipeline_class in pipelines:
        print(f"\n{'='*80}")
        print(f"PIPELINE: {pipeline_name}")
        print('='*80)
        
        # Detect wavelengths
        detected = detect_wavelengths(wavelength_data, pipeline_class)
        print(f"✅ Detected {len(detected)} wavelengths")
        
        # Test strategies on this pipeline's output
        strategies = [
            ("Raw", lambda d: d),
            ("Batch Mean (n=3)", lambda d: batch_mean(d, 3)),
            ("Batch → Savgol(7)", lambda d: batch_then_savgol(d, 3, 7)),
            ("Batch → Savgol(5)", lambda d: batch_then_savgol(d, 3, 5)),
            ("Kalman (tight)", lambda d: kalman_filter_tight(d)),
            ("Exponential α=0.2", lambda d: exponential_smoothing(d, 0.2)),
            ("Post-Savgol(11)", lambda d: savgol_filter(d, 11, 2) if len(d) >= 11 else d),
        ]
        
        for strategy_name, strategy_func in strategies:
            result_data = strategy_func(detected)
            stats = calculate_stats(result_data, f"{pipeline_name} + {strategy_name}")
            if stats:
                all_results.append(stats)
                print(f"  {strategy_name:25s} P2P={stats['peak_to_peak_pm']:7.3f} pm, "
                      f"Std={stats['std_pm']:6.3f} pm, N={stats['points']:3d}")
    
    # Overall ranking
    print(f"\n{'='*80}")
    print("🏆 OVERALL RANKING (All Combinations)")
    print('='*80)
    
    df = pd.DataFrame(all_results)
    df_sorted = df.sort_values('peak_to_peak_pm')
    
    for i, row in df_sorted.head(10).iterrows():
        print(f"{df_sorted.index.get_loc(i)+1:2d}. {row['name']:60s} {row['peak_to_peak_pm']:7.3f} pm")
    
    # Best per category
    print(f"\n{'='*80}")
    print("📊 ANALYSIS")
    print('='*80)
    
    # Best Fourier combination
    fourier_results = df_sorted[df_sorted['name'].str.contains("Fourier")]
    best_fourier = fourier_results.iloc[0]
    
    # Best Direct combination
    direct_results = df_sorted[df_sorted['name'].str.contains("Direct")]
    best_direct = direct_results.iloc[0]
    
    print(f"\nBest with Fourier zero-crossing:")
    print(f"  {best_fourier['name']}")
    print(f"  P2P: {best_fourier['peak_to_peak_pm']:.3f} pm")
    
    print(f"\nBest with Direct ArgMin (no Fourier):")
    print(f"  {best_direct['name']}")
    print(f"  P2P: {best_direct['peak_to_peak_pm']:.3f} pm")
    
    improvement = (best_direct['peak_to_peak_pm'] - best_fourier['peak_to_peak_pm'])
    print(f"\n✨ Fourier advantage: {improvement:.3f} pm better ({improvement/best_direct['peak_to_peak_pm']*100:.1f}% improvement)")
    
    # Recommendation
    print(f"\n{'='*80}")
    print("💡 RECOMMENDATION")
    print('='*80)
    
    overall_best = df_sorted.iloc[0]
    print(f"🥇 Use: {overall_best['name']}")
    print(f"   Peak-to-Peak: {overall_best['peak_to_peak_pm']:.3f} pm")
    print(f"   Std Dev:      {overall_best['std_pm']:.3f} pm")
    print(f"   Output rate:  {overall_best['points']} points")
    
    # Check if it's Fourier-based
    if "Fourier" in overall_best['name']:
        print(f"\n✅ Fourier zero-crossing DOES improve performance!")
        print(f"   Keep using Fourier pipeline with your batch strategy.")
    else:
        print(f"\n⚠️  Direct ArgMin performs better with this batch strategy")
        print(f"   Consider switching from Fourier to Direct ArgMin pipeline.")
    
    df.to_csv('fourier_batch_combination_results.csv', index=False)
    print(f"\n💾 Results saved to: fourier_batch_combination_results.csv")


if __name__ == '__main__':
    main()
