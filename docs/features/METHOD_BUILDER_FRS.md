# Method Builder — Feature Reference Spec

**Source file:** `affilabs/widgets/method_builder_dialog.py`
**Class:** `MethodBuilderDialog(QDialog)`

---

## Overview

The Method Builder is a modal dialog for composing ordered lists of SPR experiment steps (Cycles) before pushing them to the Run Queue. It operates independently of live acquisition — cycles are staged locally, then emitted in batch when the user pushes to queue or saves.

---

## Architecture

### Signals

| Signal | Payload | When emitted |
|--------|---------|--------------|
| `method_ready` | `(str action, str name, list[Cycle] cycles)` | User clicks "Push to Queue" — action is always `"queue"` |
| `method_saved` | `(str name, str file_path)` | User saves method to JSON file successfully |

`method_ready` is connected in `_pump_mixin.py` → `_on_method_ready()`, which inserts cycles into the main run queue.
`method_saved` is connected in `_pump_mixin.py` → `_on_method_saved()`, which expands the Run Queue sidebar panel.

### State

| Attribute | Type | Purpose |
|-----------|------|---------|
| `_local_cycles` | `list[Cycle]` | Staged cycles (not yet in main queue) |
| `_preset_storage` | `CycleTemplateStorage` | Loads/saves named presets |
| `_user_manager` | `UserProfileManager` | Operator list + current user |
| `_answer_engine` | `SparkAnswerEngine \| None` | AI engine (initialized in background thread) |
| `_waiting_for_response` | `bool` | True when dialog awaits user answer to an `@spark` question |
| `_pending_command` | `str \| None` | Which command triggered the question flow |
| `_last_ai_text` | `str` | Last AI response (for Insert button in SparkMethodPopup) |

---

## UI Layout — 3-Zone Design

### Zone A — Header
- **Method name** — editable `QLineEdit`, defaults to `"Untitled Method"`
- **Operator selector** — `QComboBox` from `UserProfileManager.get_profiles()`; hidden if only one profile exists
- **Hardware badge** — `QLabel` set by `configure_for_hardware()`
- **Mode selector** — `QComboBox`: `["Manual", "Semi-Automated"]`; locked/disabled for P4SPR (Manual only)
- **Detection selector** — `QComboBox`: `["Auto", "Priority", "Off"]`

### Zone B — Step Builder (left panel)
Two input modes available via toggle:

1. **Template Gallery** — shown when `_local_cycles` is empty; 5 built-in template cards
2. **Text Mode panel** — power-user multi-line text input (shown/hidden by toggle button)
3. **Sparq Bar** — AI-powered single-line input at the top of Zone B; type a prompt, hit "Ask"

### Zone C — Step List (right panel)
- `method_table` — 6-column `QTableWidget` showing staged cycles
- **Columns:** `Type`, `Duration`, `Channel`, `Concentration`, `Contact time`, `Note`
- **Controls:** Delete, Move Up, Move Down, Undo, Redo, Clear All
- **Footer:** Push to Queue, Save Method, Load Method buttons
- **Overnight Mode** checkbox — sets `settings.OVERNIGHT_MODE` global

---

## Cycle Types (P4SPR / Manual Injection)

Eight canonical types. Defined in `affilabs/widgets/ui_constants.py` → `CycleConfig.TYPES` and `CycleTypeStyle.MAP`.

| Type | Abbrev | Color | Injection | Contact time | Notes |
|------|--------|-------|-----------|--------------|-------|
| Baseline | BL | `#007AFF` | None | None | Buffer flow, reference period |
| Binding | BN | `#FF9500` | Yes (simple/partial) | **300 s default** | Manual injection; 8.5 min default duration |
| Kinetic | KN | `#5856D6` | Yes (simple/partial) | 120 s default | Association + dissociation window |
| Regeneration | RG | `#FF3B30` | Yes (simple) | 30 s default | Strips bound analyte |
| Immobilization | IM | `#AF52DE` | Yes (simple) | 300 s default | Ligand attachment |
| Blocking | BK | `#FF2D55` | None | None | Block unreacted sites (e.g. ethanolamine) |
| Wash | WS | `#00C7BE` | None | None | Manual rinse, no timed injection |
| Other | OT | `#636366` | None | None | Custom step (activation, etc.) |

### Binding Cycle Design (P4SPR)

A single Binding cycle is an **8.5-minute combined window** that packages:

| Phase | Duration | What happens |
|-------|----------|--------------|
| Injection prep | ~20 s | System prompts user; `injection_delay = 20 s` |
| Manual injection | Variable | User pipettes analyte into flow cell; system detects onset |
| Contact time | **300 s (5 min)** | Timer runs; user keeps sample flowing; contact timer dialog shown |
| Buffer slack | ~3.5 min | Unstructured time for user to prepare next step, flush, etc. |

The 3.5 min buffer is intentional UX slack — P4SPR users work alone at the bench. The cycle ends on the hard timer regardless of what the user does in that window.

**Regen, Wash, and Baseline after a Binding step are separate queue entries** — they are not sub-phases inside a Binding cycle. A typical binding run is:

```
Baseline 5min
Binding 8.5min [A:100nM] contact 300s
Regeneration 30sec [ALL:50mM]
Baseline 2min
```

---

## Text Syntax (Power Mode / Sparq Bar)

Cycles are entered as plain text lines. One line = one cycle. Comments (text after `#`) are preserved as the cycle's `note` field and never parsed.

### Basic Format

```
<type> <duration><unit> [<channel>:<concentration><unit>] [contact <time><unit>] [# note]
```

### Supported Cycle Types

| Keyword(s) | Cycle type |
|------------|------------|
| `baseline`, `bl` | Baseline |
| `binding`, `bn`, `association`, `inject` | Binding |
| `kinetic`, `kn`, `kinetics` | Kinetic |
| `regeneration`, `rg`, `regen`, `clean` | Regeneration |
| `immobilization`, `im`, `immob`, `immobilize` | Immobilization |
| `blocking`, `bk`, `block` | Blocking |
| `wash`, `ws` | Wash |
| `other`, `ot`, `custom` | Other |
| `concentration`, `cn` | Binding (legacy alias — old saved files) |

### Duration Syntax

| Format | Example | Result |
|--------|---------|--------|
| Minutes | `5min`, `5m` | 5 min |
| Decimal | `8.5min` | 8.5 min |
| Seconds | `30sec`, `30s` | 0.5 min |
| Hours | `2h`, `2hr`, `2hours` | 120 min |
| Overnight | `overnight` | 480 min (8 h) |

Default if unparseable: **5 min**.

### Concentration Tags

Brackets are optional. Uppercase or lowercase channel letters accepted.

| Format | Expands to |
|--------|------------|
| `A:100nM` | Channel A = 100 nM |
| `[A:100nM]` | Same (brackets stripped) |
| `ALL:50mM` | Channels A, B, C, D = 50 mM |
| `BD:5nM` | Channels B, D = 5 nM |
| `ABCD:100,50,25,10` | A=100, B=50, C=25, D=10 (comma-mapped in order) |

**Valid concentration units:** `nM`, `µM`, `uM`, `mM`, `M`, `pM`, `µg/mL`, `ug/mL`, `ng/mL`, `mg/mL`, `g/L`

### Contact Time

```
Binding 8.5min [A:100nM] contact 300s
```

`contact <value><unit>` sets the injection contact time. Defaults if omitted:

| Cycle type | Default contact time |
|------------|---------------------|
| Binding | **300 s (5 min)** |
| Kinetic | 120 s (2 min) |
| Regeneration | 30 s |
| Immobilization | 300 s (5 min) |
| Baseline / Wash / Blocking / Other | None (no injection) |

### Injection Method Auto-Rules

| Cycle type | `injection_method` |
|------------|-------------------|
| Binding, Kinetic | `"partial"` (if `partial` keyword in text), else `"simple"` |
| Regeneration, Immobilization | `"simple"` |
| Baseline, Wash, Blocking, Other | `None` (no injection) |

`injection_delay` is always **20 s**.

### Other Parseable Keywords

| Keyword | Effect |
|---------|--------|
| `partial` | Sets `injection_method = "partial"` |
| `manual injection` | Sets `manual_injection_mode = "manual"` |
| `automated injection` | Sets `manual_injection_mode = "automated"` |
| `detection priority` | Overrides detection to `"priority"` for this cycle |
| `detection off` | Overrides detection to `"off"` for this cycle |
| `detection auto` | Overrides detection to `"auto"` for this cycle |
| `channels AC`, `channels BD`, etc. | Explicitly sets `target_channels` for this cycle |

### `#N` Modifier Syntax

After adding cycles, modifiers can be applied to specific steps by number:

```
#3 contact 60s        → Apply to step 3 only
#all flow 50          → Apply to all steps
#1-5 concentration 100nM  → Apply to steps 1 through 5
```

Modifiers are processed by `_apply_modifiers()` and `_apply_single_modifier()`.

---

## `@` Commands (Power Mode Input)

| Prefix | Effect |
|--------|--------|
| `@spark <question>` | Routes question to Sparq AI, shows response suggestion |
| `@<preset_name>` | Loads a saved named preset into the step list |

---

## Template Gallery

Five built-in cards shown when the step list is empty:

| Template | Steps | Description |
|----------|-------|-------------|
| Binding | 4 | Baseline 5min → Binding 8.5min contact 300s → Regen 30sec → Baseline 2min |
| Kinetics | 5 | Baseline 2min → Kinetic 5min contact 120s → Baseline 10min (dissociation) → Regen 30sec → Baseline 2min |
| Amine Coupling | 11 | Baseline → EDC/NHS → Wash → Immobilization → Wash → Blocking → Wash → Baseline → Binding → Regen → Baseline |
| Titration | 13 | Baseline 5min + 4× (Binding 8.5min at 10/50/100/500 nM + Regen + Baseline) |
| ✏ Custom | 0 | Blank step list |

Cards defined as `lines: list[str]` in `_setup_ui()`, loaded via `_on_template_card_clicked()`.

---

## Sparq Bar

Single-line `QLineEdit` + "Ask" button at the top of Zone B.

Pattern matching (`_try_sparq_patterns`):

| Prompt pattern | Generated steps |
|----------------|-----------------|
| `build N` | Baseline 5min + N × (Binding 8.5min contact 300s + Regen 30sec + Baseline 2min) |
| `titration`, `dose response`, `serial dilution` | 4-concentration series: 10, 50, 100, 500 nM (8.5min each) + baseline/regen |
| `kinetics`, `dissociation`, `off rate` | Baseline → Kinetic 5min → Baseline 10min (dissociation) → Regen → Baseline |
| `amine coupling [N]` | Full amine coupling protocol with N binding cycles (default 3) |
| `baseline`, `equilibrate` | `Baseline 5min` |
| `regeneration`, `regen`, `clean`, `strip` | `Regeneration 30sec [ALL:50mM]` |
| `binding`, `injection`, `sample` | `Binding 8.5min [A:100nM] contact 300s` |
| `immobilize`, `ligand` | `Immobilization 10min [A:50µg/mL] contact 300s` |
| `wash`, `rinse` | `Wash 30sec` |
| `block` | `Blocking 4min` |

Falls back to `SparkAnswerEngine.generate_answer(context="method_builder")` if no pattern matches.

---

## Hardware Configuration

`configure_for_hardware(hw_name: str, has_affipump: bool)` — called by main app on dialog open.

| Hardware | Mode combo | Pump fields |
|----------|-----------|-------------|
| P4SPR (no pump) | Locked to "Manual" | Hidden |
| P4SPR + AffiPump | "Semi-Automated" available | Shown |
| P4PRO | Defaults to "Semi-Automated" | Shown |
| P4PROPLUS | Defaults to "Semi-Automated" | Shown (internal pump UI) |

---

## Save / Load / Push

### Push to Queue
`_on_push_to_queue()` — emits `method_ready("queue", name, cycles)` then clears `_local_cycles` and closes the dialog. The Run Queue panel does **not** open automatically on push — it opens only when the user saves a method file.

### Save Method
`_on_save_method()` — opens `QFileDialog` defaulting to `~/Documents/Affilabs Methods/<username>/`. Writes:

```json
{
  "version": "1.0",
  "name": "...",
  "author": "...",
  "description": "",
  "cycle_count": N,
  "created": <unix_timestamp>,
  "cycles": [<Cycle.to_dict()>, ...]
}
```

Emits `method_saved(name, file_path)` on success → triggers Run Queue sidebar expansion.

### Load Method
`_on_load_method()` — opens `QFileDialog`, reads JSON, converts via `Cycle.from_dict()`. Prompts for confirmation before replacing an existing unsaved method.

---

## Known Issues / Review Points

1. **`description` field always empty** — `_on_save_method()` writes `"description": ""` unconditionally. No UI widget collects a description.

2. **Templates hardcode `[A:100nM]`** — All built-in templates and Sparq patterns default to channel A. For experiments using other channels, the user must edit the generated steps.

3. **`injection_delay = 20.0` is always hardcoded** — No UI control for injection delay. All cycles use 20 s.
