"""Multi-Stage LED Calibration: Progressive Model Refinement
Tests at 10ms, 20ms, 30ms, 50ms, 70ms, 100ms integration times
Stops scanning if saturation detected
Validates model predictions at 50ms, 70ms, 100ms
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from affilabs.utils.controller import PicoP4SPR
from affilabs.utils.usb4000_wrapper import USB4000


def measure_led_response(
    controller,
    spectrometer,
    led_char,
    intensity,
    integration_time_ms,
    dark_counts,
    detector_wait_ms=50,
):
    """Measure single LED at given intensity and integration time.

    Args:
        detector_wait_ms: Time to wait after LED stabilization before detector sampling (default: 50ms)

    WARNING: This function uses DIRECT hardware commands (NOT HAL).
    This is acceptable for OEM calibration since:
    1. It's a one-time factory calibration process
    2. Creates the model that HAL will use for runtime
    3. Uses fixed detector_wait_ms (not settings-driven)

    The timing here is INDEPENDENT of runtime settings because this is
    measuring the LED-to-counts relationship, not performing live acquisition.

    """
    # Set integration time first (DIRECT hardware command)
    spectrometer.set_integration(integration_time_ms)
    time.sleep(0.05)

    # Turn on this LED (other LEDs stay off)
    intensities = {"a": 0, "b": 0, "c": 0, "d": 0}
    intensities[led_char] = intensity
    controller.set_batch_intensities(**intensities)
    time.sleep(0.3)  # LED settle time
    time.sleep(detector_wait_ms / 1000.0)  # Detector wait time

    # Measure (average of 3 scans, then average top 10 pixels)
    # NOTE: This is a DIRECT hardware call, NOT using HAL
    spectrum = spectrometer.intensities(num_scans=3)
    import numpy as np

    top_10_indices = np.argpartition(spectrum, -10)[-10:]
    top_10_avg = float(spectrum[top_10_indices].mean())
    corrected = top_10_avg - dark_counts

    # Enhanced saturation check: warn if approaching saturation (>60000 = 92% full)
    saturated_pixels = int((spectrum >= 65535).sum())
    near_saturation = int((spectrum >= 60000).sum())

    return {
        "raw_counts": top_10_avg,
        "corrected_counts": corrected,
        "saturated_wavelengths": saturated_pixels,
        "near_saturation_pixels": near_saturation,
        "is_saturated": saturated_pixels > 0 or top_10_avg >= 60000,
    }


def fit_linear_model(data_points):
    """Fit linear model: counts = slope * intensity
    Returns slope (counts per intensity unit)
    """
    if len(data_points) < 2:
        return None

    # Simple linear fit through origin: counts = k * intensity
    sum_i_c = sum(i * c for i, c in data_points)
    sum_i_i = sum(i * i for i, _ in data_points)

    if sum_i_i == 0:
        return None

    slope = sum_i_c / sum_i_i
    return slope


def main():
    print("=" * 80)
    print("MULTI-STAGE LED CALIBRATION WITH MODEL VALIDATION")
    print("=" * 80)
    print("\nStrategy:")
    print("  - Test at 10ms, 20ms, 30ms, 50ms, 70ms, 100ms integration times")
    print("  - Use 50ms detector wait time (fixed)")
    print("  - Reduced LED intensities to avoid saturation (<60k counts)")
    print("  - Stop scanning LED intensity if saturation detected")
    print("  - Validate model predictions at 50ms, 70ms, 100ms")
    print()

    # Connect hardware
    controller = PicoP4SPR()
    spectrometer = USB4000()

    if not controller.open():
        print("❌ Failed to connect to controller")
        return

    if not spectrometer.open():
        print("❌ Failed to connect to spectrometer")
        controller.close()
        return

    print("✓ Hardware connected\n")

    # Integration times to test
    integration_times = [10, 20, 30, 50, 70, 100]

    print("\n" + "=" * 80)
    print("⚠️  OEM CALIBRATION TIMING NOTICE")
    print("=" * 80)
    print("This script uses DIRECT hardware commands (NOT HAL).")
    print("This is intentional because:")
    print("  1. OEM calibration is a one-time factory process")
    print("  2. It measures LED-to-counts relationship at multiple times")
    print("  3. Creates the model that HAL will use for runtime")
    print("  4. Uses fixed detector_wait_ms (independent of settings)")
    print()
    print("Runtime calibration and live acquisition will use HAL with")
    print("centralized timing from settings.py (LED_ON_TIME_MS, DETECTOR_WAIT_MS, etc.)")
    print("=" * 80 + "\n")

    # Measure dark current at each integration time
    print("Measuring dark current at each integration time...")
    controller.set_batch_intensities(a=0, b=0, c=0, d=0)
    time.sleep(0.5)

    dark_counts_per_time = {}
    for time_ms in integration_times + [40, 60, 80, 90]:  # Extra for interpolation
        spectrometer.set_integration(float(time_ms))
        time.sleep(0.5)
        spectrum = spectrometer.intensities(num_scans=3)
        dark = float(spectrum.max())
        dark_counts_per_time[time_ms] = dark
        print(f"  {time_ms}ms: {dark:.0f} counts")
    print()

    # Storage for model data
    led_models = {"A": [], "B": [], "C": [], "D": []}  # List of (time_ms, slope) tuples
    all_results = []

    # Detector wait parameter (fixed at 50ms for consistency)
    DETECTOR_WAIT_MS = 50
    print(f"Detector wait time: {DETECTOR_WAIT_MS}ms (fixed)")
    print()

    # Test intensities - start with full range, stop if saturation detected
    # REDUCED INTENSITIES to avoid saturation (max 60000 counts = 92% detector capacity)
    base_intensities = [30, 60, 90, 120, 150]

    # =======================
    # MULTI-STAGE CALIBRATION
    # =======================
    for time_ms in integration_times:
        print("\n" + "=" * 80)
        print(f"STAGE {time_ms}ms: Individual LED Characterization")
        print("=" * 80)

        integration_time = float(time_ms)
        dark_counts = dark_counts_per_time[time_ms]
        stage_results = {
            "integration_time": integration_time,
            "dark_counts": dark_counts,
            "measurements": {},
        }

        for led_name, led_char in [("A", "a"), ("B", "b"), ("C", "c"), ("D", "d")]:
            print(f"\n{led_name}:")
            led_data = []

            # Test intensities until saturation detected
            for intensity in base_intensities:
                result = measure_led_response(
                    controller,
                    spectrometer,
                    led_char,
                    intensity,
                    integration_time,
                    dark_counts,
                    DETECTOR_WAIT_MS,
                )

                # Stop if saturated or near saturation (>60000 counts)
                if result["is_saturated"]:
                    if result["saturated_wavelengths"] > 0:
                        print(
                            f"  I={intensity:>3}: SATURATED ({result['saturated_wavelengths']} pixels @ 65535) - stopping scan",
                        )
                    else:
                        print(
                            f"  I={intensity:>3}: NEAR SATURATION ({result['raw_counts']:.0f} counts, >60000 threshold) - stopping scan",
                        )
                    break

                led_data.append((intensity, result["corrected_counts"]))

                # Show warning if approaching saturation
                warning = ""
                if result["near_saturation_pixels"] > 0:
                    warning = f" ⚠️ {result['near_saturation_pixels']} pixels >60k"
                print(
                    f"  I={intensity:>3}: {result['corrected_counts']:>8.0f} counts{warning}",
                )

            # Fit model if we have at least 2 points
            if len(led_data) >= 2:
                slope = fit_linear_model(led_data)
                if slope:
                    led_models[led_name].append((integration_time, slope))

                    # Compare to previous stages for linearity check
                    if len(led_models[led_name]) > 1:
                        base_slope = led_models[led_name][0][1]  # 10ms slope
                        expected_ratio = integration_time / 10.0
                        actual_ratio = slope / base_slope
                        print(
                            f"  Model: {slope:.2f} counts/intensity (ratio: {actual_ratio:.3f} vs {expected_ratio:.1f}x expected)",
                        )
                    else:
                        print(f"  Model: {slope:.2f} counts/intensity")

                    stage_results["measurements"][led_name] = {
                        "data": led_data,
                        "slope": slope,
                    }

        all_results.append(stage_results)

        # Turn off LEDs between stages
        controller.set_batch_intensities(a=0, b=0, c=0, d=0)
        time.sleep(0.3)

    # =======================
    # FINAL SUMMARY
    # =======================
    print("\n" + "=" * 80)
    print("FINAL MODEL SUMMARY")
    print("=" * 80)

    print(
        f"\n{'LED':>5} {'Time(ms)':>10} {'Slope':>15} {'Expected Ratio':>15} {'Actual Ratio':>15}",
    )
    print("-" * 80)

    for led_name in ["A", "B", "C", "D"]:
        model_data = led_models[led_name]
        base_slope = model_data[0][1]  # 10ms slope

        for i, (time_ms, slope) in enumerate(model_data):
            expected_ratio = time_ms / 10.0
            actual_ratio = slope / base_slope

            print(
                f"{led_name:>5} {time_ms:>10.0f} {slope:>15.2f} {expected_ratio:>15.1f}x {actual_ratio:>15.3f}x",
            )

    # =======================
    # MODEL VALIDATION: Test 60,000 Count Predictions
    # =======================
    print("\n" + "=" * 80)
    print("MODEL VALIDATION: Testing 60,000 Count Predictions")
    print("=" * 80)

    target_counts = 60000
    validation_times = [50, 70, 100]  # Test at these integration times

    print("\nCalculating predicted LED intensities to reach 60,000 counts...")
    print(
        f"\n{'Time':>6} {'LED':>5} {'Predicted I':>12} {'Actual Counts':>14} {'Error':>10} {'Error %':>10}",
    )
    print("-" * 80)

    validation_results = []

    for time_ms in validation_times:
        dark_counts = dark_counts_per_time.get(
            time_ms,
            dark_counts_per_time[10] * (time_ms / 10),
        )

        for led_name, led_char in [("A", "a"), ("B", "b"), ("C", "c"), ("D", "d")]:
            # Use 10ms slope as base
            slope_10ms = led_models[led_name][0][1]

            # Calculate required intensity: counts = slope_10ms * intensity * (time_ms / 10)
            # intensity = counts * 10 / (slope_10ms * time_ms)
            predicted_intensity = (target_counts * 10) / (slope_10ms * time_ms)
            predicted_intensity = int(round(min(255, predicted_intensity)))

            # Measure actual counts at this intensity
            result = measure_led_response(
                controller,
                spectrometer,
                led_char,
                predicted_intensity,
                float(time_ms),
                dark_counts,
                DETECTOR_WAIT_MS,
            )
            actual_counts = result["corrected_counts"]
            error = actual_counts - target_counts
            error_pct = (error / target_counts) * 100

            # Check for saturation
            if result["is_saturated"]:
                status = "⚠️ SAT"
                print(
                    f"{time_ms:>6} {led_name:>5} {predicted_intensity:>12} {actual_counts:>14.0f} {error:>10.0f} {error_pct:>9.1f}% {status}",
                )
            else:
                status = "✓" if abs(error_pct) < 5 else "⚠"
                print(
                    f"{time_ms:>6} {led_name:>5} {predicted_intensity:>12} {actual_counts:>14.0f} {error:>10.0f} {error_pct:>9.1f}% {status}",
                )

            validation_results.append(
                {
                    "time_ms": time_ms,
                    "led": led_name,
                    "predicted_intensity": predicted_intensity,
                    "actual_counts": actual_counts,
                    "error": error,
                    "error_pct": error_pct,
                },
            )

    # Calculate validation statistics
    errors = [v["error_pct"] for v in validation_results]
    avg_error = sum(errors) / len(errors)
    max_error = max(abs(e) for e in errors)

    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Average error: {avg_error:>6.2f}%")
    print(f"Max error:     {max_error:>6.2f}%")
    print(f"Target:        {target_counts:>6.0f} counts")

    within_5pct = sum(1 for e in errors if abs(e) < 5)
    within_10pct = sum(1 for e in errors if abs(e) < 10)
    total = len(errors)

    print(f"\nWithin ±5%:  {within_5pct}/{total} ({within_5pct/total*100:.0f}%)")
    print(f"Within ±10%: {within_10pct}/{total} ({within_10pct/total*100:.0f}%)")

    # =======================
    # BOUNDARY CONDITIONS FOR 60,000 COUNTS
    # =======================
    print("\n" + "=" * 80)
    print("BOUNDARY CONDITIONS TO REACH 60,000 COUNTS")
    print("=" * 80)
    print("\nUsing linear model: counts = slope * intensity * (time_ms / 10)")
    print("Target: 60,000 counts (≈91.5% detector fill)")
    print("\nPer LED, what (time_ms × intensity) product gives 60,000 counts:")
    print(
        f"\n{'LED':>5} {'Slope@10ms':>12} {'Time×Intensity':>16} {'Example: 50ms':>20} {'Example: 100ms':>20}",
    )
    print("-" * 80)

    for led_name in ["A", "B", "C", "D"]:
        model_data = led_models[led_name]
        slope_10ms = model_data[0][1]  # counts per intensity at 10ms

        # counts = slope_10ms * intensity * (time_ms / 10)
        # 60000 = slope_10ms * intensity * (time_ms / 10)
        # intensity * time_ms = 60000 * 10 / slope_10ms
        time_intensity_product = (target_counts * 10) / slope_10ms

        # Examples at different integration times
        intensity_at_50ms = min(255, time_intensity_product / 50)
        intensity_at_100ms = min(255, time_intensity_product / 100)

        print(
            f"{led_name:>5} {slope_10ms:>12.2f} {time_intensity_product:>16.0f} "
            f"I={intensity_at_50ms:>6.1f} ({intensity_at_50ms/255*100:>4.1f}%) "
            f"I={intensity_at_100ms:>6.1f} ({intensity_at_100ms/255*100:>4.1f}%)",
        )

    print("\n" + "=" * 80)
    print("INTENSITY RECOMMENDATIONS PER INTEGRATION TIME")
    print("=" * 80)
    print(f"\n{'Time(ms)':>10} {'LED A':>10} {'LED B':>10} {'LED C':>10} {'LED D':>10}")
    print("-" * 80)

    for time_ms in [20, 30, 40, 50, 60, 70, 80, 90, 100]:
        intensities = []
        for led_name in ["A", "B", "C", "D"]:
            slope_10ms = led_models[led_name][0][1]
            time_intensity_product = (target_counts * 10) / slope_10ms
            intensity = min(255, time_intensity_product / time_ms)
            intensities.append(intensity)

        print(
            f"{time_ms:>10} {intensities[0]:>10.1f} {intensities[1]:>10.1f} {intensities[2]:>10.1f} {intensities[3]:>10.1f}",
        )

    # =======================
    # CALCULATE GENERIC CORRECTION FACTORS
    # =======================
    print("\n" + "=" * 80)
    print("CALCULATING GENERIC CORRECTION FACTORS")
    print("=" * 80)

    # Group validation results by time and LED to calculate correction factors
    correction_factors = {}  # {time_ms: {led_name: correction_factor}}

    for v in validation_results:
        time_ms = v["time_ms"]
        led_name = v["led"]
        predicted_intensity = v["predicted_intensity"]
        error_pct = v["error_pct"]

        # Skip saturated measurements (error > 50%)
        if abs(error_pct) > 50:
            print(
                f"   ⚠ Skipping saturated: LED {led_name} @ {time_ms}ms (error {error_pct:.1f}%)",
            )
            continue

        # Calculate correction factor
        # If actual counts were higher than target (positive error), model underestimated intensity needed
        # Correction factor = 1.0 + (error% / 100)
        # Example: +5% error means we need 1.05x more intensity than predicted
        correction = 1.0 + (error_pct / 100.0)

        if time_ms not in correction_factors:
            correction_factors[time_ms] = {}

        correction_factors[time_ms][led_name] = correction

        status = "↑" if correction > 1.0 else "↓"
        print(
            f"   {status} LED {led_name} @ {time_ms}ms: correction factor = {correction:.4f} (error was {error_pct:+.1f}%)",
        )

    # Calculate per-time average correction (for LEDs without specific data)
    average_corrections = {}
    for time_ms, led_corrections in correction_factors.items():
        avg = sum(led_corrections.values()) / len(led_corrections)
        average_corrections[time_ms] = avg
        print(f"\n   Average correction @ {time_ms}ms: {avg:.4f}")

    # =======================
    # SAVE RESULTS
    # =======================
    print("\n" + "=" * 80)
    print("SAVING RESULTS")
    print("=" * 80)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = Path(__file__).parent / f"led_calibration_multistage_{timestamp}.json"

    # Format model data for JSON
    model_dict = {}
    for led_name, stages in led_models.items():
        model_dict[led_name] = [{"time_ms": t, "slope": s} for t, s in stages]

    output_data = {
        "timestamp": timestamp,
        "detector_wait_ms": DETECTOR_WAIT_MS,  # NEW: Document detector wait time used
        "saturation_threshold": 60000,  # NEW: Document saturation protection threshold
        "dark_counts_per_time": dark_counts_per_time,
        "led_models": model_dict,
        "correction_factors": correction_factors,  # NEW: Per-LED, per-time corrections
        "average_corrections": average_corrections,  # NEW: Fallback corrections per time
        "all_stage_results": all_results,
        "validation": validation_results,
        "validation_summary": {
            "average_error_pct": avg_error,
            "max_error_pct": max_error,
            "within_5pct": f"{within_5pct}/{total}",
            "within_10pct": f"{within_10pct}/{total}",
        },
        "usage_note": "Apply correction_factors when predicting LED intensity: predicted_intensity *= correction_factors[time_ms][led_name]",
    }

    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n✓ Results saved to: {output_file}")
    print("\n📋 Model includes:")
    print("   • Per-integration-time slopes for each LED")
    print("   • Correction factors to compensate for non-linearity")
    print("   • Average corrections as fallback for unmeasured times")
    print("\nCalibration complete!")

    # Cleanup
    controller.set_batch_intensities(a=0, b=0, c=0, d=0)
    time.sleep(0.3)
    controller.close()
    spectrometer.close()


if __name__ == "__main__":
    main()
