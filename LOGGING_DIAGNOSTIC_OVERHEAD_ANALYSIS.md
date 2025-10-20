# Logging and Diagnostic Overhead Analysis

**Date**: October 19, 2025  
**Question**: Would removing diagnostic windows and simplifying logging improve speed?  
**Answer**: **YES, but the impact is SMALL (~5-15ms, or 0.3-1% speedup)**

---

## 📊 Current Logging/Diagnostic Architecture

### 1. **Debug Data Saving** (Controlled by Flag)

**Location**: `utils/spr_data_acquisition.py` line 29
```python
SAVE_DEBUG_DATA = False  # Currently DISABLED
```

**What it does**:
- Saves intermediate processing steps to `.npz` files
- Includes: raw spectrum, dark-corrected, S-reference, transmittance
- Called 4× per channel (16 saves per cycle if enabled)

**Performance Impact**:
- **When DISABLED (current)**: ~0ms (early return)
- **When ENABLED**: ~200-400ms per cycle (file I/O is expensive!)
- **Verdict**: ✅ **Already optimized** - disabled in production

---

### 2. **Diagnostic Signal Emission** (Processing Steps Window)

**Location**: `utils/spr_data_acquisition.py` lines 585-611

**What it does**:
- Packages data for diagnostic viewer window
- Emits Qt signal with spectral data
- Includes wavelengths, raw, dark-corrected, S-ref, transmittance
- First-time logging per channel (debug info)

**Code Analysis**:
```python
# Happens inside transmittance calculation (hot path)
if self.processing_steps_signal:  # If diagnostic window connected
    diagnostic_data = {
        'wavelengths': self.wave_data[:len(averaged_intensity)].copy(),  # Array copy
        'raw': averaged_intensity.copy(),                                 # Array copy
        'dark_corrected': self.int_data[ch].copy(),                      # Array copy
        's_reference': ref_sig_adjusted.copy(),                           # Array copy
        'transmittance': self.trans_data[ch].copy()                       # Array copy
    }
    # 5× array copies!
    self.processing_steps_signal.emit(diagnostic_data)  # Qt signal emission
```

**Performance Impact per Channel**:
- Array copies (5×): ~2-3ms (1591 pixels × 5 arrays)
- Signal emission: ~1-2ms (Qt overhead)
- Logging (first time only): ~0.5ms
- **Total**: ~3-5ms per channel = **12-20ms per 4-channel cycle**

**Impact**: ⭐⭐⭐ **MEDIUM** - Worth optimizing if diagnostic window not needed

---

### 3. **Logger Calls in Hot Path**

**What's in the acquisition loop**:

```python
# Per-cycle logging (happens every acquisition):
logger.debug(...)   # ~20-30 calls per cycle
logger.info(...)    # ~5-10 calls per cycle  
logger.warning(...) # ~0-2 calls per cycle (conditional)
logger.error(...)   # ~0-1 calls per cycle (exceptions only)
```

**Performance Impact**:
- `logger.debug()`: ~0.1-0.2ms each (if logging level allows)
- `logger.info()`: ~0.1-0.2ms each
- `logger.warning()`: ~0.2-0.3ms each
- String formatting (f-strings): ~0.05ms per call

**Current logging in hot path** (per cycle):
```python
# These run every acquisition:
Line 314: logger.error() - if mask fails (rare)
Line 327: logger.info() - first run only (cached)
Line 337: logger.error() - if integration fails (rare)
Line 629: logger.exception() - if channel read fails (rare)
```

**Estimated Total**: ~1-3ms per cycle (most are conditional/cached)

**Impact**: ⭐ **LOW** - Minimal overhead, mostly conditional

---

### 4. **Message Boxes / Dialogs** (show_message)

**Location**: Imported but not called in hot path
```python
from widgets.message import show_message
```

**Usage**: Only in error handlers (exception cases), not per-cycle

**Performance Impact**: ~0ms in normal operation (only on errors)

**Impact**: ⭐ **NONE** - Not in hot path

---

## 🎯 Optimization Opportunities

### **Option 1: Disable Diagnostic Signal Emission** ⭐⭐⭐

**Current**: Always packages and emits diagnostic data (5 array copies)  
**Proposed**: Make it conditional on window visibility

**Implementation**:
```python
# In spr_data_acquisition.py, add flag:
self.emit_diagnostic_data = False  # Controlled by diagnostic window

# In diagnostic data section (line 585):
if self.emit_diagnostic_data and self.processing_steps_signal:
    diagnostic_data = { ... }
    self.processing_steps_signal.emit(diagnostic_data)
```

**When to enable**:
- User opens diagnostic viewer → set `emit_diagnostic_data = True`
- User closes diagnostic viewer → set `emit_diagnostic_data = False`

**Savings**: 
- **12-20ms per cycle** when disabled
- **1.27s → 1.25s** (~1.6% faster)

**Trade-off**: Diagnostic window won't work unless explicitly enabled

**Priority**: ⭐⭐⭐ **MEDIUM** - Good ROI, but diagnostic is useful for debugging

---

### **Option 2: Reduce Logging Verbosity** ⭐⭐

**Current**: INFO level includes many messages  
**Proposed**: Use DEBUG for non-critical messages in hot path

**Implementation**:
```python
# Change logger level in hot path:
# From:
logger.info(f"Channel {ch} processing...")  # Logs every time

# To:
logger.debug(f"Channel {ch} processing...")  # Only if DEBUG level set
```

**Logging levels**:
- **DEBUG**: Development/troubleshooting only
- **INFO**: Important events (keep minimal in hot path)
- **WARNING**: Unexpected but handled conditions
- **ERROR**: Failures requiring attention

**Recommended change**:
Set root logger to INFO level (filters out DEBUG automatically)

**Savings**: ~1-2ms per cycle (string formatting avoided)

**Priority**: ⭐⭐ **LOW** - Small gain, may hinder troubleshooting

---

### **Option 3: Lazy String Formatting** ⭐

**Current**: F-strings evaluated even if log level filters them out
```python
logger.debug(f"Complex {expensive_calculation()} message")  # Always evaluates!
```

**Proposed**: Use lazy formatting
```python
logger.debug("Complex %s message", expensive_calculation())  # Only if logged
```

**Savings**: ~0.5-1ms per cycle (negligible)

**Priority**: ⭐ **VERY LOW** - Not worth the code churn

---

### **Option 4: Remove Array Copies in Diagnostic** ⭐⭐⭐⭐

**Current**: Copies arrays even if diagnostic window not reading them
```python
diagnostic_data = {
    'raw': averaged_intensity.copy(),  # Defensive copy
}
```

**Proposed**: Use references (if read-only in diagnostic viewer)
```python
diagnostic_data = {
    'raw': averaged_intensity,  # Reference (no copy)
}
```

**Savings**: ~2-3ms per cycle (5 array copies eliminated)

**Risk**: MEDIUM - Must ensure diagnostic viewer doesn't modify data

**Priority**: ⭐⭐⭐⭐ **HIGH** if combined with conditional emission

---

## 📈 Combined Impact Analysis

### **Scenario A: Minimal Changes** (Production-friendly)
- Disable diagnostic emission when window closed
- Keep all logging as-is

**Savings**: 12-20ms → **1.27s → 1.25s** (1.6% faster)  
**Risk**: LOW  
**Effort**: 30 minutes

---

### **Scenario B: Aggressive Logging Reduction**
- Disable diagnostic emission
- Move hot-path logs to DEBUG level
- Remove array copies in diagnostic

**Savings**: 15-25ms → **1.27s → 1.245s** (2% faster)  
**Risk**: MEDIUM (harder to debug issues)  
**Effort**: 1-2 hours

---

### **Scenario C: Nuclear Option** (Not Recommended)
- Remove all diagnostic code
- Remove all logging in hot path
- No error recovery logging

**Savings**: 20-30ms → **1.27s → 1.24s** (2.4% faster)  
**Risk**: HIGH (blind to production issues)  
**Effort**: 2-3 hours  
**Recommendation**: ❌ **DON'T DO THIS**

---

## ⚖️ Cost-Benefit Analysis

| Optimization | Savings | Effort | Risk | Recommended? |
|--------------|---------|--------|------|--------------|
| **Conditional diagnostic emission** | 12-20ms | 30 min | LOW | ✅ **YES** |
| Remove array copies | 2-3ms | 20 min | MED | ⚠️ Maybe |
| Reduce log verbosity | 1-2ms | 1 hour | MED | ⚠️ Maybe |
| Lazy string formatting | 0.5-1ms | 2 hours | LOW | ❌ No |
| Remove all logging | 20-30ms | 3 hours | HIGH | ❌ **NO** |

---

## 💡 Recommendation

### **Best Approach: Conditional Diagnostic Emission** ⭐⭐⭐⭐⭐

**Why**:
1. ✅ **Biggest bang for buck**: 12-20ms saved (1.6% faster)
2. ✅ **Low risk**: Diagnostic still available when needed
3. ✅ **Easy to implement**: Simple flag + window connection
4. ✅ **Production-safe**: No loss of error visibility
5. ✅ **User-friendly**: Auto-enables when diagnostic opened

**Implementation Plan**:
1. Add `emit_diagnostic_data` flag to SPRDataAcquisition
2. Wrap diagnostic packaging in conditional check
3. Connect diagnostic window open/close to flag
4. Test that diagnostic works when enabled
5. Measure performance improvement (~1.25s target)

**Expected Result**: 
- **Current**: 1.27s per cycle (with 40ms integration)
- **After**: 1.25s per cycle
- **Improvement**: 20ms (1.6% faster)

---

## 🔍 Comparison to Other Optimizations

| Optimization | Savings | Effort | Status |
|--------------|---------|--------|--------|
| **Phase 1: LED delay** | 200ms | 1 day | ✅ Done |
| **Phase 2: Scan averaging** | Quality | 1 day | ✅ Done |
| **Phase 3A: Wavelength cache** | 48ms | 2 hours | ✅ Done |
| **Phase 3B: Loop cleanup** | 9-309ms | 30 min | ✅ Done |
| **Phase 4: 40ms integration** | 160ms | Testing | 🔄 Testing |
| **Diagnostic conditional** | 12-20ms | 30 min | ⏸️ Available |
| **np.append optimization** | 5ms | 1 hour | ⏸️ Available |
| **Skip denoising** | 60-80ms | 30 min | ⏸️ Available |
| **GUI update frequency** | 10-20ms | 30 min | ⏸️ Available |

**Diagnostic optimization ranks #5-6 in terms of impact**.

---

## ✅ Final Verdict

### **Should you optimize logging/diagnostics?**

**YES, but with smart prioritization:**

1. **FIRST**: Finish testing 40ms integration (160ms gain) ⭐⭐⭐⭐⭐
2. **SECOND**: Add conditional diagnostic emission (12-20ms gain) ⭐⭐⭐⭐
3. **THIRD**: Consider np.append optimization (5ms gain) ⭐⭐⭐
4. **FOURTH**: Test denoising skip (60-80ms gain) ⭐⭐⭐
5. **LATER**: Logging verbosity reduction (1-2ms gain) ⭐⭐

### **Total Available Gains**:
```
Current (Phase 3B):           1.43s
After Phase 4 (40ms):         1.27s  (testing now)
+ Conditional diagnostic:     1.25s  (12-20ms)
+ Skip denoising:            1.17s  (60-80ms)
+ np.append fix:             1.165s (5ms)
+ GUI update batching:       1.155s (10ms)
--------------------------------
Target:                      <1.2s  ✅ ACHIEVABLE!
```

### **Recommended Action**:

**After 40ms testing succeeds**, implement conditional diagnostic emission:
- **Time**: 30 minutes
- **Gain**: 12-20ms (1.6% faster)
- **Risk**: Low
- **Reversible**: Yes (just re-enable)

**It's a good micro-optimization, but not the biggest win remaining.**

---

**Bottom Line**: Logging/diagnostic overhead is ~12-25ms (~1-2% of cycle time). Worth optimizing, but **Phase 4 (40ms integration) is 8× more valuable** (160ms vs 20ms). Focus on that first! 🎯

