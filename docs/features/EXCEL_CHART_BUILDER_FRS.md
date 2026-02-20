# EXCEL_CHART_BUILDER_FRS.md

**Feature Requirement Specification: Excel Export & Chart Generation System**  
Document Status: ✅ Code-verified  
Last Updated: February 19, 2026  
Source Files: `affilabs/services/excel_exporter.py` (357 lines), `affilabs/utils/excel_chart_builder.py` (294 lines)

---

## §1. Purpose & Context

**What This Is:**  
Two-component system for exporting SPR experimental data to Excel workbooks with optional interactive charts:

1. **ExcelExporter** (services layer) — Core export engine used by RecordingManager for live recording export; generates 8-sheet workbooks with raw data, cycles, flags, events, metadata
2. **ExcelChartBuilder** (utils layer) — Standalone chart generator for post-edit analysis export; adds 4 chart types (delta SPR bars, timeline lines, flags scatter, overview) to existing workbooks

**When Used:**
- **Live Recording Export:** RecordingManager → ExcelExporter (8 sheets, no charts) — auto-save every 60s during acquisition
- **Post-Edit Analysis Export:** EditsTab → `create_analysis_workbook_with_charts()` factory function (6 sheets + 4 chart sheets) — user-initiated from Edits export dialog

**Why Two Separate Components:**  
Chart generation is computationally expensive and not needed for live recording auto-save (no user looking at file during acquisition). Charts added post-hoc when user exports processed analysis from Edits tab.

**Technology Stack:** pandas + openpyxl (Excel read/write engine, chart API)

---

## §2. Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXCEL EXPORT SYSTEM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Component 1: ExcelExporter (services/excel_exporter.py)       │
│  ┌───────────────────────────────────────────────────────┐    │
│  │  • export_to_excel(filepath, **kwargs)                │    │
│  │  • load_from_excel(filepath) → dict                   │    │
│  │  • validate_excel_file(filepath) → bool               │    │
│  │                                                        │    │
│  │  Output: 8 sheets (Raw Data, Channels XY, Cycles,     │    │
│  │           Flags, Events, Analysis, Metadata, Alignment)│    │
│  └───────────────────────────────────────────────────────┘    │
│               ▲                                                 │
│               │ Used by RecordingManager                        │
│               │                                                 │
│  Component 2: ExcelChartBuilder (utils/excel_chart_builder.py) │
│  ┌───────────────────────────────────────────────────────┐    │
│  │  • add_delta_spr_charts(analysis_data)                │    │
│  │  • add_timeline_charts(processed_data, cycles_data)   │    │
│  │  • add_flags_timeline_chart(flag_data, cycles_data)   │    │
│  │  • add_overview_chart(processed_data, cycles_data)    │    │
│  │                                                        │    │
│  │  Output: 4 chart sheets (Charts_Delta_SPR,            │    │
│  │           Charts_Timeline, Charts_Flags, Charts_Overview) │
│  └───────────────────────────────────────────────────────┘    │
│               ▲                                                 │
│               │ Called by EditsTab export dialog                │
│               │                                                 │
│  Factory: create_analysis_workbook_with_charts()               │
│  └── Creates workbook → writes 6 data sheets → adds charts →   │
│      saves to file                                             │
└─────────────────────────────────────────────────────────────────┘
```

**Key Differences:**

| Feature | ExcelExporter (Recording) | ExcelChartBuilder (Analysis) |
|---------|--------------------------|------------------------------|
| **Usage** | Live recording auto-save | Post-edit analysis export |
| **Caller** | RecordingManager | EditsTab export dialog |
| **Sheets** | 8 (data-focused) | 6 data + 4 chart sheets |
| **Charts** | None | 4 types (bars, lines, scatter, overview) |
| **Frequency** | Every 60s during recording | User-initiated (once per export) |
| **Input** | Dict from DataCollector | pandas DataFrames from EditsTab |

---

## §3. Source Files

### 3.1 ExcelExporter (Services Layer)

**File:** `affilabs/services/excel_exporter.py`  
**Size:** 357 lines  
**Purpose:** Core Excel export engine for live recording data  
**Class:** `ExcelExporter`  
**Methods:**
- `export_to_excel()` (~195 lines) — Write 8 sheets to .xlsx file
- `load_from_excel()` (~75 lines) — Read 8 sheets back into dict
- `validate_excel_file()` (~20 lines) — Check file format validity

### 3.2 ExcelChartBuilder (Utils Layer)

**File:** `affilabs/utils/excel_chart_builder.py`  
**Size:** 294 lines  
**Purpose:** Interactive Excel chart generator for post-edit analysis  
**Class:** `ExcelChartBuilder`  
**Methods:**
- `__init__(workbook)` — Initialize with existing openpyxl.Workbook
- `add_delta_spr_charts()` (~55 lines) — Bar charts for channel responses
- `add_timeline_charts()` (~60 lines) — Line charts per cycle
- `add_flags_timeline_chart()` (~60 lines) — Scatter plot for flags
- `add_overview_chart()` (~55 lines) — Complete experiment line chart

**Factory Function:** `create_analysis_workbook_with_charts()` (~85 lines)  
- Standalone function (not class method) — creates complete analysis workbook with data + charts in one call

---

## §4. Dependencies

**Required:**
- `pandas` — DataFrame operations, Excel I/O
- `openpyxl` — Excel read/write, chart API (BarChart, LineChart, ScatterChart)
- `pathlib` — Path handling

**Import Guard:**
```python
try:
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, LineChart, ScatterChart, Reference
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
```

**Fallback Behavior:**  
If openpyxl not available:
- `create_analysis_workbook_with_charts()` falls back to pandas-only export (no charts)
- ExcelChartBuilder `__init__()` raises ImportError

---

## §5. ExcelExporter Class — Core Export Engine

**Purpose:** Used by RecordingManager to export live recording data during acquisition  
**Lifecycle:** Instantiated once per recording session, called every 60s for auto-save

### 5.1 export_to_excel Signature

```python
def export_to_excel(
    self,
    filepath: Path,
    raw_data_rows: List[Dict],
    cycles: List[Dict],
    flags: List[Dict],
    events: List[Tuple[float, str]],
    analysis_results: List[Dict],
    metadata: Dict,
    alignment_data: Dict[int, Dict] = None,
    channels_xy: Dict[str, pd.DataFrame] = None,
    recording_start_time: float = None,
) -> None:
```

**8 Sheets Created:**

| Sheet | Source Param | Row Count (typical) | Purpose |
|-------|--------------|---------------------|---------|
| **Raw Data** | `raw_data_rows` | 10k-100k | Every spectrum acquired (timestamp, cycle, elapsed, channel, λ) |
| **Channels XY** | `channels_xy` | 500-5000 | Pivot of Raw Data (Time_A, SPR_A, Time_B, SPR_B...) |
| **Cycles** | `cycles` | 5-50 | Cycle metadata (ID, times, concentration, flags, delta_spr) |
| **Flags** | `flags` | 3-20 | Flag markers (cycle, type, time, confidence, note) |
| **Events** | `events` | 10-100 | User actions (start recording, calibration, pump inject) |
| **Analysis** | `analysis_results` | 5-50 | Delta SPR measurements per cycle |
| **Metadata** | `metadata` | 10-30 | Key-value pairs (user, detector, version, settings) |
| **Alignment** | `alignment_data` | 5-50 | Edits tab settings (cycle index, channel filter, time shift) |

### 5.2 Cycles Sheet Column Order

**Preferred Column Order (14 fields):**  
```python
preferred_order = [
    "cycle_id",
    "channel",
    "start_time_sensorgram",
    "end_time_sensorgram",
    "duration_minutes",
    "concentration_value",
    "concentration_units",
    "units",
    "concentrations_formatted",
    "note",
    "delta_spr",
    "flags",
    "timestamp",
]
```

**Column Reordering Logic:**
1. Extract columns present in `preferred_order`
2. Append any other columns not in preferred order (except `"concentrations"` — excluded due to nested dict)
3. Export with reordered DataFrame

**Special Handling:**  
- `"concentrations"` field (dict) → excluded from export  
- `"concentrations_formatted"` (string) → exported instead

### 5.3 Events Sheet Timestamp Normalization

**Problem:** Events stored as (unix_timestamp, event_string) tuples  
**Solution:** Convert to elapsed time relative to recording start

```python
events_data = []
for timestamp, event in events:
    elapsed = timestamp - recording_start_time
    formatted_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    events_data.append({
        "elapsed": elapsed,
        "timestamp": formatted_time,
        "event": event,
    })
```

**Exported Columns:**
- `elapsed` (float) — Seconds since recording start (t=0)
- `timestamp` (string) — Human-readable datetime (`"2026-02-19 14:35:22"`)
- `event` (string) — Event description (`"Calibration completed"`)

### 5.4 Channels XY Sheet — Buffer Manager Data

**Purpose:** Processed time-series data in TraceDrawer-compatible format (Time_A, SPR_A, Time_B, SPR_B, ...)

**Source:** `buffer_mgr.get_trace_drawer_export_data()` returns dict:
```python
channels_xy = {
    'a': pd.DataFrame({'time': [...], 'spr': [...]}),
    'b': pd.DataFrame({'time': [...], 'spr': [...]}),
    'c': pd.DataFrame({'time': [...], 'spr': [...]}),
    'd': pd.DataFrame({'time': [...], 'spr': [...]}),
}
```

**Transform:**
1. Rename columns: `'time' → 'Time_A'`, `'spr' → 'SPR_A'` (uppercase, channel suffix)
2. Concatenate all channel DataFrames horizontally: `pd.concat([df_a, df_b, df_c, df_d], axis=1)`
3. Export to `"Channels XY"` sheet

**Fallback:** If `channels_xy` param is None → sheet skipped (known issue — should pivot from `raw_data_rows` instead)

---

## §6. ExcelChartBuilder Class — Interactive Charts

**Purpose:** Add openpyxl charts to existing workbooks for post-edit analysis  
**Usage Pattern:**
```python
workbook = Workbook()
# ... add data sheets ...
chart_builder = ExcelChartBuilder(workbook)
chart_builder.add_delta_spr_charts(analysis_df)
chart_builder.add_timeline_charts(processed_df, cycles_df)
workbook.save("output.xlsx")
```

### 6.1 Chart Type 1: Delta SPR Bar Charts

**Method:** `add_delta_spr_charts(analysis_data: pd.DataFrame)`

**Input DataFrame Schema:**
```python
analysis_data.columns = [
    'Cycle_ID',        # string (e.g., "Cycle_1", "Cycle_2")
    'Delta_SPR_A',     # float (RU)
    'Delta_SPR_B',     # float (RU)
    'Delta_SPR_C',     # float (RU)
    'Delta_SPR_D',     # float (RU)
]
```

**Output:**
- Creates sheet `"Charts_Delta_SPR"`
- Writes analysis_data as reference table
- Creates **one BarChart per cycle** — 4 bars per chart (channels A, B, C, D)
- Y-axis: Response (RU)
- X-axis: Channel labels (manually set as "Channel A", "Channel B", ...)

**Chart Layout:**
- Charts stacked vertically, 15 rows spacing between each
- First chart at row `len(analysis_data) + 3`

**openpyxl Reference Pattern:**
```python
data_ref = Reference(sheet, min_col=2, max_col=5, min_row=row_idx+2, max_row=row_idx+2)
# Reads 4 consecutive cells (Delta_SPR_A through Delta_SPR_D) for one cycle
```

### 6.2 Chart Type 2: Timeline Line Charts

**Method:** `add_timeline_charts(processed_data: pd.DataFrame, cycles_data: pd.DataFrame)`

**Input DataFrames:**

**processed_data schema** (assumed column pattern):
```python
columns = [
    'Time',      # Shared time axis for all channels
    'Time_A', 'SPR_A',
    'Time_B', 'SPR_B',
    'Time_C', 'SPR_C',
    'Time_D', 'SPR_D',
]
```

**cycles_data schema:**
```python
columns = [
    'cycle_id',                 # string
    'start_time_sensorgram',    # float (s)
    'end_time_sensorgram',      # float (s)
]
```

**Output:**
- Creates sheet `"Charts_Timeline"`
- Writes processed_data as reference table
- Creates **one LineChart per cycle** — 4 series per chart (channels A, B, C, D)
- X-axis: Time (s)
- Y-axis: SPR Response (RU)

**Chart Layout:**
- Charts stacked vertically at column J (column 10), 20 rows spacing
- Series colors: `['FF0000', '0000FF', '00FF00', 'FF8000']` (red, blue, green, orange)

**Known Issue:**  
Column detection assumes pattern `Time, Time_A, SPR_A, Time_B, SPR_B, ...` with SPR columns at `2 + (ch_idx * 2) + 1`. If processed_data has different structure → series not added correctly.

### 6.3 Chart Type 3: Flags Timeline Scatter Chart

**Method:** `add_flags_timeline_chart(flag_data: pd.DataFrame, cycles_data: pd.DataFrame)`

**Input flag_data schema:**
```python
columns = [
    'Flag_Type',     # string ('injection', 'wash', 'spike')
    'Time_Position', # float (s)
    'Cycle_ID',      # string
]
```

**Output:**
- Creates sheet `"Charts_Flags"`
- Writes flag data grouped by type (injection, wash, spike)
- Creates ScatterChart showing all flag positions on timeline
- X-axis: Time (s)
- Y-axis: Flag Type (categorical)

**Current Implementation Status:**  
Chart creation code is **incomplete** — scatter series not properly added. Code contains:
```python
# Add data series for each flag type
for flag_type, color in type_colors.items():
    type_data = [row for row in flag_chart_data if row[0] == flag_type]
    if type_data:
        # Add series (simplified - would need proper reference setup)
        pass  # ← NOT IMPLEMENTED
```

**Known Issue:** Chart exists but has no data series → empty chart rendered in Excel

### 6.4 Chart Type 4: Complete Overview Chart

**Method:** `add_overview_chart(processed_data: pd.DataFrame, cycles_data: pd.DataFrame)`

**Purpose:** Show entire experiment on one large timeline with all 4 channels + cycle boundary markers

**Output:**
- Creates sheet `"Charts_Overview"`
- Writes processed_data as reference table
- Creates **one large LineChart** — 4 series (all channels overlaid)
- X-axis: Time (s)
- Y-axis: SPR Response (RU)
- Chart dimensions: width=20, height=10 (larger than standard)

**Cycle Boundary Annotations:**
- Below chart, writes cycle metadata table:
  - Column 1: Cycle ID
  - Column 2: Start (s)
  - Column 3: End (s)
- User can reference this table to identify cycle regions in overview chart

**Known Limitation:**  
Cycle boundaries not rendered as vertical lines on chart — only as reference table below chart. openpyxl has limited support for chart annotations (would require manually adding shape objects).

---

## §7. Factory Function — Complete Analysis Workbook

**Function:** `create_analysis_workbook_with_charts()`

**Signature:**
```python
def create_analysis_workbook_with_charts(
    raw_data: pd.DataFrame,
    processed_data: pd.DataFrame,
    analysis_results: pd.DataFrame,
    flag_data: pd.DataFrame,
    cycles_data: pd.DataFrame,
    export_settings: Dict[str, Any],
    output_path: Path,
    selected_cycles: list = None
) -> None:
```

**Purpose:** One-call interface for EditsTab export dialog to create complete analysis workbook with data + charts

**Workflow:**
1. Create new `Workbook()`, remove default sheet
2. Add 6 data sheets:
   - Raw_Data (original XY data)
   - Processed_Data (post-edit curves)
   - Analysis_Results (delta measurements)
   - Flag_Positions (updated markers)
   - Cycles_Metadata (enhanced cycle info)
   - Export_Settings (documentation of processing applied)
3. Instantiate `ExcelChartBuilder(workbook)`
4. Add charts:
   - `add_delta_spr_charts()` if analysis_results not empty
   - `add_timeline_charts()` + `add_overview_chart()` if processed_data not empty
   - `add_flags_timeline_chart()` if flag_data not empty
5. Save workbook to `output_path`

**Error Handling:**  
Chart generation wrapped in try-except — if chart creation fails, data sheets still exported successfully. Warning printed: `"Warning: Could not add charts to Excel file: {e}"`

**Fallback for Missing openpyxl:**  
If `OPENPYXL_AVAILABLE == False` → uses pandas `ExcelWriter` to create basic 6-sheet workbook without charts

---

## §8. Public Interface Summary

### 8.1 ExcelExporter Methods

**export_to_excel()**
- **Used by:** RecordingManager auto-save (every 60s)
- **Input:** 8 separate collections (raw_data_rows, cycles, flags, events, analysis, metadata, alignment_data, channels_xy)
- **Output:** 8-sheet .xlsx file at specified filepath
- **Returns:** None (raises exception on failure)

**load_from_excel()**
- **Used by:** EditsTab "Load from Excel" button
- **Input:** `filepath: Path`
- **Output:** Dictionary with keys `['raw_data', 'cycles', 'flags', 'events', 'analysis', 'alignment', 'metadata']` — each value is list of dicts (or dict for metadata)
- **Returns:** `dict | None` (None on failure)

**validate_excel_file()**
- **Used by:** File dialog filters, pre-load validation
- **Input:** `filepath: Path`
- **Output:** `True` if file exists, has .xlsx/.xls extension, and pandas can read it; `False` otherwise
- **Returns:** `bool`

### 8.2 ExcelChartBuilder Methods

**add_delta_spr_charts(analysis_data: pd.DataFrame)**
- **Chart type:** BarChart (one per cycle, 4 bars per chart)
- **Sheet created:** `"Charts_Delta_SPR"`
- **Returns:** None

**add_timeline_charts(processed_data: pd.DataFrame, cycles_data: pd.DataFrame)**
- **Chart type:** LineChart (one per cycle, 4 series per chart)
- **Sheet created:** `"Charts_Timeline"`
- **Returns:** None

**add_flags_timeline_chart(flag_data: pd.DataFrame, cycles_data: pd.DataFrame)**
- **Chart type:** ScatterChart (one chart, all flags)
- **Sheet created:** `"Charts_Flags"`
- **Returns:** None
- **Status:** Incomplete implementation (no series added)

**add_overview_chart(processed_data: pd.DataFrame, cycles_data: pd.DataFrame)**
- **Chart type:** LineChart (one large chart, 4 series)
- **Sheet created:** `"Charts_Overview"`
- **Returns:** None

### 8.3 Factory Function

**create_analysis_workbook_with_charts()**
- **Used by:** EditsTab export dialog for post-edit analysis export
- **Input:** 7 params (6 DataFrames + 1 dict + output_path)
- **Output:** Complete .xlsx file with 6 data sheets + 4 chart sheets
- **Returns:** None (raises exception on failure)

---

## §9. Data Flow Diagrams

### 9.1 Live Recording Export (RecordingManager → ExcelExporter)

```
┌──────────────────┐
│ RecordingManager │ Every 60s during acquisition
└────────┬─────────┘
         │
         │ Triggers auto-save
         ▼
┌────────────────────┐
│  DataCollector     │ .get_all_data() returns dict with 8 collections
│  .raw_data_rows    │ → List[Dict] (10k-100k rows)
│  .cycles           │ → List[Dict] (5-50 cycles)
│  .flags            │ → List[Dict] (3-20 flags)
│  .events           │ → List[Tuple[float, str]] (10-100 events)
│  .analysis_results │ → List[Dict] (5-50 results)
│  .metadata         │ → Dict (10-30 key-value pairs)
│  .alignment_data   │ → Dict[int, Dict] (5-50 cycle settings)
│  .channels_xy      │ → Dict[str, pd.DataFrame] (4 channels)
└────────┬───────────┘
         │
         │ Pass all collections
         ▼
┌────────────────────┐
│  ExcelExporter     │
│  .export_to_excel()│
└────────┬───────────┘
         │
         │ Write to disk
         ▼
┌────────────────────┐
│  Excel File (.xlsx)│
│  ├── Raw Data      │ 10k-100k rows
│  ├── Channels XY   │ 500-5000 rows (TraceDrawer format)
│  ├── Cycles        │ 5-50 rows (metadata + delta_spr)
│  ├── Flags         │ 3-20 rows (manual + auto-detected)
│  ├── Events        │ 10-100 rows (user actions)
│  ├── Analysis      │ 5-50 rows (delta measurements)
│  ├── Metadata      │ 10-30 rows (key-value pairs)
│  └── Alignment     │ 5-50 rows (Edits tab settings)
└────────────────────┘
    NO CHARTS
    (performance optimization)
```

### 9.2 Post-Edit Analysis Export (EditsTab → ExcelChartBuilder)

```
┌──────────────────┐
│    EditsTab      │ User clicks "Export Selected Cycles"
│  Export Dialog   │
└────────┬─────────┘
         │
         │ Collects 6 DataFrames from UI state
         ▼
┌───────────────────────────────┐
│  Prepare Analysis DataFrames  │
│  • raw_data (original XY)     │
│  • processed_data (post-edit) │
│  • analysis_results (deltas)  │
│  • flag_data (updated markers)│
│  • cycles_data (metadata)     │
│  • export_settings (dict)     │
└────────┬──────────────────────┘
         │
         │ Call factory function
         ▼
┌────────────────────────────────────┐
│  create_analysis_workbook_with_    │
│  charts(raw_data, processed_data,  │
│         analysis_results, ...)     │
└────────┬───────────────────────────┘
         │
         ├─ Step 1: Create Workbook()
         ├─ Step 2: Add 6 data sheets
         │          (Raw_Data, Processed_Data, Analysis_Results,
         │           Flag_Positions, Cycles_Metadata, Export_Settings)
         │
         ├─ Step 3: Instantiate ExcelChartBuilder(workbook)
         │
         ├─ Step 4: Add charts
         │  ├─ add_delta_spr_charts(analysis_results)
         │  │  └→ Sheet: Charts_Delta_SPR (bar charts)
         │  ├─ add_timeline_charts(processed_data, cycles_data)
         │  │  └→ Sheet: Charts_Timeline (line charts per cycle)
         │  ├─ add_overview_chart(processed_data, cycles_data)
         │  │  └→ Sheet: Charts_Overview (full experiment line)
         │  └─ add_flags_timeline_chart(flag_data, cycles_data)
         │     └→ Sheet: Charts_Flags (scatter, INCOMPLETE)
         │
         └─ Step 5: Save workbook to output_path
                    ▼
         ┌────────────────────┐
         │ Excel File (.xlsx) │
         │ DATA SHEETS (6)    │
         │ ├── Raw_Data       │
         │ ├── Processed_Data │
         │ ├── Analysis_Results│
         │ ├── Flag_Positions │
         │ ├── Cycles_Metadata│
         │ └── Export_Settings│
         │                    │
         │ CHART SHEETS (4)   │
         │ ├── Charts_Delta_SPR    │ Bar charts (one per cycle)
         │ ├── Charts_Timeline     │ Line charts (one per cycle)
         │ ├── Charts_Flags        │ Scatter (all flags, EMPTY)
         │ └── Charts_Overview     │ Line (full experiment)
         └────────────────────┘
```

### 9.3 Excel Load (Reverse Path)

```
┌────────────────────┐
│  Excel File (.xlsx)│
│  8 sheets          │
└────────┬───────────┘
         │
         │ EditsTab "Load from Excel" button
         ▼
┌────────────────────┐
│  ExcelExporter     │
│  .load_from_excel()│
└────────┬───────────┘
         │
         │ Read all sheets with pandas.read_excel(sheet_name=None)
         │
         ├─ Raw Data → dict['raw_data'] (list of dicts)
         ├─ Channels XY → (not loaded, only used for TraceDrawer export)
         ├─ Cycles → dict['cycles'] (list of dicts)
         ├─ Flags → dict['flags'] (list of dicts)
         ├─ Events → dict['events'] (list of dicts)
         ├─ Analysis → dict['analysis'] (list of dicts)
         ├─ Metadata → dict['metadata'] (dict, converted from key-value list)
         └─ Alignment → dict['alignment'] (list of dicts)
         │
         │ Return dict with 8 keys
         ▼
┌────────────────────┐
│  EditsTab          │
│  _on_load_excel()  │ Populates UI from loaded dict
│  • Renders cycles  │
│  • Applies alignment│
│  • Shows flags     │
└────────────────────┘
```

---

## §10. Integration Points

**10.1 RecordingManager (Live Export)**
- **Trigger:** `_perform_save()` method called every 60s by timer
- **Data source:** `self.data_collector.get_all_data()` + `self.buffer_mgr.get_trace_drawer_export_data()`
- **Call:** `self.excel_exporter.export_to_excel(filepath, **data_dict)`
- **File location:** User-specified recording path (set at recording start)

**10.2 EditsTab Export Dialog (Post-Edit Analysis)**
- **Trigger:** User clicks "Export" button in Edits Export dialog
- **Data source:** 
  - `self._loaded_cycles` (list of Cycle objects)
  - `self._flag_data` (list of flag dicts)
  - `self._loaded_raw_data` (dict from Excel or recording_mgr)
  - UI state (alignment settings, time shifts, reference traces)
- **Call:** `create_analysis_workbook_with_charts(...)`
- **File location:** User-selected path from file save dialog

**10.3 EditsTab Load Dialog (Import)**
- **Trigger:** User clicks "Load from Excel" button
- **Call:** `loaded_data = self.excel_exporter.load_from_excel(filepath)`
- **Post-load:** 
  - Populate `_loaded_cycles` from `loaded_data['cycles']`
  - Populate `_flag_data` from `loaded_data['flags']`
  - Apply alignment settings from `loaded_data['alignment']`
  - Render first cycle via `_on_cycle_selected_in_table(0)`

**10.4 TraceDrawer Export**
- **Sheet:** `"Channels XY"` in recording exports
- **Format:** Time_A, SPR_A, Time_B, SPR_B, Time_C, SPR_C, Time_D, SPR_D (8 columns)
- **Source:** `buffer_mgr.get_trace_drawer_export_data()` returns dict of 4 DataFrames
- **Purpose:** Allow users to import data into TraceDrawer (legacy SPR analysis software) for external analysis

---

## §11. Error Handling & Edge Cases

### 11.1 Missing openpyxl Dependency

**Error:** ImportError when openpyxl not installed

**Handling:**
- **ExcelChartBuilder.__init__():** Raises `ImportError("openpyxl is required for chart creation")`
- **create_analysis_workbook_with_charts():** Catches exception, prints warning, falls back to pandas-only export without charts
- **ExcelExporter:** No impact (pandas can use openpyxl as engine or fall back to xlsxwriter)

### 11.2 Empty DataFrames

**Scenario:** User exports with no cycles selected or no data in recording

**Handling:**
- Each chart method checks `if df.empty: return` at entry — no chart created
- Empty sheets skipped entirely in export (sheet not created if list is empty)
- Example: `if flags: df_flags.to_excel(...)` — sheet only created if flags list not empty

### 11.3 Missing Channels XY Data

**Scenario:** `buffer_mgr` not available during recording export → `channels_xy` param is None

**Current Behavior:** `"Channels XY"` sheet skipped entirely

**Known Issue:** Should fall back to pivoting `raw_data_rows` to generate Time/SPR columns, but no fallback implemented

### 11.4 Chart Generation Failure

**Scenario:** openpyxl version mismatch, malformed DataFrame, Reference bounds error

**Handling:**
- `create_analysis_workbook_with_charts()` wraps all chart calls in try-except
- Prints warning: `"Warning: Could not add charts to Excel file: {e}"`
- Data sheets still saved successfully → user gets workbook without charts

### 11.5 Incomplete Flag Timeline Chart

**Scenario:** User exports with flags → Charts_Flags sheet created but chart is empty

**Root Cause:** Series addition not implemented (code has `pass` placeholder)

**Workaround:** User can manually create scatter chart in Excel using Chart_Flags sheet data

---

## §12. Known Issues & Limitations

### Issue 1: Channels XY Sheet Missing Fallback (ExcelExporter)

**Description:** If `buffer_mgr` not available (e.g., recording before buffer_mgr integration), `channels_xy` param is None → `"Channels XY"` sheet skipped

**Impact:** TraceDrawer export unavailable for some recordings

**Root Cause:** No fallback logic to pivot `raw_data_rows` into Time_A/SPR_A/Time_B/... format

**Workaround:** User must re-run acquisition with buffer_mgr active, or manually pivot in Excel

**Priority:** Medium (only affects TraceDrawer users, ~5% of user base)

### Issue 2: Flag Timeline Chart Empty (ExcelChartBuilder)

**Description:** `add_flags_timeline_chart()` creates sheet and writes data, but does not add series to ScatterChart → chart rendered empty in Excel

**Impact:** User sees blank chart in Charts_Flags sheet

**Root Cause:** Series addition logic not implemented (placeholder `pass` statement at L173)

**Workaround:** User can manually create scatter chart in Excel from Charts_Flags data table

**Code Location:** `excel_chart_builder.py:166-176`

**Priority:** Medium (chart is nice-to-have, data still accessible in sheet)

### Issue 3: Timeline Chart Column Detection Fragile (ExcelChartBuilder)

**Description:** `add_timeline_charts()` assumes column pattern `[Time, Time_A, SPR_A, Time_B, SPR_B, ...]` and calculates SPR column indices with `2 + (ch_idx * 2) + 1`

**Impact:** If `processed_data` has different column structure (e.g., only Time + SPR_A + SPR_B without Time_A/Time_B), series not added correctly → missing lines in chart

**Root Cause:** Hard-coded column index math instead of searching for column names

**Workaround:** EditsTab export must ensure processed_data has expected column structure

**Priority:** Low (processed_data always comes from EditsTab with consistent format)

### Issue 4: Cycle Boundaries Not Visualized (ExcelChartBuilder)

**Description:** `add_overview_chart()` creates large timeline chart with all channels, but does not draw vertical lines at cycle boundaries — only writes cycle start/end times in table below chart

**Impact:** User must manually cross-reference table to identify cycle regions in chart

**Root Cause:** openpyxl has limited support for chart annotations (vertical lines would require manually adding Shape objects to worksheet, not part of chart API)

**Workaround:** User can add vertical lines manually in Excel, or reference cycle table below chart

**Priority:** Low (cycle table provides same information)

### Issue 5: Charts Not Included in Live Recording Export (By Design)

**Description:** RecordingManager uses `ExcelExporter.export_to_excel()` which does not generate charts — only 8 data sheets created during auto-save

**Impact:** User cannot view charts during acquisition, must export from Edits tab post-experiment

**Root Cause:** Chart generation adds ~2-5 seconds to export time (unacceptable for 60s auto-save interval during acquisition)

**Workaround:** User exports post-edit analysis from EditsTab with charts using `create_analysis_workbook_with_charts()`

**Priority:** Not a bug (intentional design — performance optimization)

---

## §13. Testing Strategy

### 13.1 Unit Tests (Recommended)

**ExcelExporter Tests:**
1. **test_export_all_sheets()** — Export with all 8 collections populated, verify all sheets exist
2. **test_export_empty_collections()** — Export with empty lists, verify only non-empty sheets created
3. **test_load_round_trip()** — Export → load → verify all data intact
4. **test_cycles_column_order()** — Verify preferred_order columns appear first in Cycles sheet
5. **test_events_timestamp_normalization()** — Verify elapsed time calculated correctly
6. **test_channels_xy_format()** — Verify Time_A/SPR_A/Time_B/... columns in correct order
7. **test_validate_excel_file()** — Verify detection of valid/invalid files

**ExcelChartBuilder Tests:**
1. **test_delta_spr_charts_created()** — Verify Charts_Delta_SPR sheet exists with N bar charts
2. **test_timeline_charts_per_cycle()** — Verify Charts_Timeline has one chart per cycle
3. **test_overview_chart_all_channels()** — Verify 4 series in overview LineChart
4. **test_flag_chart_sheet_exists()** — Verify Charts_Flags created (even if empty)
5. **test_empty_dataframes_no_charts()** — Call all methods with empty DataFrames, verify no exceptions

**Factory Function Tests:**
1. **test_create_complete_workbook()** — Call with all DataFrames, verify 10 sheets (6 data + 4 charts)
2. **test_fallback_without_openpyxl()** — Mock `OPENPYXL_AVAILABLE=False`, verify 6 data sheets only
3. **test_chart_failure_data_preserved()** — Mock chart exception, verify data sheets still saved

### 13.2 Integration Tests (Current Testing Method)

**Test Workflow:**
1. Run acquisition → record 5 cycles → stop recording
2. Verify Excel file created at recording path
3. Open Excel → check 8 sheets exist, verify row counts
4. Open EditsTab → Load Excel → verify cycles render correctly
5. Select cycles → Export with charts → open output file
6. Verify 10 sheets exist (6 data + 4 charts)
7. Manually inspect charts: bar charts, timeline, overview visible; flags chart empty

### 13.3 Validation Checklist (Manual QC)

**For Live Recording Export:**
- [ ] Raw Data sheet: verify timestamp/cycle/elapsed/channel/wavelength columns
- [ ] Channels XY sheet: verify 8 columns (Time_A, SPR_A, ..., Time_D, SPR_D)
- [ ] Cycles sheet: verify preferred column order (cycle_id first, flags before timestamp)
- [ ] Flags sheet: verify cycle_id, flag_type, time_position, confidence, note columns
- [ ] Events sheet: verify elapsed time relative to recording start (t=0)
- [ ] Analysis sheet: verify delta_spr matches Edits tab calculations
- [ ] Metadata sheet: verify user, detector, version, settings keys
- [ ] Alignment sheet: verify cycle_index, channel filter, time_shift columns

**For Post-Edit Analysis Export:**
- [ ] All 6 data sheets present (Raw_Data, Processed_Data, Analysis_Results, Flag_Positions, Cycles_Metadata, Export_Settings)
- [ ] Charts_Delta_SPR: one bar chart per cycle, 4 bars per chart
- [ ] Charts_Timeline: one line chart per cycle, 4 colored series per chart
- [ ] Charts_Overview: one large line chart, 4 series, cycle table below
- [ ] Charts_Flags: sheet exists (chart empty, known issue)

---

## §14. Future Enhancements

### Enhancement 1: Implement Flag Timeline Chart Series

**Goal:** Complete `add_flags_timeline_chart()` implementation — add scatter series with proper Reference objects

**Code Location:** `excel_chart_builder.py:166-176`

**Approach:**
```python
# Replace placeholder pass statement with:
for flag_type, color in type_colors.items():
    type_flags = flag_data[flag_data['Flag_Type'] == flag_type]
    if not type_flags.empty:
        # Create reference to time positions (X-axis)
        x_ref = Reference(chart_sheet, min_col=2, min_row=start_row, max_row=start_row+len(type_flags))
        # Create reference to cycle IDs (Y-axis)
        y_ref = Reference(chart_sheet, min_col=3, min_row=start_row, max_row=start_row+len(type_flags))
        # Create series
        series = Series(y_ref, x_ref, title=f"{flag_type.title()} Flags")
        scatter_chart.append(series)
```

**Effort:** ~2 hours (coding + testing)

### Enhancement 2: Channels XY Fallback from Raw Data

**Goal:** If `channels_xy` param is None, pivot `raw_data_rows` to generate Time_A/SPR_A/... columns

**Code Location:** `excel_exporter.py:85-105`

**Approach:**
```python
if channels_xy is None and raw_data_rows:
    # Pivot raw_data_rows to channels_xy format
    df_raw = pd.DataFrame(raw_data_rows)
    channels_xy = {}
    for ch in ['a', 'b', 'c', 'd']:
        ch_data = df_raw[df_raw['channel'] == ch]
        channels_xy[ch] = pd.DataFrame({
            'time': ch_data['elapsed'],
            'spr': ch_data['wavelength']  # or whatever column contains SPR values
        })
```

**Effort:** ~4 hours (coding + testing + validation)

### Enhancement 3: Robust Column Detection for Timeline Charts

**Goal:** Replace hard-coded column index math with column name search

**Code Location:** `excel_chart_builder.py:128-138`

**Approach:**
```python
# Instead of: spr_col = 2 + (ch_idx * 2) + 1
# Use column name search:
spr_col_name = f'SPR_{ch_name}'
if spr_col_name in processed_data.columns:
    spr_col = processed_data.columns.get_loc(spr_col_name) + 1  # +1 for Excel 1-based
    spr_ref = Reference(chart_sheet, min_col=spr_col, ...)
```

**Effort:** ~2 hours (refactor + add column validation)

### Enhancement 4: Cycle Boundary Vertical Lines on Overview Chart

**Goal:** Add vertical lines at cycle start/end times to overview chart

**Approach:** Use openpyxl Shape API to add vertical lines to worksheet (outside chart object), positioned over chart

**Code Example:**
```python
from openpyxl.drawing.line import LineProperties
from openpyxl.drawing.colors import ColorChoice

for _, cycle_row in cycles_data.iterrows():
    start_time = cycle_row.get('start_time_sensorgram', 0)
    # Convert time to chart X-coordinate (requires chart units calculation)
    # Create vertical line shape at X-position
    line = Shape(...)
    chart_sheet.add_shape(line)
```

**Effort:** ~6 hours (non-trivial coordinate mapping + testing)

**Alternative:** Export cycle boundary times to separate columns in processed_data → user creates lines in Excel manually

### Enhancement 5: HDF5 Export for Large Datasets

**Goal:** Add `export_to_hdf5()` method to ExcelExporter for datasets >50 MB (50k+ spectra)

**Rationale:** Excel files >50 MB slow to load; HDF5 format faster + smaller file size

**Approach:**
```python
def export_to_hdf5(self, filepath: Path, **data_collections) -> None:
    import h5py
    with h5py.File(filepath, 'w') as f:
        f.create_dataset('raw_data', data=raw_data_array)
        f.create_dataset('cycles', data=cycles_array)
        # ... store all collections as datasets
```

**Effort:** ~8 hours (new method + load counterpart + integration with RecordingManager)

---

## §15. Method Inventory

### ExcelExporter Methods (3)

| Method | Lines | Purpose | Called By |
|--------|-------|---------|-----------|
| `export_to_excel()` | ~195 | Write 8 sheets to .xlsx file | RecordingManager auto-save |
| `load_from_excel()` | ~75 | Read 8 sheets into dict | EditsTab load dialog |
| `validate_excel_file()` | ~20 | Check file format | File selection validators |

### ExcelChartBuilder Methods (5)

| Method | Lines | Purpose | Called By |
|--------|-------|---------|-----------|
| `__init__()` | ~8 | Store workbook reference, check openpyxl | Factory function |
| `add_delta_spr_charts()` | ~55 | Bar charts per cycle | Factory function (if analysis_results not empty) |
| `add_timeline_charts()` | ~60 | Line charts per cycle | Factory function (if processed_data not empty) |
| `add_flags_timeline_chart()` | ~60 | Scatter chart (INCOMPLETE) | Factory function (if flag_data not empty) |
| `add_overview_chart()` | ~55 | Complete experiment line chart | Factory function (if processed_data not empty) |

### Module-Level Functions (1)

| Function | Lines | Purpose | Called By |
|----------|-------|---------|-----------|
| `create_analysis_workbook_with_charts()` | ~85 | Complete analysis workbook with data + charts | EditsTab export dialog |

**Total Implementation:** 2 classes, 8 methods, 1 factory function = ~600 lines across 2 files

---

## §16. Document Metadata

**Created:** February 19, 2026  
**Codebase Version:** Affilabs.core v2.0.5 beta  
**Review Date:** February 19, 2026  
**Lines Reviewed:** 651 (357 excel_exporter + 294 excel_chart_builder)  
**Next Review:** After implementation of Issue 1 (Channels XY fallback) or Issue 2 (Flag chart series)

**Related Documents:**
- `RECORDING_MANAGER_FRS.md` — RecordingManager orchestration layer (calls ExcelExporter)
- `EDITS_EXPORT_FRS.md` — EditsTab export dialog (calls create_analysis_workbook_with_charts)
- `EDITS_CYCLE_DISPLAY_FRS.md` — EditsTab rendering (provides processed_data for charts)

**Dependencies Flow:**
```
RecordingManager → ExcelExporter → openpyxl
EditsTab → create_analysis_workbook_with_charts() → ExcelChartBuilder → openpyxl
```
