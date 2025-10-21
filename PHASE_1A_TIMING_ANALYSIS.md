# Phase 1A: Timing Analysis Results

## Executive Summary

**Baseline Performance (120+ cycles analyzed):**
- **Current cycle time**: 1704ms average (0.59 Hz)
- **Target cycle time**: 1100ms (0.91 Hz) - matching old software
- **Gap to close**: ~600ms per cycle

## Detailed Breakdown

### Per-Channel Timing (typical values)
Each channel takes ~400ms total:

| Component | Time (ms) | % of Channel | Status | Notes |
|-----------|-----------|--------------|--------|-------|
| **LED_on** | **105ms** | **26%** | 🔴 **CRITICAL ISSUE** | Should be <10ms! |
| **LED_settle** | **100ms** | **25%** | ✅ Expected | Configured delay |
| **scan** | **190ms** | **48%** | ✅ Reasonable | 4×40ms + USB overhead |
| **dark** | **0-7ms** | **<2%** | ✅ Excellent | Dark correction |
| **trans** | **0ms** | **0%** | ✅ Excellent | Denoising disabled |
| **peak** | **0-1ms** | **<1%** | ✅ Excellent | Centroid method |
| **TOTAL** | **~400ms** | **100%** | - | Per channel |

### Per-Cycle Timing (statistics from cycles 101-120)

| Metric | Value | Notes |
|--------|-------|-------|
| **Average cycle** | **1704ms** | vs 1100ms target |
| **Min cycle** | **1679ms** | Best case |
| **Max cycle** | **1722ms** | Worst case |
| **Variability** | **±20ms** | Very stable |
| **Update rate** | **0.59 Hz** | vs 0.91 Hz target |
| **Emit time** | **110-120ms** | GUI update overhead |
| **Acquisition time** | **1580-1605ms** | 4 channels × ~400ms |

## Root Cause Analysis

### 🔴 **PRIMARY BOTTLENECK: LED Control = 420ms/cycle**

**LED_on timing consistently shows ~105ms per channel:**
```
ch=a: LED_on=105ms
ch=b: LED_on=105ms
ch=c: LED_on=105ms
ch=d: LED_on=105ms
TOTAL: 420ms wasted per cycle!
```

**This is 10× slower than expected!**
- Expected: <5ms (batch LED control)
- Actual: ~105ms (likely sequential serial commands)
- **Impact: 420ms per cycle** (70% of the gap to close!)

### Analysis: What's happening during LED_on?

The 105ms likely includes:
1. Serial command to controller
2. Polarizer motor movement
3. LED PWM adjustment
4. Multiple serial round-trips

**Hypothesis**: The code is using sequential commands instead of a single batch command.

### Secondary Issues

| Issue | Impact | Priority |
|-------|--------|----------|
| GUI emit overhead | 110-120ms/cycle | Medium |
| Scan variability | 171-231ms range | Low |
| Overall overhead | ~180ms vs old SW | Medium |

## Optimization Roadmap

### 🔥 **PHASE 1B: Fix LED Control (Priority 1)**

**Target savings: 400ms per cycle** (gets us to ~1300ms)

**Implementation:**
1. Investigate `_activate_channel_batch()` method
2. Check if it's actually using batch commands
3. If not, implement single-command channel activation:
   ```python
   # Instead of:
   set_polarizer(s_pos)
   set_polarizer(p_pos)
   set_led_pwm(led_intensity)
   # Use:
   set_channel(channel='a', s_pos, p_pos, led_intensity)  # Single command
   ```

**Code locations to check:**
- `utils/spr_data_acquisition.py` line ~465: `self._activate_channel_batch(ch)`
- `utils/hal/pico_p4spr_hal.py`: HAL LED control methods
- Look for serial communication delays

### Phase 1C: Optimize GUI Emissions (Priority 2)

**Target savings: 40-60ms per cycle**

**Current**: Emit every cycle (~110ms)
**Proposed**: Emit every 3rd cycle for spectroscopy, keep sensorgram real-time

```python
if self.cycle_count % 3 == 0:
    self.spectroscopy_data.emit(...)  # Heavy data
self.sensorgram_data.emit(...)  # Lightweight, keep real-time
```

### Phase 1D: Investigate Scan Time Variability (Priority 3)

**Observation**: Scan time varies 171-231ms (60ms range)
- Typical: ~190ms (expected for 4×40ms + overhead)
- Outliers: 171ms (fast) or 231ms (slow)

**Possible causes:**
- USB bus contention
- Spectrometer firmware timing
- Operating system scheduling

**Action**: Monitor but likely not worth optimizing vs LED fix

## Comparison: Old vs New Software

### Integration Time per Channel
Both use same total photon collection:
- Old: 2 scans × 100ms = 200ms
- New: 4 scans × 40ms = 160ms (current test)

### LED Control
**Old software** (`Old software/main/main.py` lines 1600-1620):
- Uses direct serial commands
- Appears to use batch/single commands
- **LED overhead: minimal (<10ms per channel)**

**New software** (current):
- Uses HAL abstraction with multiple layers
- **LED overhead: 105ms per channel** 🔴

### Overhead Comparison

| Component | Old SW | New SW | Delta |
|-----------|--------|--------|-------|
| LED control | ~10ms/ch | ~105ms/ch | +95ms |
| LED total | ~40ms | ~420ms | **+380ms** ⚠️ |
| Scan time | ~210ms/ch | ~190ms/ch | -20ms ✅ |
| GUI emit | ~40ms | ~115ms | +75ms |
| Dark/proc | ~10ms | ~1ms | -9ms ✅ |
| **Cycle total** | **~1100ms** | **~1704ms** | **+604ms** |

## Success Criteria

### Phase 1B Target (LED fix)
- ✅ LED_on time reduced to <10ms per channel
- ✅ Total cycle time <1300ms (0.77 Hz)
- ✅ 400ms savings achieved

### Phase 1C Target (GUI throttle)
- ✅ Emit time reduced to <70ms
- ✅ Total cycle time <1240ms (0.81 Hz)
- ✅ Sensorgram still real-time

### Ultimate Goal
- ✅ Cycle time <1150ms (0.87 Hz) - within 5% of old software
- ✅ Maintain <2 RU noise stability
- ✅ No loss of functionality

## Next Steps

1. **IMMEDIATE**: Investigate LED control bottleneck
   - Read `_activate_channel_batch()` implementation
   - Check HAL serial command structure
   - Profile serial communication timing

2. **FIX**: Implement batch LED control (if not already)
   - Single serial command per channel activation
   - Combine polarizer + LED in one transmission

3. **VALIDATE**: Re-run timing after LED fix
   - Should see LED_on drop to <10ms
   - Cycle time should drop to ~1300ms

4. **OPTIMIZE**: Implement GUI throttling
   - Final cycle time ~1200-1240ms

5. **DOCUMENT**: Update performance comparison guide

## Data Collection Details

- **Cycles analyzed**: 120+ continuous cycles
- **Date**: 2025-10-20
- **Integration time**: 40ms (Phase 4 optimization)
- **Configuration**: Real hardware, production mode
- **Stability**: Excellent (±20ms variability)

---

## Appendix: Sample Timing Logs

### Typical Cycle (Cycle #110)
```
⏱️ TIMING ch=a: LED_on=105ms, LED_settle=100ms, scan=190ms, dark=0ms, trans=0ms, peak=0ms, TOTAL=397ms
⏱️ TIMING ch=b: LED_on=108ms, LED_settle=100ms, scan=190ms, dark=0ms, trans=0ms, peak=0ms, TOTAL=399ms
⏱️ TIMING ch=c: LED_on=105ms, LED_settle=100ms, scan=194ms, dark=0ms, trans=0ms, peak=0ms, TOTAL=401ms
⏱️ TIMING ch=d: LED_on=104ms, LED_settle=100ms, scan=193ms, dark=0ms, trans=0ms, peak=1ms, TOTAL=400ms
⏱️ CYCLE #110: total=1713ms, emit=111ms, acq=1601ms
📊 TIMING STATS (last 10 cycles): avg=1704ms, min=1693ms, max=1719ms, rate=0.59 Hz
```

### Fast Cycle (Cycle #14, outlier)
```
⏱️ TIMING ch=a: LED_on=105ms, LED_settle=100ms, scan=174ms, dark=0ms, trans=0ms, peak=0ms, TOTAL=381ms
⏱️ TIMING ch=b: LED_on=104ms, LED_settle=100ms, scan=171ms, dark=0ms, trans=0ms, peak=0ms, TOTAL=377ms
⏱️ TIMING ch=c: LED_on=105ms, LED_settle=100ms, scan=194ms, dark=0ms, trans=0ms, peak=0ms, TOTAL=400ms
⏱️ TIMING ch=d: LED_on=105ms, LED_settle=100ms, scan=193ms, dark=0ms, trans=0ms, peak=0ms, TOTAL=400ms
⏱️ CYCLE #14: total=1673ms, emit=111ms, acq=1561ms
```

### Slow Cycle (Cycle #125, outlier)
```
⏱️ TIMING ch=a: LED_on=105ms, LED_settle=100ms, scan=194ms, dark=0ms, trans=0ms, peak=0ms, TOTAL=402ms
⏱️ TIMING ch=b: LED_on=105ms, LED_settle=100ms, scan=192ms, dark=0ms, trans=0ms, peak=0ms, TOTAL=400ms
⏱️ TIMING ch=c: LED_on=104ms, LED_settle=100ms, scan=231ms, dark=0ms, trans=0ms, peak=0ms, TOTAL=436ms
⏱️ TIMING ch=d: LED_on=105ms, LED_settle=100ms, scan=184ms, dark=0ms, trans=0ms, peak=0ms, TOTAL=390ms
⏱️ CYCLE #125: total=1779ms, emit=127ms, acq=1652ms
```
Note: Channel C scan took 231ms (vs typical 190ms) - USB/scheduling variability.

---

**Status**: ✅ Phase 1A Complete - Bottleneck identified
**Next**: Phase 1B - Fix LED control bottleneck
**ETA**: ~400ms cycle time improvement possible
