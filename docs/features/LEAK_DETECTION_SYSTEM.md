# Live Optical Leak Detection

*Implemented: 2026-02-22 | Source: `mixins/_acquisition_mixin.py`*

---

## Overview

The leak detection system monitors per-channel signal intensity in real time during live acquisition and alerts the user via Sparq if a sudden, sustained drop is detected. The primary symptom this catches is water or buffer entering the optical path during an injection — which causes intensity to collapse to 10–15% of normal within seconds.

---

## How It Works

### 1. Baseline Establishment (0–30 s)

For the first 30 seconds of each acquisition session, the system tracks the **rolling maximum intensity** per channel. This establishes a per-channel baseline without any configuration needed.

- The baseline is the highest intensity seen per channel during the window
- After 30 s the baseline is **locked** — it won't drift up from later readings
- If acquisition is restarted, all state resets automatically (`_on_acquisition_started`)

### 2. Drop Detection

On every spectrum frame (after the baseline is locked), the system checks:

```
drop_ratio = current_intensity / baseline_intensity
```

If `drop_ratio ≤ 0.15` (intensity at or below 15% of normal), the channel enters a **low-signal state** and a timer starts.

### 3. Confirmation Window

To avoid false alerts from single bad reads or brief transients, the alert only fires if the signal stays below 15% for **≥ 3 consecutive seconds**.

If the signal recovers above 15% before 3 s elapse, the timer resets — no alert is raised.

### 4. Alert (fires once per channel per session)

When confirmed:
- A `logger.warning` is written with the exact drop ratio and duration
- A **Sparq push message** appears in the AI sidebar:

> **Warning — Possible optical leak on Channel X**
> Signal intensity dropped to **N% of normal** (M counts vs. K counts).
> This usually means liquid has entered the optical path — check the flow cell and fiber connections for water or buffer. If injections are in progress, pause and inspect the chip.

The alert fires **once per channel per session**. If channel A leaks and recovers, it will not alert again unless acquisition is restarted.

---

## Constants

| Constant | Value | Location | Description |
|----------|-------|----------|-------------|
| `_LEAK_DROP_THRESHOLD` | `0.15` | `_acquisition_mixin.py` | Alert threshold (15% of baseline) |
| `_LEAK_BASELINE_WINDOW` | `30.0 s` | `_acquisition_mixin.py` | Time to establish baseline |
| `_LEAK_CONFIRM_WINDOW` | `3.0 s` | `_acquisition_mixin.py` | Sustained low duration before alert |

---

## State Variables (per acquisition session)

| Variable | Type | Purpose |
|----------|------|---------|
| `_intensity_baseline` | `dict[str, float]` | Max intensity seen per channel during baseline window |
| `_intensity_baseline_locked` | `dict[str, bool]` | True once baseline window has elapsed |
| `_intensity_low_since` | `dict[str, float\|None]` | Timestamp when channel first went below threshold |
| `_leak_alerted` | `set[str]` | Channels that have already triggered an alert this session |
| `_acq_start_time` | `float\|None` | Acquisition start timestamp (for baseline window calculation) |

All state is initialized in `_on_acquisition_started` → clean slate on each new run.

---

## What It Detects

| Scenario | Detected? | Notes |
|----------|-----------|-------|
| Water entering flow cell mid-run | ✅ | Intensity drops to ~10% in <2 s |
| Buffer leak during injection | ✅ | Same mechanism |
| Fiber disconnection during run | ✅ | Signal goes to ~0% |
| Slow LED degradation over days | ❌ | Gradual drift, never crosses 15% in 3 s |
| Normal SPR signal variation | ❌ | Typical variation is <5%, far above threshold |
| Baseline window transient | ❌ | Baseline not locked yet — no check runs |

---

## Implementation Notes

- `_handle_intensity_monitoring` runs on the **processing thread** (not the Qt main thread). The Sparq push uses `QTimer.singleShot(0, _do_push)` to safely call the UI from a background thread.
- `intensity` in the spectrum data dict is the **peak signal** returned by the spectrum pipeline (not raw pixel max). It reflects the actual SPR-active wavelength window.
- The existing dark-noise check (`dark_noise × LEAK_THRESHOLD_RATIO`) was removed — it only caught near-total signal loss (fiber completely disconnected) and produced false negatives for partial leaks. The new baseline-relative check covers both scenarios.

---

## Related

- `affilabs/app_config.py` — `LEAK_DETECTION_WINDOW` (legacy sliding-window constant, no longer used for threshold but still used for buffer trimming)
- `affilabs/widgets/spark_sidebar.py` — `SparkSidebar.spark_widget.push_system_message()`
- `affilabs/utils/sensor_iq.py` — separate IQ system for optical quality (long-term trend, not sudden drops)
