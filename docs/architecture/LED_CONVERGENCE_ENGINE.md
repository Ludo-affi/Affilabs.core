# LED Convergence Engine — Architecture Specification

**Type:** Architecture Specification  
**Status:** 🟢 Active — Production Default  
**Owner:** Affinite Instruments  
**Last Updated:** February 19, 2026  
**Implementation:** `affilabs/convergence/`

---

## Table of Contents

1. [What Is Convergence](#1-what-is-convergence)
2. [The Core Problem: Device Variability](#2-the-core-problem-device-variability)
3. [System Overview](#3-system-overview)
4. [Algorithm: How Convergence Works](#4-algorithm-how-convergence-works)
5. [Key Engineering Decisions](#5-key-engineering-decisions)
6. [Slope Model (Physics Foundation)](#6-slope-model-physics-foundation)
7. [Sensitivity Classification](#7-sensitivity-classification)
8. [ML Layer](#8-ml-layer)
9. [Convergence Output](#9-convergence-output)
10. [Failure Modes & Detection](#10-failure-modes--detection)
11. [Device Health & Aging](#11-device-health--aging)
12. [Troubleshooting Relevance](#12-troubleshooting-relevance)
13. [Component Map](#13-component-map)
14. [Configuration Reference](#14-configuration-reference)

---

## 1. What Is Convergence

LED convergence is the automated calibration process that finds the optimal operating point for each instrument before every measurement session. It answers a deceptively simple question:

> **Given this specific detector and these 4 LEDs, what integration time and per-LED brightness settings will put each channel's signal within ±5% of 85% of the detector's maximum capacity?**

The result — integration time in milliseconds plus 4 LED brightness values (0–255) — is what the system uses for all subsequent P-pol and S-pol spectrum acquisition.

Getting this wrong causes everything downstream to be wrong: too dim → noisy sensorgrams; too bright → saturated pixels → clipped SPR dip → invalid peak finding. Convergence is the entry point to all reliable measurement.

---

## 2. The Core Problem: Device Variability

This is the hardest part. Two instruments that look identical on the outside can require radically different operating parameters. Differences compound from four sources:

### 2.1 LED-to-LED Brightness Variation

Even brand-new, same-batch LEDs from the same supplier have ±15–25% luminous flux spread. Channel A might deliver 3,500 counts/LED unit at 10 ms integration, while Channel C delivers 2,800 counts/LED unit at the same settings. This variation shifts with:
- Manufacturing batch
- Component aging (LEDs dim over time — slow, but measurable over months)
- Temperature at time of measurement

### 2.2 Detector Sensitivity Variation

Two Ocean Optics Flame-T units do not have the same spectral sensitivity. One unit might be ~30% more sensitive than another at 600–700 nm (the SPR window). Phase Photonics detectors have a completely different sensitivity curve and 12-bit ADC (4,095 max, not 65,535). There is no factory specification tight enough to use the same integration time across all units.

### 2.3 Fiber Coupling Efficiency Variation

The 4-branch bifurcated fiber bundle transmits light from each LED's prism region to the spectrometer. The coupling efficiency varies per branch based on fiber alignment, bend radius, end-face condition, and connector cleanliness. A dirty fiber tip can reduce a channel's signal by 40–60%.

### 2.4 Optical Stack Wear

As instruments age, LEDs dim, fiber surfaces accumulate contamination, and prism/chip coupling degrades. The same device calibrated today vs. six months ago will require different LED values to hit the same signal target — the convergence parameters track this drift.

**The result:** There is no universal table of "correct" settings. Every device must be measured and converged individually, every session.

---

## 3. System Overview

```
CalibrationOrchestrator
  │
  ├── S-pol convergence pass
  │     └── LEDconverge(target_percent = 0.85, tolerance_percent = 0.15, max_iterations = 12,
  │                     model_slopes = per-device slopes, polarization = "S")
  │           → (integration_ms, led_intensities_s, converged)
  │
  └── P-pol convergence pass
        └── LEDconverge(initial_leds = s_leds × 0.92, initial_integration = s_integration_time,
                        target_percent = 0.75, tolerance_percent = 0.05, max_iterations = 12,
                        model_slopes = None, polarization = "P")
              → (integration_ms, led_intensities_p, converged)
              Note: starts from S-pol values; integration can only increase, never decrease

Outputs stored in CalibrationData:
  - integration_ms   (shared, set by S-pol convergence)
  - led_intensities  {ch: {'S': int, 'P': int}} per channel
  - num_scans        (frames averaged per polarization position)
  - convergence_summary (QC reporting dict)
```

Two passes run in sequence: S-polarization, then P-polarization. S-pol is run first because S-pol is always brighter than P-pol (P-pol light is partially absorbed by the SPR coupling at the gold surface, making it inherently dimmer).

**S-pol pass:** Target 85% of detector max, tolerance ±15%, up to 12 iterations, uses per-device model slopes.

**P-pol pass:** Starts from S-pol integration time and S-pol LED values scaled × 0.92 (a practical initial guess). Target 75% of detector max, tolerance ±5%, up to 12 iterations, model slopes disabled (P/S ratios vary too much per channel to use the same slope model). Config enforces `ALLOW_INTEGRATION_INCREASE_ONLY = True`: integration time can only go up from the S-pol starting point, never down. P-pol will typically need to increase integration time because P-pol signals are dimmer than S-pol at the same LED intensity.

---

## 4. Algorithm: How Convergence Works

The engine is an **iterative feedback controller** — measure, compare to target, adjust, repeat.

### 4.1 Initialization

**S-pol target:** 85% of `detector_max_counts` (~55,700 counts for Flame-T), tolerance ±15%, up to 12 iterations  
**P-pol target:** 75% of `detector_max_counts` (~49,150 counts for Flame-T), tolerance ±5%, up to 12 iterations, no model slopes  

*Note: the `ConvergenceRecipe` dataclass has a `target_percent=0.85` and `tolerance_percent=0.05` default, but the calibration orchestrator always overrides these at call time. The 15% S-pol tolerance is intentional: it accepts partial convergence when the weakest channel physically cannot reach the tighter ±5% window.*

**Initial LED calculation** (if `model_slopes_at_10ms` available):
1. Find the **weakest channel** — the channel with the lowest photons-per-LED-unit (lowest slope at 10 ms)
2. Set the weakest channel LED to **255** (maximum) — it needs all the light it can get
3. Scale all other channels relative to the weakest using the slope ratio, then apply a 75% conservative factor:
   ```
   LED[ch] = int( (slope_weakest / slope[ch]) × 255 × 0.75 )
   ```
   The 0.75 safety factor prevents immediately saturating brighter channels while staying close to target.

If no slope model is available (first-time calibration or P-pol), all channels start from the recipe's `initial_leds` defaults.

### 4.2 Iteration Loop

Each iteration:

**Step 1: Measure all channels**

For each channel (A, B, C, D), sequentially:
- Set LED to current value
- Acquire spectrum at current integration time (single scan, `recipe.num_scans = 1`)
- Extract ROI mean signal over `[wave_min_index : wave_max_index]` (560–720 nm)
- Count saturated pixels (pixels ≥ `saturation_threshold`)
- Detect "approaching saturation" (any pixel ≥ 85% of `max_counts`)

**Step 2: Classify channels**

Each channel is classified by `PriorityPolicy`:
- **Urgent** — signal is outside `target ± near_window` (default ±15%) OR any saturation present
- **Near** — signal is within `target ± near_window` — needs fine adjustment only
- **Locked (sticky)** — signal has been within tolerance for one or more consecutive iterations and stays at that LED value

**Step 3: Acceptance check**

`AcceptancePolicy` asks: are ALL channels within `target ± tolerance`, with zero saturated pixels?
- If YES → `converged = True` → return immediately
- Early stopping at iteration ≥ 3: if stable/improving and error < 5%, stop early to prevent oscillation

**Step 4: Calculate LED adjustments**

For each unlocked channel, the engine selects a slope and computes a predicted LED:
```
δ_signal_needed = target_signal - current_signal
δ_LED = δ_signal_needed / slope
new_LED = current_LED + δ_LED
```

Slope source is selected by `SlopeSelectionStrategy`:
- Prefer `estimated` slope (from live `SlopeEstimator` regression) after iteration 1
- Fall back to `model_slope_at_10ms` (from prior calibration history) if estimated not yet reliable
- Fall back to no-slope path (percentage-based saturation reduction) if both unavailable

**Boundary enforcement** prevents the LED from crossing into known-bad territory:
- `max_led_no_sat` — highest LED that did NOT saturate in a prior iteration
- `min_led_above_target` — lowest LED that was above target
- New LED is clamped below `max_led_no_sat` and constrained by `max_led_change = 80`

**Step 5: Handle saturation**

If any channels are saturating (`SaturationPolicy`):
1. Reduce those channels' LED values (percentage-based, severity-proportional: 2%/7%/15% reduction)
2. Evaluate integration time reduction (S-pol only):
   - 1–2 channels saturating heavily → 15–25% integration reduction
   - 3–4 channels saturating → 30% integration reduction
3. If integration time changes, slope history is **scaled** (not cleared) using the physics relationship `signal ∝ t_integration`

**Step 6: Update state and repeat**

After all channels are updated:
- `SlopeEstimator.record(ch, led, signal)` for non-saturated channels
- State is updated in-place
- Locked channels are preserved across iterations

### 4.3 Post-Loop Result

If max iterations reached without convergence, the engine returns the **per-channel best** — the LED settings from the iteration where each individual channel was closest to target (with zero or minor saturation). This means partial convergence can still yield usable calibration for most channels even if one problem channel never fully converged.

---

## 5. Key Engineering Decisions

### 5.1 Weakest Channel as Anchor

The weakest channel (dimmest LED or lowest fiber coupling efficiency) defines the floor. It is always set to LED=255 first, then other channels are scaled down relative to it. This prevents the common failure mode where the weakest channel gets stuck below target while the engine tries to reduce a brighter channel's integration time, making the weak channel even worse.

**Weakest channel protection:** If the weakest channel is locked at LED=255 and the engine would otherwise reduce integration time (dropping the weakest below target), it scales other channels' LEDs using the slope ratio instead — a much safer path.

### 5.2 Sticky Locks

Once a channel converges, its LED value is **locked** and does not change even if integration time changes. This prevents the engine from re-optimizing a good channel and accidentally making it worse while fixing a bad channel.

Lock clearing only happens if the signal drifts more than 10% from target — this catches the case where an integration time change invalidates a previously good lock.

### 5.3 Boundary Tracking

Every non-saturating LED value is remembered as `max_led_no_sat`. Every LED that produced above-target signal is remembered as `min_led_above_target`. Future LED calculations are constrained by these boundaries, preventing the engine from returning to a known-bad operating point across iterations.

### 5.4 P-pol Never Reduces Integration

P-pol spectra are always dimmer than S-pol spectra at the same LED intensity (because P-pol energy is partially coupled into the surface plasmon and absorbed). Therefore, if S-pol was successfully converged at a given integration time, P-pol will never saturate at the same integration time. The `SaturationPolicy` enforces this: for P-pol mode, integration time reduction is disabled entirely.

### 5.5 Slope History Scaling on Integration Change

Rather than clearing all historical measurements when integration time changes, the `SlopeEstimator` scales all recorded `(LED, signal)` pairs by the ratio `new_time / old_time`. This preserves slope knowledge and avoids needing 2+ fresh measurements before slope-based LED prediction becomes available again after an integration change.

### 5.6 Polarizer Blocking Bail-Out

If all channels are below 3% of detector maximum for 3 consecutive iterations, the polarizer is physically blocking light (wrong servo position). The engine aborts immediately with a diagnostic error rather than exhausting all 6 iterations. This is an important diagnostic signal — it means the servo calibration is wrong or the polarizer has been moved physically.

---

## 6. Slope Model (Physics Foundation)

The core physics relationship the engine exploits:

$$\text{signal} = \text{slope}_{10\text{ms}} \times \text{LED} \times \frac{t_{\text{integration}}}{10\text{ ms}}$$

Where `slope_10ms` is the counts-per-LED-unit at 10 ms integration time, measured empirically for each channel during prior calibration sessions.

**How slopes are learned:** During `SlopeEstimator.record()`, the engine stores `(LED, signal)` pairs from non-saturating measurements within the current session. Linear regression over the last 5 pairs gives a live slope estimate. This live estimate replaces the model slope after iteration 1 (it's more accurate because it's from the current session, not a historical average).

**At startup (cold device, no history):** Prior calibration slopes stored in `device_config.json` are loaded and passed as `model_slopes_at_10ms`. These are the empirical per-device characterization data — the accumulated mapping between this specific device's optical properties and its operating point.

---

## 7. Sensitivity Classification

Not all devices respond the same to the same LED/integration settings. Some devices (particularly those with very efficient fiber coupling or high-sensitivity detectors) saturate at integration times that would leave a standard device at only 50% of target.

The `SensitivityClassifier` runs **during iterations 1 and 2** (`if iteration <= 2`) and classifies the device:

| Label | Condition | Action |
|-------|-----------|--------|
| **HIGH** | Multiple channels saturating at ≤20 ms | Cap integration time at 20 ms; maximize LED adjustment instead |
| **BASELINE** | Normal response | No cap — allow full integration time range |

**Classification features:**
- Integration time at which saturation occurred
- Number of saturating channels
- Number of saturated pixels
- Average model slope at 10 ms
- Ratio of actual signal to target signal

HIGH sensitivity detection prevents the cascade failure where the engine keeps reducing integration time to escape saturation, reaches 1 ms, and still saturates — leaving nothing left to adjust.

---

## 8. ML Layer

Two ML models guide the convergence process. The sensitivity detection (Section 7) is a separate rule-based classifier — not an ML model — though a trained `sensitivity_classifier.joblib` exists in the models directory as a future replacement candidate.

### 8.1 LED Intensity Predictor (✅ Active)

**File:** `affilabs/convergence/models/led_predictor.joblib`  
**Algorithm:** Trained regression model (R² = 0.973 on training data)  
**Input:** `[channel_encoding, target_counts, integration_ms, sensitivity_label]` — 4 features  
**Output:** Predicted optimal LED value  
**Use:** Tried on every urgent, unlocked channel on every iteration. The prediction is then **blended 30% ML + 70% physics-slope** to temper the ML influence with the deterministic model. If no slope data is available for a channel, the ML prediction is used directly (ML-ONLY mode). If the ML prediction would overshoot target by >50% based on the slope model, it is replaced with the slope-derived value before blending.  
**Fallback:** If the model fails or is absent, pure slope-based LED calculation runs instead  
**Impact:** Accelerates convergence on all devices; blending preserves algorithmic safety while injecting ML-learned device knowledge

### 8.2 Convergence Success Predictor (✅ Active)

**File:** `affilabs/convergence/models/convergence_predictor.joblib`  
**Algorithm:** Trained classifier (97% accuracy on training data)  
**Status:** Wired in — runs after iteration 1  
**Trigger:** After the first iteration completes, the predictor evaluates whether the target is achievable given current signals, slopes, and device sensitivity  
**Output:** ACHIEVABLE or UNACHIEVABLE  
**Action on UNACHIEVABLE:** Disables ML LED predictions (`use_ml_led_predictor = False`) and ML sensitivity classification for all remaining iterations — switches to algorithm-only mode without discarding iteration 1 measurements  
**Impact:** Prevents the ML layer from compounding errors on devices where the ML model's training data doesn't represent the failure mode; graceful degradation to physics-only convergence

Both models are trained from production calibration logs across all fielded devices. As the install base grows, these models improve.

---

## 9. Convergence Output

### 9.1 ConvergenceResult Dataclass

```python
@dataclass
class ConvergenceResult:
    integration_ms: float        # Final integration time that worked
    final_leds: Dict[str, int]   # {ch: LED value} for each channel
    signals: Dict[str, float]    # {ch: signal counts} at final settings
    converged: bool              # True if all channels hit target ± tolerance
    qc_warnings: List[str]       # Warnings to surface in QC dialog
    best_iteration: int          # Which iteration produced this result
    max_signal_achieved_pct: float  # Actual best signal as % of max_counts
```

### 9.2 Convergence Summary (stored in CalibrationData)

One summary dict is produced per convergence pass (one for S-pol, one for P-pol). The QC dialog reads the S-pol summary by default.

```python
{
    "strategy": "intensity",          # or "time" (per-channel integration mode)
    "shared_integration_ms": 12.5,    # final integration time in ms
    "ok": True,                       # overall pass/fail (converged AND zero saturation)
    "channels": {
        "a": {
            "final_led": 198,                 # Converged LED value for this channel
            "final_integration_ms": 12.5,    # Integration time at convergence
            "final_top50_counts": 55200.0,   # Mean signal in ROI (counts)
            "final_percentage": 84.3,        # Signal as % of detector max_counts
            "iterations": 3,                 # Iterations this channel took to settle
        },
        "b": { ... },
        "c": { ... },
        "d": { ... },
    }
}
```

This dict flows into `CalibrationData` via `affilabs/domain/adapters.py`, is stored in `device_config.json` per device serial, and is rendered in the **Calibration QC Dialog** convergence summary section. The `final_percentage` field drives saturation color-coding: >95% = red (saturated), >85% = green (target range), <85% = orange (low signal).

---

## 10. Failure Modes & Detection

| Failure | Symptom | Diagnostic Signal |
|---------|---------|-------------------|
| **Polarizer blocking** | All channels < 3% max for 3 iterations | Engine aborts with "POLARIZER BLOCKING DETECTED" — wrong servo position or servo fault |
| **Weak channel never reaches target** | One channel saturated at LED=255, others OK | Fiber coupling problem or LED failure on that channel |
| **All channels fail to rise** | Dim signals, many iterations, no convergence | Integration time at max (60 ms), LEDs at 255 — detector sensitivity problem or fiber disconnected |
| **Oscillation (signal bounces up/down per iteration)** | `GETTING WORSE` trend alternating with `IMPROVING` | Anti-oscillation guard (recent integration history checked) — usually corrects itself |
| **HIGH sensitivity trap** | Saturation persists even with LED=10 | Sensitivity classifier fires, caps integration at 20 ms, maximizes LED reduction |
| **Convergence succeeded but signals drift afterward** | Post-convergence drift in sensorgram baseline | Thermal effects — typically stabilizes within 5 minutes; consider temperature control (potential improvement) |

Failed convergence (`converged = False`) does not prevent the system from continuing — it stores the best-effort result and marks QC warnings. The calibration QC dialog surfaces these warnings to the user.

---

## 11. Device Health & Aging

Convergence parameters are the most sensitive indicator of device health available without additional hardware. Because convergence must hit a fixed target (85% of detector max) every session, the LED values required to reach that target directly reveal how much the optical path has changed since the device was first characterized.

### What the convergence result tells you

| Parameter | What it means |
|-----------|--------------|
| **integration_ms increasing** | The optical path is dimming overall — LEDs aging, fiber degradation, or detector sensitivity loss |
| **LED values for one channel creeping up** | That specific channel's LED is dimming, or fiber coupling has degraded |
| **LED values for one channel near 255, others well below** | Fiber alignment problem on that channel — physical inspection needed |
| **Convergence iteration count increasing over time** | The device's optical response is becoming less predictable — possible internal contamination or component aging |
| **Device suddenly fails convergence that previously succeeded** | Acute change — fiber disconnected, LED burned out, or detector USB fault |

### Slope history as a health record

The per-device `model_slopes_at_10ms` values (stored in `device_config.json`) are the empirical characterization of "how this device converts LED power to signal". When re-calibrated, the new slopes are compared to the stored slopes. If a channel's slope has dropped by >20% since last calibration, that is evidence of LED or optical path degradation.

This data exists. The **missing piece is the longitudinal analysis tool** — a view that graphs convergence parameters over the device's lifetime. This is the planned device health dashboard.

---

## 12. Troubleshooting Relevance

Convergence failure is the first diagnostic checkpoint for most hardware problems. The pattern of failure — which channels fail, in what direction, and at what iteration — immediately narrows the fault class.

### Diagnostic matrix

| Observation | Likely cause |
|-------------|-------------|
| Channel A fails, others pass | Fiber branch A problem or LED A failure |
| All channels fail (dim) | Integration time limit hit — check fiber trunk, detector connection |
| All channels fail (saturated) | Detector sensitivity higher than expected — check detector profile, or Phase Photonics detector connected instead of Flame-T |
| Convergence passes but S-pol flatness fails QC | Servo position problem — S-pol is hitting SPR coupling accidentally |
| `POLARIZER BLOCKING` error | Servo positions wrong or servo mechanically failed |
| Convergence took 6 iterations | Device is unusual — slopes are poor or fiber coupling is degraded |
| LED=255 on all channels | Very dim optical path — fiber contamination, LED failure, or prism coupling problem |

### Calibration QC Dialog

All convergence data is rendered in the Calibration QC Dialog:
- Per-channel LED values (S-pol and P-pol)
- Iteration counts (green if ≤ 3, red if > 3)
- Convergence pass/fail per channel
- Integration time
- Any QC warnings from the convergence engine

---

## 13. Component Map

```
affilabs/convergence/
  engine.py            ← ConvergenceEngine — the main algorithm
  config.py            ← ConvergenceRecipe, DetectorParams
  interfaces.py        ← Protocol definitions (Spectrometer, LEDActuator, ROIExtractor)
  estimators.py        ← SlopeEstimator — live slope regression from measurements
  policies.py          ← AcceptancePolicy, PriorityPolicy, BoundaryPolicy,
                           SlopeSelectionStrategy, SaturationPolicy
  sensitivity.py       ← SensitivityClassifier — HIGH vs BASELINE detector classification
  adapters.py          ← Production adapter implementations
  production_adapters.py  ← create_production_adapters() — wires real hardware into engine interfaces
  production_bridge.py ← Recipe/params conversion from production config format
  production_wrapper.py   ← LEDconverge_engine() — drop-in replacement for legacy LEDconverge()
  models/
    sensitivity_classifier.joblib   ← sklearn model for HIGH/BASELINE classification
    led_predictor.joblib            ← sklearn model for LED intensity prediction
    convergence_predictor.joblib    ← sklearn model — runs after iteration 1; disables ML if target unachievable

affilabs/utils/
  led_convergence_core.py          ← ConvergenceConfig, DetectorParams (production types)
  led_convergence_algorithm.py     ← Legacy LEDconverge() — still used as fallback

affilabs/widgets/
  calibration_qc_dialog.py         ← Renders convergence_summary in QC dialog
```

---

## 14. Configuration Reference

### ConvergenceRecipe class defaults

These are the dataclass field defaults. The calibration orchestrator **always overrides** `target_percent`, `tolerance_percent`, and `max_iterations` at call time (see Production Overrides below).

| Parameter | Default | Notes |
|-----------|---------|-------|
| `target_percent` | 0.85 | 85% of detector max (overridden in production) |
| `tolerance_percent` | 0.05 | ±5% acceptance window (overridden in production) |
| `near_window_percent` | 0.15 | ±15% for "near target" classification |
| `max_iterations` | 6 | Overridden in production |
| `max_led_change` | 80 | Max LED step per iteration |
| `led_small_step` | 8 | Fine adjustment step |
| `boundary_margin` | 3 | Safety margin from known-bad LED values (LED units) |
| `prefer_est_after_iters` | 1 | Use live slope estimate after 1 iteration |
| `min_signal_for_model` | 0.10 | 10% of target minimum signal to trust slope |
| `accept_above_extra_percent` | 0.03 | Allow 3% overshoot to reduce iterations |
| `use_batch_command` | True | Use batch LED command (`lbp255...`) |

### Production Orchestrator Overrides

Values passed by `calibration_orchestrator.py` at runtime — these are what actually runs:

| Parameter | S-pol | P-pol | Notes |
|-----------|-------|-------|---------|
| `target_percent` | 0.85 | 0.75 | P-pol signal is inherently dimmer |
| `tolerance_percent` | 0.15 | 0.05 | S-pol wide tolerance accepts weak-channel partial convergence |
| `max_iterations` | 12 | 12 | Both use 12; P-pol may need more time without model slopes |
| `model_slopes` | from device_config | `None` | P/S slope ratios vary too much per channel to reuse S-pol slopes |
| `initial_integration_ms` | from prior calibration or default | S-pol result (start point) | P-pol inherits S-pol integration time |
| `initial_leds` | from device_config or defaults | S-pol LEDs × 0.92 | P-pol starts at 92% of S-pol values |
| `polarization` | `"S"` | `"P"` | Controls saturation policy (P-pol: integration can only increase) |
| `ALLOW_INTEGRATION_INCREASE_ONLY` | not set | `True` | P-pol config attribute preventing integration decrease |

### DetectorParams (per detector model)

| Detector | `max_counts` | `saturation_threshold` | `min_integration_ms` | `max_integration_ms` |
|----------|-------------|----------------------|---------------------|---------------------|
| Ocean Optics Flame-T | 65,535 | 65,535 | 1.0 | 60.0 |
| Ocean Optics USB4000 | 65,535 | 65,535 | 1.0 | 60.0 |
| Phase Photonics | 4,095 | 4,095 | 1.0 | 20.0 |

Phase Photonics is automatically treated as HIGH sensitivity (12-bit ADC saturates far more easily than 16-bit).
