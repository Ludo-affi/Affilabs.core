"""Debug cycles display issue in loaded Excel file."""

import pandas as pd
import openpyxl

file_path = r"C:\Users\lucia\Documents\Affilabs Data\Ludo\SPR_data\spr_data_20260212_001016.xlsx"

print("=" * 80)
print("DEBUGGING CYCLE DISPLAY ISSUE")
print("=" * 80)

# Load Excel file
excel_file = pd.ExcelFile(file_path)
print(f"\nAvailable sheets: {excel_file.sheet_names}")

# Check Cycles sheet
if 'Cycles' in excel_file.sheet_names:
    df_cycles = pd.read_excel(file_path, sheet_name='Cycles')
    print(f"\n{'='*80}")
    print("CYCLES SHEET ANALYSIS")
    print(f"{'='*80}")
    print(f"Total rows: {len(df_cycles)}")
    print(f"Columns: {list(df_cycles.columns)}")
    print(f"\nFirst 10 rows:")
    print(df_cycles.head(10))
    print(f"\nLast 10 rows:")
    print(df_cycles.tail(10))
    
    # Check for data issues
    print(f"\n{'='*80}")
    print("DATA QUALITY CHECK")
    print(f"{'='*80}")
    
    # Check start/end times
    if 'Start Time (s)' in df_cycles.columns:
        print(f"\nStart Time stats:")
        print(f"  Min: {df_cycles['Start Time (s)'].min()}")
        print(f"  Max: {df_cycles['Start Time (s)'].max()}")
        print(f"  NaN count: {df_cycles['Start Time (s)'].isna().sum()}")
        
        # Check for negative or zero values
        invalid_starts = df_cycles[df_cycles['Start Time (s)'] <= 0]
        if len(invalid_starts) > 0:
            print(f"  ⚠️ {len(invalid_starts)} cycles with start time <= 0")
            print(invalid_starts[['Cycle #', 'Type', 'Start Time (s)']])
    
    if 'Duration (min)' in df_cycles.columns:
        print(f"\nDuration stats:")
        print(f"  Min: {df_cycles['Duration (min)'].min()}")
        print(f"  Max: {df_cycles['Duration (min)'].max()}")
        print(f"  NaN count: {df_cycles['Duration (min)'].isna().sum()}")
        
        # Check for zero or negative durations
        invalid_durations = df_cycles[df_cycles['Duration (min)'] <= 0]
        if len(invalid_durations) > 0:
            print(f"  ⚠️ {len(invalid_durations)} cycles with duration <= 0")
            print(invalid_durations[['Cycle #', 'Type', 'Duration (min)', 'Start Time (s)']])
    
    # Check cycle types
    if 'Type' in df_cycles.columns:
        print(f"\nCycle types distribution:")
        print(df_cycles['Type'].value_counts())
    
    # Check for overlapping cycles
    print(f"\n{'='*80}")
    print("CYCLE BOUNDARIES CHECK")
    print(f"{'='*80}")
    
    if 'Start Time (s)' in df_cycles.columns and 'Duration (min)' in df_cycles.columns:
        df_cycles['End Time (s)'] = df_cycles['Start Time (s)'] + (df_cycles['Duration (min)'] * 60)
        
        print(f"\nFirst 15 cycles boundary info:")
        print(df_cycles[['Cycle #', 'Type', 'Start Time (s)', 'End Time (s)', 'Duration (min)']].head(15))
        
        # Check for gaps or overlaps
        for i in range(len(df_cycles) - 1):
            current_end = df_cycles.iloc[i]['End Time (s)']
            next_start = df_cycles.iloc[i + 1]['Start Time (s)']
            gap = next_start - current_end
            
            if abs(gap) > 5:  # More than 5 seconds gap/overlap
                cycle_num = df_cycles.iloc[i]['Cycle #']
                next_cycle_num = df_cycles.iloc[i + 1]['Cycle #']
                if gap > 0:
                    print(f"  GAP: {gap:.1f}s between Cycle {cycle_num} and {next_cycle_num}")
                else:
                    print(f"  OVERLAP: {-gap:.1f}s between Cycle {cycle_num} and {next_cycle_num}")

# Check raw data sheet
if 'Channel Data' in excel_file.sheet_names:
    df_raw = pd.read_excel(file_path, sheet_name='Channel Data', nrows=100)
    print(f"\n{'='*80}")
    print("CHANNEL DATA SHEET (first 100 rows)")
    print(f"{'='*80}")
    print(f"Columns: {list(df_raw.columns)}")
    print(f"\nFirst 10 rows:")
    print(df_raw.head(10))
    
    # Check time range
    time_cols = [col for col in df_raw.columns if 'Time' in col]
    if time_cols:
        print(f"\nTime range analysis:")
        for col in time_cols:
            valid_times = df_raw[col].dropna()
            if len(valid_times) > 0:
                print(f"  {col}: {valid_times.min():.2f}s to {valid_times.max():.2f}s")

print(f"\n{'='*80}")
print("ANALYSIS COMPLETE")
print(f"{'='*80}")
