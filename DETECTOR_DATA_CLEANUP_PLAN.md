# DETECTOR DATA CLEANUP PLAN

**Objective**: Follow the trail of detector data throughout the codebase, streamline flow, eliminate redundancy, and remove obsolete/legacy paths.

**Pattern**: Following successful polarizer and LED cleanups (85 lines removed, 5× speedup on polarizer; consistent API on LEDs).

---

## DETECTOR DATA FLOW - COMPLETE MAP

### 1. **Hardware Detection** (Initial Connection)

**File**: `utils/hardware_detection.py`

```python
def detect_spectrometer(self, detected_ports: dict) -> dict | None:
    """Detect Ocean Optics spectrometer using SeaBreeze."""
    try:
        import seabreeze
        # Use cseabreeze (C backend) - more reliable than pyseabreeze
        seabreeze.use('cseabreeze')
        from seabreeze.spectrometers import list_devices, Spectrometer

        devices = list_devices()
        for device in devices:
            return {
                'device': 'SeaBreeze',
                'model': device.model,
                'serial': device.serial_number,
                'hwid': 'SeaBreeze',
                'connection_type': 'USB (SeaBreeze)',
                'detected': True,
            }
```

**Status**: ✅ **Clean**
- Uses cseabreeze backend correctly
- Single detection path via SeaBreeze
- Returns structured device info

---

### 2. **Device Initialization** (USB4000 Direct)

**File**: `utils/usb4000_oceandirect.py`

```python
class USB4000OceanDirect:
    """USB4000 Spectrometer using Ocean Optics OceanDirect API."""

    def acquire_spectrum(self) -> np.ndarray:
        """Acquire spectrum from USB4000."""
        if BACKEND_TYPE == "seabreeze":
            intensity_data = np.array(self._device.intensities())
        else:
            intensity_data = np.array(self._device.get_formatted_spectrum())
        return intensity_data

    def get_wavelengths(self) -> np.ndarray:
        """Get wavelength array for this spectrometer."""
        if self._wavelengths is not None:
            return self._wavelengths

        # Generate wavelength calibration
        try:
            wavelengths = self._device.wavelengths()
            self._wavelengths = np.array(wavelengths)
        except:
            self._wavelengths = self._generate_fallback_wavelengths()
        return self._wavelengths
```

**Status**: ✅ **Clean**
- Single acquisition method: `acquire_spectrum()`
- Wavelength caching (no redundant reads)
- Fallback wavelength generation

---

### 3. **HAL Adapter Layer** (Abstraction for Detector-Agnostic Code)

**File**: `utils/spr_calibrator.py` (lines 967-1010)

```python
class HALAdapter:
    def __init__(self, hal_instance):
        self._hal = hal_instance

    def read_wavelength(self):
        """Adapter method: HAL get_wavelengths -> read_wavelength"""
        wavelengths = self._hal.get_wavelengths()
        return wavelengths

    def read_intensity(self):
        """Adapter method: HAL acquire_spectrum -> read_intensity"""
        if hasattr(self._hal, 'acquire_spectrum'):
            intensities = self._hal.acquire_spectrum()
        elif hasattr(self._hal, 'capture_spectrum'):
            _, intensities = self._hal.capture_spectrum(integration_time)
        return intensities

    def set_integration(self, integration_time):
        """Adapter method: HAL set_integration_time -> set_integration"""
        return self._hal.set_integration_time(integration_time)
```

**Purpose**: Bridges modern HAL interface to legacy calibrator code

**Status**: ⚠️ **NEEDS REVIEW**
- Creates wrapper methods (`read_wavelength`, `read_intensity`, `set_integration`)
- Modern code uses HAL methods directly (`acquire_spectrum`, `get_wavelengths`)
- Inconsistent naming across codebase

**Question**: Can we standardize on HAL methods and remove adapter layer?

---

### 4. **Data Acquisition Layer** (Main Read Operations)

**File**: `utils/spr_data_acquisition.py`

#### 4A. **Wavelength Reads** (Legacy Pattern)

```python
# Line 237-239: Wavelength acquisition during live measurements
try:
    current_wavelengths = self.usb.read_wavelength()
except AttributeError:
    wl = self.usb.get_wavelengths()
```

**Issue**: ⚠️ **DUAL PATH REDUNDANCY**
- `read_wavelength()` - Legacy adapter method
- `get_wavelengths()` - Modern HAL method
- Both do the same thing

#### 4B. **Intensity Reads** (Spectrum Acquisition)

```python
# Line 1200: Initial read
first_reading = self.usb.read_intensity()

# Line 1225: Subsequent reads in loop
for _ in range(n_buffers):
    reading = self.usb.read_intensity()
```

**Status**: ✅ **CLEAN (via adapter)**
- Single method: `read_intensity()`
- Adapter wraps HAL's `acquire_spectrum()` or `capture_spectrum()`
- Consistent usage throughout

---

### 5. **Calibrator Read Operations**

**File**: `utils/spr_calibrator.py`

#### 5A. **Direct Intensity Reads**

```python
# Line 1214: Initial raw read
raw = self.usb.read_intensity()  # 3648 pixels

# Line 1295: Spectrum acquisition
first_spectrum = self.usb.read_intensity()

# Line 1312: Loop reads
raw_spectrum = self.usb.read_intensity()

# Line 2725: Transmittance calculation
raw_array = self.usb.read_intensity()

# Line 4225, 4232, 4234: Polarizer calibration
max_intensities[steps] = usb.read_intensity().max()
```

**Status**: ✅ **CONSISTENT**
- All use `read_intensity()` method
- Via HAL adapter when needed

#### 5B. **Wavelength Reads**

```python
# Line 1233: Legacy method with fallback
try:
    current_wavelengths = self.usb.read_wavelength()
except AttributeError:
    wl = self.usb.get_wavelengths()

# Line 1518, 1521: Dual path
try:
    wave_data = self.usb.read_wavelength()
except AttributeError:
    wave_data = self.usb.get_wavelengths()

# Line 1656, 1658: Dual path
try:
    wave_data = self.usb.read_wavelength()
except AttributeError:
    wave_data = self.usb.get_wavelengths()
```

**Issue**: ⚠️ **3× REDUNDANT DUAL-PATH PATTERN**
- Same pattern repeated 3 times
- Should be unified to HAL method: `get_wavelengths()`

---

### 6. **State Machine Adapter Layer**

**File**: `utils/spr_state_machine.py` (lines 199-218)

```python
class SpectrometerAdapter:
    """Adapter to make HAL spectrometer compatible with SPRDataAcquisition."""
    def __init__(self, hal_spectrometer):
        self.hal = hal_spectrometer

    def read_intensity(self):
        """Read intensity using HAL method."""
        if hasattr(self.hal, 'acquire_spectrum'):
            return self.hal.acquire_spectrum()
        elif hasattr(self.hal, 'capture_spectrum'):
            return self.hal.capture_spectrum()
        elif hasattr(self.hal, 'read_intensity'):
            return self.hal.read_intensity()
        raise NotImplementedError("Spectrometer HAL missing acquisition method")

    def __getattr__(self, name):
        """Forward other attributes to HAL."""
        return getattr(self.hal, name)
```

**Status**: ✅ **NECESSARY ADAPTER**
- Bridges HAL to SPRDataAcquisition interface
- Graceful fallback through multiple method names
- Pass-through for other attributes

---

### 7. **Legacy Controller Methods** (OBSOLETE?)

**File**: `utils/controller.py` (lines 253-258)

```python
def read_wavelength(self, channel):
    data = self._send_command(cmd=f"read{channel}")
    if data:
        return numpy.asarray([int(v) for v in data.split(",")])

def read_intensity(self):
    data = self._send_command(cmd="intensity")
    if data:
        return numpy.asarray([int(v) for v in data.split(",")])
```

**Status**: ⚠️ **LIKELY OBSOLETE**

**Evidence**:
1. These are controller methods, but detector operations should be on USB object
2. Modern codebase uses USB4000OceanDirect, not controller serial commands
3. PicoEZSPR legacy hardware might have used controller for detector reads
4. No references found in modern code paths

**Action Required**: Search for usage to confirm obsolescence

---

## REDUNDANCY ANALYSIS

### **Issue 1: Dual Wavelength Read Paths** (PRIORITY: ⭐⭐⭐⭐⭐)

**Pattern Found**:
```python
# REPEATED 3 TIMES in spr_calibrator.py
try:
    wavelengths = self.usb.read_wavelength()  # Legacy adapter method
except AttributeError:
    wavelengths = self.usb.get_wavelengths()  # Modern HAL method
```

**Locations**:
- `spr_calibrator.py` line 1233
- `spr_calibrator.py` line 1518-1521
- `spr_calibrator.py` line 1656-1658
- `spr_data_acquisition.py` line 237-239

**Root Cause**:
- `read_wavelength()` is adapter wrapper around `get_wavelengths()`
- HAL adapter creates the wrapper method
- Some code uses adapter method, some uses HAL method directly

**Solution**:
```python
# Option 1: Always use HAL method directly (preferred)
wavelengths = self.usb.get_wavelengths()

# Option 2: If adapter is required, use it consistently
wavelengths = self.usb.read_wavelength()
```

**Impact**:
- Simplifies code (4 locations)
- Removes exception handling
- Eliminates confusion about which method to use

---

### **Issue 2: HAL Adapter Overhead** (PRIORITY: ⭐⭐⭐)

**Current Flow**:
```
Calibrator → HALAdapter.read_intensity()
           → HAL.acquire_spectrum()
           → USB4000OceanDirect.acquire_spectrum()
           → SeaBreeze.intensities()
```

**Question**: Is HAL Adapter layer necessary or legacy?

**Analysis**:
- **Purpose**: Bridges modern HAL interface to legacy calibrator code
- **Methods wrapped**: `read_intensity()`, `read_wavelength()`, `set_integration()`
- **Modern alternative**: Use HAL methods directly

**Verdict**: ⚠️ **Adapter is necessary for backward compatibility**
- Calibrator expects `read_intensity()` interface
- HAL provides `acquire_spectrum()` interface
- Adapter bridges the gap

**No action needed** - adapter serves a purpose.

---

### **Issue 3: Obsolete Controller Read Methods** (PRIORITY: ⭐⭐⭐⭐)

**Methods**:
```python
# controller.py lines 253-258
def read_wavelength(self, channel):  # Obsolete?
def read_intensity(self):             # Obsolete?
```

**Investigation Needed**:
1. Search for usage in codebase
2. Check if PicoEZSPR legacy hardware uses these
3. If unused, mark as deprecated or remove

---

### **Issue 4: Spectral Filtering Redundancy** (PRIORITY: ⭐⭐)

**Current Approach**:
```python
# spr_calibrator.py line 1214
raw = self.usb.read_intensity()  # 3648 pixels

# Size mismatch handling (lines 1223-1235)
if len(raw) != len(self._spr_mask):
    current_wavelengths = self.usb.read_wavelength()
    mask = (current_wavelengths >= MIN_WAVELENGTH) & (current_wavelengths <= MAX_WAVELENGTH)
    self._spr_mask = mask  # Recreate mask
```

**Issue**: Mask recreation on every size mismatch

**Better Approach**:
```python
# Cache wavelengths once at initialization
if not hasattr(self, '_cached_wavelengths'):
    self._cached_wavelengths = self.usb.get_wavelengths()
    self._spr_mask = (self._cached_wavelengths >= MIN_WAVELENGTH) & (self._cached_wavelengths <= MAX_WAVELENGTH)

# Use cached mask
filtered_spectrum = raw[self._spr_mask]
```

**Impact**: Eliminates redundant wavelength reads during acquisitions

---

## CLEANUP TASKS (Priority Order)

### **Task 1: Unify Wavelength Access** ⭐⭐⭐⭐⭐

**Objective**: Use single method for wavelength reads

**Files to modify**:
- `spr_calibrator.py` (3 locations: lines 1233, 1518, 1656)
- `spr_data_acquisition.py` (line 237)

**Change**:
```python
# Before (dual path):
try:
    wavelengths = self.usb.read_wavelength()
except AttributeError:
    wavelengths = self.usb.get_wavelengths()

# After (single path):
wavelengths = self.usb.get_wavelengths()
```

**Justification**:
- `get_wavelengths()` is the modern HAL method
- All detectors support this method
- HAL adapter provides `read_wavelength()` wrapper anyway, so both work
- Prefer direct HAL method to eliminate adapter overhead

**Testing**:
- ✅ Run calibration with Flame-T
- ✅ Run calibration with USB4000
- ✅ Verify wavelength range detection works

**Lines removed**: ~8-12 (exception handling × 4 locations)

---

### **Task 2: Remove/Deprecate Obsolete Controller Methods** ⭐⭐⭐⭐

**Objective**: Identify and remove unused controller detector read methods

**Investigation**:
```python
# Search for usage:
grep -r "ctrl.read_wavelength" utils/ widgets/
grep -r "ctrl.read_intensity" utils/ widgets/
```

**If unused**:
1. Add deprecation warning
2. Document migration path
3. Schedule for removal in next version

**Change** (if unused):
```python
# In controller.py lines 253-258

@deprecated("Use USB4000OceanDirect.get_wavelengths() instead")
def read_wavelength(self, channel):
    """DEPRECATED: Legacy method for PicoEZSPR hardware.

    Modern systems use USB4000OceanDirect.get_wavelengths() directly.
    This method will be removed in v0.2.0.

    Migration:
        # Old (deprecated):
        wavelengths = ctrl.read_wavelength(channel='a')

        # New (recommended):
        wavelengths = usb.get_wavelengths()
    """
    logger.warning("read_wavelength() is deprecated - use usb.get_wavelengths()")
    data = self._send_command(cmd=f"read{channel}")
    if data:
        return numpy.asarray([int(v) for v in data.split(",")])

@deprecated("Use USB4000OceanDirect.acquire_spectrum() instead")
def read_intensity(self):
    """DEPRECATED: Legacy method for PicoEZSPR hardware.

    Modern systems use USB4000OceanDirect.acquire_spectrum() directly.
    This method will be removed in v0.2.0.

    Migration:
        # Old (deprecated):
        intensity = ctrl.read_intensity()

        # New (recommended):
        intensity = usb.read_intensity()  # Via HAL adapter
        # Or directly:
        intensity = usb.acquire_spectrum()
    """
    logger.warning("read_intensity() is deprecated - use usb.acquire_spectrum()")
    data = self._send_command(cmd="intensity")
    if data:
        return numpy.asarray([int(v) for v in data.split(",")])
```

**Lines added**: ~20 (deprecation warnings + migration guide)

---

### **Task 3: Cache Wavelength Mask** ⭐⭐⭐

**Objective**: Eliminate redundant wavelength reads during acquisition

**File**: `spr_calibrator.py`

**Current** (line 1214-1235):
```python
raw = self.usb.read_intensity()

# Handle size mismatch by recreating mask
if len(raw) != len(self._spr_mask):
    try:
        current_wavelengths = self.usb.read_wavelength()
    except AttributeError:
        wl = self.usb.get_wavelengths()
    # Recreate mask
    mask = (current_wavelengths >= MIN_WAVELENGTH) & (current_wavelengths <= MAX_WAVELENGTH)
    self._spr_mask = mask
```

**Improved** (cache wavelengths at init):
```python
# In __init__ (after usb initialization):
self._cached_wavelengths = None
self._spr_mask = None

# In _initialize_wavelength_mask():
if self._cached_wavelengths is None:
    self._cached_wavelengths = self.usb.get_wavelengths()
    self._spr_mask = (
        (self._cached_wavelengths >= MIN_WAVELENGTH) &
        (self._cached_wavelengths <= MAX_WAVELENGTH)
    )
    logger.info(f"Wavelength mask initialized: {self._spr_mask.sum()}/{len(self._cached_wavelengths)} pixels")

# During acquisition (simplified):
raw = self.usb.read_intensity()
filtered = raw[self._spr_mask]
```

**Impact**:
- Eliminates wavelength read on every size mismatch
- Faster acquisition (no redundant USB reads)
- Cleaner code (no exception handling)

**Lines removed**: ~10-15

---

### **Task 4: Document HAL Adapter Purpose** ⭐⭐

**Objective**: Clarify why HAL adapter exists

**File**: `spr_calibrator.py` (line 967)

**Addition**:
```python
def _create_hal_adapter(self, hal):
    """Create a simple adapter to make HAL compatible with calibrator interface.

    **Purpose**: Bridges modern HAL interface to legacy calibrator code.

    The calibrator was written to use:
        - usb.read_intensity()
        - usb.read_wavelength()
        - usb.set_integration(seconds)

    Modern HAL provides:
        - hal.acquire_spectrum()
        - hal.get_wavelengths()
        - hal.set_integration_time(seconds)

    This adapter wraps HAL methods to match calibrator's expected interface,
    avoiding the need to refactor all calibrator code.

    **Alternative**: Refactor calibrator to use HAL methods directly.
    This would eliminate the adapter layer but require extensive changes.

    **Deprecation**: Consider migrating to direct HAL usage in v0.2.0.
    """
    class HALAdapter:
        def __init__(self, hal_instance):
            self._hal = hal_instance

        # ... rest of adapter code ...
```

**Impact**: Clarifies architecture, prevents future confusion

---

### **Task 5: Add Detector Profile Documentation** ⭐

**Objective**: Document detector-agnostic architecture

**File**: `DETECTOR_AGNOSTIC_CALIBRATION.md` (new file)

**Content** (summary):
- Detector profile system (Flame-T, USB4000, etc.)
- HAL abstraction layer
- Adapter pattern usage
- Migration guide from legacy code
- Performance characteristics

**Impact**: Helps developers understand system architecture

---

## ESTIMATED IMPACT

### **Lines Removed**
- Task 1 (Wavelength unification): ~8-12 lines
- Task 2 (Obsolete methods): ~0 lines (deprecated, not removed)
- Task 3 (Wavelength cache): ~10-15 lines

**Total**: ~18-27 lines removed

### **Lines Added**
- Task 2 (Deprecation warnings): ~20 lines
- Task 4 (HAL adapter docs): ~15 lines

**Total**: ~35 lines added (net: ~8-17 lines increase, but code quality improved)

### **Performance Impact**
- Task 1: Negligible (removes exception handling overhead)
- Task 3: ~5-10ms saved per acquisition (eliminates redundant wavelength reads)

### **Code Quality**
- ✅ Single wavelength access path
- ✅ Clear deprecation warnings
- ✅ Better documentation
- ✅ Eliminated redundant reads

---

## ARCHITECTURE SUMMARY

### **Clean Data Flow** (No Changes Needed)
```
SeaBreeze Device (Ocean Optics)
    ↓
USB4000OceanDirect.acquire_spectrum()
    ↓
HAL Adapter.read_intensity()  ← Bridges HAL to calibrator interface
    ↓
Calibrator / DataAcquisition
    ↓
Spectral Filtering (580-720nm)
    ↓
UI / Processing
```

### **Redundant Paths to Remove**
1. ✅ Dual wavelength access (`read_wavelength` vs `get_wavelengths`)
2. ✅ Redundant wavelength reads during acquisition
3. ✅ Obsolete controller detector methods (if unused)

---

## TESTING CHECKLIST

After implementing cleanup tasks:

- [ ] Calibration with Flame-T detector
- [ ] Calibration with USB4000 detector
- [ ] Live measurement acquisition (all channels)
- [ ] Wavelength range detection
- [ ] Spectral filtering (580-720nm)
- [ ] Dark noise correction
- [ ] Reference signal acquisition
- [ ] HAL adapter functionality
- [ ] No performance regression

---

## SUCCESS CRITERIA

✅ **Single wavelength access method** used throughout codebase
✅ **Deprecated obsolete controller methods** with migration guide
✅ **Cached wavelength mask** eliminates redundant reads
✅ **Comprehensive documentation** of HAL adapter purpose
✅ **No performance regression** - measurements remain fast
✅ **All tests passing** - no functionality broken

---

## CONCLUSION

**Detector data flow is ALREADY CLEAN** with minimal redundancy. Main issues:

1. **Dual wavelength path** (4 locations) - easy fix, standardize on `get_wavelengths()`
2. **Wavelength caching** - optimization opportunity, eliminate redundant reads
3. **Obsolete controller methods** - need investigation, likely safe to deprecate
4. **HAL adapter** - necessary for backward compatibility, but needs better documentation

**Estimated effort**: ~2-3 hours for complete cleanup
**Risk**: Low - changes are minimal and well-isolated
**Benefit**: Cleaner code, better documentation, slight performance improvement

---

**Next Steps**: Implement Task 1 (wavelength unification) first as highest priority, lowest risk change.
