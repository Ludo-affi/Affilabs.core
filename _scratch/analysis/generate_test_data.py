"""
Generate test data files for testing the Edits interface.
Creates an Excel file with realistic SPR cycle data for 4 channels.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

def generate_test_data():
    """Generate realistic test data for SPR experiment."""

    # Configuration
    num_cycles = 10
    duration_minutes = 5
    sample_rate = 1.0  # seconds

    # Generate timestamps
    start_time = datetime.now() - timedelta(hours=2)

    # Create raw data rows (sensorgram)
    raw_data_rows = []
    current_time = 0

    # Base wavelengths for each channel (in nm)
    base_wavelengths = {
        'a': 650.0,
        'b': 655.0,
        'c': 660.0,
        'd': 665.0
    }

    # Generate 2 hours of continuous data (covers all cycles)
    total_duration = num_cycles * duration_minutes * 60 + 600  # Extra padding

    for t in np.arange(0, total_duration, sample_rate):
        row = {
            'elapsed': t,
            'time': t,
            'timestamp': (start_time + timedelta(seconds=t)).isoformat()
        }

        # Add wavelength data for each channel with realistic SPR signal
        for ch in ['a', 'b', 'c', 'd']:
            # Add slow drift + noise
            drift = 0.001 * t  # Slow drift over time
            noise = np.random.normal(0, 0.05)  # Small noise

            # Add cycle-specific binding events
            wavelength = base_wavelengths[ch] + drift + noise

            # Simulate binding events during certain cycles
            for cycle_idx in range(num_cycles):
                cycle_start = cycle_idx * duration_minutes * 60 + 30  # 30s offset
                cycle_end = cycle_start + (duration_minutes * 60)

                if cycle_start <= t <= cycle_end:
                    # Simulate association/dissociation curve
                    relative_time = t - cycle_start
                    cycle_duration = duration_minutes * 60

                    # Different response for each cycle
                    if cycle_idx % 3 == 0:  # Strong binder
                        amplitude = 2.0 + cycle_idx * 0.3
                    elif cycle_idx % 3 == 1:  # Medium binder
                        amplitude = 1.0 + cycle_idx * 0.2
                    else:  # Weak binder
                        amplitude = 0.5 + cycle_idx * 0.1

                    # Association phase (first 60%)
                    if relative_time < cycle_duration * 0.6:
                        # Exponential association
                        signal = amplitude * (1 - np.exp(-relative_time / 60))
                    else:
                        # Dissociation phase
                        dissoc_start = cycle_duration * 0.6
                        dissoc_time = relative_time - dissoc_start
                        max_signal = amplitude * (1 - np.exp(-dissoc_start / 60))
                        signal = max_signal * np.exp(-dissoc_time / 120)

                    wavelength += signal

            row[f'wavelength_{ch}'] = round(wavelength, 4)

        raw_data_rows.append(row)

    # Create cycles data
    cycles_data = []

    for i in range(num_cycles):
        cycle_start = i * duration_minutes * 60 + 30
        cycle_end = cycle_start + (duration_minutes * 60)

        # Create cycle metadata
        cycle = {
            'cycle_number': i + 1,
            'start_time_sensorgram': cycle_start,
            'end_time_sensorgram': cycle_end,
            'sensorgram_time': cycle_start,  # Alias for compatibility
            'duration_minutes': duration_minutes,
            'length_minutes': duration_minutes,  # Alias for compatibility
            'cycle_type': ['Baseline', 'Association', 'Dissociation'][i % 3],
            'concentration_value': [0, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000][i],
            'concentration_units': 'nM',
            'note': f'Test cycle {i+1}',
            'notes': f'Test cycle {i+1}',  # Alias for compatibility
            'timestamp': (start_time + timedelta(seconds=cycle_start)).isoformat()
        }
        cycles_data.append(cycle)

    # Convert to DataFrames
    raw_df = pd.DataFrame(raw_data_rows)
    cycles_df = pd.DataFrame(cycles_data)

    # Create output directory
    output_dir = Path('test_data')
    output_dir.mkdir(exist_ok=True)

    # Save to Excel with two sheets
    output_file = output_dir / f'test_spr_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        raw_df.to_excel(writer, sheet_name='Raw Data', index=False)
        cycles_df.to_excel(writer, sheet_name='Cycles', index=False)

    print(f"✓ Test data generated: {output_file}")
    print(f"  - {len(raw_data_rows)} raw data points")
    print(f"  - {len(cycles_data)} cycles")
    print(f"  - Duration: {total_duration/60:.1f} minutes")
    print("\nTo use:")
    print("  1. Run the application")
    print("  2. Go to Edits tab")
    print(f"  3. Click 'Load Data' and select: {output_file}")
    print("  4. Select cycles from the table to view them on the graph")
    print("  5. Test multi-cycle selection and segment creation")

    return output_file


if __name__ == '__main__':
    generate_test_data()
