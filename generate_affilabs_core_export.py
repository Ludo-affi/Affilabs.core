"""
Generate test data in Affilabs.core export format.

Creates an Excel file with all 8 sheets matching the exact format 
that Affilabs.core exports, for testing Affilabs.analyze import.

Sheets:
1. Raw Data - Long format (channel, time, value, timestamp)
2. Channel Data - Wide format (Time A (s), Channel A (nm), etc.)
3. Cycles - Cycle definitions with timing and concentration
4. Flags - User-added markers
5. Events - Timestamped events
6. Analysis - Analysis results
7. Metadata - Key-value pairs
8. Alignment - Edits tab settings
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta


def generate_spr_signal(t, ka, kd, conc, rmax):
    """Generate realistic SPR association/dissociation curve.
    
    Args:
        t: Time array
        ka: Association rate constant (1/Ms)
        kd: Dissociation rate constant (1/s)
        conc: Analyte concentration (M)
        rmax: Maximum response
    
    Returns:
        Response array
    """
    kobs = ka * conc + kd
    req = rmax * ka * conc / (ka * conc + kd)
    return req * (1 - np.exp(-kobs * t))


def generate_affilabs_core_export():
    """Generate test data file in Affilabs.core export format."""
    
    print("Generating Affilabs.core format test data...")
    
    # Configuration
    concentrations_nM = [100, 50, 25, 12.5, 6.25]  # nM
    concentrations_M = [c * 1e-9 for c in concentrations_nM]  # Convert to M
    
    # Kinetic parameters (realistic for antibody-antigen)
    ka = 1e5   # 1/Ms - association rate
    kd = 1e-3  # 1/s - dissociation rate
    rmax = 800  # RU - max response
    
    # Timing
    baseline_time = 60       # seconds
    association_time = 300   # seconds
    dissociation_time = 400  # seconds
    
    sample_rate = 1.0  # Hz
    start_time = datetime.now() - timedelta(hours=1)
    recording_start = start_time.timestamp()
    
    # =========================================================================
    # Sheet 1: Raw Data (long format)
    # =========================================================================
    raw_data_rows = []
    current_time = 0
    
    for cycle_idx, (conc_nM, conc_M) in enumerate(zip(concentrations_nM, concentrations_M)):
        cycle_start = current_time
        
        # Baseline phase
        for t in np.arange(0, baseline_time, 1/sample_rate):
            abs_time = current_time + t
            for ch in ['a', 'b', 'c', 'd']:
                raw_data_rows.append({
                    'channel': ch,
                    'time': abs_time,
                    'value': 645.0 + np.random.normal(0, 0.1),  # baseline with noise
                    'timestamp': recording_start + abs_time,
                })
        
        current_time += baseline_time
        
        # Association phase
        t_assoc = np.arange(0, association_time, 1/sample_rate)
        signal = generate_spr_signal(t_assoc, ka, kd, conc_M, rmax)
        
        for i, t in enumerate(t_assoc):
            abs_time = current_time + t
            for ch in ['a', 'b', 'c', 'd']:
                value = 645.0 + signal[i] + np.random.normal(0, 0.1)
                raw_data_rows.append({
                    'channel': ch,
                    'time': abs_time,
                    'value': value,
                    'timestamp': recording_start + abs_time,
                })
        
        current_time += association_time
        
        # Dissociation phase
        r_at_end = signal[-1]
        for t in np.arange(0, dissociation_time, 1/sample_rate):
            abs_time = current_time + t
            response = r_at_end * np.exp(-kd * t)
            for ch in ['a', 'b', 'c', 'd']:
                value = 645.0 + response + np.random.normal(0, 0.1)
                raw_data_rows.append({
                    'channel': ch,
                    'time': abs_time,
                    'value': value,
                    'timestamp': recording_start + abs_time,
                })
        
        current_time += dissociation_time
    
    df_raw = pd.DataFrame(raw_data_rows)
    
    # =========================================================================
    # Sheet 2: Channel Data (wide format)
    # =========================================================================
    channels = ['a', 'b', 'c', 'd']
    channel_dfs = []
    
    for ch in channels:
        ch_data = df_raw[df_raw['channel'] == ch][['time', 'value']].copy()
        ch_data.columns = [f'Time {ch.upper()} (s)', f'Channel {ch.upper()} (nm)']
        channel_dfs.append(ch_data.reset_index(drop=True))
    
    df_channel = pd.concat(channel_dfs, axis=1)
    
    # =========================================================================
    # Sheet 3: Cycles
    # =========================================================================
    cycles = []
    current_time = 0
    cycle_duration = baseline_time + association_time + dissociation_time
    
    for cycle_idx, conc_nM in enumerate(concentrations_nM):
        cycle_start = current_time
        cycle_end = cycle_start + cycle_duration
        
        cycles.append({
            'cycle_id': cycle_idx + 1,
            'cycle_num': cycle_idx + 1,
            'type': 'Kinetic',
            'name': f'Anti-HER2 {conc_nM} nM',
            'start_time_sensorgram': cycle_start,
            'end_time_sensorgram': cycle_end,
            'duration_minutes': cycle_duration / 60,
            'concentration_value': conc_nM,
            'concentration_units': 'nM',
            'concentrations_formatted': f'A:{conc_nM}',
            'note': f'Concentration series cycle {cycle_idx + 1}',
            'delta_spr': None,  # To be filled by analysis
            'flags': '',
            'timestamp': (start_time + timedelta(seconds=cycle_start)).isoformat(),
        })
        
        current_time = cycle_end
    
    df_cycles = pd.DataFrame(cycles)
    
    # =========================================================================
    # Sheet 4: Flags
    # =========================================================================
    flags = [
        {'flag_id': 1, 'time': 60.0, 'label': 'Injection Start', 'color': '#34C759', 'channel': 'all'},
        {'flag_id': 2, 'time': 360.0, 'label': 'Dissociation', 'color': '#FF9500', 'channel': 'all'},
    ]
    df_flags = pd.DataFrame(flags)
    
    # =========================================================================
    # Sheet 5: Events
    # =========================================================================
    events = [
        {'elapsed': 0.0, 'timestamp': start_time.strftime('%Y-%m-%d %H:%M:%S'), 'event': 'Recording started'},
        {'elapsed': 60.0, 'timestamp': (start_time + timedelta(seconds=60)).strftime('%Y-%m-%d %H:%M:%S'), 'event': 'Sample injection'},
        {'elapsed': 360.0, 'timestamp': (start_time + timedelta(seconds=360)).strftime('%Y-%m-%d %H:%M:%S'), 'event': 'Buffer switch'},
    ]
    df_events = pd.DataFrame(events)
    
    # =========================================================================
    # Sheet 6: Analysis (empty - to be filled by Affilabs.analyze)
    # =========================================================================
    df_analysis = pd.DataFrame(columns=['cycle_id', 'ka', 'kd', 'KD', 'Rmax', 'chi2', 'residual_rms'])
    
    # =========================================================================
    # Sheet 7: Metadata
    # =========================================================================
    metadata = {
        'experiment_name': 'Anti-HER2 Kinetic Study',
        'user': 'Test User',
        'date': start_time.strftime('%Y-%m-%d'),
        'time': start_time.strftime('%H:%M:%S'),
        'instrument': 'Affilabs SPR',
        'chip_type': 'CM5',
        'ligand': 'HER2',
        'analyte': 'Anti-HER2 IgG',
        'running_buffer': 'HBS-EP+',
        'temperature': '25°C',
        'flow_rate': '30 µL/min',
        'affilabs_core_version': '2.0.0',
        'export_format_version': '1.0',
    }
    df_metadata = pd.DataFrame([{'key': k, 'value': str(v)} for k, v in metadata.items()])
    
    # =========================================================================
    # Sheet 8: Alignment (Edits tab settings)
    # =========================================================================
    alignment = [
        {'Cycle_Index': i + 1, 'Channel_Filter': 'All', 'Time_Shift_s': 0.0}
        for i in range(len(concentrations_nM))
    ]
    df_alignment = pd.DataFrame(alignment)
    
    # =========================================================================
    # Write to Excel
    # =========================================================================
    output_dir = Path('test_data')
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / f'affilabs_core_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df_raw.to_excel(writer, sheet_name='Raw Data', index=False)
        df_channel.to_excel(writer, sheet_name='Channel Data', index=False)
        df_cycles.to_excel(writer, sheet_name='Cycles', index=False)
        df_flags.to_excel(writer, sheet_name='Flags', index=False)
        df_events.to_excel(writer, sheet_name='Events', index=False)
        df_analysis.to_excel(writer, sheet_name='Analysis', index=False)
        df_metadata.to_excel(writer, sheet_name='Metadata', index=False)
        df_alignment.to_excel(writer, sheet_name='Alignment', index=False)
    
    print(f"\n✓ Generated: {output_file}")
    print(f"\nFile contents (matching Affilabs.core export):")
    print(f"  • Raw Data:     {len(df_raw):,} rows (long format)")
    print(f"  • Channel Data: {len(df_channel):,} rows (wide format)")
    print(f"  • Cycles:       {len(df_cycles)} cycles")
    print(f"  • Flags:        {len(df_flags)} markers")
    print(f"  • Events:       {len(df_events)} events")
    print(f"  • Analysis:     (empty - ready for fitting)")
    print(f"  • Metadata:     {len(df_metadata)} entries")
    print(f"  • Alignment:    {len(df_alignment)} settings")
    
    print(f"\n📊 To test in Affilabs.analyze:")
    print(f"   1. Run: python affilabs_analyze_prototype.py")
    print(f"   2. Click '📊 Import' in toolbar")
    print(f"   3. Select: {output_file}")
    
    return output_file


if __name__ == '__main__':
    generate_affilabs_core_export()
