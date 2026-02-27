# Device Health Dashboard FRS

**Version:** 0.1 (draft)
**Status:** Planned — signals implemented, dashboard not wired
**Owner:** Affilabs.core v2.1+

---

## 1. Purpose

Affilabs.core already computes a rich set of per-channel and per-session health signals. They are currently dispersed across 6+ widgets and services with no unified view. This document defines the **Device Health Dashboard** — a single surface that aggregates all health signals into one place the user can glance at to understand instrument state.

**Design principle:** All data already exists. The dashboard is a **wiring and display problem**, not a computation problem. No new sensors or algorithms are needed for Phase 1.

---

## 2. Current State — What Exists vs What Is Missing

### 2.1 Implemented signals (data ready to consume)

| Signal | Where computed | Current display | Gap |
|--------|----------------|-----------------|-----|
| **SensorIQ level** (GOOD/FAIR/POOR/CRITICAL) | `sensor_iq.py` per-frame | Legend dots (●) | No trend, no dashboard row |
| **P2P rolling noise** (RU, 5-frame) | `spectrum_helpers.py` | `CycleIntelligenceFooter` (hidden by default) | Dashboard row needed |
| **FWHM current** (nm) | `sensor_iq.py` / `iq_metrics` | Footer (hidden) | No trend, no dashboard row |
| **Wavelength position** (nm) | Pipeline per-frame | Legend ΔSPR value | No zone warning in dashboard |
| **Wavelength >690 nm alert** | `spectrum_helpers.py` | Spark bubble (once/session/ch) | No persistent indicator |
| **Leak alert** | `_acquisition_mixin.py` | Spark bubble + spectrum bubble | No persistent event log |
| **Bubble alert** | `air_bubble_detector.py` | Spark bubble (60 s cooldown) | No persistent event log |
| **Chip degraded (triage)** | `injection_coordinator.py` | Spark bubble via anomaly_detected | No persistent indicator |
| **Raw LED peak counts** | `spectrum_helpers.py` (intensity) | Device status tab (LED intensity values) | Not live-wired to dashboard |
| **Cycle quality score** (0–100) | `signal_quality_scorer.py` | Queue table row dot colour | No dashboard summary |
| **Run quality rating** (1–5 stars) | `signal_quality_scorer.py` | **Nowhere** — `run_scored` signal unconnected | Needs display |
| **Calibration success/fail history** | `device_history.db` | Triage message on failure only | No live indicator |
| **Hardware connection** | `hardware_manager.py` | Device status tab (prototype, not live-wired) | Needs live wiring |

### 2.2 Prototype shell (exists, not wired)

- `affilabs/widgets/device_status.py` — `DeviceStatusWidget`: hardware connection, subunit readiness (Sensor/Optics/Fluidics), LED intensity. API exists (`update_status()`, `update_system_status()`, `update_led_status()`), but **no coordinator feeds it live data**.
- `affilabs/sidebar_tabs/AL_device_status_builder.py` — sidebar tab that mirrors device_status with LED bars + maintenance stats section. Also **not wired to live data**.

### 2.3 Gaps — what does not yet exist

| Gap | Severity | Notes |
|-----|----------|-------|
| **Unified health coordinator** — nothing aggregates all signals | Critical | Needed to feed any dashboard |
| **Persistent fault event log** — leaks/bubbles/spikes are ephemeral (Spark only) | High | Users need to review what happened during a run |
| **FWHM trend across cycles** — per-frame value exists but not stored across cycle boundaries | Medium | Needed for chip degradation tracking over time |
| **Cross-channel %T comparison** — filling uniformity check (one channel vs others) | Medium | Useful first-30s alert; see §5.3 |
| **Raw peak trend** — LED intensity drift over a session | Medium | Early warning of fiber degradation |
| **Run quality rating display** — `run_scored` signal emitted but consumed nowhere | High | Already computed, just needs a widget |
| **Calibration health indicator** — no live badge showing last-cal result or cal age | Medium | Session-level health signal |

---

## 3. Proposed Dashboard — Design

### 3.1 Location options

| Option | Pros | Cons |
|--------|------|------|
| **A — Device Status sidebar tab** (extend existing) | Already has a tab; natural home | Tab is not visible during acquisition |
| **B — LiveRightPanel section** (Phase 2 stub exists) | Visible during live run | Right panel not yet implemented |
| **C — Floating panel** (like SpectrumBubble) | Always accessible | Another floating widget |
| **D — Expand CycleIntelligenceFooter** | Already in live view | Footer is narrow |

**Recommendation: Option A + B.** Sidebar tab = full health history + trends. LiveRightPanel = condensed live status (4-channel IQ + P2P + last fault). Phase 1 implements the sidebar tab (lowest friction — shell already exists).

### 3.2 Dashboard sections (sidebar tab — Phase 1)

```
┌─ DEVICE HEALTH ─────────────────────────────────────────────┐
│                                                              │
│  INSTRUMENT          ● Connected  FLMT09788                  │
│  Last calibration    Today 09:14  ✓ Passed                   │
│                                                              │
├─ CHANNEL STATUS ────────────────────────────────────────────┤
│  Ch  IQ       λ (nm)   P2P (RU)  FWHM (nm)  Status          │
│  A   ● GOOD   642.3    2.1       24.5       ✓ OK             │
│  B   ● FAIR   651.8    8.4       31.2       ⚠ Noisy          │
│  C   ● GOOD   639.1    1.8       22.8       ✓ OK             │
│  D   ● GOOD   644.2    2.3       25.1       ✓ OK             │
│                                                              │
├─ THIS SESSION ──────────────────────────────────────────────┤
│  Run quality         ★★★★☆  (4/5)                           │
│  Cycles scored       5 / 5                                   │
│  Faults detected     0 leaks · 1 bubble                      │
│                                                              │
├─ FAULT LOG ─────────────────────────────────────────────────┤
│  09:42:11  🫧 Bubble — Ch B  (resolved)                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Channel status row — field definitions

| Field | Source | Update rate | Threshold colours |
|-------|--------|-------------|-------------------|
| **IQ** | `SensorIQLevel` from `sensor_iq.py` | Per-frame | Green=GOOD/EXCELLENT, Amber=FAIR, Orange=POOR, Red=CRITICAL |
| **λ (nm)** | `app._latest_peaks[ch]` | Per-frame | Green=590–690, Amber=570–590/690–710, Red=<570/>710 |
| **P2P (RU)** | `SignalTelemetryLogger` rolling p2p | Per-frame | Green=<5, Amber=5–15, Red=≥15 |
| **FWHM (nm)** | `iq_metrics['fwhm']` | Per-frame | Green=<30, Amber=30–60, Red=≥60 |
| **Status** | Derived from worst of above | Per-frame | ✓ OK / ⚠ Noisy / ⛔ Fault |

### 3.4 Fault log — event sources

Events appended to an in-session list (cleared on `_on_acquisition_started`):

| Event | Source signal | Format |
|-------|---------------|--------|
| Leak detected | `spark_alert_signal` (starts with `⚠️ Leak`) | `HH:MM:SS 💧 Leak — Ch X` |
| Leak resolved | `spark_alert_signal` (starts with `✅ Leak resolved`) | `HH:MM:SS ✅ Leak resolved — Ch X` |
| Bubble detected | `spark_alert_signal` (starts with `🫧`) | `HH:MM:SS 🫧 Bubble — Ch X` |
| Chip degraded | `anomaly_detected('CHIP_DEGRADED', ch)` | `HH:MM:SS ⚠️ Signal broadening — Ch X` |
| Wavelength OOR | `spark_alert_signal` (starts with `⚠️ SPR peak out`) | `HH:MM:SS ⚠️ Peak OOR — Ch X (693nm)` |
| Calibration fail | `calibration_failed` signal | `HH:MM:SS ⛔ Calibration failed` |

All events timestamped with wall-clock time. Max 50 events retained (rolling, oldest dropped).

---

## 4. Planned Checks — Not Yet Implemented

### 4.1 Cross-channel %T uniformity (filling check)

**Problem:** When a user pipettes into P4SPR channels, some may have air pockets. %T is higher in channels with air pockets (dip shallows). If one channel's %T deviates >15pp from the mean of all active channels for >30s, it has not filled properly.

**Proposed algorithm:**
```
Every 5s, during first 60s of a cycle:
  active_channels = channels with data in last 5s
  if len(active_channels) < 2: skip
  mean_T = mean(%T across active channels)
  for each channel:
    if abs(channel_%T - mean_T) > 15pp for > 30s:
      emit once-per-cycle Spark message:
        "Channel X may not be fully filled — %T is 18pp below other channels.
         Re-pipette 50 µL into the inlet port."
```

**Confidence:** Medium — %T is geometry-dependent. The inter-channel relative comparison is more robust than any absolute threshold, but needs validation on real hardware data before enabling by default. **Implement behind `CHANNEL_TX_UNIFORMITY_CHECK = False` feature flag in settings.py.**

### 4.2 FWHM trend across cycles (chip degradation tracking)

**Problem:** A chip degrades gradually over many cycles. Per-frame FWHM is computed but not stored across cycle boundaries. No signal currently tracks whether FWHM is drifting upward over a session.

**Proposed algorithm:**
```
At end of each cycle:
  record mean(FWHM[last 30s of cycle]) per channel → append to _fwhm_history[ch]
  if len(_fwhm_history[ch]) >= 3:
    trend = linear_regression(_fwhm_history[ch])
    if trend.slope > 0.5 nm/cycle:
      emit Spark (once per session):
        "FWHM broadening across cycles — Ch X. Sensor chip may be degrading.
         Consider replacing the chip if binding signal quality declines."
```

**Home:** `SignalQualityScorer` — already cycle-scoped, natural fit.

### 4.3 LED raw peak drift (fiber/optical path integrity)

**Problem:** Gradual drop in raw LED peak counts across a session indicates fiber degradation, dirty optics, or LED aging. Not tracked.

**Proposed algorithm:**
```
Track mean(raw_peak) per channel per cycle (same pattern as FWHM trend).
If mean_peak[cycle_n] < 0.7 × mean_peak[cycle_1]: emit once-per-session alert.
```

**Home:** `SignalQualityScorer` or new `OpticalPathMonitor` service.

### 4.4 Run quality rating display

**Problem:** `SignalQualityScorer.run_scored` emits a `RunQualityScore` with star rating (1–5) at session end. This signal is **never connected to any UI element**.

**Fix:** Wire `run_scored` to:
1. Health dashboard "This Session" section (star display)
2. Notes tab experiment entry (auto-populate star rating field)
3. Experiment index (store with recording metadata)

This is a wiring task only — no new computation needed.

---

## 5. Implementation Plan

### Phase 1 — Wire existing signals to sidebar tab (v2.1)

**Scope:** No new algorithms. Wire what exists.

1. **`DeviceHealthCoordinator`** (new, `affilabs/coordinators/device_health_coordinator.py`)
   - Subscribes to: `spark_alert_signal`, `anomaly_detected`, `calibration_failed`, `hardware_connected/disconnected`, `run_scored`
   - Maintains: in-session fault log (list of `FaultEvent`)
   - Exposes: `get_channel_status(ch)` → dict with latest IQ, λ, p2p, FWHM, status_string
   - Updates dashboard widget on a 2s timer (no per-frame updates to sidebar)

2. **`DeviceHealthDashboard`** widget (extend `DeviceStatusWidget` or replace `AL_device_status_builder` sections)
   - Renders channel status table (4 rows)
   - Renders session summary (run quality stars, fault count)
   - Renders fault log (scrollable, max 50 entries)
   - `refresh(coordinator_snapshot)` — called by coordinator on 2s timer

3. **Wire `run_scored`** → Notes tab + experiment index

### Phase 2 — Live panel during acquisition (v2.1)

Condensed 4-channel status in `LiveRightPanel` (stub already in `affilabs/widgets/live_right_panel.py`):
- 4 rows: Ch A/B/C/D with IQ dot + P2P bar + λ value
- Updates per-frame via `AL_UIUpdateCoordinator`

### Phase 3 — Trend tracking (v2.2)

- FWHM trend across cycles (§4.2)
- LED raw peak drift (§4.3)
- Cross-channel %T uniformity (§4.1, behind feature flag)

---

## 6. Files

| File | Role | Status |
|------|------|--------|
| `affilabs/widgets/device_status.py` | `DeviceStatusWidget` — hardware + subunit readiness | Prototype, not wired |
| `affilabs/sidebar_tabs/AL_device_status_builder.py` | Sidebar device status tab builder | Stub, not wired |
| `affilabs/widgets/live_right_panel.py` | Phase 2 live condensed panel | Stub |
| `affilabs/coordinators/device_health_coordinator.py` | New — aggregates all health signals | **Not yet created** |
| `affilabs/utils/sensor_iq.py` | SensorIQ classification | ✅ Done |
| `affilabs/services/signal_telemetry_logger.py` | P2P + optical rolling buffer | ✅ Done |
| `affilabs/services/signal_quality_scorer.py` | Cycle + run quality scores | ✅ Done (run_scored unwired) |
| `affilabs/utils/signal_event_classifier.py` | Triage cascade (check_event_triage) | ✅ Done |
| `affilabs/utils/spectrum_helpers.py` | Wavelength OOR alert | ✅ Done |
| `mixins/_acquisition_mixin.py` | Leak detector | ✅ Done |
| `affilabs/services/air_bubble_detector.py` | Bubble detector | ✅ Done |
| `affilabs/coordinators/injection_coordinator.py` | CHIP_DEGRADED triage | ✅ Done |

---

## 7. What Good Looks Like

**Scenario 1 — Normal run:**
Dashboard shows 4 green rows, 0 faults, ★★★★☆ at end of session.

**Scenario 2 — Ch B has air pocket:**
P2P spikes → BUBBLE triage fires (or filling check fires if implemented) → fault log shows `🫧 Bubble — Ch B`. User re-pipettes. P2P drops → Ch B returns to green.

**Scenario 3 — Chip degrading:**
FWHM trends upward across cycles → dashboard row for Ch A turns amber → end-of-session message in Spark: "FWHM broadening detected — consider replacing chip."

**Scenario 4 — Optical fiber fault:**
Raw peak collapses → LEAK triage fires → red row in dashboard → fault log shows `💧 Leak — Ch C`. If signal doesn't recover after drying → escalation message in Spark: "Contact Affinite support."

---

**Last Updated:** 2026-02-26
**Codebase Version:** Affilabs.core v2.0.5 beta
