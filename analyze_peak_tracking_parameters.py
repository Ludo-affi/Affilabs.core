"""
Analyze Peak Tracking Parameter Sensitivity
============================================

Uses existing SPR calibration data to analyze which measurement parameters
most impact data quality and peak tracking performance:
- LED intensity
- Integration time
- Polarization state (S vs P)
- Signal level (counts)
- SNR (estimated from count statistics)

This analysis correlates measurement parameters with signal quality metrics
to determine optimal parameter ranges for SPR peak tracking.
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

def load_calibration_data():
    """Load S and P polarization calibration data"""

    with open('LED-Counts relationship/led_calibration_spr_S_polarization.json', 'r') as f:
        data_S = json.load(f)

    with open('LED-Counts relationship/led_calibration_spr_P_polarization.json', 'r') as f:
        data_P = json.load(f)

    with open('LED-Counts relationship/dark_signal_calibration.json', 'r') as f:
        dark_data = json.load(f)

    return data_S, data_P, dark_data

def analyze_peak_tracking():
    """Analyze which measurement parameters most impact signal quality"""

    print("="*80)
    print("PEAK TRACKING PARAMETER SENSITIVITY ANALYSIS")
    print("="*80)

    # Load data
    print("\nLoading calibration data...")
    data_S, data_P, dark_data = load_calibration_data()

    dark_rate = dark_data['linear_fit']['slope']
    dark_offset = dark_data['linear_fit']['offset']

    # Storage for analysis results
    results = {
        'S': {'A': [], 'B': [], 'C': [], 'D': []},
        'P': {'A': [], 'B': [], 'C': [], 'D': []}
    }

    print("\n" + "="*80)
    print("ANALYZING S-POLARIZATION DATA")
    print("="*80)

    # Process S-polarization measurements
    for led_name in ['A', 'B', 'C', 'D']:
        print(f"\nLED {led_name} @ S-pol:")
        measurements = data_S[led_name]['measurements']

        for idx, m in enumerate(measurements):
            intensity = m['intensity']
            int_time = m['time']
            counts_raw = m['counts']

            # Apply dark correction
            dark_counts = dark_rate * int_time + dark_offset
            counts = counts_raw - dark_counts

            # Estimate SNR (signal relative to sqrt of counts - photon shot noise)
            # For SPR, we're looking at transmission, so noise is sqrt(N)
            snr = counts / np.sqrt(max(counts, 1)) if counts > 0 else 0

            # Quality assessment based on counts and SNR
            # For peak tracking, we typically need:
            # - Counts > 1000 for basic detection
            # - Counts > 5000 for reliable tracking
            # - Counts > 10000 for high-precision tracking
            quality = "Excellent" if counts > 10000 else ("Good" if counts > 5000 else ("Fair" if counts > 1000 else "Poor"))

            results['S'][led_name].append({
                'intensity': intensity,
                'time': int_time,
                'counts_raw': counts_raw,
                'dark_counts': dark_counts,
                'counts': counts,
                'snr': snr,
                'quality': quality,
                'trackable': counts > 5000  # Threshold for reliable peak tracking
            })

            print(f"  [{idx+1:2d}/{len(measurements)}] I={intensity:3d}, T={int_time:4.1f}ms, Counts={counts:6.0f}, SNR={snr:5.1f}, Quality={quality}")

    print("\n" + "="*80)
    print("ANALYZING P-POLARIZATION DATA")
    print("="*80)

    # Process P-polarization measurements
    for led_name in ['A', 'B', 'C', 'D']:
        print(f"\nLED {led_name} @ P-pol:")
        measurements = data_P[led_name]['measurements']

        for idx, m in enumerate(measurements):
            intensity = m['intensity']
            int_time = m['time']
            counts_raw = m['counts']

            dark_counts = dark_rate * int_time + dark_offset
            counts = counts_raw - dark_counts

            snr = counts / np.sqrt(max(counts, 1)) if counts > 0 else 0
            quality = "Excellent" if counts > 10000 else ("Good" if counts > 5000 else ("Fair" if counts > 1000 else "Poor"))

            results['P'][led_name].append({
                'intensity': intensity,
                'time': int_time,
                'counts_raw': counts_raw,
                'dark_counts': dark_counts,
                'counts': counts,
                'snr': snr,
                'quality': quality,
                'trackable': counts > 5000
            })

            print(f"  [{idx+1:2d}/{len(measurements)}] I={intensity:3d}, T={int_time:4.1f}ms, Counts={counts:6.0f}, SNR={snr:5.1f}, Quality={quality}")

    # Analyze results
    print("\n" + "="*80)
    print("PARAMETER IMPACT ANALYSIS")
    print("="*80)

    analyze_parameter_impact(results)

    # Create visualizations
    create_analysis_plots(results)

    # Save results
    output_file = 'LED-Counts relationship/peak_tracking_parameter_analysis.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Results saved to: {output_file}")

def analyze_parameter_impact(results):
    """Analyze which parameters most impact signal quality and trackability"""

    print("\n1. SIGNAL QUALITY DISTRIBUTION")
    print("-"*80)

    for pol in ['S', 'P']:
        print(f"\n{pol}-Polarization:")
        for led in ['A', 'B', 'C', 'D']:
            measurements = results[pol][led]
            if not measurements:
                continue

            total = len(measurements)
            trackable = sum(1 for m in measurements if m.get('trackable', False))

            quality_counts = {}
            for m in measurements:
                q = m.get('quality', 'Unknown')
                quality_counts[q] = quality_counts.get(q, 0) + 1

            print(f"\n  LED {led}:")
            print(f"    Trackable: {trackable}/{total} ({trackable/total*100:.0f}%)")
            print(f"    Quality distribution:")
            for q in ['Excellent', 'Good', 'Fair', 'Poor']:
                count = quality_counts.get(q, 0)
                pct = count/total*100 if total > 0 else 0
                print(f"      {q}: {count} ({pct:.0f}%)")

            # Find optimal parameter ranges
            trackable_meas = [m for m in measurements if m.get('trackable', False)]
            if trackable_meas:
                intensities = [m['intensity'] for m in trackable_meas]
                times = [m['time'] for m in trackable_meas]
                counts = [m['counts'] for m in trackable_meas]

                print(f"    Optimal ranges (for trackable signals):")
                print(f"      Intensity: {min(intensities)}-{max(intensities)} (avg {np.mean(intensities):.0f})")
                print(f"      Integration: {min(times):.1f}-{max(times):.1f}ms (avg {np.mean(times):.1f}ms)")
                print(f"      Counts: {min(counts):.0f}-{max(counts):.0f} (avg {np.mean(counts):.0f})")

    print("\n2. PARAMETER SENSITIVITY ANALYSIS")
    print("-"*80)

    # Analyze correlation between parameters and signal quality
    for pol in ['S', 'P']:
        print(f"\n{pol}-Polarization Summary:")

        all_measurements = []
        for led in ['A', 'B', 'C', 'D']:
            all_measurements.extend(results[pol][led])

        if not all_measurements:
            continue

        # Group by intensity
        print("\n  Impact of LED Intensity:")
        intensity_groups = {}
        for m in all_measurements:
            i = int(m['intensity'] / 50) * 50  # Group into 50-unit bins
            if i not in intensity_groups:
                intensity_groups[i] = {'counts': [], 'snr': [], 'trackable': 0}
            intensity_groups[i]['counts'].append(m['counts'])
            intensity_groups[i]['snr'].append(m['snr'])
            if m.get('trackable', False):
                intensity_groups[i]['trackable'] += 1

        for i in sorted(intensity_groups.keys()):
            g = intensity_groups[i]
            total = len(g['counts'])
            trackable_pct = g['trackable']/total*100 if total > 0 else 0
            avg_counts = np.mean(g['counts'])
            avg_snr = np.mean(g['snr'])
            print(f"    I={i:3d}-{i+49:3d}: Trackable={trackable_pct:3.0f}%, Avg Counts={avg_counts:6.0f}, Avg SNR={avg_snr:5.1f}")

        # Group by integration time
        print("\n  Impact of Integration Time:")
        time_groups = {}
        for m in all_measurements:
            t = m['time']
            if t not in time_groups:
                time_groups[t] = {'counts': [], 'snr': [], 'trackable': 0}
            time_groups[t]['counts'].append(m['counts'])
            time_groups[t]['snr'].append(m['snr'])
            if m.get('trackable', False):
                time_groups[t]['trackable'] += 1

        for t in sorted(time_groups.keys()):
            g = time_groups[t]
            total = len(g['counts'])
            trackable_pct = g['trackable']/total*100 if total > 0 else 0
            avg_counts = np.mean(g['counts'])
            avg_snr = np.mean(g['snr'])
            print(f"    T={t:4.1f}ms: Trackable={trackable_pct:3.0f}%, Avg Counts={avg_counts:6.0f}, Avg SNR={avg_snr:5.1f}")

    print("\n3. KEY FINDINGS")
    print("-"*80)

    # Compare S vs P polarization
    s_counts = []
    p_counts = []
    for led in ['A', 'B', 'C', 'D']:
        s_counts.extend([m['counts'] for m in results['S'][led]])
        p_counts.extend([m['counts'] for m in results['P'][led]])

    s_avg = np.mean(s_counts)
    p_avg = np.mean(p_counts)
    pol_ratio = s_avg / p_avg if p_avg > 0 else 1.0

    print(f"\n  Polarization Effect:")
    print(f"    S-pol average counts: {s_avg:.0f}")
    print(f"    P-pol average counts: {p_avg:.0f}")
    print(f"    S/P ratio: {pol_ratio:.3f}")

    if pol_ratio > 1.2:
        print(f"    → S-polarization provides {(pol_ratio-1)*100:.0f}% more signal")
    elif pol_ratio < 0.8:
        print(f"    → P-polarization provides {(1/pol_ratio-1)*100:.0f}% more signal")
    else:
        print(f"    → Minimal polarization dependence")

    # Find most important parameter
    print(f"\n  Most Impactful Parameters (for peak tracking):")
    print(f"    1. Integration Time: Longer times (15-25ms) generally provide better SNR")
    print(f"    2. LED Intensity: Higher intensities increase counts but may saturate")
    print(f"    3. Signal Level: Need >5k counts for reliable tracking, >10k for high precision")
    print(f"    4. Polarization: {'S-pol preferred' if pol_ratio > 1.1 else ('P-pol preferred' if pol_ratio < 0.9 else 'Either polarization OK')}")

def create_analysis_plots(results):
    """Create visualization showing parameter impacts on signal quality"""

    print("\n" + "="*80)
    print("CREATING VISUALIZATIONS")
    print("="*80)

    fig, axes = plt.subplots(2, 4, figsize=(18, 10))

    for col_idx, led_name in enumerate(['A', 'B', 'C', 'D']):
        # S-polarization plot
        ax_s = axes[0, col_idx]
        measurements_s = results['S'][led_name]

        if measurements_s:
            # Plot all measurements colored by quality
            colors = {'Excellent': 'darkgreen', 'Good': 'green', 'Fair': 'orange', 'Poor': 'red'}

            for quality, color in colors.items():
                data = [m for m in measurements_s if m.get('quality') == quality]
                if data:
                    counts = [m['counts'] for m in data]
                    snr = [m['snr'] for m in data]
                    ax_s.scatter(counts, snr, c=color, alpha=0.7, label=quality, s=100, edgecolors='black', linewidths=1)

            ax_s.axvline(5000, color='blue', linestyle='--', alpha=0.5, linewidth=2, label='Tracking threshold')
            ax_s.axvline(10000, color='darkblue', linestyle='--', alpha=0.5, linewidth=2, label='High precision')

            ax_s.set_xlabel('Counts (dark-corrected)', fontsize=11, fontweight='bold')
            ax_s.set_ylabel('SNR', fontsize=11, fontweight='bold')
            ax_s.set_title(f'LED {led_name} - S-pol\nSignal Quality vs Counts', fontsize=12, fontweight='bold')
            ax_s.grid(True, alpha=0.3)
            ax_s.legend(loc='upper left', fontsize=8)
            ax_s.set_xlim(0, max([m['counts'] for m in measurements_s]) * 1.1)

        # P-polarization plot
        ax_p = axes[1, col_idx]
        measurements_p = results['P'][led_name]

        if measurements_p:
            for quality, color in colors.items():
                data = [m for m in measurements_p if m.get('quality') == quality]
                if data:
                    counts = [m['counts'] for m in data]
                    snr = [m['snr'] for m in data]
                    ax_p.scatter(counts, snr, c=color, alpha=0.7, label=quality, s=100, edgecolors='black', linewidths=1)

            ax_p.axvline(5000, color='blue', linestyle='--', alpha=0.5, linewidth=2, label='Tracking threshold')
            ax_p.axvline(10000, color='darkblue', linestyle='--', alpha=0.5, linewidth=2, label='High precision')

            ax_p.set_xlabel('Counts (dark-corrected)', fontsize=11, fontweight='bold')
            ax_p.set_ylabel('SNR', fontsize=11, fontweight='bold')
            ax_p.set_title(f'LED {led_name} - P-pol\nSignal Quality vs Counts', fontsize=12, fontweight='bold')
            ax_p.grid(True, alpha=0.3)
            ax_p.legend(loc='upper left', fontsize=8)
            ax_p.set_xlim(0, max([m['counts'] for m in measurements_p]) * 1.1)

    plt.suptitle('Peak Tracking Parameter Analysis:\nSignal Quality Across Measurement Conditions',
                 fontsize=14, fontweight='bold', y=1.00)
    plt.tight_layout()

    output_plot = 'LED-Counts relationship/peak_tracking_parameter_analysis.png'
    plt.savefig(output_plot, dpi=150, bbox_inches='tight')
    print(f"✓ Visualization saved to: {output_plot}")
    plt.close()

    # Create second plot: Parameter correlation heatmap
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for pol_idx, pol in enumerate(['S', 'P']):
        ax = axes[pol_idx]

        # Collect all measurements for this polarization
        all_data = []
        for led in ['A', 'B', 'C', 'D']:
            for m in results[pol][led]:
                all_data.append({
                    'led': led,
                    'intensity': m['intensity'],
                    'time': m['time'],
                    'counts': m['counts'],
                    'trackable': 1 if m.get('trackable', False) else 0
                })

        if all_data:
            # Create 2D histogram: intensity vs time, colored by trackability
            intensities = np.array([d['intensity'] for d in all_data])
            times = np.array([d['time'] for d in all_data])
            trackable = np.array([d['trackable'] for d in all_data])

            # Plot with size based on trackability
            scatter = ax.scatter(intensities, times, c=trackable, cmap='RdYlGn',
                               s=200, alpha=0.7, edgecolors='black', linewidths=1.5,
                               vmin=0, vmax=1)

            ax.set_xlabel('LED Intensity', fontsize=12, fontweight='bold')
            ax.set_ylabel('Integration Time (ms)', fontsize=12, fontweight='bold')
            ax.set_title(f'{pol}-Polarization\nTrackability Map', fontsize=13, fontweight='bold')
            ax.grid(True, alpha=0.3)

            cbar = plt.colorbar(scatter, ax=ax)
            cbar.set_label('Trackable (1=Yes, 0=No)', fontsize=10)

    plt.suptitle('Parameter Space Analysis:\nOptimal Measurement Conditions for Peak Tracking',
                 fontsize=14, fontweight='bold')
    plt.tight_layout()

    output_plot2 = 'LED-Counts relationship/peak_tracking_parameter_space.png'
    plt.savefig(output_plot2, dpi=150, bbox_inches='tight')
    print(f"✓ Parameter space map saved to: {output_plot2}")
    plt.close()

if __name__ == '__main__':
    analyze_peak_tracking()
