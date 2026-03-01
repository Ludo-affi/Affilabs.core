# Cycle Boundary Adjust — FRS

**Document Status:** 🟡 Implementation Ready  
**Last Updated:** February 28, 2026  
**Source files:**
- `affilabs/tabs/edits/_ui_builders.py` — `_create_active_selection()`: wrap content in QTabWidget, add Adjust tab
- `affilabs/tabs/edits/_adjust_mixin.py` — new mixin: all Adjust tab logic
- `affilabs/domain/cycle.py` — add `time_correction_s: float` field to cycle domain model (or equivalent storage)
- `affilabs/ui_mixins/_edits_cycle_mixin.py` — propagate correction when rendering cycle in Edits

---

## 1. Purpose

Users sometimes mistime a manual injection — they inject late, or start the cycle too early, or the cycle queue cut off before they were done. The raw data is fine. The cycle boundary is wrong.

This feature lets the user redefine the cycle's time window post-hoc — by dragging handles on a padded view of the raw session data. No raw data is modified. The correction is a metadata offset stored on the cycle object.

**Overlapping cycles are explicitly allowed.** If the adjusted windows of two cycles share data, that is fine — the session file always contains the full continuous recording; each cycle is just a view into it.

---

## 2. What Changes in the UI

### 2.1 "Selected Cycle" panel — tabbed

`_create_active_selection()` currently returns a plain `QFrame` with a title bar + pyqtgraph `PlotWidget`. It becomes a `QTabWidget` with two tabs:

```
┌─ Selected Cycle ────────────────────────────────────────────────┐
│  [ Cycle ]  [ Adjust ]                          🔒 Unlock  ↺   │
│─────────────────────────────────────────────────────────────────│
│  [graph content — switches based on active tab]                 │
└─────────────────────────────────────────────────────────────────┘
```

The title bar buttons (Unlock, Reset) remain at the top and apply to the **Cycle** tab only. The Adjust tab has its own control strip.

The **Adjust** tab is disabled (greyed) when no cycle is selected. It becomes enabled as soon as a cycle is selected in the table.

---

## 3. Cycle Tab (existing — no change)

Displays the cycle within its defined boundaries exactly as today. No modifications from this FRS.

---

## 4. Adjust Tab

### 4.1 Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ [◀ +] ───────────────────────────────────────────────── [+ ▶]  │  ← expand strip
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   context    │░░░░░░ shaded cycle window ░░░░░░│   context      │
│   (dimmed)   ▲                               ▲  (dimmed)       │
│              drag                           drag                │
│              handle                         handle              │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Start offset: −12.0 s    Duration: 647.0 s    [Reset] [Apply] │  ← control strip
└─────────────────────────────────────────────────────────────────┘
```

**Three zones:**
1. **Expand strip** — two small `[◀ +]` / `[+ ▶]` buttons at the far left and right edges of the graph, overlaid on the plot (not in a separate row). Each press expands the visible context by 10% of the cycle duration on that side.
2. **Graph** — pyqtgraph `PlotWidget` showing the padded data window with drag handles and shaded region.
3. **Control strip** — shows live values + Reset + Apply buttons.

### 4.2 Graph content

**X-axis:** seconds, relative to the *original* cycle start (t=0 = original start). Negative values appear in left context, values beyond original duration appear in right context.

**Data plotted:** the same channel curves as the Cycle tab (respects the current channel/alignment selection).

**Shaded region:** a `pyqtgraph.LinearRegionItem` spanning `[new_start, new_end]` — draggable as a unit or by each edge independently. This is the standard pyqtgraph primitive — no custom implementation needed.

**Dimmed context:** the data outside the shaded region is rendered at reduced opacity (alpha ~60%) to visually distinguish "in cycle" from "context". Achieved by setting the pen alpha on those series or by a semi-transparent overlay `QGraphicsRectItem`.

**Drag handles:** the `LinearRegionItem` edges act as the drag handles. No custom widget needed. Cursor changes to `SizeHorCursor` on hover automatically.

### 4.3 Expand buttons

Positioned as overlay `QPushButton` widgets anchored to the left and right inner edges of the plot frame (not in the plot's coordinate space — `QVBoxLayout`/`QHBoxLayout` overlay or `QStackedLayout`).

| Button | Label | Action |
|---|---|---|
| Left expand | `◀+` | Extend `context_left` by `0.10 × cycle_duration`. Cap: beginning of session data. |
| Right expand | `+▶` | Extend `context_right` by `0.10 × cycle_duration`. Cap: end of session data. |

Both buttons grey out individually when their respective edge hits the session boundary.

**Initial state:** `context_left = context_right = 0.20 × cycle_duration`. So on first opening the Adjust tab for a 600 s cycle, 120 s of context is shown each side.

### 4.4 Control strip

Three read-only labels updated live as the user drags:

| Label | Value | Notes |
|---|---|---|
| **Start offset** | `−12.0 s` | How far the new start is from the original start. Negative = earlier, Positive = later. |
| **Duration** | `647.0 s` | New cycle duration = (new_end − new_start). |

Two buttons:

| Button | Action |
|---|---|
| **Reset** | Snap `LinearRegionItem` back to original boundaries (offset = 0, duration = original). Clears any pending correction without saving. |
| **Apply** | Persist the correction (see §5). Switch back to Cycle tab automatically. |

---

## 5. Data Model — Cycle Correction

### 5.1 What is stored

A correction is stored as two values on the cycle:

```python
# On the cycle domain object (cycle.py or equivalent):
time_start_correction_s: float = 0.0   # seconds to add to original start_time
time_end_correction_s: float = 0.0     # seconds to add to original end_time
```

**Example:** user drags start 12 s earlier and end 47 s later:
```
time_start_correction_s = -12.0
time_end_correction_s   = +47.0
```

Effective window used downstream:
```
effective_start = cycle.start_time + time_start_correction_s
effective_end   = cycle.end_time   + time_end_correction_s
```

### 5.2 Where corrections are applied

Every piece of code that consumes `cycle.start_time` / `cycle.end_time` must go through a helper:

```python
def effective_start(cycle) -> float:
    return cycle.start_time + getattr(cycle, 'time_start_correction_s', 0.0)

def effective_end(cycle) -> float:
    return cycle.end_time + getattr(cycle, 'time_end_correction_s', 0.0)
```

This helper is defined once in `affilabs/domain/cycle.py` (or a utility module). All downstream consumers are updated to call it:

- Cycle graph rendering in `_edits_cycle_mixin.py`
- Δ SPR cursor auto-placement
- Export (Excel, CSV) — the exported time axis uses the corrected window
- Alignment — the corrected window defines what frame t=0 maps to

### 5.3 Persistence

Corrections are stored in the session's cycle metadata alongside the cycle's existing fields. The exact storage location depends on whether cycles are stored in the CSV header, a sidecar JSON, or the in-memory `RecordingManager` object — verify against `RECORDING_MANAGER_FRS.md` before implementation.

**Minimum requirement:** corrections survive a session reload (i.e., they are written to disk with the session, not held only in memory).

### 5.4 Overlapping cycles

Two cycles may reference overlapping time ranges after correction. This is explicitly allowed. Each cycle is an independent view into the session timeline. No validation or warning is needed.

---

## 6. Loading Session Data for the Adjust View

The Adjust graph needs data outside the cycle's original boundaries. Two scenarios:

| Scenario | Behaviour |
|---|---|
| Session file loaded in Edits (full timeline available) | Read ±`context` seconds from the session DataFrame/array already in memory |
| Session file not loaded (cycle loaded from a saved export that was trimmed to the cycle window) | Left and right expand buttons both disabled. Show message: "Full session data required to adjust boundaries. Load the original recording." |

**Check:** when a cycle is selected and the user switches to the Adjust tab, attempt to find the corresponding session data in `RecordingManager` or the loaded session DataFrame. If found, enable the tab. If not, show the message above and disable drag/expand.

---

## 7. UX Details

### 7.1 Cycle tab badge when correction is active

When `time_start_correction_s != 0` or `time_end_correction_s != 0`, the **Adjust** tab label shows a small indicator:

```
[ Cycle ]  [ Adjust ✎ ]
```

This persists until the correction is reset. It makes the correction visible without being intrusive.

### 7.2 Edits table indicator

The cycle row in the Edits table shows a small pencil icon or italic style in the Duration column when a correction is active. Tooltip: "Boundaries adjusted — original: 600 s → corrected: 647 s".

### 7.3 No undo beyond Reset

The Reset button is the undo. There is no multi-level undo. If the user applies and later wants to revert, they open the Adjust tab again and click Reset.

### 7.4 Switching tabs mid-drag

If the user switches to the Cycle tab while the `LinearRegionItem` has been moved but **Apply** not clicked, the pending correction is discarded silently — the graph moves back to the applied (or original) boundaries. A `QDialog` confirmation is intentionally NOT shown — too much friction for a correction tool.

---

## 8. Implementation Plan

| Step | What | File |
|---|---|---|
| 1 | Add `time_start_correction_s` / `time_end_correction_s` fields to cycle domain model | `affilabs/domain/cycle.py` |
| 2 | Add `effective_start()` / `effective_end()` helpers | `affilabs/domain/cycle.py` |
| 3 | Update all existing consumers of `cycle.start_time` / `cycle.end_time` to use helpers | `_edits_cycle_mixin.py`, export, alignment |
| 4 | Wrap `_create_active_selection()` content in `QTabWidget` with Cycle + Adjust tabs | `_ui_builders.py` |
| 5 | Implement Adjust tab graph: `LinearRegionItem`, dimmed context series, expand buttons | `_adjust_mixin.py` (new) |
| 6 | Implement control strip: live labels, Reset, Apply | `_adjust_mixin.py` |
| 7 | Implement session data lookup for padding | `_adjust_mixin.py` |
| 8 | Add Adjust tab badge on active correction | `_ui_builders.py` + `_adjust_mixin.py` |
| 9 | Add Edits table duration indicator | `_table_mixin.py` |
| 10 | Verify corrections persist across Edits tab reload | manual test |

Steps 1–3 first — they are a dependency for everything else and low-risk. Steps 4–6 are the bulk of the work. Steps 8–9 are polish.

---

## 9. Out of Scope

- Adjusting injection flag position separately from window (separate drag interaction — deferred)
- Multi-cycle batch adjustment (select multiple rows, apply same offset to all) — deferred
- Undo history — Reset covers the use case
- Modifying the underlying raw session CSV timestamps — never, this is view-layer only
