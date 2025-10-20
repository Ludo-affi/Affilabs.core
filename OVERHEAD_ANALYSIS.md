# Overhead Analysis: Why 880ms Slower Than Old Software?

**Date**: October 20, 2025  
**Critical Discovery**: The problem is OVERHEAD, not acquisition time!

---

## The Real Problem

### Old Software Performance
```
Acquisition: 200ms × 4 channels = 800ms
Overhead: ~300ms
─────────────────────────────────────
Total: 1.1s per cycle
```

### New Software Performance (Phase 5)
```
Acquisition: 105ms × 4 channels = 420ms  ✅ FASTER
Overhead: ~1180ms                         ❌ 4× WORSE!
─────────────────────────────────────────
Total: 1.6s per cycle
```

**We're 380ms FASTER in acquisition, but 880ms SLOWER in overhead!**

---

## Overhead Breakdown Analysis

### Known Overhead Components

| Component | Estimated Time | Total (4 ch) | Notes |
|-----------|---------------|--------------|-------|
| **Peak tracking (centroid)** | 1-2ms | 4-8ms | Minimal |
| **Data array appends** | 0.5ms × 15 | 30ms | np.append overhead |
| **Signal emissions** | 2-5ms | 8-20ms | Qt signals (if diagnostic off) |
| **GUI updates** | 5-10ms | 5-10ms | Chart rendering |
| **Unknown** | ??? | **900ms+** | ❌ THE PROBLEM |

### Unknown Overhead Sources (Need Investigation)

1. **LED Control Delays** ⚠️ HIGH PROBABILITY
   - Batch LED: Should be fast
   - Sequential LED: 15ms per channel = 60ms
   - LED stabilization: 50ms × 4 = 200ms
   - **Potential**: 200-260ms

2. **Spectrometer Readout** ⚠️ HIGH PROBABILITY
   - USB transfer time
   - Driver overhead
   - Buffer management
   - **Potential**: 100-200ms

3. **Data Processing Loop** ⚠️ MEDIUM PROBABILITY
   - Dark correction
   - P/S calibration
   - Transmittance calculation
   - Array operations (np.append)
   - **Potential**: 50-100ms

4. **Thread Synchronization** ⚠️ MEDIUM PROBABILITY
   - Worker thread → GUI thread
   - Signal/slot overhead
   - Mutex locks
   - **Potential**: 20-50ms

5. **Unnecessary Sleeps** ⚠️ LOW (already removed)
   - Phase 3B removed known sleeps
   - **Potential**: 0-10ms

6. **Data Copying** ⚠️ LOW PROBABILITY
   - Array copies for diagnostics (disabled)
   - Shallow vs deep copies
   - **Potential**: 5-10ms

---

## Comparison Needed

### What to Look For in Old Software

**Critical Questions**:
1. How does old software handle LED switching?
   - Batch or sequential?
   - Any delays between LEDs?
   
2. How does old software read spectrometer?
   - Blocking or async?
   - Any buffering?

3. How does old software process data?
   - Peak finding algorithm?
   - Array management (lists vs numpy)?

4. How does old software update GUI?
   - Every cycle or throttled?
   - Direct or signal/slot?

5. What's the main acquisition loop structure?
   - Single threaded or multi-threaded?
   - Any wait conditions?

---

## Quick Tests to Identify Bottleneck

### Test 1: Disable Peak Tracking Entirely
```python
# In spr_data_acquisition.py, comment out peak finding
# Just acquire and display raw data
# Expected: If overhead drops to ~300ms, peak tracking is the issue
```

### Test 2: Profile the Acquisition Loop
```python
import cProfile
import pstats

# Profile one cycle
profiler = cProfile.Profile()
profiler.enable()
# ... acquisition code ...
profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

### Test 3: Time Each Component
```python
import time

# In grab_data() loop:
t0 = time.time()
# LED control
t1 = time.time()
# Spec readout
t2 = time.time()
# Processing
t3 = time.time()
# Peak finding
t4 = time.time()

print(f"LED: {(t1-t0)*1000:.1f}ms, Read: {(t2-t1)*1000:.1f}ms, "
      f"Process: {(t3-t2)*1000:.1f}ms, Peak: {(t4-t3)*1000:.1f}ms")
```

---

## Hypotheses (Ordered by Likelihood)

### Hypothesis 1: LED Delay is 50ms (not optimized) ⭐⭐⭐⭐⭐
**Evidence**: 
- Phase 1 claimed to reduce LED delay to 50ms
- Old software might use 0ms or minimal delay
- 50ms × 4 channels = 200ms overhead

**Test**: 
```python
# settings/settings.py
LED_DELAY = 0.001  # Try minimal delay (1ms)
```

### Hypothesis 2: Spectrometer USB Transfer Slow ⭐⭐⭐⭐
**Evidence**:
- USB communication inherently slow
- Driver overhead
- Old software might use faster method

**Test**: Compare USB4000 driver initialization/settings

### Hypothesis 3: Enhanced Peak Tracking Despite 'Centroid' ⭐⭐⭐
**Evidence**:
- Maybe enhanced method is still being called somewhere
- Debugging logs show which method

**Test**: 
```python
ENHANCED_PEAK_TRACKING = False  # Disable completely
```

### Hypothesis 4: np.append Creating New Arrays Every Cycle ⭐⭐⭐
**Evidence**:
- 15+ np.append calls per cycle
- Each creates new array (O(n) copy)
- Old software might use lists

**Test**: Convert to Python lists for appending

### Hypothesis 5: Qt Signal/Slot Overhead ⭐⭐
**Evidence**:
- Qt signals are convenient but slow
- Thread communication adds latency

**Test**: Compare with direct function calls

---

## Next Steps

1. **Share old software code** ✅ USER WILL DO
2. **Compare architectures** - Find key differences
3. **Profile new software** - Identify exact bottleneck
4. **Apply targeted fix** - Address root cause
5. **Re-measure** - Confirm improvement

---

## Expected Outcome

If we fix the overhead:
```
Acquisition: 420ms (Phase 5: 35ms × 3 × 4)
Overhead: 300ms (match old software)
─────────────────────────────────────
Total: 0.72s per cycle! (1.4 Hz!)
```

This would be **faster than old software** while using less integration time!

---

## Status

- ⏸️ Waiting for old software code
- 🔄 Analysis in progress
- ⚠️ Do NOT reduce integration further until overhead fixed
- 💡 Real solution is fixing the 880ms overhead gap

**The good news**: We're NOT limited by hardware acquisition speed. There's huge optimization potential once we identify the bottleneck!
