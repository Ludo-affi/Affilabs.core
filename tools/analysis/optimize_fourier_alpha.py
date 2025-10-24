"""
Optimize Fourier Regularization Parameter (α) for Peak Detection

Tests different α values to find optimal balance between:
- Noise reduction (lower RU variation)
- Signal preservation (accurate peak tracking)
- Real-time performance (computation time)

The old software used α = 2000. This tool explores whether a different value
could achieve better than 4-5 RU peak-to-peak noise.

Usage:
    # Use debug data from application:
    python optimize_fourier_alpha.py data/debug/4_final_transmittance_ChA.npy

    # Or with specific alpha range:
    python optimize_fourier_alpha.py baseline_data.npy --alpha-min 1000 --alpha-max 5000

    # Generate synthetic test data:
    python optimize_fourier_alpha.py --synthetic
"""

import time
import numpy as np
import argparse
from pathlib import Path
from scipy.fftpack import dst, idct
from scipy.stats import linregress

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import logger


def calculate_fourier_weights(spectrum_length: int, alpha: float) -> np.ndarray:
    """Calculate Fourier regularization weights.

    Args:
        spectrum_length: Length of spectrum array
        alpha: Regularization parameter (higher = more smoothing)

    Returns:
        Weight array for DST coefficients
    """
    n = spectrum_length - 1
    phi = np.pi / n * np.arange(1, n)
    phi2 = phi**2
    weights = phi / (1 + alpha * phi2 * (1 + phi2))
    return weights


def find_peak_with_alpha(
    wavelengths: np.ndarray,
    spectrum: np.ndarray,
    alpha: float,
    window: int = 165
) -> float:
    """Find SPR peak using Fourier derivative with specified α.

    Args:
        wavelengths: Wavelength array
        spectrum: Transmission spectrum (0-100%)
        alpha: Fourier regularization parameter
        window: Linear regression window (±pixels)

    Returns:
        Peak wavelength in nm
    """
    try:
        # Linear baseline subtraction
        baseline = np.linspace(spectrum[0], spectrum[-1], len(spectrum))

        # Calculate Fourier weights for this α
        fourier_weights = calculate_fourier_weights(len(spectrum), alpha)

        # Fourier coefficients
        fourier_coeff = np.zeros_like(spectrum)
        fourier_coeff[0] = 2 * (spectrum[-1] - spectrum[0])

        # DST of baseline-subtracted spectrum
        baseline_subtracted = spectrum[1:-1] - baseline[1:-1]
        fourier_coeff[1:-1] = fourier_weights * dst(baseline_subtracted, type=1)

        # Derivative via IDCT
        derivative = idct(fourier_coeff, type=1)

        # Find zero-crossing
        zero_idx = derivative.searchsorted(0)

        # Validate zero-crossing
        if zero_idx < window or zero_idx > len(derivative) - window:
            return np.nan

        # Linear regression around zero-crossing
        start = max(zero_idx - window, 0)
        end = min(zero_idx + window, len(derivative))

        result = linregress(wavelengths[start:end], derivative[start:end])

        if abs(result.slope) < 1e-10:
            return np.nan

        peak_wavelength = -result.intercept / result.slope

        # Validate result
        if not (wavelengths[0] <= peak_wavelength <= wavelengths[-1]):
            return np.nan

        return float(peak_wavelength)

    except Exception as e:
        logger.debug(f"Peak finding failed with α={alpha}: {e}")
        return np.nan


def test_alpha_value(
    wavelengths: np.ndarray,
    spectra: list[np.ndarray],
    alpha: float,
    window: int = 165
) -> dict:
    """Test a specific α value on multiple spectra.

    Args:
        wavelengths: Wavelength array
        spectra: List of transmission spectra
        alpha: Fourier regularization parameter to test
        window: Linear regression window

    Returns:
        Dictionary with statistics for this α value
    """
    peaks = []
    computation_times = []

    for spectrum in spectra:
        t_start = time.perf_counter()
        peak = find_peak_with_alpha(wavelengths, spectrum, alpha, window)
        t_end = time.perf_counter()

        if not np.isnan(peak):
            peaks.append(peak)
            computation_times.append((t_end - t_start) * 1000)  # ms

    if len(peaks) < 2:
        return None

    peaks_array = np.array(peaks)

    # Calculate statistics
    mean_peak = np.mean(peaks_array)
    std_peak_nm = np.std(peaks_array)
    std_peak_ru = std_peak_nm * 355  # Convert to RU
    peak_to_peak_nm = np.max(peaks_array) - np.min(peaks_array)
    peak_to_peak_ru = peak_to_peak_nm * 355
    mean_time = np.mean(computation_times)

    return {
        'alpha': alpha,
        'num_peaks': len(peaks),
        'mean_peak_nm': mean_peak,
        'std_nm': std_peak_nm,
        'std_ru': std_peak_ru,
        'peak_to_peak_nm': peak_to_peak_nm,
        'peak_to_peak_ru': peak_to_peak_ru,
        'mean_time_ms': mean_time,
        'peaks': peaks_array
    }


def optimize_fourier_alpha(
    wavelengths: np.ndarray,
    spectra: list[np.ndarray],
    alpha_range: tuple[float, float] = (500, 10000),
    num_tests: int = 20
) -> dict:
    """Optimize α parameter by testing multiple values.

    Args:
        wavelengths: Wavelength array
        spectra: List of transmission spectra (stable baseline)
        alpha_range: (min, max) α values to test
        num_tests: Number of α values to test

    Returns:
        Dictionary with optimization results
    """
    # Generate α values to test (logarithmic spacing)
    alpha_values = np.logspace(
        np.log10(alpha_range[0]),
        np.log10(alpha_range[1]),
        num_tests
    )

    logger.info(f"🔬 Testing {num_tests} α values from {alpha_range[0]} to {alpha_range[1]}")
    logger.info(f"   Using {len(spectra)} spectra for evaluation")
    logger.info("")

    results = []

    for i, alpha in enumerate(alpha_values, 1):
        result = test_alpha_value(wavelengths, spectra, alpha)

        if result is not None:
            results.append(result)
            logger.info(
                f"   [{i:2d}/{num_tests}] α={alpha:7.0f} → "
                f"σ={result['std_ru']:5.2f} RU, "
                f"P2P={result['peak_to_peak_ru']:5.2f} RU, "
                f"time={result['mean_time_ms']:.2f}ms"
            )
        else:
            logger.warning(f"   [{i:2d}/{num_tests}] α={alpha:7.0f} → FAILED")

    if not results:
        logger.error("No valid results! All α values failed.")
        return None

    # Find optimal α (minimum RU noise)
    best_result = min(results, key=lambda r: r['std_ru'])

    logger.info("")
    logger.info("=" * 80)
    logger.info("📊 OPTIMIZATION RESULTS:")
    logger.info("")
    logger.info(f"   Old software α: 2000")
    logger.info(f"   Optimal α: {best_result['alpha']:.0f}")
    logger.info("")
    logger.info(f"   Best noise (std dev): {best_result['std_ru']:.3f} RU")
    logger.info(f"   Best peak-to-peak: {best_result['peak_to_peak_ru']:.3f} RU")
    logger.info(f"   Computation time: {best_result['mean_time_ms']:.2f} ms")
    logger.info("")

    # Compare to α=2000 if available
    old_software_result = next((r for r in results if abs(r['alpha'] - 2000) < 100), None)
    if old_software_result:
        logger.info(f"   Old software (α=2000):")
        logger.info(f"      Noise: {old_software_result['std_ru']:.3f} RU")
        logger.info(f"      P2P: {old_software_result['peak_to_peak_ru']:.3f} RU")
        logger.info("")

        improvement = (old_software_result['std_ru'] - best_result['std_ru']) / old_software_result['std_ru'] * 100
        if improvement > 1:
            logger.info(f"   🎉 IMPROVEMENT: {improvement:.1f}% noise reduction!")
        elif improvement < -1:
            logger.info(f"   ⚠️ Old software α=2000 is better by {-improvement:.1f}%")
        else:
            logger.info(f"   ✓ Performance similar (within 1%)")

    logger.info("=" * 80)

    return {
        'all_results': results,
        'best_result': best_result,
        'old_software_result': old_software_result,
        'alpha_values': alpha_values.tolist()
    }


def main():
    parser = argparse.ArgumentParser(description='Optimize Fourier α parameter')
    parser.add_argument('input_file', nargs='?', default=None,
                       help='NPY file with transmission spectrum (from debug folder)')
    parser.add_argument('--synthetic', action='store_true',
                       help='Generate synthetic test data')
    parser.add_argument('--alpha-min', type=float, default=500,
                       help='Minimum α to test')
    parser.add_argument('--alpha-max', type=float, default=10000,
                       help='Maximum α to test')
    parser.add_argument('--num-tests', type=int, default=20,
                       help='Number of α values to test')
    parser.add_argument('--num-spectra', type=int, default=60,
                       help='Number of spectra to use for testing (default: 60)')

    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("🔬 FOURIER REGULARIZATION (α) OPTIMIZER")
    print("=" * 80)

    # Load or generate data
    wavelengths = None
    spectra = []

    if args.synthetic:
        # Generate synthetic SPR spectrum with noise
        print("\n📊 Generating synthetic test data...")
        wavelengths = np.linspace(500, 900, 2048)  # Typical spectrometer range

        # Create realistic SPR dip
        center = 650  # nm
        width = 20    # nm
        depth = 30    # % transmission dip

        for i in range(args.num_spectra):
            # Base spectrum with SPR dip (Lorentzian)
            baseline = 75  # % transmission
            dip = depth / (1 + ((wavelengths - center) / width) ** 2)
            clean_spectrum = baseline - dip

            # Add realistic noise (~1 RU = 0.0028 nm)
            noise_nm = 0.003  # Equivalent to ~1 RU
            noise = np.random.normal(0, noise_nm, len(wavelengths))
            noisy_spectrum = clean_spectrum + noise

            spectra.append(noisy_spectrum)

        print(f"   ✓ Generated {len(spectra)} spectra")
        print(f"   ✓ Wavelength range: {wavelengths[0]:.1f}-{wavelengths[-1]:.1f} nm")
        print(f"   ✓ SPR dip at {center} nm")
        print(f"   ✓ Added ~1 RU noise")

    elif args.input_file:
        # Load from NPY file
        input_path = Path(args.input_file)

        if not input_path.exists():
            print(f"\n❌ Error: File not found: {input_path}")
            print("\n💡 To collect data:")
            print("   1. Edit settings/settings.py: SAVE_DEBUG_DATA = True")
            print("   2. Restart application and calibrate")
            print("   3. Run on baseline for 60+ seconds")
            print("   4. Find files in: data/debug/4_final_transmittance_*.npy")
            print("   5. Run: python optimize_fourier_alpha.py <file.npy>")
            return 1

        print(f"\n📂 Loading data from: {input_path.name}")

        try:
            # Load NPY file
            data = np.load(input_path, allow_pickle=True)

            # Handle different formats
            if data.ndim == 1:
                # Single spectrum - create multiple copies with noise
                print("   ⚠️  Single spectrum detected, generating multiple samples...")
                base_spectrum = data
                wavelengths = np.linspace(500, 900, len(base_spectrum))

                for i in range(args.num_spectra):
                    # Add slight noise variation
                    noise = np.random.normal(0, 0.001, len(base_spectrum))
                    spectra.append(base_spectrum + noise)

            elif data.ndim == 2:
                # Multiple spectra (rows or columns?)
                if data.shape[0] > data.shape[1]:
                    # More rows than columns: rows are spectra
                    print(f"   ✓ Found {data.shape[0]} spectra × {data.shape[1]} pixels")
                    wavelengths = np.linspace(500, 900, data.shape[1])
                    spectra = [data[i, :] for i in range(min(args.num_spectra, data.shape[0]))]
                else:
                    # More columns: columns are spectra
                    print(f"   ✓ Found {data.shape[1]} spectra × {data.shape[0]} pixels")
                    wavelengths = np.linspace(500, 900, data.shape[0])
                    spectra = [data[:, i] for i in range(min(args.num_spectra, data.shape[1]))]

            else:
                print(f"   ❌ Unexpected data shape: {data.shape}")
                return 1

            print(f"   ✓ Using {len(spectra)} spectra for optimization")
            print(f"   ✓ Spectrum length: {len(wavelengths)} points")

            # Try to load wavelength calibration
            calib_file = Path("calibration_data/detector_0_wavelength.npy")
            if calib_file.exists():
                try:
                    wavelengths = np.load(calib_file)
                    if len(wavelengths) == len(spectra[0]):
                        print(f"   ✓ Loaded wavelength calibration from {calib_file.name}")
                    else:
                        print(f"   ⚠️  Wavelength cal size mismatch, using linear spacing")
                        wavelengths = np.linspace(500, 900, len(spectra[0]))
                except Exception as e:
                    print(f"   ⚠️  Could not load wavelength cal: {e}")

        except Exception as e:
            print(f"   ❌ Error loading file: {e}")
            return 1

    else:
        # No input provided - guide user
        print("\n⚠️  No input file specified!")
        print("\n📖 USAGE OPTIONS:")
        print("\n   1. Use debug data from application:")
        print("      python optimize_fourier_alpha.py data/debug/4_final_transmittance_ChA.npy")
        print("\n   2. Generate synthetic test data:")
        print("      python optimize_fourier_alpha.py --synthetic")
        print("\n   3. Collect real data:")
        print("      a. Edit settings/settings.py: SAVE_DEBUG_DATA = True")
        print("      b. Restart application")
        print("      c. Complete calibration")
        print("      d. Run on stable baseline for 60 seconds")
        print("      e. Find transmission files in data/debug/")
        print("      f. Run: python optimize_fourier_alpha.py <file.npy>")

        # Check if debug folder exists
        debug_path = Path("data/debug")
        if debug_path.exists():
            transmittance_files = list(debug_path.glob("4_final_transmittance_*.npy"))
            if transmittance_files:
                print("\n✅ Found existing transmission files:")
                for f in sorted(transmittance_files)[-5:]:
                    print(f"   {f.name}")
                latest = sorted(transmittance_files)[-1]
                print(f"\n💡 Quick start:")
                print(f"   python optimize_fourier_alpha.py \"{latest}\"")

        return 0

    # Run optimization
    if wavelengths is None or not spectra:
        print("\n❌ No data available for optimization")
        return 1

    print(f"\n🔬 Testing {args.num_tests} α values ({args.alpha_min:.0f}-{args.alpha_max:.0f})")
    print(f"   Using {len(spectra)} spectra")
    print("")

    results = optimize_fourier_alpha(
        wavelengths,
        spectra,
        alpha_range=(args.alpha_min, args.alpha_max),
        num_tests=args.num_tests
    )

    if results:
        print("\n✅ Optimization complete!")
        print(f"\n💾 To apply optimal α={results['best_result']['alpha']:.0f}:")
        print("   1. Edit settings/settings.py")
        print(f"   2. Change line ~216: FOURIER_ALPHA = {results['best_result']['alpha']:.0f}")
        print("   3. Restart application")
        print("   4. Verify improved noise performance")

    return 0


if __name__ == '__main__':
    sys.exit(main())
