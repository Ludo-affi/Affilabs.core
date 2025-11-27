"""
Test peak detection with realistic batch=12 constraint (3 points per channel)

Simulates the real acquisition pattern where we collect 12 spectra total,
cycling through 4 channels, giving us 3 points per channel before processing.

Tests:
1. Raw (no batching) - baseline
2. Mean of 3 points - simple average
3. Median of 3 points - robust average
4. Linear fit of 3 points - trend extraction
5. Post-process full history with different Savgol windows

Goal: Find best method given the 3-point constraint
"""

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.pipelines.fourier_pipeline import FourierPipeline
from utils.pipelines.direct_argmin_pipeline import DirectArgminPipeline

# SPR simulation parameters
SPR_CENTER = 646.5  # nm
SPR_WIDTH = 10.0    # nm (FWHM)
WAVELENGTH_RANGE = (560, 720)  # nm
NUM_PIXELS = 3648

def create_mock_spectrum(wavelength_nm):
    """Create a synthetic SPR spectrum centered at wavelength_nm"""
    wavelengths = np.linspace(WAVELENGTH_RANGE[0], WAVELENGTH_RANGE[1], NUM_PIXELS)
    
    # Lorentzian dip
    width = SPR_WIDTH / 2.355  # Convert FWHM to width parameter
    baseline = 90.0  # % transmission baseline
    depth = 60.0  # % transmission dip depth
    
    transmission = baseline - depth / (1 + ((wavelengths - wavelength_nm) / width)**2)
    
    return transmission, wavelengths


def load_baseline_data():
    """Load baseline wavelength data from CSV"""
    baseline_file = "src/baseline_data/baseline_wavelengths_20251127_013519.csv"
    
    if not os.path.exists(baseline_file):
        print(f"❌ ERROR: Baseline file not found: {baseline_file}")
        return None
    
    df = pd.read_csv(baseline_file)
    wavelength_data = df['channel_a'].values
    timestamps = df['timestamp_a'].values
    duration = timestamps[-1] - timestamps[0]
    
    print(f"✅ Loaded {len(wavelength_data)} baseline data points (Channel A)")
    print(f"   Time range: {timestamps[0]:.2f}s to {timestamps[-1]:.2f}s")
    print(f"   Duration: {duration:.2f}s")
    print(f"   Acquisition rate: {len(wavelength_data)/duration:.2f} Hz")
    
    return wavelength_data


def detect_wavelengths(wavelength_data, pipeline_class):
    """Detect wavelengths for all data points"""
    pipeline = pipeline_class()
    detected = []
    
    for true_wl in wavelength_data:
        transmission, wavelengths = create_mock_spectrum(true_wl)
        detected_wl = pipeline.find_resonance_wavelength(transmission, wavelengths)
        
        if detected_wl is None:
            detected.append(np.nan)
        else:
            detected.append(float(detected_wl))
    
    return np.array(detected, dtype=float)


def test_batch_3_mean(detected_wavelengths):
    """Batch method: Mean of 3 consecutive points"""
    result = []
    for i in range(0, len(detected_wavelengths) - 2, 3):
        batch = detected_wavelengths[i:i+3]
        result.append(np.mean(batch))
    
    return np.array(result)


def test_batch_3_median(detected_wavelengths):
    """Batch method: Median of 3 consecutive points"""
    result = []
    for i in range(0, len(detected_wavelengths) - 2, 3):
        batch = detected_wavelengths[i:i+3]
        result.append(np.median(batch))
    
    return np.array(result)


def test_batch_3_linear(detected_wavelengths):
    """Batch method: Linear fit midpoint of 3 consecutive points"""
    result = []
    for i in range(0, len(detected_wavelengths) - 2, 3):
        batch = detected_wavelengths[i:i+3]
        # Fit line to 3 points, return center point
        x = np.array([0, 1, 2])
        coeffs = np.polyfit(x, batch, 1)
        midpoint = np.polyval(coeffs, 1)  # Evaluate at x=1 (center)
        result.append(midpoint)
    
    return np.array(result)


def test_post_savgol(detected_wavelengths, window_length, polyorder=2):
    """Post-processing: Savgol on full time series"""
    if len(detected_wavelengths) < window_length:
        return detected_wavelengths
    
    return savgol_filter(detected_wavelengths, window_length=window_length, polyorder=polyorder)


def calculate_stats(data, name):
    """Calculate and return statistics"""
    valid_data = data[~np.isnan(data)]
    
    if len(valid_data) == 0:
        return None
    
    p2p = np.ptp(valid_data)
    std = np.std(valid_data)
    mean = np.mean(valid_data)
    
    return {
        'name': name,
        'points': len(valid_data),
        'peak_to_peak_pm': p2p * 1000,
        'std_pm': std * 1000,
        'mean_nm': mean
    }


def main():
    print("\n" + "="*80)
    print("🧪 BATCH=12 CONSTRAINT TEST (3 points per channel)")
    print("="*80)
    
    # Load data
    wavelength_data = load_baseline_data()
    if wavelength_data is None:
        return
    
    print(f"\n📊 Raw Input Statistics:")
    print(f"   Peak-to-Peak: {np.ptp(wavelength_data)*1000:.3f} pm")
    print(f"   Std Dev:      {np.std(wavelength_data)*1000:.3f} pm")
    
    # Detect wavelengths using Fourier pipeline
    print(f"\n🔍 Detecting wavelengths with Fourier pipeline...")
    detected = detect_wavelengths(wavelength_data, FourierPipeline)
    
    valid_mask = ~np.isnan(detected)
    detected = detected[valid_mask]
    
    print(f"✅ Detected {len(detected)} valid wavelengths")
    
    results = []
    
    # Test 1: Raw (no processing)
    print(f"\n{'='*80}")
    print("TEST 1: RAW (No Batching)")
    print('='*80)
    stats = calculate_stats(detected, "Raw (No Batching)")
    if stats:
        results.append(stats)
        print(f"P2P: {stats['peak_to_peak_pm']:.3f} pm, Std: {stats['std_pm']:.3f} pm")
    
    # Test 2: Batch mean (3 points)
    print(f"\n{'='*80}")
    print("TEST 2: BATCH MEAN (3 consecutive points)")
    print('='*80)
    batch_mean = test_batch_3_mean(detected)
    stats = calculate_stats(batch_mean, "Batch Mean (n=3)")
    if stats:
        results.append(stats)
        print(f"P2P: {stats['peak_to_peak_pm']:.3f} pm, Std: {stats['std_pm']:.3f} pm")
        print(f"Output rate: {stats['points']} points (every ~5 seconds)")
    
    # Test 3: Batch median (3 points)
    print(f"\n{'='*80}")
    print("TEST 3: BATCH MEDIAN (3 consecutive points)")
    print('='*80)
    batch_median = test_batch_3_median(detected)
    stats = calculate_stats(batch_median, "Batch Median (n=3)")
    if stats:
        results.append(stats)
        print(f"P2P: {stats['peak_to_peak_pm']:.3f} pm, Std: {stats['std_pm']:.3f} pm")
    
    # Test 4: Batch linear fit (3 points)
    print(f"\n{'='*80}")
    print("TEST 4: BATCH LINEAR FIT (3 consecutive points)")
    print('='*80)
    batch_linear = test_batch_3_linear(detected)
    stats = calculate_stats(batch_linear, "Batch Linear Fit (n=3)")
    if stats:
        results.append(stats)
        print(f"P2P: {stats['peak_to_peak_pm']:.3f} pm, Std: {stats['std_pm']:.3f} pm")
    
    # Test 5-8: Post-processing Savgol (different windows)
    savgol_windows = [5, 7, 9, 11]
    
    for window in savgol_windows:
        print(f"\n{'='*80}")
        print(f"TEST: POST-PROCESS SAVGOL (window={window}, poly=2)")
        print('='*80)
        smoothed = test_post_savgol(detected, window_length=window, polyorder=2)
        stats = calculate_stats(smoothed, f"Post-Savgol (w={window}, p=2)")
        if stats:
            results.append(stats)
            lag_seconds = window * (299.11 / len(wavelength_data))
            print(f"P2P: {stats['peak_to_peak_pm']:.3f} pm, Std: {stats['std_pm']:.3f} pm")
            print(f"Lag: ~{lag_seconds:.1f} seconds")
    
    # Summary table
    print(f"\n{'='*80}")
    print("📊 SUMMARY - ALL METHODS")
    print('='*80)
    
    df = pd.DataFrame(results)
    df_sorted = df.sort_values('peak_to_peak_pm')
    
    print("\n" + df_sorted.to_string(index=False))
    
    # Find best method
    best = df_sorted.iloc[0]
    print(f"\n{'='*80}")
    print("🏆 BEST METHOD")
    print('='*80)
    print(f"Method: {best['name']}")
    print(f"Peak-to-Peak: {best['peak_to_peak_pm']:.3f} pm")
    print(f"Std Dev:      {best['std_pm']:.3f} pm")
    print(f"Output points: {int(best['points'])}")
    
    # Calculate improvement
    raw_stats = df[df['name'] == "Raw (No Batching)"].iloc[0]
    improvement = (raw_stats['peak_to_peak_pm'] - best['peak_to_peak_pm']) / raw_stats['peak_to_peak_pm'] * 100
    reduction = raw_stats['peak_to_peak_pm'] / best['peak_to_peak_pm']
    
    print(f"\nImprovement over raw: {improvement:.1f}% ({reduction:.1f}x reduction)")
    
    # Recommendation
    print(f"\n{'='*80}")
    print("💡 RECOMMENDATION")
    print('='*80)
    
    if "Batch" in best['name']:
        print("✅ Use batch processing (3-point groups)")
        print("   - Reduces output rate by 3x (every ~5 seconds)")
        print("   - Simple to implement (mean/median/linear fit)")
    else:
        print("✅ Use post-processing Savgol filter")
        print("   - Maintains high output rate")
        print("   - Requires buffering for larger windows")
        print(f"   - Optimal window: {best['name'].split('=')[1].split(',')[0]} points")
    
    # Save results
    df.to_csv('batch_12_constraint_results.csv', index=False)
    print(f"\n💾 Results saved to: batch_12_constraint_results.csv")


if __name__ == '__main__':
    main()
