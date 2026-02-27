# Injection Auto-Detection — FRS

**Status:** ✅ v2 multi-feature scorer implemented (Feb 2026).
**Last Updated:** 2026-02-26
**Source files:** `affilabs/coordinators/injection_coordinator.py` (`_InjectionMonitor`), `affilabs/utils/spr_signal_processing.py` (`score_injection_event`)

---

## Architectural Decision — `_InjectionMonitor` (implemented)

> **Decided and implemented: Feb 25–26, 2026**

v2 injection detection uses `_InjectionMonitor` — a per-channel background thread in `injection_coordinator.py`. Key decisions:

- **Not** built on `_WashMonitor` (that class was removed). `_InjectionMonitor` is a standalone implementation with its own polling loop.
- **Bidirectional** delta: `delta = mean(window_now) - mean(window_prev)` — detects both rises and falls (accommodates negative bulk-RI transients on some buffer systems).
- **Not one-shot**: the monitor stays alive after fire #1. Fire #2+ = wash detection. Dead zone of 15s between fires absorbs the biphasic bulk-RI artifact.
- **Cycle-scoped**: monitor runs for the full lifecycle of the `_InjectionSession`, not just the 80s dialog window. Stopped by `_stop_all_monitors()` in `_on_bar_done`, `_on_cancelled`, `_on_timeout`, or `cleanup_monitors()` at cycle end.
- **`ManualInjectionDialog`** is now a state container only — no scan loop, no timers. Detection is entirely in `_InjectionMonitor`.

### `_InjectionMonitor` — implemented class (lines 63–316 in `injection_coordinator.py`)

```python
class _InjectionMonitor(QObject):
    """Per-channel injection + wash detector.

    Polls every POLL_INTERVAL_S (2s). Uses two rolling windows of WINDOW_FRAMES (5)
    points each. Bidirectional delta — fires on any step-change above adaptive threshold.

    Fire #1 = injection detected (routes to _handle_injection)
    Fire #2+ = wash detected (routes to _handle_wash) after DEAD_ZONE_S (15s)

    Emits:
        injection_detected(channel_upper, approx_t)
        anomaly_detected(flag, channel_upper)
        readiness_update(ReadinessResult)
    """
    POLL_INTERVAL_S = 2
    WINDOW_FRAMES   = 5
    HARD_MIN_RU     = 5.0
    CONFIRM_FRAMES  = 2       # from settings.INJECTION_CONFIRM_FRAMES
    SIGMA           = 3.0     # from settings.INJECTION_DETECTION_SIGMA
    STD_MAX_NM      = 0.056   # from settings.INJECTION_STD_MAX_NM
    DEAD_ZONE_S     = 15.0    # from settings.INJECTION_DEAD_ZONE_S
```

### Detection algorithm (per poll)

```
1. Quality gate: std of early 5 frames < STD_MAX_RU → skip if noisy
2. Spike detector: p2p of last 2W frames > adaptive threshold
     threshold = max(HARD_MIN_RU, SIGMA × baseline_std_ru)
3. Dead zone: if monotonic() - last_fire_at < DEAD_ZONE_S → skip
4. Confirmation: CONFIRM_FRAMES consecutive polls above threshold
     t_fire = _find_onset_time()   ← backtracked to onset
5. Triage (deferred, 5 polls = 5s):
     On confirm: snapshot pre_window (last 5 optical frames from SignalTelemetryLogger)
     Wait 5 more polls, then compare pre vs post across 4 signals:
       raw_peak collapses ≥75%          → POSSIBLE_LEAK
       %T drops ≥10pp AND FWHM +≥30%   → POSSIBLE_BUBBLE
       FWHM broadens ≥30%               → CHIP_DEGRADED
       SPR mean returns to baseline     → SIGNAL_SPIKE (transient)
       none of the above                → INJECTION ✅
```

### Optical rolling buffer

`SignalTelemetryLogger._ChannelRollingState.optical_buffer` — `deque(maxlen=10)` per channel.
Populated every frame via `push_optical(wavelength, transmittance, fwhm, raw_peak)` from `record()`.
`get_optical_snapshot(ch)` returns the last 5 entries as the pre-event snapshot.
Pre-window snapshot taken at spike confirm; post-window snapshot taken after 5 more polls.

### Fire routing

Managed by `_InjectionSession._fire_counts` dict (per-channel):
- Fire #1 → `_handle_injection()` — stores in dialog state, updates bar LED, unblocks BG thread (P4SPR: first channel; P4PRO: all channels)
- Fire #2+ → `_handle_wash()` — calls `bar.set_channel_wash(ch)` + `SignalQualityScorer.notify_wash_detected(ch)`

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
| Resonance wavelength | λ | `spr_signal_processing.py` → pipeline | **1 Hz per channel** |
| Peak-to-peak variation | P2P | `sensor_iq.py` | per frame (1 Hz) |
| % Transmittance | %T | `TransmissionProcessor` | per frame (1 Hz) |
| FWHM | FWHM | pipeline output | per frame (1 Hz) |
| 10s baseline slope | slope | computed in `auto_detect_injection_point` | on demand |

All four are available in the channel buffer (`buffer_mgr.timeline_data`). No new acquisition needed.

---

## 2a. System Timing Stack — Acquisition to Detection

Understanding the hardware timing chain is critical for choosing the right monitoring window sizes.

```
Hardware (per-channel, sequential):
  LED ON duration:        225 ms   (LED_ON_TIME_MS)
  Detector stabilisation:  45 ms   (DETECTOR_WAIT_MS)
  Detector window:        170 ms   (LED_ON_TIME - DETECTOR_WAIT - SAFETY_BUFFER_MS)
  Integration time:     ≤62.5 ms   per scan (MAX_INTEGRATION_PER_SCAN_MS), ×3 scans
  ──────────────────────────────
  Per-channel slot:      ~250 ms   (hardware-determined)

Full cycle (all 4 channels, A→B→C→D):
  4 × ~250 ms = ~1.0 s             (CYCLE_TIME = 1.0)
  → Each channel is updated at exactly 1 Hz

Detection / monitoring timebases:
  Dialog check interval:   200 ms   (DETECTION_CHECK_INTERVAL_MS)
    However, new data arrives at 1 Hz — checking every 200ms re-runs the
    same data 5× between new points. Effectively 1 Hz resolution.

  WashMonitor / InjectionMonitor poll: 2 s   (POLL_INTERVAL_S)
    Polls slope every 2s, each over two back-to-back 10s windows → 20s total
    coverage. At 1 Hz, each 10s window = 10 data points — sufficient for
    a reliable linear regression.

  Telemetry logger:        1 Hz     (passthrough — one row per frame)
```

### Monitoring window design rules

Given 1 Hz per-channel acquisition:

| Window | Points | Purpose | Minimum useful? |
|--------|--------|---------|-----------------|
| 5 s | 5 pts | Baseline σ, pre-injection reference | ✅ Yes — minimum reliable σ |
| 10 s | 10 pts | Slope window (linear regression) | ✅ Yes — solid regression |
| 20 s | 20 pts | %T recovery check | ✅ Yes — covers injection transient |
| 30 s | 30 pts | Rolling baseline P2P / %T mean | ✅ Yes — stable reference |
| 60 s | 60 pts | Long-term drift reference | ✅ Yes |

**Rule:** Never design a rolling window shorter than 5 points (5s) — below that, σ estimates are unreliable. The 5-point / 5-second baseline rule used in the injection detector is the hard lower limit.

**Implication for bubble detection:** A bubble that lasts <5s may not be long enough to trigger the sustained-P2P check. That is acceptable — a <5s bubble is transient and unlikely to corrupt data. The check targets bubbles that persist ≥5s.

---

## 3. Physical signatures of each event

### 3a. Real injection
1. **P2P spike** — syringe push creates a brief mechanical/fluidic disturbance. P2P rises to >2.5× rolling baseline, then returns to normal within ~10s.
2. **λ transient** — the initial bulk RI shift at injection start may cause λ to jump and then **partially return** as the flow front settles. This return takes **5–6 seconds**, not 1–2 seconds. After the transient, λ then drifts again at the new binding slope. This multi-phase shape (jump → partial return → new slope) is characteristic of a real injection with a buffer mismatch.
3. **%T transient dip** — flow front entering the cell briefly scatters light. %T drops >0.5%, then **recovers** within 20–30s. Recovery is the key discriminator.
4. **λ slope change** — after injection settles, λ drifts at a new rate (binding slope vs baseline slope). Change in slope >0.05 nm/s.
5. **λ onset** (current method) — bulk RI shift at injection start. Present but can be near-zero with matched buffers.

### 3b. Air bubble

**Physics:** Air has a much lower refractive index than aqueous buffer (~1.0 vs ~1.33). When an air bubble enters the flow cell, two things happen simultaneously:
1. **No plasmon coupling** — air's RI is outside the range that supports surface plasmon resonance at our geometry and gold thickness. The SPR dip effectively disappears or jumps far outside the 560–720 nm measurement window.
2. **Large %T drop** — without the SPR dip absorbing light, the transmission reading at the dip wavelength rises sharply. Conversely, the bulk scattering from the air/buffer interface can also scatter light away from the fiber, causing a hard intensity drop at the detector. In practice the measured %T falls significantly: a baseline of ~77% may drop to ~72% on a partial bubble or to ~55% or lower on a full channel fill.

This makes the %T drop from a bubble **much larger in magnitude** than the brief transient from a real injection (where the flow front causes only a few percent dip before recovering).

- **P2P: sustained elevation** — unlike a real injection where P2P spikes briefly then returns to baseline, a bubble causes P2P to rise AND STAY elevated for the duration of the bubble. With no stable SPR dip to track, the pipeline fits a noisy or absent feature, producing frame-to-frame λ scatter. P2P and σ increase together and remain high — this is a **degrading signal**, not a one-off disturbance.
- **%T: large sharp drop** (e.g. 77% → 72–55% or lower), **does not recover** while bubble is present
- **λ: unstable, oscillating** or untrackable (no valid SPR dip to fit) — the pipeline may report wildly varying wavelengths because it is fitting noise
- **Discriminator:** %T drop is large (>2%) AND does not recover AND P2P stays elevated (not a brief spike) → air bubble, not injection

> **Key distinction from real injection:**
> - Real injection: P2P spikes briefly (syringe push) then returns to normal within ~10s. %T dips <2% then recovers.
> - Air bubble: P2P rises and **stays high** for the duration (degrading signal). %T drops 2–25% and **stays down**. Both signals degrade together — this co-degradation pattern is the strongest indicator.
>
> Using σ as an alternative to P2P: rolling σ of λ over the last 5 frames will show the same sustained elevation as P2P. Either metric works; P2P is faster to compute, σ is more robust against single outlier frames.

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

### 3f. Transient spike (1–2 point excursion)

Spikes occur occasionally from mechanical disturbance (touching the instrument, nearby vibration), a brief electrical noise event, or a micro-particle passing through the beam.

**Signature:**
- λ jumps above/below baseline for exactly **1–2 data points**, then **returns to the prior level within 1–3 seconds**
- No slope change before or after — baseline is stable on both sides
- P2P rises sharply for those 1–2 frames, then returns to normal as the spike exits the 5-frame window
- %T: minor or no change (no fluidic cause)
- No sustained deviation → **injection detector correctly rejects it** (sustain window = 3–6 consecutive same-sign points; 1–2 points fails this check)

**The key temporal discriminator — return timescale:**

| Event | λ returns to baseline? | How fast? |
|-------|----------------------|-----------|
| **Spike** | ✅ Yes, fully | **<3 s** — back within 1–2 data points |
| **Real injection** (with buffer mismatch) | ✅ Partially — then new slope begins | **5–6 s** for transient to settle, then λ drifts again at binding rate |
| **Real injection** (matched buffer) | ❌ No return — step stays | Never returns to pre-injection baseline |
| **Air bubble** | ❌ No | Stays displaced until bubble clears |

A return within **<3 seconds** = spike. A return taking **5–6 seconds** followed by a new slope = real injection transient. This timescale is the primary discriminator between the two events that both show a "λ goes up and comes back down" pattern.

**Discriminating signature vs other events:**

| Feature | Spike | Real injection | Air bubble |
|---------|-------|---------------|------------|
| P2P elevation | 1–3 frames only, then back to normal | 1–3 frames, then returns to normal P2P | Sustained — stays elevated |
| Signal returns to baseline | ✅ Yes, <3 s | ⚠ Partially, over 5–6 s, then new slope | ❌ No — stays displaced |
| Slope change post-event | ❌ None | ✅ Yes (new binding slope after transient) | ❌ None |
| %T change | Minor / none | Minor transient (<2%), recovers | Large (2–25%), sustained |

**Detection:** the monitoring system catches spikes for free — no additional algorithm needed. The P2P 5-frame window will show a high value at the spike frame(s), and the signal returning to baseline is detectable by checking that λ is within 1σ of baseline_mean within 3–5 frames after the P2P peak.

**Flag: `SIGNAL_SPIKE`**

```python
# Spike: P2P elevated for ≤2 consecutive frames, signal returns to baseline within 3s,
# and no new slope emerges after return.
# Distinguished from a real injection transient by return timescale (<3s vs 5–6s)
# and absence of any new slope following the return.
spike_detected = (
    p2p_ratio > 2.5                          # P2P elevated
    and frames_above_threshold <= 2          # brief — 1 or 2 points only
    and return_time_s < 3.0                  # back within 3s (injection transient takes 5–6s)
    and lambda_returned_to_baseline          # back within 1σ of baseline mean
    and abs(slope_change) < 0.02             # no new slope after return
)
```

Spike flags are informational — they do not block injection detection or stop the cycle. They are logged in telemetry and can surface as a subtle UI indicator (e.g. a brief orange flash on the channel IQ dot) so the user is aware the signal had a transient event.
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
| P2P elevated ≤2 frames, signal returns to baseline, no slope change | `SIGNAL_SPIKE` |
| score >= 0.65 | `INJECTION_DETECTED` |

These flags feed into the per-cycle quality score and global run star rating — see **[SIGNAL_EVENT_CLASSIFIER_FRS.md §6b](SIGNAL_EVENT_CLASSIFIER_FRS.md)** for the canonical scoring mapping of each flag. In summary:

| Flag | Per-cycle impact | Run-level impact |
|------|-----------------|------------------|
| `INJECTION_DETECTED` | +20 pts injection confidence (full 20 if score ≥ 0.80) | Missed detections flow through to Poor band → lowers star rating |
| `POSSIBLE_BUBBLE` | −5 pts per bubble frame in contact window (0 if >3 frames) | `bubble_cycles` count sent to Sparq Coach |
| `POSSIBLE_LEAK` | Cycle score clamped to max 20 (data unusable) | `leak_cycles` count; Poor band guaranteed |
| `BASELINE_DRIFT` | −5 pts per drift event from baseline stability component | `drift_cycles_pre_inject` count for Sparq Coach |
| `SIGNAL_SPIKE` | −5 pts per spike beyond the first in contact window | Reported to Sparq Coach only if >10 total in run |

---

## 5. Timing constraints

### 5a. Hardware acquisition timing (fixed)

```
LED scan order:    A → B → C → D → A → ... (continuous loop, never stops)
Full cycle:        1.0 s   (all 4 channels)
Per-channel slot:  ~250 ms (LED_ON_TIME = 225ms + overhead)
Inter-channel lag: A fires at t=0, B at t≈250ms, C at t≈500ms, D at t≈750ms

→ Each channel is updated at 1 Hz
→ Maximum inter-channel timing skew: 750 ms
→ This skew is hardware-fixed and cannot be reduced in software
```

The 750ms inter-channel skew is small relative to any injection-related timescale (seconds to minutes) and can be ignored for detection purposes. Each channel is treated as an independent 1 Hz signal stream.

### 5b. Manual injection timing (user-driven, highly variable)

When a user injects manually by pipetting into flow cell inlets:

| User level | Time per inlet | 2-channel total spread | 4-channel total spread |
|------------|---------------|----------------------|----------------------|
| Expert | ~3 s | ~6 s | ~12 s |
| Intermediate | ~5–10 s | ~10–20 s | ~20–40 s |
| Beginner | ~10–20 s | ~20–40 s | ~40–80 s |

**Key insight:** The spread between first and last channel injection can be 6–80 seconds depending on the user and experiment design. The detection system must tolerate this — it cannot assume all channels inject simultaneously.

Two-channel experiments (e.g. AC only) are faster than four-channel by roughly half, reducing the total spread. This should inform the monitoring window width.

### 5c. Optimal software monitoring frequency

**The fundamental constraint:** data arrives at 1 Hz per channel. No matter how fast the software polls, it cannot detect an injection before the first post-injection data point arrives. The temporal resolution of detection is therefore capped at **1 second**.

| Layer | Current frequency | Data-effective frequency | Assessment |
|-------|------------------|-----------------------|------------|
| `ManualInjectionDialog` check | 200 ms (5 Hz) | 1 Hz (new data only) | ⚠ Runs 5× per new point — redundant but harmless. Could be 1 s without loss of detection latency. |
| `_InjectionMonitor` / `_WashMonitor` poll | 2 s | 2 pts per poll at 1 Hz | ✅ Appropriate — always has new data since last poll |
| Telemetry logger | 1 Hz | 1 Hz | ✅ Matches data rate exactly |

**Recommended monitoring cadence:**
- **Detection check: 1 s** — matches data rate, no redundant computation
- **Slope polling: 2 s** — gives 2 new points per evaluation; slope window of 10s = 10 pts
- **Anomaly / P2P / %T check: 1 s** — same as detection check, same data pass

The dialog's current 200ms check is a historical artefact from a time when the system aimed for sub-second detection. At 1 Hz acquisition, it provides no benefit. It should be changed to 1 s to reduce CPU load during the 80s monitoring window.

### 5d. Continuous monitoring — cycle-scoped, not dialog-scoped

**Decision (Feb 25 2026): `_InjectionMonitor` runs for the full duration of any binding/kinetic/concentration cycle — not just the 80s dialog window.**

A typical manual binding cycle runs at most **30 minutes**. Running injection detection continuously across the full cycle is computationally trivial:

```
30 min × 60 s × 4 channels = 7,200 data points total
Each check: slice 5–10 floats, 2 comparisons → <1 ms
Total compute across full 30-min cycle: ~7 s of equivalent microsecond-ops
                                         spread over 1,800 s real time
→ CPU impact: unmeasurable in a profiler
```

**Implication for architecture:** The current design gates detection behind the `ManualInjectionDialog` 80s window. This was originally necessary because detection was expensive and context-sensitive. Given that continuous monitoring is essentially free, the architecture changes to:

> **`_InjectionMonitor` runs for the full duration of any binding/kinetic/concentration cycle** — not just the 80s dialog window. It starts when the cycle starts, watches the signal continuously, and places injection flags whenever a valid step-change above threshold is detected — regardless of when the user injects or whether the dialog is open.

Benefits:
- Catches injections that happen before or after the dialog window (early pipetter, slow pipetter)
- The dialog becomes a **UI convenience only** (shows LED feedback, lets user click Done) — not the detection trigger
- Retroactive scan (`detect_injection_all_channels`) becomes redundant — the monitor already has continuous coverage
- Per-channel independence is preserved — each channel fires independently whenever it detects a step
- No window sizing problem (§5d sizing table below) — the monitor never times out

### 5d. Detection window sizing

The monitoring window must cover the **slowest expected user on the most channels**:

| Scenario | Expected spread | Recommended window |
|----------|----------------|-------------------|
| 2-channel, expert | 6 s | 30 s (plenty of margin) |
| 4-channel, expert | 12 s | 30 s |
| 4-channel, intermediate | 20–40 s | 60 s |
| 4-channel, beginner | 40–80 s | 90 s |

**Current window: 80 s.** This covers the intermediate 4-channel case but may time out on a slow beginner doing 4-channel. Consider extending to **90 s** as a safer default, or making it **adaptive based on channel count** (2-channel: 60 s, 4-channel: 90 s).

**Per-channel independence is the key design requirement:** each channel runs its own 5-point baseline → threshold → sustain check from the moment the window opens. Channel A detecting at t=5s and channel D not detecting until t=50s is normal and correct — they are processed independently. The window timeout applies per-channel, not globally.

### 5e. Signal event timescales post-injection

| Phase | Duration | What's happening |
|-------|----------|-----------------|
| P2P spike | 0–5 s post-injection | Syringe push disturbance — mechanical |
| λ onset | 0–10 s post-injection | Bulk RI shift at flow front arrival |
| %T dip | 0–10 s post-injection | Flow front scattering light briefly |
| %T recovery | 10–30 s post-injection | Cell clearing, buffer matching |
| Slope change detectable | 20–60 s post-injection | Binding accumulating on surface |

**Detection can fire as early as 1–5 s post-injection** (λ onset + P2P observed within the first second). The recovery check uses a 20s lookback window and can confirm retroactively.

**Injection timestamp** = earliest of P2P spike onset OR λ onset, whichever fires first and scores. Not the slope change (that lags injection by 20–60s).

---

## 6. Implementation status

> **Architecture (Feb 25–26, 2026):** `_InjectionMonitor` is implemented and wired. Detection is fully decoupled from `ManualInjectionDialog` (which is now a state container only).

### Step 1 — `_InjectionMonitor` in `injection_coordinator.py` ✅ Done

Lines 63–316. Bidirectional delta (not sign-flipped from `_WashMonitor`). Stays alive for wash detection (fire #2). See §Architecture above.

### Step 2 — Monitor lifecycle ✅ Done

Started in `_InjectionSession._setup()` for each active channel. Stopped by `_stop_all_monitors()` on bar done, cancel, timeout, or `cleanup_monitors()` at cycle end. P4SPR keeps monitors alive after injection (for wash fire #2); P4PRO stops on injection.

### Step 3 — Multi-feature scorer wired ✅ Done

`score_injection_event()` in `spr_signal_processing.py` called from `_InjectionMonitor._fire()`. Four active features: P2P (Option B std proxy at 0.30 weight), %T dip+recovery (Option A at 0.40 weight), slope change (0.20), λ onset (0.10). Score ≥ 0.65 + ≥2 features → confirmed.

### Step 4 — `ManualInjectionDialog` replaced ✅ Done

Old scan loop (`_scan_channel`, `_handle_all_detected`, `_finalize_detection`) deleted. Dialog is now an 87-line state container. LED feedback (PENDING → CONTACT) still works via `bar.update_channel_detected()` called from `_handle_injection()`.

### Step 5 — Retroactive scan ⚠ Partially obsolete

`detect_injection_all_channels()` still exists in `InjectionCoordinator` but is rarely needed — `_InjectionMonitor` continuous monitoring provides coverage that the dialog window used to miss. Still available as fallback for `detection_priority="off"` path.

### Step 6 — Anomaly flags ✅ Partial

`POSSIBLE_BUBBLE` and `POSSIBLE_LEAK` emitted via `anomaly_detected` signal → `_on_anomaly()` in `_InjectionSession` → `bar_ref.set_inject_anomaly()` or `bar_ref.set_anomaly()` on `UnifiedCycleBar`. `guidance_coordinator.emit_alert()` path not yet wired.

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
BUBBLE_T_DROP_THRESHOLD          = 2.0    # %T drop for bubble flag (bubbles drop 2–25%; real injection transient <2%)
BUBBLE_RECOVERY_THRESHOLD        = 0.20   # if recovery < this → bubble (vs injection which recovers >0.55)
LEAK_T_DROP_THRESHOLD            = 2.0    # %T drop for leak flag
LEAK_DURATION_S                  = 30.0   # sustained drop duration for leak
```

---

## 9. What changed vs v1

| Component | v1 (λ-only) | v2 (implemented) |
|-----------|-------------|-----------------|
| Detection engine | `ManualInjectionDialog._scan_channel()` (200ms loop) | `_InjectionMonitor` (2s poll, per background thread) |
| Algorithm | λ deviation > 2.5σ baseline | Bidirectional delta across two 5-frame windows + multi-feature scorer |
| Wash detection | `_WashMonitor` (separate class, slope-drop) | `_InjectionMonitor` fire #2 (same monitor, 15s dead zone) |
| Wash flag placement | `_on_wash_detected` in `_pump_mixin` | ⚠ Not yet — only bar UI updated (gap) |
| Contact marker move on wash | ✅ `_WashMonitor` moved it | ⚠ Not yet (gap) |
| Dialog | Visible dialog with scan loop | 87-line state container, no UI |
| Retroactive scan | Primary fallback | Still available but rarely needed |
| `detection_priority="off"` | Skips dialog detection | Skips `_InjectionMonitor` (not yet confirmed — verify) |

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
| `POSSIBLE_BUBBLE` | 🫧 | "Bubble trouble — Channel B. Signal may recover." |
| `POSSIBLE_LEAK` | 💧 | "Check for leak — Channel C. Check connections." |
| `CHIP_DEGRADED` | ⚠️ | "Signal broadening — Channel X. Sensor chip may need replacing." |
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
