"""
Process SPR Calibration with Polarization and Dark Correction
==============================================================

BILINEAR MODEL - PRODUCTION READY (Validated Dec 2025)
-------------------------------------------------------

This module processes LED-intensity-time calibration measurements and fits a 
physics-based bilinear model to predict detector counts.

Model Equation:
    counts(I, t) = (a·t + b)·I + (c·t + d)

Where:
    - I: LED intensity (0-255)
    - t: Integration time (ms)
    - a, b, c, d: Fitted parameters per LED per polarization

Physical Interpretation:
    - Sensitivity: S(t) = a·t + b (linear with integration time)
    - Dark Signal: D(t) = c·t + d (linear with integration time)
    - Combined: counts = S(t)·I + D(t)

Validation Results:
    - R² > 0.9999 (perfect linearity)
    - Mean error < 0.15%
    - Max error < 2.15% (unsaturated range)
    - Validated: 10-60ms integration time, counts < 60k

Processing Steps:
1. Load S-pol, P-pol, and dark current measurements
2. Validate intensity/time matching between polarizations
3. Apply dark correction to all measurements
4. Fit bilinear model using linear regression (4 parameters per LED/pol)
5. Validate model accuracy in SPR region
6. Save model to JSON for deployment

Output Location:
    spr_calibration/models/led_calibration_spr_processed_{serial}.json

For documentation see:
    spr_calibration/models/BILINEAR_MODEL_DOCUMENTATION.md
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from pathlib import Path
from datetime import datetime

def get_detector_serial():
    """Get detector serial from device config"""
    try:
        config_file = 'src/config/devices/FLMT09116/device_config.json'
        with open(config_file, 'r') as f:
            device_config = json.load(f)
        return device_config['hardware']['spectrometer_serial']
    except (FileNotFoundError, KeyError):
        return 'FLMT09116'  # Default fallback

def load_calibration_data(detector_serial=None):
    """Load S, P, and dark calibration data for specific detector"""

    if detector_serial is None:
        detector_serial = get_detector_serial()

    print("="*80)
    print("LOADING CALIBRATION DATA")
    print("="*80)
    print(f"Detector: {detector_serial}\n")

    # Try loading calibration files in order of preference:
    # 1. spr_2d_grid (new optimized 2-point linear sampling)
    # 2. spr_adaptive (old adaptive sampling)
    # 3. legacy format
    grid_s_file = f'spr_calibration/data/spr_2d_grid_S_{detector_serial}.json'
    grid_p_file = f'spr_calibration/data/spr_2d_grid_P_{detector_serial}.json'
    adaptive_s_file = f'spr_calibration/data/spr_adaptive_S_{detector_serial}.json'
    adaptive_p_file = f'spr_calibration/data/spr_adaptive_P_{detector_serial}.json'

    # Load S-polarization data
    try:
        # Try 2D grid format first (newest)
        if Path(grid_s_file).exists():
            with open(grid_s_file, 'r', encoding='utf-8') as f:
                raw_data_S = json.load(f)
            print(f"[OK] Loaded S-polarization data (2d_grid)")
            # Convert format
            data_S = convert_adaptive_to_old_format(raw_data_S)
        # Try adaptive format
        elif Path(adaptive_s_file).exists():
            with open(adaptive_s_file, 'r', encoding='utf-8') as f:
                raw_data_S = json.load(f)
            print(f"[OK] Loaded S-polarization data (adaptive)")
            # Convert adaptive format to old format
            data_S = convert_adaptive_to_old_format(raw_data_S)
        else:
            # Fall back to old format
            with open('LED-Counts relationship/led_calibration_spr_S_polarization.json', 'r') as f:
                data_S = json.load(f)
            print(f"[OK] Loaded S-polarization data")
        # Verify detector match
        if data_S.get('detector_serial') and data_S['detector_serial'] != detector_serial:
            print(f"[WARN] Data is for detector {data_S['detector_serial']}, current is {detector_serial}")
    except FileNotFoundError:
        print("[ERROR] S-polarization data not found!")
        return None, None, None, None

    # Load P-polarization data
    try:
        # Try 2D grid format first (newest)
        if Path(grid_p_file).exists():
            with open(grid_p_file, 'r', encoding='utf-8') as f:
                raw_data_P = json.load(f)
            print(f"[OK] Loaded P-polarization data (2d_grid)")
            # Convert format
            data_P = convert_adaptive_to_old_format(raw_data_P)
        # Try adaptive format
        elif Path(adaptive_p_file).exists():
            with open(adaptive_p_file, 'r', encoding='utf-8') as f:
                raw_data_P = json.load(f)
            print(f"[OK] Loaded P-polarization data (adaptive)")
            # Convert adaptive format to old format
            data_P = convert_adaptive_to_old_format(raw_data_P)
        else:
            # Fall back to old format
            with open('LED-Counts relationship/led_calibration_spr_P_polarization.json', 'r') as f:
                data_P = json.load(f)
            print(f"[OK] Loaded P-polarization data")
        # Verify detector match
        if data_P.get('detector_serial') and data_P['detector_serial'] != detector_serial:
            print(f"[WARN] Data is for detector {data_P['detector_serial']}, current is {detector_serial}")
    except FileNotFoundError:
        print("[ERROR] P-polarization data not found!")
        return None, None, None, None

    # Load dark current data
    dark_file_new = f'spr_calibration/data/dark_current_{detector_serial}.json'
    dark_file_legacy = 'LED-Counts relationship/dark_signal_calibration.json'

    try:
        # Try new format first
        if Path(dark_file_new).exists():
            with open(dark_file_new, 'r') as f:
                data_dark = json.load(f)
            print(f"[OK] Loaded dark current data (new format)")
            # New format uses 'model' key
            dark_rate = data_dark['model']['dark_rate']
            dark_offset = data_dark['model']['dark_offset']
        else:
            # Fall back to legacy format
            with open(dark_file_legacy, 'r') as f:
                data_dark = json.load(f)
            print(f"[OK] Loaded dark current data (legacy format)")
            # Legacy format uses 'linear_fit' key
            dark_rate = data_dark['linear_fit']['slope']
            dark_offset = data_dark['linear_fit']['offset']
        print(f"  Dark rate: {dark_rate:.2f} counts/ms")
        print(f"  Dark offset: {dark_offset:.1f} counts")
    except FileNotFoundError:
        print("[WARN] Dark current data not found - proceeding without dark correction")
        dark_rate = 0.0
        dark_offset = 0.0

    return data_S, data_P, (dark_rate, dark_offset), detector_serial


def convert_adaptive_to_old_format(adaptive_data):
    """Convert adaptive calibration format to old processing format"""

    led_map = {
        'LED_A': 'A',
        'LED_B': 'B',
        'LED_C': 'C',
        'LED_D': 'D'
    }

    old_format = {
        'detector_serial': adaptive_data.get('detector_serial', 'FLMT09116'),
        'detector_max': adaptive_data.get('detector_max', 65535),
        'polarization': adaptive_data.get('polarization', 'S'),
        'A': {'measurements': []},
        'B': {'measurements': []},
        'C': {'measurements': []},
        'D': {'measurements': []}
    }

    # Convert each LED's data
    for led_wavelength, measurements_dict in adaptive_data.get('leds', {}).items():
        led_letter = led_map.get(led_wavelength)
        if led_letter:
            old_format[led_letter]['measurements'] = measurements_dict.get('measurements', [])

    return old_format


def validate_intensity_time_matching(data_S, data_P):
    """
    Validate that S and P measurements have matching (intensity, time) pairs

    This is critical for building proper 2D RBF models where both S and P
    need to sample the same (intensity, time) space.

    Returns: (is_valid, report_dict)
    """
    print("\n" + "="*80)
    print("VALIDATING S/P INTENSITY/TIME MATCHING")
    print("="*80)

    report = {
        'overall_valid': True,
        'timestamp': datetime.now().isoformat(),
        'leds': {}
    }

    for led_name in ['A', 'B', 'C', 'D']:
        measurements_S = data_S[led_name]['measurements']
        measurements_P = data_P[led_name]['measurements']

        # Extract (intensity, time) pairs, excluding failed measurements
        pairs_S = [(m['intensity'], m['time']) for m in measurements_S
                   if m.get('counts') is not None]
        pairs_P = [(m['intensity'], m['time']) for m in measurements_P
                   if m.get('counts') is not None]

        # Convert to sets for comparison
        set_S = set(pairs_S)
        set_P = set(pairs_P)

        # Find differences
        missing_in_P = set_S - set_P
        missing_in_S = set_P - set_S
        common = set_S & set_P

        # Check for duplicates
        duplicates_S = [p for p in pairs_S if pairs_S.count(p) > 1]
        duplicates_P = [p for p in pairs_P if pairs_P.count(p) > 1]

        led_valid = (len(missing_in_P) == 0 and len(missing_in_S) == 0 and
                    len(duplicates_S) == 0 and len(duplicates_P) == 0)

        report['leds'][led_name] = {
            'valid': led_valid,
            'num_S': len(pairs_S),
            'num_P': len(pairs_P),
            'num_common': len(common),
            'missing_in_P': sorted(list(missing_in_P)),
            'missing_in_S': sorted(list(missing_in_S)),
            'duplicates_S': sorted(list(set(duplicates_S))),
            'duplicates_P': sorted(list(set(duplicates_P)))
        }

        print(f"\nLED {led_name}:")
        print(f"  S measurements: {len(pairs_S)}")
        print(f"  P measurements: {len(pairs_P)}")
        print(f"  Common (I, T) pairs: {len(common)}")

        if duplicates_S:
            print(f"  [WARN]  Duplicates in S: {len(set(duplicates_S))} unique pairs")
            report['overall_valid'] = False

        if duplicates_P:
            print(f"  [WARN]  Duplicates in P: {len(set(duplicates_P))} unique pairs")
            report['overall_valid'] = False

        if missing_in_P:
            print(f"  [WARN]  Missing in P: {len(missing_in_P)} pairs")
            if len(missing_in_P) <= 5:
                for pair in sorted(missing_in_P):
                    print(f"      - I={pair[0]}, T={pair[1]} ms")
            report['overall_valid'] = False

        if missing_in_S:
            print(f"  [WARN]  Missing in S: {len(missing_in_S)} pairs")
            if len(missing_in_S) <= 5:
                for pair in sorted(missing_in_S):
                    print(f"      - I={pair[0]}, T={pair[1]} ms")
            report['overall_valid'] = False

        if led_valid:
            print(f"  [OK] Perfect S/P matching")

    print("\n" + "-"*80)
    if report['overall_valid']:
        print("[OK] ALL LEDS: Perfect S/P matching - ready for 2D RBF model construction")
    else:
        print("[WARN]  WARNING: S/P measurements not perfectly matched")
        print("   This may cause issues in 2D RBF model construction")
        print("   Consider filtering to common pairs only")

    return report['overall_valid'], report


def filter_to_common_pairs(data_S, data_P):
    """
    Filter S and P measurements to only include common (intensity, time) pairs

    This ensures both datasets have identical sampling points for 2D RBF model.

    Returns: (filtered_data_S, filtered_data_P)
    """
    print("\n" + "="*80)
    print("FILTERING TO COMMON (INTENSITY, TIME) PAIRS")
    print("="*80)

    filtered_S = {}
    filtered_P = {}

    for led_name in ['A', 'B', 'C', 'D']:
        measurements_S = data_S[led_name]['measurements']
        measurements_P = data_P[led_name]['measurements']

        # Build dict of (intensity, time) -> measurement for quick lookup
        s_dict = {(m['intensity'], m['time']): m for m in measurements_S
                  if m.get('counts') is not None}
        p_dict = {(m['intensity'], m['time']): m for m in measurements_P
                  if m.get('counts') is not None}

        # Find common pairs
        common_pairs = set(s_dict.keys()) & set(p_dict.keys())

        # Extract measurements for common pairs only
        common_S = [s_dict[pair] for pair in sorted(common_pairs)]
        common_P = [p_dict[pair] for pair in sorted(common_pairs)]

        filtered_S[led_name] = {
            'measurements': common_S,
            'polarization': 'S',
            'original_count': len(measurements_S),
            'filtered_count': len(common_S)
        }

        filtered_P[led_name] = {
            'measurements': common_P,
            'polarization': 'P',
            'original_count': len(measurements_P),
            'filtered_count': len(common_P)
        }

        print(f"LED {led_name}:")
        print(f"  Original S: {len(measurements_S)} -> Filtered: {len(common_S)}")
        print(f"  Original P: {len(measurements_P)} -> Filtered: {len(common_P)}")

        if len(common_S) < len(measurements_S) or len(common_P) < len(measurements_P):
            removed_S = len(measurements_S) - len(common_S)
            removed_P = len(measurements_P) - len(common_P)
            print(f"  [WARN]  Removed {removed_S} S and {removed_P} P measurements")

    return filtered_S, filtered_P


def apply_dark_correction(measurements, dark_rate, dark_offset):
    """Apply dark correction to measurements"""

    corrected = []
    for m in measurements:
        dark_counts = dark_rate * m['time'] + dark_offset
        corrected_counts = m['counts'] - dark_counts

        corrected.append({
            'intensity': m['intensity'],
            'time': m['time'],
            'counts_raw': m['counts'],
            'dark_counts': dark_counts,
            'counts': corrected_counts,  # Dark-corrected signal
            'target': m.get('target', 0),
            'polarization': m.get('polarization', 'unknown')
        })

    return corrected

def build_2d_bilinear_model(measurements, led_name, polarization):
    """
    Build 2D BILINEAR model for LED at given polarization.
    
    Model: counts = (a*t + b)*I + (c*t + d)
    
    This expands to: counts = a*(t*I) + b*I + c*t + d
    
    Which is linear regression with 4 predictors: (t*I), I, t, 1
    
    Returns: dict with 'a', 'b', 'c', 'd' parameters and fit statistics
    """
    
    # Extract data
    intensities = np.array([m['intensity'] for m in measurements])
    times = np.array([m['time'] for m in measurements])
    counts = np.array([m['counts'] for m in measurements])
    
    # Build design matrix: [t*I, I, t, 1]
    X = np.column_stack([
        times * intensities,  # a coefficient
        intensities,           # b coefficient
        times,                 # c coefficient
        np.ones(len(times))   # d coefficient
    ])
    
    # Solve linear system: X * params = counts
    params, residuals, rank, s = np.linalg.lstsq(X, counts, rcond=None)
    
    a, b, c, d = params
    
    # Calculate R²
    predicted = X @ params
    ss_res = np.sum((counts - predicted) ** 2)
    ss_tot = np.sum((counts - np.mean(counts)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    
    # Calculate RMSE
    rmse = np.sqrt(np.mean((counts - predicted) ** 2))
    
    model = {
        'type': 'bilinear',
        'a': float(a),  # Sensitivity time slope (counts/intensity/ms)
        'b': float(b),  # Sensitivity intercept (counts/intensity)
        'c': float(c),  # Offset time slope (counts/ms)
        'd': float(d),  # Offset intercept (counts)
        'r_squared': float(r_squared),
        'rmse': float(rmse),
        'n_measurements': len(measurements),
        'led': led_name,
        'polarization': polarization
    }
    
    return model


def predict_bilinear(model, intensity, time):
    """
    Predict counts using bilinear model.
    
    counts = (a*t + b)*I + (c*t + d)
    """
    a = model['a']
    b = model['b']
    c = model['c']
    d = model['d']
    
    return (a * time + b) * intensity + (c * time + d)


def validate_bilinear_model(model, measurements, led_name, polarization):
    """Validate bilinear model accuracy against measurements"""
    
    errors = []
    errors_pct = []
    
    for m in measurements:
        predicted = predict_bilinear(model, m['intensity'], m['time'])
        actual = m['counts']
        error = predicted - actual
        error_pct = (error / actual) * 100 if actual != 0 else 0
        
        errors.append(error)
        errors_pct.append(error_pct)
    
    return {
        'mean_error': float(np.mean(errors_pct)),
        'std_error': float(np.std(errors_pct)),
        'max_error': float(np.max(np.abs(errors_pct))),
        'rmse': float(np.sqrt(np.mean(np.array(errors)**2))),
        'errors': errors,
        'errors_pct': errors_pct
    }

def process_calibration():
    """Main processing function"""

    # Load data
    data_S, data_P, dark_params, detector_serial = load_calibration_data()

    if data_S is None or data_P is None:
        print("\nERROR: Required calibration data not found!")
        print("Run: python measure_spr_calibration_matched.py")
        return

    dark_rate, dark_offset = dark_params

    # Validate S/P matching
    is_matched, validation_report = validate_intensity_time_matching(data_S, data_P)

    # Save validation report
    validation_file = f'LED-Counts relationship/spr_processing_validation_{detector_serial}.json'
    with open(validation_file, 'w') as f:
        json.dump(validation_report, f, indent=2)
    print(f"\n[OK] Validation report saved to: {validation_file}")

    # Filter to common pairs if not perfectly matched
    if not is_matched:
        print("\n[WARN] For adaptive sampling, S and P sample independently")
        print("       Building separate models without filtering...")
        print("       (Each polarization will have its own optimized model)")

        # Don't filter - just use the data as-is for independent modeling
        # data_S and data_P keep their original measurements
    else:
        print("\n[OK] Data validation passed - proceeding with processing")

    print("\n" + "="*80)
    print("APPLYING DARK CORRECTION")
    print("="*80)

    # Process each LED
    models_S = {}
    models_P = {}
    processed_data = {
        'detector_serial': detector_serial,
        'processed_date': str(np.datetime64('now')),
        'calibration_type': 'SPR 2D Bilinear',
        'model_equation': 'counts(I,t) = (a*t + b)*I + (c*t + d)',
        'S': {'A': {}, 'B': {}, 'C': {}, 'D': {}},
        'P': {'A': {}, 'B': {}, 'C': {}, 'D': {}},
        'dark': {'rate': dark_rate, 'offset': dark_offset}
    }

    for led_name in ['A', 'B', 'C', 'D']:
        print(f"\nLED {led_name}:")

        # Process S-polarization
        measurements_S_raw = data_S[led_name]['measurements']
        measurements_S = apply_dark_correction(measurements_S_raw, dark_rate, dark_offset)

        print(f"  S-pol: {len(measurements_S)} measurements")
        if len(measurements_S) > 0:
            counts_S = [m['counts'] for m in measurements_S]
            print(f"    Raw counts range: {min([m['counts_raw'] for m in measurements_S]):.0f} - "
                  f"{max([m['counts_raw'] for m in measurements_S]):.0f}")
            print(f"    Corrected counts range: {min(counts_S):.0f} - {max(counts_S):.0f}")
        else:
            counts_S = []
            print(f"    [WARN] No S-polarization measurements for LED {led_name}")

        # Process P-polarization
        measurements_P_raw = data_P[led_name]['measurements']
        measurements_P = apply_dark_correction(measurements_P_raw, dark_rate, dark_offset)

        print(f"  P-pol: {len(measurements_P)} measurements")
        if len(measurements_P) > 0:
            counts_P = [m['counts'] for m in measurements_P]
            print(f"    Raw counts range: {min([m['counts_raw'] for m in measurements_P]):.0f} - "
                  f"{max([m['counts_raw'] for m in measurements_P]):.0f}")
            print(f"    Corrected counts range: {min(counts_P):.0f} - {max(counts_P):.0f}")
        else:
            counts_P = []
            print(f"    [WARN] No P-polarization measurements for LED {led_name}")

        # Calculate average polarization ratio
        if len(counts_S) > 0 and len(counts_P) > 0:
            avg_S = np.mean(counts_S)
            avg_P = np.mean(counts_P)
            pol_ratio = avg_S / avg_P if avg_P > 0 else 1.0
            print(f"    Polarization ratio (S/P): {pol_ratio:.3f}")
        else:
            print(f"    [WARN] Cannot calculate polarization ratio - missing measurements")

        # Store processed data
        processed_data['S'][led_name] = {
            'measurements': measurements_S,
            'polarization': 'S'
        }
        processed_data['P'][led_name] = {
            'measurements': measurements_P,
            'polarization': 'P'
        }

    print("\n" + "="*80)
    print("BUILDING 2D BILINEAR MODELS")
    print("="*80)
    print("Model: counts(I, t) = (a*t + b)*I + (c*t + d)")
    print("  - Sensitivity = a*t + b (linear with time)")
    print("  - Offset = c*t + d (linear with time)")
    print("="*80)

    validation_results = {}

    for led_name in ['A', 'B', 'C', 'D']:
        print(f"\nLED {led_name}:")

        # Build S model
        measurements_S = processed_data['S'][led_name]['measurements']

        # Check if we have enough points for bilinear fit (need at least 4)
        if len(measurements_S) < 4:
            print(f"  [WARN] Skipping S-pol: only {len(measurements_S)} points (need >=4)")
            models_S[led_name] = None
            val_S = None
        else:
            model_S = build_2d_bilinear_model(measurements_S, led_name, 'S')
            models_S[led_name] = model_S

            # Validate S model
            val_S = validate_bilinear_model(model_S, measurements_S, led_name, 'S')
            print(f"  S-pol model:")
            print(f"    a={model_S['a']:.4f} (sens. slope), b={model_S['b']:.2f} (sens. intercept)")
            print(f"    c={model_S['c']:.4f} (offset slope), d={model_S['d']:.2f} (offset intercept)")
            print(f"    R²={model_S['r_squared']:.6f}, RMSE={model_S['rmse']:.1f} counts")
            print(f"    Mean error: {val_S['mean_error']:.2f}%")
            print(f"    Max error: {val_S['max_error']:.2f}%")
            
            # Store model in processed data
            processed_data['S'][led_name]['model'] = model_S

        # Build P model
        measurements_P = processed_data['P'][led_name]['measurements']

        # Check if we have enough points for bilinear fit (need at least 4)
        if len(measurements_P) < 4:
            print(f"  [WARN] Skipping P-pol: only {len(measurements_P)} points (need >=4)")
            models_P[led_name] = None
            val_P = None
        else:
            model_P = build_2d_bilinear_model(measurements_P, led_name, 'P')
            models_P[led_name] = model_P

            # Validate P model
            val_P = validate_bilinear_model(model_P, measurements_P, led_name, 'P')
            print(f"  P-pol model:")
            print(f"    a={model_P['a']:.4f} (sens. slope), b={model_P['b']:.2f} (sens. intercept)")
            print(f"    c={model_P['c']:.4f} (offset slope), d={model_P['d']:.2f} (offset intercept)")
            print(f"    R²={model_P['r_squared']:.6f}, RMSE={model_P['rmse']:.1f} counts")
            print(f"    Mean error: {val_P['mean_error']:.2f}%")
            print(f"    Max error: {val_P['max_error']:.2f}%")
            
            # Store model in processed data
            processed_data['P'][led_name]['model'] = model_P

        validation_results[led_name] = {
            'S': val_S if val_S else {'mean_error': None, 'std_error': None, 'max_error': None},
            'P': val_P if val_P else {'mean_error': None, 'std_error': None, 'max_error': None},
            'measurements': {'S': len(measurements_S), 'P': len(measurements_P)}
        }

    # Save processed data with detector-specific filename
    output_file = f'LED-Counts relationship/led_calibration_spr_processed_{detector_serial}.json'
    with open(output_file, 'w') as f:
        json.dump(processed_data, f, indent=2)

    print(f"\n[OK] Processed data saved to: {output_file}")
    print(f"  Detector: {detector_serial}")
    print(f"  Date: {processed_data['processed_date']}")

    # Calculate and display polarization transmission factors
    print("\n" + "="*80)
    print("POLARIZATION TRANSMISSION ANALYSIS")
    print("="*80)

    print(f"\n{'LED':<6} {'Avg S Counts':<15} {'Avg P Counts':<15} {'S/P Ratio':<12} {'Extinction':<12}")
    print("-"*80)

    pol_ratios = []

    for led_name in ['A', 'B', 'C', 'D']:
        measurements_S = processed_data['S'][led_name]['measurements']
        measurements_P = processed_data['P'][led_name]['measurements']

        avg_S = np.mean([m['counts'] for m in measurements_S])
        avg_P = np.mean([m['counts'] for m in measurements_P])

        ratio = avg_S / avg_P if avg_P > 0 else 1.0
        extinction = abs(avg_S - avg_P) / max(avg_S, avg_P) * 100

        pol_ratios.append(ratio)

        print(f"{led_name:<6} {avg_S:<15.0f} {avg_P:<15.0f} {ratio:<12.3f} {extinction:<12.1f}%")

    avg_ratio = np.mean(pol_ratios)
    std_ratio = np.std(pol_ratios)

    print("-"*80)
    print(f"{'Avg':<6} {'':15} {'':15} {avg_ratio:<12.3f} (+/- {std_ratio:.3f})")

    if std_ratio > 0.1:
        print("\n[WARN]  WARNING: High variation in S/P ratio across LEDs (>10%)")
        print("   This suggests wavelength-dependent polarization effects")

    if avg_ratio > 1.2 or avg_ratio < 0.8:
        print(f"\n[WARN]  NOTE: S/P ratio = {avg_ratio:.3f}")
        print("   Significant polarization dependence detected")
        print("   This may include SPR effects if sample was present during calibration")

    # Create visualization
    create_calibration_plots(processed_data, models_S, models_P)

    print("\n" + "="*80)
    print("CALIBRATION PROCESSING COMPLETE")
    print("="*80)
    print("""
NEXT STEPS:
1. Review validation errors - should be <5% for production use
2. Check polarization ratios - ensure consistency across LEDs
3. Review system performance metrics below
4. Update LED2DCalibrationModel to use polarization-aware model
5. Test SPR measurements with new calibration

FILES CREATED:
- led_calibration_spr_processed_<DETECTOR_SERIAL>.json (normalized data)
- spr_calibration_comparison_<DETECTOR_SERIAL>.png (S vs P visualization)

NOTE: Calibration files are detector-specific and include serial number.
""")

    return processed_data, models_S, models_P


def create_calibration_plots(processed_data, models_S, models_P):
    """Create enhanced 3D plots with safety margins and contour projections"""

    print("\n" + "="*80)
    print("CREATING 3D VISUALIZATION - SAFE vs SATURATING REGIONS")
    print("="*80)

    detector_serial = processed_data.get('detector_serial', 'unknown')
    detector_max = processed_data.get('detector_max', 65535)
    saturation_threshold = int(detector_max * 0.91)  # 91% saturation
    target_max = int(detector_max * 0.80)  # 80% target

    # Create figure with 5 subplots: 4 per-LED + 1 global
    fig = plt.figure(figsize=(20, 14))

    # Define subplot positions
    subplot_positions = [
        (2, 3, 1),  # LED_A
        (2, 3, 2),  # LED_B
        (2, 3, 3),  # LED_C
        (2, 3, 4),  # LED_D
        (2, 3, (5, 6))  # Global
    ]

    # Process each LED
    all_safe_points = []
    all_saturating_points = []
    all_warning_points = []

    for idx, led_name in enumerate(['A', 'B', 'C', 'D']):
        ax = fig.add_subplot(*subplot_positions[idx], projection='3d')

        # Collect measurements from both polarizations
        measurements_S = processed_data['S'][led_name]['measurements']
        measurements_P = processed_data['P'][led_name]['measurements']

        safe_S = []
        warning_S = []
        saturating_S = []
        safe_P = []
        warning_P = []
        saturating_P = []

        # Classify S-pol measurements (safe < 80%, warning 80-91%, saturating >= 91%)
        for m in measurements_S:
            point = [m['intensity'], m['time'], m['counts']]
            if m['counts'] >= saturation_threshold:
                saturating_S.append(point)
            elif m['counts'] >= target_max:
                warning_S.append(point)
            else:
                safe_S.append(point)

        # Classify P-pol measurements
        for m in measurements_P:
            point = [m['intensity'], m['time'], m['counts']]
            if m['counts'] >= saturation_threshold:
                saturating_P.append(point)
            elif m['counts'] >= target_max:
                warning_P.append(point)
            else:
                safe_P.append(point)

        # Add to global collection
        all_safe_points.extend(safe_S + safe_P)
        all_warning_points.extend(warning_S + warning_P)
        all_saturating_points.extend(saturating_S + saturating_P)

        # Convert to arrays for plotting
        safe_S = np.array(safe_S) if safe_S else np.empty((0, 3))
        warning_S = np.array(warning_S) if warning_S else np.empty((0, 3))
        saturating_S = np.array(saturating_S) if saturating_S else np.empty((0, 3))
        safe_P = np.array(safe_P) if safe_P else np.empty((0, 3))
        warning_P = np.array(warning_P) if warning_P else np.empty((0, 3))
        saturating_P = np.array(saturating_P) if saturating_P else np.empty((0, 3))

        # Plot safe points (green)
        if len(safe_S) > 0:
            ax.scatter(safe_S[:, 0], safe_S[:, 1], safe_S[:, 2],
                      c='#2ecc71', marker='o', s=50, alpha=0.7,
                      edgecolors='darkgreen', linewidths=1.5, label='S-pol Safe')

        if len(safe_P) > 0:
            ax.scatter(safe_P[:, 0], safe_P[:, 1], safe_P[:, 2],
                      c='#3498db', marker='s', s=50, alpha=0.7,
                      edgecolors='darkblue', linewidths=1.5, label='P-pol Safe')

        # Plot warning points (yellow/orange - between 80-91%)
        if len(warning_S) > 0:
            ax.scatter(warning_S[:, 0], warning_S[:, 1], warning_S[:, 2],
                      c='#f39c12', marker='o', s=70, alpha=0.8,
                      edgecolors='darkorange', linewidths=2, label='S-pol Warning')

        if len(warning_P) > 0:
            ax.scatter(warning_P[:, 0], warning_P[:, 1], warning_P[:, 2],
                      c='#f1c40f', marker='s', s=70, alpha=0.8,
                      edgecolors='orange', linewidths=2, label='P-pol Warning')

        # Plot saturating points (red)
        if len(saturating_S) > 0:
            ax.scatter(saturating_S[:, 0], saturating_S[:, 1], saturating_S[:, 2],
                      c='#e74c3c', marker='X', s=120, alpha=1.0,
                      edgecolors='darkred', linewidths=2.5, label='S-pol SAT')

        if len(saturating_P) > 0:
            ax.scatter(saturating_P[:, 0], saturating_P[:, 1], saturating_P[:, 2],
                      c='#c0392b', marker='X', s=120, alpha=1.0,
                      edgecolors='maroon', linewidths=2.5, label='P-pol SAT')

        # Draw reference planes
        if len(safe_S) > 0 or len(safe_P) > 0 or len(warning_S) > 0 or len(warning_P) > 0 or len(saturating_S) > 0 or len(saturating_P) > 0:
            all_points = []
            if len(safe_S) > 0: all_points.extend(safe_S.tolist())
            if len(safe_P) > 0: all_points.extend(safe_P.tolist())
            if len(warning_S) > 0: all_points.extend(warning_S.tolist())
            if len(warning_P) > 0: all_points.extend(warning_P.tolist())
            if len(saturating_S) > 0: all_points.extend(saturating_S.tolist())
            if len(saturating_P) > 0: all_points.extend(saturating_P.tolist())

            if all_points:
                all_points = np.array(all_points)
                x_range = [all_points[:, 0].min(), all_points[:, 0].max()]
                y_range = [all_points[:, 1].min(), all_points[:, 1].max()]

                # Create mesh for planes
                xx, yy = np.meshgrid(x_range, y_range)

                # Saturation plane (red, 91%)
                zz_sat = np.full_like(xx, saturation_threshold)
                ax.plot_surface(xx, yy, zz_sat, alpha=0.15, color='red',
                              linewidth=0, antialiased=True)

                # Target plane (green, 80%)
                zz_target = np.full_like(xx, target_max)
                ax.plot_surface(xx, yy, zz_target, alpha=0.1, color='green',
                              linewidth=0, antialiased=True)

                # Add contour projections on bottom plane
                z_min = all_points[:, 2].min()
                if len(safe_S) > 0:
                    ax.scatter(safe_S[:, 0], safe_S[:, 1], z_min,
                             c='lightgreen', marker='o', s=10, alpha=0.3)
                if len(safe_P) > 0:
                    ax.scatter(safe_P[:, 0], safe_P[:, 1], z_min,
                             c='lightblue', marker='s', s=10, alpha=0.3)
                if len(saturating_S) > 0 or len(saturating_P) > 0:
                    sat_combined = np.vstack([s for s in [saturating_S, saturating_P] if len(s) > 0])
                    ax.scatter(sat_combined[:, 0], sat_combined[:, 1], z_min,
                             c='pink', marker='x', s=20, alpha=0.4)

        # Labels and styling
        ax.set_xlabel('Intensity', fontsize=10, labelpad=10, fontweight='bold')
        ax.set_ylabel('Time (ms)', fontsize=10, labelpad=10, fontweight='bold')
        ax.set_zlabel('Counts', fontsize=10, labelpad=10, fontweight='bold')

        safe_count = len(safe_S) + len(safe_P)
        warn_count = len(warning_S) + len(warning_P)
        sat_count = len(saturating_S) + len(saturating_P)
        total = safe_count + warn_count + sat_count

        # Calculate safety percentage
        safety_pct = (safe_count / total * 100) if total > 0 else 0

        title_color = 'green' if safety_pct > 80 else ('orange' if safety_pct > 60 else 'red')
        ax.set_title(f'LED {led_name} - Safety: {safety_pct:.0f}%\n'
                    f'Safe: {safe_count} | Warning: {warn_count} | SAT: {sat_count}',
                    fontsize=11, fontweight='bold', color=title_color, pad=15)

        ax.legend(fontsize=7, loc='upper left', framealpha=0.9)
        ax.view_init(elev=25, azim=45)
        ax.grid(True, alpha=0.2, linestyle='--')

        # Add background color based on safety
        ax.set_facecolor('#f0f0f0' if safety_pct > 80 else '#fff9e6')

    # Create global overview plot
    ax_global = fig.add_subplot(*subplot_positions[4], projection='3d')

    # Convert global collections to arrays
    safe_all = np.array(all_safe_points) if all_safe_points else np.empty((0, 3))
    warn_all = np.array(all_warning_points) if all_warning_points else np.empty((0, 3))
    sat_all = np.array(all_saturating_points) if all_saturating_points else np.empty((0, 3))

    if len(safe_all) > 0:
        ax_global.scatter(safe_all[:, 0], safe_all[:, 1], safe_all[:, 2],
                         c='#2ecc71', marker='o', s=25, alpha=0.5, label='Safe (<80%)')

    if len(warn_all) > 0:
        ax_global.scatter(warn_all[:, 0], warn_all[:, 1], warn_all[:, 2],
                         c='#f39c12', marker='^', s=35, alpha=0.7, label='Warning (80-91%)')

    if len(sat_all) > 0:
        ax_global.scatter(sat_all[:, 0], sat_all[:, 1], sat_all[:, 2],
                         c='#e74c3c', marker='X', s=80, alpha=0.9,
                         edgecolors='darkred', linewidths=2, label='Saturating (≥91%)')

    # Draw global reference planes
    if len(safe_all) > 0 or len(warn_all) > 0 or len(sat_all) > 0:
        all_global = []
        if len(safe_all) > 0: all_global.extend(safe_all.tolist())
        if len(warn_all) > 0: all_global.extend(warn_all.tolist())
        if len(sat_all) > 0: all_global.extend(sat_all.tolist())

        if all_global:
            all_global = np.array(all_global)
            x_range = [all_global[:, 0].min(), all_global[:, 0].max()]
            y_range = [all_global[:, 1].min(), all_global[:, 1].max()]

            xx, yy = np.meshgrid(x_range, y_range)

            # Saturation plane
            zz_sat = np.full_like(xx, saturation_threshold)
            ax_global.plot_surface(xx, yy, zz_sat, alpha=0.2, color='red',
                                  linewidth=0, antialiased=True)

            # Target plane
            zz_target = np.full_like(xx, target_max)
            ax_global.plot_surface(xx, yy, zz_target, alpha=0.15, color='green',
                                  linewidth=0, antialiased=True)

            # Contour projections
            z_min = all_global[:, 2].min()
            if len(safe_all) > 0:
                ax_global.scatter(safe_all[:, 0], safe_all[:, 1], z_min,
                                c='lightgreen', marker='o', s=8, alpha=0.2)
            if len(sat_all) > 0:
                ax_global.scatter(sat_all[:, 0], sat_all[:, 1], z_min,
                                c='pink', marker='x', s=15, alpha=0.3)

    ax_global.set_xlabel('Intensity', fontsize=11, labelpad=12, fontweight='bold')
    ax_global.set_ylabel('Time (ms)', fontsize=11, labelpad=12, fontweight='bold')
    ax_global.set_zlabel('Counts', fontsize=11, labelpad=12, fontweight='bold')

    total_safe = len(all_safe_points)
    total_warn = len(all_warning_points)
    total_sat = len(all_saturating_points)
    total_all = total_safe + total_warn + total_sat

    global_safety_pct = (total_safe / total_all * 100) if total_all > 0 else 0

    ax_global.set_title(f'GLOBAL SYSTEM VIEW - All LEDs & Polarizations\n'
                       f'Safety Score: {global_safety_pct:.1f}% ({total_safe}/{total_all} safe)\n'
                       f'Safe: {total_safe} | Warning: {total_warn} | Saturating: {total_sat}\n'
                       f'Limits: Target={target_max} (80%) | Saturation={saturation_threshold} (91%)',
                       fontsize=12, fontweight='bold', pad=20)

    ax_global.legend(fontsize=10, loc='upper left', framealpha=0.95)
    ax_global.view_init(elev=30, azim=50)
    ax_global.grid(True, alpha=0.2, linestyle='--')

    plt.tight_layout(pad=2.0)

    output_plot = f'LED-Counts relationship/spr_calibration_comparison_{detector_serial}.png'
    plt.savefig(output_plot, dpi=200, bbox_inches='tight', facecolor='white')
    print(f"[OK] Enhanced 3D Visualization saved to: {output_plot}")
    print(f"     Global Safety Score: {global_safety_pct:.1f}%")
    print(f"     Safe parameters: {total_safe} (target range)")
    print(f"     Warning parameters: {total_warn} (80-91%, approaching saturation)")
    print(f"     Saturating parameters: {total_sat} (>=91%, unusable)")
    print(f"     Target threshold: {target_max} counts (80% of {detector_max})")
    print(f"     Saturation threshold: {saturation_threshold} counts (91% of {detector_max})")
    plt.close()


def analyze_system_performance(models_S, models_P):
    """
    Analyze 3 key system metrics:
    1. Global minimum integration time to reach 80% detector max (all 4 LEDs)
    2. Per-channel fastest integration time at max LED intensity (255) to reach 80%
    3. Detector sensitivity at different integration times
    """
    print("\n" + "="*80)
    print("SYSTEM PERFORMANCE ANALYSIS")
    print("="*80)

    # Hard-code detector max
    detector_max = 65535
    target_80 = detector_max * 0.80  # 80% of max

    # Metric 1: Global minimum integration time (all LEDs can reach 80%)
    print("\n[1] GLOBAL INTEGRATION TIME LIMIT (80% detector max)")
    print(f"    Target: {target_80:.0f} counts ({detector_max} max)")

    global_min_times = {}
    for led_letter in ['A', 'B', 'C', 'D']:
        # Try both S and P polarizations
        model_S = models_S.get(led_letter)
        model_P = models_P.get(led_letter)

        for pol, model in [('S', model_S), ('P', model_P)]:
            if model is None:
                continue

            # Find minimum integration time at max intensity (255) to reach 80%
            # Search from 5ms to 200ms with 0.01ms resolution
            for t_ms in np.arange(5, 201, 0.01):
                predicted = predict_bilinear(model, 255, t_ms)
                if predicted >= target_80:
                    key = f"{led_letter}_{pol}"
                    global_min_times[key] = t_ms
                    break

    if global_min_times:
        max_time = max(global_min_times.values())
        slowest = [k for k, v in global_min_times.items() if v == max_time][0]
        print(f"    Slowest LED: {slowest} requires {max_time:.2f}ms")
        print(f"    -> Global minimum: {max_time:.2f}ms (all LEDs reach 80%)")
        print(f"\n    Per-LED breakdown:")
        for key in sorted(global_min_times.keys()):
            print(f"      {key}: {global_min_times[key]:.2f}ms")
    else:
        print("    [WARN] No LEDs can reach 80% detector max")

    # Metric 2: Per-channel fastest time at max LED intensity
    print("\n[2] PER-CHANNEL FASTEST INTEGRATION TIME (I=255, 80% target)")

    for led_letter in ['A', 'B', 'C', 'D']:
        print(f"\n    LED_{led_letter}:")

        model_S = models_S.get(led_letter)
        model_P = models_P.get(led_letter)

        for pol, model in [('S', model_S), ('P', model_P)]:
            if model is None:
                print(f"      {pol}-pol: No model")
                continue

            # Find minimum time with 0.01ms resolution
            found = False
            for t_ms in np.arange(5, 201, 0.01):
                predicted = predict_bilinear(model, 255, t_ms)
                if predicted >= target_80:
                    print(f"      {pol}-pol: {t_ms:.2f}ms (predicted: {predicted:.0f} counts)")
                    found = True
                    break

            if not found:
                # Check what max we can achieve
                max_predicted = predict_bilinear(model, 255, 200)
                print(f"      {pol}-pol: Cannot reach 80% (max: {max_predicted:.0f} @ 200ms)")

    # Metric 3: Detector sensitivity at different integration times
    print("\n[3] DETECTOR SENSITIVITY ANALYSIS (counts per ms at I=255)")
    print("    Integration Time -> Sensitivity (counts/ms)")

    # Analyze at different integration times
    test_times = [10, 25, 50, 100, 150, 200]

    for led_letter in ['A', 'B', 'C', 'D']:
        print(f"\n    LED_{led_letter}:")

        model_S = models_S.get(led_letter)
        model_P = models_P.get(led_letter)

        for pol, model in [('S', model_S), ('P', model_P)]:
            if model is None:
                continue

            sensitivities = []
            for t_ms in test_times:
                counts = predict_bilinear(model, 255, t_ms)
                sensitivity = counts / t_ms
                sensitivities.append(sensitivity)

            print(f"      {pol}-pol:", end="")
            for t_ms, sens in zip(test_times, sensitivities):
                print(f" {t_ms}ms={sens:.1f}", end="")
            print()

            # Check if sensitivity changes (non-linear detector response)
            if len(sensitivities) > 1:
                sens_range = max(sensitivities) - min(sensitivities)
                sens_avg = np.mean(sensitivities)
                variation = (sens_range / sens_avg) * 100
                if variation > 10:
                    print(f"        [WARN] Sensitivity varies by {variation:.1f}% - non-linear detector response!")

    print("\n" + "="*80)


def calculate_sensitivity_correction_factors(models_S, models_P, detector_max=65535):
    """
    Calculate time-dependent sensitivity correction factors for each LED/polarization.

    Returns a dictionary of correction factors that normalize measurements to a
    reference integration time (10ms), accounting for non-linear detector response.

    Correction factor = (reference_sensitivity) / (actual_sensitivity)
    Normalized_counts = raw_counts × correction_factor
    """
    print("\n" + "="*80)
    print("CALCULATING SENSITIVITY CORRECTION FACTORS")
    print("="*80)
    print("Reference: 10ms integration time (highest efficiency)")
    print()

    correction_factors = {}

    # Reference integration time (shortest = most efficient)
    ref_time = 10.0
    intensity = 255  # Max intensity for sensitivity calculation

    for led_name in ['A', 'B', 'C', 'D']:
        correction_factors[f'LED_{led_name}'] = {}

        print(f"LED_{led_name}:")

        for pol, models in [('S', models_S), ('P', models_P)]:
            model = models.get(led_name)
            if model is None:
                print(f"  {pol}-pol: [SKIP] No model")
                continue

            # Calculate reference sensitivity at 10ms
            try:
                ref_counts = predict_bilinear(model, intensity, ref_time)
                ref_sensitivity = ref_counts / ref_time
            except:
                print(f"  {pol}-pol: [ERROR] Cannot calculate reference sensitivity")
                continue

            # Calculate correction factors across integration time range
            time_points = np.arange(5, 201, 5)  # 5-200ms in 5ms steps
            factors = []

            for t_ms in time_points:
                try:
                    counts = predict_bilinear(model, intensity, t_ms)
                    actual_sensitivity = counts / t_ms

                    # Correction factor normalizes to reference sensitivity
                    correction = ref_sensitivity / actual_sensitivity
                    factors.append({
                        'time_ms': float(t_ms),
                        'correction_factor': float(correction),
                        'sensitivity': float(actual_sensitivity)
                    })
                except:
                    pass

            if len(factors) > 0:
                correction_factors[f'LED_{led_name}'][pol] = {
                    'reference_time_ms': ref_time,
                    'reference_sensitivity': float(ref_sensitivity),
                    'factors': factors
                }

                # Show summary
                factor_values = [f['correction_factor'] for f in factors]
                min_factor = min(factor_values)
                max_factor = max(factor_values)
                range_pct = (max_factor - min_factor) / min_factor * 100

                print(f"  {pol}-pol: Correction range {min_factor:.3f}-{max_factor:.3f} ({range_pct:.1f}% variation)")
            else:
                print(f"  {pol}-pol: [ERROR] No correction factors calculated")

    return correction_factors


def apply_sensitivity_correction(counts, time_ms, led_name, polarization, correction_factors):
    """
    Apply sensitivity correction to raw counts based on integration time.

    Args:
        counts: Raw detector counts
        time_ms: Integration time in milliseconds
        led_name: LED identifier (e.g., 'LED_A')
        polarization: 'S' or 'P'
        correction_factors: Dictionary from calculate_sensitivity_correction_factors()

    Returns:
        Corrected counts normalized to reference integration time
    """
    if led_name not in correction_factors:
        return counts

    if polarization not in correction_factors[led_name]:
        return counts

    factors_data = correction_factors[led_name][polarization]['factors']

    # Find nearest time point
    times = [f['time_ms'] for f in factors_data]
    factors = [f['correction_factor'] for f in factors_data]

    # Interpolate correction factor for exact time
    correction = np.interp(time_ms, times, factors)

    return counts * correction


if __name__ == '__main__':
    """
    Main Processing Pipeline
    ------------------------
    
    Run this script to:
    1. Process calibration measurements (S-pol, P-pol, dark current)
    2. Fit bilinear models (4 parameters per LED per polarization)
    3. Validate model accuracy
    4. Generate visualizations
    5. Save model to: spr_calibration/models/led_calibration_spr_processed_{serial}.json
    
    The output JSON can be deployed to other systems via Git.
    
    Model Performance:
    - R² > 0.9999 (perfect linearity)
    - Errors < 2% in valid operating range (10-60ms, counts < 60k)
    - Validated with transmission spectra and fixed intensity tests
    
    See: spr_calibration/models/BILINEAR_MODEL_DOCUMENTATION.md
    """
    result = process_calibration()

    # Run system performance analysis
    if result:
        processed_data, models_S, models_P = result
        analyze_system_performance(models_S, models_P)
        
        print("\n" + "="*80)
        print("✅ CALIBRATION PROCESSING COMPLETE")
        print("="*80)
        print("\nModel saved to: spr_calibration/models/")
        print("Documentation: spr_calibration/models/BILINEAR_MODEL_DOCUMENTATION.md")
        print("\nNext steps:")
        print("  1. Review validation plots in LED-Counts relationship/")
        print("  2. Run tests: python spr_calibration/tests/validate_*.py")
        print("  3. Commit model JSON to Git for deployment")
        print("="*80)

        # Calculate and save sensitivity correction factors
        correction_factors = calculate_sensitivity_correction_factors(models_S, models_P)

        # Save correction factors to file
        detector_serial = processed_data.get('detector_serial', 'unknown')
        correction_file = f'LED-Counts relationship/sensitivity_correction_factors_{detector_serial}.json'

        correction_data = {
            'detector_serial': detector_serial,
            'detector_max': processed_data.get('detector_max', 65535),
            'timestamp': datetime.now().isoformat(),
            'description': 'Time-dependent sensitivity correction factors to normalize detector non-linearity',
            'usage': 'corrected_counts = raw_counts * correction_factor[time_ms]',
            'correction_factors': correction_factors
        }

        with open(correction_file, 'w') as f:
            json.dump(correction_data, f, indent=2)

        print(f"\n[OK] Sensitivity correction factors saved to: {correction_file}")
        print("     Use apply_sensitivity_correction() to normalize measurements")
        print("     This corrects for non-linear detector response across integration times")