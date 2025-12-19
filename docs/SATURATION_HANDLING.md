# Saturation Handling Improvements

**Date:** December 18, 2025
**Status:** Implemented

## Problem Statement

The convergence engine was struggling with widespread pixel saturation:
- Device FLMT09788 saturated all 4 channels even at minimum integration (5.0ms)
- Engine ran 15 iterations without converging, all with saturation present
- Final signals were 95-99% of target (too high) despite 5764+ saturated pixels
- Slope-based LED adjustments unreliable when signals are saturated

## Root Causes

1. **Insufficient LED reduction**: Engine was using slope calculations even for saturated channels
2. **Weak saturation policy**: Only reduced integration by 10-30%, not aggressive enough
3. **No saturation boundaries**: Didn't track which LED values caused saturation
4. **Poor initial values**: Started with high LEDs even when slopes predicted saturation risk
5. **Contaminated slope estimates**: Recording slopes from saturated measurements

## Implemented Solutions

### 1. Aggressive LED Reduction for Saturated Channels

**Location:** [engine.py](../affilabs/convergence/engine.py) lines ~437-470

When a channel is saturating, **bypass** slope calculations and ML predictors entirely:

```python
if sat > 0:
    # Severity-based reduction
    if sat > 100:      reduction_factor = 0.40  # Cut to 40%
    elif sat > 50:     reduction_factor = 0.50  # Cut to 50%
    elif sat > 20:     reduction_factor = 0.65  # Cut to 65%
    else:              reduction_factor = 0.75  # Cut to 75%

    new_led = int(current_led * reduction_factor)
```

**Benefits:**
- Breaks out of saturation spirals faster (50-60% cuts vs 10-20%)
- Doesn't trust unreliable slope data from saturated pixels
- Records LED value as saturation boundary for future reference

### 2. Enhanced Saturation Policy

**Location:** [policies.py](../affilabs/convergence/policies.py) lines 116-148

Graduated integration time reduction based on saturation severity:

| Severity | Condition | Reduction Factor | Time Cut |
|----------|-----------|------------------|----------|
| Very Severe | >100 saturated pixels | 0.50 | 50% |
| Severe | >50 saturated pixels | 0.60 | 40% |
| Moderate | >20 saturated pixels | 0.75 | 25% |
| Multiple Channels | ≥3 channels saturating | 0.70 | 30% |
| Mild | <20 saturated pixels | 0.85 | 15% |

**Old behavior:** 0.70 (>50px) or 0.90 (else) - too conservative
**New behavior:** 0.50-0.85 based on severity - more aggressive

### 3. Saturation Boundary Tracking

**Location:** [engine.py](../affilabs/convergence/engine.py) lines ~466, ~547

Now records LED values that caused saturation:

```python
# When saturation detected
if sat > 0:
    b = state.get_bounds(ch)
    if b.max_led_no_sat is None or current_led < b.max_led_no_sat:
        b.max_led_no_sat = current_led  # Don't go higher than this
```

**Benefits:**
- Prevents returning to known-bad LED values
- Helps boundary enforcement during LED adjustments
- Works with existing `max_led_no_sat` boundary system

### 4. Clean Slope Estimates

**Location:** [engine.py](../affilabs/convergence/engine.py) lines ~540-554

Only record slope data from **non-saturated** measurements:

```python
# Only record slopes from non-saturated, reliable measurements
if sat == 0:
    state.slope_est.record(ch, state.leds[ch], sig)

# Record saturation boundary if this channel saturated
if sat > 0:
    b = state.get_bounds(ch)
    # ... update boundary
```

**Benefits:**
- Slope estimates remain accurate and trustworthy
- No contamination from clipped/saturated signals
- Better predictions for non-saturated adjustments

### 5. Conservative Initial LEDs

**Location:** [engine.py](../affilabs/convergence/engine.py) lines ~193-216

Calculate smarter starting LED values based on model slopes:

```python
if model_slopes_at_10ms and ch in model_slopes_at_10ms:
    slope_at_initial = model_slopes_at_10ms[ch] * (recipe.initial_integration_ms / 10.0)
    predicted_led = target_signal / slope_at_initial
    conservative_led = int(predicted_led * 0.60)  # 60% safety factor
```

**Benefits:**
- Avoids immediate saturation on first measurement
- Uses device-specific calibration data when available
- Falls back to recipe default if no slopes available
- 60% safety factor accounts for slope uncertainty

## Expected Behavior Changes

### Before Improvements
```
Iteration 1: LED=223, Signal=60432 (108%), SAT=1432px
Iteration 2: LED=211, Signal=58940 (106%), SAT=1289px  # Slow reduction
Iteration 3: LED=198, Signal=57103 (102%), SAT=1147px
...
Iteration 15: LED=148, Signal=55315 (99.3%), SAT=892px  # Still saturating!
```

### After Improvements
```
Iteration 1: LED=134, Signal=48203 (86.5%), SAT=0px     # Conservative start
Iteration 2: LED=138, Signal=49821 (89.4%), SAT=0px     # Quick convergence
✅ CONVERGED at iteration 2!
```

Or if saturation still occurs:
```
Iteration 1: LED=180, Signal=62318 (112%), SAT=1823px
🔴 A SATURATED (1823px): LED 180→90 (50% cut)           # Aggressive!
Iteration 2: LED=90, Signal=31250 (56%), SAT=0px
Iteration 3: LED=153, Signal=53125 (95%), SAT=0px       # Approaching target
...
```

## Testing Checklist

- [ ] Test with HIGH sensitivity device (FLMT09788)
- [ ] Verify saturation resolves within 3-5 iterations
- [ ] Check that slope estimates remain stable (no contamination)
- [ ] Confirm boundary tracking prevents LED oscillation
- [ ] Test with BASELINE sensitivity device to ensure no regression
- [ ] Verify conservative initial LEDs prevent first-iteration saturation

## Configuration Parameters

Can be tuned if needed:

| Parameter | Location | Default | Purpose |
|-----------|----------|---------|---------|
| `reduction_factor` | engine.py:452-455 | 0.40-0.75 | LED cut when saturating |
| `integration_factor` | policies.py:138-145 | 0.50-0.85 | Integration reduction |
| `conservative_factor` | engine.py:206 | 0.60 | Initial LED safety margin |
| `saturation_threshold` | params | 64500 | Pixel value = saturated |

## Related Files

- [engine.py](../affilabs/convergence/engine.py) - Main convergence loop
- [policies.py](../affilabs/convergence/policies.py) - SaturationPolicy class
- [estimators.py](../affilabs/convergence/estimators.py) - SlopeEstimator class
- [state.py](../affilabs/convergence/state.py) - Boundary tracking

## Future Enhancements

1. **Saturation prediction ML**: Train model to predict if given LED/integration will saturate
2. **Adaptive thresholds**: Adjust reduction factors based on device history
3. **Per-channel strategies**: Different channels may need different aggressiveness
4. **Saturation recovery**: Special handling when coming out of saturation
