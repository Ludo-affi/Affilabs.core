# EDITS_DATA_LOADING_FRS — Data Utilities Feature Specification

**Source:** `affilabs/tabs/edits/_data_mixin.py` (271 lines)  
**Consumed by:** `_table_mixin.py`, `_export_mixin.py`, `_alignment_mixin.py`, `edits_tab.py`  
**Version:** Affilabs.core v2.0.5 beta  
**Status:** Code-verified 2026-02-24 — clean

---

## 1. Overview

`DataMixin` provides 8 pure utility helpers used across all other Edits tab mixins. It contains no UI construction and no signals. It is responsible for:

| Responsibility | Methods |
|----------------|---------|
| **Flags system delegation** | `_edits_flags` property + setter |
| **Cycle data parsing** | `_parse_delta_spr`, `_format_flags_display`, `_collect_channel_data_from_cycle` |
| **File save path resolution** | `_get_save_path`, `_get_user_export_dir`, `_ensure_experiment_folder` |
| **Duration calculation** | `_calculate_actual_duration` |

---

## 2. State Variables

Initialised in `EditsTab.__init__` (not in `DataMixin` itself):

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| `_edits_flags_fallback` | `list` | `[]` | Local flags store when `FlagManager` is unavailable |
| `_selected_flag_idx` | `int \| None` | `None` | Currently selected flag index |
| `user_manager` | `UserProfileManager \| None` | Resolved from `main_window.app.user_profile_manager` | Used by `_get_user_export_dir` and `_ensure_experiment_folder` |
| `_loaded_metadata` | `dict` | `{}` | Metadata parsed from loaded Excel file |
| `_loaded_file_path` | `Path \| None` | `None` | Path to currently loaded Excel file |

`_loaded_cycles_data` and `_loaded_raw_data` are **not** owned by `DataMixin` — they live on `main_window` and are populated by `_edits_cycle_mixin.py` (`affilabs/ui_mixins/`).

---

## 3. `_edits_flags` Property

### Purpose
Backward-compatible delegating property. Old code that reads/writes `self._edits_flags` works the same whether `FlagManager` is available or not.

### Getter

```
Priority 1: main_window.app.flag_mgr.get_edits_flags()   ← authoritative source
Priority 2: self._edits_flags_fallback                    ← used if FlagManager absent
```

Failure modes: `AttributeError` or `RuntimeError` from accessing `app.flag_mgr` fall through silently to the fallback.

### Setter

```python
self._edits_flags_fallback = value
```

Writes to the local fallback only. If `FlagManager` is available, the setter does NOT forward to it — only the getter reads from it. Legacy code that assigns `self._edits_flags = [...]` will write to the fallback, which will be ignored if `FlagManager` is active.

> ⚠️ **Design note:** Setter does not forward to `FlagManager`. If `FlagManager` is active, any direct assignment is silently lost. This is intentional — only `FlagManager` should be the write target.

---

## 4. `_parse_delta_spr(cycle: dict) → dict`

### Purpose
Returns the `delta_spr_by_channel` dict from a cycle, handling both the native dict form and the stringified form that appears in Excel-loaded data.

### Input formats

| Source | Type | Example |
|--------|------|---------|
| Live cycle (from `RecordingManager`) | `dict` | `{'A': -12.5, 'B': -14.0, 'C': -8.2, 'D': -10.1}` |
| Excel-loaded cycle (pandas reads as string) | `str` | `"{'A': -12.5, 'B': -14.0, ...}"` |
| Missing key | `{}` | (missing or null) |

### Logic

```python
delta_by_ch = cycle.get('delta_spr_by_channel', {})
if isinstance(delta_by_ch, str):
    try:
        delta_by_ch = ast.literal_eval(delta_by_ch)
    except Exception:
        delta_by_ch = {}
return delta_by_ch if isinstance(delta_by_ch, dict) else {}
```

`ast.literal_eval` is used — not `eval()` — for safety. Returns `{}` on any parse failure.

### Callers

| Caller | Context |
|--------|---------|
| `_table_mixin._populate_cycles_table` | Initial table build |
| `_table_mixin._update_cycle_table_row` | Row refresh |
| `_table_mixin.add_cycle` | New cycle addition |
| `_export_mixin._export_raw_data_long_format` | Excel export |
| `_export_mixin._export_raw_data_direct` | Excel export |
| `_export_mixin._export_post_edit_analysis_with_charts` | Chart export |

---

## 5. `_format_flags_display(cycle: dict) → str`

### Purpose
Converts flag data from a cycle dict into a compact display string for the table. Reads only from the authoritative `flag_data` field (legacy `flags` fallback was removed in v2.0.5).

### Flag icons

| Flag type | Icon |
|-----------|------|
| `injection` | `▲` |
| `wash` | `■` |
| `spike` | `◆` |
| Unknown (unrecognised type) | `●` |

### Logic

```python
flag_data = cycle.get('flag_data', [])
if not flag_data:
    return ''

parts = []
for f in flag_data:
    icon = FLAG_ICONS.get(f.get('type', ''), '●')
    parts.append(f"{icon}{f.get('time', 0):.0f}s")
return " ".join(parts)
```

Returns empty string if `flag_data` is missing or empty list. Each flag item is expected to be a dict with `'type'` (str) and `'time'` (float/int) keys.

**Example:**
- Input: `[{'type': 'injection', 'time': 120.0}, {'type': 'wash', 'time': 240.0}]`
- Output: `"▲120s ■240s"`

### Callers

| Caller | Context |
|--------|---------|
| `_table_mixin.add_cycle` | New cycle row |
| `_table_mixin._update_cycle_table_row` | Row refresh |
| `_export_mixin._export_raw_data_direct` | Excel export flags column |

---

## 6. `_get_save_path(title, file_filter, subfolder) → str`

### Purpose
Unified `QFileDialog.getSaveFileName` wrapper that resolves the default directory consistently across all export operations.

### Arguments

| Argument | Default | Purpose |
|----------|---------|---------|
| `title` | (required) | Dialog title bar text |
| `file_filter` | `"Excel Files (*.xlsx)"` | File type filter shown in dialog |
| `subfolder` | `"Analysis"` | Subfolder within experiment folder |

### Directory resolution

```
1. _ensure_experiment_folder()
   ├─ Returns active experiment folder → get_subfolder_path(exp_folder, subfolder)
   └─ Returns None → fall through

2. _get_user_export_dir(subfolder)
   → Documents/Affilabs Data/<username>/<subfolder>/
```

Returns: selected file path string, or `""` if user cancels.

### Callers

| Caller | title argument | subfolder |
|--------|---------------|-----------|
| `_export_mixin._export_selection` (cycle path) | `"Export Combined Sensorgram"` | `"Analysis"` |
| `_export_mixin._export_raw_data` | `"Save Raw Data"` | `"Analysis"` |

---

## 7. `_collect_channel_data_from_cycle(cycle, fields) → dict`

### Purpose
Extracts per-channel values from a cycle dict using a flexible field-pattern API. Handles both the `delta_spr_by_channel` dict format and the `delta_ch1/ch2/ch3/ch4` numbered-column format, preferring the dict format.

### Arguments

```python
fields: dict[str, str]
# Maps result key name → field pattern with optional substitution tokens
# Tokens: {num} = 1-4, {ch} = A-D
# Examples:
#   {'delta': 'delta_ch{num}'}
#   {'delta': 'delta_ch{num}', 'time': 'time_ch{num}'}
```

### Return structure

```python
{
    'A': {'delta': -12.5, 'time': 120.0, ...},
    'B': {'delta': -14.0, ...},
    'C': {'delta': -8.2, ...},
    'D': {'delta': -10.1, ...},
}
```
Only present if value is non-empty and `pd.notna(value)` is True.

### Lookup order for `delta` fields

1. `_parse_delta_spr(cycle)` → `delta_spr_by_channel` dict (channel-keyed)
2. `cycle[pattern.format(num=i)]` → numbered columns (1-based)

For all other field names, only the pattern lookup is used.

### Callers

Referenced in `docs/architecture/PRD_METHOD_BUILDER_DATA_FLOW.md` but not called from within the edits tab mixin files. Designed as a utility for `_export_mixin` chart export and future consumers.

---

## 8. `_get_user_export_dir(subfolder: str = "SPR_data") → Path`

### Purpose
Returns the current user's default export directory, creating it if it doesn't exist.

### Path formula

```
Path.home() / "Documents" / "Affilabs Data" / {username} / {subfolder}
```

- `username` resolved from `self.user_manager` (lazy init from `main_window.app.user_profile_manager`)
- Falls back to `"Default"` if no user manager or current user returns `None`
- Directory created with `mkdir(parents=True, exist_ok=True)`

### Callers

| Caller | subfolder used |
|--------|---------------|
| `_export_mixin._export_raw_data` | default `"SPR_data"` |
| `_export_mixin._export_post_edit_analysis_with_charts` | default `"SPR_data"` |
| `_export_mixin._export_table_data` | default `"SPR_data"` |
| `_export_mixin._export_for_external_software` | default `"SPR_data"` |
| `_table_mixin._save_timeline_to_pdf` | default `"SPR_data"` |
| `_get_save_path()` (internal) | caller-specified |

---

## 9. `_ensure_experiment_folder() → Path | None`

### Purpose
Provides access to the active GLP/GMP experiment folder. Returns immediately if one already exists; otherwise prompts the user to name one and creates it.

### Resolution flow

```
1. main_window.app.current_experiment_folder → return immediately if set

2. QInputDialog.getText("Create Experiment Folder", default="Experiment")
   └─ User cancels / empty → return None

3. Resolve user_name from user_manager (lazy init)
4. Resolve device_id from main_window.app.device_config.device_serial

5. experiment_folder_mgr.create_experiment_folder(
       experiment_name, user_name, device_id, sensor_type="", description=""
   )
   └─ Success → store in main_window.app.current_experiment_folder → return path
   └─ Exception → QMessageBox.warning → return None
```

### Callers

| Caller | Context |
|--------|---------|
| `_get_save_path()` (internal) | Default dir resolution for all dialogs |
| `_export_mixin._export_post_edit_analysis_with_charts` | Direct call |
| `_export_mixin._export_for_external_software` | Direct call |

---

## 10. `_calculate_actual_duration(cycle_idx, cycle, all_cycles) → float`

### Purpose
Returns the actual duration (in minutes) for a cycle, using the best available source. Avoids recalculating when pre-computed data is present.

### Arguments

| Argument | Type | Source |
|----------|------|--------|
| `cycle_idx` | `int` | Row index in `all_cycles` |
| `cycle` | `dict` | From `Cycle.to_export_dict()` or `_loaded_cycles_data[row]` |
| `all_cycles` | `list[dict]` | Full cycle list (for spacing calculation) |

### Strategy cascade

```
1. cycle.get('duration_minutes')
   If present and > 0 → return it
   ↓

2. cycle.get('start_time_sensorgram') + next cycle's start_time_sensorgram
   If both valid: (next_start - current_start) / 60.0
   ↓

3. cycle.get('length_minutes', 0)   ← planned duration fallback
```

Each strategy logs at `DEBUG` level with the resolved value.

**Strategy 2 not available** for the last cycle (no next cycle) → falls to strategy 3.

### Callers

| Caller | Context |
|--------|---------|
| `_table_mixin._populate_cycles_table` | Duration display in table rows |
| `_table_mixin._update_cycle_table_row` | Row refresh |

---

## 11. Cycle Data Structures

These structures are consumed by `DataMixin` methods but are owned by `main_window`:

### `main_window._loaded_cycles_data` — `list[dict]`

Populated by `_edits_cycle_mixin.py` from Excel Cycles sheet. Each dict is a flat row from `Cycle.to_export_dict()`.

Key fields consumed by `DataMixin`:

| Field | Type | Description |
|-------|------|-------------|
| `delta_spr_by_channel` | `dict \| str` | Per-channel ΔSPR at time of recording; may be stringified |
| `flag_data` | `list[dict]` | Structured flags: `[{'type': str, 'time': float}]` |
| `flags` | `list \| str` | Legacy flag field (fallback) |
| `duration_minutes` | `float` | Pre-calculated actual duration |
| `start_time_sensorgram` | `float` | Absolute start time in seconds |
| `length_minutes` | `float` | Planned (programmed) duration |
| `delta_ch1` … `delta_ch4` | `float` | Per-channel ΔSPR (numbered format; 1=A, 2=B, 3=C, 4=D) |

### `main_window._loaded_raw_data` — `list[dict]`

Long-format raw SPR data. Each dict is one time-point for one channel:

```python
{
    'time': float,      # Seconds from recording start
    'channel': str,     # 'a', 'b', 'c', or 'd' (lowercase)
    'value': float,     # Wavelength in nm (pre-RU conversion)
}
```

### `main_window._edits_raw_data` — `pd.DataFrame`

Wide-format version of raw data (one row per time point, one column per channel). Set by `_edits_cycle_mixin._on_send_to_edits_clicked()`:

```
Columns: time_s, Channel_A_nm, Channel_B_nm, Channel_C_nm, Channel_D_nm
```

---

## 12. ExperimentFolderManager Interface

`_ensure_experiment_folder()` calls `main_window.app.experiment_folder_mgr` (an `ExperimentFolderManager` instance, sourced from `affilabs/utils/experiment_folder_manager.py`).

Methods used:

| Method | Signature | Purpose |
|--------|-----------|---------|
| `create_experiment_folder` | `(experiment_name, user_name, device_id, sensor_type, description) → Path` | Creates GLP folder structure |
| `get_subfolder_path` | `(exp_folder, subfolder_name) → Path` | Returns path to a named subfolder |

`main_window.app.current_experiment_folder` persists the active experiment across the session.

---

## 13. Method Inventory

| Method | Lines | Return | Purpose |
|--------|-------|--------|---------|
| `_edits_flags` (property) | ~10 | `list` | Delegate to FlagManager or fallback |
| `_edits_flags` (setter) | 2 | — | Write to fallback only |
| `_parse_delta_spr` | ~15 | `dict` | Parse ΔSPR, handle stringified Excel format |
| `_format_flags_display` | ~10 | `str` | Flags → icon-annotated display string (cleaned-up, no legacy fallback) |
| `_get_save_path` | ~20 | `str` | Unified file save dialog |
| `_collect_channel_data_from_cycle` | ~25 | `dict` | Multi-field per-channel extraction |
| `_get_user_export_dir` | ~15 | `Path` | User's default export directory |
| `_ensure_experiment_folder` | ~40 | `Path \| None` | Active experiment folder (prompt if needed) |
| `_calculate_actual_duration` | ~20 | `float` | Best-available duration in minutes |

---

## 14. Known Issues

None. File is clean.

**Changes made this session:**
- Removed legacy `flags` fallback from `_format_flags_display` (§5). Codebase audit confirmed `flags` field in cycle dicts is always an integer (0) or empty string `''` — never a structured list. Only `flag_data` is authoritative for display. See session context for verification across the codebase.
