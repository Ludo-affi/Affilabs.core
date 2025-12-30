"""Test if we can read the data properly."""
import pandas as pd

# Read the file
excel_data = pd.read_excel('test_data/test_spr_data_20251223_101055.xlsx', sheet_name=None, engine='openpyxl')

print("Sheets in file:", list(excel_data.keys()))
print()

# Check Raw Data
raw_df = excel_data.get('Raw Data')
if raw_df is not None:
    print(f"Raw Data: {len(raw_df)} rows")
    print("Columns:", raw_df.columns.tolist())
    print("\nFirst row:")
    print(raw_df.iloc[0])
    print()

    # Convert to dict
    raw_data_rows = raw_df.to_dict('records')
    first_row = raw_data_rows[0]
    print("First row as dict:")
    for k, v in first_row.items():
        print(f"  {k}: {v} ({type(v).__name__})")
    print()

    # Check time range
    times = [r.get('elapsed', r.get('time', 0)) for r in raw_data_rows]
    print(f"Time range: {min(times)} - {max(times)}")
    print()

# Check Cycles
cycles_df = excel_data.get('Cycles')
if cycles_df is not None:
    print(f"Cycles: {len(cycles_df)} rows")
    print("Columns:", cycles_df.columns.tolist())
    print("\nFirst cycle:")
    print(cycles_df.iloc[0])
    print()

    # Check what happens with first cycle
    cycle_dict = cycles_df.to_dict('records')[0]
    start_time = cycle_dict.get('start_time_sensorgram', cycle_dict.get('sensorgram_time'))
    end_time = cycle_dict.get('end_time_sensorgram')
    print(f"Cycle 1 time range: {start_time} - {end_time}")
    print(f"Types: start={type(start_time).__name__}, end={type(end_time).__name__}")
    print()

    # Check how many raw data points fall in this range
    matching = [r for r in raw_data_rows if start_time <= r.get('elapsed', r.get('time', 0)) <= end_time]
    print(f"Raw data points in cycle 1 time range: {len(matching)}")
    if len(matching) > 0:
        print("First matching point:")
        print(f"  time: {matching[0].get('elapsed', matching[0].get('time'))}")
        print(f"  wavelength_a: {matching[0].get('wavelength_a')}")
        print(f"  wavelength_b: {matching[0].get('wavelength_b')}")
        print(f"  wavelength_c: {matching[0].get('wavelength_c')}")
        print(f"  wavelength_d: {matching[0].get('wavelength_d')}")
