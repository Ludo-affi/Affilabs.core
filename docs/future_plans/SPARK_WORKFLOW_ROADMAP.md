# Spark Workflow Development Roadmap

**Document Date:** February 17, 2026  
**Status:** Planning  
**Priority:** User experience for both new and experienced SPR users

---

## Overview

Spark users need guided paths to common experiment workflows. The codebase already has significant infrastructure (method templates, cycle templates, queue presets, analysis wizards) but lacks user-facing workflow orchestration. This roadmap prioritizes building workflows that:

1. **Reduce setup time** — from 15 min of cycle-by-cycle editing → 2 min from template
2. **Guide inexperienced users** — step-by-step dialogs with sensible defaults
3. **Enable power users** — smart shortcuts and one-click patterns
4. **Preserve retrievability** — pause/resume/cancel workflows without losing method definition

---

## Existing Infrastructure (Ready to Activate)

### 1. Method Templates
- **Status:** 5 templates coded (`MethodTemplateService`)
- **Templates:** Kinetics Analysis, Affinity Screening, Single-Cycle Kinetics, Regen Screening, Binding Analysis
- **Tier:** Pro templates require license gate (already implemented)
- **Issue:** No UI button; templates only accessible via MethodBuilderDialog

### 2. Cycle Template Storage
- **Status:** TinyDB + CRUD built (`CycleTemplateStorage` in services/)
- **Database:** Currently empty
- **Features:** Save/Load/Delete/Search, JSON export/import
- **Issue:** Feature skeleton exists; save/load buttons present but untested

### 3. Queue Preset Storage
- **Status:** TinyDB + CRUD built (`QueuePresetStorage` in services/)
- **Database:** Currently empty
- **Features:** Named queue configurations, persistence
- **Issue:** No UI wiring

### 4. Analysis Wizards (Active)
- **KD Wizard** (`affilabs/widgets/kd_wizard.py`) — Steady-state affinity fitting
- **ka/kd Wizard** (`affilabs/widgets/ka_kd_wizard.py`) — Full kinetics fitting
- **Status:** Fully functional, discoverable via menu
- **Gap:** No integration with queue completion workflow

---

## Tier 1: Ship First (Highest Impact, Low Effort)

### 1.1 Quick Start Wizard
**Goal:** Get users from "New Experiment" → "Method ready to run" in 3 steps  
**Effort:** 1-2 days

**Design:**
```
Step 1: Assay Type Selection
┌─────────────────────────┐
│ What are you measuring? │
│                         │
│ ⚪ Kinetics Analysis    │
│ ⚪ Affinity Screening   │
│ ⚪ Binding Check        │
│ ⚪ Regen Scout          │
│ ⚪ Custom              │
└─────────────────────────┘

Step 2: Configure Parameters
[Input fields with smart defaults per assay type]
- Number of concentrations: 5
- Top concentration: 100 nM
- Dilution factor: 2x
- Baselines: Start + end
- Wash cycle: 30s regen

Step 3: Review & Load
[Method summary table]
13 cycles total, 45 min duration
├─ 1 min Baseline
├─ 3 min Association (100 nM)
├─ 5 min Dissociation
├─ 30s Regeneration
└─ ... (repeated for each concentration)

[Load to Queue] [Edit in Method Builder] [Save as Template]
```

**Implementation:**
- New file: `affilabs/widgets/quick_start_wizard.py` (~300 lines)
- Wrapper around `MethodTemplateService.generate_method()`
- Modify sidebar: add "New Experiment" button
- Hook into `QueuePresenter.add_cycle()` on Load

**Key Decisions:**
- Reuse existing template generation logic (no new kinematics code)
- Smart defaults per template (kinetics → 5 concentrations, screening → 7, etc.)
- "Save as Template" persists user-modified concentrations/timing to cycle templates database

### 1.2 Startup Checklist Widget
**Goal:** Ensure users don't forget calibration, buffer, recording before running  
**Effort:** 1 day

**Design:**
```
[Startup Checklist]

☑ Hardware Connected     [Status: ✓ Controller + Spectrometer]
☑ Calibration Current    [Status: ⚠ 18h old] [Recalibrate]
☑ Chip Loaded           [Status: ✓]
☑ Buffer Flowing        [Status: ⚠ Baseline unstable] [Prime System]
☑ Recording Active      [Status: ✗ Not recording] [Start Recording]

─────────────────────────────────
5/5 Ready to Run
```

**Implementation:**
- New file: `affilabs/widgets/startup_checklist.py` (~200 lines)
- Widget with CheckBox + status label + action button per item
- Place in sidebar or modal on first hardware connect
- Each action links to existing functions (calibration dialog, recording start, etc.)

**Data Sources:**
- Hardware connected: `HardwareManager` state
- Calibration age: `CalibrationManager.last_calibration_time`
- Chip state: *unclear — may need to infer from sensorgram stability*
- Buffer flowing: Baseline stability metric (real-time)
- Recording: `RecordingManager.is_recording`

**Tiers:**
- **Beginner:** Follow top-to-bottom; modal blocks other actions
- **Expert:** Widget in sidebar; skip items as needed

### 1.3 Seed Default Templates
**Goal:** Populate databases with factory defaults so templates are immediately useful  
**Effort:** 0.5-1 day

**Cycle Templates to Create:**
```json
{
  "templates": [
    {
      "name": "30s Baseline",
      "type": "Baseline",
      "duration_minutes": 0.5,
      "flow_rate": 20,
      "description": "Quick baseline for validation"
    },
    {
      "name": "Dynamic Association",
      "type": "Kinetic",
      "duration_minutes": 3,
      "flow_rate": 20,
      "injection_method": "dosing_series",
      "description": "Kinetic measurement"
    },
    ...
  ]
}
```

**Queue Presets to Create:**
```json
{
  "presets": [
    {
      "name": "Quick Kinetics (5-conc)",
      "cycles": [...generated from MethodTemplateService...],
      "duration_minutes": 45,
      "description": "5 concentrations: 100, 50, 25, 12.5, 6.25 nM"
    },
    {
      "name": "Regen Scout",
      "cycles": [...],
      "duration_minutes": 20
    }
  ]
}
```

**Implementation:**
- Modify: `cycle_templates.json` and `queue_presets.json`
- Create: migration script to populate TinyDB on first app launch (if databases are empty)
- Wire: "Load Preset" button in sidebar → opens QueuePresetDialog → populates queue

---

## Tier 2: Next Sprint (Gap Filling)

### 2.1 Concentration Series Builder
**Goal:** Component for easily defining concentration matrices within the wizard  
**Effort:** 1 day

**Design:**
```
[Concentration Series]

Input Method:
⚪ Generate from top + dilution
  Top concentration:  [100     ] nM
  Dilution factor:    [2       ] x
  Number of points:   [5       ]
  Generated: 100, 50, 25, 12.5, 6.25 nM

⚪ Paste comma-separated list
  [100, 50, 25, 12.5, 6.25]

⚪ Import from file
  [Browse...]

[Preview table with concentrations] [OK]
```

**Implementation:**
- New file: `affilabs/widgets/concentration_builder.py` (~150 lines)
- Integrate into Quick Start Wizard Step 2
- Also exposed as standalone component in Method tab

### 2.2 Post-Experiment Analysis Workflow
**Goal:** Guide users from "queue done" → "KD fit + export report"  
**Effort:** 1-1.5 days

**Design:**
```
[Queue Completed!]

Experiment finished in 47 minutes.
What would you like to do?

┌──────────────────────────┐
│ Fit Kinetics (ka/kd)     │
│ Pre-populated with cycle │
│ data from this run       │
└──────────────────────────┘

┌──────────────────────────┐
│ Fit Affinity (KD)        │
│ Steady-state analysis    │
└──────────────────────────┘

┌──────────────────────────┐
│ Export Report (PDF)      │
│ Summary + plots          │
└──────────────────────────┘

┌──────────────────────────┐
│ Start New Experiment     │
│ Quick Start Wizard       │
└──────────────────────────┘
```

**Implementation:**
- New file: `dialog_experiment_complete.py` (~200 lines)
- Hook into `_on_cycle_completed()` when `self.queue_presenter.get_queue_size() == 0`
- Pre-populate wizards with cycle data from just-completed method
- Export button uses existing Excel/PDF export

**Key Integration:**
- Triggered when: queue becomes empty AND snapshot exists (method was run)
- Passes: cycle data from `self.queue_presenter.get_original_method()` + completed cycles
- Preserve: snapshot until user dismisses dialog, so method remains retrievable

### 2.3 Instrument Prep Workflows
**Goal:** Step-by-step guided sequences for recurring manual tasks  
**Effort:** 1.5 days

**Workflows:**
1. **Prime System** — Prepare fluidic path for use
   - Instruction card: "Prime the pump to remove air from lines"
   - Auto commands: Flush @ 50 µL/min for 30s
   - Verification: "Is buffer flowing smoothly? (Yes / No / Troubleshoot)"
   
2. **Surface Prep** — Immobilize ligand, block, equilibrate
   - Sequence of cycles: Immobilization → Blocking → Baseline
   - Step-by-step instructions with screenshots
   
3. **Chip Loading** — Mount SPR chip safely
   - Visual guide with images
   - Checklist: Chip seated, temperature stable, baseline stable

**Implementation:**
- New file: `affilabs/widgets/prep_workflow_dialogs.py` (~300 lines)
- Button in sidebar to launch prep workflows
- Each workflow = sequence of instruction cards + verification buttons

---

## Tier 3: Future Features (Competitive Differentiators)

### 3.1 Visual Method Timeline
- Replace method table with Gantt-style visualization
- Drag-to-reorder cycles
- Inject points marked with colored labels
- Duration estimate updates dynamically

### 3.2 Experiment Journal
- Auto-generated log combining method + calibration + results
- PDF export for lab notebook
- Linked to cycle data in edits table

### 3.3 AI Experiment Assistant
- Real-time suggestions ("Your dissociation is ending — consider extending 2 more minutes for slow off-rates")
- Anomaly detection ("Baseline instability detected — prime system recommended")

---

## Implementation Sequence

**Sprint 1 (3-4 days: Tier 1 ship)**
1. Seed templates (0.5 day)
2. Quick Start Wizard (2 days)
3. Startup Checklist (1 day)
4. Testing + Polish (0.5 day)

**Result:** Users can load common experiment templates in 2 minutes; guided startup reduces errors.

**Sprint 2 (4 days: Tier 2 gaps)**
1. Concentration Builder (1 day)
2. Post-Experiment Analysis Dialog (1 day)
3. Prep Workflows (1 day)
4. Testing + Integration (1 day)

**Result:** Full experiment pipeline guided end-to-end.

---

## File Structure to Create

```
affilabs/
├── widgets/
│   ├── quick_start_wizard.py          (NEW - dialog, 300L)
│   ├── startup_checklist.py           (NEW - widget, 200L)
│   ├── concentration_builder.py       (NEW - dialog, 150L)
│   ├── prep_workflow_dialogs.py       (NEW - dialogs, 300L)
│   └── dialog_experiment_complete.py  (NEW - dialog, 200L)
├── utils/
│   └── (possible helper functions for workflow orchestration)
└── [existing files to modify]
    ├── sidebar_tabs/ → add "New Experiment" button
    ├── main.py → hook experiment_complete dialog
    └── cycle_templates.json, queue_presets.json → seed defaults
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Time to load experiment** | < 2 min | Stopwatch from "New Experiment" click → method queued |
| **User setup errors avoided** | 50% reduction | Track un-calibrated/un-recording starts |
| **One-click template adoption** | 70% of new expts | Analytics on Quick Start usage |
| **Workflow discovery** | 90% visible | UI audit: buttons/menu placement |
| **Post-run fitting uptake** | 40% | Track wizard launches post-experiment |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Tier 1 estimated effort underestimated | Buffer +1 day; use existing patterns (no new algorithms) |
| Template defaults don't match user needs | Make defaults editable; save user modifications to templates |
| Checklist items hard to measure (e.g., baseline stability) | Start with simple heuristics; refine based on feedback |
| Post-run dialog triggers at wrong time | Careful state tracking; test queue completion paths thoroughly |

---

## Notes for Future Sessions

- This roadmap is **not** a redesign of the queue execution system (which was just refactored via snapshot-based pause/resume).
- All Tier 1 features reuse existing code (templates, CRUD, wizards) — no new domain logic.
- Tier 2 begins **only after** Tier 1 testing confirms queue/pause/resume works correctly in production.
- Concentration builder is a **reusable component** — pull it into Method tab after wizard ships.
- Post-experiment workflow should **not** clear method snapshot until user explicitly dismisses dialog.

