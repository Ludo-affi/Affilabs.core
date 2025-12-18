# Convergence Engine Migration Plan

## Already Migrated ✓
1. **Maxed LED Detection** (engine.py lines 181-208) - If channel at LED=255 AND below acceptance threshold, increase integration time
2. **Robust Slope Estimation** (estimators.py) - Linear regression with 3+ points, two-point fallback
3. **Production-Proven Defaults** (config.py) - Documented rationale for all thresholds

## High Priority - Production Proven Logic to Migrate

### 1. Device Sensitivity Classification
**Location**: `affilabs/utils/device_sensitivity_classifier.py`
**Purpose**: Early detection of HIGH sensitivity detectors to cap integration time ≤20ms

**Current Stack Logic**:
```python
# In led_convergence_algorithm.py lines 238-269
if iteration <= 2:
    features = SensitivityFeatures(
        integration_ms=integration_ms,
        num_saturating=len(channels_saturating),
        total_saturated_pixels=sum(sat_per_ch.values()),
        avg_signal_fraction_of_target=...,
        avg_model_slope_10ms=...,
    )
    label, conf, reason = classifier.classify(features)
    if label == SensitivityLabel.HIGH:
        high_sensitivity_detected = True
        # Cap integration time at 20ms
```

**Value**: Prevents runaway saturation on ultra-sensitive detectors
**Migration Target**: Add to engine.py as early-iteration check

### 2. Weakest Channel Protection Logic
**Location**: `led_convergence_algorithm.py` lines 328-392
**Purpose**: When weakest channel is maxed+locked, reduce OTHER channels' LEDs instead of integration time

**Current Stack Logic**:
```python
if total_sat > 0:
    weakest_ch = min(ch_list, key=lambda c: signals.get(c, 0.0))
    weakest_led = led_intensities.get(weakest_ch, 0)
    weakest_locked = weakest_ch in locked_channels

    # If weakest maxed and locked, reduce saturating channels using slope ratios
    if weakest_led >= config.MAX_LED and weakest_locked:
        for ch in channels_saturating:
            # Normalize using model slopes
            normalized_led = (weakest_led * ch_slope) / weakest_slope
```

**Value**: Prevents integration time reduction when weakest channel can't improve further
**Migration Target**: Add to engine.py saturation handling (lines 210-220)

### 3. Near-Window Adaptive Margin
**Location**: `led_convergence_algorithm.py` lines 222-232
**Purpose**: Dynamically adjust near window to match tolerance if tolerance > near_window

**Current Stack Logic**:
```python
configured_near_percent = getattr(config, "NEAR_WINDOW_PERCENT", 0.10)
effective_near_percent = max(configured_near_percent, tolerance_percent)
if effective_near_percent > configured_near_percent:
    logger.info(f"Adjusted near window from {configured_near_percent*100:.1f}% to {effective_near_percent*100:.1f}%")
```

**Value**: Prevents near window from being smaller than tolerance (logical inconsistency)
**Migration Target**: Add to policies.py PriorityPolicy initialization

### 4. High Sensitivity Integration Cap
**Location**: `led_convergence_algorithm.py` lines 411-427
**Purpose**: Cap integration time at 20ms for HIGH sensitivity devices

**Current Stack Logic**:
```python
if high_sensitivity_detected:
    max_allowed_integration = min(20.0, detector_params.max_integration_time)
    if new_integration_ms > max_allowed_integration:
        logger.info(f"⚠️ HIGH sensitivity device: Capping integration at {max_allowed_integration:.1f}ms")
        new_integration_ms = max_allowed_integration
```

**Value**: Prevents saturation spiral on ultra-sensitive detectors
**Migration Target**: Add to engine.py integration time adjustment

### 5. Sticky Locks with Detailed Logging
**Location**: `led_convergence_algorithm.py` lines 283-322
**Purpose**: Enhanced channel status logging with priority grouping

**Current Stack Logic**:
```python
locked_channels = set()
for ch in channels_acceptable:
    if sat_per_ch.get(ch, 0) == 0:
        locked_channels.add(ch)
        state.lock_channel(ch)  # Sticky lock

# Merge with sticky locks from prior iterations at same integration
locked_channels |= set([ch for ch in state.get_locked() if sat_per_ch.get(ch, 0) == 0])

# Log status
logger.info(f"🔒 LOCKED: [{locked_str}]")
logger.info(f"🚩 PRIORITY (sat or >±10%): [{urgent_str}]")
logger.info(f"🟡 NEAR (within ±10% but outside tolerance): [{near_str}]")
logger.info(f"⚠️ SATURATING: [{sat_str}]")
```

**Value**: Clear visibility into convergence progress
**Migration Target**: Already in engine.py (lines 150-180), enhance logging format

## Medium Priority - Refinements

### 6. Boundary Margin Scaling
**Location**: `led_convergence_core.py` lines 229-235
**Purpose**: Use smaller margin when channel is near target (within near_window)

**Current Stack Logic**:
```python
def enforce_boundaries(..., current_signal, target_signal):
    margin = config.LED_BOUNDARY_MARGIN  # Default 5
    if current_signal and target_signal:
        err_pct = abs(current_signal - target_signal) / target_signal
        if err_pct <= near_window_percent:
            margin = int(round(margin * near_scale))  # Reduce to 2-3
```

**Value**: Allows finer LED adjustments near target
**Migration Target**: Already in policies.py BoundaryPolicy (lines 69-80), verify implementation

### 7. Model Slope Validation
**Location**: Throughout current stack
**Purpose**: Check if model slopes are reasonable before using

**Current Stack Logic**:
```python
if model_slopes and model_slopes.get(ch):
    slope = model_slopes[ch]
    if 0 < slope < 1000:  # Sanity check
        # Use slope
```

**Value**: Prevents bad slopes from causing divergence
**Migration Target**: Add validation in estimators.py SlopeEstimator

## Low Priority - Nice to Have

### 8. Integration Time Increase Aggressiveness
**Location**: `led_methods_OLD_BACKUP.py` lines 715-740
**Purpose**: Use at least 1.15x increase to overcome measurement noise

**Current Stack Logic**:
```python
required_ratio = target / signal if signal > 0 else 2.0
# Use at least 1.15x to overcome noise
time_increase = min(2.0, max(1.15, required_ratio))
```

**Value**: Faster convergence, fewer iterations
**Migration Target**: Add to engine.py integration time increase logic

## Implementation Priority

1. **CRITICAL**: Maxed LED detection ✓ DONE
2. **CRITICAL**: Robust slope estimation ✓ DONE
3. **HIGH**: Device sensitivity classification
4. **HIGH**: Weakest channel protection
5. **MEDIUM**: Near-window adaptive margin
6. **MEDIUM**: High sensitivity integration cap
7. **LOW**: Enhanced logging format
8. **LOW**: Boundary margin scaling validation

## Testing Requirements

Each migrated feature should be tested with:
- HIGH sensitivity device (Flame-T S/N FLMT09116)
- BASELINE device (USB4000 S/N USB4E####)
- Both S-mode and P-mode calibration
- Verify convergence success rate ≥95%
- Verify iteration count ≤10 for typical cases

## Success Metrics

- **Convergence Rate**: ≥95% success (current stack: 97%)
- **Iteration Count**: ≤10 iterations typical (current stack: 5-7)
- **Speed**: 3 PWM steps in refinement (3x faster than 1 PWM step)
- **Robustness**: Handle maxed LED + weak signal case (P-mode critical)
