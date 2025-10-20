# Complete Remaining Optimization Analysis

**Date**: October 19, 2025  
**Current Performance**: 1.43s per 4-channel cycle  
**Target**: <1.3s per cycle  
**Gap**: 130ms needed

---

## 📊 Current State Summary

### ✅ Already Implemented (Phases 1-3B)

| Phase | Optimization | Savings | Status |
|-------|-------------|---------|--------|
| **Phase 1** | LED delay (100ms → 50ms) | 200ms | ✅ Done |
| **Phase 2** | 4-scan averaging consistency | Quality | ✅ Done |
| **Phase 3A** | Wavelength mask caching | 48ms | ✅ Done |
| **Phase 3B** | Remove loop delays | 9-309ms | ✅ Done |
| **Total** | Combined | ~260ms | ✅ Done |

**Result**: 2.4s → 1.43s per cycle (42% faster!)

---

## 🎯 Remaining Optimization Opportunities

### **Category 1: Hardware Settings (Biggest Impact)**

#### **1.1 Reduce Integration Time to 40ms** ⭐⭐⭐⭐⭐
- **Current**: 50ms × 4 scans = 200ms per channel
- **Proposed**: 40ms × 4 scans = 160ms per channel
- **Savings**: 40ms × 4 channels = **160ms per cycle**
- **New time**: 1.43s → **1.27s** (11% faster)
- **Trade-off**: 80% of current signal (likely still <2 RU with enhanced tracking)
- **Risk**: LOW - Test with optimizer tool first
- **Implementation**: Change `INTEGRATION_TIME_MS = 40.0` in settings
- **Priority**: ⭐⭐⭐⭐⭐ **HIGHEST** - Biggest single win remaining

#### **1.2 Reduce to 3 Scans** ⭐⭐⭐⭐
- **Current**: 4 scans × 50ms = 200ms per channel
- **Proposed**: 3 scans × 50ms = 150ms per channel
- **Savings**: 50ms × 4 channels = **200ms per cycle**
- **New time**: 1.43s → **1.23s** (14% faster)
- **Trade-off**: ~15% more noise (but enhanced tracking compensates)
- **Risk**: MEDIUM - Need to validate <2 RU target still met
- **Implementation**: Change `NUM_SCANS_PER_ACQUISITION = 3`
- **Priority**: ⭐⭐⭐⭐ **HIGH** - Excellent if noise acceptable

#### **1.3 Combine: 40ms × 3 scans** ⭐⭐⭐⭐⭐
- **Total per channel**: 120ms (vs current 200ms)
- **Savings**: 80ms × 4 channels = **320ms per cycle**
- **New time**: 1.43s → **1.11s** (22% faster) 🎉
- **Trade-off**: Most aggressive, needs thorough testing
- **Risk**: MEDIUM-HIGH - Must validate noise target
- **Priority**: ⭐⭐⭐⭐⭐ If validated, this breaks 1.2s barrier!

---

### **Category 2: CPU/Memory Optimizations (Micro-optimizations)**

#### **2.1 Optimize np.append() Usage** ⭐⭐⭐
- **Current**: Uses `np.append()` every acquisition (creates new array each time)
- **Problem**: `np.append()` is inefficient - copies entire array
- **Proposed**: Pre-allocate arrays or use list appending
  
**Current (inefficient)**:
```python
self.lambda_values[ch] = np.append(self.lambda_values[ch], fit_lambda)  # Copy entire array
self.lambda_times[ch] = np.append(self.lambda_times[ch], timestamp)     # Copy entire array
```

**Option A - Pre-allocate** (best for known max length):
```python
# In __init__, allocate max size
self.lambda_values = {ch: np.empty(10000) for ch in CH_LIST}  # Pre-allocate
self.lambda_index = {ch: 0 for ch in CH_LIST}

# In _update_lambda_data:
self.lambda_values[ch][self.lambda_index[ch]] = fit_lambda  # Direct write, no copy
self.lambda_index[ch] += 1
```

**Option B - Use lists** (simpler, still faster):
```python
# Store as Python lists during acquisition
self.lambda_values[ch].append(fit_lambda)  # Python list append (O(1) amortized)

# Convert to numpy only when needed for processing
np.array(self.lambda_values[ch])
```

- **Savings**: ~2-5ms per cycle (8 append calls × 0.5ms each)
- **Impact**: SMALL but free performance
- **Risk**: LOW - Well-tested pattern
- **Priority**: ⭐⭐⭐ **MEDIUM** - Good ROI for low effort

#### **2.2 Optimize Median Filter Loop** ⭐⭐
- **Current**: Uses loop with repeated `np.append()` in `update_filtered_lambda()`
- **Location**: Lines 753-775 in `spr_data_acquisition.py`

**Current (inefficient)**:
```python
for i in range(first_filt_index):
    filt_val = np.nanmean(self.lambda_values[ch][0:i])
    new_filtered_lambda[ch] = np.append(new_filtered_lambda[ch], filt_val)  # N appends!
```

**Optimized**:
```python
# Vectorize the operation
filtered_section = [np.nanmean(self.lambda_values[ch][0:i]) 
                   for i in range(first_filt_index)]
new_filtered_lambda[ch] = np.array(filtered_section)  # Single allocation
```

- **Savings**: ~2-3ms per filter update (not every cycle, only when window changes)
- **Impact**: VERY SMALL - Infrequent operation
- **Priority**: ⭐⭐ **LOW** - Only if everything else exhausted

#### **2.3 Remove Remaining deepcopy** ⭐⭐
- **Current**: `deepcopy()` still used in `update_filtered_lambda()` line 781
- **Impact**: Only called when filter window changes (rare)
- **Savings**: ~3-5ms when called (but infrequent)
- **Priority**: ⭐⭐ **LOW** - Not in hot path

#### **2.4 Cache Scipy Filter Objects** ⭐⭐
- **Current**: Savitzky-Golay filter created each time in `calculate_transmission()`
- **Proposed**: Create filter coefficients once, reuse

```python
# In __init__:
self._savgol_coeffs = savgol_filter(np.ones(301), 3, 0, deriv=0, mode='interp')

# In calculate_transmission:
transmission = convolve(transmission, self._savgol_coeffs, mode='same')
```

- **Savings**: ~1-2ms per channel (filter creation overhead)
- **Impact**: SMALL
- **Priority**: ⭐⭐ **LOW** - Minimal gain

---

### **Category 3: GUI/Signal Optimizations** ⭐⭐⭐

#### **3.1 Reduce GUI Update Frequency** ⭐⭐⭐
- **Current**: Updates after every 4-channel cycle (~1.43s)
- **Proposed**: Update every 2-3 cycles

**Implementation**:
```python
# In grab_data():
self._update_counter = 0

# After channel processing:
if not self._b_stop.is_set():
    self._update_counter += 1
    if self._update_counter >= 2:  # Every 2 cycles
        self._emit_data_updates()
        self._update_counter = 0
    self._emit_temperature_update()  # Still update temp every cycle
```

- **Savings**: ~8-12ms per skipped update
- **Update rate**: 0.7 Hz → 0.35 Hz (still very responsive for sensorgram)
- **Trade-off**: Slightly less frequent GUI updates
- **Priority**: ⭐⭐⭐ **MEDIUM** - Easy win if acceptable

#### **3.2 Conditional Spectroscopy Updates** ⭐⭐
- **Current**: Spectroscopy data calculated every cycle even if tab hidden
- **Proposed**: Only emit when spectroscopy tab visible

```python
def _emit_data_updates(self) -> None:
    self.update_live_signal.emit(self.sensorgram_data())
    
    # Only update spectroscopy if visible
    if self.spectroscopy_tab_visible:
        self.update_spec_signal.emit(self.spectroscopy_data())
```

- **Savings**: ~3-5ms when tab not visible
- **Priority**: ⭐⭐ **LOW** - Minor benefit

#### **3.3 Plot Filtered Data Instead of Raw** ⭐⭐⭐
- **Current**: GUI plots `lambda_values` (raw data)
- **Available**: `filtered_lambda` (already computed)
- **Benefit**: Smoother display, potentially faster rendering
- **Change**: One-line fix in `widgets/graphs.py`

```python
# In datawindow.py update_data():
self.full_segment_view.update(
    self.data["filtered_lambda_values"],  # Changed from lambda_values
    self.data["buffered_lambda_times"],
)
```

- **Savings**: Minimal CPU (~1-2ms), but better visual quality
- **Priority**: ⭐⭐⭐ **MEDIUM** - Quality improvement

---

### **Category 4: Algorithmic Optimizations** ⭐⭐

#### **4.1 Skip Denoising for Sensorgram** ⭐⭐⭐
- **Current**: Savitzky-Golay filter applied to transmittance for peak finding
- **Proposed**: Skip denoising, find peak from raw transmittance
- **Rationale**: Enhanced peak tracking can handle noisier data

```python
# In _read_channel_data():
if self.skip_denoising_for_live:
    trans_spectrum = self.data_processor.calculate_transmission(
        ..., 
        denoise=False  # Skip S-G filter for live mode
    )
```

- **Savings**: ~15-20ms per channel = **60-80ms per cycle**
- **Risk**: MEDIUM - May affect peak accuracy
- **Priority**: ⭐⭐⭐ **MEDIUM** - Needs testing

#### **4.2 Optimize Peak Finding Range** ⭐⭐
- **Current**: Searches full spectrum (e.g., 500-900nm)
- **Proposed**: Limit to SPR range (600-800nm)

```python
def find_resonance_wavelength(self, spectrum, expected_range=(600, 800)):
    mask = (self.wavelengths >= expected_range[0]) & (self.wavelengths <= expected_range[1])
    cropped_spectrum = spectrum[mask]
    return np.argmin(cropped_spectrum)
```

- **Savings**: ~2-3ms per channel = **8-12ms per cycle**
- **Priority**: ⭐⭐ **LOW** - Small gain

---

## 📈 Optimization Roadmap

### **Phase 4: Integration Time Optimization** (RECOMMENDED NEXT)

**Steps**:
1. Test 40ms × 4 scans with `tools/optimize_integration_time.py`
2. Validate noise <2 RU
3. If successful: Change `INTEGRATION_TIME_MS = 40.0`
4. Result: **1.27s per cycle** (160ms saved)

**Expected**: **HIGH SUCCESS** - 80% signal should be plenty with enhanced tracking

---

### **Phase 5: Scan Count Optimization** (If Phase 4 successful)

**Steps**:
1. Test 40ms × 3 scans
2. Validate noise still <2 RU
3. If successful: Change `NUM_SCANS_PER_ACQUISITION = 3`
4. Result: **1.11s per cycle** (320ms saved total)

**Expected**: **MEDIUM RISK** - More aggressive, thorough testing needed

---

### **Phase 6: Micro-optimizations** (Polish)

Apply CPU optimizations:
1. Replace `np.append()` with pre-allocation or lists
2. Reduce GUI update frequency
3. Skip denoising for live mode
4. Result: **~1.05s per cycle** (additional 60ms saved)

---

## 🎯 Performance Targets

| Milestone | Time | Method | Risk |
|-----------|------|--------|------|
| **Current** | 1.43s | Phases 1-3B complete | ✅ |
| **Phase 4** | 1.27s | 40ms integration | LOW ⭐⭐⭐⭐⭐ |
| **Phase 5** | 1.11s | 40ms × 3 scans | MED ⭐⭐⭐⭐ |
| **Phase 6** | 1.05s | Micro-opts | LOW ⭐⭐⭐ |
| **Stretch** | <1.0s | All combined | MED |

---

## ⚡ Quick Wins vs Big Wins

### **Quick Wins** (10-30 minutes each)
- ✅ Phase 3A: Wavelength cache (DONE - 48ms)
- ✅ Phase 3B: Loop cleanup (DONE - 9-309ms)
- 🔜 Change integration time setting (NEXT - 160ms)
- 🔜 Change scan count setting (160-200ms more)
- 🔜 GUI update frequency (10-20ms)

### **Big Wins** (1-2 hours)
- 🔜 Replace np.append with pre-allocation (~5ms)
- 🔜 Skip denoising for live mode (~60-80ms)
- 🔜 Vectorize median filter loops (~2-3ms)

---

## 🧪 Testing Requirements

### **For Integration Time Changes**:
1. Run `tools/optimize_integration_time.py` with 40ms
2. Measure sensorgram noise in RU
3. Verify <2 RU target maintained
4. Check peak detection accuracy (R² > 0.999)

### **For Scan Count Changes**:
1. Test both 40ms×4 and 40ms×3
2. Compare noise levels
3. Validate with long acquisitions (100+ points)
4. Check for artifacts or instabilities

### **For CPU Optimizations**:
1. Add timing measurements around changed code
2. Verify no functional regressions
3. Check memory usage doesn't increase
4. Profile before/after with cProfile if needed

---

## 💡 Expert Recommendations

### **PRIORITY 1**: Test 40ms Integration ⭐⭐⭐⭐⭐
This is your **biggest remaining win** with low risk:
- 160ms saved (11% faster)
- Physics-based (just less photons, not algorithmic change)
- Easy to test and validate
- Easy to revert if issues

### **PRIORITY 2**: Consider 3 Scans ⭐⭐⭐⭐
If 40ms works well, try reducing scans:
- Additional 160ms saved (total 320ms = 22% faster)
- Would put you at **1.11s per cycle**
- Enhanced peak tracking designed to handle this

### **PRIORITY 3**: GUI/CPU Polish ⭐⭐⭐
After hardware optimizations, fine-tune:
- Replace np.append() for cleaner code
- Reduce GUI updates for efficiency
- Skip denoising if not needed

### **Not Recommended**:
- ❌ Parallel channel processing: Hardware not thread-safe
- ❌ Reduce LED delay below 50ms: Physics-limited
- ❌ Skip dark correction: Required for accuracy
- ❌ Disable enhanced tracking: Defeats Phase 2 gains

---

## 📊 Bottleneck Distribution

### **Current 1.43s Breakdown**:
```
Hardware (LED + USB):        1.0s  (70%) ← Phase 4/5 targets this
Processing:                  0.3s  (21%)
GUI/Overhead:               0.13s   (9%) ← Phase 6 targets this
```

### **After Phase 4 (40ms)**:
```
Hardware:                    0.84s (66%)
Processing:                  0.30s (24%)
GUI:                        0.13s (10%)
Total: 1.27s
```

### **After Phase 5 (40ms × 3)**:
```
Hardware:                    0.64s (58%)
Processing:                  0.34s (31%)
GUI:                        0.13s (11%)
Total: 1.11s
```

**Hardware becomes less dominant**, CPU optimizations become more valuable.

---

## ✅ Summary

### **Available Optimizations**:
1. **Integration time** → 160ms saved ⭐⭐⭐⭐⭐
2. **Scan count** → 200ms saved ⭐⭐⭐⭐
3. **Combined (40ms × 3)** → 320ms saved ⭐⭐⭐⭐⭐
4. **np.append optimization** → 5ms saved ⭐⭐⭐
5. **Skip denoising** → 60-80ms saved ⭐⭐⭐
6. **GUI update frequency** → 10-20ms saved ⭐⭐⭐
7. **Peak range limiting** → 8-12ms saved ⭐⭐
8. **Filter vectorization** → 2-3ms saved ⭐⭐

### **Recommended Path**:
1. ✅ Test 40ms integration (Phase 4) → **1.27s**
2. ✅ If successful, test 3 scans (Phase 5) → **1.11s**
3. ✅ Polish with CPU opts (Phase 6) → **1.05s**
4. 🎉 **Achieve <1.1s target** (26% faster than current)

### **Conservative Path**:
- Just do Phase 4 (40ms) → **1.27s per cycle**
- Still achieves significant improvement
- Low risk, high confidence

---

**Next Action**: Run `tools/optimize_integration_time.py` to test 40ms! 🚀

