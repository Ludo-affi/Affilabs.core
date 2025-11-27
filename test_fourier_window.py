"""
Test effect of doubling the Fourier window size around minimum

Current: window_size = 165 (default)
Test: window_size = 330, 200, 400, 600

This controls how many points around the zero-crossing are used for
the linear regression to refine the peak position.
"""

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.pipelines.fourier_pipeline import FourierPipeline

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
    return df['channel_a'].values


def test_window_size(wavelength_data, window_size):
    """Test Fourier pipeline with specific window size"""
    config = {'window_size': window_size}
    pipeline = FourierPipeline(config=config)
    
    detected = []
    for true_wl in wavelength_data:
        transmission, wavelengths = create_mock_spectrum(true_wl)
        detected_wl = pipeline.find_resonance_wavelength(transmission, wavelengths)
        detected.append(float(detected_wl) if detected_wl is not None else np.nan)
    
    return np.array(detected, dtype=float)[~np.isnan(np.array(detected, dtype=float))]


def batch_savgol_exp(data, batch_size, savgol_win, exp_alpha):
    """Apply best combo: Batch → Savgol → Exponential"""
    # Batch
    batched = []
    for i in range(0, len(data) - batch_size + 1, batch_size):
        batched.append(np.mean(data[i:i+batch_size]))
    batched = np.array(batched)
    
    # Savgol
    if len(batched) >= savgol_win:
        batched = savgol_filter(batched, window_length=savgol_win, polyorder=2)
    
    # Exponential
    result = [batched[0]]
    for i in range(1, len(batched)):
        result.append(exp_alpha * batched[i] + (1 - exp_alpha) * result[-1])
    
    return np.array(result)


def main():
    print("\n" + "="*80)
    print("🔬 FOURIER WINDOW SIZE OPTIMIZATION")
    print("="*80)
    
    wavelength_data = load_baseline_data()
    if wavelength_data is None:
        return
    
    print(f"✅ Loaded {len(wavelength_data)} baseline points")
    print(f"📊 Raw: P2P={np.ptp(wavelength_data)*1000:.3f} pm\n")
    
    # Test different window sizes
    window_sizes = [50, 100, 165, 200, 250, 330, 400, 500, 600, 800, 1000, 1500]
    
    results = []
    
    print("Testing Fourier window sizes...")
    print("-" * 80)
    
    for window_size in window_sizes:
        print(f"\nWindow size: {window_size}")
        
        # Test raw detection
        detected = test_window_size(wavelength_data, window_size)
        p2p_raw = np.ptp(detected) * 1000
        std_raw = np.std(detected) * 1000
        
        print(f"  Raw: P2P={p2p_raw:7.3f} pm, Std={std_raw:6.3f} pm")
        
        results.append({
            'window_size': window_size,
            'processing': 'Raw',
            'p2p_pm': p2p_raw,
            'std_pm': std_raw
        })
        
        # Apply best post-processing (B5+SG3+Exp0.1)
        if len(detected) >= 5:
            processed = batch_savgol_exp(detected, batch_size=5, savgol_win=3, exp_alpha=0.1)
            p2p_proc = np.ptp(processed) * 1000
            std_proc = np.std(processed) * 1000
            
            print(f"  +B5+SG3+Exp0.1: P2P={p2p_proc:7.3f} pm, Std={std_proc:6.3f} pm")
            
            results.append({
                'window_size': window_size,
                'processing': 'B5+SG3+Exp0.1',
                'p2p_pm': p2p_proc,
                'std_pm': std_proc
            })
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 RESULTS SUMMARY")
    print('='*80)
    
    df = pd.DataFrame(results)
    
    # Best raw
    print("\n🏆 BEST RAW DETECTION (no post-processing):")
    df_raw = df[df['processing'] == 'Raw'].sort_values('p2p_pm')
    for i, row in df_raw.head(5).iterrows():
        print(f"  Window={row['window_size']:4d}: P2P={row['p2p_pm']:7.3f} pm, Std={row['std_pm']:6.3f} pm")
    
    # Best with processing
    print("\n🏆 BEST WITH POST-PROCESSING (B5+SG3+Exp0.1):")
    df_proc = df[df['processing'] == 'B5+SG3+Exp0.1'].sort_values('p2p_pm')
    for i, row in df_proc.head(5).iterrows():
        print(f"  Window={row['window_size']:4d}: P2P={row['p2p_pm']:7.3f} pm, Std={row['std_pm']:6.3f} pm")
    
    # Best overall
    best = df.sort_values('p2p_pm').iloc[0]
    default = df[(df['window_size'] == 165) & (df['processing'] == 'B5+SG3+Exp0.1')].iloc[0]
    
    print(f"\n{'='*80}")
    print("🥇 ABSOLUTE BEST")
    print('='*80)
    print(f"Window size: {int(best['window_size'])}")
    print(f"Processing:  {best['processing']}")
    print(f"Peak-to-Peak: {best['p2p_pm']:.3f} pm")
    print(f"Std Dev:      {best['std_pm']:.3f} pm")
    
    print(f"\n📊 vs Default (window=165, B5+SG3+Exp0.1):")
    print(f"Default:  {default['p2p_pm']:.3f} pm")
    print(f"Best:     {best['p2p_pm']:.3f} pm")
    improvement = (default['p2p_pm'] - best['p2p_pm']) / default['p2p_pm'] * 100
    print(f"Improvement: {improvement:.1f}%")
    
    # Save
    df.to_csv('fourier_window_optimization.csv', index=False)
    print(f"\n💾 Results saved to: fourier_window_optimization.csv")


if __name__ == '__main__':
    main()
