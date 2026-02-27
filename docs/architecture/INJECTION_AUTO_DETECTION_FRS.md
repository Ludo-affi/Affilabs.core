# Injection Auto-Detection — Functional Specification

**Version:** 2.0.5 beta
**Verified against source:** Yes
**Last updated:** 2026-02-25
**Source files:**
- `affilabs/utils/spr_signal_processing.py` — algorithm layer
- `affilabs/coordinators/injection_coordinator.py` — orchestration layer
- `affilabs/dialogs/manual_injection_dialog.py` — UI/trigger layer

---

## 1. Overview

Injection auto-detection identifies the moment an analyte enters the flow cell by detecting a **sudden step-jump** of the SPR resonance wavelength away from its pre-injection baseline. Detection runs per-channel, produces a time + confidence score, and causes an injection flag to be placed on the sensorgram.

**Signal polarity:** Injection causes a **blue shift** (wavelength decreases) in this system. The detection algorithm is direction-agnostic — it detects any sustained step-jump from baseline, rising or falling.

**Detection philosophy:** An injection is a **step change**, not a slope/drift. Example: baseline 3 RU, sample enters, signal jumps to 9 RU. The algorithm finds the first point where the signal exceeds a threshold above the settled baseline AND stays on the same side of baseline for several consecutive points. Slow baseline drift does not trigger detection.

---

## 1b. Signal Inventory — Three Tracked Features

The detector monitors three independent signals per channel. These are the same features logged by `SignalTelemetryLogger` (see `affilabs/services/signal_telemetry_logger.py`):

| Feature | Symbol | Telemetry column | Description |
|---------|--------|-----------------|-------------|
| **Position** | λ | `dip_position_nm` | Current SPR resonance wavelength (nm). The primary measured value. Deviation from baseline position is the core injection signal. |
| **Slope** | dλ/dt | `slope_5s_nm_per_s` | Rate of change of λ over a 5-second rolling window (linear regression, nm/s). Positive = red shift (binding). Negative = blue shift (injection in this system). |
| **Noise floor (σ)** | σ | derived from `p2p_5frame_nm` | Standard deviation of λ over the baseline window. Sets the detection threshold. A high-noise baseline raises the threshold, making detection less sensitive — which is correct, because a noisy signal needs a larger step to be unambiguous. |

**Why these three?** Position tells us where we are; slope tells us where we are going; σ tells us how much to trust the position reading. Together, a credible injection event must show: (1) position deviated from baseline, (2) slope changed sign or magnitude at the right moment, (3) the deviation exceeds the noise floor by a meaningful margin.

---

## 2. System Architecture

```
ManualInjectionDialog (per tick, 200ms timer, off-screen on Windows)
  │  calls per-channel:
  ▼
auto_detect_injection_point(times, values, sensitivity_factor)
  │  returns: {injection_time, confidence, ...}
  │
  ├─ if detected → dialog marks channel LED green, stores result
  │               → InjectionActionBar.update_channel_detected(ch, True)
  │
  └─ when all channels detected OR 80s expires:
       dialog closes (auto — no user button)
         │
         ▼
       InjectionCoordinator._process_detection_results()
         │  if per-channel results present: emit injection_flag_requested per channel
         │  else: emit primary channel flag, then call _scan_all_channels_for_injection()
         ▼
       injection_flag_requested(channel, time, confidence)  ← Qt Signal
         │
         ▼
       FlagManager / SensogramPresenter → flag placed on sensorgram
```

---

## 3. Core Algorithm — `auto_detect_injection_point()`

**Source:** `affilabs/utils/spr_signal_processing.py`
**Called from:** `ManualInjectionDialog._check_for_injection_in_window()` (per channel, every 200ms)

### 3.1 Signature

```python
auto_detect_injection_point(
    times:              np.ndarray,       # Time array (seconds, RAW_ELAPSED)
    values:             np.ndarray,       # SPR signal (RU or wavelength nm)
    smoothing_window:   int = 11,         # Unused parameter (accepted, not applied)
    baseline_points:    int = 5,          # Initial points for baseline establishment
    min_rise_threshold: float = 2.0,      # Minimum absolute signal change to confirm
    sensitivity_factor: float = 1.0,      # Scales min_rise_threshold only (see §3.5)
) -> dict
```

Requires at least 10 points in each array; returns all-zero/None dict otherwise.

### 3.2 Step 1 — Baseline Establishment

**Design rule: 5 seconds OR 5 points, whichever gives more data.**

The baseline window is defined as the first N samples at the start of the detection window, where N satisfies both a minimum count and a minimum time coverage:

- **Minimum points:** `baseline_points = 5` (default parameter) — ensures at least 5 measurements regardless of acquisition rate
- **Minimum time:** equivalent to 5 seconds of data at the current acquisition rate (~1 Hz per channel = 5 points ≈ 5 seconds, consistent)
- **Maximum:** capped at 25% of total array length so the baseline doesn't consume most of the window

```python
baseline_end = min(baseline_points, int(len(values) * 0.25))
baseline_end = max(baseline_end, min(5, len(values) // 3))
```

Uses the first `baseline_end` points to compute:
- `baseline_mean` — mean of baseline window (λ position reference)
- `baseline_noise` — std dev (σ), floored at `0.1` RU (prevents zero-noise threshold)

**No linear trend is fit.** The baseline is a flat mean. Pre-injection drift is tolerated as long as the step-jump is large enough relative to noise.

**Why 5 points is sufficient:** At ~1 Hz acquisition the 5-point window covers 5 seconds of the pre-injection signal. That is long enough to estimate σ representative of real noise (not a single-point spike), and short enough that the signal hasn't drifted significantly from the true pre-injection value.

### 3.3 Step 2 — Threshold Calculation

```python
effective_rise_threshold = max(
    min_rise_threshold * sensitivity_factor,
    SIGMA_MULTIPLIER * baseline_noise,
)
```

The threshold is the **larger** of:
- `min_rise_threshold × sensitivity_factor` — absolute minimum rise (default 2.0 RU)
- `SIGMA_MULTIPLIER × baseline_noise` — N-sigma above the baseline noise floor

This ensures the detector never fires on noise (σ requirement) but always requires at least 2 RU of actual signal change.

### 3.3a — Sensitivity Knob: σ Multiplier

The σ multiplier is the primary sensitivity control for the injection detector:

| Multiplier | Behaviour | When to use |
|-----------|-----------|-------------|
| **3σ** (default) | Standard sensitivity. Fires when signal is 3 standard deviations above baseline. Appropriate for most experiments. | Normal conditions, good SNR |
| **4σ** (conservative) | Reduced sensitivity. Requires a larger step-jump relative to noise before triggering. Suppresses false positives from noisy baselines or temperature artefacts. | Noisy baseline, frequent false triggers |
| **2σ** (aggressive) | Increased sensitivity. May fire on smaller signal changes. Use only for very low-concentration analytes where the expected step is small. | Weak binders, high-affinity trace analytes |

**Rule of thumb:** Start at 3σ. If the detector fires during plain buffer flow (no injection), increase to 4σ. If it consistently misses real injections, drop to 2σ or lower the absolute `min_rise_threshold`.

**Current hardcoded value:** `3.0` (see §8 constants). The multiplier is not yet exposed to the user — it is a developer/calibration setting in `auto_detect_injection_point()`. To change it, pass a different value or modify the constant.

### 3.4 Step 3 — Step-Jump Detection

```python
deviation = values - baseline_mean
abs_deviation = np.abs(deviation)

sustain_window = max(3, min(6, len(values) // 30))
```

Scanning from `baseline_end` to `len(values) - sustain_window`:

```
for each point i:
    if abs_deviation[i] >= effective_rise_threshold:
        window = deviation[i : i + sustain_window]
        if np.all(window > 0) or np.all(window < 0):
            injection_idx = i  ← FOUND
            break
```

**Key properties of this detector:**
- Requires the signal to cross the threshold AND stay on the **same side of baseline** for `sustain_window` consecutive points (3–6 points depending on array length)
- No "wiggle room" within the sustain window — all points must be strictly same-sign
- No fallback: if no sustained crossing found, `injection_time = None` (no flag placed)
- Direction-agnostic: works for both upward and downward step-jumps

### 3.5 Sensitivity Factor

`sensitivity_factor` only scales `min_rise_threshold`. It does **not** change the noise-sigma multiplier (3.0) or the sustain window.

| Method mode (`cycle.detection_priority`) | `sensitivity_factor` | Effect |
|------------------------------------------|---------------------|--------|
| `"priority"` | `0.5` | Min threshold halved → fires at smaller steps |
| `"manual"` | `0.6` | Moderate sensitivity boost |
| `"auto"` / `"semi-automated"` | `1.0` | Default |
| `"off"` | — | `auto_detect_injection_point` is never called |

### 3.6 Step 4 — Confidence Scoring

Three sub-scores, weighted sum:

| Component | Formula | Weight |
|-----------|---------|--------|
| `deviation_confidence` | `min(abs_deviation[idx] / threshold, 1.0)` | 0.5 |
| `sustain_confidence` | `min(mean(abs_deviation[idx:idx+10]) / threshold, 1.0)` | 0.3 |
| `edge_confidence` | `0.3` if idx within 5% of array edges, else `1.0` | 0.2 |

```python
confidence = deviation × 0.5 + sustain × 0.3 + edge × 0.2
```

**Penalty:** if `abs_signal_rise < effective_rise_threshold`, confidence is halved (`× 0.5`).

`signal_rise` = distance from `baseline_mean` to the post-injection value at `injection_idx` (direction-aware signed value).

### 3.7 Return Dict

```python
{
    'injection_time':  float | None,  # Detected time (RAW_ELAPSED seconds)
    'injection_index': int | None,    # Array index
    'confidence':      float,         # 0.0–1.0
    'max_slope':       float,         # Slope at injection point (RU/s, signed)
    'signal_rise':     float,         # Signal change from baseline at detection (RU, signed)
    'snr':             float,         # abs_signal_rise / baseline_noise
    'baseline_noise':  float,         # Baseline std dev (RU)
}
```

---

## 4. Multi-Channel Detection — `detect_injection_all_channels()`

**Source:** `affilabs/utils/spr_signal_processing.py`
**Called from:** `InjectionCoordinator._scan_all_channels_for_injection()` (retroactive scan)

### 4.1 Signature

```python
detect_injection_all_channels(
    timeline_data:    dict,       # buffer_mgr.timeline_data {ch → ChannelBuffer}
    window_start_time: float,     # RAW_ELAPSED seconds (detection window start)
    window_end_time:   float,     # RAW_ELAPSED seconds (detection window end)
    min_confidence:    float = 0.70,
) -> dict
```

### 4.2 Per-Channel Processing

For each channel in `['a', 'b', 'c', 'd']`:
1. Extract `time` and `wavelength` arrays from `ChannelBuffer`
2. Mask to `[window_start_time, window_end_time]`
3. **Wavelength → RU conversion:** `window_ru = (window_wl - window_wl[0]) * 355.0`
   - Baseline = first wavelength in window (not global)
   - Scale factor 355.0 converts nm shift to pseudo-RU
4. Call `auto_detect_injection_point(window_times, window_ru)` with default sensitivity
5. Accept result only if `confidence >= min_confidence` (default 0.70)

### 4.3 Return Dict

```python
{
    'times':        {'A': 123.5, 'C': 124.1, ...},   # detected channels only
    'confidences':  {'A': 0.85, 'C': 0.72, ...},
    'all_results':  {'A': {...}, 'B': {...}, ...},     # full dict per channel including non-detections
}
```

---

## 5. Delta SPR Measurement — `measure_delta_spr()`

**Source:** `affilabs/utils/spr_signal_processing.py`
**Purpose:** Measures SPR shift from pre-injection baseline to end of contact phase (cycle result reporting).

### 5.1 Signature

```python
measure_delta_spr(
    times:          np.ndarray,
    spr_values:     np.ndarray,
    injection_time: float,        # Detected injection time (RAW_ELAPSED seconds)
    contact_time:   float,        # Contact phase duration (seconds)
    avg_points:     int = 3,      # Points averaged at each measurement site
    pre_offset:     float = 10.0, # Seconds before injection for baseline measurement
) -> dict
```

### 5.2 Measurement Points

```
START: injection_time - pre_offset  (10s before injection)
END:   injection_time + contact_time
```

Both use a centered `avg_points` window around the nearest data point.

### 5.3 Quality Assessment

| Condition | `quality` |
|-----------|-----------|
| Both actual times within 2s of targets | `"good"` |
| Either gap > 2s | `"extrapolated"` |
| Exception or insufficient data | `"failed"` |

### 5.4 Return Dict

```python
{
    'delta_spr':     float | None,  # end_spr - start_spr (RU)
    'start_spr':     float,
    'end_spr':       float,
    'start_time':    float,         # Actual time of start measurement
    'end_time':      float,         # Actual time of end measurement
    'start_indices': list[int],
    'end_indices':   list[int],
    'quality':       str,           # 'good' | 'extrapolated' | 'failed'
}
```

---

## 6. S/P Orientation Validation — `validate_sp_orientation()`

**Source:** `affilabs/utils/spr_signal_processing.py`
**Called from:** Calibration orchestrator (Step 5 QC)

Analyzes the P/S transmission spectrum in the 600–750 nm SPR region to validate that the servo polarizer is in the correct orientation.

### 6.1 Decision Logic

```
Compute P/S transmission
Find local min and max in 600–750 nm region
Compare each to edge mean (left + right 25% of SPR region)

min_deviation = local_min - edge_mean
max_deviation = local_max - edge_mean

if min_deviation < -5%:              → orientation_correct = True  (clear dip)
elif max_deviation > 10%:            → orientation_correct = False (clear peak = inverted)
elif abs(min_deviation) > abs(max_deviation): → orientation_correct = True, confidence ≤ 0.7
else:                                → orientation_correct = None  (indeterminate)
```

A flat spectrum (range < 5%) returns `orientation_correct = None`, `confidence = 0.0`.

### 6.2 Return Dict

```python
{
    'orientation_correct': bool | None,  # True / False / None (indeterminate)
    'peak_idx':    int,
    'peak_wl':     float,                # nm
    'peak_value':  float,                # % transmission at peak/dip
    'left_value':  float,                # mean transmission at left SPR edge
    'right_value': float,                # mean transmission at right SPR edge
    'is_flat':     bool,
    'confidence':  float,                # 0.0–1.0; ≤0.7 for weak signals
}
```

---

## 7. InjectionCoordinator — Orchestration Layer

**Source:** `affilabs/coordinators/injection_coordinator.py`

### 7.1 Signals

```python
injection_started          = Signal(str)             # injection_type: "manual" | "automated"
injection_completed        = Signal()
injection_cancelled        = Signal()
injection_flag_requested   = Signal(str, float, float)  # channel, injection_time, confidence
```

`injection_flag_requested` is the primary output — it causes the flag manager to place an injection marker on the sensorgram at the detected time.

### 7.2 Mode Determination

```python
InjectionCoordinator._determine_injection_mode(cycle) -> bool
```

| Priority | Condition | Result |
|----------|-----------|--------|
| 1 | `cycle.manual_injection_mode == "manual"` | Manual |
| 2 | `cycle.manual_injection_mode == "automated"` | Automated |
| 3 (fallback) | `hardware_mgr.requires_manual_injection` | Hardware-based |

P4SPR without pump → `requires_manual_injection = True` → manual.

### 7.3 Channel Resolution — `_resolve_detection_channels()`

```
Priority:
1. cycle.target_channels           (explicit override)
2. sorted keys of cycle.concentrations  (e.g. {"A": 50, "C": 40} → "AC")
3. "ABCD" if P4SPR, else sample_info["channels"] or "AC"
```

### 7.4 Manual Injection Flow

```
_execute_manual_injection(cycle, parent_widget):
  1. Parse sample_info (sample_id, channels, concentration)
  2. Set _is_p4spr flag (P4SPR: no valve channels shown)
  3. Open 3-way valves for target channels (non-P4SPR only)
  4. Resolve _detection_channels via _resolve_detection_channels()
  5. Skip dialog if cycle.method_mode in ["pump", "semi-automated"] → auto-complete
  6. Show ManualInjectionDialog off-screen (move to -9999,-9999 before show())
     Blocks worker thread for up to 80s — dialog closes automatically
  7. On Accepted → _process_detection_results() → close valves → injection_completed.emit()
  8. On Rejected (worker timeout) → close valves → injection_cancelled.emit()
```

### 7.5 Detection Results Processing — `_process_detection_results()`

Three cases handled:

| Case | Condition | Action |
|------|-----------|--------|
| **Per-channel results available** | `dialog._detected_channels_results` is populated | Emit `injection_flag_requested` for **every** detected channel |
| **Primary only, no per-channel** | `detected_injection_time` set but no `_detected_channels_results` | Emit primary channel flag, then call `_scan_all_channels_for_injection()` retroactively |
| **Timeout** | `detected_injection_time is None` | No flag emitted; increment `cycle.injection_count` |

Both Case 1 and Case 2 increment `cycle.injection_count` for Binding/Kinetic/Concentration cycles.

### 7.6 Retroactive Scan — `_scan_all_channels_for_injection()`

Used as fallback when `ManualInjectionDialog` detected a primary channel but didn't complete per-channel scanning during the grace period.

```
window_start = self._window_start_time
window_end   = max(window_start + 80.0, latest timestamp in timeline_data)

result = detect_injection_all_channels(buffer_mgr.timeline_data, window_start, window_end, min_confidence=0.70)

→ stores per-channel times on cycle.injection_time_by_channel
→ checks for mislabeled channels (detected on inactive channel → logged as warning)
```

**Mislabel detection:** If injection detected on a channel not in `cycle.channels`, it's flagged as `cycle.injection_mislabel_flags[ch] = 'inactive_channel'` and logged as a warning.

### 7.7 Automated Injection Flow

Runs in a background `threading.Thread` (daemon). Uses asyncio event loop. Stops any running pump first (`stop_and_wait_for_idle`, 30s timeout), then:

| `cycle.injection_method` | Pump call |
|--------------------------|-----------|
| `"simple"` | `pump_mgr.inject_simple(flow_rate, channels)` |
| `"partial"` | `pump_mgr.inject_partial_loop(flow_rate, channels)` |

Emits `injection_completed` on success, logs error on failure.

### 7.8 Valve Control

Only for non-P4SPR hardware. Requires `ctrl.knx_three_both()` to exist (FlowController only).

| Channel pair | 3-way valve state |
|-------------|------------------|
| `"AC"` | `state = 0` |
| `"BD"` | `state = 1` |

Valves closed after injection: 3-way resets to `pump_mgr.default_channels` state; 6-port set to state 0 (LOAD).

---

## 8. Key Constants

| Constant | Value | Location | Description |
|----------|-------|----------|-------------|
| Min noise floor | `0.1` RU | `auto_detect_injection_point` | Prevents zero noise from making threshold zero |
| Noise sigma multiplier | `3.0` | `auto_detect_injection_point` | Detection threshold = max(min_rise, Nσ noise). Increase to 4.0 to reduce false positives; decrease to 2.0 for weak-binder sensitivity. |
| Min rise threshold | `2.0` RU | `auto_detect_injection_point` | Absolute minimum step-jump size |
| Sustain window | `3–6` points | `auto_detect_injection_point` | Consecutive same-side points required for confirmation |
| Edge margin | `5%` of array length | `auto_detect_injection_point` | Edge penalty zone for confidence scoring |
| Detection window | **`80` seconds** | `ManualInjectionDialog` | Hard cutoff for manual injection monitoring |
| Phase 1 duration | **`10` seconds** | `InjectionActionBar` | Non-interactive prep countdown before detection |
| Phase 2 duration | **`80` seconds** | `InjectionActionBar` | Maximum detection monitoring time |
| Coordinator timeout | `95` seconds | `InjectionCoordinator` | Worker thread wait timeout (phase1 + phase2 + margin) |
| RU conversion factor | `355.0` | `detect_injection_all_channels` | nm → pseudo-RU scale factor |
| Multi-channel min confidence | `0.70` | `detect_injection_all_channels` | Minimum to accept a channel detection |
| Pre-injection offset | `10.0` s | `measure_delta_spr` | Baseline measurement point before injection |
| Time gap tolerance | `2.0` s | `measure_delta_spr` | Max gap before quality = 'extrapolated' |
| P4SPR detection channels | `"ABCD"` | `_resolve_detection_channels()` | All 4 channels for P4SPR (independent fluidics) |
| Default non-P4SPR channels | `"AC"` | `_resolve_detection_channels()` | Default pair for P4PRO valve routing |

---

## 9. Gotchas

1. **Blue-shift means injection is a drop:** The algorithm detects any deviation, but in this system injections produce a wavelength decrease. If values passed to `auto_detect_injection_point` are raw wavelengths (not RU), a binding event will show `signal_rise < 0` and `max_slope < 0`.

2. **RU conversion uses first-window-point as baseline (not global):** In `detect_injection_all_channels`, `baseline = window_wl[0]` — the first wavelength in the detection window, not the global baseline.

3. **No fallback on detection failure:** Unlike the previous algorithm, there is no "highest-deviation fallback" candidate. If no sustained crossing is found, `injection_time = None` and no flag is placed. This is intentional — a false positive flag is worse than a missed flag.

4. **`smoothing_window` param is accepted but not used:** The `smoothing_window=11` parameter is in the signature but not applied.

5. **ManualInjectionDialog is off-screen on Windows:** `WA_DontShowOnScreen` is X11-only and non-functional on Windows. The dialog is moved to `(-9999, -9999)` before `show()` to keep it off-screen while still firing `showEvent` (which starts the detection engine).

6. **Pump/semi-automated modes skip dialog entirely:** If `cycle.method_mode in ["pump", "semi-automated"]`, `_execute_manual_injection` returns immediately without showing the dialog and without detection — `injection_completed` emitted directly.

7. **P4SPR valve control is suppressed:** `_is_p4spr = True` blocks `_open_valves_for_manual_injection()` since P4SPR lacks 3-way valve hardware. Channels are also set to `None` in `sample_info`.

8. **Detection check interval is 200ms (5 Hz):** `DETECTION_CHECK_INTERVAL_MS = 200`. Each channel is scanned 5 times per second during the 80s window.

9. **`DETECTION_CONFIDENCE_THRESHOLD = 0.30`:** The minimum confidence to mark a channel as detected in the live dialog scan. Lower than the retroactive scan threshold (0.70) to be more permissive during the live window.
