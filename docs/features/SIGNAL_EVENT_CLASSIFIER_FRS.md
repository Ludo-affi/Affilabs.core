# Signal Event Classifier — FRS

**Document Status:** 🟡 Partially implemented — core scoring done, UI display and Sparq Coach pending
**Last Updated:** 2026-02-26

### Implementation status by file

| File | Status | Notes |
|------|--------|-------|
| `affilabs/services/signal_telemetry_logger.py` | ✅ Implemented | Per-channel CSV, rolling p2p + slope, disk guard. Wired via `spectrum_helpers.py` + `_acquisition_mixin.py` session lifecycle. |
| `affilabs/utils/signal_event_classifier.py` | ✅ Implemented | `check_readiness()` + `check_bubble()` as static methods. Called per-poll from `_InjectionMonitor._check_bubbles()`. Readiness called from `_InjectionMonitor._poll()` (fire_count == 0 guard). |
| `affilabs/services/signal_quality_scorer.py` | ✅ Implemented | `SignalQualityScorer` singleton, `CycleQualityScore`, `RunQualityScore`. Wired: `notify_injection_detected`, `notify_wash_detected`, `notify_leak_detected`. `record_frame()` not yet wired from `spectrum_helpers`. |
| `affilabs/widgets/signal_event_badge.py` | ❌ Not implemented | Pre-inject readiness badge widget. Planned. |
| `affilabs/services/sparq_coach_service.py` | ❌ Not implemented | Tier 1/2 upload + response handling. Planned. |
| Queue dot display | ❌ Not wired | `SignalQualityScorer.cycle_scored` signal exists but not connected to `QueueSummaryWidget`. |
| Edits tab score display | ❌ Not wired | `CycleQualityScore` not yet serialised to session or shown in cycle list. |

---

## 1. Purpose

Two live guidance outputs only:

1. **Pre-injection readiness** — "Ready" or "Wait" before the user commits expensive reagent
2. **Bubble detection** — the one real-time risk that can contaminate data irreversibly mid-experiment

Everything else (binding interpretation, dissociation, regen quality, concentration context) is deferred. The telemetry logger runs silently and collects data for future interpretation layers. Nothing is shown to the user during incubation beyond the existing dot-in-circle contact monitor.

**Flags are live UI only** — they assist with injection timing but are not tracked in Edits.

---

## 2. What the User Sees

### Pre-inject (Stage 1)

Simple one-line readiness badge per channel pair, shown during `pre_inject` sub-phase only:

```
┌─────────────────────────────────┐
│  Ch A  ●  Ready                 │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│  Ch A  ●  Wait — stabilising    │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│  Ch A  ⚠  Check baseline        │
└─────────────────────────────────┘
```

No quantification. No nm or RU values shown. Plain English only.

### During contact / wash (Stage 2)

**Nothing shown unless a bubble is detected.** The dot-in-circle contact monitor is the user's visual anchor during incubation. No binding interpretation, no confidence scores, no delta-SPR display.

If a bubble is detected:

```
┌─────────────────────────────────┐
│  Ch A  ⚠  Air bubble suspected  │
│            — check flow         │
└─────────────────────────────────┘
```

Alert persists until the signal recovers (P2P returns to baseline, dip depth and FWHM normalise). Auto-dismisses after recovery is confirmed (3 consecutive clean frames).

### When to show / hide

- **Pre-inject badge**: shown during `pre_inject` sub-phase, ≥ 10 frames accumulated, SensorIQ not CRITICAL
- **Bubble alert**: shown any time acquisition is running and bubble criterion fires
- **Hidden**: all other times — no placeholder, nothing rendered

---

## 3. Stage 1 — Pre-Inject Readiness

### 3.1 Purpose

Answer: **"Is my signal stable enough to inject right now?"**

Pure threshold checks — no probability, no tables. Deterministic and auditable.

### 3.2 Readiness criteria

All criteria must pass for READY. Any WAIT → overall WAIT. Any CHECK → overall CHECK (overrides WAIT).

| Criterion | Feature | READY | WAIT | CHECK |
|---|---|---|---|---|
| Baseline stable | `slope_5s` | \|slope\| < 7 RU/s ≥ 10 frames | 7–35 RU/s | > 35 RU/s sustained > 30 s |
| Noise acceptable | `p2p_5frame` | < 12 RU (noise floor) | 12–35 RU | > 35 RU sustained > 10 s |
| Control flat | `control_slope_5s` | \|slope\| < 7 RU/s | 7–18 RU/s | > 18 RU/s |
| No bulk artefact | `slope_diff` (sample − control) | Uncorrelated | Weakly correlated | Strongly correlated |
| Regen complete | `regen_delta` from last cycle | < 18 RU | 18–53 RU | > 53 RU |
| SensorIQ | Per channel | GOOD or better | FAIR | POOR or CRITICAL |

`slope_5s` = linear regression over last 5 frames (5 s at 1 Hz).
`p2p_5frame` = rolling std of last 5 frames.
`control_slope_5s` = same as slope_5s on control channel. Skip if no control channel configured.
`slope_diff` = `slope_5s[sample] − slope_5s[control]`. Correlated = both moving same direction, similar magnitude.
`regen_delta` = post-regen baseline − pre-injection baseline from previous cycle. Skip on first cycle.

### 3.3 Readiness messages

| State | Message | Colour |
|---|---|---|
| `READY` | "Ready" | #34C759 green |
| `WAIT` — baseline | "Wait — stabilising" | #FF9500 amber |
| `WAIT` — noise | "Wait — noisy signal" | #FF9500 amber |
| `WAIT` — control | "Wait — reference settling" | #FF9500 amber |
| `CHECK` — baseline | "Check baseline — unstable" | #FF3B30 red |
| `CHECK` — regen | "Check — residual signal from last cycle" | #FF3B30 red |
| `CHECK` — bulk | "Check — buffer matching" | #FF3B30 red |
| `CHECK` — noise | "Check — persistent noise" | #FF3B30 red |
| `CHECK` — IQ | "Check — signal quality low" | #FF3B30 red |

First cycle on a fresh chip: regen criterion skipped; baseline stability criterion loosened (chips equilibrate over 10–20 min).

---

## 4. Stage 2 — Bubble Detection

### 4.1 Why bubble detection matters

An air bubble passing through the flow cell during incubation is the primary data quality risk. It produces a transient signal disturbance that looks like a binding event but is not. Unlike other artefacts, the user cannot tell from the raw sensorgram alone whether a spike is a bubble or a real signal — the dip shape tells the truth.

### 4.2 Bubble signature

A bubble passing through the flow cell partially occludes the optical path. It reduces evanescent field coupling efficiency, producing a characteristic transmission dip change:

- **Dip depth drops ~5%+** — e.g. a 77% dip drops to ~72% or lower. Air reduces optical coupling.
- **FWHM broadens slightly** — the dip gets wider and shallower as the bubble distorts evanescent field uniformity across the illuminated area.
- **P2P spikes** — the signal is noisy during the passage (1–3 frames typically).

A bubble is identified by the **simultaneous** occurrence of all three:

| Feature | Normal | Bubble |
|---|---|---|
| `p2p_5frame` | 12–15 RU | 20–25 RU — moderate increase (~1.5–2× normal) |
| `dip_depth` | Stable (reference ± 3%) | Drops ≥ 5% from reference — e.g. 77% → < 72% |
| `fwhm_nm` | Stable (~20–40 nm) | Broadens ≥ 3 nm from reference |

All three must fire together. Any single feature alone is insufficient:
- P2P at 20–25 RU alone → easily caused by normal signal variation; would false-trigger constantly
- Dip depth drop alone → LED intensity drift or intensity change
- FWHM change alone → slow surface change or regen effect

The P2P increase is intentionally modest — it is a supporting criterion, not the primary detector. Dip depth drop is the most reliable single indicator; the triple combination is unambiguous.

**Fourth discriminator — channel correlation:**
- Bubble on **all channels simultaneously** → system-level air event (main tubing upstream of flow cell split)
- Bubble on **one channel only** → localised to that flow cell

This cross-channel pattern is logged in telemetry and used to classify bubble severity. It does not change the per-channel alert — both cases show the alert on affected channels.

### 4.3 Detection criterion

```python
bubble_detected = (
    p2p_5frame > BUBBLE_P2P_THRESHOLD                              # RU — noise spike
    AND (dip_depth_ref - dip_depth) / dip_depth_ref > BUBBLE_DEPTH_THRESHOLD   # ≥5% drop
    AND (fwhm_nm - fwhm_ref) > BUBBLE_FWHM_THRESHOLD              # broadening only
)
```

Note: dip depth drop is directional — a bubble always reduces depth, never increases it. FWHM broadens, never narrows. The criterion uses directional checks, not absolute difference.

Reference values (`dip_depth_ref`, `fwhm_ref`) = mean of last 10 clean frames before contact window opened.

Thresholds — starting points, to be validated from telemetry of real bubble events:

| Parameter | Initial value | Unit | Notes |
|---|---|---|---|
| `BUBBLE_P2P_THRESHOLD` | 20 | RU | ~1.5× normal (12–15 RU) — supporting criterion only |
| `BUBBLE_DEPTH_THRESHOLD` | 0.05 | fractional | 5% drop — e.g. 77% → 72% |
| `BUBBLE_FWHM_THRESHOLD` | 3 | nm | Broadening threshold |

All three in `settings.py` — adjustable without code change.

> **Study needed:** Confirm bubble characteristics from real data — how fast does depth drop (frames), does FWHM always broaden or sometimes just shift, and recovery time (frames). The 5% depth threshold is the empirical anchor; FWHM and P2P thresholds need validation.

### 4.4 Alert behaviour

The alert is **advisory only** — it indicates a potential data quality issue and suggests a corrective action. It does not stop the cycle or reset the coordinator.

Badge text when bubble detected:

```
┌─────────────────────────────────────────┐
│  Ch A  ⚠  Possible air bubble           │
│            Inject a small sample pulse  │
│            to flush and re-establish    │
└─────────────────────────────────────────┘
```

- **Fires immediately** on first frame meeting all three criteria — no EMA, no confirmation delay
- **Persists** until 3 consecutive clean frames (all criteria back within normal range) — then auto-dismisses
- **If signal recovers after a flush pulse** → data after the pulse is likely valid; data during the bubble window is flagged in telemetry
- **Logged to telemetry** with `bubble_detected = True` for affected frames — analyst can assess impact offline
- **Does not place a flag** — bubble is a data quality qualifier, not a cycle event

### 4.5 Features required

`dip_depth` and `fwhm_nm` are already computed by `_latest_iq_metrics` per channel per frame. No new computation required — just read the values.

---

## 5. Adaptive Transition Detection (for coordinator improvement)

This section documents the target algorithm for improving the existing injection/wash detection in `spr_signal_processing.detect_injection_all_channels()`. It is not part of the classifier badge — it feeds into the coordinator's flag placement.

### 5.1 Current limitation

The coordinator uses a fixed slope confidence threshold (0.15). This does not adapt to per-channel noise — a noisy channel has the same threshold as a quiet one.

### 5.2 Adaptive threshold

```python
baseline_std = np.std(positions[-5:])       # std of last 5 frames before detection window
threshold    = N_SIGMA * baseline_std        # adaptive per-channel threshold
detected     = abs(delta_1frame) > threshold # spike above noise
```

`N_SIGMA` = `settings.INJECTION_DETECTION_SIGMA` (default 3, raise to 4 if false positives observed in telemetry).

- **3σ** — sensitive; detects weak injections; may false-trigger on noisy baselines
- **4σ** — conservative; fewer false positives; may miss weak injections

### 5.3 Detection limits at 1 Hz, max P2P = 12 RU

| Channel noise (std) | 3σ threshold | 4σ threshold | Latency |
|---|---|---|---|
| Quiet (std ≈ 2 RU) | 6 RU | 8 RU | **1 s** |
| Normal (std ≈ 4 RU) | 12 RU | 16 RU | **1–2 s** |
| Noisy (std ≈ 6 RU) | 18 RU | 24 RU | **2–3 s** |
| Below threshold | — | — | Not detected — manual flag in Edits |

Typical injection RI step: 70–530 RU. Reliable detection in 1–2 s for normal channels.

**Detection accuracy target: ±2 seconds of true onset.** Fine adjustment in Edits tab.

### 5.4 Direction validation

At each transition, the sign of `delta_1frame` is checked against expectation:

| Transition | Expected sign | Wrong sign |
|---|---|---|
| Buffer → Sample (injection) | Positive | Buffer mismatch — sample RI < buffer RI |
| Sample → Buffer (wash) | Negative | Buffer mismatch |
| Buffer → Regen agent | Negative | Check regen agent |
| Regen agent → Buffer | Positive | Buffer mismatch |

Wrong direction → `BUFFER_MISMATCH` flag emitted; sub-phase does not advance.

Wash detection uses the same adaptive criterion with `baseline_5s` computed from the last 5 frames of the contact window — not the pre-injection baseline. The wash is typically cleaner and sharper than injection (buffer is homogeneous, no binding component).

---

## 6. Silent Telemetry Logger

> **Status: ✅ Implemented** (`affilabs/services/signal_telemetry_logger.py`)

Runs silently every frame. Invisible to the user. Collects data for future interpretation layers.

Controlled by `SIGNAL_TELEMETRY_ENABLED` in `settings.py`.

Output: Per-channel rolling CSV files in `_data/logs/telemetry/`. Disk guard: skips writes when free space < 500 MB.

### 6.1 Auto-labelling from existing flags

Transition events labelled automatically from coordinator flag timestamps:

| Condition | Auto label |
|---|---|
| Frame within ±2 s of injection flag | `INJECTION_FRONT` |
| Frame within ±2 s of wash flag | `WASH_FRONT` |
| Frame > 5 s after injection flag, before wash flag | `CONTACT_WINDOW` |
| Frame > 5 s after wash flag | `WASH_WINDOW` |

### 6.2 Schema (one row per channel per frame)

| Column | Type | Notes |
|---|---|---|
| `session_id` | str UUID | Generated at acquisition start |
| `timestamp_utc` | ISO datetime | |
| `elapsed_s` | float | Seconds since acquisition start |
| `channel` | A/B/C/D | |
| `is_control_channel` | bool | Designated reference channel |
| `cycle_type` | str | `_current_cycle.type` or `"none"` |
| `cycle_sub_phase` | str | `pre_inject` / `contact` / `wash` / `none` |
| `cycle_elapsed_frac` | float 0–1 | |
| `injection_index` | int \| null | 0-based index in concentration series |
| `dip_position_ru` | float | Pipeline output in RU (dip_position_nm × 355) |
| `delta_1frame_ru` | float | `position[n] − position[n−1]`, signed, RU |
| `slope_5s_ru_per_s` | float | Signed, RU/s |
| `p2p_5frame_ru` | float | RU |
| `raw_intensity_ratio` | float | P-pol peak / calibration reference |
| `dip_depth` | float | Fractional — from `_latest_iq_metrics` |
| `fwhm_nm` | float | From `_latest_iq_metrics` |
| `control_slope_5s_ru` | float \| null | Control channel slope, RU/s |
| `slope_diff_ru` | float \| null | `slope_5s − control_slope_5s`, RU/s |
| `iq_level` | str | `SensorIQLevel.value` |
| `stage1_verdict` | str | `READY` / `WAIT` / `CHECK` / `none` |
| `bubble_detected` | bool | Stage 2 bubble criterion |
| `positive_front` | bool | Adaptive threshold fired positive |
| `negative_front` | bool | Adaptive threshold fired negative |
| `auto_label` | str \| null | From flag timestamps — see §6.1 |
| `manual_label` | str \| null | Null at runtime — filled offline by analyst |

All user-facing values in RU. Internal processing in nm where noted.

### 6.3 Write strategy

- Buffer 20 rows, flush in one write
- `threading.Thread` — never blocks acquisition loop
- Write to `.tmp` then `os.replace()` — no corrupt files on crash

---

## 6b. Signal Event Registry — Flags into Scoring

The monitoring system defined in [INJECTION_DETECTION_FRS.md](INJECTION_DETECTION_FRS.md) emits five event flags during acquisition. This section is the canonical mapping of those flags into the per-cycle score (§7) and the global run star rating (§8). Every flag type has exactly one role in scoring — no double-counting.

### 6b.1 Flag definitions (from INJECTION_DETECTION_FRS.md)

| Flag | Source | What it means |
|------|--------|---------------|
| `INJECTION_DETECTED` | Multi-feature scorer (score ≥ 0.65, ≥ 2 features) | A valid injection step-change was identified — position deviated ≥ 3σ from baseline, sustained over ≥ 3 consecutive points |
| `POSSIBLE_BUBBLE` | P2P sustained + %T large drop (2–25%) + no recovery | Air entered the flow cell — no plasmon signal, optical path disrupted |
| `POSSIBLE_LEAK` | %T drops >2% AND stays down >30s | Sustained light loss — possible flow cell leak or disconnected line |
| `BASELINE_DRIFT` | slope >0.02 nm/s, no P2P spike, no %T event | Signal drifting before injection — system not equilibrated |
| `SIGNAL_SPIKE` | P2P elevated ≤2 frames, returns <3s, no slope change | Transient 1–2 point excursion — mechanical or electrical noise |

### 6b.2 Per-cycle score impact

These map directly into the §7.2 component weights. Each component is computed from the flags emitted during that cycle:

| Score component | Weight | Flag(s) that drive it | Penalty logic |
|----------------|--------|----------------------|---------------|
| **Baseline stability** | 25 | `BASELINE_DRIFT` before injection | Full credit if no drift flags during pre-inject sub-phase; −5 pts per drift event; 0 pts if drift sustained >30s |
| **Injection detection confidence** | 20 | `INJECTION_DETECTED` | Full credit if detected cleanly (score ≥ 0.80); 10 pts if detected weakly (0.65–0.79); 0 pts if not detected |
| **Signal-to-noise during contact** | 20 | `SIGNAL_SPIKE` | Full credit if ≤1 spike in contact window; −5 pts per additional spike; 0 pts if >4 spikes |
| **Wash detection confidence** | 15 | (wash flag, scored separately) | Full credit if wash front detected; 0 pts if timeout |
| **Bubble-free contact window** | 15 | `POSSIBLE_BUBBLE` | Full credit if zero bubble frames; −5 pts per bubble frame (1 frame = 1s); 0 pts if >3 bubble frames |
| **Regen effectiveness** | 5 | (regen delta from prior cycle) | Full credit if regen_delta < 18 RU; 0 pts if > 53 RU |
| **Leak detected** | Override | `POSSIBLE_LEAK` | If `POSSIBLE_LEAK` fires at any point during the cycle, cycle score is **clamped to max 20** — data is likely unusable |

### 6b.3 Global run star rating impact

Roll-up across all scored binding cycles into the §8 signal quality sub-score (0–4 stars):

| Flag | Run-level roll-up |
|------|------------------|
| `INJECTION_DETECTED` (missed) | Cycles where injection was not detected score lower via §7.2 → flow through to §8.3 band distribution automatically |
| `POSSIBLE_BUBBLE` | Aggregated as `bubble_cycles` count in `RunQualityScore`. Each bubble cycle already penalised per §7.2 → flows to §8.3 automatically. Sparq Coach receives raw count for advice generation. |
| `POSSIBLE_LEAK` | Clamped-score cycles (≤20) score as Poor in §8.3. `leak_cycles` count reported to Sparq Coach. |
| `BASELINE_DRIFT` | Penalised per cycle via baseline stability component → flows to §8.3. Aggregate `drift_cycles` count for Sparq Coach pattern detection. |
| `SIGNAL_SPIKE` | Individual spikes do not affect run-level stars (they're minor). Aggregate spike counts per channel logged in telemetry for future diagnostics. Reported to Sparq Coach only if count > 10 in a run (pattern worth mentioning). |

### 6b.4 Sparq Coach payload additions

The Tier 1 JSON payload (§9.3) gains these aggregate fields from flag counts:

```json
"signal_events": {
  "bubble_cycles": 1,
  "leak_cycles": 0,
  "drift_cycles_pre_inject": 2,
  "missed_injection_cycles": 1,
  "spike_total_count": 3,
  "spike_high_channel": null
}
```

`spike_high_channel` = channel letter (A/B/C/D) if one channel accounts for >50% of total spikes — indicates a specific flow cell or connection problem. `null` if spikes are distributed.

---

## 7. Post-Cycle Quality Report

### 7.1 Purpose

Each completed binding cycle receives a single quality score (0–100) and a short auto-generated plain-English note. The score builds live during the cycle and finalises when the cycle ends. It is the primary feedback mechanism for the user during data collection — visible in the queue and transferred to Edits for post-hoc triage.

The score answers one question: **"Was this cycle worth keeping?"**

### 7.2 Score components

| Component | Weight | What it measures |
|---|---|---|
| Baseline stability (pre-inject) | 25 | Were stage 1 criteria met before injection? |
| Injection detection confidence | 20 | Was a clear positive front detected (adaptive threshold)? |
| Signal-to-noise during contact | 20 | Was `p2p_5frame` within the noise floor (< 12 RU) for ≥ 80% of contact frames? |
| Wash detection confidence | 15 | Was a clear negative front detected? |
| Bubble-free contact window | 15 | No bubble frames during contact (weighted by bubble frame count) |
| Regen effectiveness | 5 | `regen_delta` < 18 RU (skipped on first cycle) |

Score = Σ(component × weight), clipped to [0, 100].

Components fire on cycle completion — `regen_delta` is computed after the post-regen wash sub-phase closes.

### 7.3 Score bands

| Score | Band | Queue dot | Label |
|---|---|---|---|
| 85–100 | Excellent | 🟢 Green | "Clean cycle" |
| 65–84 | Good | 🟡 Amber | "Usable" |
| 40–64 | Marginal | 🟠 Orange | "Check in Edits" |
| 0–39 | Poor | 🔴 Red | "Consider repeating" |

### 7.4 Auto-generated note

One to three plain-English sentences, appended to the cycle's note field in telemetry and Edits. Examples:

| Trigger | Note text |
|---|---|
| Baseline WAIT at injection | "Baseline was still drifting when injection was triggered." |
| Injection front missed (threshold not crossed) | "Injection start could not be auto-detected — verify in Edits." |
| Bubble detected (1–3 frames) | "Short bubble event during contact window. Check sensorgram." |
| Bubble detected (> 3 frames) | "Sustained bubble event. Data quality during contact is uncertain." |
| Wash front missed | "Wash start not detected. Wash flag may need manual placement." |
| Regen incomplete | "Residual signal from previous cycle. Consider longer regen or higher concentration." |
| Clean cycle | "Baseline stable, injection and wash clearly detected, no bubble events." |

Notes are concatenated. A cycle with a drifting baseline + bubble gets both sentences.

### 7.5 Queue display

The cycle row in `QueueSummaryWidget` gains a coloured dot (5 × 5 px, right-aligned) once the cycle ends. During the cycle the dot shows as a pulsing grey spinner to indicate live scoring is in progress.

```
┌────────────────────────────────────────────────┐
│  #3  Analyte injection 1 (100 nM)     3:20   🟢 │
│  #4  Wash                             1:45   🟡 │
│  #5  Analyte injection 2 (500 nM)     3:20   ⟳  │  ← current, scoring in progress
└────────────────────────────────────────────────┘
```

Dot colours follow §7.3. The dot is advisory only — it does not block cycle progression.

### 7.6 Transfer to Edits

> **Status: ❌ Not yet wired.** `CycleQualityScore` objects are produced by `SignalQualityScorer` and emitted via `cycle_scored` signal, but are not currently serialised to session recordings or shown in the Edits tab cycle list.

When implemented, each cycle row in the Edits tab cycle list gains a coloured dot and the auto-generated note appears in the cycle detail panel.

**Implemented `CycleQualityScore` dataclass** (in `signal_quality_scorer.py`):

```python
@dataclass
class CycleQualityScore:
    cycle_index: int
    cycle_id: str                       # ← added (not in original FRS)
    cycle_type: str
    score: int                          # 0–100
    band: str                           # "excellent" / "good" / "marginal" / "poor"
    note: str                           # auto-generated plain English
    components: dict[str, float]        # per-component raw scores for debugging
    finished: bool                      # True if cycle reached natural end

@dataclass
class RunQualityScore:
    signal_quality_stars: int           # 0–4
    completion_stars: float             # 0, 0.5, or 1
    total_stars: int                    # 1–5 (clamped)
    tier: str                           # "easy" / "medium" / "pro"
    cycles_planned: int
    cycles_finished: int
    note: str                           # e.g. "2 poor cycles, run completed"
    manual_override: int | None         # user-set star count, or None
```

### 7.7 Planned source file

`affilabs/services/signal_quality_scorer.py` — `SignalQualityScorer` class. Receives per-frame telemetry from the logger, tracks component running totals, emits `CycleQualityScore` on cycle end and `RunQualityScore` on session end via Qt signals.

---

## 8. Run Star Rating

### 8.1 Purpose

A single 1–5 star rating for the entire run (recording session). Shown in the Edits tab header and in the experiment index (Notes tab).

The rating answers: **"Was this run worth spending time analysing?"**

Three inputs feed the rating:

| Input | Weight | What it captures |
|---|---|---|
| Signal quality roll-up | 4 stars max | Cycle score band distribution — injection quality, bubbles, missed detections |
| Run completion | 1 star | Did the user finish all planned cycles? |
| Run complexity tier | Modifier (display only) | Contextualises the stars — a ⭐⭐⭐⭐ Pro run means more than ⭐⭐⭐⭐ Easy |

### 8.2 Run complexity tier

Determined at session end from the number of scored binding cycles:

| Tier | Binding cycles | Label shown in UI |
|---|---|---|
| **Easy** | ≤ 5 | "Easy" |
| **Medium** | 6–10 | "Medium" |
| **Pro** | ≥ 11 or overnight flag | "Pro" |

"Overnight flag" = session duration > 6 hours (user left acquisition running unattended).

The tier is displayed alongside the stars as a badge: `⭐⭐⭐⭐  Medium`. It does not adjust the numerical roll-up — it is context only, so users understand the difficulty level of the run they are comparing against.

### 8.3 Signal quality roll-up (4 stars)

The distribution of cycle quality bands across all **scored binding cycles** maps to a 0–4 star signal quality sub-score:

| Signal quality sub-score | Criterion |
|---|---|
| 4 stars | ≥ 80% of cycles Excellent or Good; zero Poor cycles |
| 3 stars | ≥ 60% of cycles Excellent or Good; ≤ 1 Poor cycle |
| 2 stars | ≥ 40% of cycles Good or better; ≤ 2 Poor cycles |
| 1 star | Some usable data; > 2 Poor cycles OR majority Marginal |
| 0 stars | Majority of cycles Poor; run likely needs repeating |

Cycles with injection problems, air bubbles, missed injection detection, or incomplete contact windows already score lower via the §7 component weights — they flow through to this roll-up automatically without double-counting.

Only binding cycles are included. Baseline-only, regen-only, activation, and immobilisation cycles are excluded. Minimum 2 binding cycles required — otherwise "Not enough data".

### 8.4 Run completion component (1 star)

Completion = `cycles_finished / cycles_planned_at_start`.

`cycles_planned_at_start` = length of `_original_method` at the time acquisition began (snapshotted by `QueueManager`). Cycles appended mid-run via "Repeat cycle" or user additions are added to the denominator only if they were also completed.

| Completion | Contribution |
|---|---|
| ≥ 90% of planned cycles finished | +1 star |
| 70–89% finished | +0.5 star (rounds to nearest whole star in display) |
| < 70% finished | +0 stars |

**Nuance:** A cycle counts as "finished" if it reached the end of its wash sub-phase, regardless of cycle quality score. A user who aborted a bubble-damaged cycle and re-queued it via "Repeat cycle" gets credit for the repeat completing — the abort is penalised by the Poor cycle score, not by completion.

A run stopped by the user before all cycles completed (not due to hardware error) is logged with `abort_reason = "user_stop"`. This does not override the completion calculation — if they completed 9/10 cycles before stopping, they still get ≥ 90% credit.

### 8.5 Final star rating

```
stars = signal_quality_sub_score + completion_star
stars = clamp(stars, 1, 5)
```

Minimum 1 star — even a failed run gets recorded so the user has a reference.

Example outcomes:

| Signal quality | Completion | Tier | Stars displayed |
|---|---|---|---|
| 4 (all clean cycles) | 1 (all finished) | Medium | ⭐⭐⭐⭐⭐  Medium |
| 3 (1 poor cycle) | 1 (all finished) | Easy | ⭐⭐⭐⭐  Easy |
| 4 (all clean cycles) | 0 (aborted halfway) | Pro | ⭐⭐⭐⭐  Pro |
| 1 (several poor cycles) | 0.5 (70–89%) | Medium | ⭐⭐  Medium |
| 0 (majority poor) | 0 (aborted early) | Easy | ⭐  Easy |

### 8.6 Display locations

- **Edits tab header** — stars + tier badge next to session filename. Static, not editable.
- **Experiment index** (Notes tab) — stars + tier in session list row.
- **Experiment browser dialog** — stars + tier in search results.

### 8.7 Manual override

User can click the stars in Edits to override. Manual override stored in the session index entry. Auto-generated rating shown alongside: `Auto: ⭐⭐⭐ Medium → Manual: ⭐⭐⭐⭐`.

---

## 9. Sparq Coach — Post-Run Debrief

### 9.1 Purpose

After a run completes, the user can send their run data to **Sparq Coach** — an LLM-powered (Claude Haiku) debrief that reads the run quality summary and delivers concrete, actionable advice for the next run. Think of it as a senior SPR scientist looking at your data and telling you what to fix.

Examples of advice Sparq Coach can give:

| Run pattern | Sparq advice |
|---|---|
| ≥ 2 cycles with bubble events | "Your flow cell had air events on multiple cycles. Degas your running buffer for 10 min under vacuum before the next run, and prime the lines twice before starting acquisition." |
| Missed injection detection | "Injection start couldn't be detected on 3 cycles — your baseline may have been drifting at injection time. Wait for the Ready badge before triggering injection." |
| Regen incomplete across cycles | "Residual signal is accumulating across cycles. Try increasing your regeneration agent concentration or extending the contact time." |
| Low signal on all channels | "Binding signal was weak across all concentrations. Check ligand density — you may need to re-immobilise at higher surface density." |
| Poor cycle on one channel only | "Channel B scored consistently lower than A/C/D. Check the flow cell inlet for that channel — possible partial blockage or air pocket." |
| ⭐⭐⭐⭐⭐ clean run | "Excellent run — baseline was stable, all injections detected cleanly, no bubble events. Your data is ready for analysis." |

The advice is generated by Haiku from the structured run summary. It is not pre-scripted — Haiku synthesises patterns across all cycle notes and scores to give a holistic debrief, not just per-issue bullets.

### 9.2 "Send to Sparq Coach" button

A single button in the Edits tab header, shown for any completed session with a `RunQualityScore`:

```
┌──────────────────────────────────────────────────────────────┐
│  Session: 2026-02-25_14-32  ⭐⭐⭐  Medium     [Sparq Coach ✦] │
└──────────────────────────────────────────────────────────────┘
```

Clicking the button opens a **pre-send confirmation dialog** showing exactly what will be uploaded, with a data tier selector. The Sparq Coach response appears in the Sparq sidebar — no new UI component needed.

### 9.3 Data tiers

Two tiers, selected in the confirmation dialog before each send:

#### Tier 1 — Summary only (default, always available)

Structured run metadata only. No sensorgram curves, no ligand/analyte names, no concentration values, no device serial.

```json
{
  "run_id": "<random UUID generated at send time — not session UUID>",
  "app_version": "2.0.5",
  "tier": "medium",
  "stars": 3,
  "cycles_planned": 8,
  "cycles_finished": 7,
  "scored_cycles": [
    { "index": 1, "band": "good", "score": 72, "notes": ["Baseline was still drifting when injection was triggered."] },
    { "index": 2, "band": "excellent", "score": 91, "notes": ["Clean cycle."] },
    ...
  ],
  "aggregate": {
    "bubble_cycles": 1,
    "missed_injection_cycles": 1,
    "poor_cycles": 0,
    "marginal_cycles": 2,
    "regen_incomplete_cycles": 0
  }
}
```

No PII. No customer name. No device serial. The `run_id` is a fresh UUID generated at send time — it cannot be correlated back to the session file on disk.

#### Tier 2 — Full Excel export (explicit opt-in)

Tier 1 payload **plus** the Excel export file (`.xlsx`) attached as a multipart upload. The Excel contains raw sensorgram curves, delta-SPR values per cycle, concentration series, and any user-entered metadata (ligand name, analyte, notes).

The confirmation dialog shows a **clear disclosure** before Tier 2 is enabled:

```
┌─────────────────────────────────────────────────────────────┐
│  ☐  Include full Excel export                               │
│                                                             │
│  This shares your raw sensorgram data, concentration        │
│  series, and any experiment notes you have entered.         │
│  Affilabs may use this data to improve Sparq.               │
│  You can withdraw consent at any time via Settings.         │
└─────────────────────────────────────────────────────────────┘
```

Tier 2 is unchecked by default on every send. The user must explicitly tick it each time — no sticky state.

Haiku uses the Excel data to give curve-aware advice ("your association phase shows a slow on-rate — consider increasing analyte concentration or flow rate").

### 9.4 Confirmation dialog layout

```
┌──────────────────────────────────────────────────────┐
│  Send to Sparq Coach                                 │
│                                                      │
│  Run: 2026-02-25_14-32  ⭐⭐⭐  Medium               │
│                                                      │
│  What will be sent:                                  │
│  ✓  Run summary (scores, cycle notes, star rating)   │
│  ✓  App version                                      │
│  ✗  Device serial / customer identity                │
│  ✗  Ligand / analyte names                           │
│                                                      │
│  ☐  Also include full Excel export (see note above)  │
│                                                      │
│        [Cancel]          [Send to Sparq Coach →]     │
└──────────────────────────────────────────────────────┘
```

### 9.5 Response delivery

Response appears in the **Sparq sidebar** as a new conversation turn — same as any Sparq Q&A response. Sparq opens automatically if the sidebar is collapsed.

The response is framed as a coaching debrief, not a raw LLM dump. System prompt instructs Haiku to act as a senior SPR scientist / coach:

- Lead with what went well (positive reinforcement)
- Identify the top 1–3 issues by impact
- Give one concrete fix per issue (not a list of 10 bullets)
- End with a one-sentence summary for the next run

Coaching history is stored locally in `data/spark/coach_history.json` (same directory as Sparq conversation history). Each entry links the run UUID to the debrief text. No server-side history — the cloud endpoint is stateless.

### 9.6 Network and failure handling

- **Endpoint:** `POST https://api.affilabs.com/sparq/coach/v1` (TBD — backend greenfield)
- **Auth:** Sparq API key from existing Sparq account settings (same key used for Sparq help sidebar)
- **No account:** button is greyed out with tooltip "Connect Sparq account in Settings to use Sparq Coach"
- **Timeout:** 30 s. If no response, show in sidebar: "Sparq Coach is unavailable right now. Your run summary has been saved locally — try again later."
- **Offline:** button disabled with tooltip "No internet connection"
- **Rate limit:** 1 debrief per session per 5 minutes (prevent accidental double-sends)

### 9.7 Data use disclosure (Settings)

A dedicated section in Settings → Sparq:

```
Sparq Coach data sharing

When you send a run to Sparq Coach, Affilabs receives
your run summary (scores and cycle notes). If you opt
in to sharing your Excel export, Affilabs may use that
data to improve Sparq and SPR analysis models.

You can review what was sent in: data/spark/coach_history.json

[Withdraw consent and delete my data]  →  opens affilabs.com/privacy
```

---

## 10. "Repeat Cycle" Action

### 10.1 What it does

A **"Repeat cycle"** button in the Edits tab cycle detail panel. Available on any completed binding cycle. Clicking it re-queues an identical copy of the cycle at the end of the current method queue — using the same duration, concentration label, and channel config as the original.

This is a shortcut for the common workflow: "my cycle scored red, I want to redo it before ending the session."

### 10.2 Behaviour

- Available during an active session only (acquisition running, queue not empty or not finished)
- Appends via `QueueManager.add_cycle()` — same mid-run cycle append path already supported (see CLAUDE.md Gotcha #11)
- Adds a note to the new cycle: "Repeat of cycle #N (auto-queued from Edits)"
- Does not affect the original cycle — the original remains in Edits with its score

### 10.3 UI placement

Single button, right-aligned in the cycle detail panel, visible only for binding cycles with a completed score. Icon: recycle SVG or "↺ Repeat cycle" text button.

Not available if acquisition has already stopped for the session.

---

## 10. Implementation Phases

| Phase | Deliverable | Gate |
|---|---|---|
| **1** | `SignalTelemetryLogger` — records all features silently. No classifier. No badge. | Ship in dev builds. Verify features look physically correct in CSV. |
| **2** | Stage 1 readiness classifier + badge. Pre-inject only. "Ready" / "Wait" / "Check". | Validate against real baselines — does READY fire reliably before clean injections? |
| **3** | Stage 2 bubble detection + alert. | Validate against known bubble events in telemetry. Tune thresholds. |
| **4** | Adaptive transition threshold in coordinator (`detect_injection_all_channels`). | Compare detection latency vs current fixed threshold on real data. |
| **5** | `SignalQualityScorer` — per-cycle score, queue dot, Edits transfer. | Validate scoring bands against real session data. |
| **6** | Run star rating + complexity tier — roll-up in Edits header + experiment index. | Confirm roll-up formula produces sensible ratings on real sessions. |
| **7** | "Repeat cycle" button in Edits. | Confirm mid-run append works correctly via `QueueManager.add_cycle()`. |
| **8** | Sparq Coach — Tier 1 send (summary only). "Send to Sparq Coach" button, confirmation dialog, Sparq sidebar response. | End-to-end test: send real run summary, verify Haiku coaching response is relevant. Requires backend endpoint. |
| **9** | Sparq Coach — Tier 2 opt-in (Excel upload). Checkbox in confirmation dialog, multipart upload, curve-aware advice. | Privacy review. Confirm Excel parsing on Haiku side produces better advice than Tier 1 alone. |
| **10** | Future interpretation layers — binding guidance, regen effectiveness, concentration context. | After sufficient labelled telemetry collected. Individually gated. |

---

## 12. Out of Scope (Phases 1–9)

- Binding interpretation / confidence scores shown to user during acquisition
- Dissociation, regen effectiveness, baseline recovery guidance — telemetry only for now
- Live delta-SPR display — Edits tab handles post-hoc analysis
- Cross-channel differential signal
- Server-side coaching history (Phase 8–9 backend is stateless — history stored locally only)
- Live / online ML — never; all model updates are deliberate and versioned
- CHIP_FAULT, TEMPERATURE_DRIFT — deferred
- Gamification badges / streaks / achievements — deferred to post-Phase 9 based on user feedback
