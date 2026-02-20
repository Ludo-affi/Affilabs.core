# Manual Injection UI — State Machine Specification (FRS)
**P4SPR Manual Syringe Mode · Affilabs.core v2.0.5+**

> **Bugs fixed during this audit (2026-02-18):**
> 1. `contact_time_seconds` → `contact_time` — attribute mismatch prevented contact timer from ever starting
> 2. `_manual_timer_next_action` never set to `"Perform wash"` — popout showed no wash hint
> 3. Only primary channel got injection flag — now all detected channels get flags

---

## State Machine Overview

```
┌──────────┐    user starts     ┌─────────────┐   dialog shown    ┌─────────────────────┐
│          │    cycle queue      │             │   (valves opened   │                     │
│   IDLE   │ ─────────────────► │ PREPARATION │   for non-P4SPR)  │ INJECTING/DETECTING │
│          │                    │             │ ──────────────────►│                     │
└──────────┘                    └─────────────┘                    └─────────┬───────────┘
                                                                            │
                                     ┌──────────────────────────────────────┘
                                     │  dialog closes (accepted) +
                                     │  injection flag placed +
                                     │  contact_time_seconds > 0
                                     ▼
                               ┌──────────────┐   timer expires   ┌──────────┐
                               │              │   (alarm rings)   │          │
                               │ CONTACT_TIME │ ─────────────────►│   WASH   │
                               │              │                   │          │
                               └──────────────┘                   └────┬─────┘
                                                                       │
                                     ┌─────────────────────────────────┘
                                     │  wash acknowledged +
                                     │  auto wash flags placed
                                     ▼
                               ┌──────────────┐
                               │   COMPLETE   │ → next cycle in queue OR recording stops
                               │   / EDIT     │ → Edits tab available for adjustments
                               └──────────────┘
```

---

## States

### 1. IDLE

| Property | Value |
|----------|-------|
| **Entry** | Application launched, or previous cycle completed |
| **UI** | Live sensorgram running, no modal dialogs, timer button shows no countdown |
| **Exit trigger** | User starts cycle queue (clicks Record + cycle queue begins executing) |

No injection-specific UI is active. Acquisition may or may not be running.

---

### 2. PREPARATION

| Property | Value |
|----------|-------|
| **Entry** | Cycle queue scheduler reaches a cycle requiring injection |
| **Code path** | `InjectionCoordinator.execute_injection()` → `_determine_injection_mode()` → `_execute_manual_injection()` |
| **Duration** | Milliseconds (valve open + dialog construction) |

**What happens:**
1. `InjectionCoordinator` determines injection mode (manual vs automated) based on:
   - Explicit `cycle.manual_injection_mode` setting (highest priority)
   - Hardware auto-detection: P4SPR without pump → manual
2. Sample info parsed from cycle metadata (`parse_sample_info(cycle)`)
3. Detection channels resolved: `cycle.target_channels` → `cycle.concentrations` keys → `"ABCD"` (P4SPR default) or `"AC"` (PRO default)
4. **Valves opened** for non-P4SPR hardware (`_open_valves_for_manual_injection()`)
5. `injection_started.emit("manual")` signal fired
6. `ManualInjectionDialog` constructed and shown via `.exec()` (modal, blocking)

**UI elements:**
- Concentration schedule dialog may have shown earlier (20s countdown in `main.py._schedule_injection()`)
- For pump/semi-automated `method_mode`: dialog is **skipped entirely** — auto-completes immediately

**Exit trigger:** `ManualInjectionDialog.exec()` begins → transitions to INJECTING/DETECTING

---

### 3. INJECTING / DETECTING

This is the core user-facing state. The `ManualInjectionDialog` is on screen.

| Property | Value |
|----------|-------|
| **Entry** | Dialog `.exec()` starts; detection timer begins immediately |
| **Duration** | Up to 60 seconds (`INJECTION_WINDOW_SECONDS = 60`) |
| **UI** | Modal dialog with per-channel LED indicators, status label, countdown |
| **Code** | `affilabs/dialogs/manual_injection_dialog.py` |

#### Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `INJECTION_WINDOW_SECONDS` | 60 | Hard timeout for entire injection window |
| `CHANNEL_SCAN_GRACE_SECONDS` | 10 | Keep scanning other channels after first detection |
| `DETECTION_CHECK_INTERVAL_MS` | 200 | How often each channel is scanned (5 Hz) |
| `DETECTION_CONFIDENCE_THRESHOLD` | 0.30 | Minimum confidence to count as detected |
| `FINAL_MEASUREMENT_TIMEOUT_MS` | 2000 | Auto-close delay on total timeout (no detection) |
| `MINIMUM_DATA_POINTS` | 10 | Minimum datapoints before scanning a channel |

#### Detection Loop

Every 200ms, `_check_for_injection_in_window()` runs:

```
for each monitored channel:
    _scan_channel(channel)
        → get buffer data since window_start_time
        → convert wavelength → RU (baseline-corrected)
        → auto_detect_injection_point(times, ru, sensitivity_factor)
        → if confidence > 0.30: mark channel as detected, light LED green
```

#### Sub-states within INJECTING/DETECTING

```
┌───────────────────────────────────────────────────────────────┐
│ INJECTING/DETECTING                                           │
│                                                               │
│  ┌──────────────┐  1st channel   ┌──────────────────┐        │
│  │              │  detected       │                  │        │
│  │  SCANNING    │ ──────────────► │  GRACE_PERIOD    │        │
│  │  (0–60s)     │                │  (10s countdown)  │        │
│  └──────┬───────┘                └────────┬─────────┘        │
│         │ 60s timeout                     │                   │
│         │ (no detection)                  │ all channels      │
│         ▼                                 │ detected          │
│  ┌──────────────┐                         ▼                   │
│  │   TIMEOUT    │                ┌──────────────────┐         │
│  │  (2s close)  │                │  ALL_DETECTED    │         │
│  └──────────────┘                │  (3s success)    │         │
│                                  └──────────────────┘         │
│                                                               │
│  User can click "Done Injecting" at any time:                 │
│  → sets _user_done_injecting = True                           │
│  → monitoring continues for 10 more seconds, then finalizes   │
│  User can click "Cancel" at any time → dialog.reject()        │
└───────────────────────────────────────────────────────────────┘
```

#### Exit Conditions (5 paths, priority order)

| # | Condition | Delay before close | Signal emitted | Result |
|---|-----------|-------------------|----------------|--------|
| 1 | **All monitored channels detected** | 3 seconds (success display) | `injection_complete` | `accept()` |
| 2 | **Grace period expired** (10s after first detection, not all channels found) | Immediate | `injection_complete` | `accept()` |
| 3 | **60s timeout, some channels detected** | Immediate (via `_finalize_detection`) | `injection_complete` | `accept()` |
| 4 | **60s timeout, NO channels detected** | 2 seconds (`FINAL_MEASUREMENT_TIMEOUT_MS`) | `injection_complete` | `accept()` |
| 5 | **User cancels** | Immediate | `injection_cancelled` | `reject()` |

**"Done Injecting" button behavior:**
- Sets `_user_done_injecting = True`
- Shows "✓ Injection complete. Finalizing measurement..."
- Detection continues for 10 more seconds (grace period), then finalizes
- Does NOT immediately close the dialog

**What "injection completed" means (Q1 answer):**
The dialog considers the injection phase done when ANY of exit conditions 1–4 trigger. The primary "happy path" is #1 (all channels autodetected). The system is tolerant — even if not all channels are detected, it proceeds with whatever was found. Detection results are stored per-channel in `_detected_channels_results` and passed back to the coordinator.

---

### 4. CONTACT_TIME

| Property | Value |
|----------|-------|
| **Entry** | Injection dialog closes (accepted) AND injection flag placed AND `cycle.contact_time_seconds > 0` |
| **Duration** | User-defined per cycle (typically 60–300 seconds) |
| **UI** | PopOutTimerWindow (Big Timer) + timer button countdown in nav bar |
| **Code** | `_place_injection_flag()` in `mixins/_pump_mixin.py` → `_start_manual_timer_countdown()` in `affilabs/ui_mixins/_timer_mixin.py` |

#### When does the Big Timer start? (Q2 answer)

The Big Timer starts **immediately after the injection dialog closes and the injection flag is placed** — NOT at first autodetection and NOT when the injection popup opens.

**Signal chain:**
```
ManualInjectionDialog closes (accepted)
  → InjectionCoordinator._execute_manual_injection()
    → _process_detection_results(dialog, cycle)
      → injection_flag_requested.emit(channel, time, confidence)
    → injection_completed.emit()

injection_flag_requested  →  _place_injection_flag()  [pump_mixin L303]
  → flag_mgr.add_flag_marker(channel, time, spr, flag_type='injection')
  → IF cycle.contact_time_seconds > 0:
      → main_window._start_manual_timer_countdown(label, seconds, sound=True)
        → IF "Contact" in label:
            → _auto_show_timer_window(label, seconds)
              → PopOutTimerWindow created/shown  ← BIG TIMER APPEARS HERE

injection_completed  →  _show_contact_time_marker()  [pump_mixin L269]
  → Places orange dashed "Contact end" vertical line on cycle graph
```

#### Timer Controls (PopOutTimerWindow)

| Control | Effect |
|---------|--------|
| **Pause** | `_on_pause_manual_timer()` — stops QTimer tick, window shows paused state |
| **Resume** | `_on_resume_manual_timer()` — restarts QTimer tick |
| **Edit time** | While paused, user can adjust remaining seconds via `_on_timer_time_edited()` |
| **Clear** | `_on_clear_manual_timer()` — stops timer, clears state, reopens as configurable |
| **Restart** | `_on_restart_manual_timer()` — resets to `_manual_timer_initial_duration` |
| **Close window** | Timer keeps running in background; button in nav bar still shows countdown |

#### Timer Tick (`_on_manual_timer_tick`, 1Hz)

Each second:
1. Decrement `_manual_timer_remaining`
2. Update timer button in nav bar
3. Update PopOutTimerWindow display (if visible)
4. Update `flag_mgr.update_contact_timer_display()` (overlay on cycle graph)

**Exit trigger:** `_manual_timer_remaining` reaches 0 → transitions to WASH

---

### 5. WASH

| Property | Value |
|----------|-------|
| **Entry** | Contact timer expires (`_manual_timer_remaining == 0`) |
| **UI** | Timer button flashes "WASH NOW" alert, PopOutTimerWindow shows finished state, alarm loops |
| **Code** | `_on_manual_timer_tick()` zero branch → `_timer_mixin.py` |

**What happens at timer=0:**
1. `_manual_timer.stop()` — QTimer stopped
2. `timer_button.show_wash_alert()` — nav button flashes WASH NOW
3. `_popout_timer.timer_finished(label, next_action)` — Big Timer shows completion + optional next action hint
4. `flag_mgr.clear_contact_timer_overlay()` — removes countdown overlay from graph
5. **`_place_automatic_wash_flags()`** — auto-places wash flags on ALL channels that have injection flags
6. `_start_alarm_loop()` — ascending alarm tone every 1.5 seconds until acknowledged

#### Automatic Wash Flag Placement

For each channel with an `InjectionFlag` in `FlagManager._flag_markers`:
- Read current graph stop cursor position → convert to cycle-relative display time
- Look up SPR value at that position from buffer
- `flag_mgr.add_flag_marker(channel, time, spr, flag_type='wash')`

#### Exit Conditions

| Trigger | Effect |
|---------|--------|
| **User clicks timer button** | `_on_wash_acknowledged()` → `_stop_alarm_loop()` → alarm stops, timer clears |
| **User clicks stop in PopOutTimerWindow** | `alarm_stopped` signal → `_stop_alarm_loop()` |

**Exit trigger:** Wash acknowledged → transitions to COMPLETE/EDIT

---

### 6. COMPLETE / EDIT

| Property | Value |
|----------|-------|
| **Entry** | Wash alarm acknowledged, or cycle queue advances |
| **UI** | Cycle graph has injection + wash flag markers; Edits tab available |

**Post-injection state:**
- Injection flags placed on detected channels (with per-channel times + confidence)
- Wash flags placed automatically at contact time expiry position
- Contact time marker (orange dashed line) on cycle graph
- All metadata stored in `Cycle` dataclass:
  - `injection_time_by_channel`: `dict[str, float]`
  - `injection_confidence_by_channel`: `dict[str, float]`
  - `injection_count`: incremented
- If more injections remain in a Binding/Kinetic cycle, queue loops back to PREPARATION
- If all injections done, cycle completes → next cycle in queue

**Edits tab** allows post-hoc adjustment of:
- Injection flag positions (drag or manual time entry)
- Wash flag positions
- Contact time values
- Flag deletion/addition

---

## Confirmation Answers Summary

### Q1: What defines "injections are completed"?

**All of the following exit the injection dialog as "completed" (accepted):**
1. All monitored channels autodetected (happy path) — 3s success display, then close
2. Grace period expired (10s after first detection) with partial results — immediate close
3. 60s hard timeout with partial results — immediate close
4. 60s hard timeout with NO results — 2s delay, then close
5. User clicked "Done Injecting" + 10s finalization window elapsed

**Only user cancel exits as "not completed" (rejected).**

The dialog emits `injection_complete` and calls `accept()` in all non-cancel cases. The coordinator then processes whatever detection results exist (could be all channels, some channels, or none).

### Q2: When does the Big Timer (PopOutTimerWindow) start?

**After the injection dialog closes and the injection flag is placed** — specifically in `_place_injection_flag()` (pump_mixin L350-365).

It does NOT start:
- ❌ At first autodetection inside the dialog
- ❌ When the injection popup first appears
- ❌ When the user clicks "Done Injecting"

It starts:
- ✅ When `injection_flag_requested` signal fires → `_place_injection_flag()` → checks `cycle.contact_time_seconds > 0` → calls `_start_manual_timer_countdown()` → `_auto_show_timer_window()` (because label contains "Contact")

### Q3: Auto-close delay — exactly 3 seconds?

**Yes, exactly 3 seconds for the "all detected" happy path:**
```python
# In _handle_all_detected():
QTimer.singleShot(3000, self._finalize_detection_and_close)
```

**For the total timeout (no detection) path: 2 seconds:**
```python
# In _on_detection_timeout():
close_timer.start(FINAL_MEASUREMENT_TIMEOUT_MS)  # 2000ms
```

---

## Key Source Files

| File | Role |
|------|------|
| `affilabs/dialogs/manual_injection_dialog.py` (816 lines) | Modal injection dialog — 60s window, per-channel detection, LED feedback |
| `affilabs/coordinators/injection_coordinator.py` (517 lines) | Orchestrates manual vs automated injection, processes detection results |
| `mixins/_pump_mixin.py` (2285 lines) | `_place_injection_flag()`, `_show_contact_time_marker()`, contact timer start |
| `affilabs/ui_mixins/_timer_mixin.py` (555 lines) | PopOutTimerWindow management, alarm loop, automatic wash flags |
| `affilabs/managers/flag_manager.py` | Flag storage (injection, wash, spike), contact timer overlay |
| `main.py` | Signal wiring: `injection_completed → _show_contact_time_marker`, `injection_flag_requested → _place_injection_flag` |
