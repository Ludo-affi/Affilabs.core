"""
Test 2D RBF Model - Validation Using Existing Calibration Data
===============================================================

Tests the 2D RBF interpolation models by:
1. Loading the calibration models
2. Using the calibration data points as ground truth
3. Testing interpolation at intermediate points
4. Showing model accuracy and error statistics
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import RBFInterpolator
from pathlib import Path

def load_processed_calibration():
    """Load processed calibration data with RBF models"""
    
    print("="*80)
    print("LOADING PROCESSED CALIBRATION DATA")
    print("="*80)
    
    # Load processed data
    calib_file = Path('LED-Counts relationship/led_calibration_spr_processed_FLMT09116.json')
    
    if not calib_file.exists():
        print(f"✗ Calibration file not found: {calib_file}")
        return None
    
    with open(calib_file, 'r') as f:
        data = json.load(f)
    
    detector = data['detector_serial']
    calib_date = data['processed_date']
    dark_rate = data['dark']['rate']
    dark_offset = data['dark']['offset']
    
    print(f"✓ Loaded calibration data")
    print(f"  Detector: {detector}")
    print(f"  Date: {calib_date}")
    print(f"  Dark correction: {dark_rate:.2f} counts/ms + {dark_offset:.1f} offset\n")
    
    return data

def build_rbf_model(measurements, led_name, polarization):
    """Build 2D RBF interpolation model"""
    
    points = np.array([(m['intensity'], m['time']) for m in measurements])
    values = np.array([m['counts'] for m in measurements])
    
    # Build RBF interpolator (same parameters as process_spr_calibration.py)
    interpolator = RBFInterpolator(
        points, values,
        kernel='thin_plate_spline',
        smoothing=0.1,
        epsilon=1.0
    )
    
    return interpolator, points, values

def test_model_at_training_points(interpolator, measurements, led_name, polarization):
    """Test model accuracy at training points"""
    
    errors = []
    results = []
    
    for m in measurements:
        predicted = float(interpolator(np.array([[m['intensity'], m['time']]]))[0])
        actual = m['counts']
        error_pct = ((predicted - actual) / actual) * 100 if actual != 0 else 0
        
        errors.append(error_pct)
        results.append({
            'intensity': m['intensity'],
            'time': m['time'],
            'actual': actual,
            'predicted': predicted,
            'error_pct': error_pct
        })
    
    mean_error = np.mean(np.abs(errors))
    std_error = np.std(errors)
    max_error = np.max(np.abs(errors))
    
    return {
        'mean_error': mean_error,
        'std_error': std_error,
        'max_error': max_error,
        'results': results
    }

def test_model_at_interpolation_points(interpolator, points_range):
    """Test model at interpolated points (not in training set)"""
    
    # Generate grid of test points
    intensity_range = np.linspace(points_range['intensity_min'], 
                                 points_range['intensity_max'], 5)
    time_range = np.linspace(points_range['time_min'], 
                            points_range['time_max'], 5)
    
    test_points = []
    for i in intensity_range:
        for t in time_range:
            test_points.append([i, t])
    
    test_points = np.array(test_points)
    
    # Predict at test points
    predictions = interpolator(test_points)
    
    return test_points, predictions

def visualize_2d_rbf(data, led_name):
    """Create visualization of 2D RBF interpolation"""
    
    print(f"\n{'='*80}")
    print(f"VISUALIZING 2D RBF INTERPOLATION - LED {led_name}")
    print('='*80)
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    for idx, pol in enumerate(['S', 'P']):
        ax = axes[idx]
        
        measurements = data[pol][led_name]['measurements']
        
        # Build model
        interpolator, points, values = build_rbf_model(measurements, led_name, pol)
        
        # Get range
        intensities = points[:, 0]
        times = points[:, 1]
        
        # Create interpolation grid
        intensity_grid = np.linspace(intensities.min(), intensities.max(), 50)
        time_grid = np.linspace(times.min(), times.max(), 50)
        
        I_mesh, T_mesh = np.meshgrid(intensity_grid, time_grid)
        grid_points = np.c_[I_mesh.ravel(), T_mesh.ravel()]
        
        # Predict on grid
        counts_pred = interpolator(grid_points).reshape(I_mesh.shape)
        
        # Plot interpolated surface
        contour = ax.contourf(I_mesh, T_mesh, counts_pred, levels=20, cmap='viridis', alpha=0.7)
        
        # Overlay training points
        scatter = ax.scatter(intensities, times, c=values, s=100, 
                           edgecolors='red', linewidths=2, cmap='viridis',
                           marker='o', label='Training points')
        
        ax.set_xlabel('Intensity', fontsize=12)
        ax.set_ylabel('Integration Time (ms)', fontsize=12)
        ax.set_title(f'LED {led_name} - {pol}-Polarization\n2D RBF Interpolation', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Add colorbar
        cbar = plt.colorbar(contour, ax=ax)
        cbar.set_label('Counts (dark-corrected)', fontsize=10)
    
    plt.tight_layout()
    
    output_file = f'LED-Counts relationship/2d_rbf_visualization_{led_name}_FLMT09116.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✓ Visualization saved: {output_file}")
    plt.close()

def main():
    """Main test function"""
    
    print("="*80)
    print("2D RBF MODEL VALIDATION TEST")
    print("="*80)
    print("\nThis test validates the 2D RBF interpolation models")
    print("built from your SPR calibration data.\n")
    
    # Load calibration data
    data = load_processed_calibration()
    if data is None:
        return
    
    # Test each LED
    print("="*80)
    print("TESTING MODEL ACCURACY AT TRAINING POINTS")
    print("="*80)
    
    print(f"\n{'LED':<6} {'Pol':<6} {'Points':<8} {'Mean Error':<12} {'Std Error':<12} {'Max Error':<12}")
    print("-"*80)
    
    all_results = {}
    
    for led_name in ['A', 'B', 'C', 'D']:
        all_results[led_name] = {}
        
        for pol in ['S', 'P']:
            measurements = data[pol][led_name]['measurements']
            
            # Build model
            interpolator, points, values = build_rbf_model(measurements, led_name, pol)
            
            # Test at training points
            validation = test_model_at_training_points(interpolator, measurements, led_name, pol)
            
            all_results[led_name][pol] = {
                'interpolator': interpolator,
                'validation': validation,
                'measurements': measurements
            }
            
            print(f"{led_name:<6} {pol:<6} {len(measurements):<8} "
                  f"{validation['mean_error']:<12.3f}% "
                  f"{validation['std_error']:<12.3f}% "
                  f"{validation['max_error']:<12.3f}%")
    
    print("\n" + "="*80)
    print("DETAILED ERROR ANALYSIS")
    print("="*80)
    
    # Show detailed errors for one LED as example
    led_example = 'A'
    pol_example = 'S'
    
    print(f"\nExample: LED {led_example}, {pol_example}-Polarization")
    print(f"\n{'Intensity':<12} {'Time (ms)':<12} {'Actual':<12} {'Predicted':<12} {'Error %':<12}")
    print("-"*80)
    
    results = all_results[led_example][pol_example]['validation']['results'][:10]  # Show first 10
    for r in results:
        print(f"{r['intensity']:<12} {r['time']:<12.1f} {r['actual']:<12.0f} "
              f"{r['predicted']:<12.0f} {r['error_pct']:<12.2f}%")
    
    print(f"\n... ({len(all_results[led_example][pol_example]['validation']['results']) - 10} more points)")
    
    # Create visualizations
    print("\n" + "="*80)
    print("CREATING 2D RBF VISUALIZATIONS")
    print("="*80)
    
    for led_name in ['A', 'B', 'C', 'D']:
        visualize_2d_rbf(data, led_name)
    
    # Summary statistics
    print("\n" + "="*80)
    print("OVERALL MODEL PERFORMANCE")
    print("="*80)
    
    all_mean_errors = []
    all_max_errors = []
    
    for led_name in ['A', 'B', 'C', 'D']:
        for pol in ['S', 'P']:
            val = all_results[led_name][pol]['validation']
            all_mean_errors.append(val['mean_error'])
            all_max_errors.append(val['max_error'])
    
    print(f"\nAcross all LEDs and polarizations:")
    print(f"  Average mean error: {np.mean(all_mean_errors):.3f}%")
    print(f"  Average max error: {np.mean(all_max_errors):.3f}%")
    print(f"  Best mean error: {np.min(all_mean_errors):.3f}%")
    print(f"  Worst mean error: {np.max(all_mean_errors):.3f}%")
    
    if np.mean(all_mean_errors) < 5.0:
        print(f"\n✓ EXCELLENT: Models achieve <5% mean error")
        print("  → Ready for production SPR measurements")
    elif np.mean(all_mean_errors) < 10.0:
        print(f"\n✓ GOOD: Models achieve <10% mean error")
        print("  → Acceptable for SPR measurements")
    else:
        print(f"\n⚠ WARNING: Mean error >10%")
        print("  → Consider re-calibration for better accuracy")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("\nFiles created:")
    print("  - 2d_rbf_visualization_A_FLMT09116.png")
    print("  - 2d_rbf_visualization_B_FLMT09116.png")
    print("  - 2d_rbf_visualization_C_FLMT09116.png")
    print("  - 2d_rbf_visualization_D_FLMT09116.png")

if __name__ == '__main__':
    main()
