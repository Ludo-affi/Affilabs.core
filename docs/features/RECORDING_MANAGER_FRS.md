# RECORDING_MANAGER_FRS — Data Recording & Export System

**Source:** `affilabs/core/recording_manager.py` (404 lines)  
**Delegates to:** `DataCollector` (236 lines), `ExcelExporter` (357 lines)  
**Consumed by:** `main.py`, `EditsTab`, `CycleManager`, `FlagManager`, `InjectionCoordinator`  
**Version:** Affilabs.core v2.0.5 beta  
**Status:** Code-verified 2026-02-19

---

## 1. Overview

`RecordingManager` orchestrates the data recording lifecycle with a **3-layer architecture**:

```
┌──────────────────────────────────────────────────┐
│ RecordingManager (Orchestration Layer)          │
│ - Recording lifecycle (start/stop)              │
│ - Auto-save scheduling                          │
│ - Signal emission (UI coordination)             │
│ - User experiment count tracking                │
└──────────────────────────────────────────────────┘
                      ↓
┌──────────────────────────────────────────────────┐
│ DataCollector (In-Memory Storage Layer)         │
│ - Accumulates raw_data_rows, cycles, flags      │
│ - Manages events, metadata, analysis_results    │
│ - Deduplicates cycles by cycle_id               │
│ - Provides data snapshots for export            │
└──────────────────────────────────────────────────┘
                      ↓
┌──────────────────────────────────────────────────┐
│ ExcelExporter (File I/O Layer)                  │
│ - Multi-sheet Excel workbook generation         │
│ - 7 sheets: Raw Data, Channels XY, Cycles,      │
│   Events, Flags, Analysis, Metadata             │
│ - CSV/JSON fallback formats                     │
│ - Timestamp normalization (t=0 at start)        │
└──────────────────────────────────────────────────┘
```

**Benefits of separation:**
- **Single Responsibility** — Each layer has one job
- **Testable** — Can test data accumulation without file I/O
- **Swappable** — Easy to add CSV, JSON, SQL, cloud storage exporters
- **Thread-safe potential** — Locking can be added to DataCollector only

---

## 2. Recording Modes

### Mode 1: File Recording (Live Save)

**Trigger:** `start_recording(filename="/path/to/file.xlsx")`

**Behavior:**
- File created immediately on start
- Auto-save every 60 seconds (configurable via `auto_save_interval`)
- Final save on stop
- User experiment count incremented on stop

**Use case:** Long-running experiments where data must be preserved even if app crashes.

### Mode 2: Memory-Only Recording

**Trigger:** `start_recording(filename=None)`

**Behavior:**
- Data accumulates in `DataCollector` only
- No file created until user clicks Export
- No auto-save (data only in RAM)
- User experiment count **not** incremented on stop

**Use case:** Short tests, demos, or when user wants to review data before deciding whether to save.

---

## 3. State Variables

Managed by `RecordingManager`:

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| `is_recording` | `bool` | `False` | Recording active flag |
| `current_file` | `str \| None` | `None` | Full path to output file (None = memory-only mode) |
| `recording_start_offset` | `float` | `0.0` | Elapsed time when recording started (for t=0 export) |
| `output_directory` | `Path` | `~/Documents/Affilabs Data` | Default output directory (overridden by `get_user_output_directory()`) |
| `auto_save_interval` | `int` | `60` | Seconds between auto-saves (file mode only) |
| `last_save_time` | `float` | `0` | Unix timestamp of last auto-save |
| `data_mgr` | `DataAcquisitionManager` | — | Reference to acquisition manager |
| `buffer_mgr` | `BufferManager \| None` | — | Reference to buffer manager (for Channels XY export) |
| `user_manager` | `UserProfileManager \| None` | — | Reference to user manager (for experiment count) |
| `data_collector` | `DataCollector` | — | In-memory data accumulation delegate |
| `excel_exporter` | `ExcelExporter` | — | File I/O delegate |

Managed by `DataCollector`:

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| `raw_data_rows` | `list[dict]` | `[]` | Raw SPR data points: `[{'time': float, 'channel': str, 'value': float}]` |
| `events` | `list[tuple]` | `[]` | Event log: `[(timestamp, description), ...]` |
| `cycles` | `list[dict]` | `[]` | Cycle metadata from `Cycle.to_export_dict()` |
| `flags` | `list[dict]` | `[]` | Flag markers: `[{'type': str, 'channel': str, 'time': float, 'spr': float, ...}]` |
| `metadata` | `dict[str, Any]` | `{}` | Key-value metadata (device_id, user, detector_model, etc.) |
| `analysis_results` | `list[dict]` | `[]` | Analysis measurements (not used in v2.0.5) |
| `_cycle_ids_seen` | `set[str \| int]` | `set()` | Deduplication tracker for cycles |
| `recording_start_time` | `float \| None` | `None` | Unix timestamp when recording started |

---

## 4. Qt Signals

All signals are emitted by `RecordingManager` (inherits `QObject`):

| Signal | Payload | Purpose |
|--------|---------|---------|
| `recording_started` | `str` (filename or "memory") | Notify UI recording has begun |
| `recording_stopped` | — | Notify UI recording has ended |
| `recording_error` | `str` (error message) | Notify UI of recording failure |
| `event_logged` | `(str, float)` (description, timestamp) | Notify UI of new event (for live event log display) |

**Connection pattern:**
```python
recording_mgr.recording_started.connect(main_window._on_recording_started)
recording_mgr.recording_stopped.connect(main_window._on_recording_stopped)
recording_mgr.recording_error.connect(main_window._show_error_dialog)
recording_mgr.event_logged.connect(main_window._update_event_log_widget)
```

---

## 5. Recording Lifecycle Methods

### `start_recording(filename: str | None = None, time_offset: float = 0.0)`

**Trigger:** User clicks Start Recording button, or method execution begins.

**Pre-conditions:**
- `is_recording == False` (guards against double-start)

**Flow:**
```
1. Guard: if is_recording, log warning → return
2. Set state:
   - is_recording = True
   - current_file = filename
   - recording_start_offset = time_offset
   - last_save_time = time.time()
3. Start data collection:
   - data_collector.start_collection(start_time=time.time())
   - Initializes metadata with {'recording_start': '2026-02-19 10:30:15'}
4. If filename provided (file mode):
   - Create parent directories: filepath.parent.mkdir(parents=True, exist_ok=True)
   - Log: "Recording started - saving to file: {filename}"
   - Emit: recording_started.emit(filename)
5. Else (memory-only mode):
   - Log: "Recording started (data collecting to memory - will save on Export)"
   - Emit: recording_started.emit("memory")
```

**Error handling:**
- Exception caught → `recording_error.emit(f"Failed to start recording: {e}")`
- Cleanup via `_cleanup_recording()` (sets `is_recording=False`, clears data)

**Callers:**
- `main.py` — Start Recording button (`_on_start_recording_clicked`)
- `CycleManager` — Method execution start (`execute_method()`)

### `stop_recording()`

**Trigger:** User clicks Stop Recording button, or method execution completes.

**Pre-conditions:**
- `is_recording == True` (silent return if False)

**Flow:**
```
1. Guard: if not is_recording, return
2. If file mode (current_file is not None):
   - Final save: _save_to_file()
   - Log: "Recording stopped - final save to: {current_file}"
   - Increment user experiment count:
     - user_manager.increment_experiment_count() → returns new count
     - Log: "Experiment count incremented: {new_count}"
3. Else (memory-only mode):
   - Log: "Recording stopped (data in memory - click Export to save)"
4. Clean up:
   - is_recording = False
   - current_file = None
5. Emit: recording_stopped.emit()
```

**Error handling:**
- Exception caught → `recording_error.emit(f"Error stopping recording: {e}")`
- Cleanup via `_cleanup_recording()`

**Experiment count increment:**
Only happens in **file mode** (when `current_file` is not None). Memory-only recordings do not count as experiments.

**Callers:**
- `main.py` — Stop Recording button (`_on_stop_recording_clicked`)
- `CycleManager` — Method execution complete (`on_method_complete()`)

---

## 6. Data Ingestion Methods

### `record_data_point(data: dict)`

**Purpose:** Add a single SPR measurement to recording.

**Input format:**
```python
data = {
    'time': float,      # Elapsed time in seconds (or absolute timestamp)
    'channel': str,     # 'a', 'b', 'c', or 'd'
    'value': float,     # Wavelength in nm
}
```

**Flow:**
```
1. Guard: if not is_recording, return
2. Normalize data:
   - row_data = {'time': data.get('time', None), 'channel': ..., 'value': ...}
3. Add to collector:
   - data_collector.add_data_point(row_data)
4. Auto-save check (file mode only):
   - If current_file and (time.time() - last_save_time >= auto_save_interval):
     - _save_to_file()
     - last_save_time = time.time()
```

**Auto-save interval:** Default 60 seconds, configurable via `auto_save_interval` property.

**Caller:**
- `main.py._on_spectrum_acquired()` — Called for every spectrum acquired (post-processing)

### `add_cycle(cycle_data: dict)`

**Purpose:** Add cycle metadata to recording.

**Input format:**
```python
cycle_data = Cycle.to_export_dict()  # Returns dict with:
{
    'cycle_id': str | int,           # Unique cycle identifier
    'cycle_num': int,                # 1-indexed cycle number
    'type': str,                     # 'Baseline', 'Sample', 'Regeneration', etc.
    'start_time_sensorgram': float,  # Absolute start time (seconds)
    'end_time_sensorgram': float,    # Absolute end time
    'duration_minutes': float,       # Actual duration
    'concentration_value': str,      # e.g., "100 nM"
    'channel': str,                  # 'A', 'B', 'C', 'D', or 'All'
    'delta_spr_by_channel': dict,    # {'A': -12.5, 'B': -14.0, ...}
    'flag_data': list[dict],         # [{'type': 'injection', 'time': 120.0}, ...]
    'note': str,                     # User note
    ...
}
```

**Deduplication:**
- `DataCollector.add_cycle()` checks `cycle_id` or `cycle_num` against `_cycle_ids_seen` set
- If already seen → skip, log "Duplicate cycle skipped: ID {cycle_id}"
- Else → add to `_cycle_ids_seen` set + append to `cycles` list

**Caller:**
- `CycleManager.complete_cycle()` — Called when cycle completes

### `add_flag(flag_data: dict)`

**Purpose:** Add flag marker to recording.

**Input format:**
```python
flag_data = {
    'type': str,            # 'injection', 'wash', 'spike', 'manual'
    'channel': str,         # 'a', 'b', 'c', 'd', or 'all'
    'time': float,          # Time in seconds (sensorgram time)
    'spr': float,           # SPR value at flag time (RU or nm)
    'timestamp': float,     # Unix timestamp when flag created
    'confidence': float,    # 0.0-1.0 (for auto-detected flags)
    'source': str,          # 'manual' or 'auto'
}
```

**No deduplication** — all flags are kept, even duplicates (user may want multiple marks at same time).

**Caller:**
- `FlagManager.add_flag()` — User manual flag placement or auto-detection

### `log_event(event: str, channel: str | None = None, flow: str | None = None, temp: str | None = None)`

**Purpose:** Add timestamped event to event log.

**Flow:**
```
1. timestamp = time.time()
2. Build event string:
   - event_parts = [event]
   - If channel: append "Channel={channel}"
   - If flow: append "Flow={flow}"
   - If temp: append "Temp={temp}"
   - event_str = " | ".join(event_parts)
3. Add to collector:
   - data_collector.add_event(event_str, timestamp)
4. Log: "Event logged: {event_str}"
5. Emit: event_logged.emit(event_str, timestamp)
```

**Example events:**
- `"Injection started | Channel=A | Flow=25 µL/min"`
- `"Valve switched to Sample"`
- `"Pump priming complete"`
- `"Calibration started"`

**Caller:**
- `CycleManager` — Injection start/stop, valve switches
- `PumpController` — Priming, aspiration, dispense
- `CalibrationService` — Calibration lifecycle events

### `update_metadata(key: str, value: any)`

**Purpose:** Add or update metadata entry.

**Storage:**
- All metadata is stored as strings in `DataCollector.metadata` dict
- Values auto-converted via `str(value)` when exported to Excel

**Common metadata keys:**
```python
{
    'recording_start': '2026-02-19 10:30:15',  # Auto-set by start_collection()
    'device_id': 'P4PRO-00123',
    'device_type': 'P4PRO',
    'firmware_version': '2.4.1',
    'detector_model': 'Flame-T',
    'detector_serial': 'FLMT09876',
    'user': 'alice',
    'sensor_chip': 'BK71-Gold',
    'buffer': 'PBS pH 7.4',
    'flow_rate': '25',
    'temperature': '25',
}
```

**Caller:**
- `main.py` — Device config on recording start
- `EditsTab` — User-entered metadata in metadata panel
- `CycleManager` — Method parameters (flow rate, temperature, etc.)

### `add_analysis_result(result_data: dict)` (Not Used in v2.0.5)

**Purpose:** Add kinetic analysis measurement to recording.

**Status:** Placeholder for future ML/kinetics analysis features. Not called in v2.0.5.

---

## 7. File I/O Methods

### `_save_to_file()` — Internal Auto-Save & Final Save (70 lines)

**Pre-conditions:**
- `current_file` is not None (file mode)

**Flow:**
```
1. Guard: if not current_file, return
2. Get raw_data_rows from collector
3. If no data: log warning → return
4. Convert to DataFrame: df_raw = pd.DataFrame(raw_data)
5. Sort by time + channel for consistent output
6. Determine file format from extension:

   ┌─ .xlsx ────────────────────────────────────────────┐
   │ A. Build Channels XY dataframe (optional):         │
   │    - ExportHelpers.build_channels_xy_dataframe()   │
   │    - Reads from buffer_mgr.timeline_data           │
   │    - Wide format: one row per time, cols per ch    │
   │ B. Call ExcelExporter.export_to_excel():           │
   │    - 7 sheets: Raw Data, Channels XY, Cycles,      │
   │      Events, Flags, Analysis, Metadata             │
   └────────────────────────────────────────────────────┘

   ┌─ .csv ─────────────────────────────────────────────┐
   │ - Simple flat format: df_raw.to_csv()              │
   │ - Columns: time, channel, value                    │
   │ - No cycles, events, or metadata                   │
   └────────────────────────────────────────────────────┘

   ┌─ .json ────────────────────────────────────────────┐
   │ - Full structured export:                          │
   │   {                                                │
   │     "raw_data": [...],                             │
   │     "cycles": [...],                               │
   │     "events": [...],                               │
   │     "metadata": {...}                              │
   │   }                                                │
   └────────────────────────────────────────────────────┘

7. Log: "Data saved to {filepath} ({len(raw_data)} rows)"
```

**Error handling:**
- Exception caught → `recording_error.emit(f"Failed to save: {e}")`

**Excel export details** (delegated to `ExcelExporter.export_to_excel()`):

#### Sheet 1: Raw Data
```
Columns: time, channel, value
- time: Elapsed time (seconds, t=0 at recording start)
- channel: 'a', 'b', 'c', 'd'
- value: Wavelength (nm)
```

#### Sheet 2: Channels XY (if buffer_mgr available)
```
Columns: Time A (s), Channel A (nm), Time B (s), Channel B (nm), ...
- Wide format: one row per time point
- Separate time column per channel (accounts for time misalignment)
- Built from buffer_mgr.timeline_data (numpy arrays)
```

**Fallback:** If no `buffer_mgr` or build fails, sheet is skipped.

#### Sheet 3: Cycles
```
Columns: All fields from Cycle.to_export_dict()
- cycle_id, cycle_num, type, start_time_sensorgram, end_time_sensorgram, duration_minutes,
  concentration_value, channel, delta_spr_by_channel, flag_data, note, ...
```

#### Sheet 4: Events
```
Columns: timestamp, event
- timestamp: Unix timestamp (absolute)
- event: "Injection started | Channel=A | Flow=25 µL/min"
```

#### Sheet 5: Flags
```
Columns: type, channel, time, spr, timestamp, confidence, source
```

#### Sheet 6: Analysis (empty in v2.0.5)
```
Columns: segment, channel, assoc_shift, dissoc_shift, ...
- Placeholder for future kinetics analysis
```

#### Sheet 7: Metadata
```
Columns: key, value
- All entries from DataCollector.metadata dict
```

**Timestamp normalization:**
- All `time` columns in **Raw Data** and **Channels XY** sheets are normalized to elapsed time: `time - recording_start_time`
- Result: t=0 at recording start, matches sensogram time axis

### `load_from_excel(filepath: Path) → dict`

**Purpose:** Load previously recorded data from Excel file.

**Delegated to:** `ExcelExporter.load_from_excel(filepath)`

**Returns:**
```python
{
    'Raw Data': DataFrame,
    'Channels XY': DataFrame (or 'Channel Data' for older exports),
    'Cycles': DataFrame,
    'Events': DataFrame,
    'Flags': DataFrame,
    'Metadata': DataFrame,
    'Analysis': DataFrame,
}
```

**Usage:**
- Not called by `RecordingManager` itself
- Called by `EditsTab._load_data_from_excel_internal()` to populate Edits tab from saved file

---

## 8. Configuration Methods

### `get_user_output_directory() → Path`

**Purpose:** Resolve user-specific output directory, creating it if needed.

**Path formula:**
```
If user_manager available and user set:
    ~/Documents/Affilabs Data/<username>/SPR_data/

Else (no user or no user_manager):
    ~/Documents/Affilabs Data/   (generic fallback)
```

**Auto-create:** `user_dir.mkdir(parents=True, exist_ok=True)`

**Callers:**
- `main.py._on_start_recording_clicked()` — Default directory for file dialog
- `EditsTab.export_raw_data()` — Default export location

### `set_output_directory(directory: Path)`

**Purpose:** Override default output directory (for testing or custom installs).

**Flow:**
```
1. Convert to Path: directory = Path(directory)
2. Create if missing: directory.mkdir(parents=True, exist_ok=True)
3. Update: self.output_directory = directory
4. Log: "Output directory set to: {directory}"
```

**Error handling:**
- Exception caught → `recording_error.emit(f"Invalid output directory: {e}")`

**Use case:** Rare — most users rely on `get_user_output_directory()` for automatic user-specific paths.

---

## 9. Status Query Methods

### `get_recording_info() → dict`

**Purpose:** Get current recording status for UI display.

**Returns:**
```python
If not recording:
    {
        'recording': False,
        'filename': None,
        'elapsed_time': 0,
        'event_count': 0,
    }

If recording:
    {
        'recording': True,
        'filename': str(current_file) or None,
        'elapsed_time': float,  # Seconds since start
        'event_count': int,     # Number of events logged
    }
```

**Used by:**
- `main.py._update_recording_status_label()` — Status bar display
- `main.py._on_timer_tick()` — Periodic UI updates

---

## 10. Internal Cleanup

### `_cleanup_recording()`

**Purpose:** Reset recording state and clear data (called on errors or double-stop).

**Flow:**
```
1. is_recording = False
2. current_file = None
3. data_collector.clear_all()
   - Clears: raw_data_rows, events, cycles, flags, analysis_results, metadata
   - Resets: _cycle_ids_seen, recording_start_time
```

**Callers:**
- `start_recording()` — On exception
- `stop_recording()` — On exception

---

## 11. DataCollector API (In-Memory Layer)

### Storage Collections

| Collection | Type | Contents |
|------------|------|----------|
| `raw_data_rows` | `list[dict]` | Raw SPR measurements: `[{'time': float, 'channel': str, 'value': float}]` |
| `events` | `list[tuple]` | Event log: `[(timestamp, description), ...]` |
| `cycles` | `list[dict]` | Cycle metadata from `Cycle.to_export_dict()` |
| `flags` | `list[dict]` | Flag markers: `[{'type': str, 'channel': str, 'time': float, ...}]` |
| `metadata` | `dict` | Key-value pairs: `{'device_id': 'P4PRO-00123', 'user': 'alice', ...}` |
| `analysis_results` | `list[dict]` | Analysis measurements (unused in v2.0.5) |

### Methods

| Method | Purpose |
|--------|---------|
| `start_collection(start_time)` | Initialize collections, set `recording_start_time`, add `recording_start` to metadata |
| `clear_all()` | Clear all collections, reset `_cycle_ids_seen`, set `recording_start_time = None` |
| `add_data_point(data)` | Append dict to `raw_data_rows` |
| `add_event(description, timestamp)` | Append `(timestamp, description)` to `events` |
| `add_cycle(cycle_data)` | Append to `cycles` if `cycle_id` not in `_cycle_ids_seen`, returns `True` if added |
| `add_flag(flag_data)` | Append dict to `flags` (no deduplication) |
| `update_metadata(key, value)` | Set `metadata[key] = value` |
| `add_analysis_result(result_data)` | Append dict to `analysis_results` (unused) |
| `get_summary()` | Returns dict with counts: `{'raw_data_points': int, 'events': int, 'cycles': int, ...}` |
| `get_all_data()` | Returns dict with all collections: `{'raw_data_rows': [...], 'events': [...], ...}` |
| `get_data_count()` | Returns `len(raw_data_rows)` |
| `get_elapsed_time()` | Returns `time.time() - recording_start_time` (0 if not started) |
| `has_data()` | Returns `True` if any collection is non-empty |

### Cycle Deduplication Logic

```python
def add_cycle(self, cycle_data: dict) -> bool:
    # Extract cycle ID (try cycle_id first, fall back to cycle_num)
    cycle_id = cycle_data.get('cycle_id') or cycle_data.get('cycle_num')
    
    if cycle_id is None:
        # No ID available - add anyway (no deduplication possible)
        self.cycles.append(cycle_data)
        return True
    
    # Check if already seen
    if cycle_id in self._cycle_ids_seen:
        logger.debug(f"Duplicate cycle skipped: ID {cycle_id}")
        return False
    
    # New cycle - add it
    self._cycle_ids_seen.add(cycle_id)
    self.cycles.append(cycle_data)
    return True
```

**Why deduplication?**
- `CycleManager.complete_cycle()` may be called multiple times for the same cycle (e.g., if user manually marks end, then method auto-completes)
- Prevents duplicate rows in Excel Cycles sheet

---

## 12. ExcelExporter API (File I/O Layer)

### `export_to_excel(filepath, raw_data_rows, cycles, flags, events, analysis_results, metadata, recording_start_time, alignment_data=None, channels_xy_dataframe=None)`

**Purpose:** Generate multi-sheet Excel workbook from in-memory data.

**Arguments:**

| Argument | Type | Purpose |
|----------|------|---------|
| `filepath` | `Path` | Output file path |
| `raw_data_rows` | `list[dict]` | Raw SPR data points |
| `cycles` | `list[dict]` | Cycle metadata |
| `flags` | `list[dict]` | Flag markers |
| `events` | `list[tuple]` | Event log |
| `analysis_results` | `list[dict]` | Analysis measurements |
| `metadata` | `dict` | Key-value metadata |
| `recording_start_time` | `float` | Unix timestamp for t=0 normalization |
| `alignment_data` | `dict \| None` | Optional: `{cycle_idx: {'channel': str, 'shift': float}}` for Edits export |
| `channels_xy_dataframe` | `DataFrame \| None` | Optional: Pre-built wide-format DataFrame (replaces Channel Data sheet) |

**Sheet generation:**

1. **Raw Data** — Long format, one row per data point
2. **Channels XY** (or **Channel Data**) — Wide format, one row per time point
3. **Cycles** — One row per cycle
4. **Events** — One row per event
5. **Flags** — One row per flag
6. **Analysis** — One row per analysis result (empty in v2.0.5)
7. **Metadata** — Two columns: key, value

**Timestamp normalization:**
- All `time` columns in Raw Data and Channels XY sheets: `time - recording_start_time`
- Result: t=0 matches sensogram UI

**Error handling:**
- `ImportError` if pandas/openpyxl not installed
- `IOError` if file cannot be written (permissions, disk full, etc.)

### `load_from_excel(filepath) → dict`

**Purpose:** Parse previously exported Excel file.

**Returns:** Dict mapping sheet name → DataFrame

**Used by:** `EditsTab._load_data_from_excel_internal()`

---

## 13. Data Flow Diagrams

### Flow 1: File Recording (Live Save)

```
User: Click Start Recording, enter filename "experiment_001.xlsx"
  ↓
main.py._on_start_recording_clicked()
  ↓
recording_mgr.start_recording(filename="/path/experiment_001.xlsx")
  ├→ Set: is_recording=True, current_file=filepath
  ├→ data_collector.start_collection(start_time=time.time())
  │   └→ recording_start_time=timestamp, metadata={'recording_start': '2026-02-19 10:30:15'}
  ├→ Create parent dirs: filepath.parent.mkdir()
  └→ Emit: recording_started.emit(filepath)
  ↓
[Acquisition loop running...]
  ↓
main.py._on_spectrum_acquired(data)
  ↓
recording_mgr.record_data_point({'time': 123.4, 'channel': 'a', 'value': 620.5})
  ├→ data_collector.add_data_point(row_data)
  │   └→ raw_data_rows.append({'time': 123.4, 'channel': 'a', 'value': 620.5})
  └→ Auto-save check:
      └→ If (time.time() - last_save_time) >= 60s:
          └→ _save_to_file()
              └→ excel_exporter.export_to_excel(...)
  ↓
[60 seconds later...]
  ↓
_save_to_file()
  ├→ df_raw = pd.DataFrame(raw_data_rows)
  ├→ Sort by time + channel
  ├→ Build Channels XY sheet (if buffer_mgr available)
  └→ excel_exporter.export_to_excel(
         filepath=current_file,
         raw_data_rows=data_collector.raw_data_rows,
         cycles=data_collector.cycles,
         flags=data_collector.flags,
         events=data_collector.events,
         ...
     )
      └→ Write 7-sheet Excel workbook
  ↓
[User clicks Stop Recording]
  ↓
recording_mgr.stop_recording()
  ├→ Final save: _save_to_file()
  ├→ Increment user experiment count:
  │   └→ user_manager.increment_experiment_count() → new_count
  ├→ Cleanup: is_recording=False, current_file=None
  └→ Emit: recording_stopped.emit()
```

### Flow 2: Memory-Only Recording → Manual Export

```
User: Click Start Recording (no filename prompt)
  ↓
recording_mgr.start_recording(filename=None)
  ├→ Set: is_recording=True, current_file=None
  ├→ data_collector.start_collection()
  └→ Emit: recording_started.emit("memory")
  ↓
[Data accumulates in memory via record_data_point()...]
  ↓
[User clicks Stop Recording]
  ↓
recording_mgr.stop_recording()
  ├→ Skip save (current_file is None)
  ├→ Skip experiment count increment (memory-only)
  ├→ Cleanup: is_recording=False
  └→ Emit: recording_stopped.emit()
  ↓
[User navigates to Edits tab, clicks Export]
  ↓
edits_tab._export_raw_data()
  ↓
QFileDialog.getSaveFileName() → user selects "my_data.xlsx"
  ↓
excel_exporter.export_to_excel(
    filepath="my_data.xlsx",
    raw_data_rows=recording_mgr.data_collector.raw_data_rows,
    cycles=recording_mgr.data_collector.cycles,
    ...
)
  └→ Write 7-sheet Excel workbook
```

### Flow 3: Cycle & Flag Recording

```
CycleManager.complete_cycle(cycle)
  ↓
cycle_data = cycle.to_export_dict()
  ↓
recording_mgr.add_cycle(cycle_data)
  ↓
data_collector.add_cycle(cycle_data)
  ├→ Extract: cycle_id = cycle_data.get('cycle_id') or cycle_data.get('cycle_num')
  ├→ Check: if cycle_id in _cycle_ids_seen → skip (duplicate)
  ├→ Else: _cycle_ids_seen.add(cycle_id), cycles.append(cycle_data)
  └→ Log: "Cycle added: Sample (Cycle 3)"
  ↓
[Later: User places manual flag]
  ↓
FlagManager.add_flag(flag_type='injection', time=120.0, channel='a', spr=-12.5, source='manual')
  ↓
recording_mgr.add_flag({'type': 'injection', 'time': 120.0, 'channel': 'a', 'spr': -12.5, ...})
  ↓
data_collector.add_flag(flag_data)
  └→ flags.append(flag_data)
```

---

## 14. Auto-Save Strategy

### File Mode Auto-Save

**Trigger:** `record_data_point()` checks `time.time() - last_save_time >= auto_save_interval`

**Interval:** Default 60 seconds (configurable)

**Behavior:**
```python
if self.current_file:  # File mode only
    current_time = time.time()
    if current_time - self.last_save_time >= self.auto_save_interval:
        self._save_to_file()
        self.last_save_time = current_time
```

**Performance impact:**
- Saves entire dataset every 60 seconds
- For 10k data points: ~200ms to write Excel file
- Non-blocking (no UI freeze)

**Benefits:**
- Data preserved even if app crashes
- User can resume from last auto-save

**Limitations:**
- Not truly continuous (60s gaps)
- No incremental append (full file rewrite each time)

### Memory-Only Mode: No Auto-Save

**Reason:** No `current_file` → no file to write to.

**Risk:** All data lost if app crashes before user exports.

**Mitigation:** Warn user in UI: "Recording to memory - data not saved yet"

---

## 15. Excel Export Schema (7 Sheets)

### Sheet 1: Raw Data

```
┌──────────┬─────────┬────────┐
│ time     │ channel │ value  │
├──────────┼─────────┼────────┤
│ 0.000    │ a       │ 620.50 │
│ 0.100    │ a       │ 620.51 │
│ 0.100    │ b       │ 621.20 │
│ 0.200    │ a       │ 620.52 │
│ ...      │ ...     │ ...    │
└──────────┴─────────┴────────┘

- time: Elapsed seconds (t=0 at recording start)
- channel: 'a', 'b', 'c', 'd'
- value: Wavelength (nm)
```

### Sheet 2: Channels XY (Wide Format)

```
┌───────────┬──────────────┬───────────┬──────────────┬─────┐
│ Time A (s)│ Channel A (nm)│ Time B (s)│ Channel B (nm)│ ... │
├───────────┼──────────────┼───────────┼──────────────┼─────┤
│ 0.000     │ 620.50       │ 0.050     │ 621.20       │ ... │
│ 0.100     │ 620.51       │ 0.150     │ 621.21       │ ... │
│ ...       │ ...          │ ...       │ ...          │ ... │
└───────────┴──────────────┴───────────┴──────────────┴─────┘

- Separate time column per channel (accounts for slight time misalignment)
- One row per time point
- Easier for external plotting tools (Excel, Origin, TraceDrawer)
```

**Build source:** `buffer_mgr.timeline_data` (numpy arrays) via `ExportHelpers.build_channels_xy_dataframe()`

**Fallback:** If `buffer_mgr` unavailable or build fails, sheet is skipped.

### Sheet 3: Cycles

```
┌──────────┬───────────┬──────────┬──────────────────────┬──────────────────────┬─────┐
│ cycle_id │ cycle_num │ type     │ start_time_sensorgram│ end_time_sensorgram  │ ... │
├──────────┼───────────┼──────────┼──────────────────────┼──────────────────────┼─────┤
│ cy_001   │ 1         │ Baseline │ 0.0                  │ 300.0                │ ... │
│ cy_002   │ 2         │ Sample   │ 300.0                │ 600.0                │ ... │
│ ...      │ ...       │ ...      │ ...                  │ ...                  │ ... │
└──────────┴───────────┴──────────┴──────────────────────┴──────────────────────┴─────┘

- All fields from Cycle.to_export_dict()
- Additional fields: concentration_value, channel, delta_spr_by_channel, flag_data, note
```

### Sheet 4: Events

```
┌───────────────┬────────────────────────────────────────────┐
│ timestamp     │ event                                      │
├───────────────┼────────────────────────────────────────────┤
│ 1708345815.23 │ Injection started | Channel=A | Flow=25... │
│ 1708345900.45 │ Valve switched to Sample                   │
│ ...           │ ...                                        │
└───────────────┴────────────────────────────────────────────┘

- timestamp: Unix timestamp (absolute, not normalized)
- event: Concatenated string with pipe separators
```

### Sheet 5: Flags

```
┌───────────┬─────────┬────────┬────────┬───────────────┬────────────┬────────┐
│ type      │ channel │ time   │ spr    │ timestamp     │ confidence │ source │
├───────────┼─────────┼────────┼────────┼───────────────┼────────────┼────────┤
│ injection │ a       │ 120.0  │ -12.5  │ 1708345935.67 │ 0.95       │ auto   │
│ wash      │ all     │ 240.0  │ -8.0   │ 1708346055.89 │ 1.0        │ manual │
│ ...       │ ...     │ ...    │ ...    │ ...           │ ...        │ ...    │
└───────────┴─────────┴────────┴────────┴───────────────┴────────────┴────────┘

- type: 'injection', 'wash', 'spike', 'manual'
- time: Sensorgram time (seconds, t=0 at recording start)
- spr: SPR value at flag time (RU or nm)
- confidence: 0.0-1.0 for auto-detected flags (1.0 for manual)
```

### Sheet 6: Analysis (Empty in v2.0.5)

```
┌─────────┬─────────┬──────────────┬──────────────┬─────┐
│ segment │ channel │ assoc_shift  │ dissoc_shift │ ... │
├─────────┼─────────┼──────────────┼──────────────┼─────┤
│         │         │              │              │     │
└─────────┴─────────┴──────────────┴──────────────┴─────┘

- Placeholder for future kinetics analysis features
- Not populated in v2.0.5
```

### Sheet 7: Metadata

```
┌─────────────────────┬──────────────────────────┐
│ key                 │ value                    │
├─────────────────────┼──────────────────────────┤
│ recording_start     │ 2026-02-19 10:30:15      │
│ device_id           │ P4PRO-00123              │
│ device_type         │ P4PRO                    │
│ firmware_version    │ 2.4.1                    │
│ detector_model      │ Flame-T                  │
│ detector_serial     │ FLMT09876                │
│ user                │ alice                    │
│ sensor_chip         │ BK71-Gold                │
│ buffer              │ PBS pH 7.4               │
│ flow_rate           │ 25                       │
│ temperature         │ 25                       │
│ ...                 │ ...                      │
└─────────────────────┴──────────────────────────┘

- All entries from DataCollector.metadata dict
- Values auto-converted to strings
```

---

## 16. Known Issues & Limitations

### Issue #1: Auto-Save Rewrites Entire File

**Current:** Full file rewrite every 60 seconds in file mode.

**Problem:** For long experiments (>10k data points), this can take 200-500ms per save.

**Expected:** Incremental append would be more efficient.

**Workaround:** Increase `auto_save_interval` to reduce frequency (e.g., 300s for 5-minute saves).

**Fix:** Switch to a database backend (SQLite) for true incremental writes, or use HDF5 for large datasets.

### Issue #2: Memory-Only Mode Loses Data on Crash

**Current:** Data only in RAM until user manually exports.

**Problem:** App crash or power loss = complete data loss.

**Expected:** Some users expect "Start Recording" to always create a file.

**Workaround:** Always provide filename when starting recording.

**Fix:** Force filename prompt on start, or auto-save to temp file even in memory mode.

### Issue #3: No Compression for Large Datasets

**Current:** Excel files can grow to 50+ MB for long recordings.

**Expected:** Some compression or binary format (HDF5, Parquet).

**Workaround:** Use CSV export for smaller files (but loses cycles/events/metadata).

**Fix:** Add HDF5 export option via `h5py` or use Parquet via `pandas.to_parquet()`.

### Issue #4: Channels XY Sheet Skipped if buffer_mgr Missing

**Current:** If `buffer_mgr` is `None` or build fails, Channels XY sheet is silently skipped.

**Expected:** Fallback to generating from `raw_data_rows` (possible but not implemented).

**Impact:** Older exports or test scenarios without `buffer_mgr` lose wide-format sheet.

**Fix:** Add fallback builder that pivots `raw_data_rows` into wide format.

### Issue #5: No TraceDrawer Live Export

**Expected:** TraceDrawer users want live CSV updates during recording for real-time external analysis.

**Current:** TraceDrawer export only available from Edits tab (post-recording).

**Planned:** Add `tracedrawer_live_export: bool` flag to `start_recording()` → write separate CSV file every auto-save interval.

**Documented:** Mentioned in `EDITS_EXPORT_FRS.md` as a gap.

---

## 17. Integration Points

### → DataAcquisitionManager

**Data passed:**
- `main.py._on_spectrum_acquired()` → `recording_mgr.record_data_point(data)`
- Called for **every** spectrum after processing

**Frequency:** ~10 Hz (10 spectra/second) per channel = ~40 Hz total

### → CycleManager

**Methods called:**
- `complete_cycle()` → `recording_mgr.add_cycle(cycle.to_export_dict())`
- `execute_method()` → `recording_mgr.start_recording(filename=auto_generated_name)`
- `on_method_complete()` → `recording_mgr.stop_recording()`

### → FlagManager

**Methods called:**
- `add_flag()` → `recording_mgr.add_flag(flag_data)`

### → InjectionCoordinator

**Methods called:**
- Injection start/stop → `recording_mgr.log_event("Injection started", channel='A')`

### → PumpController

**Methods called:**
- Priming start/stop → `recording_mgr.log_event("Pump priming", flow='100 µL/min')`

### → CalibrationService

**Methods called:**
- Calibration lifecycle → `recording_mgr.log_event("Calibration started")`

### → EditsTab

**Data read:**
- `recording_mgr.data_collector.raw_data_rows` → populate Edits graph
- `recording_mgr.data_collector.cycles` → populate cycles table
- `recording_mgr.data_collector.metadata` → populate metadata panel

**Export:**
- `EditsTab._export_raw_data()` → calls `excel_exporter.export_to_excel()` directly

### → UserProfileManager

**Methods called:**
- `stop_recording()` → `user_manager.increment_experiment_count()`

**Data passed:**
- `get_user_output_directory()` → `user_manager.get_current_user()`

### → BufferManager

**Data read:**
- `_save_to_file()` → `buffer_mgr.timeline_data` for Channels XY sheet

---

## 18. Testing Scenarios

### Scenario 1: File Recording with Auto-Save
1. Start recording with filename `test_001.xlsx`
2. Verify: File created immediately (empty or with minimal metadata)
3. Let acquisition run for 90 seconds
4. Verify: File updated after 60s (auto-save triggered)
5. Stop recording
6. Verify: Final save + user experiment count incremented
7. Open Excel file
8. Verify: 7 sheets present (Raw Data, Channels XY, Cycles, Events, Flags, Analysis, Metadata)

### Scenario 2: Memory-Only Recording → Manual Export
1. Start recording without filename prompt
2. Verify: `recording_started` signal emits "memory"
3. Let acquisition run for 60 seconds
4. Verify: No file created (data only in RAM)
5. Stop recording
6. Verify: `recording_stopped` signal emitted, user experiment count **not** incremented
7. Navigate to Edits tab → Export
8. Save as `manual_export.xlsx`
9. Verify: Excel file created with all data

### Scenario 3: Cycle & Flag Recording
1. Start memory-only recording
2. Complete 3 cycles via `CycleManager`
3. Verify: `data_collector.cycles` has 3 entries
4. Add 2 manual flags via `FlagManager`
5. Verify: `data_collector.flags` has 2 entries
6. Stop recording → Export to Excel
7. Open Excel → Cycles sheet: verify 3 rows
8. Open Excel → Flags sheet: verify 2 rows

### Scenario 4: Duplicate Cycle Handling
1. Start recording
2. Call `add_cycle({'cycle_id': 'cy_001', 'type': 'Sample', ...})`
3. Verify: Cycle added, `_cycle_ids_seen = {'cy_001'}`
4. Call `add_cycle({'cycle_id': 'cy_001', 'type': 'Sample', ...})` again
5. Verify: Skipped, log "Duplicate cycle skipped: ID cy_001"
6. Stop → Export → Verify Cycles sheet has only 1 row

### Scenario 5: Event Logging
1. Start recording
2. Call `log_event("Injection started", channel='A', flow='25 µL/min')`
3. Verify: `event_logged` signal emitted with "Injection started | Channel=A | Flow=25 µL/min"
4. Stop → Export → Open Events sheet
5. Verify: Row with formatted event string

### Scenario 6: Load from Excel
1. Load previously exported file via `EditsTab._load_data_from_excel()`
2. Verify: All sheets parsed into DataFrames
3. Verify: `_loaded_cycles_data` populated
4. Verify: Edits graph displays loaded data

---

## 19. Performance Notes

### Data Accumulation — Memory Growth

**Rate:** ~40 data points/second (4 channels × 10 Hz)

**Memory per point:** ~100 bytes (dict overhead + float storage)

**1-hour recording:** 40 pts/s × 3600s = **144k points** = ~14 MB RAM

**10-hour recording:** **1.44M points** = ~140 MB RAM

**Conclusion:** Memory-only mode feasible for up to ~10 hours on modern hardware.

### Excel Export Time

| Dataset Size | Export Time | File Size |
|--------------|-------------|-----------|
| 10k points | ~50 ms | ~200 KB |
| 100k points | ~300 ms | ~2 MB |
| 1M points | ~3 s | ~20 MB |

**Bottleneck:** pandas DataFrame creation + openpyxl write.

**Optimization:** Already uses chunked writes; further gains require binary formats (HDF5, Parquet).

### Auto-Save Overhead

**Frequency:** Every 60 seconds

**Duration:** 50-300ms (scales with dataset size)

**UI impact:** Non-blocking (runs in main thread but fast enough to not freeze UI)

**Thread-safety note:** Not currently threaded. Could move to background thread for large datasets.

---

## 20. Future Enhancements

### 1. Incremental Export (SQLite Backend)
Replace in-memory list storage with SQLite database → true incremental writes, no auto-save delays.

**Benefit:** Scalable to 100+ hour recordings without memory issues.

### 2. TraceDrawer Live Export
Add `tracedrawer_live_export: bool` flag → write separate CSV every auto-save interval.

**Benefit:** Real-time external analysis during recording.

### 3. Compression (HDF5 or Parquet)
Add export format options: `.h5` (HDF5), `.parquet` (Parquet).

**Benefit:** 10× smaller files for long recordings.

### 4. Background Thread for Auto-Save
Move `_save_to_file()` to separate thread → zero UI latency.

**Benefit:** Smooth UI for very large datasets.

### 5. Cloud Sync Integration
Add optional cloud backup: auto-upload to Google Drive, Dropbox, or S3 after each auto-save.

**Benefit:** Remote backup for critical experiments.

---

**Document End**
