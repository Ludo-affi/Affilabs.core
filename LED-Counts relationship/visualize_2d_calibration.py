"""
Visualize 2D Calibration Surface
=================================
Plot the intensity × time → counts relationship to visualize:
1. Existing 5-point data
2. New refinement measurements
3. 2D interpolation surface
4. 80% target contour line
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.interpolate import RBFInterpolator
from pathlib import Path


def load_2d_calibration(filename="led_calibration_2d_refined.json"):
    """Load 2D refined calibration data"""
    with open(filename, 'r') as f:
        return json.load(f)


def plot_2d_surface(led_name, measurements, target_counts=52428):
    """
    Create 3D surface plot showing intensity × time → counts relationship
    """
    # Extract data
    intensities = [m['intensity'] for m in measurements]
    times = [m['time'] for m in measurements]
    counts = [m['counts'] for m in measurements]
    
    # Build 2D model
    points = np.array(list(zip(intensities, times)))
    values = np.array(counts)
    
    interpolator = RBFInterpolator(
        points, 
        values,
        kernel='thin_plate_spline',
        smoothing=0.1,
        epsilon=1.0
    )
    
    # Create grid for surface
    intensity_grid = np.linspace(40, 255, 50)
    time_grid = np.linspace(7, 50, 50)
    I_mesh, T_mesh = np.meshgrid(intensity_grid, time_grid)
    
    # Predict counts on grid
    grid_points = np.column_stack([I_mesh.ravel(), T_mesh.ravel()])
    C_mesh = interpolator(grid_points).reshape(I_mesh.shape)
    
    # Create figure with subplots
    fig = plt.figure(figsize=(16, 10))
    
    # 3D Surface plot
    ax1 = fig.add_subplot(221, projection='3d')
    surf = ax1.plot_surface(I_mesh, T_mesh, C_mesh, cmap='viridis', alpha=0.7, 
                            edgecolor='none')
    ax1.scatter(intensities, times, counts, c='red', s=50, marker='o', 
                label='Measurements')
    
    # Add target plane
    target_plane = np.ones_like(C_mesh) * target_counts
    ax1.plot_surface(I_mesh, T_mesh, target_plane, alpha=0.2, color='orange')
    
    ax1.set_xlabel('Intensity')
    ax1.set_ylabel('Integration Time (ms)')
    ax1.set_zlabel('Counts')
    ax1.set_title(f'LED {led_name} - 3D Calibration Surface')
    fig.colorbar(surf, ax=ax1, shrink=0.5)
    
    # Contour plot at 80% target
    ax2 = fig.add_subplot(222)
    contour = ax2.contour(I_mesh, T_mesh, C_mesh, levels=20, cmap='viridis')
    ax2.clabel(contour, inline=True, fontsize=8)
    
    # Highlight 80% target contour
    target_contour = ax2.contour(I_mesh, T_mesh, C_mesh, levels=[target_counts], 
                                  colors='red', linewidths=3)
    ax2.clabel(target_contour, inline=True, fmt='80%%', fontsize=10)
    
    ax2.scatter(intensities, times, c='red', s=50, marker='o', 
                label='Measurements', zorder=5)
    ax2.set_xlabel('Intensity')
    ax2.set_ylabel('Integration Time (ms)')
    ax2.set_title(f'LED {led_name} - Contour Map (Red = 80% Target)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Time slices at different intensities
    ax3 = fig.add_subplot(223)
    for intensity in [100, 150, 200, 255]:
        slice_points = np.column_stack([np.ones(50)*intensity, time_grid])
        slice_counts = interpolator(slice_points)
        ax3.plot(time_grid, slice_counts, label=f'I={intensity}', linewidth=2)
    
    ax3.axhline(y=target_counts, color='red', linestyle='--', linewidth=2, 
                label='80% Target')
    ax3.set_xlabel('Integration Time (ms)')
    ax3.set_ylabel('Counts')
    ax3.set_title(f'LED {led_name} - Time Response at Different Intensities')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # Intensity slices at different times
    ax4 = fig.add_subplot(224)
    for time_ms in [15, 25, 35, 45]:
        slice_points = np.column_stack([intensity_grid, np.ones(50)*time_ms])
        slice_counts = interpolator(slice_points)
        ax4.plot(intensity_grid, slice_counts, label=f'T={time_ms}ms', linewidth=2)
    
    ax4.axhline(y=target_counts, color='red', linestyle='--', linewidth=2,
                label='80% Target')
    ax4.set_xlabel('Intensity')
    ax4.set_ylabel('Counts')
    ax4.set_title(f'LED {led_name} - Intensity Response at Different Times')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def analyze_nonlinearity(led_name, measurements):
    """
    Analyze the non-linearity in the time response
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'LED {led_name} - Non-linearity Analysis', fontsize=14, fontweight='bold')
    
    # Group by intensity
    intensity_groups = {}
    for m in measurements:
        intensity = m['intensity']
        if intensity not in intensity_groups:
            intensity_groups[intensity] = []
        intensity_groups[intensity].append((m['time'], m['counts']))
    
    # Plot 1: Counts vs Time for different intensities
    ax1 = axes[0, 0]
    for intensity in sorted(intensity_groups.keys()):
        points = sorted(intensity_groups[intensity])
        times = [p[0] for p in points]
        counts = [p[1] for p in points]
        if len(times) > 1:
            ax1.plot(times, counts, 'o-', label=f'I={intensity}', linewidth=2)
    
    ax1.set_xlabel('Integration Time (ms)')
    ax1.set_ylabel('Counts')
    ax1.set_title('Counts vs Time (Different Intensities)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Counts/ms vs Time (shows degradation)
    ax2 = axes[0, 1]
    for intensity in sorted(intensity_groups.keys()):
        points = sorted(intensity_groups[intensity])
        times = [p[0] for p in points]
        counts = [p[1] for p in points]
        if len(times) > 1:
            rates = [c/t for t, c in zip(times, counts)]
            ax2.plot(times, rates, 'o-', label=f'I={intensity}', linewidth=2)
    
    ax2.set_xlabel('Integration Time (ms)')
    ax2.set_ylabel('Counts / ms')
    ax2.set_title('Response Rate vs Time (Shows Non-linearity)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Group by time
    time_groups = {}
    for m in measurements:
        time_ms = m['time']
        if time_ms not in time_groups:
            time_groups[time_ms] = []
        time_groups[time_ms].append((m['intensity'], m['counts']))
    
    ax3 = axes[1, 0]
    for time_ms in sorted(time_groups.keys()):
        points = sorted(time_groups[time_ms])
        intensities = [p[0] for p in points]
        counts = [p[1] for p in points]
        if len(intensities) > 1:
            ax3.plot(intensities, counts, 'o-', label=f'T={time_ms}ms', linewidth=2)
    
    ax3.set_xlabel('Intensity')
    ax3.set_ylabel('Counts')
    ax3.set_title('Counts vs Intensity (Different Times)')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # Plot 4: Residuals from linear model
    ax4 = axes[1, 1]
    
    # Calculate linear prediction (simple time scaling)
    # Find baseline at 10ms
    baseline_10ms = [m for m in measurements if abs(m['time'] - 10.0) < 0.5]
    
    if baseline_10ms:
        residuals_time = []
        residuals_counts = []
        
        for m in measurements:
            # Find closest baseline intensity
            closest_baseline = min(baseline_10ms, 
                                   key=lambda x: abs(x['intensity'] - m['intensity']))
            
            # Linear prediction
            predicted = closest_baseline['counts'] * (m['time'] / 10.0)
            residual = ((m['counts'] - predicted) / predicted) * 100
            
            residuals_time.append(m['time'])
            residuals_counts.append(residual)
        
        scatter = ax4.scatter(residuals_time, residuals_counts, 
                              c=[m['intensity'] for m in measurements],
                              cmap='viridis', s=50, alpha=0.7)
        ax4.axhline(y=0, color='red', linestyle='--', linewidth=2)
        ax4.set_xlabel('Integration Time (ms)')
        ax4.set_ylabel('Residual Error (%)')
        ax4.set_title('Linear Model Residuals (Color = Intensity)')
        plt.colorbar(scatter, ax=ax4, label='Intensity')
        ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


if __name__ == "__main__":
    import sys
    
    # Check if calibration file exists
    calib_file = Path("led_calibration_2d_refined.json")
    
    if not calib_file.exists():
        print("ERROR: led_calibration_2d_refined.json not found")
        print("Run test_2d_calibration_refinement.py first")
        sys.exit(1)
    
    # Load data
    print("Loading 2D calibration data...")
    calib_data = load_2d_calibration()
    
    print(f"Found data for LEDs: {', '.join(calib_data.keys())}")
    
    # Plot each LED
    for led_name, led_data in calib_data.items():
        print(f"\nPlotting LED {led_name}...")
        
        measurements = led_data['measurements']
        print(f"  {len(measurements)} measurement points")
        
        # Create surface plot
        fig1 = plot_2d_surface(led_name, measurements)
        fig1.savefig(f'led_{led_name}_2d_surface.png', dpi=150, bbox_inches='tight')
        print(f"  Saved: led_{led_name}_2d_surface.png")
        
        # Create non-linearity analysis
        fig2 = analyze_nonlinearity(led_name, measurements)
        fig2.savefig(f'led_{led_name}_nonlinearity.png', dpi=150, bbox_inches='tight')
        print(f"  Saved: led_{led_name}_nonlinearity.png")
        
        plt.close('all')
    
    print("\n✓ Visualization complete!")
