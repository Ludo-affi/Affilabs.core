# Contact Monitor Panel — Feature Requirement Specification

**Document Status:** ✅ Phase 1 — P4SPR binding experiments
**Last Updated:** February 22, 2026
**Source File:** `affilabs/widgets/injection_action_bar.py` (class `InjectionActionBar`)
**Parent Container:** `AL_method_builder.py` → `InjectionZone` QFrame (30% of queue splitter)

---

## §1. Purpose

The **Contact Monitor** panel is a persistent sidebar widget showing the real-time state of each physical flow channel (A, B, C, D) during an SPR binding experiment. It answers three questions at a glance:

1. **What role does each channel play?** — Sample / Reference / Buffer
2. **What phase is each channel in?** — idle / approaching / in contact / washing
3. **How much contact time remains?** — per-channel independent countdown

**Scope (Phase 1):** P4SPR manual injection with binding experiments only. The panel is **dormant** (greyed out) when no binding cycle is active — it only lights up for binding/kinetic/concentration cycles. Contact time tracking starts on auto-detection per channel. Wash state transitions automatically when the per-channel countdown expires.

**Zero-click design:** The panel has no interactive buttons during injection. Phase 1 shows a non-interactive countdown badge. Phase 2 shows monitoring state only. The user never needs to click anything — injection detection and contact timing are fully automatic.

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

| Element | Widget | Width | Content |
|---------|--------|-------|---------|
| Channel letter | `QLabel` | 16px fixed | `A` / `B` / `C` / `D` — always visible |
| Binding visualizer | `ChannelBindingWidget` | 80px fixed | Custom `QPainter` ring + dot (see §3) |
| Role label | `QLabel` (stretch=1) | flex | Sample / Reference / Buffer / `—` |
| Countdown timer | `QLabel` | 38px fixed | `M:SS` — hidden until CONTACT state |

Row font: 13px. Row padding: 5px top/bottom. Rows are separated by 1px `rgba(0,122,255,0.10)` dividers (last row has no bottom divider).

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
| INACTIVE | PENDING | `show_phase2()` or `set_upcoming()` called with channel in active set | `_set_channel_colors_for_phase1()` |
| PENDING | CONTACT | `update_channel_detected(ch, True)` — auto-detection engine detects injection on this channel | `update_channel_detected()` |
| CONTACT | WASH | Per-channel countdown reaches 0:00 | `_auto_wash_channel()` (automatic) |
| CONTACT | WASH | External call (e.g., pump completes wash cycle) | `set_channel_wash()` (manual) |
| Any | INACTIVE | `set_panel_active(False)` called (cycle end, cancel) | `_reset_all_leds()` |

### Detection-to-WASH is fully automatic for binding cycles

When `update_channel_detected(ch, True)` fires:
1. Symbol transitions to CONTACT (◉)
2. Role label turns green
3. If `contact_time` was set on the panel (via `show_phase2(contact_time=N)`), a **per-channel `QTimer`** starts counting down from `N` seconds
4. Timer label appears right-aligned in the row, showing `M:SS`
5. At ≤10 seconds remaining, timer label turns amber (#FF9500)
6. At 0:00 — timer shows `0:00` for 1.2 seconds, then:
   - Symbol auto-transitions to WASH (○·)
   - Role label turns sky-blue
   - Timer label hides
   - `channel_countdown_complete` signal emits the channel letter
7. When ALL active channels have completed their countdown → global `_fire_done()` triggers (800ms delay for visual feedback)

**No manual interaction is needed** — the entire flow from detection to wash is driven by the per-channel countdown.

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
| `set_upcoming()` called (binding cycle starts) | Panel activates | Auto-activate in `set_upcoming()` |
| `show_phase1()` called (injection prep) | Panel activates | Auto-activate in `show_phase1()` |
| `show_phase2()` called (injection monitoring) | Panel activates | Auto-activate in `show_phase2()` |
| `set_panel_active(True)` called explicitly | Panel activates | `_apply_active_appearance()` |
| `set_panel_active(False)` called (cycle end or timeout) | Panel goes dormant | `_apply_dormant_appearance()`, stops timers, resets channels |
| `_fire_done()` (countdown complete) | Panel goes dormant | `_apply_dormant_appearance()` |

**`hide()` is never called on the panel.** Only `set_panel_active(False)` is used for deactivation. The panel stays in its splitter slot at all times.

### Which cycle types activate the panel?

Only cycles that trigger injection flow activate the panel — specifically **Binding**, **Kinetic**, and **Concentration** cycles in manual mode. These are the only cycle types where `_schedule_injection()` calls `set_upcoming()` / `show_phase1()`.

Non-binding cycles (Baseline, Regeneration, Immobilisation, Wash, Auto-read) never call these methods, so the panel stays dormant throughout.

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
| Contact time duration | — | `_contact_countdown` — set once per `show_phase2()` |
| "All done" check | — | `_auto_wash_channel()` checks all active channels |

### Format

- `M:SS` (no leading zero for minutes): `3:00`, `0:47`, `0:05`
- Green (#34C759) by default
- Amber (#FF9500) when ≤10 seconds remaining
- `0:00` shown for 1.2s flash before hiding

---

## §6. Role Labels

Each channel row has a persistent role label set by the caller before injection begins.

### Valid roles

| Role | Meaning | Set when |
|------|---------|----------|
| `Sample` | Channel receiving analyte | Cycle config assigns sample channels |
| `Reference` | Channel with buffer only (negative control) | Cycle config assigns reference channels |
| `Buffer` | Channel left in running buffer | Channel not in active set but user wants to label it |
| `—` | Unassigned / idle | Default state, reset by `set_panel_active(False)` |

### API

```python
bar.set_channel_role("A", "Sample")
bar.set_channel_role("B", "Reference")
bar.set_channel_role("C", "Sample")
bar.set_channel_role("D", "—")
```

### Color behavior

Role text does NOT change. Only the label **color** shifts to reflect the channel's phase:

| Channel state | Label color | Token |
|---------------|------------|-------|
| INACTIVE | Muted grey | `#86868B` |
| PENDING | Amber | `#FF9500` |
| CONTACT | Green | `#34C759` |
| WASH | Sky-blue | `#5AC8FA` |

---

## §7. Phase 1 — Injection Prep (non-interactive countdown)

Phase 1 runs for **10 seconds** (`PHASE1_SECONDS = 10`) before the detection window opens.

### Behavior

- `show_phase1()` is called by the coordinator
- Panel activates (active appearance)
- Active channels set to PENDING state
- A **non-interactive blue badge** (`_phase1_badge` QLabel) appears in the lower control area showing the remaining seconds: `"10s"`, `"9s"`, ..., `"1s"`
- No buttons, no cancel option
- After 10 seconds, `show_phase2()` is called automatically

### UI elements

| Element | Widget | Notes |
|---------|--------|-------|
| Countdown badge | `QLabel` with blue pill style | Non-interactive, shows `Ns` format |
| Cancel | Not present | Phase 1 cannot be cancelled from this panel |

---

## §8. Phase 2 — Injection Monitoring (no buttons)

Phase 2 runs for up to **80 seconds** (`PHASE2_SECONDS = 80`), monitoring for injection detection.

### Behavior

- `show_phase2()` is called by the coordinator (or auto-called after phase 1)
- Detection window is active in the background (`ManualInjectionDialog`, off-screen)
- Status label shows: `"Monitoring {channels} for injection…"`
- No buttons of any kind
- When injection detected → `update_channel_detected(ch, True)` → channel transitions to CONTACT + per-channel countdown starts
- When all channels detected or 80s timeout → detection completes automatically

### UI elements

| Element | Widget | Notes |
|---------|--------|-------|
| Status label | `QLabel` | Informational only |
| Action button | Not present | Removed |
| Cancel button | Not present | Stop via cycle table only |

---

## §9. Public API

### Panel-level

| Method | Args | Effect |
|--------|------|--------|
| `set_panel_active(active)` | `bool` | Activate (True) or deactivate (False) the panel. Auto-called by injection methods; can also be called explicitly. `False` = dormant + stops timers + resets channels |
| `show_phase1(label, channels, on_ready, contact_time?)` | — | Phase 1 prep — auto-activates panel, sets PENDING on active channels, starts 10s non-interactive countdown badge |
| `show_phase2(channels, on_done, contact_time?)` | — | Phase 2 monitoring — auto-activates panel, sets PENDING, configures contact countdown duration. No cancel callback |
| `update_channel_detected(channel, detected)` | — | Per-channel detection event. `True` → CONTACT + starts per-channel timer. `False` → reverts to PENDING or INACTIVE |
| `set_channel_wash(channel)` | — | Force a channel to WASH state + stops its timer |
| `set_channel_role(channel, role)` | — | Set the role label text for a channel |
| `set_upcoming(label, channels)` | — | Pre-announce next injection — auto-activates panel |
| `update_status(text)` | — | Update Phase 2 status line |
| `hide()` | — | **Not used for normal operation.** Panel is always visible. Use `set_panel_active(False)` instead |

### Property

| Property | Type | Description |
|----------|------|-------------|
| `panel_active` | `bool` (read-only) | Whether the panel is currently active (binding cycle in progress) |

### Signal

| Signal | Payload | When |
|--------|---------|------|
| `channel_countdown_complete` | `str` (channel letter) | Per-channel countdown reaches 0 and auto-transitions to WASH |

---

## §10. Integration Points

### Injection Coordinator → Panel

**File:** `affilabs/coordinators/injection_coordinator.py`

```
_setup_on_main_thread():
  bar.set_channel_role("A", "Sample")   # from cycle metadata
  bar.set_channel_role("B", "Reference")
  bar.show_phase2(channels="AB", contact_time=180, ...)

_on_dialog_detected():
  bar.update_channel_detected("A", True)  # → CONTACT + starts A's 3:00 countdown
  bar.update_channel_detected("B", True)  # → CONTACT + starts B's 3:00 countdown

_on_timeout():
  QTimer.singleShot(0, lambda: bar.set_panel_active(False))   # dormant, never hide()
```

### Timer Mixin → Panel (wash auto-placement)

**File:** `affilabs/ui_mixins/_timer_mixin.py`

When `_place_automatic_wash_flags()` fires (contact timer expiry), it places wash flags on the live sensorgram. The **panel auto-transitions to WASH independently** via its own per-channel countdown — no additional call needed. Both systems (flag placement + panel visual) converge on the same event but are independently timed per channel.

### Channel Countdown Complete signal

Consumers can connect to `channel_countdown_complete` to trigger external wash actions when a specific channel's sample contact is done:

```python
bar.channel_countdown_complete.connect(lambda ch: logger.info(f"Channel {ch} wash due"))
```

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
