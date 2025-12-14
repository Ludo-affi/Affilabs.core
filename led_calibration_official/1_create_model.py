"""
3-Stage LED Calibration: Progressive Model Refinement
Stage 1: 10ms - Initial model per LED
Stage 2: 20ms - Measure all at once, refine model per LED
Stage 3: 30ms - Measure all at once, refine model per LED
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime

parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from affilabs.utils.controller import PicoP4SPR
from affilabs.utils.usb4000_wrapper import USB4000

def measure_led_response(controller, spectrometer, led_char, intensity, integration_time_ms, dark_counts):
    """Measure single LED at given intensity and integration time."""
    # Set integration time first
    spectrometer.set_integration(integration_time_ms)
    time.sleep(0.05)

    # Turn off all LEDs
    controller.set_batch_intensities(a=0, b=0, c=0, d=0)
    time.sleep(0.2)

    # Enable all channels first, then set intensities
    controller._ser.write(b"lm:A,B,C,D\n")
    time.sleep(0.1)

    # Turn on this LED
    intensities = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
    intensities[led_char] = intensity
    controller.set_batch_intensities(**intensities)
    time.sleep(0.5)

    # Measure (average of 3 scans, then average top 10 pixels)
    spectrum = spectrometer.intensities(num_scans=3)
    import numpy as np
    top_10_indices = np.argpartition(spectrum, -10)[-10:]
    top_10_avg = float(spectrum[top_10_indices].mean())
    corrected = top_10_avg - dark_counts

    return {
        'raw_counts': top_10_avg,
        'corrected_counts': corrected,
        'saturated_wavelengths': int((spectrum >= 65535).sum())
    }

def measure_all_leds_together(controller, spectrometer, intensity, integration_time_ms, dark_counts):
    """Measure all 4 LEDs together at given intensity and integration time."""
    # Set integration time first
    spectrometer.set_integration(integration_time_ms)
    time.sleep(0.05)

    # Turn off all LEDs
    controller.set_batch_intensities(a=0, b=0, c=0, d=0)
    time.sleep(0.2)

    # Turn on all LEDs using lm command + batch
    controller._ser.write(b"lm:A,B,C,D\n")
    time.sleep(0.1)
    controller.set_batch_intensities(a=intensity, b=intensity, c=intensity, d=intensity)
    time.sleep(0.5)

    # Measure (average of 3 scans, then average top 10 pixels)
    spectrum = spectrometer.intensities(num_scans=3)
    import numpy as np
    top_10_indices = np.argpartition(spectrum, -10)[-10:]
    top_10_avg = float(spectrum[top_10_indices].mean())
    corrected = top_10_avg - dark_counts

    return {
        'raw_counts': top_10_avg,
        'corrected_counts': corrected,
        'saturated_wavelengths': int((spectrum >= 65535).sum())
    }

def fit_linear_model(data_points):
    """Fit linear model: counts = slope * intensity
    Returns slope (counts per intensity unit)"""
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
    print("3-STAGE LED CALIBRATION: PROGRESSIVE MODEL REFINEMENT")
    print("=" * 80)
    print("\nStrategy:")
    print("  Stage 1 (10ms): Measure each LED individually, build initial model")
    print("  Stage 2 (20ms): Measure all at once, then refine individual models")
    print("  Stage 3 (30ms): Measure all at once, then refine individual models")
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

    # Measure dark current at each integration time
    print("Measuring dark current at each integration time...")
    controller.set_batch_intensities(a=0, b=0, c=0, d=0)

    dark_counts_per_time = {}
    for time_ms in [10, 20, 30]:
        spectrometer.set_integration(float(time_ms))
        time.sleep(0.5)
        spectrum = spectrometer.intensities(num_scans=3)
        dark = float(spectrum.max())
        dark_counts_per_time[time_ms] = dark
        print(f"  {time_ms}ms: {dark:.0f} counts")
    print()

    # Storage for model data
    led_models = {'A': [], 'B': [], 'C': [], 'D': []}  # List of (time_ms, slope) tuples
    all_results = []

    # Test intensities - using recommended values from calculations
    intensities_per_stage = {
        10: [50, 100, 150, 200, 255],  # At 10ms, all can go high
        20: [50, 100, 150, 200, 255],  # At 20ms, still safe
        30: [50, 100, 150, 200, 255]   # At 30ms, need to check saturation
    }

    # Stage-specific intensities based on LED brightness
    led_max_intensity = {
        10: {'A': 255, 'B': 255, 'C': 255, 'D': 255},
        20: {'A': 255, 'B': 255, 'C': 255, 'D': 255},
        30: {'A': 255, 'B': 206, 'C': 181, 'D': 255}  # Based on calculations
    }

    # =======================
    # STAGE 1: 10ms Individual LEDs
    # =======================
    print("=" * 80)
    print("STAGE 1: 10ms - Initial Model (Individual LEDs)")
    print("=" * 80)

    integration_time = 10.0
    dark_counts = dark_counts_per_time[10]
    stage_results = {'integration_time': integration_time, 'dark_counts': dark_counts, 'measurements': {}}

    for led_name, led_char in [('A', 'a'), ('B', 'b'), ('C', 'c'), ('D', 'd')]:
        print(f"\n{led_name}:")
        led_data = []
        max_i = led_max_intensity[10][led_name]
        test_intensities = [i for i in intensities_per_stage[10] if i <= max_i]

        for intensity in test_intensities:
            result = measure_led_response(controller, spectrometer, led_char, intensity, integration_time, dark_counts)
            led_data.append((intensity, result['corrected_counts']))

            sat_warning = f" ⚠ {result['saturated_wavelengths']} saturated!" if result['saturated_wavelengths'] > 0 else ""
            print(f"  I={intensity:>3}: {result['corrected_counts']:>8.0f} counts{sat_warning}")

        # Fit model
        slope = fit_linear_model(led_data)
        if slope:
            led_models[led_name].append((integration_time, slope))
            print(f"  Model: {slope:.2f} counts/intensity")
            stage_results['measurements'][led_name] = {'data': led_data, 'slope': slope}

    all_results.append(stage_results)

    # =======================
    # STAGE 2: 20ms - All Together + Refine
    # =======================
    print("\n" + "=" * 80)
    print("STAGE 2: 20ms - Measure All Together + Refine Individual Models")
    print("=" * 80)

    integration_time = 20.0
    dark_counts = dark_counts_per_time[20]
    stage_results = {'integration_time': integration_time, 'dark_counts': dark_counts, 'measurements': {}}

    # First, measure all LEDs together
    print("\nAll 4 LEDs together:")
    all_together_data = []
    for intensity in intensities_per_stage[20]:
        result = measure_all_leds_together(controller, spectrometer, intensity, integration_time, dark_counts)
        all_together_data.append((intensity, result['corrected_counts']))

        sat_warning = f" ⚠ {result['saturated_wavelengths']} saturated!" if result['saturated_wavelengths'] > 0 else ""
        print(f"  I={intensity:>3}: {result['corrected_counts']:>8.0f} counts{sat_warning}")

    stage_results['all_together'] = {'data': all_together_data}

    # Now refine individual models
    print("\nRefining individual LED models:")
    for led_name, led_char in [('A', 'a'), ('B', 'b'), ('C', 'c'), ('D', 'd')]:
        print(f"\n{led_name}:")
        led_data = []
        max_i = led_max_intensity[20][led_name]
        test_intensities = [i for i in intensities_per_stage[20] if i <= max_i]

        for intensity in test_intensities:
            result = measure_led_response(controller, spectrometer, led_char, intensity, integration_time, dark_counts)
            led_data.append((intensity, result['corrected_counts']))

            sat_warning = f" ⚠ {result['saturated_wavelengths']} saturated!" if result['saturated_wavelengths'] > 0 else ""
            print(f"  I={intensity:>3}: {result['corrected_counts']:>8.0f} counts{sat_warning}")

        # Fit model
        slope = fit_linear_model(led_data)
        if slope:
            led_models[led_name].append((integration_time, slope))

            # Compare to previous stage
            prev_slope = led_models[led_name][0][1] if len(led_models[led_name]) > 1 else None
            if prev_slope:
                ratio = slope / (prev_slope * 2.0)  # Should be ~1.0 if perfectly linear
                print(f"  Model: {slope:.2f} counts/intensity (ratio to 10ms*2: {ratio:.3f})")
            else:
                print(f"  Model: {slope:.2f} counts/intensity")

            stage_results['measurements'][led_name] = {'data': led_data, 'slope': slope}

    all_results.append(stage_results)

    # =======================
    # STAGE 3: 30ms - All Together + Refine
    # =======================
    print("\n" + "=" * 80)
    print("STAGE 3: 30ms - Measure All Together + Refine Individual Models")
    print("=" * 80)

    integration_time = 30.0
    dark_counts = dark_counts_per_time[30]
    stage_results = {'integration_time': integration_time, 'dark_counts': dark_counts, 'measurements': {}}

    # First, measure all LEDs together (use reduced intensities to avoid saturation)
    print("\nAll 4 LEDs together:")
    all_together_data = []
    # Reduce max intensity for brightest LEDs at 30ms
    safe_intensities = [50, 100, 150, 181]  # 181 is safe for LED C at 30ms
    for intensity in safe_intensities:
        result = measure_all_leds_together(controller, spectrometer, intensity, integration_time, dark_counts)
        all_together_data.append((intensity, result['corrected_counts']))

        sat_warning = f" ⚠ {result['saturated_wavelengths']} saturated!" if result['saturated_wavelengths'] > 0 else ""
        print(f"  I={intensity:>3}: {result['corrected_counts']:>8.0f} counts{sat_warning}")

    stage_results['all_together'] = {'data': all_together_data}

    # Now refine individual models
    print("\nRefining individual LED models:")
    for led_name, led_char in [('A', 'a'), ('B', 'b'), ('C', 'c'), ('D', 'd')]:
        print(f"\n{led_name}:")
        led_data = []
        max_i = led_max_intensity[30][led_name]
        test_intensities = [i for i in [50, 100, 150, 200, 255] if i <= max_i]

        for intensity in test_intensities:
            result = measure_led_response(controller, spectrometer, led_char, intensity, integration_time, dark_counts)
            led_data.append((intensity, result['corrected_counts']))

            sat_warning = f" ⚠ {result['saturated_wavelengths']} saturated!" if result['saturated_wavelengths'] > 0 else ""
            print(f"  I={intensity:>3}: {result['corrected_counts']:>8.0f} counts{sat_warning}")

        # Fit model
        slope = fit_linear_model(led_data)
        if slope:
            led_models[led_name].append((integration_time, slope))

            # Compare to previous stages
            prev_10ms = led_models[led_name][0][1] if len(led_models[led_name]) >= 1 else None
            prev_20ms = led_models[led_name][1][1] if len(led_models[led_name]) >= 2 else None

            if prev_10ms:
                ratio_10 = slope / (prev_10ms * 3.0)  # Should be ~1.0 if perfectly linear
                print(f"  Model: {slope:.2f} counts/intensity (ratio to 10ms*3: {ratio_10:.3f})")
            else:
                print(f"  Model: {slope:.2f} counts/intensity")

            stage_results['measurements'][led_name] = {'data': led_data, 'slope': slope}

    all_results.append(stage_results)

    # =======================
    # FINAL SUMMARY
    # =======================
    print("\n" + "=" * 80)
    print("FINAL MODEL SUMMARY")
    print("=" * 80)

    print(f"\n{'LED':>5} {'Time(ms)':>10} {'Slope':>15} {'Expected Ratio':>15} {'Actual Ratio':>15}")
    print("-" * 80)

    for led_name in ['A', 'B', 'C', 'D']:
        model_data = led_models[led_name]
        base_slope = model_data[0][1]  # 10ms slope

        for i, (time_ms, slope) in enumerate(model_data):
            expected_ratio = time_ms / 10.0
            actual_ratio = slope / base_slope

            print(f"{led_name:>5} {time_ms:>10.0f} {slope:>15.2f} {expected_ratio:>15.1f}x {actual_ratio:>15.3f}x")

    # Check linearity
    print("\n" + "=" * 80)
    print("LINEARITY CHECK")
    print("=" * 80)
    print("\nIf ratio ≈ 1.0, LED response is perfectly linear with integration time")
    print(f"\n{'LED':>5} {'10→20ms':>12} {'10→30ms':>12} {'20→30ms':>12}")
    print("-" * 80)

    for led_name in ['A', 'B', 'C', 'D']:
        model_data = led_models[led_name]

        if len(model_data) >= 3:
            slope_10 = model_data[0][1]
            slope_20 = model_data[1][1]
            slope_30 = model_data[2][1]

            ratio_10_20 = slope_20 / (slope_10 * 2.0)
            ratio_10_30 = slope_30 / (slope_10 * 3.0)
            ratio_20_30 = slope_30 / (slope_20 * 1.5)

            print(f"{led_name:>5} {ratio_10_20:>12.3f} {ratio_10_30:>12.3f} {ratio_20_30:>12.3f}")

    # =======================
    # BOUNDARY CONDITIONS FOR 60,000 COUNTS
    # =======================
    print("\n" + "=" * 80)
    print("BOUNDARY CONDITIONS TO REACH 60,000 COUNTS")
    print("=" * 80)
    print("\nUsing linear model: counts = slope * intensity * (time_ms / 10)")
    print("Target: 60,000 counts (≈91.5% detector fill)")
    print("\nPer LED, what (time_ms × intensity) product gives 60,000 counts:")
    print(f"\n{'LED':>5} {'Slope@10ms':>12} {'Time×Intensity':>16} {'Example: 50ms':>20} {'Example: 100ms':>20}")
    print("-" * 80)

    target_counts = 60000
    for led_name in ['A', 'B', 'C', 'D']:
        model_data = led_models[led_name]
        slope_10ms = model_data[0][1]  # counts per intensity at 10ms

        # counts = slope_10ms * intensity * (time_ms / 10)
        # 60000 = slope_10ms * intensity * (time_ms / 10)
        # intensity * time_ms = 60000 * 10 / slope_10ms
        time_intensity_product = (target_counts * 10) / slope_10ms

        # Examples at different integration times
        intensity_at_50ms = min(255, time_intensity_product / 50)
        intensity_at_100ms = min(255, time_intensity_product / 100)

        print(f"{led_name:>5} {slope_10ms:>12.2f} {time_intensity_product:>16.0f} "
              f"I={intensity_at_50ms:>6.1f} ({intensity_at_50ms/255*100:>4.1f}%) "
              f"I={intensity_at_100ms:>6.1f} ({intensity_at_100ms/255*100:>4.1f}%)")

    print("\n" + "=" * 80)
    print("INTENSITY RECOMMENDATIONS PER INTEGRATION TIME")
    print("=" * 80)
    print(f"\n{'Time(ms)':>10} {'LED A':>10} {'LED B':>10} {'LED C':>10} {'LED D':>10}")
    print("-" * 80)

    for time_ms in [20, 30, 40, 50, 60, 70, 80, 90, 100]:
        intensities = []
        for led_name in ['A', 'B', 'C', 'D']:
            slope_10ms = led_models[led_name][0][1]
            time_intensity_product = (target_counts * 10) / slope_10ms
            intensity = min(255, time_intensity_product / time_ms)
            intensities.append(intensity)

        print(f"{time_ms:>10} {intensities[0]:>10.1f} {intensities[1]:>10.1f} {intensities[2]:>10.1f} {intensities[3]:>10.1f}")

    # Save results
    output_file = f"led_calibration_3stage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path = Path(__file__).parent / "spr_calibration" / "data" / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump({
            'dark_counts_per_time': dark_counts_per_time,
            'led_models': {led: [(t, s) for t, s in data] for led, data in led_models.items()},
            'stage_results': all_results,
            'timestamp': datetime.now().isoformat()
        }, f, indent=2)

    print(f"\n✓ Results saved to: {output_path}")

    # =======================
    # ADDITIONAL DARK MEASUREMENTS (for model validation)
    # =======================
    print("\n" + "=" * 80)
    print("ADDITIONAL DARK MEASUREMENTS")
    print("=" * 80)
    print("\nMeasuring dark spectrum at additional integration times for model validation...")

    # Turn off all LEDs
    controller.set_batch_intensities(a=0, b=0, c=0, d=0)
    time.sleep(0.5)

    # Measure dark at more integration times (10-100ms in 10ms increments)
    additional_dark_times = [40, 50, 60, 70, 80, 90, 100]

    for time_ms in additional_dark_times:
        spectrometer.set_integration(float(time_ms))
        time.sleep(0.2)
        spectrum = spectrometer.intensities(num_scans=3)
        dark_max = float(spectrum.max())
        dark_mean = float(spectrum.mean())
        dark_counts_per_time[time_ms] = dark_max
        print(f"  {time_ms}ms: {dark_max:.0f} counts (max), {dark_mean:.0f} counts (mean)")

    print(f"\n✓ Total dark measurements: {len(dark_counts_per_time)} integration times")

    # Update saved JSON with additional dark measurements
    output_data = {
        'dark_counts_per_time': dark_counts_per_time,
        'led_models': {led: [(t, s) for t, s in data] for led, data in led_models.items()},
        'stage_results': all_results,
        'timestamp': datetime.now().isoformat()
    }

    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"✓ Updated results with dark measurements saved to: {output_path}")

    # Turn off all LEDs
    controller.set_batch_intensities(a=0, b=0, c=0, d=0)
    controller.close()
    spectrometer.close()
    print("\n✓ Hardware closed")

if __name__ == "__main__":
    main()
