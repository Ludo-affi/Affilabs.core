# Sensorgram Update Speed - Quick Reference

**Date**: October 19, 2025
**Goal**: Reduce latency from spectrum → GUI
**Full Analysis**: `SENSORGRAM_UPDATE_OPTIMIZATION_OPPORTUNITIES.md`

---

## Current Performance

- **Per-channel cycle**: ~250-300ms
- **Update rate**: ~3.3-4 Hz (4 channels)
- **Main bottlenecks**: Denoising (15-25ms), Peak finding (5-10ms), Data copies (8-13ms)

---

## Top 3 Quick Wins ⚡

### 1. Skip Denoising for Sensorgram (O2) 🔴
**Time Saved**: 15-20ms per channel
**Effort**: 2-3 hours
**Risk**: Low (validate peak detection accuracy)

```python
# In calculate_transmission():
def calculate_transmission(self, p_pol, s_ref, dark_noise, denoise=False):
    # Skip denoising for sensorgram (only need peak wavelength)
    # Keep denoising for spectroscopy display
```

---

### 2. Eliminate deepcopy Operations (O4) 🟡
**Time Saved**: 8-13ms per cycle
**Effort**: 2-4 hours
**Risk**: Low (careful testing needed)

```python
# Replace deepcopy with shallow copy or array views
def sensorgram_data(self):
    return {
        "lambda_values": self.lambda_values.copy(),  # Shallow copy
        ...
    }

# In graph update:
y_data = lambda_values[ch][self.static_index:]  # Array view (zero-copy)
```

---

### 3. Optimize Peak Finding Range (O3A) 🟡
**Time Saved**: 3-5ms per channel
**Effort**: 1-2 hours
**Risk**: Very low

```python
# Reduce search range to SPR-relevant wavelengths only
def find_resonance_wavelength(self, spectrum, expected_range=(600, 800)):
    mask = (self.wavelengths >= 600) & (self.wavelengths <= 800)
    cropped = spectrum[mask]
    min_idx = np.argmin(cropped)
    return self.wavelengths[mask][min_idx]
```

---

## Expected Results

### Phase 1 Implementation (All 3 optimizations)

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Per-channel time | 250ms | 175-190ms | **25-30% faster** |
| Update rate | 4 Hz | 5.3-5.7 Hz | **+33-43%** |
| Total time saved | - | 60-75ms | **Per channel** |

---

## Testing Checklist

After implementing optimizations:

✅ **Peak Detection Accuracy**
- Test with reference data
- Acceptable error: <0.5nm difference

✅ **Noise Level**
- Check sensorgram baseline STD
- Acceptable increase: <20%

✅ **Visual Quality**
- Sensorgram should appear smooth
- Binding curves should be clear

✅ **Performance**
- Log timing before/after
- Verify expected speedup achieved

---

## Implementation Order

1. **O3A** - Optimize peak range (1-2 hours, very safe)
2. **O4** - Remove deepcopy (2-4 hours, test carefully)
3. **O2** - Skip denoising (2-3 hours, validate accuracy)

**Total Time**: ~6-9 hours for 25-30% improvement

---

## Advanced Optimization (Optional)

### Parallel Channel Processing (O1) 🔴

**Only if**: You need 4-channel performance

**Benefit**: 4-channel cycle: 1000ms → 300ms (**3.3× faster**)

**Effort**: 2-3 days (major refactoring)

**Risk**: Medium (thread-safety, hardware compatibility)

---

## Files to Modify

1. **spr_data_processor.py**
   - `calculate_transmission()` - Add denoise flag
   - `find_resonance_wavelength()` - Add range parameter

2. **spr_data_acquisition.py**
   - `_read_channel_data()` - Pass denoise=False
   - `sensorgram_data()` - Change deepcopy to shallow copy

3. **widgets/graphs.py**
   - `update()` - Use array views instead of deepcopy

4. **widgets/datawindow.py**
   - `update_data()` - Remove or reduce deepcopy calls

---

## Performance Measurement

Add timing to key functions:

```python
import time

# At start of function
t_start = time.perf_counter()

# Your code here...

# At end of function
t_elapsed = (time.perf_counter() - t_start) * 1000
logger.info(f"⏱️ {function_name}: {t_elapsed:.2f}ms")
```

Log these functions:
- `_read_channel_data()` - Total per-channel time
- `calculate_transmission()` - Denoising time
- `find_resonance_wavelength()` - Peak finding time
- `sensorgram_data()` - Data copy time
- `update()` in graphs.py - GUI rendering time

---

**Next Step**: Implement Phase 1 optimizations (O3A + O4 + O2)
**Expected Time**: 6-9 hours
**Expected Result**: **25-30% faster** sensorgram updates
