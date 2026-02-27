# Optical Fault Detection FRS

**Version:** 1.2
**Status:** Implemented (leak detector v2, air bubble detector v1)
**Owner:** Affilabs.core v2.0.5+

---

## Overview

### Device fault taxonomy

All faults that affect optical signal quality fall into one of four categories, ordered by severity and intervention type:

| Category | Component | Detection point | Who resolves |
|----------|-----------|----------------|--------------|
| **A — Fluidic / operational** | Liquid in optical path (leak); air bubble in flow cell | Software — real-time background detectors (this FRS) | User (self-service) |
| **B — Optomechanical / calibration** | Servo polarizer misalignment; LED intensity drift | Software — calibration failure diagnostics (CalibrationOrchestrator FRS) | User guided by Sparq calibration flow |
| **C — Hardware failure** | Optical fiber break or contamination; spectrometer detector failure | Software — calibration failure + Sparq escalation prompt | Affinite support (RMA or field service) |
| **D — Firmware / connectivity** | USB drop, controller crash | Software — hardware manager reconnect logic | User (reconnect) or Affinite support |

**Categories B and C are handled at the calibration layer** — servo and LED faults are diagnosed during `run_startup_calibration()` and surfaced through the existing `CalibrationOrchestrator` / `CalibrationService` triage flow (see `CALIBRATION_ORCHESTRATOR_FRS.md`). They are **not** re-detected in the live acquisition path.

**Category C (fiber/detector)** produces the same signal as a severe leak — a sustained raw intensity collapse that does not recover after the user dries the optical path. The Sparq message for a persistent leak includes an escalation step directing the user to contact Affinite support, who will confirm whether the fault is hardware-level and initiate an RMA if needed.

---

### Real-time detectors (Category A — this document)

Two independent background detectors monitor the live acquisition stream:

| Fault | Detector | Trigger | Alert |
|-------|----------|---------|-------|
| **Optical leak** (liquid in optical path) | `_handle_intensity_monitoring` in `_acquisition_mixin.py` | Raw intensity ≤15% of baseline sustained ≥3 s | Sparq bubble opens + spectrum bubble opens; auto-recal on recovery |
| **Air bubble** (bubble passing through flow cell) | `AirBubbleDetector` in `affilabs/services/air_bubble_detector.py` | std(λ, 30 frames) > 20 RU **AND** %T drops >10 pp within 30 s window | Sparq bubble: "Air bubble detected — push more liquid" |

All alerts route through `spark_alert_signal` (Qt Signal on `Application`) → `_on_spark_alert()` slot on the main thread → `spark_bubble.push_system_message`. No direct `QTimer.singleShot` calls from processing threads.

---

## 1. Optical Leak Detector

### 1.1 Symptom
Liquid (buffer, sample) enters the optical path — typically at the fiber tip/flow cell window interface. This **blocks white light** from reaching the spectrometer, causing a sustained, severe drop in raw detector counts.

### 1.2 Observable signal
- `np.max(raw_spectrum)` drops suddenly and **stays low** (not a transient spike)
- Typical: 60,000 counts (normal) → <9,000 counts (leak present)
- Wavelength output becomes unreliable simultaneously
- The drop persists until the optical path is dried

### 1.3 Detection algorithm
Implemented in `AcquisitionMixin._handle_intensity_monitoring()` (`mixins/_acquisition_mixin.py`).

```
Per-channel state:
  _intensity_baseline[ch]        : float — rolling max of raw_peak (set during baseline window)
  _intensity_baseline_locked[ch] : bool  — frozen after _LEAK_BASELINE_WINDOW seconds
  _intensity_low_since[ch]       : float | None — timestamp when drop first detected
  _leak_alerted[ch]              : set   — channels that have already fired alert this session
  _leak_recovered[ch]            : set   — channels where recovery message already sent

Thresholds (module-level constants in _acquisition_mixin.py):
  _LEAK_DROP_THRESHOLD     = 0.25    # Alert if peak ≤ 25% of baseline
  _LEAK_RECOVERY_THRESHOLD = 0.50    # Resolved if peak ≥ 50% of baseline (after alert)
  _LEAK_BASELINE_WINDOW    = 30.0    # Seconds to establish baseline (rolling max)
  _LEAK_CONFIRM_WINDOW     = 3.0     # Seconds of sustained low signal before alerting
```

**Baseline establishment:** The rolling max of `raw_peak` over the first 30 seconds of acquisition. Locked after the window expires. This ensures a transient startup glitch does not set an abnormally low baseline.

**Trigger condition:** `raw_peak ≤ baseline × 0.25` continuously for ≥3 seconds.

**Alert frequency:** Once per channel per acquisition session. If the signal recovers and drops again, no second alert is sent (avoids alert spam).

### 1.4 Data hook
`SpectrumHelpers.process_spectrum_data()` (`affilabs/utils/spectrum_helpers.py`) computes `np.max(data["raw_spectrum"])` and calls `app._handle_intensity_monitoring(channel, peak_data, timestamp)` on every frame.

### 1.5 Alert delivery — thread-safe signal path

`_push_leak_alert()` emits `self.spark_alert_signal.emit(msg)` — **not** `QTimer.singleShot`.

**Why:** `_handle_intensity_monitoring()` is called from the processing worker thread (`threading.Thread`). `QTimer.singleShot()` called from a plain thread (not a `QThread`) silently does nothing on Windows — no event loop is attached. All processing-thread → UI delivery must use Qt Signals.

Signal wiring in `main.py`:
```python
# Application class
spark_alert_signal = Signal(str)       # system alert text → main thread
leak_recalibrate_signal = Signal()     # auto-trigger quick cal after leak resolves

# Connected in signal wiring section
self.spark_alert_signal.connect(self._on_spark_alert)
self.leak_recalibrate_signal.connect(self._on_simple_led_calibration)
```

`_on_spark_alert(text)` runs on main thread:
- If `text.startswith('✅')`: closes spectrum bubble, pushes resolved message to Sparq
- Otherwise: opens spectrum bubble (`spectrum_bubble.show()`), pushes alert message to Sparq

### 1.6 Alert text
```
⚠️ Leak detected — Channel X

Signal dropped to N% of baseline (M vs B counts).

1. Pause if injections are in progress.
2. Check flow cell window — dry with lint-free swab.
3. Re-run calibration once dry.
4. If signal doesn't recover, contact Affinite support.
```

### 1.7 Recovery detection
After a leak alert fires, `_handle_intensity_monitoring()` continues monitoring the channel for recovery.

**Recovery condition:** `raw_peak ≥ baseline × 0.50` (50% of baseline recovered).

**Recovery flow:**
1. `_push_leak_resolved()` emits the resolved alert via `spark_alert_signal`
2. Immediately after, emits `leak_recalibrate_signal` to trigger auto-recalibration
3. Channel added to `_leak_recovered` set — prevents duplicate resolved messages

**Recovery alert text:**
```
✅ Leak resolved — Channel X

Signal has recovered — optical path looks clear.
Running a quick recalibration to restore the S-pol reference...
```

**Recovery alert frequency:** Once per channel per session (`_leak_recovered` set). Channels in `_leak_recovered` are skipped in subsequent frames.

### 1.8 Auto-recalibration on recovery
`leak_recalibrate_signal` triggers `_on_simple_led_calibration()` on the main thread.

**Recalibration behavior (leak path):**
- **Pause** (not stop) acquisition — recording and cycle position are preserved
- `_leak_recal_was_acquiring = True` is set before pausing
- Quick LED calibration runs (S-pol reference only)
- On success: `resume_acquisition()` restores live data; graph is **not** cleared
- Post-recal Sparq message sent via `spark_alert_signal`:

```
✅ Recalibration complete — data intact

Your recording is still running. The S-pol reference has been updated.
Redo this cycle when ready — the data before the leak is still saved.
```

**Flag `_leak_recal_was_acquiring`:** Distinguishes leak-triggered recal (use `resume_acquisition`) from user-triggered manual recal (use `start_acquisition`). Reset to `False` in the `finally` block of `_process_simple_calibration_result()`.

### 1.9 Session reset
On `_on_acquisition_started()`, all per-channel state dicts are cleared:
- `_intensity_baseline`, `_intensity_baseline_locked`, `_intensity_low_since`
- `_leak_alerted` set
- `_leak_recovered` set

A new session starts with a fresh baseline.

---

## 2. Air Bubble Detector

### 2.1 Symptom
An air bubble passing through the flow cell transiently disrupts the evanescent field. The refractive index of air (n≈1.0) vs buffer (n≈1.33) causes the SPR wavelength to become erratic **and** the mean transmittance (%T) to drop abruptly (the transmission dip deepens).

### 2.2 Observable signal
- `std(wavelength, 30-frame window)` spikes above 20 RU — the signal becomes noisy
- Mean `%T` drops by >10 percentage points (absolute) within the same 30 s window
  - Example: 77% → 50% = 27 pp drop → confirmed bubble
- Both effects are transient — signal recovers once the bubble clears

### 2.3 Mutual exclusion with leak detector
Leaks and bubbles are **mutually exclusive** faults on the same channel.
If `_leak_alerted` contains the channel (set by `_handle_intensity_monitoring`), `AirBubbleDetector.feed()` returns immediately and never triggers for that channel.

### 2.4 Detection algorithm
Implemented in `AirBubbleDetector` (`affilabs/services/air_bubble_detector.py`).

```
Stage 1 — Noise trigger:
  wl_std = std(wavelength_history[-30 frames])
  if wl_std < _STD_THRESHOLD_NM: return  # normal noise

Stage 2 — %T confirmation (within _CONFIRM_WINDOW_S = 30 s):
  t_baseline = max(%T seen in window)    # best/pre-bubble value
  t_drop_pp  = t_baseline − current_%T  # pp drop (positive = dip deepened)
  if t_drop_pp < _T_DROP_THRESHOLD_PP: return  # not a bubble

→ Confirmed: fire alert (subject to 60 s cooldown)

Thresholds (module constants in air_bubble_detector.py):
  _STD_THRESHOLD_NM    = 20 / 355 ≈ 0.056 nm   (20 RU)
  _T_DROP_THRESHOLD_PP = 10.0  pp               (e.g. 77%→67% = 10 pp)
  _STD_WINDOW_FRAMES   = 30    frames            (~30 s at 1 Hz per channel)
  _CONFIRM_WINDOW_S    = 30.0  s                 (%T history window)
  _BUBBLE_COOLDOWN_S   = 60.0  s                 per channel
```

### 2.5 Data hook
`SpectrumHelpers.process_spectrum_data()` calls:
```python
AirBubbleDetector.get_instance().feed(channel, float(wavelength), mean_t, timestamp, app)
```
on every frame where both `wavelength` and `mean_t` are available. `app` is passed for mutual exclusion (`app._leak_alerted`).

### 2.6 Alert delivery — thread-safe signal path
`AirBubbleDetector._fire_alert()` uses the same signal path as the leak detector:
```python
from PySide6.QtWidgets import QApplication
app = QApplication.instance()
if app is not None and hasattr(app, 'spark_alert_signal'):
    app.spark_alert_signal.emit(msg)
```
No `QTimer.singleShot` — see §1.5 for rationale.

### 2.7 Alert text
```
🫧 Air bubble detected — Channel X

Signal noise spiked (N RU std) and transmission dropped M percentage points.
Push more liquid to flush the bubble out.

P4SPR (manual): Pipette 50–100 µL running buffer slowly through inlet.
P4PRO / P4PROPLUS (automated): Run a 2–3 min buffer wash at normal flow rate.

Signal should recover within 1–2 minutes once the bubble clears.
```

### 2.8 Interaction with InjectionMonitor
The `_InjectionMonitor` existing `DEAD_ZONE_S = 15 s` absorbs most bubble-induced transients, preventing false injection detection. No additional cross-wiring needed.

---

## 3. Sparq Integration (All Fault Alerts)

All optical fault alerts route through `Application.spark_alert_signal` → `_on_spark_alert(text)` slot (main thread):

```python
def _on_spark_alert(self, text: str):
    if text.startswith('✅'):
        # Recovery/resolved message — close spectrum bubble
        self.spectrum_bubble.hide()
        self.spark_bubble.push_system_message(text)
    else:
        # Fault alert — open spectrum bubble for visual context
        self.spectrum_bubble.show()
        self.spark_bubble.push_system_message(text)
```

- `SparkBubble` opens automatically (toggled visible if not shown)
- Message injected into Sparq chat as a system message (visually distinct from user messages)
- `SpectrumBubble` opened on fault (shows live spectrum so user can see the intensity collapse), closed on recovery
- No modal dialogs, no blocking popups

---

## 4. Files

| File | Role |
|------|------|
| `mixins/_acquisition_mixin.py` | `_handle_intensity_monitoring`, `_push_leak_alert`, `_push_leak_resolved`, `_on_spark_alert` — leak detection core + alert delivery slot |
| `mixins/_calibration_mixin.py` | `_on_simple_led_calibration` (pause/resume path), `_process_simple_calibration_result` (post-recal Sparq message) |
| `main.py` | `spark_alert_signal`, `leak_recalibrate_signal` on `Application` class; signal wiring |
| `affilabs/utils/spectrum_helpers.py` | Data hook — feeds raw_peak and wavelength to both detectors |
| `affilabs/services/air_bubble_detector.py` | `AirBubbleDetector` singleton — bubble detection logic + signal-based alert delivery |
| `affilabs/widgets/spark_bubble.py` | `SparkBubble.push_system_message()` — alert text display |
| `affilabs/widgets/spectrum_bubble.py` | `SpectrumBubble` — opened on fault, closed on recovery |

---

## 5. Thresholds Summary

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Leak** drop threshold | ≤25% of baseline | ≈75% raw count loss |
| **Leak** baseline window | 30 s | Rolling max of raw peak counts |
| **Leak** confirm window | 3 s | Must be sustained |
| **Leak** alert cooldown | Once per channel per session | Reset on new acquisition |
| **Leak** recovery threshold | ≥50% of baseline | After alert fired |
| **Leak** recovery cooldown | Once per channel per session | `_leak_recovered` set |
| **Bubble** std trigger | >20 RU (≈0.056 nm) | Over 30-frame rolling window |
| **Bubble** %T drop confirm | >10 pp absolute | e.g. 77%→67% = 10 pp |
| **Bubble** %T window | 30 s | Max−current within window |
| **Bubble** cooldown | 60 s per channel | Prevents alert storm |
| **Mutual exclusion** | Leak alerted → bubble suppressed | Per channel, per session |

---

**Last Updated:** February 26, 2026
**Codebase Version:** Affilabs.core v2.0.5 beta
