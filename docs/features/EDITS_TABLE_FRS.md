# Edits Tab — Cycle Table FRS

> **Source files**
> - `affilabs/tabs/edits_tab.py` — class constants, `__init__`, index integration
> - `affilabs/tabs/edits/_table_mixin.py` — all table operations
> - `affilabs/tabs/edits/_ui_builders.py` — layout construction

---

## 1. Class Composition

```python
class EditsTab(DataMixin, ExportMixin, UIBuildersMixin, AlignmentMixin, TableMixin, BindingPlotMixin):
    CHANNELS       = ['A', 'B', 'C', 'D']
    CHANNELS_LOWER = ['a', 'b', 'c', 'd']
    TABLE_COL_EXPORT    = 0
    TABLE_COL_TYPE      = 1
    TABLE_COL_TIME      = 2
    TABLE_COL_CONC      = 3
    TABLE_COL_DELTA_SPR = 4
```

---

## 2. Cycle Data Table

### Column Layout

| Index | Constant | Header | Width | Notes |
|-------|----------|--------|-------|-------|
| 0 | `TABLE_COL_EXPORT` | Export | 50px fixed | Centered QCheckBox widget |
| 1 | `TABLE_COL_TYPE` | Type | 55px fixed | Abbr + cycle num, colored by type |
| 2 | `TABLE_COL_TIME` | Time | Stretch | `"{dur:.1f}m @ {start:.0f}s"` |
| 3 | `TABLE_COL_CONC` | Conc. | Stretch | Concentration value; **hidden by default** |
| 4 | `TABLE_COL_DELTA_SPR` | ΔSPR | Stretch | `"A:val B:val C:val D:val"` in RU |

- Row height: 22px; vertical header hidden; alternating row colors
- Selection: `ExtendedSelection`, row-based (Ctrl/Shift multi-select)

### ΔSPR Data Resolution (two-path)

1. **Priority 1** — `_parse_delta_spr(cycle)` → `{'A': float, 'B': float, …}` (live acquisition)
2. **Priority 2** — `delta_ch1/delta_ch2/delta_ch3/delta_ch4` keys (Excel import fallback)

---

## 3. Cycle Entry Paths

### Live Acquisition — `add_cycle(cycle_dict)`

```
add_cycle(cycle_dict)
  → insertRow at rowCount
  → append to main_window._loaded_cycles_data
  → increment _cycle_type_counts[cycle_type]
  → setCellWidget(row, 0, _create_export_checkbox(row_idx))
  → setItem cols 1–4
  → store flags/notes/cycle_id in _cycle_details_data[row_idx]
  → _update_empty_state()
  → _update_metadata_stats()
  → update filter_combo if new type
  → scrollToBottom()
```

### Excel Import — `_populate_cycles_table(cycles_data)`

```
_populate_cycles_table(cycles_data)
  → setRowCount(0)  ← clears all rows
  → reset _cycle_export_selection, _cycle_type_counts
  → for each cycle: same column setup as add_cycle
  → _update_empty_state()
  → _update_metadata_stats()
```

---

## 4. Export Selection

Each row has a **widget-based** checkbox — not a `QTableWidgetItem`.

| Component | Description |
|-----------|-------------|
| `_create_export_checkbox(cycle_idx, checked=True)` | Centered QWidget container with QCheckBox |
| `_on_export_checkbox_toggled(cycle_idx, state)` | `_cycle_export_selection[cycle_idx] = bool` |
| `_cycle_export_selection: dict[int, bool]` | Single source of truth for export selection |

---

## 5. Row Operations

### Edit Timing Dialog

`_edit_cycle_timing(row_index)` — modal QDialog with:
- `QDoubleSpinBox` for start time and end time (seconds)
- Read-only duration label (turns red if end ≤ start)
- Saves back to `main_window._loaded_cycles_data[row_index]`

### Delete

`_delete_cycles_from_table(row_indices)`:
- Confirms with `QMessageBox.question`
- Removes in reverse index order from table + `_loaded_cycles_data`
- Rebuilds `_cycle_alignment` to correct indices

### Programmatic Selection

`_select_cycle_by_index(cycle_idx)` — calls `selectRow()`; `itemSelectionChanged` drives graph update.

---

## 6. Context Menu (Right-click)

| Selection | Actions |
|-----------|---------|
| 1 row | ✏️ Edit Cycle Timing, 📊 Load to Reference Graph (submenu 1/2/3), 🗑️ Delete |
| N rows | 🗑️ Delete cycles |

---

## 7. Timeline Marker Overlay

`add_cycle_markers_to_timeline(cycles_data)` decorates `edits_timeline_graph`:

- `LinearRegionItem` per cycle — colored by type (baseline=gray, association=blue, dissociation=yellow, regen=red, wash=green)
- `InfiniteLine` (dotted gray) at each cycle start
- `TextItem` `"Cycle N\n(type)"` label
- Click on region → `_select_cycle_by_index(idx)` syncs table row

---

## 8. Filtering

### Type Filter

```python
filter_combo.currentTextChanged → _apply_cycle_filter(filter_text)
```
- Populated by `_update_cycle_type_filter(cycles_data)` (sorted unique types)
- Hides rows where type doesn't match

### Search Filter

```python
search_box.textChanged → _apply_search_filter(search_text)
```
- Searches across all visible column text
- Row shown only if it passes both type + search filter

Both filters call `_apply_row_color_coding()` and `_update_metadata_stats()` on completion.

---

## 9. Row Color Coding

`_apply_row_color_coding()`:
- Red background `(255, 230, 230)` if concentration cell (col 3) is empty
- White `(255, 255, 255)` otherwise
- Skips hidden rows

---

## 10. Column Visibility

`☰` button → `_show_columns_menu()` — toggles cols 1–4:

| Menu item | Column |
|-----------|--------|
| Type | 1 |
| Time | 2 |
| Conc. | 3 (hidden by default) |
| ΔSPR | 4 |

Export (col 0) is not toggleable.

---

## 11. Details Panel (Notes)

`details_tab_widget` is now a plain `QFrame` (not a QTabWidget). Flags tab removed.

`_update_details_panel()` — called on every `itemSelectionChanged`:
- If selected cycle has a non-empty note: shows `cycle_notes_edit` with text
- Otherwise: hides the panel entirely

Data source: `_cycle_details_data: dict[int, dict]` with keys `flags`, `note`, `cycle_id`.

---

## 12. Metadata Panel

Updated by `_update_metadata_stats()` in `edits_tab.py`:

| Widget | Data |
|--------|------|
| `meta_method` | Method name from metadata |
| `meta_total_cycles` | Count of visible rows |
| `meta_cycle_types` | Comma-separated unique types |
| `meta_conc_range` | Min–max concentration |
| `meta_date` | Recording date/time |
| `meta_operator` | From metadata or user_manager |
| `meta_device` | Serial (FLMT → AFFI masked) |
| `meta_calibration` | Startup calibration JSON filename |
| `meta_transmission_file` | Baseline recording filename |
| `meta_star_buttons[0..4]` | Star rating (0–5), linked to ExperimentIndex |
| `meta_tags_pills` | Tag pills (blue), linked to ExperimentIndex |
| `meta_tag_input` | QLineEdit for adding new tags |
| `sensor_input` | User-editable sensor type |

### ExperimentIndex Integration

`_find_index_entry_for_file(path)` — matches loaded file path against index entries.
Returns `None` if not found (new recording or missing index).

Star rating: `_on_star_clicked(n)` → `ExperimentIndex.set_rating(entry_id, n)` (click same star again to clear).

Tags: `_on_tag_added()` / `_on_tag_removed(tag)` → `ExperimentIndex.add_tag/remove_tag`.

---

## 13. Experiment Browser

`_open_experiment_browser()` in `_table_mixin.py`:
- Switches to Notes tab (`content_stack.setCurrentIndex(2)`) if Notes tab exists
- Falls back to `ExperimentBrowserDialog` if Notes tab not available

---

## 14. Signal Wiring (itemSelectionChanged)

When table selection changes, 4 slots fire:

1. `_on_cycle_selected_in_table` — updates primary graph + cursor positions
2. `_update_export_sidebar_stats` — refreshes export sidebar cycle count
3. `_update_details_panel` — refreshes notes panel
4. `_reset_delta_spr_lock` — unlocks ΔSPR cursor lock

---

## 15. State Variables

| Variable | Type | Description |
|----------|------|-------------|
| `_cycle_export_selection` | `dict[int, bool]` | True = row checked for export |
| `_cycle_details_data` | `dict[int, dict]` | flags, note, cycle_id per row |
| `_cycle_type_counts` | `dict[str, int]` | Per-type counter for display numbering |
| `_loaded_file_path` | `str \| None` | Path set on file open |
| `_loaded_metadata` | `dict` | Parsed from Excel Metadata sheet |
| `_cycle_alignment` | `dict[int, dict]` | Per-row alignment settings |
| `edits_cycle_markers` | `list` | pyqtgraph LinearRegionItems on timeline |
| `edits_cycle_labels` | `list` | pyqtgraph TextItems on timeline |

---

**Last Updated:** February 24, 2026
**Codebase Version:** Affilabs.core v2.0.5 beta
