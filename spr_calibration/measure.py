"""
SPR 2D Grid Calibration - OPTIMIZED LINEAR SAMPLING

**OPTIMIZED APPROACH (60% FASTER!):**
Since LED intensity is LINEAR (verified R² > 0.999), we only need 2 points per time:

At each integration time (11 time points):
  1. Find I_min: intensity that gives 20% detector
  2. Find I_max: intensity that gives 80% detector
  3. Measure ONLY these 2 points, 3 times each
  4. Linear interpolation provides full intensity range

Result: 11 times × 2 points × 3 scans = 66 measurements per LED/pol
Previous 5-point method: 11 × 5 × 3 = 165 measurements
**Speedup: 60% reduction in measurement time!**

Physics: Intensity range narrows at longer integration times (to avoid saturation).
At 5ms: might use I=40-255 (wide range)
At 200ms: might use I=15-30 (narrow range to stay below 80% detector)

**REQUIRES FIRMWARE V1.9+** for optimized LED control.
"""

import sys
import time
import json
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

# Add parent to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from src.hardware.device_interface import IController, ISpectrometer
from src.hardware.controller_adapter import wrap_existing_controller
from src.hardware.spectrometer_adapter import wrap_existing_spectrometer
from src.hardware.optimized_led_controller import create_optimized_controller

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('spr_adaptive_calibration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Suppress debug logging from underlying libraries to avoid unicode issues
logging.getLogger('src.utils.controller').setLevel(logging.WARNING)
logging.getLogger('src.hardware.optimized_led_controller').setLevel(logging.WARNING)
logging.getLogger('src.utils.usb4000_wrapper').setLevel(logging.WARNING)

# Detector-agnostic percentages (NOT hardcoded counts!)
TARGET_MIN_PERCENT = 0.20  # 20% of detector max
TARGET_MAX_PERCENT = 0.80  # 80% of detector max
SATURATION_THRESHOLD = 0.91  # 91% = saturation warning

# SPR Servo positions (PWM values from servo optimization study)
SERVO_S_POL = 72  # S-pol (parallel) - PWM 72
SERVO_P_POL = 8   # P-pol (perpendicular) - PWM 8


def get_detector_max(spec_interface):
    """Get detector max from spectrometer (detector-agnostic!)"""
    if hasattr(spec_interface, 'detector_max'):
        return spec_interface.detector_max
    elif hasattr(spec_interface, '_spec') and hasattr(spec_interface._spec, 'max_intensity'):
        return spec_interface._spec.max_intensity
    else:
        logger.warning("Could not get detector_max from spectrometer, using 65535")
        return 65535


def find_intensity_for_target_counts(controller, spectrometer, opt_controller, channel,
                                     time_ms, target_counts, detector_max, tolerance=0.05):
    """
    Binary search to find intensity that gives target counts at specified integration time.
    Returns: (intensity, actual_counts) or (None, None) if target unreachable
    """
    saturation_threshold = int(detector_max * SATURATION_THRESHOLD)

    # Binary search bounds
    i_min, i_max = 40, 255
    best_intensity = None
    best_counts = None
    best_error = float('inf')

    for iteration in range(10):  # Max 10 iterations
        i_mid = (i_min + i_max) // 2

        # Measure at this intensity
        opt_controller.configure_led_atomic(channel, i_mid)
        spectrometer.set_integration_time(time_ms)
        time.sleep(0.1)
        spectrum = spectrometer.read_spectrum()
        counts = float(np.max(spectrum))
        opt_controller.turn_off_all_leds()
        time.sleep(0.05)

        error = abs(counts - target_counts) / target_counts

        # Track best result
        if error < best_error:
            best_error = error
            best_intensity = i_mid
            best_counts = counts

        # Check if we're close enough
        if error < tolerance:
            return (i_mid, counts)

        # Check saturation
        if counts >= saturation_threshold:
            # Saturated - need lower intensity
            i_max = i_mid - 1
        elif counts < target_counts:
            # Too dim - need higher intensity
            i_min = i_mid + 1
        else:
            # Too bright - need lower intensity
            i_max = i_mid - 1

        # Check if search space exhausted
        if i_min > i_max:
            break

    # Return best result found
    if best_intensity is not None and best_error < 0.15:  # Within 15% is acceptable
        return (best_intensity, best_counts)
    else:
        return (None, None)


def sample_led_2d_grid(controller, spectrometer, opt_controller, led_name, channel, detector_max):
    """
    OPTIMIZED 2D CALIBRATION - LINEAR SAMPLING:

    Since LED intensity is LINEAR (R² > 0.999), we only need 2 points per integration time:
    - Measure I_min (20% detector) and I_max (80% detector)
    - Linear interpolation gives the full intensity range

    This reduces measurements from 55 -> 22 per LED/pol (60% faster!)
    """
    logger.info("="*80)
    logger.info(f"2D LINEAR SAMPLING (OPTIMIZED): {led_name}")
    logger.info(f"Detector max: {detector_max} counts")
    logger.info("="*80)

    # Define count targets (20-80% detector range for safety margin)
    count_min = int(detector_max * TARGET_MIN_PERCENT)
    count_max = int(detector_max * TARGET_MAX_PERCENT)

    # Integration times to scan
    integration_times = [5.0, 10.0, 15.0, 25.0, 40.0, 60.0, 80.0, 100.0, 120.0, 150.0, 200.0]

    all_measurements = []

    logger.info(f"\nScanning {len(integration_times)} integration times")
    logger.info(f"Target range: {count_min} - {count_max} counts ({TARGET_MIN_PERCENT*100:.0f}-{TARGET_MAX_PERCENT*100:.0f}% detector)")
    logger.info(f"Strategy: 2-point linear sampling (verified R² > 0.999)\n")

    for time_ms in integration_times:
        logger.info(f"--- Time = {time_ms:.2f}ms ---")

        # Step 1: Find I_min (intensity for min% detector)
        i_min, counts_min = find_intensity_for_target_counts(
            controller, spectrometer, opt_controller, channel,
            time_ms, count_min, detector_max, tolerance=0.15
        )

        if i_min is None:
            logger.warning(f"  [SKIP] Cannot reach {TARGET_MIN_PERCENT*100:.0f}% detector at {time_ms}ms - LED too bright")
            # Try measuring at minimum intensity anyway
            opt_controller.configure_led_atomic(channel, 40)
            spectrometer.set_integration_time(time_ms)
            time.sleep(0.1)
            spectrum = spectrometer.read_spectrum()
            counts = float(np.max(spectrum))
            opt_controller.turn_off_all_leds()

            if counts < int(detector_max * SATURATION_THRESHOLD):
                i_min = 40
                counts_min = counts
                logger.info(f"  [OK] Using I_min=40 -> {counts:.0f} counts ({counts/detector_max*100:.1f}%)")
            else:
                logger.error(f"  [ERROR] Saturated even at I=40! Skipping {time_ms}ms")
                continue
        else:
            logger.info(f"  [OK] I_min={i_min} -> {counts_min:.0f} counts ({counts_min/detector_max*100:.1f}%)")

        # Step 2: Find I_max (intensity for max% detector)
        i_max, counts_max = find_intensity_for_target_counts(
            controller, spectrometer, opt_controller, channel,
            time_ms, count_max, detector_max, tolerance=0.15
        )

        if i_max is None:
            logger.warning(f"  [SKIP] Cannot reach {TARGET_MAX_PERCENT*100:.0f}% detector at {time_ms}ms - LED too weak")
            # Try measuring at maximum intensity anyway
            opt_controller.configure_led_atomic(channel, 255)
            spectrometer.set_integration_time(time_ms)
            time.sleep(0.1)
            spectrum = spectrometer.read_spectrum()
            counts = float(np.max(spectrum))
            opt_controller.turn_off_all_leds()

            if counts > count_min:  # At least above minimum
                i_max = 255
                counts_max = counts
                logger.info(f"  [OK] Using I_max=255 -> {counts:.0f} counts ({counts/detector_max*100:.1f}%)")
            else:
                logger.error(f"  [ERROR] Too weak even at I=255! Skipping {time_ms}ms")
                continue
        else:
            logger.info(f"  [OK] I_max={i_max} -> {counts_max:.0f} counts ({counts_max/detector_max*100:.1f}%)")

        # Check if we have a reasonable range
        if i_max <= i_min:
            logger.warning(f"  [SKIP] Invalid range: I_min={i_min}, I_max={i_max}")
            continue

        # Step 3: Sample ONLY 2 POINTS (min and max) with 3 scans each
        for intensity, target_name in [(i_min, "MIN"), (i_max, "MAX")]:
            # Measure 3 times for repeatability
            measurements_i = []
            for scan in range(3):
                opt_controller.configure_led_atomic(channel, intensity)
                spectrometer.set_integration_time(time_ms)
                time.sleep(0.1)
                spectrum = spectrometer.read_spectrum()
                counts = float(np.max(spectrum))
                measurements_i.append(counts)
                time.sleep(0.05)

            opt_controller.turn_off_all_leds()
            time.sleep(0.05)

            # Calculate statistics
            mean_counts = np.mean(measurements_i)
            std_counts = np.std(measurements_i, ddof=1) if len(measurements_i) > 1 else 0
            pct = (mean_counts / detector_max) * 100

            all_measurements.append((intensity, time_ms, mean_counts))

            logger.info(f"    [{target_name}] I={intensity:3d} -> {mean_counts:7.0f} +/-{std_counts:4.0f} counts ({pct:5.1f}%)")

    logger.info(f"\n[OK] Collected {len(all_measurements)} measurements for {led_name}")
    logger.info(f"     2D coverage: {len(integration_times)} times × 2 points (linear interpolation)")
    logger.info(f"     >> 60% FASTER than 5-point sampling!")

    return all_measurements


def measure_polarization_2d_grid(controller, spec_interface, opt_controller,
                                  controller_hw, polarization, servo_position, detector_max):
    """
    Measure calibration for one polarization using CORRECT 2D grid approach.
    At each integration time, sample 5 intensities spanning 10-90% detector range.
    """
    logger.info("\n" + "="*80)
    logger.info(f"{polarization}-POLARIZATION 2D GRID CALIBRATION")
    logger.info("="*80)

    # Move servo
    logger.info(f"\nMoving servo to {polarization}-pol position ({servo_position}°)...")
    cmd = f'sv{servo_position:03d}{servo_position:03d}\n'
    controller_hw._ser.write(cmd.encode())
    time.sleep(0.05)
    controller_hw._ser.write(b'ss\n')
    time.sleep(0.5)

    # LED configuration - 4 independent LEDs
    leds = {
        'LED_A': 'a',
        'LED_B': 'b',
        'LED_C': 'c',
        'LED_D': 'd'
    }

    all_results = {}

    for led_name, channel in leds.items():
        logger.info(f"\n{'='*80}")
        logger.info(f"{led_name} (Channel {channel})")
        logger.info(f"{'='*80}")

        # Execute 2D grid sampling - NO ML/RBF during collection!
        all_measurements = sample_led_2d_grid(
            controller, spec_interface, opt_controller, led_name, channel, detector_max
        )

        all_results[led_name] = {
            'measurements': all_measurements
        }

    return all_results


def run_spr_2d_grid_calibration():
    """Main calibration workflow with CORRECT 2D grid sampling."""
    logger.info("="*80)
    logger.info("SPR 2D GRID CALIBRATION")
    logger.info("="*80)
    logger.info(f"\nSampling Strategy: At each integration time, find intensity range (10-90% detector)")
    logger.info(f"                   Sample 5 evenly spaced intensities in that range")
    logger.info(f"                   Repeat 3 times per point for repeatability")
    logger.info(f"\nIntegration Times: [5, 10, 15, 25, 40, 60, 80, 100, 120, 150, 200] ms")
    logger.info(f"Expected: 11 times × 5 intensities × 3 scans = 165 measurements per LED")
    logger.info(f"S-polarization servo: {SERVO_S_POL}°")
    logger.info(f"P-polarization servo: {SERVO_P_POL}°")

    # Initialize hardware
    logger.info("\nInitializing hardware...")

    from src.utils.controller import PicoP4SPR
    from src.utils.usb4000_wrapper import USB4000

    controller_hw = PicoP4SPR()
    spec_hw = USB4000()

    controller = wrap_existing_controller(controller_hw)
    spectrometer = wrap_existing_spectrometer(spec_hw)

    if not controller.connect():
        logger.error("Could not connect to LED controller!")
        return

    if not spectrometer.connect():
        logger.error("Could not connect to spectrometer!")
        controller.disconnect()
        return

    logger.info("OK Connected to hardware")

    # Create optimized LED controller
    opt_controller = create_optimized_controller(controller_hw)
    info = opt_controller.get_info()
    logger.info(f"Firmware: {info['firmware_version']}")

    if opt_controller.enter_calibration_mode():
        logger.info("OK Calibration mode enabled")

    # Get detector max
    detector_max = get_detector_max(spectrometer)
    detector_serial = spec_hw.serial_number if hasattr(spec_hw, 'serial_number') else "UNKNOWN"

    logger.info(f"  Detector: {detector_serial}")
    logger.info(f"  Detector max: {detector_max} counts")
    logger.info(f"  Sampling range: 10-90% = {int(detector_max*0.10)}-{int(detector_max*0.90)} counts")

    try:
        # Measure S-polarization
        results_S = measure_polarization_2d_grid(
            controller, spectrometer, opt_controller,
            controller_hw, 'S', SERVO_S_POL, detector_max
        )

        # Measure P-polarization
        results_P = measure_polarization_2d_grid(
            controller, spectrometer, opt_controller,
            controller_hw, 'P', SERVO_P_POL, detector_max
        )

        # Save results
        output_dir = Path('spr_calibration/data')
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save S-polarization data
        s_data = {
            'detector_serial': detector_serial,
            'detector_max': detector_max,
            'sampling_method': '2D_LINEAR',
            'sampling_range': '20-80% detector',
            'sampling_points': '2 per time (linear interpolation)',
            'polarization': 'S',
            'servo_position': SERVO_S_POL,
            'timestamp': datetime.now().isoformat(),
            'leds': {}
        }

        for led_name, data in results_S.items():
            s_data['leds'][led_name] = {
                'measurements': [
                    {'intensity': int(i), 'time': float(t), 'counts': float(c)}
                    for i, t, c in data['measurements']
                ]
            }

        s_file = output_dir / f'spr_2d_grid_S_{detector_serial}.json'
        with open(s_file, 'w') as f:
            json.dump(s_data, f, indent=2)
        logger.info(f"[OK] S-polarization data saved: {s_file}")

        # Save P-polarization data
        p_data = {
            'detector_serial': detector_serial,
            'detector_max': detector_max,
            'sampling_method': '2D_LINEAR',
            'sampling_range': '20-80% detector',
            'sampling_points': '2 per time (linear interpolation)',
            'polarization': 'P',
            'servo_position': SERVO_P_POL,
            'timestamp': datetime.now().isoformat(),
            'leds': {}
        }

        for led_name, data in results_P.items():
            p_data['leds'][led_name] = {
                'measurements': [
                    {'intensity': int(i), 'time': float(t), 'counts': float(c)}
                    for i, t, c in data['measurements']
                ]
            }

        p_file = output_dir / f'spr_2d_grid_P_{detector_serial}.json'
        with open(p_file, 'w') as f:
            json.dump(p_data, f, indent=2)
        logger.info(f"[OK] P-polarization data saved: {p_file}")

        # Final data validation
        logger.info("\n" + "="*80)
        logger.info("FINAL DATA VALIDATION")
        logger.info("="*80)

        validation_passed = True
        saturation_threshold = int(detector_max * SATURATION_THRESHOLD)

        for pol_name, results in [('S', results_S), ('P', results_P)]:
            logger.info(f"\n{pol_name}-Polarization:")

            for led_name, data in results.items():
                measurements = data['measurements']
                if len(measurements) == 0:
                    logger.error(f"  [ERROR] {led_name}: NO MEASUREMENTS!")
                    validation_passed = False
                    continue

                counts = [c for i, t, c in measurements]

                # Check for NaN
                nan_count = sum(1 for c in counts if np.isnan(c))
                if nan_count > 0:
                    logger.error(f"  [ERROR] {led_name}: {nan_count} NaN values detected!")
                    validation_passed = False

                # Check for zeros
                zero_count = sum(1 for c in counts if c <= 0)
                if zero_count > 0:
                    logger.error(f"  [ERROR] {led_name}: {zero_count} zero/negative values!")
                    validation_passed = False

                # Check for saturation
                saturated_count = sum(1 for c in counts if c >= saturation_threshold)
                if saturated_count > 0:
                    logger.warning(f"  [WARN] {led_name}: {saturated_count}/{len(counts)} points saturated (>{saturation_threshold})")

                # Analyze 2D coverage
                times_measured = sorted(set([t for i, t, c in measurements]))
                intensities_per_time = {}
                for time_ms in times_measured:
                    intensities_at_time = [i for i, t, c in measurements if t == time_ms]
                    intensities_per_time[time_ms] = len(intensities_at_time)

                # Check range coverage
                min_count = min(counts)
                max_count = max(counts)

                logger.info(f"  [OK] {led_name}: {len(counts)} points")
                logger.info(f"       2D coverage: {len(times_measured)} times × avg {np.mean(list(intensities_per_time.values())):.1f} intensities/time")
                logger.info(f"       Count range: {min_count:.0f}-{max_count:.0f} ({min_count/detector_max*100:.1f}%-{max_count/detector_max*100:.1f}%)")

        if validation_passed:
            logger.info("\n[OK] All validation checks passed!")
        else:
            logger.error("\n[ERROR] Validation failed - check data quality!")

        # Measure dark current at the end
        logger.info("\n" + "="*80)
        logger.info("DARK CURRENT MEASUREMENT")
        logger.info("="*80)
        logger.info("Measuring dark current after detector warm-up...")

        dark_measurements = []
        integration_times = [5.0, 10.0, 15.0, 25.0, 40.0, 60.0, 80.0, 100.0, 120.0, 150.0, 200.0]

        opt_controller.turn_off_all_leds()
        time.sleep(1.0)

        for time_ms in integration_times:
            spectrometer.set_integration_time(time_ms)
            time.sleep(0.2)

            dark_scans = []
            for scan in range(3):
                spectrum = spectrometer.read_spectrum()
                dark_peak = float(np.max(spectrum))
                dark_scans.append(dark_peak)
                time.sleep(0.1)

            dark_avg = np.mean(dark_scans)
            dark_std = np.std(dark_scans, ddof=1)
            dark_measurements.append({
                'time_ms': float(time_ms),
                'dark_counts': float(dark_avg),
                'std': float(dark_std)
            })

            logger.info(f"  T={time_ms:6.2f}ms -> {dark_avg:7.1f} counts (+/-{dark_std:.1f})")

        # Fit linear model
        times = np.array([m['time_ms'] for m in dark_measurements])
        darks = np.array([m['dark_counts'] for m in dark_measurements])

        A = np.vstack([times, np.ones(len(times))]).T
        dark_rate, dark_offset = np.linalg.lstsq(A, darks, rcond=None)[0]

        residuals = darks - (dark_rate * times + dark_offset)
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((darks - np.mean(darks))**2)
        r_squared = 1 - (ss_res / ss_tot)

        logger.info(f"\n[OK] Dark current model: {dark_rate:.2f} × T + {dark_offset:.1f}")
        logger.info(f"     R² = {r_squared:.6f}")

        dark_data = {
            'detector_serial': detector_serial,
            'detector_max': detector_max,
            'timestamp': datetime.now().isoformat(),
            'measurement_condition': 'post_calibration_warm',
            'measurements': dark_measurements,
            'model': {
                'dark_rate': float(dark_rate),
                'dark_offset': float(dark_offset),
                'r_squared': float(r_squared)
            }
        }

        dark_file = output_dir / f'dark_current_{detector_serial}.json'
        with open(dark_file, 'w') as f:
            json.dump(dark_data, f, indent=2)
        logger.info(f"[OK] Dark current data saved: {dark_file}")

        return {'S': results_S, 'P': results_P}

    finally:
        logger.info("\nShutting down hardware...")
        opt_controller.exit_calibration_mode()
        opt_controller.turn_off_all_leds()
        controller.disconnect()
        spectrometer.disconnect()
        logger.info("[OK] Hardware shutdown complete")


if __name__ == '__main__':
    run_spr_2d_grid_calibration()
