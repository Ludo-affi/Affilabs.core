# AffiLabs SPR Software - Workflow Architecture v2.0

## Executive Summary
The software follows a two-phase workflow: **Capture** (Live tab) and **Analysis** (Edit tab). This document defines the clean separation between raw data collection and post-experiment analysis.

---

## Phase 1: Data Capture (Live Tab)

### Purpose
Record raw experimental data with minimal processing. Focus on real-time acquisition, visualization, and annotation during the experiment.

### Responsibilities
1. **Real-time data acquisition**
   - Stream wavelength data from spectrometer (4 channels: A, B, C, D)
   - Display live sensorgram with automatic baseline correction
   - Apply reference channel subtraction (if configured)

2. **Experimental metadata**
   - Execute queued cycle method (baseline, binding, kinetic, regeneration, etc.)
   - Track cycle boundaries (start/end times)
   - Record concentration values and units per cycle
   - Capture user flags (injection markers, wash events, spikes)
   - Store operator notes per cycle

3. **Method execution**
   - Load/save method files (sequence of cycles)
   - Control pump injections (if connected)
   - Execute timed cycles with automatic progression
   - Display queue status and progress

### What Gets Saved (Raw Data Export)
**File format:** Excel (.xlsx) with multiple sheets

**Sheet 1: Raw Data (Long Format)**
| Column | Description |
|--------|-------------|
| Time | Elapsed time in seconds |
| Channel | A, B, C, or D |
| Value | Wavelength shift in nm (raw sensor output) |

**Sheet 2: Per-Channel Format**
| Columns | Description |
|---------|-------------|
| Time_A, A, Time_B, B, Time_C, C, Time_D, D | Separate time/value columns per channel |

**Sheet 3: Cycle Table (Minimal)**
| Column | Description |
|--------|-------------|
| Cycle # | Cycle number |
| Type | Baseline, Binding, Kinetic, Regeneration, etc. |
| Duration (min) | Cycle length |
| Start Time (s) | When cycle started |
| Concentration | Analyte concentration |
| Units | nM, µM, mg/mL, etc. |
| ΔSPR | **NEW:** Delta SPR values (A:val B:val C:val D:val) |
| Flags | **NEW:** Event markers with times (▲120s ■250s) |
| Notes | User-entered notes |
| Cycle ID | Unique identifier |

**Sheet 4: Export Info**
- Export timestamp
- Data point count
- Channel list
- Software version

### Key Constraints
- **Immutable raw data**: Once saved, raw wavelength data is never modified
- **No analysis**: No curve fitting, kinetics, or advanced processing
- **Timestamped truth**: Raw data file is the source of truth for "what happened"

### User Actions
- ▶️ **Start Run** → Begin queued cycle execution
- 🚩 **Add Flag** → Right-click on graph to mark injection/wash/spike
- 📝 **Add Note** → Type notes for current cycle
- 💾 **Save Raw Data** → Export timestamped data to Excel
- 📤 **Send to Edits** → Copy current data to Edit tab for analysis

---

## Phase 2: Analysis & Annotation (Edit Tab)

### Purpose
Load raw data, perform analysis, annotate cycles with calculated metrics, validate quality, and export comprehensive results.

### Responsibilities
1. **Data loading**
   - Load raw data files from Live tab exports
   - Load previously-analyzed cycle tables (re-editable)
   - Display all cycles in scrollable table

2. **Cycle analysis**
   - **Delta SPR calculation**: Place cursors on sensorgram → measure binding response (start vs end value)
   - Auto-save ΔSPR to selected cycle when cursors move
   - Display ΔSPR bar chart for all 4 channels

3. **Alignment & correction**
   - Time-shift individual cycles or channels (fine adjustment slider)
   - Apply shifts in real-time (no "Apply" button needed)
   - Reference channel subtraction (per-cycle or global)

4. **Validation & QC**
   - Flag low-quality cycles
   - Mark outliers
   - Add QC notes

5. **Metadata enrichment**
   - Display experiment metadata (date, user, device)
   - Sensor type annotation
   - Concentration range summary

### What Gets Exported (Analysis Export)
**File format:** Excel (.xlsx) with annotated cycle table

**Primary Export: Cycle Analysis Table**
| Column | Description | Source |
|--------|-------------|--------|
| Cycle # | Sequential number | Original |
| Type | Cycle type | Original |
| Duration (min) | Cycle length | Original |
| Time | Duration @ start time | Calculated |
| Concentration | Analyte conc | Original |
| Units | nM, µM, etc. | Original |
| **ΔSPR** | **A:120 B:150 C:95 D:110** | **Calculated (cursor-based)** |
| Flags | Event markers (▲120s ■250s) | Original + new |
| Notes | User notes | Original + edited |
| Cycle ID | Unique ID | Original |
| **Alignment Shift (s)** | Time correction applied | **Calculated** |
| **Ref Channel** | Reference subtraction | **Analysis setting** |
| **QC Status** | Pass/Fail/Review | **Validation** |

**Optional: Re-export raw data** (if needed for re-analysis)

### Key Features
- **Non-destructive**: Original raw data files remain unchanged
- **Repeatable**: Can reload raw data and re-analyze with different settings
- **Editable**: Load previously-exported cycle tables to continue analysis
- **Comprehensive**: Export includes all annotations, calculations, and QC flags

### User Actions
- 📂 **Load Data** → Import raw data or previous analysis
- 🎯 **Place Cursors** → Click & drag to measure ΔSPR (auto-saves)
- ⚖️ **Align Cycles** → Drag slider for real-time shift adjustment
- ✅ **Validate** → Mark cycles as pass/fail
- 💾 **Export Analysis** → Save annotated cycle table to Excel

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        LIVE TAB                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐ │
│  │ Record   │ → │ Annotate │ → │ Flag     │ → │ Save    │ │
│  │ Raw Data │   │ Cycles   │   │ Events   │   │ Raw.xlsx│ │
│  └──────────┘   └──────────┘   └──────────┘   └─────────┘ │
└─────────────────────────────────────────────────────────────┘
                           ↓
                    Raw_Data_20260206.xlsx
                    (Immutable source of truth)
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                        EDIT TAB                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐ │
│  │ Load     │ → │ Analyze  │ → │ Validate │ → │ Export  │ │
│  │ Raw Data │   │ (ΔSPR,   │   │ QC       │   │ Analysis│ │
│  │          │   │  Align)  │   │          │   │ .xlsx   │ │
│  └──────────┘   └──────────┘   └──────────┘   └─────────┘ │
└─────────────────────────────────────────────────────────────┘
                           ↓
                Analysis_20260206_Final.xlsx
                (Annotated cycle table with ΔSPR, QC, alignment)
                           ↓
                   ┌──────────────────┐
                   │ Re-loadable for  │
                   │ further editing  │
                   │ or export to     │
                   │ other software   │
                   └──────────────────┘
```

---

## File Organization Structure (GLP/GMP-Compliant)

### Experiment Folder Hierarchy
```
C:/Users/<username>/Documents/Affilabs_Data/
└── 2026-02-06_Antibody_Screening_Lucy/          # Experiment folder
    ├── Raw_Data/                                 # Raw sensor data
    │   ├── Raw_20260206_143052.xlsx
    │   ├── Raw_20260206_150122.xlsx
    │   └── README.txt
    ├── Analysis/                                 # Processed analysis results
    │   ├── Analysis_20260206_153045.xlsx
    │   ├── Analysis_20260206_160212_Final.xlsx
    │   └── README.txt
    ├── Figures/                                  # Exported visualizations
    │   ├── Sensorgram_ChA_20260206.png
    │   ├── ΔSPR_Barchart_20260206.png
    │   └── README.txt
    ├── Method/                                   # Experimental protocols
    │   ├── method_binding_assay.json
    │   └── README.txt
    ├── QC_Reports/                              # Quality control reports
    │   ├── QC_Report_20260206.pdf
    │   └── README.txt
    └── experiment_metadata.json                 # Experiment metadata & audit trail
```

### Experiment Metadata File
`experiment_metadata.json` contains:
- Experiment name, date, description
- Operator name
- Instrument (device ID, sensor type)
- Software version
- File registry (all files created during experiment)
- Audit trail (all actions with timestamps)

**Example:**
```json
{
  "experiment_info": {
    "name": "Antibody Screening",
    "folder_name": "2026-02-06_Antibody_Screening_Lucy",
    "created_date": "2026-02-06T14:30:52",
    "description": "Screening 10 antibody candidates for binding affinity"
  },
  "operator": {
    "name": "Lucy"
  },
  "instrument": {
    "device_id": "FLMT09788",
    "sensor_type": "CM5 Chip"
  },
  "software": {
    "version": "2.0",
    "name": "Affilabs-Core"
  },
  "files": {
    "raw_data": [{"filename": "Raw_20260206_143052.xlsx", ...}],
    "analysis": [{"filename": "Analysis_20260206_153045.xlsx", ...}],
    "figures": [],
    "methods": [],
    "qc_reports": []
  },
  "audit_trail": [
    {"timestamp": "2026-02-06T14:30:52", "action": "Experiment folder created", "user": "Lucy"},
    {"timestamp": "2026-02-06T14:35:10", "action": "File added: raw_data", "filename": "Raw_20260206_143052.xlsx"}
  ]
}
```

---

## File Format Standards

### Raw Data File (from Live)
**Filename:** `Raw_YYYYMMDD_HHMMSS.xlsx`
**Location:** `<ExperimentFolder>/Raw_Data/`

**Required Sheets:**
1. `Raw Data` - Long format timestamped values
2. `Per-Channel Format` - Wide format for plotting
3. `Cycle Table` - Basic cycle info (type, duration, conc, notes, flags)
4. `Export Info` - Metadata (date, version, device)

**Characteristics:**
- Large file (thousands of rows)
- Includes all sensor noise
- No calculated metrics (except baseline-corrected RU conversion)

### Analysis File (from Edit)
**Filename:** `Analysis_<ExperimentName>_<YYYYMMDD_HHMMSS>.xlsx`

**Required Sheets:**
1. `Cycle Analysis` - Full annotated cycle table with ΔSPR, QC, alignment
2. `Metadata` - Experiment metadata (date, user, device, sensor)
3. `Settings` - Analysis settings (ref channel, cursors, filters)

**Optional Sheets:**
4. `Raw Data` - Copy of raw data for traceability
5. `Flags` - Detailed event log

**Characteristics:**
- Small file (one row per cycle)
- Human-readable
- Re-loadable into Edit tab
- Exportable to other analysis software (Prism, Origin, custom tools)

---

## Implementation Checklist

### Live Tab Changes
- [ ] Remove all "Export Analysis" buttons (only "Save Raw Data" allowed)
- [ ] Ensure flags are saved to Cycle Table sheet in raw export
- [ ] Add "Send to Edits" button to copy current data to Edit tab
- [ ] Display clear message: "For analysis, use Edit tab after saving raw data"

### Edit Tab Changes
- [ ] ✅ ΔSPR auto-saves when cursors move (DONE)
- [ ] ✅ Real-time alignment slider (DONE)
- [ ] ✅ Expanded table by default (DONE)
- [ ] ✅ Metadata panel shows Date, User, Device (DONE)
- [ ] Add "Load Analysis File" option (reload previous edits)
- [ ] Export button labeled "Export Analysis" (not "Export Data")
- [ ] Include all cycle annotations in export (ΔSPR, alignment, QC)

### Export Tab Changes
- [ ] Rename to "Report" or merge into Edit export
- [ ] Only show final export options (PDF report, summary plots)
- [ ] Remove raw data export (belongs in Live tab)

---

## User Story Examples

### Story 1: First-time user runs binding assay
1. **Live Tab**: Load method → Start Run → Watch real-time data → Add flag at injection → Save Raw Data → `Raw_Assay1_20260206.xlsx`
2. **Edit Tab**: Load `Raw_Assay1_20260206.xlsx` → Place cursors to measure binding → ΔSPR auto-calculates → Align baseline cycles → Mark bad cycles → Export Analysis → `Analysis_Assay1_20260206.xlsx`
3. **External**: Open `Analysis_Assay1_20260206.xlsx` in Excel → Copy ΔSPR values to Prism for curve fitting

### Story 2: User revisits analysis next day
1. **Edit Tab**: Load `Analysis_Assay1_20260206.xlsx` → Adjust cursor positions → Re-measure ΔSPR → Update QC flags → Export Analysis → `Analysis_Assay1_20260206_v2.xlsx`
2. Analysis history preserved (v1, v2, etc.)

### Story 3: User re-analyzes from scratch
1. **Edit Tab**: Load `Raw_Assay1_20260206.xlsx` (original raw data) → Apply different reference channel → Re-measure ΔSPR → Export Analysis → `Analysis_Assay1_Reprocessed.xlsx`
2. Raw data unchanged, new analysis created

---

## Technical Architecture

### Live Tab Components
- `recording_manager` - Data acquisition
- `buffer_manager` - Live data stream
- `queue_presenter` - Method execution
- `flag_markers` - Event annotation
- **Export:** `_export_raw_data_long_format()`

### Edit Tab Components
- `_loaded_cycles_data` - Cycle data structure
- `_cycle_alignment` - Shift/ref settings per cycle
- `delta_spr_cursors` - Measurement cursors
- `cycle_data_table` - Editable cycle table
- **Export:** `_export_table_data()` + enhanced with ΔSPR/QC

### Shared Data Structures
**Cycle Dictionary:**
```python
{
    'cycle_number': int,
    'type': str,  # 'Baseline', 'Binding', 'Kinetic', etc.
    'duration_minutes': float,
    'start_time': float,
    'end_time': float,
    'concentration_value': float,
    'concentration_units': str,
    'delta_ch1': float,  # ΔSPR for channel A (RU)
    'delta_ch2': float,  # ΔSPR for channel B (RU)
    'delta_ch3': float,  # ΔSPR for channel C (RU)
    'delta_ch4': float,  # ΔSPR for channel D (RU)
    'flag_data': [{'type': 'injection', 'time': 120.5}],
    'note': str,
    'cycle_id': str,
    'shifts': {0: 0.0, 1: -2.3, 2: 0.0, 3: 1.1},  # Per-channel alignment
    'qc_status': 'Pass' | 'Fail' | 'Review',
}
```

---

## Migration Path (Current → v2.0)

### Breaking Changes
- **Live tab exports** no longer include analysis (only raw data)
- **Edit tab** becomes primary analysis interface
- **Export tab** deprecated (merged into Edit)

### Backward Compatibility
- Old raw data files (.xlsx) still loadable in Edit tab
- Old analysis files recognized by presence of ΔSPR columns
- Migration script: Convert old exports to new Analysis format

### User Communication
**v2.0 Release Notes:**
> **Workflow Simplified:**
> - **Live Tab:** Save raw data only (💾 Save Raw Data button)
> - **Edit Tab:** Analyze, annotate, validate, export (💾 Export Analysis button)
> - **Result:** Clear separation between capture and analysis. Your raw data stays pristine. Your analysis is re-editable.

---

## Success Metrics
1. Users understand when to use Live vs Edit (measured by support tickets)
2. Raw data files are never manually edited (data integrity)
3. Analysis files are re-opened for editing (workflow adoption)
4. Export files are compatible with external tools (Prism, Origin, custom Python scripts)

---

**Document Version:** 2.0
**Last Updated:** 2026-02-06
**Author:** AffiLabs Development Team
**Status:** Approved for Implementation
