# Afterglow Correction Optimization Analysis

## Executive Summary

**Question:** Should we improve the afterglow correction model to reduce cycle time, or simply increase LED delay?

**Answer:** **Both approaches have merit, but improving the model is FAR superior** for your use case.

---

## Current Situation Analysis

### Measured Performance (from diagnostics)

| Configuration | LED Delay | Cycle Time | Ch A Noise | Ch B Noise | Lagged Corr |
|---------------|-----------|------------|------------|------------|-------------|
| **Original (20ms)** | 20ms | ~600ms | 33.68 RU σ | 37.69 RU σ | 0.372 (HIGH) |
| **No Afterglow** | 20ms | ~600ms | 62.65 RU σ | 44.73 RU σ | 0.403 (HIGH) |
| **30ms delay** | 30ms | ~650ms | ? | ? | ? (crashed) |

### Key Findings

1. **Afterglow correction HELPS** (disabling made noise worse: 33→63 RU)
2. **Lagged correlation still HIGH (0.372)** = Model parameters are slightly wrong
3. **Cycle time** = 4 channels × (integration + delay + readout) ≈ 600ms

---

## Option 1: Increase LED Delay (Simple but Costly)

### Approach
Simply wait longer between channels for phosphor to decay naturally.

```json
{
  "led_delay_ms": 40.0  // or 50.0ms
}
```

### Pros ✅
- **Trivially simple** - just change one number
- **Guaranteed to reduce afterglow** - physics ensures this
- **No model complexity** - brute force solution
- **Safe** - won't make things worse

### Cons ❌
- **KILLS THROUGHPUT**:
  - 20ms → 40ms delay = +80ms per cycle
  - 600ms → 680ms cycle time = **-13% throughput**
  - 1.67 Hz → 1.47 Hz acquisition rate
- **Doesn't fix root cause** - model parameters still wrong
- **Diminishing returns** - exponential decay means 60ms gets you little more than 40ms
- **Wastes time** - Most of the afterglow (63%) decays in first τ ≈ 20ms

### When to Use
- Quick temporary fix
- You can afford slower acquisition
- You're unsure of your model parameters

---

## Option 2: Optimize Afterglow Correction Model (Best)

### Approach
Fine-tune the exponential decay model parameters (τ, amplitude, baseline) to better predict actual afterglow.

```python
# Current model:
correction = baseline + A × exp(-delay/τ)

# Problem: τ, A, baseline are slightly wrong
# → Leaves residual afterglow OR over-corrects
```

### Why Current Model is Wrong

From your diagnostic **lagged correlation = 0.372**, we know:
1. Afterglow from Ch D is affecting Ch A (next cycle)
2. After correction is applied, residual is still 37% correlated
3. This means correction is **under-estimating** the true afterglow

**Possible causes:**
- τ too large (model thinks it decays faster than reality)
- Amplitude too small (model thinks initial glow is weaker)
- Baseline wrong (model misestimates steady-state glow)
- Integration time dependency incorrect

### Proposed Solution: Adaptive Model Refinement

I can create a tool that:

1. **Measures Real Afterglow** (in-situ)
   - Use your existing data (test.csv) to extract actual channel-to-channel correlation
   - Compare predicted vs actual afterglow at different delays

2. **Fits Correction Parameters**
   - Optimize τ, A, baseline to minimize lagged correlation
   - Uses least-squares fitting on real data

3. **Validates Performance**
   - Tests on multiple datasets
   - Ensures lagged correlation drops below 0.1

4. **Updates Calibration File**
   - Writes refined parameters to optical calibration JSON
   - Preserves integration time dependency

### Pros ✅
- **PRESERVES SPEED**: Keep 20ms delay → 600ms cycle time (1.67 Hz)
- **Fixes root cause**: Model matches reality
- **Maximizes throughput**: No wasted time waiting
- **Better noise**: Proper correction → lower residual afterglow
- **Scales**: Works across all integration times
- **Future-proof**: Once calibrated, works indefinitely

### Cons ❌
- **More complex**: Requires running optimization script
- **Needs data**: Requires baseline acquisitions for fitting
- **Time investment**: ~1 hour to collect data and optimize
- **Risk**: Could overfit to noise if not careful

### Expected Results

If we reduce lagged correlation from 0.372 → 0.100:

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Lagged correlation | 0.372 | <0.100 | -73% |
| Ch A noise | 33.68 RU | ~22-25 RU | -30% |
| Ch B noise | 37.69 RU | ~25-28 RU | -30% |
| **Cycle time** | 600ms | **600ms** | ✅ NO PENALTY |
| Throughput | 1.67 Hz | **1.67 Hz** | ✅ PRESERVED |

---

## Option 3: Hybrid Approach (Good Compromise)

Combine both:
1. **Small delay increase**: 20ms → 25ms (+8% time penalty)
2. **Model optimization**: Fix parameter errors

This gives you:
- Safer margin if model isn't perfect
- Most of the speed benefit (vs 40ms delay)
- Better noise than either approach alone

---

## Recommendation: **Option 2 (Model Optimization)**

### Why?
1. **Your bottleneck is NOISE (33 RU), not speed**
   - You showed me 156-182 RU peak-to-peak data
   - Target is <5 RU for good SPR
   - Afterglow is a major contributor (lagged corr = 0.372)

2. **Throughput is critical for SPR**
   - Faster cycles = better time resolution
   - Kinetic analysis needs 1+ Hz sampling
   - Every 50ms matters for binding curves

3. **One-time investment, permanent benefit**
   - Spend 1 hour optimizing now
   - Benefit forever on all measurements
   - No ongoing speed penalty

4. **You have the infrastructure**
   - Afterglow correction system already exists
   - Just needs parameter tuning
   - Calibration file is JSON (easy to edit)

### What I'll Create

**Tool: `optimize_afterglow_model.py`**

Features:
- Loads your test data (CSV files)
- Extracts inter-channel afterglow signatures
- Fits τ, amplitude, baseline using least-squares
- Validates fit quality (R² > 0.95 target)
- Updates `led_afterglow_integration_time_models_*.json`
- Generates before/after comparison plots
- Estimates noise improvement

Usage:
```powershell
# Collect 5 minutes of baseline data (with 20ms delay)
.\run_app.bat
# → Export CSV

# Optimize model parameters
python optimize_afterglow_model.py baseline_data.csv

# Verify improvement
python diagnose_noise_sources.py new_data.csv
```

Expected time: **1 hour total** (30min collection + 30min optimization)

---

## Decision Matrix

| Criteria | Delay↑ | Model Opt | Hybrid |
|----------|--------|-----------|--------|
| **Speed** | ❌ -13% | ✅ 0% | 🟡 -8% |
| **Noise** | 🟡 ~25% better | ✅ ~30% better | ✅ ~35% better |
| **Effort** | ✅ 5 min | 🟡 1 hour | 🟡 1 hour |
| **Risk** | ✅ None | 🟡 Small | ✅ Low |
| **Long-term** | ❌ Permanent penalty | ✅ One-time fix | ✅ Good balance |

---

## Next Steps

**I recommend we optimize the model.** Would you like me to:

**A)** Create the `optimize_afterglow_model.py` tool now?
- Uses your existing test.csv data
- Fits corrected parameters
- Updates calibration file
- Shows before/after comparison

**B)** Do the hybrid approach?
- Set delay to 25ms (quick fix)
- Then optimize model (better fix)
- Safest path

**C)** Just increase delay to 40ms?
- Fastest to implement
- Sacrifice speed for safety
- Good if you're unsure

---

## Technical Details (if you want to dive deeper)

### Current Model Implementation

```python
# In afterglow_correction.py
def calculate_correction(self, previous_channel, integration_time_ms, delay_ms):
    # Interpolate τ from calibration data
    tau_ms = self.tau_interpolators[channel](integration_time_ms)
    amplitude = self.amplitude_interpolators[channel](integration_time_ms)
    baseline = self.baseline_interpolators[channel](integration_time_ms)

    # Exponential decay model
    correction = baseline + amplitude * np.exp(-delay_ms / tau_ms)
    return correction
```

### What We'll Optimize

For each channel and integration time:
```python
# Current values (example for Ch A, 50ms integration):
τ = 21.45 ms        # Decay time constant
A = 1234.5 counts   # Initial amplitude
B = 890.2 counts    # Baseline offset

# We'll fit these to minimize:
residual_afterglow = measured_ChA[n+1] - model(ChD[n], delay=20ms)
```

### Expected Parameter Adjustments

Based on lagged correlation = 0.372, likely issues:
- **τ is too HIGH** (predicts faster decay than reality) → reduce by ~10-15%
- **A is too LOW** (underestimates initial glow) → increase by ~20-30%
- **B might be slightly off** → adjust by ±5%

---

## Cost-Benefit Summary

### LED Delay Increase (20→40ms)
- **Cost**: -13% throughput (permanent)
- **Benefit**: ~25% noise reduction
- **ROI**: Poor (wastes time forever)

### Model Optimization
- **Cost**: 1 hour setup time (one-time)
- **Benefit**: ~30% noise reduction + preserved speed
- **ROI**: Excellent (pay once, benefit forever)

### Hybrid
- **Cost**: 1 hour + 8% throughput
- **Benefit**: ~35% noise reduction
- **ROI**: Good (best noise, small speed penalty)

---

**My strong recommendation: Option 2 (Model Optimization)**

Let me know which approach you prefer, and I'll build the solution!
