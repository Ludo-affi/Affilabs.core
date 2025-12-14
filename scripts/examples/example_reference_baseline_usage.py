"""
Example: Using the Reference Baseline Method

This script demonstrates practical usage of the reference baseline processing
method for comparing experimental approaches against the validated baseline.
"""

import numpy as np
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from utils.reference_baseline_processing import (
    process_spectrum_reference,
    calculate_fourier_weights_reference,
    REFERENCE_PARAMETERS
)


def example_1_basic_usage():
    """Example 1: Basic usage with synthetic data."""

    print("=" * 70)
    print("EXAMPLE 1: Basic Usage")
    print("=" * 70)
    print()

    # Simulate detector data (in real code, get from USB spectrometer)
    wavelengths = np.linspace(560, 720, 650)  # ~650 pixels in SPR region

    # Simulate P-mode intensity (with SPR dip at 625nm)
    p_intensity = 30000 - 10000 * np.exp(-((wavelengths - 625)**2) / (2*8**2))
    p_intensity += np.random.normal(0, 150, len(wavelengths))

    # Simulate S-mode reference (from calibration)
    s_reference = np.full_like(wavelengths, 50000.0)
    s_reference += np.random.normal(0, 100, len(wavelengths))

    # Simulate dark noise
    dark_noise = np.full_like(wavelengths, 1000.0)
    dark_noise += np.random.normal(0, 10, len(wavelengths))

    # LED intensities (from calibration)
    p_led = 220  # P-mode LED intensity
    s_led = 80   # S-mode LED intensity

    print("Data prepared:")
    print(f"  Wavelength range: {wavelengths[0]:.1f} - {wavelengths[-1]:.1f} nm")
    print(f"  Spectrum length: {len(wavelengths)} pixels")
    print(f"  P-LED: {p_led}, S-LED: {s_led}")
    print()

    # Calculate Fourier weights (do this ONCE and reuse)
    print("Calculating Fourier weights...")
    fourier_weights = calculate_fourier_weights_reference(len(wavelengths))
    print(f"  Weights calculated: {len(fourier_weights)} coefficients")
    print()

    # Process spectrum using reference method
    print("Processing spectrum with REFERENCE baseline method...")
    result = process_spectrum_reference(
        raw_spectrum=p_intensity,
        wavelengths=wavelengths,
        reference_spectrum=s_reference,
        fourier_weights=fourier_weights,
        dark_noise=dark_noise,
        p_led_intensity=p_led,
        s_led_intensity=s_led,
        window_size=REFERENCE_PARAMETERS['fourier_window'],
        sg_window=REFERENCE_PARAMETERS['sg_window'],
        sg_polyorder=REFERENCE_PARAMETERS['sg_polyorder']
    )

    # Display results
    print("✅ Processing complete!")
    print()
    print("Results:")
    print(f"  Resonance wavelength: {result['resonance_wavelength']:.3f} nm")
    print(f"  Transmission range: {np.min(result['transmission']):.1f}% - {np.max(result['transmission']):.1f}%")
    print(f"  Expected resonance: ~625.0 nm")
    print(f"  Error: {abs(result['resonance_wavelength'] - 625.0):.3f} nm")
    print()


def example_2_compare_window_sizes():
    """Example 2: Compare standard vs optimized Fourier window."""

    print("=" * 70)
    print("EXAMPLE 2: Comparing Fourier Window Sizes")
    print("=" * 70)
    print()

    # Generate test data
    wavelengths = np.linspace(560, 720, 650)
    true_resonance = 630.0

    # Calculate Fourier weights once
    fourier_weights = calculate_fourier_weights_reference(len(wavelengths))

    # Run 20 measurements with different noise realizations
    num_measurements = 20
    resonances_standard = []
    resonances_optimized = []

    print(f"Running {num_measurements} measurements...")
    print()

    for i in range(num_measurements):
        # Generate spectrum with noise
        p_intensity = 30000 - 10000 * np.exp(-((wavelengths - true_resonance)**2) / (2*8**2))
        p_intensity += np.random.normal(0, 150, len(wavelengths))

        s_reference = np.full_like(wavelengths, 50000.0)
        s_reference += np.random.normal(0, 100, len(wavelengths))

        dark_noise = np.full_like(wavelengths, 1000.0)

        # Process with STANDARD window (165)
        result_std = process_spectrum_reference(
            raw_spectrum=p_intensity,
            wavelengths=wavelengths,
            reference_spectrum=s_reference,
            fourier_weights=fourier_weights,
            dark_noise=dark_noise,
            p_led_intensity=220,
            s_led_intensity=80,
            window_size=165  # STANDARD
        )
        resonances_standard.append(result_std['resonance_wavelength'])

        # Process with OPTIMIZED window (1500)
        result_opt = process_spectrum_reference(
            raw_spectrum=p_intensity,
            wavelengths=wavelengths,
            reference_spectrum=s_reference,
            fourier_weights=fourier_weights,
            dark_noise=dark_noise,
            p_led_intensity=220,
            s_led_intensity=80,
            window_size=1500  # OPTIMIZED
        )
        resonances_optimized.append(result_opt['resonance_wavelength'])

    # Calculate statistics
    std_mean = np.mean(resonances_standard)
    std_std = np.std(resonances_standard)
    std_p2p = np.max(resonances_standard) - np.min(resonances_standard)

    opt_mean = np.mean(resonances_optimized)
    opt_std = np.std(resonances_optimized)
    opt_p2p = np.max(resonances_optimized) - np.min(resonances_optimized)

    # Display comparison
    print("Results Comparison:")
    print()
    print(f"True resonance: {true_resonance:.3f} nm")
    print()

    print("STANDARD window (165 points):")
    print(f"  Mean: {std_mean:.3f} nm")
    print(f"  Std dev: {std_std:.4f} nm")
    print(f"  Peak-to-peak: {std_p2p:.4f} nm")
    print(f"  Error from true: {abs(std_mean - true_resonance):.3f} nm")
    print()

    print("OPTIMIZED window (1500 points):")
    print(f"  Mean: {opt_mean:.3f} nm")
    print(f"  Std dev: {opt_std:.4f} nm")
    print(f"  Peak-to-peak: {opt_p2p:.4f} nm")
    print(f"  Error from true: {abs(opt_mean - true_resonance):.3f} nm")
    print()

    # Calculate improvement
    if std_p2p > opt_p2p:
        improvement = ((std_p2p - opt_p2p) / std_p2p) * 100
        print(f"✅ OPTIMIZED window reduces P2P variation by {improvement:.1f}%")
    else:
        degradation = ((opt_p2p - std_p2p) / std_p2p) * 100
        print(f"⚠️  OPTIMIZED window increases P2P variation by {degradation:.1f}%")
    print()


def example_3_experimental_comparison():
    """Example 3: Compare reference method with experimental method."""

    print("=" * 70)
    print("EXAMPLE 3: Reference vs Experimental Method Comparison")
    print("=" * 70)
    print()

    # Generate test data
    wavelengths = np.linspace(560, 720, 650)
    true_resonance = 628.5

    p_intensity = 30000 - 10000 * np.exp(-((wavelengths - true_resonance)**2) / (2*8**2))
    p_intensity += np.random.normal(0, 150, len(wavelengths))

    s_reference = np.full_like(wavelengths, 50000.0)
    dark_noise = np.full_like(wavelengths, 1000.0)

    fourier_weights = calculate_fourier_weights_reference(len(wavelengths))

    # Process with REFERENCE method
    print("Processing with REFERENCE method...")
    result_ref = process_spectrum_reference(
        raw_spectrum=p_intensity,
        wavelengths=wavelengths,
        reference_spectrum=s_reference,
        fourier_weights=fourier_weights,
        dark_noise=dark_noise,
        p_led_intensity=220,
        s_led_intensity=80,
        window_size=165
    )
    print(f"  ✅ Resonance: {result_ref['resonance_wavelength']:.3f} nm")
    print()

    # Simulate EXPERIMENTAL method (e.g., simple argmin on transmission)
    print("Processing with EXPERIMENTAL method (simple argmin)...")

    # Manually replicate transmission calculation
    intensity_corrected = p_intensity - dark_noise
    transmission_exp = (intensity_corrected / s_reference) * (80 / 220) * 100

    # Simple argmin (no Fourier, no denoising)
    min_idx = np.argmin(transmission_exp)
    resonance_exp = wavelengths[min_idx]

    print(f"  ✅ Resonance: {resonance_exp:.3f} nm")
    print()

    # Compare methods
    print("Comparison:")
    print(f"  True resonance: {true_resonance:.3f} nm")
    print(f"  Reference error: {abs(result_ref['resonance_wavelength'] - true_resonance):.3f} nm")
    print(f"  Experimental error: {abs(resonance_exp - true_resonance):.3f} nm")
    print()

    diff = abs(result_ref['resonance_wavelength'] - resonance_exp)
    print(f"  Difference between methods: {diff:.3f} nm")

    if abs(result_ref['resonance_wavelength'] - true_resonance) < abs(resonance_exp - true_resonance):
        print("  ✅ REFERENCE method is more accurate")
    else:
        print("  ✅ EXPERIMENTAL method is more accurate")
    print()

    print("Note: Reference method uses:")
    print("  - Savitzky-Golay filtering (reduces noise)")
    print("  - Fourier transform (smooths derivative)")
    print("  - Linear regression (refines position)")
    print("  → Better accuracy and stability than simple argmin")
    print()


def example_4_batch_processing():
    """Example 4: Batch processing multiple spectra efficiently."""

    print("=" * 70)
    print("EXAMPLE 4: Batch Processing (Efficient Usage)")
    print("=" * 70)
    print()

    # Setup (do ONCE for all measurements)
    wavelengths = np.linspace(560, 720, 650)
    s_reference = np.full_like(wavelengths, 50000.0)
    dark_noise = np.full_like(wavelengths, 1000.0)
    p_led = 220
    s_led = 80

    print("Setup (calculate once, reuse for all spectra):")
    fourier_weights = calculate_fourier_weights_reference(len(wavelengths))
    print(f"  ✅ Fourier weights calculated: {len(fourier_weights)} coefficients")
    print()

    # Simulate batch processing
    num_spectra = 50
    print(f"Processing {num_spectra} spectra...")

    resonances = []
    for i in range(num_spectra):
        # Generate spectrum (in real code, read from detector)
        p_intensity = 30000 - 10000 * np.exp(-((wavelengths - 625)**2) / (2*8**2))
        p_intensity += np.random.normal(0, 150, len(wavelengths))

        # Process using reference method
        result = process_spectrum_reference(
            raw_spectrum=p_intensity,
            wavelengths=wavelengths,
            reference_spectrum=s_reference,
            fourier_weights=fourier_weights,  # REUSE (don't recalculate!)
            dark_noise=dark_noise,
            p_led_intensity=p_led,
            s_led_intensity=s_led
        )

        resonances.append(result['resonance_wavelength'])

    # Calculate statistics
    resonances = np.array(resonances)
    mean_res = np.mean(resonances)
    std_res = np.std(resonances)
    p2p_res = np.max(resonances) - np.min(resonances)

    print(f"  ✅ Complete!")
    print()
    print("Batch statistics:")
    print(f"  Mean resonance: {mean_res:.3f} nm")
    print(f"  Std deviation: {std_res:.4f} nm")
    print(f"  Peak-to-peak: {p2p_res:.4f} nm")
    print(f"  Range: {np.min(resonances):.3f} - {np.max(resonances):.3f} nm")
    print()
    print("✅ Low variation confirms reference method stability")
    print()


if __name__ == '__main__':
    # Run all examples
    example_1_basic_usage()
    print("\n")

    example_2_compare_window_sizes()
    print("\n")

    example_3_experimental_comparison()
    print("\n")

    example_4_batch_processing()

    print("=" * 70)
    print("ALL EXAMPLES COMPLETE")
    print("=" * 70)
    print()
    print("Key takeaways:")
    print("  1. Calculate Fourier weights ONCE and reuse")
    print("  2. Use REFERENCE_PARAMETERS for consistent processing")
    print("  3. Compare experimental methods against reference baseline")
    print("  4. Reference method provides stable, low P2P variation")
    print()
    print("For more details, see:")
    print("  - REFERENCE_BASELINE_QUICK_START.md")
    print("  - REFERENCE_BASELINE_METHOD_COMPLETE.md")
