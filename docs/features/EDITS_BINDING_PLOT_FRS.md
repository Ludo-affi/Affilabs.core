# Edits Tab — Binding Plot FRS

> **Source:** `affilabs/tabs/edits/_binding_plot_mixin.py`
> **UI location:** Tab 1 of the bottom-right `QTabWidget` in EditsTab

---

## §1. Overview

The Binding Plot tab provides concentration-response analysis and kinetics fitting directly from Edits tab data. It is the second tab in the bottom-right panel (Tab 0 = ΔSPR bar chart, Tab 1 = Binding).

---

## §2. Layout

```
Binding tab (QWidget)
└─ QVBoxLayout
     ├─ header row (QHBoxLayout)
     │    ├─ "Binding Analysis" title
     │    ├─ Channel selector buttons (A / B / C / D, exclusive)
     │    └─ Concentration unit combo (nM / µM / pM)
     ├─ binding_scatter_plot (pg.PlotWidget)
     ├─ fit info panel (QHBoxLayout)
     │    ├─ binding_model_lbl     "Model: —"
     │    ├─ binding_formula_lbl   formula string
     │    ├─ binding_params_lbl    fit parameter values
     │    ├─ binding_r2_lbl        R² value
     │    ├─ binding_ref_lbl       reference channel used
     │    └─ binding_kd_lbl        Kd (shown only for Langmuir/kinetics)
     ├─ binding_warn_frame         (Langmuir warning, hidden by default)
     └─ Rmax calculator panel
          ├─ MW inputs (ligand MW, analyte MW spinboxes)
          ├─ binding_immob_lbl     Immobilization ΔSPR (auto-filled)
          ├─ binding_rmax_theor_lbl Theoretical Rmax
          ├─ binding_rmax_emp_lbl  Empirical Rmax (Langmuir only)
          └─ binding_surface_act_lbl Surface activity %
```

---

## §3. Fit Models

Three models selectable from the fit model dropdown / toolbar:

### 3.1 Linear

`y = m·x + b` (concentration vs ΔSPR)

**Output:**
- slope `m` (RU / concentration_unit)
- intercept `b` (RU)
- R²

### 3.2 1:1 Langmuir

`y = Rmax · c / (Kd + c)`

Fitted via `scipy.optimize.curve_fit`.

**Output:**
- `Rmax` (RU) — maximum response
- `Kd` (in selected concentration unit: nM/µM/pM)
- R²

`binding_warn_frame` shown if fit quality is poor (R² < 0.9 or curve_fit convergence warning).

### 3.3 Kinetics (ka/kd)

Extracts raw sensorgram per cycle. Fits association phase:

```
R(t) = Rmax · (1 − exp(−kobs · t))
```

Linear regression: `kobs = ka·[C] + kd`

**Output:**
- `ka` (conc_unit⁻¹·s⁻¹) — association rate constant
- `kd` (s⁻¹) — dissociation rate constant
- `KD = kd / ka` (in concentration unit)
- Requires `data_collector.raw_data_rows` (live session) or embedded raw data (Excel)

---

## §4. Concentration Units

`binding_conc_unit_combo` (QComboBox): **nM** (default) / µM / pM

Scaling applied to all fit inputs and display:
- nM: factor 1.0
- µM: factor 1e-3
- pM: factor 1e3

Axis label: `"Concentration ({unit})"` updates on combo change.

---

## §5. Channel Selection

`binding_ch_btns` — 4 exclusive-select QPushButtons (A / B / C / D).

Selecting a channel:
- Replots scatter with data for that channel only
- Re-runs last fit model for the new channel
- Updates all fit labels

---

## §6. Data Source

`_build_binding_data(channel)` — collects ΔSPR vs concentration pairs:

1. For each visible row in `cycle_data_table`:
   - Skip rows with no concentration value
   - Get ΔSPR for the selected channel from `_parsed_delta_spr[row]` or `delta_ch{1-4}` key
2. Returns `(concentrations, delta_spr_values, cycle_labels)`

If fewer than 2 data points: shows "Not enough data" message, skips fit.

---

## §7. Rmax Calculator

`_update_rmax_calculator()` — auto-runs after each Langmuir fit:

| Field | Source |
|-------|--------|
| `binding_immob_lbl` | Auto-filled from `_injection_stats['Immobilisation'].delta_spr_ru`; 0 if not found |
| `binding_rmax_theor_lbl` | `(MW_analyte / MW_ligand) × Immob_ΔSPR` |
| `binding_rmax_emp_lbl` | Langmuir fit Rmax (shown only for 1:1 model) |
| `binding_surface_act_lbl` | `(Empirical / Theoretical) × 100%` |

**Surface activity thresholds:**
- > 80%: High (green)
- 50–80%: Good (blue)
- 20–50%: Low (orange)
- < 20%: Poor (red)

MW inputs: `QDoubleSpinBox` for ligand MW and analyte MW (kDa).

---

## §8. Fit Result Cache

`_binding_fit_result: dict` — preserved between channel changes and tab switches:

```python
{
    'model': str,          # 'linear' | 'langmuir' | 'kinetics'
    'channel': str,        # 'A'/'B'/'C'/'D'
    'r2': float,
    'ref': str | None,     # reference channel subtracted
    'conc': list[float],
    'dspr': list[float],
    'labels': list[str],
    'x_fit': np.ndarray,   # fitted curve x values
    'y_fit': np.ndarray,   # fitted curve y values
    'params': str,         # display string
    # Langmuir only:
    'Kd_nM': float,
    'Rmax_RU': float,
    # Kinetics only:
    'ka': float,
    'kd': float,
    'KD': float,
}
```

---

## §9. Key Gotchas

1. **Kinetics requires raw sensorgram data** — only available during live session or if raw data was embedded in the Excel export. Falls back gracefully with "Raw data not available" message.
2. **Langmuir Kd display** units follow `binding_conc_unit_combo` selection — verify unit consistency before reporting.
3. **Immobilization cycle lookup**: searches `_injection_stats` dict for key containing `'Immobilisation'` (British spelling). Missing or zero immob ΔSPR makes theoretical Rmax 0 — not an error.
4. **Binding tab is Tab index 1** — Tab 0 is ΔSPR bar chart. Both share the same bottom-right `QTabWidget`.

---

**Last Updated:** February 24, 2026
**Codebase Version:** Affilabs.core v2.0.5 beta
