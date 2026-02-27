# Injection Workflow — Feature Reference Spec

> **Version**: v2.0.5-beta
> **Last updated**: 2026-02-26
> **Covers**: Manual injection (P4SPR), automated injection (P4PRO/PROPLUS), contact monitor, wash detection, flag placement, marker lifecycle

---

## 1. Overview

The injection system routes every injection event through `InjectionCoordinator`, which:

1. Determines mode (manual vs automated) from hardware + cycle settings
2. Runs the appropriate detection path
3. Emits flags per detected channel
4. Monitors for wash injection via fire #2 of `_InjectionMonitor`

### Key files

| File | Role |
|------|------|
| `affilabs/coordinators/injection_coordinator.py` | `_InjectionMonitor`, `_InjectionSession`, `InjectionCoordinator` |
| `affilabs/dialogs/manual_injection_dialog.py` | **State container only** — holds detection result attributes. No UI, no timers, no detection logic. |
| `affilabs/widgets/injection_action_bar.py` | Visible contact monitor UI (sidebar / queue panel) |
| `mixins/_pump_mixin.py` | Flag placement, contact marker, ΔSPR baseline snapshot |
| `affilabs/managers/flag_manager.py` | Flag domain model, timeline annotation |
| `affilabs/utils/spr_signal_processing.py` | `score_injection_event()` (multi-feature scorer called by `_InjectionMonitor`) |

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

- **`ManualInjectionDialog`** — a **state container** (`QObject`), NOT a visible dialog. Holds `detected_injection_time`, `detected_channel`, `_detected_channels_results`. Created on main thread. No timers, no scan loop.
- **`_InjectionSession`** — the lifecycle object that owns monitors, session state, and all event routing for a single injection. Runs on background "ManualInjectionExec" thread; all UI callbacks marshalled to main thread via `_invoke_on_main`.
- **`_InjectionMonitor`** — per-channel background thread. Polls SPR data every 2s, runs multi-feature scorer, fires `injection_detected` signal per channel. Runs for the full cycle duration (not just the dialog window). Fire #1 = injection; fire #2+ = wash.
- **`InjectionActionBar`** — the visible contact monitor panel. Shows per-channel LED states, ΔSPR in STATUS column, per-channel contact countdown.
- **Background thread** — blocks on `done_event` while the detection + contact window runs.

### 3.2 Setup

1. Coordinator resolves `_detection_channels`:
   - `cycle.target_channels` if set (explicit override)
   - Keys of `cycle.concentrations` if set (auto-derive from sample map)
   - Otherwise `"ABCD"` for P4SPR, `"AC"` for P4PRO/PROPLUS
2. For non-P4SPR hardware: `_open_valves_for_manual_injection(channels)` routes 3-way valves
3. `done_event = threading.Event()` is created; background thread blocks on it
4. On main thread: `ManualInjectionDialog` state container created, `InjectionActionBar.show_monitoring()` called, one `_InjectionMonitor` started per active channel

### 3.3 Detection engine — `_InjectionMonitor`

Polls every `POLL_INTERVAL_S` (2s). Per poll:

```
Step 1 — Quality gate:
    fetch cd.spr from buffer
    baseline_std = std of early 5 frames → must be < STD_MAX_RU (0.056 nm × 355)
    skip if std too high (noisy baseline)

Step 2 — Two rolling windows (5 frames each, WINDOW_FRAMES=5):
    window_prev = spr[-10:-5]   (older)
    window_now  = spr[-5:]      (recent)
    delta = mean(window_now) - mean(window_prev)   ← signed, bidirectional

Step 3 — Adaptive threshold:
    threshold = max(HARD_MIN_RU, SIGMA × baseline_std_ru)
    HARD_MIN_RU = 5.0 RU, SIGMA = 3.0 (from settings)

Step 4 — Dead zone after each fire:
    DEAD_ZONE_S = 15s after each fire — skip polls to absorb biphasic bulk-RI artifact

Step 5 — Confirmation:
    Requires CONFIRM_FRAMES (2) consecutive polls above threshold
    t_fire = times[-CONFIRM_FRAMES]   ← backtracked to actual onset

Step 6 — Multi-feature scorer (score_injection_event):
    Runs on buffered data at t_fire. Computes P2P, %T dip+recovery, slope change, λ onset.
    Score ≥ 0.65 with ≥2 features → INJECTION_DETECTED confirmed
```

`_fire()` increments `_fire_count` per monitor instance. The DEAD_ZONE_S rearms the same monitor for wash detection (fire #2).

### 3.4 Fire routing — injection vs wash

`_InjectionSession._on_detected(ch_upper, approx_t)`:

```python
_fire_counts[ch_upper] += 1
fire_num = _fire_counts[ch_upper]

if fire_num == 1:
    _handle_injection(ch_upper, approx_t)   # first step-change = injection
else:
    _handle_wash(ch_upper, approx_t, fire_num)   # subsequent = wash (P4SPR manual buffer flush)
```

**`_handle_injection`**: stores result in `dialog._detected_channels_results`, calls `bar.update_channel_detected(ch, True)`. On P4SPR: unblocks BG thread after first channel detected (`_on_detection_complete`). Monitors kept alive (P4SPR) or stopped (P4PRO/PROPLUS).

**`_handle_wash`**: calls `bar.set_channel_wash(ch)` + `SignalQualityScorer.notify_wash_detected(ch)`. Fires independently per channel.

**`_on_detection_complete`** behaviour by hardware:
- P4SPR: does NOT stop monitors — keeps them alive for wash fire #2+
- P4PRO/PROPLUS: stops all monitors immediately (simultaneous injection, no manual wash step)

### 3.5 ΔSPR in Contact Monitor STATUS column

STATUS column shows:
- `—` before injection detected on that channel
- `+N RU` / `-N RU` from injection baseline after detection (live, refreshed every tick)
- `Wash` after `set_channel_wash()` called on that channel

Baseline is snapshotted in `_pump_mixin._place_injection_flag()` using `spr_val` already time-matched to `t_fire` via `argmin(|cd.time - injection_time|)`. Called via `bar.set_injection_baseline(ch, spr_val)` immediately after flag placement. This gives ΔSPR = 0 RU at injection and grows with the binding response.

### 3.6 Completion paths

| Condition | Path | done_event |
|-----------|------|-----------|
| First channel detected (P4SPR) | `_handle_injection` → 300ms delay → `_on_detection_complete` → `done_event.set()` | Set immediately |
| All expected channels detected (P4PRO) | `_handle_injection` → `_on_detection_complete` | Set when all channels found |
| Contact timer expires | `_on_bar_done` → `_stop_all_monitors()` + `done_event.set()` (if not already set) | Set by bar done |
| User cancels | `injection_cancelled` signal → `_on_cancelled` → `_stop_all_monitors()` + `done_event.set()` | Set by cancel |
| Lifecycle timeout | `_on_timeout` → `_stop_all_monitors()` | Set by timeout |
| Cycle end (cleanup) | `InjectionCoordinator.cleanup_monitors()` → `session._stop_all_monitors()` | — |

Total timeout: `95s` (no contact_time) or `contact_time + 120 + 95s` (with contact_time).

### 3.7 Multi-channel timing (P4SPR sequential pipetting)

Because the user pipettes manually, channels are injected sequentially — typically 2–15s apart. Each channel's `_InjectionMonitor` fires independently. P4SPR unblocks the BG thread after the **first** channel detected (fire #1 on any channel), allowing the cycle contact countdown to start. Remaining channels continue to be monitored and detected independently.

Example with 3 channels:
```
t=0s    Phase 2 opens — all active channels set to PENDING (yellow)
t=3s    Channel A fire #1 → _handle_injection → done_event set, contact timer starts
t=8s    Channel B fire #1 → _handle_injection (done_event already set, just updates bar)
t=14s   Channel C fire #1 → _handle_injection
...
t=180s+ Wash injected...
t=195s  Channel A fire #2 → _handle_wash → bar.set_channel_wash("A")
t=197s  Channel B fire #2 → _handle_wash → bar.set_channel_wash("B")
t=199s  Channel C fire #2 → _handle_wash → bar.set_channel_wash("C")
```

### 3.8 Contact time: with vs without

**No contact_time on cycle** (e.g., baseline, equilibration):
- `_has_contact_time = False`
- Bar timer does not start on detection
- Monitors still run for full lifecycle timeout

**contact_time set** (e.g., Binding cycle: 300s):
- Per-channel independent countdown starts on `update_channel_detected(ch, True)`
- Marker placed at `injection_display_time + contact_time` (predicted contact end)
- When contact timer expires → `_on_bar_done` → stops monitors + unblocks BG thread if needed
- Wash is detected via `_InjectionMonitor` fire #2 (independent of timer expiry)

---

## 4. Contact Monitor (InjectionActionBar)

### 4.1 Channel states

```
INACTIVE  ○   Grey ring, no dot        — channel not part of this cycle
PENDING   ●◀  Orange ring, dot left    — monitored, not yet detected
CONTACT   ●   Green ring, dot center   — sample in contact
WASH      ▶●  Grey ring, dot right     — wash detected
```

### 4.2 Phase lifecycle

**`show_monitoring(channels, on_done, on_cancel, contact_time, buffer_mgr)`**: Single entry point. All active channels set to PENDING. Bar activates. ΔSPR refresh timer starts. Called by `_InjectionSession._setup()`.

**`update_channel_detected(ch, True)`**: Transitions channel to CONTACT. Per-channel countdown starts if `contact_time` was set. Role label goes green.

**`set_channel_wash(ch)`**: Transitions channel to WASH. Stops that channel's countdown timer. Role label goes sky-blue. STATUS shows "Wash".

### 4.3 Per-channel independent countdown

Each detected channel gets an independent `QTimer` counting from `contact_time` → 0. At 0:00, timer continues into negative (overrun shown in red, capped at −`_OVERRUN_CAP_S` = −120s showing "No wash detected"). Timer stops when `set_channel_wash(ch)` is called.

### 4.4 Completion logic

`_fire_done()` is triggered by `on_done` callback (set to `_on_bar_done` in session). Called when all active-channel countdowns complete or when coordinator explicitly calls `set_panel_active(False)`.

---

## 5. Contact End Marker Lifecycle

```
1. Injection detected on primary channel
       ↓
   _place_injection_flag() stores self._last_injection_display_time
   bar.set_injection_baseline(ch, spr_val) — snapshots ΔSPR=0 at injection
       ↓
2. injection_completed fires
       ↓
   _show_contact_time_marker()
   marker_pos = _last_injection_display_time + cycle.contact_time
   → orange dashed InfiniteLine placed at predicted contact end
       ↓
3. Contact timer expires OR wash detected on bar (via _on_bar_done)
       ↓
   Monitors stopped. Cycle continues.
```

> **⚠ Known gaps**: When `_InjectionMonitor` fire #2 detects wash, it calls `bar.set_channel_wash(ch)` and notifies `SignalQualityScorer` only. The contact marker does **not** move — it stays at the predicted `injection_time + contact_time`. No wash flag is placed from this path. Wash flags are only placed by the timer-expiry path (`_place_automatic_wash_flags()`). See §10 gap table.

If `contact_time` is not set on the cycle, `_show_contact_time_marker()` returns early (no marker placed).

---

## 6. Automated Injection Flow (P4PRO / P4PROPLUS)

`_execute_automated_injection(cycle, flow_rate)` runs on a background thread:

1. Stop pump and wait for idle (30s timeout)
2. Route based on `cycle.injection_method`:
   - `"simple"`: `pump_mgr.inject_simple(flow_rate, channels=cycle.channels)`
   - `"partial"`: `pump_mgr.inject_partial_loop(flow_rate, channels=cycle.channels)`
3. `injection_completed.emit()` on success

`ManualInjectionDialog` state container is not used. `_InjectionMonitor` runs for detection; monitors stopped immediately after all expected channels detected (P4PRO path in `_on_detection_complete`).

---

## 7. Flag Placement

**Per detected channel**, the coordinator emits `injection_flag_requested(ch, raw_time, confidence)`.

`_place_injection_flag()` in `_pump_mixin.py`:

```
raw_time (RAW_ELAPSED) → injection_display_time (cycle-relative):
    injection_display_time = injection_time - clock.convert(start_cursor, DISPLAY → RAW_ELAPSED)

Guard: if injection_display_time < 0 → clamp to 0.0 (auto-detection before cycle start)
Guard (flag_manager): add_flag_marker() also clamps time_val < 0 → 0.0

Stores: self._last_injection_display_time = injection_display_time
Stores ΔSPR baseline: bar.set_injection_baseline(ch, spr_val)  ← spr_val time-matched to t_fire

Calls: flag_mgr.add_flag_marker(ch, injection_display_time, spr_val, 'injection')
```

**Wash flags** (`_place_automatic_wash_flags()`): placed when contact timer expires. The `_InjectionMonitor` fire #2 (wash) path does **not** currently place a wash flag — it only updates the bar UI and `SignalQualityScorer`.

---

## 8. User-Facing Scenarios

### Scenario A — P4SPR, 4 channels, all detect, contact_time set

```
show_monitoring() → all 4 PENDING
A, B, C, D detected via _InjectionMonitor fire #1 (sequentially, per-channel)
All 4 CONTACT, per-channel countdowns running
done_event set on first detection (P4SPR)
At contact_time expiry: _on_bar_done → _stop_all_monitors
OR: _InjectionMonitor fire #2 per channel → set_channel_wash(ch)
✓ Clean path
```

### Scenario B — P4SPR, 3 channels used (A/B/C), D unused

```
show_monitoring() → all 4 PENDING
A, B, C detected via _InjectionMonitor fire #1
D never detects (monitor stays alive but never fires fire #1)
Contact timer counts down for A, B, C independently
At expiry: bar done fires, monitors cleaned up
D stays PENDING until cleanup
✓ Works — D's permanent PENDING is visually harmless
```

### Scenario C — No auto-detection (very low signal)

```
_InjectionMonitor never crosses threshold (baseline too noisy, quality gate blocks)
After lifecycle timeout (95s no-contact, or contact_time+215s with contact): _on_timeout
Bar shows dormant — no injection flags placed
User must add flags manually in Edits tab
```

### Scenario D — Wash detected early (before contact timer expires)

```
contact_time = 300s, user pipettes buffer at t=45s
_InjectionMonitor DEAD_ZONE_S = 15s after fire #1
At t=45s post-injection (>15s dead zone): fire #2 → _handle_wash
bar.set_channel_wash(ch) — ring goes sky-blue, STATUS shows "Wash"
Contact timer stops for that channel
Marker: DOES NOT MOVE (no _WashMonitor equivalent — gap, see §5)
No wash flag placed by this path (only auto-placed at timer expiry — gap, see §5)
```

### Scenario E — Contact countdown overrun (user forgets to wash)

```
contact_time = 300s
All channels detect; per-channel timers count from 5:00
At t=300s: timers reach 0:00, continue negative (shown red)
Timer mixin: _place_automatic_wash_flags() fires at expiry
  → wash flags placed at injection_display_time + contact_time
  → logged: "🧼 Automatic wash flag placed on channel {ch}"
_InjectionMonitor keeps polling (fire #2 still possible if user eventually washes)
At -2:00 cap: timer shows "No wash detected"
```

### Scenario F — Stop cycle mid-contact time

```
User clicks Stop Cycle / Next Cycle while contact timer is running
InjectionCoordinator.cleanup_monitors() called from cycle teardown
  → session._stop_all_monitors() — all _InjectionMonitor threads stopped
Bar resets (set_panel_active(False))
Flags: injection flags already placed (if detection fired before stop) — PERSIST
Marker: "Contact end" marker STAYS on graph ← stale until next injection overwrites it
Wash flags: NOT placed (timer didn't expire, auto-path not triggered)
```

### Scenario G — P4PRO automated injection, AC channels

```
_execute_automated_injection() runs on BG thread
_InjectionMonitor runs on A and C
pump_mgr.inject_simple(flow_rate, channels="AC")
6-port valve routes sample; pump dispenses
_InjectionMonitor detects on A and C → _handle_injection for each
_on_detection_complete: stops all monitors (P4PRO path)
injection_completed emits
Contact marker placed if contact_time set
```

### Scenario H — Negative injection display time (auto-detect fires before cycle start)

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

---

## 9. Key Constants

| Constant | Value | Location | Meaning |
|----------|-------|----------|---------|
| `POLL_INTERVAL_S` | 2s | `injection_coordinator.py` (`_InjectionMonitor`) | Monitor polling rate |
| `WINDOW_FRAMES` | 5 | `injection_coordinator.py` | Frames per rolling window |
| `HARD_MIN_RU` | 5.0 RU | `injection_coordinator.py` | Minimum detectable delta (floor) |
| `SIGMA` | 3.0 | `settings.py` (`INJECTION_DETECTION_SIGMA`) | Adaptive threshold multiplier |
| `CONFIRM_FRAMES` | 2 | `settings.py` (`INJECTION_CONFIRM_FRAMES`) | Consecutive polls required |
| `STD_MAX_NM` | 0.056 nm | `settings.py` (`INJECTION_STD_MAX_NM`) | Max baseline σ to allow polling |
| `DEAD_ZONE_S` | 15s | `settings.py` (`INJECTION_DEAD_ZONE_S`) | Post-fire silence window |
| `FLUIDIC_PATH_VOLUME_UL` | 8.0 µL | `manual_injection_dialog.py` | Dead volume for pump transit delay |
| 355 RU/nm | — | Throughout | Wavelength → RU conversion |
| `_OVERRUN_CAP_S` | 120s | `injection_action_bar.py` | Max negative overrun shown before "No wash detected" |

---

## 10. Known Gaps / Active Issues

> **Status as of v2.0.5-beta (Feb 2026)**

| # | Gap | Status | Impact |
|---|-----|--------|--------|
| 1 | **Contact marker does not move on wash detection** | ⚠ Open | Marker always shows predicted time, not actual wash time. `_WashMonitor` (which moved the marker) was removed when wash detection moved to `_InjectionMonitor` fire #2. |
| 2 | **No wash flag from `_InjectionMonitor` fire #2** | ⚠ Open | `_handle_wash()` only updates bar UI + scorer. No `flag_mgr.add_flag_marker(..., 'wash')` call. Wash flags are only auto-placed at timer expiry, which may not match actual wash time. |
| 3 | **No wash flag when wash is early** (before timer expires) | ⚠ Open | If user washes before `contact_time`, `_InjectionMonitor` fire #2 fires but places no flag. `_place_automatic_wash_flags()` never runs (timer didn't expire). Edits tab has no wash marker. |
| 4 | **Contact marker left on graph after cycle cancel** | ⚠ Open | `_on_injection_cancelled()` does not remove `_contact_time_marker`. Stale orange line persists until next injection. |
| 5 | **`_InjectionMonitor` wash detection pending live validation** | 🧪 Needs test | Fire #2 routing implemented (Feb 26 2026). Not yet validated on hardware. |
| 6 | **DEAD_ZONE_S = 15s** | Design decision | If user washes within 15s of injection, it won't be detected. This prevents the biphasic bulk-RI artifact from being flagged as a wash. Acceptable for normal lab use. |
