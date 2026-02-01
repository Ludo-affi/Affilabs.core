import pandas as pd

file_path = 'test_data/test_spr_data_20251223_101055.xlsx'
excel = pd.ExcelFile(file_path)
print('Sheets:', excel.sheet_names)
print()

# Analyze Metadata sheet
print('=== METADATA ===')
meta = pd.read_excel(file_path, sheet_name='Metadata')
print(meta)
print()

# Analyze Raw Data sheet structure
print('=== RAW DATA ===')
raw_data = pd.read_excel(file_path, sheet_name='Raw Data')
print(f'Columns: {list(raw_data.columns)}')
print(f'Shape: {raw_data.shape}')
print(f'Memory usage: {raw_data.memory_usage(deep=True).sum() / 1024:.1f} KB')
print()

# Check if Flags sheet exists
if 'Flags' in excel.sheet_names:
    print('=== FLAGS ===')
    flags = pd.read_excel(file_path, sheet_name='Flags')
    print(f'Columns: {list(flags.columns)}')
    print('Sample data:')
    print(flags.head())
