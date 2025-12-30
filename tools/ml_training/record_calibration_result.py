"""Record calibration results to device history database.

This module should be called after each calibration run to track device-specific patterns.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from device_history import DeviceHistoryDatabase, CalibrationRecord
import statistics


def extract_metrics_from_calibration_json(json_path: Path) -> Dict[str, Any]:
    """Extract quality metrics from calibration results JSON.

    Args:
        json_path: Path to calibration results JSON file

    Returns:
        Dict with quality metrics (FWHM, SNR, dip depth)
    """
    with open(json_path, 'r') as f:
        data = json.load(f)

    metrics = {
        'final_fwhm_avg': None,
        'final_fwhm_std': None,
        'final_snr_avg': None,
        'final_dip_depth_avg': None,
        'overall_quality': None,
    }

    # Extract S-mode quality metrics
    if 's' in data and 'channels' in data['s']:
        channels = data['s']['channels']

        fwhm_values = []
        snr_values = []
        dip_depth_values = []

        for ch_name, ch_data in channels.items():
            if 'quality_metrics' in ch_data:
                qm = ch_data['quality_metrics']

                if 'fwhm_nm' in qm:
                    fwhm_values.append(qm['fwhm_nm'])
                if 'snr' in qm:
                    snr_values.append(qm['snr'])
                if 'dip_depth' in qm:
                    dip_depth_values.append(qm['dip_depth'])

        if fwhm_values:
            metrics['final_fwhm_avg'] = statistics.mean(fwhm_values)
            metrics['final_fwhm_std'] = statistics.stdev(fwhm_values) if len(fwhm_values) > 1 else 0.0

        if snr_values:
            metrics['final_snr_avg'] = statistics.mean(snr_values)

        if dip_depth_values:
            metrics['final_dip_depth_avg'] = statistics.mean(dip_depth_values)

        # Determine overall quality
        if metrics['final_fwhm_avg']:
            if metrics['final_fwhm_avg'] < 60:
                metrics['overall_quality'] = 'excellent'
            elif metrics['final_fwhm_avg'] < 70:
                metrics['overall_quality'] = 'good'
            else:
                metrics['overall_quality'] = 'poor'

    return metrics


def extract_metrics_from_debug_log(log_path: Path) -> Dict[str, Any]:
    """Extract convergence metrics from debug log.

    Args:
        log_path: Path to debug log file

    Returns:
        Dict with convergence metrics (iterations, LEDs, temporal features)
    """
    import re

    metrics = {
        'detector_serial': 65535,  # Default
        's_mode_iterations': 0,
        'p_mode_iterations': 0,
        's_mode_converged': False,
        'p_mode_converged': False,
        'final_leds_s_avg': None,
        'final_leds_p_avg': None,
        'final_integration_s': None,
        'final_integration_p': None,
        'led_convergence_rate_s': None,
        'signal_stability_s': None,
        'oscillation_detected_s': False,
        'num_warnings': 0,
    }

    # Patterns
    DEVICE_SERIAL_PATTERN = re.compile(r'DEVICE_SERIAL:\s*(\d+)')
    ITERATION_PATTERN = re.compile(r'\[([sp])\] Iteration (\d+):')
    CONVERGENCE_PATTERN = re.compile(r'\[([sp])\] .*CONVERGED')
    LED_PATTERN = re.compile(r'\[([sp])\] Final LEDs: (.+)')
    INTEGRATION_PATTERN = re.compile(r'\[([sp])\] Integration time: ([\d.]+) ms')
    WARNING_PATTERN = re.compile(r'WARNING', re.IGNORECASE)

    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Extract device serial
    serial_match = DEVICE_SERIAL_PATTERN.search(content)
    if serial_match:
        metrics['detector_serial'] = int(serial_match.group(1))

    # Extract iterations
    for line in content.split('\n'):
        # Count iterations per mode
        iter_match = ITERATION_PATTERN.search(line)
        if iter_match:
            mode = iter_match.group(1)
            iter_num = int(iter_match.group(2))

            if mode == 's':
                metrics['s_mode_iterations'] = max(metrics['s_mode_iterations'], iter_num)
            else:
                metrics['p_mode_iterations'] = max(metrics['p_mode_iterations'], iter_num)

        # Check convergence
        conv_match = CONVERGENCE_PATTERN.search(line)
        if conv_match:
            mode = conv_match.group(1)
            if mode == 's':
                metrics['s_mode_converged'] = True
            else:
                metrics['p_mode_converged'] = True

        # Extract final LEDs
        led_match = LED_PATTERN.search(line)
        if led_match:
            mode = led_match.group(1)
            led_str = led_match.group(2)

            try:
                # Parse LED dict: "{'A': 75, 'B': 80, ...}"
                led_dict = eval(led_str)
                avg_led = statistics.mean(led_dict.values())

                if mode == 's':
                    metrics['final_leds_s_avg'] = avg_led
                else:
                    metrics['final_leds_p_avg'] = avg_led
            except:
                pass

        # Extract integration time
        int_match = INTEGRATION_PATTERN.search(line)
        if int_match:
            mode = int_match.group(1)
            integration = float(int_match.group(2))

            if mode == 's':
                metrics['final_integration_s'] = integration
            else:
                metrics['final_integration_p'] = integration

        # Count warnings
        if WARNING_PATTERN.search(line):
            metrics['num_warnings'] += 1

    return metrics


def record_calibration_to_database(
    debug_log_path: Path,
    calibration_json_path: Optional[Path] = None,
    db_path: Optional[Path] = None
) -> int:
    """Record calibration results to device history database.

    Args:
        debug_log_path: Path to calibration debug log
        calibration_json_path: Optional path to calibration results JSON
        db_path: Optional path to database (defaults to tools/ml_training/device_history.db)

    Returns:
        Record ID
    """
    # Initialize database
    db = DeviceHistoryDatabase(db_path)

    # Extract timestamp from log filename or use current time
    # Expected format: debug_20251220_143022.log
    import re
    timestamp_match = re.search(r'(\d{8}_\d{6})', debug_log_path.name)
    if timestamp_match:
        timestamp_str = timestamp_match.group(1)
        timestamp = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S').isoformat()
    else:
        timestamp = datetime.now().isoformat()

    # Extract metrics from debug log
    log_metrics = extract_metrics_from_debug_log(debug_log_path)

    # Extract quality metrics from JSON if available
    quality_metrics = {}
    if calibration_json_path and calibration_json_path.exists():
        quality_metrics = extract_metrics_from_calibration_json(calibration_json_path)

    # Combine metrics
    success = log_metrics['s_mode_converged'] and log_metrics['p_mode_converged']

    record = CalibrationRecord(
        timestamp=timestamp,
        detector_serial=log_metrics['detector_serial'],
        success=success,

        s_mode_iterations=log_metrics['s_mode_iterations'],
        p_mode_iterations=log_metrics['p_mode_iterations'],
        total_iterations=log_metrics['s_mode_iterations'] + log_metrics['p_mode_iterations'],
        s_mode_converged=log_metrics['s_mode_converged'],
        p_mode_converged=log_metrics['p_mode_converged'],

        final_fwhm_avg=quality_metrics.get('final_fwhm_avg'),
        final_fwhm_std=quality_metrics.get('final_fwhm_std'),
        final_snr_avg=quality_metrics.get('final_snr_avg'),
        final_dip_depth_avg=quality_metrics.get('final_dip_depth_avg'),
        num_warnings=log_metrics['num_warnings'],
        overall_quality=quality_metrics.get('overall_quality'),

        final_leds_s_avg=log_metrics['final_leds_s_avg'],
        final_leds_p_avg=log_metrics['final_leds_p_avg'],
        final_integration_s=log_metrics['final_integration_s'],
        final_integration_p=log_metrics['final_integration_p'],

        led_convergence_rate_s=log_metrics['led_convergence_rate_s'],
        signal_stability_s=log_metrics['signal_stability_s'],
        oscillation_detected_s=log_metrics['oscillation_detected_s'],
    )

    record_id = db.add_record(record)

    print(f"✓ Recorded calibration to device history database")
    print(f"  Device Serial: {record.detector_serial}")
    print(f"  Success: {record.success}")
    print(f"  Total Iterations: {record.total_iterations}")
    print(f"  Record ID: {record_id}")

    return record_id


def main():
    """Test recording from a recent log file."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python record_calibration_result.py <debug_log_path> [calibration_json_path]")
        print("\nExample:")
        print("  python record_calibration_result.py logs/debug_20251220_143022.log calibration_results/calibration_20251220_143022.json")
        sys.exit(1)

    debug_log_path = Path(sys.argv[1])
    calibration_json_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    if not debug_log_path.exists():
        print(f"ERROR: Debug log not found: {debug_log_path}")
        sys.exit(1)

    if calibration_json_path and not calibration_json_path.exists():
        print(f"WARNING: Calibration JSON not found: {calibration_json_path}")
        calibration_json_path = None

    record_id = record_calibration_to_database(debug_log_path, calibration_json_path)

    print(f"\n✓ Successfully recorded calibration (ID: {record_id})")


if __name__ == "__main__":
    main()
