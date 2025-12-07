"""
Simple Sensitivity Correction Experiment
=========================================

Test 1: Use the ACTUAL calibration data table
  - Find integration time at I=255 where counts ≈ 80% detector (52,428)
  - Use those exact times from the table

Test 2: Apply correction factors to LED intensities
  - Adjust LED intensity based on correction factors
  - Recalculate integration times to reach 80% CORRECTED counts
"""

import sys
import time
import json
import numpy as np
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt

# Add parent to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from src.hardware.device_interface import IController, ISpectrometer
from src.hardware.controller_adapter import wrap_existing_controller
from src.hardware.spectrometer_adapter import wrap_existing_spectrometer
from src.hardware.optimized_led_controller import create_optimized_controller

# SPR Servo positions
SERVO_S_POL = 156

def load_processed_calibration(detector_serial):
    """Load the processed calibration data table"""
    calib_file = f'LED-Counts relationship/led_calibration_spr_processed_{detector_serial}.json'

    try:
        with open(calib_file, 'r') as f:
            data = json.load(f)
        print(f"[OK] Loaded calibration data: {calib_file}")
        return data
    except FileNotFoundError:
        print(f"[ERROR] Calibration file not found: {calib_file}")
        return None

def find_time_at_i255_for_target(calib_data, led_letter, target_counts=52428):
    """
    Use RBF interpolation to find integration time at I=255 where counts = target
    """
    if 'S' not in calib_data or led_letter not in calib_data['S']:
        print(f"[ERROR] No S-pol data for LED_{led_letter}")
        return None

    from scipy.interpolate import RBFInterpolator

    measurements = calib_data['S'][led_letter]['measurements']

    # Build RBF model
    X = np.array([[m['intensity'], m['time']] for m in measurements])
    y = np.array([m['counts'] for m in measurements])

    model = RBFInterpolator(X, y, kernel='thin_plate_spline', smoothing=0.1, epsilon=1.0)

    # Binary search for time at I=255 that gives target_counts
    best_time = None
    best_error = float('inf')

    # Search from 5ms to 150ms
    for test_time in np.arange(5.0, 150.0, 0.5):
        predicted_counts = model([[255, test_time]])[0]
        error = abs(predicted_counts - target_counts)

        if error < best_error:
            best_error = error
            best_time = test_time

        # Stop if we found good match
        if error < 200:
            break

    if best_time is None:
        print(f"[ERROR] Could not find time for LED_{led_letter}")
        return None

    # Get final prediction
    final_counts = model([[255, best_time]])[0]

    return {
        'time_ms': best_time,
        'counts': final_counts,
        'intensity': 255
    }

def load_correction_factors(detector_serial):
    """Load sensitivity correction factors"""
    correction_file = f'LED-Counts relationship/sensitivity_correction_factors_{detector_serial}.json'

    try:
        with open(correction_file, 'r') as f:
            data = json.load(f)
        return data['correction_factors']
    except:
        print(f"[ERROR] Cannot load correction factors: {correction_file}")
        return None

def get_correction_factor(correction_factors, led_name, polarization, time_ms):
    """Interpolate correction factor"""
    if led_name not in correction_factors:
        return 1.0

    if polarization not in correction_factors[led_name]:
        return 1.0

    factors_data = correction_factors[led_name][polarization]['factors']

    times = [f['time_ms'] for f in factors_data]
    factors = [f['correction_factor'] for f in factors_data]

    return float(np.interp(time_ms, times, factors))

def test_1_no_correction(controller, spec_interface, opt_controller, calib_data,
                        detector_serial, duration_sec=60):
    """
    Test 1: Use exact times from calibration table at I=255 to reach 80%
    """
    print("\n" + "="*80)
    print("TEST 1: CALIBRATION TABLE VALUES (NO CORRECTION)")
    print("="*80)
    print(f"Duration: {duration_sec} seconds")
    print("Strategy: Use I=255, find time from table where counts ≈ 52,428 (80%)")
    print()

    target_counts = 52428
    detector_max = 65535

    led_mapping = {
        'LED_A': 'a',
        'LED_B': 'b',
        'LED_C': 'c',
        'LED_D': 'd'
    }

    # Find settings from calibration table
    test_settings = {}
    print("Settings from calibration table:")
    for led_name, channel in led_mapping.items():
        led_letter = led_name.split('_')[1]
        settings = find_time_at_i255_for_target(calib_data, led_letter, target_counts)

        if settings is None:
            return None, None, None

        test_settings[led_name] = settings
        pct = (settings['counts'] / detector_max * 100)
        print(f"  {led_name}: I=255, T={settings['time_ms']:.2f}ms → {settings['counts']:.0f} counts ({pct:.1f}%)")

    # Set servo to S-polarization
    from src.utils.controller import PicoP4SPR
    controller_hw = controller._controller
    cmd = f'sv{SERVO_S_POL:03d}{SERVO_S_POL:03d}\n'
    controller_hw._ser.write(cmd.encode())
    time.sleep(0.5)

    results = {led: [] for led in led_mapping.keys()}
    start_time = time.time()
    cycle_times = []

    print("\nAcquiring data...")
    while (time.time() - start_time) < duration_sec:
        cycle_start = time.time()

        for led_name, channel in led_mapping.items():
            settings = test_settings[led_name]

            # Set LED and integration time
            opt_controller.configure_led_atomic(channel, 255)
            spec_interface.set_integration_time(settings['time_ms'])
            time.sleep(0.05)

            # Acquire
            spectrum = spec_interface.read_spectrum()
            peak = float(np.max(spectrum))

            opt_controller.turn_off_all_leds()

            results[led_name].append({
                'timestamp': time.time() - start_time,
                'counts': peak,
                'integration_time': settings['time_ms']
            })

        cycle_times.append(time.time() - cycle_start)

    opt_controller.turn_off_all_leds()

    # Stats
    total_time = time.time() - start_time
    total_cycles = len(cycle_times)

    print(f"\n[Results - Test 1]")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Total cycles: {total_cycles}")
    print(f"  Avg cycle time: {np.mean(cycle_times)*1000:.1f}ms")
    print(f"  Per-LED measurements:")
    for led_name in led_mapping.keys():
        count = len(results[led_name])
        avg_counts = np.mean([m['counts'] for m in results[led_name]])
        std_counts = np.std([m['counts'] for m in results[led_name]])
        cv = (std_counts / avg_counts * 100) if avg_counts > 0 else 0
        pct = (avg_counts / detector_max * 100)
        print(f"    {led_name}: {count} measurements, avg={avg_counts:.0f} counts ({pct:.1f}%, CV={cv:.2f}%)")

    return results, cycle_times, total_time

def test_2_with_correction(controller, spec_interface, opt_controller, calib_data,
                          correction_factors, detector_serial, duration_sec=60):
    """
    Test 2: Apply correction to find times where corrected counts = target

    Strategy:
      - Target: 52,428 counts AFTER correction
      - Use RBF model to find time at I=255 where raw × correction = 52,428
    """
    print("\n" + "="*80)
    print("TEST 2: WITH SENSITIVITY CORRECTION")
    print("="*80)
    print(f"Duration: {duration_sec} seconds")
    print("Strategy: Find time where (raw counts × correction) = 52,428")
    print()

    from scipy.interpolate import RBFInterpolator

    target_corrected = 52428
    detector_max = 65535

    led_mapping = {
        'LED_A': 'a',
        'LED_B': 'b',
        'LED_C': 'c',
        'LED_D': 'd'
    }

    test_settings = {}
    print("Settings with correction factors:")

    for led_name, channel in led_mapping.items():
        led_letter = led_name.split('_')[1]

        if 'S' not in calib_data or led_letter not in calib_data['S']:
            return None, None, None

        measurements = calib_data['S'][led_letter]['measurements']

        # Build RBF model
        X = np.array([[m['intensity'], m['time']] for m in measurements])
        y = np.array([m['counts'] for m in measurements])
        model = RBFInterpolator(X, y, kernel='thin_plate_spline', smoothing=0.1, epsilon=1.0)

        # Search for time where raw × correction = target
        best_time = None
        best_error = float('inf')
        best_raw = None
        best_correction = None
        best_corrected = None

        for test_time in np.arange(5.0, 150.0, 0.5):
            # Predict raw counts
            raw_counts = model([[255, test_time]])[0]

            # Get correction factor at this time
            correction = get_correction_factor(correction_factors, led_name, 'S', test_time)

            # Calculate corrected counts
            corrected_counts = raw_counts * correction

            # Check error
            error = abs(corrected_counts - target_corrected)

            if error < best_error:
                best_error = error
                best_time = test_time
                best_raw = raw_counts
                best_correction = correction
                best_corrected = corrected_counts

            # Stop if good match
            if error < 200:
                break

        if best_time is None:
            print(f"[ERROR] No valid match for {led_name}")
            return None, None, None

        test_settings[led_name] = {
            'time_ms': best_time,
            'raw_counts': best_raw,
            'correction': best_correction,
            'corrected_counts': best_corrected,
            'intensity': 255
        }

        pct_raw = (best_raw / detector_max * 100)
        pct_corr = (best_corrected / detector_max * 100)
        print(f"  {led_name}: I=255, T={best_time:.2f}ms, corr={best_correction:.3f}")
        print(f"           Raw={best_raw:.0f} ({pct_raw:.1f}%) → "
              f"Corrected={best_corrected:.0f} ({pct_corr:.1f}%)")

    # Set servo
    from src.utils.controller import PicoP4SPR
    controller_hw = controller._controller
    cmd = f'sv{SERVO_S_POL:03d}{SERVO_S_POL:03d}\n'
    controller_hw._ser.write(cmd.encode())
    time.sleep(0.5)

    results = {led: [] for led in led_mapping.keys()}
    start_time = time.time()
    cycle_times = []

    print("\nAcquiring data...")
    while (time.time() - start_time) < duration_sec:
        cycle_start = time.time()

        for led_name, channel in led_mapping.items():
            settings = test_settings[led_name]

            # Set LED and integration time
            opt_controller.configure_led_atomic(channel, 255)
            spec_interface.set_integration_time(settings['time_ms'])
            time.sleep(0.05)

            # Acquire
            spectrum = spec_interface.read_spectrum()
            peak = float(np.max(spectrum))

            # Apply correction
            corrected_peak = peak * settings['correction']

            opt_controller.turn_off_all_leds()

            results[led_name].append({
                'timestamp': time.time() - start_time,
                'raw_counts': peak,
                'corrected_counts': corrected_peak,
                'integration_time': settings['time_ms'],
                'correction': settings['correction']
            })

        cycle_times.append(time.time() - cycle_start)

    opt_controller.turn_off_all_leds()

    # Stats
    total_time = time.time() - start_time
    total_cycles = len(cycle_times)

    print(f"\n[Results - Test 2]")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Total cycles: {total_cycles}")
    print(f"  Avg cycle time: {np.mean(cycle_times)*1000:.1f}ms")
    print(f"  Per-LED measurements:")
    for led_name in led_mapping.keys():
        count = len(results[led_name])
        avg_raw = np.mean([m['raw_counts'] for m in results[led_name]])
        avg_corr = np.mean([m['corrected_counts'] for m in results[led_name]])
        std_corr = np.std([m['corrected_counts'] for m in results[led_name]])
        cv = (std_corr / avg_corr * 100) if avg_corr > 0 else 0
        pct_corr = (avg_corr / detector_max * 100)
        print(f"    {led_name}: {count} measurements")
        print(f"            Raw={avg_raw:.0f} → Corrected={avg_corr:.0f} ({pct_corr:.1f}%, CV={cv:.2f}%)")

    return results, cycle_times, total_time

def run_experiment():
    """Run the experiment"""
    print("="*80)
    print("SENSITIVITY CORRECTION EXPERIMENT - SIMPLE VERSION")
    print("="*80)
    print("\nInitializing hardware...")

    from src.utils.controller import PicoP4SPR
    from src.utils.usb4000_wrapper import USB4000

    controller_hw = PicoP4SPR()
    spec_hw = USB4000()

    controller = wrap_existing_controller(controller_hw)
    spectrometer = wrap_existing_spectrometer(spec_hw)

    if not controller.connect():
        print("[ERROR] Could not connect to LED controller!")
        return

    if not spectrometer.connect():
        print("[ERROR] Could not connect to spectrometer!")
        controller.disconnect()
        return

    print("[OK] Hardware connected")

    opt_controller = create_optimized_controller(controller_hw)
    opt_controller.enter_calibration_mode()

    detector_serial = spec_hw.serial_number if hasattr(spec_hw, 'serial_number') else "FLMT09116"

    # Load calibration data
    calib_data = load_processed_calibration(detector_serial)
    if calib_data is None:
        opt_controller.turn_off_all_leds()
        controller.disconnect()
        spectrometer.disconnect()
        return

    # Load correction factors
    correction_factors = load_correction_factors(detector_serial)
    if correction_factors is None:
        opt_controller.turn_off_all_leds()
        controller.disconnect()
        spectrometer.disconnect()
        return

    try:
        # Test 1
        results1, cycle_times1, time1 = test_1_no_correction(
            controller, spectrometer, opt_controller, calib_data, detector_serial, duration_sec=60
        )

        print("\nWaiting 5 seconds...")
        time.sleep(5)

        # Test 2
        results2, cycle_times2, time2 = test_2_with_correction(
            controller, spectrometer, opt_controller, calib_data,
            correction_factors, detector_serial, duration_sec=60
        )

        # Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"\nTest 1: Avg cycle={np.mean(cycle_times1)*1000:.1f}ms")
        print(f"Test 2: Avg cycle={np.mean(cycle_times2)*1000:.1f}ms")
        print(f"Speedup: {np.mean(cycle_times1)/np.mean(cycle_times2):.2f}x")

    finally:
        print("\nShutting down...")
        opt_controller.exit_calibration_mode()
        opt_controller.turn_off_all_leds()
        controller.disconnect()
        spectrometer.disconnect()
        print("[OK] Complete")

if __name__ == '__main__':
    run_experiment()
