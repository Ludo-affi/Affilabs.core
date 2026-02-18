"""Check for duplicate cycles and display issue."""

import pandas as pd

file_path = r"C:\Users\lucia\Documents\Affilabs Data\Ludo\SPR_data\spr_data_20260212_001016.xlsx"

df = pd.read_excel(file_path, sheet_name='Cycles')

print("FULL CYCLE DATA:")
print("=" * 120)
print(df[['cycle_id', 'cycle_num', 'type', 'start_time_sensorgram', 'end_time_sensorgram', 'duration_minutes']])

print("\n\nDUPLICATE CHECK:")
print("=" * 120)
duplicates = df.duplicated(subset=['cycle_id'], keep=False)
print(f"Total duplicates: {duplicates.sum()}")

print("\n\nGROUP BY CYCLE_ID:")
print("=" * 120)
grouped = df.groupby('cycle_id').size()
print(f"Cycles appearing more than once:")
print(grouped[grouped > 1])

print("\n\nFIRST vs SECOND OCCURRENCE COMPARISON:")
print("=" * 120)
for cycle_id in [1, 2, 3]:
    rows = df[df['cycle_id'] == cycle_id]
    if len(rows) > 1:
        print(f"\nCycle {cycle_id}:")
        print(rows[['cycle_num', 'start_time_sensorgram', 'end_time_sensorgram', 'duration_minutes']])
