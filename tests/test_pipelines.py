"""Test Processing Pipeline System

Simple test to verify pipeline architecture works correctly.
"""

import os
import sys
from pathlib import Path

import numpy as np

# Add Old software to path and change directory
old_software_path = Path(__file__).parent / "Old software"
sys.path.insert(0, str(old_software_path))
os.chdir(old_software_path)

from utils.pipelines import initialize_pipelines
from utils.processing_pipeline import get_pipeline_registry


def create_synthetic_spr_data():
    """Create synthetic SPR spectrum for testing"""
    # Wavelengths (nm)
    wavelengths = np.linspace(560, 720, 1797)

    # Create synthetic transmission with SPR dip
    # Dip centered at 620 nm
    center = 620
    width = 20
    depth = 30  # % transmission drop

    # Gaussian dip
    transmission = 100 - depth * np.exp(-0.5 * ((wavelengths - center) / width) ** 2)

    # Add some noise
    noise = np.random.normal(0, 1.0, len(wavelengths))
    transmission += noise

    # Create intensity and reference that would produce this transmission
    # intensity = transmission * reference / 100
    reference = np.ones_like(wavelengths) * 30000  # Typical reference level
    intensity = transmission * reference / 100

    return wavelengths, intensity, reference, center


def test_pipelines():
    """Test all registered pipelines"""
    print("=" * 60)
    print("Processing Pipeline System Test")
    print("=" * 60)

    # Initialize pipelines
    print("\n1. Initializing pipelines...")
    initialize_pipelines()

    registry = get_pipeline_registry()
    print(f"   ✓ {len(registry.list_pipelines())} pipelines registered")

    # List available pipelines
    print("\n2. Available pipelines:")
    for metadata in registry.list_pipelines():
        print(f"   • {metadata.name} (v{metadata.version})")
        print(f"     {metadata.description}")

    # Create synthetic data
    print("\n3. Creating synthetic SPR data...")
    wavelengths, intensity, reference, true_center = create_synthetic_spr_data()
    print(f"   True resonance: {true_center:.2f} nm")

    # Test each pipeline
    print("\n4. Testing pipelines:")
    results = {}

    for pid in ["fourier", "centroid", "polynomial"]:
        try:
            # Set active pipeline
            registry.set_active_pipeline(pid)
            pipeline = registry.get_active_pipeline()

            # Process data
            result = pipeline.process(
                intensity=intensity,
                reference=reference,
                wavelengths=wavelengths,
            )

            if result.success:
                results[pid] = result.resonance_wavelength
                error = abs(result.resonance_wavelength - true_center)
                print(
                    f"   ✓ {pipeline.get_metadata().name:25} → {result.resonance_wavelength:6.2f} nm (error: {error:5.2f} nm)",
                )
            else:
                print(
                    f"   ✗ {pipeline.get_metadata().name:25} → FAILED: {result.error_message}",
                )

        except Exception as e:
            print(f"   ✗ {pid:25} → ERROR: {e}")

    # Compare results
    if len(results) > 1:
        print("\n5. Pipeline comparison:")
        pipeline_names = list(results.keys())
        print(
            f"   Max difference: {max(results.values()) - min(results.values()):.2f} nm",
        )

        for i, pid1 in enumerate(pipeline_names[:-1]):
            for pid2 in pipeline_names[i + 1 :]:
                diff = abs(results[pid1] - results[pid2])
                print(f"   {pid1} vs {pid2}: {diff:.2f} nm difference")

    # Test backward compatibility
    print("\n6. Testing backward compatibility:")
    try:
        from utils.spr_signal_processing import (
            calculate_transmission,
            find_resonance_wavelength_fourier,
        )

        # Set to Fourier pipeline
        registry.set_active_pipeline("fourier")

        # Use old functions (should use active pipeline internally if using compat layer)
        transmission = calculate_transmission(intensity, reference)
        resonance = find_resonance_wavelength_fourier(
            transmission_spectrum=transmission,
            wavelengths=wavelengths,
            fourier_weights=None,  # Will be calculated
            window_size=165,
        )

        print(f"   ✓ Legacy functions work: {resonance:.2f} nm")
    except Exception as e:
        print(f"   ✗ Legacy functions failed: {e}")

    print("\n" + "=" * 60)
    print("Pipeline system test complete!")
    print("=" * 60)


if __name__ == "__main__":
    test_pipelines()
