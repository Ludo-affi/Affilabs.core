"""Compare Pipeline 1 (Fourier) vs Pipeline 2 (Adaptive Multi-Feature).

This script demonstrates the differences between the two pipelines,
particularly showing how Pipeline 2 handles jitter and artifacts better.
"""

import numpy as np

from utils.pipelines import initialize_pipelines
from utils.processing_pipeline import get_pipeline_registry

# Initialize pipelines
initialize_pipelines()


def generate_spr_with_jitter(base_wavelength, fwhm, noise_level, jitter_amplitude):
    """Generate SPR spectrum with noise and jitter."""
    wavelengths = np.linspace(600, 800, 256)

    # Asymmetric Gaussian peak
    baseline = 60.0
    depth = 20.0
    left_sigma = fwhm / 2.355
    right_sigma = left_sigma * 1.3  # Red broadening

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
    transmission += np.random.normal(0, noise_level, len(wavelengths))

    # Add jitter (afterglow artifact)
    peak_offset = np.random.uniform(-jitter_amplitude, jitter_amplitude)
    base_wavelength += peak_offset

    return wavelengths, transmission, base_wavelength


def compare_pipelines():
    """Compare Pipeline 1 vs Pipeline 2 on simulated data with jitter."""
    print("=" * 80)
    print("PIPELINE COMPARISON: Fourier vs Adaptive Multi-Feature")
    print("=" * 80)
    print()

    # Get pipelines
    registry = get_pipeline_registry()

    # Simulate measurements with jitter
    print("Simulating 30 measurements with periodic afterglow jitter...")
    print("-" * 80)

    true_wavelengths = []
    pipeline1_results = []
    pipeline2_results = []
    pipeline2_confidences = []
    pipeline2_jitter_flags = []

    for frame in range(30):
        # True wavelength drifts slowly (simulating real binding)
        true_wavelength = 650.0 + 0.3 * frame  # 9 nm total shift

        # Add periodic jitter every 3rd frame
        jitter_amplitude = 1.5 if frame % 3 == 0 else 0.0

        # Generate spectrum
        wavelengths, transmission, actual_wavelength = generate_spr_with_jitter(
            base_wavelength=true_wavelength,
            fwhm=30.0,
            noise_level=0.3,
            jitter_amplitude=jitter_amplitude,
        )

        true_wavelengths.append(actual_wavelength)

        # Process with Pipeline 1 (Fourier)
        registry.set_active_pipeline("fourier")
        pipeline1 = registry.get_pipeline("fourier")
        result1 = pipeline1.find_resonance_wavelength(transmission, wavelengths)
        pipeline1_results.append(result1)

        # Process with Pipeline 2 (Adaptive)
        registry.set_active_pipeline("adaptive")
        pipeline2 = registry.get_pipeline("adaptive")
        timestamp = frame * 0.1  # 100ms per frame
        result2, metadata2 = pipeline2.find_resonance_wavelength(
            transmission,
            wavelengths,
            timestamp=timestamp,
        )
        pipeline2_results.append(result2)
        pipeline2_confidences.append(metadata2["confidence"])
        pipeline2_jitter_flags.append(metadata2["jitter_flag"])

    print(f"Completed {len(true_wavelengths)} measurements")
    print()

    # Calculate statistics
    print("RESULTS:")
    print("=" * 80)

    # Errors
    pipeline1_errors = np.abs(np.array(pipeline1_results) - np.array(true_wavelengths))
    pipeline2_errors = np.abs(np.array(pipeline2_results) - np.array(true_wavelengths))

    print("Pipeline 1 (Fourier):")
    print(f"  Mean Error:   {np.mean(pipeline1_errors):.3f} nm")
    print(f"  Std Error:    {np.std(pipeline1_errors):.3f} nm")
    print(f"  Max Error:    {np.max(pipeline1_errors):.3f} nm")
    print()

    print("Pipeline 2 (Adaptive Multi-Feature):")
    print(f"  Mean Error:   {np.mean(pipeline2_errors):.3f} nm")
    print(f"  Std Error:    {np.std(pipeline2_errors):.3f} nm")
    print(f"  Max Error:    {np.max(pipeline2_errors):.3f} nm")
    print(f"  Avg Confidence: {np.mean(pipeline2_confidences):.3f}")
    print(
        f"  Jitter Detected: {sum(pipeline2_jitter_flags)}/{len(pipeline2_jitter_flags)} frames",
    )
    print()

    # Improvement
    improvement_mean = (
        (np.mean(pipeline1_errors) - np.mean(pipeline2_errors))
        / np.mean(pipeline1_errors)
        * 100
    )
    improvement_std = (
        (np.std(pipeline1_errors) - np.std(pipeline2_errors))
        / np.std(pipeline1_errors)
        * 100
    )

    print("IMPROVEMENT (Pipeline 2 vs Pipeline 1):")
    print("-" * 80)
    print(
        f"Mean Error:     {improvement_mean:+.1f}% {'better' if improvement_mean > 0 else 'worse'}",
    )
    print(
        f"Std Error:      {improvement_std:+.1f}% {'better' if improvement_std > 0 else 'worse'}",
    )
    print()

    # Temporal smoothness
    pipeline1_velocity = np.abs(np.diff(pipeline1_results))
    pipeline2_velocity = np.abs(np.diff(pipeline2_results))

    print("TEMPORAL SMOOTHNESS:")
    print("-" * 80)
    print(f"Pipeline 1 mean |velocity|: {np.mean(pipeline1_velocity):.3f} nm/frame")
    print(f"Pipeline 2 mean |velocity|: {np.mean(pipeline2_velocity):.3f} nm/frame")
    smoothness_improvement = (
        (np.mean(pipeline1_velocity) - np.mean(pipeline2_velocity))
        / np.mean(pipeline1_velocity)
        * 100
    )
    print(f"Smoothness improvement: {smoothness_improvement:+.1f}%")
    print()

    # Show some examples
    print("EXAMPLE MEASUREMENTS (frames with jitter):")
    print("-" * 80)
    print(
        f"{'Frame':<8} {'True':<10} {'Pipeline 1':<12} {'Pipeline 2':<12} {'Jitter?':<10}",
    )
    print("-" * 80)
    for frame in [0, 3, 6, 9, 12, 15, 18, 21, 24, 27]:
        jitter_marker = "[!] YES" if pipeline2_jitter_flags[frame] else "    No"
        print(
            f"{frame:<8} {true_wavelengths[frame]:<10.3f} "
            f"{pipeline1_results[frame]:<12.3f} {pipeline2_results[frame]:<12.3f} "
            f"{jitter_marker}",
        )

    print()
    print("=" * 80)
    print("KEY FINDINGS:")
    print("=" * 80)

    if improvement_mean > 10:
        print("[+] Pipeline 2 shows SIGNIFICANT accuracy improvement")
    elif improvement_mean > 0:
        print("[+] Pipeline 2 shows moderate accuracy improvement")
    else:
        print("[ ] Similar accuracy (both pipelines perform well)")

    if improvement_std > 10:
        print("[+] Pipeline 2 has MUCH lower variance (more stable)")
    elif improvement_std > 0:
        print("[+] Pipeline 2 has lower variance (more stable)")

    if smoothness_improvement > 10:
        print("[+] Pipeline 2 produces SMOOTHER trajectories (better jitter rejection)")

    jitter_detection_rate = sum(pipeline2_jitter_flags) / sum(
        1 for i in range(30) if i % 3 == 0
    )
    if jitter_detection_rate > 0.7:
        print(
            f"[+] Pipeline 2 detects jitter effectively ({jitter_detection_rate:.0%} detection rate)",
        )

    print()
    print("RECOMMENDATION:")
    print("-" * 80)
    if improvement_mean > 5 or improvement_std > 10:
        print("==> Use Pipeline 2 for this type of data (noisy with afterglow)")
    else:
        print(
            "==> Both pipelines work well; Pipeline 1 is faster, Pipeline 2 more robust",
        )
    print()
    print("=" * 80)


if __name__ == "__main__":
    compare_pipelines()
