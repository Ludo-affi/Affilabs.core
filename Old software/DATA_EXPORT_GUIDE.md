# Data Export System Guide

## Overview

The data export system has been refactored to use a centralized `DataExporter` service with standardized file naming, atomic writes, validation, and export manifests.

## New Directory Structure

When you export/record data, files are now organized in a standardized structure:

```
{Recording Name}/
├── experiment_metadata.json      # Experiment configuration & settings
├── export_manifest.json          # List of all exported files with checksums
├── raw_data/
│   └── raw_data.txt             # Raw sensorgram data (TraceDrawer format)
├── filtered_data/
│   └── filtered_data.txt        # Filtered sensorgram data (if available)
├── segments/
│   ├── segments_summary.csv     # Summary table of all segments
│   ├── segment_001_baseline.csv # Individual segment data files
│   ├── segment_002_association.csv
│   └── ...
└── logs/
    ├── temperature_log.csv      # Temperature log (PicoP4SPR only)
    ├── kinetic_ch_a.csv         # Kinetic channel A log
    └── kinetic_ch_b.csv         # Kinetic channel B log (dual channel only)
```

## Key Improvements

### 1. **Standardized Naming**
- **No spaces** in filenames (better for scripting)
- **Organized by type** (raw_data, filtered_data, segments, logs)
- **Sequential numbering** for segments (001, 002, etc.)
- **Clear hierarchy** for easy navigation

### 2. **Data Validation**
All data is validated before export:
- Checks for empty DataFrames
- Validates required columns exist
- Detects NaN/Inf values
- Ensures time/value array length consistency

### 3. **Atomic Writes**
- Uses temp file + rename pattern
- Prevents corruption from crashes during write
- Guaranteed file integrity

### 4. **Export Manifest**
The `export_manifest.json` file contains:
```json
{
  "experiment": "Recording_2025-11-19",
  "export_timestamp": "2025-11-19T15:30:00",
  "software_version": "4.0.0",
  "total_files": 8,
  "files": [
    {
      "filepath": "raw_data/raw_data.txt",
      "format": "tracedrawer",
      "checksum": "a1b2c3d4e5f6...",
      "row_count": 50000,
      "timestamp": "2025-11-19T15:30:05",
      "size_bytes": 2048576
    }
  ]
}
```

**Use cases:**
- Verify export completeness
- Detect file corruption (checksum validation)
- Track what was exported and when
- Audit trail for data integrity

### 5. **Experiment Metadata**
The `experiment_metadata.json` file contains:
```json
{
  "experiment_name": "Binding_Study",
  "timestamp": "2025-11-19T14:30:00",
  "device": {
    "controller": "PicoP4SPR",
    "kinetic": "",
    "detector": "PhasePhotonics",
    "device_id": "ST00012"
  },
  "settings": {
    "integration_time": 100,
    "channels": ["a", "b", "c", "d"],
    "temperature": 25.0
  },
  "software_version": "4.0.0"
}
```

## File Formats

### Raw Data (`raw_data/raw_data.txt`)
- **Format**: Tab-separated CSV with TraceDrawer metadata headers
- **Columns**: X_RawDataA, Y_RawDataA, X_RawDataB, Y_RawDataB, etc.
- **Compatible with**: TraceDrawer, Excel, Python pandas

### Filtered Data (`filtered_data/filtered_data.txt`)
- **Format**: Tab-separated CSV with TraceDrawer metadata headers
- **Columns**: X_DataA, Y_DataA, X_DataB, Y_DataB, etc.
- **Compatible with**: TraceDrawer, Excel, Python pandas

### Segments Summary (`segments/segments_summary.csv`)
- **Format**: Tab-separated CSV
- **Columns**: Name, StartTime, EndTime, ShiftA, ShiftB, ShiftC, ShiftD, ShiftM, UserNote

### Individual Segments (`segments/segment_###_name.csv`)
- **Format**: Tab-separated CSV
- **Columns**: Interleaved X/Y pairs for all channels
- **Naming**: Sequential numbering + sanitized segment name

### Logs (`logs/`)
- **Format**: Tab-separated CSV
- **Encoding**: UTF-8
- **Columns vary by log type**

## Usage in Code

### Basic Export
```python
from utils.data_exporter import DataExporter

# Create exporter
exporter = DataExporter(
    base_dir="/path/to/output",
    experiment_name="My_Experiment"
)

# Export data
exporter.export_raw_data(data, metadata, references)
exporter.export_segments(segments, value_list, ts_list)
exporter.export_temperature_log(temp_df)

# Save manifest
exporter.save_manifest()
```

### With Validation
```python
from utils.data_exporter import DataValidator

# Validate before export
is_valid, error_msg = DataValidator.validate_sensorgram(data)
if not is_valid:
    logger.error(f"Validation failed: {error_msg}")
    return

# Proceed with export
exporter.export_raw_data(data)
```

## Migration from Old System

### Old Filenames → New Filenames

| Old | New |
|-----|-----|
| `{dir} Raw Data.txt` | `{dir}/raw_data/raw_data.txt` |
| `{dir} Filtered Data.txt` | `{dir}/filtered_data/filtered_data.txt` |
| `{dir} Temperature Log.txt` | `{dir}/logs/temperature_log.csv` |
| `{dir} Kinetic Log Ch A.txt` | `{dir}/logs/kinetic_ch_a.csv` |
| `{dir} Kinetic Log Ch B.txt` | `{dir}/logs/kinetic_ch_b.csv` |
| `{path}/segments_table.csv` | `{dir}/segments/segments_summary.csv` |
| `{path}/{name}.csv` | `{dir}/segments/segment_###_{name}.csv` |

## Benefits

1. **Better Organization**: Files grouped by type, easier to find
2. **Safer**: Atomic writes prevent corruption, validation catches errors
3. **Traceable**: Manifests provide audit trail with checksums
4. **Scriptable**: No spaces in filenames, consistent naming
5. **Maintainable**: Centralized export logic, easier to update
6. **Professional**: Industry-standard practices for data integrity

## Backwards Compatibility

The old export methods (`export_raw_data()`, `export_table()`) are still available in `datawindow.py` for manual exports. The new `DataExporter` is used automatically for:
- Recording data (`save_rec_data()`)
- Auto-save during experiments

Manual exports still use the old format to maintain user familiarity. This can be migrated gradually.
