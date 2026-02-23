# Injection Auto-Detection — FRS

**Status:** v1 = λ-only (shipped). v2 = multi-feature scorer (this document, to implement).
**Source files:** `affilabs/utils/spr_signal_processing.py`, `affilabs/dialogs/manual_injection_dialog.py`

---

## 1. Problem with v1 (λ-only detection)

The current detector uses a single signal: resonance wavelength (λ) converted to RU.
It fires when λ deviates from baseline by >2.5σ sustained over 2–5 points.

**Failure modes:**

| Event | λ response | v1 result |
|-------|-----------|-----------|
| Real injection, good buffer match | small or no bulk shift | **missed** |
| Temperature drift | slow λ shift | **false positive** |
| Air bubble | large λ spike | **false positive** |
| Water leak | λ collapse | **false positive** |
| Real injection, bad buffer match | large transient then binding | **detects, but wrong timestamp** |

Root cause: λ alone is ambiguous. Multiple physical events produce similar λ signatures.

---

## 2. Signal inventory

These signals are already computed per-frame during acquisition:

| Signal | Symbol | Where computed | Update rate |
|--------|--------|----------------|-------------|
| Resonance wavelength | λ | `spr_signal_processing.py` → pipeline | ~1 Hz per channel |
| Peak-to-peak variation | P2P | `sensor_iq.py` | per frame |
| % Transmittance | %T | `TransmissionProcessor` | per frame |
| FWHM | FWHM | pipeline output | per frame |
| 10s baseline slope | slope | computed in `auto_detect_injection_point` | on demand |

All four are available in the channel buffer (`buffer_mgr.timeline_data`). No new acquisition needed.

---

## 3. Physical signatures of each event

### 3a. Real injection
1. **P2P spike** — syringe push creates a brief mechanical/fluidic disturbance. P2P rises to >2.5× rolling baseline, then returns to normal within ~10s.
2. **%T transient dip** — flow front entering the cell briefly scatters light. %T drops >0.5%, then **recovers** within 20–30s. Recovery is the key discriminator.
3. **λ slope change** — after injection settles, λ drifts at a new rate (binding slope vs baseline slope). Change in slope >0.05 nm/s.
4. **λ onset** (current method) — bulk RI shift at injection start. Present but can be near-zero with matched buffers.

### 3b. Air bubble
- P2P: extreme spike (>>5×)
- %T: sharp drop, **does not recover** (bubble stays)
- λ: unstable, oscillating
- **Discriminator:** %T does not recover → not injection

### 3c. Water / leak
- P2P: sustained elevation (not a spike)
- %T: sharp drop, **stays down** (light blocked)
- λ: collapses
- **Discriminator:** %T drops hard and stays → not injection

### 3d. Temperature drift
- P2P: normal (no spike)
- %T: stable (no dip)
- λ: slow monotonic shift
- **Discriminator:** no P2P spike, no %T event → not injection

### 3e. Normal experiment variation (e.g. between binding cycles)
- All signals within normal rolling range
- **Discriminator:** score below threshold → no event

---

## 4. Multi-feature scorer — v2 algorithm

### 4a. Features (computed over a 5s rolling window at each timestep)

```
p2p_ratio     = current_p2p / rolling_baseline_p2p        # baseline = median of last 60s
t_drop        = baseline_%T − current_%T                   # baseline = mean of last 30s
t_recovered   = (%T_now − %T_min_recent) / max(t_drop, ε) # 0=no recovery, 1=full recovery
slope_change  = |post_slope − pre_slope|                   # pre=last 10s, post=next 10s
lambda_onset  = |λ_deviation| / (2.5 × λ_baseline_std)    # existing method, normalized 0–1+
```

### 4b. Injection score

```python
score = 0.0

# P2P spike — brief mechanical disturbance
if p2p_ratio > 2.5:
    score += 0.30

# %T dip WITH recovery — flow front entering, then clearing
# Recovery condition is the primary discriminator vs air/leak
if t_drop > 0.5 and t_recovered > 0.55:
    score += 0.40

# Slope change — new binding trend starting
if slope_change > 0.05:   # nm/s
    score += 0.20

# λ onset — any RI change (existing signal, now one vote among four)
if lambda_onset > 1.0:
    score += 0.10

# Detection: score >= 0.65 AND at least 2 independent features fired
# (prevents a single extreme feature driving the whole score)
```

**Threshold:** `score >= 0.65` with `feature_count >= 2`

### 4c. Anomaly flags (from the same computation, no extra cost)

| Condition | Flag |
|-----------|------|
| P2P spike AND %T drops AND `t_recovered < 0.2` | `POSSIBLE_BUBBLE` |
| %T drops >2% AND stays down >30s | `POSSIBLE_LEAK` |
| λ drifting (slope >0.02 nm/s), NO P2P spike, NO %T event | `BASELINE_DRIFT` |
| score >= 0.65 | `INJECTION_DETECTED` |

These flags feed into Spark guidance and the existing `SensorIQ` system — no UI changes required.

---

## 5. Timing constraints

| Phase | Duration | What's happening |
|-------|----------|-----------------|
| P2P spike | 0–5s post-injection | Syringe push disturbance |
| %T dip | 0–10s post-injection | Flow front entering |
| %T recovery | 10–30s post-injection | Cell clearing |
| Slope change detectable | 20–60s post-injection | Binding accumulating |

**Implication:** detection can fire as early as **5–10s** post-injection (P2P + %T dip observed before recovery is complete). The recovery check uses a 20s lookback window — it can confirm recovery retroactively.

**Injection timestamp** = earliest of: P2P spike onset OR λ onset, whichever is first and has score contribution. Not the slope change (that's post-injection).

---

## 6. Implementation plan

### Step 1 — New function: `score_injection_event()` in `spr_signal_processing.py`

```python
def score_injection_event(
    times: np.ndarray,
    wavelengths: np.ndarray,
    p2p_values: np.ndarray,
    transmittance: np.ndarray,
    eval_time: float,
    baseline_window_s: float = 30.0,
    recovery_window_s: float = 20.0,
) -> dict:
    """
    Returns:
        {
          'score': float,           # 0.0–1.0+
          'feature_count': int,     # how many features fired
          'injection_time': float | None,
          'confidence': float,
          'flags': list[str],       # 'INJECTION_DETECTED', 'POSSIBLE_BUBBLE', etc.
          'features': dict,         # per-feature values for debug/logging
        }
    """
```

### Step 2 — Replace `_scan_channel()` in `manual_injection_dialog.py`

- Call `score_injection_event()` instead of `auto_detect_injection_point()`
- Keep the same LED feedback and grace period logic
- Keep the same `DETECTION_CONFIDENCE_THRESHOLD` (map score → confidence)
- Add anomaly flag storage: `self._anomaly_flags[ch]`

### Step 3 — Keep `auto_detect_injection_point()` for retroactive scan

`detect_injection_all_channels()` in `InjectionCoordinator` runs after the dialog closes on historical data. It can remain λ-only or be upgraded in a separate pass — the retroactive scan has more data and less time pressure, so the existing algorithm is acceptable there.

### Step 4 — Emit anomaly flags to Spark / SensorIQ

If `POSSIBLE_BUBBLE` or `POSSIBLE_LEAK` detected during scanning, emit a guidance event:
```python
self.guidance_coordinator.emit_alert(flag, channel=ch)
```

---

## 7. Baseline rolling windows — implementation notes

The scorer needs per-channel rolling buffers of P2P and %T. These are not currently stored in `timeline_data`. Two options:

**Option A (preferred):** Add `p2p` and `transmittance_mean` arrays to `ChannelBuffer` alongside the existing `wavelength` array. Feed them in `DataAcquisitionManager` at the same point wavelength is appended.

**Option B (fallback):** Compute P2P from raw wavelength variance in the scorer itself using the existing `wavelength` array (rolling std as a P2P proxy). Less accurate but requires no buffer changes.

Option A is cleaner and enables future diagnostics. Option B is faster to ship.

---

## 8. Constants (move to `settings.py`)

```python
# Injection detection v2
INJECTION_P2P_RATIO_THRESHOLD    = 2.5    # ratio vs rolling baseline P2P
INJECTION_T_DROP_THRESHOLD       = 0.5    # % absolute drop in transmittance
INJECTION_T_RECOVERY_THRESHOLD   = 0.55   # fraction recovered (0=none, 1=full)
INJECTION_SLOPE_CHANGE_THRESHOLD = 0.05   # nm/s change in baseline slope
INJECTION_SCORE_THRESHOLD        = 0.65   # minimum score to accept detection
INJECTION_FEATURE_COUNT_MIN      = 2      # minimum features that must fire
INJECTION_BASELINE_WINDOW_S      = 30.0   # seconds for rolling baseline
INJECTION_RECOVERY_WINDOW_S      = 20.0   # lookback window for %T recovery check
BUBBLE_T_DROP_THRESHOLD          = 1.0    # %T drop for bubble flag
BUBBLE_RECOVERY_THRESHOLD        = 0.20   # if recovery < this → bubble
LEAK_T_DROP_THRESHOLD            = 2.0    # %T drop for leak flag
LEAK_DURATION_S                  = 30.0   # sustained drop duration for leak
```

---

## 9. What does NOT change

- Dialog UI, LED indicators, grace period, 60s timeout — all unchanged
- `detect_injection_all_channels()` retroactive scan — unchanged (v1 acceptable there)
- Flag placement, recording export, coordinator signal chain — unchanged
- `detection_priority` / sensitivity factor — replaced by feature weights, but the
  `"off"` → disable path is kept
- Per-channel independent detection — unchanged

---

## 9b. Anomaly flag display — UnifiedCycleBar

Anomaly flags surface in the `UnifiedCycleBar` (`affilabs/widgets/unified_cycle_bar.py`) — the 50px bar that sits directly below the active cycle graph. This is already the user's primary attention point during an injection.

### During INJECT state (bubble/leak detected mid-injection)

No new state. The bar updates **in place**:

| Element | Normal INJECT | Anomaly detected |
|---------|--------------|-----------------|
| `icon_label` | 💉 | ⚠ (amber) |
| `message_label` | "Injection 1/3 • Sample A (50 nM)" | "⚠ Possible air bubble — Channel B" |
| `message_label` color | `#1D1D1F` | `#FF9500` amber |
| `info_label` | countdown (60s…) | countdown continues |
| Buttons | Cancel / Done Injecting | Cancel / Done Injecting (unchanged) |
| Background | `_inject_style()` warm yellow | `_anomaly_inject_style()` amber |

User can still click Done or Cancel — the warning doesn't block. They make the call.

New method on `UnifiedCycleBar`:
```python
def set_inject_anomaly(self, flag: str, channel: str) -> None:
    """Show anomaly warning within INJECT state (non-blocking)."""
    # flag: 'POSSIBLE_BUBBLE' | 'POSSIBLE_LEAK'
    # Does not change self._state — stays CycleBarState.INJECT
```

### During RUNNING / CONTACT state (anomaly detected outside injection window)

New `ANOMALY` state — amber background, Dismiss button, auto-reverts:

```python
def set_anomaly(self, flag: str, channel: str, prev_state_restore_fn) -> None:
    """Amber warning bar. Dismiss reverts to previous state."""
    # flag: 'POSSIBLE_BUBBLE' | 'POSSIBLE_LEAK' | 'BASELINE_DRIFT'
    # prev_state_restore_fn: callable to re-apply previous state on dismiss
```

| Flag | Icon | Message |
|------|------|---------|
| `POSSIBLE_BUBBLE` | 🫧 | "Air bubble detected — Channel B. Signal may recover." |
| `POSSIBLE_LEAK` | 💧 | "Possible leak — Channel C. Check connections." |
| `BASELINE_DRIFT` | 📉 | "Baseline drifting. Consider re-stabilising before injecting." |

Background: `qlineargradient` amber (`#FFF3CD` → `#FFE082`), top border `#FF9500`.

### What does NOT show anomalies

- The IQ dots (●) on the sensorgram legend are **not** used for anomaly flags — they reflect signal quality (SNR / convergence), not fluidic events. Mixing the two would create confusing semantics.
- No Spark notification for anomalies by default — Spark tips fire on user workflow context, not hardware events. Future: add a Spark guidance hook if anomaly count exceeds threshold in a session.

---

## 10. Expected improvement

| Scenario | v1 result | v2 expected |
|----------|-----------|-------------|
| Injection, matched buffer (no bulk shift) | miss | detect (P2P + %T) |
| Injection, mismatched buffer | detect (λ) | detect (all 4) |
| Temperature drift | false positive | filtered (no P2P, no %T) |
| Air bubble | false positive | `POSSIBLE_BUBBLE` flag, not injection |
| Leak | false positive | `POSSIBLE_LEAK` flag, not injection |
| Clean baseline event | correct | correct |

---

## 11. Post-detection: contact window visualization

**Implemented in v2.0.5** — `mixins/_pump_mixin.py:_place_injection_flag()`, `affilabs/managers/flag_manager.py`

When injection is detected and the cycle has a `contact_time > 0`, the Active Cycle graph immediately renders three visual elements:

| Element | Type | Position | Purpose |
|---------|------|----------|---------|
| ▲ Injection flag | `InfiniteLine` (triangle marker) | `t_injection` | Marks where the injection was detected |
| Contact zone | `LinearRegionItem` (light blue, 11% opacity) | `t_injection → t_injection + contact_time` | Visual gap the user watches the data fill |
| 🧹 Wash line | `InfiniteLine` (dashed blue) | `t_injection + contact_time` | Target moment to perform wash |

**User experience intent**: The user stands at the bench and watches the sensorgram trace grow rightward through the light blue zone toward the dashed wash line. When data reaches the line, contact time is complete. No timer-watching required — the graph tells the story.

**Cleanup**: All three items are stored as `AutoMarker` entries in `flag_manager._auto_markers`. `clear_auto_markers()` removes them automatically at cycle end.

**Step-change detector (Feature 5)**: For injections where the bulk shift has already settled before detection runs (e.g., P4SPR manual where the user injects and the window opens post-injection), a step-change scorer compares pre/post means divided by baseline σ. Fires at >3σ (`step_fired`), bypasses partner-score requirement at >4σ (`step_strong`). Implemented in `spr_signal_processing.py:score_injection_event()`.
