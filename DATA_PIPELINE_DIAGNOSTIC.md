# Data Pipeline Diagnostic Report

## Data Shape Integrity Analysis

### ✅ **Raw Data Shape is PRESERVED Correctly**

The data pipeline maintains array shapes throughout processing:

```python
# Pipeline flow:
1. USB Read:           np.array([...])  # Shape: (2048,)
2. Wavelength Trim:    spectrum[min:max]  # Shape: (1800,)
3. Dark Subtraction:   spectrum - dark_noise  # Shape: (1800,)
4. Spectral Correction: spectrum * weights  # Shape: (1800,)
5. Afterglow Correct:  spectrum - scalar  # Shape: (1800,)
6. Emit to UI:         full_spectrum  # Shape: (1800,)
```

**All operations preserve numpy array structure** - no shape mutations occur.

---

## Potential Issues Causing Real Live Data Problems

### Issue #1: **Wavelength Array Mismatch** 🔴

**Location**: `data_acquisition_manager.py` lines 420-440

**Problem**: Length mismatch between raw spectrum and wave_data during live acquisition.

```python
# During calibration:
self.wave_data = wave_data[wave_min_index:wave_max_index]  # Trimmed once

# During live acquisition:
raw_spectrum = usb.read_intensity()  # Full length (2048)

# Mismatch occurs here:
if len(raw_spectrum) != len(self.wave_data):  # LIKELY ALWAYS TRUE
    # Falls back to reading full wavelength array EVERY acquisition
    full_wave = usb.read_wavelength()  # EXPENSIVE - adds ~50ms per channel
```

**Impact**:
- Adds 200ms+ per cycle (4 channels × 50ms)
- May cause data lag/stutter
- USB communication bottleneck

**Fix Needed**:
Store `wave_min_index` and `wave_max_index` from calibration, reuse during acquisition:
```python
# Store indices during calibration:
self.wave_min_index = wave_min_index
self.wave_max_index = wave_max_index

# Use during acquisition:
raw_spectrum = raw_spectrum[self.wave_min_index:self.wave_max_index]
```

### Issue #2: **Stop Cursor Not Following** 🔴

**Location**: `main_simplified.py` lines 404-409

**Problem**: Cursor movement check has correct logic BUT may fail if cursor not initialized.

```python
if hasattr(self.main_window.full_timeline_graph, 'stop_cursor'):
    stop_cursor = self.main_window.full_timeline_graph.stop_cursor
    if stop_cursor and not stop_cursor.moving:  # ✅ Correct check
        stop_cursor.setValue(elapsed_time)
        stop_cursor.label.setFormat(f'Stop: {elapsed_time:.1f}s')
```

**Potential Issues**:
1. **Cursor not initialized**: `stop_cursor` is None
2. **`moving` attribute not set**: InfiniteLine may not have this attribute initially
3. **Live data disabled**: Check happens inside `if self.main_window.live_data_enabled` block

**Current Guard**: Only moves if `live_data_enabled=True`

### Issue #3: **Data Not Showing at All** 🔴

**Possible Root Causes**:

#### A. Hardware Not Returning Data
```python
# In _acquire_channel_spectrum():
raw_spectrum = usb.read_intensity()
if raw_spectrum is None:  # ❌ Returns None on failure
    logger.error(f"Failed to read spectrum for channel {channel}")
    return None
```
**Check**: Look for "Failed to read spectrum" errors in logs.

#### B. Calibration Not Completing
```python
# In _on_spectrum_acquired():
if (hasattr(self.data_mgr, 'ref_spectrum') and
    self.data_mgr.ref_spectrum is not None and
    hasattr(self.data_mgr, 'wave_data') and
    self.data_mgr.wave_data is not None):
    # Only calculate transmission if calibrated
```
**Check**: Verify `ref_spectrum` and `wave_data` exist after calibration.

#### C. Graph Update Logic
```python
# Transmission graph update:
if self.main_window.live_data_enabled:  # Must be True
    self.main_window.transmission_curves[channel_idx].setData(
        wavelengths,  # Must match spectrum length
        transmission  # Must match wavelengths length
    )
```
**Check**: Are wavelengths and transmission same length?

---

## Diagnostic Steps to Find Root Cause

### Step 1: Add Debug Logging

Add to `_on_spectrum_acquired()` in `main_simplified.py`:

```python
def _on_spectrum_acquired(self, data: dict):
    channel = data['channel']
    wavelength = data['wavelength']

    # DEBUG: Log data receipt
    logger.info(f"📊 Data received: Ch {channel.upper()}, wavelength={wavelength:.2f}nm")

    # DEBUG: Check full spectrum
    spectrum_intensity = data.get('full_spectrum', None)
    if spectrum_intensity is not None:
        logger.info(f"   Full spectrum: shape={spectrum_intensity.shape}, "
                   f"min={spectrum_intensity.min():.1f}, max={spectrum_intensity.max():.1f}")
    else:
        logger.warning(f"   ⚠️ NO full_spectrum in data!")

    # DEBUG: Check calibration data
    if hasattr(self.data_mgr, 'wave_data'):
        logger.info(f"   wave_data: shape={self.data_mgr.wave_data.shape}")
    else:
        logger.warning(f"   ⚠️ NO wave_data available!")

    # ... rest of method
```

### Step 2: Verify Cursor Initialization

Add to cursor movement section:

```python
if hasattr(self.main_window.full_timeline_graph, 'stop_cursor'):
    stop_cursor = self.main_window.full_timeline_graph.stop_cursor

    # DEBUG: Check cursor state
    logger.debug(f"Cursor state: exists={stop_cursor is not None}, "
                f"moving={getattr(stop_cursor, 'moving', 'NO ATTRIBUTE')}, "
                f"value={stop_cursor.value() if stop_cursor else 'N/A'}")

    if stop_cursor and not stop_cursor.moving:
        stop_cursor.setValue(elapsed_time)
```

### Step 3: Check Live Data Flag

Add at start of `_on_spectrum_acquired()`:

```python
logger.debug(f"Live data enabled: {self.main_window.live_data_enabled}")
```

### Step 4: Monitor Acquisition Loop

Add to `_acquisition_worker()` in `data_acquisition_manager.py`:

```python
for ch in channels:
    logger.info(f"🔄 Acquiring channel {ch.upper()}...")
    spectrum_data = self._acquire_channel_spectrum(ch)

    if spectrum_data:
        logger.info(f"   ✅ Got spectrum: {len(spectrum_data['intensity'])} points")
        processed = self._process_spectrum(ch, spectrum_data)
        logger.info(f"   ✅ Processed: wavelength={processed['wavelength']:.2f}nm")
    else:
        logger.error(f"   ❌ No data from {ch.upper()}")
```

---

## Expected vs Actual Behavior

### **Expected Behavior**:
1. Calibration completes → `wave_data` stored (1800 points)
2. Acquisition starts → 4 channels cycle continuously
3. Each acquisition:
   - Reads raw spectrum (2048 points)
   - Trims to match wave_data (1800 points)
   - Processes (dark, spectral, afterglow corrections)
   - Emits with full_spectrum (1800 points)
4. UI receives data:
   - Updates transmission plot (wavelengths vs transmission)
   - Updates raw data plot (wavelengths vs raw intensity)
   - Updates timeline graph (time vs peak wavelength)
   - Moves stop cursor to latest time point

### **Actual Behavior** (User Report):
- ❌ Raw live data "not working well"
- ❌ End cursor not following latest data

### **Most Likely Root Causes**:

1. **Wavelength array re-reading** (Issue #1)
   - Slows acquisition → appears frozen/laggy
   - Solution: Store indices, reuse

2. **Cursor initialization timing**
   - Cursor may not exist when first data arrives
   - Solution: Add defensive checks

3. **Live data flag disabled**
   - User may have toggled "Live Data" checkbox off
   - Solution: Verify checkbox state

4. **Calibration incomplete**
   - `wave_data` or `ref_spectrum` missing
   - Solution: Wait for calibration_complete signal

---

## Recommended Fixes

### Fix #1: Store Wavelength Indices (HIGH PRIORITY)

**File**: `Old software/core/data_acquisition_manager.py`

**Line 130** (in `_calibration_worker`):
```python
# Current:
wave_data = usb.read_wavelength()
wave_min_index = wave_data.searchsorted(MIN_WAVELENGTH)
wave_max_index = wave_data.searchsorted(MAX_WAVELENGTH)
self.wave_data = wave_data[wave_min_index:wave_max_index]

# Add:
self.wave_min_index = wave_min_index
self.wave_max_index = wave_max_index
```

**Line 435** (in `_acquire_channel_spectrum`):
```python
# Replace entire trimming section with:
if len(raw_spectrum) != len(self.wave_data):
    # Use stored indices from calibration
    raw_spectrum = raw_spectrum[self.wave_min_index:self.wave_max_index]
```

**Impact**: Eliminates 200ms+ overhead per cycle.

### Fix #2: Defensive Cursor Checks (MEDIUM PRIORITY)

**File**: `Old software/main_simplified.py`

**Line 404**:
```python
# Add more defensive checks:
if (hasattr(self.main_window.full_timeline_graph, 'stop_cursor') and
    self.main_window.full_timeline_graph.stop_cursor is not None):

    stop_cursor = self.main_window.full_timeline_graph.stop_cursor

    # Check moving attribute exists
    is_moving = getattr(stop_cursor, 'moving', False)

    if not is_moving:
        stop_cursor.setValue(elapsed_time)
        if hasattr(stop_cursor, 'label'):
            stop_cursor.label.setFormat(f'Stop: {elapsed_time:.1f}s')
```

### Fix #3: Add Diagnostic Logging (DEBUG)

Enable detailed logging to identify actual issue:

```python
# In main_simplified.py, at top of _on_spectrum_acquired():
if logger.isEnabledFor(logging.DEBUG):
    logger.debug(f"📊 Spectrum acquired: ch={channel}, "
                f"wl={wavelength:.2f}nm, "
                f"spectrum_shape={data.get('full_spectrum', np.array([])).shape}, "
                f"live_enabled={self.main_window.live_data_enabled}")
```

---

## Testing Plan

1. **Test Fix #1** (wavelength indices):
   - Apply fix
   - Run application
   - Check logs for "Trimming spectrum by length" warnings
   - Expected: No warnings, faster acquisition

2. **Test Fix #2** (cursor):
   - Start application
   - Watch stop cursor during live data
   - Expected: Cursor follows latest time point

3. **Test with Debug Logging**:
   - Enable DEBUG level logging
   - Capture full acquisition cycle
   - Look for:
     - ✅ "Spectrum acquired" messages
     - ✅ "Full spectrum: shape=(1800,)"
     - ❌ Any error messages

---

## Conclusion

**Data shape integrity is CORRECT** ✅ - arrays preserved throughout pipeline.

**Likely issues**:
1. **Performance bottleneck** from re-reading wavelength array every acquisition
2. **Cursor initialization** timing or attribute checks
3. **Live data flag** state or calibration completeness

**Recommended action**: Apply Fix #1 first (biggest impact), then add debug logging to identify remaining issues.
