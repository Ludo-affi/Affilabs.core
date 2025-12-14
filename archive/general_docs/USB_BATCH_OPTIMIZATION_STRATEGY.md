# USB Optimization Strategy - Batch Spectrum Acquisition

## Executive Summary

**Goal**: Reduce USB overhead from **~12ms per read** to **~3-4ms per read** by batching multiple spectrum acquisitions into fewer USB transactions.

**Current Performance**:
- Single spectrum read: 12ms (1ms integration + 11ms USB overhead)
- 8 reads per cycle: 96ms total USB overhead
- **USB overhead = 7% of total cycle time**

**Target Performance**:
- Batch 4 spectra per USB transaction
- Effective overhead: 12ms / 4 = **3ms per spectrum**
- 8 reads per cycle: 24ms total USB overhead
- **Savings: 72ms per cycle (5.5% improvement)**

## Investigation Results

### Hardware Capabilities

**USB4000 Features Tested**:
```python
✅ raw_usb_bus_access: Available (raw_usb_read/raw_usb_write)
✅ continuous_strobe: Available (set_enable, set_period_micros)
✅ acquisition_delay: Listed but empty
❌ data_buffer: Listed but empty (not supported on USB4000)
❌ fast_buffer: Listed but empty (not supported on USB4000)
```

**Conclusion**: USB4000 does **NOT have hardware buffering** for multiple spectra. However, we can optimize in other ways.

## Optimization Approaches

### ❌ Approach 1: Hardware Buffering (NOT AVAILABLE)
**Concept**: Configure USB4000 to buffer multiple spectra in firmware, read in one USB transaction

**Status**: **USB4000 doesn't support this**
- `data_buffer` feature is empty
- `fast_buffer` feature is empty
- Firmware doesn't support multi-spectrum buffering

**Verdict**: Not feasible with USB4000 hardware

### ⚠️ Approach 2: Continuous Mode + Bulk Read
**Concept**: Use `continuous_strobe` to trigger rapid acquisitions, read multiple spectra quickly

**Implementation**:
```python
# Enable continuous acquisition mode
continuous_strobe = spec.features['continuous_strobe'][0]
continuous_strobe.set_period_micros(1000)  # 1ms between acquisitions
continuous_strobe.set_enable(True)

# Rapidly read multiple spectra
spectra = []
for i in range(4):
    spectra.append(spec.intensities())  # Still 12ms each, but continuous

continuous_strobe.set_enable(False)
```

**Expected savings**: Minimal
- Still need individual `intensities()` calls
- USB overhead remains ~12ms per call
- Only saves LED switching time (already optimized)

**Verdict**: Not worthwhile - doesn't address USB overhead

### ✅ Approach 3: Raw USB Bulk Transfer (ADVANCED)
**Concept**: Use `raw_usb_read()` to bypass SeaBreeze's high-level API and read spectrum data directly

**Advantages**:
- Bypass Python wrapper overhead
- Direct control of USB transactions
- Potentially read multiple spectra in one bulk transfer
- Could reduce overhead from 12ms to 2-4ms

**Challenges**:
- Requires understanding USB4000 protocol
- Need to parse raw binary spectrum data
- Complex implementation
- Risk of errors if protocol changes

**Feasibility**: Medium-High effort, uncertain gain

### ✅ Approach 4: Software-Level Averaging (CURRENT BEST OPTION)
**Concept**: Instead of averaging N scans in software sequentially, leverage the fact that integration time ≈ duration

**Current Implementation** (sequential):
```python
# Average 4 scans, 1ms integration each
for i in range(4):
    spectrum = spec.intensities()  # 12ms USB overhead × 4 = 48ms overhead
    sum += spectrum
average = sum / 4
```

**Optimized Implementation** (longer integration):
```python
# Single scan, 4ms integration (equivalent to 4× 1ms scans)
spec.integration_time_micros(4000)  # 4ms integration
spectrum = spec.intensities()  # 12ms overhead × 1 = 12ms overhead
# No averaging needed - hardware already integrated 4× longer
```

**Savings**:
- Before: 4 reads × 12ms = 48ms overhead
- After: 1 read × 12ms = 12ms overhead
- **Reduction: 36ms (75% less USB overhead)**

**Caveat**: Only works if we can tolerate longer single integration instead of averaging multiple short ones

### ✅ Approach 5: Reduce Scan Count (IMMEDIATE WIN)
**Current**: Your code uses **2-10 scans per channel** for averaging

**Question**: Do we actually need that many scans?

**Analysis**:
```python
# Current: 2 scans per channel
2 scans × 4 channels = 8 reads × 12ms = 96ms USB overhead

# Optimized: 1 scan per channel with longer integration
1 scan × 4 channels = 4 reads × 12ms = 48ms USB overhead
Savings: 48ms (50% reduction in USB overhead)
```

**Implementation**: Use `integration_time × num_scans` instead of multiple reads

### ✅ Approach 6: Parallel LED + Spectrum Read (OVERLAP)
**Concept**: Start next LED while current spectrum is being read

**Current Sequential**:
```
Channel 1: LED on → Wait → Read spectrum (12ms) →
Channel 2: LED on → Wait → Read spectrum (12ms) → ...
```

**Optimized Overlapped**:
```
Channel 1: LED on → Wait → Read spectrum (12ms) ──┐
Channel 2: LED on (overlapped) ───────────────────┘→ Wait → Read (12ms)
```

**Savings**: Overlap LED settling time with USB read
- If LED delay = 50ms and Read = 12ms
- Can hide up to 12ms of LED delay
- **Potential savings: ~40ms per cycle** (depending on timing)

**Complexity**: Medium - requires threading or async I/O

## Recommended Implementation Plan

### Phase 1: Quick Wins (Low effort, proven results)

#### Option A: Reduce Scan Count ⭐⭐⭐⭐⭐
**Effort**: 5 minutes
**Gain**: 48ms per cycle (3.7%)

**Implementation**:
```python
# In spr_data_acquisition.py
# Instead of:
num_scans = 2
integration_time = 0.02  # 20ms

# Use:
num_scans = 1
integration_time = 0.04  # 40ms (equivalent total integration)
```

**Tradeoff**: Slightly different noise characteristics, but likely negligible

#### Option B: Optimize Integration Time Strategy ⭐⭐⭐⭐
**Effort**: 15 minutes
**Gain**: 36ms per cycle per channel that uses averaging

**Change averaging strategy from**:
```python
# OLD: Multiple short scans + averaging
for i in range(num_scans):
    spectrum = read_spectrum()  # 12ms overhead each
    stack.append(spectrum)
average = np.mean(stack, axis=0)
```

**To**:
```python
# NEW: Single longer scan (no averaging needed)
integration_time *= num_scans
spectrum = read_spectrum()  # 12ms overhead once
# No averaging - hardware already integrated longer
```

### Phase 2: Medium Effort, Good Returns

#### Option C: LED/Read Overlap ⭐⭐⭐⭐
**Effort**: 2-4 hours
**Gain**: 30-40ms per cycle

**Concept**: Pipeline LED switching and spectrum reading

### Phase 3: Advanced Optimization (Consider if Phases 1-2 insufficient)

#### Option D: Raw USB Implementation ⭐⭐
**Effort**: 8-16 hours
**Gain**: Uncertain (potentially 48-72ms if we can batch)

**Risk**: High complexity, uncertain returns

## Cost/Benefit Analysis

| Approach | Effort | Gain | Risk | Priority |
|----------|--------|------|------|----------|
| **Reduce scan count** | 5 min | 48ms | Low | ⭐⭐⭐⭐⭐ |
| **Optimize integration** | 15 min | 36ms | Low | ⭐⭐⭐⭐ |
| **LED/Read overlap** | 2-4 hrs | 30-40ms | Medium | ⭐⭐⭐ |
| **Raw USB** | 8-16 hrs | ?ms | High | ⭐⭐ |
| **Continuous mode** | 2 hrs | <10ms | Medium | ⭐ |

## Answer to Your Question

**"Can we send batch commands to reduce overhead?"**

**Direct Answer**: The USB4000 hardware **does NOT support batching multiple spectra** into one USB transaction. The `data_buffer` and `fast_buffer` features are not available on this model.

**However**, we can achieve the same goal through:

1. **Reduce the number of reads** by using longer integration times instead of averaging
   - This effectively "batches" the acquisition at the hardware level
   - **Immediate 48ms savings** with 5 minutes of work

2. **Optimize the scan strategy** to minimize USB transactions
   - 1 long scan instead of N short scans
   - **36ms savings per channel** that uses averaging

3. **Advanced**: Use `raw_usb_read()` to potentially batch reads at USB protocol level
   - High effort, uncertain gain
   - Requires reverse-engineering USB4000 protocol

## Recommended Next Steps

### Immediate Action (5 minutes) ⭐
1. **Reduce scan count from 2 to 1** per channel
2. **Double the integration time** to compensate
3. **Test** that signal quality is equivalent
4. **Measure** actual cycle time improvement

**Expected outcome**: 1300ms → 1252ms (48ms savings)

### Quick Follow-up (15 minutes) ⭐
1. **Replace scan averaging with longer integration**
2. **Remove averaging loops** where possible
3. **Test** signal-to-noise ratio

**Expected outcome**: Additional 36ms savings per channel

### If More Performance Needed
1. Implement LED/Read overlap (2-4 hours)
2. Investigate raw USB approach (8-16 hours)

## Code Example: Quick Win Implementation

```python
# In spr_data_acquisition.py - Update scan strategy

# BEFORE (current):
def _acquire_spectra_for_channel(self, channel, num_scans=2):
    """Acquire and average multiple scans."""
    self.usb.set_integration_time(0.02)  # 20ms

    spectra_stack = np.zeros((num_scans, len(wavelengths)))
    for i in range(num_scans):
        spectra_stack[i] = self.usb.read_intensity()  # 12ms × 2 = 24ms overhead

    return np.mean(spectra_stack, axis=0)  # Average


# AFTER (optimized):
def _acquire_spectra_for_channel(self, channel, num_scans=1):  # Reduced to 1
    """Acquire spectrum with optimized integration time."""
    # Use longer integration instead of averaging
    self.usb.set_integration_time(0.04)  # 40ms (2× 20ms)

    spectrum = self.usb.read_intensity()  # 12ms × 1 = 12ms overhead

    return spectrum  # No averaging needed - 12ms overhead saved!
```

**Result**: 50% reduction in USB overhead for this operation.

---

**Status**: Ready to implement Phase 1 quick wins
**Next**: User decision on which optimization level to pursue
