# Contact Monitor Panel — Feature Requirement Specification

**Document Status:** ✅ Phase 1 — P4SPR binding experiments
**Last Updated:** 2026-02-26
**Source File:** `affilabs/widgets/injection_action_bar.py` (class `InjectionActionBar`)
**Parent Container:** `AL_method_builder.py` → `InjectionZone` QFrame (30% of queue splitter)

---

## §1. Purpose

The **Contact Monitor** panel is a persistent sidebar widget showing the real-time state of each physical flow channel (A, B, C, D) during an SPR binding experiment. It answers three questions at a glance:

1. **What phase is each channel in?** — idle / approaching / in contact / washing
2. **How much ΔSPR has accumulated since injection?** — live per-channel STATUS column
3. **How much contact time remains?** — per-channel independent countdown

**Scope (Phase 1):** P4SPR manual injection with binding experiments only. The panel is **dormant** (greyed out) when no binding cycle is active — it only lights up for binding/kinetic/concentration cycles. Contact time tracking starts on auto-detection per channel.

**Zero-click design:** The panel has no interactive buttons during injection. The user never needs to click anything — injection detection and contact timing are fully automatic.

---

## §2. Visual Layout

```
┌─ CONTACT MONITOR ────────────────────────────────┐
│ A   ·○   Sample                          2:47   │
├─────────────────────────────────────────────────┤
│ B   ◉    Reference                       2:39   │
├─────────────────────────────────────────────────┤
│ C   ○·   Sample                                 │
├─────────────────────────────────────────────────┤
│ D   ○    —                                      │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
│   ·○ approaching  ◉ contact  ○· wash            │  ← legend
├─────────────────────────────────────────────────┤
│           [stacked idle/active controls]         │
└─────────────────────────────────────────────────┘
```

### Row anatomy (per channel)

Column headers: **CH | STATUS | TIME**

| Element | Widget | Width | Content |
|---------|--------|-------|---------|
| Channel letter + binding widget | `ChannelBindingWidget` | 44px fixed | Ring + dot, channel letter inside. State drives color (see §3) |
| STATUS label | `QLabel` (stretch=1) | flex | `—` before detection; `+N RU` / `-N RU` live ΔSPR from injection baseline after detection; `Wash` in WASH state |
| TIME label | `QLabel` | 46px fixed | `M:SS` countdown — hidden until CONTACT state |

Row font: 13px. Rows separated by `1px solid rgba(0,0,0,0.06)` dividers.

### Legend strip

A single 8px muted label below the four rows:
`·○ approaching  ◉ contact  ○· wash`

Explains the three binding symbol states. Always visible.

---

## §3. Binding Symbol — `ChannelBindingWidget`

A custom-painted `QWidget` (80×38–46 px) showing the SPR analyte lifecycle through a ring + dot metaphor.

### States

| State | Visual | Ring | Dot | Meaning |
|-------|--------|------|-----|---------|
| `INACTIVE` | `○` | Grey (#C7C7CC), 2px stroke | None | Channel not part of this cycle |
| `PENDING` | `·  ○` | Amber (#FF9500) | Amber, 6px radius, LEFT of ring | Injection in progress, sample approaching surface |
| `CONTACT` | `◉` | Green (#34C759) | Green, 6px radius, INSIDE ring | Sample bound to ligand on surface |
| `WASH` | `○  ·` | Grey (#86868B) | Sky-blue (#5AC8FA), RIGHT of ring | Buffer washing sample off surface |

### Geometry

- Ring radius: **13px**, stroke width: 2px, centered in widget
- Dot radius: **6px**, solid fill, no stroke
- Dot offset from ring center: **26px** (left for PENDING, right for WASH)
- Widget width: **80px**, height: 38–46px (auto from row)
- `QPainter` with `Antialiasing` render hint enabled
- `WA_OpaquePaintEvent = False` for transparent background

---

## §4. Channel States & Transitions

### State machine per channel

```
              injection             contact timer          countdown
  INACTIVE ──detected──→ PENDING ──auto-detect──→ CONTACT ──expires──→ WASH
     ↑                                                                   │
     └───────────────────── set_panel_active(False) / cycle end ────────┘
```

### Transition triggers

| From | To | Trigger | Method |
|------|----|---------|--------|
| INACTIVE | PENDING | `show_monitoring()` called with channel in active set | `_set_pending()` |
| PENDING | CONTACT | `update_channel_detected(ch, True)` — `_InjectionMonitor` fire #1 detected | `update_channel_detected()` |
| CONTACT | WASH | `set_channel_wash(ch)` called — from `_InjectionMonitor` fire #2 (P4SPR wash detection) | `set_channel_wash()` |
| CONTACT | WASH | Contact countdown expires → `_auto_wash_channel(ch)` (fallback, not currently called by timer) | `_auto_wash_channel()` |
| Any | INACTIVE | `set_panel_active(False)` called (cycle end, cancel) | `_reset_all_leds()` |

### Detection-to-CONTACT

When `update_channel_detected(ch, True)` fires:
1. Symbol transitions to CONTACT (◉ — green ring, dot center)
2. STATUS label starts showing live ΔSPR from injection baseline (refreshed by `_refresh_delta_spr()` every tick)
3. If `contact_time` was set (via `show_monitoring(contact_time=N)`), a **per-channel `QTimer`** starts counting down from `N` seconds
4. TIME label appears showing `M:SS`
5. At ≤10s remaining: TIME label turns amber (#FF9500)
6. At 0:00: timer continues negative (overrun, shown red), capped at −`_OVERRUN_CAP_S` (120s) showing "No wash detected"

### CONTACT-to-WASH

Triggered by `set_channel_wash(ch)` called from `_InjectionSession._handle_wash()` when `_InjectionMonitor` fires #2 (user pipettes buffer = second step-change detected on that channel):
1. Symbol transitions to WASH (○·)
2. STATUS label shows "Wash"
3. Per-channel countdown timer stops
4. `channel_countdown_complete` signal emits the channel letter (downstream consumers can react)

---

## §4.5. Dormant / Active Panel State

The Contact Monitor is either **dormant** (greyed out) or **active** (blue/green). This signals whether the panel is relevant to the current cycle.

**The panel is ALWAYS VISIBLE** — it never hides. Only its appearance changes.

### Appearance

| State | Frame BG | Border | Header color | Channel symbols | Idle text |
|-------|----------|--------|-------------|-----------------|-----------|
| **Dormant** | `#F2F2F7` (light grey) | `1px dashed #C7C7CC` | `#C7C7CC` (light grey) | All INACTIVE (grey rings) | "No binding cycle active" (`#C7C7CC`) |
| **Active** | `#F8F8FA` (near-white) | `1.5px solid rgba(0,122,255,0.20)` | `#86868B` (muted) | Per-channel state colors | "Waiting for injection…" (`#86868B`) |
| **Detected** | `#EDFAF1` (soft green) | `1.5px solid rgba(52,199,89,0.5)` | — | Green CONTACT states | Status + countdown |

### Activation rules

| Trigger | Result | Method |
|---------|--------|--------|
| `show_monitoring()` called (injection session starts) | Panel activates | `_apply_active_appearance()` |
| `set_panel_active(True)` called explicitly | Panel activates | `_apply_active_appearance()` |
| `set_panel_active(False)` called (cycle end or timeout) | Panel goes dormant | `_apply_dormant_appearance()`, stops timers, resets channels |

**`hide()` is never called on the panel.** Only `set_panel_active(False)` is used for deactivation.

### Which cycle types activate the panel?

Only cycles that trigger injection flow activate the panel — specifically **Binding**, **Kinetic**, and **Concentration** cycles in manual mode. Non-binding cycles (Baseline, Regeneration, Immobilisation, Wash, Auto-read) never call `show_monitoring()`, so the panel stays dormant throughout.

---

## §5. Per-Channel Independent Countdown

### Why independent timers?

On P4SPR, the user physically pipettes samples into channels A–D one at a time. There can be **5–15 seconds of delay** between the first and last channel injection. Each channel's contact time must count from its own detection moment, not from a global start.

Example with 180s contact time:
```
T=0s    Inject channel A → A detects at T=3s  → A countdown: 3:00 → 2:59 → ...
T=8s    Inject channel B → B detects at T=10s → B countdown: 3:00 → 2:59 → ...
T=12s   Inject channel C → C detects at T=14s → C countdown: 3:00 → 2:59 → ...
```

Channel A finishes contact at T=183s, channel C finishes at T=194s — an 11-second spread. Each row reflects its own truth.

### Implementation

| Component | Per-channel | Shared |
|-----------|------------|--------|
| `QTimer` (1s interval) | `_ch_timers[ch]` — one per channel | — |
| Remaining seconds | `_ch_remaining[ch]` — int | — |
| Timer label | `_ch_timer_labels[ch]` — `QLabel`, hidden by default | — |
| Contact time duration | — | `_contact_countdown` — set once per `show_monitoring(contact_time=N)` |

### Format

- `M:SS` (no leading zero for minutes): `3:00`, `0:47`, `0:05`
- Green (#34C759) by default
- Amber (#FF9500) when ≤10 seconds remaining
- `0:00` shown for 1.2s flash before hiding

---

## §6. STATUS Column — Live ΔSPR

The STATUS column (middle column in each row) shows live feedback per channel:

| Phase | Status text |
|-------|-------------|
| Dormant / INACTIVE | `—` |
| PENDING (monitoring, not yet detected) | `—` |
| CONTACT (injection detected) | `+N RU` or `-N RU` — live ΔSPR from injection baseline, updated every tick |
| WASH | `Wash` |

ΔSPR is computed as `cd.spr[-1] - _injection_spr[ch]` where `_injection_spr[ch]` is snapshotted at `t_fire` via `bar.set_injection_baseline(ch, spr_val)`. Refreshed by `_refresh_delta_spr()` on the main-thread tick timer.

---

## §7. Public API

### Panel-level

| Method | Args | Effect |
|--------|------|--------|
| `show_monitoring(channels, on_done, on_cancel, contact_time, buffer_mgr)` | — | **Primary entry point.** Activates panel, sets active channels to PENDING, starts ΔSPR refresh timer. `contact_time` (int/float/None) — if set, per-channel countdown starts on detection. `buffer_mgr` — needed for live ΔSPR reads. |
| `set_panel_active(active)` | `bool` | Activate/deactivate. `False` = dormant + stops all timers + resets all channels. Called by coordinator on cancel/timeout/cycle-end. |
| `update_channel_detected(channel, detected)` | — | Per-channel detection event. `True` → CONTACT + starts per-channel timer. `False` → reverts to PENDING. |
| `set_channel_wash(channel)` | — | Transition channel to WASH state, stop its timer. Called from `_InjectionSession._handle_wash()` on `_InjectionMonitor` fire #2. |
| `set_injection_baseline(channel, spr_at_injection)` | — | Set SPR baseline for ΔSPR display. Called from `_pump_mixin._place_injection_flag()` with time-matched SPR at `t_fire`. ΔSPR = 0 at injection point. |
| `update_status(text)` | — | Update status label text. |
| `show_injection_missed()` | — | Called by coordinator on lifecycle timeout with zero detections. Shows persistent "No injection detected" message before auto-dismiss. |
| `set_channel_role(channel, role)` | — | Exists but not wired — STATUS shows ΔSPR, not role text. |

### Property

| Property | Type | Description |
|----------|------|-------------|
| `panel_active` | `bool` (read-only) | Whether the panel is currently active (binding cycle in progress) |

### Signal

| Signal | Payload | When |
|--------|---------|------|
| `channel_countdown_complete` | `str` (channel letter) | Per-channel countdown auto-transitions to WASH (timer path only — not from `_InjectionMonitor` fire #2) |

---

## §10. Integration Points

### Injection Coordinator → Panel

**File:** `affilabs/coordinators/injection_coordinator.py` (`_InjectionSession._setup()`)

```python
# Called on main thread when session starts:
bar.show_monitoring(
    channels     = "ABCD",          # detection channels
    on_done      = self._on_bar_done,
    on_cancel    = self._on_cancelled,
    contact_time = cycle.contact_time,  # None if no contact time
    buffer_mgr   = self._buffer_mgr,
)

# On _InjectionMonitor fire #1 (injection detected):
bar.update_channel_detected("A", True)   # → CONTACT + starts A's countdown

# On _InjectionMonitor fire #2 (wash detected):
bar.set_channel_wash("A")                # → WASH, stops A's timer

# On timeout / cancel:
bar.set_panel_active(False)              # → dormant, never hide()
```

### Pump Mixin → Panel (ΔSPR baseline)

**File:** `mixins/_pump_mixin.py` (`_place_injection_flag()`)

```python
bar.set_injection_baseline(ch, spr_val)
# spr_val = cd.spr[argmin(|cd.time - injection_time|)]
# Called immediately after flag placement — sets ΔSPR = 0 at injection
```

### Timer Mixin → Panel (wash flag placement at timer expiry)

**File:** `affilabs/ui_mixins/_timer_mixin.py`

When `_place_automatic_wash_flags()` fires (contact timer expiry), it places wash flags on the live sensorgram via `flag_mgr`. The panel does **not** auto-transition to WASH at timer expiry — transition only happens via `set_channel_wash()` called from `_InjectionSession._handle_wash()`. Both systems are independent.

> **⚠ Gap**: If the user washes before the timer expires, `_InjectionMonitor` fire #2 calls `set_channel_wash(ch)` but does NOT call `_place_automatic_wash_flags()`. No wash flag is placed in that case.

---

## §11. Idle State

When no cycle is active (`set_panel_active(False)` called or app startup):

- All four channels show INACTIVE (○) with `—` role label in muted grey
- Lower section shows "All channels idle" centered text
- No timers visible
- Panel background: `#F2F2F7` with `rgba(0,0,0,0.08)` border (dormant)
- Panel is **visible** — never hidden

---

## §12. Phase 1 Scope Boundaries

### In scope (P4SPR binding)

- [x] 4-channel vertical layout with ring+dot binding visualizer (ring 13px, dot 6px, width 80px)
- [x] Per-channel independent contact countdown (auto-starts on detection)
- [x] Auto-transition CONTACT → WASH when countdown expires
- [x] Role labels (Sample / Reference / Buffer)
- [x] Legend strip for symbol states
- [x] `channel_countdown_complete` signal for downstream consumers
- [x] Zero-click injection flow (non-interactive phase 1 badge, no buttons in phase 2)
- [x] Panel always visible (never hidden, only dormant ↔ active)

### Out of scope (future phases)

- [ ] P4PRO/PROPLUS pump-driven injection timing
- [ ] Kinetic cycles (association → dissociation multi-phase per channel)
- [ ] Regeneration state tracking per channel
- [ ] Channel pair grouping (AC / BD) visual for P4PRO valve routing
- [ ] Historical injection log per channel (past N injections)
- [ ] Contact time estimation from sensorgram slope analysis

---

## §13. Styling Reference

| Element | Property | Value |
|---------|----------|-------|
| Panel background | `background` | `#F2F2F7` (dormant) / `#F8F8FA` (active idle) / `#EDFAF1` (detected) |
| Panel border | `border` | `1px dashed #C7C7CC` (dormant) / `1.5px solid rgba(0,122,255,0.20)` (active) / `rgba(52,199,89,0.5)` (detected) |
| Header | `font-size` | 9px, weight 700, letter-spacing 1.2px, color `#86868B` |
| Channel letter | `font-size` | 10px, weight 700, color `#86868B`, width 16px |
| Role label | `font-size` | 9px, color varies by state |
| Row font | `font-size` | 13px |
| Row padding | — | 5px top/bottom |
| Timer label | `font-size` | 10px, weight 700, monospace, color green/amber |
| Legend | `font-size` | 8px, color `#AEAEB2`, monospace |
| Row dividers | `border-bottom` | `1px solid rgba(0,122,255,0.10)` |
| Phase 1 badge | — | Blue pill label, non-interactive, shows `Ns` countdown |

### Color tokens

| Token | Hex | Usage |
|-------|-----|-------|
| `_GREEN` | `#34C759` | CONTACT state — ring, dot, label, timer |
| `_YELLOW` | `#FF9500` | PENDING state — ring, dot, label; timer ≤10s warning |
| `_GREY` | `#C7C7CC` | INACTIVE ring |
| `_MUTED` | `#86868B` | INACTIVE labels, header, channel letters |
| `_BLUE` | `#007AFF` | Panel border (active), phase 1 badge |
| Sky-blue | `#5AC8FA` | WASH dot, WASH label color |

---

## §14. File Map

| File | What it contains |
|------|-----------------|
| `affilabs/widgets/injection_action_bar.py` | `ChannelState`, `ChannelBindingWidget`, `InjectionActionBar` — all panel code |
| `affilabs/sidebar_tabs/AL_method_builder.py` | Panel instantiation + reparenting into `InjectionZone` QFrame |
| `affilabs/coordinators/injection_coordinator.py` | Wires `update_channel_detected()` from detection dialog; calls `set_panel_active(False)` on timeout |
| `affilabs/ui_mixins/_timer_mixin.py` | `_place_automatic_wash_flags()` — parallel wash flag system |
