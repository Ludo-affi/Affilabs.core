import pandas as pd

# Read the Cycles sheet
df = pd.read_excel('test_data/test_spr_data_20251223_101055.xlsx', sheet_name='Cycles')

print("Columns:", df.columns.tolist())
print("\nFirst 3 rows:")
print(df.head(3))
print("\nData types:")
print(df.dtypes)
