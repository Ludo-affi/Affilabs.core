# Calibration Acceleration Guide

## Overview
Analysis of all timing parameters in the calibration process and opportunities for speed optimization.

## Current Timing Parameters

### 1. LED Stabilization Delays

#### settings.py - LED_DELAY = 0.1s
**Location:** `settings/settings.py` line 92
```python
LED_DELAY = 0.1  # led-stabilization delay
```

**Usage Locations:**
- Step 3.1: Weakest channel identification (4 channels × 0.1s = **0.4s**)
- Step 3.2: Integration time optimization (~15 iterations × 0.1s = **1.5s**)
- Step 3.3: Validation (4 channels × 0.1s = **0.4s**)
- Step 5: Dark noise (4 channels × 0.1s = **0.4s**)
- Step 6: S-mode reference signals (4 channels × 0.1s = **0.4s**)
- Step 8: P-mode LED boost (4 channels × 2 measurements × 0.1s = **0.8s**)
- Step 8: P-mode reference signals (4 channels × 0.1s = **0.4s**)

**Total Impact:** ~4.3 seconds per calibration

**Optimization:**
```python
LED_DELAY = 0.05  # Reduce to 50ms (50% speedup)
```
- **Risk:** Low - LEDs usually stabilize within 50ms
- **Benefit:** Save ~2.2 seconds
- **Recommendation:** ✅ Safe to reduce to 0.05s

---

#### spr_calibrator.py - ADAPTIVE_STABILIZATION_DELAY = 0.15s ✅ Already Optimized
**Location:** `utils/spr_calibrator.py` line 77
```python
ADAPTIVE_STABILIZATION_DELAY = 0.15  # LED stabilization delay (optimized for speed)
```

**Usage:** Step 4 - Adaptive LED calibration (4 channels × ~6 iterations × 0.15s = **3.6s**)

**Status:** Already optimized from 0.3s → 0.15s (50% faster)

---

### 2. Mode Switching Delays

#### Polarizer Rotation Delay = 0.4s
**Locations:**
- Line 1059: S-mode initialization - `time.sleep(0.5)` → **Can reduce to 0.3s**
- Line 1564: S-mode for reference signals - `time.sleep(0.4)` → **Keep at 0.4s**
- Line 1677: P-mode switch - `time.sleep(0.4)` → **Keep at 0.4s**
- Line 2123: P-mode switch (main sequence) - `time.sleep(0.4)` → **Keep at 0.4s**

**Total Impact:** 1.6 seconds (3 × 0.4s + 1 × 0.5s)

**Optimization:**
```python
# Line 1059: Initial S-mode setup
time.sleep(0.3)  # Reduce from 0.5s → save 0.2s
```

**Recommendation:** ⚠️ Moderate risk - polarizer needs time to rotate
- Can try 0.3s for initial setup
- Keep 0.4s for actual S↔P switches during measurement

---

### 3. Reference Signal Averaging

#### REF_SCANS = 20 scans
**Location:** `settings/settings.py` line 90
```python
REF_SCANS = 20  # number of scans to average in reference measurement
```

**Usage:**
- Step 6: S-mode reference signals (4 channels × 20 scans × integration_time)
  - At 50ms integration: 4 × 20 × 0.05s = **4.0 seconds**
  - At 100ms integration: 4 × 20 × 0.1s = **8.0 seconds**

**Impact:** Major bottleneck for reference signal measurement

**Optimization Options:**
```python
REF_SCANS = 10  # Reduce to 10 scans (50% speedup)
REF_SCANS = 15  # Conservative reduction (25% speedup)
```

**Trade-off Analysis:**
- ✅ **Benefit:** Save 2-4 seconds at typical integration times
- ⚠️ **Risk:** Lower SNR in reference signals (affects baseline quality)
- 📊 **Recommendation:** Start with 15 scans (25% faster), test quality

---

### 4. Dark Noise Scans

#### Dark noise averaging logic
**Location:** Lines 1484-1500 (approximate)

**Current Logic:**
```python
if integration < INTEGRATION_STEP_THRESHOLD:  # 0.1s threshold
    dark_scans = DARK_SCANS  # 20 scans
else:
    dark_scans = DARK_SCANS / 2  # 10 scans
```

**Impact:**
- At 50ms integration: 20 scans × 0.05s = **1.0 second**
- At 100ms integration: 10 scans × 0.1s = **1.0 second**

**Optimization:**
```python
# Reduce dark scan count
DARK_SCANS = 10  # Down from 20 (50% speedup)
# Then adaptive logic gives: 10 scans or 5 scans
```

**Recommendation:** ✅ Safe - dark noise is very stable, doesn't need 20 scans

---

### 5. Integration Time Search (Step 3.2)

#### Binary search iterations
**Location:** Lines 1140-1300 (approximate)

**Current:** Binary search with variable iterations (~10-15 iterations)

**Each iteration costs:**
- LED stabilization: 0.1s (LED_DELAY)
- Detector read: ~0.05s (integration time)
- Processing: <0.01s

**Total:** 10-15 iterations × 0.15s = **1.5-2.25 seconds**

**Optimization:** Already reasonably fast, binary search is efficient

**Could optimize:**
- Start closer to expected value (e.g., 100ms instead of 50% of range)
- Reduce convergence tolerance (accept wider range)

---

### 6. Small Delays (Low Impact)

#### Various 0.1s delays
- Line 1076: After integration set - `time.sleep(0.1)`
- Lines 845, 850, 855: Channel turn-off delays - `time.sleep(0.1)` × 3

**Total Impact:** ~0.4 seconds

**Optimization:** Can reduce to 0.05s, save ~0.2s

---

## Summary of Optimization Opportunities

### High Impact (Save 2-4 seconds each):

1. **REF_SCANS: 20 → 15**
   - Save: ~2 seconds at 50ms integration
   - Risk: Low-moderate (may reduce SNR slightly)
   - File: `settings/settings.py` line 90

2. **LED_DELAY: 0.1s → 0.05s**
   - Save: ~2.2 seconds total
   - Risk: Low (LEDs stabilize quickly)
   - File: `settings/settings.py` line 92

### Medium Impact (Save 0.5-1 second each):

3. **DARK_SCANS: 20 → 10**
   - Save: ~0.5-1 second
   - Risk: Low (dark noise very stable)
   - File: Define in `settings/settings.py` (currently 20)

4. **Initial S-mode delay: 0.5s → 0.3s**
   - Save: 0.2 seconds
   - Risk: Low (one-time setup)
   - File: `utils/spr_calibrator.py` line 1059

### Already Optimized ✅:

- **ADAPTIVE_STABILIZATION_DELAY: 0.3s → 0.15s** (Done)
- **ADAPTIVE_MAX_STEP: 50 → 75** (Done)
- **ADAPTIVE_CONVERGENCE_FACTOR: 0.8 → 0.9** (Done)

---

## Recommended Fast Configuration

### Conservative (Safe):
```python
# settings/settings.py
LED_DELAY = 0.05  # Down from 0.1s
REF_SCANS = 15  # Down from 20
DARK_SCANS = 15  # Down from 20 (if exists, otherwise define it)
```

**Expected speedup:** ~3-4 seconds (10-15% faster total)

### Aggressive (Maximum Speed):
```python
# settings/settings.py
LED_DELAY = 0.05  # Down from 0.1s
REF_SCANS = 10  # Down from 20 (50% reduction)
DARK_SCANS = 10  # Down from 20

# spr_calibrator.py line 1059
time.sleep(0.3)  # Down from 0.5s
```

**Expected speedup:** ~5-7 seconds (15-25% faster total)
**Risk:** Moderate - may affect signal quality in noisy conditions

---

## Total Calibration Time Breakdown (Estimated)

### Current Timing:
1. Step 0: Detector profile load - **0.1s**
2. Step 1: Hardware init - **0.5s**
3. Step 2: Auto-polarization (optional) - **variable**
4. Step 3: Integration time calibration - **4-5s**
   - 3.1 Weakest channel: 0.4s
   - 3.2 Binary search: 2-3s
   - 3.3 Validation: 0.4s
5. Step 4: Adaptive LED calibration - **3.6s** ✅ Already optimized
6. Step 5: Dark noise - **1.5s** (including scans)
7. Step 6: S-mode reference signals - **4-8s** (depends on integration)
8. Step 7: Switch to P-mode - **0.4s**
9. Step 8: P-mode calibration - **3-4s**
10. Step 9: Validation - **0.5s**

**Total: ~18-27 seconds** (depends on integration time and iterations)

### After Conservative Optimization:
- Reduce LED_DELAY: Save 2.2s
- Reduce REF_SCANS: Save 1-2s
- Reduce DARK_SCANS: Save 0.5s
- Small delays: Save 0.3s

**New Total: ~14-22 seconds** (25-30% faster)

### After Aggressive Optimization:
- Additional REF_SCANS reduction: Save 1-2s more
- Mode switch optimization: Save 0.2s

**New Total: ~12-18 seconds** (35-40% faster)

---

## Implementation Priority

### Phase 1 - Low Risk (Implement Now):
1. ✅ ADAPTIVE_STABILIZATION_DELAY: 0.15s (Already done)
2. ✅ ADAPTIVE_MAX_STEP: 75 (Already done)
3. LED_DELAY: 0.05s
4. DARK_SCANS: 15
5. Initial S-mode delay: 0.3s

### Phase 2 - Moderate Risk (Test First):
1. REF_SCANS: 15
2. Validate signal quality is acceptable

### Phase 3 - Aggressive (Only if Needed):
1. REF_SCANS: 10
2. Monitor for SNR degradation

---

## Testing Recommendations

After each optimization:
1. ✅ Verify calibration completes successfully
2. ✅ Check signal quality (60-80% detector range)
3. ✅ Verify no saturation or instability
4. ✅ Compare reference signal SNR
5. ✅ Test with multiple calibrations for consistency

---

**Date:** October 11, 2025
**Status:** Phase 1 partially complete (adaptive delays optimized)
**Next:** Implement LED_DELAY and scan count reductions
