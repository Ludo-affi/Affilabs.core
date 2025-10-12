# Batch Processing and Acceleration Analysis

**Date**: October 11, 2025  
**Status**: 📊 Analysis Complete - Implementation Needed

---

## Summary

**Your question**: "Having a dark before and after the LEDs will be interesting to compare especially with the Afterglow correction. Is the arrayed scan method, batch processing method, and no overhead batch LED signal implemented to accelerate data processing?"

**Answer**: 
✅ **Batch LED control EXISTS** (`set_batch_intensities()`) but is **NOT USED**  
❌ **Array-based scan methods**: Not fully implemented  
❌ **No overhead batch processing**: Not implemented  
✅ **Dark before/after comparison**: Easy to add with current structure

---

## Current Implementation Status

### ✅ **1. Batch LED Control (Available but Unused)**

**Location**: `utils/controller.py` line 497

```python
def set_batch_intensities(self, a=0, b=0, c=0, d=0):
    """Set all LED intensities in a single batch command.
    
    Performance:
        Sequential commands: ~12ms for 4 LEDs (3ms per LED)
        Batch command: ~0.8ms for 4 LEDs
        Speedup: 15x faster
    
    Command Format: batch:A,B,C,D\n
    Example: batch:255,128,64,0\n
    """
```

**Status**: 
- ✅ Implemented in controller
- ❌ NOT used in data acquisition
- ❌ NOT used in calibration

**Current Method** (Sequential):
```python
# Current approach in spr_data_acquisition.py line 256
for ch in CH_LIST:
    self.ctrl.turn_on_channel(ch=ch)  # Activates ONE LED at a time
    time.sleep(self.led_delay)
    # Measure this channel
    # Turn off, move to next
```

**Potential Improvement**: Could use batch command to set all LEDs at once

---

### ❌ **2. Array-Based Scan Methods (Not Implemented)**

**Current Method** (Loop-based):
```python
# Current: Loop through scans one at a time
for _scan in range(self.num_scans):
    reading = self.usb.read_intensity()  # Single spectrum
    int_data_sum += reading  # Accumulate
```

**Potential Improvement** (Not implemented):
```python
# Array-based: Read multiple scans, process as batch
scans = np.zeros((self.num_scans, spectrum_length))
for i in range(self.num_scans):
    scans[i] = self.usb.read_intensity()

# Vectorized processing
averaged = np.mean(scans, axis=0)  # Much faster than loop
filtered = apply_spectral_filter_vectorized(scans)  # Batch filtering
```

**Status**: ❌ Not implemented

---

### ❌ **3. No Overhead Batch Processing (Not Implemented)**

**Current Overhead**:
1. **LED switching**: 3ms per channel (sequential)
2. **LED delay**: 20ms per channel (waiting for stabilization)
3. **Channel iteration**: Python loop overhead

**Potential Optimization** (Not implemented):
```python
# Batch approach: Set all LEDs simultaneously, measure all at once
# Requires hardware support for simultaneous LED activation
# OR: Pipeline LED switching with data processing
```

**Status**: ❌ Not implemented

---

### ✅ **4. Dark Before/After Comparison (Easy to Add)**

**Current Dark Measurements**:
- **Step 1** (Before LEDs): 32ms integration, clean
- **Step 5** (After LEDs): 55ms integration, contaminated (now corrected with Phase 2!)

**Comparison Analysis** (Easy to implement):
```python
# In measure_dark_noise():
if self._last_active_channel is None:
    # Step 1: First dark (before LEDs)
    self.state.dark_noise_before_leds = full_spectrum_dark_noise
    logger.info("📊 Dark noise BEFORE LEDs: {mean:.1f} counts")
else:
    # Step 5: Second dark (after LEDs)
    self.state.dark_noise_after_leds_uncorrected = full_spectrum_dark_noise_before_correction
    self.state.dark_noise_after_leds_corrected = full_spectrum_dark_noise
    
    # Calculate contamination
    contamination = mean(uncorrected) - mean(before_leds)
    correction_effectiveness = mean(uncorrected) - mean(corrected)
    
    logger.info("📊 Dark Comparison:")
    logger.info(f"   Before LEDs: {mean(before_leds):.1f} counts")
    logger.info(f"   After LEDs (uncorrected): {mean(uncorrected):.1f} counts")
    logger.info(f"   After LEDs (corrected): {mean(corrected):.1f} counts")
    logger.info(f"   Contamination: {contamination:.1f} counts")
    logger.info(f"   Correction effectiveness: {correction_effectiveness:.1f} counts")
```

**Status**: ✅ Easy to add (requires minor code changes)

---

## Performance Analysis

### **Current Timing** (4-channel acquisition without afterglow correction):
```
Per-Channel Breakdown:
- LED turn on: 3ms
- LED stabilization delay: 20ms (default LED_DELAY)
- Spectrum acquisition: 55ms (integration time)
- Processing: 5ms
- LED turn off: 3ms
Total per channel: ~86ms

4-channel cycle: 4 × 86ms = 344ms
Frequency: ~2.9 Hz
```

### **With Batch LED Control** (not yet implemented):
```
Per-Channel Breakdown:
- Batch LED command: 0.8ms (all 4 LEDs at once) → save 11.2ms
- LED stabilization delay: 20ms (still needed)
- Spectrum acquisition: 55ms
- Processing: 5ms
Total per channel: ~81ms

4-channel cycle: 4 × 81ms = 324ms
Frequency: ~3.1 Hz
Improvement: ~6% faster
```

### **With Afterglow Correction + Reduced Delay** (Phase 1):
```
Per-Channel Breakdown:
- LED turn on: 3ms
- LED stabilization delay: 5ms (reduced from 20ms with afterglow correction)
- Spectrum acquisition: 55ms
- Processing: 5ms
- Afterglow correction: 0.1ms
- LED turn off: 3ms
Total per channel: ~71ms

4-channel cycle: 4 × 71ms = 284ms
Frequency: ~3.5 Hz
Improvement: ~17% faster than current
```

### **With Batch LED + Afterglow Correction** (ideal):
```
Per-Channel Breakdown:
- Batch LED command: 0.8ms
- LED stabilization delay: 5ms (with correction)
- Spectrum acquisition: 55ms
- Processing: 5ms
- Afterglow correction: 0.1ms
Total per channel: ~66ms

4-channel cycle: 4 × 66ms = 264ms
Frequency: ~3.8 Hz
Improvement: ~23% faster than current
```

---

## Implementation Recommendations

### **Priority 1: Dark Before/After Comparison** (Easy Win)
**Estimated Time**: 30 minutes  
**Complexity**: Low  
**Impact**: High (validation of afterglow correction)

**Implementation**:
1. Add `dark_noise_before_leds` to `CalibrationState`
2. Store Step 1 dark in this field
3. In Step 5, compare before/after and log statistics
4. Save comparison to calibration metadata

**Benefits**:
- Validates afterglow correction effectiveness
- Provides diagnostic information
- Easy to implement with current structure

---

### **Priority 2: Batch LED Control** (Medium Win)
**Estimated Time**: 2-3 hours  
**Complexity**: Medium  
**Impact**: Medium (~6% speedup, or ~23% with afterglow correction)

**Implementation**:
1. Modify `spr_data_acquisition.py` to use `set_batch_intensities()`
2. Update calibration to use batch commands
3. Test compatibility with existing hardware
4. Fallback to sequential if batch fails

**Challenges**:
- Need to test on hardware
- May require firmware validation
- Need graceful fallback

---

### **Priority 3: Array-Based Scan Processing** (Small Win)
**Estimated Time**: 4-5 hours  
**Complexity**: High  
**Impact**: Low (~2-3% speedup from vectorization)

**Implementation**:
1. Pre-allocate scan array
2. Collect all scans first
3. Vectorized averaging
4. Vectorized filtering

**Challenges**:
- Memory overhead (storing all scans)
- Limited benefit (Python loop overhead is small)
- Code complexity increase

---

## Proposed Implementation Order

### **Phase 1: Dark Comparison Analysis** ✅ Recommended
**Goal**: Validate afterglow correction effectiveness

**Steps**:
1. Add `dark_noise_before_leds` to `CalibrationState`
2. Modify `measure_dark_noise()` to store Step 1 dark separately
3. Add comparison logging in Step 5
4. Create visualization tool for dark comparison

**Expected Output**:
```
STEP 1: Dark Noise Measurement (BEFORE LEDs)
   Dark noise mean: 850.2 counts
   ✅ Stored as baseline for comparison

STEP 5: Dark Noise Measurement (AFTER LEDs)
📊 Dark Noise Comparison:
   Before LEDs (Step 1): 850.2 counts
   After LEDs (uncorrected): 2084.7 counts (+1234.5 contamination)
   After LEDs (corrected): 850.7 counts (+0.5 residual)
   ✨ Afterglow correction effectiveness: 99.96%
```

---

### **Phase 2: Batch LED Control** ⚠️ Hardware Testing Required
**Goal**: Reduce LED switching overhead

**Steps**:
1. Test `set_batch_intensities()` on hardware
2. Add batch control option to `spr_data_acquisition.py`
3. Add enable/disable flag in `device_config.json`
4. Fallback to sequential if batch fails

**Expected Speedup**: 6-23% (depending on afterglow correction usage)

---

### **Phase 3: Array-Based Scan Processing** ⏳ Future
**Goal**: Vectorize scan averaging and filtering

**Steps**:
1. Pre-allocate scan arrays
2. Vectorized numpy operations
3. Batch spectral filtering

**Expected Speedup**: 2-3% (diminishing returns)

---

## Code Examples

### **Example 1: Dark Comparison (Priority 1)**

```python
# In CalibrationState.__init__():
self.dark_noise_before_leds: Optional[np.ndarray] = None
self.dark_noise_after_leds_uncorrected: Optional[np.ndarray] = None
self.dark_noise_contamination: Optional[float] = None

# In measure_dark_noise():
if self._last_active_channel is None:
    # Step 1: Store as baseline
    self.state.dark_noise_before_leds = full_spectrum_dark_noise.copy()
    logger.info(f"📊 Dark BEFORE LEDs: {np.mean(full_spectrum_dark_noise):.1f} counts")
else:
    # Step 5: Compare and correct
    before_mean = np.mean(self.state.dark_noise_before_leds)
    uncorrected_mean = np.mean(full_spectrum_dark_noise)
    
    # Store uncorrected for comparison
    self.state.dark_noise_after_leds_uncorrected = full_spectrum_dark_noise.copy()
    
    # Apply afterglow correction
    # ... correction code ...
    
    corrected_mean = np.mean(full_spectrum_dark_noise)
    contamination = uncorrected_mean - before_mean
    correction_effectiveness = (uncorrected_mean - corrected_mean) / contamination * 100
    
    self.state.dark_noise_contamination = contamination
    
    logger.info(f"📊 Dark Noise Comparison:")
    logger.info(f"   Before LEDs (Step 1): {before_mean:.1f} counts")
    logger.info(f"   After LEDs (uncorrected): {uncorrected_mean:.1f} counts")
    logger.info(f"   After LEDs (corrected): {corrected_mean:.1f} counts")
    logger.info(f"   Contamination: {contamination:.1f} counts ({contamination/before_mean*100:.1f}%)")
    logger.info(f"   ✨ Correction effectiveness: {correction_effectiveness:.2f}%")
```

---

### **Example 2: Batch LED Control (Priority 2)**

```python
# In spr_data_acquisition.py:
def _read_all_channels_batch(self, ch_list):
    """Read all channels using batch LED control (experimental).
    
    Speedup: ~15x faster LED switching (12ms → 0.8ms)
    """
    try:
        # Set all LED intensities at once
        intensities = {ch: self.state.leds_calibrated.get(ch, 0) for ch in ch_list}
        
        # Batch command (all LEDs off except active channel)
        for ch in ch_list:
            led_vals = {ch: intensities[ch] if ch == ch else 0 for ch in ['a', 'b', 'c', 'd']}
            success = self.ctrl.set_batch_intensities(**led_vals)
            
            if not success:
                logger.warning("Batch LED command failed, falling back to sequential")
                return self._read_all_channels_sequential(ch_list)
            
            time.sleep(self.led_delay)
            # Measure this channel
            # ...
    
    except Exception as e:
        logger.error(f"Batch processing failed: {e}, falling back to sequential")
        return self._read_all_channels_sequential(ch_list)
```

---

## Summary Table

| Feature | Status | Priority | Estimated Speedup | Complexity | Time to Implement |
|---------|--------|----------|-------------------|------------|-------------------|
| **Dark Before/After Comparison** | ❌ Not Implemented | 🔥 **HIGH** | N/A (validation) | Low | 30 min |
| **Batch LED Control** | ✅ Available, Not Used | ⚠️ **MEDIUM** | 6-23% | Medium | 2-3 hours |
| **Array-Based Scan Processing** | ❌ Not Implemented | ⏳ **LOW** | 2-3% | High | 4-5 hours |
| **Afterglow Correction (Phase 1)** | ✅ Implemented | ✅ **DONE** | 17% | N/A | Complete |
| **Calibration Afterglow (Phase 2)** | ✅ Implemented | ✅ **DONE** | N/A (quality) | N/A | Complete |

---

## Recommended Next Steps

### **Immediate** (Next 1 hour):
1. ✅ **Implement Dark Comparison** - Easy win, validates Phase 2
2. ⏳ **Test afterglow correction** - Run calibration to verify behavior

### **Short Term** (Next week):
3. ⚠️ **Test Batch LED Control** - Validate on hardware
4. ⚠️ **Integrate batch commands** - If hardware supports it

### **Long Term** (Future):
5. ⏳ **Array-based scan processing** - Diminishing returns

---

**Status**: Analysis complete, recommendations provided  
**Last Updated**: October 11, 2025
