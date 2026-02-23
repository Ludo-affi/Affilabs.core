# EDITS_ALIGNMENT_DELTA_SPR_FRS — Alignment & ΔSPR Feature Specification

**Source:** `affilabs/tabs/edits/_alignment_mixin.py` (605 lines after cleanup)  
**UI wiring:** `affilabs/tabs/edits/_ui_builders.py`  
**State init:** `affilabs/tabs/edits_tab.py`  
**Version:** Affilabs.core v2.0.5 beta  
**Status:** Code-verified 2026-02-19

---

## 1. Overview

`AlignmentMixin` provides four independent capabilities for the Edits tab:

| Capability | Purpose |
|------------|---------|
| **Time-shift alignment** | Shift a cycle's sensorgram ±20s on a selected channel to align injection starts across cycles |
| **Reference subtraction** | Subtract one channel from all others to cancel non-specific response; supports global and per-cycle override |
| **ΔSPR measurement** | Drag two vertical cursors on the sensorgram; bar chart shows end-minus-start value per channel in real time |
| **Cursor lock** | Lock cursor distance to `contact_time × 1.1` for reproducible measurement across cycles |

Additionally provides:
- `_create_processing_cycle()` — multi-cycle channel extraction to `.xlsx`
- `update_barchart_colors()` — colorblind palette toggle for bar chart

---

## 2. State Variables

Initialised in `EditsTab.__init__`:

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| `_cycle_alignment` | `dict[int, dict]` | `{}` | Per-row alignment settings: `{'channel': str, 'shift': float, 'ref': str}` |
| `_delta_spr_cursor_locked` | `bool` | `False` | Whether cursors are pinned to `contact_time × 1.1` |
| `_delta_spr_lock_distance` | `float` | `0.0` | Absolute cursor distance in seconds when locked |
| `_suppressing_position_change` | `bool` | `False` | Reentrancy guard — prevents recursive `sigPositionChanged` cascades |
| `current_delta_values` | `list[float]` | (created on first update) | Latest ΔSPR per channel [A, B, C, D] |
| `edits_graph_curves` | `list[pg.PlotDataItem]` | `[]` | 4 pyqtgraph curves (one per channel) on `edits_primary_graph` |

---

## 3. Alignment Panel UI Widgets

Built by `_ui_builders._create_alignment_panel()`:

| Widget | Type | Values | Handler |
|--------|------|--------|---------|
| `alignment_ref_combo` | `QComboBox` | Global / None / Ch A / Ch B / Ch C / Ch D | `_on_cycle_ref_changed` (per-cycle), `_on_reference_changed` (global) |
| `alignment_channel_combo` | `QComboBox` | All / A / B / C / D | `_on_alignment_channel_changed` |
| `alignment_shift_input` | `QLineEdit("0.0")` | float (seconds) | `_on_shift_input_changed` → syncs slider |
| `alignment_shift_slider` | `QSlider(Horizontal)` | −200 to +200 integer | `_on_shift_slider_changed` → applies in real-time |

**Slider resolution:** integer value ÷ 10 = seconds → range −20.0s to +20.0s in 0.1s increments.

Both `alignment_shift_input` and `alignment_shift_slider` use `blockSignals(True/False)` when the other triggers an update to prevent circular firing.

---

## 4. Time-Shift Alignment

### Flow

```
User drags slider  →  _on_shift_slider_changed(value)
  → converts value ÷ 10 → shift_value (float)
  → updates alignment_shift_input.setText (signals blocked)
  → calls _apply_time_shift()

User types in input  →  _on_shift_input_changed(text)
  → parses float, clamps to ±20.0s
  → updates alignment_shift_slider.setValue (signals blocked)
  (does NOT auto-apply — requires slider drag or button press)
```

### `_apply_time_shift()`

1. Reads `row_idx` from `cycle_data_table.currentRow()`
2. Reads `shift_value` from `alignment_shift_input.text()`
3. Reads `channel_text` from `alignment_channel_combo`
4. Writes into `_loaded_cycles_data[row_idx]`:
   - `cycle['shifts'][ch_idx] = shift_value` (per-channel dict)
   - `cycle['shift'] = shift_value` (top-level, "All channels" default)
5. Updates `main_window._cycle_alignment[row_idx]` with `{'channel', 'shift', 'ref'}`
6. Calls `main_window._on_cycle_selected_in_table()` to redraw graph with shift applied

### Channel scope

| `alignment_channel_combo` value | Channels shifted |
|---------------------------------|-----------------|
| `"All"` | All 4 (indices 0–3 in `shifts` dict) |
| `"A"` / `"B"` / `"C"` / `"D"` | Single channel only |

The graph rendering code in `main.py._on_cycle_selected_in_table()` applies the shift from `_cycle_alignment[row_idx]` when plotting.

---

## 5. Reference Subtraction

### Priority Resolution — `_get_effective_ref_channel(row_idx)`

```
1. Check _cycle_alignment[row_idx].get('ref')
   ├─ If not 'Global' → use per-cycle override
   └─ If 'Global' → fall through

2. Check edits_ref_combo (global toolbar)
   └─ Apply to all cycles with no per-cycle override
```

Mapping: `{"None": None, "Ch A": 0, "Ch B": 1, "Ch C": 2, "Ch D": 3}`

Returns channel index (0–3) or `None` (no subtraction).

### Handlers

| Handler | Trigger | Effect |
|---------|---------|--------|
| `_on_reference_changed(text)` | `edits_ref_combo` global combo | Calls `_on_cycle_selected_in_table()` to redraw |
| `_on_cycle_ref_changed(text)` | `alignment_ref_combo` per-cycle combo | Saves into `_cycle_alignment[row_idx]['ref']`, redraws |

Reference subtraction arithmetic is performed in `main_window._on_cycle_selected_in_table()`, not in this mixin.

---

## 6. Delta SPR Measurement

### Cursor Widgets

Built in `_ui_builders._create_active_selection()` (the Delta SPR panel section):

| Widget | Type | Initial position | Signal |
|--------|------|-----------------|--------|
| `delta_spr_start_cursor` | `pg.InfiniteLine(movable=True)` | t = 0 | `sigPositionChanged → _update_delta_spr_barchart` |
| `delta_spr_stop_cursor` | `pg.InfiniteLine(movable=True)` | t = 60 | `sigPositionChanged → _update_delta_spr_barchart` |

Both cursors are added to `edits_primary_graph` directly.

### Bar Chart

- `delta_spr_barchart` — `pg.PlotWidget`, white background, context menu enabled
- `delta_spr_bars` — 4 `pg.BarGraphItem` objects, one per channel (A, B, C, D)
- `delta_spr_labels` — 4 `pg.TextItem` objects positioned above/below each bar
- Y-axis auto-scales with ≥25% padding each side (minimum 50 RU headroom for labels)
- Reset button calls `delta_spr_barchart.autoRange()`

### `_update_delta_spr_barchart()` — Calculation Logic

```
For each channel ch_idx in [0, 1, 2, 3]:
  times, values = edits_graph_curves[ch_idx].getData()
  start_value  = values[first index where times >= start_cursor]
  stop_value   = values[last index where times <= stop_cursor]
  delta_spr    = stop_value - start_value          # end − start, NOT abs
```

**Sign convention:** delta_spr is **positive** when analyte binds (red-shift — resonance wavelength increases on binding in spectral SPR). Do not negate or take abs().

Results stored in `self.current_delta_values` (list of 4 floats).

### Auto-save to cycle data

After computing deltas, `_update_delta_spr_barchart` writes back to the currently selected cycle:

```python
cycle[f'delta_ch{ch_idx + 1}'] = round(delta_val, 2)   # delta_ch1 … delta_ch4
```

Table column `TABLE_COL_DELTA_SPR` (col 4) is updated with a summary string:
`"A:-12 B:-14 C:-8 D:-10"`

### Label positioning

```
if delta_val >= 0:
    label_y = delta_val + max(abs(delta_val) * 0.08, 15)   # at least 15 RU above bar
else:
    label_y = delta_val - max(abs(delta_val) * 0.08, 15)   # at least 15 RU below bar
```

---

## 7. Cursor Lock (contact_time × 1.1)

### State machine

```
UNLOCKED (default)                    LOCKED
  delta_spr_lock_btn.isChecked() = False   delta_spr_lock_btn.isChecked() = True
  _delta_spr_cursor_locked = False          _delta_spr_cursor_locked = True
  _delta_spr_lock_distance = 0.0            _delta_spr_lock_distance = contact_time * 1.1
  Button label: "🔓 Unlock"                 Button label: "🔒 Locked"
```

### `_toggle_delta_spr_lock(checked: bool)`

**When enabling (checked = True):**
1. Get `row_idx = cycle_data_table.currentRow()` — bail if no selection
2. Resolve `contact_time`:
   a. From `main_window._current_cycle.contact_time` (live cycle, if available)
   b. From `_loaded_cycles_data[row_idx].get('contact_time')` (loaded data)
3. If `contact_time` is None or ≤ 0 → abort, uncheck button, show warning dialog
4. Set `_delta_spr_lock_distance = float(contact_time) * 1.1`
5. Set `_delta_spr_cursor_locked = True`
6. Update button label + tooltip

**When disabling (checked = False):**
1. Clear `_delta_spr_cursor_locked = False`
2. Restore button label to "🔓 Unlock"

### `_reset_delta_spr_lock()`

Called via `cycle_data_table.itemSelectionChanged`. Automatically unlocks cursors whenever the user selects a different cycle, so the new cycle's `contact_time` can take effect.

```python
delta_spr_lock_btn.blockSignals(True)
delta_spr_lock_btn.setChecked(False)
delta_spr_lock_btn.blockSignals(False)
_toggle_delta_spr_lock(False)
```

### `_enforce_delta_spr_lock()`

Called at the start of `_update_delta_spr_barchart()` (before computing deltas).

```python
if not _delta_spr_cursor_locked or _suppressing_position_change:
    return
current_distance = abs(stop_cursor.value() - start_cursor.value())
if abs(current_distance - _delta_spr_lock_distance) > 0.1:   # 0.1s tolerance
    _suppressing_position_change = True
    try:
        delta_spr_stop_cursor.setValue(start_cursor.value() + _delta_spr_lock_distance)
    finally:
        _suppressing_position_change = False
```

The `_suppressing_position_change` guard prevents `setValue()` from triggering another `sigPositionChanged → _enforce_delta_spr_lock()` recursion.

**Anchor:** start cursor is the anchor — stop cursor is adjusted.

---

## 8. Bar Chart Color Update

`update_barchart_colors(colorblind_enabled: bool)`

Called externally (from settings or theme toggle) when colorblind mode changes.

```python
bar_colors = CHANNEL_COLORS_COLORBLIND if colorblind_enabled else CHANNEL_COLORS
for bar, color in zip(delta_spr_bars, bar_colors):
    bar.setOpts(brush=pg.mkColor(color))
```

Both color palettes are defined in `affilabs/plot_helpers.py`.

---

## 9. Processing Cycle Creation

`_create_processing_cycle()` — multi-cycle extraction utility.

### Purpose
Extract per-cycle channel data from `_loaded_raw_data` and combine into a single synthetic cycle suitable for further processing or export.

### Input

- `cycle_data_table` selected rows (multi-selection allowed)
- Per-row alignment settings from `_cycle_alignment[row]` → channel filter + time shift

### Algorithm

```
For each selected row:
  channel_filter = _cycle_alignment[row]['channel']   # 'All' or 'A'/'B'/'C'/'D'
  time_shift = _cycle_alignment[row]['shift']

  channels_to_extract = CHANNELS_LOWER if 'All' else [channel.lower()]

  For each channel:
    For each point in _loaded_raw_data where channel matches:
      if start_time <= point.time <= end_time:
        adjusted_time = (point.time - start_time) + time_shift + current_time_offset
        append {'Time_s': adjusted_time, 'Channel': ch, 'Response_RU': value}

  current_time_offset += (end_time - start_time)   # concatenate durations
```

**Y unit:** data is already in RU (WAVELENGTH_TO_RU = 355.0 was applied upstream by `affilabs_core_ui.py`).

### Output Files

| Sheet | Columns | Content |
|-------|---------|---------|
| `Data` | `Time_s`, `Channel`, `Response_RU` | Long-format extracted point data |
| `Metadata` | `name`, `created`, `source_cycles`, `type`, `description` | Cycle metadata |
| `Source_Cycles` | `index`, `name`, `channel`, `time_shift`, `duration_s` | One row per source cycle |

**Output path:** `data_results/processing_cycles/{safe_name}.xlsx` (relative to CWD)

> ⚠️ **Known Issue:** Output path is hardcoded relative to CWD, not the user's experiment folder. Should use `self._get_user_export_dir()` or `self.main_window._experiment_folder`.

### Dialog flow

1. `QInputDialog.getText` — user enters cycle name (default auto-timestamped)
2. If file exists: `QMessageBox.question` — overwrite?
3. On success: `QMessageBox.information` with summary (source count, points, duration, path)
4. On failure: `QMessageBox.critical`

---

## 10. Signal Connection Summary

| Signal (source) | Handler | File |
|----------------|---------|------|
| `alignment_channel_combo.currentTextChanged` | `_on_alignment_channel_changed` | `_ui_builders.py` |
| `alignment_ref_combo.currentTextChanged` | `_on_cycle_ref_changed` | `_ui_builders.py` |
| `alignment_shift_input.textChanged` | `_on_shift_input_changed` | `_ui_builders.py` |
| `alignment_shift_slider.valueChanged` | `_on_shift_slider_changed` | `_ui_builders.py` |
| `delta_spr_start_cursor.sigPositionChanged` | `_update_delta_spr_barchart` | `_ui_builders.py` |
| `delta_spr_stop_cursor.sigPositionChanged` | `_update_delta_spr_barchart` | `_ui_builders.py` |
| `delta_spr_lock_btn.toggled` | `_toggle_delta_spr_lock` | `_ui_builders.py` |
| `cycle_data_table.itemSelectionChanged` | `_reset_delta_spr_lock` | `_ui_builders.py` |
| `edits_ref_combo.currentTextChanged` (global toolbar) | `_on_reference_changed` | wired in `_ui_builders.py` |

---

## 11. Data Persistence

### In `_loaded_cycles_data[row_idx]`

| Key | Written by | Content |
|-----|-----------|---------|
| `delta_ch1` … `delta_ch4` | `_update_delta_spr_barchart` | ΔSPR per channel (float, 2dp) |
| `shifts` | `_apply_time_shift` | `{ch_idx: float}` dict |
| `shift` | `_apply_time_shift` | Scalar shift (All channels path) |
| `cursor_lock_used` | `edits_tab.get_state_snapshot()` | Bool — was lock active at measurement |

### In `main_window._cycle_alignment[row_idx]`

```python
{
    'channel': str,    # 'All' | 'A' | 'B' | 'C' | 'D'
    'shift': float,    # seconds
    'ref': str,        # 'Global' | 'None' | 'Ch A' … 'Ch D'
}
```

State is preserved across cycle selections but reset on full data reload.

### In `edits_tab.get_state_snapshot()` (exported snapshot)

```python
{
    'Delta_SPR_A': current_delta_values[0],
    'Delta_SPR_B': current_delta_values[1],
    'Delta_SPR_C': current_delta_values[2],
    'Delta_SPR_D': current_delta_values[3],
    'Contact_Time': cycle.get('contact_time'),
    'Cursor_Start': delta_spr_start_cursor.value(),
    'Cursor_Stop':  delta_spr_stop_cursor.value(),
    'Locked_Distance': _delta_spr_lock_distance if _delta_spr_cursor_locked else None,
    'Lock_Active': _delta_spr_cursor_locked,
}
```

---

## 12. Method Inventory

| Method | Lines (approx) | Purpose |
|--------|----------------|---------|
| `update_barchart_colors` | 8 | Colorblind palette swap for bar chart |
| `_on_alignment_channel_changed` | 18 | Store channel filter, redraw graph |
| `_create_processing_cycle` | ~100 | Multi-cycle extraction → xlsx |
| `_toggle_delta_spr_lock` | ~55 | Enable/disable cursor lock |
| `_reset_delta_spr_lock` | 8 | Auto-unlock on cycle selection change |
| `_enforce_delta_spr_lock` | 18 | Enforce stop-cursor distance constraint |
| `_update_delta_spr_barchart` | ~55 | Compute ΔSPR, update bars, save to cycle |
| `_apply_time_shift` | ~40 | Write shift to `_cycle_alignment`, redraw |
| `_on_shift_input_changed` | 10 | Sync slider when input box changes |
| `_on_shift_slider_changed` | 8 | Sync input box + apply shift in real-time |
| `_on_reference_changed` | 4 | Global ref change → redraw |
| `_get_effective_ref_channel` | 12 | Per-cycle override > global toolbar |
| `_on_cycle_ref_changed` | 10 | Store per-cycle ref, redraw |

---

## 13. Known Issues

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| 1 | Medium | `_create_processing_cycle` saves to `data_results/processing_cycles/` (CWD-relative) — ignores user folder | 🔴 Open |

---

## 14. Bugs Fixed (This Audit)

| # | File | Change |
|---|------|--------|
| 1 | `_alignment_mixin.py` | Removed `_on_alignment_shift_changed()` — dead method, never connected (shift applied via `_on_shift_input_changed` / `_on_shift_slider_changed`) |
| 2 | `_alignment_mixin.py` | Removed `_on_cycle_start_changed()` — dead method; `cycle_start_spinbox` was removed from simplified UI panel; direct widget access would crash |
| 3 | `_alignment_mixin.py` | Removed `_on_cycle_end_changed()` — same reason as #2 |
