"""
SPR-Focused Calibration with S and P Polarization States
=========================================================

Measures LED calibration separately for S and P polarization states.
This captures the complete optical system including polarizer transmission.

Workflow:
1. Measure SPR-focused calibration at S-polarization (92 points)
2. Measure SPR-focused calibration at P-polarization (92 points)
3. Measure dark current (11 integration times)
4. Process and normalize the calibration matrix

Total: 195 measurements, ~10 minutes
"""

import sys
import json
import time
import numpy as np
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.hardware.device_interface import IController, ISpectrometer
from src.hardware.controller_adapter import wrap_existing_controller
from src.hardware.spectrometer_adapter import wrap_existing_spectrometer

def measure_spr_calibration_with_polarization():
    """Execute SPR-focused calibration for both S and P polarization"""

    # Load calibration plan
    plan_file = 'LED-Counts relationship/spr_calibration_plan.json'
    with open(plan_file, 'r') as f:
        plan = json.load(f)

    # Load device config to get servo positions
    config_file = 'src/config/devices/FLMT09116/device_config.json'
    with open(config_file, 'r') as f:
        device_config = json.load(f)

    servo_s_pos = device_config['hardware']['servo_s_position']
    servo_p_pos = device_config['hardware']['servo_p_position']

    # Initialize hardware
    print("="*80)
    print("SPR-FOCUSED LED CALIBRATION WITH POLARIZATION")
    print("="*80)
    print("\nMeasuring calibration at S and P polarization states")
    print("This captures the complete optical system for SPR measurements")
    print(f"\nServo positions from device config:")
    print(f"  S-polarization: {servo_s_pos}°")
    print(f"  P-polarization: {servo_p_pos}°\n")

    print("\nInitializing hardware...")

    # Import hardware classes
    from src.utils.controller import PicoP4SPR
    from src.utils.usb4000_wrapper import USB4000

    # Initialize controller
    controller_hw = PicoP4SPR()
    spec_hw = USB4000()

    # Wrap in interface
    controller = wrap_existing_controller(controller_hw)
    spectrometer = wrap_existing_spectrometer(spec_hw)

    if not controller.connect():
        print("ERROR: Could not connect to LED controller!")
        return

    if not spectrometer.connect():
        print("ERROR: Could not connect to spectrometer!")
        controller.disconnect()
        return

    print("✓ Connected to hardware")

    # Move servo to S-polarization position using V1.9 calibration method
    print(f"\nMoving servo to S-polarization position ({servo_s_pos}°)...")
    # Step 1: Set S position with sv command (format: sv###### where each ### is S and P position)
    cmd_s = f'sv{servo_s_pos:03d}{servo_s_pos:03d}\n'
    controller_hw._ser.write(cmd_s.encode())
    time.sleep(0.05)
    # Step 2: Move to S position with ss command
    controller_hw._ser.write(b'ss\n')
    time.sleep(3)  # Allow servo to settle and you should hear it move

    input("STEP 1: Verify polarizer is at S-POLARIZATION (you should have heard servo move), then press ENTER...")

    # Prepare results storage
    results_S = {
        'A': {'measurements': [], 'polarization': 'S'},
        'B': {'measurements': [], 'polarization': 'S'},
        'C': {'measurements': [], 'polarization': 'S'},
        'D': {'measurements': [], 'polarization': 'S'}
    }

    results_P = {
        'A': {'measurements': [], 'polarization': 'P'},
        'B': {'measurements': [], 'polarization': 'P'},
        'C': {'measurements': [], 'polarization': 'P'},
        'D': {'measurements': [], 'polarization': 'P'}
    }

    # LED channel mapping
    led_channels = {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd'}

    total_per_pol = sum(len(points) for points in plan.values())

    print(f"\nMeasurements per polarization state: {total_per_pol}")
    print(f"Total measurements (S + P): {total_per_pol * 2}")
    print(f"Estimated time: {total_per_pol * 2 * 3 / 60:.1f} minutes\n")

    # ========================================================================
    # PHASE 1: S-POLARIZATION CALIBRATION
    # ========================================================================

    print("="*80)
    print("PHASE 1: S-POLARIZATION CALIBRATION")
    print("="*80)
    print("Measuring SPR region (8k-22k counts) at S-polarization\n")

    measurement_count = 0

    for led_name in ['A', 'B', 'C', 'D']:
        channel = led_channels[led_name]
        led_plan = plan[led_name]

        print("="*80)
        print(f"LED {led_name} @ S-POL - {len(led_plan)} measurements")
        print("="*80)

        for i, point in enumerate(led_plan, 1):
            measurement_count += 1

            intensity = point['intensity']
            time_ms = point['time']
            target = point['target_counts']

            # Turn off all LEDs
            controller.turn_off_channels()
            time.sleep(0.05)

            # Enable target LED
            controller.turn_on_channel(channel)
            controller.set_intensity(channel, intensity)
            spectrometer.set_integration_time(time_ms)
            time.sleep(0.1)  # LED stabilization

            # Measure counts
            try:
                spectrum = spectrometer.read_spectrum()
                if spectrum is None or len(spectrum) == 0:
                    raise ValueError("No spectrum data")
                counts = float(np.max(spectrum))

                # Store measurement
                results_S[led_name]['measurements'].append({
                    'intensity': intensity,
                    'time': time_ms,
                    'counts': counts,
                    'target': target,
                    'polarization': 'S'
                })

                error_pct = ((counts - target) / target) * 100 if target > 0 else 0
                status = "✓" if abs(error_pct) < 30 else "⚠"

                print(f"{status} [{measurement_count:3d}/{total_per_pol}] "
                      f"I={intensity:3d}, T={time_ms:5.1f}ms → "
                      f"{counts:7.0f} counts (target: {target:,})")

            except Exception as e:
                print(f"✗ [{measurement_count:3d}/{total_per_pol}] "
                      f"FAILED - I={intensity}, T={time_ms}ms: {e}")
                continue

        # Turn off LED after each channel
        controller.turn_off_channels()
        print()

    # Save S-polarization results
    output_S = 'LED-Counts relationship/led_calibration_spr_S_polarization.json'
    with open(output_S, 'w') as f:
        json.dump(results_S, f, indent=2)

    print("\n" + "="*80)
    print("S-POLARIZATION CALIBRATION COMPLETE")
    print("="*80)
    print(f"Data saved to: {output_S}\n")

    # ========================================================================
    # PHASE 2: P-POLARIZATION CALIBRATION
    # ========================================================================

    # Move servo to P-polarization position using V1.9 calibration method
    print(f"\nMoving servo to P-polarization position ({servo_p_pos}°)...")
    # Step 1: Set P position with sv command (format: sv###### where each ### is S and P position)
    cmd_p = f'sv{servo_p_pos:03d}{servo_p_pos:03d}\n'
    controller_hw._ser.write(cmd_p.encode())
    time.sleep(0.05)
    # Step 2: Move to S position with ss command (yes, ss, because we set both S and P to P position)
    controller_hw._ser.write(b'ss\n')
    time.sleep(3)  # Allow servo to settle and you should hear it move

    input("STEP 2: Verify polarizer is at P-POLARIZATION (you should have heard servo move), then press ENTER...")

    print("\n" + "="*80)
    print("PHASE 2: P-POLARIZATION CALIBRATION")
    print("="*80)
    print("Measuring SPR region (8k-22k counts) at P-polarization\n")

    measurement_count = 0

    for led_name in ['A', 'B', 'C', 'D']:
        channel = led_channels[led_name]
        led_plan = plan[led_name]

        print("="*80)
        print(f"LED {led_name} @ P-POL - {len(led_plan)} measurements")
        print("="*80)

        for i, point in enumerate(led_plan, 1):
            measurement_count += 1

            intensity = point['intensity']
            time_ms = point['time']
            target = point['target_counts']

            # Turn off all LEDs
            controller.turn_off_channels()
            time.sleep(0.05)

            # Enable target LED
            controller.turn_on_channel(channel)
            controller.set_intensity(channel, intensity)
            spectrometer.set_integration_time(time_ms)
            time.sleep(0.1)  # LED stabilization

            # Measure counts
            try:
                spectrum = spectrometer.read_spectrum()
                if spectrum is None or len(spectrum) == 0:
                    raise ValueError("No spectrum data")
                counts = float(np.max(spectrum))

                # Store measurement
                results_P[led_name]['measurements'].append({
                    'intensity': intensity,
                    'time': time_ms,
                    'counts': counts,
                    'target': target,
                    'polarization': 'P'
                })

                error_pct = ((counts - target) / target) * 100 if target > 0 else 0
                status = "✓" if abs(error_pct) < 30 else "⚠"

                print(f"{status} [{measurement_count:3d}/{total_per_pol}] "
                      f"I={intensity:3d}, T={time_ms:5.1f}ms → "
                      f"{counts:7.0f} counts (target: {target:,})")

            except Exception as e:
                print(f"✗ [{measurement_count:3d}/{total_per_pol}] "
                      f"FAILED - I={intensity}, T={time_ms}ms: {e}")
                continue

        # Turn off LED after each channel
        controller.turn_off_channels()
        print()

    # Save P-polarization results
    output_P = 'LED-Counts relationship/led_calibration_spr_P_polarization.json'
    with open(output_P, 'w') as f:
        json.dump(results_P, f, indent=2)

    print("\n" + "="*80)
    print("P-POLARIZATION CALIBRATION COMPLETE")
    print("="*80)
    print(f"Data saved to: {output_P}\n")

    # ========================================================================
    # PHASE 3: DARK CURRENT MEASUREMENT
    # ========================================================================

    input("\nSTEP 3: Ready to measure DARK current (all LEDs OFF), press ENTER...")

    print("\n" + "="*80)
    print("PHASE 3: DARK CURRENT MEASUREMENT")
    print("="*80)
    print("Measuring detector dark current with all LEDs OFF\n")

    # Ensure ALL LEDs are OFF
    controller.turn_off_channels()

    time.sleep(0.5)  # Wait for LEDs to fully turn off

    # Integration times matching calibration
    integration_times = [5.0, 7.5, 10.0, 12.5, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0]

    print(f"{'#':<4} {'Time (ms)':<12} {'Dark Counts':<15} {'Counts/ms':<12}")
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

        print(f"{i:<4} {time_ms:<12.1f} {avg_counts:<15.1f} {counts_per_ms:<12.2f} "
              f"(+/- {std_counts:.1f})")

    # Linear fit to dark current
    times = [m['time'] for m in dark_measurements]
    counts = [m['dark_counts'] for m in dark_measurements]

    coeffs = np.polyfit(times, counts, 1)
    dark_rate = coeffs[0]
    offset = coeffs[1]

    print(f"\nDark current linear fit:")
    print(f"  Rate: {dark_rate:.2f} counts/ms")
    print(f"  Offset: {offset:.1f} counts")

    # Save dark measurements
    dark_output = {
        'measurements': dark_measurements,
        'linear_fit': {
            'slope': dark_rate,
            'offset': offset
        },
        'notes': 'Dark current measured with all LEDs OFF'
    }

    output_dark = 'LED-Counts relationship/dark_signal_calibration.json'
    with open(output_dark, 'w') as f:
        json.dump(dark_output, f, indent=2)

    print(f"\nDark signal data saved to: {output_dark}")

    # Disconnect hardware
    spectrometer.disconnect()

    # ========================================================================
    # SUMMARY
    # ========================================================================

    print("\n" + "="*80)
    print("CALIBRATION MEASUREMENT COMPLETE")
    print("="*80)

    # Cleanup
    controller.turn_off_channels()
    controller.disconnect()

    print("\nFILES CREATED:")
    print(f"  1. {output_S}")
    print(f"  2. {output_P}")
    print(f"  3. {output_dark}")

    # Summary statistics
    print("\n" + "="*80)
    print("MEASUREMENT SUMMARY")
    print("="*80)

    for led_name in ['A', 'B', 'C', 'D']:
        measurements_S = results_S[led_name]['measurements']
        measurements_P = results_P[led_name]['measurements']

        if measurements_S and measurements_P:
            counts_S = [m['counts'] for m in measurements_S]
            counts_P = [m['counts'] for m in measurements_P]

            print(f"\nLED {led_name}:")
            print(f"  S-pol measurements: {len(measurements_S)}")
            print(f"    Counts range: {min(counts_S):.0f} - {max(counts_S):.0f}")
            print(f"  P-pol measurements: {len(measurements_P)}")
            print(f"    Counts range: {min(counts_P):.0f} - {max(counts_P):.0f}")

            # Check if P shows SPR extinction (should be lower than S in SPR region)
            avg_S = np.mean(counts_S)
            avg_P = np.mean(counts_P)

            if avg_P < avg_S:
                extinction_pct = (avg_S - avg_P) / avg_S * 100
                print(f"  Average extinction (S vs P): {extinction_pct:.1f}%")
                if extinction_pct > 5:
                    print(f"    ⚠️  High extinction detected - may include SPR effects!")
                    print(f"        (Expected if measuring through sample)")
            else:
                print(f"  Note: P counts >= S counts (unexpected for SPR)")

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("""
1. Process and normalize the calibration matrix:
   - Subtract dark current from all measurements
   - Build 2D RBF models for S and P separately
   - Create unified calibration model

2. Run: python process_spr_calibration.py
   - Combines S, P, and dark data
   - Builds normalized calibration models
   - Validates accuracy in SPR region

3. Update LED2DCalibrationModel to use new polarization-aware model
""")

if __name__ == '__main__':
    measure_spr_calibration_with_polarization()
