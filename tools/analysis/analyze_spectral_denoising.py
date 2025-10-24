"""
Spectral Denoising Analysis for SPR Data.

Test different denoising methods applied to raw spectra (before transmission calculation)
to reduce the 86 px p-p variation in sensorgram tracking.

Denoising strategies:
1. Savitzky-Golay filter (preserves peak shape)
2. Median filter (removes spikes)
3. Gaussian smoothing (simple averaging)
4. Wavelet denoising (multi-scale noise removal)
5. No denoising (baseline)

Goal: Find optimal denoising that reduces noise without distorting peak features.
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.signal import savgol_filter, medfilt
from scipy.ndimage import gaussian_filter1d
import pywt
from typing import Tuple, Dict, List
import json
import time

# Data paths
BASE_DIR = Path("spectral_training_data/demo P4SPR 2.0")
S_MODE_DIR = BASE_DIR / "s" / "used"
P_MODE_DIR = BASE_DIR / "p" / "used"
OUTPUT_DIR = Path("analysis_results") / "spectral_denoising"


def find_latest_data_dir(base_path: Path) -> Path:
    """Find the most recent data collection directory."""
    timestamp_dirs = sorted([d for d in base_path.iterdir() if d.is_dir()])
    return timestamp_dirs[-1]


def load_channel_data(data_dir: Path, channel: str = "A") -> dict:
    """Load NPZ data for a specific channel."""
    npz_file = data_dir / f"channel_{channel}.npz"
    data = np.load(npz_file)
    return {
        'spectra': data['spectra'],
        'dark': data['dark'],
        'timestamps': data['timestamps'],
    }


def denoise_savgol(spectrum: np.ndarray, window_length: int = 11, polyorder: int = 2) -> np.ndarray:
    """
    Savitzky-Golay filter - fits polynomial to local windows.

    Pros: Preserves peak shape, doesn't shift features
    Cons: Can amplify noise if window too small
    """
    # Ensure window_length is odd
    if window_length % 2 == 0:
        window_length += 1

    return savgol_filter(spectrum, window_length, polyorder)


def denoise_median(spectrum: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    """
    Median filter - replaces each point with local median.

    Pros: Excellent spike removal, preserves edges
    Cons: Can flatten smooth curves
    """
    # Ensure kernel_size is odd
    if kernel_size % 2 == 0:
        kernel_size += 1

    return medfilt(spectrum, kernel_size=kernel_size)


def denoise_gaussian(spectrum: np.ndarray, sigma: float = 2.0) -> np.ndarray:
    """
    Gaussian smoothing - weighted average with Gaussian kernel.

    Pros: Simple, smooth output
    Cons: Can blur sharp features
    """
    return gaussian_filter1d(spectrum, sigma=sigma)


def denoise_wavelet(spectrum: np.ndarray, wavelet: str = 'db4', level: int = 3) -> np.ndarray:
    """
    Wavelet denoising - decompose signal, threshold noise, reconstruct.

    Pros: Adaptive, preserves sharp features while removing noise
    Cons: More complex, slower
    """
    # Decompose
    coeffs = pywt.wavedec(spectrum, wavelet, level=level)

    # Calculate threshold (universal threshold)
    sigma = np.median(np.abs(coeffs[-1])) / 0.6745
    threshold = sigma * np.sqrt(2 * np.log(len(spectrum)))

    # Apply soft thresholding to detail coefficients
    coeffs_thresholded = [coeffs[0]]  # Keep approximation coefficients
    for coeff in coeffs[1:]:
        coeffs_thresholded.append(pywt.threshold(coeff, threshold, mode='soft'))

    # Reconstruct
    denoised = pywt.waverec(coeffs_thresholded, wavelet)

    # Handle length mismatch (wavelet transform may change length)
    if len(denoised) > len(spectrum):
        denoised = denoised[:len(spectrum)]
    elif len(denoised) < len(spectrum):
        denoised = np.pad(denoised, (0, len(spectrum) - len(denoised)), mode='edge')

    return denoised


def apply_denoising_method(
    spectra: np.ndarray,
    method: str,
    **kwargs
) -> Tuple[np.ndarray, float]:
    """
    Apply denoising method to all spectra.

    Returns:
        denoised_spectra: Denoised spectra array
        processing_time: Time per spectrum in ms
    """
    n_time, n_wavelength = spectra.shape
    denoised = np.zeros_like(spectra)

    start_time = time.time()

    for t in range(n_time):
        if method == 'none':
            denoised[t] = spectra[t]
        elif method == 'savgol':
            denoised[t] = denoise_savgol(spectra[t], **kwargs)
        elif method == 'median':
            denoised[t] = denoise_median(spectra[t], **kwargs)
        elif method == 'gaussian':
            denoised[t] = denoise_gaussian(spectra[t], **kwargs)
        elif method == 'wavelet':
            denoised[t] = denoise_wavelet(spectra[t], **kwargs)
        else:
            raise ValueError(f"Unknown method: {method}")

    elapsed = time.time() - start_time
    time_per_spectrum = elapsed / n_time * 1000  # ms

    return denoised, time_per_spectrum


def calculate_transmission_from_denoised(
    s_denoised: np.ndarray,
    p_denoised: np.ndarray,
    s_dark: np.ndarray,
    p_dark: np.ndarray
) -> np.ndarray:
    """Calculate transmission from denoised spectra."""
    # Dark correction
    s_corrected = s_denoised - s_dark
    p_corrected = p_denoised - p_dark

    # Use median S-mode as reference
    s_reference = np.median(s_corrected, axis=0)

    # Calculate transmission
    epsilon = 1e-6
    s_reference_safe = np.where(np.abs(s_reference) < epsilon, epsilon, s_reference)
    transmission = p_corrected / s_reference_safe[np.newaxis, :]

    return transmission


def track_minimum_simple(transmission: np.ndarray, search_region: Tuple[int, int]) -> np.ndarray:
    """Simple direct minimum tracking."""
    start, end = search_region
    n_time = transmission.shape[0]
    positions = np.zeros(n_time)

    for t in range(n_time):
        region = transmission[t, start:end]
        positions[t] = start + np.argmin(region)

    return positions


def test_denoising_methods(
    s_data: dict,
    p_data: dict,
    search_region: Tuple[int, int] = (1000, 2600)
) -> Dict:
    """
    Test all denoising methods and compare sensorgram quality.

    Returns:
        results: Dictionary with statistics for each method
    """
    print("\n" + "="*70)
    print("TESTING DENOISING METHODS")
    print("="*70)

    # Extract raw data
    s_spectra = s_data['spectra']
    s_dark = s_data['dark'][0]
    p_spectra = p_data['spectra']
    p_dark = p_data['dark'][0]

    # Define methods to test
    methods = {
        'none': {},
        'savgol_w11': {'window_length': 11, 'polyorder': 2},
        'savgol_w21': {'window_length': 21, 'polyorder': 2},
        'savgol_w51': {'window_length': 51, 'polyorder': 3},
        'median_k5': {'kernel_size': 5},
        'median_k11': {'kernel_size': 11},
        'gaussian_s2': {'sigma': 2.0},
        'gaussian_s5': {'sigma': 5.0},
        'wavelet_db4': {'wavelet': 'db4', 'level': 3},
        'wavelet_sym4': {'wavelet': 'sym4', 'level': 4},
    }

    results = {}

    for method_name, params in methods.items():
        print(f"\n{method_name.upper()}:")

        # Extract base method name
        base_method = method_name.split('_')[0]

        # Denoise S-mode
        print(f"  Denoising S-mode spectra...")
        s_denoised, s_time = apply_denoising_method(s_spectra, base_method, **params)

        # Denoise P-mode
        print(f"  Denoising P-mode spectra...")
        p_denoised, p_time = apply_denoising_method(p_spectra, base_method, **params)

        total_time = s_time + p_time
        print(f"  Processing time: {total_time:.2f} ms per spectrum pair")

        # Calculate transmission
        transmission = calculate_transmission_from_denoised(
            s_denoised, p_denoised, s_dark, p_dark
        )

        # Track minimum
        positions = track_minimum_simple(transmission, search_region)

        # Calculate statistics
        pp = np.ptp(positions)
        std = np.std(positions)

        print(f"  Sensorgram: P-P = {pp:.2f} px, STD = {std:.2f} px")

        results[method_name] = {
            's_denoised': s_denoised,
            'p_denoised': p_denoised,
            'transmission': transmission,
            'positions': positions,
            'peak_to_peak': pp,
            'std': std,
            'processing_time': total_time,
        }

    return results


def calculate_noise_metrics(
    original: np.ndarray,
    denoised: np.ndarray
) -> Dict:
    """Calculate noise reduction metrics."""
    # Difference is the "noise" that was removed
    noise = original - denoised

    # Original signal statistics
    original_std = np.std(original)
    denoised_std = np.std(denoised)
    noise_std = np.std(noise)

    # SNR improvement
    snr_improvement_db = 20 * np.log10(original_std / denoised_std) if denoised_std > 0 else 0

    return {
        'original_std': original_std,
        'denoised_std': denoised_std,
        'noise_removed_std': noise_std,
        'snr_improvement_db': snr_improvement_db,
    }


def visualize_denoising_results(
    s_data: dict,
    p_data: dict,
    results: Dict,
    output_dir: Path
):
    """Create comprehensive visualization of denoising results."""

    output_dir.mkdir(parents=True, exist_ok=True)

    # Select methods to show in detail
    methods_to_show = ['none', 'savgol_w21', 'median_k11', 'gaussian_s5', 'wavelet_db4']

    fig = plt.figure(figsize=(20, 14))

    # 1. Single spectrum comparison (middle time point)
    ax1 = plt.subplot(4, 3, 1)
    t_idx = len(p_data['timestamps']) // 2
    wavelength_pixels = np.arange(p_data['spectra'].shape[1])

    colors = {'none': 'blue', 'savgol_w21': 'red', 'median_k11': 'green',
              'gaussian_s5': 'orange', 'wavelet_db4': 'purple'}

    for method in methods_to_show:
        p_spectrum = results[method]['p_denoised'][t_idx] - p_data['dark'][0]
        ax1.plot(wavelength_pixels, p_spectrum,
                color=colors.get(method, 'gray'), linewidth=1, alpha=0.7, label=method)

    ax1.set_xlabel('Wavelength pixel')
    ax1.set_ylabel('Intensity (counts)')
    ax1.set_title('P-mode Spectrum (Middle Time Point)')
    ax1.set_xlim([1000, 2600])
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    # 2. Transmission spectrum comparison
    ax2 = plt.subplot(4, 3, 2)

    for method in methods_to_show:
        transmission = results[method]['transmission'][t_idx]
        ax2.plot(wavelength_pixels, transmission,
                color=colors.get(method, 'gray'), linewidth=1, alpha=0.7, label=method)

    ax2.set_xlabel('Wavelength pixel')
    ax2.set_ylabel('Transmission')
    ax2.set_title('Transmission Spectrum (Middle Time Point)')
    ax2.set_xlim([1000, 2600])
    ax2.set_ylim([0, 1.2])
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # 3. Peak-to-peak comparison (all methods)
    ax3 = plt.subplot(4, 3, 3)
    all_methods = list(results.keys())
    pp_values = [results[m]['peak_to_peak'] for m in all_methods]
    colors_bar = ['blue' if m == 'none' else 'coral' for m in all_methods]

    bars = ax3.barh(all_methods, pp_values, color=colors_bar, alpha=0.7, edgecolor='black')
    ax3.axvline(results['none']['peak_to_peak'], color='blue', linestyle='--',
               linewidth=2, label='No denoising')
    ax3.set_xlabel('Peak-to-Peak (pixels)')
    ax3.set_title('Sensorgram Variation by Method')
    ax3.legend()
    ax3.grid(True, alpha=0.3, axis='x')

    # 4-8. Sensorgrams for selected methods
    for idx, method in enumerate(methods_to_show):
        ax = plt.subplot(4, 3, 4 + idx)

        positions = results[method]['positions']
        timestamps = p_data['timestamps']

        ax.plot(timestamps, positions, color=colors.get(method, 'gray'), linewidth=1.5)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Position (pixel)')

        pp = results[method]['peak_to_peak']
        std = results[method]['std']
        improvement = (1 - pp / results['none']['peak_to_peak']) * 100

        ax.set_title(f'{method.upper()}\nP-P: {pp:.1f} px ({improvement:+.1f}%)')
        ax.grid(True, alpha=0.3)

    # 9. Processing time comparison
    ax9 = plt.subplot(4, 3, 9)
    proc_times = [results[m]['processing_time'] for m in all_methods]

    bars = ax9.barh(all_methods, proc_times, color='steelblue', alpha=0.7, edgecolor='black')
    ax9.axvline(10, color='red', linestyle='--', linewidth=2, label='10ms target')
    ax9.set_xlabel('Processing Time (ms/spectrum pair)')
    ax9.set_title('Processing Speed')
    ax9.legend()
    ax9.grid(True, alpha=0.3, axis='x')

    # 10. Improvement vs. processing time scatter
    ax10 = plt.subplot(4, 3, 10)
    improvements = [(1 - results[m]['peak_to_peak'] / results['none']['peak_to_peak']) * 100
                   for m in all_methods]

    for method, improvement, proc_time in zip(all_methods, improvements, proc_times):
        color = colors.get(method, 'gray')
        marker = 'o' if method in methods_to_show else 's'
        ax10.scatter(proc_time, improvement, s=100, color=color, marker=marker,
                    alpha=0.7, edgecolors='black', linewidths=2)

        # Label
        if method in methods_to_show or improvement > 5:
            ax10.annotate(method, (proc_time, improvement),
                         fontsize=7, ha='right', va='bottom')

    ax10.axhline(0, color='black', linestyle='-', linewidth=1)
    ax10.axvline(10, color='red', linestyle='--', linewidth=1, alpha=0.5, label='10ms limit')
    ax10.set_xlabel('Processing Time (ms)')
    ax10.set_ylabel('Improvement (%)')
    ax10.set_title('Performance Trade-off')
    ax10.legend()
    ax10.grid(True, alpha=0.3)

    # 11. Noise removed visualization (sample spectrum)
    ax11 = plt.subplot(4, 3, 11)

    # Compare original vs best denoising method
    best_method = min([m for m in all_methods if m != 'none'],
                     key=lambda m: results[m]['peak_to_peak'])

    original = p_data['spectra'][t_idx] - p_data['dark'][0]
    denoised = results[best_method]['p_denoised'][t_idx] - p_data['dark'][0]
    noise = original - denoised

    ax11.plot(wavelength_pixels, original, 'b-', linewidth=1, alpha=0.5, label='Original')
    ax11.plot(wavelength_pixels, denoised, 'r-', linewidth=1.5, label=f'Denoised ({best_method})')
    ax11.plot(wavelength_pixels, noise + np.mean(original), 'g-', linewidth=0.5,
             alpha=0.7, label='Noise (offset)')

    ax11.set_xlabel('Wavelength pixel')
    ax11.set_ylabel('Intensity (counts)')
    ax11.set_title(f'Noise Removal Example\n{best_method.upper()}')
    ax11.set_xlim([1000, 2600])
    ax11.legend(fontsize=8)
    ax11.grid(True, alpha=0.3)

    # 12. Summary table
    ax12 = plt.subplot(4, 3, 12)
    ax12.axis('off')

    # Find best methods
    best_accuracy = min(all_methods, key=lambda m: results[m]['peak_to_peak'])
    best_speed = min(all_methods, key=lambda m: results[m]['processing_time'])
    best_tradeoff = min([m for m in all_methods if results[m]['processing_time'] < 10],
                       key=lambda m: results[m]['peak_to_peak'], default=best_speed)

    summary_text = "SUMMARY\n" + "="*40 + "\n\n"
    summary_text += f"Baseline (no denoising):\n"
    summary_text += f"  P-P: {results['none']['peak_to_peak']:.2f} px\n\n"

    summary_text += f"🏆 Best Accuracy:\n"
    summary_text += f"  {best_accuracy}\n"
    summary_text += f"  P-P: {results[best_accuracy]['peak_to_peak']:.2f} px\n"
    summary_text += f"  Improvement: {(1 - results[best_accuracy]['peak_to_peak'] / results['none']['peak_to_peak']) * 100:.1f}%\n"
    summary_text += f"  Time: {results[best_accuracy]['processing_time']:.2f} ms\n\n"

    summary_text += f"⚡ Fastest (<10ms):\n"
    summary_text += f"  {best_speed}\n"
    summary_text += f"  Time: {results[best_speed]['processing_time']:.2f} ms\n\n"

    if best_tradeoff != best_speed:
        summary_text += f"⚖️ Best Trade-off (<10ms):\n"
        summary_text += f"  {best_tradeoff}\n"
        summary_text += f"  P-P: {results[best_tradeoff]['peak_to_peak']:.2f} px\n"
        summary_text += f"  Improvement: {(1 - results[best_tradeoff]['peak_to_peak'] / results['none']['peak_to_peak']) * 100:.1f}%\n"
        summary_text += f"  Time: {results[best_tradeoff]['processing_time']:.2f} ms\n"

    ax12.text(0.1, 0.9, summary_text, transform=ax12.transAxes,
             fontsize=10, verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    plt.tight_layout()
    plt.savefig(output_dir / 'spectral_denoising_comparison.png', dpi=150, bbox_inches='tight')
    print(f"\n📊 Visualization saved: {output_dir / 'spectral_denoising_comparison.png'}")
    plt.close()


def main():
    """Test spectral denoising methods."""

    print("="*70)
    print("SPECTRAL DENOISING ANALYSIS - CHANNEL A")
    print("="*70)

    # Load data
    print("\n📂 Loading data...")
    s_mode_dir = find_latest_data_dir(S_MODE_DIR)
    p_mode_dir = find_latest_data_dir(P_MODE_DIR)

    s_data = load_channel_data(s_mode_dir, "A")
    p_data = load_channel_data(p_mode_dir, "A")

    print(f"   S-mode: {s_data['spectra'].shape}")
    print(f"   P-mode: {p_data['spectra'].shape}")

    # Test denoising methods
    results = test_denoising_methods(s_data, p_data)

    # Visualize results
    visualize_denoising_results(s_data, p_data, results, OUTPUT_DIR)

    # Summary
    print("\n" + "="*70)
    print("SUMMARY - DENOISING METHOD COMPARISON")
    print("="*70)

    print(f"\n{'Method':<15} {'P-P (px)':<12} {'Improvement':<15} {'Time (ms)':<12}")
    print("-" * 70)

    baseline_pp = results['none']['peak_to_peak']

    for method in results.keys():
        r = results[method]
        improvement = (1 - r['peak_to_peak'] / baseline_pp) * 100
        print(f"{method:<15} {r['peak_to_peak']:<12.2f} {improvement:<15.1f}% {r['processing_time']:<12.2f}")

    # Find best methods
    all_methods = list(results.keys())
    best_accuracy = min(all_methods, key=lambda m: results[m]['peak_to_peak'])
    fast_methods = [m for m in all_methods if results[m]['processing_time'] < 10]
    best_fast = min(fast_methods, key=lambda m: results[m]['peak_to_peak']) if fast_methods else None

    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)

    print(f"\n🏆 Best overall accuracy: {best_accuracy}")
    print(f"   P-P: {results[best_accuracy]['peak_to_peak']:.2f} px "
          f"({(1 - results[best_accuracy]['peak_to_peak'] / baseline_pp) * 100:.1f}% improvement)")
    print(f"   Time: {results[best_accuracy]['processing_time']:.2f} ms/pair")

    if best_fast:
        print(f"\n⚡ Best under 10ms: {best_fast}")
        print(f"   P-P: {results[best_fast]['peak_to_peak']:.2f} px "
              f"({(1 - results[best_fast]['peak_to_peak'] / baseline_pp) * 100:.1f}% improvement)")
        print(f"   Time: {results[best_fast]['processing_time']:.2f} ms/pair")

    # Save summary
    summary = {
        'baseline': {
            'peak_to_peak': float(baseline_pp),
            'std': float(results['none']['std']),
        },
        'methods': {
            method: {
                'peak_to_peak': float(results[method]['peak_to_peak']),
                'std': float(results[method]['std']),
                'improvement_percent': float((1 - results[method]['peak_to_peak'] / baseline_pp) * 100),
                'processing_time_ms': float(results[method]['processing_time']),
            }
            for method in results.keys()
        },
        'best_accuracy': best_accuracy,
        'best_fast': best_fast,
    }

    summary_file = OUTPUT_DIR / 'denoising_summary.json'
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\n📄 Summary saved: {summary_file}")

    print(f"\n✅ Analysis complete! Results saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    main()
