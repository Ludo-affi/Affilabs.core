# Manual Injection UI — State Machine Specification (FRS)
**P4SPR Manual Syringe Mode · Affilabs.core v2.0.5+**

> **Zero-click design (v2.0.5):** The injection flow is fully automatic. No user buttons are required at any point. The user can stop injection only via the cycle table. Phase 1 is a 10s non-interactive countdown; Phase 2 is 80s automated monitoring. Detection auto-completes.

---

## State Machine Overview

```
┌──────────┐    user starts     ┌─────────────┐   10s auto-    ┌─────────────────────┐
│          │    cycle queue      │             │   countdown    │                     │
│   IDLE   │ ─────────────────► │  PHASE 1    │ ─────────────► │ INJECTING/DETECTING │
│          │                    │  (10s prep) │                │   (0–80 seconds)    │
└──────────┘                    └─────────────┘                └─────────┬───────────┘
                                                                         │
                                     ┌───────────────────────────────────┘
                                     │  injection detected (auto) +
                                     │  flag placed +
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

### 2. PHASE 1 — PREPARATION

| Property | Value |
|----------|-------|
| **Entry** | Cycle queue scheduler reaches a cycle requiring injection |
| **Code path** | `InjectionCoordinator.execute_injection()` → `_determine_injection_mode()` → `_execute_manual_injection()` |
| **Duration** | **10 seconds** (`PHASE1_SECONDS = 10`) — non-interactive, cannot be stopped |
| **UI** | Contact Monitor panel activates; non-interactive blue countdown badge in panel |

**What happens:**
1. `InjectionCoordinator` determines injection mode (manual vs automated) based on:
   - Explicit `cycle.manual_injection_mode` setting (highest priority)
   - Hardware auto-detection: P4SPR without pump → manual
2. Sample info parsed from cycle metadata (`parse_sample_info(cycle)`)
3. Detection channels resolved: `cycle.target_channels` → `cycle.concentrations` keys → `"ABCD"` (P4SPR default) or `"AC"` (PRO default)
4. **Valves opened** for non-P4SPR hardware (`_open_valves_for_manual_injection()`)
5. `injection_started.emit("manual")` signal fired
6. Contact Monitor panel: `show_phase1()` called → panel activates, PENDING state on active channels, badge shows `10s` → `9s` → ... → `1s`

**UI elements:**
- Contact Monitor panel sidebar — active appearance, PENDING ring on channels
- Non-interactive blue pill badge in panel lower area: `"Ns"` countdown
- **No buttons.** No cancel option in the panel.

**Exit trigger:** 10s countdown completes → transitions to INJECTING/DETECTING (auto)

---

### 3. INJECTING / DETECTING

This is the core auto-detection state. The `ManualInjectionDialog` is active off-screen (invisible to user).

| Property | Value |
|----------|-------|
| **Entry** | Phase 1 countdown completes; `show_phase2()` called; dialog starts off-screen |
| **Duration** | Up to **80 seconds** (`INJECTION_WINDOW_SECONDS = 80`) |
| **UI** | Contact Monitor panel showing "Monitoring {ch} for injection…" — no buttons |
| **Code** | `affilabs/dialogs/manual_injection_dialog.py` (off-screen), `InjectionActionBar` (visible) |

#### Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `INJECTION_WINDOW_SECONDS` | **80** | Hard timeout for entire injection window |
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
            → baseline = mean of first N points
            → effective_rise_threshold = max(min_rise × sensitivity_factor, 3 × baseline_noise)
            → scan for sustained step-jump (all sustain_window consecutive points same-side of baseline)
        → if confidence > 0.30: mark channel as detected
            → InjectionActionBar.update_channel_detected(ch, True)
            → channel transitions to CONTACT state, per-channel countdown starts
```

#### Sub-states within INJECTING/DETECTING

```
┌───────────────────────────────────────────────────────────────┐
│ INJECTING/DETECTING (off-screen dialog)                        │
│                                                               │
│  ┌──────────────┐  1st channel   ┌──────────────────┐        │
│  │              │  detected       │                  │        │
│  │  SCANNING    │ ──────────────► │  GRACE_PERIOD    │        │
│  │  (0–80s)     │                │  (10s countdown)  │        │
│  └──────┬───────┘                └────────┬─────────┘        │
│         │ 80s timeout                     │                   │
│         │ (no detection)                  │ all channels      │
│         ▼                                 │ detected          │
│  ┌──────────────┐                         ▼                   │
│  │   TIMEOUT    │                ┌──────────────────┐         │
│  │  (2s close)  │                │  ALL_DETECTED    │         │
│  └──────────────┘                │  (1.5s confirm)  │         │
│                                  └──────────────────┘         │
│                                                               │
│  NO USER INTERACTION POSSIBLE — dialog is off-screen          │
│  Stop via cycle table only                                    │
└───────────────────────────────────────────────────────────────┘
```

#### Exit Conditions (4 paths, priority order)

| # | Condition | Delay before close | Signal emitted | Result |
|---|-----------|-------------------|----------------|--------|
| 1 | **All monitored channels detected** | 1.5 seconds (success confirmation) | `injection_complete` | `accept()` |
| 2 | **Grace period expired** (10s after first detection, not all channels found) | Immediate | `injection_complete` | `accept()` |
| 3 | **80s timeout, some channels detected** | Immediate (via `_finalize_detection`) | `injection_complete` | `accept()` |
| 4 | **80s timeout, NO channels detected** | 2 seconds (`FINAL_MEASUREMENT_TIMEOUT_MS`) | `injection_complete` | `accept()` |

**No user-initiated exit path.** There is no "Done Injecting" button and no cancel button in the injection panel. The dialog is off-screen and managed entirely by the coordinator.

#### Contact Monitor panel during detection

- Status label: `"Monitoring {channels} for injection…"`
- As each channel detects: ring → CONTACT (◉, green), per-channel countdown starts
- No buttons displayed at any time

---

### 4. CONTACT_TIME

| Property | Value |
|----------|-------|
| **Entry** | Injection dialog closes (accepted) AND injection flag placed AND `cycle.contact_time_seconds > 0` |
| **Duration** | User-defined per cycle (typically 60–300 seconds) |
| **UI** | PopOutTimerWindow (Big Timer) + timer button countdown in nav bar + Contact Monitor per-channel countdowns |
| **Code** | `_place_injection_flag()` in `mixins/_pump_mixin.py` → `_start_manual_timer_countdown()` in `affilabs/ui_mixins/_timer_mixin.py` |

#### When does the Big Timer start?

The Big Timer starts **immediately after the injection flag is placed** — not at first autodetection and not when the dialog opens.

**Signal chain:**
```
ManualInjectionDialog closes (accepted) — auto, no user action
  → InjectionCoordinator._execute_manual_injection()
    → _process_detection_results(dialog, cycle)
      → injection_flag_requested.emit(channel, time, confidence)
    → injection_completed.emit()

injection_flag_requested  →  _place_injection_flag()  [pump_mixin]
  → flag_mgr.add_flag_marker(channel, time, spr, flag_type='injection')
  → IF cycle.contact_time_seconds > 0:
      → main_window._start_manual_timer_countdown(label, seconds, sound=True)
        → IF "Contact" in label:
            → _auto_show_timer_window(label, seconds)
              → PopOutTimerWindow created/shown  ← BIG TIMER APPEARS HERE

injection_completed  →  _show_contact_time_marker()  [pump_mixin]
  → Places orange dashed "Contact end" vertical line on cycle graph
```

**If no contact_time (`cycle.contact_time_seconds == 0`):** injection detection completes, flag placed, Contact Monitor shows CONTACT state briefly then `_fire_done()` is called after 1.5s. No Big Timer. Panel goes dormant.

#### Timer Controls (PopOutTimerWindow)

| Control | Effect |
|---------|--------|
| **Pause** | `_on_pause_manual_timer()` — stops QTimer tick |
| **Resume** | `_on_resume_manual_timer()` — restarts QTimer tick |
| **Edit time** | While paused, user can adjust remaining seconds |
| **Clear** | Stops timer, clears state |
| **Restart** | Resets to `_manual_timer_initial_duration` |
| **Close window** | Timer keeps running in background; nav bar still shows countdown |

#### Timer Tick (`_on_manual_timer_tick`, 1Hz)

Each second:
1. Decrement `_manual_timer_remaining`
2. Update timer button in nav bar
3. Update PopOutTimerWindow display (if visible)
4. Update `flag_mgr.update_contact_timer_display()` (overlay on cycle graph)

**Contact Monitor per-channel countdowns run in parallel** — each channel has its own `QTimer` started at detection time, counting from `contact_time` seconds independently.

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
3. `_popout_timer.timer_finished(label, next_action)` — Big Timer shows completion
4. `flag_mgr.clear_contact_timer_overlay()` — removes countdown overlay from graph
5. **`_place_automatic_wash_flags()`** — auto-places wash flags on ALL channels that have injection flags
6. `_start_alarm_loop()` — ascending alarm tone every 1.5 seconds until acknowledged

**Contact Monitor panel:** Per-channel countdowns also expire independently (may be slightly out of sync with global timer). Each channel auto-transitions to WASH (○·) when its own countdown reaches zero.

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
- If more injections remain in a Binding/Kinetic cycle, queue loops back to PHASE 1
- If all injections done, cycle completes → next cycle in queue
- Contact Monitor panel: `set_panel_active(False)` → dormant (always visible, greys out)

**Edits tab** allows post-hoc adjustment of:
- Injection flag positions (drag or manual time entry)
- Wash flag positions
- Contact time values
- Flag deletion/addition

---

## User Interaction Summary

### What the user does during injection

| Phase | User action | System response |
|-------|------------|----------------|
| Phase 1 (10s) | Nothing | Panel shows non-interactive countdown badge |
| Phase 2 (0–80s) | Nothing | Panel shows monitoring state; channels light up as injection detected |
| Contact time | Optionally: Pause/Resume/Edit Big Timer | Timer adjusts; contact countdowns continue |
| Wash alarm | Click timer button or stop in Big Timer | Alarm stops; wash complete |
| Stop entire injection | Click cycle table stop | Cycle cancelled |

**The user never clicks "Done", "Cancel", or any injection button.**

---

## Confirmation Answers Summary

### Q1: What defines "injections are completed"?

**All of the following close the detection dialog as "completed" (accepted):**
1. All monitored channels autodetected (happy path) — 1.5s success confirmation, then close
2. Grace period expired (10s after first detection) with partial results — immediate close
3. 80s hard timeout with partial results — immediate close
4. 80s hard timeout with NO results — 2s delay, then close

**There is no user-initiated "cancel" exit path.** The injection cannot be cancelled from the panel — only from the cycle table.

### Q2: When does the Big Timer (PopOutTimerWindow) start?

**After the injection flag is placed** — in `_place_injection_flag()` (pump_mixin).

It does NOT start:
- ❌ At first autodetection inside the dialog
- ❌ When phase 1 countdown begins
- ❌ When phase 2 (monitoring) starts

It starts:
- ✅ When `injection_flag_requested` signal fires → `_place_injection_flag()` → checks `cycle.contact_time_seconds > 0` → calls `_start_manual_timer_countdown()` → `_auto_show_timer_window()`

### Q3: Auto-close delays

**1.5 seconds for "all detected" happy path:**
```python
# After all channels detected:
QTimer.singleShot(1500, self._finalize_detection_and_close)
```

**2 seconds for total timeout (no detection):**
```python
close_timer.start(FINAL_MEASUREMENT_TIMEOUT_MS)  # 2000ms
```

**Immediate** for grace period expiry and partial timeout paths.

---

## Key Source Files

| File | Role |
|------|------|
| `affilabs/dialogs/manual_injection_dialog.py` | Off-screen detection dialog — 80s window, per-channel detection, LED feedback |
| `affilabs/coordinators/injection_coordinator.py` | Orchestrates manual vs automated injection, processes detection results |
| `affilabs/widgets/injection_action_bar.py` | Contact Monitor panel — visible sidebar, phase 1 badge, channel state rings |
| `mixins/_pump_mixin.py` | `_place_injection_flag()`, `_show_contact_time_marker()`, contact timer start |
| `affilabs/ui_mixins/_timer_mixin.py` | PopOutTimerWindow management, alarm loop, automatic wash flags |
| `affilabs/managers/flag_manager.py` | Flag storage (injection, wash, spike), contact timer overlay |
| `main.py` | Signal wiring: `injection_completed → _show_contact_time_marker`, `injection_flag_requested → _place_injection_flag` |
