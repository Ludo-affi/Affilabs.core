# Injection Workflow — Feature Reference Spec

> **Version**: v2.0.5-beta
> **Last updated**: 2026-02-24
> **Covers**: Manual injection (P4SPR), automated injection (P4PRO/PROPLUS), contact monitor, wash detection, flag placement, marker lifecycle

---

## 1. Overview

The injection system routes every injection event through `InjectionCoordinator`, which:

1. Determines mode (manual vs automated) from hardware + cycle settings
2. Runs the appropriate detection path
3. Emits flags per detected channel
4. Monitors for wash injection and moves the contact-end marker

### Key files

| File | Role |
|------|------|
| `affilabs/coordinators/injection_coordinator.py` | Orchestration, WashMonitor, mode routing |
| `affilabs/dialogs/manual_injection_dialog.py` | Hidden detection engine (200ms scan loop) |
| `affilabs/widgets/injection_action_bar.py` | Visible contact monitor UI (sidebar / queue panel) |
| `mixins/_pump_mixin.py` | Flag placement, contact marker, wash flag helpers |
| `affilabs/managers/flag_manager.py` | Flag domain model, timeline annotation |
| `affilabs/utils/spr_signal_processing.py` | `auto_detect_injection_point`, `detect_injection_all_channels` |

---

## 2. Mode Determination

**Entry**: `InjectionCoordinator.execute_injection(cycle, parent_widget)`

```
cycle.manual_injection_mode == "manual"    → _execute_manual_injection()
cycle.manual_injection_mode == "automated" → _execute_automated_injection()
cycle.manual_injection_mode == None        → hardware_mgr.requires_manual_injection
    P4SPR + no pump → manual
    P4SPR + AffiPump → automated
    P4PRO / P4PROPLUS → automated
```

**Special shortcut**: If `method_mode in ["pump", "semi-automated"]`, the manual injection dialog is skipped entirely — `injection_completed` fires immediately and the pump handles timing autonomously.

---

## 3. Manual Injection Flow (P4SPR)

### 3.1 Participants

- **`ManualInjectionDialog`** — runs hidden off-screen (`dialog.move(-9999, -9999)`). Its `showEvent` triggers the detection engine. It is never visible to the user.
- **`InjectionActionBar`** — the visible contact monitor panel in the right queue panel. Shows per-channel LED states and the contact countdown.
- **`_WashMonitor`** — per-channel QObject polling the SPR slope every 2s to detect the wash injection.
- **Background thread** — blocks on `done_event` while the detection + contact window runs.

### 3.2 Setup

1. Coordinator resolves `_detection_channels`:
   - `cycle.target_channels` if set (explicit override)
   - Keys of `cycle.concentrations` if set (auto-derive from sample map)
   - Otherwise `"ABCD"` for P4SPR, `"AC"` for P4PRO/PROPLUS
2. For non-P4SPR hardware: `_open_valves_for_manual_injection(channels)` routes 3-way valves
3. `done_event = threading.Event()` is created; background thread will block on it
4. On the main thread: `ManualInjectionDialog` is constructed and wired, `InjectionActionBar.show_phase2()` is called, `dialog.show()` fires

### 3.3 Detection engine

`ManualInjectionDialog._start_detection()` runs on `showEvent`:

- Sets `window_start_time = max(times[0], times[-1] - 45s)` — 45-second lookback
- **Pump transit delay** (P4PRO/PROPLUS only): if `pump_transit_delay_s > 0`, shifts `window_start_time` into the future (`times[-1] + delay`). The scan loop returns empty until real time catches up, preventing false positives on the bulk RI shift from the approaching sample plug.
- Starts two QTimers: detection every **200ms**, UI status every **1s**

**Per-channel scan** (`_scan_channel`, every 200ms):

```
Skip if already detected
Skip if fewer than 10 data points in window
Convert wavelength → RU: (wl - baseline_wl) × 355
sensitivity_factor = 0.75 if pump transit delay > 0, else 1.0
auto_detect_injection_point(times, ru, sensitivity_factor)
Accept if confidence >= 0.15
```

**Multi-channel timing** (P4SPR, 3-channel example):

Because the user pipettes manually, channels A/B/C are injected sequentially — typically 2–15 seconds apart. The detector handles this: each channel is scanned independently, and detection can fire at different times.

```
t=0s:   Phase 2 opens — all active channels set to PENDING (yellow)
t=2.1s: Channel A peak detected (conf 0.95) → LED green, WashMonitor[A] starts
t=3.6s: Channel B detected (conf 0.92)      → LED green, WashMonitor[B] starts
t=5.3s: Channel C detected (conf 0.88)      → LED green, WashMonitor[C] starts
t=5.3s: First detection already fired at t=2.1s; contact countdown is already running
t=20.3s (15s grace after A): D never detected → dialog finalizes with {A, B, C}
```

### 3.4 Completion paths

| Condition | Path | done_event |
|-----------|------|-----------|
| All monitored channels detected within grace | `_handle_all_detected()` → 3s delay → `injection_complete` → `accept()` | Set by `_on_bar_done` (wash) or `_on_dialog_complete` (no contact_time) |
| Partial detection (some channels), grace expired | `_finalize_detection()` with partial results → `injection_complete` → `accept()` | Same as above |
| Detection priority = "off" | User clicks "Done Injecting" manually | Set on Done click |
| User clicks "Done Injecting" (no auto-detect yet) | 10s post-done monitoring, then `_finalize_detection()` | Set same |
| 80s window expired, no detection | `_on_detection_timeout()` → warning shown 2s → `injection_complete` + `accept()` | `accepted_flag = False` → `injection_cancelled` emitted |
| 80s window expired, partial detection | `_on_detection_timeout()` → `_finalize_detection()` with partial results | Set by bar/wash |
| User clicks Cancel | `injection_cancelled` emitted, `reject()` | `accepted_flag = False` |

**Grace period**: 15s (`CHANNEL_SCAN_GRACE_SECONDS`) from the moment of **first** channel detection. If remaining channels don't detect within 15s, `_finalize_detection()` is called with whatever was found. This is what makes 3-channel injection work — the 4th (unused) channel doesn't block completion.

### 3.5 Contact time: with vs without

**No contact_time on cycle** (e.g., baseline, equilibration):
- First detection → `_fire_done()` after 1.5s
- `_show_contact_time_marker()` places no marker (no `contact_time` to compute from)
- Wash flags placed immediately at injection end via `_place_automatic_wash_flags()`

**contact_time set** (e.g., Binding cycle: 300s):
- First detection → contact countdown resets to full duration
- Marker placed at `injection_display_time + contact_time` (predicted contact end)
- WashMonitor runs per detected channel
- When wash detected → marker moves to actual wash time
- `_fire_done()` fires when all *detected* channels reach WASH state (see §4.3)

---

## 4. Contact Monitor (InjectionActionBar)

### 4.1 Channel states

```
INACTIVE  ○   Grey ring, no dot        — channel not part of this cycle
PENDING   ●◀  Orange ring, dot left    — monitored, not yet detected
CONTACT   ●   Green ring, dot center   — sample in contact
WASH      ▶●  Grey ring, dot right     — wash injection detected
```

### 4.2 Phase lifecycle

**Phase 1** (`show_phase1`): "Get Ready" — 10s countdown before monitoring begins. All active channels shown as PENDING. Timer fires `_fire_ready()` → transitions to Phase 2.

**Phase 2** (`show_phase2`): Contact monitor. Called directly by coordinator (Phase 1 may be skipped for automated flows). Channels start PENDING → CONTACT on detection → WASH on wash detection.

### 4.3 Completion logic

```python
# Was: checked _active_channels (all 4 monitored channels)
# Fixed: checks _detected_channels (only those that actually auto-detected)
wash_set = _detected_channels if _detected_channels else _active_channels
all_washed = all(widget[c].state == WASH for c in wash_set)
if all_washed:
    QTimer.singleShot(800, _fire_done)
```

**Why this matters for 3-channel injection**: `_active_channels` is `{"A", "B", "C", "D"}` (all channels are monitored). If only A/B/C detect, D stays PENDING forever. The old code would never call `_fire_done()` via the wash path — it would wait for the 80s fallback timer. The fix: track which channels actually detected (`_detected_channels`), and only require those to wash.

**Fallback**: If `_first_detection_fired` is still False after `PHASE2_SECONDS` (80s), `_tick()` force-fires `_fire_done()`. This is the safety net for dialog timeout + no detection.

### 4.4 Per-channel contact countdown

Each detected channel gets an independent QTimer counting from `contact_time` → 0 → negative (overrun). Overrun is intentional — the timer continues past 0 (shown in red) until wash is actually detected on that channel, at which point `_stop_channel_countdown(ch)` is called.

---

## 5. WashMonitor

**Class**: `_WashMonitor(QObject)` in `injection_coordinator.py`

**Algorithm** (polls every 2s, `POLL_INTERVAL_S`):

```
1. Guard: skip first 15s after monitor start (MIN_CONTACT_S) — injection transient
2. Fetch cycle_data[ch].spr (RU) from buffer
3. Exclude pre-injection data using _injection_cycle_t
4. Split last 20s into two 10s halves:
     slope_prev = polyfit(t[-20s..-10s])
     slope_now  = polyfit(t[-10s..now])
5. delta = abs(slope_now - slope_prev)
6. Adaptive threshold = max(0.5 RU/s, 4.0 × std(recent_slope_history))
7. If delta >= threshold for 2 consecutive polls → wash_detected.emit(ch, t_split)
   t_split = boundary between prev/now windows = the estimated wash start time
```

**Signal chain**:
```
_WashMonitor.wash_detected(ch, t_split)
  → _on_wash(ch, t_split) [closure in coordinator]
      → bar.set_channel_wash(ch)          [UI transition]
      → self.wash_detected.emit(ch, t)    [InjectionCoordinator signal]
          → main._on_wash_detected(ch, t) [moves contact marker]
```

**Known issue**: `_WashMonitor` is initialised with `injection_time=time.time()` (wall-clock). The `MIN_CONTACT_S` guard uses `time.time() - _injection_wall_time`, which is wall-clock elapsed — this works correctly. However, `_injection_cycle_t` (used to exclude pre-injection data) reads the *current* cycle data tail at monitor construction time, which is a cycle-relative time. These two time systems are separate and correct for their respective uses.

---

## 6. Contact End Marker Lifecycle

```
1. Injection detected on primary channel
       ↓
   _place_injection_flag() stores self._last_injection_display_time
       ↓
2. injection_completed fires
       ↓
   _show_contact_time_marker()
   marker_pos = _last_injection_display_time + cycle.contact_time
   → orange dashed InfiniteLine placed at predicted contact end
       ↓
3. WashMonitor detects wash on channel X
       ↓
   InjectionCoordinator.wash_detected.emit(ch, t_split)
       ↓
   main._on_wash_detected(ch, t_split)
   → _place_contact_marker(graph, t_split)
   → marker MOVES to actual wash time
```

If multiple channels wash at different times, the marker moves on each wash detection. Final position = last channel to wash.

If `contact_time` is not set on the cycle, `_show_contact_time_marker()` returns early (no marker placed).

---

## 7. Automated Injection Flow (P4PRO / P4PROPLUS)

`_execute_automated_injection(cycle, flow_rate)` runs on a background thread:

1. Stop pump and wait for idle (30s timeout)
2. Route based on `cycle.injection_method`:
   - `"simple"`: `pump_mgr.inject_simple(flow_rate, channels=cycle.channels)`
   - `"partial"`: `pump_mgr.inject_partial_loop(flow_rate, channels=cycle.channels)`
3. `injection_completed.emit()` on success

The `ManualInjectionDialog` is not used. Flag placement via `injection_flag_requested` happens through the retroactive scan path or coordinator-driven detection.

---

## 8. Flag Placement

**Per detected channel**, the coordinator emits `injection_flag_requested(ch, raw_time, confidence)`.

`_place_injection_flag()` in `_pump_mixin.py`:

```
raw_time (RAW_ELAPSED) → injection_display_time (cycle-relative):
    injection_display_time = injection_time - clock.convert(start_cursor, DISPLAY → RAW_ELAPSED)

Guard: if injection_display_time < 0 → clamp to 0.0 (auto-detection before cycle start)
Guard (flag_manager): add_flag_marker() also clamps time_val < 0 → 0.0

Stores: self._last_injection_display_time = injection_display_time

Calls: flag_mgr.add_flag_marker(ch, injection_display_time, spr_val, 'injection')
```

**Wash flags** (`_place_automatic_wash_flags()`): placed when contact timer expires (timer path) or immediately if no contact_time (via `_show_contact_time_marker`). The WashMonitor path does **not** currently place a flag — it only updates the bar UI and moves the contact marker.

---

## 9. User-Facing Scenarios

### How much time does the user have?

**Phase 1 (Get Ready)**: `show_phase1` is **not called** by the coordinator. The bar goes directly to Phase 2 (`show_phase2`) when the dialog opens. There is no 10-second pre-countdown in the current flow.

**Phase 2 (Detection window)**: **80 seconds** hard timeout (`INJECTION_WINDOW_SECONDS`). The dialog scans every 200ms. The bar shows "Monitoring A, B, C, D for injection…" with a 1-second status update.

**Total time user has to inject**: **80 seconds** from the moment the injection step starts.

**Urgency feedback**: The dialog status text shows "🔍 Inject within {remaining}s ({elapsed}s used)..." in orange, updated every second. No alarm sound. No bar countdown — the bar timer only starts ticking once the *first* injection is detected (contact time countdown, not detection countdown). A user who hasn't injected yet sees a static "Monitoring…" message with no indication of urgency.

> **Gap**: No visible countdown in the bar for the detection window. Users don't know they have 80s and could miss the window silently.

---

### Scenario N — Failed to inject (80s, zero detection)

```
Bar:      All channels stay YELLOW (PENDING) for 80s
Dialog:   At 80s: shows "⚠ 60-second window expired — No injection peak detected
                          Manual adjustment available in Edits tab" (orange, 2s)
          Auto-closes after 2s
Bar:      Dismisses, returns to dormant state
Cycle:    CONTINUES — no halt, no error
Flags:    NONE placed
Marker:   NONE placed (no _last_injection_display_time)
User:     Must add flags manually in Edits tab
```

**What the user actually sees in the bar**: the panel goes idle with no explanation — the timeout message is only visible inside the hidden dialog for 2 seconds before it auto-closes. The user sees the bar disappear.

> **Gap**: User gets no persistent feedback in the bar that the injection was missed. The bar just vanishes.

---

### Scenario O — Injected in wrong channel (expects A/B, user pipettes C/D)

```
Detector: CHANNEL-AGNOSTIC — scans all channels in detection_channels ("ABCD" for P4SPR)
          Detects peak on C and D (where user actually injected)
Bar:      C and D go green (CONTACT), A and B stay yellow (PENDING)
Flags:    Injection flags placed on C and D
          A and B get NO injection flags
Mislabel: anomaly_detected signal exists on dialog but is NEVER emitted
          No visual warning shown to user in bar or graph
Cycle:    Continues with wrong-channel flags
User:     Discovers mislabel later in Edits tab (flags on C/D, not A/B)
```

> **Gap**: No real-time mislabel warning. The bar LEDs turning green on the wrong channels is the only visual signal — easy to miss if the user isn't watching closely.

---

### Scenario P — Forgot to wash (contact timer expires, no wash injection)

```
Timer:    Contact countdown reaches 0:00
Bar:      Timer continues counting into NEGATIVE (red): -0:01, -0:02, ...
          Channels stay GREEN (CONTACT) — no auto-transition to WASH
Timer mixin: _place_automatic_wash_flags() fires immediately at 0
          → Wash flags placed on all channels that had injection flags
          → Flag placed at injection_display_time + contact_time
          → Logged: "🧼 Automatic wash flag placed on channel {ch}"
Marker:   "Contact end" stays at injection + contact_time position (unchanged)
WashMonitor: Keeps polling — still looking for slope break
Cycle:    CONTINUES — no block at timer = 0
User:     Sees red negative timer, no further prompts
          Wash flags placed automatically, so Edits tab analysis is still possible
```

**Practical impact**: The experiment is recoverable. Delta SPR can still be calculated from the auto-placed wash flags, but the measurement end-time may be slightly off if the user eventually washed much later.

---

### Scenario Q — Wash late (washes after contact timer expired)

```
Timer:    Expired, showing -2:30 (red)
Auto wash flags: Already placed at injection + contact_time
WashMonitor: Still running, no timeout
User washes at contact_time + 150s
WashMonitor: Detects slope break on each channel → wash_detected.emit(ch, t_split)
Bar:      Channels transition CONTACT → WASH (sky-blue dot)
          _fire_done() called when all detected channels reach WASH
          Bar dismisses cleanly
Marker:   MOVES from original position to actual wash time (t_split)
Flags:    Wash flags already placed at contact_time (by auto-path)
          Actual wash time is later — MISMATCH between flag position and marker
Cycle:    Completes normally (background thread unblocks via _on_bar_done)
```

> **Gap**: Wash flags were placed at the predicted time (contact_time expiry); the actual wash happened later. The marker moves but the flag doesn't. In Edits tab the delta SPR measurement endpoint will be wrong.

---

### Scenario R — Wash early (before contact timer expires)

```
contact_time = 300s, user washes at t=45s
WashMonitor: MIN_CONTACT_S = 15s guard (skip injection transient)
             At t=15s post-injection: starts polling every 2s
             At t=45s: detects slope break (2 consecutive confirms)
             → wash_detected.emit(ch, t_split) where t_split ≈ 45s
Bar:      Channel immediately transitions CONTACT → WASH (sky-blue)
          If all detected channels wash: _fire_done() fires immediately
          Contact timer shows e.g. "3:45" remaining → stops mid-countdown
Marker:   Moves from injection+300s → actual wash at ~45s
Flags:    Wash flags NOT placed by WashMonitor (gap — only bar UI updated)
          Wash flags would only be placed by timer expiry (which hasn't happened)
Cycle:    ENDS EARLY — background thread unblocks, injection_completed fires
          The configured 300s contact_time is treated as a target, not a minimum
```

> **Gap**: Early wash produces no wash flag. The contact marker moves but no flag lands on the timeline at the wash point. User can't see the wash event in Edits tab.

> **Gap**: Cycle ends before configured contact time. For binding kinetics, an early wash may invalidate the measurement. No enforcement of minimum contact duration.

---

### Scenario S — Stop cycle mid contact time

```
User clicks Stop Cycle / Next Cycle while contact timer is running

InjectionActionBar._on_cancel():
  → Stops all timers (global + per-channel)
  → Clears _active_channels, _detected_channels
  → Resets all LEDs to grey (INACTIVE)
  → Calls _on_cancel_cb() → coordinator._on_dialog_cancelled()

Coordinator._on_dialog_cancelled():
  → accepted_flag = False
  → _stop_all_wash_monitors() — all WashMonitor QTimers stopped, dict cleared
  → done_event.set() — unblocks background thread
  → dialog.reject()

Background thread:
  → accepted = False → injection_cancelled.emit()
  → Valves closed (_close_valves_after_manual_injection)

Flags:    Injection flags already placed (if detection fired before stop) — PERSIST
          Wash flags NOT placed (timer didn't expire, WashMonitor stopped)
Marker:   "Contact end" marker STAYS on graph (not removed on cancel) ← stale
Bar:      Hidden, dormant
Cycle:    Terminates, moves to next cycle or stops queue
```

> **Gap**: Contact marker left on graph after cycle stops. Next cycle will show the stale orange line from the previous injection until a new marker overwrites it.

---

### Scenario A — P4SPR, 4 channels, all detect, contact_time set

```
Phase 2 opens → all 4 PENDING
A, B, C, D detected in sequence within grace window
All 4 channels CONTACT, 4 WashMonitors running
All 4 channels wash (slope break detected)
all_washed = True (_detected_channels = {A,B,C,D}) → _fire_done()
Contact marker moves to wash time of last channel
✓ Clean path
```

### Scenario B — P4SPR, 3 channels used (A/B/C), D unused

```
Phase 2 opens → all 4 PENDING (detection_channels always "ABCD" for P4SPR)
A, B, C detected within grace
15s grace expires → dialog finalizes with {A, B, C}
D stays PENDING; _detected_channels = {A, B, C}
A, B, C wash → all_washed checks {A,B,C} only → True → _fire_done()
✓ Fixed: previously would wait 80s fallback timer
```

### Scenario C — P4SPR, 2 channels, contact_time set, user-paced wash

```
A, B detect. C, D never detect (grace expires).
_detected_channels = {A, B}
A washes at t=45s → all_washed = False (B still CONTACT)
B washes at t=48s → all_washed = True → _fire_done()
✓ Works correctly
```

### Scenario D — No auto-detection, user clicks "Done"

```
80s window: no channel detects (very low signal, or detection_priority="off")
User clicks "Done Injecting"
10s post-done monitoring → _finalize_detection() with empty results
injection_complete emitted; accepted_flag = True
_process_detection_results: detected_injection_time is None
→ retroactive scan: detect_injection_all_channels() on full window at min_confidence=0.20
→ flags emitted for any channels found retroactively (or none if truly undetectable)
✓ Graceful degradation
```

### Scenario E — 80s timeout, partial detection (2 of 4 channels)

```
A, B detect at t=5s and t=8s
C, D never detect
80s window expires → _on_detection_timeout() → _finalize_detection({A,B})
injection_complete emitted; wash monitors running for A, B
A, B wash → _fire_done()
✓ Works correctly
```

### Scenario F — 80s timeout, zero detection

```
No channel detects in 80s
_on_detection_timeout(): warning shown 2s
injection_complete emitted; accepted_flag = False
Coordinator: injection_cancelled emitted
No flags placed; no marker placed
User must add flags manually in Edits tab
✓ Handled (user informed via warning message)
```

### Scenario G — User cancels mid-injection

```
Injection dialog showing (hidden)
User clicks Cancel in bar
_on_dialog_cancelled(): stop wash monitors, _dismiss_bar(), done_event.set()
accepted_flag = False → injection_cancelled emitted
Valves closed
No flags placed
✓ Clean cancel path
```

### Scenario H — contact_time NOT set on cycle

```
Injection detected
_show_contact_time_marker(): contact_time is None → returns early (no marker)
_on_dialog_complete(): contact_time falsy → done_event.set() immediately
_fire_done() called from bar (first detection → 1.5s → done, since no contact_time)
_place_automatic_wash_flags() called immediately from _show_contact_time_marker
No WashMonitors started (_has_contact_time = False)
✓ Fast path, no waiting
```

### Scenario I — P4PRO automated injection, AC channels

```
_execute_automated_injection() runs on BG thread
pump_mgr.inject_simple(flow_rate, channels="AC")
6-port valve routes sample; pump dispenses
injection_completed emits on success
_place_injection_flag called via injection_flag_requested
Contact marker placed if contact_time set
WashMonitor starts on A, C if contact_time set
✓ No dialog, no user interaction needed
```

### Scenario J — Retroactive scan finds injection on unexpected channel

```
User injected into D, but cycle.channels = "AC"
Retroactive scan detects D at confidence 0.35
Mislabel detection: D not in active_channels {"A", "C"}
injection_mislabel_flags["D"] = 'inactive_channel'
Warning logged; flag still placed on D
User informed in log / future triage dialog
⚠ Handled defensively; user should check Edits tab
```

### Scenario K — Negative injection display time (auto-detect fires before cycle start)

```
Auto-detection fires at raw t=12.2s
Cycle start raw = 17.4s (cursor position)
injection_display_time = 12.2 - 17.4 = -5.2s
Guard in _place_injection_flag: clamp to 0.0, log debug
Guard in flag_manager.add_flag_marker: also clamps to 0.0
Flag placed at t=0 (cycle boundary)
Contact marker placed at 0 + contact_time
✓ No crash; flag appears at cycle start
```

### Scenario L — WashMonitor false positive suppressed by CONFIRM_POLLS

```
At t=20s post-injection: sudden noise spike, delta_slope > threshold
_confirm_count = 1 (need 2 consecutive)
Next poll (t=22s): delta_slope back to normal → _confirm_count reset to 0
Wash NOT reported
At t=45s: actual wash injection — delta_slope high for 2 consecutive polls
Wash reported correctly
✓ Debouncing prevents false wash flags
```

### Scenario M — Contact countdown overrun (wash not detected yet)

```
contact_time = 300s
All channels detect; per-channel timers count from 5:00
At t=300s: timers reach 0:00
bar._ch_tick(): _ch_remaining[ch] goes negative → shown in red as "-00:15"
WashMonitor keeps polling; user should wash soon
When wash detected → _stop_channel_countdown(ch), timer hidden
If wash never detected: timer counts negative indefinitely until _fire_done() via another path
⚠ No hard overrun cap; user sees red overrun timer
```

---

## 10. Key Constants

| Constant | Value | Location | Meaning |
|----------|-------|----------|---------|
| `INJECTION_WINDOW_SECONDS` | 80s | `manual_injection_dialog.py:78` | Hard timeout for entire detection window |
| `CHANNEL_SCAN_GRACE_SECONDS` | 15s | `manual_injection_dialog.py:83` | Grace after first detection to find remaining channels |
| `PHASE1_SECONDS` | 10s | `injection_action_bar.py:176` | "Get Ready" countdown before Phase 2 |
| `PHASE2_SECONDS` | 80s | `injection_action_bar.py:177` | Detection window in bar (matches dialog) |
| `MIN_CONTACT_S` | 15s | `injection_coordinator.py:93` | Ignore first 15s of contact (injection transient) |
| `HARD_MIN_SLOPE` | 0.5 RU/s | `injection_coordinator.py:94` | Minimum detectable wash slope change |
| `SIGMA` | 4.0 | `injection_coordinator.py:95` | Noise σ multiplier for adaptive wash threshold |
| `CONFIRM_POLLS` | 2 | `injection_coordinator.py:96` | Consecutive polls above threshold required to confirm wash |
| `POLL_INTERVAL_S` | 2s | `injection_coordinator.py:89` | WashMonitor polling rate |
| `FLUIDIC_PATH_VOLUME_UL` | 8.0 µL | `injection_coordinator.py:61` | Dead volume for pump transit delay calculation |
| Min confidence (live) | 0.15 | `manual_injection_dialog.py` | Threshold for live per-channel scan |
| Min confidence (retro) | 0.20 | `injection_coordinator.py` | Threshold for retroactive full-window scan |
| 355 RU/nm | — | `manual_injection_dialog.py` | Wavelength → RU conversion |

---

## 11. Known Gaps

> **Status as of v2.0.5-beta (Feb 2026):** All code gaps fixed. Gap 7 and 10 are design decisions — see notes.

| # | Gap | Status | Notes |
|---|-----|--------|-------|
| 1 | **No detection countdown in bar** | ✅ Fixed | `_tick()` waiting branch shows live countdown with urgency colours (grey → amber ≤ 20s → red ≤ 10s) |
| 2 | **Bar timeout message not visible** | ✅ Fixed | `show_injection_missed()` called from coordinator on lifecycle timeout; bar shows persistent message, auto-dismisses after 8s |
| 3 | **No mislabel warning** | ✅ Fixed | `show_mislabel_warning(detected, expected)` called after retroactive scan when `injection_mislabel_flags` is non-empty |
| 4 | **No wash flag from WashMonitor** | ✅ Fixed | `_on_wash_detected()` in `_pump_mixin` now calls `flag_mgr.add_flag_marker(..., 'wash')` at `t_split` |
| 5 | **Early wash flag mismatch** | ✅ Fixed | Covered by Gap 4 fix; wash flag placed at `t_split` (actual wash time) |
| 6 | **Contact marker not removed on cancel** | ✅ Fixed | `_on_injection_cancelled()` removes `_contact_time_marker` from graph |
| 7 | **No minimum contact time enforcement** | Design decision | `contact_time` is advisory. WashMonitor fires whenever slope breaks, regardless of elapsed time. Enforcing a hard minimum would block the background thread unnecessarily. Document in user guide instead. |
| 8 | **Overrun cap missing** | ✅ Fixed | `_ch_tick()` stops at `–_OVERRUN_CAP_S` (−120s) and shows "No wash detected" label |
| 9 | **`measure_delta_spr` NameError** | ✅ Fixed | `start_target` / `end_target` now saved as locals before `_avg_at()` calls in `spr_signal_processing.py` |
| 10 | **Phase 1 (Get Ready) skipped** | Design decision | `show_phase1()` is dead code — coordinator goes directly to `show_phase2`. Phase 1 (10s settle period) is enforced by the fluidic step, not the bar. Leave as-is; remove if confusing. |
