"""
2D Calibration Matrix Refinement
==================================
Densely sample the (intensity, time) space around 80% detector saturation target.

Strategy:
1. Use existing 5-point data as baseline
2. Add targeted measurements around 80% target (52,428 counts)
3. Build 2D interpolation surface: counts = f(intensity, time)
4. Focus sampling density near the operating region

Sampling Plan:
- Integration times: 25ms, 30ms, 35ms, 40ms, 45ms (around target range)
- Intensities: Strategic values based on initial predictions
- ~5 measurements per LED per point for statistics
"""

import sys
import time
import logging
import numpy as np
import json
import os
from pathlib import Path
from scipy.interpolate import RBFInterpolator, LinearNDInterpolator
from scipy.optimize import minimize_scalar

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import hardware interfaces
from src.utils.controller import PicoP4SPR
from src.utils.usb4000_wrapper import USB4000
from src.hardware.controller_adapter import wrap_existing_controller
from src.hardware.spectrometer_adapter import wrap_existing_spectrometer

# Load existing calibration
CALIBRATION_FILE = Path("led_calibration_matrix_5point.json")


def load_existing_calibration():
    """Load the 5-point calibration data"""
    with open(CALIBRATION_FILE, 'r') as f:
        return json.load(f)


def calculate_sampling_points(led_calib, target_counts=52428):
    """
    Calculate strategic sampling points around the target.
    
    Returns list of (intensity, time) tuples to measure.
    """
    # Use linear model as starting estimate
    intensity_fit = led_calib['characterization']['intensity_fit']
    slope = intensity_fit['slope']
    intercept = intensity_fit['intercept']
    
    # Target integration times (around 35ms based on initial analysis)
    target_times = [25, 30, 35, 40, 45]
    
    sampling_points = []
    
    for time_ms in target_times:
        # Calculate intensity needed for target using linear model
        # counts = (T/10) * (slope * I + intercept)
        # I = (counts / (T/10) - intercept) / slope
        time_scale = time_ms / 10.0
        predicted_intensity = (target_counts / time_scale - intercept) / slope
        
        # Clamp to valid range
        predicted_intensity = max(40, min(255, predicted_intensity))
        
        # Sample at predicted intensity ±20% and ±40%
        intensities = [
            max(40, int(predicted_intensity * 0.6)),
            max(40, int(predicted_intensity * 0.8)),
            int(predicted_intensity),
            min(255, int(predicted_intensity * 1.2)),
            min(255, int(predicted_intensity * 1.4))
        ]
        
        # Remove duplicates and out of range
        intensities = sorted(list(set([i for i in intensities if 40 <= i <= 255])))
        
        for intensity in intensities:
            sampling_points.append((intensity, time_ms))
    
    return sampling_points


def measure_point(controller, spec_interface, channel, intensity, time_ms, num_measurements=5):
    """
    Measure LED at specific (intensity, time) point.
    Returns mean peak counts and statistics.
    """
    # Turn off all LEDs
    controller.turn_off_channels()
    time.sleep(0.05)
    
    # Enable target LED
    controller.turn_on_channel(channel)
    controller.set_intensity(channel, intensity)
    
    # Set integration time
    spec_interface.set_integration_time(time_ms)
    time.sleep(0.1)
    
    # Take measurements
    measurements = []
    for i in range(num_measurements):
        spectrum = spec_interface.read_spectrum()
        if spectrum is None or len(spectrum) == 0:
            logger.warning(f"  [{i+1}/{num_measurements}] No spectrum data")
            continue
        
        peak = float(np.max(spectrum))
        measurements.append(peak)
        time.sleep(0.05)
    
    # Turn off LED
    controller.turn_off_channels()
    
    # Calculate statistics
    if len(measurements) >= 3:
        mean_counts = np.mean(measurements)
        std_counts = np.std(measurements, ddof=1)
        cv_pct = (std_counts / mean_counts * 100) if mean_counts > 0 else 0
        
        return {
            'mean': mean_counts,
            'std': std_counts,
            'cv': cv_pct,
            'measurements': measurements,
            'success': True
        }
    else:
        return {'success': False}


def build_2d_model(calibration_points):
    """
    Build 2D interpolation model from calibration points.
    
    calibration_points: list of (intensity, time, counts) tuples
    """
    if len(calibration_points) < 4:
        raise ValueError("Need at least 4 points for 2D interpolation")
    
    # Separate into arrays
    points = np.array([(i, t) for i, t, c in calibration_points])
    values = np.array([c for i, t, c in calibration_points])
    
    # Build RBF interpolator (smooth, good for scattered data)
    interpolator = RBFInterpolator(
        points, 
        values,
        kernel='thin_plate_spline',
        smoothing=0.1,  # Small smoothing to handle noise
        epsilon=1.0
    )
    
    return interpolator


def predict_with_2d_model(model, intensity, time):
    """Predict counts using 2D model"""
    point = np.array([[intensity, time]])
    return float(model(point)[0])


def find_optimal_settings_2d(model, target_counts, time_fixed=None, intensity_fixed=None):
    """
    Find optimal (intensity, time) to hit target counts.
    
    If time_fixed: optimize intensity at fixed time
    If intensity_fixed: optimize time at fixed intensity
    """
    if time_fixed is not None:
        # Optimize intensity at fixed time
        def objective(intensity):
            return abs(predict_with_2d_model(model, intensity, time_fixed) - target_counts)
        
        result = minimize_scalar(objective, bounds=(40, 255), method='bounded')
        return (int(round(result.x)), time_fixed)
    
    elif intensity_fixed is not None:
        # Optimize time at fixed intensity
        def objective(time):
            return abs(predict_with_2d_model(model, intensity_fixed, time) - target_counts)
        
        result = minimize_scalar(objective, bounds=(10, 50), method='bounded')
        return (intensity_fixed, result.x)
    
    else:
        # Optimize both - find minimum time
        best_time = None
        best_intensity = None
        
        for time in range(10, 50):
            def objective(intensity):
                return abs(predict_with_2d_model(model, intensity, time) - target_counts)
            
            result = minimize_scalar(objective, bounds=(40, 255), method='bounded')
            predicted = predict_with_2d_model(model, result.x, time)
            
            if abs(predicted - target_counts) / target_counts < 0.02:  # Within 2%
                best_time = time
                best_intensity = int(round(result.x))
                break
        
        if best_time is None:
            # Fall back to 35ms
            def objective(intensity):
                return abs(predict_with_2d_model(model, intensity, 35) - target_counts)
            result = minimize_scalar(objective, bounds=(40, 255), method='bounded')
            return (int(round(result.x)), 35.0)
        
        return (best_intensity, best_time)


def run_2d_calibration_refinement(target_counts=52428):
    """
    Run 2D calibration refinement focused on 80% target region.
    """
    print("="*80)
    print("2D CALIBRATION MATRIX REFINEMENT")
    print("="*80)
    print(f"\nTarget: {target_counts} counts ({target_counts/65535*100:.1f}%)")
    print("\nStrategy: Dense sampling around 80% target region")
    print("Integration times: 25ms, 30ms, 35ms, 40ms, 45ms")
    print("Intensities: Strategic values ±40% around predicted optimal")
    
    # Load existing calibration
    print("\n" + "-"*80)
    print("Loading existing 5-point calibration...")
    print("-"*80)
    existing_calib = load_existing_calibration()
    
    # Initialize hardware
    print("\n" + "-"*80)
    print("Initializing Hardware...")
    print("-"*80)
    
    controller_hw = PicoP4SPR()
    spec_hw = USB4000()
    
    controller = wrap_existing_controller(controller_hw)
    spec_interface = wrap_existing_spectrometer(spec_hw)
    
    if not controller.connect():
        print("ERROR: Failed to connect to LED controller")
        return None
    
    if not spec_interface.connect():
        print("ERROR: Failed to connect to spectrometer")
        controller.disconnect()
        return None
    
    print(" Hardware initialized successfully")
    
    # LED configuration
    leds = {
        'A': {'channel': 'a', 'calib': existing_calib['A']},
        'B': {'channel': 'b', 'calib': existing_calib['B']},
        'C': {'channel': 'c', 'calib': existing_calib['C']},
        'D': {'channel': 'd', 'calib': existing_calib['D']}
    }
    
    refined_calibration = {}
    
    try:
        for led_name, led_info in leds.items():
            print("\n" + "="*80)
            print(f"LED {led_name} - 2D CALIBRATION REFINEMENT")
            print("="*80)
            
            channel = led_info['channel']
            led_calib = led_info['calib']
            
            # Calculate sampling points
            sampling_points = calculate_sampling_points(led_calib, target_counts)
            
            print(f"\nSampling {len(sampling_points)} (intensity, time) points:")
            for i, (intensity, time_ms) in enumerate(sampling_points[:5]):
                print(f"  {i+1}. Intensity={intensity}, Time={time_ms}ms")
            if len(sampling_points) > 5:
                print(f"  ... and {len(sampling_points)-5} more points")
            
            # Collect existing 5-point data
            all_measurements = []
            
            # Add existing intensity_data points (at 10ms)
            print("\n" + "-"*80)
            print("Including existing intensity_data (at 10ms)...")
            for intensity_str, counts in led_calib['characterization']['intensity_data'].items():
                intensity = int(intensity_str)
                all_measurements.append((intensity, 10.0, counts))
                print(f"  I={intensity}, T=10ms: {counts:.0f} counts")
            
            # Add existing time_data points (at intensity 255)
            print("\n" + "-"*80)
            print("Including existing time_data (at intensity 255)...")
            for time_str, counts in led_calib['characterization']['time_data'].items():
                time_ms = float(time_str)
                all_measurements.append((255, time_ms, counts))
                print(f"  I=255, T={time_ms}ms: {counts:.0f} counts")
            
            # Measure new refinement points
            print("\n" + "-"*80)
            print("Measuring refinement points...")
            print("-"*80)
            
            for idx, (intensity, time_ms) in enumerate(sampling_points):
                print(f"\n[{idx+1}/{len(sampling_points)}] I={intensity}, T={time_ms}ms")
                
                result = measure_point(
                    controller, spec_interface, channel,
                    intensity, time_ms, num_measurements=5
                )
                
                if result['success']:
                    counts = result['mean']
                    pct = (counts / 65535) * 100
                    all_measurements.append((intensity, time_ms, counts))
                    
                    print(f"  Mean: {counts:.0f} counts ({pct:.1f}%)")
                    print(f"  CV: {result['cv']:.2f}%")
                else:
                    print(f"  FAILED - skipping point")
            
            # Build 2D model
            print("\n" + "-"*80)
            print(f"Building 2D interpolation model from {len(all_measurements)} points...")
            print("-"*80)
            
            model_2d = build_2d_model(all_measurements)
            
            # Find optimal settings for 80% target
            print("\nFinding optimal settings for 80% target...")
            
            # Option 1: Fixed time approach (e.g., 35ms)
            fixed_time = 35.0
            optimal_intensity_35ms, _ = find_optimal_settings_2d(
                model_2d, target_counts, time_fixed=fixed_time
            )
            predicted_35ms = predict_with_2d_model(model_2d, optimal_intensity_35ms, fixed_time)
            
            print(f"\nFixed time ({fixed_time}ms):")
            print(f"  Optimal intensity: {optimal_intensity_35ms}")
            print(f"  Predicted counts: {predicted_35ms:.0f} ({predicted_35ms/65535*100:.1f}%)")
            
            # Option 2: Fixed intensity 255 approach
            optimal_time_255, _ = find_optimal_settings_2d(
                model_2d, target_counts, intensity_fixed=255
            )
            predicted_255 = predict_with_2d_model(model_2d, 255, optimal_time_255)
            
            print(f"\nFixed intensity (255):")
            print(f"  Optimal time: {optimal_time_255:.1f}ms")
            print(f"  Predicted counts: {predicted_255:.0f} ({predicted_255/65535*100:.1f}%)")
            
            # Option 3: Minimum time approach
            optimal_intensity, optimal_time = find_optimal_settings_2d(
                model_2d, target_counts
            )
            predicted_optimal = predict_with_2d_model(model_2d, optimal_intensity, optimal_time)
            
            print(f"\nMinimum time approach:")
            print(f"  Optimal: I={optimal_intensity}, T={optimal_time:.1f}ms")
            print(f"  Predicted counts: {predicted_optimal:.0f} ({predicted_optimal/65535*100:.1f}%)")
            
            # Store refined calibration
            refined_calibration[led_name] = {
                'channel': channel,
                'measurements': [
                    {'intensity': int(i), 'time': float(t), 'counts': float(c)}
                    for i, t, c in all_measurements
                ],
                'optimal_settings': {
                    'fixed_time_35ms': {
                        'intensity': optimal_intensity_35ms,
                        'time': 35.0,
                        'predicted_counts': float(predicted_35ms)
                    },
                    'fixed_intensity_255': {
                        'intensity': 255,
                        'time': float(optimal_time_255),
                        'predicted_counts': float(predicted_255)
                    },
                    'minimum_time': {
                        'intensity': optimal_intensity,
                        'time': float(optimal_time),
                        'predicted_counts': float(predicted_optimal)
                    }
                }
            }
    
    finally:
        # Cleanup
        print("\n" + "-"*80)
        print("Cleaning up...")
        controller.turn_off_channels()
        spec_interface.disconnect()
        controller.disconnect()
        print(" Hardware disconnected")
    
    # Summary
    print("\n" + "="*80)
    print("2D CALIBRATION REFINEMENT SUMMARY")
    print("="*80)
    
    print(f"\n{'LED':<6} {'Measurements':<15} {'Optimal (35ms)':<20} {'Optimal (I=255)':<20}")
    print("-"*80)
    
    for led_name, data in refined_calibration.items():
        num_measurements = len(data['measurements'])
        opt_35 = data['optimal_settings']['fixed_time_35ms']
        opt_255 = data['optimal_settings']['fixed_intensity_255']
        
        print(f"{led_name:<6} {num_measurements:<15} "
              f"I={opt_35['intensity']:<3} ({opt_35['predicted_counts']/65535*100:>5.1f}%)     "
              f"T={opt_255['time']:<5.1f}ms ({opt_255['predicted_counts']/65535*100:>5.1f}%)")
    
    return refined_calibration


if __name__ == "__main__":
    try:
        results = run_2d_calibration_refinement(target_counts=52428)
        
        if results:
            # Save results
            output_file = Path("led_calibration_2d_refined.json")
            
            # Convert to JSON-serializable format
            json_results = {}
            for led_name, data in results.items():
                json_results[led_name] = {
                    'channel': data['channel'],
                    'measurements': data['measurements'],
                    'optimal_settings': data['optimal_settings']
                }
            
            with open(output_file, 'w') as f:
                json.dump(json_results, f, indent=2)
            
            print(f"\n Results saved to: {output_file}")
            print("\n✓ 2D calibration refinement complete!")
            
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
