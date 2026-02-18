"""Generate simulated SPR data for testing Edits tab.

Creates realistic calibration data with multiple cycles, baseline shifts, and noise.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime


def generate_spr_cycle(
    duration_s: float = 300,
    baseline: float = 650.0,
    association_shift: float = 2.5,
    dissociation_decay: float = 0.7,
    noise_level: float = 0.05,
    sampling_rate: float = 10.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate realistic SPR binding cycle.
    
    Args:
        duration_s: Cycle duration in seconds
        baseline: Initial baseline wavelength (nm)
        association_shift: Maximum shift during association (nm)
        dissociation_decay: Fraction of signal remaining after dissociation
        noise_level: Noise amplitude (nm)
        sampling_rate: Samples per second (Hz)
    
    Returns:
        (time_array, wavelength_array) in seconds and nm
    """
    # Time points
    num_points = int(duration_s * sampling_rate)
    time = np.linspace(0, duration_s, num_points)
    
    # Realistic SPR cycle phases
    # Phase 1: Baseline (0-60s)
    # Phase 2: Buffer flow (60-90s) - slight shift
    # Phase 3: Association (90-180s) - exponential rise
    # Phase 4: Dissociation (180-270s) - exponential decay
    # Phase 5: Regeneration (270-300s) - return to baseline
    
    signal = np.zeros_like(time)
    
    for i, t in enumerate(time):
        if t < 60:
            # Baseline
            signal[i] = baseline
        elif t < 90:
            # Buffer flow - slight negative shift
            progress = (t - 60) / 30
            signal[i] = baseline - 0.1 * progress
        elif t < 180:
            # Association - exponential rise
            progress = (t - 90) / 90
            ka = 0.05  # Association rate constant
            signal[i] = baseline + association_shift * (1 - np.exp(-ka * (t - 90)))
        elif t < 270:
            # Dissociation - exponential decay
            progress = (t - 180) / 90
            kd = 0.03  # Dissociation rate constant
            max_signal = baseline + association_shift
            signal[i] = baseline + association_shift * dissociation_decay * np.exp(-kd * (t - 180))
        else:
            # Regeneration - rapid return to baseline
            progress = (t - 270) / 30
            signal[i] = baseline + (signal[269] - baseline) * (1 - progress**2)
    
    # Add realistic noise
    noise = np.random.normal(0, noise_level, len(signal))
    signal += noise
    
    # Add slow baseline drift
    drift = 0.02 * (time / duration_s)
    signal += drift
    
    return time, signal


def generate_multi_cycle_data(
    num_cycles: int = 5,
    cycle_duration: float = 300,
    sampling_rate: float = 10.0,
) -> pd.DataFrame:
    """Generate multi-cycle SPR data for 4 channels.
    
    Args:
        num_cycles: Number of binding cycles
        cycle_duration: Duration per cycle (seconds)
        sampling_rate: Samples per second
        
    Returns:
        DataFrame with columns: time, channel, value
    """
    all_data = []
    
    # Different baseline and response for each channel
    channel_params = {
        'a': {'baseline': 650.0, 'shift': 2.5, 'decay': 0.7},
        'b': {'baseline': 648.5, 'shift': 3.2, 'decay': 0.65},
        'c': {'baseline': 651.2, 'shift': 2.8, 'decay': 0.72},
        'd': {'baseline': 649.8, 'shift': 2.3, 'decay': 0.68},
    }
    
    for cycle_num in range(num_cycles):
        cycle_start = cycle_num * cycle_duration
        
        for channel, params in channel_params.items():
            # Add slight variation per cycle
            baseline_var = params['baseline'] + np.random.normal(0, 0.1)
            shift_var = params['shift'] * (0.9 + 0.2 * np.random.random())
            
            time, signal = generate_spr_cycle(
                duration_s=cycle_duration,
                baseline=baseline_var,
                association_shift=shift_var,
                dissociation_decay=params['decay'],
                noise_level=0.05,
                sampling_rate=sampling_rate,
            )
            
            # Offset time by cycle start
            time_offset = time + cycle_start
            
            # Add to dataframe
            for t, val in zip(time_offset, signal):
                all_data.append({
                    'time': t,
                    'channel': channel,
                    'value': val,
                })
    
    return pd.DataFrame(all_data)


def save_to_excel(df: pd.DataFrame, filename: str, num_cycles: int = 5, cycle_duration: float = 300):
    """Save data to Excel format compatible with Edits tab.
    
    Creates separate sheets for each channel plus metadata and cycles.
    """
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        # Metadata sheet
        metadata = pd.DataFrame({
            'Parameter': [
                'Device Type',
                'Detector Serial',
                'Date',
                'Integration Time (ms)',
                'Channels',
                'Cycles',
                'Sampling Rate (Hz)',
            ],
            'Value': [
                'PicoP4SPR',
                'SIM00001',
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                '50',
                '4',
                str(num_cycles),
                '10',
            ],
        })
        metadata.to_excel(writer, sheet_name='Metadata', index=False)
        
        # Cycles sheet - matches real software export structure
        # The real software exports: cycle_id, cycle_num, type, name, start_time_sensorgram, 
        # end_time_sensorgram, duration_minutes, concentration_value, etc.
        # But the loader expects a simplified format with time ranges, so we use both approaches:
        cycles_data = []
        for i in range(num_cycles):
            cycle_start = i * cycle_duration
            cycle_end = (i + 1) * cycle_duration
            duration_min = cycle_duration / 60.0
            concentration_nm = (i + 1) * 10  # 10, 20, 30, 40, 50 nM
            
            cycles_data.append({
                # Core identifiers (like real export)
                'cycle_id': f'cycle_{i+1}',
                'cycle_num': i + 1,
                'type': 'Binding',
                'name': f'[High] {concentration_nm} nM',
                
                # Timing (like real export)
                'start_time_sensorgram': cycle_start,
                'end_time_sensorgram': cycle_end,
                'duration_minutes': duration_min,
                
                # Concentration (like real export)
                'concentration_value': concentration_nm,
                'concentration_units': 'nM',
                'concentrations_formatted': f'A:{concentration_nm}, B:{concentration_nm}, C:{concentration_nm}, D:{concentration_nm}',
                
                # Additional metadata
                'note': f'Simulated binding cycle {i+1}',
                'delta_spr': None,  # Would be calculated post-analysis
                'flags': '',
                
                # Custom format for loader compatibility (time ranges)
                'ACh1': f'{cycle_start:.1f}-{cycle_end:.1f}',
                'Channel': 'All',
            })
        cycles_df = pd.DataFrame(cycles_data)
        cycles_df.to_excel(writer, sheet_name='Cycles', index=False)
        
        # Channel sheets
        for channel in ['a', 'b', 'c', 'd']:
            channel_data = df[df['channel'] == channel][['time', 'value']].copy()
            channel_data.columns = ['Elapsed Time (s)', 'Wavelength (nm)']
            sheet_name = f'Channel_{channel.upper()}'
            channel_data.to_excel(writer, sheet_name=sheet_name, index=False)
        
        print(f"✓ Saved to {filename}")
        print(f"  Sheets: Metadata, Cycles, Channel_A, Channel_B, Channel_C, Channel_D")
        print(f"  Cycles: {num_cycles}")
        print(f"  Total points: {len(df)} ({len(df[df['channel']=='a'])} per channel)")


def main():
    """Generate simulated SPR data."""
    print("=" * 80)
    print("SIMULATED SPR DATA GENERATOR")
    print("=" * 80)
    
    # Generate data
    print("\nGenerating 5 cycles × 4 channels (300s per cycle)...")
    df = generate_multi_cycle_data(
        num_cycles=5,
        cycle_duration=300,
        sampling_rate=10.0,
    )
    
    # Save to multiple formats
    output_dir = Path("simulated_data")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Excel format (for Edits tab)
    excel_file = output_dir / f"SPR_simulated_{timestamp}.xlsx"
    save_to_excel(df, str(excel_file), num_cycles=5, cycle_duration=300)
    
    print("\n" + "=" * 80)
    print("SIMULATION COMPLETE!")
    print("=" * 80)
    print(f"\nFile saved to: {excel_file.absolute()}")
    print("\nTo load in Edits tab:")
    print("  1. Open Affilabs")
    print("  2. Go to Edits tab")
    print("  3. Click 'Load Data'")
    print(f"  4. Select: {excel_file.name}")
    print("\n✓ Ready to use!")


if __name__ == "__main__":
    main()
