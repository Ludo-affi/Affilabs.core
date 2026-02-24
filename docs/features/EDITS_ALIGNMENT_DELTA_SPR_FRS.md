# Edits Tab — Alignment, Delta SPR & Graph Interaction FRS

> **Source files**
> - `affilabs/tabs/edits/_alignment_mixin.py` — event filter, delta SPR, reference channel
> - `affilabs/ui_mixins/_edits_cycle_mixin.py` — cycle selection, time labels, graph population

---

## §1. Overview

The "alignment" subsystem handles:
1. **Keyboard navigation** — Left/Right arrows step through cycle table rows
2. **Reference channel** — Ctrl+click on a channel button sets it as the subtraction reference
3. **Delta SPR bar chart** — Two draggable cursors on `edits_primary_graph`; bar chart shows ΔSPR per channel between them
4. **InteractiveSPRLegend** — Floating legend on the primary graph showing live ΔSPR values
5. **Start/end time labels** — Shown inline in the graph header when a cycle is selected
6. **Shift/alignment state** — Per-cycle time offset and channel selector (stubs present, shift not actively applied to graph data)

---

## §2. Event Filter

`_EditsEventFilter(QObject)` — proxy shim because EditsTab is not a QObject.

Installed on `edits_primary_graph` and each channel button. Delegates to `EditsTab.eventFilter(obj, event)`.

`eventFilter(obj, event)` handles:

| Object | Event | Action |
|--------|-------|--------|
| `edits_primary_graph` | `KeyPress: Left` | `_step_cycle_selection(-1)` |
| `edits_primary_graph` | `KeyPress: Right` | `_step_cycle_selection(+1)` |
| `edits_primary_graph` | `Resize` | `_position_edits_legend()` |
| Channel button (A/B/C/D) | `MouseButton + Ctrl` | `_on_edits_channel_ref_ctrl_click(ch)` |

Returns `False` for all handled events (not `super().eventFilter()`) — EditsTab is not a QObject.

---

## §3. Keyboard Navigation

`_step_cycle_selection(delta)`:
- Gets current selected row from `cycle_data_table`
- Computes `new_row = current_row + delta`, clamped to `[0, rowCount-1]`
- Skips hidden rows (filter applied)
- Calls `cycle_data_table.selectRow(new_row)`
- `itemSelectionChanged` fires → graph updates automatically

---

## §4. Reference Channel

`_edits_ref_channel: str | None` — currently selected reference (None, 'A', 'B', 'C', or 'D').

### Setting Reference

**Ctrl+click** on channel toggle button → `_on_edits_channel_ref_ctrl_click(ch)`:
```
If ch == _edits_ref_channel: clear reference (set to None)
Else: set _edits_ref_channel = ch
```

After change:
1. Updates button styling — reference channel button gets dotted border
2. Updates `alignment_ref_combo` (stub) to match
3. Triggers graph redraw: replays `_on_cycle_selected_in_table()`

### Visual Indicator

Reference channel button style (when active):
```css
QPushButton {
    border: 2px dashed {color};
    background: {color}22;   /* 13% opacity fill */
}
```

### Application

Reference subtraction applied during `_on_cycle_selected_in_table()` — reference channel wavelength array subtracted from each other channel before plotting.

---

## §5. Alignment State (Per-Cycle)

`_cycle_alignment: dict[int, dict]` — keyed by table row index:

```python
{ row_idx: {'channel': str, 'shift': float} }
# channel: "All" | "A" | "B" | "C" | "D"
# shift: time offset in seconds (stub — not applied to graph data currently)
```

### _AlignChannelProxy

Thin wrapper over the channel toggle buttons exposing the same API as QComboBox:
- `.currentText()` — active channel name
- `.setCurrentText(text)` — syncs button visual state
- `.blockSignals(bool)` — no-op compatibility shim
- `currentTextChanged` signal

**Critical**: `_on_cycle_selected_in_table()` calls `.blockSignals()` and `.setCurrentText()` on this proxy. If these methods are absent, the entire function silently fails (wrapped in try/except) and the graph stays blank.

---

## §6. Delta SPR Bar Chart

`_update_delta_spr_barchart()` — called by:
- Cursor `sigPositionChanged` (live drag)
- `_on_cycle_selected_in_table()` after graph data plotted

### Logic

1. Get `start_pos = delta_spr_start_cursor.value()`, `stop_pos = delta_spr_stop_cursor.value()`
2. For each channel A/B/C/D:
   - Slice wavelength data between start and stop positions
   - `delta = (mean_stop - mean_start) × 355`  (nm × 355 = RU)
3. Update bars: `delta_spr_bars[i].setOpts(height=delta)`
4. Update text labels: `delta_spr_labels[i].setText(f"{delta:.1f}")`
5. Call `legend.update_values({'A': delta_a, ...})`
6. Call `legend.setVisible(True)`

### Lock Button

`delta_spr_lock_btn` (checkable) — "🔓 Unlock" / "🔒 Locked":
- **Locked**: cursor distance fixed to `contact_time × 1.1`; snap to `[start, start + locked_distance]`
- **Unlocked**: cursors move freely

`_toggle_delta_spr_lock(checked)` — computes `_delta_spr_lock_distance` from selected cycle.
`_reset_delta_spr_lock()` — called on every table selection change; always unlocks.

---

## §7. InteractiveSPRLegend

Floating overlay on `edits_primary_graph`.

### Construction & Visibility

```python
self._edits_legend = InteractiveSPRLegend(edits_primary_graph)
self._edits_legend.setVisible(False)      # hidden at construction
QTimer.singleShot(200, self._position_edits_legend)
```

`QTimer.singleShot(200ms)` required — layout must settle before coordinates are valid.

- Made **visible** in `_on_cycle_selected_in_table()` after `autoRange()` is called
- Stays visible after first show; never explicitly hidden again

### Positioning

`_position_edits_legend()`:
```python
vr = self.edits_primary_graph.viewRect()
legend.setPos(vr.right() - legend.boundingRect().width() - 10, vr.top() + 10)
```

Called on: initial 200ms delay, every resize event, after `autoRange()`.

### Updates

`legend.update_values({'A': float, ...})` — from `_update_delta_spr_barchart()`
`legend.update_colors(hex_colors_dict)` — from `update_barchart_colors()` on colorblind toggle

---

## §8. Start/End Time Labels

Cycle timing shown inline in the Active Selection graph header (removed from alignment panel Feb 24 2026):

```python
self.alignment_start_time = QLabel("")   # "▶ 1140 s"
self.alignment_end_time   = QLabel("")   # "◼ 1440 s"
```

Populated by `_on_cycle_selected_in_table()`:

```python
# Single cycle selected:
self.alignment_start_time.setText(f"▶ {start:.0f} s")
self.alignment_end_time.setText(f"◼ {end:.0f} s")
self.alignment_start_time.setVisible(True)
self.alignment_end_time.setVisible(True)

# Multi-select or no selection:
self.alignment_start_time.setVisible(False)
self.alignment_end_time.setVisible(False)
```

---

## §9. Color Update

`update_barchart_colors(colorblind_enabled, hex_colors)` — synchronizes all color-coded elements:

1. `delta_spr_bars[i].setOpts(brush=color)` — bar fills
2. `edits_graph_curves[ch].setPen(color)` — graph curves
3. `edits_graph_curve_labels[ch].setColor(color)` — channel-end labels
4. `_edits_legend.update_colors(hex_colors)` — legend text
5. Channel button stylesheets via `get_channel_button_style(hex_color)`

---

## §10. Alignment Panel Removal

The visible alignment panel was removed February 24 2026. Functions it provided:
- **Start/end time** → moved to graph header labels (§8)
- **Reference subtraction** → Ctrl+click on channel button (§4)
- **Channel filter** → `_AlignChannelProxy` button group (§5)
- **Flags display** → removed (flags tracking deprioritized)
- **Time shift** → stub only; not wired to graph rendering

All alignment widgets remain as invisible stubs (`_create_alignment_stubs()`) so mixin code calling `.show()`, `.hide()`, `.addItems()`, `.setCurrentText()` does not crash. See EDITS_UI_BUILDERS_FRS.md §8.

---

**Last Updated:** February 24, 2026
**Codebase Version:** Affilabs.core v2.0.5 beta
