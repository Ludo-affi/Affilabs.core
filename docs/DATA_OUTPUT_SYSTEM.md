# Data Output & Export System

## Overview

The Affilabs.core data output system provides robust, validated, and flexible export mechanisms for SPR experiment data. The architecture separates concerns across multiple layers, ensuring data integrity, format flexibility, and comprehensive metadata tracking.

**Current Status**: Production-ready with atomic writes, validation, multi-format export, and real-time recording.

---

## System Architecture

### Export Flow

```
┌──────────────────┐
│   User Action    │  Export button, preset, or auto-save trigger
│  (UI Trigger)    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  ExportManager   │  Extract UI config (format, channels, options)
│   (Coordinator)  │  Apply presets (Quick CSV, Analysis, Publication)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ RecordingManager │  Orchestrate recording lifecycle
│  (Orchestrator)  │  • Start/stop recording
└────────┬─────────┘  • Trigger auto-save
         │            • Manage metadata
         ▼
┌──────────────────┐
│  DataCollector   │  In-memory data accumulation
│   (Aggregator)   │  • Raw data points (channel, time, value)
└────────┬─────────┘  • Cycles, flags, events
         │            • Analysis results
         ▼
┌──────────────────┐
│  ExcelExporter   │  Format-specific file I/O
│  (File Writer)   │  • Multi-sheet Excel workbooks
└────────┬─────────┘  • CSV with wide/long formats
         │            • JSON structured data
         ▼
┌──────────────────┐
│  Data Validator  │  Pre-export validation
│  (Quality Gate)  │  • Check data integrity
└────────┬─────────┘  • Verify array lengths
         │            • Detect NaN/Inf
         ▼
┌──────────────────┐
│  Atomic Write    │  Safe file operations
│   (Temp + Rename)│  • Write to temp file
└────────┬─────────┘  • Atomic rename on success
         │            • Prevent partial writes
         ▼
┌──────────────────┐
│   Excel File     │  8 sheets: Raw Data, Channel Data, Cycles,
│   (.xlsx)        │  Flags, Events, Analysis, Metadata, Alignment
└──────────────────┘
```

---

## Export Formats

### 1. Excel Format (.xlsx) - Default

**Purpose**: Comprehensive multi-sheet workbook with all experiment data and metadata.

**File Structure**:
```
experiment_20260202_143022.xlsx
├── Sheet 1: Raw Data (long format)
│   ├── channel | time | value | timestamp
│   └── a       | 0.0  | 645.2 | 1706882222.5
│
├── Sheet 2: Channel Data (wide format)
│   ├── Time A (s) | Channel A (nm) | Time B (s) | Channel B (nm) | ...
│   └── 0.0        | 645.2          | 0.0        | 643.1          | ...
│
├── Sheet 3: Cycles
│   ├── cycle_id | cycle_num | type | name | start_time | duration | concentration | ...
│   └── 1        | 1         | Bind | IgG  | 120.0      | 300.0    | 100 nM        | ...
│
├── Sheet 4: Flags
│   ├── flag_id | time | label | color | note
│   └── 1       | 250.5| Spike | red   | Artifact detected
│
├── Sheet 5: Events
│   ├── elapsed | timestamp           | event
│   └── 120.5   | 2026-02-02 14:32:00 | Injection: Sample A
│
├── Sheet 6: Analysis
│   ├── measurement_id | channel | Ka | Kd | KD | Rmax | ...
│   └── 1              | a       | ... | ... | ... | ...
│
├── Sheet 7: Metadata
│   ├── key            | value
│   ├── user           | JohnDoe
│   ├── experiment     | Antibody Binding
│   ├── chip_id        | AU-001
│   └── temperature_c  | 25.0
│
└── Sheet 8: Alignment (Edits tab settings)
    ├── Cycle_Index | Channel_Filter | Time_Shift_s
    └── 1           | A              | -0.5
```

**Advantages**:
- All data in one file (no fragmentation)
- Human-readable in Excel/LibreOffice
- Multiple views of same data (long vs wide format)
- Metadata preserved in dedicated sheet
- Easy import for analysis tools (GraphPad Prism, Origin, MATLAB)

**Use Cases**:
- Lab notebooks and archiving
- Sharing with collaborators
- Direct analysis in Excel
- Publication supplementary data

---

### 2. CSV Format (.csv)

**Purpose**: Plain text export for universal compatibility.

**Export Modes**:

#### **Mode A: Single Combined CSV** (Default)
```
experiment_20260202_143022.csv
Time (s), Channel A (nm), Channel B (nm), Channel C (nm), Channel D (nm)
0.0,      645.2,          643.1,          0.0,            0.0
1.0,      645.3,          643.2,          0.0,            0.0
2.0,      645.4,          643.3,          0.0,            0.0
```

**Format**: Wide format (time + all channels)
**Size**: Compact (one file)
**Use Case**: Quick export for plotting software

#### **Mode B: Separate CSV per Channel**
```
experiment_20260202_143022_ChA.csv
Time (s), Wavelength (nm)
0.0,      645.2
1.0,      645.3
2.0,      645.4

experiment_20260202_143022_ChB.csv
Time (s), Wavelength (nm)
0.0,      643.1
1.0,      643.2
2.0,      643.3
```

**Format**: Long format (time + single channel)
**Size**: Multiple files
**Use Case**: Per-channel analysis workflows

#### **Mode C: TraceDrawer Format** (Legacy)
```
# Experiment: Antibody Binding
# User: JohnDoe
# Date: 2026-02-02 14:30:22
# Chip ID: AU-001
# Temperature: 25.0 C
# Software: ezControl v2.0.1
X_RawDataA, Y_RawDataA, X_RawDataB, Y_RawDataB, ...
0.0,        645.2,      0.0,        643.1,      ...
```

**Format**: Wide format with metadata header
**Size**: Single file
**Use Case**: Import into TraceDrawer or legacy analysis software

**Advantages**:
- Universal compatibility (any spreadsheet/analysis software)
- Plain text (easy to parse programmatically)
- Lightweight (smaller file size than Excel)
- Version control friendly (text diff)

**Limitations**:
- Single sheet (no cycles, flags, events in same file)
- Metadata in header comments (not structured)

---

### 3. JSON Format (.json)

**Purpose**: Structured data export for programmatic access.

**File Structure**:
```json
{
  "metadata": {
    "export_date": "2026-02-02T14:30:22",
    "format": "json",
    "precision": 4,
    "channels": "A, B, C, D",
    "user": "JohnDoe",
    "experiment": "Antibody Binding",
    "chip_id": "AU-001",
    "temperature_c": 25.0
  },
  "channel_a": {
    "raw": {
      "time": [0.0, 1.0, 2.0, ...],
      "wavelength": [645.2, 645.3, 645.4, ...]
    },
    "processed": {
      "time": [0.0, 1.0, 2.0, ...],
      "spr": [0.0, 0.1, 0.2, ...]
    }
  },
  "channel_b": { ... },
  "cycles": [
    {
      "cycle_id": 1,
      "cycle_num": 1,
      "type": "Bind",
      "name": "IgG",
      "start_time": 120.0,
      "duration": 300.0,
      "concentration": "100 nM"
    }
  ],
  "events": [
    {
      "elapsed": 120.5,
      "timestamp": "2026-02-02T14:32:00",
      "event": "Injection: Sample A"
    }
  ]
}
```

**Advantages**:
- Structured data (easy programmatic parsing)
- Hierarchical organization
- Native support in Python, JavaScript, R
- API-friendly

**Use Cases**:
- Data pipelines and automation
- Web applications
- Database import
- Machine learning training data

---

## File Naming Conventions

### Automatic Naming Scheme

**Pattern**: `{user}_{experiment}_{date}_{time}_{suffix}.{ext}`

**Components**:
```
JohnDoe_AntibodyBinding_20260202_143022_ChA.csv
└─────┘ └──────────────┘ └──────┘ └────┘ └─┘ └─┘
  User   Experiment Name   Date    Time  Suffix Ext
```

**Rules**:
1. **User**: Current user profile (see User Profile Manager)
2. **Experiment**: Sanitized experiment name (spaces → underscores, special chars removed)
3. **Date**: YYYYMMDD format
4. **Time**: HHMMSS format (24-hour)
5. **Suffix**: Optional (e.g., `ChA`, `Raw`, `Filtered`)
6. **Extension**: `.xlsx`, `.csv`, `.json`

**Examples**:
```
# Single Excel export
JohnDoe_AntibodyBinding_20260202_143022.xlsx

# Multiple CSV exports
JohnDoe_AntibodyBinding_20260202_143022_ChA.csv
JohnDoe_AntibodyBinding_20260202_143022_ChB.csv

# Filtered data
JohnDoe_AntibodyBinding_20260202_143022_Filtered.csv

# Segments
JohnDoe_AntibodyBinding_20260202_143022_Segments.csv
```

### Manual Naming

**File Dialog**: User can override automatic naming via file save dialog.

**Sanitization**: Special characters automatically removed/replaced:
```
Input:  "My Experiment (Test #1) @ 25°C"
Output: "My_Experiment_Test_1_25C"
```

**Forbidden Characters**: `<>:"/\|?*`

---

## Export Presets

### 1. Quick CSV Preset

**Purpose**: Fast export for immediate plotting/analysis.

**Configuration**:
```python
{
    "preset": "quick_csv",
    "format": "csv",
    "channels": ["a", "b", "c", "d"],  # All channels
    "include_metadata": False,
    "include_events": False,
    "include_cycles": False,
    "data_types": {
        "raw": True,
        "processed": False,
        "summary": False
    }
}
```

**Output**: Single CSV file with time + wavelength columns.

**Use Case**: "I need a quick CSV to plot in Origin/GraphPad right now."

---

### 2. Analysis Preset

**Purpose**: Export for detailed analysis with summary statistics.

**Configuration**:
```python
{
    "preset": "analysis",
    "format": "excel",
    "channels": ["a", "b", "c", "d"],
    "include_metadata": True,
    "include_events": True,
    "include_cycles": True,
    "data_types": {
        "raw": False,
        "processed": True,  # SPR values in RU
        "summary": True     # Summary statistics
    }
}
```

**Output**: Excel workbook with processed data, cycles, and analysis summary.

**Use Case**: "I need to analyze binding kinetics with all experiment details."

---

### 3. Publication Preset

**Purpose**: High-precision export for publication supplementary data.

**Configuration**:
```python
{
    "preset": "publication",
    "format": "excel",
    "channels": ["a", "b", "c", "d"],
    "precision": 5,  # 5 decimal places
    "include_metadata": True,
    "include_events": True,
    "include_cycles": True,
    "timestamp_format": "ISO8601",  # 2026-02-02T14:30:22.123Z
    "data_types": {
        "raw": True,
        "processed": True,
        "summary": True
    }
}
```

**Output**: Excel workbook with maximum precision and complete metadata.

**Use Case**: "I need publication-quality data with full traceability."

---

## Real-Time Recording

### Recording Manager

**Purpose**: Continuous data logging during live acquisition.

**Architecture**:
```python
class RecordingManager:
    """Orchestrates recording lifecycle"""

    def __init__(self, data_mgr, buffer_mgr):
        self.data_collector = DataCollector()  # In-memory accumulation
        self.excel_exporter = ExcelExporter()  # File I/O
        self.is_recording = False
        self.current_file = None

    def start_recording(self, filename=None, time_offset=0.0):
        """Start recording to file (or memory if no filename)"""
        self.is_recording = True
        self.current_file = filename
        self.recording_start_offset = time_offset  # For t=0 export
        self.data_collector.start_collection()

    def log_data_point(self, channel, time, wavelength):
        """Log single data point during acquisition"""
        self.data_collector.add_data_point(
            channel=channel,
            time=time - self.recording_start_offset,  # Normalize to t=0
            value=wavelength
        )

    def log_event(self, event, time=None):
        """Log experiment event (injection, valve switch)"""
        timestamp = time or current_time()
        self.data_collector.add_event(timestamp, event)

    def stop_recording(self):
        """Stop recording and save final file"""
        if self.current_file:
            self._save_to_file()
        self.is_recording = False
```

### Auto-Save Feature

**Purpose**: Periodic file saves during long experiments to prevent data loss.

**Configuration**:
```python
self.auto_save_interval = 60  # seconds
self.last_save_time = 0

def _check_auto_save(self):
    """Check if auto-save is needed"""
    if not self.is_recording or not self.current_file:
        return

    current_time = time.time()
    if current_time - self.last_save_time > self.auto_save_interval:
        self._save_to_file()
        self.last_save_time = current_time
        logger.info("Auto-saved recording")
```

**Default**: 60 seconds
**Configurable**: User can adjust interval
**Benefits**: Prevents data loss from crashes, power failures

---

## Data Collection Layer

### DataCollector Class

**Purpose**: In-memory accumulation of experiment data during recording.

**Data Structures**:
```python
class DataCollector:
    """Accumulates experiment data in memory"""

    def __init__(self):
        # Raw data points (long format)
        self.raw_data_rows = []  # [{channel, time, value, timestamp}, ...]

        # Experiment markers
        self.cycles = []         # [cycle_dict, ...]
        self.flags = []          # [flag_dict, ...]
        self.events = []         # [(timestamp, event_str), ...]

        # Analysis results
        self.analysis_results = []  # [result_dict, ...]

        # Metadata
        self.metadata = {}       # {key: value, ...}

        # State
        self.collection_start_time = None

    def add_data_point(self, channel, time, value, timestamp=None):
        """Add single data point"""
        self.raw_data_rows.append({
            "channel": channel,
            "time": time,
            "value": value,
            "timestamp": timestamp or current_time()
        })

    def add_cycle(self, cycle_data):
        """Add cycle marker"""
        self.cycles.append({
            "cycle_id": cycle_data.get("id"),
            "cycle_num": cycle_data.get("num"),
            "type": cycle_data.get("type"),
            "name": cycle_data.get("name"),
            "start_time": cycle_data.get("start"),
            "end_time": cycle_data.get("end"),
            "duration": cycle_data.get("duration"),
            "concentration": cycle_data.get("concentration"),
            "note": cycle_data.get("note", "")
        })

    def add_flag(self, flag_data):
        """Add flag marker"""
        self.flags.append({
            "flag_id": flag_data.get("id"),
            "time": flag_data.get("time"),
            "label": flag_data.get("label"),
            "color": flag_data.get("color", "red"),
            "note": flag_data.get("note", "")
        })

    def add_event(self, timestamp, event):
        """Log experiment event"""
        self.events.append((timestamp, event))

    def update_metadata(self, key, value):
        """Update metadata"""
        self.metadata[key] = value
```

**Memory Efficiency**:
- Data stored in lists (not NumPy arrays) for fast append
- Converted to pandas DataFrame only during export
- Memory footprint: ~24 bytes per data point
- Typical experiment (1 hour @ 4 Hz × 4 channels): ~3.5 MB

---

## Excel Export Layer

### ExcelExporter Class

**Purpose**: Format-specific file I/O for Excel workbooks.

**Multi-Sheet Export**:
```python
class ExcelExporter:
    """Handles Excel file generation"""

    def export_to_excel(
        self,
        filepath: Path,
        raw_data_rows: list[dict],
        cycles: list[dict],
        flags: list[dict],
        events: list[tuple],
        analysis_results: list[dict],
        metadata: dict,
        recording_start_time: float,
        alignment_data: dict = None
    ):
        """Export all data to Excel with multiple sheets"""
        import pandas as pd

        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            # Sheet 1: Raw Data (long format)
            if raw_data_rows:
                df_raw = pd.DataFrame(raw_data_rows)
                df_raw.to_excel(writer, sheet_name="Raw Data", index=False)

            # Sheet 2: Channel Data (wide format)
            if raw_data_rows:
                df_wide = self._create_wide_format(raw_data_rows)
                df_wide.to_excel(writer, sheet_name="Channel Data", index=False)

            # Sheet 3: Cycles
            if cycles:
                df_cycles = pd.DataFrame(cycles)
                df_cycles.to_excel(writer, sheet_name="Cycles", index=False)

            # Sheet 4: Flags
            if flags:
                df_flags = pd.DataFrame(flags)
                df_flags.to_excel(writer, sheet_name="Flags", index=False)

            # Sheet 5: Events
            if events:
                df_events = self._format_events(events, recording_start_time)
                df_events.to_excel(writer, sheet_name="Events", index=False)

            # Sheet 6: Analysis
            if analysis_results:
                df_analysis = pd.DataFrame(analysis_results)
                df_analysis.to_excel(writer, sheet_name="Analysis", index=False)

            # Sheet 7: Metadata
            if metadata:
                df_meta = pd.DataFrame([
                    {"key": k, "value": str(v)}
                    for k, v in metadata.items()
                ])
                df_meta.to_excel(writer, sheet_name="Metadata", index=False)

            # Sheet 8: Alignment (Edits tab)
            if alignment_data:
                df_align = self._format_alignment(alignment_data)
                df_align.to_excel(writer, sheet_name="Alignment", index=False)

    def _create_wide_format(self, raw_data_rows):
        """Convert long format to wide format (time + all channels)"""
        df = pd.DataFrame(raw_data_rows)
        channels = df["channel"].unique()

        # Create separate dataframes for each channel
        channel_dfs = []
        for ch in sorted(channels):
            ch_data = df[df["channel"] == ch][["time", "value"]].copy()
            ch_data.columns = [f"Time {ch.upper()} (s)", f"Channel {ch.upper()} (nm)"]
            channel_dfs.append(ch_data.reset_index(drop=True))

        # Concatenate horizontally
        return pd.concat(channel_dfs, axis=1)
```

**Wide Format Example**:
```
Time A (s) | Channel A (nm) | Time B (s) | Channel B (nm) | Time C (s) | Channel C (nm)
0.0        | 645.2          | 0.0        | 643.1          | 0.0        | 0.0
1.0        | 645.3          | 1.0        | 643.2          | 1.0        | 0.0
2.0        | 645.4          | 2.0        | 643.3          | 2.0        | 0.0
```

**Benefits**:
- Each channel has independent time axis (handles async data)
- Easy to plot in Excel (select two columns)
- Compatible with GraphPad Prism import

---

## Data Validation

### Pre-Export Validation

**Purpose**: Ensure data integrity before writing to disk.

**DataValidator Class**:
```python
class DataValidator:
    """Validate data before export"""

    @staticmethod
    def validate_sensorgram(data: dict) -> tuple[bool, str]:
        """Check sensorgram data integrity"""
        errors = []

        # Check structure
        required_keys = ["lambda_times", "lambda_values"]
        for key in required_keys:
            if key not in data:
                errors.append(f"Missing key: {key}")
                return (False, "; ".join(errors))

        # Check data consistency per channel
        for ch in ["a", "b", "c", "d"]:
            times = data["lambda_times"].get(ch, [])
            values = data["lambda_values"].get(ch, [])

            # Length mismatch
            if len(times) != len(values):
                errors.append(
                    f"Ch {ch}: length mismatch "
                    f"(times={len(times)}, values={len(values)})"
                )

            # No data
            if len(times) == 0:
                errors.append(f"Ch {ch}: no data")

            # NaN/Inf check
            if len(values) > 0 and np.any(~np.isfinite(values)):
                errors.append(f"Ch {ch}: contains NaN or Inf")

        return (len(errors) == 0, "; ".join(errors) if errors else "Valid")

    @staticmethod
    def validate_dataframe(df: pd.DataFrame, name: str) -> tuple[bool, str]:
        """Check DataFrame integrity"""
        if df is None:
            return (False, f"{name}: DataFrame is None")

        if df.empty:
            return (False, f"{name}: DataFrame is empty")

        # Check for all-NaN columns
        all_nan_cols = [col for col in df.columns if df[col].isna().all()]
        if all_nan_cols:
            return (False, f"{name}: Columns with all NaN: {all_nan_cols}")

        return (True, "Valid")
```

**Validation Flow**:
```python
# Before export
is_valid, error_msg = DataValidator.validate_sensorgram(data)
if not is_valid:
    logger.error(f"Export validation failed: {error_msg}")
    raise ValueError(f"Invalid data: {error_msg}")

# Proceed with export only if valid
exporter.export_raw_data(data, metadata)
```

**Validation Checks**:
1. **Structure**: Required keys present
2. **Length**: Time and value arrays match
3. **Content**: No NaN/Inf values
4. **Consistency**: All channels have data
5. **Format**: Column names exist

---

## Atomic File Writes

### Problem: Partial File Corruption

**Scenario**: Application crashes mid-write → corrupted Excel file.

**Solution**: Atomic writes using temp file + rename.

### Implementation

```python
def _atomic_write(self, filepath: Path, content_writer, encoding="utf-8"):
    """Write file atomically using temp file + rename"""
    try:
        # Write to temp file in same directory
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            dir=filepath.parent,
            delete=False,
            suffix=".tmp"
        ) as tmp_file:
            content_writer(tmp_file)  # Write all content
            tmp_path = Path(tmp_file.name)

        # Atomic rename (POSIX guarantees atomicity)
        tmp_path.replace(filepath)
        logger.debug(f"File written successfully: {filepath}")

    except Exception as e:
        logger.error(f"Failed to write file {filepath}: {e}")
        raise
```

**Usage**:
```python
# Define content writer
def write_excel(writer):
    df.to_excel(writer, sheet_name="Data", index=False)

# Atomic write
exporter._atomic_write(
    filepath=Path("experiment.xlsx"),
    content_writer=write_excel
)
```

**Benefits**:
- **All-or-nothing**: File is either complete or doesn't exist
- **No corruption**: Crash during write leaves old file intact
- **Thread-safe**: Multiple threads can write different files safely
- **Cross-platform**: Works on Windows, Linux, macOS

---

## Export Manifest

### Purpose: Track Exported Files

**Manifest File**: `experiment_manifest.json`

**Structure**:
```json
{
  "experiment_name": "Antibody Binding",
  "export_timestamp": "2026-02-02T14:30:22",
  "software_version": "ezControl v2.0.1",
  "exported_files": [
    {
      "filepath": "raw_data/JohnDoe_AntibodyBinding_20260202_143022.csv",
      "format": "csv_simple",
      "checksum": "5d41402abc4b2a76b9719d911017c592",
      "row_count": 14400,
      "timestamp": "2026-02-02T14:30:22",
      "size_bytes": 578560
    },
    {
      "filepath": "filtered_data/JohnDoe_AntibodyBinding_20260202_143022_Filtered.csv",
      "format": "csv_simple",
      "checksum": "7d793037a0760186574b0282f2f435e7",
      "row_count": 14200,
      "timestamp": "2026-02-02T14:31:05",
      "size_bytes": 569600
    }
  ]
}
```

**Fields**:
- `filepath`: Relative path from export directory
- `format`: Export format used
- `checksum`: MD5 hash for integrity verification
- `row_count`: Number of data rows
- `timestamp`: Export time (ISO 8601)
- `size_bytes`: File size

**Use Cases**:
1. **Integrity Check**: Verify file hasn't been tampered with
2. **Audit Trail**: Track all exports from experiment
3. **Provenance**: Link exported files to source experiment
4. **Deduplication**: Detect if same data exported twice

---

## User Profile Manager

### Purpose: Track User Information in Exports

**User Profiles**: Stored in `settings/user_profiles.json`

**Profile Structure**:
```json
{
  "profiles": [
    {
      "username": "JohnDoe",
      "full_name": "John Doe",
      "email": "john.doe@example.com",
      "institution": "University of Science",
      "department": "Biochemistry",
      "created": "2026-01-15T09:00:00",
      "last_used": "2026-02-02T14:30:22"
    }
  ],
  "active_user": "JohnDoe"
}
```

**Integration with Export**:
```python
# User selection in Export tab
user_manager = UserProfileManager()
active_user = user_manager.get_active_user()

# Include in metadata
metadata = {
    "user": active_user["username"],
    "user_email": active_user["email"],
    "institution": active_user["institution"],
    ...
}

# Include in filename
filename = f"{active_user['username']}_{experiment_name}_{timestamp}.xlsx"
```

**Benefits**:
- **Traceability**: Know who performed each experiment
- **Lab Notebooks**: Link data to researcher
- **Publications**: Track data provenance
- **Compliance**: Audit trail for regulated environments

---

## Export Strategies (Strategy Pattern)

### Architecture

**Purpose**: Pluggable export formats using strategy pattern.

```python
class ExportStrategy:
    """Base class for export strategies"""

    def export(self, file_path: str, export_data: dict, config: dict):
        """Export data to file"""
        raise NotImplementedError("Subclasses must implement export()")

    def _build_metadata(self, config: dict) -> dict:
        """Build common metadata dict"""
        return {
            "export_date": datetime.now().strftime("%Y-%m-%d"),
            "export_time": datetime.now().strftime("%H:%M:%S"),
            "format": config.get("format", "unknown"),
            "precision": config.get("precision", 4),
            "channels": ", ".join(config.get("channels", []))
        }
```

### Concrete Strategies

#### 1. ExcelExportStrategy
```python
class ExcelExportStrategy(ExportStrategy):
    """Export to Excel workbook"""

    def export(self, file_path, export_data, config):
        import pandas as pd

        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            # Export each channel's data
            for ch, ch_data in export_data.items():
                if "raw" in ch_data:
                    sheet_name = f"Channel_{ch.upper()}_Raw"
                    ch_data["raw"].to_excel(writer, sheet_name=sheet_name)

                if "processed" in ch_data:
                    sheet_name = f"Channel_{ch.upper()}_Processed"
                    ch_data["processed"].to_excel(writer, sheet_name=sheet_name)

            # Add metadata sheet
            if config.get("include_metadata"):
                metadata = self._build_metadata(config)
                pd.DataFrame([metadata]).to_excel(writer, sheet_name="Metadata")
```

#### 2. CSVExportStrategy
```python
class CSVExportStrategy(ExportStrategy):
    """Export to CSV (combined all channels)"""

    def export(self, file_path, export_data, config):
        import pandas as pd

        # Combine all channels into one CSV
        combined_data = {}

        for ch, ch_data in export_data.items():
            if "raw" in ch_data:
                df = ch_data["raw"]
                if "Time (s)" in df.columns:
                    if "Time (s)" not in combined_data:
                        combined_data["Time (s)"] = df["Time (s)"]
                    # Add channel column
                    combined_data[f"Channel {ch.upper()} (nm)"] = df["Wavelength (nm)"]

        combined_df = pd.DataFrame(combined_data)
        combined_df.to_csv(file_path, index=False)
```

#### 3. JSONExportStrategy
```python
class JSONExportStrategy(ExportStrategy):
    """Export to JSON"""

    def export(self, file_path, export_data, config):
        import json

        # Convert DataFrames to dictionaries
        json_data = {}
        for ch, ch_data in export_data.items():
            json_data[f"channel_{ch}"] = {}
            if "raw" in ch_data:
                json_data[f"channel_{ch}"]["raw"] = ch_data["raw"].to_dict("list")
            if "processed" in ch_data:
                json_data[f"channel_{ch}"]["processed"] = ch_data["processed"].to_dict("list")

        # Add metadata
        if config.get("include_metadata"):
            json_data["metadata"] = self._build_metadata(config)

        with open(file_path, "w") as f:
            json.dump(json_data, f, indent=2)
```

### Strategy Selection

```python
# Export manager selects strategy based on format
format_strategies = {
    "excel": ExcelExportStrategy(),
    "csv": CSVExportStrategy(),
    "json": JSONExportStrategy()
}

# Execute export with selected strategy
format_type = config.get("format", "excel")
strategy = format_strategies[format_type]
strategy.export(file_path, export_data, config)
```

**Benefits**:
- **Open/Closed Principle**: Add new formats without modifying existing code
- **Single Responsibility**: Each strategy handles one format
- **Testability**: Test each format independently
- **Flexibility**: Easy to add HDF5, Parquet, SQL, etc.

---

## API Reference

### RecordingManager

```python
from affilabs.core.recording_manager import RecordingManager

# Initialize
recorder = RecordingManager(data_mgr, buffer_mgr)

# Start recording
recorder.start_recording(
    filename="path/to/experiment.xlsx",  # Or None for memory-only
    time_offset=120.5  # Normalize times to t=0
)

# Log data during acquisition
recorder.log_data_point(
    channel='a',
    time=125.5,
    wavelength=645.2
)

# Log experiment events
recorder.log_event("Injection: Sample A", time=130.0)

# Update metadata
recorder.update_metadata("chip_id", "AU-001")
recorder.update_metadata("temperature_c", 25.0)

# Add cycle marker
recorder.add_cycle({
    "id": 1,
    "num": 1,
    "type": "Bind",
    "name": "IgG",
    "start": 120.0,
    "end": 420.0,
    "duration": 300.0,
    "concentration": "100 nM"
})

# Add flag marker
recorder.add_flag({
    "id": 1,
    "time": 250.5,
    "label": "Spike",
    "color": "red",
    "note": "Artifact detected"
})

# Stop recording (triggers final save)
recorder.stop_recording()

# Get recording info
info = recorder.get_recording_info()
print(info["data_points"])  # Number of points collected
print(info["duration"])     # Recording duration in seconds
```

### ExcelExporter

```python
from affilabs.services.excel_exporter import ExcelExporter
from pathlib import Path

# Initialize
exporter = ExcelExporter()

# Export to Excel
exporter.export_to_excel(
    filepath=Path("experiment.xlsx"),
    raw_data_rows=[
        {"channel": "a", "time": 0.0, "value": 645.2, "timestamp": 1706882222.5},
        {"channel": "a", "time": 1.0, "value": 645.3, "timestamp": 1706882223.5},
        ...
    ],
    cycles=[
        {"cycle_id": 1, "cycle_num": 1, "type": "Bind", "name": "IgG", ...},
        ...
    ],
    flags=[
        {"flag_id": 1, "time": 250.5, "label": "Spike", "color": "red", ...},
        ...
    ],
    events=[
        (1706882350.0, "Injection: Sample A"),
        ...
    ],
    analysis_results=[
        {"measurement_id": 1, "channel": "a", "Ka": 1.2e5, "Kd": 3.4e-3, ...},
        ...
    ],
    metadata={
        "user": "JohnDoe",
        "experiment": "Antibody Binding",
        "chip_id": "AU-001",
        "temperature_c": 25.0
    },
    recording_start_time=1706882222.0,
    alignment_data={
        1: {"channel": "A", "shift": -0.5},
        2: {"channel": "All", "shift": 0.0}
    }
)

# Load from Excel
data = exporter.load_from_excel(Path("experiment.xlsx"))
print(data["raw_data"])  # pandas DataFrame
print(data["cycles"])    # List of cycle dicts
print(data["metadata"])  # Metadata dict
```

### DataExporter

```python
from affilabs.utils.data_exporter import DataExporter
from pathlib import Path

# Initialize
exporter = DataExporter(
    base_dir="C:/Data/Experiments/2026-02-02",
    experiment_name="Antibody Binding"
)

# Export raw data
exporter.export_raw_data(
    data={
        "lambda_times": {"a": [0.0, 1.0, 2.0], ...},
        "lambda_values": {"a": [645.2, 645.3, 645.4], ...}
    },
    metadata=metadata_widget,  # Optional
    references=[645.0, 643.0, 0.0, 0.0]  # Reference wavelengths
)

# Export filtered data
exporter.export_filtered_data(
    data={
        "lambda_times": {"a": [0.0, 1.0, 2.0], ...},
        "lambda_values": {"a": [645.2, 645.3, 645.4], ...},
        "filt": True
    },
    metadata=metadata_widget
)

# Export segments
exporter.export_segments(
    segments=[
        {"start": 100.0, "end": 200.0, "label": "Baseline"},
        {"start": 200.0, "end": 500.0, "label": "Binding"},
        ...
    ],
    value_list=wavelength_values,
    ts_list=time_values
)

# Save manifest
exporter.save_manifest()

# Get exported files list
files = exporter.exported_files
for f in files:
    print(f"{f.filepath} - {f.checksum} - {f.row_count} rows")
```

### ExportManager

```python
from affilabs.managers.export_manager import ExportManager

# Initialize (inside main window)
self.export_manager = ExportManager(self)

# Quick CSV preset
self.export_manager.on_quick_csv_preset()
# Emits: export_requested signal with CSV config

# Analysis preset
self.export_manager.on_analysis_preset()
# Emits: export_requested signal with Excel + analysis config

# Publication preset
self.export_manager.on_publication_preset()
# Emits: export_requested signal with high-precision config

# Custom export
self.export_manager.on_export_data()
# Emits: export_requested signal with UI-configured settings

# Get current config
config = self.export_manager.get_export_config()
print(config["format"])          # "excel" / "csv" / "json"
print(config["channels"])        # ["a", "b", "c", "d"]
print(config["include_metadata"])  # True / False
print(config["precision"])       # 4 (decimal places)
```

---

## Troubleshooting

### Issue: Export Fails with "Invalid Data"

**Symptoms**: Export button throws error "Invalid data: Ch a: contains NaN or Inf".

**Diagnosis**:
```python
# Check data validity
from affilabs.utils.data_exporter import DataValidator

is_valid, error_msg = DataValidator.validate_sensorgram(data)
if not is_valid:
    print(f"Validation failed: {error_msg}")

# Inspect problematic channel
import numpy as np
wavelengths = data["lambda_values"]["a"]
nan_count = np.sum(np.isnan(wavelengths))
inf_count = np.sum(np.isinf(wavelengths))
print(f"NaN count: {nan_count}, Inf count: {inf_count}")
```

**Solutions**:
```python
# Solution 1: Remove NaN/Inf values
wavelengths_clean = np.where(np.isfinite(wavelengths), wavelengths, 0)

# Solution 2: Interpolate missing values
from scipy.interpolate import interp1d
mask = np.isfinite(wavelengths)
f = interp1d(times[mask], wavelengths[mask], fill_value="extrapolate")
wavelengths_interp = f(times)

# Solution 3: Filter data before export
data["lambda_values"]["a"] = wavelengths_clean
```

### Issue: Excel File Corrupted After Crash

**Symptoms**: Excel file won't open after application crash.

**Diagnosis**:
```bash
# Check if temp file exists
ls experiment.xlsx.tmp

# Verify file size
ls -lh experiment.xlsx
# If 0 bytes → corruption during write
```

**Solutions**:
```python
# Solution 1: Use atomic writes (default in current version)
# Already implemented - check if enabled:
# exporter._atomic_write(filepath, content_writer)

# Solution 2: Recover from auto-save
# Look for auto-save files (created every 60 seconds)
ls *_autosave_*.xlsx

# Solution 3: Prevent corruption
# Enable auto-save with shorter interval
recorder.auto_save_interval = 30  # Save every 30 seconds
```

### Issue: Export Takes Too Long

**Symptoms**: Export button hangs for 10+ seconds on large datasets.

**Diagnosis**:
```python
import time

# Time individual steps
t0 = time.time()
df = pd.DataFrame(raw_data_rows)
t1 = time.time()
print(f"DataFrame creation: {t1 - t0:.2f} s")

t2 = time.time()
df.to_excel(writer, sheet_name="Data")
t3 = time.time()
print(f"Excel write: {t3 - t2:.2f} s")

# Check data size
print(f"Data points: {len(raw_data_rows)}")
print(f"DataFrame memory: {df.memory_usage().sum() / 1e6:.1f} MB")
```

**Solutions**:
```python
# Solution 1: Export to CSV instead (10x faster)
config["format"] = "csv"

# Solution 2: Downsample data before export
# Export every Nth point for large datasets
stride = max(1, len(raw_data_rows) // 100_000)  # Max 100k points
raw_data_subset = raw_data_rows[::stride]

# Solution 3: Use background thread for export
import threading

def export_in_background():
    exporter.export_to_excel(...)

thread = threading.Thread(target=export_in_background, daemon=True)
thread.start()
# UI remains responsive
```

### Issue: Filename Too Long Error

**Symptoms**: Export fails with "Filename too long" error (Windows limit: 260 chars).

**Diagnosis**:
```python
filename = generate_filename(user, experiment, timestamp)
print(f"Filename length: {len(filename)}")
# > 260 → ERROR on Windows
```

**Solutions**:
```python
# Solution 1: Shorten experiment name
experiment_name = "Antibody Binding"[:50]  # Max 50 chars

# Solution 2: Use short date format
timestamp = datetime.now().strftime("%Y%m%d")  # Instead of "%Y%m%d_%H%M%S"

# Solution 3: Save to shorter path
export_dir = Path("C:/Data")  # Instead of C:/Users/JohnDoe/Documents/Experiments/...
```

---

## Summary

The ezControl data output system provides:

✅ **Multi-Format Export**: Excel (default), CSV, JSON with pluggable strategy pattern
✅ **Real-Time Recording**: Continuous logging during acquisition with auto-save
✅ **Data Validation**: Pre-export integrity checks (NaN/Inf detection, length matching)
✅ **Atomic Writes**: Prevent file corruption via temp file + rename
✅ **Export Manifest**: Track all exported files with checksums and metadata
✅ **User Profiles**: Link data to researchers for traceability
✅ **Export Presets**: Quick CSV, Analysis, Publication presets
✅ **Comprehensive Metadata**: Experiment details, device config, analysis results

**Key Files**:
- [recording_manager.py](affilabs/core/recording_manager.py) - Recording orchestration
- [excel_exporter.py](affilabs/services/excel_exporter.py) - Excel file I/O
- [data_exporter.py](affilabs/utils/data_exporter.py) - Validation and atomic writes
- [export_manager.py](affilabs/managers/export_manager.py) - UI config extraction
- [export_strategies.py](affilabs/utils/export_strategies.py) - Format strategies
- [data_collector.py](affilabs/services/data_collector.py) - In-memory accumulation
- [user_profile_manager.py](affilabs/services/user_profile_manager.py) - User tracking

**Current Production Format**: Excel (.xlsx) with 8 sheets (Raw Data, Channel Data, Cycles, Flags, Events, Analysis, Metadata, Alignment).

**Export Workflow**: User clicks Export → ExportManager extracts config → RecordingManager orchestrates → DataCollector provides data → ExcelExporter writes file → Atomic write ensures integrity → Manifest tracks export.
