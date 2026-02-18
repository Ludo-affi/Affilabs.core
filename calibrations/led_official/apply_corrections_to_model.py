"""Apply Validation-Based Corrections to LED Model
================================================

This script uses the validation results to improve LED model predictions by:
1. Adding per-integration-time slope lookup (instead of linear extrapolation)
2. Adding saturation limits based on empirical data
3. Creating a corrected model file for use in calibration

Based on validation results from led_calibration_multistage_20251213_184717.json
"""

import json
from datetime import datetime
from pathlib import Path


def load_multistage_model(json_path):
    """Load the multistage calibration model."""
    with open(json_path) as f:
        return json.load(f)


def create_corrected_model(validation_data):
    """Create corrected model with per-time slopes and saturation limits."""
    led_models = validation_data["led_models"]
    validation = validation_data["validation"]

    corrected_model = {
        "version": "2.0",
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "description": "LED model with validation-based corrections and saturation limits",
        "source_file": "led_calibration_multistage_20251213_184717.json",
        "led_models": {},
        "dark_counts_per_time": validation_data["dark_counts_per_time"],
    }

    # Process each LED
    for led_name, slopes_data in led_models.items():
        # Build slope lookup table
        slope_lookup = {}
        max_safe_time = 100  # Default: all times safe

        for entry in slopes_data:
            time_ms = int(entry["time_ms"])
            slope = entry["slope"]
            slope_lookup[time_ms] = slope

        # Determine saturation limits from validation
        # LED B: saturated at 100ms with predicted I=68
        # LED C: saturated at 100ms with predicted I=50
        saturation_limits = {}

        if led_name == "B":
            # From validation: saturated at 100ms, but worked at 70ms
            saturation_limits = {
                70: 255,  # Max safe at 70ms
                100: 0,  # Unusable at 100ms
            }
            max_safe_time = 70

        elif led_name == "C":
            # From validation: saturated at 70ms and 100ms, worked at 50ms
            saturation_limits = {
                50: 255,  # Max safe at 50ms
                70: 0,  # Unusable at 70ms
                100: 0,  # Unusable at 100ms
            }
            max_safe_time = 50

        else:
            # LEDs A & D work at all times
            saturation_limits = {
                100: 255,  # Max safe at all times
            }
            max_safe_time = 100

        # Calculate correction factors based on validation errors
        correction_factors = {}
        for v in validation:
            if v["led"] == led_name and abs(v["error_pct"]) < 50:  # Exclude saturated
                time_ms = v["time_ms"]
                # If model underpredicts (negative error), need higher intensity
                # If model overpredicts (positive error), need lower intensity
                error_pct = v["error_pct"]
                correction = 1.0 - (
                    error_pct / 100.0
                )  # e.g., +5% error → 0.95× correction
                correction_factors[time_ms] = correction

        corrected_model["led_models"][led_name] = {
            "slopes": slope_lookup,
            "saturation_limits": saturation_limits,
            "max_safe_integration_time_ms": max_safe_time,
            "correction_factors": correction_factors,
            "base_slope_10ms": slope_lookup.get(10, 0),
            "measurement_note": f"LED {led_name}: Measured at {list(slope_lookup.keys())}ms",
        }

    return corrected_model


def predict_led_intensity_corrected(
    model,
    led_name,
    target_counts,
    integration_time_ms,
):
    """Predict LED intensity using corrected model with per-time slopes.

    Args:
        model: Corrected model dictionary
        led_name: 'A', 'B', 'C', or 'D'
        target_counts: Desired detector counts
        integration_time_ms: Integration time in ms

    Returns:
        Predicted intensity (0-255) or None if saturated

    """
    led_data = model["led_models"][led_name]

    # Check if this integration time is safe
    max_safe_time = led_data["max_safe_integration_time_ms"]
    if integration_time_ms > max_safe_time:
        print(
            f"   ⚠ LED {led_name} saturates at {integration_time_ms}ms (max safe: {max_safe_time}ms)",
        )
        return None

    # Get slope for this integration time (or interpolate)
    slopes = led_data["slopes"]

    if integration_time_ms in slopes:
        # Exact match
        slope = slopes[integration_time_ms]
    else:
        # Linear interpolation between nearest measured times
        times = sorted(slopes.keys())

        if integration_time_ms < times[0]:
            # Extrapolate down from first measurement
            slope = slopes[times[0]] * (integration_time_ms / times[0])
        elif integration_time_ms > times[-1]:
            # Extrapolate up from last measurement
            slope = slopes[times[-1]] * (integration_time_ms / times[-1])
        else:
            # Interpolate between two measurements
            t_low = max(t for t in times if t < integration_time_ms)
            t_high = min(t for t in times if t > integration_time_ms)

            slope_low = slopes[t_low]
            slope_high = slopes[t_high]

            # Linear interpolation
            weight = (integration_time_ms - t_low) / (t_high - t_low)
            slope = slope_low + weight * (slope_high - slope_low)

    # Calculate intensity: counts = slope * intensity
    # intensity = counts / slope
    raw_intensity = target_counts / slope

    # Apply correction factor if available
    correction_factors = led_data.get("correction_factors", {})
    if integration_time_ms in correction_factors:
        correction = correction_factors[integration_time_ms]
        raw_intensity *= correction

    # Clamp to valid range
    intensity = max(0, min(255, int(round(raw_intensity))))

    return intensity


def main():
    print("=" * 80)
    print("CREATING CORRECTED LED MODEL")
    print("=" * 80)

    # Load multistage validation data
    input_file = (
        Path(__file__).parent / "led_calibration_multistage_20251213_184717.json"
    )

    if not input_file.exists():
        print(f"❌ Error: Input file not found: {input_file}")
        return

    print(f"\n📂 Loading: {input_file.name}")
    validation_data = load_multistage_model(input_file)

    # Create corrected model
    print("\n🔧 Creating corrected model...")
    corrected_model = create_corrected_model(validation_data)

    # Save corrected model
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = Path(__file__).parent / f"led_model_corrected_{timestamp}.json"

    with open(output_file, "w") as f:
        json.dump(corrected_model, f, indent=2)

    print(f"✅ Corrected model saved: {output_file.name}")

    # ===== DEMONSTRATION =====
    print("\n" + "=" * 80)
    print("DEMONSTRATION: Predict LED Intensity for 60,000 Counts")
    print("=" * 80)

    target_counts = 60000
    test_times = [50, 70, 100]

    print(f"\nTarget: {target_counts:,} counts")
    print(
        f"\n{'Time':>6} {'LED':>5} {'Old Model':>12} {'New Model':>12} {'Status':>20}",
    )
    print("-" * 80)

    for time_ms in test_times:
        for led_name in ["A", "B", "C", "D"]:
            # Old model (simple linear extrapolation)
            slope_10ms = corrected_model["led_models"][led_name]["base_slope_10ms"]
            old_intensity = int((target_counts * 10) / (slope_10ms * time_ms))
            old_intensity = min(255, old_intensity)

            # New model (per-time slope with saturation check)
            new_intensity = predict_led_intensity_corrected(
                corrected_model,
                led_name,
                target_counts,
                time_ms,
            )

            if new_intensity is None:
                status = "⚠ SATURATED"
                new_str = "N/A"
            else:
                status = "✓ OK"
                new_str = str(new_intensity)

            print(
                f"{time_ms:>6} {led_name:>5} {old_intensity:>12} {new_str:>12} {status:>20}",
            )

    print("\n" + "=" * 80)
    print("KEY IMPROVEMENTS")
    print("=" * 80)
    print("1. ✅ Uses actual measured slopes at each integration time")
    print("2. ✅ Detects saturation BEFORE trying to use LED B/C at 70-100ms")
    print("3. ✅ Applies empirical correction factors from validation")
    print("4. ✅ Prevents convergence failures by avoiding saturated regions")
    print("\nNext step: Update main calibration code to use corrected model!")


if __name__ == "__main__":
    main()
