# Afterglow Correction Architecture: Flexible Channel Sequencing

## Executive Summary

The optical calibration system measures **each LED's afterglow independently**, enabling correction for **any channel sequence** - not just sequential 4-channel patterns. This architectural decision provides critical flexibility for future assay designs.

---

## The Problem: LED Phosphor Afterglow

When an LED turns off, its phosphor continues to emit light (afterglow/phosphorescence):

```
LED ON:  ████████████ (steady signal)
LED OFF:          ▄▃▂▁  (exponential decay)
                  ↑
                  This residual signal contaminates the next measurement
```

**Physics**: `afterglow(t) = amplitude × e^(-t/τ) + baseline`
- τ (tau): decay time constant (~15-25ms for typical LEDs)
- amplitude: initial afterglow intensity (depends on LED drive level)
- baseline: steady-state dark level

---

## The Solution: Independent Characterization

### What Gets Calibrated

For EACH of the 4 LEDs (A, B, C, D):
- Measure afterglow decay at multiple integration times
- Fit exponential decay model
- Store τ(integration_time), amplitude, baseline

**Result**: Complete afterglow profile for each LED, stored independently.

### Data Structure

```json
{
  "channel_data": {
    "a": {
      "integration_time_data": [
        {"integration_time_ms": 10, "tau_ms": 18.2, "amplitude": 1234, "baseline": 890},
        {"integration_time_ms": 25, "tau_ms": 19.5, "amplitude": 2341, "baseline": 905},
        ...
      ]
    },
    "b": { /* independent calibration */ },
    "c": { /* independent calibration */ },
    "d": { /* independent calibration */ }
  }
}
```

**Key Point**: Each channel's data is INDEPENDENT. No coupling between channels in the calibration.

---

## Architectural Advantage: Any Channel Sequence

### Current Application: 4-Channel Sequential

```
Measure A → B → C → D (repeat)

Corrections applied:
  B_corrected = B_measured - afterglow_from_A
  C_corrected = C_measured - afterglow_from_B
  D_corrected = D_measured - afterglow_from_C
  A_corrected = A_measured - afterglow_from_D  (next cycle)
```

### Future Application: 2-Channel Non-Adjacent

**Scenario 1**: Use channels A and C only
```
Measure A → C → A → C (repeat)

Corrections applied:
  C_corrected = C_measured - afterglow_from_A
  A_corrected = A_measured - afterglow_from_C  (next cycle)
```

**Scenario 2**: Use channels B and D only
```
Measure B → D → B → D (repeat)

Corrections applied:
  D_corrected = D_measured - afterglow_from_B
  B_corrected = B_measured - afterglow_from_D  (next cycle)
```

### Custom Application: Any Arbitrary Sequence

```
Measure D → A → B (some assay-specific pattern)

Corrections applied:
  A_corrected = A_measured - afterglow_from_D
  B_corrected = B_measured - afterglow_from_A
```

**The system doesn't care about the sequence** - it just looks up:
> "What was the previous channel? Look up THAT channel's afterglow characteristics and apply correction."

---

## Implementation: How It Works in Code

### In `afterglow_correction.py`:

```python
def apply_correction(
    measured_signal,
    previous_channel,  # ← Can be ANY channel (a, b, c, or d)
    integration_time_ms,
    delay_ms
):
    # Look up the specific channel's afterglow
    tau = tau_interpolators[previous_channel](integration_time_ms)
    amplitude = amplitude_tables[previous_channel](integration_time_ms)
    baseline = baseline_tables[previous_channel](integration_time_ms)

    # Calculate correction using that channel's parameters
    correction = amplitude * exp(-delay_ms / tau) + baseline

    return measured_signal - correction
```

### In `data_acquisition_manager.py`:

```python
# Track whatever channel was measured last
self._previous_channel = None

# During measurement loop
for channel in active_channels:  # Could be ['a', 'c'] or ['b', 'd'] or any combo
    raw_signal = measure(channel)

    if self._previous_channel is not None:
        corrected = afterglow_correction.apply_correction(
            raw_signal,
            previous_channel=self._previous_channel,  # ← Automatically uses correct LED
            integration_time_ms=current_integration_time,
            delay_ms=led_switch_delay
        )

    self._previous_channel = channel  # Update for next iteration
```

---

## Why Calibrate All 4 Channels?

Even if your current assay only uses 2 channels, you need all 4 calibrated because:

### 1. Assay Flexibility
Different assays may use different channel combinations:
- Assay A: channels A+B
- Assay B: channels B+D
- Assay C: channels A+C+D (3-channel)
- Assay D: all 4 channels

### 2. Future-Proofing
New assay development may require:
- Testing different wavelength combinations
- Multi-analyte detection with non-sequential channels
- Custom sequences optimized for specific biomolecules

### 3. System Validation
Full characterization enables:
- Complete optical system health monitoring
- LED aging detection across all channels
- Maintenance decision support

### 4. No Penalty for Completeness
- Calibration takes ~10 minutes for all 4 channels
- Storage: ~10KB per device
- Runtime overhead: negligible (simple lookup + exponential)

**Decision**: Always calibrate all 4 channels, even if only using subset.

---

## Comparison with Alternative Approaches

### Alternative 1: Sequential Dependency (REJECTED)

```
Only store "afterglow from channel N affects channel N+1"
```

**Problems:**
- ❌ Locked into sequential pattern
- ❌ Can't use non-adjacent channels (e.g., A→C)
- ❌ Requires recalibration if channel order changes
- ❌ Can't skip channels

### Alternative 2: Pairwise Calibration (REJECTED)

```
Calibrate specific pairs: A→B, B→C, A→C, B→D, etc.
```

**Problems:**
- ❌ Exponential combinations (16 pairs for 4 channels)
- ❌ Huge calibration time (40+ minutes)
- ❌ Complex data structure
- ❌ Still missing some combinations

### Selected Approach: Independent Characterization ✅

```
Calibrate each LED's afterglow independently
```

**Advantages:**
- ✅ Works for ANY channel sequence
- ✅ Fixed calibration time (~10 minutes)
- ✅ Simple data structure
- ✅ Easy to understand and validate
- ✅ Future-proof

---

## Real-World Scenario: 2-Channel Assay

### Customer Request
> "We only need wavelengths from channels A and C for our antibody assay. Can we just measure those two and skip B and D?"

### With Independent Calibration (Current Architecture)
**Answer**: "Yes! No problem."

```python
# Configure measurement sequence
active_channels = ['a', 'c']  # ← Just change this

# System automatically:
# 1. Measures A
# 2. Measures C
# 3. Applies A's afterglow correction to C
# 4. Repeat

# No recalibration needed
# No code changes needed
# Just works
```

### Without Independent Calibration (Alternative Design)
**Answer**: "Sorry, the system is designed for sequential A→B→C→D. We'd need to recalibrate for A→C specifically."

```python
# Would need:
# 1. New calibration procedure for A→C pattern
# 2. Different correction algorithm
# 3. Store separate calibration file
# 4. Possibly different LED delays
# 5. Validation and testing
#
# Estimated time: 2-3 days of engineering work
```

---

## Impact on System Flexibility

### Without This Architecture
- **Rigid**: Only supports predefined channel sequences
- **Limited**: New assays require engineering effort
- **Fragile**: System breaks if channel order changes
- **Slow**: Each new pattern needs recalibration

### With This Architecture
- **Flexible**: Any channel sequence just works
- **Fast**: Customer can change patterns instantly
- **Robust**: System adapts automatically
- **Scalable**: Easy to add new assay types

---

## Technical Notes

### Integration Time Dependency

Afterglow characteristics change with integration time (longer exposure accumulates more phosphor energy):

```
τ = f(integration_time)
amplitude = g(integration_time)
```

The calibration measures at multiple integration times (e.g., [10, 25, 40, 55, 70, 85] ms) and uses **cubic spline interpolation** to estimate values at arbitrary integration times.

### Correction Accuracy

Expected improvement with afterglow correction:
- **Measurement noise reduction**: 10-20%
- **Baseline stability**: 15-30% better
- **Critical for**: Low-signal applications, kinetics, drift detection

### Computational Cost

Per correction:
- Interpolation lookup: ~100 ns
- Exponential calculation: ~50 ns
- Array subtraction: ~1 μs (for 3648-pixel spectrum)

**Total**: Negligible (<0.1% of measurement time)

---

## Summary

| Aspect | Design Decision |
|--------|----------------|
| **What we calibrate** | Each LED independently |
| **What we store** | τ, amplitude, baseline for each LED × integration time |
| **What we enable** | Any channel sequence |
| **Cost** | ~10 minutes calibration, negligible runtime |
| **Benefit** | Complete assay flexibility |

**Key Insight**: By investing slightly more effort in calibration (measure all 4 LEDs completely), we gain enormous flexibility in how the system is used. This enables customer-driven assay customization without engineering intervention.

---

**Related Documents:**
- `afterglow_correction.py` - Implementation
- `utils/afterglow_calibration.py` - Measurement procedure
- `OEM_OPTICAL_CALIBRATION_GUIDE.md` - Factory procedures
- `AFTERGLOW_CHANNEL_D_MISSING_FIX.md` - Current issue resolution

**Date**: 2025-11-23
**Architecture Decision Record**: This documents a key architectural choice that enables future product flexibility.
