# Data Export & Recording Save Audit Report

**Date**: February 16, 2026  
**Scope**: Complete audit of all data export and recording save paths  
**Goal**: Identify consistency issues, duplication, and efficiency problems

---

## 1. SUMMARY OF FINDINGS

### ✅ Consistency Status: **PARTIALLY CONSISTENT**
- Export and Record button paths use **different services** for file I/O
- Multiple Excel export implementations exist with **duplicated logic**
- CSV export has **two separate implementations** (one via recording_manager, one via export_helpers)
- Metadata handling is **inconsistent** across paths

### 🔴 Efficiency Issues: **MODERATE**
- Excel export logic duplicated in 3+ locations
- Channel data formatting duplicated (wide format vs long format confusion)
- Cycles/flags/events deduplication happens in **multiple places**
- Data collection architecture uses both `RecordingManager.data_collector` AND raw buffer access

### 📊 Complexity: **HIGH** 
- 7 different entry points for saving data
- 3 different output pathways (recording_mgr, export_helpers, edits_tab)
- Inconsistent folder structures and naming conventions

---

## 2. EXPORT PATH INVENTORY

### Path 1: Export Button (User-Triggered)
**Handler**: `main.py:_on_export_requested()` (line 9516)  
**Implementation**: `affilabs/utils/export_helpers.py:export_requested()` (line 319)  

**Trigger**: User clicks Export button → Shows file save dialog → Asks for confirmation

**Data Saved**:
- Raw data (long format: time, channel, value per row)
- Cycles metadata (from `recording_mgr.data_collector.cycles`)
- Flags (from `recording_mgr.data_collector.flags`)
- Events (from `recording_mgr.data_collector.events`)
- Metadata (from `recording_mgr.data_collector.metadata`)
- Per-channel XY format (Time_A, SPR_A, Time_B, SPR_B, etc.)

**Format**: Excel (.xlsx), CSV (.csv), JSON (.json)

**Directory**: User-configured OR default `~/Documents/Affilabs Data/<user>/SPR_data/`

**Output Sheets** (if Excel):
1. `Raw Data` - Long format (time, channel, value)
2. `Cycles` - Cycle metadata with deduplication
3. `Flags` - Flag markers
4. `Events` - Event log
5. `Metadata` - Session metadata
6. `Channels XY` - Wide format (Time_A, SPR_A, Time_B, SPR_B, Time_C, SPR_C, Time_D, SPR_D)

**Key Code Reference**:
```python
# Lines 319-590 in export_helpers.py
def export_requested(app: Application, config: dict) -> None:
    # Builds raw_data in LONG format (time, channel, value)
    raw_data_rows = []
    for ch in channels:
        cycle_time = app.buffer_mgr.cycle_data[ch].time
        wavelength = app.buffer_mgr.cycle_data[ch].wavelength
        for t, w in zip(cycle_time, wavelength):
            raw_data_rows.append({
                'time': round(t, precision),
                'channel': ch,
                'value': round(w, precision)
            })
```

**Issues**:
- ❌ Uses raw `app.buffer_mgr.cycle_data` directly (bypasses DataCollector)
- ❌ Builds channel-specific data only if recording was NOT to file
- ⚠️ Deduplicates cycles by cycle_id/cycle_num inside Excel export (inefficient)

---

### Path 2: Record Button (Live Recording)
**Handler**: `affilabs/core/recording_manager.py`  
**Lifecycle**: `start_recording()` → `record_data_point()` (repeating) → `stop_recording()` → `_save_to_file()`

**Data Flow**:
1. Start: Creates file path, initializes DataCollector
2. Recording: Each data point calls `data_collector.add_data_point()`
3. Stop: Calls `_save_to_file()` which exports all accumulated data

**Data Saved**:
- Raw data (from `data_collector.raw_data_rows`)
- Cycles (from `data_collector.cycles`)
- Flags (from `data_collector.flags`)
- Events (from `data_collector.events`)
- Metadata (from `data_collector.metadata`)
- Per-channel XY data (from `buffer_mgr.cycle_data` - accessed inside _save_to_file)

**Format**: Excel (.xlsx), CSV (.csv), JSON (.json)

**Directory**: Configured in `RecordingManager.output_directory` → Default `~/Documents/Affilabs Data`

**Output Sheets** (if Excel):
1. `Raw Data` - From collected data
2. `Cycles` - With cycle deduplication
3. `Flags`
4. `Events`
5. `Metadata`
6. `Channels XY` - Per-channel time/SPR data (if `buffer_mgr` available)

**Key Code Reference**:
```python
# Lines 134-296 in recording_manager.py
def _save_to_file(self) -> None:
    """Save collected data to the current file."""
    raw_data = self.data_collector.raw_data_rows
    # ... sorts by time then channel
    # Excel: Multiple sheets including Channels XY
    # CSV: Only raw data
    # JSON: Everything (raw, cycles, events, metadata)
```

**Issues**:
- ✅ Uses DataCollector for accumulation (good separation)
- ⚠️ Also accesses `buffer_mgr.cycle_data` for XY sheet (mixed data sources)
- ⚠️ Auto-saves every 60 seconds during recording (background I/O)

---

### Path 3: Quick CSV Export
**Handler**: `main.py` (no direct handler visible - likely called via UI)  
**Implementation**: `affilabs/utils/export_helpers.py:quick_export_csv()` (line 31)

**Trigger**: "Quick Export CSV" button (in export sidebar)

**Data Saved**:
- Cycle data in **wide format**: Time(s), Channel_A_SPR(RU), Channel_B_SPR(RU), etc.
- Metadata header: export date, start time, stop time, duration

**Format**: CSV (.csv) ONLY

**Directory**: Default `~/Documents/Affilabs Data/<user>/SPR_data/`

**Content**:
```
# AffiLabs Cycle Export
# Export Date,2026-02-16T12:34:56.789Z
# Start Time (display s),10.50
# Stop Time (display s),45.75
# Duration (s),35.25

Time (s),Channel_A_SPR (RU),Channel_B_SPR (RU),Channel_C_SPR (RU),Channel_D_SPR (RU)
0.0,685.2,690.1,688.5,692.3
...
```

**Key Code Reference**:
```python
# Lines 31-135 in export_helpers.py
def quick_export_csv(app: Application) -> None:
    # Builds DataFrame with Time + SPR for each channel
    # Wide format with metadata header
```

**Issues**:
- ⚠️ Uses WIDE format (different from Raw Data export's LONG format)
- ⚠️ Only exports SPR, NOT wavelength
- ❌ No deduplication logic (unlike Excel exports)
- ⚠️ Metadata written as CSV comments, not structured data

---

### Path 4: Cycle Autosave (Background)
**Handler**: `main.py:_autosave_cycle_data()` (line 9510)  
**Implementation**: `affilabs/utils/export_helpers.py:autosave_cycle_data()` (line 137)

**Trigger**: After cycle completion (deferred via `_do_deferred_autosave()`)

**Data Saved**:
- Cycle data (wide format): Time(s), Ch_X_Wavelength(nm), Ch_X_SPR(RU) for each channel
- Metadata as JSON sidecar file with flags, injection time, channel offsets, etc.
- CSV metadata header with filter settings, reference subtraction config

**Format**: 
- CSV (.csv) for data
- JSON (.json) for metadata sidecar

**Directory**: Session cycles folder → `data/cycles/YYYYMMDD/` or from `recording_mgr.current_session_dir`

**Filename**: `current_cycle.csv` (overwrites each time - prevents file spam)

**File Pair Output**:
```
current_cycle.csv
│
├─ # AffiLabs Cycle Autosave
├─ # Timestamp, Filter Enabled, Reference Subtraction, etc. (CSV header comments)
└─ Time(s), Ch A Wavelength, Ch A SPR, Ch B Wavelength, Ch B SPR, ...

current_cycle.json
{
  "timestamp": "...",
  "operator": "...",
  "cycle_start": 10.5,
  "cycle_stop": 45.75,
  "flags": [...],
  "channel_offsets": {...},
  "injection_time": 12.3
}
```

**Key Code Reference**:
```python
# Lines 137-318 in export_helpers.py
def autosave_cycle_data(app: Application, start_time: float, stop_time: float) -> None:
    # Overwrites single current_cycle.csv file
    # Also creates current_cycle.json with full metadata
```

**Issues**:
- ⚠️ WIDE format (different from Export path's LONG format)
- ❌ Only one file at a time (previous cycles lost if not manually saved)
- ⚠️ JSON metadata is custom format (not part of Excel workbook)
- ⚠️ Writes both CSV and JSON - data split across two files

---

### Path 5: Image/Figure Export
**Handler**: `main.py:_on_quick_export_image()` (line 9522)  
**Implementation**: `affilabs/utils/export_helpers.py:quick_export_image()` (line 627)

**Trigger**: User clicks "Export Active Cycle Image" button

**Data Saved**:
- PNG image of cycle graph
- Metadata overlay on image: export timestamp, time range, channel names

**Format**: PNG (.png) image ONLY

**Directory**: User selects via file dialog

**Output**: High-resolution PNG with metadata text rendered at bottom

**Key Code Reference**:
```python
# Lines 627-730 in export_helpers.py
def quick_export_image(app: Application) -> None:
    # Renders graph from pyqtgraph to QImage
    # Adds metadata text overlay
    # Saves as PNG
```

**Issues**:
- ✅ Minimal duplication (unique implementation)
- ⚠️ Metadata rendered as text, not structured (cannot parse)
- ⚠️ Rendering happens in UI thread (potential blocking)

---

### Path 6: Edits Tab Save
**Handler**: `affilabs/tabs/edits_tab.py:_save_cycles_to_excel()` (line 5097)

**Trigger**: User clicks "💾 Save" button in Edits tab (after loading and editing cycles)

**Data Saved**:
- Updated cycle data from table (`_loaded_cycles_data`)
- All other sheets from original Excel file (preserved unchanged)

**Format**: Excel (.xlsx) ONLY

**Directory**: Original file location (overwrites in-place)

**Process**:
1. Reads existing Excel file with `pd.read_excel(..., sheet_name=None)`
2. Extracts cycles data from `main_window._loaded_cycles_data`
3. Creates DataFrame from cycles
4. Writes back to Excel, replacing only `Cycles` sheet, preserving all others

**Key Code Reference**:
```python
# Lines 5097-5170 in edits_tab.py
def _save_cycles_to_excel(self):
    # Read original file to preserve other sheets
    excel_sheets = pd.read_excel(file_path, sheet_name=None, engine='openpyxl')
    # Update Cycles sheet
    # Write back, preserving all other sheets
```

**Issues**:
- ✅ Preserves existing sheets (good design)
- ⚠️ Requires file to already be loaded (coupled to UI state)
- ❌ Does NOT match other export paths' sheet structure
- ⚠️ No deduplication of cycles (assumes user loaded data correctly)

---

## 3. DATA CONSISTENCY ANALYSIS

### Format Inconsistencies

| Aspect | Export Button | Record Button | Quick CSV | Autosave | Edits Save |
|--------|---|---|---|---|---|
| **Raw Data Format** | Long (time, channel, value) | Long | Wide (channels as columns) | Wide | N/A |
| **Data Source** | `buffer_mgr.cycle_data` | `data_collector` + `buffer_mgr` | `buffer_mgr.cycle_data` | `buffer_mgr.cycle_data` | Excel file rows |
| **Includes Wavelength** | No | No | No | Yes | N/A |
| **Includes SPR** | Yes (as "value" in long) | Yes | Yes | Yes | N/A |
| **Excel Sheets** | 6 sheets | 6 sheets | N/A | N/A | Original + Cycles |
| **Cycle Deduplication** | Yes (inside export) | Yes (inside export) | N/A | N/A | No |
| **Metadata** | In Metadata sheet | In Metadata sheet | CSV header comments | Separate JSON | Original Metadata sheet |

### Critical Inconsistencies:

1. **Data Format Mismatch**
   - Export Button produces LONG format (time, channel, value)
   - Quick CSV produces WIDE format (channels as columns)
   - Autosave produces WIDE format
   - Inconsistent across different save paths!

2. **Data Source Inconsistency**
   - Export Button uses `buffer_mgr.cycle_data` (raw buffer)
   - Record Button uses `data_collector.raw_data_rows` + `buffer_mgr` (hybrid)
   - Quick CSV uses `buffer_mgr.cycle_data` (raw buffer)
   - Autosave uses `buffer_mgr.cycle_data` (raw buffer)

3. **Cycles Data Path**
   - Export & Record get cycles from `recording_mgr.data_collector.cycles`
   - Edits gets cycles from table/file (different source!)
   - Autosave does NOT include cycles

4. **Metadata Location**
   - Excel paths: Metadata sheet
   - Quick CSV: CSV header comments
   - Autosave: Separate JSON file
   - Edits: Preserved from original file

---

## 4. DUPLICATION ANALYSIS

### Duplicated Code #1: Excel Export Logic
**Locations**: 
- `recording_manager.py:_save_to_file()` - Lines 134-296 (Excel export block)
- `export_helpers.py:export_requested()` - Lines 517-580 (Excel export block)
- `excel_exporter.py:export_to_excel()` - Lines 46+ (service class, NOT currently used!)

**Issue**: THREE independent implementations of Excel export!

**Sheet Creation Duplicated**:
```python
# All three do this independently:
1. Create Raw Data sheet
2. Create Cycles sheet with deduplication
3. Create Flags sheet
4. Create Events sheet
5. Create Metadata sheet
6. Create Channels XY sheet
```

**Root Cause**: 
- `ExcelExporter` service exists (lines 46-362) but is NOT used
- Both `recording_manager._save_to_file()` and `export_helpers.export_requested()` have their own inline Excel logic
- No clear entry point for Excel export

### Duplicated Code #2: Cycle Deduplication
**Locations**:
- `recording_manager.py:_save_to_file()` - Lines 169-259
- `export_helpers.py:export_requested()` - Lines 535
- `excel_exporter.py:export_to_excel()` - Lines 123-143

**Pattern** (all identical):
```python
if 'cycle_id' in df_cycles.columns:
    original_count = len(df_cycles)
    df_cycles = df_cycles.drop_duplicates(subset=['cycle_id'], keep='first')
    if len(df_cycles) < original_count:
        logger.warning(f"Removed {original_count - len(df_cycles)} duplicate...")
elif 'cycle_num' in df_cycles.columns:
    # same logic with cycle_num
```

**Root Cause**: No shared utility for cycle data validation/deduplication

### Duplicated Code #3: Channels XY Sheet Generation
**Locations**:
- `recording_manager.py:_save_to_file()` - Lines 262-289
- `export_helpers.py:export_requested()` - Lines 517-580

**Pattern** (nearly identical):
```python
# Both do:
1. Find max length across all channels
2. Pad all time/SPR arrays to max_len with NaN
3. Create DataFrame with Time_A, SPR_A, Time_B, SPR_B, etc.
4. Write to "Channels XY" sheet
```

**Root Cause**: Export path also needs this sheet, so code was copied

### Unused Service Class
**Location**: `affilabs/services/excel_exporter.py` - Exists but NOT called!

Provides `export_to_excel()` with full workbook generation, but:
- `recording_manager._save_to_file()` reimplements it inline
- `export_helpers.export_requested()` reimplements it inline
- Never instantiated in any production code

---

## 5. DATA SOURCE INCONSISTENCIES

### Buffer Manager Access vs Data Collector

**Current State**:
```
┌─ Export Button ─────────────────────┐
│  Data Source: buffer_mgr.cycle_data │ ← Direct raw buffer access
│  (bypasses DataCollector!)          │
└─────────────────────────────────────┘

┌─ Record Button ─────────────────────┐
│  Data Source: data_collector        │ ← Collected data
│  + buffer_mgr.cycle_data (for XY)   │ ← Also raw buffer access!
└─────────────────────────────────────┘

┌─ Quick CSV ─────────────────────────┐
│  Data Source: buffer_mgr.cycle_data │ ← Direct raw buffer access
└─────────────────────────────────────┘

┌─ Autosave ─────────────────────────┐
│  Data Source: buffer_mgr.cycle_data │ ← Direct raw buffer access
└─────────────────────────────────────┘
```

**Problem**: 
- Export button data is INDEPENDENT of RecordingManager's collected data
- If user exports without recording, gets stale buffer data
- If user records then exports, gets fresh buffer data (redundant with DataCollector)
- Inconsistency: Export doesn't use DataCollector, but Record does

---

## 6. KEY EFFICIENCY ISSUES

### Issue #1: Deduplication Happens During Export (Not At Accumulation)
**Current**: 
- Cycles accumulated with potential duplicates
- Duplicates only removed during file write
- Same deduplication code runs in 3 places

**Better Approach**:
```python
# In DataCollector.add_cycle():
def add_cycle(self, cycle_data: dict) -> None:
    # Only add if cycle_id not already present
    if cycle_data.get('cycle_id') not in self.cycle_ids_seen:
        self.cycles.append(cycle_data)
        self.cycle_ids_seen.add(cycle_data.get('cycle_id'))
```

### Issue #2: Multiple Pandas DataFrame Conversions
**Current Pattern**:
```python
# recording_manager._save_to_file()
df_raw = pd.DataFrame(raw_data)  # Convert once
df_raw = df_raw.sort_values(...)  # Convert back
if filepath.suffix == ".xlsx":
    df_raw.to_excel(...)  # CSV export handles differently

# export_helpers.export_requested()
df_raw = pd.DataFrame(raw_data_rows)  # Convert again
if format_type == "excel":
    # More DataFrame operations
```

**Issue**: DataFrame objects created multiple times from same data

### Issue #3: Channel Data Formatting on Every Export
**Current**: Each export path rebuilds channel-specific data
```python
# Both _save_to_file() and export_requested() do:
for ch in channels:
    ch_time = app.buffer_mgr.cycle_data[ch].time
    ch_spr = app.buffer_mgr.cycle_data[ch].spr
    # Pad to max_len, create DataFrame columns, etc.
```

**Better Approach**: Precompute and cache in BufferManager

### Issue #4: Auto-Save Every 60 Seconds (Background I/O)
**Current** (`recording_manager.record_data_point()`, line 310):
```python
if self.current_file:
    current_time = time.time()
    if current_time - self.last_save_time >= self.auto_save_interval:
        self._save_to_file()  # Full Excel write every 60 seconds!
```

**Issue**: 
- Writes entire workbook every 60 seconds (expensive)
- Blocks if file is locked
- No user control over frequency

---

## 7. DIRECTORY STRUCTURE INCONSISTENCY

| Path | Default Directory |
|------|---|
| Export Button | `~/Documents/Affilabs Data/<user>/SPR_data/` |
| Record Button | `~/Documents/Affilabs Data/` (from RecordingManager.output_directory) |
| Quick CSV | `~/Documents/Affilabs Data/<user>/SPR_data/` |
| Autosave | `data/cycles/YYYYMMDD/` OR from `recording_mgr.current_session_dir` |
| Edits Save | Original file location (in-place) |

**Issue**: Inconsistent default locations suggest unclear design intent

---

## 8. METADATA HANDLING INCONSISTENCY

### Export Button Metadata (In Metadata Sheet):
```python
{
    "recording_start": "2026-02-16 12:34:56",
    "recording_start_iso": "2026-02-16T12:34:56.123456"
}
```

### Record Button Metadata (In Metadata Sheet):
```python
{
    "recording_start": "2026-02-16 12:34:56",
    "recording_start_iso": "2026-02-16T12:34:56.123456"
}
```

### Autosave Metadata (In JSON Sidecar):
```json
{
    "timestamp": "...",
    "operator": "...",
    "cycle_start": 10.5,
    "cycle_stop": 45.75,
    "flags": [...],
    "channel_offsets": {...},
    "injection_time": 12.3
}
```

**Issue**: Different metadata schemas across paths!

---

## 9. EXCEL EXPORTER SERVICE (UNUSED)

**File**: `affilabs/services/excel_exporter.py` (362 lines)

**Features**:
- ✅ Comprehensive `export_to_excel()` method
- ✅ Multi-sheet generation
- ✅ Handles all data types (raw, cycles, flags, events, analysis, metadata, alignment)
- ✅ Clean API design

**Status**: **NOT USED IN PRODUCTION**

**Why Not Used**:
- ExcelExporter instantiated in RecordingManager but never called
- `recording_manager._save_to_file()` reimplements inline
- `export_helpers.export_requested()` reimplements inline
- Dead code/unreachable

**Evidence**:
```python
# recording_manager.py line 28:
self.excel_exporter = ExcelExporter()  # Instantiated

# But never called! Self._save_to_file() has inline implementation instead
```

---

## 10. SUMMARY TABLE: Export Path Comparison

| Path | Entry Point | Service Layer | Format | Sheet Count | Cycles Dedupe | Directory | Status |
|------|---|---|---|---|---|---|---|
| Export Button | `_on_export_requested()` | `export_helpers` | Excel/CSV/JSON | 6 | ✅ | User-configured | PRIMARY |
| Record Button | `stop_recording()` | `recording_manager` | Excel/CSV/JSON | 6 | ✅ | Default | PRIMARY |
| Quick CSV | (UI button) | `export_helpers` | CSV only | N/A | ❌ | User-specific | SECONDARY |
| Autosave | `_autosave_cycle_data()` | `export_helpers` | CSV+JSON pair | N/A | ❌ | Session folder | AUTO |
| Image Export | `_on_quick_export_image()` | `export_helpers` | PNG only | N/A | N/A | User selects | SECONDARY |
| Edits Save | `_save_cycles_to_excel()` | `edits_tab` | Excel only | Original+1 | ❌ | Original location | SPECIAL |

---

## 11. CONSISTENCY VERDICT

### Does Export Button match Record Button?

**Aspects that MATCH**:
- ✅ Both produce 6-sheet Excel files
- ✅ Both include Cycles, Flags, Events, Metadata sheets
- ✅ Both deduplicate cycles

**Aspects that DIFFER**:
1. **Data Source**:
   - Export uses `buffer_mgr.cycle_data` (raw buffer)
   - Record uses `data_collector.raw_data_rows` (accumulated data)
   - Record falls back to buffer_mgr for XY sheet

2. **Metadata**:
   - Both write to Metadata sheet
   - But Record's DataCollector has different metadata structure

3. **Timing**:
   - Export: On-demand, user-triggered
   - Record: Automatic on stop_recording, but also auto-saves every 60 seconds

4. **Directory**:
   - Export: `~/Documents/Affilabs Data/<user>/SPR_data/`
   - Record: `~/Documents/Affilabs Data/` (parent)

### Overall Consistency: **4/10** ❌
- Sheet structure: Consistent
- Data source: Inconsistent
- Deduplication: Both implemented separately
- Directory: Different defaults

---

## 12. IS EXPORT EFFICIENTLY ORGANIZED?

### Overall Assessment: **NO - 4/10** ❌

**Problems**:

1. ❌ **Duplicated Excel Export Logic** (3 places)
   - `recording_manager._save_to_file()` 
   - `export_helpers.export_requested()`
   - `excel_exporter.export_to_excel()` (unused)

2. ❌ **Duplicated Cycle Deduplication** (3 places)
   - Same code copied, not shared

3. ❌ **Duplicated Channels XY Sheet** (2 places)
   - Recording manager and export helpers

4. ❌ **Mixed Data Sources**
   - Export uses buffer_mgr
   - Record uses data_collector + buffer_mgr
   - No unified abstraction

5. ❌ **Unused ExcelExporter Service**
   - Dead code that should be primary path

6. ⚠️ **Format Inconsistency**
   - Long vs Wide format across paths

7. ⚠️ **Auto-Save Performance**
   - Full Excel write every 60 seconds

---

## 13. RECOMMENDATIONS

### HIGH PRIORITY (Consolidation)

1. **Unify Excel Export to ExcelExporter Service**
   ```
   CURRENT:
   - recording_manager._save_to_file() → inline Excel logic
   - export_helpers.export_requested() → inline Excel logic
   - ExcelExporter.export_to_excel() → unused
   
   RECOMMENDED:
   - Both paths → ExcelExporter.export_to_excel()
   - Single source of truth
   - Reduces code by ~300 lines
   ```

2. **Consolidate CSV/Long Format Export**
   ```
   CURRENT:
   - export_requested() does long format CSV
   - quick_export_csv() does wide format CSV
   - Inconsistent naming and structure
   
   RECOMMENDED:
   - Create unified `export_to_format(format, data, options)` method
   - Support both long and wide format options
   - Single deduplication logic
   ```

3. **Unify Data Source for Buffer Access**
   ```
   CURRENT:
   export_helpers.export_requested() uses:
   ```python
   for ch in channels:
       cycle_time = app.buffer_mgr.cycle_data[ch].time
       wavelength = app.buffer_mgr.cycle_data[ch].wavelength
   ```
   
   RECOMMENDED:
   - Add wrapper method to BufferManager
   - `get_channel_export_data(channel, format='long'|'wide')`
   - Handles padding, deduplication, formatting
   ```

4. **Move Cycle Deduplication to DataCollector**
   ```python
   # DataCollector.add_cycle() should check for duplicates
   def add_cycle(self, cycle_data: dict) -> None:
       cycle_id = cycle_data.get('cycle_id') or cycle_data.get('cycle_num')
       if cycle_id not in self._cycle_ids_seen:
           self.cycles.append(cycle_data)
           self._cycle_ids_seen.add(cycle_id)
   ```

### MEDIUM PRIORITY (Cleanup)

5. **Standardize Directory Structure**
   ```
   CURRENT: Inconsistent defaults
   RECOMMENDED:
   - Export: ~/Documents/Affilabs Data/<user>/exports/
   - Recording: ~/Documents/Affilabs Data/<user>/recordings/
   - Autosave: ~/Documents/Affilabs Data/<user>/autosave/
   ```

6. **Implement Smart Auto-Save (Not Dumb 60-Second)**
   ```python
   # CURRENT: Every 60 seconds (expensive)
   # RECOMMENDED:
   # - Save on cycle completion (not periodic)
   # - Save before stop_recording()
   # - User can toggle auto-save on/off
   # - Implement incremental append (not full rewrite)
   ```

7. **Standardize Metadata Format**
   ```python
   # Create MetadataBuilder that generates same structure
   # for all export paths
   metadata = {
       "recording_start": "ISO8601",
       "recording_end": "ISO8601",
       "operator": "...",
       "device_serial": "...",
       "cycles_count": int,
       "flags_count": int,
       "events_count": int,
       "channels": [...],
       "filters": {...},
       ...
   }
   ```

### LOW PRIORITY (Enhancement)

8. **Create ExportPresets Configuration**
   ```python
   # ~/.affilabs/export_presets.json
   {
       "quick": {"format": "csv", "include_metadata": false},
       "analysis": {"format": "xlsx", "include_all": true},
       "publication": {"format": "csv", "precision": 2}
   }
   ```

9. **Add Export History/Audit Trail**
   - Log all exports with timestamp, user, destination
   - Track who exported what when
   - Useful for regulatory compliance (21 CFR Part 11)

10. **Implement Format Validators**
    - Verify Excel sheets have correct structure
    - Check cycle IDs are unique
    - Validate timestamp ordering

---

## 14. CODE DEBT ITEMS

### Dead Code
- `affilabs/services/excel_exporter.py` - Instantiated but never used
  - Solution: Replace inline Excel code in recording_manager and export_helpers with calls to this service

### Technical Debt
- Deduplication logic appears in 3 files
- Channel data formatting appears in 2 files
- Excel export logic appears in 2-3 files

### Architectural Issues
- Mixed data sources (buffer_mgr vs data_collector) - no abstraction
- Export paths accessed directly from main.py - tight coupling
- No unified export service interface

---

## 15. TESTING GAPS

### Not Currently Validated:
- [ ] Export button data matches Record button data
- [ ] Cycles aren't duplicated in Excel export
- [ ] All 4 channels export correctly even if some have no data
- [ ] Metadata correctly formatted across all export paths
- [ ] Auto-save doesn't corrupt file if stopped mid-write
- [ ] Directory creation works for all export paths
- [ ] Large dataset export doesn't hang UI

### Recommended Tests:
```python
# test_export_consistency.py
def test_export_button_vs_record_button():
    # Record 100 data points
    # Export two ways
    # Compare Excel sheets should be identical

def test_cycle_deduplication():
    # Add same cycle 5 times
    # Export to Excel
    # Cycles sheet should have 1 row

def test_all_export_formats():
    # Try exporting as xlsx, csv, json
    # Each should complete without error
    # Data should be readable
```

---

## 16. FINAL RECOMMENDATIONS PRIORITY

**URGENT**: Refactor Excel export logic to use ExcelExporter service
- **Impact**: Reduces bugs, improves maintainability, enables future enhancements
- **Effort**: 2-3 hours
- **Benefit**: Single source of truth, clear abstraction

**HIGH**: Unify data source access 
- **Impact**: Export button will be consistent with Record button
- **Effort**: 1-2 hours  
- **Benefit**: Data integrity, easier debugging

**MEDIUM**: Consolidate CSV export paths
- **Impact**: Clear long vs wide format choices
- **Effort**: 3-4 hours
- **Benefit**: Better user control, documented formats

**LOW**: Clean up directory structure
- **Impact**: Users have organized saved data
- **Effort**: 1 hour
- **Benefit**: Better UX, easier data management

---

## Appendix: File Locations Quick Reference

| Component | File | Lines | Function |
|---|---|---|---|
| Export Button Handler | main.py | 9516-9518 | `_on_export_requested()` |
| Export Implementation | export_helpers.py | 319-590 | `export_requested()` |
| Record Handler | recording_manager.py | 103-132 | `stop_recording()` |
| Record Save | recording_manager.py | 134-296 | `_save_to_file()` |
| Quick CSV | export_helpers.py | 31-135 | `quick_export_csv()` |
| Autosave | export_helpers.py | 137-318 | `autosave_cycle_data()` |
| Image Export | export_helpers.py | 627-730 | `quick_export_image()` |
| Edits Save | edits_tab.py | 5097-5170 | `_save_cycles_to_excel()` |
| Excel Exporter (Unused) | excel_exporter.py | 46-362 | `export_to_excel()` |
| Data Collector | data_collector.py | 1-208 | `DataCollector` class |
