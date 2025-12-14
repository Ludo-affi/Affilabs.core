"""
Optimize Savitzky-Golay parameters for best noise reduction

Test different combinations of:
- Window length (5, 7, 9, 11, 15, 21, 31, 51)
- Polynomial order (2, 3, 4)

Goal: Achieve <5 pm peak-to-peak variation (10x improvement from current 51 pm)
"""

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
import sys
import os

# Add src to path
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

    # Get time info
    timestamps = df['timestamp_a'].values
    duration = timestamps[-1] - timestamps[0]

    print(f"✅ Loaded {len(wavelength_data)} baseline data points (Channel A)")
    print(f"   Time range: {timestamps[0]:.2f}s to {timestamps[-1]:.2f}s")
    print(f"   Duration: {duration:.2f}s")

    return wavelength_data


def test_savgol_params(wavelength_data, pipeline_class, window_length, polyorder):
    """Test specific Savgol parameters

    Returns: dict with statistics
    """
    pipeline = pipeline_class()

    # Process each data point
    raw_wavelengths = []

    for true_wl in wavelength_data:
        transmission, wavelengths = create_mock_spectrum(true_wl)
        detected_wl = pipeline.find_resonance_wavelength(transmission, wavelengths)

        if detected_wl is None:
            raw_wavelengths.append(np.nan)
        else:
            raw_wavelengths.append(float(detected_wl))

    raw_wavelengths = np.array(raw_wavelengths, dtype=float)
    valid_mask = ~np.isnan(raw_wavelengths)
    raw_wavelengths = raw_wavelengths[valid_mask]

    if len(raw_wavelengths) < window_length:
        return None

    # Apply Savgol smoothing
    smoothed = savgol_filter(raw_wavelengths, window_length=window_length, polyorder=polyorder)

    # Calculate statistics
    p2p = np.ptp(smoothed)
    std = np.std(smoothed)
    mean = np.mean(smoothed)

    return {
        'window_length': window_length,
        'polyorder': polyorder,
        'peak_to_peak_pm': p2p * 1000,
        'std_pm': std * 1000,
        'mean_nm': mean
    }


def main():
    print("\n" + "="*80)
    print("🔬 SAVITZKY-GOLAY PARAMETER OPTIMIZATION")
    print("="*80)

    # Load data
    wavelength_data = load_baseline_data()
    if wavelength_data is None:
        return

    print(f"\n📊 Raw Input Statistics:")
    print(f"   Peak-to-Peak: {np.ptp(wavelength_data)*1000:.3f} pm")
    print(f"   Std Dev:      {np.std(wavelength_data)*1000:.3f} pm")

    # Test window lengths and polynomial orders
    window_lengths = [51, 71, 101, 121, 141, 161, 181]
    polyorders = [2, 3, 4, 5]

    print(f"\n🧪 Testing {len(window_lengths)} window lengths × {len(polyorders)} polynomial orders = {len(window_lengths)*len(polyorders)} combinations")
    print(f"   Window lengths: {window_lengths}")
    print(f"   Polynomial orders: {polyorders}")
    print(f"   🎯 TARGET: <16.6 pm (10x from 166 pm raw)")


    # Test with Fourier pipeline (current default)
    print(f"\n{'='*80}")
    print("FOURIER PIPELINE + SAVGOL POST-PROCESSING")
    print('='*80)

    results_fourier = []

    for window_length in window_lengths:
        for polyorder in polyorders:
            if polyorder >= window_length:
                continue  # Invalid combination

            result = test_savgol_params(wavelength_data, FourierPipeline, window_length, polyorder)
            if result is not None:
                results_fourier.append(result)
                print(f"Window={window_length:3d}, Poly={polyorder}, P2P={result['peak_to_peak_pm']:7.3f} pm, Std={result['std_pm']:6.3f} pm")

    # Test with Direct ArgMin (simplest/fastest)
    print(f"\n{'='*80}")
    print("DIRECT ARGMIN PIPELINE + SAVGOL POST-PROCESSING")
    print('='*80)

    results_direct = []

    for window_length in window_lengths:
        for polyorder in polyorders:
            if polyorder >= window_length:
                continue

            result = test_savgol_params(wavelength_data, DirectArgminPipeline, window_length, polyorder)
            if result is not None:
                results_direct.append(result)
                print(f"Window={window_length:3d}, Poly={polyorder}, P2P={result['peak_to_peak_pm']:7.3f} pm, Std={result['std_pm']:6.3f} pm")

    # Find best results
    print(f"\n{'='*80}")
    print("🏆 TOP 10 CONFIGURATIONS (Fourier Pipeline)")
    print('='*80)

    df_fourier = pd.DataFrame(results_fourier)
    df_fourier_sorted = df_fourier.sort_values('peak_to_peak_pm')
    print(df_fourier_sorted.head(10).to_string(index=False))

    best_fourier = df_fourier_sorted.iloc[0]
    print(f"\n⭐ BEST FOURIER: Window={int(best_fourier['window_length'])}, Poly={int(best_fourier['polyorder'])}")
    print(f"   Peak-to-Peak: {best_fourier['peak_to_peak_pm']:.3f} pm")
    print(f"   Std Dev:      {best_fourier['std_pm']:.3f} pm")

    print(f"\n{'='*80}")
    print("🏆 TOP 10 CONFIGURATIONS (Direct ArgMin Pipeline)")
    print('='*80)

    df_direct = pd.DataFrame(results_direct)
    df_direct_sorted = df_direct.sort_values('peak_to_peak_pm')
    print(df_direct_sorted.head(10).to_string(index=False))

    best_direct = df_direct_sorted.iloc[0]
    print(f"\n⭐ BEST DIRECT: Window={int(best_direct['window_length'])}, Poly={int(best_direct['polyorder'])}")
    print(f"   Peak-to-Peak: {best_direct['peak_to_peak_pm']:.3f} pm")
    print(f"   Std Dev:      {best_direct['std_pm']:.3f} pm")

    # Calculate improvement
    raw_p2p = np.ptp(wavelength_data) * 1000
    best_p2p = min(best_fourier['peak_to_peak_pm'], best_direct['peak_to_peak_pm'])
    improvement = (raw_p2p - best_p2p) / raw_p2p * 100
    reduction_factor = raw_p2p / best_p2p

    print(f"\n{'='*80}")
    print(f"📈 OVERALL IMPROVEMENT")
    print('='*80)
    print(f"   Raw P2P:      {raw_p2p:.3f} pm")
    print(f"   Best P2P:     {best_p2p:.3f} pm")
    print(f"   Improvement:  {improvement:.1f}%")
    print(f"   Reduction:    {reduction_factor:.1f}x")

    if best_p2p < 5.0:
        print(f"\n🎉 TARGET ACHIEVED! P2P < 5 pm (10x goal from 51 pm baseline)")
    elif best_p2p < 10.0:
        print(f"\n✅ EXCELLENT! P2P < 10 pm (5x improvement)")
    else:
        print(f"\n📊 Current best: {best_p2p:.3f} pm")

    # Save results
    df_fourier.to_csv('savgol_optimization_fourier.csv', index=False)
    df_direct.to_csv('savgol_optimization_direct.csv', index=False)
    print(f"\n💾 Results saved to savgol_optimization_*.csv")


if __name__ == '__main__':
    main()
