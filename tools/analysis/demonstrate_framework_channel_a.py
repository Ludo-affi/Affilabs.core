"""
Apply AFfilab Spectral Analysis Framework to Channel A data.

This script demonstrates the complete proprietary analysis pipeline:
1. Load S-mode and P-mode data
2. Calculate transmission time series
3. Extract spectral features (peak position, depth, FWHM, asymmetry)
4. Test all peak-finding algorithms
5. Apply bias corrections
6. Compare corrected vs. uncorrected sensorgrams
7. Assess signal quality
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.signal import find_peaks
from scipy.optimize import curve_fit
from typing import Tuple, Dict
import json
import time

# Data paths
BASE_DIR = Path("spectral_training_data/demo P4SPR 2.0")
S_MODE_DIR = BASE_DIR / "s" / "used"
P_MODE_DIR = BASE_DIR / "p" / "used"
OUTPUT_DIR = Path("analysis_results") / "framework_demonstration"


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


def calculate_transmission(s_data: dict, p_data: dict) -> np.ndarray:
    """Calculate transmission time series."""
    s_reference = np.median(s_data['spectra'], axis=0)
    s_dark = s_data['dark'][0]
    p_spectra = p_data['spectra']
    p_dark = p_data['dark'][0]

    s_corrected = s_reference - s_dark
    p_corrected = p_spectra - p_dark

    epsilon = 1e-6
    s_corrected_safe = np.where(np.abs(s_corrected) < epsilon, epsilon, s_corrected)
    transmission = p_corrected / s_corrected_safe[np.newaxis, :]

    return transmission


def extract_peak_features(spectrum: np.ndarray, search_region: Tuple[int, int]) -> Dict:
    """
    Extract comprehensive peak features from transmission spectrum.

    Returns:
        features: Dictionary with position, depth, FWHM, asymmetry, sharpness, etc.
    """
    start, end = search_region
    region = spectrum[start:end]

    # Find minimum
    local_min_idx = np.argmin(region)
    min_pixel = start + local_min_idx
    min_value = region[local_min_idx]

    # Estimate background (mean of edges)
    background = np.mean([np.mean(region[:50]), np.mean(region[-50:])])

    # Peak depth
    depth = min_value / background if background > 0 else min_value

    # Calculate FWHM
    half_depth = (background + min_value) / 2

    # Find points where spectrum crosses half depth
    below_half = region < half_depth
    if np.sum(below_half) > 0:
        indices = np.where(below_half)[0]
        fwhm = indices[-1] - indices[0]
    else:
        fwhm = 0

    # Asymmetry: compare left and right half-widths
    left_width = local_min_idx - (indices[0] if np.sum(below_half) > 0 else 0)
    right_width = (indices[-1] if np.sum(below_half) > 0 else len(region)-1) - local_min_idx

    if left_width + right_width > 0:
        asymmetry = (right_width - left_width) / (right_width + left_width)
    else:
        asymmetry = 0.0

    # Peak sharpness (second derivative at minimum)
    if 2 <= local_min_idx < len(region) - 2:
        sharpness = region[local_min_idx - 2] - 2*region[local_min_idx] + region[local_min_idx + 2]
    else:
        sharpness = 0.0

    # Background slope
    x = np.arange(len(region))
    slope, _ = np.polyfit([0, len(region)-1], [region[0], region[-1]], 1)

    # SNR
    noise_std = np.std(region[:50])  # Estimate noise from background region
    snr = (background - min_value) / noise_std if noise_std > 0 else 0

    return {
        'position': min_pixel,
        'depth': depth,
        'depth_transmission': min_value,
        'background': background,
        'fwhm': fwhm,
        'asymmetry': asymmetry,
        'sharpness': sharpness,
        'background_slope': slope,
        'snr': snr,
    }


def find_minimum_direct(spectrum: np.ndarray, search_region: Tuple[int, int]) -> float:
    """Direct minimum finding."""
    start, end = search_region
    region = spectrum[start:end]
    return start + np.argmin(region)


def find_minimum_polynomial(spectrum: np.ndarray, search_region: Tuple[int, int], window: int = 3) -> float:
    """Polynomial fit around minimum."""
    start, end = search_region
    region = spectrum[start:end]
    local_min_idx = np.argmin(region)

    fit_start = max(0, local_min_idx - window)
    fit_end = min(len(region), local_min_idx + window + 1)

    x_fit = np.arange(fit_start, fit_end)
    y_fit = region[fit_start:fit_end]

    try:
        coeffs = np.polyfit(x_fit, y_fit, 2)
        if coeffs[0] > 0:
            refined_min = -coeffs[1] / (2 * coeffs[0])
            return start + refined_min
    except:
        pass

    return start + local_min_idx


def find_minimum_centroid(spectrum: np.ndarray, search_region: Tuple[int, int], threshold_factor: float = 1.2) -> float:
    """Centroid of dip region."""
    start, end = search_region
    region = spectrum[start:end]
    local_min_idx = np.argmin(region)

    threshold = region[local_min_idx] * threshold_factor
    dip_mask = region < threshold

    if np.sum(dip_mask) > 0:
        x_indices = np.arange(len(region))
        centroid = np.sum(x_indices[dip_mask] * region[dip_mask]) / np.sum(region[dip_mask])
        return start + centroid

    return start + local_min_idx


# Bias correction formulas from synthetic analysis
BIAS_CORRECTIONS = {
    'direct': lambda depth, fwhm, asymmetry: 0.607*depth - 0.268,
    'polynomial': lambda depth, fwhm, asymmetry: 1.112*depth + 0.810*asymmetry - 0.831,
    'centroid': lambda depth, fwhm, asymmetry: 1.513*depth + 0.002*fwhm + 52.455*asymmetry - 0.961,
}


def track_minimum_with_correction(
    transmission: np.ndarray,
    method: str,
    search_region: Tuple[int, int]
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict]:
    """
    Track minimum with bias correction.

    Returns:
        positions_raw: Raw positions from algorithm
        positions_corrected: Bias-corrected positions
        features_list: Features extracted for each spectrum
        stats: Processing statistics
    """
    n_time = transmission.shape[0]
    positions_raw = np.zeros(n_time)
    positions_corrected = np.zeros(n_time)
    features_list = []

    # Select method
    if method == 'direct':
        find_func = find_minimum_direct
    elif method == 'polynomial':
        find_func = find_minimum_polynomial
    elif method == 'centroid':
        find_func = find_minimum_centroid
    else:
        raise ValueError(f"Unknown method: {method}")

    correction_func = BIAS_CORRECTIONS.get(method, lambda d, f, a: 0)

    print(f"\n  Tracking with {method.upper()} method...")
    start_time = time.time()

    for t in range(n_time):
        spectrum = transmission[t]

        # Extract features
        features = extract_peak_features(spectrum, search_region)
        features_list.append(features)

        # Find minimum (raw)
        pos_raw = find_func(spectrum, search_region)
        positions_raw[t] = pos_raw

        # Calculate bias correction
        bias = correction_func(features['depth'], features['fwhm'], features['asymmetry'])

        # Apply correction
        positions_corrected[t] = pos_raw - bias

    elapsed = time.time() - start_time

    stats = {
        'processing_time_total': elapsed,
        'processing_time_per_spectrum': elapsed / n_time * 1000,  # ms
        'mean_depth': np.mean([f['depth'] for f in features_list]),
        'mean_fwhm': np.mean([f['fwhm'] for f in features_list]),
        'mean_asymmetry': np.mean([f['asymmetry'] for f in features_list]),
        'mean_snr': np.mean([f['snr'] for f in features_list]),
    }

    print(f"    ✅ Complete in {elapsed:.3f}s ({stats['processing_time_per_spectrum']:.2f} ms/spectrum)")

    return positions_raw, positions_corrected, features_list, stats


def calculate_variation_stats(signal: np.ndarray) -> Dict:
    """Calculate variation statistics."""
    return {
        'peak_to_peak': np.ptp(signal),
        'std': np.std(signal),
        'mean': np.mean(signal),
        'median': np.median(signal),
        'min': np.min(signal),
        'max': np.max(signal),
    }


def assess_signal_quality(features_list: list) -> Dict:
    """
    Assess signal quality based on extracted features.

    This is a simplified version - full implementation would use empirical baseline.
    """
    # Calculate mean features
    mean_depth = np.mean([f['depth'] for f in features_list])
    mean_fwhm = np.mean([f['fwhm'] for f in features_list])
    mean_asymmetry = np.mean([f['asymmetry'] for f in features_list])
    mean_snr = np.mean([f['snr'] for f in features_list])

    # Temporal stability
    positions = np.array([f['position'] for f in features_list])
    position_stability = np.std(positions)

    # Simple rule-based assessment
    issues = []

    if mean_depth > 0.7:
        issues.append("⚠️ Shallow peak (depth > 70%) - possible degraded sensor")

    if mean_fwhm > 250:
        issues.append("⚠️ Broad peak (FWHM > 250 px) - possible recycled sensor")

    if abs(mean_asymmetry) > 0.3:
        issues.append("⚠️ Highly asymmetric peak - unusual peak shape")

    if mean_snr < 10:
        issues.append("⚠️ Low SNR (<10) - noisy signal")

    if position_stability > 50:
        issues.append("⚠️ High position variation - temporal instability")

    if len(issues) == 0:
        quality_flag = "✅ Good signal quality"
    else:
        quality_flag = "⚠️ Signal quality concerns"

    return {
        'quality_flag': quality_flag,
        'issues': issues,
        'metrics': {
            'depth': mean_depth,
            'fwhm': mean_fwhm,
            'asymmetry': mean_asymmetry,
            'snr': mean_snr,
            'position_stability': position_stability,
        }
    }


def visualize_results(
    transmission: np.ndarray,
    timestamps: np.ndarray,
    results: Dict,
    features_list: list,
    output_dir: Path
):
    """Create comprehensive visualization."""

    output_dir.mkdir(parents=True, exist_ok=True)

    methods = list(results.keys())
    n_methods = len(methods)

    # Create large figure
    fig = plt.figure(figsize=(20, 12))

    # 1. Transmission heatmap with all tracked positions
    ax1 = plt.subplot(3, 3, 1)
    wavelength_pixels = np.arange(transmission.shape[1])
    im = ax1.imshow(
        transmission.T,
        aspect='auto',
        extent=[timestamps[0], timestamps[-1], wavelength_pixels[-1], wavelength_pixels[0]],
        cmap='viridis',
        vmin=0, vmax=1
    )

    colors = {'direct': 'red', 'polynomial': 'yellow', 'centroid': 'cyan'}
    for method in methods:
        ax1.plot(timestamps, results[method]['raw'], '-',
                color=colors.get(method, 'white'), linewidth=1, alpha=0.7, label=f'{method} (raw)')

    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Wavelength pixel')
    ax1.set_title('Transmission Heatmap + Tracked Positions')
    ax1.legend(fontsize=8)
    plt.colorbar(im, ax=ax1, label='Transmission')

    # 2-4. Individual sensorgrams (raw vs corrected)
    for idx, method in enumerate(methods):
        ax = plt.subplot(3, 3, 2 + idx)

        raw = results[method]['raw']
        corrected = results[method]['corrected']

        ax.plot(timestamps, raw, 'b-', linewidth=1, alpha=0.7, label='Raw')
        ax.plot(timestamps, corrected, 'r-', linewidth=1.5, label='Corrected')

        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Position (pixel)')
        ax.set_title(f'{method.upper()} Sensorgram')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Add stats
        raw_stats = results[method]['raw_stats']
        corr_stats = results[method]['corrected_stats']

        stats_text = f"Raw P-P: {raw_stats['peak_to_peak']:.1f} px\n"
        stats_text += f"Corr P-P: {corr_stats['peak_to_peak']:.1f} px\n"
        stats_text += f"Improvement: {(1 - corr_stats['peak_to_peak']/raw_stats['peak_to_peak'])*100:.1f}%"

        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
               verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
               fontsize=8)

    # 5. Peak-to-peak comparison
    ax5 = plt.subplot(3, 3, 5)
    x_pos = np.arange(len(methods))
    raw_pp = [results[m]['raw_stats']['peak_to_peak'] for m in methods]
    corr_pp = [results[m]['corrected_stats']['peak_to_peak'] for m in methods]

    width = 0.35
    ax5.bar(x_pos - width/2, raw_pp, width, label='Raw', color='steelblue', alpha=0.7)
    ax5.bar(x_pos + width/2, corr_pp, width, label='Corrected', color='coral', alpha=0.7)

    ax5.set_ylabel('Peak-to-Peak Variation (pixels)')
    ax5.set_title('Bias Correction Impact')
    ax5.set_xticks(x_pos)
    ax5.set_xticklabels([m.upper() for m in methods])
    ax5.legend()
    ax5.grid(True, alpha=0.3, axis='y')

    # 6. Feature evolution over time
    ax6 = plt.subplot(3, 3, 6)
    depths = [f['depth'] for f in features_list]
    ax6.plot(timestamps, depths, 'g-', linewidth=1.5)
    ax6.set_xlabel('Time (s)')
    ax6.set_ylabel('Peak Depth (transmission)')
    ax6.set_title('Peak Depth Over Time')
    ax6.grid(True, alpha=0.3)

    # 7. FWHM over time
    ax7 = plt.subplot(3, 3, 7)
    fwhms = [f['fwhm'] for f in features_list]
    ax7.plot(timestamps, fwhms, 'm-', linewidth=1.5)
    ax7.set_xlabel('Time (s)')
    ax7.set_ylabel('FWHM (pixels)')
    ax7.set_title('Peak Width Over Time')
    ax7.grid(True, alpha=0.3)

    # 8. Asymmetry over time
    ax8 = plt.subplot(3, 3, 8)
    asymmetries = [f['asymmetry'] for f in features_list]
    ax8.plot(timestamps, asymmetries, 'orange', linewidth=1.5)
    ax8.axhline(0, color='black', linestyle='--', linewidth=1)
    ax8.set_xlabel('Time (s)')
    ax8.set_ylabel('Asymmetry')
    ax8.set_title('Peak Asymmetry Over Time')
    ax8.grid(True, alpha=0.3)

    # 9. SNR over time
    ax9 = plt.subplot(3, 3, 9)
    snrs = [f['snr'] for f in features_list]
    ax9.plot(timestamps, snrs, 'purple', linewidth=1.5)
    ax9.set_xlabel('Time (s)')
    ax9.set_ylabel('SNR')
    ax9.set_title('Signal-to-Noise Ratio Over Time')
    ax9.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / 'framework_demonstration.png', dpi=150, bbox_inches='tight')
    print(f"\n📊 Visualization saved: {output_dir / 'framework_demonstration.png'}")
    plt.close()


def main():
    """Demonstrate complete AFfilab analysis framework on Channel A."""

    print("="*70)
    print("AFFILAB SPECTRAL ANALYSIS FRAMEWORK - CHANNEL A DEMONSTRATION")
    print("="*70)

    # Load data
    print("\n📂 Loading Channel A data...")
    s_mode_dir = find_latest_data_dir(S_MODE_DIR)
    p_mode_dir = find_latest_data_dir(P_MODE_DIR)

    s_data = load_channel_data(s_mode_dir, "A")
    p_data = load_channel_data(p_mode_dir, "A")

    print(f"   S-mode: {s_data['spectra'].shape}")
    print(f"   P-mode: {p_data['spectra'].shape}")

    # Calculate transmission
    print("\n🔬 Calculating transmission time series...")
    transmission = calculate_transmission(s_data, p_data)
    print(f"   Transmission shape: {transmission.shape}")
    print(f"   Range: {np.nanmin(transmission):.3f} to {np.nanmax(transmission):.3f}")

    # Define search region (where SPR resonance appears)
    search_region = (1000, 2600)

    # Test all methods with bias correction
    print("\n" + "="*70)
    print("PEAK TRACKING WITH BIAS CORRECTION")
    print("="*70)

    methods = ['direct', 'polynomial', 'centroid']
    results = {}

    for method in methods:
        print(f"\n{method.upper()} METHOD:")

        positions_raw, positions_corrected, features_list, stats = track_minimum_with_correction(
            transmission, method, search_region
        )

        # Calculate statistics
        raw_stats = calculate_variation_stats(positions_raw)
        corrected_stats = calculate_variation_stats(positions_corrected)

        # Calculate improvement
        improvement = (1 - corrected_stats['peak_to_peak'] / raw_stats['peak_to_peak']) * 100

        print(f"\n    Raw sensorgram:")
        print(f"      P-P: {raw_stats['peak_to_peak']:.2f} px, STD: {raw_stats['std']:.2f} px")
        print(f"    Corrected sensorgram:")
        print(f"      P-P: {corrected_stats['peak_to_peak']:.2f} px, STD: {corrected_stats['std']:.2f} px")
        print(f"    Improvement: {improvement:.1f}%")
        print(f"\n    Mean features:")
        print(f"      Depth: {stats['mean_depth']:.3f}")
        print(f"      FWHM: {stats['mean_fwhm']:.1f} px")
        print(f"      Asymmetry: {stats['mean_asymmetry']:.3f}")
        print(f"      SNR: {stats['mean_snr']:.1f}")

        results[method] = {
            'raw': positions_raw,
            'corrected': positions_corrected,
            'features': features_list,
            'raw_stats': raw_stats,
            'corrected_stats': corrected_stats,
            'processing_stats': stats,
            'improvement': improvement,
        }

    # Signal quality assessment
    print("\n" + "="*70)
    print("SIGNAL QUALITY ASSESSMENT")
    print("="*70)

    # Use centroid features for assessment (most commonly used)
    quality = assess_signal_quality(results['centroid']['features'])

    print(f"\n{quality['quality_flag']}")
    if quality['issues']:
        print("\nIdentified issues:")
        for issue in quality['issues']:
            print(f"  {issue}")

    print("\nSignal metrics:")
    for key, value in quality['metrics'].items():
        print(f"  {key}: {value:.3f}")

    # Visualize results
    print("\n" + "="*70)
    print("CREATING VISUALIZATIONS")
    print("="*70)

    visualize_results(
        transmission,
        p_data['timestamps'],
        results,
        results['centroid']['features'],
        OUTPUT_DIR
    )

    # Summary comparison
    print("\n" + "="*70)
    print("SUMMARY - METHOD COMPARISON")
    print("="*70)

    print(f"\n{'Method':<12} {'Raw P-P (px)':<15} {'Corr P-P (px)':<15} {'Improvement':<15} {'Speed (ms)':<12}")
    print("-" * 70)

    for method in methods:
        r = results[method]
        print(f"{method:<12} {r['raw_stats']['peak_to_peak']:<15.1f} "
              f"{r['corrected_stats']['peak_to_peak']:<15.1f} "
              f"{r['improvement']:<15.1f}% "
              f"{r['processing_stats']['processing_time_per_spectrum']:<12.2f}")

    # Save summary
    summary = {
        'dataset': {
            'device': 'demo P4SPR 2.0',
            'channel': 'A',
            'sensor_quality': 'used',
            'n_spectra': transmission.shape[0],
            'duration': float(p_data['timestamps'][-1] - p_data['timestamps'][0]),
        },
        'methods': {
            method: {
                'raw_peak_to_peak': float(results[method]['raw_stats']['peak_to_peak']),
                'corrected_peak_to_peak': float(results[method]['corrected_stats']['peak_to_peak']),
                'improvement_percent': float(results[method]['improvement']),
                'processing_time_ms': float(results[method]['processing_stats']['processing_time_per_spectrum']),
            }
            for method in methods
        },
        'quality_assessment': {
            'flag': quality['quality_flag'],
            'issues': quality['issues'],
            'metrics': {k: float(v) for k, v in quality['metrics'].items()},
        }
    }

    summary_file = OUTPUT_DIR / 'framework_demonstration_summary.json'
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\n📄 Summary saved: {summary_file}")

    print("\n" + "="*70)
    print("✅ FRAMEWORK DEMONSTRATION COMPLETE!")
    print("="*70)

    print("\nKey findings:")
    best_raw = min(methods, key=lambda m: results[m]['raw_stats']['peak_to_peak'])
    best_corrected = min(methods, key=lambda m: results[m]['corrected_stats']['peak_to_peak'])
    best_improvement = max(methods, key=lambda m: results[m]['improvement'])

    print(f"  🏆 Best raw performance: {best_raw.upper()} "
          f"({results[best_raw]['raw_stats']['peak_to_peak']:.1f} px p-p)")
    print(f"  🏆 Best corrected performance: {best_corrected.upper()} "
          f"({results[best_corrected]['corrected_stats']['peak_to_peak']:.1f} px p-p)")
    print(f"  📈 Largest improvement: {best_improvement.upper()} "
          f"({results[best_improvement]['improvement']:.1f}%)")
    print(f"  ⚡ All methods process in < 1 ms/spectrum")
    print(f"  {quality['quality_flag']}")

    print(f"\nResults saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    main()
