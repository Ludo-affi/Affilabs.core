# Data Export Architecture

**Status**: Core design documented (Excel primary, extensible)
**Last Updated**: 2026-02-18

## Overview

Affilabs.core exports SPR experimental data in multiple formats tailored to downstream analysis software. The architecture uses a **Strategy Pattern** for format-agnostic extensibility.

```
RecordingManager (data collection)
    ↓
ExcelExporter / export_strategies
    ↓
Multiple output formats (Excel, CSV, JSON, AnIML, TracedRawer, Origin)
    ↓
Downstream analysis (GraphPad Prism, Origin, Affilabs.analyze, etc.)
```

---

## Current Architecture (v2.0.5)

### Layer 1: Export Entry Points

| Location | Purpose | Entry |
|----------|---------|-------|
| **affilabs/managers/export_manager.py** | High-level export config extraction | `get_export_config()` |
| **affilabs/tabs/edits/_export_mixin.py** | User-triggered exports from Edits UI | `_export_selection()`, `_export_for_external_software()` |
| **affilabs/widgets/_dw_export_mixin.py** | DataWindow export operations | (embedded in DataWindow) |
| **affilabs/services/excel_exporter.py** | Core Excel file generation | `export_to_excel()` |
| **affilabs/utils/export_strategies.py** | Strategy implementations for all formats | `ExportStrategy` base class |

### Layer 2: Core Service Classes

#### **ExcelExporter** (`services/excel_exporter.py`)
- Primary exporter; handles Excel workbook generation
- **Input**: Raw data rows, cycles, flags, events, analysis results, metadata
- **Output**: Multi-sheet Excel file (.xlsx)
- **Sheets**: Raw Data, Channel Data, Cycles, Flags, Events, Analysis, Metadata

**Example sheet structure**:
```
Sheet: Raw Data
  Time (s) | Channel A | Channel B | Channel C | Channel D

Sheet: Cycles
  Cycle ID | Type | Start (s) | Duration (s) | Concentration | Notes

Sheet: Flags
  Flag ID | Type | Time (s) | Channel | Confidence | Notes

Sheet: Analysis
  Cycle | Channel | Peak Position | Peak Height | Baseline | ... (measurement fields)
```

#### **ExportStrategy** (`utils/export_strategies.py`)
Base class for pluggable export strategies:

```python
class ExportStrategy:
    def export(self, file_path: str, export_data: dict, config: dict) -> None:
        """Export data to file with format-specific behavior."""
        raise NotImplementedError
```

**Concrete implementations**:
- `ExcelExportStrategy` — Multi-sheet Excel workbooks
- `CSVExportStrategy` — Comma-separated values (combines all channels)
- `JSONExportStrategy` — Structured JSON (channels as objects)
- *Planned*: `AnIMLExportStrategy`, `TracedRawerExportStrategy`, `OriginExportStrategy`

### Layer 3: Configuration & Flow

#### **Export Configuration** (passed through signals)
```python
export_config = {
    "format": "excel",  # or "csv", "json", "animl", "origin", "tracedrawer"
    "data_types": {
        "raw": True,              # Include raw spectrum data
        "processed": True,        # Include processed signals
        "cycles": True,           # Include cycle metadata
        "summary": True,          # Include analysis summary table
    },
    "channels": ["A", "B", "C", "D"],
    "precision": 4,              # Decimal places
    "include_metadata": True,    # Add metadata sheet
    "include_events": True,      # Add event timeline
    "preset": "publication",     # Optional preset name
}
```

#### **Preset Configurations**
- **quick_csv**: All data, CSV format, no metadata
- **analysis**: Processed data + summary, Excel, metadata included
- **publication**: High precision (5 decimals), Excel, comprehensive metadata

---

## Data Flow

```
1. User clicks "Export" in Edits tab
   ↓
2. _export_selection() → get_export_config()
   ↓
3. Config passed via Signal: export_requested.emit(config)
   ↓
4. RecordingManager catches signal → prepares data bundles
   ↓
5. Select strategy based on config["format"]
   ↓
6. Strategy.export(file_path, export_data, config)
   ↓
7. File written to disk
```

### Example: Excel Export

```python
# Edits tab triggers export
exporter = ExcelExporter()
exporter.export_to_excel(
    filepath="/data/experiment_2026_02_18.xlsx",
    raw_data_rows=[{time: 1.0, channel_a: 12345, ...}, ...],
    cycles=[{id: 1, type: "Baseline", start: 0, duration: 300}, ...],
    flags=[{type: "injection", time: 23.5, channel: "A", ...}, ...],
    events=[(1.0, "experiment_started"), (23.5, "injection_flagged"), ...],
    analysis_results=[{cycle: 1, channel: "A", peak_position: 750.2, ...}, ...],
    metadata={"user": "lucia", "device": "FLMT09116", "date": "2026-02-18"},
    recording_start_time=1708286400.0,
)
```

---

## Supported Formats

### ✅ Excel (Primary)
- **Status**: Fully implemented
- **Use case**: Primary analysis format; universal compatibility
- **Features**:
  - Multi-sheet workbooks (raw, processed, cycles, flags, events, analysis, metadata)
  - Precise formatting (decimal places configurable)
  - Chart support via `excel_chart_builder.py`
  - Conditional formatting (alerts, thresholds)

### ✅ CSV
- **Status**: Partially implemented
- **Use case**: Quick data export for scripting
- **Features**:
  - Wide format (time, channel A, channel B, ...)
  - Long format (time, channel, value)
  - Optional metadata inline

### ⚠️ JSON
- **Status**: Planned (strategy stub exists)
- **Use case**: Web/API workflows
- **Proposed structure**:
  ```json
  {
    "metadata": {...},
    "channels": {
      "A": {"raw": [...], "processed": [...]},
      "B": {...}
    },
    "cycles": [...],
    "flags": [...],
    "analysis": [...]
  }
  ```

### 🎯 Future Formats

#### **AnIML** (Analytical Information Markup Language)
- **Target**: Regulatory/compliance workflows (GxP compliance)
- **Implementation**: `AnIMLExportStrategy` in `export_strategies.py`
- **Features**:
  - XML-based standard for analytical data
  - Instrument metadata, sample info, measurement results
  - Audit trail / timestamp validation
- **Resources**: [AnIML Standard](http://www.animl.org/)

#### **Origin** (OriginLab)
- **Target**: OriginLab Pro analysis software
- **Implementation**: `OriginExportStrategy` in `export_strategies.py`
- **Features**:
  - Per-channel worksheets with metadata columns
  - X-Y pairing for SPR dip vs. reference
  - Native plotting import
- **Format**: `.opj` (OriginLab Project)

#### **TracedRawer**
- **Target**: Custom Affilabs trace analysis tool (future)
- **Implementation**: `TracedRawerExportStrategy` in `export_strategies.py`
- **Features**:
  - Optimized column ordering for trace reconstruction
  - Baseline subtraction metadata
  - Flag/event timing alignment

#### **Affilabs.analyze** (Planned)
- **Target**: Native Python data processing module (future)
- **Implementation**: Standalone package `affilabs.analyze` or `affilabs.data`
- **Features**:
  - Direct API for accessing exported data
  - Built-in SPR metrics (dip position, width, baseline drift)
  - Plotting integration (matplotlib/plotly)
  - Reporting templates (PDF, HTML)

---

## Extension Points

### Adding a New Export Format

1. **Create strategy class** in `affilabs/utils/export_strategies.py`:
   ```python
   class MyFormatExportStrategy(ExportStrategy):
       def export(self, file_path: str, export_data: dict, config: dict) -> None:
           # Implementation
           pass
   ```

2. **Register in factory function**:
   ```python
   def get_export_strategy(format_name: str) -> ExportStrategy:
       if format_name == "my_format":
           return MyFormatExportStrategy()
   ```

3. **Update UI** (`affilabs/managers/export_manager.py`):
   ```python
   format_options = ["excel", "csv", "json", "my_format"]
   ```

4. **Test** with sample export data

---

## Data Structures & Contracts

### Raw Data Row Contract
```python
{
    "time": float,           # Elapsed seconds
    "channel_a": int,        # Raw CCD counts
    "channel_b": int,
    "channel_c": int,
    "channel_d": int,
    "led_intensity": int,    # LED power level
    "integration_time": float,
}
```

### Cycle Contract
```python
{
    "id": int,
    "type": str,             # "Baseline", "Concentration", "Regeneration", etc.
    "start_time": float,     # Seconds into recording
    "duration": float,
    "concentration": str,    # e.g., "100nM", "50µM"
    "channels": list[str],   # ["A", "B", "C", "D"]
    "contact_time": float,   # For injection cycles
    "notes": str,
}
```

### Analysis Result Contract
```python
{
    "cycle_id": int,
    "channel": str,
    "peak_position_nm": float,
    "peak_height": float,
    "baseline": float,
    "dip_width_nm": float,
    "convergence_time_s": float,
    "signal_quality": str,   # "good", "fair", "poor"
    "saturation_warning": bool,
}
```

---

## Performance Considerations

### Large Datasets
- **Pandas DataFrames**: Handles millions of rows efficiently
- **ExcelWriter streaming**: Avoids loading entire file into memory
- **Chunked processing**: Process channels independently to reduce footprint

### Optimization Tips
- Use `data_types` config to exclude unnecessary sheets (e.g., skip raw if only analysis needed)
- For very large exports, consider CSV over Excel
- Pre-filter cycles/flags before passing to exporter

---

## Known Limitations & Future Work

| Issue | Impact | Status |
|-------|--------|--------|
| **AnIML not yet implemented** | Regulatory workflows blocked | Planned Q2 2026 |
| **TracedRawer format TBD** | Trace analysis workflows blocked | Planned Q3 2026 |
| **Origin native format** | OriginLab users currently use CSV import | Planned Q2 2026 |
| **No direct affilabs.analyze integration** | Post-export requires separate Python script | Planned Q3 2026 |
| **Chart/plot embedding in Excel limited** | Users must rebuild charts manually | Roadmap |

---

## Testing & Validation

### Export Checklist
- [ ] Raw data matches acquisition history
- [ ] Cycle boundaries align with actual run
- [ ] Flag timestamps accurate (injection, wash, etc.)
- [ ] Analysis results match live display
- [ ] Metadata complete (device, user, date, etc.)
- [ ] File opens in target software (Excel, Origin, etc.)

### Test Files
- Located in `data/samples/` (demo data)
- Use for validating new format implementations

---

## References

- **Main entry point**: `affilabs/tabs/edits/_export_mixin.py` → `_export_selection()`
- **Strategy implementations**: `affilabs/utils/export_strategies.py`
- **Signal relay**: `main.py` → `RecordingManager` → `ExcelExporter`
- **Excel utilities**: `affilabs/utils/excel_chart_builder.py`
- **Future module**: `affilabs/` (to be created: `analyze/`, `data/`, or `reporting/`)

---

## Active Notes

**For v2.0.6+**:
1. Begin AnIML implementation (regulatory requirement)
2. Define TracedRawer format spec (collaboration with analysis team)
3. Plan affilabs.analyze module structure (Python package design)
4. Add Origin .opj export (user request)
5. Implement export preview dialog (show sample rows before commit)
