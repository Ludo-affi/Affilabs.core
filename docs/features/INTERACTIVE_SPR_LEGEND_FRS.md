# Interactive SPR Legend — FRS

**Document Status:** 🟢 Implemented
**Last Updated:** February 28, 2026
**Source files:**
- `affilabs/widgets/interactive_spr_legend.py` — widget
- `affilabs/affilabs_core_ui.py` — `_on_timing_channel_selected`, `_on_channel_nudge`, `reset_channel_time_offsets`
- `affilabs/utils/ui_update_helpers.py` — `update_cycle_of_interest_graph` (offset applied at `curve.setData`)

---

## 1. Purpose

The Interactive SPR Legend is a floating, draggable overlay on the Active Cycle graph in the Live tab. It shows live Δ SPR values per channel and allows the user to:

1. **Select a channel** — highlights that channel's curve (thicker line) on both the Active Cycle and Live Sensorgram graphs.
2. **Nudge a channel's curve left or right** — shifts the X-axis start position of one channel's curve in the Active Cycle view, correcting for inter-channel injection timing skew (P4SPR manual injection scenario).

The nudge is **display-only** — it does not modify recorded data, flag times, or session files. It is a visual alignment aid for the user to compare injection responses across channels in real time.

---

## 2. Widget Layout

Horizontal pill, white background with drop-shadow:

```
⠿  Δ  ▾  │  +0  │  +0  │  +0  │  +0
          A      B      C      D
```

- **⠿** — drag handle (`SizeAllCursor`). Click-drag to reposition anywhere within the parent graph.
- **Δ** — title label (also a secondary drag target).
- **▾ / ▸** — collapse/expand toggle. Collapsed = only drag handle + title visible.
- **Channel cells** (A–D) — clickable. Selected channel highlighted with blue background (`rgba(0,122,255,0.10)`).
- **Value** — Δ SPR in nm, integers only (e.g. `+12`, `-3`, `0`). Color matches `ACTIVE_GRAPH_COLORS[ch]`.

---

## 3. Channel Selection

Clicking a channel cell:
1. Sets that channel as `selected_channel`.
2. Updates cell background highlight.
3. Emits `channel_timing_selected(channel_lower)`.
4. Handler in `affilabs_core_ui._on_timing_channel_selected`:
   - Stores `selected_channel_for_timing` and `selected_channel_letter`.
   - Updates curve pen width: selected = 4px, others = 2px.
   - Syncs `app._selected_flag_channel` (used by FlagManager for software flag placement).

---

## 4. Channel Nudge (Time Offset)

### 4.1 Interaction

1. User clicks a channel cell to select it (cell highlights blue, curve thickens).
2. User presses **Left** or **Right** arrow key while the legend has focus.
   - Plain arrow: ±1 s per press.
   - **Shift + arrow**: ±5 s per press.
3. The selected channel's curve shifts left (earlier) or right (later) on the Active Cycle X-axis.

### 4.2 Signal

`InteractiveSPRLegend.channel_nudge_requested = Signal(str, float)`

Payload: `(channel_lower, delta_seconds)` — e.g. `('b', -1.0)`.

### 4.3 State

`affilabs_core_ui._channel_time_offsets: dict[str, float]` — one entry per channel (`'a'`–`'d'`), initialised to `0.0` on first use. Accumulates with each key press.

Handler: `_on_channel_nudge(channel, delta_seconds)` adds `delta` to `_channel_time_offsets[ch]`.

### 4.4 Rendering

In `ui_update_helpers.update_cycle_of_interest_graph`, after computing `display_cycle_time`:

```python
nudge = _channel_time_offsets.get(ch_letter.lower(), 0.0)
if nudge != 0.0:
    display_cycle_time = np.asarray(display_cycle_time) + nudge
curve.setData(display_cycle_time, display_delta_spr)
```

The Y-axis (`display_delta_spr`) is never modified — only the X-axis shifts.

### 4.5 Reset Conditions

Offsets are reset to zero when:

| Trigger | Where |
|---|---|
| Cursor region moves significantly (>5% of duration) | `ui_update_helpers.py` — `cycle_changed = True` block calls `main_window.reset_channel_time_offsets()` |
| Acquisition stopped / new experiment started | Not yet explicitly wired — reset occurs naturally when new cycle region is selected |

`reset_channel_time_offsets()` sets all four channel offsets to `0.0`.

### 4.6 Constraints

- Nudge is **display only** — recorded data, SPR flag timestamps, and exported files are unaffected.
- No minimum/maximum bound is enforced on the offset. The user can shift a channel arbitrarily far; the curve simply exits the visible range if nudged too far.
- No visual indicator showing the current offset value (out of scope for this iteration).

---

## 5. Minimize / Expand

Clicking ▾ hides all channel cells and separator lines (the `_content_widgets` list). The widget shrinks to show only the drag handle + title + toggle button. Clicking ▸ restores full width.

State: `_collapsed: bool`. Toggled by `_toggle_collapse()`.

---

## 6. Drag Repositioning

The legend floats inside the `PlotWidget` parent at fixed pixel position. Drag sources:
- `_DragHandle` (⠿) — primary
- `_title_label` — secondary (same drag logic via `_do_drag`)

After a user drag, `_user_moved = True` suppresses auto-repositioning by the graph's resize handler.

Initial position: set by `_position_active_cycle_legend()` in `affilabs_core_ui.py`, called 200 ms after widget creation.

---

## 7. Colorblind Mode

`update_colors()` re-reads `settings.ACTIVE_GRAPH_COLORS` and applies updated CSS color to value labels. Called by the colorblind mode toggle handler in `affilabs_core_ui.py`.

---

## 8. Signals Summary

| Signal | Payload | When emitted |
|---|---|---|
| `channel_timing_selected` | `str` (channel lower) | On cell click |
| `channel_visibility_changed` | `(str, bool)` | Backward compat — not actively used |
| `channel_nudge_requested` | `(str, float)` | Left/Right arrow when a channel is selected |

---

## 9. Use Case: P4SPR Inter-Channel Injection Skew

In P4SPR manual injection, the user pipettes sample into channels A → B → C → D sequentially. This introduces up to ~15 s of timing skew between channels. On the Active Cycle graph all channels start at t=0 (the start cursor position), so channel D's signal appears delayed compared to A.

The nudge feature lets the user right-shift A, B, C to match D's response onset, making multi-channel comparison straightforward without modifying any recorded data.

---

## 10. Out of Scope

- Persisting nudge offsets across sessions.
- Displaying current offset value per channel in the legend cell.
- Applying nudge to the Live Sensorgram (full timeline graph) — Active Cycle graph only.
- Nudge in Edits tab — handled separately by `CYCLE_BOUNDARY_ADJUST_FRS.md`.
