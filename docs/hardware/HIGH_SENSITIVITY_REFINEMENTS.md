# HIGH Sensitivity Device Refinements

**Device:** FLMT09788 (Flame-T spectrometer)
**Date:** December 18, 2025
**Status:** Proposed Improvements

## Observed Behavior

### Current Performance
- **Initial**: 5ms integration, LED ~78-89
- **Iteration 2**: Saturates immediately (416px) at LED 128-134, 5ms
- **Aggressive cut**: Drops to LED 51-53 (40% cut)
- **Over-correction**: LEDs spiral down to minimum (10)
- **Recovery attempt**: Integration increases 5ms → 10ms → 20ms
- **Re-saturation**: At 20ms, LED 31-34 saturates again
- **Oscillation**: Integration drops back to 10ms
- **Failure**: Ends at 50% of target, doesn't converge

### Root Causes
1. **Initial integration too high**: 5ms is already near saturation threshold
2. **Aggressive saturation cuts**: 40-60% cuts push LEDs too low
3. **Large slope-based jumps**: After clearing saturation, LED jumps are too large
4. **No hysteresis**: Engine doesn't remember it just cleared saturation
5. **Binary thinking**: Either saturating OR too low - no middle ground

## Proposed Improvements

### 1. Lower Initial Integration Time

**Change:** Start HIGH sensitivity devices at 2-3ms instead of 5ms

```python
# After HIGH sensitivity detection (iteration 2)
if high_sensitivity_detected and state.integration_ms > 3.0:
    state.integration_ms = 3.0
    state.clear_for_integration_change()
    self._log("info", f"  → Reduced integration to 3.0ms for HIGH sensitivity")
    continue
```

**Benefit:** Avoids immediate saturation, gives more LED headroom

### 2. Gentler Post-Saturation Adjustments

**Change:** After aggressive cuts clear saturation, use small incremental steps (10-15%) instead of slope-based jumps

```python
# Track if we recently had saturation
recent_saturation = (iteration > 2 and high_sensitivity_detected and
                     any(state.was_saturated_recently(ch)))

# For channels recovering from saturation at low LEDs
if recent_saturation and current_led <= 15:
    if sig < target_signal * 0.5:      new_led = int(current_led * 1.15)  # +15%
    elif sig < target_signal * 0.7:    new_led = int(current_led * 1.10)  # +10%
    else:                              new_led = int(current_led * 1.05)  # +5%
```

**Benefit:** Prevents over-shooting back into saturation

### 3. Adaptive Saturation Cuts

**Current:** Fixed 40-75% cuts based on pixel count
**Problem:** Too aggressive for devices that need delicate LED control

**Proposed:** Scale cuts based on **how close** the signal is to target

```python
if sat > 0:
    # How far over target are we?
    overshoot_ratio = sig / target_signal

    if overshoot_ratio > 1.5:       # Way over
        reduction = 0.40
    elif overshoot_ratio > 1.2:     # Moderately over
        reduction = 0.55
    elif overshoot_ratio > 1.0:     # Slightly over
        reduction = 0.70
    else:                           # Below target but saturating
        reduction = 0.80

    new_led = int(current_led * reduction)
```

**Benefit:** Cuts just enough to clear saturation without going too low

### 4. Integration Time as Primary Control

**Change:** For HIGH sensitivity below 50% of target with LEDs < 20, prefer increasing integration over increasing LEDs

```python
# Detect if we're stuck at low LEDs
all_leds_low = all(state.leds[ch] < 20 for ch in recipe.channels)
all_signals_low = all(signals[ch] < target_signal * 0.5 for ch in recipe.channels)

if high_sensitivity_detected and all_leds_low and all_signals_low:
    # Use integration time as primary control variable
    new_time = min(state.integration_ms * 1.5, 20.0)
    if new_time > state.integration_ms:
        self._log("info", f"  📈 HIGH-SENS: Increasing integration {state.integration_ms:.1f}ms → {new_time:.1f}ms")
        state.integration_ms = new_time
        state.clear_for_integration_change()
        continue
```

**Benefit:** Uses the right control variable for the situation

### 5. Saturation Memory/Hysteresis

**Add state tracking:**

```python
# In EngineState class
class EngineState:
    def __init__(self, ...):
        self.saturation_history: Dict[str, List[int]] = {}  # Last 5 iterations

    def was_saturated_recently(self, channel: str, lookback: int = 3) -> bool:
        """Check if channel had saturation in last N iterations"""
        hist = self.saturation_history.get(channel, [])
        return len(hist) >= lookback and any(s > 0 for s in hist[-lookback:])
```

**Benefit:** Engine remembers context and adjusts behavior accordingly

### 6. Smaller Integration Steps for HIGH Sensitivity

**Change:** Limit integration time increases to 1.4x (40%) per step instead of 2x

```python
if high_sensitivity_detected:
    needed_scale = min(needed_scale, 1.4)  # Max 40% increase
```

**Benefit:** Prevents oscillation between extremes

## Implementation Priority

### Phase 1 (Quick Wins - 15 min)
1. ✅ Lower initial integration to 3ms on HIGH detection
2. ✅ Limit integration scaling to 1.4x for HIGH sensitivity
3. ✅ Catch minimized LEDs earlier (≤15 instead of ≤10)

### Phase 2 (Moderate - 30 min)
4. Add gentle post-saturation adjustments (10-15% steps)
5. Make saturation cuts proportional to overshoot ratio
6. Add saturation history tracking to EngineState

### Phase 3 (Advanced - 1 hour)
7. Integration-first strategy for LOW-LED, LOW-SIGNAL state
8. Adaptive acceptance windows for HIGH sensitivity
9. ML model training with collected data

## Data Collection for ML Training

**Log these additional metrics** to improve ML models:

```python
# At each iteration
training_data = {
    'device_serial': device_serial,
    'iteration': iteration,
    'sensitivity': 'HIGH' if high_sensitivity_detected else 'BASELINE',
    'integration_ms': state.integration_ms,
    'led_values': dict(state.leds),
    'signals': dict(signals),
    'saturation_pixels': dict(saturation),
    'action_taken': 'increase_integration|decrease_integration|adjust_led|skip',
    'converged': False,  # Updated at end
    'final_error_percent': 0.0,  # Updated at end
}
```

**Save to JSON** after each calibration:
```python
with open(f'training_data/calibration_{timestamp}.json', 'w') as f:
    json.dump(training_data, f, indent=2)
```

## Testing Protocol

### Test 1: Verify Lower Integration Start
- Start calibration with HIGH sensitivity device
- Confirm integration drops to 3ms at iteration 2
- Check if saturation is avoided or reduced

### Test 2: Gentle Recovery
- Let device saturate, then clear saturation
- Verify LED increases are 10-15% steps, not large jumps
- Check convergence time vs current behavior

### Test 3: Integration-First Strategy
- Test with LEDs stuck at 10-15
- Verify integration increases before LED increases
- Confirm no saturation on integration increase

### Success Criteria
- ✅ Converges within 10 iterations (vs current 15+ without convergence)
- ✅ No oscillation between saturation and under-signal
- ✅ Final signals within 85±5% of target
- ✅ No saturation in final state

## Expected Improvements

| Metric | Before | After (Expected) |
|--------|--------|------------------|
| Iterations to converge | 15+ (fails) | 6-8 |
| Saturation events | 2-3 | 0-1 |
| LED oscillations | High | Low |
| Final accuracy | 50% (fails) | 85±5% |
| Time to calibrate | 45s (fails) | 20-25s |

## Rollback Plan

If refinements cause regressions:
1. Revert initial integration change (keep at 5ms)
2. Disable gentle adjustments (use slope-based only)
3. Fall back to current aggressive saturation cuts
4. Document which device types need which strategies

## Next Steps

1. **Implement Phase 1** (quick wins)
2. **Test with FLMT09788** (your HIGH sensitivity device)
3. **Collect 5-10 calibration logs** with new behavior
4. **Review convergence patterns** - did we eliminate oscillation?
5. **Implement Phase 2** if Phase 1 shows promise
6. **Start ML training** once 20+ logs collected
