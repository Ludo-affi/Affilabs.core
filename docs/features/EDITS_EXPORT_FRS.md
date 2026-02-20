# Edits Tab — Export System FRS

> **Source files (code-verified)**
> - `affilabs/tabs/edits/_export_mixin.py` — all Edits tab export methods (1467 lines)
> - `affilabs/widgets/_dw_export_mixin.py` — live recording TraceDrawer export (reference)
> - `affilabs/widgets/metadata.py` — `Metadata.write_tracedrawer_header()`, `CurveTable`
> - `affilabs/utils/data_exporter.py` — `ExportFormat` enum, export presets
> - `affilabs/ui_mixins/_edits_cycle_mixin.py` — `_export_segment_to_tracedrawer()`
> - `affilabs/utils/export_helpers.py` — `ExportHelpers.build_channels_xy_from_wide_dataframe()`

---

## 1. Export Sidebar

Fixed-width (260 px) left panel, visible by default, constructed in `_create_export_sidebar()`.

### Button Inventory

| Button | Label | Method | File type |
|--------|-------|--------|-----------|
| 💾 | Export Analysis | `_export_table_data()` | `.xlsx` or `.csv` |
| 📊 | Export with Charts | `_export_post_edit_analysis_with_charts()` | `.xlsx` (openpyxl charts) |
| 📋 | Save as Method | `_save_cycles_as_method()` | `.json` |
| 📊 | Export Sensorgram | `_export_graph_image()` | `.png` / `.jpg` / `.svg` |
| 📈 | Export ΔSPR Chart | `_export_barchart_image()` | `.png` / `.jpg` / `.svg` |
| 📋 | Copy to Clipboard | `_copy_table_to_clipboard()` | tab-separated text |
| 🔗 | External Software | `_export_for_external_software()` | `.csv` |

Also reachable via the **📥 Export** button in the tools panel (`_export_selection()`).

### Summary Stats Widget

Updated by `_update_export_sidebar_stats()` on every `itemSelectionChanged` signal.

| Label | Content |
|-------|---------|
| `export_stats_cycles` | Count of visible (unfiltered) rows |
| `export_stats_selected` | Count of table-selected rows |
| `export_stats_channels` | Always "A, B, C, D" (static) |
| `export_stats_duration` | First visible row's Time → last visible row's Time |

Sidebar collapse: `_toggle_export_sidebar()` toggles `export_sidebar.isVisible()` and syncs `export_toggle_btn.checked`.

---

## 2. Export Dispatch — `_export_selection()`

The primary "Export" button in the tools panel. Logic:

```
1. Check main_window._edits_raw_data → if present, call _export_raw_data_direct(df)
2. elif recording_mgr.data_collector.raw_data_rows → call _export_raw_data_long_format(raw_rows)
3. else → export selected cycle rows as combined sensorgram (multi-sheet .xlsx)
```

The cycle-based path (case 3) iterates `selectedItems()` rows, applies `_cycle_alignment`
settings (channel filter + time shift), then converts wavelength data to RU using
`WAVELENGTH_TO_RU = 355.0`.

**Sheets produced (case 3):**

| Sheet | Content |
|-------|---------|
| Combined Data (Long) | Long format: Time_s, Channel, Wavelength_nm, Response_RU, Cycle_Index, Cycle_Type |
| Per-Channel Format | Wide: Time_A, A, Time_B, B, Time_C, C, Time_D, D |
| Cycle Metadata | One row per cycle: indices, types, shift, conc, Delta_A/B/C/D |
| Alignment | `_cycle_alignment` rows for selected cycles |
| Flags | `_edits_flags` list (each flag's `.to_export_dict()`) |
| Export Info | Date, total cycles, data points |

Per-channel format built via `ExportHelpers.build_channels_xy_from_wide_dataframe()`.

---

## 3. Raw Data Export Paths

### 3a. `_export_raw_data_long_format(raw_rows)`

Input: list of row dicts from `recording_mgr.data_collector.raw_data_rows`  
Expected row keys: `{'elapsed'|'time', 'channel', 'value'}`

**Sheets produced:**

| Sheet | Content |
|-------|---------|
| Raw Data | Long: Time, Channel (upper), Value |
| Per-Channel Format | Wide: Time_A, A, … Time_D, D |
| Cycle Table | Cycle #, Type, Duration, Start Time, Concentration, Units, Delta_A–D, Flags, Notes |
| Export Info | Date, data points, channels, cycle count |

Default save path: `experiment_folder / Raw_Data / Raw_{timestamp}.xlsx`.  
After save, registers file with `experiment_folder_mgr.register_file(entry, "raw_data", …)`.

### 3b. `_export_raw_data_direct(df_raw)`

Input: `DataFrame` from `main_window._edits_raw_data` (columns: Time, A, B, C, D).

**Sheets produced:**

| Sheet | Content |
|-------|---------|
| Raw Data | Wide: Time, A, B, C, D |
| Per-Channel Format | Wide: Time_A, A, Time_B, B, … (NaN-stripped per channel) |
| Cycle Table | Same as 3a minus Flags/Start columns |
| Export Info | Date, source file path, data points, time range, cycle count |

Save path: user-specified via `QFileDialog`, defaults to `_get_user_export_dir()`.

### 3c. `_export_raw_data()`

Gets `DataFrame` from `main_window._edits_raw_data` directly.  
Produces: Raw Data + Per-Channel Format + Export Info sheets.  
No Cycle Table sheet. Labeled "Live Data" in Export Info.

---

## 4. Analysis Table Export — `_export_table_data()`

Exports the visible (non-filtered) rows of `cycle_data_table` to `.xlsx` or `.csv`.

- Respects hidden columns (`isColumnHidden`)
- Respects hidden rows (`isRowHidden`) — only visible rows exported
- Default save path: `experiment_folder / Analysis / Analysis_{timestamp}.xlsx`
- Falls back to CSV if pandas unavailable (`_write_csv(file_path, rows_data)`)
- Registers file with experiment manager on success
- Updates `sidebar.intel_message_label` (not a dialog) on success/failure

---

## 5. Export with Charts — `_export_post_edit_analysis_with_charts()`

Full analysis workbook built by `affilabs.utils.excel_chart_builder.create_analysis_workbook_with_charts()`.

**Data sources:**

| Source | Method |
|--------|--------|
| Raw data | `_get_raw_data_untouched()` |
| Processed data | `_get_processed_data_with_edits()` |
| Analysis results | `_get_current_analysis_results()` |
| Flag positions | `_get_updated_flag_positions()` |
| Cycles metadata | `_get_enriched_cycles_metadata()` |

All result tables are filtered to cycles where `_cycle_export_selection[idx] is True`.

**Export settings dict** (written to "Export Settings" sheet):

| Key | Source |
|-----|--------|
| export_timestamp | `datetime.now().isoformat()` |
| user | `user_manager.get_current_user()` |
| smoothing_level | `edits_smooth_slider.value()` |
| baseline_corrected | Always `True` |
| cursor_lock_active | `_delta_spr_cursor_locked` |
| locked_distance | `_delta_spr_lock_distance` |
| software_version | `"Affilabs Core v2.0"` |
| selected_cycles / total_cycles | counts from `_cycle_export_selection` |

Requires at least one export-checkbox-selected cycle; shows warning if none.

---

## 6. Image Export

### `_export_barchart_image()`

Source: `delta_spr_barchart.plotItem`  
Uses `pg.exporters.ImageExporter`; sets width=1200 px.  
Formats: PNG (default), JPEG, SVG.

### `_export_graph_image()`

Source: `edits_primary_graph.plotItem`  
Uses `pg.exporters.ImageExporter`; sets width=2400 px.  
Formats: PNG (default), JPEG, SVG.

---

## 7. TraceDrawer Compatibility

### TraceDrawer CSV Format Spec

TraceDrawer is the **primary external analysis software** target for Affilabs.core exports.

**File format:**
- Extension: `.txt`
- Encoding: UTF-8
- Delimiter: **tab** (`excel-tab` dialect)
- Column headers: `X_RawDataA, Y_RawDataA, X_RawDataB, Y_RawDataB, X_RawDataC, Y_RawDataC, X_RawDataD, Y_RawDataD`
- X values: time in seconds (4 decimal places)
- Y values: wavelength shift in **RU** = `(λ - λ_reference) × 355.0` (4 decimal places)

**Metadata header** (rows before data columns, written by `Metadata.write_tracedrawer_header()`):

| Row col[0] | Row col[1] | Notes |
|------------|-----------|-------|
| `Plot name` | dataset name | e.g. "Raw data" |
| `Plot xlabel` | `Time (s)` | |
| `Plot ylabel` | `RU` | |
| `Property Analysis date` | ISO datetime with timezone | |
| `Property Filename` | `{name} {YYYY-MM-DD HH:MM}` | |
| `Property Instrument id` | serial number | optional; blank row if empty |
| `Property Instrument type` | model string (e.g. "P4SPR") | optional |
| `Property Software` | `ezControl {SW_VERSION}` | |
| `Property Solid support` | | blank |
| `Property Reference Levels (nm)` | `λA;λB;λC;λD` | reference wavelengths at t=0 |
| *(curve rows)* | per `CurveTable.output()` | curve names, concentrations in scientific notation |

**Concentration string format** (in header):  
`1.5E-7(0)` = 150 nM injected at t=0. No `+` sign after E (TraceDrawer rejects `E+7`).  
Implemented in `ConcentrationEntry.output()` with `.replace("+", "")`.

### Where TraceDrawer Export Is Currently Implemented

| Location | Method | Path |
|----------|--------|------|
| Live recording | `_dw_export_mixin.export_raw_data()` | Main window recording tab |
| Segments (edits cycle mixin) | `_export_segment_to_tracedrawer()` → `segment.export_to_tracedrawer_csv()` | Old edits UI (pre-mixin refactor) |

### Gap: ExportMixin Has No TraceDrawer Path

The `_export_for_external_software()` button in the export sidebar currently writes a
**Prism/Origin-compatible CSV** (one row per cycle, concentration + ΔSPR columns).
This is **not** a TraceDrawer format.

For the Edits tab to be TraceDrawer-compatible, `_export_for_external_software()` (or a
new dedicated button) must produce:
- Tab-delimited `.txt`
- `X_RawDataA/Y_RawDataA … X_RawDataD/Y_RawDataD` column pairs
- Metadata header via `Metadata.write_tracedrawer_header()`
- Y values as RU: `(wavelength_value - reference_wavelength) * 355.0`
- Reference = first wavelength value at or after t=0 per channel (same logic as `_dw_export_mixin`)

**Implementation note:** The header writer requires a live `Metadata` widget instance
(`self.metadata`) to pull instrument type, instrument ID, and curve names from.
These come from `affilabs/widgets/settings_menu.py` → `MetadataTab`. Confirm whether
this widget instance is accessible from `ExportMixin` before wiring.

---

## 8. Save as Method — `_save_cycles_as_method()`

Converts visible table rows into a reusable method JSON.

**Source:** Reads from the table widget (cols 1–6), not from `_loaded_cycles_data`.

**Abbreviation → full type mapping** (applied during parse):

| Abbr | Full type |
|------|-----------|
| BL | Baseline |
| IM | Immobilization |
| WS | Wash |
| CN | Concentration |
| RG | Regeneration |
| CU | Custom |
| AS | Association |
| DS | Dissociation |
| BD | Binding |

**JSON schema produced:**

```json
{
  "version": "1.0",
  "name": "My Method",
  "description": "Created from Edit tab cycle table (N cycles)",
  "author": "username",
  "created": "2026-02-19T…",
  "source_experiment": "exp_folder_name",
  "cycles": [
    {
      "type": "Baseline",
      "length_minutes": 2.0,
      "note": "",
      "pumps": {},
      "contact_times": {},
      "concentration_value": 150.0,   ← only if parsed
      "concentration_units": "nM"
    }
  ],
  "cycle_count": N
}
```

Default save directory: `~/Documents/Affilabs Methods/{username}/`.  
Method files can be re-loaded in the Method Builder sidebar.

---

## 9. External Software CSV — `_export_for_external_software()`

Produces a **row-per-cycle** CSV for pasting into curve-fitting software.

**Current output columns:**

| Column | Source |
|--------|--------|
| Cycle Type | `type_item.toolTip()` |
| Concentration | First number parsed from conc cell |
| ΔSPR Ch A (RU) | Parsed from ΔSPR cell (`A:val` pattern) |
| ΔSPR Ch B (RU) | Parsed from ΔSPR cell |
| ΔSPR Ch C (RU) | Parsed from ΔSPR cell |
| ΔSPR Ch D (RU) | Parsed from ΔSPR cell |

ΔSPR regex: `([ABCD]):([+-]?\d+\.?\d*)` applied to col 4 cell text.

This format is **suitable for GraphPad Prism / Origin** binding analysis workflows
(concentration vs. response columns).

**This is not TraceDrawer format** — see Section 7 for the distinction.

---

## 10. Clipboard Copy — `_copy_table_to_clipboard()`

Scope: selected rows if any selection active, else all visible (non-hidden) rows.  
Skips hidden columns.  
Format: tab-separated, with header row from `horizontalHeaderItem(col).text()`.  
Written to `QApplication.clipboard()`.  
Feedback: `sidebar.intel_message_label` if available, else `QMessageBox.information`.

---

## 11. Per-Channel Format (shared convention)

Used in `_export_selection`, `_export_raw_data_long_format`, `_export_raw_data_direct`, and `_export_raw_data`.

Column order: `Time_A, A, Time_B, B, Time_C, C, Time_D, D`

For long-format sources: built via `ExportHelpers.build_channels_xy_from_wide_dataframe(df_wide, channels=['A','B','C','D'])`.  
For direct DataFrame sources: per-channel NaN-stripped manually with `df[ch].notna()` masking, then
padded to max length with `None`.

This format is **not** the same as TraceDrawer (`X_RawDataA` etc.) but is compatible with
Excel and Origin for manual analysis.

---

## 12. Default Save Paths

| Method | Default path |
|--------|-------------|
| `_export_table_data` | `experiment_folder/Analysis/Analysis_{ts}.xlsx` |
| `_export_raw_data_long_format` | `experiment_folder/Raw_Data/Raw_{ts}.xlsx` |
| `_export_raw_data_direct` | `user_export_dir / Edits_Data_{ts}.xlsx` |
| `_export_raw_data` | `user_export_dir / Live_Data_{ts}.xlsx` |
| `_export_for_external_software` | `user_export_dir / SPR_external_{ts}.csv` |
| `_save_cycles_as_method` | `~/Documents/Affilabs Methods/{username}/{name}.json` |
| `_export_graph_image` | CWD: `sensorgram_{ts}.png` |
| `_export_barchart_image` | CWD: `delta_spr_barchart_{ts}.png` |

`user_export_dir` comes from `_get_user_export_dir(subfolder='SPR_data')` in `DataMixin`.  
`experiment_folder` comes from `_ensure_experiment_folder()` in `DataMixin`.

---

## 13. Experiment Folder Integration

Both `_export_table_data` and `_export_raw_data_long_format` call:

```python
experiment_folder_mgr.register_file(
    exp_folder,
    Path(file_path),
    "analysis"|"raw_data",
    description
)
```

This only runs if `Path(file_path).is_relative_to(exp_folder)` — i.e., the user saved
inside the experiment folder. Files saved elsewhere are not registered.

---

## 14. Missing / Known Issues

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 1 | `_export_for_external_software()` produces Prism CSV, not TraceDrawer format | `_export_mixin.py` L1254 | TraceDrawer cannot import this file |
| 2 | ~~Export sidebar "External Software" tooltip said "Prism / Origin" — did not mention TraceDrawer~~ | Fixed | Tooltip now clarifies TraceDrawer is on main tab |
| 3 | ~~`_save_cycles_as_method` read from table cols 5 and 6 (non-existent)~~ | Fixed | Now reads from `_cycle_details_data` |
| 4 | Image exports default to CWD (no user-specific folder) | L656, L694 | Inconsistent with other exports |
