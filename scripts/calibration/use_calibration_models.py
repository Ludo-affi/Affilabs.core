"""Use Calibration Models for Prediction
======================================

Demonstrates how to use the trained RBF calibration models to:
1. Predict counts for any (intensity, time) combination
2. Find optimal settings to achieve target count range
3. Validate measurement parameters before acquisition
4. Calculate expected SNR and signal quality

The models interpolate smoothly between calibration points and can
extrapolate slightly beyond the measured range (with caution).
"""

import json

import numpy as np
from scipy.interpolate import RBFInterpolator
from scipy.optimize import minimize


def get_detector_serial():
    """Get detector serial from device config"""
    try:
        config_file = "src/config/devices/FLMT09116/device_config.json"
        with open(config_file) as f:
            device_config = json.load(f)
        return device_config["hardware"]["spectrometer_serial"]
    except (FileNotFoundError, KeyError):
        return "FLMT09116"  # Default fallback


def load_calibration_models_ML(detector_serial=None):
    """Load the trained RBF models from processed calibration data

    Args:
        detector_serial: Detector serial number. If None, loads from device config.

    Returns:
        models_S: Dict of S-polarization RBF models
        models_P: Dict of P-polarization RBF models
        dark_params: Tuple of (dark_rate, dark_offset)
        detector_serial: Detector serial number

    """
    if detector_serial is None:
        detector_serial = get_detector_serial()

    print("=" * 80)
    print("LOADING CALIBRATION MODELS")
    print("=" * 80)

    # Try to load detector-specific file first, fall back to generic
    calibration_file = (
        f"LED-Counts relationship/led_calibration_spr_processed_{detector_serial}.json"
    )
    fallback_file = "LED-Counts relationship/led_calibration_spr_processed.json"

    try:
        with open(calibration_file) as f:
            data = json.load(f)
        print("✓ Loaded detector-specific calibration")
        print(f"  File: {calibration_file}")
    except FileNotFoundError:
        try:
            with open(fallback_file) as f:
                data = json.load(f)
            print("⚠️  Using generic calibration (detector-specific not found)")
            print(f"  File: {fallback_file}")
        except FileNotFoundError:
            raise FileNotFoundError(
                "Calibration not found. Run: python process_spr_calibration.py",
            )

    # Verify detector match
    if "detector_serial" in data:
        if data["detector_serial"] != detector_serial:
            print(
                f"⚠️  WARNING: Calibration is for {data['detector_serial']}, current detector is {detector_serial}",
            )
        else:
            print(f"  Detector: {data['detector_serial']} ✓")

    if "processed_date" in data:
        print(f"  Calibrated: {data['processed_date']}")

    dark_rate = data["dark"]["rate"]
    dark_offset = data["dark"]["offset"]

    print("✓ Loaded calibration data")
    print(f"  Dark rate: {dark_rate:.2f} counts/ms")
    print(f"  Dark offset: {dark_offset:.1f} counts")

    # Rebuild RBF models
    models_S = {}
    models_P = {}

    for led_name in ["A", "B", "C", "D"]:
        # S-polarization model
        measurements_S = data["S"][led_name]["measurements"]
        points_S = np.array([(m["intensity"], m["time"]) for m in measurements_S])
        values_S = np.array([m["counts"] for m in measurements_S])

        models_S[led_name] = RBFInterpolator(
            points_S,
            values_S,
            kernel="thin_plate_spline",
            smoothing=0.1,
            epsilon=1.0,
        )

        # P-polarization model
        measurements_P = data["P"][led_name]["measurements"]
        points_P = np.array([(m["intensity"], m["time"]) for m in measurements_P])
        values_P = np.array([m["counts"] for m in measurements_P])

        models_P[led_name] = RBFInterpolator(
            points_P,
            values_P,
            kernel="thin_plate_spline",
            smoothing=0.1,
            epsilon=1.0,
        )

        print(
            f"  ✓ LED {led_name}: S-pol ({len(measurements_S)} points), P-pol ({len(measurements_P)} points)",
        )

    return models_S, models_P, (dark_rate, dark_offset), detector_serial


def predict_counts_ML(models, led_name, intensity, time_ms, polarization="S"):
    """Predict counts for given measurement parameters

    Args:
        models: Dictionary of RBF models (models_S or models_P)
        led_name: 'A', 'B', 'C', or 'D'
        intensity: LED intensity (0-255)
        time_ms: Integration time in milliseconds
        polarization: 'S' or 'P'

    Returns:
        Predicted dark-corrected counts

    """
    model = models[led_name]
    predicted = float(model(np.array([[intensity, time_ms]]))[0])
    return predicted


def find_optimal_settings_ML(
    models,
    led_name,
    target_counts,
    polarization="S",
    intensity_range=(40, 255),
    time_range=(5.0, 25.0),
):
    """Find optimal (intensity, time) to achieve target counts

    Args:
        models: Dictionary of RBF models
        led_name: 'A', 'B', 'C', or 'D'
        target_counts: Desired count level
        polarization: 'S' or 'P'
        intensity_range: (min, max) LED intensity
        time_range: (min, max) integration time in ms

    Returns:
        dict with optimal intensity, time, predicted counts, and error

    """
    model = models[led_name]

    # Objective: minimize squared error from target
    def objective(params):
        intensity, time_ms = params
        predicted = float(model(np.array([[intensity, time_ms]]))[0])
        return (predicted - target_counts) ** 2

    # Initial guess: middle of ranges
    x0 = [
        (intensity_range[0] + intensity_range[1]) / 2,
        (time_range[0] + time_range[1]) / 2,
    ]

    # Bounds
    bounds = [intensity_range, time_range]

    # Optimize
    result = minimize(objective, x0, method="L-BFGS-B", bounds=bounds)

    optimal_intensity = int(round(result.x[0]))
    optimal_time = round(result.x[1], 1)
    predicted = predict_counts_ML(
        {led_name: model},
        led_name,
        optimal_intensity,
        optimal_time,
    )
    error_pct = (
        ((predicted - target_counts) / target_counts * 100) if target_counts > 0 else 0
    )

    return {
        "intensity": optimal_intensity,
        "time": optimal_time,
        "predicted_counts": predicted,
        "target_counts": target_counts,
        "error_pct": error_pct,
        "achieved": abs(error_pct) < 10,  # Within 10% of target
    }


def validate_measurement_quality(counts, time_ms):
    """Assess measurement quality based on counts and SNR

    Args:
        counts: Predicted or measured counts
        time_ms: Integration time

    Returns:
        dict with quality metrics

    """
    # Estimate SNR (photon shot noise limited)
    snr = counts / np.sqrt(max(counts, 1)) if counts > 0 else 0

    # Quality thresholds
    if counts > 10000:
        quality = "Excellent"
        trackable = True
    elif counts > 5000:
        quality = "Good"
        trackable = True
    elif counts > 1000:
        quality = "Fair"
        trackable = False
    else:
        quality = "Poor"
        trackable = False

    return {
        "counts": counts,
        "snr": snr,
        "quality": quality,
        "trackable": trackable,
        "recommendation": "Suitable for SPR" if trackable else "Increase signal level",
    }


def demonstrate_usage():
    """Demonstrate how to use the calibration models"""
    # Load models
    models_S, models_P, dark_params, detector_serial = load_calibration_models_ML()

    print("\n" + "=" * 80)
    print("EXAMPLE 1: PREDICT COUNTS FOR SPECIFIC SETTINGS")
    print("=" * 80)

    # Example: Predict counts for LED B, S-pol, I=100, T=15ms
    led = "B"
    intensity = 100
    time_ms = 15.0

    predicted_S = predict_counts_ML(models_S, led, intensity, time_ms, "S")
    predicted_P = predict_counts_ML(models_P, led, intensity, time_ms, "P")

    print(f"\nLED {led} @ I={intensity}, T={time_ms}ms:")
    print(f"  S-pol predicted: {predicted_S:.0f} counts")
    print(f"  P-pol predicted: {predicted_P:.0f} counts")
    print(f"  P/S ratio: {predicted_P/predicted_S:.3f}")

    quality_S = validate_measurement_quality(predicted_S, time_ms)
    quality_P = validate_measurement_quality(predicted_P, time_ms)

    print(f"\n  S-pol quality: {quality_S['quality']} (SNR={quality_S['snr']:.1f})")
    print(f"  P-pol quality: {quality_P['quality']} (SNR={quality_P['snr']:.1f})")
    print(f"  Recommendation: {quality_P['recommendation']}")

    print("\n" + "=" * 80)
    print("EXAMPLE 2: FIND OPTIMAL SETTINGS FOR TARGET COUNTS")
    print("=" * 80)

    # Goal: Achieve 15,000 counts for best SPR measurements
    target = 15000

    print(f"\nTarget: {target:,} counts")
    print("\nOptimal settings for each LED (P-polarization):")
    print(
        f"{'LED':<6} {'Intensity':<12} {'Time (ms)':<12} {'Predicted':<12} {'Error%':<10} {'Status':<10}",
    )
    print("-" * 80)

    for led_name in ["A", "B", "C", "D"]:
        result = find_optimal_settings_ML(models_P, led_name, target, "P")

        status = "✓ Good" if result["achieved"] else "⚠ Off"
        print(
            f"{led_name:<6} {result['intensity']:<12} {result['time']:<12.1f} "
            f"{result['predicted_counts']:<12.0f} {result['error_pct']:<10.1f} {status:<10}",
        )

    print("\n" + "=" * 80)
    print("EXAMPLE 3: SCAN PARAMETER SPACE")
    print("=" * 80)

    # Scan intensity and time to find all valid combinations for target range
    led = "A"
    target_min = 10000
    target_max = 20000

    print(
        f"\nLED {led} - Finding settings for {target_min:,}-{target_max:,} counts (P-pol):",
    )
    print(f"{'Intensity':<12} {'Time (ms)':<12} {'Predicted':<12} {'Quality':<12}")
    print("-" * 60)

    valid_combos = []

    for intensity in range(50, 200, 30):
        for time_ms in [10.0, 15.0, 20.0, 25.0]:
            predicted = predict_counts_ML(models_P, led, intensity, time_ms, "P")

            if target_min <= predicted <= target_max:
                quality = validate_measurement_quality(predicted, time_ms)
                valid_combos.append((intensity, time_ms, predicted, quality["quality"]))
                print(
                    f"{intensity:<12} {time_ms:<12.1f} {predicted:<12.0f} {quality['quality']:<12}",
                )

    if valid_combos:
        print(f"\n✓ Found {len(valid_combos)} valid parameter combinations")
    else:
        print("\n⚠ No combinations found in target range - adjust constraints")

    print("\n" + "=" * 80)
    print("EXAMPLE 4: PREDICT FOR CURRENT POLARIZATION STATE")
    print("=" * 80)

    # In production, polarizer is fixed at one position (typically P for SPR)
    # The calibration measured BOTH orientations to characterize the optical system
    # Use the model that matches your current hardware polarization setting

    current_polarization = "P"  # Your actual polarizer position
    current_models = models_P if current_polarization == "P" else models_S

    intensity = 120
    time_ms = 20.0

    print(f"\nCurrent polarizer: {current_polarization}-polarization")
    print(f"Predictions at I={intensity}, T={time_ms}ms:")
    print(f"{'LED':<6} {'Predicted Counts':<18} {'SNR':<10} {'Quality':<12}")
    print("-" * 60)

    for led_name in ["A", "B", "C", "D"]:
        counts = predict_counts_ML(
            current_models,
            led_name,
            intensity,
            time_ms,
            current_polarization,
        )
        quality = validate_measurement_quality(counts, time_ms)

        print(
            f"{led_name:<6} {counts:<18.0f} {quality['snr']:<10.1f} {quality['quality']:<12}",
        )

    print("\n" + "=" * 80)
    print("USAGE SUMMARY")
    print("=" * 80)
    print("""
The calibration models can be used to:

1. **Predict Performance**: Given (intensity, time), predict counts and quality
   → Use before measurements to validate settings will work

2. **Optimize Settings**: Given target counts, find best (intensity, time)
   → Use to plan experiments requiring specific signal levels

3. **Explore Parameter Space**: Scan ranges to find all valid combinations
   → Use to understand measurement constraints

4. **Validate Before Acquisition**: Check if settings will give trackable signal
   → Prevent wasted measurements with poor SNR

IMPORTANT - POLARIZATION:
- Polarizer is FIXED at one position during SPR measurements (hardware servo setting)
- Calibration measured BOTH S and P to characterize the complete optical system
- Use models_P for P-polarization or models_S for S-polarization
- Match the model to your ACTUAL hardware polarizer position
- You cannot "switch" polarization - it's set by physical servo rotation

INTEGRATION INTO WORKFLOW:
- Load models once at startup
- Determine which polarization your hardware is set to (S or P)
- Use the corresponding model (models_S or models_P)
- Call predict_counts_ML() before each measurement
- Use find_optimal_settings_ML() for experiment planning
- Validate quality with validate_measurement_quality()
""")


if __name__ == "__main__":
    demonstrate_usage()
