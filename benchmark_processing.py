"""Benchmark processing time for single vs batch spectrum processing"""

import sys
import time
import numpy as np
from pathlib import Path
from scipy.fftpack import dst, idct
from scipy.stats import linregress

# Simple implementations without importing from Old software
def calculate_transmission(intensity, reference):
    """Calculate transmission percentage"""
    with np.errstate(divide='ignore', invalid='ignore'):
        transmission = (intensity / reference) * 100
        transmission = np.where(reference == 0, 0, transmission)
    return transmission

def find_resonance_wavelength_fourier(transmission_spectrum, wavelengths, fourier_weights, window_size=165):
    """Find resonance wavelength using Fourier method"""
    try:
        spectrum = transmission_spectrum
        fourier_coeff = np.zeros_like(spectrum)
        fourier_coeff[0] = 2 * (spectrum[-1] - spectrum[0])
        fourier_coeff[1:-1] = fourier_weights * dst(
            spectrum[1:-1] - np.linspace(spectrum[0], spectrum[-1], len(spectrum))[1:-1], 1
        )
        derivative = idct(fourier_coeff, 1)
        zero = derivative.searchsorted(0)
        start = max(zero - window_size, 0)
        end = min(zero + window_size, len(spectrum) - 1)
        line = linregress(wavelengths[start:end], derivative[start:end])
        return float(-line.intercept / line.slope)
    except:
        return np.nan

# Generate synthetic data similar to real spectra
def generate_test_data():
    """Generate synthetic spectrum data"""
    wavelengths = np.linspace(500, 800, 1797)  # Typical wavelength range
    
    # Simulate SPR dip at ~650nm
    center = 650
    width = 20
    transmission = 100 - 40 * np.exp(-((wavelengths - center)**2) / (2 * width**2))
    transmission += np.random.normal(0, 0.5, len(wavelengths))  # Add noise
    
    intensity = transmission * 500  # Simulate intensity counts
    reference = np.ones_like(intensity) * 500
    
    return wavelengths, intensity, reference, transmission


def benchmark_sequential(n_channels=4, n_repeats=100):
    """Benchmark sequential processing (current method)"""
    wavelengths, intensity, reference, _ = generate_test_data()
    
    # Pre-calculate Fourier weights (done once in real app)
    N = len(wavelengths)
    fourier_weights = np.sqrt(2.0 / N) * np.arange(1, N - 1)
    
    times = []
    
    for _ in range(n_repeats):
        t0 = time.perf_counter()
        
        # Process each channel sequentially
        for ch in range(n_channels):
            # 1. Calculate transmission
            trans = calculate_transmission(intensity, reference)
            
            # 2. Find resonance peak
            lambda_val = find_resonance_wavelength_fourier(
                trans, wavelengths, fourier_weights, window_size=165
            )
        
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)  # Convert to ms
    
    return times


def benchmark_batch(n_channels=4, n_repeats=100):
    """Benchmark batch processing (vectorized across channels)"""
    wavelengths, intensity, reference, _ = generate_test_data()
    
    # Pre-calculate Fourier weights
    N = len(wavelengths)
    fourier_weights = np.sqrt(2.0 / N) * np.arange(1, N - 1)
    
    times = []
    
    for _ in range(n_repeats):
        t0 = time.perf_counter()
        
        # Stack data for all channels (simulate having all 4 at once)
        intensities = np.stack([intensity] * n_channels)
        references = np.stack([reference] * n_channels)
        
        # 1. Vectorized transmission calculation (all channels at once)
        trans_batch = (intensities / references) * 100
        
        # 2. Process peaks (still need loop but could be optimized)
        lambda_vals = []
        for ch in range(n_channels):
            lambda_val = find_resonance_wavelength_fourier(
                trans_batch[ch], wavelengths, fourier_weights, window_size=165
            )
            lambda_vals.append(lambda_val)
        
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)
    
    return times


if __name__ == "__main__":
    print("=" * 60)
    print("Spectrum Processing Performance Benchmark")
    print("=" * 60)
    
    n_repeats = 100
    n_channels = 4
    
    print(f"\nConfiguration:")
    print(f"  Channels: {n_channels}")
    print(f"  Repeats: {n_repeats}")
    print(f"  Spectrum size: 1797 pixels")
    
    # Sequential processing (current)
    print("\n1. Sequential Processing (current method)...")
    seq_times = benchmark_sequential(n_channels, n_repeats)
    seq_mean = np.mean(seq_times)
    seq_std = np.std(seq_times)
    
    print(f"   Mean: {seq_mean:.3f} ms ± {seq_std:.3f} ms")
    print(f"   Per channel: {seq_mean/n_channels:.3f} ms")
    
    # Batch processing (optimized)
    print("\n2. Batch Processing (vectorized)...")
    batch_times = benchmark_batch(n_channels, n_repeats)
    batch_mean = np.mean(batch_times)
    batch_std = np.std(batch_times)
    
    print(f"   Mean: {batch_mean:.3f} ms ± {batch_std:.3f} ms")
    print(f"   Per channel: {batch_mean/n_channels:.3f} ms")
    
    # Calculate savings
    savings = seq_mean - batch_mean
    speedup = seq_mean / batch_mean
    
    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)
    print(f"Time saved per cycle: {savings:.3f} ms")
    print(f"Speedup: {speedup:.2f}x")
    print(f"Percentage improvement: {(1 - 1/speedup) * 100:.1f}%")
    
    print("\n" + "=" * 60)
    print("Context:")
    print("=" * 60)
    print(f"Per cycle breakdown (4 channels):")
    print(f"  LED commands:      ~600 ms  (turn on)")
    print(f"  Integration:       ~100 ms  (varies)")
    print(f"  USB transfers:      ~48 ms  (4 × 12ms)")
    print(f"  Processing:         ~{seq_mean:.1f} ms  (current)")
    print(f"  LED off:            ~50 ms   (turn off)")
    print(f"  ─────────────────────────────")
    print(f"  Total cycle:       ~{600+100+48+seq_mean+50:.0f} ms")
    print()
    print(f"With batch processing:")
    print(f"  Processing:         ~{batch_mean:.1f} ms  (optimized)")
    print(f"  ─────────────────────────────")
    print(f"  Total cycle:       ~{600+100+48+batch_mean+50:.0f} ms")
    print(f"  Savings:            ~{savings:.1f} ms ({savings/(600+100+48+seq_mean+50)*100:.1f}% of total)")
    print()
    print("⚠️  NOTE: Processing is only ~0.3% of total cycle time.")
    print("   Biggest bottleneck is LED command overhead (~75% of cycle).")
