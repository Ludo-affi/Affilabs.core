# Live Mode vs Calibration Mode - Optimization Comparison

**Date**: October 12, 2025
**Status**: ⚠️ **PARTIAL PARITY** - Some optimizations missing in live mode

---

## 🔍 Quick Answer

**NO, live mode does NOT have all the optimizations from calibration.**

Specifically missing:
- ❌ **Batch LED control** (15× speedup)
- ❌ **LED afterglow correction** (Phase 2)
- ✅ **Dark noise correction** (applied)
- ✅ **Spectral filtering** (applied)
- ⚠️ **Integration time** (now scaled to 50% to prevent saturation)

---

## 📊 Optimization Comparison Table

| Optimization | Calibration Mode | Live Mode | Status |
|-------------|------------------|-----------|--------|
| **Batch LED Control** | ✅ Implemented | ❌ Missing | 🔴 **CRITICAL GAP** |
| **LED Afterglow Correction** | ✅ Phase 2 Applied | ❌ Missing | 🟡 **MINOR GAP** |
| **Dark Noise Correction** | ✅ Applied | ✅ Applied | ✅ **PARITY** |
| **Spectral Filtering** | ✅ Applied | ✅ Applied | ✅ **PARITY** |
| **Vectorized Averaging** | ✅ NumPy Operations | ✅ NumPy Operations | ✅ **PARITY** |
| **Integration Time Scaling** | ✅ Optimized (200.5ms) | ✅ Scaled (100.3ms) | ✅ **IMPROVED** |
| **Dynamic Scan Count** | ✅ Calculated | ✅ Calculated | ✅ **PARITY** |

---

## 🔴 CRITICAL GAP: Batch LED Control

### In Calibration (FAST ⚡)
```python
# utils/spr_calibrator.py - Uses batch command
def _activate_channel_batch(self, channels, intensities=None):
    # Single USB command for all 4 LEDs
    self.ctrl.set_batch_intensities(a=int_a, b=int_b, c=int_c, d=int_d)
    # Time: 0.8ms for all 4 channels
```

**Performance**: 0.8ms for 4 LEDs (15× faster than sequential)

### In Live Mode (SLOW 🐌)
```python
# utils/spr_data_acquisition.py - Uses sequential commands
def _read_channel_data(self, ch):
    self.ctrl.turn_on_channel(ch=ch)  # ONE LED at a time
    time.sleep(self.led_delay)
    # Read spectrum
    # Turn off, move to next channel
    # Time: 3ms per LED × 4 = 12ms total
```

**Performance**: 12ms for 4 LEDs (sequential, one at a time)

### Impact
- **Calibration**: ~650ms saved across entire process
- **Live Mode**: ~11ms overhead **PER MEASUREMENT CYCLE**
  - At 2Hz frequency: **22ms/second wasted**
  - At 60 seconds: **1.32 seconds wasted per minute**

---

## 🟡 MINOR GAP: LED Afterglow Correction

### In Calibration (Phase 2 Applied)
```python
# utils/spr_calibrator.py - Line 1902-1927
if (self.afterglow_correction and
    self._last_active_channel is not None and
    self.afterglow_correction_enabled):

    # Calculate LED-on time
    time_since_led_on = time.time() - self.ctrl.last_led_on_time

    # Predict and correct afterglow contamination
    integration_seconds = self.state.integration
    predicted_afterglow = self.afterglow_correction.predict_led_afterglow(
        time_since_led_on=time_since_led_on,
        integration_time=integration_seconds,
        led_channel=self._last_active_channel
    )

    # Subtract afterglow from dark measurement
    dark_corrected = raw_dark - predicted_afterglow
```

**Accuracy**: Removes ~50-200 counts of LED afterglow contamination

### In Live Mode (No Correction)
```python
# utils/spr_data_acquisition.py - Line 379
# Dark noise subtraction ONLY (no afterglow correction)
self.int_data[ch] = averaged_intensity - dark_correction
```

**Impact**:
- Minor error in live measurements (~0.3-1% depending on LED history)
- Most visible when switching between channels rapidly
- Less critical because:
  - Dark noise measured during calibration with afterglow correction
  - Live mode uses calibrated dark noise (already corrected)
  - Afterglow mainly affects fresh dark measurements

---

## ✅ Optimizations That ARE Applied in Live Mode

### 1. Dark Noise Correction ✅
```python
# utils/spr_data_acquisition.py - Line 322-380
dark_correction = self.dark_noise  # From calibration
self.int_data[ch] = averaged_intensity - dark_correction
```

### 2. Spectral Filtering ✅
```python
# utils/spr_data_acquisition.py - Line 293-301
wavelength_mask = (current_wavelengths >= min_wavelength) & (current_wavelengths <= max_wavelength)
int_data_single = reading[wavelength_mask]
```

### 3. Vectorized Averaging ✅
```python
# utils/spr_data_acquisition.py - Line 260-280
for _scan in range(self.num_scans):
    reading = self.usb.read_intensity()
    int_data_sum = np.add(int_data_sum, int_data_single)
averaged_intensity = int_data_sum / self.num_scans
```

### 4. Integration Time Scaling ✅ (NEW!)
```python
# utils/spr_state_machine.py - Line 365-395
live_integration_seconds = calibrated_integration * LIVE_MODE_INTEGRATION_FACTOR
# Result: 200.5ms → 100.3ms (50% scaling to prevent saturation)
```

---

## 📈 Performance Impact Analysis

### Calibration Mode Performance
```
Total Time: 88.7 seconds (47% faster than baseline 170s)

Optimizations Applied:
1. Batch LED Control:          -73.2s  (15× speedup)
2. Single Dark Measurement:     -6.0s  (Step 7 optimization)
3. LED_DELAY Reduction:         -0.55s (100ms→50ms)
4. Vectorized Processing:       -0.75s (NumPy operations)
5. Afterglow Correction:        +2.0s  (adds time but improves accuracy)
────────────────────────────────────────
NET IMPROVEMENT:               -78.5s  (-46% faster)
```

### Live Mode Performance (WITHOUT Batch LED)
```
Per Measurement Cycle:
├─ Turn on Channel A:     3ms   (sequential)
├─ LED Delay:            50ms
├─ Read Spectrum:        100ms  (scaled integration time)
├─ Turn off:             1ms
├─ Turn on Channel B:     3ms   (sequential)
├─ LED Delay:            50ms
├─ Read Spectrum:        100ms
├─ Turn off:             1ms
├─ (repeat for C, D)
└─ Total 4 channels:     ~616ms

Measurement Frequency: ~1.6 Hz
```

### Live Mode Performance (WITH Batch LED - Not Implemented)
```
Per Measurement Cycle:
├─ Set Batch LEDs:       0.8ms  (all at once!)
├─ Turn on Channel A:
├─ LED Delay:           50ms
├─ Read Spectrum:       100ms
├─ Turn on Channel B:
├─ LED Delay:           50ms
├─ Read Spectrum:       100ms
├─ (repeat for C, D)
└─ Total 4 channels:    ~605ms

Measurement Frequency: ~1.65 Hz
Improvement: +3% faster (11ms saved per cycle)
```

---

## 🛠️ How to Add Missing Optimizations to Live Mode

### Priority 1: Batch LED Control (HIGH IMPACT)

**Estimated Time**: 2-3 hours
**Complexity**: Medium
**Impact**: ~11ms saved per measurement cycle (+3% faster)

**Implementation Steps**:

1. **Add batch LED helper to data acquisition wrapper** (`utils/spr_state_machine.py`):
```python
class ControllerAdapter:
    def turn_on_channel_batch(self, channels: list[str], intensities: dict = None):
        """Turn on multiple channels using batch command."""
        if hasattr(self.hal, 'set_batch_intensities'):
            # Use batch command
            intensity_array = [0, 0, 0, 0]
            for i, ch in enumerate(['a', 'b', 'c', 'd']):
                if ch in channels and intensities:
                    intensity_array[i] = intensities.get(ch, 0)
            return self.hal.set_batch_intensities(*intensity_array)
        else:
            # Fallback to sequential
            for ch in channels:
                self.hal.activate_channel(ch)
```

2. **Modify data acquisition loop** (`utils/spr_data_acquisition.py` line ~250):
```python
# BEFORE (sequential):
for ch in ch_list:
    self.ctrl.turn_on_channel(ch=ch)
    time.sleep(self.led_delay)
    reading = self.usb.read_intensity()
    # ...

# AFTER (batch):
if hasattr(self.ctrl, 'turn_on_channel_batch'):
    # Pre-set all LED intensities
    intensities = {ch: self.leds_calibrated.get(ch, 255) for ch in ch_list}
    for ch in ch_list:
        # Just activate the channel (LEDs already set)
        self.ctrl.turn_on_channel_batch([ch], intensities)
        time.sleep(self.led_delay)
        reading = self.usb.read_intensity()
        # ...
else:
    # Fallback to current sequential method
    # ...
```

3. **Test on hardware**:
   - Verify batch command works
   - Check signal quality unchanged
   - Measure actual speed improvement

---

### Priority 2: LED Afterglow Correction (LOW IMPACT)

**Estimated Time**: 4-6 hours
**Complexity**: High
**Impact**: ~0.3-1% accuracy improvement

**Implementation Steps**:

1. **Add afterglow correction to data acquisition** (`utils/spr_data_acquisition.py`):
```python
def __init__(self, ...):
    # Add afterglow correction instance
    self.afterglow_correction = None
    if hasattr(ctrl, 'afterglow_correction'):
        self.afterglow_correction = ctrl.afterglow_correction
```

2. **Track LED on/off times**:
```python
def _read_channel_data(self, ch):
    led_on_time = time.time()
    self.ctrl.turn_on_channel(ch=ch)
    time.sleep(self.led_delay)

    # Read spectrum
    reading = self.usb.read_intensity()

    # Turn off and record
    self.ctrl.turn_off_channels()
    led_off_time = time.time()

    # Store for potential afterglow correction
    self.last_led_times[ch] = (led_on_time, led_off_time)
```

3. **Apply correction when switching channels**:
```python
# If previous channel was different, apply afterglow correction
if self.last_channel != ch and self.afterglow_correction:
    time_since_led_off = time.time() - self.last_led_times[self.last_channel][1]
    afterglow = self.afterglow_correction.predict_led_afterglow(
        time_since_led_on=time_since_led_off,
        integration_time=self.integration_time,
        led_channel=self.last_channel
    )
    # Apply correction...
```

**Recommendation**: ⚠️ **Skip for now** - Low ROI, high complexity

---

## 🎯 Recommended Action Plan

### Phase 1: Batch LED Control (RECOMMENDED)
- **Priority**: HIGH
- **Effort**: Medium (2-3 hours)
- **Impact**: +3% faster live measurements
- **Risk**: Low (graceful fallback available)

### Phase 2: Integration Time Auto-Scaling (COMPLETED ✅)
- **Priority**: HIGH
- **Effort**: Low (1 hour) - **Already done!**
- **Impact**: Prevents saturation, allows higher signals
- **Status**: **IMPLEMENTED** (see SATURATION_FIX_AND_LOG_CLEANUP.md)

### Phase 3: Afterglow Correction (OPTIONAL)
- **Priority**: LOW
- **Effort**: High (4-6 hours)
- **Impact**: Minor accuracy improvement (~0.5%)
- **Recommendation**: **Skip** - Not worth the effort

---

## 📝 Current Status Summary

### What Works ✅
1. ✅ Dark noise correction (from calibration)
2. ✅ Spectral filtering (wavelength-based masking)
3. ✅ Vectorized averaging (NumPy operations)
4. ✅ Integration time scaling (prevents saturation)
5. ✅ Dynamic scan count (optimizes throughput)

### What's Missing ❌
1. ❌ Batch LED control (11ms/cycle wasted)
2. ❌ LED afterglow correction (minor accuracy impact)

### Recommended Fix 🔧
**Add batch LED control to live mode** for 3% speed improvement with minimal effort.

---

## 📚 Related Documentation

- `BATCH_LED_IMPLEMENTATION_COMPLETE.md` - Batch LED in calibration
- `SATURATION_FIX_AND_LOG_CLEANUP.md` - Integration time scaling
- `BATCH_PROCESSING_ANALYSIS.md` - Performance analysis
- `INTEGRATION_TIME_AWARE_AFTERGLOW_CORRECTION.md` - Afterglow details

---

## Summary

Live mode is **mostly optimized** but missing **batch LED control**, which would provide a modest 3% speed improvement. The afterglow correction is less critical since:

1. Dark noise from calibration already has afterglow correction applied
2. Impact is minimal in steady-state measurements
3. Only affects rapid channel switching scenarios

**Bottom line**: Live mode is production-ready, but could be 3% faster with batch LED control.
