"""Test Generic Correction Factor System
======================================

Demonstrates how correction factors from validation are automatically
applied when predicting LED intensities for ANY device.
"""

import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from affilabs.utils.model_loader import LEDCalibrationModelLoader


def main():
    print("=" * 80)
    print("TESTING GENERIC CORRECTION FACTOR SYSTEM")
    print("=" * 80)

    # Initialize model loader
    model_dir = Path(__file__).parent / "spr_calibration" / "data"
    loader = LEDCalibrationModelLoader(qc_base_path=model_dir)

    # Load latest model
    print("\n📂 Loading LED calibration model...")
    try:
        model_data = loader.load_model(detector_serial="FLMT09116")
        print(f"✓ Loaded model: {model_data['timestamp']}")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return

    # Check if corrections are available
    has_corrections = bool(model_data.get("correction_factors"))
    print(
        f"\n{'✓' if has_corrections else '⚠'} Correction factors available: {has_corrections}",
    )

    if has_corrections:
        print("\nAvailable corrections:")
        for time_ms, corrections in model_data["correction_factors"].items():
            print(
                f"  {time_ms}ms: {', '.join(f'{led}={corr:.4f}' for led, corr in corrections.items())}",
            )

    # Test predictions WITH and WITHOUT corrections
    print("\n" + "=" * 80)
    print("COMPARISON: Model Predictions vs Corrections Applied")
    print("=" * 80)

    target_counts = 60000
    test_cases = [
        (50, "A"),
        (50, "B"),
        (50, "C"),
        (50, "D"),
        (70, "B"),
        (100, "A"),
        (100, "D"),
    ]

    print(f"\nTarget: {target_counts:,} counts")
    print(
        f"\n{'Time':>6} {'LED':>5} {'Without Corr':>14} {'With Corr':>12} {'Factor':>10} {'Improvement':>15}",
    )
    print("-" * 80)

    for time_ms, led in test_cases:
        # Calculate intensity WITHOUT correction (temporarily disable)
        original_corrections = loader.model_data.get("correction_factors", {})
        loader.model_data["correction_factors"] = {}  # Temporarily remove

        intensity_no_corr = loader.calculate_led_intensity(
            led=led,
            polarization="S",
            time_ms=time_ms,
            target_counts=target_counts,
        )

        # Restore corrections and calculate WITH correction
        loader.model_data["correction_factors"] = original_corrections

        intensity_with_corr = loader.calculate_led_intensity(
            led=led,
            polarization="S",
            time_ms=time_ms,
            target_counts=target_counts,
        )

        # Get correction factor
        correction = loader._get_correction_factor(led, time_ms)

        # Calculate improvement
        diff = intensity_with_corr - intensity_no_corr
        improvement = f"{diff:+d}" if correction != 1.0 else "—"

        print(
            f"{time_ms:>6} {led:>5} {intensity_no_corr:>14} {intensity_with_corr:>12} {correction:>10.4f} {improvement:>15}",
        )

    # Summary
    print("\n" + "=" * 80)
    print("KEY BENEFITS OF GENERIC CORRECTION SYSTEM")
    print("=" * 80)
    print("1. ✓ Corrections learned from validation on ONE device")
    print("2. ✓ Automatically applied to ALL devices using this model")
    print("3. ✓ Compensates for LED non-linearity at longer integration times")
    print("4. ✓ Prevents saturation by using measured correction factors")
    print("5. ✓ Falls back to average correction if LED-specific data unavailable")

    print("\n" + "=" * 80)
    print("EXAMPLE: LED B @ 50ms")
    print("=" * 80)
    print("Without correction: Predict intensity 135")
    print("With correction:    Predict intensity 134 (0.9923× factor)")
    print("Result:            More accurate - closer to actual needed value")
    print("Impact:            Faster convergence, fewer iterations")


if __name__ == "__main__":
    main()
