"""Test and demonstrate Pipeline 2: Adaptive Multi-Feature Analysis.

This script demonstrates the innovative features of Pipeline 2:
- 3D feature tracking (wavelength, FWHM, depth)
- Temporal Kalman filtering
- Asymmetric peak modeling
- Jitter detection
"""

import numpy as np

from utils.pipelines.adaptive_multifeature_pipeline import AdaptiveMultiFeaturePipeline


def generate_synthetic_spr_data(
    base_wavelength=650,
    fwhm=30,
    depth=20,
    num_points=256,
    noise_level=0.5,
    asymmetry=1.2,
):
    """Generate synthetic SPR spectrum with asymmetric peak.

    Args:
        base_wavelength: Peak center (nm)
        fwhm: Full-width at half-maximum (nm)
        depth: Peak depth (% transmission drop)
        num_points: Number of spectral points
        noise_level: Noise amplitude (%)
        asymmetry: Right/left slope ratio (>1 = red broadening)

    Returns:
        Tuple of (wavelengths, transmission)

    """
    wavelengths = np.linspace(600, 800, num_points)

    # Asymmetric Gaussian
    baseline = 60.0
    left_sigma = fwhm / 2.355  # Convert FWHM to sigma
    right_sigma = left_sigma * asymmetry

    transmission = np.zeros_like(wavelengths)
    for i, wl in enumerate(wavelengths):
        if wl < base_wavelength:
            transmission[i] = baseline - depth * np.exp(
                -(((wl - base_wavelength) / left_sigma) ** 2),
            )
        else:
            transmission[i] = baseline - depth * np.exp(
                -(((wl - base_wavelength) / right_sigma) ** 2),
            )

    # Add noise
    transmission += np.random.normal(0, noise_level, num_points)

    return wavelengths, transmission


def simulate_binding_event():
    """Simulate a binding event with realistic SPR dynamics."""
    print("=" * 80)
    print("PIPELINE 2 DEMONSTRATION: Adaptive Multi-Feature SPR Analysis")
    print("=" * 80)
    print()

    # Initialize pipeline
    pipeline = AdaptiveMultiFeaturePipeline()

    print(f"Pipeline: {pipeline.name}")
    print(f"Description: {pipeline.description}")
    print()

    # Simulate time-series: baseline → binding → plateau
    num_frames = 50
    wavelengths_data = []
    fwhm_data = []
    depth_data = []
    confidence_data = []
    jitter_flags = []

    print("Simulating binding event (50 frames)...")
    print("-" * 80)

    for frame in range(num_frames):
        # Simulate binding kinetics: exponential approach to plateau
        if frame < 10:
            # Baseline
            peak_wavelength = 650.0
            peak_fwhm = 30.0
            peak_depth = 20.0
        elif frame < 30:
            # Binding phase (exponential)
            progress = (frame - 10) / 20.0
            shift = 10.0 * (1 - np.exp(-3 * progress))  # Exponential approach
            peak_wavelength = 650.0 + shift
            peak_fwhm = 30.0 + 2.0 * progress  # Slight broadening
            peak_depth = 20.0 + 5.0 * progress  # Deeper dip
        else:
            # Plateau
            peak_wavelength = 659.5
            peak_fwhm = 32.0
            peak_depth = 25.0

        # Add jitter to simulate afterglow (high frequency, small amplitude)
        if frame % 3 == 0:  # Periodic jitter
            jitter = np.random.uniform(-0.5, 0.5)
            peak_wavelength += jitter

        # Generate spectrum
        wavelengths, transmission = generate_synthetic_spr_data(
            base_wavelength=peak_wavelength,
            fwhm=peak_fwhm,
            depth=peak_depth,
            noise_level=0.3,
            asymmetry=1.3,  # Red-side broadening
        )

        # Process with Pipeline 2
        timestamp = frame * 0.1  # 100ms per frame
        result_wavelength, metadata = pipeline.find_resonance_wavelength(
            transmission,
            wavelengths,
            timestamp=timestamp,
        )

        # Store results
        wavelengths_data.append(result_wavelength)
        fwhm_data.append(metadata["fwhm"])
        depth_data.append(metadata["depth"])
        confidence_data.append(metadata["confidence"])
        jitter_flags.append(metadata["jitter_flag"])

        # Print selected frames
        if frame % 10 == 0 or frame < 3:
            print(f"Frame {frame:2d}:")
            print(
                f"  Wavelength: {result_wavelength:.3f} nm (raw: {metadata['raw_wavelength']:.3f} nm)",
            )
            print(f"  FWHM: {metadata['fwhm']:.2f} nm")
            print(f"  Depth: {metadata['depth']:.2f}%")
            print(f"  Confidence: {metadata['confidence']:.3f}")
            print(f"  Jitter Flag: {metadata['jitter_flag']}")
            print(f"  Temporal Coherence: {metadata['temporal_coherence']:.3f}")
            print(
                f"  Asymmetry: L={metadata['left_slope']:.2f}, R={metadata['right_slope']:.2f}",
            )
            print()

    print("-" * 80)
    print()

    # Analysis
    print("MULTI-FEATURE ANALYSIS:")
    print("-" * 80)

    # Calculate statistics
    wavelength_shift = wavelengths_data[-1] - wavelengths_data[0]
    fwhm_change = fwhm_data[-1] - fwhm_data[0]
    depth_change = depth_data[-1] - depth_data[0]
    jitter_count = sum(jitter_flags)
    avg_confidence = np.mean(confidence_data)

    print(f"Wavelength Shift: {wavelength_shift:.3f} nm")
    print(f"FWHM Change: {fwhm_change:.2f} nm")
    print(f"Depth Change: {depth_change:.2f}%")
    print(f"Jitter Events Detected: {jitter_count} / {num_frames}")
    print(f"Average Confidence: {avg_confidence:.3f}")
    print()

    # Correlation analysis
    wavelength_fwhm_corr = np.corrcoef(wavelengths_data, fwhm_data)[0, 1]
    wavelength_depth_corr = np.corrcoef(wavelengths_data, depth_data)[0, 1]

    print(f"Wavelength-FWHM Correlation: {wavelength_fwhm_corr:.3f}")
    print(f"Wavelength-Depth Correlation: {wavelength_depth_corr:.3f}")
    print()

    # Interpretation
    print("INTERPRETATION:")
    print("-" * 80)
    if wavelength_shift > 5.0:
        print("[+] Significant binding detected (wavelength shift > 5 nm)")
    else:
        print("[ ] No significant binding detected")

    if abs(fwhm_change) < 5.0:
        print("[+] Stable peak width (homogeneous binding)")
    else:
        print("[ ] Peak broadening detected (heterogeneous binding or artifacts)")

    if jitter_count < num_frames * 0.2:
        print(
            f"[+] Low jitter rate ({jitter_count}/{num_frames} = {100*jitter_count/num_frames:.1f}%)",
        )
    else:
        print(
            f"[!] High jitter rate ({jitter_count}/{num_frames} = {100*jitter_count/num_frames:.1f}%)",
        )

    if wavelength_fwhm_corr > 0.8:
        print("[+] Strong wavelength-FWHM correlation (expected for red broadening)")

    print()
    print("=" * 80)
    print("KEY INNOVATIONS OF PIPELINE 2:")
    print("=" * 80)
    print(
        "1. Tracks 3 features simultaneously (wavelength, FWHM, depth) ==> more robust",
    )
    print("2. Temporal filtering ==> rejects jitter, smooth trajectories")
    print("3. Advanced peak model ==> accurate for complex peak shapes")
    print("4. Artifact detection ==> flags spurious measurements automatically")
    print("5. Confidence scoring ==> quantifies measurement quality")
    print("6. Temporal coherence ==> validates physical plausibility")
    print()
    print("RESULT: More accurate, artifact-resistant SPR measurements!")
    print("=" * 80)


if __name__ == "__main__":
    simulate_binding_event()
