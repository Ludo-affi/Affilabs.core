# Adaptive Guidance Plan — Affilabs.core v2.1

> **Status**: Approved design, not yet implemented
> **Depends on**: SIDEBAR_REDESIGN_PLAN.md Phases 1–5 complete
> **Scope**: P4SPR (manual injection). Flow/automated method deferred.
> **Goal**: First-time users are guided through every step. Experienced users see a clean, fast UI with no hand-holding.

---

## Guidance Levels

Derived from `experiment_count` via `UserProfileManager.get_title()` — no new data needed.

| Tier | Experiments | Guidance level | Philosophy |
|------|-------------|----------------|------------|
| Novice | 0–4 | **Full** | Every stage has a visible label, inline hint, and one-time tooltip |
| Operator | 5–19 | **Standard** | Stage labels remain; one-time hints suppressed after first dismissal |
| Specialist | 20–49 | **Minimal** | Stage labels gone; clean UI; no hints |
| Expert | 50–99 | **Minimal** | |
| Master | 100+ | **Minimal** | |

`get_guidance_level(username)` → `"full"` / `"standard"` / `"minimal"` — proposed addition to `UserProfileManager`.

Guidance level is evaluated **at app launch** after the user is identified (Phase 2 of init, before hardware connect). It does not change mid-session even if `experiment_count` increments.

---

## Stage-by-Stage Guidance Behaviour

### Stage 1 — CONNECT

| Element | Full (Novice) | Standard (Operator) | Minimal (Specialist+) |
|---------|--------------|--------------------|-----------------------|
| Power button hint | Inline label below button: *"Click to connect your instrument"* — removed after first successful connect | Not shown | Not shown |
| Searching state | Elapsed timer + *"Searching… Ns"* (already implemented) | Same | Same |
| Subunit labels | Plain language: *"Sensor: Ready"* / *"Sensor: Warming up"* | Same | Same (always plain language — not guidance-gated) |
| Post-connect nudge | Sidebar pulses calibrate button 3× (already implemented) | Same | Same |

**One-time flag**: `hint_connect_shown` — stored in user profile JSON. Once dismissed, never shown again regardless of tier.

---

### Stage 2 — CALIBRATE

| Element | Full | Standard | Minimal |
|---------|------|----------|---------|
| Stage label | *"Step 2: Calibrate"* badge on calibrate button frame | Not shown | Not shown |
| Inline hint | *"Calibration captures your S-pol reference. Required before every experiment."* — one-time, shown below button | Not shown | Not shown |
| Pre-cal dialog | Water warning (already implemented — always shown, not guidance-gated) | Same | Same |
| Progress messages | Verbose: *"Reading channel A…"*, *"Setting polarizer…"* | Brief: *"Calibrating…"* | Brief |
| Failure message | Actionable: *"Signal too weak — check fiber connection and retry"* (always shown — not guidance-gated) | Same | Same |
| Post-cal auto-switch | Sidebar switches to Method tab (already implemented) | Same | Same |

**One-time flag**: `hint_calibrate_shown`

---

### Stage 3 — ACQUIRE

| Element | Full | Standard | Minimal |
|---------|------|----------|---------|
| Stage label | *"Step 3: Watching your baseline"* — visible in right panel header while acquiring, pre-injection | Not shown | Not shown |
| "What am I seeing?" panel | Collapsible panel in Live page right panel: *"Flat baseline = instrument ready for injection"* — dismissable, shown on first acquire | Not shown | Not shown |
| Stability badge | *"Stabilizing…"* → *"Ready to inject ✓"* (already implemented — always shown) | Same | Same |
| Signal IQ dots | Channel A/B/C/D quality dots (already implemented — always shown) | Same | Same |
| Baseline hint label | Graph annotation: *"Flat baseline = instrument ready for injection"* (already implemented — always shown until injection) | Same | Same |

**One-time flag**: `hint_acquire_shown`

---

### Stage 4 — INJECT

| Element | Full | Standard | Minimal |
|---------|------|----------|---------|
| Stage label | *"Step 4: Inject your sample"* — shown in Injection panel header when panel is open | Not shown | Not shown |
| Injection panel nudge | Injection panel icon (💉) pulses once when stability badge turns green — draws eye to it | Not shown | Not shown |
| First injection tooltip | *"SPR signals decrease on binding — a drop means your sample is working"* (already implemented — one-time, always shown regardless of tier) | Same | Same |
| Mark Injection button | Prominent, full-width (already planned in Live page left panel — not guidance-gated) | Same | Same |
| Contact timer | Always visible when panel open — not guidance-gated | Same | Same |

**One-time flag**: `hint_inject_shown`
**Note**: The first-injection tooltip is already implemented in `flag_manager.py` and fires for all tiers — keep as-is.

---

### Stage 5 — RECORD

| Element | Full | Standard | Minimal |
|---------|------|----------|---------|
| Stage label | *"Step 5: Start recording"* — shown as a badge on Record button frame, pre-first-record | Not shown | Not shown |
| Record nudge | Record button pulses once after first injection flag is placed | Not shown | Not shown |
| Recording indicator | Pulsing red dot + *"⏺ Saving to: filename.xlsx"* (already implemented — always shown) | Same | Same |
| Post-stop toast | *"Recording saved"* with Open/View Results (already implemented — always shown) | Same | Same |

**One-time flag**: `hint_record_shown`

---

### Stage 6 — EXPORT & ANALYZE

| Element | Full | Standard | Minimal |
|---------|------|----------|---------|
| Post-recording nav | Toast includes *"View results →"* (already implemented — always shown) | Same | Same |
| Edits tab tooltip | *"A cycle is one complete injection + wash sequence…"* (already implemented — one-time, all tiers) | Same | Same |
| Export CTA label | *"Step 6: Export your data"* — shown once as label above Export button in User+Export tab | Not shown | Not shown |

**One-time flag**: `hint_export_shown`

---

## What "One-Time" Means

Each hint has a flag stored in the user's profile JSON (`hints_shown` dict). Once the user dismisses or completes the action that triggers the hint, the flag is set and the hint never reappears — even if the user stays at Novice tier.

```json
"hints_shown": {
    "hint_connect_shown": true,
    "hint_calibrate_shown": false,
    "hint_acquire_shown": false,
    "hint_inject_shown": true,
    "hint_record_shown": false,
    "hint_export_shown": false
}
```

This means a Novice user who has done 3 experiments will only see hints for stages they haven't completed yet — not the same hints every time.

---

## User Selection at Launch

Currently the app loads the last-used user silently. For guidance to work correctly, the user must be identified **before** hardware connect — so the guidance level is known before any UI state transitions fire.

**Proposed change**: On launch, if more than one user profile exists, show a compact user selector before the main window is fully interactive:

- ~~Option A (preferred)~~: Small modal at centre of splash/loading screen — *"Who's running today's experiment?"* with a dropdown + OK button. Dismisses immediately; does not block hardware scanning.
- ~~Option B~~: User selector baked into the connection flow — shown after power button click, before hardware scan begins.

> **Decision (resolved): Option A.** Hardware scan starts in parallel immediately — user selection does not delay connect.

**If only one profile exists**: skip selector entirely, load silently (current behaviour).

---

## Implementation Components

### 1. `UserProfileManager` additions
**File**: `affilabs/services/user_profile_manager.py`

```python
def get_guidance_level(self, username: str = None) -> str:
    """Returns 'full', 'standard', or 'minimal'."""
    title, _ = self.get_title(username or self.current_user)
    if title.value == "Novice":
        return "full"
    elif title.value == "Operator":
        return "standard"
    return "minimal"

def is_hint_shown(self, hint_key: str, username: str = None) -> bool:
    ...

def mark_hint_shown(self, hint_key: str, username: str = None) -> None:
    ...
```

> **Signal caveat**: `UserProfileManager` is not a `QObject` — it cannot carry Qt Signals. Instead of `profile_changed = Signal(str)`, use a plain callback slot: `user_profile_manager.on_user_changed = coordinator._on_user_changed` registered at `GuidanceCoordinator.__init__`. `UserProfileManager.set_current_user()` calls `self.on_user_changed(username)` if the attribute is set. No `QObject` inheritance required.

### 2. `GuidanceCoordinator` (new)
**File**: `affilabs/coordinators/guidance_coordinator.py`

Responsibilities:
- Holds reference to `UserProfileManager`
- Listens to app state signals: `hardware_connected`, `calibration_complete`, `acquisition_started`, `injection_flag_placed`, `recording_started`, `recording_stopped`
- On each signal: checks guidance level + hint flags → shows/hides the appropriate hint element
- Owns no widgets directly — calls show/hide methods on the widgets via the main window reference

### 3. Hint widgets (inline, not popups)
All hints are **inline labels or badges** — not modal dialogs, not floating tooltips that block interaction.

- Stage label badge: `QLabel` with rounded background, positioned above or beside the relevant control
- "What am I seeing?" panel: `CollapsibleSection` in Live page right panel — default collapsed for Standard/Minimal, default expanded for Full on first acquire
- Injection panel nudge: CSS animation on the 💉 icon — brief pulse, not repeated

### 4. `hints_shown` storage
Added to existing user profile JSON structure. `mark_hint_shown()` writes immediately (same pattern as `increment_experiment_count()`).

---

## What Is NOT Guidance-Gated

These elements are always shown regardless of tier — they are operational signals, not educational hints:

- Subunit dots in status bar
- Stability badge (*"Stabilizing…"* / *"Ready to inject ✓"*)
- Signal IQ dots on channel buttons
- Baseline hint label on graph (hides on first injection — this is functional, not educational)
- Recording indicator (pulsing dot + filename)
- Post-stop toast
- Pre-calibration water warning dialog
- Calibration failure messages
- First-injection binding direction tooltip (already one-time in `flag_manager.py`)
- Edits tab cycle explanation tooltip (already one-time in `navigation_presenter.py`)

---

## Files Affected

| File | Change |
|------|--------|
| `affilabs/services/user_profile_manager.py` | Add `get_guidance_level()`, `is_hint_shown()`, `mark_hint_shown()`, `on_user_changed` callback hook; add `hints_shown` dict to profile JSON schema |
| new `affilabs/coordinators/guidance_coordinator.py` | GuidanceCoordinator — listens to state signals, drives hint visibility |
| `affilabs/affilabs_core_ui.py` | Launch-time user selector (if >1 profile); wire GuidanceCoordinator |
| `affilabs/widgets/live_right_panel.py` | "What am I seeing?" CollapsibleSection; stage label badges |
| `affilabs/widgets/live_context_panel.py` | Stage label badges on Spectroscopy + Injection panels |
| `affilabs/sidebar_tabs/AL_export_builder.py` | Export CTA stage label (Stage 6, Full only) |

---

## Out of Scope

- Guided onboarding wizard / walkthrough overlay — too heavy, conflicts with hardware scanning
- Per-stage video or documentation links — deferred
- Guidance for P4PRO/P4PROPLUS flow methods — deferred
- Changing guidance level manually (user override) — deferred; derive from experiment_count only
