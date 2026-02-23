# EDITS_BINDING_PLOT_FRS — Binding Plot Feature Specification

**Source (to be created):** `affilabs/tabs/edits/_binding_plot_mixin.py`
**UI wiring:** `affilabs/tabs/edits/_ui_builders.py`
**State init:** `affilabs/tabs/edits/edits_tab.py`
**Version:** Affilabs.core v2.0.5 beta
**Status:** Specification — not yet implemented

---

## 1. Purpose

The Binding Plot lets users visualise how **ΔSPR varies with analyte concentration** across multiple binding cycles. This is the primary quantitative output of an SPR dose-response experiment:

- **Linear fit** — for early-phase (low-occupancy) data or quick QC
- **1:1 Langmuir fit** — equilibrium Kd estimate from multi-concentration binding data

This is the last FRS for v2.0.5. It completes the analysis loop:

```
Acquire cycles → Edits tab → measure ΔSPR per cycle → Binding Plot → Kd / linearity
```

---

## 2. Layout Change

### Before

```
RIGHT column (graphs_splitter, vertical)
  ├── TOP 55%:  Active Cycle View (sensorgram + cursors)
  └── BOT 45%:  Delta SPR Bar Chart  ← single widget
```

### After

```
RIGHT column (graphs_splitter, vertical)
  ├── TOP 55%:  Active Cycle View  (unchanged)
  └── BOT 45%:  QTabWidget
        ├── Tab 0: "ΔSPR"     Delta SPR Bar Chart  (existing, unchanged)
        └── Tab 1: "Binding"  Binding Plot          (new)
```

**Implementation:** In `_ui_builders._build_edits_layout()`, wrap `barchart_widget` in a `QTabWidget` before adding it to `graphs_splitter`. Store as `self.bottom_tab_widget`.

---

## 3. Binding Tab Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  [A] [B] [C] [D]   Model: [Linear ▼]                          │  ← controls bar (32px)
├───────────────────────────────────────┬─────────────────────────┤
│                                       │  Model                  │
│   Scatter plot                        │  ───────────────────    │
│   X = Concentration (µM)             │  Linear                 │
│   Y = ΔSPR (RU)                      │  y = mx + b             │
│                                       │  m = 0.42 RU/µM         │
│   • dots per cycle                    │  b = 1.3 RU             │
│   ─── fit line                        │  R² = 0.991             │
│                                       │                         │
│   (pyqtgraph PlotWidget)              │  ref: Ch D              │
│                                       │  ⚠ Kd = 2.4 µM         │
│                                       │  (equilibrium estimate) │
└───────────────────────────────────────┴─────────────────────────┘
```

**Proportions:** Plot 70% width | Formula panel 30% width (QSplitter, horizontal, user-resizable).

### Controls bar widgets

| Widget | Type | Behaviour |
|--------|------|-----------|
| `binding_ch_btns` | 4× `QPushButton`, checkable, exclusive | A / B / C / D — one selected at a time. Disabled + greyed if that channel has no valid ΔSPR + concentration pairs across the selected cycles. Auto-selects first channel with valid data on update. |
| `binding_model_combo` | `QComboBox` | Linear / 1:1 Langmuir |

**No explicit Fit button** — plot re-computes automatically whenever channel, model, or table selection changes and the Binding tab is active.

### Channel button style

Matches the live-data channel toggle pattern (outlined, colored border when active):

```python
# Active state — channel color border
"QPushButton:checked { border: 2px solid {color}; background: white; color: {color}; font-weight: 600; }"
# Disabled state — greyed, not clickable
"QPushButton:disabled { color: #C7C7CC; border: 1px solid #E5E5EA; background: #F8F9FA; }"
```

Channel colors match `CHANNEL_COLORS` from `affilabs/plot_helpers.py` (same as sensorgram curves).

### Scatter plot (`binding_scatter_plot`)

- `pg.PlotWidget`, white background, context menu enabled
- X-axis label: `"Concentration (µM)"`
- Y-axis label: `"ΔSPR (RU)"`
- Grid: `showGrid(x=True, y=True, alpha=0.2)`
- Data points: `pg.ScatterPlotItem`, size=10, symbol='o', color matches selected channel
- Fit line: `pg.PlotDataItem`, dashed pen, same channel color, width=2
- Each dot has a tooltip showing cycle name + conc + ΔSPR value (`pg.ScatterPlotItem` with `hoverable=True`)

### Formula panel (`binding_formula_panel`)

`QFrame` with `QVBoxLayout`. Contains:

1. **Model name** — `QLabel`, bold 12px
2. **Formula** — `QLabel`, monospace 11px, shows symbolic form
3. **Fitted parameters** — `QLabel` per parameter, 11px
4. **R²** — `QLabel`, 12px, bold, green if ≥ 0.95, amber if 0.85–0.95, red if < 0.85
5. **Reference badge** — `QLabel`, 11px, grey italic: `ref: Ch D` or `ref: none`. Reads `cycle['delta_ref_ch']` from the first selected cycle with a valid delta. If cycles disagree on reference (mixed), shows `ref: mixed ⚠`.
6. **Kd line** — `QLabel`, 11px, italic, only shown for Langmuir fit
7. **Warning banner** — `QFrame` with amber background, only shown for Langmuir fit

#### Warning banner text (Langmuir only)

> ⚠ **Equilibrium estimate only.**
> Kd from endpoint ΔSPR assumes binding has reached equilibrium at the end of each injection.
> Verify with full kinetic fitting for publication-quality data.

---

## 4. Data Model

### Option A — Consume stored ΔSPR (chosen approach)

The binding plot is a **dumb consumer** of values already written by `_update_delta_spr_barchart`. It does not re-apply reference subtraction or re-read raw curve data. Whatever reference was active when the user placed their cursors is already baked into `delta_ch{n}`.

This means:
- No logic duplication between bar chart and binding plot
- If the user changes the reference after measuring, they must re-place the cursors to update the stored deltas — the binding plot will reflect the old values until then
- The formula panel shows `ref: {channel}` so the user knows what was applied

### Source data

Reads from `self._loaded_cycles_data` for each selected row in `cycle_data_table`:

| Field | Source | Notes |
|-------|--------|-------|
| Concentration | `cycle['concentration_value']` | Float, µM. Skipped if empty or non-numeric. |
| ΔSPR (Ch A–D) | `cycle['delta_ch1']` … `cycle['delta_ch4']` | Written by `_update_delta_spr_barchart`. Absent if cursors not yet placed. |
| Reference used | `cycle['delta_ref_ch']` | Written alongside delta values (see §4.1). `'None'` if no reference was active. |

### 4.1 Writing `delta_ref_ch` — change to `_update_delta_spr_barchart`

When `_update_delta_spr_barchart()` writes `delta_ch{n}` values, it also stores the reference channel that was active at that moment:

```python
# In _alignment_mixin._update_delta_spr_barchart(), after computing deltas:
ref_ch = self._get_effective_ref_channel(row_idx)   # returns int 0-3 or None
cycle['delta_ref_ch'] = f'Ch {chr(65 + ref_ch)}' if ref_ch is not None else 'None'
```

This is a one-line addition to an existing method. No new state variables required.

### 4.2 Channel button enable/disable

Before updating the plot, scan all selected cycles to determine which channels have at least one valid (concentration + delta) pair:

```python
valid_channels = set()
for row in selected_rows:
    cycle = _loaded_cycles_data[row]
    conc = _parse_conc(cycle.get('concentration_value', ''))
    if conc is None:
        continue
    for ch_idx in range(4):
        delta = cycle.get(f'delta_ch{ch_idx + 1}')
        if delta is not None:
            valid_channels.add(ch_idx)

for ch_idx, btn in enumerate(binding_ch_btns):
    btn.setEnabled(ch_idx in valid_channels)
```

If the currently selected channel becomes disabled, auto-select the lowest-index valid channel. If no channels are valid, show the appropriate empty state.

### 4.3 Selected channel index mapping

```python
# binding_ch_btns is a list of 4 QPushButtons indexed 0-3
ch_idx = next(i for i, b in enumerate(binding_ch_btns) if b.isChecked())
delta_key = f'delta_ch{ch_idx + 1}'
```

### Valid point criteria

A cycle contributes a data point if and only if:

1. `concentration_value` is present, non-empty, and parseable as float
2. `delta_ch{n}` for the selected channel is present and not None

Cycles failing either criterion are silently skipped. If fewer than 2 valid points remain, show an empty-state message instead of fitting.

### Empty states

| Condition | Message shown in plot area |
|-----------|---------------------------|
| No cycles selected | *"Select cycles in the table to generate a binding plot."* |
| No concentration values set | *"Set concentration values in the Conc. column to generate a binding plot."* |
| ΔSPR not measured | *"Place the ΔSPR cursors on each cycle first."* |
| Fewer than 2 valid points | *"Need at least 2 data points to fit. Select more cycles or fill concentration values."* |
| Langmuir fit failed (scipy exception) | *"1:1 fit did not converge. Try Linear, or check that concentration range spans the Kd."* |

All messages rendered as `pg.TextItem` centered in the plot, grey 12px italic.

---

## 5. Fitting Models

### 5.1 Linear

```python
import numpy as np

coeffs = np.polyfit(conc_array, dspr_array, deg=1)   # [m, b]
m, b = coeffs
y_fit = np.polyval(coeffs, x_line)

# R²
ss_res = np.sum((dspr_array - np.polyval(coeffs, conc_array)) ** 2)
ss_tot = np.sum((dspr_array - dspr_array.mean()) ** 2)
r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
```

**Formula panel output:**

```
Linear
y = mx + b
m = {m:.3f} RU/µM
b = {b:.2f} RU
R² = {r2:.3f}
```

### 5.2 1:1 Langmuir (Equilibrium)

```python
from scipy.optimize import curve_fit

def langmuir(c, Rmax, Kd):
    return Rmax * c / (Kd + c)

p0 = [max(dspr_array), np.median(conc_array)]   # initial guess
bounds = ([0, 0], [np.inf, np.inf])

popt, _ = curve_fit(langmuir, conc_array, dspr_array, p0=p0, bounds=bounds, maxfev=5000)
Rmax, Kd = popt

# R²
y_pred = langmuir(conc_array, *popt)
ss_res = np.sum((dspr_array - y_pred) ** 2)
ss_tot = np.sum((dspr_array - dspr_array.mean()) ** 2)
r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
```

**Formula panel output:**

```
1:1 Langmuir
y = Rmax·c / (Kd + c)
Rmax = {Rmax:.1f} RU
Kd   = {Kd:.3f} µM
R²   = {r2:.3f}

⚠ Equilibrium estimate only.
```

**Failure handling:** Wrap `curve_fit` in `try/except RuntimeError`. On failure, show the Langmuir-fit-failed empty state and do not crash.

---

## 6. State Variables

Initialised in `EditsTab.__init__` alongside existing state:

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| `_binding_fit_result` | `dict \| None` | `None` | Last successful fit: `{'model', 'params', 'r2', 'x_fit', 'y_fit'}` |

---

## 7. `_update_binding_plot()` — Full Algorithm

```
1. Guard: if Binding tab not active → return early (don't compute if invisible)

2. Collect selected rows from cycle_data_table

3. If no rows selected → show empty state "Select cycles"

4. Update binding_ch_btns enabled/disabled state (§4.2)

5. ch_idx = index of currently checked binding_ch_btn (§4.3)
   model   = binding_model_combo.currentText()

6. Build arrays:
   conc_list, dspr_list, labels_list, refs_seen = [], [], [], set()
   For each row:
     cycle = _loaded_cycles_data[row]
     conc = parse float(cycle.get('concentration_value', ''))  → skip if invalid
     dspr = cycle.get(f'delta_ch{ch_idx+1}')                  → skip if None
     conc_list.append(conc)
     dspr_list.append(dspr)
     labels_list.append(cycle.get('name', f'Cycle {row+1}'))
     refs_seen.add(cycle.get('delta_ref_ch', 'None'))

7. If len(conc_list) < 2 → show appropriate empty state

8. conc_array = np.array(conc_list)
   dspr_array = np.array(dspr_list)
   x_line = np.linspace(conc_array.min(), conc_array.max(), 200)
   ref_label = refs_seen.pop() if len(refs_seen) == 1 else 'mixed ⚠'

9. Fit:
   if model == 'Linear':
     run polyfit → (m, b, r2)
   elif model == '1:1 Langmuir':
     run curve_fit → (Rmax, Kd, r2), catch RuntimeError

10. Update scatter plot:
    binding_scatter_plot.clear()
    Add ScatterPlotItem(conc_array, dspr_array)
    Add PlotDataItem(x_line, y_fit, pen=dashed)

11. Update formula panel labels including ref_label

12. Store result in _binding_fit_result
```

---

## 8. Trigger Points

| Event | Action |
|-------|--------|
| `bottom_tab_widget.currentChanged` → index == 1 | Call `_update_binding_plot()` |
| `cycle_data_table.itemSelectionChanged` | If binding tab active: call `_update_binding_plot()` |
| `binding_ch_btns[i].clicked` (any of 4) | Call `_update_binding_plot()` |
| `binding_model_combo.currentTextChanged` | Call `_update_binding_plot()` |
| `_update_delta_spr_barchart()` completes | If binding tab active: call `_update_binding_plot()` (cursor moves instantly refresh the plot) |

---

## 9. Export

The binding plot result is included in the Excel export when present.

### New Excel sheet: `"Binding Plot"`

| Column | Content |
|--------|---------|
| `Cycle` | Cycle name |
| `Concentration_uM` | Concentration value |
| `Delta_SPR_RU` | ΔSPR for the selected channel |
| `Channel` | Selected channel letter (A/B/C/D) |
| `Fit_Model` | "Linear" or "1:1 Langmuir" |
| `Fit_R2` | R² value |
| `Fit_Params` | JSON string of fit parameters |

### Chart

An XY scatter chart is auto-generated on the `"Binding Plot"` sheet using `openpyxl`:
- Series 1: raw data points (markers only, no line)
- Series 2: fit line (line only, no markers)
- Title: `"Binding Plot — Ch {X} — {Model}"`
- X-axis: `"Concentration (µM)"`
- Y-axis: `"ΔSPR (RU)"`

The `_binding_fit_result` dict is passed to `ExcelExporter` via `edits_tab.get_state_snapshot()`.

---

## 10. Implementation Plan

### Files to create

| File | Purpose |
|------|---------|
| `affilabs/tabs/edits/_binding_plot_mixin.py` | All fitting logic, `_update_binding_plot()`, Rmax calculator |
| `affilabs/utils/live_binding_stats.py` | Pure computation: pre/post baseline, slope, anchor, classification functions, `NM_TO_RU = 355.0` |

### Files to modify

| File | Change |
|------|--------|
| `affilabs/tabs/edits/edits_tab.py` | Add `BindingPlotMixin`; init `_binding_fit_result = None`, `_ligand_mw = None`, `_analyte_mw = None`, `_immob_delta_spr_ru = None` |
| `affilabs/tabs/edits/_ui_builders.py` | Wrap bar chart in `QTabWidget`; add `_create_binding_panel()` with Rmax calculator section; wire trigger signals |
| `affilabs/tabs/edits/_alignment_mixin.py` | After `_update_delta_spr_barchart` completes, call `_update_binding_plot()` if tab active; pre-fill `delta_ch{n}` from `_injection_stats` if cursor not yet placed |
| `affilabs/tabs/edits/_export_mixin.py` | Add "Binding Plot" sheet + Rmax summary block + chart to Excel export |
| `affilabs/utils/excel_chart_builder.py` | Add `add_binding_plot_chart()` helper |
| `mixins/_pump_mixin.py` | In `_place_injection_flag()`: compute pre-baseline, schedule t+15 slope freeze and t+20 anchor freeze via `QTimer.singleShot`; store in `_injection_stats` |
| `mixins/_cycle_mixin.py` | In cycle-end handler: compute post-baseline, finalise `delta_spr_ru`, call `overlay.show_cycle_result()` |
| `affilabs/widgets/cycle_status_overlay.py` | Add `update_binding_signal(response_label, response_color, slope_label, slope_color)` for row 2 during contact; add `show_cycle_result(label, color)` for end-of-cycle display |

### Class composition after

```python
class EditsTab(DataMixin, ExportMixin, UIBuildersMixin, AlignmentMixin, TableMixin, BindingPlotMixin):
```

---

## 11. Auto-ΔSPR from Live Binding Stats

### Source

When the live binding stats system is active (see `affilabs/utils/live_binding_stats.py`), each completed binding or immobilization cycle writes a `delta_spr_ru` value per channel into `_injection_stats`. This is computed as:

```
delta_spr_ru = (post_baseline_nm − pre_baseline_nm) × 355.0
```

Where:
- `pre_baseline_nm` = mean wavelength of last 30s **before** injection flag
- `post_baseline_nm` = mean wavelength of last 30s **before cycle ends**

### Pre-fill behaviour

When a cycle is loaded into the Edits tab, if `_injection_stats` contains a `delta_spr_ru` entry for that cycle number and channel, it is written directly into `delta_ch{n}` **as the default value** — no cursor placement required.

The user can still override by placing cursors manually. The cursor-derived value takes precedence once set. The auto-value is shown with a subtle indicator (e.g. grey italic) until overridden.

This means the binding plot can populate automatically after recording ends, without the user needing to place any cursors.

### Key fields written per cycle per channel

```python
_injection_stats[(cycle_num, channel)] = {
    'flag_time':        float,   # injection flag display time (seconds)
    'pre_baseline_nm':  float,   # mean of 30s before flag
    'anchor_nm':        float,   # mean of first 20s after flag (frozen at t+20)
    'slope_nm_per_s':   float,   # polyfit over first 15s (frozen at t+15)
    'post_baseline_nm': float,   # mean of last 30s of cycle
    'delta_spr_nm':     float,   # post_baseline_nm − pre_baseline_nm
    'delta_spr_ru':     float,   # delta_spr_nm × 355.0
    'cycle_num':        int,
    'cycle_type':       str,     # 'Binding' | 'Immobilization' | etc.
}
```

`NM_TO_RU = 355.0` is defined as a module-level constant in `live_binding_stats.py`.

---

## 12. Rmax Calculator

### Purpose

After immobilization, the user can calculate the **theoretical Rmax** — the maximum binding signal expected at saturating analyte concentration, assuming 1:1 stoichiometry and 100% surface activity. This guides experiment design: if Rmax is too low (< 50 RU), the surface density is insufficient for reliable kinetics.

### Formula

```
Theoretical Rmax (RU) = (Analyte MW / Ligand MW) × Immobilization ΔSPR (RU)
```

Where immobilization ΔSPR = `delta_spr_ru` from the Immobilization cycle in `_injection_stats`.

### Layout

Collapsible panel below the formula panel in the Binding tab, or as a third tab. Contains:

```
┌─ Rmax Calculator ──────────────────────────────────┐
│  Ligand MW:     [        ] Da                       │
│  Analyte MW:    [        ] Da                       │
│  Immob ΔSPR:    1240 RU   (auto from cycle data)   │
│  ─────────────────────────────────────────────────  │
│  Theoretical Rmax:   442 RU                         │
│  Empirical Rmax:     387 RU   (from Langmuir fit)  │
│  Surface activity:    87.6%   ● High activity       │
└────────────────────────────────────────────────────┘
```

### Inputs

| Field | Type | Source |
|-------|------|--------|
| Ligand MW | `QDoubleSpinBox`, Da | User types; persisted to `user_profiles.json` |
| Analyte MW | `QDoubleSpinBox`, Da | User types; persisted to `user_profiles.json` |
| Immob ΔSPR | Read-only `QLabel` | Auto-filled from `_injection_stats` where `cycle_type == 'Immobilization'`; editable fallback if no immobilization cycle recorded |

### Outputs

**Theoretical Rmax** — computed live as MW ratio × immob ΔSPR. Shown as `QLabel`, updates on any input change.

**Empirical Rmax** — sourced from `_binding_fit_result['langmuir_rmax']` if a Langmuir fit has been run. Shown only if available. Labelled `(from Langmuir fit)`.

**Surface activity** — shown only if both theoretical and empirical Rmax are available:

```
Surface activity (%) = (Empirical Rmax / Theoretical Rmax) × 100
```

| Reading | Condition | Label | Color |
|---------|-----------|-------|-------|
| Excellent | > 80% | `● High activity` | Green |
| Good | 50–80% | `● Good` | Green |
| Low | 20–50% | `◐ Low activity` | Amber |
| Poor | < 20% | `○ Poor — check surface` | Red |

### State variables added to EditsTab

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| `_ligand_mw` | `float \| None` | `None` | Ligand molecular weight (Da) |
| `_analyte_mw` | `float \| None` | `None` | Analyte molecular weight (Da) |
| `_immob_delta_spr_ru` | `float \| None` | `None` | Auto-filled from immobilization cycle |

### Export

The Rmax calculator values are included in the Excel export `"Binding Plot"` sheet as a summary block below the data table:

```
Ligand MW:           48000 Da
Analyte MW:          14200 Da
Immob ΔSPR:          1240 RU
Theoretical Rmax:    442 RU
Empirical Rmax:      387 RU
Surface activity:    87.6%
```

---

## 13. Out of Scope (v2.0.5)

| Feature | Rationale |
|---------|-----------|
| Kinetic fitting (kon/koff) | Requires full sensorgram fitting infrastructure — separate project |
| Hill equation | Cooperativity not relevant for SPR |
| Multi-site Langmuir | Too complex for on-instrument QC |
| Saving fit result per-session | State is reconstructed from `_loaded_cycles_data` on demand; no persistence needed |
| Confidence intervals on fit | scipy provides them but display adds complexity — post-v2.0.5 |

---

## 14. Known Design Constraints

1. **Concentration unit is µM throughout** — no unit selector. Users must enter µM in the Conc. column. This matches the most common SPR experimental unit and avoids unit-conversion bugs.

2. **Single channel at a time** — the binding plot shows one channel's ΔSPR vs concentration. Users switch channels via the combo. Multi-channel overlay would require a legend and color-coding scheme that adds complexity without proportional value for this use case.

3. **Equilibrium assumption for Langmuir** — the Langmuir fit uses endpoint ΔSPR, not a kinetic model. The warning banner is mandatory and non-dismissible for this reason.

4. **Concentration must be in the Conc. column** — the column is hidden by default (v2.0.5 quick win). The binding tab empty-state message tells users where to find it. No automatic detection of concentration from cycle names.
