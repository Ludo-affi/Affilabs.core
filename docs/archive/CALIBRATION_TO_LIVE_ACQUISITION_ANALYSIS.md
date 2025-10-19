# Calibration → Live Acquisition Data Flow Analysis

**Date**: October 18, 2025
**Purpose**: Complete end-to-end analysis from calibration to sensorgram display
**Goal**: Identify inconsistencies, optimization opportunities, and areas to tighten/clarify

---

## 🔍 Executive Summary

### ✅ **What's Working Well**
1. **200ms acquisition target** consistently applied in calibration
2. **Batch LED control** implemented for 15× speedup
3. **Spectral filtering** applied at acquisition (no resampling needed)
4. **Dark correction** with afterglow compensation
5. **Sequential channel updates** providing ~1.2 Hz perceived update rate

### ⚠️ **Critical Inconsistencies Found**

| Issue | Location | Impact | Priority |
|-------|----------|--------|----------|
| **Legacy scan calculation in Steps 3-4** | `spr_calibrator.py` lines 2196, 2494 | Using `MAX_READ_TIME_MS / integration` instead of `calculate_dynamic_scans()` | **HIGH** |
| **settings.py still defines 1.0s cycle time** | `settings.py` line 101 | `ACQUISITION_CYCLE_TIME = 1.0` conflicts with 200ms target | **HIGH** |
| **Live mode uses ACQUISITION_CYCLE_TIME** | `spr_state_machine.py` line 379 | Calculates scans based on 1.0s instead of 0.2s | **CRITICAL** |
| **Deprecated constants still used** | Multiple locations | `REF_SCANS`, `CYCLE_TIME` referenced but deprecated | **MEDIUM** |

---

## 📊 Complete Data Flow Map

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CALIBRATION PHASE                                │
└─────────────────────────────────────────────────────────────────────────┘

Step 1: Dark Noise (LEDs OFF)
├─ Integration: Not yet set
├─ Scans: DARK_NOISE_SCANS (30)
├─ Purpose: Baseline measurement
└─ ✅ Consistent

Step 2: Wavelength Calibration
├─ Integration: 0.1s (hardcoded)
├─ Scans: 1
├─ Purpose: Establish pixel-to-wavelength mapping
└─ ✅ Consistent

Step 3: Integration Time Optimization (LEGACY)
├─ Integration: Adaptive (min_int → max_int)
├─ ⚠️ Scans: int(MAX_READ_TIME_MS / integration) = int(50ms / 100ms) ≈ 0 → 1
│   └─ PROBLEM: Uses MAX_READ_TIME_MS (50ms) instead of target_cycle_time (200ms)
├─ Purpose: Find optimal integration for weakest channel
└─ ❌ INCONSISTENT - Not using calculate_dynamic_scans()

Step 4: Integration Time Validation
├─ Integration: From Step 3
├─ ⚠️ Scans: int(MAX_READ_TIME_MS / integration)
│   └─ PROBLEM: Same as Step 3 - not using calculate_dynamic_scans()
├─ Purpose: Validate all 4 channels
└─ ❌ INCONSISTENT - Should use calculate_dynamic_scans()

Step 5: Dark Noise Re-measurement
├─ Integration: Final from Step 4
├─ Scans: DARK_NOISE_SCANS (30)
├─ Purpose: Dark noise at final integration time
└─ ✅ Consistent

Step 6: LED Intensity Calibration (Skipped)
├─ LED values copied from Step 4
└─ ✅ Efficient optimization

Step 7: Reference Signal Measurement
├─ Integration: Final from Step 4
├─ ✅ Scans: calculate_dynamic_scans(integration) → 1-2 scans for 150ms
│   └─ Uses 200ms target correctly!
├─ Purpose: S-mode references with afterglow correction
└─ ✅ CONSISTENT - Uses calculate_dynamic_scans()

Step 8: Validation
├─ Uses Step 7 reference signals
└─ ✅ Consistent

┌─────────────────────────────────────────────────────────────────────────┐
│                    TRANSITION TO LIVE MODE                               │
└─────────────────────────────────────────────────────────────────────────┘

spr_state_machine.py: _sync_calibration_to_live()
├─ ❌ Line 379: calculated_scans = int(ACQUISITION_CYCLE_TIME / live_integration)
│   └─ PROBLEM: Uses ACQUISITION_CYCLE_TIME = 1.0s (should be 0.2s)
├─ Clamps to 5-50 scans
├─ With 150ms integration: 1.0 / 0.150 = 6.67 → 7 scans
│   └─ RESULT: Takes 7 × 150ms = 1,050ms (5× slower than target!)
└─ ❌ CRITICAL: Undoes all 200ms optimization!

┌─────────────────────────────────────────────────────────────────────────┐
│                     LIVE DATA ACQUISITION                                │
└─────────────────────────────────────────────────────────────────────────┘

spr_data_acquisition.py: grab_data()
├─ Per-channel cycle:
│   ├─ LED activation (batch): <1ms
│   ├─ LED stabilization: 50ms (LED_DELAY)
│   ├─ ❌ Spectrum acquisition: num_scans × integration
│   │   └─ If num_scans=7, integration=150ms → 1,050ms total
│   ├─ Dark correction: ~2ms
│   ├─ Transmittance calc: ~2ms
│   └─ Peak finding: ~5ms
│
├─ 4-channel cycle: 4 × ~1,120ms = 4,480ms (0.22 Hz) ❌
│   └─ PROBLEM: Should be ~824ms (1.2 Hz) with 200ms target
│
└─ ❌ CRITICAL: Live mode performance degraded by wrong scan calculation

┌─────────────────────────────────────────────────────────────────────────┐
│                      SENSORGRAM DISPLAY                                  │
└─────────────────────────────────────────────────────────────────────────┘

widgets/graphs.py: SensorgramGraph.update()
├─ Receives: lambda_values, lambda_times (sequential per-channel)
├─ Update pattern:
│   ├─ t=0.0s: Channel A updates
│   ├─ t=1.1s: Channel B updates (should be 0.2s!) ❌
│   ├─ t=2.2s: Channel C updates (should be 0.4s!) ❌
│   └─ t=3.3s: Channel D updates (should be 0.6s!) ❌
│
├─ Perceived update rate: ~0.9 Hz (should be ~4.9 Hz) ❌
├─ Full cycle: 4.48s (should be 0.82s) ❌
│
└─ ❌ User sees 5× slower sensorgram updates than designed

```

---

## 🔥 Critical Issues Requiring Immediate Fix

### **Issue #1: Live Mode Scan Calculation (CRITICAL)**

**Location**: `utils/spr_state_machine.py`, lines 373-387

**Problem**:
```python
# CURRENT (WRONG):
from settings import ACQUISITION_CYCLE_TIME  # = 1.0s
calculated_scans = int(ACQUISITION_CYCLE_TIME / live_integration_seconds)
# With 150ms integration: 1.0 / 0.150 = 6.67 → 7 scans (1,050ms total) ❌
```

**Should be**:
```python
# CORRECT:
from utils.spr_calibrator import calculate_dynamic_scans
self.num_scans = calculate_dynamic_scans(live_integration_seconds)
# With 150ms integration: 1 scan (150ms total) ✅
```

**Impact**:
- Live mode **5× slower** than calibration (1,050ms vs 200ms per channel)
- Sensorgram updates at **0.22 Hz** instead of **1.2 Hz**
- Completely negates 200ms optimization work

**Fix Complexity**: Simple import and function call replacement

---

### **Issue #2: Legacy Scan Calculation in Steps 3-4**

**Locations**:
- `utils/spr_calibrator.py`, line 2196 (Step 3 - legacy integration time calibration)
- `utils/spr_calibrator.py`, line 2494 (Step 4 - P-mode calibration)

**Problem**:
```python
# CURRENT (WRONG):
MAX_READ_TIME_MS = 50  # Only 50ms target (way too fast!)
self.state.num_scans = int(MAX_READ_TIME_MS / (self.state.integration * MS_TO_SECONDS))
# With 150ms integration: 50ms / 150ms = 0.33 → 1 scan (by accident correct!)
# But with 50ms integration: 50ms / 50ms = 1 scan (should be 4 scans!)
```

**Should be**:
```python
# CORRECT:
self.state.num_scans = calculate_dynamic_scans(self.state.integration)
# With 50ms integration: 4 scans (200ms total) ✅
# With 150ms integration: 1 scan (150ms total) ✅
```

**Impact**:
- Steps 3-4 **accidentally work** with long integration times
- But **fail to average properly** with short integration times
- **Inconsistent** with Step 7 which uses correct function

**Fix Complexity**: Simple function call replacement (2 lines)

---

### **Issue #3: settings.py Defines Wrong Cycle Time**

**Location**: `settings/settings.py`, lines 101-102

**Problem**:
```python
ACQUISITION_CYCLE_TIME = 1.0 / ACQUISITION_FREQUENCY  # 1.0 second for full cycle ❌
TIME_PER_CHANNEL = ACQUISITION_CYCLE_TIME / 4  # 0.25 seconds per channel ❌
```

**Should be**:
```python
# Option A: Redefine constants to match 200ms target
ACQUISITION_CYCLE_TIME = 0.8  # 0.8 seconds for full 4-channel cycle (200ms/channel)
TIME_PER_CHANNEL = 0.2  # 200ms per channel (matches calculate_dynamic_scans target)

# Option B: Deprecate and point to calculate_dynamic_scans()
# DEPRECATED: Acquisition time is now DYNAMIC based on integration time
# Use calculate_dynamic_scans(integration_time) for per-channel timing
# Target: ≤200ms per channel for responsive sensorgram
```

**Impact**:
- Other code imports `ACQUISITION_CYCLE_TIME` and gets wrong value
- Live mode uses this wrong value to calculate scans
- Creates confusion between "design target" (200ms) and "legacy constant" (1000ms)

**Fix Complexity**: Medium (need to audit all imports of this constant)

---

## 🎯 Recommended Fixes (Priority Order)

### **Priority 1: Fix Live Mode Scan Calculation (CRITICAL)**

**File**: `utils/spr_state_machine.py`

**Change lines 373-387**:
```python
# OLD (WRONG):
from settings import ACQUISITION_CYCLE_TIME, LIVE_MODE_INTEGRATION_FACTOR
integration_seconds = self.calib_state.integration
live_integration_seconds = integration_seconds * LIVE_MODE_INTEGRATION_FACTOR
calculated_scans = int(ACQUISITION_CYCLE_TIME / live_integration_seconds)
self.num_scans = max(5, min(50, calculated_scans))

# NEW (CORRECT):
from settings import LIVE_MODE_INTEGRATION_FACTOR
from utils.spr_calibrator import calculate_dynamic_scans
integration_seconds = self.calib_state.integration
live_integration_seconds = integration_seconds * LIVE_MODE_INTEGRATION_FACTOR
self.num_scans = calculate_dynamic_scans(live_integration_seconds)  # ✅ Uses 200ms target
```

**Testing**:
- With 150ms integration: Should get 1 scan (150ms per channel, 600ms full cycle)
- With 100ms integration: Should get 2 scans (200ms per channel, 800ms full cycle)
- Sensorgram should update at ~1.2-1.5 Hz

---

### **Priority 2: Uniformize Step 3-4 Scan Calculation**

**File**: `utils/spr_calibrator.py`

**Change line 2196** (Step 3):
```python
# OLD:
self.state.num_scans = int(MAX_READ_TIME_MS / (self.state.integration * MS_TO_SECONDS))

# NEW:
self.state.num_scans = calculate_dynamic_scans(self.state.integration)
```

**Change line 2494** (Step 4 P-mode):
```python
# OLD:
self.state.num_scans = int(MAX_READ_TIME_MS / (self.state.integration * MS_TO_SECONDS))

# NEW:
self.state.num_scans = calculate_dynamic_scans(self.state.integration)
```

**Remove line 141** (obsolete constant):
```python
# DELETE THIS LINE:
MAX_READ_TIME_MS = 50  # No longer needed
```

**Testing**:
- Calibration should take similar time as before (Steps 3-4 currently work by accident)
- But now consistent with Step 7 methodology
- Better averaging with short integration times

---

### **Priority 3: Update settings.py Documentation**

**File**: `settings/settings.py`

**Change lines 101-110**:
```python
# OLD:
ACQUISITION_CYCLE_TIME = 1.0 / ACQUISITION_FREQUENCY  # 1.0 second for full cycle
TIME_PER_CHANNEL = ACQUISITION_CYCLE_TIME / 4  # 0.25 seconds per channel
# REF_SCANS = int(ACQUISITION_CYCLE_TIME / integration_time) - calculated at runtime
CYCLE_TIME = 1.3  # DEPRECATED

# NEW:
# DEPRECATED: Acquisition timing is now DYNAMIC based on integration time
# Use calculate_dynamic_scans(integration_time) from utils.spr_calibrator
# Target: ≤200ms per channel for responsive sensorgram updates
#
# Legacy constants (kept for backward compatibility, but should not be used):
ACQUISITION_CYCLE_TIME = 1.0 / ACQUISITION_FREQUENCY  # DEPRECATED - use calculate_dynamic_scans()
TIME_PER_CHANNEL = ACQUISITION_CYCLE_TIME / 4  # DEPRECATED - target is now 200ms/channel
CYCLE_TIME = 1.3  # DEPRECATED - use calculate_dynamic_scans()
```

**Add new constants**:
```python
# Modern timing architecture (200ms per channel target)
TARGET_CHANNEL_TIME_MS = 200  # Target acquisition time per channel (milliseconds)
TARGET_CHANNEL_TIME_S = 0.2   # Target acquisition time per channel (seconds)
```

**Testing**:
- No functional changes (just documentation)
- Prevents future confusion

---

### **Priority 4: Audit All Imports of ACQUISITION_CYCLE_TIME**

**Search results** show only 2 files import it:
1. ✅ `utils/spr_calibrator.py` - Imports but never uses it (only for Step 7 comment)
2. ❌ `utils/spr_state_machine.py` - Uses it incorrectly (Priority 1 fix addresses this)

**Action**: After Priority 1 fix, remove unused import from `spr_calibrator.py`

---

## 📈 Expected Performance After Fixes

### **Current Performance (BROKEN)**

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Per-channel time | 1,120ms | 200ms | ❌ 5.6× slower |
| Full cycle time | 4,480ms | 800ms | ❌ 5.6× slower |
| Sensorgram update rate | 0.22 Hz | 1.2 Hz | ❌ 5.5× slower |
| Perceived responsiveness | Poor | Excellent | ❌ |

### **After Priority 1 Fix (CORRECTED)**

| Metric | After Fix | Target | Status |
|--------|-----------|--------|--------|
| Per-channel time | 206ms | 200ms | ✅ 3% over (acceptable) |
| Full cycle time | 824ms | 800ms | ✅ 3% over (acceptable) |
| Sensorgram update rate | 1.21 Hz | 1.2 Hz | ✅ On target |
| Perceived responsiveness | Excellent | Excellent | ✅ |

**Performance Improvement**: **5.4× faster sensorgram updates** 🚀

---

## 🧪 Testing Strategy

### **Test 1: Calibration Scan Counts**

Monitor logs during calibration:

```
Expected output after Priority 2 fix:
Step 3: Integration optimization → num_scans via calculate_dynamic_scans()
Step 4: Validation → num_scans via calculate_dynamic_scans()
Step 7: Reference signals → num_scans via calculate_dynamic_scans()
```

### **Test 2: Live Mode Scan Counts**

Monitor logs during live acquisition:

```
Expected output after Priority 1 fix:
✅ Dynamic scan count: 1 scans (integration=150ms, total time=0.15s)
📊 Plotting data: 4 total points (one per channel, every ~0.82s)
```

### **Test 3: Sensorgram Responsiveness**

Visual test:
1. Start live acquisition
2. Inject sample (binding event)
3. **Measure time** from injection to visible peak on sensorgram
4. Should see update **within 1 second** (currently 4+ seconds)

### **Test 4: Data Quality**

Verify noise levels acceptable with 1 scan instead of 7:
- Peak position standard deviation should be <0.1 nm
- Baseline drift should be <1 RU/min
- If noise too high, increase target from 200ms to 300ms in `calculate_dynamic_scans()`

---

## 🔍 Additional Optimization Opportunities

### **Low Priority (Nice-to-Have)**

1. **Parallel Channel Processing** (Advanced)
   - Current: Sequential A→B→C→D
   - Potential: Parallel acquisition if hardware supports
   - Gain: 4× faster (theoretical)
   - Complexity: High (hardware dependent)

2. **Adaptive Scan Count Based on Noise**
   - Current: Fixed scan count per integration time
   - Potential: Monitor peak position variance, reduce scans if noise low
   - Gain: 10-30% faster in stable conditions
   - Complexity: Medium

3. **GPU-Accelerated Peak Finding**
   - Current: CPU numpy operations
   - Potential: cupy for GPU acceleration
   - Gain: 2-5× faster peak finding
   - Complexity: High (requires CUDA)

---

## 🎓 Key Takeaways

### **Root Cause**
The 200ms optimization was **only half-implemented**:
- ✅ Calibration Step 7 uses `calculate_dynamic_scans()` (correct)
- ❌ Live mode uses `ACQUISITION_CYCLE_TIME` constant (wrong)
- ❌ Steps 3-4 use `MAX_READ_TIME_MS` constant (inconsistent)

### **Why This Happened**
1. `calculate_dynamic_scans()` was added later (October optimization)
2. Live mode code wasn't updated to use new function
3. Steps 3-4 still use legacy formula (works by accident with long integration)

### **Solution**
Replace all hardcoded timing calculations with `calculate_dynamic_scans()`:
- ✅ Single source of truth (200ms target in one place)
- ✅ Consistent across calibration and live modes
- ✅ Easy to adjust target if needed (change one default parameter)

---

## 📋 Implementation Checklist

- [ ] **Priority 1**: Fix live mode scan calculation (spr_state_machine.py)
- [ ] **Priority 2**: Uniformize Steps 3-4 scan calculation (spr_calibrator.py)
- [ ] **Priority 3**: Update settings.py documentation
- [ ] **Priority 4**: Remove unused imports
- [ ] **Test**: Run full calibration, verify scan counts in logs
- [ ] **Test**: Run live acquisition, measure sensorgram update rate
- [ ] **Test**: Visual responsiveness test with sample injection
- [ ] **Test**: Verify noise levels acceptable with reduced averaging
- [ ] **Document**: Update SENSORGRAM_LATENCY_ANALYSIS.md with new performance
- [ ] **Commit**: Single atomic commit with all fixes

---

## 🚀 Expected User Experience After Fix

**Before** (Current):
> "The sensorgram feels sluggish. When I inject a sample, it takes 4-5 seconds before I see anything happen on the graph. Real-time monitoring is frustrating."

**After** (Fixed):
> "Perfect! The sensorgram updates almost instantly - I can see binding kinetics happen in real-time. The system feels snappy and responsive. This is exactly what I needed for monitoring fast-binding events."

---

**Status**: Ready for implementation
**Estimated Time**: 30 minutes (code changes) + 30 minutes (testing)
**Risk**: Low (well-defined changes, easy to revert if issues)
**Benefit**: 5.4× faster sensorgram updates, consistent timing architecture
