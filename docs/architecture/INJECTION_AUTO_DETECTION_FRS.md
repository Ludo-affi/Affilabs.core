# Injection Auto-Detection — Functional Specification

**Version:** 2.0.5 beta  
**Verified against source:** Yes  
**Last updated:** 2026-02-19  
**Source files:**
- `affilabs/utils/spr_signal_processing.py` — algorithm layer
- `affilabs/coordinators/injection_coordinator.py` — orchestration layer
- `affilabs/dialogs/manual_injection_dialog.py` — UI/trigger layer

---

## 1. Overview

Injection auto-detection identifies the moment an analyte enters the flow cell by tracking a sustained deviation of the SPR resonance wavelength from its pre-injection baseline trend. Detection runs per-channel, produces a time + confidence score, and causes an injection flag to be placed on the sensorgram.

**Signal polarity:** Injection causes a **blue shift** (wavelength decreases) in this system. The detection algorithm is direction-agnostic — it detects any sustained deviation from baseline, rising or falling.

---

## 2. System Architecture

```
ManualInjectionDialog (per tick, 500ms timer)
  │  calls per-channel:
  ▼
auto_detect_injection_point(times, values, sensitivity_factor)
  │  returns: {injection_time, confidence, ...}
  │
  ├─ if detected → dialog marks channel LED green, stores result
  │
  └─ when all channels detected OR 60s expires:
       dialog.exec() returns Accepted
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

**Source:** `affilabs/utils/spr_signal_processing.py` line 260  
**Called from:** `ManualInjectionDialog._check_channel_for_injection()` (per channel, every 500ms)

### 3.1 Signature

```python
auto_detect_injection_point(
    times:              np.ndarray,       # Time array (seconds, RAW_ELAPSED)
    values:             np.ndarray,       # SPR signal (RU or wavelength nm)
    smoothing_window:   int = 11,         # SG window (unused in current implementation)
    baseline_points:    int = 5,          # Initial points for baseline (see §3.2)
    min_rise_threshold: float = 2.0,      # Minimum absolute signal change to confirm
    sensitivity_factor: float = 1.0,      # Scales all thresholds (see §3.5)
) -> dict
```

Requires at least 10 points in each array; returns all-zero/None dict otherwise.

### 3.2 Step 1 — Baseline Establishment

```python
baseline_end = min(baseline_points, int(len(values) * 0.33))
baseline_end = max(baseline_end, min(10, len(values) // 2))
```

Uses the first `baseline_end` points (capped at 33% of total data, minimum 10 points) to compute:
- `baseline_mean` — mean of baseline window
- `baseline_noise` — std dev, floored at `0.1` (minimum noise floor)

A **linear trend** is fit to the baseline window via `np.polyfit(baseline_times, baseline_values, 1)` to account for pre-injection drift. Fallback: constant `baseline_mean` if polyfit fails.

### 3.3 Step 2 — Deviation from Trend

```python
expected_trend = baseline_trend(times)     # projected linear drift
deviation = values - expected_trend        # signed deviation
abs_deviation = np.abs(deviation)
```

All subsequent comparisons are against `abs_deviation`, making the algorithm direction-agnostic.

### 3.4 Step 3 — Sustained Crossing Detection

```python
threshold = 2.5 * baseline_noise * sensitivity_factor
effective_rise_threshold = min_rise_threshold * sensitivity_factor

base_sustain = min(5, max(2, len(values) // 50))
sustain_window = max(2, int(base_sustain * sensitivity_factor))
```

Scanning from `baseline_end` to `len(values) - sustain_window`:

```
for each point i:
    if abs_deviation[i] > threshold:
        if mean(abs_deviation[i : i+sustain_window]) > threshold × 0.8:
            injection_idx = i  ← FOUND
            break
```

The 0.8 factor allows minor dips within the sustain window ("wiggle room").

**Fallback** if no sustained crossing found:
```python
candidate = argmax(abs_deviation[baseline_end:]) + baseline_end
if abs_deviation[candidate] > threshold × 0.5:
    injection_idx = candidate
```

If still no candidate → return `injection_time = None`.

### 3.5 Step 4 — Slope Calculation

```python
max_slope_value = float(np.gradient(values, times)[injection_idx])
```

Uses `np.gradient`'s centered finite difference for interior points, forward/backward at edges.

### 3.6 Step 5 — Confidence Scoring

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

`signal_rise` is the distance from `baseline_mean` to the post-injection peak or trough (direction-aware).

### 3.7 Return Dict

```python
{
    'injection_time':  float | None,  # Detected time (RAW_ELAPSED seconds)
    'injection_index': int | None,    # Array index
    'confidence':      float,         # 0.0–1.0
    'max_slope':       float,         # Slope at injection point (RU/s, signed)
    'signal_rise':     float,         # Total signal change from baseline (RU, signed)
    'snr':             float,         # abs_signal_rise / baseline_noise
    'baseline_noise':  float,         # Baseline std dev (RU)
}
```

---

## 4. Sensitivity Factor — Per-Mode Scaling

The `sensitivity_factor` parameter scales both thresholds and the sustain window. Lower = more sensitive.

| Method mode (`cycle.detection_priority`) | `sensitivity_factor` | Effect |
|------------------------------------------|---------------------|--------|
| `"priority"` | `0.5` | Threshold halved, sustain window halved — fires earliest |
| `"manual"` | `0.6` | Moderate sensitivity boost |
| `"auto"` / `"semi-automated"` | `1.0` | Default |
| `"off"` | — | `auto_detect_injection_point` is never called |

These are set in `ManualInjectionDialog` at construction and passed through to each detection call.

---

## 5. Multi-Channel Detection — `detect_injection_all_channels()`

**Source:** `affilabs/utils/spr_signal_processing.py` line 585  
**Called from:** `InjectionCoordinator._scan_all_channels_for_injection()` (retroactive scan)

### 5.1 Signature

```python
detect_injection_all_channels(
    timeline_data:    dict,       # buffer_mgr.timeline_data {ch → ChannelBuffer}
    window_start_time: float,     # RAW_ELAPSED seconds (detection window start)
    window_end_time:   float,     # RAW_ELAPSED seconds (detection window end)
    min_confidence:    float = 0.70,
) -> dict
```

### 5.2 Per-Channel Processing

For each channel in `['a', 'b', 'c', 'd']`:
1. Extract `time` and `wavelength` arrays from `ChannelBuffer`
2. Mask to `[window_start_time, window_end_time]`
3. **Wavelength → RU conversion:** `window_ru = (window_wl - window_wl[0]) * 355.0`
   - Baseline = first wavelength in window (not global)
   - Scale factor 355.0 converts nm shift to pseudo-RU
4. Call `auto_detect_injection_point(window_times, window_ru)` with default sensitivity
5. Accept result only if `confidence >= min_confidence` (default 0.70)

### 5.3 Return Dict

```python
{
    'times':        {'A': 123.5, 'C': 124.1, ...},   # detected channels only
    'confidences':  {'A': 0.85, 'C': 0.72, ...},
    'all_results':  {'A': {...}, 'B': {...}, ...},     # full dict per channel including non-detections
}
```

---

## 6. Delta SPR Measurement — `measure_delta_spr()`

**Source:** `affilabs/utils/spr_signal_processing.py` line 473  
**Purpose:** Measures SPR shift from pre-injection baseline to end of contact phase (cycle result reporting).

### 6.1 Signature

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

### 6.2 Measurement Points

```
START: injection_time - pre_offset  (10s before injection)
END:   injection_time + contact_time
```

Both use a centered `avg_points` window around the nearest data point. The inner helper `_avg_at(target)` handles the clamping logic and is shared between both measurements.

### 6.3 Quality Assessment

| Condition | `quality` |
|-----------|-----------|
| Both actual times within 2s of targets | `"good"` |
| Either gap > 2s | `"extrapolated"` |
| Exception or insufficient data | `"failed"` |

### 6.4 Return Dict

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

## 7. S/P Orientation Validation — `validate_sp_orientation()`

**Source:** `affilabs/utils/spr_signal_processing.py` line 62  
**Called from:** Calibration orchestrator (Step 5 QC)

Analyzes the P/S transmission spectrum in the 600–750 nm SPR region to validate that the servo polarizer is in the correct orientation.

### 7.1 Decision Logic

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

### 7.2 Return Dict

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

## 8. InjectionCoordinator — Orchestration Layer

**Source:** `affilabs/coordinators/injection_coordinator.py`

### 8.1 Signals

```python
injection_started          = Signal(str)             # injection_type: "manual" | "automated"
injection_completed        = Signal()
injection_cancelled        = Signal()
injection_flag_requested   = Signal(str, float, float)  # channel, injection_time, confidence
```

`injection_flag_requested` is the primary output — it causes the flag manager to place an injection marker on the sensorgram at the detected time.

### 8.2 Mode Determination

```python
InjectionCoordinator._determine_injection_mode(cycle) -> bool
```

| Priority | Condition | Result |
|----------|-----------|--------|
| 1 | `cycle.manual_injection_mode == "manual"` | Manual |
| 2 | `cycle.manual_injection_mode == "automated"` | Automated |
| 3 (fallback) | `hardware_mgr.requires_manual_injection` | Hardware-based |

P4SPR without pump → `requires_manual_injection = True` → manual.

### 8.3 Channel Resolution — `_resolve_detection_channels()`

```
Priority:
1. cycle.target_channels           (explicit override)
2. sorted keys of cycle.concentrations  (e.g. {"A": 50, "C": 40} → "AC")
3. "ABCD" if P4SPR, else sample_info["channels"] or "AC"
```

### 8.4 Manual Injection Flow

```
_execute_manual_injection(cycle, parent_widget):
  1. Parse sample_info (sample_id, channels, concentration)
  2. Set _is_p4spr flag (P4SPR: no valve channels shown)
  3. Open 3-way valves for target channels (non-P4SPR only)
  4. Resolve _detection_channels via _resolve_detection_channels()
  5. Skip dialog if cycle.method_mode in ["pump", "semi-automated"] → auto-complete
  6. Show ManualInjectionDialog.exec() — blocks for up to 60s
  7. On Accepted → _process_detection_results() → close valves → injection_completed.emit()
  8. On Rejected → close valves → injection_cancelled.emit()
```

### 8.5 Detection Results Processing — `_process_detection_results()`

Three cases handled:

| Case | Condition | Action |
|------|-----------|--------|
| **Per-channel results available** | `dialog._detected_channels_results` is populated | Emit `injection_flag_requested` for **every** detected channel |
| **Primary only, no per-channel** | `detected_injection_time` set but no `_detected_channels_results` | Emit primary channel flag, then call `_scan_all_channels_for_injection()` retroactively |
| **Timeout** | `detected_injection_time is None` | No flag emitted; increment `cycle.injection_count` |

Both Case 1 and Case 2 increment `cycle.injection_count` for Binding/Kinetic/Concentration cycles.

### 8.6 Retroactive Scan — `_scan_all_channels_for_injection()`

Used as fallback when `ManualInjectionDialog` detected a primary channel but didn't complete per-channel scanning during the grace period.

```
window_start = self._window_start_time
window_end   = max(window_start + 60.0, latest timestamp in timeline_data)

result = detect_injection_all_channels(buffer_mgr.timeline_data, window_start, window_end, min_confidence=0.70)

→ stores per-channel times on cycle.injection_time_by_channel
→ checks for mislabeled channels (detected on inactive channel → logged as warning)
```

**Mislabel detection:** If injection detected on a channel not in `cycle.channels`, it's flagged as `cycle.injection_mislabel_flags[ch] = 'inactive_channel'` and logged as a warning.

### 8.7 Automated Injection Flow

Runs in a background `threading.Thread` (daemon). Uses asyncio event loop. Stops any running pump first (`stop_and_wait_for_idle`, 30s timeout), then:

| `cycle.injection_method` | Pump call |
|--------------------------|-----------|
| `"simple"` | `pump_mgr.inject_simple(flow_rate, channels)` |
| `"partial"` | `pump_mgr.inject_partial_loop(flow_rate, channels)` |

Emits `injection_completed` on success, logs error on failure.

### 8.8 Valve Control

Only for non-P4SPR hardware. Requires `ctrl.knx_three_both()` to exist (FlowController only).

| Channel pair | 3-way valve state |
|-------------|------------------|
| `"AC"` | `state = 0` |
| `"BD"` | `state = 1` |

Valves closed after injection: 3-way resets to `pump_mgr.default_channels` state; 6-port set to state 0 (LOAD).

---

## 9. Key Constants

| Constant | Value | Location | Description |
|----------|-------|----------|-------------|
| Detection threshold | `2.5 × baseline_noise × sensitivity_factor` | `auto_detect_injection_point` | Sigma multiplier for breakout detection |
| Sustain wiggle | `0.8 × threshold` | `auto_detect_injection_point` | Min mean deviation during sustained window |
| Fallback threshold | `0.5 × threshold` | `auto_detect_injection_point` | Threshold for highest-deviation fallback |
| Min noise floor | `0.1` RU | `auto_detect_injection_point` | Prevents zero noise from making threshold zero |
| Edge margin | `5%` of array length | `auto_detect_injection_point` | Edge penalty zone |
| Detection window | `60` seconds | `ManualInjectionDialog` | Hard cutoff for manual injection monitoring |
| RU conversion factor | `355.0` | `detect_injection_all_channels` | nm → pseudo-RU scale factor |
| Multi-channel min confidence | `0.70` | `detect_injection_all_channels` | Minimum to accept a channel detection |
| Pre-injection offset | `10.0` s | `measure_delta_spr` | Baseline measurement point before injection |
| Time gap tolerance | `2.0` s | `measure_delta_spr` | Max gap before quality = 'extrapolated' |
| P4SPR detection channels | `"ABCD"` | `_resolve_detection_channels()` | All 4 channels for P4SPR (independent fluidics) |
| Default non-P4SPR channels | `"AC"` | `_resolve_detection_channels()` | Default pair for P4PRO valve routing |

---

## 10. Gotchas

1. **Blue-shift means injection is a drop:** The algorithm detects any deviation, but in this system injections produce a wavelength decrease. If values passed to `auto_detect_injection_point` are raw wavelengths (not RU), a binding event will show `signal_rise < 0` and `max_slope < 0`.

2. **RU conversion uses first-window-point as baseline (not global):** In `detect_injection_all_channels`, `baseline = window_wl[0]` — the first wavelength in the detection window, not the global baseline. This means the RU values are relative to the state at detection window open, not experiment start.

3. **`baseline_points` default is 5, not 50:** The docstring says default 50; the actual default is 5. The effective baseline uses `min(5, int(len*0.33))`, clamped to at least 10 — meaning with short windows, 10 points are used regardless.

4. **`smoothing_window` param is accepted but not used:** The `smoothing_window=11` parameter is in the signature but the SG filter inside `auto_detect_injection_point` is not called in the current implementation.

5. **Per-channel results in dialog come from grace-period scan:** When the dialog detects a primary channel, it runs a grace-period scan on all channels. `_detected_channels_results` is only populated if that grace-period scan completes before dialog close. If not, `InjectionCoordinator` falls back to the retroactive scan.

6. **Pump/semi-automated modes skip dialog entirely:** If `cycle.method_mode in ["pump", "semi-automated"]`, `_execute_manual_injection` returns immediately without showing the dialog and without detection — `injection_completed` emitted directly.

7. **P4SPR valve control is suppressed:** `_is_p4spr = True` blocks `_open_valves_for_manual_injection()` since P4SPR lacks 3-way valve hardware. Channels are also set to `None` in `sample_info`.
