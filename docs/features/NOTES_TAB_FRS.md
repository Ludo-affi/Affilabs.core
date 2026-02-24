# Notes Tab — Feature Reference Specification

> **Component rename:** Originally scoped as "Experiment History Window" (floating dialog). Redesigned as a permanent **Notes tab** — third tab in the main window tab bar.

**Component:** `affilabs/tabs/notes_tab.py` (new, with sub-modules in `affilabs/tabs/notes/`)
**Location:** Third tab in main tab bar — Live · Edits · **Notes**
**Window type:** Permanent `QWidget` tab — not a dialog, not a floating window
**Keyboard shortcut:** `Ctrl+3` (consistent with Live = `Ctrl+1`, Edits = `Ctrl+2`)
**Offline:** Fully functional with no hardware connected and no file loaded
**Depends on:** `affilabs/services/experiment_index.py`, `affilabs/services/cycle_template_storage.py`
**Version target:** v2.1.0

---

## 1. Purpose

The Notes tab is the third step in the SPR researcher workflow:

| Tab | When | Purpose |
|-----|------|---------|
| **Live** | During acquisition | Real-time sensorgram, hardware controls |
| **Edits** | After recording | Load, align, fit, export |
| **Notes** | Before, during, after | Document, search, rate, plan next runs |

It is an **Electronic Lab Notebook (ELN)** embedded in the main app. Always accessible — researchers can plan tomorrow's experiment while today's run is still live.

---

## 2. Layout

```
+----------------------------------------------------------------------+
|  Live      Edits      Notes                                          |  <- Tab bar
+----------+---------------------------------------+-------------------+
|          | Search notes, tags, chips...  [All]   |                  |
| LEFT     +------------------------------------   +  RIGHT            |
| PANEL    |                                       |  PANEL            |
|          |  EXPERIMENT LIST                      |                   |
| Filters  |  Feb 23  HER2 kinetics  **** #kin     |  Preview          |
|          |  Feb 22  Bad baseline   *    #bad      |  sensorgram       |
| Tags     |  Feb 21  Immobilization ***  #immob    |                  |
|          |  Feb 18  Regen test     unrated        |  Metadata         |
| Needs    |  [Planned] Repeat kinetics lower c     |                  |
| Repeat   |  ...                                  |  Notes editor     |
|          |                                       |                  |
| Planned  +---------------------------------------+  Star rating      |
|          |  [= List]  [# Kanban]   Sort: Newest  |                  |
|          |                                       |  Tags             |
|          |  <- toggle between list and kanban ->  |                  |
|          |                                       |  Actions          |
+----------+---------------------------------------+-------------------+
```

**Three panels:**
- **Left (200 px fixed):** Navigation — smart filters, tags, counts
- **Centre (flex):** Experiment list + Kanban toggle
- **Right (300 px fixed):** Preview sensorgram + ELN panel

---

## 3. Left Panel — Navigation

### 3.1 Smart Filters

```
ALL EXPERIMENTS     (47)
* Needs Repeat      (6)    <- red text, rating 1-2
o Planned           (3)    <- blue text, type = planned
- Unrated           (12)   <- rating = 0
```

Clicking any filter updates the centre list instantly. Only one active at a time.

### 3.2 Tags

Auto-populated from all tags across all entries, sorted by usage count descending. Click to filter. Multiple tags selectable (AND logic).

```
TAGS
  #kinetics     6
  #regen        4
  #immob        3
  #baseline     2
  #bad          1
  + New tag...
```

Clicking `+ New tag...` opens an inline QLineEdit — typed tag is not attached to any entry yet, just created in the tag pool.

### 3.3 Collections

**Deferred — v2.2.** Placeholder section label "Collections" with greyed "Coming soon" text.

---

## 4. Centre Panel — Experiment List

### 4.1 Header

```
[= List]  [# Kanban]          Sort: Newest v
```

Toggle and sort state persisted to `%LOCALAPPDATA%\Affilabs\notes_prefs.json`.

### 4.2 List View (default)

One row per entry (recorded experiment or planned placeholder). Dense rows — no thumbnails.

| Column | Content |
|--------|---------|
| Date | `Feb 23, 2026` |
| Description | First line of notes, or filename if no notes |
| Rating | `****-` (interactive — click to change inline) |
| Tags | Pill chips (read-only, click to filter) |
| Status | `Done` / `Needs Repeat` / `Planned` badge |

- Single-click -> show in right panel
- Double-click -> load in Edits tab (recorded entries only; no-op on planned)
- Right-click -> context menu: Load · Open Excel · Reveal · Edit tags · Link to planned · Delete from index

Planned entries appear in the same list with a `[Planned]` prefix instead of a date and a dashed description.

### 4.3 Kanban View

Four columns: **Planned -> Running -> Done -> Needs Repeat**

```
+------------+-------------+---------------+------------------+
|  PLANNED   |   RUNNING   |     DONE      |  NEEDS REPEAT    |
|            |             |               |                  |
| [+] New    | HER2 rep 2  | HER2 rep 1    | Bad baseline     |
|            | (live now)  | Feb 23 ****   | Feb 22 *         |
| Repeat     |             |               |                  |
| kinetics   |             | Immobiliz.    |                  |
|            |             | Feb 21 ***    |                  |
+------------+-------------+---------------+------------------+
```

Cards show: date + first-line description + rating dot colour.

**Column auto-population rules:**
- `Planned` — entries with `type = "planned"` and `status = "planned"`
- `Running` — current active recording, populated live via `RecordingManager` signal
- `Done` — entries with `rating >= 3` (or unrated)
- `Needs Repeat` — entries with `rating` 1 or 2; auto-moved when rating is set

Drag between columns updates the entry's `status` field. The `Running` column is read-only — managed by `RecordingManager`.

---

## 5. Right Panel — Preview + ELN

### 5.1 Header

Filename (bold) or planned description. Status badge beside it.

### 5.2 Sensorgram Preview

`pyqtgraph.PlotWidget`, read-only, loaded by `PreviewWorker` in background thread.
- All 4 channels, accessibility palette colours
- 180 px fixed height
- Placeholder: "Select an experiment to preview" when nothing selected
- Greyed placeholder + "File missing" for stale index entries

### 5.3 Metadata Grid

```
Chip      FLMT09788     Duration   47 min
Cycles    8             User       lucia
Date      Feb 23 2026   Hardware   P4SPR
```

Hidden for planned entries (no metadata yet).

### 5.4 Rating

Interactive `StarRatingWidget` (1–5 stars, same widget as MVP). Rating 1–2 auto-adds `#needs-repeat` tag and moves card to Needs Repeat column. Rating raised above 2 removes `#needs-repeat` tag.

### 5.5 Tags (inline editor)

Pill chips with `x` remove button per tag. `[+ Add tag]` -> inline `QLineEdit` with autocomplete from all known tags. Saved immediately on add/remove.

### 5.6 Notes (inline editor)

`QTextEdit`, 4 visible lines. Auto-saves on focus-out with 800 ms debounce. Saved to `experiment_index.json`. Plain text only.

### 5.7 Plan Next Run

Visible when the selected entry is a **planned** placeholder, or when user clicks `[Plan Next Run]` on a Done / Needs Repeat entry.

```
+------------------------------------------------+
|  PLAN NEXT RUN                                 |
|                                                |
|  Description  [Repeat kinetics low conc      ] |
|  Based on     [Feb 22 - Bad baseline        v] |
|  Method       [Select method...             v] |  <- CycleTemplateStorage
|  Target date  [2026-03-01                    ] |
|  Notes        [Try 500 nM instead...         ] |
|                                                |
|                    [Create Planned Entry]      |
+------------------------------------------------+
```

**Method dropdown** — populated from `CycleTemplateStorage.get_all_templates()`. Selecting a method attaches its `template_id` to the planned entry.

**Bidirectional with Method Builder (see §15):** When the researcher opens the Method Builder while a planned entry with an attached method is active, the builder offers "Load planned method" at the top. Conversely, the Method Builder has a "Save as Plan" action that creates a new planned entry in Notes with the current queue pre-attached.

### 5.8 Analyte Tag Suggestion

When `recording_stopped` fires, if any cycle in the completed run has a non-generic name (e.g. "HER2 100nM", "Anti-IgG regen"), Notes surfaces a **non-blocking toast** at the bottom of the right panel:

```
"Add tag #HER2?"  [Yes]  [No]
```

Tag is extracted from the first word of the cycle name. One suggestion per recording, one click to accept. No suggestion if cycle names are all generic ("Baseline", "Regen", "Buffer").

### 5.9 Actions

```
[Load in Edits]  [Open Excel]  [Reveal]  [Plan Next Run]
```

`Load in Edits` switches to Edits tab and loads the file.
`Plan Next Run` shows the Plan Next Run section in the same right panel.
`Load Method` — only shown for planned entries with an attached method template; loads it into Method Builder queue.

---

## 6. Search

`QLineEdit` at the top of the centre panel. 150 ms debounce. Searches across:
`notes`, `tags[]`, `chip_serial`, `filename`, `user`, `description`, `planned_description`.

Empty search = show all (respecting active left-panel filter).

Sort: Newest first / Oldest first / Rating high-to-low / Duration / Unrated first.

---

## 7. Planned Entries

Planned entries are **not recordings** — no Excel file, no sensorgram. They are intention placeholders for future runs.

```json
{
  "id": "plan_20260224_001",
  "type": "planned",
  "description": "Repeat kinetics at 500 nM",
  "based_on_entry_id": "exp_20260222_091030",
  "method_template_id": "tpl_her2_kinetics",
  "target_date": "2026-03-01",
  "notes": "Try lower concentration — previous run saturated",
  "tags": ["kinetics", "plan"],
  "created": "2026-02-24T10:00:00",
  "status": "planned",
  "linked_entry_id": null
}
```

**Linking to a real recording:** Right-click a new recording in the list -> "Link to planned entry" -> pick from dropdown. Sets `planned_entry.status = "done"` and `planned_entry.linked_entry_id = exp_id`.

---

## 8. Data Model

### 8.1 Experiment entry additions (new optional fields)

```json
{
  "tags": [],
  "rating": 0,
  "description": "",
  "status": "done",
  "calibration_run": false,
  "baseline_run": false
}
```

- `calibration_run` — set `true` on `recording_started` if a calibration was completed in the same session (i.e. `CalibrationService` has a valid `CalibrationData` with timestamp < 30 min before recording start)
- `baseline_run` — set `true` on `recording_started` if the loaded method queue contains a cycle with `type = "Baseline"` as its first step
- Both are **stamped once at recording start** and never updated after — they describe what was prepared before the run, not what happened during it
- Displayed as small greyed check marks on the list row / Kanban card: `✓ cal  ✓ bsl` — not visually prominent, just present for traceability

All fields default gracefully on read — no migration script needed for existing entries.

### 8.2 Top-level structure of `experiment_index.json`

```json
{
  "schema_version": 2,
  "entries": [ ... ],
  "planned": [ ... ]
}
```

`schema_version` bumped 1 -> 2 on first write that adds the `planned` key.

---

## 9. ExperimentIndex API Extensions

```python
# Tags
def add_tag(entry_id: str, tag: str) -> None
def remove_tag(entry_id: str, tag: str) -> None
def all_tags() -> dict[str, int]           # {tag: usage_count}

# Rating
def set_rating(entry_id: str, rating: int) -> None   # 0-5
def get_needs_repeat() -> list[dict]                  # rating 1 or 2

# Notes / description
def update_notes(entry_id: str, notes: str) -> None
def update_description(entry_id: str, description: str) -> None

# Planned entries
def create_planned(description: str, *, based_on: str | None = None,
                   method_id: str | None = None, target_date: str | None = None,
                   notes: str = "") -> str            # returns plan id
def update_planned(plan_id: str, **fields) -> None
def delete_planned(plan_id: str) -> None
def link_planned_to_recording(plan_id: str, entry_id: str) -> None
def all_planned() -> list[dict]

# Extended search
def search(*, keyword: str = "", tags: list[str] | None = None,
           user: str | None = None, chip: str | None = None,
           after: str | None = None, before: str | None = None,
           rating: int | None = None, status: str | None = None) -> list[dict]
```

---

## 10. Background Workers

```python
# affilabs/tabs/notes/_workers.py

class PreviewWorker(QRunnable):
    """Load wavelength data from Excel, emit for right-panel plot."""
    signals: _PreviewSignals   # ready(entry_id: str, data: dict)
```

Thumbnail generation deferred — list view does not require thumbnails.

---

## 11. Tab Integration

### 11.1 Tab bar registration

```python
# affilabs/affilabs_core_ui.py
self.notes_tab = NotesTab(experiment_index=self._experiment_index)
self.tab_widget.addTab(self.notes_tab, "Notes")
```

Tab is always present — no conditional visibility based on hardware or recording state.

### 11.2 Keyboard shortcut

`Ctrl+3` switches to Notes tab. Added alongside existing `Ctrl+1` / `Ctrl+2` shortcuts.

### 11.3 RecordingManager integration

**Notes tab does not process live data.** All updates happen at `recording_started` or `recording_stopped` only — no `event_logged` feed, no mid-run polling.

| Event | Notes tab response |
|-------|-------------------|
| `recording_started(filename)` | 1. Stamps `calibration_run` + `baseline_run` flags on the new index entry. 2. Moves linked planned entry (if any) into "Running" Kanban column. |
| `recording_stopped` | 1. Finalises index entry (duration, cycle count). 2. Auto-refreshes list. 3. Evaluates analyte tag suggestion from cycle names (§5.8). |

### 11.4 Edits tab History button

The existing "History" button in `_ui_builders.py` switches to the Notes tab (`Ctrl+3`) instead of opening `ExperimentBrowserDialog`.

---

## 12. Offline Behaviour

No hardware required. No recording required. Loads from `~/Documents/Affilabs Data/experiment_index.json`.

If the index does not exist yet (first launch, no recordings):
- List shows empty state: "No experiments yet — start recording to build your history"
- Planned column is fully usable — researchers can plan before their first run
- All features (tags, search, Kanban, Plan Next Run) available immediately

---

## 13. File Structure

| File | Role |
|------|------|
| `affilabs/tabs/notes_tab.py` | `NotesTab(QWidget)` — assembles three panels |
| `affilabs/tabs/notes/_nav_panel.py` | Left navigation: filters + tag cloud |
| `affilabs/tabs/notes/_list_panel.py` | Centre: list view + Kanban toggle + search bar |
| `affilabs/tabs/notes/_kanban_widget.py` | Kanban board (4 columns, drag-and-drop cards) |
| `affilabs/tabs/notes/_preview_panel.py` | Right: sensorgram preview + ELN fields + actions |
| `affilabs/tabs/notes/_plan_widget.py` | "Plan Next Run" form (embedded in right panel) |
| `affilabs/tabs/notes/_workers.py` | `PreviewWorker` QRunnable |
| `affilabs/services/experiment_index.py` | Extended with tags, ratings, planned entries |

---

## 15. Method Builder Integration

**Goal:** A planned entry with an attached method template is a direct shortcut into the Method Builder — no re-building from scratch.

### 15.1 Notes → Method Builder (load planned method)

When the researcher selects a planned entry that has a `method_template_id` and clicks `[Load Method]` (§5.9):
1. Notes tab calls `CycleTemplateStorage.get_template(method_template_id)` to retrieve the queue
2. Switches active tab to Live
3. Calls `method_builder_dialog.load_template(template)` — same path as normal template loading

### 15.2 Method Builder → Notes (save as plan)

Method Builder gets a new secondary action button: **"Save as Plan"** (beside the existing Load/Save template buttons). Clicking it:
1. Opens a small inline form: description field + target date picker
2. Calls `ExperimentIndex.create_planned(description, method_id=current_template_id, target_date=...)`
3. Shows brief confirmation toast: "Planned entry created — view in Notes tab"

No new dialog. The form appears inline in Method Builder as a collapsible section.

### 15.3 Method Builder planned entry indicator

If the currently loaded queue in Method Builder matches a planned entry's `method_template_id`, Method Builder shows a small badge under the queue title:
```
Plan: Repeat kinetics 500 nM  (Mar 01)
```
Clicking the badge switches to Notes tab and selects that planned entry.

---

## 16. Supersedes

| Old file | Fate |
|----------|------|
| `affilabs/dialogs/experiment_browser_dialog.py` | Deprecated — remove when Notes tab ships |
| `affilabs/dialogs/experiment_history_window.py` | Never implemented — delete stub if it exists |

---

## 17. Explicitly Out of Scope

- **No live event feed** — `event_logged` is not connected to Notes tab. The timeline/event log stays in the Live tab only.
- **No mid-run updates** — Notes tab state only changes at `recording_started` and `recording_stopped`.
- **No calibration detail in Notes** — only the boolean "was calibration run before this experiment" is stored. SNR, FWHM, servo positions stay in calibration files.

---

## 18. Implementation Roadmap

> Build phases in order. Each phase is independently shippable with zero risk to the next.

---

### Status Snapshot (Feb 24 2026)

| Artifact | Status | Notes |
|----------|--------|-------|
| `affilabs/services/experiment_index.py` | ✅ DONE — 384 lines | Phase 1 complete — all API implemented |
| `affilabs/tabs/notes_tab.py` | ✅ DONE — 719 lines | Phase 2 scaffold complete — 3 panels wired into `content_stack` |
| `affilabs/tabs/notes/` sub-modules | ❌ Not created | All code is in the monolithic `notes_tab.py` — extract later if needed |
| Notes tab wired into UI | ✅ DONE | `affilabs_core_ui.py` L451–453: `content_stack.addWidget(notes_tab)` at index 2 |
| Right panel — Notes editor (editable) | ✅ DONE | `_notes_edit.setReadOnly(False)` + 800ms debounce save via `_save_notes` → `ExperimentIndex.update_notes()` |
| Right panel — Star rating (interactive) | ✅ DONE | `_StarRatingWidget` class (lines ~62–110); wired to `ExperimentIndex.set_rating()` |
| Right panel — Tag editor | ✅ DONE | `_refresh_tags_panel`, `_make_tag_pill`, `_on_add_tag`, `_on_remove_tag` with `QCompleter`; horizontal scroll area |
| Right panel — Sensorgram preview | ✅ DONE | `PreviewWorker(QRunnable)` + `_PreviewSignals`; `pg.PlotWidget` 130px; graceful fallback if pyqtgraph absent |
| Kanban view | ❌ Missing | No Kanban toggle or `_kanban_view` in current code |
| RecordingManager hooks | ✅ DONE | `on_recording_started` + `on_recording_stopped` on `NotesTab`; wiring in `main.py` still needed |
| Edits tab "History" button rewiring | ❌ Not done | Still calls `ExperimentBrowserDialog.exec()` |
| Method Builder "Save as Plan" | ❌ Deferred | Lowest priority |

---

### ✅ Phase 1 — Data Layer (no Qt) — COMPLETE (Feb 24 2026)

**File:** `affilabs/services/experiment_index.py` (384 lines)

All API implemented:
- `set_rating(entry_id, rating)` — 0–5 stars
- `add_tag` / `remove_tag` / `all_tags() -> dict[str, int]`
- `update_notes` / `update_description`
- `create_planned(...)` / `update_planned(...)` / `delete_planned(...)` / `all_planned()`
- `link_planned_to_recording(plan_id, entry_id)`
- `search(*, keyword, tags, user, chip_serial, after, before, rating, hardware_model, status)`
- `_SCHEMA_VERSION = 2`, v1→v2 migration guard, `"planned": []` key added on first write
- `record_experiment(...)` includes `calibration_run`, `baseline_run`, `analyte_suggestion`
- Zero Qt imports — fully unit-testable without display

---

### ✅ Phase 2 — Tab Shell — COMPLETE (Feb 24 2026)

**File:** `affilabs/tabs/notes_tab.py` (719 lines)

What is implemented:
- `_ExperimentListRow(QFrame)` — dense row widget: date, description, chip, cycles, duration, stale indicator, hover + selection state
- `NotesTab(QWidget)` — 3-panel `QSplitter` layout: left nav (200 px) · centre list (flex) · right preview (300 px)
- **Left nav:** ALL / Needs Repeat / Planned / Unrated filter buttons with live counts; date range pickers (From / To `QDateEdit`)
- **Centre list:** `QLineEdit` search (150 ms debounce), `_apply_filter()` runs `ExperimentIndex.search()`, `_rebuild_list()` populates scroll area with `_ExperimentListRow` widgets
- **Right panel:** metadata grid (Chip, Duration, Cycles, User, Date, Hardware), read-only `QTextEdit` for notes, static star label, Load in Edits + Open Excel action buttons
- Wired into `affilabs_core_ui.py`: `content_stack.addWidget(self.notes_tab)` at index 2
- `refresh()` public method — reloads entries and reapplies current filter; called by `_acquisition_mixin.py` after recording stops
- `switch_to_entry(entry_id)` — selects and scrolls to a specific entry by id
- Double-click row → Load in Edits (calls `main_window._load_recording_file(path)`)

What Phase 2 does **not** include (deferred to Phase 2b):
- Notes editor is **read-only** → needs `setReadOnly(False)` + `focusOut` debounce save via `ExperimentIndex.update_notes()`
- Star rating is a **static label** → replace with `StarRatingWidget` that calls `ExperimentIndex.set_rating()`
- No **tag editor** in right panel → add pill chips + `[+ Add tag]` QLineEdit with `QCompleter` from `all_tags()`
- No **sensorgram preview** → add `pyqtgraph.PlotWidget` (180 px, read-only) loaded by `PreviewWorker`
| No **Kanban** → the list/kanban toggle header buttons are absent; add stub `QLabel("Kanban — Phase 3")` behind toggle first | Phase 4 stub ✅ DONE |

---

### ✅ Phase 2b — Right Panel ELN Widgets — COMPLETE (Feb 24 2026)

**File:** `affilabs/tabs/notes_tab.py` (1253 lines)

- **2b-1 notes auto-save:** `_notes_edit.setReadOnly(False)`; `textChanged` → `_on_notes_changed` → 800ms `_notes_save_timer` → `_save_notes` → `ExperimentIndex.update_notes()`. `_notes_blocking` flag suppresses saves during `_populate_preview` population.
- **2b-2 star rating:** `_StarRatingWidget(QWidget)` class with 5 `QPushButton`s (26×26px); click-same-star → clear; `rating_changed Signal(int)` → `_on_rating_changed` → `ExperimentIndex.set_rating()`. Disabled on stale entries.
- **2b-3 tag editor:** Horizontal `QScrollArea` with `_refresh_tags_panel(tags)` that builds `_make_tag_pill(tag)` frames (pill + × remove button). `[+ Add tag]` button → `_on_add_tag` → inline 90px `QLineEdit` with `QCompleter(all_tags())`; commit on Return/blur. `_on_add_tag_value` / `_on_remove_tag` call `ExperimentIndex.add_tag/remove_tag`.
- **2b-4 sensorgram preview:** `_PreviewSignals(QObject)` + `PreviewWorker(QRunnable)` reads Excel sensorgram sheet with pandas; emits `ready(entry_id, dict)`. On ready, `_on_preview_ready` plots all channels with `pg.mkPen`. Graceful fallback label if pyqtgraph not installed.
- **Filter counts wired:** `_update_filter_counts` now computes needs_repeat (rating 1–2), planned (`all_planned()`), unrated from live data.
- **Filter logic wired:** `_apply_filter` now correctly filters rows for needs_repeat / unrated / planned modes; tags included in keyword haystack.
- **Recording hooks added:** `on_recording_started(filename)` + `on_recording_stopped()` on `NotesTab`; wired in `main.py` `_connect_hardware_and_manager_signals()` ✅

---

### Phase 2b — Right Panel ELN Widgets (next priority)

These are all changes within `notes_tab.py` → `_build_preview_panel()` and `_populate_preview()`. No new files needed.

**2b-1 — Editable notes field**

```python
# In _build_preview_panel():
self._notes_edit.setReadOnly(False)
self._notes_edit.textChanged.connect(self._on_notes_changed)

# Add debounce timer to __init__:
self._notes_save_timer = QTimer()
self._notes_save_timer.setSingleShot(True)
self._notes_save_timer.setInterval(800)
self._notes_save_timer.timeout.connect(self._save_notes)

def _on_notes_changed(self):
    self._notes_save_timer.start()

def _save_notes(self):
    if self._selected_row:
        from affilabs.services.experiment_index import ExperimentIndex
        ExperimentIndex().update_notes(self._selected_row.entry["id"], self._notes_edit.toPlainText())
```

**2b-2 — Interactive star rating**

Replace `self._rating_lbl = QLabel("☆☆☆☆☆")` with:

```python
class _StarRatingWidget(QWidget):
    rating_changed = Signal(int)   # 0–5
```

Five `QPushButton` stars (☆/★), clicking star N sets rating to N (click same star again → 0). On `rating_changed`, call `ExperimentIndex().set_rating(entry_id, rating)`.

**2b-3 — Tag editor**

Below the rating in `_build_preview_panel()`, add a horizontal scroll area of pill `QPushButton` widgets with `×` remove handler, plus a `[+ Add tag]` button that opens an inline `QLineEdit` with `QCompleter(list(all_tags().keys()))`. Add tag on Return; call `ExperimentIndex().add_tag(entry_id, tag)`.

**2b-4 — Sensorgram preview**

At the top of the right panel (before metadata grid), add:

```python
import pyqtgraph as pg
self._preview_plot = pg.PlotWidget()
self._preview_plot.setFixedHeight(180)
self._preview_plot.setBackground(_PREVIEW_BG)
self._preview_plot.hideAxis("left")
self._preview_plot.hideAxis("bottom")
```

Load data in a `QRunnable` (`PreviewWorker`) — read the Excel file's sensorgram sheet, emit `dict[channel → (times, wavelengths)]` via signal, plot all 4 channels in accessibility palette colours. Show placeholder text `"Select an experiment to preview"` when nothing selected.

---

### Phase 3 — RecordingManager Hooks ✅ COMPLETE (Feb 24 2026)

**What was done:**
- `on_recording_started(filename)` + `on_recording_stopped()` already existed on `NotesTab` (added in Phase 2b)
- Wired in `main.py` `_connect_hardware_and_manager_signals()`: `recording_mgr.recording_started` → `notes_tab.on_recording_started` and `recording_mgr.recording_stopped` → `notes_tab.on_recording_stopped`, both `Qt.QueuedConnection`
- Removed redundant `notes_tab.refresh()` from `_acquisition_mixin.py` (was L503–504); `on_recording_stopped` handles it now

---

### Phase 4 — Kanban Stub ✅ COMPLETE (Feb 24 2026)

**What was done:**
- Added `QStackedWidget` import to `notes_tab.py`
- Added 36px toggle header (`☰ List` / `⊞ Kanban` buttons) between search bar and scroll area
- `self._scroll` (list) at index 0, `kanban_stub` placeholder `QWidget` at index 1 of `self._view_stack`
- `_switch_to_list_view()` / `_switch_to_kanban_view()` handle active/inactive button styling (accent fill vs transparent)
- Starts in List mode; Kanban stub shows "Kanban view—coming soon"

**Next step for full Kanban:** Replace `kanban_stub` with a `_KanbanView` widget — 4 columns (Planned / Running / Done / Needs Repeat), drag-drop updates `ExperimentIndex` `status` field via `QDrag`.

---

### Deferred

| Feature | Prerequisite | Notes |
|---------|-------------|-------|
| Kanban drag-drop (full) | Phase 4 stub live ✅ | `QDrag` between columns; updates `ExperimentIndex` status field |
| Edits tab "History" button rewiring | Phase 2 live | Replace `ExperimentBrowserDialog.exec()` with `main_tabs.setCurrentWidget(notes_tab)` |
| Method Builder "Save as Plan" | Phase 3 live | Touches working UI — lowest risk to defer indefinitely |
| `calibration_run` / `baseline_run` auto-stamp | `on_recording_started` wired | Read `CalibrationService.last_calibration` timestamp; compare to recording start |
| ELN rich-text toolbar | 2b-1 plain-text working | Upgrade to bold/italic/list — QTextEdit already supports HTML |
| Collections (§3.3) | v2.2 | Placeholder only for now |

---

### Key Invariants (do not break)

1. **Key name is `"entries"`** — not `"experiments"`. Planned-entries key is `"planned"`. Both are top-level siblings in `experiment_index.json`.
2. **No live event feed** — `event_logged` is never connected to Notes tab (§17).
3. **`experiment_browser_dialog.py` is deprecated** — do not add features to it. Delete after Edits "History" button is rewired.
4. **Phase 1 has zero Qt imports** — `experiment_index.py` must remain importable without a display server.
5. **`content_stack` index 2** — Notes tab is at index 2 in `content_stack`. IconRail button at index 2 must switch to it. Do not reorder.