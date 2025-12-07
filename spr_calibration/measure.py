"""
SPR EOM Calibration with Matched S/P Measurements
==================================================

Measures LED calibration for both S and P polarization states with strict
matching of intensity and integration time pairs. This ensures proper 2D RBF
model construction with identical sampling points for both polarizations.

Key Features:
- Validates intensity/time matching between S and P measurements
- Builds verification checks before processing
- Measures dark current for correction
- Ensures data quality for SPR 2D RBF model

Workflow:
1. Load calibration plan
2. Measure S-polarization (92 measurements per LED)
3. Measure P-polarization (92 measurements per LED, matched)
4. Measure dark current (11 integration times)
5. Validate matching and save results

Total: 195 measurements, ~10-12 minutes
"""

import sys
import json
import time
import numpy as np
import os
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.hardware.device_interface import IController, ISpectrometer
from src.hardware.controller_adapter import wrap_existing_controller
from src.hardware.spectrometer_adapter import wrap_existing_spectrometer
from src.hardware.optimized_led_controller import create_optimized_controller


def validate_calibration_plan(plan):
    """
    Validate that calibration plan has consistent structure for all LEDs

    Returns: (is_valid, message, summary)
    """
    print("\n" + "="*80)
    print("VALIDATING CALIBRATION PLAN")
    print("="*80)

    led_names = ['A', 'B', 'C', 'D']

    # Check all LEDs present
    if not all(led in plan for led in led_names):
        return False, "Missing LED entries in plan", {}

    # Extract unique (intensity, time) pairs for each LED
    led_pairs = {}
    for led_name in led_names:
        pairs = [(p['intensity'], p['time']) for p in plan[led_name]]
        led_pairs[led_name] = pairs
        print(f"\nLED {led_name}: {len(pairs)} measurement points")

        # Check for duplicates
        if len(pairs) != len(set(pairs)):
            duplicates = [p for p in pairs if pairs.count(p) > 1]
            return False, f"LED {led_name} has duplicate (intensity, time) pairs: {set(duplicates)}", {}

    # Summary statistics
    summary = {}
    for led_name in led_names:
        pairs = led_pairs[led_name]
        intensities = [p[0] for p in pairs]
        times = [p[1] for p in pairs]

        summary[led_name] = {
            'num_points': len(pairs),
            'intensity_range': (min(intensities), max(intensities)),
            'time_range': (min(times), max(times)),
            'unique_intensities': len(set(intensities)),
            'unique_times': len(set(times))
        }

        print(f"  Intensity range: {min(intensities)} - {max(intensities)}")
        print(f"  Time range: {min(times)} - {max(times)} ms")
        print(f"  Unique intensities: {len(set(intensities))}")
        print(f"  Unique times: {len(set(times))}")

    print("\n✓ Calibration plan validated successfully")
    return True, "Plan validated", summary


def measure_polarization_state(controller, spectrometer, plan, polarization,
                               servo_position, controller_hw, opt_controller):
    """
    Measure all LEDs at a specific polarization state

    Args:
        controller: Wrapped controller interface
        spectrometer: Wrapped spectrometer interface
        plan: Calibration plan dict
        polarization: 'S' or 'P'
        servo_position: Servo angle for this polarization
        controller_hw: Raw controller hardware object for servo control
        opt_controller: Optimized LED controller for fast measurements

    Returns:
        results: Dict with measurements for each LED
    """
    # Move servo to position using V1.9 method
    print(f"\nMoving servo to {polarization}-polarization position ({servo_position}°)...")
    cmd = f'sv{servo_position:03d}{servo_position:03d}\n'
    controller_hw._ser.write(cmd.encode())
    time.sleep(0.05)
    controller_hw._ser.write(b'ss\n')
    time.sleep(3)  # Allow servo to settle

    input(f"✓ Verify polarizer is at {polarization}-POLARIZATION, then press ENTER...")

    # Initialize results storage
    results = {
        'A': {'measurements': [], 'polarization': polarization},
        'B': {'measurements': [], 'polarization': polarization},
        'C': {'measurements': [], 'polarization': polarization},
        'D': {'measurements': [], 'polarization': polarization}
    }

    led_channels = {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd'}
    total_measurements = sum(len(plan[led]) for led in ['A', 'B', 'C', 'D'])

    print("\n" + "="*80)
    print(f"{polarization}-POLARIZATION MEASUREMENT")
    print("="*80)
    print(f"Total measurements: {total_measurements}")
    print(f"Target range: 8k-22k counts\n")

    measurement_count = 0

    for led_name in ['A', 'B', 'C', 'D']:
        channel = led_channels[led_name]
        led_plan = plan[led_name]

        print("="*80)
        print(f"LED {led_name} @ {polarization}-POL - {len(led_plan)} measurements")
        print("="*80)

        for i, point in enumerate(led_plan, 1):
            measurement_count += 1

            intensity = point['intensity']
            time_ms = point['time']
            target = point['target_counts']

            # Configure LED atomically (optimized for speed)
            opt_controller.configure_led_atomic(channel, intensity)
            spectrometer.set_integration_time(time_ms)
            # Note: LED stabilization handled by opt_controller

            # Measure counts
            try:
                spectrum = spectrometer.read_spectrum()
                if spectrum is None or len(spectrum) == 0:
                    raise ValueError("No spectrum data")
                counts = float(np.max(spectrum))

                # Store measurement
                results[led_name]['measurements'].append({
                    'intensity': intensity,
                    'time': time_ms,
                    'counts': counts,
                    'target': target,
                    'polarization': polarization,
                    'timestamp': datetime.now().isoformat()
                })

                error_pct = ((counts - target) / target) * 100 if target > 0 else 0
                status = "✓" if abs(error_pct) < 30 else "⚠"

                print(f"{status} [{measurement_count:3d}/{total_measurements}] "
                      f"I={intensity:3d}, T={time_ms:5.1f}ms → "
                      f"{counts:7.0f} counts (target: {target:,}, error: {error_pct:+.1f}%)")

            except Exception as e:
                print(f"✗ [{measurement_count:3d}/{total_measurements}] "
                      f"FAILED - I={intensity}, T={time_ms}ms: {e}")
                # Store failed measurement with None counts
                results[led_name]['measurements'].append({
                    'intensity': intensity,
                    'time': time_ms,
                    'counts': None,
                    'target': target,
                    'polarization': polarization,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
                continue

        # Turn off LED after each channel
        controller.turn_off_channels()
        print()

    return results


def validate_s_p_matching(results_S, results_P):
    """
    Validate that S and P measurements have matching (intensity, time) pairs

    Returns: (is_valid, report_dict)
    """
    print("\n" + "="*80)
    print("VALIDATING S/P MEASUREMENT MATCHING")
    print("="*80)

    report = {
        'overall_valid': True,
        'leds': {}
    }

    for led_name in ['A', 'B', 'C', 'D']:
        measurements_S = results_S[led_name]['measurements']
        measurements_P = results_P[led_name]['measurements']

        # Extract (intensity, time) pairs
        pairs_S = [(m['intensity'], m['time']) for m in measurements_S if m['counts'] is not None]
        pairs_P = [(m['intensity'], m['time']) for m in measurements_P if m['counts'] is not None]

        # Convert to sets for comparison
        set_S = set(pairs_S)
        set_P = set(pairs_P)

        # Check matching
        missing_in_P = set_S - set_P
        missing_in_S = set_P - set_S
        common = set_S & set_P

        led_valid = len(missing_in_P) == 0 and len(missing_in_S) == 0

        report['leds'][led_name] = {
            'valid': led_valid,
            'num_S': len(pairs_S),
            'num_P': len(pairs_P),
            'num_common': len(common),
            'missing_in_P': list(missing_in_P),
            'missing_in_S': list(missing_in_S)
        }

        print(f"\nLED {led_name}:")
        print(f"  S measurements: {len(pairs_S)}")
        print(f"  P measurements: {len(pairs_P)}")
        print(f"  Common pairs: {len(common)}")

        if missing_in_P:
            print(f"  ⚠️  Missing in P: {len(missing_in_P)} pairs")
            report['overall_valid'] = False

        if missing_in_S:
            print(f"  ⚠️  Missing in S: {len(missing_in_S)} pairs")
            report['overall_valid'] = False

        if led_valid:
            print(f"  ✓ Perfect S/P matching")

    if report['overall_valid']:
        print("\n✓ All S/P measurements perfectly matched")
    else:
        print("\n⚠️  WARNING: S/P measurements not perfectly matched")
        print("    This may cause issues in 2D RBF model construction")

    return report['overall_valid'], report


def measure_dark_current(spectrometer):
    """
    Measure detector dark current across integration times

    Returns: dark_data dict
    """
    print("\n" + "="*80)
    print("DARK CURRENT MEASUREMENT")
    print("="*80)
    print("Measuring detector dark current with all LEDs OFF\n")

    # Integration times matching calibration
    integration_times = [5.0, 7.5, 10.0, 12.5, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0]

    print(f"{'#':<4} {'Time (ms)':<12} {'Dark Counts':<15} {'Counts/ms':<12} {'Std Dev':<10}")
    print("-"*80)

    dark_measurements = []

    for i, time_ms in enumerate(integration_times, 1):
        # Set integration time
        spectrometer.set_integration_time(time_ms)
        time.sleep(0.1)

        # Take multiple measurements and average
        measurements = []
        for rep in range(5):  # 5 repetitions for statistics
            spectrum = spectrometer.read_spectrum()
            if spectrum is None or len(spectrum) == 0:
                continue
            counts = float(np.max(spectrum))
            measurements.append(counts)
            time.sleep(0.05)

        if len(measurements) == 0:
            print(f"✗ {i:<4} {time_ms:<12.1f} FAILED")
            continue

        avg_counts = sum(measurements) / len(measurements)
        std_counts = np.std(measurements)
        counts_per_ms = avg_counts / time_ms

        dark_measurements.append({
            'time': time_ms,
            'dark_counts': avg_counts,
            'std_counts': std_counts,
            'counts_per_ms': counts_per_ms,
            'repetitions': measurements
        })

        print(f"{i:<4} {time_ms:<12.1f} {avg_counts:<15.1f} {counts_per_ms:<12.2f} {std_counts:<10.1f}")

    # Linear fit to dark current
    times = [m['time'] for m in dark_measurements]
    counts = [m['dark_counts'] for m in dark_measurements]

    coeffs = np.polyfit(times, counts, 1)
    dark_rate = coeffs[0]
    offset = coeffs[1]

    print(f"\nDark current linear fit:")
    print(f"  Rate: {dark_rate:.2f} counts/ms")
    print(f"  Offset: {offset:.1f} counts")

    dark_data = {
        'measurements': dark_measurements,
        'linear_fit': {
            'slope': dark_rate,
            'offset': offset
        },
        'measurement_date': datetime.now().isoformat(),
        'notes': 'Dark current measured with all LEDs OFF'
    }

    return dark_data


def main():
    """Main calibration workflow with validation"""

    print("="*80)
    print("SPR EOM CALIBRATION - MATCHED S/P MEASUREMENTS")
    print("="*80)
    print("""
This script measures LED calibration for both S and P polarization states
with strict validation of matching intensity/time pairs for proper 2D RBF
model construction.
    """)

    # Load calibration plan
    plan_file = 'LED-Counts relationship/spr_calibration_plan.json'

    try:
        with open(plan_file, 'r') as f:
            plan = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Calibration plan not found: {plan_file}")
        print("Run calibration plan generator first")
        return

    # Validate plan structure
    is_valid, message, summary = validate_calibration_plan(plan)
    if not is_valid:
        print(f"\nERROR: {message}")
        return

    # Load device config
    config_file = 'src/config/devices/FLMT09116/device_config.json'
    with open(config_file, 'r') as f:
        device_config = json.load(f)

    servo_s_pos = device_config['hardware']['servo_s_position']
    servo_p_pos = device_config['hardware']['servo_p_position']
    detector_serial = device_config['hardware']['spectrometer_serial']

    print(f"\nDevice Configuration:")
    print(f"  Detector: {detector_serial}")
    print(f"  S-polarization servo: {servo_s_pos}°")
    print(f"  P-polarization servo: {servo_p_pos}°")

    # Initialize hardware
    print("\n" + "="*80)
    print("INITIALIZING HARDWARE")
    print("="*80)

    from src.utils.controller import PicoP4SPR
    from src.utils.usb4000_wrapper import USB4000

    controller_hw = PicoP4SPR()
    spec_hw = USB4000()

    controller = wrap_existing_controller(controller_hw)
    spectrometer = wrap_existing_spectrometer(spec_hw)

    if not controller.connect():
        print("ERROR: Could not connect to LED controller!")
        return

    if not spectrometer.connect():
        print("ERROR: Could not connect to spectrometer!")
        controller.disconnect()
        return

    print("✓ Connected to hardware\n")
    
    # Create optimized LED controller
    print("="*80)
    print("OPTIMIZING LED CONTROLLER")
    print("="*80)
    opt_controller = create_optimized_controller(controller_hw)
    info = opt_controller.get_info()
    print(f"Firmware: {info['firmware_version']}")
    print(f"V1.10 Support: {'Yes' if info['supports_v110'] else 'No (V1.9 mode)'}")
    print(f"LED Stabilization: {info['led_stabilization_ms']}ms")
    
    # Enter calibration mode for optimized measurements
    if opt_controller.enter_calibration_mode():
        print("✓ Calibration mode enabled - ready for fast measurements\n")
    else:
        print("⚠ Calibration mode not available - using standard mode\n")

    try:
        # ====================================================================
        # PHASE 1: S-POLARIZATION MEASUREMENT
        # ====================================================================

        print("\n" + "="*80)
        print("PHASE 1: S-POLARIZATION CALIBRATION")
        print("="*80)

        results_S = measure_polarization_state(
            controller, spectrometer, plan, 'S', servo_s_pos, controller_hw, opt_controller
        )

        # Save S-polarization results
        output_S = 'LED-Counts relationship/led_calibration_spr_S_polarization.json'
        results_S['detector_serial'] = detector_serial
        results_S['measurement_date'] = datetime.now().isoformat()
        results_S['servo_position'] = servo_s_pos

        with open(output_S, 'w') as f:
            json.dump(results_S, f, indent=2)

        print("\n✓ S-polarization data saved to:", output_S)

        # ====================================================================
        # PHASE 2: P-POLARIZATION MEASUREMENT
        # ====================================================================

        print("\n" + "="*80)
        print("PHASE 2: P-POLARIZATION CALIBRATION")
        print("="*80)

        results_P = measure_polarization_state(
            controller, spectrometer, plan, 'P', servo_p_pos, controller_hw, opt_controller
        )

        # Save P-polarization results
        output_P = 'LED-Counts relationship/led_calibration_spr_P_polarization.json'
        results_P['detector_serial'] = detector_serial
        results_P['measurement_date'] = datetime.now().isoformat()
        results_P['servo_position'] = servo_p_pos

        with open(output_P, 'w') as f:
            json.dump(results_P, f, indent=2)

        print("\n✓ P-polarization data saved to:", output_P)

        # ====================================================================
        # VALIDATE S/P MATCHING
        # ====================================================================

        is_matched, match_report = validate_s_p_matching(results_S, results_P)

        # Save validation report
        validation_file = 'LED-Counts relationship/spr_calibration_validation.json'
        with open(validation_file, 'w') as f:
            json.dump(match_report, f, indent=2)

        print(f"\n✓ Validation report saved to: {validation_file}")

        if not is_matched:
            print("\n⚠️  WARNING: S/P measurements are not perfectly matched!")
            print("    Review validation report before building 2D RBF models")

        # ====================================================================
        # PHASE 3: DARK CURRENT MEASUREMENT
        # ====================================================================

        input("\nReady to measure DARK current (all LEDs OFF), press ENTER...")

        # Ensure all LEDs are off
        controller.turn_off_channels()
        time.sleep(0.5)

        dark_data = measure_dark_current(spectrometer)

        # Save dark measurements
        output_dark = 'LED-Counts relationship/dark_signal_calibration.json'
        with open(output_dark, 'w') as f:
            json.dump(dark_data, f, indent=2)

        print(f"\n✓ Dark signal data saved to: {output_dark}")

    finally:
        # Exit calibration mode
        opt_controller.exit_calibration_mode()
        
        # Cleanup
        opt_controller.turn_off_all_leds()
        controller.disconnect()
        spectrometer.disconnect()

    # ========================================================================
    # SUMMARY
    # ========================================================================

    print("\n" + "="*80)
    print("CALIBRATION MEASUREMENT COMPLETE")
    print("="*80)

    print("\nFILES CREATED:")
    print(f"  1. {output_S}")
    print(f"  2. {output_P}")
    print(f"  3. {output_dark}")
    print(f"  4. {validation_file}")

    # Display summary statistics
    print("\n" + "="*80)
    print("MEASUREMENT SUMMARY")
    print("="*80)

    print(f"\n{'LED':<6} {'S Measurements':<18} {'P Measurements':<18} {'S/P Ratio':<12} {'Matched':<10}")
    print("-"*80)

    for led_name in ['A', 'B', 'C', 'D']:
        measurements_S = [m for m in results_S[led_name]['measurements'] if m['counts'] is not None]
        measurements_P = [m for m in results_P[led_name]['measurements'] if m['counts'] is not None]

        if measurements_S and measurements_P:
            counts_S = [m['counts'] for m in measurements_S]
            counts_P = [m['counts'] for m in measurements_P]

            avg_S = np.mean(counts_S)
            avg_P = np.mean(counts_P)
            ratio = avg_S / avg_P if avg_P > 0 else 0.0

            matched = "✓" if match_report['leds'][led_name]['valid'] else "✗"

            print(f"{led_name:<6} {len(measurements_S):<18} {len(measurements_P):<18} {ratio:<12.3f} {matched:<10}")

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)

    if is_matched:
        print("""
✓ S/P measurements are perfectly matched - ready for processing

1. Run: python process_spr_calibration.py
   - Applies dark correction
   - Builds 2D RBF models for S and P
   - Validates model accuracy
   - Creates unified calibration matrix

2. Test SPR measurements with new calibration
3. Update LED2DCalibrationModel if needed
""")
    else:
        print("""
⚠️  S/P MEASUREMENTS NOT PERFECTLY MATCHED

1. Review validation report: spr_calibration_validation.json
2. Identify missing measurements
3. Consider re-running specific measurements
4. OR proceed with caution - models may have reduced accuracy

After addressing issues:
- Run: python process_spr_calibration.py
""")


if __name__ == '__main__':
    main()
