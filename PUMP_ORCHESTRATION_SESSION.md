# Pump Orchestration Session Summary

**Branch:** `feature/v2.0-polarizer-and-dialog-fixes`  
**Date:** February 8, 2026  
**Commits this session:** 07bd86b, c7d45a8, 8ab6288

---

## Commits Made

### 1. Channel Selection (07bd86b)
**feat: configurable channel selection (AC/BD) for P4PRO 3-way valves**
- `Cycle.valve_config` replaced with `Cycle.channels: Literal['AC','BD']`
- `PumpManager.default_channels` property (global default, settable)
- `inject_simple()` sets 3-way valves to selected channels (STEP 0)
- `inject_partial_loop()` uses channels param instead of hardcoded B+D
- Method builder parses `channels AC` or `channels BD` syntax
- `_execute_injection()` passes `cycle.channels` (falls back to `default_channels`)
- **3-way valve mapping:** AC = state 0 (de-energized), BD = state 1 (energized)
- **Resolution order:** cycle.channels (per-cycle) > pump_mgr.default_channels (global) > "AC" (factory)

### 2. inject_simple Flow Fix (c7d45a8)
**fix: inject_simple STEP 3 is pre-injection delay, STEP 7 keeps pump flowing**
- STEP 3: corrected from "loop filling" to "pre-injection delay" (15s wait before 6-port switch)
- STEP 7: no longer blocks waiting for full 1000µL dispense to finish
- After injection, pump transitions to `RUNNING_BUFFER` and keeps dispensing
- Next cycle's `stop_and_wait_for_idle()` stops the pump when ready
- `finally` block only resets to IDLE if still in INJECTING state (not RUNNING_BUFFER)

### 3. Stop Behavior Fixes (8ab6288)
**fix: proper stop behavior for all pump functions**
- Added `HOMING` to `PumpOperation` enum — `home_pumps()` now blocks concurrent ops
- `cancel_operation()` now sends `/1TR /2TR` terminate commands (not just flag)
- `inject_simple` STEP 3 (pre-inject delay): checks `_shutdown_requested` every 0.5s
- `inject_simple` STEP 5 (contact time): checks `_shutdown_requested` every 0.5s
- On cancel during injection: 6-port valves closed immediately

---

## Cycle Type Injection Rules

| Cycle Type | injection_method | Default contact_time | Notes |
|---|---|---|---|
| **Baseline** | None | — | No injection, buffer flow only |
| **Immobilization** | `simple` | User must specify | flow/contact parsed from method |
| **Wash** | `simple` | User must specify | Same as Immobilization |
| **Concentration** | `simple` (or `partial` if keyword) | User must specify | Supports `[A:100nM]` tags |
| **Regeneration** | `simple` | 30s (hardcoded) | Scales with flow rate (see below) |

### Contact Time / Flow Rate Physics
- Loop = 100µL total, usable = 80µL (80% to cut diffusion tail)
- `contact_time_s = (80 / flow_rate) * 60`
- `flow_rate = (80 / contact_time_s) * 60`
- Regen wash volume target: 40µL → `regen_contact = (40 / flow_rate) * 60`

---

## Flow Panel — Individual Commands (6 Buttons)

All functions are independent aspirate/dispense operations. After stopping, **must Home before next function**.

| Button | Handler | PumpManager Method | Notes |
|---|---|---|---|
| **Prime** | `_on_pump_prime_clicked` | `prime_pump()` | Reads `prime_spin` UI |
| **Cleanup** | `_on_pump_cleanup_clicked` | `cleanup_pump()` | Default params |
| **Inject Simple** | `_on_inject_simple_clicked` | `inject_simple(rate)` | Reads `pump_assay_spin` |
| **Inject Partial** | `_on_inject_partial_clicked` | `inject_partial_loop(rate)` | Reads `pump_assay_spin` |
| **Start Buffer** | `_on_start_buffer_clicked` | `run_buffer()` / `cancel_operation()` | Toggle (start/stop), reads `pump_setup_spin` |
| **Home** | `_on_home_pumps_clicked` | `home_pumps()` | Uses HOMING state to block concurrent ops |
| **Emergency Stop** | `_on_emergency_stop_clicked` | `emergency_stop()` | Always allowed, sends /1TR /2TR |

### Stop Behavior
- `cancel_operation()`: Sets `_shutdown_requested` + sends `/1TR /2TR` → plungers stop immediately, operation exits at next check (≤0.5s)
- `emergency_stop()`: Same terminate commands + forces `IDLE` state immediately
- After any stop: plungers at unknown position → **Home required** before next function

---

## PumpOperation Enum States

```python
IDLE = "idle"
PRIMING = "priming"
CLEANING = "cleaning"
RUNNING_BUFFER = "running_buffer"
INJECTING = "injecting"
HOMING = "homing"
EMERGENCY_STOP = "emergency_stop"
```

---

## Bundle Mode — Volume Budget Tables

### Scenario 1: Fastest (80 µL/min, 60s contact)

| Phase | Duration | Volume |
|---|---|---|
| Baseline 1 | 30s | 40 µL |
| Concentration | 7 min | 560 µL |
| Regeneration | 1 min (30s contact) | 80 µL |
| Baseline 2 | 4 min | 320 µL |
| **Total** | **12.5 min** | **1000 µL** |

### Scenario 2: Slow (16 µL/min, 5 min contact)

| Phase | Duration | Volume |
|---|---|---|
| Baseline 1 | 30s | 8 µL |
| Concentration | 20 min | 320 µL |
| Regeneration | 2.5 min (150s contact) | 40 µL |
| Baseline 2 | 2 min | 32 µL |
| **Subtotal** | **25 min** | **400 µL** |
| **Remaining** | **37.5 min** | **600 µL** |

At 16 µL/min: can fit 2 full BL→Conc→Regen→BL sequences (800 µL) within one syringe.

### Regen Contact Time Scaling
- Target wash volume: 40 µL through loop
- `regen_contact = (40 / flow_rate) * 60`
- At 80 µL/min → 30s, at 16 µL/min → 150s

---

## Bundle Mode — Architecture (NOT YET IMPLEMENTED)

Bundle mode is the next major feature. Key differences from Individual mode:

1. **Single aspirate** at start of queue (1000µL)
2. **Single continuous dispense** at constant flow rate for entire sequence
3. Injections = **valve-only events** (6-port LOAD→INJECT→LOAD), no pump commands
4. Cycle transitions = just timers, no pump stop/restart
5. Pump stops only when syringe exhausts or queue completes
6. No re-aspiration between cycles

### Current Code (Individual mode per cycle):
- `_on_start_button_clicked()` → stops pump → re-aspirates → starts buffer → schedules injection
- `inject_simple()` does its own full aspirate/dispense cycle
- Each cycle wastes unused syringe volume

### Required Changes for Bundle Mode:
- New `run_bundle(queue, flow_rate)` method in PumpManager
- Aspirate once, dispense_both at flow_rate with switch_valve=True
- Injection scheduler becomes: wait delay → open 6-port → wait contact → close 6-port
- Volume tracking: monitor plunger position, alert when syringe nearing empty
- Cycle transitions handled by timer expiry, not pump restart

---

## Files Modified This Session

| File | Changes |
|---|---|
| `affilabs/domain/cycle.py` | `valve_config` → `channels: Literal['AC','BD']`, updated `to_export_dict()` |
| `affilabs/managers/pump_manager.py` | HOMING enum, default_channels, channels param on inject_simple/partial, cancel sends /TR, shutdown checks in inject_simple STEP 3+5, STEP 7 non-blocking |
| `affilabs/widgets/method_builder_dialog.py` | `channels AC/BD` parser, channels passed to Cycle() |
| `main.py` | `_execute_injection()` passes cycle.channels |
