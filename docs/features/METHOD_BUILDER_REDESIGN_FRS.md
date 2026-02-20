# Method Builder — Redesign FRS
**Version**: 1.0  
**Status**: Implemented ✅  
**Last Updated**: 2026-02-21  
**Source file**: `affilabs/widgets/method_builder_dialog.py` (`MethodBuilderDialog`)  
**Related**: `affilabs/widgets/cycle_template_dialog.py`, `affilabs/services/cycle_template_storage.py`

---

## Problem Statement

The current Method Builder dialog has **7 distinct UI regions** packed into a 700×650px window, presenting users with design decisions before they can write a single step:

| Issue | Detail |
|-------|--------|
| **Mode split** | Two input tabs (Easy Mode form, Power Mode text). User must choose a mode before doing anything. Easy Mode still requires "Insert to Power Mode →" to actually use a step. |
| **Two Sparq surfaces** | `@spark` inline text commands in Power Mode AND a separate floating `SparkMethodPopup` chat dialog. Neither is discoverable without reading help text. |
| **Three-step build path** | Easy Form → insert to Power Mode → click `→` button → cycle appears in queue. Excessive for adding one step. |
| **Template picker is a separate window** | `CycleTemplateDialog` is opened externally, not integrated into builder flow. |
| **Settings buried** | Mode, Hardware, Detection combos placed below the queue table — below the fold on most screens. |
| **→ arrow button** | Center 56px button that "builds" the method feels like a publish step, but is actually just parsing — confusing intent. |
| **Dual tab panels** | Input has tabs AND the queue has tabs. Two tab-switchers in one dialog. |

**User failure mode**: Users open the dialog, see two tabs + a text field with a 14-line placeholder, and either ask Sparq for help or close the dialog and write cycles manually in the sidebar.

---

## Design Goals

1. **Zero decisions to start** — landing state puts the user into a method immediately
2. **One place to ask Sparq** — single, always-visible input at the bottom of the dialog
3. **The list IS the method** — no separate "build then push" two-stage path
4. **Templates are first-class** — not a separate window; they are the starting point
5. **Advanced settings are not buried, but are secondary** — visible on demand

---

## Proposed Layout (3-Zone)

```
┌──────────────────────────────────────────────────────────────────────┐
│  ┌── Zone A: Header ────────────────────────────────────────────────┐ │
│  │  Build Method  [Untitled Method____]      [👤 Lucia ▾]   [P4SPR] │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌── Zone B: Template Gallery (landing state only) ────────────────┐ │
│  │  Start from:                                                     │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────┐  │ │
│  │  │  Binding     │ │  Kinetics    │ │ Amine        │ │ Custom │  │ │
│  │  │  5min, A, C  │ │ assoc+dissoc │ │ Coupling     │ │ (blank)│  │ │
│  │  │  Regeneration│ │ Regeneration │ │ Full workflow │ │        │  │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────┘  │ │
│  │  [🔍 Browse all templates…]                                       │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│   ↑ Hidden once any step is in the list                              │
│                                                                      │
│  ┌── Zone C: Step List (the method) ───────────────────────────────┐ │
│  │  #   Type          Duration   Channel   Concentration  Contact   │ │
│  │  1   Baseline      5 min      ALL                               × ↑↓│
│  │  2   Binding       15 min     A         100 nM         180 s    × ↑↓│
│  │  3   Regeneration  30 sec     ALL       50 mM                   × ↑↓│
│  │                                                                  │ │
│  │  [+ Add step ▾]   Total: 20 min 30 sec                          │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌── Zone D: Sparq bar ─────────────────────────────────────────────┐│
│  │  ⚡ [Ask Sparq: e.g. "add 3 kinetic cycles" or "titration"___] [Ask]││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                      │
│  ▸ Mode: Manual   Detection: Auto   [⚙ Change settings]             │
│                                                                      │
│  [Cancel]                               [Add to Queue]  [▶ Start]   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Zone Specifications

### Zone A — Header

| Field | Default | Behaviour |
|-------|---------|-----------|
| Method name | Template name, or "Untitled Method" for Custom | Editable inline `QLineEdit` |
| Operator | Current user from `UserProfileManager` | `QComboBox`, only visible if >1 profile exists |
| Hardware badge | `P4SPR` / `P4PRO` / `P4PROPLUS` | Read-only `QLabel`, no border |

**Change from current**: Method name and Operator move into a single compact header row. Hardware badge stays, operator combo is **hidden when only one profile exists** (reduces UI noise for single-user setups).

---

### Zone B — Template Gallery (landing state)

Displayed **only when the step list is empty**. Collapses/hides as soon as the first step is added.

**Built-in template cards** (4 visible, scrollable if more):

| Card | Steps generated |
|------|----------------|
| **Binding** | Baseline 5min ALL → Binding 15min [A] → Regeneration 30sec ALL |
| **Kinetics** | Baseline 2min ALL → Kinetic 2min [A] 100nM contact 120s → Baseline 10min ALL → Regeneration 30sec ALL |
| **Amine Coupling** | Full 10-step immobilization + 5 binding cycles |
| **Custom** | Opens blank step list with one empty row |

**[🔍 Browse all templates…]** button opens the existing `CycleTemplateDialog` (unchanged) for user-saved templates.

**Change from current**: Templates are now the **entry point** of the dialog, not a separate modal. `CycleTemplateDialog` still exists for the library, but is no longer the primary template surface.

---

### Zone C — Step List

Replaces the dual-tab input system (Easy Mode form + Power Mode text) and the dual-tab queue (Overview + Details). The step list is **both the input and the queue** — no intermediate "build" step.

**Columns**:

| Col | Content | Editable | Notes |
|-----|---------|----------|-------|
| # | Row number | No | Auto-numbered |
| Type | Cycle type | Yes — `QComboBox` | Binding / Baseline / Kinetic / Regeneration / Rinse / Immobilization / Other |
| Duration | `QDoubleSpinBox` + unit `QComboBox` (s/min/h) | Yes | |
| Channel | `QComboBox` (A / B / C / D / ALL / AC / BD) | Yes | Hidden for Baseline/Regeneration if hardware is P4SPR |
| Concentration | `QLineEdit` (free text: `100nM`, `50mM`) | Yes | Hidden when not applicable |
| Contact | `QSpinBox` seconds | Yes | Only show for Binding/Kinetic |
| Actions | [×] [↑] [↓] | — | Delete row, move up, move down |

**Footer of step list**:
- `[+ Add step ▾]` — dropdown with quick-add options: Baseline, Binding, Regeneration, Kinetic, Custom row. This **replaces Easy Mode** for structured entry.
- Total duration label (e.g., `Total: 20 min 30 sec`) — live, updates on every change.

**Keyboard/shortcut**:
- `Delete` key on selected row → confirm delete (same as [×])
- `Ctrl+Z` / `Ctrl+Y` → undo/redo (existing behaviour, maps to same handlers)

**Change from current**: 
- **Eliminates** the Easy Mode form tab
- **Eliminates** the Power Mode text tab  
- **Eliminates** the `→` arrow button  
- **Eliminates** the dual-tab queue (Overview + Details collapse into one editable list)
- Power Mode text input is preserved as a **developer/advanced feature** behind a `⋯ Text mode` link that slides in a panel below the list — not a tab

---

### Zone D — Sparq Bar

A single, persistent **one-line input strip** at the bottom of the dialog (above the footer buttons).

```
⚡  [Ask Sparq: e.g. "add 3 kinetic cycles", "titration", "amine coupling 5x"  ___]  [Ask]
```

**Behaviour**:
- User types a query and presses Enter or clicks [Ask]
- Sparq generates cycles and **appends them to the step list** (doesn't replace — user can undo)
- If Sparq cannot parse the query, shows a one-line inline hint: `"Try: binding, kinetics, titration, amine coupling, build N"`
- [Ask] button label changes to `⏳` while thinking, back to `Ask` on completion

**Change from current**:
- Eliminates `@spark` text-command syntax from the Power Mode text field (hidden, undiscoverable)
- Eliminates the separate `SparkMethodPopup` floating chat dialog
- The Sparq bar is **always visible**, never behind a button click or tab

---

### Settings Disclosure

```
▸ Mode: Manual   Detection: Auto   [⚙ Change settings]
```

- Collapsed single line showing current values of Mode + Detection
- Click `▸` or `[⚙ Change settings]` to expand an inline panel with the full combos
- Hardware label always visible as a badge in Zone A (not here)

**Change from current**: Mode/Detection combos removed from their current buried position below the queue. Promoted to a visible summary, with full controls on demand.

---

### Footer Buttons

```
[Cancel]                                [Add to Queue]   [▶ Start]
```

| Button | Action |
|--------|--------|
| Cancel | Close dialog, discard changes |
| Add to Queue | Push all steps to main cycle queue (same as current "Push to Queue") |
| ▶ Start | Push to queue + immediately start run |

**Change from current**: Removes "Save Method" from footer (method is auto-saved to the recent methods list on push). Removes "Copy Schedule" from footer (available from within the step list via right-click or a `…` menu on the queue panel).

---

## State Transitions

```
Open dialog
  ↓
Zone B (Template Gallery) visible
  ↓ user clicks a template card
Steps pre-populated in Zone C, Zone B collapses
  ↓ user edits steps / asks Sparq
Steps updated live in Zone C
  ↓ user clicks [Add to Queue] or [▶ Start]
Steps pushed to cycle queue → dialog closes
```

**If user clicks "Custom"**:
```
Zone B collapses → Zone C shows with one blank row selected → cursor in Type column
```

---

## What Gets Removed

| Removed element | Replacement |
|----------------|-------------|
| Easy Mode tab | `[+ Add step ▾]` dropdown in step list footer |
| Power Mode text tab | `⋯ Text mode` advanced link (hidden by default) |
| `→` arrow build button | Eliminated — list IS the queue |
| `SparkMethodPopup` floating dialog | Zone D Sparq bar |
| `@spark` / `!save` / `@preset_name` text commands | Sparq bar + right-click menu on step rows |
| Method queue dual tabs (Overview + Details) | Single editable step list (shows all columns) |
| Settings combos below table | Settings disclosure strip (Zone D expanded) |
| "Insert to Power Mode →" button in Easy Mode | Eliminated |
| 14-line notes placeholder text | Eliminated — no text field, no placeholder needed |

---

## What Gets Preserved (unchanged)

- `CycleTemplateStorage` — unchanged, still backs the template system
- `CycleTemplateDialog` — unchanged, opened by [🔍 Browse all templates…]
- `QueuePresetStorage` — unchanged, `!save` command replaced by right-click "Save as template" on any step row
- `SparkAnswerEngine` — unchanged, still backs the Sparq bar
- `_build_cycle_from_text()` — unchanged, used by the text mode panel
- All signals: `method_ready(action, method_name, cycles)` — unchanged
- Hardware model conditioning (`configure_for_hardware`) — unchanged
- Undo/redo, operator change propagation — unchanged

---

## Sparq IQ Impact

| Test item (from UX_WORKFLOW_TEST_PROTOCOL.md) | Expected score change |
|----------------------------------------------|----------------------|
| Stage 4.2 — find injection controls | 2→3 (P4SPR manual injection button more visible in step list) |
| Any method-building scenario (currently untested) | New test items to add in Stage 2/3 |

**New test items to add to protocol**:
- `MB.1` — Without reading help text, can the user start a method from a template in <30 seconds?
- `MB.2` — Can the user add a Binding step using only the `[+ Add step]` dropdown?
- `MB.3` — Can the user ask Sparq to "add kinetics" and see the result in the step list?
- `MB.4` — Can the user push the method to queue and find it in the cycle list?

---

## Implementation Notes

- **File**: `affilabs/widgets/method_builder_dialog.py`
- **Minimum dialog size**: `800 × 600` (slightly wider than current 700 to accommodate step list columns)
- **Zone B template cards**: Use `QFrame` with hover stylesheet + click signal — not `QPushButton`
- **Step list**: `QTableWidget` with custom delegates for inline editing (`QComboBox`, `QDoubleSpinBox` in cells). Existing `method_table` can be repurposed with added/changed columns.
- **Zone D Sparq bar**: New `QLineEdit` + `QPushButton("Ask")` strip. Connect to `_detect_and_respond_to_question()` rewritten to append to step list rather than replace text input.
- **`⋯ Text mode`**: Shows `NotesTextEdit` in a collapsible panel using `QSplitter` or animated `QFrame` height transition. Preserves all text-syntax features for power users.
- **Settings disclosure**: `QToolButton` with `setArrowType` + hidden `QFrame` panel, shown/hidden via `setFixedHeight(0)` animation or `setVisible`.

---

## Implementation Decisions 

1. **Concentration column**: One free-text field per row showing `CH:value units` pairs. Multi-channel concentrations displayed inline (`A:100nM  B:50nM`).
2. **`!save` replacement**: Browse Templates button opens `CycleTemplateDialog`. Template gallery cards load built-in templates directly into step list.
3. **Text mode persistence**: Text mode is one-way — text → step list on "Ask". Toggling back to list view is done via `⋯ Text mode` checkbox; list reflects last-applied text.
4. **P4PROPLUS pump fields**: Contact time column populated from parsed cycles; P4PROPLUS-specific enforcement handled upstream in `_update_internal_pump_visibility()`.

---

## Related Docs

- [METHOD_PRESETS_SYSTEM.md](METHOD_PRESETS_SYSTEM.md) — template storage architecture
- [UX_WORKFLOW_TEST_PROTOCOL.md](../user_guides/UX_WORKFLOW_TEST_PROTOCOL.md) — Sparq IQ test protocol
- [UX_USER_JOURNEY.md](../ui/UX_USER_JOURNEY.md) — Stage 4 (Inject) user needs
- [UI_HARDWARE_MODEL_REQUIREMENTS.md](../ui/UI_HARDWARE_MODEL_REQUIREMENTS.md) — P4SPR vs PRO/PROPLUS column behaviour
