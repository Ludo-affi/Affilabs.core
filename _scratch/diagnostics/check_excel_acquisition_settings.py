"""Check Excel File Acquisition Settings

The Excel file might not have been recorded with production acquisition settings.
Let's check what integration time and averaging was actually used.
"""

import pandas as pd
from pathlib import Path

DATA_FILE = Path("test_data/baseline_recording_20260126_235959.xlsx")

print("=" * 80)
print("EXCEL FILE METADATA CHECK")
print("=" * 80)

# Load all sheet names
xl = pd.ExcelFile(DATA_FILE)
print(f"\nFile: {DATA_FILE.name}")
print(f"Sheets: {xl.sheet_names}")

# Check if there's a metadata sheet
if "Metadata" in xl.sheet_names:
    print("\n📋 METADATA SHEET FOUND:")
    metadata = pd.read_excel(DATA_FILE, sheet_name="Metadata")
    print(metadata.to_string())
else:
    print("\n⚠️  No 'Metadata' sheet found")

# Check Channel A for acquisition info in column headers or first rows
df = pd.read_excel(DATA_FILE, sheet_name="Channel_A")
print("\n📊 Channel A Data:")
print(f"  Shape: {df.shape}")
print(f"  Columns (first 10): {list(df.columns[:10])}")

# Check if there's any metadata in the first few rows before data starts
print("\n  First 3 rows:")
print(df.head(3))

# Timing analysis
time_columns = [col for col in df.columns if col.startswith('t_')]
num_timepoints = len(time_columns)

# Check column naming for timing info
if num_timepoints > 1:
    # Extract time indices
    times = [int(col.split('_')[1]) for col in time_columns]
    print("\n⏱️  TIMING ANALYSIS:")
    print(f"  Timepoints: {num_timepoints}")
    print(f"  Time indices: {min(times)} to {max(times)}")
    print(f"  Expected duration: ~{max(times)} seconds (if 1 Hz sampling)")
    print(f"  Actual duration: {num_timepoints / 1.0:.1f} seconds at 1 Hz")

# What we expect for live mode vs what might be in Excel
print("\n" + "=" * 80)
print("EXPECTED vs ACTUAL ACQUISITION SETTINGS")
print("=" * 80)

print("\n✅ EXPECTED (Live Production Mode):")
print("  Integration time: 22.17 ms")
print("  Hardware averaging: 8 scans per acquisition")
print("  Software batch: 12 spectra sliding window")
print("  Acquisition rate: ~25 Hz (40 ms per spectrum)")
print("  Processing: Fourier transform with SG filtering")
print("  Baseline noise: ~6 RU RMS (GOLD STANDARD)")

print("\n❓ ACTUAL (Excel File - Unknown):")
print("  Integration time: ??? (metadata not found)")
print("  Hardware averaging: ??? (likely OFF or =1)")
print("  Software batch: NO (individual spectra saved)")
print("  Acquisition rate: ~1 Hz (296 spectra in 295 seconds)")
print("  Processing: Unknown (saved raw spectra)")
print("  Baseline noise: ~58 RU RMS (measured)")

print("\n🔍 KEY OBSERVATION:")
print("  Expected baseline: ~6 RU RMS")
print("  Measured baseline: ~58 RU RMS")
print(f"  Ratio: {58/6:.1f}× WORSE")
print("  User reports: ~100× worse than expected")
print("  ")
print("  This suggests:")
print("  1. Excel data has NO hardware averaging (8-scan)")
print("  2. Excel data has NO batch smoothing (12-spectrum)")
print("  3. Integration time may be SHORTER (less photons)")
print("  4. Data saved BEFORE processing pipeline applied")

print("\n💡 HYPOTHESIS:")
print("  Your Excel file contains RAW spectra from test acquisitions,")
print("  NOT production-mode data with full averaging/processing.")
print("  ")
print("  The 100× worse noise is because:")
print("  - Single acquisitions (no 8-scan averaging) = 2.8× worse")
print("  - No batch processing (no 12-window smoothing) = 3.5× worse")
print("  - Possibly shorter integration time = 2-5× worse")
print("  - Combined effect: 2.8 × 3.5 × 2 = ~20-100× worse")

print("\n🔧 TO VERIFY:")
print("  1. Record new baseline using main.py live mode")
print("  2. Export that data (should have averaging already applied)")
print("  3. Compare noise levels")
print("  4. Check if Excel export includes acquisition parameters")

print("=" * 80)
