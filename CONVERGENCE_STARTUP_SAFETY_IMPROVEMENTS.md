# Safe Improvements: Hardware Detection → Convergence Starting

**Status**: Analysis Complete  
**Date**: February 16, 2026  
**Focus**: Low-risk validation and safety improvements before LED convergence begins

---

## Overview

Between **Step 1 (Hardware Detection)** and **Step 4 (Convergence Starting)**, the calibration sequence performs:
1. **Step 1**: Hardware validation & LED preparation
2. **Step 2**: Wavelength calibration (ROI definition)
3. **Step 3**: LED brightness & model validation
4. **[PRE-CONVERGENCE CHECKS]** ← Safe improvements here
5. **Step 4**: LED convergence start

This document identifies **low-risk, high-value improvements** to the pre-convergence validation phase.

---

## Currently Implemented Safety Features ✅

### 1. **Pre-Convergence Polarizer Check** (EXCELLENT)
**Location**: `calibration_orchestrator.py`, lines ~475-530

Tests ALL 4 LEDs at 5% intensity to verify polarizer is transmitting:
```python
# Test with ALL 4 LEDs at 5% (matches servo calibration conditions)
test_led = int(0.05 * 255)  # 5% intensity
test_time_ms = 5.0

# Enable all 4 LEDs
ctrl.enable_multi_led(a=True, b=True, c=True, d=True)
ctrl.set_batch_intensities(a=test_led, b=test_led, c=test_led, d=test_led)

# Test spectrum acquisition
test_spectrum = usb.read_intensity()
test_signal = np.mean(test_spectrum[wave_min_index:wave_max_index])

# Critical threshold: 3% of detector range
critical_threshold = detector_params.max_counts * 0.03
if test_signal < critical_threshold:
    raise RuntimeError("Polarizer blocking light...")
```

**Benefits**:
- ✅ Catches servo position errors BEFORE convergence
- ✅ Prevents wasted iterations on blocked optical path
- ✅ Provides detailed diagnostic messages
- ✅ Uses realistic test conditions (4 LEDs @ 5%)

### 2. **Model Slopes Validation** (GOOD)
**Location**: `calibration_orchestrator.py`, lines ~205-240

Loads and validates LED calibration model:
```python
try:
    model_loader.load_model(detector_serial)
    model_slopes_s = model_loader.get_slopes(polarization="S", ...)
    if not model_slopes_s:
        model_exists = False
except ModelNotFoundError:
    model_exists = False
```

**Benefits**:
- ✅ Handles missing models gracefully
- ✅ Triggers automatic OEM training if needed
- ✅ Fallback to empirical LED ranking

### 3. **Initial Integration Time Calculation** (EXCELLENT)
**Location**: `calibration_orchestrator.py`, lines ~600-700

Calculates optimal initial integration time based on model:
```python
# For weakest LED at max intensity (255)
optimal_integration_ms = (target_counts / (weakest_slope * 255.0)) * 10.0

# Clamp to detector limits
optimal_integration_ms = max(detector_params.min_integration_time, optimal_integration_ms)
optimal_integration_ms = min(detector_params.max_integration_time, optimal_integration_ms)
```

**Benefits**:
- ✅ Minimizes convergence iterations
- ✅ Respects detector hardware limits
- ✅ Adapts to different detector types

---

## Safe Improvements to Add 🚀

### 1. **ROI Index Bounds Validation** (CRITICAL)
**Risk Level**: Very Low  
**Impact**: Prevent out-of-bounds array access during convergence

**Current Code**:
```python
# calibration_orchestrator.py, lines ~150-160
wave_min_index = np.argmin(np.abs(wave_data - MIN_WAVELENGTH))
wave_max_index = np.argmin(np.abs(wave_data - MAX_WAVELENGTH))

# Direct use without validation
result.wave_min_index = int(wave_min_index)
result.wave_max_index = int(wave_max_index)
```

**Improvement**:
```python
# After calculating indices, add validation
wave_min_index = np.argmin(np.abs(wave_data - MIN_WAVELENGTH))
wave_max_index = np.argmin(np.abs(wave_data - MAX_WAVELENGTH))

# NEW: Validate indices are within bounds
if not (0 <= wave_min_index < len(wave_data)):
    raise ValueError(f"Invalid wave_min_index={wave_min_index} (out of bounds [0, {len(wave_data)-1}])")
if not (0 <= wave_max_index < len(wave_data)):
    raise ValueError(f"Invalid wave_max_index={wave_max_index} (out of bounds [0, {len(wave_data)-1}])")
if wave_max_index <= wave_min_index:
    raise ValueError(f"Invalid ROI: max_index ({wave_max_index}) <= min_index ({wave_min_index})")

# Ensure min < max
if wave_min_index > wave_max_index:
    wave_min_index, wave_max_index = wave_max_index, wave_min_index
    logger.warning(f"⚠️  Swapped ROI indices to maintain ordering")

result.wave_min_index = int(wave_min_index)
result.wave_max_index = int(wave_max_index)

# Log ROI details for diagnostics
roi_pixels = wave_max_index - wave_min_index
logger.info(f"✅ ROI validation: indices [{wave_min_index}:{wave_max_index}], {roi_pixels} pixels")
if roi_pixels < 100:
    logger.warning(f"⚠️  Small ROI: only {roi_pixels} pixels (typical: 150-200)")
```

**Why Safe**:
- Pure validation logic, no behavioral changes
- Only rejects invalid states
- Provides diagnostic logging
- Prevents silent failures later

---

### 2. **Model Slopes Completeness Check** (SAFE)
**Risk Level**: Very Low  
**Impact**: Detect missing channels before convergence

**Current Code**:
```python
# calibration_orchestrator.py, lines ~700-730
initial_leds = {}
for ch in ch_list:
    ch_slope = model_slopes_s.get(ch, 0.0)  # ← Could return 0.0 silently
    if ch == weakest_ch:
        initial_leds[ch] = 255
    elif ch_slope > 0:
        normalized_led = int((weakest_slope / ch_slope) * 255.0)
        initial_leds[ch] = max(10, min(255, normalized_led))
```

**Improvement**:
```python
# NEW: Validate model_slopes covers all channels
if model_slopes_s:
    missing_channels = set(ch_list) - set(model_slopes_s.keys())
    if missing_channels:
        logger.error(f"❌ Model missing slopes for channels: {missing_channels}")
        logger.error(f"   Model has: {list(model_slopes_s.keys())}")
        logger.error(f"   Required: {ch_list}")
        raise ValueError(f"Incomplete model slopes: missing {missing_channels}")
    
    # Validate all slopes are reasonable (not zero or negative)
    for ch, slope in model_slopes_s.items():
        if slope <= 0:
            logger.error(f"❌ Invalid model slope for channel {ch.upper()}: {slope}")
            raise ValueError(f"Invalid slope for channel {ch}: {slope}")

initial_leds = {}
for ch in ch_list:
    ch_slope = model_slopes_s[ch]  # Safe now - we validated it exists
    # ... rest of calculation
```

**Why Safe**:
- Validates preconditions before use
- Early failure with clear diagnostics
- No impact on valid models

---

### 3. **Detector Parameters Validation** (SAFE)
**Risk Level**: Very Low  
**Impact**: Prevent saturation threshold misconfigurations

**Current Code**:
```python
# calibration_orchestrator.py, lines ~140-145
detector_params = get_detector_params(usb)
logger.info(f"🔍 DEBUG: detector_params.max_counts = {detector_params.max_counts}")
# ... uses directly without validation
```

**Improvement**:
```python
# NEW: Validate detector parameters
detector_params = get_detector_params(usb)

# Validate critical parameters exist and are reasonable
if not hasattr(detector_params, 'max_counts') or detector_params.max_counts <= 0:
    raise ValueError(f"Invalid detector max_counts: {getattr(detector_params, 'max_counts', 'MISSING')}")

if not hasattr(detector_params, 'saturation_threshold') or detector_params.saturation_threshold <= 0:
    logger.warning(f"⚠️  Missing saturation_threshold, defaulting to 95% of max_counts")
    detector_params.saturation_threshold = int(0.95 * detector_params.max_counts)

if not hasattr(detector_params, 'min_integration_time') or detector_params.min_integration_time <= 0:
    raise ValueError(f"Invalid min_integration_time: {getattr(detector_params, 'min_integration_time', 'MISSING')}")

if not hasattr(detector_params, 'max_integration_time') or detector_params.max_integration_time <= 0:
    raise ValueError(f"Invalid max_integration_time: {getattr(detector_params, 'max_integration_time', 'MISSING')}")

# Sanity check: min should be < max
if detector_params.min_integration_time >= detector_params.max_integration_time:
    raise ValueError(
        f"Invalid integration time range: min={detector_params.min_integration_time}, "
        f"max={detector_params.max_integration_time}"
    )

logger.info(f"✅ Detector parameters validated:")
logger.info(f"   max_counts: {detector_params.max_counts}")
logger.info(f"   saturation_threshold: {detector_params.saturation_threshold} ({detector_params.saturation_threshold/detector_params.max_counts*100:.1f}%)")
logger.info(f"   integration range: {detector_params.min_integration_time}-{detector_params.max_integration_time}ms")
```

**Why Safe**:
- Detects configuration errors early
- Prevents silent failures during convergence
- Just validation, no logic changes

---

### 4. **Channel List Validation** (SAFE)
**Risk Level**: Very Low  
**Impact**: Prevent invalid channel names

**Current Code**:
```python
# calibration_orchestrator.py, lines ~130-135
ch_list = determine_channel_list(device_type, single_mode, single_ch)
logger.info(f"Channels: {ch_list}")
# ... used directly without validation
```

**Improvement**:
```python
# NEW: Validate channel list
ch_list = determine_channel_list(device_type, single_mode, single_ch)

# Validate channel names
valid_channels = {'a', 'b', 'c', 'd'}
invalid_channels = set(ch_list) - valid_channels

if invalid_channels:
    raise ValueError(f"Invalid channels: {invalid_channels}. Must be subset of {valid_channels}")

if not ch_list:
    raise ValueError("Channel list is empty!")

if len(ch_list) != len(set(ch_list)):
    duplicates = [ch for ch in ch_list if ch_list.count(ch) > 1]
    raise ValueError(f"Duplicate channels in list: {set(duplicates)}")

logger.info(f"✅ Channel list validated: {ch_list}")
```

**Why Safe**:
- Catches configuration errors
- Very lightweight validation
- No behavioral impact

---

### 5. **Integration Time Bounds Check** (SAFE)
**Risk Level**: Very Low  
**Impact**: Prevent out-of-range integration time

**Current Code**:
```python
# calibration_orchestrator.py, lines ~670-680
optimal_integration_ms = (target_counts / (weakest_slope * 255.0)) * 10.0
optimal_integration_ms = max(detector_params.min_integration_time, optimal_integration_ms)
optimal_integration_ms = min(detector_params.max_integration_time, optimal_integration_ms)
initial_integration_ms = optimal_integration_ms
# ... used without pre-check
```

**Improvement**:
```python
# NEW: Add explicit validation logging
optimal_integration_ms = (target_counts / (weakest_slope * 255.0)) * 10.0

# Before clamping, log if we're going out of optimal range
if optimal_integration_ms < detector_params.min_integration_time:
    logger.warning(
        f"⚠️  Calculated integration ({optimal_integration_ms:.1f}ms) below detector minimum "
        f"({detector_params.min_integration_time}ms) → Using minimum"
    )
elif optimal_integration_ms > detector_params.max_integration_time:
    logger.warning(
        f"⚠️  Calculated integration ({optimal_integration_ms:.1f}ms) exceeds detector maximum "
        f"({detector_params.max_integration_time}ms) → Using maximum"
    )

optimal_integration_ms = max(detector_params.min_integration_time, optimal_integration_ms)
optimal_integration_ms = min(detector_params.max_integration_time, optimal_integration_ms)
initial_integration_ms = optimal_integration_ms

logger.info(f"✅ Initial integration time: {initial_integration_ms:.1f}ms")
```

**Why Safe**:
- Just adds diagnostic logging
- No algorithmic changes
- Helps diagnose convergence issues

---

### 6. **Model Slope Zero Handling** (SAFE)
**Risk Level**: Low  
**Impact**: Detect and handle zero slopes

**Current Code**:
```python
# calibration_orchestrator.py, lines ~700-710
if weakest_slope > 0:
    # Calculate optimal integration time
else:
    # Fallback to average slope method
```

**Improvement**:
```python
# NEW: More explicit handling
if weakest_slope <= 0:
    logger.error(f"❌ Invalid model slope for weakest channel {weakest_ch}: {weakest_slope}")
    logger.error("   This indicates LED calibration model is corrupted.")
    logger.error("   A new model will be trained automatically.")
    # Device config allows model to be reloaded, so this should work
    raise ValueError(f"Invalid weakest slope: {weakest_slope}")
```

**Why Safe**:
- Catches data corruption early
- Clear error message
- Triggers proper recovery path

---

## Implementation Summary

| Check | Location | Risk | Impact | Priority |
|-------|----------|------|--------|----------|
| **ROI Index Bounds** | Step 2 → Step 3 | ⬜ None | 🟢 High | **HIGH** |
| **Model Slopes Complete** | Step 3 | ⬜ None | 🟢 High | **HIGH** |
| **Detector Params Valid** | Step 3 | ⬜ None | 🟠 Medium | Medium |
| **Channel List Valid** | Step 3 | ⬜ None | 🟢 High | Medium |
| **Integration Time Bounds** | Step 3 | ⬜ None | 🟠 Medium | Medium |
| **Model Slope Non-Zero** | Step 3 | ⬜ None | 🟠 Medium | Low |

---

## Already Working Well ✅ (No Changes Needed)

1. **Pre-Convergence Polarizer Check** - Excellent detection
2. **Model Validation & Auto-Retrain** - Handles missing models
3. **Initial Integration Time Optimization** - Properly clamped
4. **Initial LED Normalization** - Conservative approach
5. **Relaxed Convergence Acceptance** - Practical tolerance
6. **Post-Convergence Diagnostics** - Detailed error reporting

---

## Recommendations

1. **Start with HIGH priority items**: ROI bounds + Model completeness
2. **Add diagnostic logging** for all parameter validation
3. **Test** with edge cases:
   - Very narrow wavelength range
   - Unusual detector types
   - Missing model data
   - Weak LED channels

---

## Code Locations to Review

- `calibration_orchestrator.py` lines 100-850 (pre-convergence phase)
- `affilabs/utils/calibration_helpers.py` (helper functions)
- `affilabs/convergence/adapters.py` (ROI extraction)
- `affilabs/services/led_model_loader.py` (model validation)

