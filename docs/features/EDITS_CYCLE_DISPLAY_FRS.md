# EDITS_CYCLE_DISPLAY_FRS — Cycle Rendering & Main Window Bridge

**Source:** `affilabs/ui_mixins/_edits_cycle_mixin.py` (1664 lines)  
**Owner:** `MainWindowPrototype` (via mixin)  
**Consumed by:** `EditsTab`, `SegmentManager`, `FlagManager`, `RecordingManager`  
**Version:** Affilabs.core v2.0.5 beta
**Status:** Code-verified 2026-02-24

---

## 1. Overview

`EditsCycleMixin` is the **bridge** between `MainWindowPrototype` and `EditsTab`. It orchestrates:

| Responsibility | Methods |
|----------------|---------|
| **EditsTab delegation** | `_update_edits_selection_view`, `_toggle_edits_channel`, `_export_edits_selection` |
| **Excel data loading** | `_load_data_from_excel`, `_load_data_from_excel_internal`, `_populate_edits_timeline_from_loaded_data` |
| **Graph interaction** | `_on_edits_graph_clicked`, `_add_edits_flag` |
| **Cycle selection & rendering** | `_on_cycle_selected_in_table` (402 lines), `_on_cycle_channel_changed`, `_on_cycle_shift_changed`, `_update_channel_source_combos` |
| **Segment management** | `_create_segment_from_selection`, `_refresh_segment_list`, `_delete_selected_segment`, `_export_segment_to_tracedrawer`, `_export_segment_to_json`, `_export_selected_segment_csv`, `_export_selected_segment_json` |
| **Reference traces** | `_clear_reference_graphs`, `_load_cycle_to_reference` |
| **Utility** | `_find_nearest_index` |
| **Demo data** | `_load_demo_data` (Ctrl+Shift+D shortcut) |

**Total:** 21 methods

This mixin was extracted from `affilabs_core_ui.py` during the v2.0.5 mixin refactor.

---

## 2. State Variables

Managed by `MainWindowPrototype` (not in mixin itself):

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| `_loaded_cycles_data` | `list[dict]` | `[]` | Cycle metadata from Excel Cycles sheet |
| `_loaded_raw_data` | `list[dict]` | `[]` | Raw SPR data points (time/channel/value) from Excel |
| `_loaded_metadata` | `dict` | `{}` | Metadata key-value pairs from Excel Metadata sheet |
| `_cycle_alignment` | `dict[int, dict]` | `{}` | Per-row alignment settings: `{row_idx: {'channel': str, 'shift': float, 'ref': str}}` |
| `edits_graph_curves` | `list[pg.PlotDataItem]` | 4 curves | Primary edits graph curves (Ch A, B, C, D) |
| `edits_reference_curves` | `list[list[pg.PlotDataItem]]` | 3×4 curves | Reference graph curves (3 slots × 4 channels) |
| `edits_reference_labels` | `list[QLabel]` | 3 labels | Reference graph slot labels |
| `edits_reference_cycle_data` | `list[int \| None]` | `[None, None, None]` | Cycle row indices loaded in each ref slot |
| `channel_source_combos` | `list[QComboBox]` | 4 combos | Channel source selectors for segment creation |
| `segment_list_combo` | `QComboBox` | — | Segment dropdown |
| `cycle_data_table` | `QTableWidget` | — | EditsTab cycle table (owned by EditsTab but accessed here) |

---

## 3. EditsTab Delegators

Three thin delegators that forward calls from main window to `EditsTab`:

### `_update_edits_selection_view()`
```python
if hasattr(self, 'edits_tab'):
    self.edits_tab._update_selection_view()
```
Triggers redraw of the primary edits graph with current selection cursors + filtered data.

### `_toggle_edits_channel(ch_idx, visible)`
```python
if hasattr(self, 'edits_tab'):
    self.edits_tab._toggle_channel(ch_idx, visible)
```
Shows/hides channel `ch_idx` (0=A, 1=B, 2=C, 3=D) on edits graph.

### `_export_edits_selection()`
```python
if hasattr(self, 'edits_tab'):
    self.edits_tab._export_selection()
```
Exports currently selected time range to Excel.

**Callers:** Main window toolbar buttons, keyboard shortcuts, menu actions.

---

## 4. Excel Data Loading

### `_load_data_from_excel()` — File Dialog Entry Point

Opens `QFileDialog.getOpenFileName` → calls `_load_data_from_excel_internal(file_path)`.

**Shortcut:** Ctrl+O (File > Open in menu bar)

### `_load_data_from_excel_internal(file_path: str)` — Core Parser (269 lines)

Parses Excel exports from previous sessions. Supports 3 sheet layout formats:

#### Format Priority

**Priority 1 — "Raw Data" sheet** (current export format):
```
Columns: time, channel, value
Rows: One per data point (long format)
```

**Priority 2 — "Channel Data" sheet** (current export format):
```
Columns: Time A (s), Channel A (nm), Time B (s), Channel B (nm), ...
Rows: One per timestamp (wide format)
```

**Priority 3 — Legacy per-channel sheets**:
```
Sheets: Channel_A, Channel_B, Channel_C, Channel_D
Columns: time_s, Channel_X_nm
```

#### Cycles Sheet Parsing

```
Expected columns (flexible):
- start_time_sensorgram / ACh1 (time range string "0-300")
- end_time_sensorgram
- type / Type
- concentration_value / Conc. / name
- note / Notes
- delta_spr_by_channel (dict as string, parsed via ast.literal_eval)
- concentrations (dict as string)
- flags (list as string)
- flag_data (list of dicts as string)
```

All columns from Excel are preserved in cycle dicts; known fields are type-coerced and normalized.

#### Metadata Sheet Parsing

```
Columns: key, value
Stored in: self._loaded_metadata, self.app.recording_mgr.data_collector.metadata
```

#### Storage Flow

```
1. Parse Excel → raw_data_rows (list[dict]) + cycles_data (list[dict])
2. Store in RecordingManager.data_collector:
   - raw_data_rows → data_collector.raw_data_rows
   - cycles_data → data_collector.cycles
   - metadata → data_collector.metadata
3. Store in main window:
   - cycles_data → self._loaded_cycles_data
   - metadata → self._loaded_metadata
4. Populate EditsTab:
   - edits_tab._loaded_metadata = metadata
   - edits_tab._populate_cycles_table(cycles_data)
   - edits_tab._update_selection_view()
5. Set timeline cursors to span all data
```

#### Error Handling

- Missing sheets: Falls through priority cascade
- Parse failures: `ast.literal_eval` wrapped in `try/except` → defaults to empty dict/list
- Missing required columns: Logs warning, uses fallback defaults
- User cancels dialog: Returns silently

**Success feedback:** `QMessageBox.information` with cycle count + file path.

### `_populate_edits_timeline_from_loaded_data(raw_data: list)`

Plots raw SPR data on the timeline navigator graph (small overview at top of Edits tab).

**Input:** `[{'time': float, 'channel': str, 'value': float}, ...]` (long format)

**Output:** 4 lines on `edits_timeline_graph`, one per channel (a, b, c, d).

Skipped if `edits_timeline_graph` not found (guards against incomplete UI state).

---

## 5. Graph Interaction — Flag Placement

### `_on_edits_graph_clicked(event)`

Handles right-click on edits primary graph. Opens context menu:

```
[ Add Injection Flag ]
[ Add Wash Flag     ]
[ Add Spike Flag    ]
```

**Flow:**
1. Extract click coordinates: `(time_val, spr_val)` from `event.scenePos()`
2. Determine channel via `event.currentItem` lookup in `edits_graph_curves`
3. Show `QMenu` with 3 actions
4. On action trigger: `_add_edits_flag(channel, time_val, spr_val, flag_type)`

### `_add_edits_flag(channel, time_val, spr_val, flag_type)`

Delegates to `FlagManager.add_flag()`.

```python
if hasattr(self.app, 'flag_mgr') and self.app.flag_mgr:
    self.app.flag_mgr.add_flag(
        flag_type=flag_type,
        time=time_val,
        channel=channel,
        spr_value=spr_val,
        source='manual'
    )
```

**No flag visual created here** — `FlagManager` emits signal → UI coordinator redraws all flag markers.

---

## 6. Cycle Selection & Rendering

### `_on_cycle_selected_in_table()` — Core Render Engine (402 lines)

**Trigger:** User clicks row(s) in `cycle_data_table` (EditsTab).

**Behavior modes:**

| Selection | Action |
|-----------|--------|
| **No rows** | Clear graph, hide time labels |
| **Single row** | Render cycle with shift + ref subtraction; show start/end time labels in graph header |
| **Multi-row** | Overlay all selected cycles on graph (no shifts applied); hide time labels |

#### Single-Selection Header Population

**Time labels** (inline in Active Selection graph header):
```python
self.edits_tab.alignment_start_time.setText(f"▶ {start:.0f} s")
self.edits_tab.alignment_end_time.setText(f"◼ {end:.0f} s")
self.edits_tab.alignment_start_time.setVisible(True)
self.edits_tab.alignment_end_time.setVisible(True)
```

**Alignment panel** (now invisible stubs — no visible panel):
- `alignment_ref_combo` stub → still synced from `_cycle_alignment[row_idx]['ref']`
- `alignment_shift_input` stub → still synced from `_cycle_alignment[row_idx]['shift']`
- `alignment_channel_combo` (via `_AlignChannelProxy`) → synced from `_cycle_alignment[row_idx]['channel']`

**Cycle boundaries:**
```python
start_time = cycle.get('start_time_sensorgram', 0)
end_time = cycle.get('end_time_sensorgram') or (start_time + duration_minutes * 60)
```

#### Data Source Resolution Strategy

**Priority 1 — `recording_mgr.data_collector.raw_data_rows`**
- Populated from Excel load or when recording
- List of dicts: `[{'elapsed': float or 'time': float, 'channel': str, 'value': float}, ...]`
- Time-ordered (optimized for early exit when `time > end_time`)

**Priority 2 — `buffer_mgr.timeline_data`**
- Always populated during live acquisition
- Dict of numpy buffers: `{'a': {time: ndarray, wavelength: ndarray}, 'b': ..., 'c': ..., 'd': ...}`
- Used when raw_data_rows is empty (live-view mode without recording)

**Fallback:** If neither available, show `QMessageBox.warning` and abort.

#### Time Coordinate Conversion (buffer_mgr path only)

Cycle `start_time_sensorgram`/`end_time_sensorgram` are in **RECORDING** timebase (from `Cycle.to_export_dict()`).

Buffer stores data in **RAW_ELAPSED** timebase.

```python
if use_live_buffer:
    _clock = getattr(self.app, 'clock', None)
    if _clock:
        _buf_start = _clock.convert(start_time, TimeBase.RECORDING, TimeBase.RAW_ELAPSED)
        _buf_end = _clock.convert(end_time, TimeBase.RECORDING, TimeBase.RAW_ELAPSED)
```

If `clock` not available, uses cycle times as-is (degrades gracefully).

#### Data Collection Per Cycle

For each selected cycle:

```python
for row in selected_rows:
    cycle = self._loaded_cycles_data[row]
    start_time = cycle.get('start_time_sensorgram', ...)
    end_time = cycle.get('end_time_sensorgram', ...)

    # Get alignment settings for THIS cycle
    cycle_channel = _cycle_alignment[row]['channel']  # 'A', 'B', 'C', 'D', or 'All'
    cycle_shift = _cycle_alignment[row]['shift']      # float, in seconds

    # Collect data for time window [start_time, end_time]
    # If cycle_channel != 'All', only apply shift to that channel
    for each data point in window:
        if target_channel is None or ch == target_channel:
            relative_time = time_val - start_time + cycle_shift
        else:
            relative_time = time_val - start_time
        all_cycle_data[ch]['time'].append(relative_time)
        all_cycle_data[ch]['wavelength'].append(value)
```

All data is collected into `all_cycle_data` dict:
```python
{
    'a': {'time': [list of floats], 'wavelength': [list of floats]},
    'b': {...},
    'c': {...},
    'd': {...},
}
```

#### Reference Subtraction (Single-Selection Only)

```python
if len(selected_rows) == 1:
    ref_channel_idx = self.edits_tab._get_effective_ref_channel(selected_rows[0])
```

Priority order (from `_get_effective_ref_channel` in `_alignment_mixin.py`):
1. **Per-cycle ref** from `_cycle_alignment[row]['ref']` ('Ch A', 'Ch B', 'Ch C', 'Ch D')
2. **Global ref** from `edits_ref_combo` (if per-cycle is 'Global')
3. **None** (skip subtraction)

**Subtraction flow:**
```python
# Get reference channel data
ref_channel_name = ['a', 'b', 'c', 'd'][ref_channel_idx]
ref_time = np.array(all_cycle_data[ref_channel_name]['time'])
ref_wavelength = np.array(all_cycle_data[ref_channel_name]['wavelength'])

# Sort reference by time
ref_time, ref_wavelength = sort_by(ref_time)

# For each channel (except reference itself):
for ch in ['a', 'b', 'c', 'd']:
    if ch == ref_channel_name:
        continue  # Don't subtract from self

    ch_time = np.array(all_cycle_data[ch]['time'])
    ch_wavelength = np.array(all_cycle_data[ch]['wavelength'])

    # Interpolate reference to match channel time points
    ref_interp = np.interp(ch_time, ref_time, ref_wavelength, left=np.nan, right=np.nan)

    # Subtract (only valid interpolations)
    ch_wavelength[valid_mask] -= ref_interp[valid_mask]
```

Reference channel data is **not** plotted after subtraction (since it would appear as a flat line at 0).

#### RU Conversion & Baseline Correction

```python
WAVELENGTH_TO_RU = 355.0  # 1 nm shift = 355 RU

for ch in ['a', 'b', 'c', 'd']:
    time_data = np.array(all_cycle_data[ch]['time'])
    wavelength_data = np.array(all_cycle_data[ch]['wavelength'])

    # Sort by time (critical for line rendering)
    sort_indices = np.argsort(time_data)
    time_data = time_data[sort_indices]
    wavelength_data = wavelength_data[sort_indices]

    # Baseline correction: subtract first point
    baseline = wavelength_data[0]
    delta_wavelength = wavelength_data - baseline

    # Convert to RU
    spr_data = delta_wavelength * WAVELENGTH_TO_RU

    # Plot on graph
    self.edits_graph_curves[ch_idx].setData(time_data, spr_data)
```

**Y-axis label updated:** `'Response (RU)'`

**Auto-scale:** `self.edits_primary_graph.autoRange()` after all channels plotted.

#### ΔSPR Barchart Update

```python
if hasattr(self, 'edits_tab'):
    self.edits_tab._update_delta_spr_barchart()
```

Calls `_alignment_mixin._update_delta_spr_barchart()` to refresh the bar chart showing start/stop cursor ΔSPR values.

#### Debug Logging

Extensive logging at `INFO` level:
- `[GRAPH]` prefix for all render operations
- `[REF SUBTRACT]` for reference subtraction steps
- Per-channel point counts, time ranges, baseline values, RU ranges

### `_on_cycle_channel_changed(channel_text)` (34 lines)

**Trigger:** User changes `alignment_channel_combo` in alignment panel.

**Storage:**
```python
selected_rows = get_selected_rows()
if len(selected_rows) == 1:
    row = selected_rows[0]
    if row not in self._cycle_alignment:
        self._cycle_alignment[row] = {'channel': 'All', 'shift': 0.0, 'ref': 'Global'}
    self._cycle_alignment[row]['channel'] = channel_text
```

**Re-render:** Calls `_on_cycle_selected_in_table()` to apply new channel filter + shift.

### `_on_cycle_shift_changed(shift_value)` (34 lines)

**Trigger:** User changes `alignment_shift_input` or `alignment_shift_slider`.

Same flow as `_on_cycle_channel_changed` but updates `'shift'` field.

**Note:** Slider and input are **synced bidirectionally** by `_alignment_mixin` methods (`_on_shift_input_changed`, `_on_shift_slider_changed`). This method only handles **storage + re-render**, not the widget sync.

### `_update_channel_source_combos(selected_rows: list)` (34 lines)

Populates the 4 **channel source combos** (used for segment creation) with selected cycle options.

**Items added:**
```
[ Auto (use first selection)    ]  ← data: None
[ Cycle 1 (type, conc)           ]  ← data: 0
[ Cycle 2 (type, conc)           ]  ← data: 1
...
```

Called automatically by `_on_cycle_selected_in_table()` after selection changes.

---

## 7. Segment Management

### Segment Data Structure — `EditableSegment`

Created via `SegmentManager.create_segment()` (not defined in this mixin):

```python
segment = {
    'name': str,
    'source_cycles': [list of cycle dicts],
    'time_range': (float, float),  # (min_start, max_end)
    'channel_sources': {0: row_idx, 1: row_idx, 2: row_idx, 3: row_idx},
    # Methods: export_to_tracedrawer_csv(), export_to_json()
}
```

### `_create_segment_from_selection()` (113 lines)

**Flow:**
1. Validate selection (1+ rows)
2. Extract cycle dicts from `_loaded_cycles_data` for selected rows
3. Read `channel_source_combos[0..3].currentData()` → `channel_sources` dict
   - `currentIndex == 0` ('Auto') → use `selected_rows[0]`
   - Else: use `combo.currentData()` (cycle row index)
4. Prompt for segment name via `QInputDialog.getText`
5. Calculate time range: `(min(start_times), max(end_times))` across all cycles
6. Call `self.app.segment_mgr.create_segment(name, source_cycles, time_range, channel_sources)`
7. Refresh segment list: `_refresh_segment_list()`
8. Show `QMessageBox.information` with confirmation

**Error handling:**
- No selection → warning
- No loaded data → warning
- Creation exception → `QMessageBox.critical` with traceback

### `_refresh_segment_list()`

Syncs `segment_list_combo` with `SegmentManager.segments` keys:

```python
combo.clear()
for segment_name in self.app.segment_mgr.segments.keys():
    combo.addItem(segment_name)
if no segments:
    combo.addItem("(no segments yet)")
```

### `_delete_selected_segment()`

Deletes segment via `segment_mgr.remove_segment(name)`, then refreshes list.

**Guard:** Shows warning if `"(no segments yet)"` selected.

### `_export_segment_to_tracedrawer(segment_name: str)` (58 lines)

**TraceDrawer CSV format:**
```
Time (s), Ch A (RU), Ch B (RU), Ch C (RU), Ch D (RU)
0.0, 12.5, 14.0, 8.2, 10.1
0.1, 12.6, 14.1, ...
```

**Flow:**
1. Get segment via `segment_mgr.get_segment(name)` → aborts with warning if not found
2. `QFileDialog.getSaveFileName` for output path (default: `{segment_name}.csv`)
3. Call `segment.export_to_tracedrawer_csv(file_path)` (implemented on `EditableSegment`)
4. Show `QMessageBox.information` on success

### `_export_segment_to_json(segment_name: str)` (58 lines)

Exports segment metadata to JSON for re-import.

**Flow:** Same as TraceDrawer export but calls `segment_mgr.export_segment(name, file_path)`.

### `_export_selected_segment_csv()` / `_export_selected_segment_json()`

Convenience wrappers:
```python
segment_name = self.segment_list_combo.currentText()
if segment_name != "(no segments yet)":
    self._export_segment_to_tracedrawer(segment_name)
```

**Shortcuts:** Assigned to toolbar buttons / menu actions in main window.

---

## 8. Reference Traces

The edits tab has **3 reference graph slots** below the primary graph. Each can hold one cycle for visual comparison.

### `_clear_reference_graphs()`

```python
for ref_idx in range(3):
    for ch_idx in range(4):
        self.edits_reference_curves[ref_idx][ch_idx].setData([], [])
    self.edits_reference_labels[ref_idx].setText(f"Reference {ref_idx + 1}")
    self.edits_reference_cycle_data[ref_idx] = None
```

### `_load_cycle_to_reference(cycle_row: int, ref_index: int)` (102 lines)

**Flow:**
1. Validate `cycle_row` < `len(_loaded_cycles_data)` and `0 <= ref_index < 3`
2. Extract time range (`start_time_sensorgram`, `end_time_sensorgram`) from cycle dict
3. Filter `_loaded_raw_data` for time window `[start_time, end_time]`
4. Collect data into `cycle_data` dict (same structure as `_on_cycle_selected_in_table`)
5. Plot on `edits_reference_curves[ref_index][ch_idx].setData(time, wavelength)`
6. Update label: `"{cycle_type} {cycle_row + 1}"`
7. Store in `edits_reference_cycle_data[ref_index] = cycle_row`

**No RU conversion** — reference graphs show raw wavelength (nm) for direct comparison with recording.

**Trigger:** Context menu on cycle table row → "Load to Reference 1/2/3" action.

---

## 9. Utility

### `_find_nearest_index(time_list: list, target_time: float) → int | None`

Linear search for nearest time value. Returns index or `None` if list empty.

Used internally by TraceDrawer export logic (not in this mixin).

---

## 10. Demo Data (Ctrl+Shift+D)

### `_load_demo_data()`

**Purpose:** Generate realistic SPR kinetics data for promotional screenshots / demos.

**Flow:**
1. Import `generate_demo_cycle_data` from `affilabs.utils.demo_data_generator`
2. Generate 3 cycles with association/dissociation phases:
   - Cycle 1: Low response (50 RU)
   - Cycle 2: Medium response (150 RU)
   - Cycle 3: High response (300 RU)
3. Populate `_loaded_cycles_data` and `_loaded_raw_data`
4. Populate EditsTab table + timeline
5. Select first cycle

**Keyboard shortcut:** Ctrl+Shift+D (registered in main window).

**Visibility:** Not exposed in UI — developer/demo feature only.

---

## 11. Data Flow Diagrams

### Excel Load Flow

```
User: File > Open (Ctrl+O)
  ↓
_load_data_from_excel()
  ↓
QFileDialog.getOpenFileName()
  ↓
_load_data_from_excel_internal(file_path)
  ↓
pandas.read_excel(sheet_name=None)
  ├→ Parse "Raw Data" or "Channel Data" or legacy sheets → raw_data_rows
  ├→ Parse "Cycles" → cycles_data (normalize flags, delta_spr, concentrations via ast.literal_eval)
  └→ Parse "Metadata" → loaded_metadata
  ↓
Store in RecordingManager.data_collector:
  - raw_data_rows → data_collector.raw_data_rows
  - cycles_data → data_collector.cycles
  - metadata → data_collector.metadata
  ↓
Store in main window:
  - cycles_data → self._loaded_cycles_data
  - metadata → self._loaded_metadata
  ↓
Populate EditsTab:
  - edits_tab._loaded_metadata = metadata
  - edits_tab._populate_cycles_table(cycles_data)
  - edits_tab._update_selection_view()
  - Set timeline cursors to data bounds
  ↓
QMessageBox.information("Successfully loaded N cycles")
```

### Cycle Selection & Render Flow

```
User: Click row(s) in cycle_data_table
  ↓
EditsTab emits selectionChanged signal
  ↓
_on_cycle_selected_in_table()
  ├→ No selection: Clear graph + hide alignment panel → DONE
  ├→ Single selection:
  │   ├→ Show alignment panel
  │   ├→ Populate flags display (color-coded)
  │   ├→ Populate alignment controls from _cycle_alignment[row]
  │   └→ Populate cycle boundaries
  └→ Multi-selection: Hide alignment panel
  ↓
Update channel_source_combos(selected_rows)
  ↓
Resolve data source:
  ├→ Priority 1: recording_mgr.data_collector.raw_data_rows
  └→ Priority 2: buffer_mgr.timeline_data (numpy arrays)
  ↓
For each selected cycle:
  ├→ Get time range (start_time_sensorgram, end_time_sensorgram)
  ├→ Get alignment settings (channel, shift) from _cycle_alignment[row]
  ├→ Collect data in window [start_time, end_time]
  │   └→ Apply shift to target_channel only (if channel != 'All')
  └→ Store in all_cycle_data[ch]['time'], all_cycle_data[ch]['wavelength']
  ↓
If single selection + reference configured:
  ├→ Get ref_channel_idx from _get_effective_ref_channel(row)
  ├→ Extract ref_time, ref_wavelength
  ├→ Sort reference by time
  └→ For each non-reference channel:
      ├→ Interpolate reference to channel time points
      └→ Subtract: ch_wavelength -= ref_interp
  ↓
For each channel (a, b, c, d):
  ├→ Sort by time
  ├→ Baseline correction: wavelength -= wavelength[0]
  ├→ Convert to RU: spr_data = delta_wavelength * 355.0
  └→ Plot: edits_graph_curves[ch_idx].setData(time_data, spr_data)
  ↓
Auto-scale graph + set Y-axis label to "Response (RU)"
  ↓
Update ΔSPR barchart: edits_tab._update_delta_spr_barchart()
```

### Segment Creation Flow

```
User: Select cycles → Click "Create Segment" button
  ↓
_create_segment_from_selection()
  ├→ Validate selection (1+ rows)
  ├→ Extract cycle dicts from _loaded_cycles_data
  ├→ Read channel_source_combos[0..3] → channel_sources dict
  ├→ QInputDialog.getText("Enter segment name")
  ├→ Calculate time_range: (min(starts), max(ends))
  └→ segment_mgr.create_segment(name, source_cycles, time_range, channel_sources)
  ↓
_refresh_segment_list()
  ↓
QMessageBox.information("Created segment 'X' from N cycles")
```

### TraceDrawer Export Flow

```
User: Select segment → Click "Export to TraceDrawer" button
  ↓
_export_selected_segment_csv()
  ↓
_export_segment_to_tracedrawer(segment_name)
  ├→ segment_mgr.get_segment(name) → aborts if None
  ├→ QFileDialog.getSaveFileName(default: {name}.csv)
  └→ segment.export_to_tracedrawer_csv(file_path)
      ├→ Collect raw data for each channel from source cycles
      ├→ Baseline correct + convert to RU
      ├→ Write CSV: "Time (s), Ch A (RU), Ch B (RU), Ch C (RU), Ch D (RU)"
      └→ One row per time point
  ↓
QMessageBox.information("Exported segment 'X' to: <path>")
```

---

## 12. Key Algorithms

### RU Conversion Formula

```python
WAVELENGTH_TO_RU = 355.0  # Conversion factor for spectral SPR

# Step 1: Baseline correction
baseline = wavelength_data[0]  # First point in window
delta_wavelength = wavelength_data - baseline

# Step 2: Convert to RU
spr_data = delta_wavelength * WAVELENGTH_TO_RU
```

**Why 355?** Empirically calibrated for gold-coated sensors in Kretschmann configuration at ~630 nm resonance. This factor converts wavelength shift (nm) to standard "Response Units" (RU) comparable to angular SPR systems.

**Sign convention:** Positive wavelength shift (red shift) = positive RU response = binding event. SPR on gold produces a RED SHIFT when analyte binds — ΔSPR values are positive on binding.

### Reference Subtraction Interpolation

```python
# Reference and channel may have different time points
ref_time = np.array([0, 1, 2, 3, 4, 5])  # Example
ref_wavelength = np.array([620.5, 620.6, 620.7, 620.8, 620.9, 621.0])

ch_time = np.array([0.5, 1.5, 2.5, 3.5, 4.5])  # Offset sampling

# Interpolate reference to match channel time points
ref_interp = np.interp(ch_time, ref_time, ref_wavelength, left=np.nan, right=np.nan)
# Result: [620.55, 620.65, 620.75, 620.85, 620.95]

# Subtract
ch_wavelength -= ref_interp
```

**Boundary handling:** `left=np.nan, right=np.nan` prevents extrapolation outside reference data range. Subtraction only applied where both traces overlap.

### Time Shift Application

```python
cycle_shift = _cycle_alignment[row]['shift']  # e.g., 12.5 seconds
cycle_channel = _cycle_alignment[row]['channel']  # e.g., 'Ch A'

target_channel = {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd'}[cycle_channel[3]]

for data_point in raw_data:
    ch = data_point['channel']
    time_val = data_point['time']

    if cycle_channel == 'All' or ch == target_channel:
        # Apply shift to this channel
        relative_time = time_val - start_time + cycle_shift
    else:
        # No shift for other channels
        relative_time = time_val - start_time

    all_cycle_data[ch]['time'].append(relative_time)
```

**Effect:** Shifts the entire trace left (negative shift) or right (positive shift). Used to align injection points across cycles or compensate for controller timing drift.

---

## 13. Known Issues & TODOs

### Issue #1: Multi-Selection Shifts Not Applied

**Current:** When multiple cycles selected, shifts are **not** applied. All cycles rendered with `relative_time = time_val - start_time` (no `+ cycle_shift`).

**Expected:** Each cycle should respect its per-cycle shift from `_cycle_alignment[row]['shift']`.

**Workaround:** Select cycles one at a time to see shifted view.

**Fix:** Move shift application inside the cycle loop before time window filtering.

### Issue #2: Reference Subtraction Only for Single Selection

**Current:** Reference subtraction skipped entirely when multiple cycles selected.

**Expected:** Each cycle could have independent reference subtraction (using per-cycle ref from `_cycle_alignment[row]['ref']`).

**Complexity:** Requires per-cycle ref interpolation + separate baseline correction per cycle before overlay.

### ~~Issue #3: Baseline Cursor Logic Not Implemented~~ **RESOLVED**

Delta SPR cursors (`delta_spr_start_cursor` / `delta_spr_stop_cursor`) are implemented as draggable `pg.InfiniteLine` objects on `edits_primary_graph`. Dragging updates the bar chart and InteractiveSPRLegend in real time. Lock button pins cursor distance to `contact_time × 1.1` for consistent cross-cycle measurement.

### Issue #4: CWD-Relative Paths in Segment Export

`_export_segment_to_tracedrawer` and `_export_segment_to_json` use `QFileDialog.getSaveFileName` with default filename only (no directory).

**Expected:** Should default to `_get_user_export_dir("Segments")` or experiment folder.

**Current:** Defaults to CWD (often the app root, not user's Documents folder).

### Issue #5: `_loaded_raw_data` Not Always Populated

`_load_cycle_to_reference` reads from `self._loaded_raw_data`, but this is only set during Excel load (`_load_data_from_excel_internal`).

**Missing:** When recording live without loading Excel, `_loaded_raw_data` is empty → reference loading fails silently.

**Expected:** Should fall back to `recording_mgr.data_collector.raw_data_rows` or `buffer_mgr.timeline_data`.

---

## 14. Interaction with Other Components

### → EditsTab

**Methods called on EditsTab:**
- `_populate_cycles_table(cycles_data)` — populates table rows from cycle dicts
- `_update_selection_view()` — redraws primary graph with current cursors
- `_toggle_channel(ch_idx, visible)` — shows/hides channel trace
- `_export_selection()` — exports selected time range to Excel
- `_update_delta_spr_barchart()` — refreshes ΔSPR bar chart
- `_get_effective_ref_channel(row_idx)` — resolves reference channel priority

**Data passed to EditsTab:**
- `_loaded_metadata` (dict)
- `cycles_data` (list of dicts)

**Data read from EditsTab:**
- `alignment_start_time`, `alignment_end_time` (graph header labels — shown/hidden)
- `alignment_ref_combo` (stub), `alignment_shift_input` (stub), `alignment_shift_slider` (stub) — synced but invisible
- `_AlignChannelProxy` (channel selector proxy) — `.setCurrentText()` / `.blockSignals()` called
- `cycle_data_table.selectedItems()` → selected row indices

### → RecordingManager

**Data stored:**
- `data_collector.raw_data_rows` ← raw SPR data (long format)
- `data_collector.cycles` ← cycle metadata
- `data_collector.metadata` ← metadata key-value pairs

### → SegmentManager

**Methods called:**
- `create_segment(name, source_cycles, time_range, channel_sources)` → returns `EditableSegment`
- `get_segment(name)` → retrieves existing segment
- `remove_segment(name)` → deletes segment
- `export_segment(name, file_path)` → exports to JSON
- `segments` (dict property) → lists all segment names

### → FlagManager

**Methods called:**
- `add_flag(flag_type, time, channel, spr_value, source='manual')` → creates flag

**No flag visuals created in this mixin** — `FlagManager` emits signal → `UIUpdateCoordinator` redraws markers.

### → BufferManager

**Data read:**
- `timeline_data` (dict of numpy buffers) → used when `raw_data_rows` empty (live view)

### → ExperimentClock

**Method called:**
- `convert(time, from_timebase, to_timebase)` → converts cycle times (RECORDING) to buffer times (RAW_ELAPSED)

**No clock:** Falls back gracefully (uses cycle times as-is).

---

## 15. Method Inventory

| Method | Lines | Purpose |
|--------|-------|---------|
| **Delegators** | | |
| `_update_edits_selection_view` | 3 | Forward to `edits_tab._update_selection_view()` |
| `_toggle_edits_channel` | 3 | Forward to `edits_tab._toggle_channel()` |
| `_export_edits_selection` | 3 | Forward to `edits_tab._export_selection()` |
| **Excel Loading** | | |
| `_load_data_from_excel` | 18 | File dialog → `_load_data_from_excel_internal` |
| `_load_data_from_excel_internal` | 269 | Parse Excel (Raw Data, Cycles, Metadata sheets) → populate RecordingManager + EditsTab |
| `_populate_edits_timeline_from_loaded_data` | 68 | Plot raw data on timeline navigator graph |
| **Graph Interaction** | | |
| `_on_edits_graph_clicked` | 66 | Right-click → context menu → `_add_edits_flag` |
| `_add_edits_flag` | 10 | Delegate to `FlagManager.add_flag()` |
| **Cycle Selection** | | |
| `_on_cycle_selected_in_table` | 402 | **Core render engine**: load cycles → apply shifts → ref subtraction → RU conversion → plot |
| `_on_cycle_channel_changed` | 34 | Store channel filter in `_cycle_alignment` → re-render |
| `_on_cycle_shift_changed` | 34 | Store time shift in `_cycle_alignment` → re-render |
| `_update_channel_source_combos` | 34 | Populate segment channel source dropdowns |
| **Segments** | | |
| `_create_segment_from_selection` | 113 | Create `EditableSegment` from selected cycles + channel sources |
| `_refresh_segment_list` | 28 | Sync `segment_list_combo` with `SegmentManager` |
| `_delete_selected_segment` | 53 | Delete segment via `SegmentManager` |
| `_export_segment_to_tracedrawer` | 58 | Export segment to TraceDrawer CSV (RU, time-aligned) |
| `_export_segment_to_json` | 58 | Export segment metadata to JSON |
| `_export_selected_segment_csv` | 23 | Wrapper for `_export_segment_to_tracedrawer` |
| `_export_selected_segment_json` | 27 | Wrapper for `_export_segment_to_json` |
| **Reference Traces** | | |
| `_clear_reference_graphs` | 32 | Clear all 3 reference graph slots |
| `_load_cycle_to_reference` | 102 | Load cycle data to reference graph slot (no RU conversion) |
| **Utility** | | |
| `_find_nearest_index` | 20 | Find nearest time value in list (linear search) |
| **Demo Data** | | |
| `_load_demo_data` | 126 | Generate synthetic SPR kinetics for screenshots (Ctrl+Shift+D) |

**Total:** 1664 lines across 21 methods.

---

## 16. Testing Scenarios

### Scenario 1: Load Excel File with 4 Cycles
1. File > Open (Ctrl+O)
2. Select `.xlsx` file exported from previous session
3. Verify: Cycles table populated with 4 rows
4. Verify: Timeline graph shows all raw data
5. Verify: Metadata preserved (check Settings tab or Excel export metadata)

### Scenario 2: Single Cycle Selection with Shift
1. Load Excel file
2. Click cycle row 1
3. Verify: Alignment panel visible, title "Cycle 1 Details & Editing"
4. Set shift input to `10.0` seconds
5. Verify: Graph shifts 10s to the right
6. Select cycle row 2
7. Verify: New cycle rendered, shift resets to stored value (0.0 if not previously set)

### Scenario 3: Multi-Cycle Overlay
1. Load Excel file with 3+ cycles
2. Ctrl+Click rows 1, 2, 3
3. Verify: Alignment panel hidden
4. Verify: All 3 cycles overlaid on graph (time-aligned to their start times)
5. Verify: Channel source combos populated with "Cycle 1", "Cycle 2", "Cycle 3" options

### Scenario 4: Reference Subtraction
1. Load Excel file, select cycle 1
2. In alignment panel, set reference combo to "Ch A"
3. Verify: Ch B, C, D traces change (subtracted from Ch A)
4. Verify: Ch A trace changes (self-subtraction → flat line or no longer visible)
5. Change reference to "None"
6. Verify: All channels revert to original wavelength (no subtraction)

### Scenario 5: Segment Creation & TraceDrawer Export
1. Load Excel file, select cycles 1+2 (Ctrl+Click)
2. Adjust channel source combos: Ch A from Cycle 1, Ch B from Cycle 2, etc.
3. Click "Create Segment" button
4. Enter name "Test Segment" → OK
5. Verify: Segment appears in `segment_list_combo`
6. Select segment, click "Export to TraceDrawer"
7. Save as `test_segment.csv`
8. Verify: CSV has 5 columns: Time (s), Ch A (RU), Ch B (RU), Ch C (RU), Ch D (RU)
9. Open in TraceDrawer → verify traces load correctly

### Scenario 6: Reference Graph Loading
1. Load Excel file, right-click cycle row 1
2. Context menu: "Load to Reference 1"
3. Verify: Reference graph slot 1 shows cycle trace
4. Right-click cycle row 2, "Load to Reference 2"
5. Verify: Both reference slots active
6. Select cycle row 3
7. Verify: Primary graph shows cycle 3, reference slots unchanged

### Scenario 7: Demo Data (Ctrl+Shift+D)
1. Press Ctrl+Shift+D
2. Verify: Cycles table populated with 3 cycles (association/dissociation phases)
3. Verify: Timeline graph shows realistic kinetics
4. Select cycle 1
5. Verify: Graph shows binding curve ~50 RU max response

---

## 17. Performance Notes

### Data Loading — Excel Parse Time

**Typical:** 500 cycles + 50k raw data points → **~1.5 seconds** (pandas.read_excel + ast.literal_eval parsing).

**Bottleneck:** `ast.literal_eval` for stringified dicts/lists in Cycles sheet. Consider caching parsed values or switching to JSON columns.

### Render Time — Multiple Cycle Overlay

**Typical:** 3 cycles × 4 channels × 5000 points each = 60k points → **~300ms** to render (numpy sort + baseline correction + pyqtgraph plot).

**Optimization:** Already using numpy for bulk operations; further gains require downsampling or LoD rendering in pyqtgraph.

### Reference Subtraction — Interpolation Cost

**Typical:** 1 reference channel (5000 points) subtracted from 3 channels (5000 points each) → **~50ms** (numpy.interp × 3).

**No issue:** Fast enough for interactive use.

---

## 18. Future Enhancements

### 1. Live Edit ΔSPR via Cursors
Add draggable baseline cursors in single-cycle view → auto-calculate ΔSPR between cursors → save to `_loaded_cycles_data` and table row.

**Benefit:** Allows post-hoc correction of injection timing / contact time errors.

### 2. Multi-Cycle Reference Subtraction
Support independent reference channels per cycle when multiple cycles selected + overlaid.

**Benefit:** Compare binding responses after subtracting cycle-specific baselines.

### 3. Segment Channel Preview
Show mini-graphs in segment creation dialog previewing which cycle contributes to each channel.

**Benefit:** Reduces user errors in channel source combo selection.

### 4. Undo/Redo for Shifts
Store shift edit history → allow Ctrl+Z / Ctrl+Shift+Z for alignment panel changes.

**Benefit:** Encourages experimentation without fear of losing good alignment.

### 5. Bulk Time Shift All Cycles
Add "Apply shift to all cycles" checkbox in alignment panel → propagate current shift value to all rows in `_cycle_alignment`.

**Benefit:** Corrects systematic timing errors across entire session.

---

**Document End**
