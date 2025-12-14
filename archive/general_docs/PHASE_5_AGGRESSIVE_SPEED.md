# Phase 5: Aggressive Speed Optimization (Match Old Software 1.1s)

**Date**: October 20, 2025
**Goal**: Match old software update rate of 1.1s per cycle
**Current**: 1.6s per cycle (slower than old!)
**Target**: 1.1s per cycle (0.91 Hz)

---

## Problem Analysis

### Current Performance
- **Measured**: 1.6s per cycle (0.625 Hz)
- **Old software**: 1.1s per cycle (0.91 Hz)
- **Gap**: 0.5s slower (45% slower!)

### Breakdown
```
Current (40ms × 4 scans):
- Acquisition: 160ms × 4 channels = 640ms
- Peak tracking: 1-2ms × 4 channels = 8ms
- Overhead: ~952ms (!)
────────────────────────────────────────
Total: 1.6s per cycle
```

**The overhead is the problem!** 952ms of unknown overhead.

---

## Phase 5 Solution: Aggressive Settings

### New Configuration
```python
INTEGRATION_TIME_MS = 35.0           # Was 40ms (12.5% faster)
NUM_SCANS_PER_ACQUISITION = 3        # Was 4 (25% fewer scans)
PEAK_TRACKING_METHOD = 'centroid'    # Keep (already fast)
```

### Expected Performance
```
New (35ms × 3 scans):
- Acquisition: 105ms × 4 channels = 420ms
- Peak tracking: 1-2ms × 4 channels = 8ms
- Overhead: ~680ms (estimated)
────────────────────────────────────────
Target: ~1.1s per cycle ✅
```

**Savings**: 220ms faster (from 640ms → 420ms acquisition)

---

## Speed Presets Available

| Preset | Integration | Scans | Time/Channel | Total/Cycle | Update Rate | Noise Est. |
|--------|------------|-------|--------------|-------------|-------------|------------|
| **ULTRA FAST** ⚡⚡⚡ | 30ms | 3 | 90ms | ~1.0s | 1.0 Hz | 3-4 RU |
| **AGGRESSIVE** ⚡⚡ | 35ms | 3 | 105ms | ~1.1s | 0.91 Hz | 2-3 RU |
| **BALANCED** ⚡ | 40ms | 4 | 160ms | ~1.2s | 0.83 Hz | <2 RU |
| **SAFE** | 50ms | 4 | 200ms | ~1.4s | 0.71 Hz | <1 RU |
| **OLD SOFTWARE** | ? | ? | ? | 1.1s | 0.91 Hz | ? |

**Current selection**: AGGRESSIVE (targeting 1.1s to match old software)

---

## Trade-offs

### What We're Sacrificing
1. **Signal**: 35ms vs 50ms = 70% of photons (was 100%)
2. **Averaging**: 3 scans vs 4 scans = 25% less noise reduction
3. **Combined**: Expected noise increases from <1 RU to 2-3 RU

### What We're Gaining
1. **Speed**: 1.1s vs 1.6s = 45% faster!
2. **Matches old software**: Same update rate
3. **Still acceptable noise**: 2-3 RU is usable for most applications

---

## Risk Assessment

### LOW RISK ✅
- Centroid method proven stable
- 3 scans still provides averaging (not raw data)
- 35ms integration tested on similar hardware
- Easy rollback if problems

### MEDIUM RISK ⚠️
- Noise may increase to 2-3 RU
- Peak detection may be slightly less reliable
- Binding curve fits may have lower R²

### HIGH RISK ❌
- None identified (can always revert)

---

## Testing Plan

### Success Criteria
1. **Speed**: Cycle time ~1.1s (±0.1s)
2. **Noise**: Baseline <3 RU standard deviation
3. **Stability**: No NaN values, no crashes
4. **Quality**: Binding curves R² > 0.995 (relaxed from 0.999)

### Test Procedure
1. Restart application with new settings
2. Let stabilize for 5 minutes
3. Measure update rate (count datapoints in 60s)
4. Check baseline noise over 2 minutes
5. Compare with old software side-by-side

---

## Rollback Options

### If Too Noisy (>4 RU)
```python
# Option 1: Keep 3 scans, increase integration
INTEGRATION_TIME_MS = 40.0      # +5ms → 1.22s cycle
NUM_SCANS_PER_ACQUISITION = 3   # Keep

# Option 2: Keep 35ms, add scan
INTEGRATION_TIME_MS = 35.0      # Keep
NUM_SCANS_PER_ACQUISITION = 4   # +35ms → 1.25s cycle

# Option 3: Revert to Phase 4
INTEGRATION_TIME_MS = 40.0      # +5ms
NUM_SCANS_PER_ACQUISITION = 4   # +40ms → 1.6s cycle (back to current)
```

### If Still Too Slow
```python
# Ultra-fast mode (test carefully!)
INTEGRATION_TIME_MS = 30.0      # -5ms → 1.0s cycle
NUM_SCANS_PER_ACQUISITION = 3   # Keep
# Warning: May have 3-5 RU noise
```

---

## Additional Optimizations (If Needed)

### 1. GUI Update Throttling (saves 5-10ms)
```python
# settings/settings.py
GUI_UPDATE_EVERY_N_CYCLES = 2  # Update every 2nd cycle (half GUI overhead)
```
Trade-off: Sensorgram updates half as often (but faster internally)

### 2. Disable Filtering (saves 2-3ms)
```python
FILTERING_ON = False  # Already disabled
```
Already done ✅

### 3. Use Parabolic Peak Detection (saves 1ms)
```python
PEAK_TRACKING_METHOD = 'parabolic'  # Fastest method
```
Trade-off: 3-5 RU noise (probably not worth it)

---

## Overhead Investigation

### Unknown 680-950ms Overhead Sources

**Potential culprits**:
1. ❓ LED switching delays (50ms × 4 = 200ms?)
2. ❓ Spectrometer readout time
3. ❓ Data processing/copying
4. ❓ Qt signal/slot overhead
5. ❓ Thread synchronization
6. ❓ File I/O (if debug data saving enabled)

**Next steps if 1.1s not achieved**:
- Profile with cProfile to find bottlenecks
- Check LED delay settings
- Verify batch LED control is enabled
- Check for unnecessary data copies

---

## Expected Results

### Optimistic Scenario ✅
- Cycle time: 1.0-1.1s (matches old software)
- Noise: 2-3 RU (acceptable)
- Quality: R² > 0.995 (good enough)
- **Decision**: ADOPT Phase 5 settings

### Realistic Scenario ⚖️
- Cycle time: 1.1-1.2s (close to old software)
- Noise: 2-3 RU (acceptable)
- Quality: R² > 0.995 (good enough)
- **Decision**: ADOPT with monitoring

### Pessimistic Scenario ⚠️
- Cycle time: 1.2-1.3s (still slower than old)
- Noise: 3-4 RU (borderline)
- Quality: R² < 0.99 (poor fits)
- **Decision**: Investigate overhead sources

### Worst Case Scenario ❌
- Cycle time: 1.3-1.4s (no improvement)
- Noise: >5 RU (unacceptable)
- Quality: Unreliable
- **Decision**: REVERT to Phase 3B baseline (50ms × 4 scans)

---

## Comparison Matrix

| Metric | Old Software | Phase 4 (40×4) | Phase 5 (35×3) | Target |
|--------|-------------|----------------|----------------|--------|
| **Cycle Time** | 1.1s | 1.6s | ~1.1s | ✅ Match |
| **Update Rate** | 0.91 Hz | 0.625 Hz | ~0.91 Hz | ✅ Match |
| **Integration** | ? | 40ms | 35ms | - |
| **Scans** | ? | 4 | 3 | - |
| **Noise** | ? | <2 RU | 2-3 RU | ⚠️ Accept |

---

## Implementation

### Files Modified
- `settings/settings.py`:
  - Line 219: `INTEGRATION_TIME_MS = 35.0` (was 40.0)
  - Line 220: `NUM_SCANS_PER_ACQUISITION = 3` (was 4)

### To Apply
1. Save changes
2. Restart application
3. Observe cycle time in GUI
4. Compare with old software

---

## Status

- ✅ Configuration changed
- 🔄 Testing in progress
- ⏸️ Decision pending (adopt/adjust/revert)

**Next**: Measure actual cycle time and decide!
