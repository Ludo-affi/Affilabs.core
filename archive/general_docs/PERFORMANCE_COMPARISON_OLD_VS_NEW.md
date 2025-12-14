# Performance Comparison: Old Software vs New Optimized Version

**Date**: October 19, 2025
**Status**: TESTING - Collecting comparison data
**New Version**: All optimizations active (Phase 4 + Centroid)

---

## Quick Comparison Checklist

### ⏱️ **Speed Metrics**

| Metric | Old Software | New Software | Improvement |
|--------|-------------|--------------|-------------|
| **Cycle Time** | _____ s | ~1.20s | _____ % |
| **Update Rate** | _____ Hz | ~0.83 Hz | _____ × |
| **Calibration Time** | _____ min | _____ min | _____ % |
| **Startup Time** | _____ s | _____ s | _____ % |

### 📊 **Quality Metrics**

| Metric | Old Software | New Software | Status |
|--------|-------------|--------------|--------|
| **Baseline Noise** | _____ RU | <2 RU target | ☐ Better ☐ Same ☐ Worse |
| **Peak Stability** | _____ RU | _____ RU | ☐ Better ☐ Same ☐ Worse |
| **Binding Curve R²** | _____ | >0.999 target | ☐ Better ☐ Same ☐ Worse |
| **Signal Quality** | ☐ Good ☐ Fair | ☐ Good ☐ Fair | ☐ Better ☐ Same ☐ Worse |

### 🎯 **User Experience**

| Aspect | Old Software | New Software | Notes |
|--------|-------------|--------------|-------|
| **Responsiveness** | ☐ Smooth ☐ Laggy | ☐ Smooth ☐ Laggy | |
| **GUI Updates** | ☐ Fluid ☐ Choppy | ☐ Fluid ☐ Choppy | |
| **Data Export** | ☐ Fast ☐ Slow | ☐ Fast ☐ Slow | |
| **Overall Feel** | ☐ Good ☐ Fair ☐ Poor | ☐ Good ☐ Fair ☐ Poor | |

---

## Detailed Performance Analysis

### 1. Acquisition Speed

**What to Measure**:
- Time from start of one cycle to the next
- How many updates per minute you see in the sensorgram
- Console output showing cycle timing

**How to Compare**:
1. Run old software for 2 minutes, count updates
2. Run new software for 2 minutes, count updates
3. Calculate: `update_rate = updates / 120 seconds`

**Expected Result**:
- Old software: ~0.4-0.5 Hz (based on typical SPR systems)
- New software: ~0.83 Hz (1.20s per cycle)
- **Improvement: ~60-100% faster**

---

### 2. Baseline Noise

**What to Measure**:
- Standard deviation of sensorgram during stable baseline
- Should be measured in RU (Response Units)
- Typical: 0.5-2 RU for good systems, 2-5 RU for acceptable

**How to Compare**:
1. Let system stabilize for 5 minutes (no sample changes)
2. Check last 2 minutes of data
3. Calculate standard deviation of each channel

**Expected Result**:
- Target: <2 RU for all channels
- Should be comparable or better than old software

**Console Commands** (if needed):
```python
# In Python console or debug mode:
import numpy as np
noise = np.std(lambda_values[-120:])  # Last 2 min @ 1 Hz
print(f"Baseline noise: {noise:.3f} RU")
```

---

### 3. Peak Detection Method Comparison

**New Methods Available**:

| Method | Speed | Stability | When to Use |
|--------|-------|-----------|-------------|
| **Centroid** ⭐ | 1-2ms | <2 RU | Live mode (CURRENT) |
| **Enhanced** | 15ms | <1 RU | High-precision required |
| **Parabolic** | 0.5ms | 3-5 RU | Ultra-fast, lower quality |

**Testing Different Methods**:
```python
# In settings/settings.py, change:
PEAK_TRACKING_METHOD = 'centroid'   # Current (fastest stable)
PEAK_TRACKING_METHOD = 'enhanced'   # Slower but highest quality
PEAK_TRACKING_METHOD = 'parabolic'  # Fastest but more noise
```

---

### 4. Integration Time Comparison

**Current Settings**:
- Integration time: 40ms (Phase 4 test)
- Scans per acquisition: 4
- Total per channel: 160ms

**If 40ms is Too Fast** (too noisy):
```python
# settings/settings.py
INTEGRATION_TIME_MS = 50.0  # Revert to Phase 3B baseline
# This adds 160ms per cycle (1.20s → 1.36s)
```

**If You Want Even Faster** (more aggressive):
```python
INTEGRATION_TIME_MS = 35.0  # Even faster (test carefully!)
# or
NUM_SCANS_PER_ACQUISITION = 3  # Reduce scans (more noise)
```

---

## Optimization Summary (What's Active)

### ✅ **Currently Enabled**

| Optimization | Savings | Status |
|-------------|---------|--------|
| Phase 1: LED delay (100ms→50ms) | 200ms | ✅ Active |
| Phase 2: 4-scan averaging | Quality | ✅ Active |
| Phase 3A: Wavelength mask caching | 48ms | ✅ Active |
| Phase 3B: Loop cleanup | 9-309ms | ✅ Active |
| **Phase 4: 40ms integration** | **160ms** | 🔄 **TESTING** |
| Conditional diagnostic emission | 15ms | ✅ Active |
| Console logging reduction | 2ms | ✅ Active |
| **Centroid peak tracking** | **52ms** | 🔄 **TESTING** |

**Total Improvement**: ~487ms saved (50% faster than 2.4s baseline)

---

## Test Scenarios

### Scenario 1: Baseline Stability Test

**Goal**: Confirm <2 RU noise

**Steps**:
1. Start live mode, no sample changes
2. Wait 5 minutes for thermal stabilization
3. Observe sensorgram for 2-3 minutes
4. Check console for any errors
5. Record baseline noise level

**Success Criteria**:
- ✅ No errors or warnings
- ✅ Sensorgram smooth, no spikes
- ✅ Noise <2 RU per channel
- ✅ Peak wavelength stable

---

### Scenario 2: Binding Curve Test

**Goal**: Confirm binding kinetics accuracy

**Steps**:
1. Run sample injection (if available)
2. Fit association/dissociation curves
3. Check R² fit quality
4. Compare ka, kd, KD with old software

**Success Criteria**:
- ✅ R² > 0.999 for fits
- ✅ Kinetic constants within 10% of old software
- ✅ No fitting failures
- ✅ Smooth sensorgram during transition

---

### Scenario 3: Speed Test

**Goal**: Measure actual cycle time

**Steps**:
1. Start live mode
2. Count updates in 2 minutes
3. Check console for cycle timing
4. Calculate: `cycle_time = 120s / num_updates`

**Success Criteria**:
- ✅ Cycle time ~1.20s (±0.05s)
- ✅ Update rate ~0.83 Hz
- ✅ Consistent (no slow cycles)

---

### Scenario 4: Long-Term Stability

**Goal**: Confirm no degradation over time

**Steps**:
1. Run continuously for 30 minutes
2. Check for memory leaks (Task Manager)
3. Check for timing drift
4. Verify no crashes or errors

**Success Criteria**:
- ✅ No crashes or freezes
- ✅ Memory usage stable (<500MB increase)
- ✅ Cycle time consistent
- ✅ Peak tracking reliable

---

## Comparison with Old Software

### Known Differences

**Hardware**:
- ☐ Same hardware version
- ☐ Different hardware (specify: _____________)

**Calibration**:
- ☐ Used old calibration file
- ☐ Fresh calibration performed
- Date of calibration: _____________

**Environment**:
- ☐ Same temperature/conditions
- ☐ Different conditions (specify: _____________)

---

## Decision Matrix

### If New Software is BETTER:

**Faster + Similar/Better Quality**:
- ✅ **ADOPT** all optimizations
- Consider even more aggressive (35ms, 3 scans)
- Document final settings

**Faster but Slightly Worse Quality**:
- Evaluate trade-off: Is speed worth slight quality loss?
- If acceptable: ADOPT
- If not: Try enhanced method or 50ms integration

---

### If New Software is COMPARABLE:

**Similar Speed + Similar Quality**:
- ✅ **ADOPT** (modernized codebase, better maintainability)
- Benefits: Better architecture, documentation, future optimization potential

---

### If New Software is WORSE:

**Problem: Too Much Noise**:
- Try: `PEAK_TRACKING_METHOD = 'enhanced'` (+13ms but better quality)
- Try: `INTEGRATION_TIME_MS = 50.0` (+160ms but more signal)
- Try: Both together (revert to Phase 3B: 1.43s per cycle)

**Problem: Peak Detection Errors**:
- Check: Centroid method threshold (try 0.3 or 0.7)
- Switch to: `PEAK_TRACKING_METHOD = 'enhanced'`
- Last resort: `ENHANCED_PEAK_TRACKING = False` (old method)

**Problem: Too Slow** (shouldn't happen, but if...):
- Check: Diagnostic emission disabled? (`emit_diagnostic_data = False`)
- Check: Console logging at WARNING level?
- Check: No background processes interfering?

---

## Performance Tuning Guide

### Quick Settings Reference

```python
# settings/settings.py

# SPEED vs QUALITY Trade-offs
# ═══════════════════════════════════════════════

# Integration Time (biggest impact)
INTEGRATION_TIME_MS = 40.0  # FAST: 40ms (testing), BALANCED: 50ms, SAFE: 60ms

# Number of Scans (quality vs speed)
NUM_SCANS_PER_ACQUISITION = 4  # FAST: 3 scans, BALANCED: 4, SAFE: 5

# Peak Tracking Method
PEAK_TRACKING_METHOD = 'centroid'   # FAST: 1-2ms, <2 RU
PEAK_TRACKING_METHOD = 'enhanced'   # QUALITY: 15ms, <1 RU
PEAK_TRACKING_METHOD = 'parabolic'  # FASTEST: 0.5ms, 3-5 RU

# Diagnostic Overhead
emit_diagnostic_data = False  # Keep False for live mode (saves 15ms)

# Console Logging
CONSOLE_LOG_LEVEL = logging.WARNING  # Keep at WARNING for speed
```

### Performance Presets

**🚀 MAXIMUM SPEED** (1.0s per cycle, 3-5 RU noise):
```python
INTEGRATION_TIME_MS = 35.0
NUM_SCANS_PER_ACQUISITION = 3
PEAK_TRACKING_METHOD = 'centroid'
```

**⚖️ BALANCED** (1.2s per cycle, <2 RU noise) ⭐ **CURRENT**:
```python
INTEGRATION_TIME_MS = 40.0
NUM_SCANS_PER_ACQUISITION = 4
PEAK_TRACKING_METHOD = 'centroid'
```

**🎯 HIGH QUALITY** (1.5s per cycle, <1 RU noise):
```python
INTEGRATION_TIME_MS = 50.0
NUM_SCANS_PER_ACQUISITION = 4
PEAK_TRACKING_METHOD = 'enhanced'
```

**🛡️ ULTRA STABLE** (1.8s per cycle, <0.5 RU noise):
```python
INTEGRATION_TIME_MS = 60.0
NUM_SCANS_PER_ACQUISITION = 5
PEAK_TRACKING_METHOD = 'enhanced'
KALMAN_FILTER_ENABLED = True
```

---

## Next Steps

1. **Fill in comparison data** above
2. **Run all test scenarios**
3. **Make decision**: Adopt/Adjust/Revert
4. **Document final configuration**
5. **Update VERSION.md with final settings**

---

## Results (Fill in after testing)

### Final Decision: ☐ ADOPT ☐ ADJUST ☐ REVERT

**Reasoning**:
_____________________________________________
_____________________________________________
_____________________________________________

**Final Configuration**:
- Integration time: _____ ms
- Scans: _____
- Peak method: _________
- Cycle time: _____ s
- Noise level: _____ RU

**Notes**:
_____________________________________________
_____________________________________________
_____________________________________________

**Date of decision**: _____________
**Approved by**: _____________
