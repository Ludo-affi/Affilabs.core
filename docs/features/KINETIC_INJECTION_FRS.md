# Kinetic Cycle Injection — Feature Reference Spec

> **Version**: draft
> **Last updated**: 2026-02-25
> **Status**: Design only — not implemented
> **Covers**: Kinetic cycle injection path, flag placement, phase timing, kobs fitting

---

## 1. Core Distinction from Binding

Kinetic cycles are **flow-based** (P4PRO/PROPLUS with AffiPump or internal pumps).
Binding cycles are **manual syringe** (P4SPR).

| Property | Binding (manual) | Kinetic (flow) |
|---|---|---|
| Injection trigger | User pipettes | Pump + 6-port valve automated |
| Injection time known? | No — detected from signal | **Yes — valve switch timestamp** |
| Channel timing skew | Up to 15s (pipetting A→D) | None — simultaneous |
| RI artefact risk | High (air gap, manual) | Minimal (controlled flow) |
| `_InjectionMonitor` needed? | Yes | **No** |
| Association start | Detected from signal rise | Valve switch time |
| Dissociation start | Detected or user-triggered | Valve switch back time |
| Dissociation phase | Not tracked | Tracked — kd measurement window |

---

## 2. Intended Execution Flow (not yet implemented)

```
Kinetic cycle starts
  │
  ├─ Phase 0: Baseline (buffer flowing, stabilise signal)
  │     duration: cycle.baseline_time or first N seconds
  │
  ├─ Phase 1: Association
  │     Valve switches → sample flowing
  │     t_injection = valve switch wall-clock time        ← flag placed HERE
  │     Duration: cycle.contact_time
  │     _InjectionMonitor does NOT run
  │
  ├─ Phase 2: Dissociation
  │     Valve switches back → buffer flowing
  │     t_washout = valve switch wall-clock time          ← wash flag placed HERE
  │     Duration: cycle.dissociation_time (new field)
  │     koff fitting window opens
  │
  └─ Phase 3: Regeneration (optional, separate cycle or inline)
```

---

## 3. Flag Placement

**Current (Binding):** `injection_flag_requested.emit(ch, t_detected, confidence)` — fired by `_InjectionMonitor` when slope rise detected.

**Required (Kinetic):** Flag placed at valve switch time, not from signal detection.
- Source of truth: `PumpManager` or `InjectionCoordinator` when it commands the valve
- Confidence = 1.0 (timing is exact, not inferred)
- All channels flagged simultaneously (no per-channel skew)

---

## 4. Required New Fields on Cycle Model

> File: `affilabs/domain/cycle.py`

```python
# Kinetic phase timing
dissociation_time: Optional[float] = None   # seconds for dissociation (washout) phase

# Kinetic result fields (computed at cycle end)
ka: Optional[float] = None    # association rate constant (M⁻¹s⁻¹)
kd: Optional[float] = None    # dissociation rate constant (s⁻¹)
KD: Optional[float] = None    # equilibrium dissociation constant (M) = kd/ka
kobs_by_channel: Dict[str, float] = {}  # per-channel observed rate (s⁻¹)
```

---

## 5. Required New Execution Path

`InjectionCoordinator._determine_injection_mode()` currently routes on hardware + `manual_injection_mode`.
For Kinetic cycles with a pump, it should route to a new `_execute_kinetic_injection()` rather than
`_execute_manual_injection()` or `_execute_automated_injection()`.

`_execute_kinetic_injection()` responsibilities:
1. Command valve switch (via PumpManager) → record `t_injection`
2. Place injection flag immediately at `t_injection`
3. Wait `cycle.contact_time` seconds (association phase)
4. Command valve back → record `t_washout`
5. Place wash flag at `t_washout`
6. Wait `cycle.dissociation_time` seconds (dissociation phase)
7. Trigger kobs fit on association window
8. Optionally trigger koff fit on dissociation window
9. Store results on cycle (`ka`, `kd`, `KD`)

---

## 6. kobs Fitting

**When:** At end of association phase (once `contact_time` elapses), not real-time.

**Algorithm (already exists in `_binding_plot_mixin.py:_fit_kobs_from_raw()`):**
```
R(t) = Rmax * (1 - exp(-kobs * t))
```
Where t is time since injection, R(t) is SPR response (nm or RU).

**Per concentration:**
- Each Kinetic injection (one per `planned_concentrations` entry) yields one kobs value
- After all injections: linear regression of kobs vs [C] gives ka (slope) and kd (intercept)
- KD = kd / ka

**Where it runs:** Should move from `_binding_plot_mixin.py` to a service class
(e.g. `affilabs/services/kinetics_fitter.py`) so it can be called both at cycle-end and from EditsTab.

---

## 7. Dissociation Phase (kd direct fit)

For a single-cycle kd measurement (not from multi-injection linear regression):
```
R(t) = R0 * exp(-kd * t)
```
Where t is time since washout, R0 is response at washout start.

This gives a direct kd per cycle — more robust than the intercept method when concentrations span a wide range.

**Not in EditsTab yet.** Would require a new fit mode.

---

## 8. Contact Monitor (InjectionActionBar)

For Kinetic cycles, the Contact Monitor panel shows:
- Phase 1 (association): countdown from `contact_time` — triggered at valve switch, not at signal detection
- Phase 2 (dissociation): countdown from `dissociation_time` — triggered at valve switch back

Currently `show_phase1()` / `show_phase2()` are called from `_on_monitor_detected` which fires from `_InjectionMonitor`. For Kinetic, these calls should be triggered by the pump coordinator at valve switch time instead.

---

## 9. Open Questions (resolve before implementation)

**Q1 — Current routing:** Do existing Kinetic cycles go through `_execute_manual_injection` or `_execute_automated_injection`? Check `_determine_injection_mode()` in `injection_coordinator.py` with a Kinetic cycle configured on P4PRO hardware.

**Q2 — kobs fitting timing:** Fit at end of each association phase (simplest), or accumulate across all injections in the cycle then fit at cycle end? The linear regression (kobs vs [C]) requires all injections to be done first, so cycle-end is likely correct. Per-injection kobs can still be shown live.

**Q3 — Dissociation time field:** Does `cycle.dissociation_time` need to be user-configurable per cycle, or is it a global setting? P4PRO wash duration is currently set in method builder — should dissociation be a separate timer on top of wash, or replace it?

**Q4 — InjectionActionBar for Kinetic:** Should Phase 1 / Phase 2 labels change for Kinetic cycles? E.g., "Association (120s)" instead of "Contact time", "Dissociation" instead of "Wash"? Needs UX decision.

**Q5 — Multi-injection Kinetic:** A full kinetics experiment runs one concentration per injection (e.g. 5 injections with regen between). Is this one Kinetic cycle with `planned_concentrations`, or multiple sequential Kinetic cycles? The current model supports both, but the fitting pipeline needs to know which concentrations go with which cycles.

**Q6 — Flag confidence for valve-timed injections:** Should valve-timed flags have `confidence=1.0` to distinguish them from signal-detected flags in the EditsTab display?

**Q7 — kd from dissociation vs intercept:** Which kd method is preferred? Direct exponential fit on dissociation curve (more accurate, needs dissociation phase data) or intercept of kobs-vs-[C] linear regression (simpler, no dissociation data needed)?

---

## 10. Files to Create / Modify

| File | Change |
|---|---|
| `affilabs/domain/cycle.py` | Add `dissociation_time`, `ka`, `kd`, `KD`, `kobs_by_channel` fields |
| `affilabs/coordinators/injection_coordinator.py` | Add `_execute_kinetic_injection()`, update `_determine_injection_mode()` |
| `affilabs/services/kinetics_fitter.py` | **New** — extract kobs fitting from `_binding_plot_mixin.py`, add dissociation fit |
| `affilabs/tabs/edits/_binding_plot_mixin.py` | Refactor to call `kinetics_fitter.py` instead of inline fitting |
| `affilabs/widgets/injection_action_bar.py` | Support kinetic phase labels (Association / Dissociation) |
| `docs/features/INJECTION_WORKFLOW_FRS.md` | Add §Kinetic path section |

---

## 11. Dependencies / Blockers

- **Firmware**: Requires P4PRO GPIO or timing confirmation that valve switch time is accessible from software at the moment of switch (not retrospectively). Confirm with firmware team.
- **PumpManager**: `inject_simple()` / `inject_partial_loop()` must return or emit the exact valve-switch timestamp. Currently they return a bool.
- **`_WashMonitor`**: Kinetic dissociation is NOT a wash — they are separate concepts. `_WashMonitor` should not be used for dissociation phase timing.
