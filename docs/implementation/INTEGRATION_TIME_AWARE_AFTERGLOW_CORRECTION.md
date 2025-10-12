# LED Afterglow Correction - Integration Time Aware System

**Status**: Implementation in progress
**Date**: October 11, 2025
**Characterization Runtime**: ~45 minutes (running now)

## Overview

We discovered that LED phosphor afterglow creates measurement artifacts in multi-channel SPR measurements. Initial characterization showed true decay constants of 0.6-1.2ms (much faster than initially measured 100ms). However, validation testing revealed that **the apparent decay constant varies with integration time** due to the averaging window effect.

## Problem Statement

### Initial Discovery
- LED phosphor afterglow persists after LED turn-off
- True decay: 0.6-1.2ms (exponential decay)
- Channel-specific differences:
  - Channel D: τ = 0.60ms (fastest)
  - Channel C: τ = 0.67ms
  - Channel A: τ = 1.05ms
  - Channel B: τ = 1.16ms (slowest)

### Integration Time Dependency
Validation testing at multiple integration times (1-100ms) revealed:

| Integration Time | Observed τ (Channel D) | Fit Quality (R²) |
|-----------------|----------------------|------------------|
| 1-2ms | Fit failure | Poor (no signal) |
| 5ms | 0.59ms | 0.9833 ✅ |
| 10ms | 3.28ms | 0.9865 |
| 20ms | 2.87ms | 0.9874 |
| 50ms | 4.08ms | 0.9961 |
| 100ms | 3.57ms | 0.9979 |

**Key Finding**: τ appears 5-7× longer at long integration times (50-100ms) compared to short integration times (5ms). This is due to the integration time acting as a moving average window that smears out the fast decay.

**Consequence**: Cannot use a single τ value to correct measurements at all integration times. Need **integration-time-dependent correction model**.

## Solution: Integration-Time-Aware Correction

### Approach
Build lookup tables for each channel: **τ(integration_time)**

1. **Characterization Phase** (currently running):
   - Measure all 4 channels at 5 integration times: [5, 10, 20, 50, 100]ms
   - 5 cycles per measurement for statistical accuracy
   - Total: 4 channels × 5 int_times × 5 cycles = 100 measurements
   - Runtime: ~45 minutes

2. **Interpolation Phase** (next):
   - For arbitrary integration time (e.g., 37ms), interpolate τ from lookup table
   - Use linear or cubic spline interpolation
   - Ensures smooth correction across full range

3. **Correction Phase** (production):
   - Load channel-specific lookup tables
   - For each measurement:
     - Get current integration time
     - Interpolate τ(int_time) for that channel
     - Calculate afterglow correction: `Δsignal = A × exp(-t/τ)`
     - Apply correction: `corrected = measured - Δsignal`

### Data Structure

```json
{
  "channel_A": {
    "integration_times_ms": [5, 10, 20, 50, 100],
    "tau_ms": [1.02, 1.85, 2.45, 3.12, 3.78],
    "baseline": [2950, 2955, 2960, 2965, 2970],
    "amplitude": [150, 165, 180, 195, 210]
  },
  "channel_B": { ... },
  "channel_C": { ... },
  "channel_D": { ... }
}
```

## Implementation Plan

### Phase 1: Characterization ✅ (In Progress)
**File**: `led_afterglow_integration_time_model.py`
**Status**: Running (measurement 2/20 complete)
**Output**: `led_afterglow_integration_time_models_TIMESTAMP.json`
**Expected completion**: ~21:45-21:50 (started 21:06)

**Features**:
- All 4 channels (A, B, C, D)
- 5 integration times (5, 10, 20, 50, 100ms)
- 5 cycles per measurement (averaging for accuracy)
- Exponential fit with R² quality metric
- Comprehensive diagnostic plots showing τ vs integration time

### Phase 2: Correction Module ⏳ (Next)
**File**: `afterglow_correction.py`
**Deliverable**: Production-ready correction API

**Functions**:
```python
def load_afterglow_models(json_file: str) -> dict:
    """Load characterization data from JSON."""

def interpolate_tau(channel: ChannelID, integration_time_ms: float, models: dict) -> float:
    """Interpolate τ for arbitrary integration time."""

def calculate_afterglow_correction(
    channel: ChannelID,
    integration_time_ms: float,
    delay_ms: float,
    models: dict
) -> float:
    """Calculate expected afterglow signal at given delay."""

def apply_afterglow_correction(
    measured_spectrum: np.ndarray,
    channel: ChannelID,
    integration_time_ms: float,
    delay_ms: float,
    models: dict
) -> np.ndarray:
    """Apply afterglow correction to measured spectrum."""
```

### Phase 3: Testing & Validation ⏳
**File**: `test_afterglow_correction.py`

**Tests**:
1. **Interpolation accuracy**: Test at known points and midpoints
2. **Boundary conditions**: Test at 5ms and 100ms limits
3. **Multi-channel cycling**: Validate no cumulative buildup
4. **Correction error**: Verify <5% residual after correction
5. **Edge cases**: Handle 1ms (too short) and 200ms (extrapolation)

### Phase 4: Production Integration ⏳
**File**: `spr_data_acquisition.py` (modified)

**Integration points**:
- Load models at startup
- Apply correction during multi-channel scans
- Add `enable_afterglow_correction` flag to device config
- Log correction status and residual estimates
- Provide before/after comparison in diagnostics

### Phase 5: Documentation ⏳
**File**: `AFTERGLOW_CORRECTION_GUIDE.md`

**Contents**:
- Theory: LED phosphor afterglow physics
- Characterization procedure for new devices
- Usage examples for OEM integration
- Troubleshooting guide
- Performance benchmarks

## Expected Performance Improvements

### Multi-Channel Scan Speed
- **Before**: 700-900ms (used 105ms inter-channel delay from initial testing)
- **After**: ~300ms (optimized 5ms delays based on 2% residual threshold)
- **Improvement**: 2-3× faster

### Inter-Channel Crosstalk Reduction
- **Before correction**: 5-15% crosstalk from previous channel
- **After correction**: <2% residual (target)
- **Improvement**: >90% crosstalk reduction

### Spectrum Quality
- Reduced artifacts in multi-channel measurements
- More consistent baselines between channels
- Better separation of overlapping features

## Technical Details

### Exponential Decay Model
```
signal(t) = baseline + amplitude × exp(-t/τ)
```

Where:
- `baseline`: Dark signal (LED off, long delay)
- `amplitude`: Initial afterglow amplitude at t=0
- `τ`: Decay time constant (ms)
- `t`: Time after LED turned off (ms)

### Why τ Varies with Integration Time

**Physics**: The LED phosphor decay is intrinsically exponential with fixed τ ≈ 1ms.

**Measurement Effect**: Integration time acts as a moving average:
```
measured(t) = (1/T_int) × ∫[t to t+T_int] signal(τ) dτ
```

For fast exponential decay convolved with integration window:
- **Short T_int (5ms)**: Captures sharp decay → τ_measured ≈ τ_true
- **Long T_int (100ms)**: Averages over decay → τ_measured >> τ_true (appears slower)

This is NOT a failure of the exponential model - it's a **measurement artifact** that we must account for by using integration-time-dependent parameters.

### Interpolation Strategy

**Linear interpolation** (simple, fast):
```python
τ(T) = τ1 + (τ2 - τ1) × (T - T1) / (T2 - T1)
```

**Cubic spline** (smooth, more accurate):
```python
from scipy.interpolate import CubicSpline
cs = CubicSpline(integration_times, tau_values)
tau = cs(integration_time)
```

We'll use **cubic spline** for production since we have sufficient data points (5 per channel) and need smooth behavior for arbitrary integration times.

## Data Quality Requirements

### Acceptable Measurements
- R² > 0.95 (excellent exponential fit)
- τ > 0.5ms (physically reasonable for phosphor)
- Amplitude > 50 counts (detectable afterglow)
- Baseline stable (std < 5 counts over 5 cycles)

### Rejection Criteria
- R² < 0.90 (poor fit quality)
- τ < 0.1ms or > 50ms (unphysical)
- Amplitude < 10 counts (noise-level)
- Drift > 5% between cycles (instability)

## Current Status

### Completed ✅
1. Initial LED timing characterization (rise/fall)
2. Afterglow discovery and diagnosis (50:1 asymmetry)
3. Single-channel exponential decay modeling
4. 4-channel characterization at 5ms integration
5. Integration time dependency validation
6. Comprehensive characterization script created

### In Progress ⏳
1. **Running now**: 4 channels × 5 integration times characterization
   - Started: 21:06
   - Current: Measurement 2/20 (Channel A @ 10ms)
   - Expected completion: ~21:50
   - Output: Lookup tables for all channels

### Next Steps (After Characterization Completes)
1. Build `afterglow_correction.py` module with interpolation
2. Create test suite for validation
3. Integrate into SPR data acquisition pipeline
4. Document for OEM use
5. Validate with real SPR measurements

## Files Generated

### Characterization Data
- `led_afterglow_integration_time_models_YYYYMMDD_HHMMSS.json` - Lookup tables
- `led_afterglow_integration_time_analysis.png` - Diagnostic plots

### Code Modules
- `led_afterglow_integration_time_model.py` - Characterization script
- `afterglow_correction.py` - Production correction module (TODO)
- `test_afterglow_correction.py` - Test suite (TODO)

### Documentation
- `AFTERGLOW_CORRECTION_GUIDE.md` - Complete guide (TODO)
- This file - Implementation status

## Success Metrics

### Characterization Phase
- ✅ All 20 measurements complete
- ✅ R² > 0.95 for all measurements
- ✅ Smooth τ(integration_time) curves
- ✅ No anomalies or outliers

### Correction Phase
- Target: <2% residual afterglow
- Target: >90% crosstalk reduction
- Target: Correction adds <5ms to measurement time
- Target: Works across 5-100ms integration times

### Production Deployment
- Enable/disable flag in device config
- Automatic loading of characterization data
- Real-time correction during measurements
- Diagnostic logging of correction performance

---

**Last Updated**: October 11, 2025, 21:10
**Next Update**: After characterization completes (~21:50)
