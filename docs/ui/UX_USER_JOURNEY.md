# UX User Journey — Affilabs.core v2.0.5

> **Purpose**: Define what users need at each stage of an experiment so that UI design decisions are grounded in real workflow, not assumptions.
> **Primary persona**: First-time and occasional users — lab researchers, PhD students, technicians.
> **Core problem**: Users don't know what to do next. The UI must make the correct next action obvious at every step.

---

## Personas

| Persona | Technical level | Primary goal | Biggest frustration |
|---------|----------------|-------------|---------------------|
| **PhD student** | Medium — knows biology, not optics | Run binding assays, export data for thesis | Unclear if the instrument is working correctly |
| **Lab researcher** | High — knows SPR physics | Run multi-channel kinetics experiments | Slow to get to acquisition; too many clicks |
| **Technician** | Low-medium — follows protocols | Keep the instrument running, run standard samples | Hard to remember the workflow between sessions |

---

## The 6-Stage Experiment Workflow

Every experiment follows this sequence. The UI must reflect and reinforce this order.

```
1. CONNECT → 2. CALIBRATE → 3. ACQUIRE → 4. INJECT → 5. RECORD → 6. EXPORT
```

A user who cannot immediately identify which stage they are in — and what to do next — is lost.

---

## Stage-by-Stage Journey Map

### Stage 1 — CONNECT

**What the user wants**: Know the instrument is on and recognized.

**Current experience**:
- Click power button (red → yellow → green)
- Status updates in toolbar and status bar
- Subunit indicators (Sensor / Optics / Fluidics) update when ready

**What users think/feel**:
- "Is it searching or frozen?" — the yellow searching state gives no time estimate
- "What does 'Optics: Not Ready' mean?" — subunit labels are not self-explanatory
- First-timers don't know they need to click the power button first

**Design requirements**:
- The power button must be the **most prominent interactive element** when the app opens in disconnected state
- Show a brief inline hint: *"Click to connect your instrument"* — remove it after first successful connection
- During SEARCHING: show elapsed time ("Searching... 3s") and a cancel option
- On CONNECTED: auto-scroll the sidebar to show the next required action (Calibrate)
- Subunit labels should use plain language: "Sensor: Ready" / "Sensor: Warming up" / "Sensor: Check cable"

**Implemented**:
- ✅ Searching overlay shows elapsed time: "Searching for instrument… Ns" — updates every 300ms (`affilabs_core_ui.py:_update_connecting_animation`)
- ⬜ Inline "Click to connect" hint — not yet built
- ⬜ Sidebar auto-scroll after connect — not yet built
- ⬜ Plain-language subunit labels — not yet built

---

### Stage 2 — CALIBRATE

**What the user wants**: Get a clean baseline so measurements are meaningful.

**Current experience**:
- User must manually locate the Calibrate button (in sidebar)
- Calibration runs, progress shown via progress bar + log messages
- On success, Record button becomes enabled

**What users think/feel**:
- "Do I have to calibrate every time?" — yes, but this is never explained
- "What does calibration actually do?" — no in-context explanation
- Occasional users forget to calibrate before recording; the Record button being disabled is the only signal

**Design requirements**:
- After connecting, the sidebar should visually highlight calibration as the next step (e.g., pulsing border, "Step 2 of 5" label)
- Add a one-line tooltip or inline label: *"Calibration captures your S-pol reference. Required before every experiment."*
- Calibration progress must show **what is happening**, not just a percentage: *"Reading channel A..."*, *"Setting polarizer..."*
- On calibration failure, show **what to do**: *"Signal too weak — check fiber connection and retry"* not just *"Calibration failed"*
- On success: show a brief confirmation ("Calibration complete — signal quality: Good") and auto-advance the sidebar focus to acquisition controls
- Pre-calibration dialog must **clearly state water must be in device**

**Implemented**:
- ✅ Calibrate button (`full_calibration_btn`) flashes green border 3× after connecting, when not already calibrated (`hardware_event_coordinator.py:_pulse_calibrate_button`)
- ✅ Pre-calibration dialog shows prominent amber "⚠ WATER MUST BE IN DEVICE" warning banner (`startup_calib_dialog.py`)
- ✅ After QC dialog closes, sidebar **auto-switches to Method tab** — "Build Method" CTA is immediately visible, guiding the user to the next step (`mixins/_calibration_mixin.py:_show_qc_dialog`)
- ✅ **"Build Method" CTA**: full-width 48px blue button at top of Method tab — always the first element in the tab (`AL_method_builder.py`)
- ⬜ "Step 2 of 5" label — not yet built
- ⬜ Actionable failure messages (beyond Retry/SPARK fallback) — partially built

---

### Stage 3 — ACQUIRE

**What the user wants**: See a live signal and confirm the instrument is responding to their sample.

**Current experience**:
- Acquisition starts automatically after calibration (or user can start manually)
- Live sensorgram appears on the main content area
- Channel A/B/C/D curves update in real time

**What users think/feel**:
- "Is this a good signal?" — no immediate quality feedback
- "Why are some channels flat?" — no explanation that unused channels may show noise
- "What am I looking at?" — new users don't know what a sensorgram represents

**Design requirements**:
- Display a **Signal IQ indicator** prominently near each channel — not buried in a status bar
- Show a persistent annotation on the graph: *"Flat baseline = instrument ready for injection"* — hide it once an injection event is detected
- If a channel signal is poor quality, show a per-channel warning inline (not just in a log)
- The Live tab should have a brief collapsible "What am I seeing?" explainer panel — hidden by default, dismissable permanently

**Implemented**:
- ✅ Signal IQ dots (colored squares) on A/B/C/D channel toggle buttons — zone + FWHM + dip depth + baseline noise (`sensor_iq.py`, `spectrum_helpers.py`, `ui_update_coordinator.py`)
- ✅ "Flat baseline = instrument ready for injection" label on timeline graph; hides on first injection (`affilabs_core_ui.py:_baseline_hint_label`, `flag_manager.py`)
- ✅ **Active Cycle Card** in Method tab sidebar — shows cycle type badge, cycle index, countdown MM:SS, next cycle preview, total experiment time remaining; visible only while a cycle is running (`AL_method_builder.py`, `mixins/_cycle_mixin.py`)
- ✅ Queue table (`QueueSummaryWidget`) visible at all times in Method tab; expands to fill available space with no cap (`AL_method_builder.py`)
- ⬜ "What am I seeing?" collapsible panel — not yet built

---

### Stage 4 — INJECT

**What the user wants**: Deliver sample to the sensor and watch the signal change.

**Current experience**:
- For P4SPR: user pipettes manually; clicks an injection flag button or it's auto-detected
- For P4PRO/PROPLUS: user programs a method and the pump runs automatically
- Injection flags appear as vertical markers on the sensorgram

**What users think/feel**:
- "When exactly should I inject?" — no guidance on ideal baseline stability window
- "Did the injection register?" — flag markers appear but users miss them
- "The signal went down — is that wrong?" — blue shift on binding confuses users expecting a rise

**Design requirements**:
- Show a **baseline stability indicator**: a small badge that turns green when the signal has been stable for >30s — this is the injection cue
- When an injection flag is placed, briefly animate it (flash or expand) so users notice it
- Add a one-time tooltip on the first injection: *"SPR signals decrease on binding — a drop means your sample is working"*
- For P4SPR (manual), make the "Mark Injection" button visually prominent during acquisition — not hidden in a submenu
- For P4PRO/PROPLUS, show method progress (step X of Y, next: "Wait 120s") in a persistent status area

**Implemented**:
- ✅ Baseline stability badge in graph header — "Stabilizing…" (grey) → "Ready to inject ✓" (green) when all active channels p2p ≤ 0.15 nm for 30 samples; resets on acquisition stop (`affilabs_core_ui.py:stability_badge`, `main.py:_on_peak_updated`, `ui_update_coordinator.py`)
- ✅ Injection flag marker flashes on placement (3-step size pulse at 120ms intervals) (`flag_manager.py`)
- ✅ One-time tooltip "SPR signals decrease on binding — a drop means your sample is interacting with the sensor" on first injection ever (`flag_manager.py`)
- ✅ **Active Cycle Card** in sidebar shows current cycle type, countdown, and next cycle — partial coverage of "method step progress" for P4PRO/PROPLUS (`mixins/_cycle_mixin.py:_update_cycle_display`)
- ⬜ Prominent "Mark Injection" button for P4SPR — not yet built
- ⬜ Full P4PRO/PROPLUS method step status (step X of Y, next: "Wait 120s") — not yet built

---

### Stage 5 — RECORD

**What the user wants**: Capture their experiment data to a file they can analyze later.

**Current experience**:
- Record button in toolbar toggles recording on/off
- File is saved to the configured output directory
- Recording state shown in toolbar and status bar

**What users think/feel**:
- "Is it actually saving?" — the recording indicator is small and easy to miss
- "Where is the file going?" — output path not visible during recording
- "Can I stop and re-start? Will I lose data?" — unclear if stopping recording ends the experiment

**Design requirements**:
- The recording indicator must be **impossible to miss** — pulsing red dot, larger than current, in main view not just toolbar
- Show the output file path (truncated) in the status bar during recording: *"⏺ Saving to: experiment_2026-02-19.xlsx"*
- On Record stop: show a confirmation dialog with the saved file path and an "Open file" shortcut button
- Clearly distinguish "Stop Recording" from "Stop Acquisition" — these are different actions; users conflate them

**Implemented**:
- ✅ `rec_status_dot` pulses red at 800ms (bright ↔ faded) during recording (`affilabs_core_ui.py:set_recording_state`)
- ✅ `rec_status_text` shows "⏺ Saving to: filename.xlsx" during recording; resets to "Not Recording" on stop (`affilabs_core_ui.py:set_recording_state`)
- ✅ Post-stop toast: "Recording saved" green badge, bottom-right, with "Open file", "View results →", auto-dismiss 12s (`recording_event_coordinator.py:_show_recording_saved_prompt`)

---

### Stage 6 — EXPORT & ANALYZE

**What the user wants**: Get publication-ready data — a graph, a table, or an Excel file.

**Current experience**:
- Edits tab: view, align, and annotate recorded cycles
- Export tab: configure and download Excel/data files
- Analyze tab: currently hidden/disabled

**What users think/feel**:
- "I recorded my experiment — now where do my results go?" — Edits tab is not discoverable
- "What is a 'cycle'?" — domain term not explained
- First-timers don't know the difference between Live → Edits → Analyze

**Design requirements**:
- After recording stops, **automatically navigate to the Edits tab** (or show a prompt: "View your results →")
- Add a one-line label under the Edits tab nav button: *"Review recorded cycles"*
- "Cycle" should be explained inline on first visit: *"A cycle is one complete injection + wash sequence"*
- Export button should be the primary CTA in the Edits tab, not buried in a sidebar

**Implemented**:
- ✅ Post-recording toast includes "View results →" button that navigates to Edits tab (index 1) (`recording_event_coordinator.py`)
- ✅ First Edits tab visit shows tooltip: "A cycle is one complete injection + wash sequence. Each row in the table below represents one cycle from your recording." (`navigation_presenter.py:switch_page`)
- ⬜ Inline label under Edits nav button — not yet built
- ⬜ Export as primary CTA — not yet built

---

## Cross-Cutting Design Principles

Derived from the journey above — apply these to every UI decision.

| Principle | Implementation rule |
|-----------|---------------------|
| **Always show the next step** | At every app state, at least one UI element must clearly indicate what the user should do next |
| **Stage progress is visible** | A persistent indicator (step 1–6 or equivalent) shows where the user is in the workflow |
| **Errors are actionable** | Every error message ends with a specific corrective action: *"Check X"*, *"Retry Y"*, not just *"Failed"* |
| **Domain terms are explained once** | First use of "calibration", "cycle", "S-pol", "injection flag" shows a tooltip — dismissable, never repeated |
| **State changes are unmissable** | Connecting, calibrating, recording — all produce a visible animation or badge change in the main view, not just the toolbar |
| **Destructive actions are confirmed** | Stop recording, clear calibration, delete cycle — always require one explicit confirmation |
| **Hardware model adapts the UI** | P4SPR users never see pump controls; P4PRO/PROPLUS users see method/flow controls prominently |

---

## What This Doc Is Not

- This is **not a wireframe** — no pixel specs here, use `UI_DESIGN_SYSTEM.md` for those
- This is **not a feature backlog** — specific implementation tasks go into REQ: requests
- This is a **reference for intent** — when debating a UI decision, check which stage it affects and what the user needs at that moment

---

## Related Docs

- [UI_DESIGN_SYSTEM.md](./UI_DESIGN_SYSTEM.md) — color, typography, spacing rules
- [UI_COMPONENT_INVENTORY.md](./UI_COMPONENT_INVENTORY.md) — which widget owns which stage
- [UI_STATE_MACHINE.md](./UI_STATE_MACHINE.md) — app states that map to stages 1–3
- [UI_HARDWARE_MODEL_REQUIREMENTS.md](./UI_HARDWARE_MODEL_REQUIREMENTS.md) — P4SPR vs P4PRO/PROPLUS stage differences
