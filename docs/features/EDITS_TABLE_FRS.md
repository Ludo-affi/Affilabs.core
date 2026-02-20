# Edits Tab — Cycle Table & Layout FRS

> **Source files (code-verified)**
> - `affilabs/tabs/edits_tab.py` — class constants, `__init__`
> - `affilabs/tabs/edits/_table_mixin.py` — all table operations (1150 lines)
> - `affilabs/tabs/edits/_ui_builders.py` — all layout construction (1048 lines)
> - `affilabs/tabs/edits/_data_mixin.py` — data loading and Excel import
> - `affilabs/tabs/edits/_export_mixin.py` — export to Excel with charts
> - `affilabs/tabs/edits/_alignment_mixin.py` — per-cycle alignment and ΔSPR update

---

## 1. Class Composition

```python
class EditsTab(DataMixin, ExportMixin, UIBuildersMixin, AlignmentMixin, TableMixin):
    # affilabs/tabs/edits_tab.py
    CHANNELS       = ['A', 'B', 'C', 'D']
    CHANNELS_LOWER = ['a', 'b', 'c', 'd']
    TABLE_COL_EXPORT    = 0
    TABLE_COL_TYPE      = 1
    TABLE_COL_TIME      = 2
    TABLE_COL_CONC      = 3
    TABLE_COL_DELTA_SPR = 4
```

All table methods live in `TableMixin`; all widget construction lives in `UIBuildersMixin`.
Constants are class-level on `EditsTab`; accessible as `self.TABLE_COL_*` from all mixins.

---

## 2. Layout Overview

```
EditsTab (QFrame)
├── export_sidebar          ← Collapsible left panel (export stats + controls)
└── main_splitter (H)       ← 50:50
    ├── left_splitter (V)   ← 70:30
    │   ├── table_details_widget (TOP 70%)
    │   │   ├── cycle_data_table (QTableWidget, 5 cols)
    │   │   └── details_tab_widget (Flags | Notes, max 120px)
    │   └── bottom_left_widget (BOTTOM 30%)
    │       ├── metadata_panel
    │       └── alignment_panel (hidden until cycle selected)
    └── graphs_splitter (V) ← 70:30
        ├── active_selection_widget (TOP 70%)
        │   └── edits_primary_graph (pyqtgraph PlotWidget)
        └── delta_spr_barchart_widget (BOTTOM 30%)
            └── delta_spr_barchart (pyqtgraph PlotWidget, fixed 220px)
```

**Timeline graph** (`edits_timeline_graph`) lives in a separate widget created in `DataMixin`,
displayed above or to the side of the main splitter depending on tab layout.

---

## 3. Cycle Data Table

### Column Layout

| Index | Constant | Header | Width | Resize Mode | Content format |
|-------|----------|--------|-------|-------------|----------------|
| 0 | `TABLE_COL_EXPORT` | Export | 50 px | Fixed | Centered `QCheckBox` widget (not `QTableWidgetItem`) |
| 1 | `TABLE_COL_TYPE` | Type | 55 px | Fixed | `"{abbr} {cycle_num}"`, colored by `CycleTypeStyle` |
| 2 | `TABLE_COL_TIME` | Time | — | Stretch | `"{dur:.1f}m @ {start:.0f}s"` |
| 3 | `TABLE_COL_CONC` | Conc. | — | Stretch | `str(concentration_value)` |
| 4 | `TABLE_COL_DELTA_SPR` | ΔSPR | — | Stretch (last section) | `"A:val B:val C:val D:val"` in RU |

- Row height: 22 px (compact)  
- Row numbers (vertical header): hidden  
- Grid: solid lines, alternating row colors (`#FFFFFF` / `#FAFAFA`)  
- Selection: `ExtendedSelection`, row-based

### Type Abbreviations

`CycleTypeStyle.get(cycle_type)` returns `(abbr, color_hex)`. The type abbreviation string
and its foreground color are stored in `affilabs/widgets/ui_constants.py`.

### ΔSPR Data Resolution (two-path)

Applied in `_populate_cycles_table`, `_update_cycle_table_row`, and `add_cycle`:

1. **Priority 1** — `_parse_delta_spr(cycle)` → returns `delta_spr_by_channel` dict
   (`{'A': float, 'B': float, …}`). This is the live acquisition format.
2. **Priority 2** — `delta_ch1/delta_ch2/delta_ch3/delta_ch4` keys on the cycle dict.
   This is the Excel import fallback format.

If neither path yields values, the ΔSPR cell is left empty.

---

## 4. Cycle Entry Paths

### 4a. Live Acquisition — `add_cycle(cycle_dict)`

Called by `main.py` when a cycle completes during live recording.

```
add_cycle(cycle_dict)
  → insertRow at current rowCount
  → append cycle_dict to main_window._loaded_cycles_data
  → increment _cycle_type_counts[cycle_type]
  → setCellWidget(row, 0, _create_export_checkbox(row_idx))
  → setItem for cols 1–4
  → store flags/notes/cycle_id in _cycle_details_data[row_idx]
  → _update_empty_state()
  → _update_metadata_stats()
  → update filter_combo if new type seen
  → scrollToBottom()
```

### 4b. Excel Import — `_populate_cycles_table(cycles_data)`

Called by `DataMixin._load_data_from_excel_internal()` after parsing the file.

```
_populate_cycles_table(cycles_data)
  → setRowCount(0)  ← clear all rows
  → reset _cycle_export_selection, _cycle_type_counts
  → for each cycle: same column setup as add_cycle
  → _update_empty_state()
  → _update_metadata_stats()
```

---

## 5. Export Selection

Each row has a **widget-based** checkbox — not a `QTableWidgetItem`. This bypasses
`itemChanged` signals entirely.

| Component | Description |
|-----------|-------------|
| `_create_export_checkbox(cycle_idx, checked=True)` | Returns centered `QWidget` container with `QCheckBox` inside |
| `_on_export_checkbox_toggled(cycle_idx, state)` | `_cycle_export_selection[cycle_idx] = (state == Checked.value)` |
| `_cycle_export_selection: dict[int, bool]` | Single source of truth for which cycles are selected |

At export time, `_export_post_edit_analysis_with_charts()` reads `_cycle_export_selection`
to filter which cycles go into the workbook.

---

## 6. Row Operations

### Single Row Update

`_update_cycle_table_row(row_idx, cycle)` — refreshes cols 1–4 after an in-place edit.
Uses `_calculate_actual_duration(row_idx, cycle, all_cycles)` from `DataMixin` to correct
the displayed duration.

### Edit Timing Dialog

`_edit_cycle_timing(row_index)` — creates a modal `QDialog` with:
- `QDoubleSpinBox` for start time (seconds)
- `QDoubleSpinBox` for end time (seconds)
- Read-only duration label (auto-updated, turns red if end ≤ start)
- Saves back to `main_window._loaded_cycles_data[row_index]` and refreshes col 2

### Delete

`_delete_cycles_from_table(row_indices)`:
- Confirms with `QMessageBox.question`
- Removes rows in reverse index order from both table and `_loaded_cycles_data`
- Rebuilds `_cycle_alignment` to correct indices after deletion

### Programmatic Selection

`_select_cycle_by_index(cycle_idx)` — calls `selectRow(cycle_idx)`; the resulting
`itemSelectionChanged` signal drives cursor placement and graph update via
`main_window._on_cycle_selected_in_table`.

---

## 7. Context Menu (Right-click on Table)

Connected via `customContextMenuRequested`.

| Selection count | Available actions |
|-----------------|-------------------|
| 1 row | ✏️ Edit Cycle Timing → `_edit_cycle_timing` |
| 1 row | 📊 Load to Reference Graph → submenu (Reference 1/2/3) → `_load_cycle_to_reference` |
| 1 or N rows | 🗑️ Delete cycle(s) → `_delete_cycles_from_table` |

---

## 8. Timeline Marker Overlay

`add_cycle_markers_to_timeline(cycles_data)` decorates `edits_timeline_graph`:

- **`LinearRegionItem`** per cycle — colored background spanning `[start, end]`
  - Colors by type: baseline=gray, association=blue, dissociation=yellow,
    regeneration=red, wash=green, concentration/conc.=cyan, default=light gray
  - Alpha = 120 for visibility
  - `mouseClickEvent` → `_select_cycle_by_index(idx)` (table row follows)
- **`InfiniteLine`** (dotted, gray) at each cycle's start boundary
- **`TextItem`** label: `"Cycle N\n(type)"`, white fill, gray border

All markers are stored in `edits_cycle_markers` and `edits_cycle_labels` and cleared on
each call before rebuilding.

---

## 9. Filtering

### Type Filter

```python
filter_combo.currentTextChanged → _apply_cycle_filter(filter_text)
```

- Populated by `_update_cycle_type_filter(cycles_data)` — sorted unique types
  (no "All" default; first alphabetical type is selected)
- `_apply_cycle_filter` hides rows where `filter_text not in type_tooltip`
- Re-applies active search filter after type filter changes

### Search Filter

```python
search_box.textChanged → _apply_search_filter(search_text)
```

- Searches across all visible columns (`item.text()`)
- Row shown only if it passes **both** type filter AND search text
- Empty search restores type-filter-only view

Both filters call `_apply_row_color_coding()` and `_update_metadata_stats()` on completion.

---

## 10. Row Color Coding

`_apply_row_color_coding()` applied after every filter change:

- **Red background** `(255, 230, 230)` if concentration cell (col 3) is empty
- **White background** `(255, 255, 255)` otherwise
- Skips hidden rows (`isRowHidden`)
- Applied to every `QTableWidgetItem` in the row

---

## 11. Column Visibility

### Compact View

`compact_view: bool = False` (default expanded)

`_toggle_compact_view()`:
- True → hides `TABLE_COL_TIME` (2) and `TABLE_COL_CONC` (3)
- False → shows all cols 0–4

`_apply_compact_view_initial()` — applies compact state at widget init (no-op if False).

### Column Visibility Menu

`☰` button → `_show_columns_menu()` — toggles visibility of cols 1–4:

| Menu item | Column |
|-----------|--------|
| Type | `TABLE_COL_TYPE` (1) |
| Time | `TABLE_COL_TIME` (2) |
| Conc. | `TABLE_COL_CONC` (3) |
| ΔSPR | `TABLE_COL_DELTA_SPR` (4) |

Export (col 0) is not toggleable.  
Right-click on the horizontal header also calls `_show_columns_menu()`.

---

## 12. Details Panel (Flags & Notes Tabs)

`details_tab_widget` (below the table, max 120 px):

| Tab | Widget | Content |
|-----|--------|---------|
| Flags | `details_flags_text (QLabel)` | Formatted flags string from `_cycle_details_data[row]` |
| Notes | `details_notes_text (QLabel)` | `"[cycle_id]\nnote"` or "(No notes)" |

Updated by `_update_details_panel()` on every `itemSelectionChanged` signal.
Data source: `_cycle_details_data: dict[int, dict]` with keys `flags`, `note`, `cycle_id`.

---

## 13. Metadata Panel

Displayed below the table, left side. Labels updated by `_update_metadata_stats()` (in `DataMixin`):

| Widget | Data field |
|--------|-----------|
| `meta_method` | Method name |
| `meta_total_cycles` | `rowCount()` |
| `meta_cycle_types` | Unique type summary |
| `meta_conc_range` | Min–max concentration |
| `meta_date` | Experiment date from file |
| `meta_operator` | Operator name |
| `meta_device` | Device name |
| `sensor_input` (QLineEdit) | User-editable sensor type |

---

## 14. Alignment Panel

Hidden (`hide()`) until a cycle is selected. Shown by `main_window._on_cycle_selected_in_table`.

| Section | Controls |
|---------|----------|
| Cycle Details | `alignment_start_time`, `alignment_end_time`, `alignment_flags_display` |
| Reference Subtraction | `alignment_ref_combo` — "Global" / "None" / "Ch A–D"; triggers `_on_cycle_ref_changed` |
| Alignment Shift | `alignment_shift_input` (QLineEdit, float seconds) + `alignment_shift_slider` (−20s to +20s, 0.1s steps) |

Shift updates flow: `_on_shift_input_changed` ↔ `_on_shift_slider_changed` (kept in sync);
triggers `_update_selection_view()` in `AlignmentMixin`.

---

## 15. Active Selection View & ΔSPR Bar Chart

### Primary Graph (`edits_primary_graph`)

- 4 curves: black(A), red(B), blue(C), green(D)
- Two movable `InfiniteLine` cursors (dashed): green `delta_spr_start_cursor`, red `delta_spr_stop_cursor`
- Cursor movement → `_update_delta_spr_barchart()` in `AlignmentMixin`
- Smoothing: `edits_smooth_slider` (0–50) → `_update_selection_view()`

### ΔSPR Bar Chart (`delta_spr_barchart`)

- 4 `BarGraphItem` instances; colors match sensorgram curves (respects colorblind palette)
- Colors from `CHANNEL_COLORS` / `CHANNEL_COLORS_COLORBLIND` in `affilabs/plot_helpers.py`
- `TextItem` labels above each bar
- Lock button `🔓 Unlock` / `🔒 Locked` → `_toggle_delta_spr_lock()` locks cursor distance
  to `contact_time + 10%` for consistent measurement across cycles

---

## 16. Save & Export

### Save Back to Excel — `_save_cycles_to_excel()`

- Requires `_loaded_file_path` (set by `_load_data_from_excel_with_path_tracking`)
- Reads all sheets with `pd.read_excel(sheet_name=None)`
- Replaces the `"Cycles"` sheet with `pd.DataFrame(main_window._loaded_cycles_data)`
- Writes all other sheets back unchanged via `pd.ExcelWriter`

### Analysis Export — `_export_post_edit_analysis_with_charts()`

Delegates to `affilabs.utils.excel_chart_builder.create_analysis_workbook_with_charts()`.

Sheets produced:

| Sheet | Source |
|-------|--------|
| Raw Data | `_get_raw_data_untouched()` |
| Processed Data | `_get_processed_data_with_edits()` |
| Analysis Results | `_get_current_analysis_results()` — filtered to selected cycles |
| Flag Positions | `_get_updated_flag_positions()` — filtered to selected cycles |
| Cycles Metadata | `_get_enriched_cycles_metadata()` — filtered to selected cycles |
| Export Settings | Inline dict: version, user, smoothing, lock state, timestamps |

Charts: Delta SPR bars, timeline, flag positions, overview.

Only cycles where `_cycle_export_selection[idx] is True` are included.

---

## 17. State Variables

| Variable | Type | Owner | Description |
|----------|------|-------|-------------|
| `_cycle_export_selection` | `dict[int, bool]` | `EditsTab.__init__` | True = row checked for export |
| `_cycle_details_data` | `dict[int, dict]` | built in `add_cycle` / `_populate_cycles_table` | flags, note, cycle_id per row |
| `_cycle_type_counts` | `dict[str, int]` | TableMixin | per-type counter for display numbering |
| `_loaded_file_path` | `str \| None` | `EditsTab.__init__` | Path set on file open, used by save |
| `compact_view` | `bool` | `create_content()` init | False = expanded (default) |
| `cycle_filter` | `str` | `create_content()` init | Current type filter; "All" = show all |
| `_cycle_alignment` | `dict[int, dict]` | `EditsTab.__init__` | Per-row alignment settings |
| `edits_cycle_markers` | `list` | `create_content()` init | pyqtgraph items on timeline |
| `edits_cycle_labels` | `list` | `create_content()` init | pyqtgraph TextItems on timeline |

---

## 18. Signal Wiring (itemSelectionChanged)

When table selection changes, 4 slots fire:

1. `main_window._on_cycle_selected_in_table` — updates primary graph + cursor positions
2. `_update_export_sidebar_stats` — refreshes cycle count in the export sidebar
3. `_update_details_panel` — refreshes Flags & Notes tabs
4. `_reset_delta_spr_lock` — unlocks ΔSPR cursor lock for new selection
