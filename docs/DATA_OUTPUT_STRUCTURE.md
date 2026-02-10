# Data Output Structure & GLP Compliance

## Overview

Affilabs-Core stores all experiment data in a **GLP/GMP-compliant hierarchical folder structure** that ensures data integrity, traceability, and regulatory compliance. Each experiment session creates immutable, timestamped folders with standardized subdirectories.

---

## Base Directory Location

**Default:** `~/Documents/Affilabs_Data/` (e.g., `C:\Users\lucia\Documents\Affilabs_Data\`)

You can change this location in the app by selecting a different output directory when starting a new experiment.

---

## Folder Structure

### Naming Convention

```
YYYY-MM-DD_ExperimentName_Username/
```

**Examples:**
- `2026-02-10_Antibody_Screening_Lucia/`
- `2026-02-10_Kinetic_Study_John/`

**Format Details:**
- **Date**: `YYYY-MM-DD` (ISO 8601 standard, sortable and unambiguous)
- **Experiment Name**: Sanitized (spaces → underscores, special chars removed)
- **Username**: Operator name who ran the experiment

---

## Subdirectories

Each experiment folder contains five standard subdirectories:

### 1. `Raw_Data/`
**Purpose**: Raw timestamped sensor measurements

**Contains:**
- CSV files: `Raw_20260210_143052.csv` (timestamped raw data)
- JSON metadata files accompanying each CSV
- Real-time cycle autosaves: `current_cycle.csv`

**Format**: Long format (one measurement per row)
```
Time (s),Channel,Value (RU)
0.000,a,45.2
0.001,a,45.3
0.000,b,62.1
...
```

---

### 2. `Analysis/`
**Purpose**: Processed analysis results and annotated cycle tables

**Contains:**
- Processed sensorgram data
- Cycle analysis (kinetics, binding parameters)
- Annotated tables with peak detection results
- Statistical summaries

---

### 3. `Figures/`
**Purpose**: Exported graphs and visualizations

**Contains:**
- PNG/JPEG images of sensorgrams
- Binding curve plots
- Quality control charts
- Publication-ready figures with metadata

---

### 4. `Method/`
**Purpose**: Experimental protocols and method files

**Contains:**
- Method configuration files
- Experimental protocols
- Parameter settings used during recording
- Step-by-step procedure documentation

---

### 5. `QC_Reports/`
**Purpose**: Quality control and validation reports

**Contains:**
- Baseline stability reports
- Signal-to-noise analysis
- Calibration verification results
- Leak detection reports
- Instrument qualification (OQ/PQ) documentation

---

## Metadata & Audit Trail

### `experiment_metadata.json`

Located at the root of each experiment folder. Contains:

```json
{
  "experiment_info": {
    "name": "Antibody_Screening",
    "folder_name": "2026-02-10_Antibody_Screening_Lucia",
    "created_date": "2026-02-10T14:30:52.123456",
    "description": "SPR kinetics of monoclonal antibodies"
  },
  "operator": {
    "name": "Lucia"
  },
  "instrument": {
    "device_id": "PicoP4SPR-001",
    "sensor_type": "SPR-Gold Sensor Chip"
  },
  "software": {
    "version": "2.0.2",
    "name": "Affilabs-Core"
  },
  "files": {
    "raw_data": [
      {
        "filename": "Raw_20260210_143052.csv",
        "full_path": "...",
        "created": "2026-02-10T14:30:52.234567",
        "description": "Cycle 1: Baseline injection",
        "size_bytes": 45632
      }
    ],
    "analysis": [],
    "figures": [],
    "methods": [],
    "qc_reports": []
  },
  "audit_trail": [
    {
      "timestamp": "2026-02-10T14:30:52.123456",
      "action": "Experiment folder created",
      "user": "Lucia"
    },
    {
      "timestamp": "2026-02-10T14:32:15.456789",
      "action": "File added: raw_data",
      "filename": "Raw_20260210_143052.csv",
      "user": "Lucia"
    }
  ]
}
```

---

## GLP Compliance Features

### ✓ Immutable Raw Data
- **Timestamped filenames**: `Raw_20260210_143052.csv`
- **Read-only after export**: Original data files preserved
- **Folder date prefix**: Prevents accidental reorganization

### ✓ Complete Audit Trail
- Every file creation logged with timestamp and operator
- Metadata tracks who accessed/modified data
- ISO 8601 timestamps for international compliance
- Reversible operations (cycles can be re-analyzed)

### ✓ Metadata Tracking
- Operator name (traceability)
- Device ID & sensor type (instrument qualification)
- Software version (reproducibility)
- Experiment description (scientific context)
- Creation timestamps (temporal record)

### ✓ Standardized Organization
- Consistent folder hierarchy across all experiments
- README.txt in each subdirectory explains its purpose
- File naming conventions: `{Type}_{YYYYMMDD}_{HHMMSS}`

### ✓ Data Integrity
- File registry with sizes (detect corruption)
- JSON metadata for each dataset
- Channel-specific data separation (unmixes parallel vs. serial measurements)

---

## Data Export & Recording

### Recording During Live Mode

When you start **recording** in Live Mode:
- Data automatically saves to Excel (`.xlsx`) file
- Sheets created:
  - **Raw Data**: All measurements (long format)
  - **Cycles**: Cycle metadata (start time, stop time, duration)
  - **Flags**: User-placed annotation flags
  - **Events**: System-generated events (LED changes, etc.)
  - **Metadata**: Experiment parameters
  - **Channels XY**: Per-channel time series

**File naming**: Automatically timestamped; stored in Affilabs_Data base directory

### Manual Cycle Export

**From "Cycle of Interest" tab:**
- Select time range with cursors
- Export → CSV, Excel, JSON, or PNG image
- Includes metadata header (times, channels, filters applied)

**Example CSV export:**
```
# AffiLabs Cycle Export
# Export Date,2026-02-10T14:35:12.567890
# Start Time (s),120.45
# Stop Time (s),180.92
# Duration (s),60.47

Time (s),Channel_A_SPR (RU),Channel_B_SPR (RU),Channel_C_SPR (RU),Channel_D_SPR (RU)
0.000,45.23,62.10,28.55,51.30
0.001,45.24,62.11,28.56,51.31
...
```

### Autosave Cycle Data

During live recording, the current cycle autosaves to:
- **File**: `cycles/current_cycle.csv` + `current_cycle.json`
- **Updates**: Every cycle analysis (not timestamped spam)
- **Content**: Time, wavelength, SPR per channel

**JSON metadata includes:**
- Cycle type & length
- User notes
- Filter settings applied
- Reference subtraction info
- Injection time (first flag marker)
- All annotated flags

---

## File Organization Best Practices

### For Regulatory Submissions
1. **Keep folder intact** — Don't move or rename subdirectories
2. **Preserve metadata.json** — Audit trail proof
3. **Archive as-is** — Zip entire experiment folder for filing
4. **Document changes** — Any post-experiment edits should be logged externally

### For Collaborative Analysis
1. **Share entire folder** — Includes all context (metadata, QC reports)
2. **Version control** — Save multiple analysis versions in Analysis/ subdirectory
3. **Cross-reference** — Link figures to raw data filenames in figure metadata

### For Long-Term Storage
1. **Backup strategy**: RAID or cloud backup to protect against hardware failure
2. **File format**: CSV is platform-independent; Excel files should be saved in `xlsx` format
3. **Metadata with exports**: Always include experiment_metadata.json when archiving

---

## Accessing Your Data

### From the Application
- **Data Window**: View all recorded experiments (name, date, operator, device)
- **File paths shown**: Full location so you can browse in File Explorer
- **Re-open experiments**: Load previous experiment folders

### From File System
1. Open `C:\Users\{YourUsername}\Documents\Affilabs_Data\`
2. Browse by date (folders sorted chronologically)
3. Open `experiment_metadata.json` to see what's in the folder
4. Raw data in `Raw_Data/` subdirectory
5. Exported figures in `Figures/` subdirectory

---

## Troubleshooting

### Data Not Appearing in Expected Folder
- Check default output directory setting (Settings → Data Output Path)
- Recording may have been saved to a different location
- Check experiment_metadata.json to confirm folder contents

### Missing Files
- Raw data files are only created during "recording" (Live Mode with Record button ON)
- Autosave requires active cycle selection
- Check Raw_Data/ subdirectory (not root folder)

### Cannot Edit Metadata
- `experiment_metadata.json` is by design; edits should be minimal
- If changes needed, document them externally for audit trail
- Create a new experiment folder for modified/corrected data

---

## Technical Specifications

| Item | Specification |
|------|---------------|
| **Date Format** | ISO 8601 (YYYY-MM-DD) |
| **Timestamp Format** | ISO 8601 with microseconds |
| **File Naming** | `{Type}_{YYYYMMDD}_{HHMMSS}.{ext}` |
| **Character Encoding** | UTF-8 |
| **Metadata Format** | JSON (unicode-safe, version-controlled) |
| **Raw Data Format** | CSV (comma-separated, UTF-8 encoded) |
| **Time Precision** | 0.001 seconds (millisecond) |
| **SPR Precision** | 0.01 RU (Response Units) |

---

## References

- **GLP Standard**: OECD Principles of Good Laboratory Practice
- **Data Format**: RFC 4180 (CSV), ECMA-404 (JSON)
- **Timestamps**: ISO 8601 (international standard)
- **Software Version**: Affilabs-Core 2.0.2

---

*Last Updated: 2026-02-10*
*For support, contact: support@affinitelabs.com*
