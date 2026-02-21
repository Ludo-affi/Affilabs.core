# Sidebar Redesign Plan — Affilabs.core v2.1

> **Status**: Approved design, not yet implemented
> **Scope**: P4SPR (manual injection) first. Flow/P4PRO/P4PROPLUS deferred.
> **Goal**: Sidebar nav is global config only. Live page gains a persistent right panel for acquisition-time info and a contextual left panel for QC tools. Less is more.

---

## Final Approved Layout

### Global sidebar (left icon strip — always present)

```
Tab 0 — METHOD         Build queue before experiment
Tab 1 — USER + EXPORT  User identity + export config
Tab 2 — SETTINGS       Hardware, Calibration, Display
[Sparq]                AI assistant (unchanged)

Status bar footer:     🟢 Connected | ⏺ Not Recording | ● Sensor ● Optics
```

Flow tab is not touched in this redesign (P4SPR scope). It stays in code, hidden for P4SPR.

### Live page layout (content area)

```
┌────┬────────────────────────────────────┬──────────────────────┐
│    │                                    │  Active Cycle Card   │
│ ⚡ │                                    │  ──────────────────  │
│    │                                    │  INJECT  00:45 ↓    │
│ 👤 │         SENSORGRAM                 │  next: WASH          │
│    │         Channel A/B/C/D            │  ──────────────────  │
│ ⚙️ │         timeline, flags            │  Queue               │
│    │         stability badge            │  1 ✓ BASELINE        │
│ ── │                                    │  2 → INJECT          │
│    │                                    │  3   WASH            │
│ 📡 │                                    │  ──────────────────  │
│    │                                    │  Elapsed: 04:32      │
│ 💉 │                                    │                      │
└────┴────────────────────────────────────┴──────────────────────┘
```

**Left strip** (below global sidebar icons, separated by divider):
- `📡` Spectroscopy — opens left contextual panel
- `💉` Injection — opens left contextual panel

**Right panel** (always visible during acquisition, no click required):
- Active Cycle Card (cycle type badge, countdown, next cycle)
- Queue table (progress through experiment)
- Elapsed experiment time

**Left contextual panel** (slides in when icon clicked, overlays sensorgram left):

| Icon | Panel content |
|------|--------------|
| 📡 | Transmission plot (4 live channels, always visible); Raw spectrum (CollapsibleSection, collapsed); Capture Baseline button |
| 💉 | Channel toggles (☑ A ☑ B ☑ C ☑ D); Mark Injection button (prominent); Contact timer |

Only one panel open at a time. Clicking active icon collapses it. Panel width ~240px.

### Design rationale

| Principle | How it's met |
|-----------|-------------|
| **Eyes on the right** | Acquisition-time info (queue, countdown, elapsed) always visible right side — where attention is at experiment end |
| **Less is more** | 3 sidebar tabs instead of 5; no sidebar tab for spectroscopy |
| **QC tools on demand** | Spectroscopy and injection panels accessible in one click but don't crowd the sensorgram by default |
| **Global vs contextual** | Sidebar = global nav + config; Live page panels = in-experiment tools |
| **Sensorgram unchanged** | Same widgets, same data — only the container layout changes |
| **Device status is ambient** | Subunit dots in status bar footer — glanceable, not interactive |
| **Calibration stays in Settings** | Setup action; discovery handled by pulse-on-connect |

---

## What Changes Per Area

### Sidebar Tab 0 — Method (was Tab 1, promoted to default)
- **Change**: Tab index 0, default tab on launch
- **Change**: Active Cycle Card and Queue table **removed** from this tab (they move to Live page right panel)
- **Kept**: Build Method CTA, queue controls (add/remove/reorder cycles), method builder dialog trigger
- **Rationale**: Method tab is pre-experiment setup. Active Cycle Card belongs on the Live page where the user watches it.

### Sidebar Tab 1 — User + Export (was Tab 3, moves up)
- **Source**: Merges User Management (from Settings) + Export tab content
- **File**: `affilabs/sidebar_tabs/AL_export_builder.py` (extended) or new `AL_user_export_builder.py`
- **Layout top-to-bottom**:
  - User profile card (always visible, not collapsible):
    - `👤 Name  •  Tier` label
    - XP progress bar
    - `[Switch User ▾]` compact dropdown (switch only; add/rename/delete stays in Settings)
  - Export section (`CollapsibleSection`, expanded by default):
    - Format, Target, File settings, Export button
- **Removed from Settings**: User Management `CollapsibleSection`

### Sidebar Tab 2 — Settings (was Tab 4, renumbered)
- **Removed**: User Management section (lines 79–289 in `AL_settings_builder.py`)
- **Removed**: Live Spectroscopy section (moves to Live page contextual panel)
- **Kept**: Hardware Configuration, Calibration Controls, Display Controls
- **Added**: Minimal "Manage Users" collapsed section for add/rename/delete
- **Added**: `DeviceStatus` widget as collapsed "Hardware Info" section (reference only)

### Device Status tab — REMOVED
- **3 subunit dots** (Sensor / Optics): move to main window status bar footer
- **Controller / firmware / COM port detail**: move to hover tooltip on power button
- **`tab_indices["Device Status"]`**: key removed — all references must be updated

### Live page — Right panel (NEW, always visible during acquisition)
- **Source**: Active Cycle Card and Queue table extracted from Method tab
- **New file**: `affilabs/widgets/live_right_panel.py` (or inline in `affilabs_core_ui.py`)
- **Content**:
  - Active Cycle Card (`active_cycle_card`) — same widget, repositioned
  - Queue summary (`QueueSummaryWidget`) — same widget, repositioned
  - Elapsed time label
- **Visibility**: **Hidden when not acquiring.** Shown only while an acquisition is running (i.e. `DataAcquisitionManager` is active). The Live page sensorgram expands to use the full width when the panel is hidden. No placeholder — the panel simply isn't there.
  - Show trigger: `acquisition_started` signal
  - Hide trigger: `acquisition_stopped` signal
  - Implementation: `live_right_panel.setVisible(True/False)` wired in `affilabs_core_ui._connect_signals()` or `acquisition_event_coordinator`
- **Width**: ~220px fixed

### Live page — Left contextual panel (NEW, on-demand)
- **New file**: `affilabs/widgets/live_context_panel.py`
- **Pattern**: Reuses same show/hide mechanism as Edits `export_sidebar`
- **Spectroscopy panel**:
  - Transmission plot — `SpectroscopyPresenter` writes to same attribute names (names unchanged, widget moves)
  - Raw spectrum — `CollapsibleSection`, collapsed by default
  - Capture Baseline button — moved from Settings
- **Injection panel**:
  - Channel toggles A/B/C/D
  - Mark Injection button (full-width, prominent — addresses current UX gap for P4SPR)
  - Contact timer display
- **Icon strip**: `📡` and `💉` icons on left edge of Live page, below global sidebar icon divider

---

## Phase Breakdown

### Phase 1 — Subunit dots to status bar (low risk, isolated)
**Files**: `affilabs/affilabs_core_ui.py`, `affilabs/ui_mixins/_device_status_mixin.py`

- Add dot labels to `QStatusBar`: `subunit_sensor_dot`, `subunit_optics_dot`
- Wire `_reset_subunit_status()` and `update_hardware_status()` to update status bar dots
- Keep Device Status tab alive (just deprecated) until Phase 4
- **Does not change tab structure** — purely additive

---

### Phase 2 — Live page right panel (low-medium, widget relocation)
**Files**: `affilabs/affilabs_core_ui.py` or new `affilabs/widgets/live_right_panel.py`, `affilabs/sidebar_tabs/AL_method_builder.py`, `affilabs/affilabs_sidebar.py`

- Create right panel container in Live page layout (QSplitter or fixed QFrame, ~220px)
- **Construction order fix (resolved)**: `active_cycle_card` is currently built *inside* `AL_method_builder._build_active_cycle_card()` as a child of the Method tab layout. It cannot be re-parented after the fact. Fix: pre-build `active_cycle_card` as `QFrame` in `AffilabsSidebar._setup_ui()` *before* any tab builders run (`self.active_cycle_card = QFrame()`). `AL_method_builder._build_active_cycle_card()` then calls `tab_layout.addWidget(self.sidebar.active_cycle_card)` rather than constructing it. Phase 2 removes that `addWidget` call and adds it to the right panel instead. Same widget instance, no re-construction needed.
- Move `QueueSummaryWidget` from Method tab into right panel — same widget, already a standalone class
- Add elapsed time label to right panel
- Remove the space they vacated from Method tab (tab becomes pre-experiment setup only)
- **Visibility**: hidden when not acquiring — `live_right_panel.setVisible(False)` on init; shown on `acquisition_started`, hidden on `acquisition_stopped` (wire in `affilabs_core_ui._connect_signals()`)

---

### Phase 3 — Live page left contextual panel (medium, new widget)
**Files**: new `affilabs/widgets/live_context_panel.py`, `affilabs/affilabs_core_ui.py`, `affilabs/sidebar_tabs/AL_settings_builder.py`

- Create `LiveContextPanel` widget:
  - Icon strip on left edge (📡 💉) — same pattern as Edits `export_sidebar` toggle
  - Spectroscopy sub-panel: transmission + raw pyqtgraph plots + Capture Baseline button
  - Injection sub-panel: channel toggles + Mark Injection button + contact timer
- **SpectroscopyPresenter is zero-change (resolved)**: it writes to `main_window.transmission_curves` and `main_window.raw_data_curves` — not `sidebar.*`. These are lists currently built in `AL_settings_builder.py:629` and aliased via `affilabs_core_ui.py:405` (`self.transmission_curves = self.sidebar.transmission_curves`). Phase 3 moves curve construction into `LiveContextPanel`, then updates the alias: `self.transmission_curves = self.live_context_panel.transmission_curves`. Presenter requires no changes.
- Delete `AL_settings_builder.py` lines 576–708 (Live Spectroscopy section) after curves move
- Move Capture Baseline button from Settings into spectroscopy sub-panel
- Mark Injection button here becomes the **primary P4SPR injection CTA** (addresses UX gap from UX_USER_JOURNEY.md Stage 4)
- Settings tab: remove Live Spectroscopy section

---

### Phase 4 — User + Export tab + sidebar reorder (medium)
**Files**: `affilabs/sidebar_tabs/AL_export_builder.py`, `affilabs/sidebar_tabs/AL_settings_builder.py`, `affilabs/affilabs_sidebar.py`

- Add user profile card at top of Export tab (name + tier, XP bar, Switch User dropdown)
- Remove User Management CollapsibleSection from Settings
- Add minimal "Manage Users" collapsed section to Settings
- Rename tab: "Export" → "User & Export"
- Update `tab_indices`: remove Flow from active set for P4SPR; reorder to Method=0, User+Export=1, Settings=2

---

### Phase 5 — Remove Device Status tab (low-medium, grep sweep)
**Files**: `affilabs/affilabs_sidebar.py`, `affilabs/ui_mixins/_device_status_mixin.py`, `affilabs/coordinators/hardware_event_coordinator.py`, any file referencing `tab_indices["Device Status"]`

- Remove Device Status tab from `AffilabsSidebar`
- Move `DeviceStatus` widget into Settings tab as collapsed "Hardware Info" section
- Move controller/firmware/COM port detail to power button tooltip
- Remove `tab_indices["Device Status"]` key
- Grep all `"Device Status"` references and update
- Method tab confirmed as tab 0 default

**Must be preceded by Phase 1** — or subunit health info disappears entirely.

---

### Phase 6 — Adaptive guidance (depends on Phases 1–5 complete)
**Files**: `affilabs/services/user_profile_manager.py`, new `affilabs/coordinators/guidance_coordinator.py`

- Add `get_guidance_level(username: str = None) -> str` to `UserProfileManager` — wraps existing `get_title()` which already returns `(UserTitle, exp_count)`. Three-line implementation.
- **Signal caveat (resolved)**: `UserProfileManager` is **not** a `QObject` — it cannot hold Qt Signals. `profile_changed` is not feasible as a Qt Signal on the manager. Instead, `GuidanceCoordinator` hooks `set_current_user` via a post-call callback registered at init: `user_profile_manager.on_user_changed = coordinator._on_user_changed`. `UserProfileManager.set_current_user()` calls `self.on_user_changed(username)` if set. No `QObject` inheritance needed.
- **User selector at launch (resolved — Option A)**: On launch, if `len(get_profiles()) > 1`, show a compact non-blocking modal (centred on the loading screen) — *"Who's running today's experiment?"* dropdown + OK. Hardware scan starts immediately in parallel; user selection does not block it. If only one profile exists, skip entirely.
- Create `GuidanceCoordinator` — checks guidance level + hint flags, shows/hides hint elements per stage signal
- See `docs/future_plans/ADAPTIVE_GUIDANCE_PLAN.md` for per-stage detail

---

## Files Affected Summary

| File | Change |
|------|--------|
| `affilabs/affilabs_sidebar.py` | Remove Device Status tab; remove Spectroscopy tab (not added); rename Export → User+Export; reorder indices to 0/1/2 |
| `affilabs/sidebar_tabs/AL_settings_builder.py` | Remove User Management section; remove Live Spectroscopy section |
| `affilabs/sidebar_tabs/AL_export_builder.py` | Add user profile card at top |
| `affilabs/sidebar_tabs/AL_method_builder.py` | Remove Active Cycle Card + Queue (move to Live right panel) |
| new `affilabs/widgets/live_right_panel.py` | Right panel: Active Cycle Card + Queue + elapsed time |
| new `affilabs/widgets/live_context_panel.py` | Left contextual panel: Spectroscopy + Injection sub-panels |
| `affilabs/affilabs_core_ui.py` | Add subunit dots to status bar; wire Live page layout with right + left panels |
| `affilabs/ui_mixins/_device_status_mixin.py` | Update subunit dot writes to status bar widgets |
| `affilabs/coordinators/hardware_event_coordinator.py` | `_pulse_calibrate_button` — ensure it still finds button in Settings tab |
| `affilabs/services/user_profile_manager.py` | Add `get_guidance_level()`, `profile_changed` signal (Phase 6) |
| `docs/ui/UI_COMPONENT_INVENTORY.md` | Full §3 rewrite after implementation |
| `docs/ui/UI_STATE_MACHINE.md` | Update subunit dot section; update Active Cycle Card location |
| `docs/ui/UX_USER_JOURNEY.md` | Stage 4: Mark Injection button now prominent (Phase 3 delivers this) |

---

## Key Constraints

- `tab_indices` is accessed by **name key** — safe to renumber as long as string keys are updated
- `SpectroscopyPresenter` writes to `main_window.transmission_curves` and `main_window.raw_data_curves` (plain lists of pyqtgraph `PlotDataItem`). These are aliased from wherever the plots are built. Phase 3 changes the alias source from `AL_settings_builder` to `LiveContextPanel`. Attribute names on `main_window` are unchanged — presenter needs zero edits.
- `_pulse_calibrate_button` finds `full_calibration_btn` on the sidebar — button stays in Settings tab; attribute name must remain on `sidebar`
- Device Status tab removal (Phase 5) must be preceded by Phase 1 (dots to status bar)
- Active Cycle Card must be **pre-built** in `AffilabsSidebar._setup_ui()` as `self.active_cycle_card = QFrame()` *before* tab builders run — cannot be re-parented from inside a tab layout after the fact. `AL_method_builder` is updated to `addWidget` the pre-built card instead of constructing it.
- Phase order is not strictly serial: Phases 2 and 3 can be done together; Phase 4 is independent of 2/3

---

## Edits Tab Dovetail (resolved)

- `export_sidebar` in Edits tab is **removed** as part of this redesign (Phase 4)
- Sidebar User+Export tab = configure defaults (format, target, destination)
- Edits toolbar = execute export for the current session
- Load Data button moves from Edits table header to User+Export sidebar tab
- The left contextual panel pattern (`live_context_panel.py`) is extracted from the same Edits `export_sidebar` mechanism — same show/hide pattern, different content

---

## Out of Scope (this redesign)

- Flow tab changes (P4PRO/P4PROPLUS) — deferred
- Injection panel for P4PRO/P4PROPLUS (valve, pump controls) — deferred
- Fluidics subunit dot in status bar — deferred until P4PRO scope
- Analyze tab — not touched
