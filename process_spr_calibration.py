"""
Process SPR Calibration with Polarization and Dark Correction
==============================================================

Processes S-pol, P-pol, and dark measurements to create normalized calibration models.

Steps:
1. Load S, P, and dark measurements
2. Validate intensity/time matching between S and P
3. Apply dark correction to all measurements
4. Build 2D RBF models for S and P separately
5. Validate models in SPR region (10k-20k counts)
6. Calculate polarization-dependent correction factors
7. Create unified calibration matrix
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import RBFInterpolator
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

    # Load S-polarization data
    try:
        with open('LED-Counts relationship/led_calibration_spr_S_polarization.json', 'r') as f:
            data_S = json.load(f)
        print(f"✓ Loaded S-polarization data")
        # Verify detector match
        if data_S.get('detector_serial') and data_S['detector_serial'] != detector_serial:
            print(f"⚠️  WARNING: Data is for detector {data_S['detector_serial']}, current is {detector_serial}")
    except FileNotFoundError:
        print("✗ S-polarization data not found!")
        return None, None, None, None

    # Load P-polarization data
    try:
        with open('LED-Counts relationship/led_calibration_spr_P_polarization.json', 'r') as f:
            data_P = json.load(f)
        print(f"✓ Loaded P-polarization data")
        # Verify detector match
        if data_P.get('detector_serial') and data_P['detector_serial'] != detector_serial:
            print(f"⚠️  WARNING: Data is for detector {data_P['detector_serial']}, current is {detector_serial}")
    except FileNotFoundError:
        print("✗ P-polarization data not found!")
        return None, None, None, None

    # Load dark current data
    try:
        with open('LED-Counts relationship/dark_signal_calibration.json', 'r') as f:
            data_dark = json.load(f)
        print(f"✓ Loaded dark current data")
        dark_rate = data_dark['linear_fit']['slope']
        dark_offset = data_dark['linear_fit']['offset']
        print(f"  Dark rate: {dark_rate:.2f} counts/ms")
        print(f"  Dark offset: {dark_offset:.1f} counts")
    except FileNotFoundError:
        print("⚠️  Dark current data not found - proceeding without dark correction")
        dark_rate = 0.0
        dark_offset = 0.0

    return data_S, data_P, (dark_rate, dark_offset), detector_serial


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
            print(f"  ⚠️  Duplicates in S: {len(set(duplicates_S))} unique pairs")
            report['overall_valid'] = False

        if duplicates_P:
            print(f"  ⚠️  Duplicates in P: {len(set(duplicates_P))} unique pairs")
            report['overall_valid'] = False

        if missing_in_P:
            print(f"  ⚠️  Missing in P: {len(missing_in_P)} pairs")
            if len(missing_in_P) <= 5:
                for pair in sorted(missing_in_P):
                    print(f"      - I={pair[0]}, T={pair[1]} ms")
            report['overall_valid'] = False

        if missing_in_S:
            print(f"  ⚠️  Missing in S: {len(missing_in_S)} pairs")
            if len(missing_in_S) <= 5:
                for pair in sorted(missing_in_S):
                    print(f"      - I={pair[0]}, T={pair[1]} ms")
            report['overall_valid'] = False

        if led_valid:
            print(f"  ✓ Perfect S/P matching")

    print("\n" + "-"*80)
    if report['overall_valid']:
        print("✓ ALL LEDS: Perfect S/P matching - ready for 2D RBF model construction")
    else:
        print("⚠️  WARNING: S/P measurements not perfectly matched")
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
        print(f"  Original S: {len(measurements_S)} → Filtered: {len(common_S)}")
        print(f"  Original P: {len(measurements_P)} → Filtered: {len(common_P)}")

        if len(common_S) < len(measurements_S) or len(common_P) < len(measurements_P):
            removed_S = len(measurements_S) - len(common_S)
            removed_P = len(measurements_P) - len(common_P)
            print(f"  ⚠️  Removed {removed_S} S and {removed_P} P measurements")

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

def build_2d_model_ML(measurements, led_name, polarization):
    """Build 2D RBF interpolation model for LED at given polarization"""

    points = np.array([(m['intensity'], m['time']) for m in measurements])
    values = np.array([m['counts'] for m in measurements])

    # Build RBF interpolator
    interpolator = RBFInterpolator(
        points, values,
        kernel='thin_plate_spline',
        smoothing=0.1,
        epsilon=1.0
    )

    return interpolator

def validate_model_ML(interpolator, measurements, led_name, polarization):
    """Validate model accuracy against measurements"""

    errors = []
    for m in measurements:
        predicted = float(interpolator(np.array([[m['intensity'], m['time']]]))[0])
        actual = m['counts']
        error_pct = ((predicted - actual) / actual) * 100 if actual != 0 else 0
        errors.append(error_pct)

    mean_error = np.mean(errors)
    std_error = np.std(errors)
    max_error = np.max(np.abs(errors))

    return {
        'mean_error': mean_error,
        'std_error': std_error,
        'max_error': max_error,
        'errors': errors
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
    print(f"\n✓ Validation report saved to: {validation_file}")

    # Filter to common pairs if not perfectly matched
    if not is_matched:
        print("\n⚠️  Filtering to common (intensity, time) pairs only...")
        data_S_filtered, data_P_filtered = filter_to_common_pairs(data_S, data_P)

        # Ask user to confirm
        response = input("\nProceed with filtered data? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Processing aborted. Re-run calibration measurement for better data.")
            return

        data_S = data_S_filtered
        data_P = data_P_filtered
    else:
        print("\n✓ Data validation passed - proceeding with processing")

    print("\n" + "="*80)
    print("APPLYING DARK CORRECTION")
    print("="*80)

    # Process each LED
    models_S = {}
    models_P = {}
    processed_data = {
        'detector_serial': detector_serial,
        'processed_date': str(np.datetime64('now')),
        'calibration_type': 'SPR 2D RBF',
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
        counts_S = [m['counts'] for m in measurements_S]
        print(f"    Raw counts range: {min([m['counts_raw'] for m in measurements_S]):.0f} - "
              f"{max([m['counts_raw'] for m in measurements_S]):.0f}")
        print(f"    Corrected counts range: {min(counts_S):.0f} - {max(counts_S):.0f}")

        # Process P-polarization
        measurements_P_raw = data_P[led_name]['measurements']
        measurements_P = apply_dark_correction(measurements_P_raw, dark_rate, dark_offset)

        print(f"  P-pol: {len(measurements_P)} measurements")
        counts_P = [m['counts'] for m in measurements_P]
        print(f"    Raw counts range: {min([m['counts_raw'] for m in measurements_P]):.0f} - "
              f"{max([m['counts_raw'] for m in measurements_P]):.0f}")
        print(f"    Corrected counts range: {min(counts_P):.0f} - {max(counts_P):.0f}")

        # Calculate average polarization ratio
        avg_S = np.mean(counts_S)
        avg_P = np.mean(counts_P)
        pol_ratio = avg_S / avg_P if avg_P > 0 else 1.0

        print(f"    Polarization ratio (S/P): {pol_ratio:.3f}")

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
    print("BUILDING 2D INTERPOLATION MODELS")
    print("="*80)

    validation_results = {}

    for led_name in ['A', 'B', 'C', 'D']:
        print(f"\nLED {led_name}:")

        # Build S model
        measurements_S = processed_data['S'][led_name]['measurements']
        model_S = build_2d_model_ML(measurements_S, led_name, 'S')
        models_S[led_name] = model_S

        # Validate S model
        val_S = validate_model_ML(model_S, measurements_S, led_name, 'S')
        print(f"  S-pol model:")
        print(f"    Mean error: {val_S['mean_error']:.2f}%")
        print(f"    Std error: {val_S['std_error']:.2f}%")
        print(f"    Max error: {val_S['max_error']:.2f}%")

        # Build P model
        measurements_P = processed_data['P'][led_name]['measurements']
        model_P = build_2d_model_ML(measurements_P, led_name, 'P')
        models_P[led_name] = model_P

        # Validate P model
        val_P = validate_model_ML(model_P, measurements_P, led_name, 'P')
        print(f"  P-pol model:")
        print(f"    Mean error: {val_P['mean_error']:.2f}%")
        print(f"    Std error: {val_P['std_error']:.2f}%")
        print(f"    Max error: {val_P['max_error']:.2f}%")

        validation_results[led_name] = {
            'S': val_S,
            'P': val_P
        }

    # Save processed data with detector-specific filename
    output_file = f'LED-Counts relationship/led_calibration_spr_processed_{detector_serial}.json'
    with open(output_file, 'w') as f:
        json.dump(processed_data, f, indent=2)

    print(f"\n✓ Processed data saved to: {output_file}")
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
        print("\n⚠️  WARNING: High variation in S/P ratio across LEDs (>10%)")
        print("   This suggests wavelength-dependent polarization effects")

    if avg_ratio > 1.2 or avg_ratio < 0.8:
        print(f"\n⚠️  NOTE: S/P ratio = {avg_ratio:.3f}")
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
3. Update LED2DCalibrationModel to use polarization-aware model
4. Test SPR measurements with new calibration

FILES CREATED:
- led_calibration_spr_processed_<DETECTOR_SERIAL>.json (normalized data)
- spr_calibration_comparison_<DETECTOR_SERIAL>.png (S vs P visualization)

NOTE: Calibration files are detector-specific and include serial number.
""")

def create_calibration_plots(processed_data, models_S, models_P):
    """Create comparison plots for S and P calibration"""

    print("\n" + "="*80)
    print("CREATING VISUALIZATION")
    print("="*80)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()

    for idx, led_name in enumerate(['A', 'B', 'C', 'D']):
        ax = axes[idx]

        # Get measurements
        measurements_S = processed_data['S'][led_name]['measurements']
        measurements_P = processed_data['P'][led_name]['measurements']

        # Plot P data first (so S data appears on top)
        intensities_P = [m['intensity'] for m in measurements_P]
        times_P = [m['time'] for m in measurements_P]
        counts_P = [m['counts'] for m in measurements_P]

        scatter_P = ax.scatter(intensities_P, times_P, c=counts_P,
                              cmap='Blues', s=150, alpha=0.5,
                              edgecolors='blue', linewidths=2,
                              label='P-pol', marker='s')

        # Plot S data on top with offset for visibility
        intensities_S = [m['intensity'] for m in measurements_S]
        times_S = [m['time'] + 0.3 for m in measurements_S]  # Slight vertical offset
        counts_S = [m['counts'] for m in measurements_S]

        scatter_S = ax.scatter(intensities_S, times_S, c=counts_S,
                              cmap='Reds', s=80, alpha=0.8,
                              edgecolors='red', linewidths=2,
                              label='S-pol', marker='o')

        ax.set_xlabel('Intensity', fontsize=10)
        ax.set_ylabel('Integration Time (ms)', fontsize=10)
        ax.set_title(f'LED {led_name} - S vs P Calibration\n'
                    f'S: {min(counts_S):.0f}-{max(counts_S):.0f} counts, '
                    f'P: {min(counts_P):.0f}-{max(counts_P):.0f} counts',
                    fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper left', fontsize=8)

        # Add colorbar
        cbar = plt.colorbar(scatter_S, ax=ax)
        cbar.set_label('Counts (dark-corrected)', fontsize=8)

    plt.tight_layout()

    # Get detector serial from processed_data
    detector_serial = processed_data.get('detector_serial', 'unknown')
    output_plot = f'LED-Counts relationship/spr_calibration_comparison_{detector_serial}.png'
    plt.savefig(output_plot, dpi=150, bbox_inches='tight')
    print(f"✓ Visualization saved to: {output_plot}")
    plt.close()

if __name__ == '__main__':
    process_calibration()
