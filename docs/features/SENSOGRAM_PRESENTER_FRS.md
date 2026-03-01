# Sensogram Presenter — Functional Requirements Specification

**Source:** `affilabs/presenters/sensogram_presenter.py` (337 lines)
**Version:** 2.0.5.1 | **Date:** 2026-03-01

---

## 1. Purpose

Pure presenter that manages the two main sensorgram graphs: the **full timeline** and the **cycle-of-interest** view. Reads/writes pyqtgraph widgets on `AffilabsMainWindow`. No QObject, no signals — presentation logic only.

---

## 2. Class

**`SensogramPresenter`**

### Constructor
```python
def __init__(self, main_window: "AffilabsMainWindow")
```
Stores `self.window` reference and `_updating_cursor_inputs` guard flag.

---

## 3. Methods

### 3.1 Data Updates

| Method | Signature | Purpose |
|--------|-----------|---------|
| `update_timeline_data` | `(channel_data: dict[int, np.ndarray], time_array: np.ndarray)` | Updates `full_timeline_graph.curves[ch_idx]` — skips first point, shifts to t=0 |
| `set_live_data_enabled` | `(enabled: bool)` | Sets `window.live_data_enabled` flag |

### 3.2 Cursor & Duration

| Method | Signature | Purpose |
|--------|-----------|---------|
| `update_cursor_positions` | `(start_time: float | None, stop_time: float | None)` | Sets `start_cursor` / `stop_cursor` on timeline graph |
| `update_cursor_inputs` | `()` | Syncs spinboxes (`start_time_input`, `stop_time_input`) to cursor positions |
| `update_duration_label` | `()` | Calculates `abs(stop - start)` → updates `duration_label` text |

### 3.3 Channel Visibility

| Method | Signature | Purpose |
|--------|-----------|---------|
| `toggle_channel_visibility` | `(channel: str, visible: bool)` | Shows/hides channel curve on both timeline and cycle-of-interest graphs |

### 3.4 Flag Markers

| Method | Signature | Purpose |
|--------|-----------|---------|
| `add_flag_marker` | `(time: float, label: str, color: str = "#FF3B30")` | Adds `InfiniteLine` + `TextItem` to timeline graph; stores in `flag_markers` list |
| `clear_all_flags` | `()` | Removes all flag markers from timeline graph |

### 3.5 Curve Highlighting

| Method | Signature | Purpose |
|--------|-----------|---------|
| `highlight_selected_curve` | `(channel_idx: int)` | Applies `selected_pen` to target curve, `original_pen` to others; `-1` resets all |

### 3.6 Clear

| Method | Signature | Purpose |
|--------|-----------|---------|
| `clear_all_graph_data` | `()` | Clears all curves on both graphs, resets cursors to 0 |
| `clear_all_graphs` | `()` | Clears visual curves (doesn't affect data buffers) |

---

## 4. Widget Dependencies

Accesses these widgets on `main_window`:

| Widget | Type | Purpose |
|--------|------|---------|
| `full_timeline_graph` | pyqtgraph `PlotWidget` | Full experiment timeline |
| `cycle_of_interest_graph` | pyqtgraph `PlotWidget` | Zoomed cycle view |
| `start_time_input` | `QDoubleSpinBox` | Start cursor position input |
| `stop_time_input` | `QDoubleSpinBox` | Stop cursor position input |
| `duration_label` | `QLabel` | Cycle duration display |

---

## 5. Channel Mapping

```python
{"A": 0, "B": 1, "C": 2, "D": 3}
```

---

## 6. Key Patterns

- **No signals/slots** — pure presentation, no QObject inheritance
- **Guard flag** `_updating_cursor_inputs` prevents re-entrant cursor updates
- **Flag markers** use `pyqtgraph.InfiniteLine` (vertical) + `pyqtgraph.TextItem` (label)
- **Time shift**: timeline data starts at t=0 (first point skipped, array shifted)
