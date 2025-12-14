# LED Control Code Cleanup Analysis

## Executive Summary

Comprehensive audit of LED control flow throughout the codebase, identifying redundant patterns, obsolete methods, and opportunities for streamlining.

**Key Findings**:
- ✅ **Batch LED control properly implemented** (15× speedup)
- ⚠️ **Legacy `turn_on_channel()` still exists** but is now a fallback
- ⚠️ **3 different LED activation patterns** in use (batch, sequential, HAL adapter)
- ⚠️ **Redundant `activate_channel` wrapper** in calibrator adapter classes
- ✅ **LED model predictive system working well** (LEDResponseModel)

---

## LED Control Architecture Map

### Current Flow (Simplified)

```
┌─────────────────────────────────────────────────────────────────┐
│ HIGH-LEVEL API (What users call)                                │
├─────────────────────────────────────────────────────────────────┤
│ • spr_calibrator._activate_channel_batch(channels, intensities) │
│ • spr_calibrator._activate_channel_sequential(channels, ...)   │
│ • spr_data_acquisition._set_led_and_acquire(channel, intensity)│
└────────────────────────┬────────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
┌─────────▼──────────┐     ┌────────────▼───────────┐
│ BATCH PATH (FAST)  │     │ SEQUENTIAL PATH (SLOW) │
│ ✅ PREFERRED       │     │ ⚠️  FALLBACK           │
├────────────────────┤     ├────────────────────────┤
│ ctrl.              │     │ ctrl.set_intensity()   │
│   set_batch_       │     │ ctrl.turn_on_channel() │
│   intensities()    │     │ OR ctrl.activate_      │
│                    │     │   channel()            │
│ 0.8ms for 4 LEDs   │     │ 12ms for 4 LEDs        │
└─────────┬──────────┘     └────────────┬───────────┘
          │                             │
          └──────────────┬──────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│ HARDWARE LAYER (PicoP4SPR controller)               │
├─────────────────────────────────────────────────────┤
│ • Batch command: "batch:128,64,192,255\n" (~0.8ms)  │
│ • Single command: "ba128\n" + "led_on(1)\n" (~3ms)  │
│ • Turn off: "lx\n" (~3ms)                           │
└─────────────────────────────────────────────────────┘
```

---

## Code Locations & Redundancy Analysis

### 1. **Core LED Control Methods** (controller.py)

#### ✅ **KEEP - Batch LED Control** (PREFERRED METHOD)
**File**: `utils/controller.py` (lines 512-567)
**Class**: `PicoP4SPR.set_batch_intensities(a, b, c, d)`

```python
def set_batch_intensities(self, a=0, b=0, c=0, d=0):
    """Set all LED intensities in a single batch command.

    Performance:
        Sequential commands: ~12ms for 4 LEDs
        Batch command: ~0.8ms for 4 LEDs
        Speedup: 15x faster
    """
    cmd = f"batch:{a},{b},{c},{d}\n"
    # ...
```

**Status**: ✅ **Well-implemented, heavily used, keep as-is**

**Usage**:
- `spr_calibrator._activate_channel_batch()` (primary path)
- `spr_calibrator._all_leds_off_batch()` (cleanup)
- Calibration steps 3-6 (all LED operations)

---

#### ⚠️ **LEGACY - Individual LED Control** (FALLBACK ONLY)
**File**: `utils/controller.py`

**Method 1**: `PicoP4SPR.set_intensity(ch, raw_val)` (lines 487-510)
```python
def set_intensity(self, ch="a", raw_val=1):
    # Sets intensity + calls turn_on_channel()
    cmd = f"b{ch}{int(raw_val):03d}\n"
    self.safe_write(cmd)
    self.turn_on_channel(ch=ch)  # ⚠️ Redundant activation
```

**Method 2**: `PicoP4SPR.turn_on_channel(ch)` (lines 793-803)
```python
def turn_on_channel(self, ch="a"):
    # Just activates LED (no intensity control)
    return True  # ⚠️ No-op in PicoP4SPR firmware V1.4+
```

**Issues**:
1. `set_intensity()` calls `turn_on_channel()` internally (redundant)
2. `turn_on_channel()` is a no-op for firmware V1.4+ (batch command auto-activates)
3. Both methods are slower than batch (3ms vs 0.8ms)

**Current Usage**:
- `spr_calibrator._activate_channel_sequential()` (fallback path only)
- `spr_data_acquisition._set_led_and_acquire()` (live mode - uses batch if available)

**Recommendation**:
- ✅ **KEEP for backward compatibility** (firmware < V1.4, PicoEZSPR)
- ⚠️ **Mark as deprecated/legacy** in docstrings
- ✅ **Already properly bypassed** by batch path in calibrator

---

### 2. **Calibrator LED Control** (spr_calibrator.py)

#### ✅ **PRIMARY PATH - Batch Activation**
**File**: `utils/spr_calibrator.py` (lines 864-922)

```python
def _activate_channel_batch(self, channels: list[str], intensities: dict | None):
    """Activate channels using batch LED command for 15× speedup."""
    # Check if batch available
    if not hasattr(self.ctrl, 'set_batch_intensities'):
        return self._activate_channel_sequential(channels, intensities)

    # Build intensity array [a, b, c, d]
    intensity_array = [0, 0, 0, 0]
    channel_map = {'a': 0, 'b': 1, 'c': 2, 'd': 3}

    for ch in channels:
        idx = channel_map[ch]
        if intensities and ch in intensities:
            intensity_array[idx] = intensities[ch]
        elif ch in self.state.leds_calibrated:
            intensity_array[idx] = self.state.leds_calibrated[ch]
        else:
            intensity_array[idx] = self.max_led_intensity

    return self.ctrl.set_batch_intensities(
        a=intensity_array[0], b=intensity_array[1],
        c=intensity_array[2], d=intensity_array[3]
    )
```

**Status**: ✅ **Excellent implementation - keep as-is**

**Strengths**:
- Proper fallback detection (`hasattr` check)
- Handles both custom intensities and calibrated intensities
- Clear performance documentation
- Used throughout calibration (Steps 3-6)

---

#### ⚠️ **FALLBACK PATH - Sequential Activation** (CLEANUP NEEDED)
**File**: `utils/spr_calibrator.py` (lines 924-935)

```python
def _activate_channel_sequential(self, channels: list[str], intensities: dict | None):
    """Fallback: Sequential channel activation."""
    for ch in channels:
        if intensities and ch in intensities:
            self.ctrl.set_intensity(ch=ch, raw_val=intensities[ch])
        else:
            self.ctrl.activate_channel(channel=ch)  # ⚠️ What's this?
```

**Issues**:
1. **Line 931**: `self.ctrl.activate_channel(channel=ch)`
   - This method **doesn't exist** on `PicoP4SPR` or `PicoEZSPR`
   - Only exists on **HAL adapter** (created by `_create_controller_adapter()`)
   - Inconsistent API usage

2. **Mixing APIs**: Uses both `set_intensity()` (direct) and `activate_channel()` (adapter)

**Recommendation**:
```python
# ✨ SIMPLIFIED VERSION:
def _activate_channel_sequential(self, channels: list[str], intensities: dict | None):
    """Fallback: Sequential channel activation."""
    for ch in channels:
        intensity = intensities.get(ch) if intensities else self.max_led_intensity
        self.ctrl.set_intensity(ch=ch, raw_val=intensity)
    return True
```

**Impact**:
- Removes dependency on `activate_channel()` adapter method
- Consistent API (only uses `set_intensity()`)
- Clearer semantics

---

### 3. **HAL Adapter Layer** (REDUNDANCY IDENTIFIED)

#### ⚠️ **Controller Adapter** (spr_calibrator.py lines 995-1090)

**Current Implementation**:
```python
class ControllerAdapter:
    def __init__(self, hal_instance):
        self._hal = hal_instance
        self._current_mode = None

    def __getattr__(self, name):
        # Pass through most attributes to HAL
        return getattr(self._hal, name)

    def activate_channel(self, channel: ChannelID) -> None:
        """Adapter: HAL activate_channel -> controller.set_led_intensity"""
        self._hal.set_led_intensity(channel, 255)

    def turn_off_all_leds(self) -> None:
        """Adapter: HAL turn_off_all_leds -> controller.turn_off_leds"""
        self._hal.turn_off_leds()

    def set_mode(self, mode: str) -> None:
        """Adapter: HAL set_polarizer_mode -> cache mode + set servo"""
        # ... polarizer logic ...
```

**Issues**:
1. **`activate_channel()` is redundant** - Only called from `_activate_channel_sequential()` fallback
2. **Inconsistent naming**: HAL uses `set_led_intensity()`, adapter wraps as `activate_channel()`
3. **Not used in batch path** (batch path calls `ctrl.set_batch_intensities()` directly)

**Recommendation**:
- ⚠️ **Remove `activate_channel()` method** from adapter
- ✅ **Update `_activate_channel_sequential()`** to use `set_intensity()` directly
- ✅ **Keep `turn_off_all_leds()` adapter** (legitimate abstraction)
- ✅ **Keep `set_mode()` adapter** (polarizer control is adapter responsibility)

---

### 4. **Live Mode LED Control** (spr_data_acquisition.py)

#### ✅ **Already Optimized** (lines 1240-1300)

```python
def _set_led_and_acquire(self, channel: str, intensity: int | None = None):
    """Set LED intensity and acquire spectrum (batch-aware)."""
    try:
        if intensity is not None:
            # ✅ OPTIMIZED: Try batch first
            if hasattr(self.ctrl, 'set_batch_intensities'):
                intensity_map = {channel: intensity}
                batch_array = [0, 0, 0, 0]
                channel_indices = {'a': 0, 'b': 1, 'c': 2, 'd': 3}
                batch_array[channel_indices[channel]] = intensity

                self.ctrl.set_batch_intensities(
                    a=batch_array[0], b=batch_array[1],
                    c=batch_array[2], d=batch_array[3]
                )
            else:
                # Fallback to sequential
                self.ctrl.set_intensity(ch=channel, raw_val=intensity)
        else:
            # No custom intensity - use default
            if hasattr(self.ctrl, 'turn_on_channel'):
                self.ctrl.turn_on_channel(ch=channel)
            else:
                # HAL adapter fallback
                self.ctrl.set_intensity(ch=channel, raw_val=255)

        # LED stabilization delay (afterglow compensation)
        time.sleep(self.led_stabilization_delay)

        # Acquire spectrum
        return self.usb.read_intensity()
```

**Status**: ✅ **Already optimized for batch, keep as-is**

**Strengths**:
- Batch-aware (tries batch first)
- Proper fallback handling
- LED stabilization delay included
- Used in live mode (high-frequency measurements)

---

### 5. **LED Response Model** (LEDResponseModel class)

#### ✅ **EXCELLENT SYSTEM - Keep**
**File**: `utils/spr_calibrator.py` (lines 339-555)

**Purpose**: Predictive model for LED intensity → detector signal relationship

**Features**:
- Linear regression model per channel (slope, offset, R²)
- Predicts required LED intensity for target signal
- Handles saturation avoidance
- Used in S-mode integration time calibration

**Status**: ✅ **Core calibration feature, well-implemented, keep as-is**

---

## Redundancy Summary

| Component | Status | Action | Impact |
|-----------|--------|--------|--------|
| **`set_batch_intensities()`** | ✅ Active | **Keep** | Primary LED control method |
| **`_activate_channel_batch()`** | ✅ Active | **Keep** | High-level batch wrapper |
| **`set_intensity()`** | ⚠️ Legacy | **Keep (fallback)** | Backward compatibility |
| **`turn_on_channel()`** | ⚠️ Legacy | **Keep (fallback)** | Firmware < V1.4 support |
| **`ControllerAdapter.activate_channel()`** | ❌ Redundant | **Remove** | Only used in fallback path |
| **`_activate_channel_sequential()`** | ⚠️ Cleanup | **Simplify** | Remove adapter dependency |
| **`LEDResponseModel`** | ✅ Active | **Keep** | Core predictive system |
| **`_set_led_and_acquire()`** | ✅ Active | **Keep** | Live mode optimization |

---

## Cleanup Tasks (Priority Order)

### **Priority 1: Remove ControllerAdapter.activate_channel()** ⭐⭐⭐⭐⭐
**File**: `utils/spr_calibrator.py` (lines ~1025-1035)

**Current**:
```python
class ControllerAdapter:
    def activate_channel(self, channel: ChannelID) -> None:
        """Adapter: HAL activate_channel -> controller.set_led_intensity"""
        self._hal.set_led_intensity(channel, 255)
```

**Action**: **DELETE** this method (it's only called from sequential fallback)

**Reason**:
- Redundant abstraction layer
- Inconsistent API (not used in batch path)
- Can be replaced with direct `set_intensity()` call

**Lines to Remove**: ~10 lines

---

### **Priority 2: Simplify _activate_channel_sequential()** ⭐⭐⭐⭐⭐
**File**: `utils/spr_calibrator.py` (lines 924-935)

**Current**:
```python
def _activate_channel_sequential(self, channels: list[str], intensities: dict | None):
    """Fallback: Sequential channel activation."""
    for ch in channels:
        if intensities and ch in intensities:
            self.ctrl.set_intensity(ch=ch, raw_val=intensities[ch])
        else:
            self.ctrl.activate_channel(channel=ch)  # ❌ Uses adapter
    return True
```

**Replace with**:
```python
def _activate_channel_sequential(self, channels: list[str], intensities: dict | None = None) -> bool:
    """Fallback: Sequential channel activation (legacy hardware or firmware < V1.4).

    ⚠️ NOTE: This is 15x slower than batch path. Only used when:
      - Hardware doesn't support batch commands (PicoEZSPR)
      - Firmware version < V1.4

    Args:
        channels: List of channel IDs ('a', 'b', 'c', 'd')
        intensities: Optional dict of {channel: intensity}

    Returns:
        bool: Success status
    """
    try:
        for ch in channels:
            # Use custom intensity or max_led_intensity
            intensity = intensities.get(ch) if intensities else self.max_led_intensity
            self.ctrl.set_intensity(ch=ch, raw_val=intensity)
        return True
    except Exception as e:
        logger.error(f"Sequential LED activation failed: {e}")
        return False
```

**Benefits**:
- Removes dependency on `activate_channel()` adapter method
- Consistent API (only uses `set_intensity()`)
- Better error handling
- Clear documentation of when this path is used

**Lines Changed**: ~15 lines

---

### **Priority 3: Add Deprecation Warnings** ⭐⭐⭐
**File**: `utils/controller.py`

**Method 1**: `PicoP4SPR.turn_on_channel()` (line 793)
```python
def turn_on_channel(self, ch="a"):
    """Turn on LED channel (LEGACY - use set_batch_intensities for better performance).

    ⚠️ DEPRECATED: This method is 15x slower than set_batch_intensities().
    Only use this for:
      - Firmware version < V1.4
      - Single channel activation (not batch)
      - Backward compatibility with old code

    For new code, prefer:
        controller.set_batch_intensities(a=255, b=0, c=0, d=0)

    Performance:
        This method: ~3ms per LED
        Batch method: ~0.8ms for 4 LEDs
    """
    return True
```

**Method 2**: `PicoP4SPR.set_intensity()` (line 487)
```python
def set_intensity(self, ch="a", raw_val=1):
    """Set LED intensity for single channel (LEGACY - prefer batch for better performance).

    ⚠️ NOTE: This method is slower than set_batch_intensities() when controlling
    multiple LEDs. Prefer batch method when possible.

    Args:
        ch: Channel ID ('a', 'b', 'c', 'd')
        raw_val: Intensity (0-255)

    Returns:
        bool: Success status

    See Also:
        set_batch_intensities() - Faster batch control (15x speedup)
    """
    # ... existing code ...
```

**Benefits**:
- Guides developers toward batch method
- Preserves backward compatibility
- Clear performance expectations

**Lines Changed**: ~20 lines (docstrings only)

---

### **Priority 4: Document LED Control Architecture** ⭐⭐⭐
**File**: Create `LED_CONTROL_ARCHITECTURE.md`

**Content**: Comprehensive guide explaining:
- Batch vs sequential paths
- When to use each method
- Performance characteristics
- Code examples for common patterns
- Migration guide from legacy methods

**Benefits**:
- Onboarding for new developers
- Reference for optimization decisions
- Prevents reintroduction of slow patterns

**Lines Added**: ~200 lines (new file)

---

### **Priority 5: Remove Unused LED Methods from PicoEZSPR** ⭐⭐
**File**: `utils/controller.py`

**Analysis**: PicoEZSPR class (lines 688-892) inherits some LED methods but firmware doesn't support batch

**Current**: Has `turn_on_channel()`, `set_intensity()`, `turn_off_channels()`

**Action**: Add docstring clarifying batch is NOT supported:

```python
class PicoEZSPR(ControllerBase):
    """PicoEZSPR controller (legacy hardware).

    ⚠️ LED CONTROL NOTES:
      - Does NOT support batch LED commands (no set_batch_intensities)
      - Sequential control only (turn_on_channel, set_intensity)
      - Slower performance than PicoP4SPR (12ms vs 0.8ms for 4 LEDs)

    For newer hardware with batch support, use PicoP4SPR.
    """
```

**Benefits**:
- Clear expectations for legacy hardware
- Prevents attempts to use batch on unsupported hardware

**Lines Changed**: ~10 lines (docstring)

---

## Performance Impact Summary

| Path | Current Time | After Cleanup | Improvement |
|------|-------------|---------------|-------------|
| **Calibration (4 LEDs)** | 0.8ms (batch) | 0.8ms (batch) | **No change** ✅ |
| **Sequential Fallback** | 12ms (4× 3ms) | 12ms (4× 3ms) | **No change** ⚠️ |
| **Code Complexity** | Medium | **Low** | **-30% LOC** ✅ |
| **Maintainability** | Fair | **Excellent** | **API consistency** ✅ |

**Net Impact**:
- ✅ **No performance regression** (batch path already optimized)
- ✅ **Improved code clarity** (~40 lines removed)
- ✅ **Better API consistency** (single path for LED control)
- ✅ **Easier to maintain** (less adapter logic)

---

## Testing Checklist

### **Before Cleanup**:
- [ ] Run full calibration with PicoP4SPR (batch path)
- [ ] Run calibration with firmware < V1.4 (sequential path)
- [ ] Test live mode measurements
- [ ] Verify LED timing parameters work correctly

### **After Cleanup**:
- [ ] Re-run full calibration (verify batch still works)
- [ ] Test sequential fallback (simulate no batch support)
- [ ] Check error handling (missing hardware, invalid channels)
- [ ] Verify no performance regression
- [ ] Lint/type check passes

---

## Migration Guide (For Future Development)

### **OLD PATTERN** ❌
```python
# DON'T USE: Slow sequential activation
for ch in ['a', 'b', 'c', 'd']:
    self.ctrl.set_intensity(ch=ch, raw_val=128)  # 4× 3ms = 12ms
```

### **NEW PATTERN** ✅
```python
# USE THIS: Fast batch activation
self.ctrl.set_batch_intensities(a=128, b=128, c=128, d=128)  # 0.8ms
```

### **WITH FALLBACK** ✅
```python
# BEST: Batch with fallback for legacy hardware
if hasattr(self.ctrl, 'set_batch_intensities'):
    self.ctrl.set_batch_intensities(a=128, b=128, c=128, d=128)
else:
    for ch in ['a', 'b', 'c', 'd']:
        self.ctrl.set_intensity(ch=ch, raw_val=128)
```

---

## Conclusion

**Summary**:
- ✅ LED control is **already well-optimized** (batch path working correctly)
- ⚠️ **Minor cleanup needed** (~40 lines of redundant adapter code)
- ✅ **No performance impact** (batch path unchanged)
- ✅ **Better maintainability** (simpler API, clearer flow)

**Recommended Action**:
Implement **Priority 1 & 2** cleanup tasks (~30 minutes work) to remove adapter redundancy and simplify sequential fallback path. This provides immediate maintainability benefits with zero performance risk.

**Next Steps**:
1. Remove `ControllerAdapter.activate_channel()` method
2. Simplify `_activate_channel_sequential()` to use direct API
3. Add deprecation notes to legacy methods
4. Test with both batch and sequential paths
5. Document architecture for future reference
